#!/usr/bin/env python3
"""drone_to_print.py — Drohnen-/Photogrammetriescan → druckfertiges, wasserdichtes STL.

Scans (OBJ/PLY/GLB) sind offene, einseitige Flächen mit Schwebe-Fragmenten — nicht
druckbar. Dieses Tool macht sie wasserdicht & FDM-tauglich. Zwei Modi:

  --mode detail  (Standard für MOTIVE: Kirchen, Türme, Fassaden, Burgen)
     echte Oberfläche behalten → Screened Poisson (pymeshlab) → größter Körper →
     auf Crop-Bbox + Boden kappen → aus GRUNDFLÄCHE skalieren. Detail bleibt erhalten.

  --mode terrain (für GELÄNDE/Massen ohne Detailanspruch)
     max-Z-Rasterung → Gelände-Trend (quadratischer Fit) abziehen → Relief auf dünner
     flacher Platte, wasserdicht. Immer stützenfrei. (Optional Vorstufe fürs Gitter.)

Beispiele:
  python3 tools/drone_to_print.py scan.obj --mode detail --crop -9.5 3.5 -3 8 --foot 160 --out burg.stl
  python3 tools/drone_to_print.py scan.obj --mode terrain --foot 190 --base 4 --out gelaende.stl

Lernkurve-Hinweise (siehe Memory drohnenscan_druckpipeline):
  - Maßstab IMMER aus der GRUNDFLÄCHE (--foot), nie aus der Höhe (sonst explodiert Footprint).
  - detail: Poisson wuchert über den Rand → Crop-Bbox kappt die Seiten (--crop angeben!).
  - terrain: Detrend verhindert dicken Sockel-Klotz am Hang; Ausreißer (Bäume) werden gekappt.
  - Höhenfeld-Previews (matplotlib/trimesh) TÄUSCHEN Blobs vor — echter GL-Render via --render.
"""
import argparse, sys, numpy as np, trimesh
from trimesh.intersections import slice_mesh_plane


def load_crop(path, crop):
    """Scan laden und optional per Dreiecks-Mittelpunkt auf Bbox (x0 x1 y0 y1) croppen."""
    m = trimesh.load(path, process=False, force='mesh')
    if crop:
        x0, x1, y0, y1 = crop
        c = m.triangles_center
        keep = (c[:,0]>=x0)&(c[:,0]<=x1)&(c[:,1]>=y0)&(c[:,1]<=y1)
        m = trimesh.Trimesh(vertices=m.vertices, faces=m.faces[keep], process=True)
        m.remove_unreferenced_vertices()
    else:
        m = trimesh.Trimesh(vertices=m.vertices, faces=m.faces, process=True)
    print(f"  geladen/gecroppt: {len(m.faces):,} faces, bbox xy "
          f"[{m.bounds[0][0]:.1f},{m.bounds[1][0]:.1f}]x[{m.bounds[0][1]:.1f},{m.bounds[1][1]:.1f}]")
    return m


def mode_detail(sub, crop, foot, depth, mincomp, bottom_frac):
    """Screened-Poisson-Rekonstruktion — Detail bleibt erhalten, wasserdicht."""
    import pymeshlab as ml
    tmp = '/tmp/_d2p_crop.ply'; sub.export(tmp)
    ms = ml.MeshSet(); ms.load_new_mesh(tmp)
    try: ms.meshing_remove_connected_component_by_face_number(mincomponentsize=mincomp, removeunref=True)
    except Exception: pass
    for f in ('compute_normal_per_vertex','recompute_vertex_normals'):
        try: getattr(ms, f)()
        except Exception: pass
    print(f"  Screened Poisson (depth={depth}) ...")
    ms.generate_surface_reconstruction_screened_poisson(
        depth=depth, fulldepth=5, samplespernode=1.5, pointweight=4.0, preclean=True)
    ms.save_current_mesh('/tmp/_d2p_poisson.ply')

    m = trimesh.load('/tmp/_d2p_poisson.ply')
    m = max(m.split(only_watertight=False), key=lambda b: len(b.faces))   # größter Körper
    # Poisson-„Ballon" über den Rand → auf Crop-Bbox kappen
    bx = (crop[0], crop[1]) if crop else (m.bounds[0][0], m.bounds[1][0])
    by = (crop[2], crop[3]) if crop else (m.bounds[0][1], m.bounds[1][1])
    pad = 0.25
    for n, o in [([1,0,0],[bx[0]+pad,0,0]),([-1,0,0],[bx[1]-pad,0,0]),
                 ([0,1,0],[0,by[0]+pad,0]),([0,-1,0],[0,by[1]-pad,0])]:
        m = slice_mesh_plane(m, plane_normal=n, plane_origin=o, cap=True)
    # Boden-Ballon weg + kleine flache Standfläche
    zmin, zmax = m.vertices[:,2].min(), m.vertices[:,2].max()
    m = slice_mesh_plane(m, plane_normal=[0,0,1],
                         plane_origin=[0,0,zmin+(zmax-zmin)*bottom_frac], cap=True)
    m = max(m.split(only_watertight=False), key=lambda b: len(b.faces))
    print(f"  final: watertight={m.is_watertight} bodies={m.body_count} faces={len(m.faces):,}")
    return m


def mode_terrain(sub, crop, foot, grid, base, detrend, cap_pct):
    """Höhenfeld mit optionalem Gelände-Detrend → wasserdichtes Volumen auf dünner Platte."""
    from scipy import ndimage
    x0, x1, y0, y1 = crop if crop else (sub.bounds[0][0], sub.bounds[1][0],
                                        sub.bounds[0][1], sub.bounds[1][1])
    nx = ny = grid; dx = (x1-x0)/nx; dy = (y1-y0)/ny
    tri = sub.vertices[sub.faces]; v0,v1,v2 = tri[:,0],tri[:,1],tri[:,2]
    H = np.full((ny,nx), -1e9, dtype=np.float32)
    el = np.maximum.reduce([np.linalg.norm(v1-v0,axis=1),
                            np.linalg.norm(v2-v1,axis=1),
                            np.linalg.norm(v0-v2,axis=1)])
    nsamp = np.clip((el/min(dx,dy)*1.5).astype(int),1,40)
    rng = np.random.default_rng(0)
    for k in range(len(tri)):
        n = nsamp[k]; a = rng.random(n); b = rng.random(n)
        o = a+b>1; a[o]=1-a[o]; b[o]=1-b[o]
        p = v0[k]+a[:,None]*(v1[k]-v0[k])+b[:,None]*(v2[k]-v0[k])
        p = np.vstack([p, v0[k], v1[k], v2[k]])
        jx = np.clip(((p[:,0]-x0)/dx).astype(int),0,nx-1)
        iy = np.clip(((p[:,1]-y0)/dy).astype(int),0,ny-1)
        np.maximum.at(H,(iy,jx),p[:,2])
    mask = H < -1e8
    idx = ndimage.distance_transform_edt(mask, return_distances=False, return_indices=True)
    H = ndimage.median_filter(H[tuple(idx)], size=3)

    if detrend:
        B=20; gx=np.linspace(0,nx,B+1).astype(int); gy=np.linspace(0,ny,B+1).astype(int)
        cx,cy,cz=[],[],[]
        for i in range(B):
            for j in range(B):
                cz.append(np.percentile(H[gy[i]:gy[i+1],gx[j]:gx[j+1]],10))
                cy.append((gy[i]+gy[i+1])/2); cx.append((gx[j]+gx[j+1])/2)
        cx,cy,cz=map(np.array,(cx,cy,cz))
        A=np.column_stack([np.ones_like(cx),cx,cy,cx*cx,cy*cy,cx*cy])
        co,*_=np.linalg.lstsq(A,cz,rcond=None)
        J,I=np.meshgrid(np.arange(nx),np.arange(ny))
        trend=(co[0]+co[1]*J+co[2]*I+co[3]*J*J+co[4]*I*I+co[5]*J*I).astype(np.float32)
        relief=np.clip(H-trend,0,None)
    else:
        relief=H-H.min()
    relief=np.clip(relief,0,np.percentile(relief,cap_pct))
    relief=ndimage.median_filter(relief,size=2)
    print(f"  Relief 0..{relief.max():.2f} (detrend={detrend})")

    scale=foot/max(x1-x0,y1-y0); base_model=base/scale
    xs=x0+(np.arange(nx)+0.5)*dx; ys=y0+(np.arange(ny)+0.5)*dy
    XX,YY=np.meshgrid(xs,ys); NT=nx*ny
    top=np.column_stack([XX.ravel(),YY.ravel(),relief.ravel()])
    bot=np.column_stack([XX.ravel(),YY.ravel(),np.full(NT,-base_model)])
    V=np.vstack([top,bot]); faces=[]
    I2,J2=np.mgrid[0:ny-1,0:nx-1]; I2=I2.ravel(); J2=J2.ravel()
    a=I2*nx+J2; b=a+1; cc=(I2+1)*nx+J2; d=cc+1
    faces += [np.column_stack([a,cc,b]), np.column_stack([b,cc,d])]
    faces += [np.column_stack([a+NT,b+NT,cc+NT]), np.column_stack([b+NT,d+NT,cc+NT])]
    def wall(it):
        it=np.array(it); ib=it+NT; f=[]
        for k in range(len(it)-1):
            f.append([it[k],ib[k],it[k+1]]); f.append([it[k+1],ib[k],ib[k+1]])
        return np.array(f)
    tr=np.arange(0,nx); br=np.arange((ny-1)*nx,ny*nx)
    lc=np.arange(0,ny)*nx; rc=lc+(nx-1)
    for e,fl in [(tr,False),(br,True),(lc,True),(rc,False)]:
        faces.append(wall(e[::-1] if fl else e))
    m=trimesh.Trimesh(vertices=V,faces=np.vstack(faces),process=True)
    trimesh.repair.fix_normals(m)
    print(f"  solid: watertight={m.is_watertight} body={m.body_count} faces={len(m.faces):,}")
    return m


def finish_and_export(m, foot, out, render):
    scale = foot / max(m.extents[0], m.extents[1])
    m.apply_scale(scale); m.vertices[:,2] -= m.vertices[:,2].min()
    e = m.extents
    print(f"Maße: {e[0]:.0f} x {e[1]:.0f} x {e[2]:.0f} mm (Maßstab {scale:.2f}x)")
    m.export(out); print(f"→ {out}")
    if render:
        try:
            sc=m.scene(); sc.set_camera(angles=(np.radians(62),0,np.radians(130)),
                                        distance=m.extents.max()*2.1, center=m.centroid)
            png=out.rsplit('.',1)[0]+'_gl.png'
            open(png,'wb').write(sc.save_image(resolution=(1100,850), visible=True))
            print(f"GL-Render → {png}")
        except Exception as ex:
            print(f"GL-Render fehlgeschlagen ({ex}); braucht DISPLAY=:0")


def main():
    p=argparse.ArgumentParser(description="Drohnenscan → druckfertiges STL")
    p.add_argument('input'); p.add_argument('--out', required=True)
    p.add_argument('--mode', choices=['detail','terrain'], default='detail')
    p.add_argument('--crop', nargs=4, type=float, metavar=('X0','X1','Y0','Y1'))
    p.add_argument('--foot', type=float, default=160.0, help='Grundfläche-Kante [mm]')
    p.add_argument('--render', action='store_true', help='echter GL-Render (DISPLAY=:0)')
    # detail
    p.add_argument('--depth', type=int, default=11)
    p.add_argument('--mincomp', type=int, default=1500)
    p.add_argument('--bottom-frac', type=float, default=0.10)
    # terrain
    p.add_argument('--grid', type=int, default=560)
    p.add_argument('--base', type=float, default=4.0)
    p.add_argument('--no-detrend', action='store_true')
    p.add_argument('--cap-pct', type=float, default=99.9)
    a=p.parse_args()

    print(f"Lade {a.input} ...")
    sub=load_crop(a.input, a.crop)
    if a.mode=='detail':
        m=mode_detail(sub, a.crop, a.foot, a.depth, a.mincomp, a.bottom_frac)
    else:
        m=mode_terrain(sub, a.crop, a.foot, a.grid, a.base, not a.no_detrend, a.cap_pct)
    finish_and_export(m, a.foot, a.out, a.render)

if __name__=='__main__':
    main()
