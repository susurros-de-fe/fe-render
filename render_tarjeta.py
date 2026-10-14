#!/usr/bin/env python3
"""Render de tarjetas (imagen con texto) para las paginas de Facebook: Susurros de Fe, Dinero con Historia y Variado.
Uso: python3 render_tarjeta.py jobs/<id>/job.json salida.jpg
job.json:
  job_id, tipo, texto, referencia (opcional), marca (opcional)
  imagen_b64 (opcional): si viene, es el fondo (FE con FLUX). Si no viene, el fondo se dibuja aqui (costo 0 de IA).
  paleta ('fe' | 'dinero' | 'variado'): colores y estilo del fondo dibujado.
  cifra (opcional): numero o frase corta muy grande arriba del texto (ej. '4 %', '1923', '3 corazones').
  etiqueta (opcional): rotulo pequeno arriba (ej. 'DATO', 'MITO', 'PREGUNTA').
Tipos: versiculo, frase (con comillas), pregunta, dato (cifra + texto), mito (MITO tachado + REALIDAD: texto = mito, referencia = realidad).
Salida 1080x1350 (4:5, ideal para el feed de Facebook). Solo requiere Pillow.
"""
import base64
import io
import json
import math
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
SERIF_B = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
SERIF_I = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf'
SANS = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
SANS_B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
GOLD = (255, 214, 120)

# Paletas: (fondo arriba, fondo abajo, acento, acento 2)
PALETAS = {
    'dinero': [
        ((6, 18, 40), (12, 46, 84), (255, 205, 90), (70, 200, 140)),
        ((8, 24, 30), (10, 62, 66), (255, 205, 90), (120, 220, 200)),
        ((18, 14, 36), (44, 30, 90), (255, 205, 90), (160, 140, 255)),
    ],
    'variado': [
        ((22, 12, 56), (84, 24, 120), (255, 196, 61), (255, 107, 107)),
        ((6, 40, 70), (0, 110, 130), (255, 220, 90), (255, 140, 90)),
        ((60, 14, 40), (150, 40, 70), (255, 214, 120), (120, 220, 255)),
        ((10, 50, 40), (18, 110, 90), (255, 224, 110), (255, 150, 120)),
    ],
}


def cubrir(img, w, h):
    iw, ih = img.size
    k = max(w / iw, h / ih)
    img = img.resize((int(iw * k) + 1, int(ih * k) + 1), Image.LANCZOS)
    x = (img.size[0] - w) // 2
    y = (img.size[1] - h) // 2
    return img.crop((x, y, x + w, y + h))


def envolver(draw, texto, fuente, ancho):
    lineas, cur = [], ''
    for p in texto.split():
        prueba = (cur + ' ' + p).strip()
        if cur and draw.textlength(prueba, font=fuente) > ancho:
            lineas.append(cur)
            cur = p
        else:
            cur = prueba
    if cur:
        lineas.append(cur)
    return lineas


def degradado(c1, c2):
    base = Image.new('RGB', (1, H))
    px = base.load()
    for y in range(H):
        t = y / (H - 1)
        px[0, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    return base.resize((W, H))


def brillo(img, cx, cy, r, color, alfa):
    capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (alfa,))
    capa = capa.filter(ImageFilter.GaussianBlur(r * 0.45))
    img.paste(capa, (0, 0), capa)


def fondo_dinero(rng, pal):
    c1, c2, ac, ac2 = pal
    img = degradado(c1, c2)
    brillo(img, rng.randint(250, 830), rng.randint(180, 420), 380, ac, 55)
    capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    # cuadricula fina tipo grafico
    for x in range(0, W + 1, 90):
        d.line((x, 0, x, H), fill=(255, 255, 255, 12), width=1)
    for y in range(0, H + 1, 90):
        d.line((0, y, W, y), fill=(255, 255, 255, 12), width=1)
    # linea ascendente con ruido (grafico de crecimiento) en la parte baja
    n = 14
    puntos = []
    y = rng.randint(1000, 1150)
    for i in range(n + 1):
        x = int(W * i / n)
        y = max(560, min(1230, y - rng.randint(-40, 85)))
        puntos.append((x, y))
    area = puntos + [(W, H), (0, H)]
    d.polygon(area, fill=ac2 + (22,))
    d.line(puntos, fill=ac2 + (95,), width=5, joint='curve')
    # velas sutiles
    for i in range(n):
        x, yy = puntos[i]
        alto = rng.randint(30, 90)
        d.rectangle((x - 9, yy - alto // 2, x + 9, yy + alto // 2), fill=ac + (28,))
    # monedas
    for _ in range(5):
        cx, cy, r = rng.randint(80, 1000), rng.randint(60, 1290), rng.randint(40, 120)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ac + (60,), width=5)
        d.ellipse((cx - r * .7, cy - r * .7, cx + r * .7, cy + r * .7), outline=ac + (38,), width=3)
    capa = capa.filter(ImageFilter.GaussianBlur(1.2))
    img.paste(capa, (0, 0), capa)
    return img


def fondo_variado(rng, pal):
    c1, c2, ac, ac2 = pal
    img = degradado(c1, c2)
    brillo(img, rng.randint(150, 930), rng.randint(150, 500), 420, ac2, 60)
    brillo(img, rng.randint(150, 930), rng.randint(850, 1250), 380, ac, 45)
    capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    # puntos
    for gx in range(40, W, 70):
        for gy in range(40, H, 70):
            if rng.random() < 0.55:
                d.ellipse((gx - 3, gy - 3, gx + 3, gy + 3), fill=(255, 255, 255, 26))
    # formas geometricas
    for _ in range(7):
        cx, cy, r = rng.randint(0, W), rng.randint(0, H), rng.randint(60, 220)
        col = rng.choice([ac, ac2, (255, 255, 255)])
        forma = rng.choice(['c', 'a', 't'])
        if forma == 'c':
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col + (60,), width=rng.randint(4, 9))
        elif forma == 'a':
            d.arc((cx - r, cy - r, cx + r, cy + r), rng.randint(0, 180), rng.randint(200, 360), fill=col + (90,), width=10)
        else:
            a0 = rng.random() * math.tau
            pts = [(cx + r * math.cos(a0 + k * math.tau / 3), cy + r * math.sin(a0 + k * math.tau / 3)) for k in range(3)]
            d.polygon(pts, outline=col + (60,), width=6)
    capa = capa.filter(ImageFilter.GaussianBlur(1.0))
    img.paste(capa, (0, 0), capa)
    return img


def sombra_texto(draw, xy, txt, fuente, fill, anchor='ma', dx=3):
    x, y = xy
    draw.text((x + dx, y + dx), txt, font=fuente, fill=(0, 0, 0), anchor=anchor)
    draw.text((x, y), txt, font=fuente, fill=fill, anchor=anchor)


def ajustar(draw, texto, ruta, tam_max, tam_min, ancho, alto_max, max_lineas, inter=1.32):
    tam = tam_max
    while tam >= tam_min:
        fuente = ImageFont.truetype(ruta, tam)
        lineas = envolver(draw, texto, fuente, ancho)
        if (len(lineas) * int(tam * inter) <= alto_max and len(lineas) <= max_lineas
                and max(draw.textlength(l, font=fuente) for l in lineas) <= ancho):
            return fuente, lineas, int(tam * inter)
        tam -= 4
    fuente = ImageFont.truetype(ruta, tam_min)
    return fuente, envolver(draw, texto, fuente, ancho), int(tam_min * inter)


def main():
    job_path, out_path = sys.argv[1], sys.argv[2]
    with open(job_path, encoding='utf-8') as f:
        job = json.load(f)
    texto = ' '.join(str(job['texto']).split())
    ref = ' '.join(str(job.get('referencia', '') or '').split())
    cifra = ' '.join(str(job.get('cifra', '') or '').split())
    etiqueta = ' '.join(str(job.get('etiqueta', '') or '').split()).upper()
    tipo = job.get('tipo', 'frase')
    paleta = str(job.get('paleta', 'fe'))
    marca = str(job.get('marca', 'Susurros de Fe'))
    semilla = str(job.get('job_id', texto))
    rng = random.Random(sum(ord(c) * (i + 1) for i, c in enumerate(semilla)))

    acento = GOLD
    acento2 = GOLD
    if job.get('imagen_b64'):
        base = Image.open(io.BytesIO(base64.b64decode(job['imagen_b64']))).convert('RGB')
        img = cubrir(base, W, H)
        oscuro = Image.new('RGB', (W, H), (0, 0, 0))
        img = Image.blend(img, oscuro, 0.42)
        vig = Image.new('L', (W, H), 0)
        dv = ImageDraw.Draw(vig)
        dv.ellipse((-W * 0.25, -H * 0.1, W * 1.25, H * 1.1), fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(160))
        img = Image.composite(img, Image.blend(img, oscuro, 0.35), vig)
    else:
        lista = PALETAS.get(paleta, PALETAS['dinero'])
        pal = lista[rng.randrange(len(lista))]
        acento, acento2 = pal[2], pal[3]
        img = fondo_dinero(rng, pal) if paleta == 'dinero' else fondo_variado(rng, pal)
        # oscurecer un poco el centro para legibilidad
        oscuro = Image.new('RGB', (W, H), (0, 0, 0))
        img = Image.blend(img, oscuro, 0.18)
    draw = ImageDraw.Draw(img)

    ancho = 880
    fuente_txt_ruta = SERIF_B if paleta == 'fe' or tipo in ('frase', 'versiculo') else SANS_B

    # ---- bloques a apilar: etiqueta, cifra, texto, referencia ----
    bloques = []  # (alto, funcion dibujar(y))
    if etiqueta:
        fe_ = ImageFont.truetype(SANS_B, 34)
        tw = int(draw.textlength(etiqueta, font=fe_)) + 70

        def dib_etq(y, etiqueta=etiqueta, fe_=fe_, tw=tw):
            draw.rounded_rectangle((W // 2 - tw // 2, y, W // 2 + tw // 2, y + 66), radius=33, fill=acento)
            draw.text((W // 2, y + 33), etiqueta, font=fe_, fill=(15, 15, 25), anchor='mm')
        bloques.append((66 + 50, dib_etq))

    if cifra:
        fc, lc, pc = ajustar(draw, cifra, SANS_B, 230, 90, ancho, 420, 2, 1.1)

        def dib_cifra(y, fc=fc, lc=lc, pc=pc):
            for i, ln in enumerate(lc):
                sombra_texto(draw, (W // 2, y + i * pc), ln, fc, acento, dx=5)
        bloques.append((len(lc) * pc + 40, dib_cifra))

    if tipo == 'mito':
        fm, lm, pm = ajustar(draw, texto, SANS_B, 60, 36, ancho, 300, 5, 1.3)
        fr, lr, pr = ajustar(draw, ref, SANS_B, 66, 38, ancho, 420, 7, 1.3)

        def dib_mito(y):
            yy = y
            draw.text((W // 2, yy), 'MITO', font=ImageFont.truetype(SANS_B, 36), fill=(255, 120, 120), anchor='ma')
            yy += 60
            for ln in lm:
                sombra_texto(draw, (W // 2, yy), ln, fm, (235, 235, 235), dx=2)
                wln = draw.textlength(ln, font=fm)
                draw.line((W // 2 - wln / 2, yy + pm * 0.42, W // 2 + wln / 2, yy + pm * 0.42), fill=(255, 120, 120), width=5)
                yy += pm
            yy += 40
            draw.text((W // 2, yy), 'REALIDAD', font=ImageFont.truetype(SANS_B, 36), fill=acento2, anchor='ma')
            yy += 60
            for ln in lr:
                sombra_texto(draw, (W // 2, yy), ln, fr, (255, 255, 255))
                yy += pr
        bloques.append((60 + len(lm) * pm + 40 + 60 + len(lr) * pr, dib_mito))
    else:
        alto_disp = 700 - (230 if cifra else 0) - (116 if etiqueta else 0)
        alto_disp = max(alto_disp, 330)
        tam_max = 84 if not cifra else 66
        ft, lt, pt = ajustar(draw, texto, fuente_txt_ruta, tam_max, 38, ancho, alto_disp, 11)
        comillas = tipo in ('versiculo', 'frase')

        def dib_txt(y, ft=ft, lt=lt, pt=pt):
            yy = y
            if comillas:
                q = ImageFont.truetype(SERIF_B, 150)
                draw.text((W // 2, yy - 20), '“', font=q, fill=acento, anchor='mm')
                yy += 60
            for ln in lt:
                sombra_texto(draw, (W // 2, yy), ln, ft, (255, 255, 255))
                yy += pt
        bloques.append((len(lt) * pt + (60 if comillas else 0), dib_txt))
        if ref:
            fr_ = ImageFont.truetype(SERIF_I if paleta == 'fe' else SANS_B, 44 if paleta == 'fe' else 38)
            lr_ = envolver(draw, ('— ' if paleta == 'fe' else '') + ref, fr_, ancho)

            def dib_ref(y, fr_=fr_, lr_=lr_):
                for i, ln in enumerate(lr_):
                    draw.text((W // 2, y + 30 + i * 56), ln, font=fr_, fill=acento, anchor='ma')
            bloques.append((30 + len(lr_) * 56 + 30, dib_ref))

    total = sum(b[0] for b in bloques)
    y = max(120, (H - total) // 2 - 30)
    for alto, dib in bloques:
        dib(y)
        y += alto

    # marca de la pagina
    fm = ImageFont.truetype(SANS, 34)
    draw.line((W // 2 - 70, H - 150, W // 2 + 70, H - 150), fill=acento, width=3)
    draw.text((W // 2, H - 120), marca, font=fm, fill=(235, 235, 235), anchor='ma')
    img.save(out_path, 'JPEG', quality=92, optimize=True)
    print('Tarjeta lista:', out_path)


if __name__ == '__main__':
    main()
