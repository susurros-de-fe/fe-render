#!/usr/bin/env python3
"""FE render (pagina cristiana): voz de mujer con pausas largas, fondo relajante, subtitulos suaves,
imagenes con zoom lento y fundidos. Cierre fijo "Comparte esto con alguien especial para ti".
Uso: python3 render_fe.py jobs/<id>/job.json salida.mp4

job.json:
  job_id, titulo, tipo ('oracion'|'historia'), velocidad (1.0), fondo ('relajante'|'ninguno'),
  texto_gancho (opcional, titulo en pantalla los primeros segundos),
  imagenes: [b64, ...]
  escenas: [{texto, audio_b64, pausa (segundos de silencio despues), img (indice en imagenes), cierre (bool)}]
Escenas consecutivas con el mismo `img` forman una sola toma con un zoom continuo.
"""
import array
import base64
import json
import math
import os
import subprocess
import sys
import wave
import zlib

import numpy as np

W, H, FPS, SR = 1080, 1920, 30, 44100
NL = chr(10)
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


def ass_time(t):
    t = max(t, 0.0)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return '%d:%02d:%05.2f' % (h, m, s)


def limpiar(t):
    return ' '.join(str(t).replace('{', '(').replace('}', ')').replace(chr(92), ' ').split())


def envolver(texto, ancho):
    lineas, cur = [], ''
    for p in texto.split():
        prueba = (cur + ' ' + p).strip()
        if cur and len(prueba) > ancho:
            lineas.append(cur)
            cur = p
        else:
            cur = prueba
    if cur:
        lineas.append(cur)
    return lineas


def trozos(texto, max_words=5, max_chars=26):
    out, cur = [], []
    for w in texto.split():
        prueba = ' '.join(cur + [w])
        if cur and (len(cur) >= max_words or len(prueba) > max_chars):
            out.append(' '.join(cur))
            cur = [w]
        else:
            cur.append(w)
        if w[-1:] in '.!?;:' and cur:
            out.append(' '.join(cur))
            cur = []
    if cur:
        out.append(' '.join(cur))
    return out


def peso(t):
    return len(t) + 4 * sum(t.count(c) for c in ',;:') + 8 * sum(t.count(c) for c in '.!?')


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


def respiracion(rng, dur=0.30, nivel=0.02):
    """Inhalacion suave (ruido filtrado) para que la voz suene a persona."""
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
    """Reverberacion corta y calida de cuarto pequeno, como orar en voz baja en privado."""
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


def escribir_ass(path, eventos, gancho, gancho_hasta):
    cab = NL.join([
        '[Script Info]', 'ScriptType: v4.00+', 'PlayResX: %d' % W, 'PlayResY: %d' % H, '',
        '[V4+ Styles]',
        'Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,'
        'Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,'
        'Alignment,MarginL,MarginR,MarginV,Encoding',
        'Style: Default,DejaVu Sans,66,&H00FFFFFF,&H000000FF,&H00000000,&H78000000,'
        '1,0,0,0,100,100,1,0,1,5,2,2,70,70,480,1',
        'Style: Cierre,DejaVu Sans,74,&H0037C8FF,&H000000FF,&H00000000,&H78000000,'
        '1,0,0,0,100,100,1,0,1,6,2,2,70,70,520,1',
        'Style: Titulo,DejaVu Sans,70,&H00DDF0FF,&H000000FF,&H00000000,&H96000000,'
        '1,0,0,0,100,100,2,0,1,6,3,8,80,80,300,1',
        '', '[Events]',
        'Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text', '',
    ])
    lineas = []
    for ini, fin, estilo, txt in eventos:
        lineas.append('Dialogue: 0,%s,%s,%s,,0,0,0,,{\\fad(250,250)}%s' % (
            ass_time(ini), ass_time(fin), estilo, txt))
    if gancho and gancho_hasta > 0.5:
        t = '\\N'.join(envolver(limpiar(gancho), 22))
        lineas.append('Dialogue: 1,%s,%s,Titulo,,0,0,0,,{\\fad(500,600)}%s' % (
            ass_time(0.3), ass_time(gancho_hasta), t))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(cab + NL.join(lineas) + NL)


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
    rng = np.random.default_rng(zlib.crc32(str(job.get('job_id', 'fe')).encode()))
    partes = [np.zeros(int(LEAD * SR), dtype=np.float32)]
    t = LEAD
    tiempos = []
    pausa_prev = LEAD
    for i, e in enumerate(escenas):
        v = leer_voz(e['audio_b64'], work, i, velocidad, calida=humanizar)
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
        tiempos.append((t, t + dur))
        partes.append(v)
        partes.append(np.zeros(int(pausa * SR), dtype=np.float32))
        t += dur + pausa
        pausa_prev = pausa
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

    # 3) subtitulos
    eventos = []
    for i, e in enumerate(escenas):
        ini, fin = tiempos[i]
        ps = trozos(limpiar(e.get('texto', '')))
        if not ps:
            continue
        estilo = 'Cierre' if e.get('cierre') else 'Default'
        if e.get('cierre'):
            ps = ['\\N'.join(envolver(limpiar(e.get('texto', '')), 20))]
        pesos = [max(peso(p), 1) for p in ps]
        tw = float(sum(pesos))
        c = ini
        for p, w in zip(ps, pesos):
            dd = (fin - ini) * w / tw
            eventos.append((c, min(c + dd + 0.15, fin + 0.5), estilo, p))
            c += dd
    ass = '%s/subs.ass' % work
    gancho = limpiar(job.get('texto_gancho', '') or '')
    escribir_ass(ass, eventos, gancho, min(3.5, tiempos[0][0] + 3.0))

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
