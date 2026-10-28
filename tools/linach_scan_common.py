#!/usr/bin/env python3
"""Hilfsmodul: beide Scans laden, Scene-Transforms baken, in gemeinsames
Dam-Frame drehen (X=Krone, Y=Tiefe downstream, Z=oben, Basis z=0). Textur+UV erhalten.
"""
import numpy as np, trimesh

def load_baked(path):
    """-> V (gebakt), F, per-Vertex-Farben (aus Textur via to_color)."""
    s=trimesh.load(path)
    parts=[s] if isinstance(s,trimesh.Trimesh) else s.dump()   # dump bakt Transforms
    Vs=[];Fs=[];C=[];off=0
    for g in parts:
        Vs.append(np.asarray(g.vertices)); Fs.append(np.asarray(g.faces)+off); off+=len(g.vertices)
        try: c=np.asarray(g.visual.to_color().vertex_colors)[:,:3]
        except Exception: c=np.full((len(g.vertices),3),150)
        C.append(c)
    return np.vstack(Vs),np.vstack(Fs),np.vstack(C).astype(float)/255.0

def to_dam_frame(V):
    """-> (X=Krone, Y=Tiefe, Z=Höhe ab 0), + welche Seite downstream."""
    ext=V.max(0)-V.min(0); up=int(np.argmin(np.abs(ext-25)))     # Höhe ~25m
    order=[a for a in range(3) if a!=up]+[up]
    W=V[:,order].copy(); W[:,2]-=W[:,2].min()                    # Z=Höhe ab 0
    z=W[:,2]; hi=W[z>np.percentile(z,60)]; c=hi[:,:2].mean(0)
    w,vec=np.linalg.eigh(np.cov((hi[:,:2]-c).T)); wa=vec[:,np.argmax(w)]; pa=np.array([-wa[1],wa[0]])
    Xl=(W[:,:2]-c)@wa; Yl=(W[:,:2]-c)@pa
    ycrest=np.median(Yl[z>np.percentile(z,88)])
    side=+1 if z[Yl>ycrest].min()<z[Yl<ycrest].min() else -1
    return np.column_stack([Xl, side*(Yl-ycrest), W[:,2]])

if __name__=="__main__":
    import open3d as o3d
    rend=o3d.visualization.rendering
    for nm,pth in [("b12","modelle/linachtalsperre/linach_bogen12.glb"),
                   ("b6","daten/linach/sketchfab_gltf/scene.gltf")]:
        V,F,col=load_baked(pth); L=to_dam_frame(V)
        print(f"{nm}: {len(F)}F  X {L[:,0].min():.0f}..{L[:,0].max():.0f} ({np.ptp(L[:,0]):.0f}m)  Z..{L[:,2].max():.0f}")
        r=rend.OffscreenRenderer(1600,650); r.scene.set_background([0.6,0.7,0.82,1])
        m=o3d.geometry.TriangleMesh(); m.vertices=o3d.utility.Vector3dVector(L.astype(np.float64))
        m.triangles=o3d.utility.Vector3iVector(F.astype(np.int32)); m.vertex_colors=o3d.utility.Vector3dVector(col.astype(np.float64)); m.compute_vertex_normals()
        mt=rend.MaterialRecord(); mt.shader='defaultLit'; r.scene.add_geometry('m',m,mt)
        r.scene.scene.set_sun_light([-.3,-.6,-.7],[1,1,1],90000); r.scene.scene.enable_sun_light(True)
        ctr=L.mean(0); e=np.ptp(L[:,0])
        r.setup_camera(45,[ctr[0],ctr[1],ctr[2]],[ctr[0],ctr[1]-e*0.9,ctr[2]+e*0.35],[0,0,1])
        o3d.io.write_image(f"daten/linach/diag_{nm}.png",r.render_to_image()); print(" ->",f"daten/linach/diag_{nm}.png")
