#!/usr/bin/env python3
# FE render (pagina cristiana): voz de mujer con pausas, fondo relajante, subtitulos modernos,
# imagenes con zoom lento y fundidos.  Uso: python3 render_fe.py jobs/<id>/job.json salida.mp4
# job.json: job_id, titulo, tipo (oracion|historia|salmo), velocidad, fondo (relajante|ninguno),
#   texto_gancho (titulo en pantalla al inicio), imagenes: [b64], escenas: [{texto, audio_b64,
#   pausa, img, cierre}].  Escenas seguidas con el mismo img forman una toma con zoom continuo.
# audio_v >= 2 (opcional): cuida las pausas (recorta silencios internos largos de la voz, iguala el
#   volumen entre frases y varia un poco las pausas entre frases, como una persona).
# Subtitulos: modulo compartido subs_pro.py (mismo estilo moderno que Dinero con Historia y Variado).
import base64
import json
import math
import os
import subprocess
import sys
import wave
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subs_pro as S  # noqa: E402

W, H, FPS, SR = 1080, 1920, 30, 44100
NL = chr(10)
BS = chr(92)
LEAD = 0.5      # silencio inicial
TAIL = 2.2      # silencio final (el fondo se desvanece)
FADE = 0.7      # fundido de cada toma


def run(cmd):
    print(' '.join(str(c) for c in cmd[:7]), '...', flush=True)
    subprocess.run(cmd, check=True)


def duration(path):
    out = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                   '-of', 'csv=p=0', path])
    return float(out.decode().strip())


def leer_voz(b64, work, i, velocidad, calida=False):
    raw = '%s/v%02d.mp3' % (work, i)
    with open(raw, 'wb') as f:
        f.write(base64.b64decode(b64))
    filtro = ('silenceremove=start_periods=1:start_duration=0:start_threshold=-48dB,'
              'areverse,silenceremove=start_periods=1:start_duration=0:start_threshold=-48dB,areverse')
    if abs(velocidad - 1.0) > 0.01:
        filtro += ',atempo=%.3f' % velocidad
    if calida:
        filtro += ',highpass=f=75,bass=g=2.5:f=220,treble=g=-3.5:f=6500'
    datos = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', raw, '-af', filtro,
                                     '-f', 's16le', '-ar', str(SR), '-ac', '1', '-'])
    return np.frombuffer(datos, dtype='<i2').astype(np.float32) / 32768.0


def _db_frames(x, hop=441):
    n = len(x) // hop
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    fr = x[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(fr * fr, axis=1) + 1e-12)
    return 20.0 * np.log10(rms + 1e-9)


def reparar_pausas(x, max_sil=0.38, hop=441):
    # Recorta silencios internos largos que la voz sintetica mete donde una persona no pararia.
    # Devuelve (audio, lista de (segundo, duracion_antes, duracion_despues)).
    db = _db_frames(x, hop)
    if len(db) < 20:
        return x, []
    nivel = float(np.percentile(db, 92))
    umbral = max(nivel - 30.0, -58.0)
    silencio = db < umbral
    cortes = []
    i = 0
    n = len(db)
    while i < n:
        if silencio[i]:
            j = i
            while j < n and silencio[j]:
                j += 1
            dur = (j - i) * hop / float(SR)
            if i > 3 and j < n - 3 and dur > max_sil:
                cortes.append((i, j))
            i = j
        else:
            i += 1
    if not cortes:
        return x, []
    partes, pos, info = [], 0, []
    xf = int(0.012 * SR)
    for (i, j) in cortes:
        a, b = i * hop, j * hop
        quedan = int(max_sil * SR)
        mitad = quedan // 2
        izq_fin = a + mitad
        der_ini = b - (quedan - mitad)
        tramo = x[pos:izq_fin].copy()
        partes.append(tramo)
        pos = der_ini
        info.append((a / float(SR), (b - a) / float(SR), quedan / float(SR)))
    partes.append(x[pos:].copy())
    out = partes[0]
    for p in partes[1:]:
        if len(out) > xf and len(p) > xf:
            r = np.linspace(0.0, 1.0, xf, dtype=np.float32)
            mezcla = out[-xf:] * (1.0 - r) + p[:xf] * r
            out = np.concatenate([out[:-xf], mezcla, p[xf:]])
        else:
            out = np.concatenate([out, p])
    return out.astype(np.float32), info


def igualar_volumen(x, objetivo_db=-21.0):
    db = _db_frames(x)
    if len(db) < 5:
        return x
    activos = db[db > (float(np.percentile(db, 92)) - 25.0)]
    if len(activos) == 0:
        return x
    # nivel medio de la parte hablada
    actual = float(np.mean(activos))
    g = max(-6.0, min(6.0, objetivo_db - actual))
    return (x * (10.0 ** (g / 20.0))).astype(np.float32)


def respiracion(rng, dur=0.30, nivel=0.02):
    # Inhalacion suave (ruido filtrado) para que la voz suene a persona.
    n = int(dur * SR)
    ruido = rng.standard_normal(n).astype(np.float32)
    spec = np.fft.rfft(ruido)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    masc = np.clip((f - 600.0) / 400.0, 0, 1) * np.clip((4800.0 - f) / 1200.0, 0, 1)
    b = np.fft.irfft(spec * masc.astype(np.float32), n).astype(np.float32)
    b /= max(float(np.max(np.abs(b))), 1e-6)
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    env = np.sin(np.pi * np.power(t, 0.7)) ** 2
    return b * env * nivel


def habitacion(x, rng, humedo=0.17):
    # Reverberacion corta y calida de cuarto pequeno, como orar en voz baja en privado.
    n = int(0.6 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    ir = rng.standard_normal(n).astype(np.float32) * np.exp(-t / 0.085)
    ir[: int(0.012 * SR)] = 0.0
    spec = np.fft.rfft(ir)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    spec *= np.clip((5200.0 - f) / 2500.0, 0, 1).astype(np.float32)
    ir = np.fft.irfft(spec, n).astype(np.float32)
    ir /= math.sqrt(float(np.sum(ir * ir)) + 1e-9)
    m = len(x) + n
    L = 1 << (m - 1).bit_length()
    humedo_x = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)[: len(x)].astype(np.float32)
    return (0.92 * x + humedo * humedo_x).astype(np.float32)


def suavizar_bordes(v):
    n_in, n_out = int(0.02 * SR), int(0.09 * SR)
    if len(v) > n_in + n_out:
        v[:n_in] *= np.linspace(0.0, 1.0, n_in, dtype=np.float32)
        v[-n_out:] *= np.linspace(1.0, 0.0, n_out, dtype=np.float32)
    return v


def escribir_ass(path, escenas, tiempos, gancho, gancho_hasta):
    lineas = []
    for i, e in enumerate(escenas):
        ini, fin = tiempos[i]
        estilo = 'Cierre' if e.get('cierre') else 'Default'
        lineas += S.dialogos(e.get('texto', ''), ini, fin, estilo, 3, 22)
    if gancho and gancho_hasta > 0.5:
        t = (BS + 'N').join(S.envolver(S.limpiar(gancho), 20))
        lineas.append(('Dialogue: 1,%s,%s,Titulo,,0,0,0,,{' + BS + 'fad(450,550)}%s') % (
            S.ass_time(0.3), S.ass_time(gancho_hasta), t))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(S.cabecera(W, H) + NL.join(lineas) + NL)


def escribir_wav(path, x):
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    job_path, out_path = sys.argv[1], sys.argv[2]
    with open(job_path, encoding='utf-8') as f:
        job = json.load(f)
    work = 'work_render'
    os.makedirs(work, exist_ok=True)
    escenas = job['escenas']
    imagenes = job['imagenes']
    velocidad = float(job.get('velocidad', 1.0))

    # 1) linea de tiempo de la voz con pausas
    humanizar = bool(job.get('humanizar', False))  # sonido limpio por defecto (decision de Ferlyn 14 oct)
    audio_v = int(job.get('audio_v', 0) or 0)
    rng = np.random.default_rng(zlib.crc32(str(job.get('job_id', 'fe')).encode()))
    partes = [np.zeros(int(LEAD * SR), dtype=np.float32)]
    t = LEAD
    tiempos = []
    pausa_prev = LEAD
    informe = []
    for i, e in enumerate(escenas):
        v = leer_voz(e['audio_b64'], work, i, velocidad, calida=humanizar)
        if audio_v >= 2:
            v, cortes = reparar_pausas(v)
            for (seg, antes, despues) in cortes:
                informe.append('frase %d: silencio interno de %.2f s recortado a %.2f s (en %.1f s)' % (
                    i + 1, antes, despues, seg))
            v = igualar_volumen(v)
            n_in = int(0.008 * SR)
            if len(v) > 2 * n_in:
                v[:n_in] *= np.linspace(0.0, 1.0, n_in, dtype=np.float32)
                v[-n_in:] *= np.linspace(1.0, 0.0, n_in, dtype=np.float32)
        if humanizar:
            v = suavizar_bordes(v)
            if not e.get('cierre') and pausa_prev >= 0.8:
                b = respiracion(rng)
                z = partes[-1]
                nb, gap = len(b), int(0.07 * SR)
                if len(z) > nb + gap:
                    z[len(z) - nb - gap: len(z) - gap] += b
        dur = len(v) / float(SR)
        pausa = float(e.get('pausa', 1.0))
        if humanizar and not e.get('cierre'):
            pausa *= float(rng.uniform(0.88, 1.22))
        if audio_v >= 2 and not e.get('cierre'):
            # una persona no deja siempre el mismo silencio: varia un poco y respira mas tras frases largas
            pausa *= float(rng.uniform(0.9, 1.18))
            if len(str(e.get('texto', ''))) > 110:
                pausa += 0.12
            pausa = max(pausa, 0.14)
        tiempos.append((t, t + dur))
        partes.append(v)
        partes.append(np.zeros(int(pausa * SR), dtype=np.float32))
        t += dur + pausa
        pausa_prev = pausa
        informe.append('frase %d: voz %.2f s + pausa %.2f s' % (i + 1, dur, pausa))
    if audio_v >= 2:
        print('INFORME DE PAUSAS (audio_v=%d)' % audio_v)
        for linea in informe:
            print('  ' + linea)
    partes.append(np.zeros(int(TAIL * SR), dtype=np.float32))
    total = t + TAIL
    voz = np.concatenate(partes)
    if humanizar:
        voz = habitacion(voz, rng)
    escribir_wav('%s/voz_cruda.wav' % work, voz)
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', '%s/voz_cruda.wav' % work, '-af',
         'loudnorm=I=-16:TP=-1.5:LRA=7,aresample=44100', '%s/voz_f.wav' % work])
    total = duration('%s/voz_f.wav' % work)

    # 2) tomas: escenas consecutivas con la misma imagen
    tomas = []
    for i, e in enumerate(escenas):
        img = int(e.get('img', 0))
        if tomas and tomas[-1]['img'] == img:
            tomas[-1]['fin_idx'] = i
        else:
            tomas.append({'img': img, 'ini_idx': i, 'fin_idx': i})
    for k, tm in enumerate(tomas):
        tm['ini'] = 0.0 if k == 0 else tiempos[tm['ini_idx']][0] - 0.3
    for k, tm in enumerate(tomas):
        tm['fin'] = total if k == len(tomas) - 1 else tomas[k + 1]['ini']

    clips = []
    for k, tm in enumerate(tomas):
        d = tm['fin'] - tm['ini']
        path = '%s/i%02d.jpg' % (work, k)
        with open(path, 'wb') as f:
            f.write(base64.b64decode(imagenes[tm['img']]))
        frames = max(int(d * FPS), 1)
        if k % 2 == 0:
            z = '1+0.09*on/%d' % frames
        else:
            z = '1.09-0.09*on/%d' % frames
        f_out = max(d - FADE, 0.0)
        vf = ("crop='min(iw,ih*9/16)':ih,scale=2160:-2:flags=lanczos,"
              "zoompan=z='%s':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=%d:s=%dx%d:fps=%d,"
              "fade=t=in:st=0:d=%.2f,fade=t=out:st=%.2f:d=%.2f,format=yuv420p"
              ) % (z, frames, W, H, FPS, FADE, f_out, FADE)
        clip = '%s/c%02d.mp4' % (work, k)
        run(['ffmpeg', '-y', '-loglevel', 'error', '-i', path, '-vf', vf, '-an', '-t', '%.3f' % d,
             '-r', str(FPS), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', clip])
        clips.append(clip)
    lst = '%s/list.txt' % work
    with open(lst, 'w') as f:
        for c in clips:
            f.write("file '%s'" % os.path.basename(c) + NL)
    video = '%s/joined_v.mp4' % work
    run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
         '-c', 'copy', video])

    # 3) subtitulos modernos (modulo compartido)
    ass = '%s/subs.ass' % work
    gancho = S.limpiar(job.get('texto_gancho', '') or '')
    escribir_ass(ass, escenas, tiempos, gancho, min(3.5, tiempos[0][0] + 3.0))

    # 4) fondo relajante + mezcla final
    fondo = job.get('fondo', 'relajante')
    if fondo == 'relajante':
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from relax import synth_relax
        synth_relax('%s/musica.wav' % work, total + 1.0)
        graph = (
            '[2:a]aformat=channel_layouts=stereo,volume=%.2f,afade=t=in:d=1.5,'
            'afade=t=out:st=%.2f:d=2.2[m];'
            '[1:a]aresample=44100,aformat=channel_layouts=stereo,volume=1.15,asplit=2[v][sc];'
            '[m][sc]sidechaincompress=threshold=0.015:ratio=4:attack=60:release=1200[md];'
            '[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[out]'
        ) % (float(job.get('fondo_nivel', 0.40)), max(total - 2.4, 0.0))
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-i', '%s/voz_f.wav' % work,
               '-i', '%s/musica.wav' % work, '-filter_complex', graph + ';[0:v]ass=%s[vv]' % ass,
               '-map', '[vv]', '-map', '[out]']
    else:
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-i', '%s/voz_f.wav' % work,
               '-filter_complex', '[0:v]ass=%s[vv];[1:a]aformat=channel_layouts=stereo[out]' % ass,
               '-map', '[vv]', '-map', '[out]']
    run(cmd + ['-t', '%.2f' % total, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
               '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out_path])
    print('Duracion final: %.1f s' % duration(out_path))


if __name__ == '__main__':
    main()
