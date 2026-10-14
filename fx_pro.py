#!/usr/bin/env python3
# fx_pro.py - efectos profesionales compartidos (Fe, Variado, Dinero con Historia).
# Todo se dibuja con codigo: no gasta Cloudflare ni Kie.
#   capa_luz()   -> video corto en bucle: rayos de luz suaves + polvo flotando (se mezcla con 'screen')
#   sello_png()  -> sello de marca (nombre del canal con letras espaciadas y una linea fina)
#   sfx_bus()    -> sonido de diseno (campanas, swells, whooshes, golpes suaves) para MEZCLAR POR DEBAJO DE LA VOZ
#   graf_video() -> filtro ffmpeg de acabado: rayos + vineta + grano
# Paletas: 'fe' (dorado calido, sutil), 'variado' (rojo, dinamico), 'dinero' (azul/dorado, dinamico).
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SR = 44100

PALETAS = {
    'fe': {'luz': (255, 214, 140), 'sello': (232, 184, 109), 'nombre': 'SUSURROS DE FE', 'sfx': 'sutil'},
    'variado': {'luz': (255, 120, 120), 'sello': (255, 73, 56), 'nombre': 'VARIADO', 'sfx': 'dinamico'},
    'dinero': {'luz': (120, 190, 255), 'sello': (232, 184, 109), 'nombre': 'DINERO CON HISTORIA', 'sfx': 'dinamico'},
}


# ---------------------------------------------------------------- fuentes
def _fuente(tam, negrita=True):
    dirs = [os.path.expanduser('~/.fonts'), '/usr/local/share/fonts', '/usr/share/fonts',
            os.path.dirname(os.path.abspath(__file__))]
    nombres = ['BarlowCondensed-SemiBold.ttf', 'BarlowCondensed-Bold.ttf', 'Inter-SemiBold.ttf',
               'DejaVuSansCondensed-Bold.ttf', 'DejaVuSans-Bold.ttf']
    for d in dirs:
        for raiz, _, archivos in os.walk(d):
            for n in nombres:
                if n in archivos:
                    try:
                        return ImageFont.truetype(os.path.join(raiz, n), tam)
                    except Exception:
                        pass
    return ImageFont.load_default()


# ---------------------------------------------------------------- sello de marca
def sello_png(path, nombre, color, W=1080, H=1920, y_frac=0.905, alfa=0.82):
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = _fuente(40)
    texto = ' '.join(list(nombre.upper())).replace('   ', '    ')
    bb = d.textbbox((0, 0), texto, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x, y = (W - tw) / 2, H * y_frac
    sombra = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).text((x, y), texto, font=f, fill=(0, 0, 0, 200))
    sombra = sombra.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, sombra)
    d = ImageDraw.Draw(img)
    a = int(255 * alfa)
    d.text((x, y), texto, font=f, fill=color + (a,))
    d.line((W / 2 - 70, y + th + 22, W / 2 + 70, y + th + 22), fill=color + (a,), width=3)
    img.save(path)
    return path


# ---------------------------------------------------------------- capa de luz (rayos + polvo) en bucle
def capa_luz(path, color=(255, 214, 140), dur=10.0, w=360, h=640, fps=20, intensidad=1.0, polvo=46, seed=7):
    rng = np.random.default_rng(seed)
    n = int(dur * fps)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w * 0.62, -h * 0.12
    ang = np.arctan2(xx - cx, yy - cy)
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    caida = np.exp(-r / (h * 0.85)).astype(np.float32)
    rayos = []
    for _ in range(6):
        rayos.append((rng.uniform(5.0, 15.0), rng.uniform(0, 6.28), int(rng.integers(1, 3)) * (1 if rng.random() < 0.5 else -1),
                      rng.uniform(0.5, 1.0)))
    P = [(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.6, 2.4), rng.uniform(0.5, 2.5) * h / dur,
          rng.uniform(0, 6.28), int(rng.integers(1, 4))) for _ in range(polvo)]
    col = np.array(color, dtype=np.float32) / 255.0
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (w, h),
           '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-pix_fmt', 'yuv420p', path]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(n):
        t = k / float(fps)
        fase = 2 * math.pi * t / dur
        v = np.zeros((h, w), np.float32)
        for (f, ph, vel, amp) in rayos:
            v += amp * np.clip(0.5 + 0.5 * np.sin(ang * f + ph + fase * vel), 0, 1) ** 3
        v = v / len(rayos) * 2.2 * caida * (0.75 + 0.25 * math.sin(fase * 2))
        v = np.clip(v * 0.55 * intensidad, 0, 1)
        frame = v[..., None] * col[None, None, :]
        # polvo
        pol = Image.new('RGB', (w, h), (0, 0, 0))
        dp = ImageDraw.Draw(pol)
        for (x0, y0, rad, vy, ph, nn) in P:
            y = (y0 - vy * t) % h
            x = x0 + 8.0 * math.sin(fase * nn + ph)
            br = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(fase * 2 * nn + ph))
            c = tuple(int(255 * br * q) for q in col)
            dp.ellipse((x - rad, y - rad, x + rad, y + rad), fill=c)
        pol = pol.filter(ImageFilter.GaussianBlur(0.9))
        frame = np.clip(frame + np.asarray(pol, np.float32) / 255.0 * 0.9, 0, 1)
        pr.stdin.write((frame * 255).astype(np.uint8).tobytes())
    pr.stdin.close()
    pr.wait()
    return path


# ---------------------------------------------------------------- sonido de diseno
def _env(n, a=0.01, r=0.3):
    t = np.arange(n, dtype=np.float32) / SR
    e = np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))
    return e.astype(np.float32)


def campana(f, dur=2.4, vol=0.2):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    x = np.zeros(n, np.float32)
    for k, (m, a, r) in enumerate(((1.0, 1.0, 0.9), (2.01, 0.38, 0.55), (3.99, 0.16, 0.35), (5.4, 0.08, 0.22))):
        x += a * np.sin(2 * np.pi * f * m * t) * np.exp(-t / r)
    x *= np.minimum(1.0, t / 0.008)
    return (x / max(np.max(np.abs(x)), 1e-6) * vol).astype(np.float32)


def swell(dur=1.6, vol=0.10, f0=300.0, f1=1800.0, rng=None, subida=0.5):
    # ruido filtrado que sube y baja (aire / whoosh suave)
    rng = rng or np.random.default_rng(3)
    n = int(dur * SR)
    ruido = rng.standard_normal(n).astype(np.float32)
    out = np.zeros(n, np.float32)
    bloque = 2048
    estado = 0.0
    for i in range(0, n, bloque):
        p = i / float(n)
        q = p / subida if p < subida else 1 - (p - subida) / (1 - subida)
        fc = f0 * (f1 / f0) ** q
        a = 1 - math.exp(-2 * math.pi * fc / SR)
        seg = ruido[i:i + bloque]
        y = np.empty_like(seg)
        for j in range(len(seg)):
            estado += a * (seg[j] - estado)
            y[j] = estado
        out[i:i + bloque] = y
    t = np.linspace(0, 1, n, dtype=np.float32)
    env = np.where(t < subida, (t / subida) ** 1.6, ((1 - t) / (1 - subida)) ** 1.4).astype(np.float32)
    out *= env
    return (out / max(np.max(np.abs(out)), 1e-6) * vol).astype(np.float32)


def golpe(f=70.0, dur=0.5, vol=0.28):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    barrido = f * (1 + 2.2 * np.exp(-t / 0.06))
    x = np.sin(2 * np.pi * np.cumsum(barrido) / SR) * np.exp(-t / 0.16)
    return (x / max(np.max(np.abs(x)), 1e-6) * vol).astype(np.float32)


def chasquido(vol=0.12):
    n = int(0.05 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    x = np.sin(2 * np.pi * 2600 * t) * np.exp(-t / 0.012)
    return (x * vol).astype(np.float32)


def _poner(bus, x, t):
    i = int(t * SR)
    if i < 0:
        x = x[-i:]
        i = 0
    j = min(len(bus), i + len(x))
    if j > i:
        bus[i:j] += x[: j - i]


def sfx_bus(total, cortes, estilo='sutil', nivel=1.0, seed=11, inicio=0.15, fin=None, destacar=None):
    # total: duracion en s; cortes: segundos donde cambia la toma/escena; destacar: segundos con golpe (dato clave)
    rng = np.random.default_rng(seed)
    bus = np.zeros(int((total + 1.0) * SR), np.float32)
    if estilo == 'sutil':
        _poner(bus, campana(659.25, 3.0, 0.16 * nivel), inicio)
        _poner(bus, campana(987.77, 2.6, 0.08 * nivel), inicio + 0.18)
        for c in cortes:
            _poner(bus, swell(1.8, 0.09 * nivel, 260, 1500, rng), max(c - 0.9, 0))
            _poner(bus, campana(523.25, 2.2, 0.07 * nivel), c)
        f = (fin if fin is not None else total - 2.4)
        _poner(bus, campana(783.99, 3.2, 0.12 * nivel), f)
        _poner(bus, campana(1046.5, 3.0, 0.07 * nivel), f + 0.25)
    else:
        _poner(bus, golpe(62, 0.6, 0.30 * nivel), inicio)
        for c in cortes:
            _poner(bus, swell(0.55, 0.16 * nivel, 500, 5200, rng, subida=0.65), max(c - 0.42, 0))
            _poner(bus, golpe(80, 0.35, 0.20 * nivel), c)
        for d in (destacar or []):
            _poner(bus, chasquido(0.10 * nivel), d)
            _poner(bus, golpe(95, 0.3, 0.16 * nivel), d)
        f = (fin if fin is not None else total - 1.2)
        _poner(bus, campana(880, 2.0, 0.09 * nivel), f)
    return bus[: int(total * SR)]


def escribir_wav(path, x):
    import wave
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- acabado de video (filtros ffmpeg)
def filtro_acabado(entrada_video, entrada_luz, entrada_sello, salida, luz_opacidad=0.45, grano=6, vineta=True, fade_fin=None):
    # Devuelve un fragmento de filter_complex. entrada_* son etiquetas tipo '0:v'. El ASS se aplica DESPUES (letras nitidas).
    g = '[%s]setpts=PTS-STARTPTS[base0];' % entrada_video
    cur = 'base0'
    if entrada_luz:
        g += '[%s]scale=1080:1920:flags=bicubic,format=yuv420p[luz];[%s][luz]blend=all_mode=screen:all_opacity=%.2f[b1];' % (
            entrada_luz, cur, luz_opacidad)
        cur = 'b1'
    if vineta:
        g += '[%s]vignette=angle=0.55:mode=backward[b2];' % cur
        cur = 'b2'
    if grano:
        g += '[%s]noise=alls=%d:allf=t[b3];' % (cur, grano)
        cur = 'b3'
    if entrada_sello:
        g += '[%s]format=rgba[sel0];' % entrada_sello
        if fade_fin:
            g += '[sel0]fade=t=in:st=1.0:d=0.8:alpha=1,fade=t=out:st=%.2f:d=1.2:alpha=1[sel];' % fade_fin
        else:
            g += '[sel0]fade=t=in:st=1.0:d=0.8:alpha=1[sel];'
        g += '[%s][sel]overlay=0:0:format=auto[%s]' % (cur, salida)
    else:
        g += '[%s]null[%s]' % (cur, salida)
    return g


if __name__ == '__main__':
    # prueba rapida: python3 fx_pro.py fe /ruta/salida_dir
    est = sys.argv[1] if len(sys.argv) > 1 else 'fe'
    out = sys.argv[2] if len(sys.argv) > 2 else '.'
    os.makedirs(out, exist_ok=True)
    p = PALETAS[est]
    capa_luz(os.path.join(out, 'luz.mp4'), p['luz'])
    sello_png(os.path.join(out, 'sello.png'), p['nombre'], p['sello'])
    escribir_wav(os.path.join(out, 'sfx.wav'), sfx_bus(20.0, [6.0, 12.0], p['sfx']))
    print('ok')
