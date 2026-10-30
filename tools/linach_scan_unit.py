#!/usr/bin/env python3
"""linach_scan_unit.py — SCHRITT 1 (sorgfältig): aus dem Scan EINE saubere,
WASSERDICHTE Dam-Einheit rekonstruieren (Poisson/open3d), Löcher zu.
Erst verifizieren + zeigen, DANN (separat) kacheln.
"""
import numpy as np, trimesh, open3d as o3d, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

SCAN="daten/linach/sketchfab/source/Flug 2 - Bogen 1 + 2_simplified_3d_mesh.obj"
BAY=143.0/13; WUNIT=2*BAY; DEPTH=18.0

# ---- Scan laden, Normalen, Krone-Frame ----
m=trimesh.load(SCAN,process=True)
if hasattr(m,'geometry'): m=trimesh.util.concatenate(list(m.geometry.values()))
V=np.asarray(m.vertices); Nrm=np.asarray(m.vertex_normals)
z=V[:,2]; hi=V[z>np.percentile(z,60)]
c=hi[:,:2].mean(0); w,vec=np.linalg.eigh(np.cov((hi[:,:2]-c).T)); wa=vec[:,np.argmax(w)]; pa=np.array([-wa[1],wa[0]])
Xl=(V[:,:2]-c)@wa; Yl=(V[:,:2]-c)@pa; Zl=z-z.min()
ycrest=float(np.median(Yl[z>np.percentile(z,88)]))
side=+1 if Zl[Yl>ycrest].min()<Zl[Yl<ycrest].min() else -1
Yd=side*(Yl-ycrest)
x0=float(np.median(Xl))

# ---- EINE Einheit croppen (großzügig, Punkte+Normalen) ----
sel=(np.abs(Xl-x0)<WUNIT/2+2)&(Yd>-5.0)&(Yd<DEPTH)
P=np.column_stack([Xl[sel]-x0,Yd[sel],Zl[sel]]); Nn=Nrm[sel].copy()
# Normalen in gleiches Frame drehen (nur XY-Rotation): [wa;pa;z]
Rw=np.array([[wa[0],wa[1],0],[side*pa[0],side*pa[1],0],[0,0,1.0]])
Nn=Nn@Rw.T
print(f"Einheit-Punkte {len(P)}  (Breite {WUNIT:.1f}m Tiefe {DEPTH}m)")

pcd=o3d.geometry.PointCloud()
pcd.points=o3d.utility.Vector3dVector(P); pcd.normals=o3d.utility.Vector3dVector(Nn)
pcd.orient_normals_consistent_tangent_plane(30)
mesh,dens=o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd,depth=10,linear_fit=True)
dens=np.asarray(dens)
mesh.remove_vertices_by_mask(dens<np.quantile(dens,0.06))   # ballooned/low-density weg
# auf Einheits-BBox clippen
bb=o3d.geometry.AxisAlignedBoundingBox(np.array([-WUNIT/2,-4,0]),np.array([WUNIT/2,DEPTH,Zl[sel].max()+1]))
mesh=mesh.crop(bb)
mesh.compute_vertex_normals()
Vu=np.asarray(mesh.vertices); Fu=np.asarray(mesh.triangles)
unit=trimesh.Trimesh(Vu,Fu,process=True)
trimesh.repair.fill_holes(unit); trimesh.repair.fix_normals(unit)
oe=trimesh.grouping.group_rows(unit.edges_sorted,require_count=1).shape[0]
print(f"Einheit rekonstruiert: {len(unit.faces)}F  watertight={unit.is_watertight}  offene Kanten={oe}")
unit.export("modelle/linachtalsperre/scan_unit.stl")

# ---- Render 2 Ansichten ----
def shade(tr):
    n=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0]); n=n/np.clip(np.linalg.norm(n,axis=1,keepdims=True),1e-9,None)
    lt=np.array([0.3,-0.6,0.75]); lt/=np.linalg.norm(lt)
    b=np.array([0.90,0.88,0.83])                    # heller Beton
    return np.clip(b[None,:]*(0.6+0.42*np.clip(np.abs(n@lt),0,1))[:,None],0,1)
rv,rf=unit.vertices,unit.faces
if len(rf)>60000:
    import fast_simplification as fs
    rv,rf=fs.simplify(rv.astype(np.float32),rf.astype(np.int32),target_reduction=1-60000/len(rf))
tri=rv[rf]
fig=plt.figure(figsize=(15,6))
for i,(el,az,ti) in enumerate([(12,-84,"Luftseite (downstream)"),(18,96,"Wasserseite (upstream)")]):
    ax=fig.add_subplot(1,2,i+1,projection='3d')
    ax.add_collection3d(Poly3DCollection(tri,facecolors=shade(tri),edgecolor='none'))
    ax.set_xlim(-WUNIT/2-1,WUNIT/2+1); ax.set_ylim(-4,DEPTH); ax.set_zlim(0,rv[:,2].max()+1)
    ax.set_box_aspect((WUNIT,DEPTH+10,rv[:,2].max())); ax.view_init(elev=el,azim=az)
    ax.set_title(f"Scan-Einheit (2 Bögen), wasserdicht — {ti}"); ax.set_xlabel("m"); ax.set_zlabel("m"); ax.set_yticks([])
plt.tight_layout(); plt.savefig("daten/linach/scan_unit.png",dpi=115); print("Render: daten/linach/scan_unit.png")
