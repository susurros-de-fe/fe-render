#!/usr/bin/env python3
"""FE render de tarjetas (imagen con texto) para la pagina Susurros de Fe.
Uso: python3 render_tarjeta.py jobs/<id>/job.json salida.jpg
job.json: {job_id, tipo ('versiculo'|'frase'|'pregunta'), texto, referencia (opcional), imagen_b64, marca (opcional)}
Salida 1080x1350 (4:5, ideal para el feed de Facebook).
"""
import base64
import io
import json
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
SERIF_B = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
SERIF_I = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf'
SANS = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
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


def main():
    job_path, out_path = sys.argv[1], sys.argv[2]
    with open(job_path, encoding='utf-8') as f:
        job = json.load(f)
    texto = ' '.join(str(job['texto']).split())
    ref = ' '.join(str(job.get('referencia', '') or '').split())
    marca = str(job.get('marca', 'Susurros de Fe'))
    base = Image.open(io.BytesIO(base64.b64decode(job['imagen_b64']))).convert('RGB')
    img = cubrir(base, W, H)
    # oscurecer y viñeta suave para que el texto se lea
    oscuro = Image.new('RGB', (W, H), (0, 0, 0))
    img = Image.blend(img, oscuro, 0.42)
    vig = Image.new('L', (W, H), 0)
    dv = ImageDraw.Draw(vig)
    dv.ellipse((-W * 0.25, -H * 0.1, W * 1.25, H * 1.1), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    img = Image.composite(img, Image.blend(img, oscuro, 0.35), vig)
    draw = ImageDraw.Draw(img)
    # ajustar tamaño de letra al espacio disponible
    ancho = 860
    alto_max = 760
    tam = 84
    while tam >= 40:
        fuente = ImageFont.truetype(SERIF_B, tam)
        lineas = envolver(draw, texto, fuente, ancho)
        alto = len(lineas) * int(tam * 1.32)
        if alto <= alto_max and len(lineas) <= 11:
            break
        tam -= 4
    paso = int(tam * 1.32)
    alto = len(lineas) * paso
    extra = 90 if ref else 0
    y0 = (H - (alto + extra)) // 2 - 20
    # comillas decorativas para versiculos y frases
    if job.get('tipo') in ('versiculo', 'frase'):
        q = ImageFont.truetype(SERIF_B, 150)
        draw.text((W // 2, y0 - 85), '“', font=q, fill=GOLD, anchor='mm')
    y = y0
    for ln in lineas:
        draw.text((W // 2 + 3, y + 3), ln, font=fuente, fill=(0, 0, 0), anchor='ma')
        draw.text((W // 2, y), ln, font=fuente, fill=(255, 255, 255), anchor='ma')
        y += paso
    if ref:
        fr = ImageFont.truetype(SERIF_I, 46)
        draw.text((W // 2, y + 30), '— ' + ref, font=fr, fill=GOLD, anchor='ma')
    # marca de la pagina
    fm = ImageFont.truetype(SANS, 34)
    draw.line((W // 2 - 70, H - 150, W // 2 + 70, H - 150), fill=GOLD, width=3)
    draw.text((W // 2, H - 120), marca, font=fm, fill=(235, 235, 235), anchor='ma')
    img.save(out_path, 'JPEG', quality=92, optimize=True)
    print('Tarjeta lista:', out_path)


if __name__ == '__main__':
    main()
