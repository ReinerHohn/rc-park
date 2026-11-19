import pycolmap, json, numpy as np, sys, collections
r=pycolmap.Reconstruction(sys.argv[1]); g=json.load(open("/media/oem/rcdaten/tmp/mt_seiten/seiten2.json"))["gemeinschaft"]
uns=set(l.strip() for l in open(sys.argv[2])) if len(sys.argv)>2 else set()
ims=[im for im in r.images.values() if im.has_pose]; X=np.array([im.cam_from_world().rotation.matrix()[0] for im in ims]); up=np.linalg.svd(X)[2][-1]
a1=np.cross(up,[1,0,0]); a1/=np.linalg.norm(a1); a2=np.cross(up,a1); G=collections.defaultdict(list)
for im in ims:
    v=im.cam_from_world().rotation.matrix()[2]; G[g[im.name]].append((np.degrees(np.arctan2(v@a2,v@a1)), im.name in uns))
def mitte(w): w=np.radians(w); return np.degrees(np.arctan2(np.sin(w).mean(),np.cos(w).mean())), float(np.hypot(np.sin(w).mean(),np.cos(w).mean()))
print("Bilder im Modell",len(ims),"unstabil",sum(im.name in uns for im in ims)); m0=mitte([w for w,_ in G[0]])[0] if G[0] else 0
for k in sorted(G,key=lambda k:-len(G[k]))[:16]:
    m,b=mitte([w for w,_ in G[k]]); print(f"Gruppe {k:3d}: {len(G[k]):4d} Bilder ({sum(u for _,u in G[k]):3d} unstabil), Blickrichtung {abs((m-m0+180)%360-180):4.0f} Grad gegen Gruppe 0, Buendelung {b:.2f}")
