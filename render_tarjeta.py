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

def render_clasico(job, out_path):
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
        img = degradado((10, 16, 34), (24, 40, 80))
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

# =====================================================================
# Diseno "pro" (Dinero con Historia y Variado): plantilla editorial limpia
# =====================================================================
import glob
import os

_FUENTES = {}

def buscar_fuente(*nombres):
    for n in nombres:
        for patron in ('/usr/share/fonts/**/' + n, '/usr/local/share/fonts/**/' + n):
            hall = glob.glob(patron, recursive=True)
            if hall:
                return hall[0]
    return None

def fuente(peso, tam):
    """peso: 'xb' (extrabold), 'b' (bold), 'sb' (semibold), 'm' (medium). Usa Inter si esta instalada; si no, DejaVu."""
    clave = (peso, tam)
    if clave in _FUENTES:
        return _FUENTES[clave]
    mapa = {
        'xb': ['Inter-ExtraBold.otf', 'Inter-ExtraBold.ttf', 'Inter-Bold.otf', 'Inter-Bold.ttf'],
        'b': ['Inter-Bold.otf', 'Inter-Bold.ttf'],
        'sb': ['Inter-SemiBold.otf', 'Inter-SemiBold.ttf', 'Inter-Bold.otf', 'Inter-Bold.ttf'],
        'm': ['Inter-Medium.otf', 'Inter-Medium.ttf', 'Inter-Regular.otf', 'Inter-Regular.ttf'],
    }
    ruta = buscar_fuente(*mapa[peso])
    if not ruta:
        ruta = SANS_B if peso in ('xb', 'b', 'sb') else SANS
    f = ImageFont.truetype(ruta, tam)
    _FUENTES[clave] = f
    return f

def grano(img, fuerza=0.035):
    ruido = Image.effect_noise((W, H), 70).convert('RGB')
    return Image.blend(img, ruido, fuerza)

def diagonal(c1, c2):
    base = Image.new('RGB', (W, H))
    px = base.load()
    for y in range(H):
        for x in range(0, W, 1):
            t = (y * 0.8 + x * 0.35) / (H * 0.8 + W * 0.35)
            px[x, y] = (int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t), int(c1[2] + (c2[2] - c1[2]) * t))
    return base

def texto_espaciado(draw, xy, txt, f, fill, sp=4, anchor='l'):
    x, y = xy
    total = sum(draw.textlength(c, font=f) + sp for c in txt) - sp
    if anchor == 'r':
        x -= total
    elif anchor == 'm':
        x -= total / 2
    for c in txt:
        draw.text((x, y), c, font=f, fill=fill)
        x += draw.textlength(c, font=f) + sp
    return total

def ajustar_pro(draw, texto, peso, tam_max, tam_min, ancho, alto_max, max_lin, inter=1.28):
    tam = tam_max
    while tam >= tam_min:
        f = fuente(peso, tam)
        lin = envolver(draw, texto, f, ancho)
        if len(lin) <= max_lin and len(lin) * int(tam * inter) <= alto_max and max(draw.textlength(l, font=f) for l in lin) <= ancho:
            return f, lin, int(tam * inter)
        tam -= 2
    f = fuente(peso, tam_min)
    return f, envolver(draw, texto, f, ancho), int(tam_min * inter)

def monograma(draw, x, y, d, marca, fondo, tinta):
    draw.ellipse((x, y, x + d, y + d), fill=fondo)
    ini = ''.join(p[0] for p in marca.split()[:2]).upper()
    draw.text((x + d / 2, y + d / 2 + 1), ini, font=fuente('xb', int(d * 0.42)), fill=tinta, anchor='mm')

def anillo(img, cx, cy, d, valor, color, pista=(255, 255, 255, 34), grosor=34):
    s = 3
    capa = Image.new('RGBA', (d * s, d * s), (0, 0, 0, 0))
    g = ImageDraw.Draw(capa)
    box = (grosor * s // 2, grosor * s // 2, d * s - grosor * s // 2, d * s - grosor * s // 2)
    g.arc(box, 0, 360, fill=pista, width=grosor * s)
    fin = -90 + 3.6 * max(1, min(100, valor))
    g.arc(box, -90, fin, fill=color + (255,), width=grosor * s)
    r = (d * s - grosor * s) / 2
    for ang in (-90, fin):
        px = d * s / 2 + r * math.cos(math.radians(ang))
        py = d * s / 2 + r * math.sin(math.radians(ang))
        g.ellipse((px - grosor * s / 2, py - grosor * s / 2, px + grosor * s / 2, py + grosor * s / 2), fill=color + (255,))
    capa = capa.resize((d, d), Image.LANCZOS)
    img.paste(capa, (cx - d // 2, cy - d // 2), capa)

MARGEN = 96
ANCHO = W - 2 * MARGEN

def render_pro(job, out_path):
    texto = ' '.join(str(job['texto']).split())
    ref = ' '.join(str(job.get('referencia', '') or '').split())
    cifra = ' '.join(str(job.get('cifra', '') or '').split())
    etiqueta = ' '.join(str(job.get('etiqueta', '') or '').split()).upper()
    tipo = job.get('tipo', 'dato')
    paleta = str(job.get('paleta', 'dinero'))
    marca = str(job.get('marca', 'Dinero con Historia'))
    valor = job.get('valor')
    semilla = str(job.get('job_id', texto))
    rng = random.Random(sum(ord(c) * (i + 1) for i, c in enumerate(semilla)))
    if paleta == 'dinero':
        return render_dinero(job, out_path, texto, ref, cifra, etiqueta, tipo, marca, valor, rng)
    return render_variado(job, out_path, texto, ref, cifra, etiqueta, tipo, marca, rng)

def cabecera(draw, marca, etiqueta, fondo_mono, tinta_mono, color_marca, color_et, outline_et):
    monograma(draw, MARGEN, 92, 64, marca, fondo_mono, tinta_mono)
    draw.text((MARGEN + 84, 124), marca, font=fuente('sb', 31), fill=color_marca, anchor='lm')
    if etiqueta:
        f = fuente('b', 24)
        w = int(sum(draw.textlength(c, font=f) + 4 for c in etiqueta)) + 52
        x1 = W - MARGEN
        draw.rounded_rectangle((x1 - w, 106, x1, 150), radius=22, outline=outline_et, width=2)
        texto_espaciado(draw, (x1 - w + 26, 117), etiqueta, f, color_et, sp=4)

def render_dinero(job, out_path, texto, ref, cifra, etiqueta, tipo, marca, valor, rng):
    c1, c2 = rng.choice([((6, 14, 32), (13, 38, 74)), ((7, 18, 28), (10, 52, 66)), ((12, 12, 30), (36, 32, 84))])
    ORO = (244, 195, 85)
    VERDE = (74, 210, 150)
    img = diagonal(c1, c2)
    brillo(img, W - 60, 90, 460, ORO, 46)
    brillo(img, 40, H - 120, 520, VERDE, 22)
    # arco grande, sutil, fuera de cuadro
    capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(capa)
    g.ellipse((W - 520, H - 700, W + 380, H + 200), outline=ORO + (26,), width=3)
    g.ellipse((W - 640, H - 820, W + 500, H + 320), outline=ORO + (14,), width=2)
    img.paste(capa, (0, 0), capa)
    img = grano(img, 0.03)
    draw = ImageDraw.Draw(img, 'RGBA')
    draw.rounded_rectangle((34, 34, W - 34, H - 34), radius=28, outline=ORO + (70,), width=2)
    cabecera(draw, marca, etiqueta, ORO, (14, 22, 44), (236, 240, 248), ORO, ORO + (150,))
    draw.line((MARGEN, 188, W - MARGEN, 188), fill=(255, 255, 255, 36), width=1)

    y = 250
    if tipo == 'mito':
        fm, lm, pm = ajustar_pro(draw, texto, 'sb', 64, 38, ANCHO, 330, 5)
        fr, lr, pr = ajustar_pro(draw, ref, 'b', 60, 36, ANCHO, 430, 8)
        total = 58 + len(lm) * pm + 56 + 52 + len(lr) * pr
        y = 190 + max(40, (1010 - total) // 2 - 10)
        draw.text((MARGEN, y), 'MITO', font=fuente('b', 30), fill=(255, 125, 125))
        yy = y + 58
        for ln in lm:
            draw.text((MARGEN, yy), ln, font=fm, fill=(226, 230, 240))
            w = draw.textlength(ln, font=fm)
            draw.line((MARGEN - 6, yy + pm * 0.5, MARGEN + w + 6, yy + pm * 0.5), fill=(255, 110, 110), width=6)
            yy += pm
        yy += 56
        draw.rounded_rectangle((MARGEN, yy, MARGEN + 8, yy + 10 + 0), radius=4, fill=VERDE)
        draw.text((MARGEN + 26, yy - 8), 'REALIDAD', font=fuente('b', 30), fill=VERDE)
        yy += 52
        for ln in lr:
            draw.text((MARGEN, yy), ln, font=fr, fill=(255, 255, 255))
            yy += pr
    else:
        if valor is not None:
            d = 470
            cy = y + 40 + d // 2
            anillo(img, W // 2, cy, d, float(valor), ORO)
            draw = ImageDraw.Draw(img, 'RGBA')
            if cifra:
                fc, lc, pc = ajustar_pro(draw, cifra, 'xb', 150, 70, 300, 200, 2, 1.0)
                tot = len(lc) * pc
                for i, ln in enumerate(lc):
                    draw.text((W // 2, cy - tot // 2 + i * pc + pc // 2), ln, font=fc, fill=(255, 255, 255), anchor='mm')
            y = cy + d // 2 + 64
        elif cifra:
            fc, lc, pc = ajustar_pro(draw, cifra, 'xb', 270, 96, ANCHO, 460, 2, 1.04)
            for i, ln in enumerate(lc):
                draw.text((MARGEN, y + i * pc), ln, font=fc, fill=ORO)
            y += len(lc) * pc + 18
            draw.rounded_rectangle((MARGEN, y, MARGEN + 120, y + 8), radius=4, fill=ORO)
            y += 48
        if tipo == 'frase':
            draw.text((MARGEN - 6, y - 40), '“', font=fuente('xb', 210), fill=ORO + (200,))
            y += 120
        disp = 1060 - y - (150 if ref else 0)
        ft, lt, pt = ajustar_pro(draw, texto, 'sb', 76 if not cifra and valor is None else 56, 36, ANCHO, max(disp, 260), 10)
        if not cifra and valor is None and tipo != 'frase':
            # texto principal sin cifra: centrar verticalmente en el area libre
            alto = len(lt) * pt + (80 if ref else 0)
            y = 190 + max(70, (1010 - alto) // 2 - 10)
            draw.rounded_rectangle((MARGEN, y - 56, MARGEN + 120, y - 48), radius=4, fill=ORO)
        for ln in lt:
            draw.text((MARGEN, y), ln, font=ft, fill=(255, 255, 255))
            y += pt
        if ref:
            y += 26
            draw.line((MARGEN, y, MARGEN + 56, y), fill=ORO, width=4)
            fr = fuente('m', 30)
            for ln in envolver(draw, ref, fr, ANCHO):
                y += 18
                draw.text((MARGEN, y), ln, font=fr, fill=(184, 196, 216))
                y += 36
    pie = 'Contenido educativo · No es asesoría financiera'
    draw.line((MARGEN, H - 150, W - MARGEN, H - 150), fill=(255, 255, 255, 36), width=1)
    draw.text((MARGEN, H - 104), pie, font=fuente('m', 27), fill=(150, 164, 188), anchor='lm')
    img.convert('RGB').save(out_path, 'JPEG', quality=93, optimize=True)
    print('Tarjeta lista:', out_path)

def render_variado(job, out_path, texto, ref, cifra, etiqueta, tipo, marca, rng):
    CREMA = (245, 240, 231)
    TINTA = (22, 26, 46)
    GRIS = (110, 112, 128)
    acento = rng.choice([(232, 72, 60), (0, 122, 128), (84, 72, 188), (28, 96, 196), (24, 136, 88), (214, 110, 20)])
    img = Image.new('RGB', (W, H), CREMA)
    img = grano(img, 0.025)
    draw = ImageDraw.Draw(img, 'RGBA')
    cabecera(draw, marca, etiqueta, TINTA, CREMA, TINTA, acento, acento + (255,))
    y = 224
    if tipo == 'mito':
        h1 = 330
        draw.rounded_rectangle((MARGEN, y, W - MARGEN, y + h1), radius=44, fill=(48, 50, 70))
        draw.text((MARGEN + 44, y + 38), 'MITO', font=fuente('b', 28), fill=(255, 150, 140))
        fm, lm, pm = ajustar_pro(draw, texto, 'sb', 60, 36, ANCHO - 88, h1 - 130, 4)
        yy = y + 96
        for ln in lm:
            draw.text((MARGEN + 44, yy), ln, font=fm, fill=(236, 236, 244))
            w = draw.textlength(ln, font=fm)
            draw.line((MARGEN + 40, yy + pm * 0.5, MARGEN + 48 + w, yy + pm * 0.5), fill=(255, 130, 120), width=5)
            yy += pm
        y += h1 + 28
        fr, lr, pr = ajustar_pro(draw, ref, 'sb', 58, 34, ANCHO - 88, 430, 8)
        h2 = max(300, 96 + len(lr) * pr + 56)
        draw.rounded_rectangle((MARGEN, y, W - MARGEN, y + h2), radius=44, fill=acento)
        draw.text((MARGEN + 44, y + 38), 'REALIDAD', font=fuente('b', 28), fill=(255, 255, 255, 200))
        yy = y + 96
        for ln in lr:
            draw.text((MARGEN + 44, yy), ln, font=fr, fill=(255, 255, 255))
            yy += pr
    elif cifra:
        h = 470
        draw.rounded_rectangle((MARGEN, y, W - MARGEN, y + h), radius=44, fill=acento)
        # forma decorativa clara dentro del bloque
        capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        g = ImageDraw.Draw(capa)
        g.ellipse((W - MARGEN - 360, y - 120, W - MARGEN + 120, y + 360), fill=(255, 255, 255, 26))
        mask = Image.new('L', (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle((MARGEN, y, W - MARGEN, y + h), radius=44, fill=255)
        img.paste(capa, (0, 0), Image.composite(capa.split()[3], Image.new('L', (W, H), 0), mask))
        draw = ImageDraw.Draw(img, 'RGBA')
        fc, lc, pc = ajustar_pro(draw, cifra, 'xb', 230, 90, ANCHO - 130, h - 90, 2, 1.0)
        tot = len(lc) * pc
        yy = y + h - 44 - tot
        for ln in lc:
            draw.text((MARGEN + 44, yy), ln, font=fc, fill=(255, 255, 255))
            yy += pc
        y += h + 56
        ft, lt, pt = ajustar_pro(draw, texto, 'sb', 58, 36, ANCHO, 1000 - y - (110 if ref else 0), 8)
        for ln in lt:
            draw.text((MARGEN, y), ln, font=ft, fill=TINTA)
            y += pt
        if ref:
            y += 20
            draw.text((MARGEN, y), ref, font=fuente('m', 29), fill=GRIS)
    else:
        h = 780
        draw.rounded_rectangle((MARGEN, y, W - MARGEN, y + h), radius=44, fill=acento)
        if tipo in ('pregunta', 'frase'):
            glifo = '?' if tipo == 'pregunta' else '“'
            draw.text((MARGEN + 46, y + (30 if tipo == 'pregunta' else 70)), glifo, font=fuente('xb', 220), fill=(255, 255, 255, 90))
        else:
            draw.rounded_rectangle((MARGEN + 50, y + 64, MARGEN + 50 + 96, y + 72), radius=4, fill=(255, 255, 255, 150))
            texto_espaciado(draw, (MARGEN + 50, y + 96), 'SABÍAS QUE', fuente('b', 28), (255, 255, 255, 200), sp=5)
        ft, lt, pt = ajustar_pro(draw, texto, 'xb', 74, 40, ANCHO - 100, h - 330, 9, 1.22)
        tot = len(lt) * pt
        yy = y + 250 + (h - 250 - 50 - tot) // 2
        for ln in lt:
            draw.text((MARGEN + 50, yy), ln, font=ft, fill=(255, 255, 255))
            yy += pt
        y += h + 40
        if ref:
            fr = fuente('m', 30)
            for ln in envolver(draw, ref, fr, ANCHO)[:2]:
                draw.text((MARGEN, y), ln, font=fr, fill=GRIS)
                y += 40
    draw.line((MARGEN, H - 150, W - MARGEN, H - 150), fill=TINTA + (40,), width=1)
    draw.text((MARGEN, H - 104), 'Datos y curiosidades', font=fuente('m', 27), fill=GRIS, anchor='lm')
    draw.text((W - MARGEN, H - 104), '@' + ''.join(marca.split()).lower(), font=fuente('sb', 27), fill=TINTA, anchor='rm')
    img.convert('RGB').save(out_path, 'JPEG', quality=93, optimize=True)
    print('Tarjeta lista:', out_path)

def main():
    job_path, out_path = sys.argv[1], sys.argv[2]
    with open(job_path, encoding='utf-8') as f:
        job = json.load(f)
    if job.get('imagen_b64') or str(job.get('paleta', 'fe')) == 'fe':
        render_clasico(job, out_path)
    else:
        render_pro(job, out_path)

if __name__ == '__main__':
    main()
