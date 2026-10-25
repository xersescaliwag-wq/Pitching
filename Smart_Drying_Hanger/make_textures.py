from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).parent
OUT = ROOT / 'textures'
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(71032)
N = 1024
y, x = np.mgrid[0:N, 0:N].astype(np.float32)
h = np.zeros((N, N), np.float32)
# A seamless field of raised, slightly irregular U-shaped cotton loops.
for j in range(36):
    for i in range(32):
        cx = (i + .5 + .14*rng.standard_normal()) * N/32
        cy = (j + .5 + .16*rng.standard_normal()) * N/36
        rx, ry = rng.uniform(6, 10), rng.uniform(9, 14)
        angle = rng.uniform(-.5,.5)
        for ox, oy in [(0,0),(-N,0),(N,0),(0,-N),(0,N)]:
            if not (-20 < cx+ox < N+20 and -25 < cy+oy < N+25):
                continue
            xa, xb = max(0,int(cx+ox-23)), min(N,int(cx+ox+24))
            ya, yb = max(0,int(cy+oy-25)), min(N,int(cy+oy+26))
            xx=x[ya:yb,xa:xb]-cx-ox; yy=y[ya:yb,xa:xb]-cy-oy
            xr = xx*np.cos(angle) - yy*np.sin(angle)
            yr = xx*np.sin(angle) + yy*np.cos(angle)
            dist = np.sqrt((xr/rx)**2+(yr/ry)**2)
            ridge = np.exp(-((dist-1)/.23)**2)
            # Small gaps and longitudinal fibrils keep loops from looking stamped.
            ridge *= .78+.22*np.cos(np.arctan2(yr,xr)*3+rng.uniform(0,6))
            h[ya:yb,xa:xb] = np.maximum(h[ya:yb,xa:xb],ridge*rng.uniform(.7,1))
h += .08*gaussian_filter(rng.random((N,N)).astype(np.float32),.6,mode='wrap')
h = gaussian_filter(h,.65,mode='wrap')
noise=gaussian_filter(rng.random((N,N)).astype(np.float32),1.4,mode='wrap')
albedo=np.clip(.76+.22*h+.025*noise,0,1)
rgb=np.stack([albedo,albedo*.997,albedo*.985],-1)
Image.fromarray((rgb*255).astype('uint8')).save(OUT/'Terry_BaseColor.png')
gx=(np.roll(h,-1,1)-np.roll(h,1,1))*1.25
gy=(np.roll(h,-1,0)-np.roll(h,1,0))*1.25
normal=np.stack([-gx,gy,np.ones_like(h)],-1)
normal/=np.linalg.norm(normal,axis=-1,keepdims=True)
Image.fromarray(np.uint8(np.clip(normal*.5+.5,0,1)*255)).save(OUT/'Terry_Normal.png')
Image.fromarray(np.uint8(np.clip(.91-.06*h+.04*noise,0,1)*255)).save(OUT/'Terry_Roughness.png')
Image.fromarray(np.uint16(np.clip(h,0,1)*65535),mode='I;16').save(OUT/'Terry_Height.png')
Image.fromarray(np.uint8(np.clip(.80+.2*h,0,1)*255)).save(OUT/'Terry_AO.png')

S=2048
Y,X=np.mgrid[0:S,0:S].astype(np.float32)
U=X/(S-1); V=1-Y/(S-1)
# Front of the continuous drape occupies V=0..0.49.
mask=(np.clip((U-.07)/.08,0,1)*np.clip((.93-U)/.08,0,1)*
      np.clip((V-.07)/.13,0,1)*np.clip((.495-V)/.035,0,1))
mask=gaussian_filter(mask,13)
t=np.clip((V-.07)/.40,0,1)
blue=np.stack([.25-.12*t,.17+.47*t,.70+.05*t],-1)
emission=blue*mask[:,:,None]*.18
effect=Image.fromarray(np.uint8(np.clip(emission,0,1)*255))
effect_background=np.asarray(effect).copy()
draw=ImageDraw.Draw(effect)
font_candidates=['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','C:/Windows/Fonts/arial.ttf','/System/Library/Fonts/Supplemental/Arial.ttf']
font_path=next((x for x in font_candidates if Path(x).exists()),'DejaVuSans.ttf')
font=ImageFont.truetype(font_path,35)
def pt(u,v): return (round(u*S),round((1-v)*S))
for k in range(13):
    u=.15+k*.058
    start=.46-(k%3)*.012
    end=.16+(.025*((k*7)%5))
    c=(40,117,166)
    px,py=pt(u,start); ex,ey=pt(u,end)
    # Outlined, fine blue down-arrows matching the technical reference.
    hw=7
    points=[(px-hw,py),(px+hw,py),(ex+hw,ey-31),(ex+21,ey-31),(ex,ey),
            (ex-21,ey-31),(ex-hw,ey-31),(px-hw,py)]
    draw.line(points,fill=c,width=3,joint='curve')
    if k%2==0:
        dx=px+22
        draw.line([(dx-5,py),(dx-5,ey-6)],fill=(43,116,171),width=2)
        draw.line([(dx+7,py),(dx+7,ey-6)],fill=(43,116,171),width=2)
        for yy in range(py+9,ey-10,22):
            draw.rectangle((dx-1,yy,dx+4,yy+9),outline=(60,143,189),width=2)
for u,v,r in [(.19,.27,20),(.31,.20,23),(.44,.26,21),(.57,.19,23),(.70,.24,21),(.82,.30,20),(.41,.12,29),(.75,.13,28)]:
    px,py=pt(u,v)
    draw.ellipse((px-r,py-r,px+r,py+r),outline=(55,100,151),width=3)
    bbox=draw.textbbox((0,0),'UV',font=font)
    scale=ImageFont.truetype(font_path,round(r*1.05))
    draw.text((px,py),'UV',font=scale,fill=(55,100,151),anchor='mm')
effect.save(OUT/'Towel_UV_Emission.png')
graphics=np.max(np.abs(np.asarray(effect).astype(float)-effect_background.astype(float)),axis=2)>4
glow=np.stack([.55-.18*t,.38+.42*t,.92-.06*t],-1)
mix=.72*mask[:,:,None]
fullbase=np.ones((S,S,3),np.float32)*np.array([.94,.945,.93])
fullbase=fullbase*(1-mix)+glow*mix
fullbase[graphics]=np.asarray(effect)[graphics]/255*.70+.13
xi=(np.arange(S)*7/S*N).astype(int)%N
yi=(np.arange(S)*15/S*N).astype(int)%N
cotton=rgb[yi[:,None],xi[None,:],:]/.89
fullbase*=cotton
fullbase += rng.normal(0,.003,(S,S,1))
Image.fromarray(np.uint8(np.clip(fullbase,0,1)*255)).save(OUT/'Towel_BaseColor.png')

# Panel markings are authored as a texture, keeping fine labels editable.
panel=Image.new('RGB',(2048,256),(12,16,19))
d=ImageDraw.Draw(panel)
small=ImageFont.truetype(font_path,35)
tiny=ImageFont.truetype(font_path,25)
for xx,lab in [(85,'POWER'),(290,'DRY'),(470,'UV')]:
    d.text((xx,185),lab,font=tiny,fill=(186,190,190))
d.rounded_rectangle((670,55,1190,150),radius=12,fill=(22,35,41),outline=(66,88,94),width=3)
mono='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
digit=ImageFont.truetype(mono if Path(mono).exists() else font_path,73)
d.text((710,53),'45% 28°C',font=digit,fill=(132,207,217))
d.text((1320,65),'HUMIDITY / TEMP',font=small,fill=(181,189,189))
d.text((1320,122),'SMART DRYING SYSTEM',font=tiny,fill=(129,143,146))
panel.save(OUT/'Indicator_BaseColor.png')
print('Created PBR fabric maps, UV emission, and panel texture.')
