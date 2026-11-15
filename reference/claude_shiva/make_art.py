import json, math, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
OUT = sys.argv[1]
S = 2
random.seed(3); np.random.seed(3)
SK=(150,166,174); SKD=(112,128,138); OR=(226,122,42); GOLD=(236,184,72); BR=(72,44,30); RED=(176,44,44); GR=(62,146,96); LINE=(52,36,34)

def canvas(w,h): return Image.new("RGBA",(w*S,h*S),(0,0,0,0))
def P(pts): return [(x*S,y*S) for x,y in pts]
def capsule(d,a,b,w,col):
    d.line(P([a,b]),fill=col,width=int(w*S))
    for p in (a,b):
        r=w/2; d.ellipse([ (p[0]-r)*S,(p[1]-r)*S,(p[0]+r)*S,(p[1]+r)*S ],fill=col)
def ell(d,cx,cy,rx,ry,col): d.ellipse([(cx-rx)*S,(cy-ry)*S,(cx+rx)*S,(cy+ry)*S],fill=col)
def grain(img,amt=14):
    a=np.array(img).astype(np.int16)
    n=np.random.randint(-amt,amt+1,a.shape[:2])[...,None]
    a[...,:3]=np.clip(a[...,:3]+n,0,255)
    return Image.fromarray(a.astype(np.uint8))
def outline(img,px=3):
    al=img.split()[3]
    big=al.filter(ImageFilter.MaxFilter(px*S*2+1))
    base=Image.new("RGBA",img.size,LINE+(255,)); base.putalpha(big)
    base.alpha_composite(img); return base
def finish(img,ol=True):
    if ol: img=outline(img)
    img=grain(img.convert("RGBA"))
    return img.resize((img.width//S,img.height//S),Image.LANCZOS)

W,H=700,1300
parts={}
def part(name,fn,pivot,z,parent,ol=True):
    im=canvas(W,H); d=ImageDraw.Draw(im); fn(d)
    im=finish(im,ol)
    bb=im.split()[3].point(lambda v:255 if v>8 else 0).getbbox()
    im.crop(bb).save(f"{OUT}/{name}.png")
    parts[name]=dict(bbox=bb,pivot=pivot,z=z,parent=parent)
    return im

def head(d):
    ell(d,350,175,76,94,BR)                      # hair back
    ell(d,350,92,54,72,BR)                       # bun
    d.rectangle(P([(300,100),(400,114)]),fill=OR)  # bun band
    d.rectangle(P([(335,266),(365,325)]),fill=SKD) # neck
    ell(d,350,208,64,80,SK)                      # face
    d.pieslice(P([(278,120),(422,260)])[0]+P([(278,120),(422,260)])[1],180,360,fill=BR)  # fringe
    for x in (322,378):                          # eyes
        d.line(P([(x-16,208),(x,202),(x+16,208)]),fill=(30,24,24),width=5*S//1)
        d.line(P([(x-14,198),(x+14,198)]),fill=(30,24,24),width=3*S)
    d.line(P([(350,222),(344,246),(356,246)]),fill=SKD,width=4*S)   # nose
    d.arc(P([(332,252),(368,272)])[0]+P([(332,252),(368,272)])[1],10,170,fill=(110,50,50),width=4*S)
    for i,y in enumerate((154,162,170)):         # ash lines
        d.line(P([(322,y),(378,y)]),fill=(235,235,230),width=3*S)
    d.ellipse([ (343)*S,(176)*S,(357)*S,(196)*S ],fill=RED)  # third eye
    # crescent moon
    ell(d,350,34,26,26,GOLD); ell(d,360,28,24,24,BR)
    # ganga stream
    pts=[(330,60),(300,20),(292,-0)]
    d.line(P([(325,48),(296,10),(300,-6)]),fill=(150,210,226),width=7*S)
def torso(d):
    d.polygon(P([(255,310),(445,310),(428,480),(405,640),(295,640),(272,480)]),fill=SK)
    d.line(P([(350,330),(350,600)]),fill=SKD,width=3*S)
    for t in np.linspace(0.05,0.95,22):          # garland arc
        a=math.pi*t; x=350-80*math.cos(a); y=330+150*math.sin(a)
        ell(d,x,y,7,7,RED)
    ell(d,350,490,13,16,GR)
    d.rectangle(P([(290,610),(410,640)]),fill=GOLD)
def skirt(d):
    d.polygon(P([(292,620),(408,620),(448,780),(434,935),(266,935),(252,780)]),fill=OR)
    for i in range(14):
        x=270+random.random()*160; y=650+random.random()*270
        ell(d,x,y,9,6,(150,70,25))
    for y in (700,790,880): d.line(P([(262,y),(438,y)]),fill=(150,70,25),width=4*S)
    d.rectangle(P([(292,618),(408,640)]),fill=GOLD)
def legs(d):
    for x in (322,380):
        capsule(d,(x,900),(x,1200),46,SK); ell(d,x-6,1228,34,16,SKD)
        ell(d,x,1000,24,40,SK)
def rupper(d):
    capsule(d,(440,332),(535,430),40,SK)
    capsule(d,(470,362),(486,378),46,GOLD)
def rfore(d):
    capsule(d,(535,430),(640,470),34,SK)
    ell(d,648,474,22,19,SK); d.line(P([(655,476),(700,488)]),fill=SK,width=10*S)
    capsule(d,(560,438),(575,445),38,GOLD)
def lupper(d): capsule(d,(262,332),(236,440),40,SK); capsule(d,(254,366),(249,382),46,GOLD)
def lfore(d):
    capsule(d,(236,440),(204,560),34,SK); ell(d,196,566,22,20,SK)
def trishul(d):
    d.rectangle(P([(185,70),(197,1240)]),fill=(160,118,62))
    d.line(P([(191,100),(191,6)]),fill=GOLD,width=9*S)
    d.arc(P([(150,26),(232,118)])[0]+P([(150,26),(232,118)])[1],0,180,fill=GOLD,width=9*S)
    d.line(P([(150,72),(150,22)]),fill=GOLD,width=8*S); d.line(P([(232,72),(232,22)]),fill=GOLD,width=8*S)
    d.polygon(P([(143,30),(150,0),(157,30)]),fill=GOLD); d.polygon(P([(225,30),(232,0),(239,30)]),fill=GOLD); d.polygon(P([(184,22),(191,-14),(198,22)]),fill=GOLD)

part("trishul",trishul,(350,1300),-0.30,"root")
part("legs",legs,(350,1300),-0.10,"root")
part("skirt",skirt,(350,625),0.0,"waist")
part("torso",torso,(350,625),0.05,"waist")
part("lupper",lupper,(262,332),0.10,"waist_l") 
part("lfore",lfore,(236,440),0.11,"lelbow")
part("head",head,(350,300),0.20,"neck")
part("rupper",rupper,(440,332),0.30,"rsh")
part("rfore",rfore,(535,430),0.31,"relbow")

# glow silhouette
sil=Image.new("RGBA",(W,H),(0,0,0,0))
for n in parts:
    if n=="trishul": continue
    im=Image.open(f"{OUT}/{n}.png"); sil.alpha_composite(im,tuple(parts[n]["bbox"][:2]))
al=sil.split()[3].filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(22))
g=Image.new("RGBA",(W,H),(255,150,50,0)); g.putalpha(al.point(lambda v:int(v*0.55))); g.save(f"{OUT}/glow.png")
parts["glow"]=dict(bbox=[0,0,W,H],pivot=(350,1300),z=-0.5,parent="root")
json.dump(parts,open(f"{OUT}/parts.json","w"))

# ---------- backgrounds (1080x1920) ----------
FW,FH=1080,1920
def bgl():
    a=np.zeros((FH,FW,3),np.float32)
    t=np.linspace(0,1,FH)[:,None]
    top=np.array([26,30,34]);bot=np.array([52,60,58])
    a[:]=(top*(1-t)+bot*t)[:,None,:] if False else (top[None,None,:]*(1-t[...,None])+bot[None,None,:]*t[...,None])
    im=Image.fromarray(a.astype(np.uint8)).convert("RGBA")
    d=ImageDraw.Draw(im)
    for _ in range(40):
        x,y=random.randint(0,FW),random.randint(80,900); r=random.choice((1,1,2,3)); d.ellipse([x-r,y-r,x+r,y+r],fill=(230,200,120,200))
    # moon top-right
    d.ellipse([930,110,1010,190],fill=(226,214,180)); d.ellipse([950,100,1030,180],fill=(34,38,42))
    return grain(im,8)
bgl().save(f"{OUT}/bg.png")

im=Image.new("RGBA",(FW*S,FH*S),(0,0,0,0)); d=ImageDraw.Draw(im)
def mtn(apex,left,right,base,cap):
    d.polygon(P([apex,(left,base),(right,base)]),fill=(84,94,92))
    h=cap
    # snow cap w/ scalloped bottom
    L=apex[0]-(apex[0]-left)*h/(base-apex[1]); R=apex[0]+(right-apex[0])*h/(base-apex[1])
    y=apex[1]+h
    pts=[apex,(L,y)]
    n=5
    for i in range(n+1):
        x=L+(R-L)*i/n; pts.append((x,y+(24 if i%2 else -6)))
    pts.append((R,y))
    d.polygon(P(pts),fill=(240,226,196))
mtn((660,520),60,1300,1500,230)
mtn((190,830),-120,500,1500,110)
# ridge dotted lines
for k in range(9):
    x=660+ (k-4)*40; d.line(P([(660+(x-660)*0.1,560),(x*1.15-90,1480)]),fill=(110,122,118),width=2*S)
d=ImageDraw.Draw(im)
mt=grain(im.resize((FW,FH),Image.LANCZOS),8); mt.save(f"{OUT}/mountains.png")

im=Image.new("RGBA",(FW*S,FH*S),(0,0,0,0)); d=ImageDraw.Draw(im)
d.polygon(P([(0,1520),(300,1500),(520,1530),(1080,1560),(1080,1920),(0,1920)]),fill=(28,32,36))
for _ in range(10):
    x=random.randint(20,1000);y=random.randint(1580,1850); ell(d,x,y,random.randint(30,70),random.randint(12,22),(40,46,50))
grain(im.resize((FW,FH),Image.LANCZOS),8).save(f"{OUT}/ledge.png")

# water 1200x2400 : wavy top at y=60
WW,WH=1200,2400
a=np.zeros((WH,WW,4),np.float32)
t=np.linspace(0,1,WH)[:,None]
c0=np.array([46,128,130]);c1=np.array([18,60,70])
a[...,:3]=c0*(1-t[...,None])+c1*t[...,None]
a[...,3]=0.80
im=Image.fromarray(a.clip(0,255).astype(np.uint8) if False else np.concatenate([a[...,:3],a[...,3:]*255],2).astype(np.uint8),"RGBA")
mask=Image.new("L",(WW,WH),0); md=ImageDraw.Draw(mask)
pts=[(0,WH)]+[(x,60+10*math.sin(x/38)) for x in range(0,WW+1,6)]+[(WW,WH)]
md.polygon(pts,fill=255)
# light shafts
sh=Image.new("RGBA",(WW,WH),(0,0,0,0)); sd=ImageDraw.Draw(sh)
for x in range(80,WW,170): sd.polygon([(x,60),(x+50,60),(x+170,1800),(x+90,1800)],fill=(180,240,230,26))
im.alpha_composite(sh)
al=ImageChops.multiply(im.split()[3],mask); im.putalpha(al)
d=ImageDraw.Draw(im)
d.line([(x,60+10*math.sin(x/38)) for x in range(0,WW+1,6)],fill=(190,240,230,255),width=5)
grain(im,6).save(f"{OUT}/water.png")

# bubble
b=Image.new("RGBA",(96,96),(0,0,0,0)); d=ImageDraw.Draw(b)
d.ellipse([6,6,90,90],outline=(210,245,240,230),width=6); d.ellipse([26,22,42,34],fill=(255,255,255,220))
b.save(f"{OUT}/bubble.png")
print("ok",list(parts))