# FE con Remotion: dibuja la ilustracion animada (remotion_tsx del job) sobre los tiempos de la voz
# ya armada por render_fe.py. Devuelve un mp4 SIN audio; render_fe.py pone voz, musica, subtitulos y acabado.
# Si falla, render_fe.py usa respaldo() (fondo de luz suave) para que el video nunca se pierda.
import json
import os
import re
import subprocess

AQUI = os.path.dirname(os.path.abspath(__file__))
RM = os.path.join(AQUI, 'remotion')


def palabras(escenas, tiempos, total):
    # La voz de FE no trae el tiempo de cada palabra: se reparte cada frase por largo de palabra.
    out = []
    for e, (ini, fin) in zip(escenas, tiempos):
        ws = str(e.get('texto', '')).split()
        if not ws:
            continue
        tot = sum(len(w) + 1 for w in ws)
        d = max(fin - ini, 0.2)
        t = ini
        primera = True
        for w in ws:
            dd = d * (len(w) + 1) / tot
            out.append({'w': w, 't': round(t, 3), 'd': round(dd, 3), 'f': primera})
            primera = bool(re.search(r'[.!?]$', w))
            t += dd
    return {'dur': round(total, 3), 'words': out}


def render(job, escenas, tiempos, total, work, fps):
    os.makedirs(os.path.join(RM, 'public'), exist_ok=True)
    with open(os.path.join(RM, 'public', 'palabras.json'), 'w', encoding='utf-8') as f:
        json.dump(palabras(escenas, tiempos, total), f, ensure_ascii=False)
    with open(os.path.join(RM, 'src', 'Escena.tsx'), 'w', encoding='utf-8') as f:
        f.write(job['remotion_tsx'])
    if not os.path.isdir(os.path.join(RM, 'node_modules')):
        subprocess.run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=RM, check=True)
    out = os.path.abspath(os.path.join(work, 'rm_v.mp4'))
    subprocess.run(['npx', 'remotion', 'render', 'src/index.ts', 'Video', out, '--log=error', '--muted',
                    '--concurrency=2'], cwd=RM, check=True)
    print('Remotion FE listo', out, flush=True)
    return out


def respaldo(total, work, fps):
    # Fondo de luz suave (amanecer) con movimiento lento, por si Remotion falla y no hay imagenes.
    out = os.path.abspath(os.path.join(work, 'rm_resp.mp4'))
    src = ('gradients=s=1080x1920:c0=0x0f1e3d:c1=0x3b4f7a:c2=0xe0a15e:n=3:x0=540:y0=0:x1=540:y1=1920'
           ':speed=0.004:r=%d' % fps)
    try:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', src, '-t', '%.3f' % total,
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', out], check=True)
    except Exception:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                        'color=c=0x22324f:s=1080x1920:r=%d' % fps, '-t', '%.3f' % total,
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', out], check=True)
    return out
