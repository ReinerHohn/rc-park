import numpy as np, json, base64, sys
z=np.load(sys.argv[1]); out=sys.argv[2]; V=z["V"]; F=z["F"]; lo=V.min(0); hi=V.max(0); sp=(hi-lo)/65535.0; q=((V-lo)/sp).round().astype(np.uint16)
off=np.r_[0,np.cumsum(z["ntri"])].tolist()
d=dict(v=base64.b64encode(q.tobytes()).decode(),f=base64.b64encode(F.astype(np.uint32).tobytes()).decode(),off=off,ids=z["ids"].tolist(),npts=z["npts"].tolist(),farbe=z["farbe"].tolist(),lo=lo.tolist(),sp=sp.tolist())
t=open("tools/huellen_viewer.tpl.html").read().replace("__DATA__",json.dumps(d,separators=(",",":"))); open(out,"w").write(t); print(len(t)//1024,"KB")
