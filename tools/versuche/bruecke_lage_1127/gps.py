import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np, json, glob
from PIL import Image
def dms(v): return v[0]+v[1]/60+v[2]/3600
def lese(names, ordner='/media/oem/rcdaten/rc-park_daten_neu/handy_20261126'):
    out={}
    for n in names:
        f=os.path.join(ordner,n)
        if not os.path.exists(f): continue
        e=Image.open(f)._getexif() or {}; g=e.get(34853)
        if not g or 2 not in g: continue
        meth=g.get(27,b'')
        out[n]=dict(lat=dms(g[2]),lon=dms(g[4]),alt=float(g.get(6,np.nan)),meth=meth.decode('ascii','ignore').replace('\x00','').replace('ASCII',''))
    return out
