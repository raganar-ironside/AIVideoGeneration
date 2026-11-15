import bpy, json, math, os, random
random.seed(5)
A=os.path.abspath("art"); OUT=os.path.abspath("frames")
os.makedirs(OUT,exist_ok=True)
parts=json.load(open(f"{A}/parts.json"))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=6
sc.cycles.use_denoising=False; sc.cycles.transparent_max_bounces=48; sc.cycles.max_bounces=48
sc.render.resolution_x=720; sc.render.resolution_y=1280; sc.render.resolution_percentage=100
sc.render.fps=24; sc.frame_start=1; sc.frame_end=48
sc.view_settings.view_transform='Standard'
sc.render.image_settings.file_format='PNG'; sc.render.filepath=OUT+"/f_"
cam=bpy.data.objects.new("cam",bpy.data.cameras.new("cam")); sc.collection.objects.link(cam)
cam.data.type='ORTHO'; cam.data.ortho_scale=19.2; cam.location=(0,0,20); sc.camera=cam

def mat(path,name):
    m=bpy.data.materials.new(name); m.use_nodes=True; nt=m.node_tree; nt.nodes.clear()
    t=nt.nodes.new("ShaderNodeTexImage"); t.image=bpy.data.images.load(path); t.interpolation='Linear'
    e=nt.nodes.new("ShaderNodeEmission"); tr=nt.nodes.new("ShaderNodeBsdfTransparent")
    mx=nt.nodes.new("ShaderNodeMixShader"); o=nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(t.outputs['Color'],e.inputs['Color']); nt.links.new(t.outputs['Alpha'],mx.inputs['Fac'])
    nt.links.new(tr.outputs[0],mx.inputs[1]); nt.links.new(e.outputs[0],mx.inputs[2]); nt.links.new(mx.outputs[0],o.inputs['Surface'])
    return m
def quad(name,x0,y0,x1,y1,z,m):
    me=bpy.data.meshes.new(name)
    me.from_pydata([(x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z)],[],[(0,1,2,3)])
    me.uv_layers.new(name="uv"); uv=me.uv_layers.active.data
    for i,c in enumerate([(0,0),(1,0),(1,1),(0,1)]): uv[i].uv=c
    ob=bpy.data.objects.new(name,me); sc.collection.objects.link(ob); me.materials.append(m); return ob
def empty(name,loc=(0,0,0),parent=None):
    e=bpy.data.objects.new(name,None); sc.collection.objects.link(e); e.location=loc
    if parent: e.parent=parent
    return e

K=0.0072
def U(dx,dy): return ((dx)*K,-(dy)*K)
# backgrounds
for n,z in (("bg",-8),("mountains",-7),("ledge",-4)):
    quad(n,-5.4,-9.6,5.4,9.6,z,mat(f"{A}/{n}.png",n))
# Shiva rig (pivots in canvas px)
root=empty("root",(-2.3,-5.2,0)); ROOT=(350,1300)
def rel(p,q): return (*U(p[0]-q[0],p[1]-q[1]),0)
waist=empty("waist",rel((350,625),ROOT),root)
neck=empty("neck",rel((350,300),(350,625)),waist)
rsh=empty("rsh",rel((440,332),(350,625)),waist)
relbow=empty("relbow",rel((535,430),(440,332)),rsh)
lsh=empty("waist_l",rel((262,332),(350,625)),waist)
lelb=empty("lelbow",rel((236,440),(262,332)),lsh)
E=dict(root=root,waist=waist,neck=neck,rsh=rsh,relbow=relbow,waist_l=lsh,lelbow=lelb)
for n,p in parts.items():
    x0,y0,x1,y1=p["bbox"]; pv=p["pivot"]
    a=U(x0-pv[0],y0-pv[1]); b=U(x1-pv[0],y1-pv[1])
    ob=quad(n,a[0],b[1],b[0],a[1],p["z"],mat(f"{A}/{n}.png",n)); ob.parent=E[p["parent"]]
    # parts whose parent empty is not located at their pivot need offset: fix by placing at difference
    par=E[p["parent"]]
    # parent pivot pos in canvas
    pp={"root":ROOT,"waist":(350,625),"neck":(350,300),"rsh":(440,332),"relbow":(535,430),"waist_l":(262,332),"lelbow":(236,440)}[p["parent"]]
    ob.location=(*U(pv[0]-pp[0],pv[1]-pp[1]),0)
# water + bubbles
water=quad("water",-6,-24+0.6,6,0.6,2.0,mat(f"{A}/water.png","water"))
# water image height 2400px=24u, top edge at 60px=0.6u below top -> top edge at y=0
bub=mat(f"{A}/bubble.png","bub")
bubs=[]
for i in range(16):
    s=random.uniform(0.25,0.6)
    ob=quad(f"b{i}",-s/2,-s/2,s/2,s/2,3.0,bub); ob.location=(random.uniform(-4.5,1.5),-20,3); bubs.append((ob,s))

def key(o,path,idx,frames):
    for f,v in frames:
        if idx is None: setattr(o,path,v)
        else: getattr(o,path)[idx]=v
        o.keyframe_insert(path,index=idx if idx is not None else -1,frame=f)
def smooth(o):
    ad=o.animation_data
    if ad and ad.action:
        try:
            for fc in ad.action.fcurves:
                for k in fc.keyframe_points: k.interpolation='BEZIER'; k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
        except Exception: pass
R=math.radians
# right arm: hangs -> raises to point, then drifts up as he sinks
key(rsh,"rotation_euler",2,[(1,R(-70)),(12,R(6)),(16,R(0)),(30,R(0)),(48,R(26))])
key(relbow,"rotation_euler",2,[(1,R(-20)),(12,R(4)),(16,R(0)),(48,R(18))])
key(lsh,"rotation_euler",2,[(1,R(0)),(30,R(0)),(48,R(-16))])
key(lelb,"rotation_euler",2,[(1,R(0)),(48,R(-10))])
key(neck,"rotation_euler",2,[(1,R(-3)),(14,R(4)),(30,R(0)),(48,R(-4))])
key(waist,"rotation_euler",2,[(1,R(0)),(20,R(-1.5)),(48,R(3))])
# idle sway + sink
key(root,"location",1,[(1,-5.2),(14,-5.2),(48,-9.4)])
key(root,"location",0,[(1,-2.3),(14,-2.3),(48,-1.6)])
key(root,"rotation_euler",2,[(1,0),(30,R(-1)),(48,R(4))])
# water rises: top edge from y=-11 to y=3.4
key(water,"location",1,[(1,-11),(10,-11),(34,3.4),(48,3.6)])
for i,(ob,s) in enumerate(bubs):
    st=18+i*1.4; x=ob.location[0]
    key(ob,"location",1,[(1,-20),(int(st),-9.5),(48,1.0+random.uniform(-0.5,1.5))])
    key(ob,"location",0,[(1,x),(int(st),x),(48,x+random.uniform(-0.6,0.6))])
for o in [rsh,relbow,lsh,lelb,neck,waist,root,water]+[b for b,_ in bubs]: smooth(o)
bpy.ops.render.render(animation=True)
print("done")