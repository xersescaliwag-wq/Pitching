"""Optional Intel Open Image Denoise pass on Cycles previews (pip install oidn)."""
from pathlib import Path
import sys
import numpy as np
from PIL import Image
import oidn
import OpenEXR

def read_exr(path):
    f=OpenEXR.File(str(path))
    c=f.channels()
    if 'RGB' in c:return np.ascontiguousarray(c['RGB'].pixels,dtype=np.float32)
    if 'RGBA' in c:return np.ascontiguousarray(c['RGBA'].pixels[:,:,:3],dtype=np.float32)
    return np.ascontiguousarray(np.stack([c[k].pixels for k in ['R','G','B']],-1),dtype=np.float32)

for arg in sys.argv[1:]:
    path=Path(arg)
    a=np.asarray(Image.open(path).convert('RGB')).astype(np.float32)/255
    color=np.ascontiguousarray(np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4),dtype=np.float32)
    result=np.empty_like(color)
    device=oidn.NewDevice();oidn.CommitDevice(device)
    f=oidn.NewFilter(device,'RT')
    for name,data in [('color',color),('output',result)]:
        oidn.SetSharedFilterImage(f,name,data,oidn.FORMAT_FLOAT3,a.shape[1],a.shape[0])
    buffers=[]
    for name,label in [('albedo','Albedo'),('normal','Normal')]:
        src=path.parent/'auxiliary'/(path.stem.replace('_Raw','')+'_'+label+'_0001.exr')
        if src.exists():
            data=read_exr(src);buffers.append(data)
            oidn.SetSharedFilterImage(f,name,data,oidn.FORMAT_FLOAT3,a.shape[1],a.shape[0])
    oidn.CommitFilter(f);oidn.ExecuteFilter(f)
    err=oidn.GetDeviceError(device)
    if err:raise RuntimeError('OIDN error '+str(err))
    result=np.clip(result,0,1)
    rgb=np.where(result<=.0031308,result*12.92,1.055*result**(1/2.4)-.055)
    dest=path.with_name(path.stem.replace('_Raw','')+'_Clean.png')
    Image.fromarray(np.uint8(np.clip(rgb,0,1)*255)).save(dest)
    oidn.ReleaseFilter(f);oidn.ReleaseDevice(device)
    print(dest,flush=True)
