import math
import os
import random
import re
import urllib.request
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from render_tarjeta import ANCHO, H, MARGEN, W, fuente, grano, monograma, texto_espaciado, anillo
EMB = {'bookmark-outline': ['m17 18-5-2.18L7 18V5h10m0-2H7a2 2 0 0 0-2 2v16l7-3 7 3V5a2 2 0 0 0-2-2'], 'comment-text-outline': ['M9 22a1 1 0 0 1-1-1v-3H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-6.1l-3.7 3.71c-.2.19-.45.29-.7.29zm1-6v3.08L13.08 16H20V4H4v12zM6 7h12v2H6zm0 4h9v2H6z'], 'check-bold': ['m9 20.42-6.21-6.21 2.83-2.83L9 14.77l9.88-9.89 2.83 2.83z'], 'close-thick': ['M20 6.91 17.09 4 12 9.09 6.91 4 4 6.91 9.09 12 4 17.09 6.91 20 12 14.91 17.09 20 20 17.09 14.91 12z'], 'cash': ['M3 6h18v12H3zm9 3a3 3 0 0 1 3 3 3 3 0 0 1-3 3 3 3 0 0 1-3-3 3 3 0 0 1 3-3M7 8a2 2 0 0 1-2 2v4a2 2 0 0 1 2 2h10a2 2 0 0 1 2-2v-4a2 2 0 0 1-2-2z'], 'lightbulb-on': ['M12 6a6 6 0 0 1 6 6c0 2.22-1.21 4.16-3 5.2V19a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-1.8c-1.79-1.04-3-2.98-3-5.2a6 6 0 0 1 6-6m2 15v1a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-1zm6-10h3v2h-3zM1 11h3v2H1zM13 1v3h-2V1zM4.92 3.5l2.13 2.14-1.42 1.41L3.5 4.93zm12.03 2.13 2.12-2.13 1.43 1.43-2.13 2.12z'], 'star-four-points': ['M12 1 9 9l-8 3 8 3 3 8 3-8 8-3-8-3z'], 'help-circle-outline': ['M11 18h2v-2h-2zm1-16A10 10 0 0 0 2 12a10 10 0 0 0 10 10 10 10 0 0 0 10-10A10 10 0 0 0 12 2m0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8m0-14a4 4 0 0 0-4 4h2a2 2 0 0 1 2-2 2 2 0 0 1 2 2c0 2-3 1.75-3 5h2c0-2.25 3-2.5 3-5a4 4 0 0 0-4-4'], 'chart-line': ['m16 11.78 4.24-7.33 1.73 1-5.23 9.05-6.51-3.75L5.46 19H22v2H2V3h2v14.54L9.5 8z'], 'format-quote-open': ['m10 7-2 4h3v6H5v-6l2-4zm8 0-2 4h3v6h-6v-6l2-4z']}
_NUM = re.compile('[-+]?(?:[0-9]*[.][0-9]+|[0-9]+[.]?)(?:[eE][-+]?[0-9]+)?')
_SVG = {}
def _arco(x1, y1, rx, ry, phi, fa, fs, x2, y2, out):
 if rx == 0 or ry == 0:
  out.append((x2, y2))
  return
 rx, ry = abs(rx), abs(ry)
 ph = math.radians(phi)
 c, s = math.cos(ph), math.sin(ph)
 dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
 xp, yp = c * dx + s * dy, -s * dx + c * dy
 lam = xp * xp / (rx * rx) + yp * yp / (ry * ry)
 if lam > 1:
  k = math.sqrt(lam)
  rx, ry = rx * k, ry * k
 num = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
 den = rx * rx * yp * yp + ry * ry * xp * xp
 co = math.sqrt(max(0.0, num / den)) if den else 0.0
 if fa == fs:
  co = -co
 cxp, cyp = co * rx * yp / ry, -co * ry * xp / rx
 cx, cy = c * cxp - s * cyp + (x1 + x2) / 2, s * cxp + c * cyp + (y1 + y2) / 2
 def ang(ux, uy, vx, vy):
  return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
 t1 = ang(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
 dt = ang((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
 if not fs and dt > 0:
  dt -= 2 * math.pi
 elif fs and dt < 0:
  dt += 2 * math.pi
 n = max(8, int(abs(dt) / (math.pi / 20)) + 1)
 for k in range(1, n + 1):
  t = t1 + dt * k / n
  px, py = rx * math.cos(t), ry * math.sin(t)
  out.append((c * px - s * py + cx, s * px + c * py + cy))
def _subpaths(d):
 n = len(d)
 st = {'i': 0}
 def skip():
  while st['i'] < n and d[st['i']] in ' ,' + chr(9) + chr(13) + chr(10):
   st['i'] += 1
 def num():
  skip()
  m = _NUM.match(d, st['i'])
  st['i'] = m.end()
  return float(m.group())
 def flag():
  skip()
  ch = d[st['i']]
  st['i'] += 1
  return ch == '1'
 subs, cur = [], []
 x = y = sx = sy = 0.0
 cmd = None
 lc = lq = None
 while True:
  skip()
  if st['i'] >= n:
   break
  if d[st['i']].isalpha():
   cmd = d[st['i']]
   st['i'] += 1
   if cmd in 'zZ':
    if cur:
     subs.append(cur)
    cur = []
    x, y = sx, sy
    lc = lq = None
    continue
  elif cmd is None:
   break
  rel = cmd.islower()
  c = cmd.upper()
  if c != 'M' and not cur:
   cur = [(x, y)]
  ox, oy = (x, y) if rel else (0.0, 0.0)
  if c == 'M':
   nx, ny = num() + ox, num() + oy
   if cur:
    subs.append(cur)
   cur = [(nx, ny)]
   x, y, sx, sy = nx, ny, nx, ny
   cmd = 'l' if rel else 'L'
   lc = lq = None
  elif c == 'L':
   x, y = num() + ox, num() + oy
   cur.append((x, y))
   lc = lq = None
  elif c == 'H':
   x = num() + ox
   cur.append((x, y))
   lc = lq = None
  elif c == 'V':
   y = num() + oy
   cur.append((x, y))
   lc = lq = None
  elif c in 'CS':
   if c == 'C':
    x1, y1 = num() + ox, num() + oy
   else:
    x1, y1 = (2 * x - lc[0], 2 * y - lc[1]) if lc else (x, y)
   x2, y2 = num() + ox, num() + oy
   nx, ny = num() + ox, num() + oy
   for k in range(1, 17):
    t = k / 16
    mt = 1 - t
    cur.append((mt ** 3 * x + 3 * mt * mt * t * x1 + 3 * mt * t * t * x2 + t ** 3 * nx,
       mt ** 3 * y + 3 * mt * mt * t * y1 + 3 * mt * t * t * y2 + t ** 3 * ny))
   lc, lq = (x2, y2), None
   x, y = nx, ny
  elif c in 'QT':
   if c == 'Q':
    x1, y1 = num() + ox, num() + oy
   else:
    x1, y1 = (2 * x - lq[0], 2 * y - lq[1]) if lq else (x, y)
   nx, ny = num() + ox, num() + oy
   for k in range(1, 13):
    t = k / 12
    mt = 1 - t
    cur.append((mt * mt * x + 2 * mt * t * x1 + t * t * nx, mt * mt * y + 2 * mt * t * y1 + t * t * ny))
   lq, lc = (x1, y1), None
   x, y = nx, ny
  elif c == 'A':
   rx, ry, rot = num(), num(), num()
   fa, fs = flag(), flag()
   nx, ny = num() + ox, num() + oy
   _arco(x, y, rx, ry, rot, fa, fs, nx, ny, cur)
   x, y = nx, ny
   lc = lq = None
  else:
   break
 if cur:
  subs.append(cur)
 return subs
def _svg_paths(nombre):
 nombre = re.sub(r'[^a-z0-9-]', '', str(nombre or '').lower())
 if not nombre:
  return None
 if nombre in _SVG:
  return _SVG[nombre]
 txt = None
 base = os.path.dirname(os.path.abspath(__file__))
 for carpeta in (os.environ.get('MDI_DIR'), os.path.join(base, 'iconos'), '/usr/local/lib/python3.13/dist-packages/material/templates/.icons/material'):
  if carpeta and os.path.exists(os.path.join(carpeta, nombre + '.svg')):
   with open(os.path.join(carpeta, nombre + '.svg'), encoding='utf-8') as f:
    txt = f.read()
   break
 if txt is None and not os.environ.get('SIN_RED'):
  for url in ('https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG/master/svg/%s.svg' % nombre,
     'https://cdn.jsdelivr.net/npm/@mdi/svg/svg/%s.svg' % nombre):
   try:
    txt = urllib.request.urlopen(url, timeout=12).read().decode('utf-8')
    break
   except Exception:
    txt = None
 ds = re.findall(' d="([^"]+)"', txt) if txt else EMB.get(nombre)
 _SVG[nombre] = ds or None
 return _SVG[nombre]
def mascara_icono(nombre, tam):
 ds = _svg_paths(nombre)
 if not ds:
  return None
 S = 3 if tam <= 520 else 2
 N = tam * S
 sc = N / 24.0
 m = Image.new('L', (N, N), 0)
 for d in ds:
  for sp in _subpaths(d):
   if len(sp) < 3:
    continue
   pts = [(px * sc, py * sc) for px, py in sp]
   x0 = max(0, int(min(p[0] for p in pts)) - 1)
   y0 = max(0, int(min(p[1] for p in pts)) - 1)
   x1 = min(N, int(max(p[0] for p in pts)) + 2)
   y1 = min(N, int(max(p[1] for p in pts)) + 2)
   if x1 <= x0 or y1 <= y0:
    continue
   t = Image.new('L', (x1 - x0, y1 - y0), 0)
   ImageDraw.Draw(t).polygon([(px - x0, py - y0) for px, py in pts], fill=255)
   m.paste(ImageChops.difference(m.crop((x0, y0, x1, y1)), t), (x0, y0))
 return m.resize((tam, tam), Image.LANCZOS)
def pegar_icono(img, nombre, cx, cy, tam, color, alfa=255, rot=0, respaldo=None):
 m = mascara_icono(nombre, tam)
 if m is None and respaldo:
  m = mascara_icono(respaldo, tam)
 if m is None:
  return False
 if rot:
  m = m.rotate(rot, resample=Image.BICUBIC, expand=True)
 if alfa < 255:
  m = m.point(lambda v: v * alfa // 255)
 x, y = int(cx - m.size[0] / 2), int(cy - m.size[1] / 2)
 img.paste(color, (x, y), m)
 return True
def palabras(txt):
 out = []
 for i, p in enumerate(str(txt).split('*')):
  for w in p.split():
   out.append((w, i % 2 == 1))
 return out
def lineas_ricas(draw, pal, f, ancho):
 esp = draw.textlength(' ', font=f)
 res, cur, cw = [], [], 0
 for w, e in pal:
  ww = draw.textlength(w, font=f)
  add = ww if not cur else esp + ww
  if cur and cw + add > ancho:
   res.append(cur)
   cur, cw = [(w, e)], ww
  else:
   cur.append((w, e))
   cw += add
 if cur:
  res.append(cur)
 return res
def ajustar_rico(draw, txt, peso, tmax, tmin, ancho, amax, maxl, inter=1.14):
 pal = palabras(txt)
 t = tmax
 while t >= tmin:
  f = fuente(peso, t)
  L = lineas_ricas(draw, pal, f, ancho)
  paso = int(t * inter)
  if len(L) <= maxl and len(L) * paso <= amax and all(draw.textlength(w, font=f) <= ancho for l in L for w, _ in l):
   return f, L, paso
  t -= 2
 f = fuente(peso, tmin)
 return f, lineas_ricas(draw, pal, f, ancho), int(tmin * inter)
def ancho_linea(draw, l, f):
 return sum(draw.textlength(w, font=f) for w, _ in l) + draw.textlength(' ', font=f) * (len(l) - 1)
def dibujar_rico(draw, x, y, L, f, paso, col, enf, centro=False, ancho=0, tachado=None):
 esp = draw.textlength(' ', font=f)
 for l in L:
  wt = ancho_linea(draw, l, f)
  cx = x + (ancho - wt) / 2 if centro else x
  x0 = cx
  for w, e in l:
   draw.text((cx, y), w, font=f, fill=enf if e else col)
   cx += draw.textlength(w, font=f) + esp
  if tachado:
   draw.line((x0 - 4, y + paso * 0.56, x0 + wt + 4, y + paso * 0.56), fill=tachado, width=max(4, int(f.size / 11)))
  y += paso
 return y
def alto_rico(L, paso):
 return len(L) * paso
DINERO = [
 dict(c1=(6, 14, 32), c2=(14, 40, 78), acc=(244, 195, 85), acc2=(74, 210, 150)),
 dict(c1=(7, 18, 28), c2=(10, 54, 68), acc=(244, 195, 85), acc2=(90, 214, 196)),
 dict(c1=(12, 12, 30), c2=(38, 32, 88), acc=(244, 195, 85), acc2=(120, 220, 170)),
]
VARIADO = [
 dict(c1=(240, 84, 72), c2=(190, 36, 74), acc=(255, 228, 120), acc2=(255, 255, 255)),
 dict(c1=(0, 132, 146), c2=(0, 76, 112), acc=(255, 228, 120), acc2=(255, 255, 255)),
 dict(c1=(98, 74, 214), c2=(52, 38, 152), acc=(120, 255, 214), acc2=(255, 255, 255)),
 dict(c1=(34, 104, 226), c2=(14, 54, 150), acc=(255, 214, 102), acc2=(255, 255, 255)),
 dict(c1=(24, 156, 100), c2=(8, 90, 72), acc=(255, 238, 140), acc2=(255, 255, 255)),
 dict(c1=(255, 132, 34), c2=(212, 66, 22), acc=(255, 248, 200), acc2=(255, 255, 255)),
 dict(c1=(246, 241, 232), c2=(234, 226, 212), acc=(232, 72, 60), acc2=(28, 96, 196), claro=True),
]
BLANCO = (255, 255, 255)
TINTA = (22, 26, 46)
def elegir_tema(job, lista):
 jid = str(job.get('job_id', ''))
 m = re.search('([0-9]{8})-([0-9]{2})([0-9]{2})', jid)
 if job.get('tema') is not None and str(job['tema']).isdigit():
  return lista[int(job['tema']) % len(lista)]
 if m:
  ord_dia = int(m.group(1)[4:6]) * 31 + int(m.group(1)[6:8])
  franja = int(m.group(2)) // 3
  return lista[(ord_dia * 2 + franja) % len(lista)]
 return lista[sum(ord(c) for c in jid) % len(lista)]
def gradiente(c1, c2):
 base = Image.new('RGB', (48, 60))
 px = base.load()
 for y in range(60):
  for x in range(48):
   t = (y * 0.8 + x * 0.35) / (59 * 0.8 + 47 * 0.35)
   px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
 return base.resize((W, H), Image.BICUBIC)
def resplandor(img, cx, cy, r, color, alfa):
 capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
 ImageDraw.Draw(capa).ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (alfa,))
 capa = capa.filter(ImageFilter.GaussianBlur(r * 0.45))
 img.paste(capa, (0, 0), capa)
def sombra(img, caja, radio, alfa=60, desv=14, blur=22):
 capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
 x0, y0, x1, y1 = caja
 ImageDraw.Draw(capa).rounded_rectangle((x0, y0 + desv, x1, y1 + desv), radius=radio, fill=(10, 20, 50, alfa))
 capa = capa.filter(ImageFilter.GaussianBlur(blur))
 img.paste(capa, (0, 0), capa)
class Ctx:
 pass
def preparar(job, paleta):
 c = Ctx()
 c.paleta = paleta
 c.dinero = paleta == 'dinero'
 c.t = elegir_tema(job, DINERO if c.dinero else VARIADO)
 c.claro = bool(c.t.get('claro'))
 c.tx = TINTA if c.claro else BLANCO
 c.mu = (102, 106, 124) if c.claro else ((176, 190, 212) if c.dinero else (255, 255, 255))
 c.mu_a = 255 if (c.claro or c.dinero) else 205
 c.acc, c.acc2 = c.t['acc'], c.t['acc2']
 c.mal = (255, 125, 125) if not c.claro else (214, 56, 48)
 c.bien = c.acc2 if c.dinero else ((24, 150, 96) if c.claro else (255, 255, 255))
 c.tinta_chip = (14, 22, 44) if not c.claro else BLANCO
 c.chip_fill = c.acc if not c.claro else TINTA
 c.rng = random.Random(sum(ord(ch) * (i + 1) for i, ch in enumerate(str(job.get('job_id', job.get('texto', ''))))))
 c.marca = str(job.get('marca', 'Dinero con Historia' if c.dinero else 'Variado'))
 c.icono = str(job.get('icono', '') or '')
 c.dy = 0
 c.fin = 0
 c.defecto = 'cash' if c.dinero else 'lightbulb-on'
 return c
def panel(img, draw, c, caja, radio=34, tinte=None, borde=None):
 if c.claro:
  sombra(img, caja, radio)
  draw = ImageDraw.Draw(img, 'RGBA')
  draw.rounded_rectangle(caja, radius=radio, fill=BLANCO + (255,), outline=(0, 0, 0, 18), width=2)
  if tinte:
   draw.rounded_rectangle((caja[0], caja[1], caja[0] + 12, caja[3]), radius=6, fill=tinte + (255,))
 else:
  fill = (255, 255, 255, 26) if not tinte else tinte + (34,)
  draw.rounded_rectangle(caja, radius=radio, fill=fill, outline=(borde or tinte or BLANCO) + (70 if tinte else 44,), width=2)
 return draw
def fondo(job, c):
 img = gradiente(c.t['c1'], c.t['c2'])
 if c.dinero:
  resplandor(img, W - 60, 90, 460, c.acc, 46)
  resplandor(img, 40, H - 120, 520, c.acc2, 22)
 elif not c.claro:
  resplandor(img, W - 120, 160, 420, (255, 255, 255), 38)
  resplandor(img, 60, H - 160, 520, (0, 0, 0), 46)
 else:
  resplandor(img, W - 100, 140, 420, c.acc, 22)
  resplandor(img, 60, H - 200, 460, c.acc2, 12)
 capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
 g = ImageDraw.Draw(capa)
 col = c.acc if (c.dinero or c.claro) else BLANCO
 g.ellipse((W - 520, H - 700, W + 380, H + 200), outline=col + (28,), width=3)
 g.ellipse((W - 650, H - 830, W + 510, H + 330), outline=col + (16,), width=2)
 img.paste(capa, (0, 0), capa)
 wm = BLANCO if (not c.dinero and not c.claro) else c.acc
 alfa = 30 if c.dinero else (40 if not c.claro else 30)
 pegar_icono(img, c.icono, W - 330, H - 500, 640, wm, alfa, rot=-6, respaldo=c.defecto)
 img = grano(img, 0.028)
 return img
def cabecera(draw, c, etiqueta):
 mono_fondo = c.acc if (c.dinero or c.claro) else BLANCO
 mono_tinta = (14, 22, 44) if c.dinero else (c.t['c1'] if not c.claro else BLANCO)
 if c.claro:
  mono_fondo, mono_tinta = TINTA, BLANCO
 monograma(draw, MARGEN, 92, 64, c.marca, mono_fondo, mono_tinta)
 draw.text((MARGEN + 84, 124), c.marca, font=fuente('sb', 31), fill=c.tx, anchor='lm')
 if etiqueta:
  f = fuente('b', 24)
  w = int(sum(draw.textlength(ch, font=f) + 4 for ch in etiqueta)) + 52
  x1 = W - MARGEN
  draw.rounded_rectangle((x1 - w, 104, x1, 150), radius=23, fill=c.chip_fill)
  texto_espaciado(draw, (x1 - w + 26, 115), etiqueta, f, c.tinta_chip, sp=4)
def pie(img, draw, c, cta, pregunta=False):
 ln = c.tx + (40,)
 draw.line((MARGEN, H - 150, W - MARGEN, H - 150), fill=ln, width=1)
 if c.dinero:
  izq = 'Educativo · No es asesoría financiera'
 else:
  izq = '@' + ''.join(c.marca.split()).lower()
 draw.text((MARGEN, H - 104), izq, font=fuente('m', 26), fill=c.mu + (c.mu_a,), anchor='lm')
 f = fuente('b', 25)
 cta = (cta or '').upper()
 w = int(sum(draw.textlength(ch, font=f) + 3 for ch in cta))
 x1 = W - MARGEN
 texto_espaciado(draw, (x1 - w, H - 116), cta, f, c.acc if (c.dinero or c.claro) else BLANCO, sp=3)
 pegar_icono(img, 'comment-text-outline' if pregunta else 'bookmark-outline', x1 - w - 36, H - 104, 40, c.acc if (c.dinero or c.claro) else BLANCO, 255)
def hook_bloque(draw, c, hook, y, amax, tmax=84, tmin=46, maxl=4):
 f, L, paso = ajustar_rico(draw, hook, 'xb', tmax, tmin, ANCHO, amax, maxl, 1.12)
 dibujar_rico(draw, MARGEN, y, L, f, paso, c.tx, c.acc)
 return y + alto_rico(L, paso)
def insignia(img, c, cx, cy, d, nombre=None):
 capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
 g = ImageDraw.Draw(capa)
 g.ellipse((cx - d // 2, cy - d // 2, cx + d // 2, cy + d // 2), fill=(c.acc if (c.dinero or c.claro) else BLANCO) + (40,), outline=(c.acc if (c.dinero or c.claro) else BLANCO) + (150,), width=3)
 img.paste(capa, (0, 0), capa)
 pegar_icono(img, nombre or c.icono, cx, cy, int(d * 0.56), c.acc if (c.dinero or c.claro) else BLANCO, 255, respaldo=c.defecto)
def limpio(v, n=None):
 s = ' '.join(str(v or '').split())
 return s[:n] if n else s
def f_dato(img, draw, c, job):
 hook = limpio(job.get('hook')) or limpio(job.get('etiqueta')) or 'Dato'
 cifra, texto, ref = limpio(job.get('cifra')), limpio(job.get('texto')), limpio(job.get('fuente') or job.get('referencia'))
 valor = job.get('valor')
 Y0, Y1 = 236 + c.dy, 1150
 ft, lt, pt = ajustar_rico(draw, texto, 'sb', 46, 32, ANCHO, 330, 6, 1.28)
 alto_t = alto_rico(lt, pt)
 for tam in (84, 76, 68, 60, 52, 46):
  fh, lh, ph = ajustar_rico(draw, hook, 'xb', tam, tam, ANCHO, 400, 4, 1.12)
  if len(lh) <= 4:
   break
 alto_h = alto_rico(lh, ph)
 alto_ref = 56 if ref else 0
 zona_stat = (Y1 - Y0) - alto_h - alto_t - alto_ref - 130
 stat_h = max(260, min(440, zona_stat))
 total = alto_h + 40 + stat_h + 40 + alto_t + alto_ref
 y = Y0 + max(0, (Y1 - Y0 - total) // 3)
 y = hook_bloque(draw, c, hook, y, 400, tmax=fh.size, tmin=fh.size, maxl=4) + 40
 cy = y + stat_h // 2
 if valor is not None and cifra:
  d = min(stat_h, 400)
  anillo(img, MARGEN + d // 2, cy, d, float(valor), c.acc, pista=(255, 255, 255, 40 if not c.claro else 30), grosor=34)
  draw = ImageDraw.Draw(img, 'RGBA')
  fc, lc, pc = ajustar_rico(draw, cifra, 'xb', 120, 56, d - 120, 160, 2, 1.0)
  tot = len(lc) * pc
  for i, ln in enumerate(lc):
   draw.text((MARGEN + d // 2, cy - tot // 2 + i * pc + pc // 2), ' '.join(w for w, _ in ln), font=fc, fill=c.tx, anchor='mm')
  insignia(img, c, W - MARGEN - 150, cy, 290)
 elif cifra:
  fc, lc, pc = ajustar_rico(draw, cifra, 'xb', 260, 90, ANCHO - 330, stat_h, 2, 1.0)
  tot = len(lc) * pc
  yy = cy - tot // 2
  for ln in lc:
   draw.text((MARGEN, yy), ' '.join(w for w, _ in ln), font=fc, fill=c.acc)
   yy += pc
  insignia(img, c, W - MARGEN - 140, cy, 270)
 else:
  insignia(img, c, W // 2, cy, 280)
 draw = ImageDraw.Draw(img, 'RGBA')
 y = y + stat_h + 40
 draw.rounded_rectangle((MARGEN, y - 22, MARGEN + 110, y - 15), radius=4, fill=c.acc)
 y = dibujar_rico(draw, MARGEN, y + 6, lt, ft, pt, c.tx, c.acc)
 if ref:
  draw.text((MARGEN, y + 18), 'Fuente: ' + ref, font=fuente('m', 27), fill=c.mu + (c.mu_a,))
  y += 50
 c.fin = y
 return draw
def f_mito(img, draw, c, job):
 hook = limpio(job.get('hook')) or 'Te lo contaron mal'
 mito, real = limpio(job.get('texto')), limpio(job.get('referencia'))
 Y0, Y1 = 236 + c.dy, 1150
 fh, lh, ph = ajustar_rico(draw, hook, 'xb', 74, 46, ANCHO, 280, 3, 1.12)
 y = Y0
 y = dibujar_rico(draw, MARGEN, y, lh, fh, ph, c.tx, c.acc) + 34
 libre = Y1 - y - 28
 fm, lm, pm = ajustar_rico(draw, mito, 'sb', 52, 34, ANCHO - 100, 230, 4, 1.22)
 fr, lr, pr = ajustar_rico(draw, real, 'b', 50, 32, ANCHO - 100, 400, 8, 1.24)
 h1 = 96 + alto_rico(lm, pm) + 36
 h2 = 96 + alto_rico(lr, pr) + 40
 if h1 + h2 > libre:
  sobra = h1 + h2 - libre
  fr, lr, pr = ajustar_rico(draw, real, 'b', 44, 30, ANCHO - 100, max(180, alto_rico(lr, pr) - sobra), 9, 1.22)
  h2 = 96 + alto_rico(lr, pr) + 40
 caja1 = (MARGEN, y, W - MARGEN, y + h1)
 draw = panel(img, draw, c, caja1, 34, c.mal, c.mal)
 draw.ellipse((MARGEN + 36, y + 26, MARGEN + 36 + 44, y + 26 + 44), fill=c.mal)
 pegar_icono(img, 'close-thick', MARGEN + 58, y + 48, 30, BLANCO if not c.claro else BLANCO, 255)
 draw = ImageDraw.Draw(img, 'RGBA')
 texto_espaciado(draw, (MARGEN + 96, y + 32), 'MITO', fuente('b', 28), c.mal, sp=5)
 dibujar_rico(draw, MARGEN + 50, y + 90, lm, fm, pm, c.tx if not c.claro else c.tx, c.acc, tachado=c.mal)
 y += h1 + 28
 caja2 = (MARGEN, y, W - MARGEN, y + h2)
 draw = panel(img, draw, c, caja2, 34, c.bien, c.bien)
 draw.ellipse((MARGEN + 36, y + 26, MARGEN + 36 + 44, y + 26 + 44), fill=c.bien)
 pegar_icono(img, 'check-bold', MARGEN + 58, y + 48, 30, (14, 22, 44) if (c.dinero or not c.claro) else BLANCO, 255)
 draw = ImageDraw.Draw(img, 'RGBA')
 texto_espaciado(draw, (MARGEN + 96, y + 32), 'REALIDAD', fuente('b', 28), c.bien if (c.dinero or c.claro) else BLANCO, sp=5)
 dibujar_rico(draw, MARGEN + 50, y + 90, lr, fr, pr, c.tx, c.acc)
 c.fin = y + h2
 return draw
def f_lista(img, draw, c, job):
 hook = limpio(job.get('hook')) or limpio(job.get('texto'))
 items = [limpio(i, 120) for i in (job.get('items') or []) if limpio(i)][:4]
 cierre = limpio(job.get('texto')) if job.get('hook') else ''
 ref = limpio(job.get('fuente') or job.get('referencia'))
 Y0, Y1 = 236 + c.dy, 1150
 fh, lh, ph = ajustar_rico(draw, hook, 'xb', 76, 46, ANCHO, 300, 4, 1.12)
 y = dibujar_rico(draw, MARGEN, Y0, lh, fh, ph, c.tx, c.acc) + 38
 extra = (84 if cierre else 0) + (44 if ref else 0)
 libre = Y1 - y - extra
 n = max(1, len(items))
 for tam in (46, 42, 38, 34, 30):
  filas = [ajustar_rico(draw, it, 'sb', tam, tam, ANCHO - 190, 400, 5, 1.22) for it in items]
  alturas = [max(116, alto_rico(f[1], f[2]) + 52) for f in filas]
  if sum(alturas) + 22 * (n - 1) <= libre:
   break
 sep = 22
 for k, (f, L, paso) in enumerate(filas):
  h = alturas[k]
  draw = panel(img, draw, c, (MARGEN, y, W - MARGEN, y + h), 30)
  cx, cy = MARGEN + 70, y + h // 2
  draw.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=c.acc if (c.dinero or c.claro) else BLANCO)
  draw.text((cx, cy + 1), str(k + 1), font=fuente('xb', 42), fill=(14, 22, 44) if not c.claro else BLANCO, anchor='mm')
  tot = alto_rico(L, paso)
  dibujar_rico(draw, MARGEN + 132, cy - tot // 2 + 3, L, f, paso, c.tx, c.acc)
  y += h + sep
 y -= sep
 if cierre:
  y += 30
  fc, lc, pc = ajustar_rico(draw, cierre, 'b', 36, 28, ANCHO, 90, 2, 1.25)
  draw.rounded_rectangle((MARGEN, y + 4, MARGEN + 8, y + 4 + alto_rico(lc, pc) - 8), radius=4, fill=c.acc)
  y = dibujar_rico(draw, MARGEN + 28, y, lc, fc, pc, c.tx, c.acc)
 if ref:
  draw.text((MARGEN, y + 18), 'Fuente: ' + ref, font=fuente('m', 26), fill=c.mu + (c.mu_a,))
  y += 44
 c.fin = y
 return draw
def f_versus(img, draw, c, job):
 hook = limpio(job.get('hook')) or 'Dos caminos'
 items = [limpio(i, 220) for i in (job.get('items') or []) if limpio(i)][:2]
 while len(items) < 2:
  items.append('|')
 cierre = limpio(job.get('texto'))
 ref = limpio(job.get('fuente') or job.get('referencia'))
 Y0, Y1 = 236 + c.dy, 1150
 fh, lh, ph = ajustar_rico(draw, hook, 'xb', 74, 46, ANCHO, 300, 3, 1.12)
 y = dibujar_rico(draw, MARGEN, Y0, lh, fh, ph, c.tx, c.acc) + 40
 extra = (110 if cierre else 0) + (40 if ref else 0)
 alto_max = Y1 - y - extra
 gap = 36
 pw = (ANCHO - gap) // 2
 tint = [c.acc if (c.dinero or c.claro) else BLANCO, c.acc2 if c.dinero else (c.acc2 if c.claro else c.acc)]
 partes = []
 for k in range(2):
  tit, _, cuerpo = items[k].partition('|')
  partes.append((tit.strip(), cuerpo.strip()))
 for tam in (42, 40, 38, 36, 34, 32, 30, 28, 26):
  ajus = []
  for tit, cuerpo in partes:
   ajus.append((ajustar_rico(draw, tit, 'xb', 44, 30, pw - 60, 190, 3, 1.12),
      ajustar_rico(draw, cuerpo, 'sb', tam, tam, pw - 60, 900, 14, 1.26)))
  hs = [116 + alto_rico(a_[0][1], a_[0][2]) + 38 + alto_rico(a_[1][1], a_[1][2]) + 44 for a_ in ajus]
  alto = max(hs)
  if alto <= alto_max:
   break
 alto = max(min(alto_max, alto), 380)
 for k in range(2):
  x0 = MARGEN + k * (pw + gap)
  caja = (x0, y, x0 + pw, y + alto)
  draw = panel(img, draw, c, caja, 34, tint[k] if (c.dinero or c.claro) else None)
  draw.ellipse((x0 + 30, y + 30, x0 + 30 + 56, y + 30 + 56), fill=tint[k])
  draw.text((x0 + 58, y + 59), 'AB'[k], font=fuente('xb', 30), fill=(14, 22, 44) if not c.claro else BLANCO, anchor='mm')
  (ft, lt, pt), (fb, lb, pb) = ajus[k][0], ajus[k][1]
  yy = dibujar_rico(draw, x0 + 30, y + 116, lt, ft, pt, c.tx, tint[k] if c.dinero else c.acc) + 16
  draw.rounded_rectangle((x0 + 30, yy, x0 + 90, yy + 6), radius=3, fill=tint[k])
  dibujar_rico(draw, x0 + 30, yy + 22, lb, fb, pb, c.tx, c.acc)
 cx, cy = MARGEN + pw + gap // 2, y + 58
 draw.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=(14, 22, 44) if not c.claro else TINTA, outline=BLANCO + (200,), width=3)
 draw.text((cx, cy + 1), 'VS', font=fuente('xb', 28), fill=BLANCO, anchor='mm')
 y += alto
 if cierre:
  y += 28
  fc, lc, pc = ajustar_rico(draw, cierre, 'b', 36, 28, ANCHO, 90, 2, 1.25)
  draw.rounded_rectangle((MARGEN, y + 4, MARGEN + 8, y + 4 + alto_rico(lc, pc) - 8), radius=4, fill=c.acc)
  y = dibujar_rico(draw, MARGEN + 28, y, lc, fc, pc, c.tx, c.acc)
 if ref:
  draw.text((MARGEN, y + 14), 'Fuente: ' + ref, font=fuente('m', 26), fill=c.mu + (c.mu_a,))
  y += 40
 c.fin = y
 return draw
def f_frase(img, draw, c, job):
 kicker = limpio(job.get('hook'), 48).upper().replace('*', '')
 texto, ref = limpio(job.get('texto')), limpio(job.get('referencia'))
 Y0, Y1 = 236 + c.dy, 1150
 ft, lt, pt = ajustar_rico(draw, texto, 'xb', 80, 46, ANCHO, 640, 9, 1.18)
 alto_t = alto_rico(lt, pt)
 total = 230 + alto_t + (90 if ref else 0)
 y = Y0 + max(0, (Y1 - Y0 - total) // 2)
 if kicker:
  texto_espaciado(draw, (MARGEN, y), kicker, fuente('b', 27), c.acc, sp=5)
 glifo = c.acc if (c.dinero or c.claro) else BLANCO
 pegar_icono(img, 'format-quote-open', MARGEN + 70, y + 130, 190, glifo, 230)
 draw = ImageDraw.Draw(img, 'RGBA')
 y += 250
 y = dibujar_rico(draw, MARGEN, y, lt, ft, pt, c.tx, c.acc)
 if ref:
  y += 34
  draw.line((MARGEN, y, MARGEN + 64, y), fill=c.acc, width=5)
  draw.text((MARGEN + 84, y), ref, font=fuente('b', 32), fill=c.tx, anchor='lm')
  y += 30
 c.fin = y
 return draw
def f_pregunta(img, draw, c, job):
 hook = limpio(job.get('hook')) or limpio(job.get('texto'))
 ctx = limpio(job.get('texto')) if job.get('hook') else ''
 items = [limpio(i, 80) for i in (job.get('items') or []) if limpio(i)][:4]
 Y0, Y1 = 236 + c.dy, 1150
 amax = 520 if items else 700
 fh, lh, ph = ajustar_rico(draw, hook, 'xb', 90, 48, ANCHO, amax, 6, 1.12)
 alto_h = alto_rico(lh, ph)
 alto_c = 0
 if ctx:
  fc, lc, pc = ajustar_rico(draw, ctx, 'm', 38, 28, ANCHO, 150, 3, 1.3)
  alto_c = alto_rico(lc, pc) + 30
 n = len(items)
 alto_op = n * 108 + max(0, n - 1) * 20 if n else 0
 total = alto_h + alto_c + (44 + alto_op if n else 0)
 y = Y0 + max(0, (Y1 - Y0 - total) // 3)
 if not n:
  insignia(img, c, W - MARGEN - 100, y + 60, 190, 'help-circle-outline')
  draw = ImageDraw.Draw(img, 'RGBA')
 y = dibujar_rico(draw, MARGEN, y, lh, fh, ph, c.tx, c.acc)
 if ctx:
  y += 30
  y = dibujar_rico(draw, MARGEN, y, lc, fc, pc, c.mu + (c.mu_a,), c.acc)
 if n:
  y += 44
  for k, it in enumerate(items):
   draw = panel(img, draw, c, (MARGEN, y, W - MARGEN, y + 108), 54)
   cx, cy = MARGEN + 58, y + 54
   draw.ellipse((cx - 32, cy - 32, cx + 32, cy + 32), fill=c.acc if (c.dinero or c.claro) else BLANCO)
   draw.text((cx, cy + 1), 'ABCD'[k], font=fuente('xb', 34), fill=(14, 22, 44) if not c.claro else BLANCO, anchor='mm')
   fi, li, pi = ajustar_rico(draw, it, 'sb', 40, 28, ANCHO - 150, 90, 2, 1.15)
   dibujar_rico(draw, MARGEN + 112, cy - alto_rico(li, pi) // 2 + 2, li, fi, pi, c.tx, c.acc)
   y += 108 + 20
  y -= 20
 c.fin = y
 return draw
FORMATOS = {'dato': f_dato, 'mito': f_mito, 'lista': f_lista, 'versus': f_versus, 'frase': f_frase, 'pregunta': f_pregunta}
CTA = {'dato': 'Guárdalo', 'mito': 'Guárdalo', 'lista': 'Guárdala', 'versus': 'Guárdalo', 'frase': 'Guárdala', 'pregunta': 'Responde abajo'}
ETIQUETA = {'dato': 'DATO', 'mito': 'MITO', 'lista': 'LISTA', 'versus': 'VERSUS', 'frase': 'IDEA', 'pregunta': 'PREGUNTA'}
def render(job, out_path):
 tipo = str(job.get('tipo', 'dato'))
 if tipo not in FORMATOS:
  tipo = 'dato'
 paleta = 'dinero' if str(job.get('paleta', 'dinero')) == 'dinero' else 'variado'
 c = preparar(job, paleta)
 base = fondo(job, c)
 etiqueta = limpio(job.get('etiqueta'), 16).upper() or ETIQUETA[tipo]
 for paso in (0, 1):
  img = base.copy()
  draw = ImageDraw.Draw(img, 'RGBA')
  cabecera(draw, c, etiqueta)
  draw.line((MARGEN, 188, W - MARGEN, 188), fill=c.tx + (36,), width=1)
  draw = FORMATOS[tipo](img, draw, c, job) or draw
  if paso == 0:
   libre = 1150 - c.fin
   if libre > 30 and tipo not in ('frase',):
    c.dy = min(150, libre // 3)
   else:
    break
 draw = ImageDraw.Draw(img, 'RGBA')
 pie(img, draw, c, limpio(job.get('cta'), 24) or CTA[tipo], pregunta=(tipo == 'pregunta'))
 img.convert('RGB').save(out_path, 'JPEG', quality=93, optimize=True)
 print('Tarjeta lista:', out_path, tipo, c.paleta, c.icono or '-')
