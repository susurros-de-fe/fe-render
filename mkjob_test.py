import base64, json, math, subprocess, numpy as np, io, wave
from PIL import Image, ImageDraw, ImageFilter
rng=np.random.default_rng(5)
def img(seed, top, bot, sol):
    r=np.random.default_rng(seed); W,H=1024,1792
    y=np.linspace(0,1,H)[:,None,None]
    a=np.array(top)[None,None,:]; b=np.array(bot)[None,None,:]
    base=(a*(1-y)+b*y)*np.ones((H,W,1))
    im=Image.fromarray(base.astype(np.uint8)); d=ImageDraw.Draw(im)
    d.ellipse((sol[0]-90,sol[1]-90,sol[0]+90,sol[1]+90),fill=(255,236,190))
    im=im.filter(ImageFilter.GaussianBlur(40)); d=ImageDraw.Draw(im)
    for k,(col,yy) in enumerate(((  (60,50,70),1250),((35,30,50),1450),((15,15,25),1650))):
        pts=[(0,H)]
        for x in range(0,W+1,32): pts.append((x,yy+60*math.sin(x/140+k*2+seed)+r.uniform(-8,8)))
        pts.append((W,H)); d.polygon(pts,fill=col)
    im=im.filter(ImageFilter.GaussianBlur(2))
    b=io.BytesIO(); im.save(b,'JPEG',quality=88); return base64.b64encode(b.getvalue()).decode()
imgs=[img(1,(250,170,110),(70,60,110),(560,900)), img(2,(120,160,220),(240,200,170),(300,700)), img(3,(30,30,70),(190,110,90),(700,1000))]
def voz(dur, f0):
    SR=44100; n=int(dur*SR); t=np.arange(n)/SR
    sil=np.abs(np.sin(2*np.pi*t*3.6+rng.uniform(0,6)))**0.7
    ton=sum(np.sin(2*np.pi*f0*(1+0.03*np.sin(2*np.pi*0.7*t))*h*t)/h for h in range(1,7))
    x=ton*sil*np.minimum(1,t/0.04)*np.minimum(1,(dur-t)/0.1)*0.3
    pcm=(x*32767).astype('<i2'); b=io.BytesIO()
    w=wave.open(b,'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes()); w.close()
    p=subprocess.run(['ffmpeg','-v','error','-i','pipe:0','-f','mp3','pipe:1'],input=b.getvalue(),capture_output=True)
    return base64.b64encode(p.stdout).decode()
frases=[('Permíteme contarte una historia de la Biblia que es para ti.',0,3.2),('David era un joven pastor que cuidaba las ovejas de su padre.',0,3.8),
('Una noche, en medio de la oscuridad, le habló al Señor con el corazón.',1,4.0),('Jehová es mi pastor, nada me faltará.',1,2.8),('En lugares de delicados pastos me hará descansar.',1,3.2),
('Aunque ande en valle de sombra de muerte, no temeré mal alguno.',2,3.8),('Porque tú estarás conmigo.',2,2.4),('Si esta historia fue de bendición para ti, dale like, escribe amén y compártela con alguien que aprecies.',2,5.0)]
esc=[]
for i,(t,im,d) in enumerate(frases):
    esc.append({'texto':t,'audio_b64':voz(d,150+10*(i%3)),'pausa':0.8 if i<7 else 0.4,'img':im,'cierre':i==7,'enfasis':False})
job={'job_id':'ftest-0000','titulo':'Prueba','tipo':'historia','fondo':'relajante','fondo_nivel':0.4,'velocidad':1.0,'texto_gancho':'La noche en que David oró','imagenes':imgs,'escenas':esc,'audio_v':2}
json.dump(job,open('job.json','w'))
print('job ok')
