#!/usr/bin/env python3
"""
Kastelburg Waldkirch — OBJ → druckfertiges STL
Workflow: OBJ laden → in STL konvertieren → größte Komponente → Boden abschneiden → skalieren
"""
import sys, struct, numpy as np, os

TARGET_HEIGHT_MM = 120   # Druckhöhe (anpassen wie gewünscht)
CUT_FRAC = 0.03          # unterste 3% abschneiden (Boden-Rauschen)

def read_obj_as_tris(path):
    verts, tris = [], []
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith('v '):
                verts.append(list(map(float, line.split()[1:4])))
            elif line.startswith('f '):
                idx = [int(p.split('/')[0])-1 for p in line.split()[1:4]]
                if len(idx) == 3:
                    tris.append(idx)
    v = np.array(verts, dtype=np.float32)
    t = np.array(tris, dtype=np.int32)
    return v[t]  # (N,3,3)

def write_stl(tris, path):
    n = len(tris)
    with open(path, 'wb') as f:
        f.write(b'\x00'*80)
        f.write(struct.pack('<I', n))
        for tri in tris:
            ab = tri[1]-tri[0]; ac = tri[2]-tri[0]
            nrm = np.cross(ab, ac)
            l = np.linalg.norm(nrm)
            nrm = nrm/l if l>0 else nrm
            f.write(struct.pack('<fff', *nrm))
            for v in tri: f.write(struct.pack('<fff', *v))
            f.write(b'\x00\x00')
    print(f"Wrote {n} triangles → {path}")

def union_find_components(tris):
    N = len(tris)
    parent = list(range(N*3))
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[a]=b
    # build vertex→tri map
    vmap = {}
    for i,tri in enumerate(tris):
        for j,v in enumerate(tri):
            key = (round(float(v[0]),4), round(float(v[1]),4), round(float(v[2]),4))
            if key in vmap:
                union(i*3+j, vmap[key])
            else:
                vmap[key] = i*3+j
    roots = {}
    for i in range(N):
        r = find(i*3)
        roots.setdefault(r,[]).append(i)
    return list(roots.values())

def planar_cut(tris, z_cut):
    """Keep only tris fully above z_cut; interpolate edge tris."""
    kept = []
    for tri in tris:
        zs = tri[:,2]
        if zs.min() >= z_cut:
            kept.append(tri)
    return np.array(kept) if kept else tris

# ── main ──────────────────────────────────────────────────────────────────────
obj_path = sys.argv[1] if len(sys.argv)>1 else '/tmp/kastelburg_raw/kastelburg.obj'
print(f"Lade {obj_path} ...")
tris = read_obj_as_tris(obj_path)
print(f"  {len(tris)} Dreiecke geladen")

# Y-up → Z-up (OBJ ist meist Y-up)
tris = tris[:, :, [0,2,1]]
tris[:,:,1] *= -1  # flip Y nach vorne

# Bounding box
xmin,xmax = tris[:,:,0].min(), tris[:,:,0].max()
ymin,ymax = tris[:,:,1].min(), tris[:,:,1].max()
zmin,zmax = tris[:,:,2].min(), tris[:,:,2].max()
print(f"  Bbox: X{xmin:.1f}..{xmax:.1f}  Y{ymin:.1f}..{ymax:.1f}  Z{zmin:.1f}..{zmax:.1f}")

# Größte Komponente
print("Analysiere Komponenten ...")
comps = union_find_components(tris)
comps.sort(key=len, reverse=True)
print(f"  {len(comps)} Komponenten, größte: {len(comps[0])} Tris")
tris = tris[comps[0]]

# Boden abschneiden
zmin2 = tris[:,:,2].min()
zmax2 = tris[:,:,2].max()
z_cut = zmin2 + (zmax2-zmin2)*CUT_FRAC
print(f"  Boden-Cut bei Z={z_cut:.2f} (unterste {CUT_FRAC*100:.0f}%)")
tris = planar_cut(tris, z_cut)

# Re-base auf Z=0
zmin3 = tris[:,:,2].min()
tris[:,:,2] -= zmin3

# Skalieren auf Zielhöhe
current_h = tris[:,:,2].max()
scale = TARGET_HEIGHT_MM / current_h
tris *= scale
xmin,xmax = tris[:,:,0].min(), tris[:,:,0].max()
ymin,ymax = tris[:,:,1].min(), tris[:,:,1].max()
zmin,zmax = tris[:,:,2].min(), tris[:,:,2].max()
print(f"\nFertig: {xmax-xmin:.0f}×{ymax-ymin:.0f}×{zmax-zmin:.0f} mm @ Maßstab {scale:.4f}")

out = '/tmp/kastelburg_ready.stl'
write_stl(tris, out)
print(f"\n→ Bereit zum Slicen: {out}")
print(f"  Empfehlung: 0.20mm Schichten, hohl (0% Infill), Brim 5mm")
