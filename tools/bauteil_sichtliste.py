#!/usr/bin/env python3
"""bauteil_sichtliste.py - Sichtliste je Bauteil (Koordinator/Nutzer 2026-11-09, Pflicht nach jedem Bau):
jedes aktive Bauteil bekommt das Foto, auf dem es am besten zu sehen ist (groesste UNVERDECKTE Pixelflaeche), und ein Overlay-Ausschnitt auf diesem Foto.

  bauteil_sichtliste.py --bauteile DIR (baukasten_gen BAUTEILE_AUS=DIR: je Bauteil <typ>.stl in mm) --fotos KAM.json --bilder DIR --out DIR
                        [--massstab 87] [--stufe 0.2] [--max_fotos 0] [--fest typ=foto.jpg ...] [--nur_fotos a.jpg,b.jpg]
Ablauf: alle Bauteile zu EINEM Netz mit Bauteil-Etikett je Dreieck -> je Foto GPU-Z-Puffer (render_kern.dreiecke_rastern, verkleinert um --stufe) ->
sichtbare Pixel je Bauteil; Wertung = sichtbare Pixel * Sichtanteil (sichtbar / projiziert, ohne Verdeckung gerastert), damit ein halb verdecktes Teil
nicht gegen ein freies gewinnt. Dann je Bauteil: Kanten (Knick + Umriss) mit Z-Puffer-Sichtpruefung rot ueber das Foto, Ausschnitt = Bauteilbox + Rand.
Schreibt <out>/sichtliste.json (Bauteil -> Foto, Pixel, Sichtanteil, Ausschnitt) und <out>/<bauteil>.jpg, <out>/uebersicht.jpg (Kontaktbogen).
Generisch: keine Objektnamen; Rahmen = Rahmen der Kameradatei (muss der Modellrahmen sein)."""
import os, sys, json, glob, argparse, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch, render_kern as RK
ap = argparse.ArgumentParser(); ap.add_argument("--bauteile", required=True); ap.add_argument("--fotos", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--stufe", type=float, default=0.2); ap.add_argument("--max_fotos", type=int, default=0)
ap.add_argument("--fest", nargs="*", default=[]); ap.add_argument("--nur_fotos"); ap.add_argument("--winkel", type=float, default=0.6); ap.add_argument("--wolke", help="Punktwolke (npy, Modellrahmen) fuer Fremdverdeckung")
ap.add_argument("--kandidaten", type=int, default=8); a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
_lp = os.path.join(a.bauteile, "liste.json")                                                          # Liste des letzten Generatorlaufs (abgeschaltete Bauteile liegen evtl. noch als STL im Ordner)
dateien = sorted(os.path.join(a.bauteile, e["datei"]) for e in json.load(open(_lp)).values() if e["modus"] == "anbau") if os.path.exists(_lp) else \
          sorted(f for f in glob.glob(os.path.join(a.bauteile, "*.stl")) if not f.endswith("__ausschnitt.stl"))
namen = [os.path.basename(f)[:-4].replace("__", ":") for f in dateien]; teile = []
for f in dateien: m = trimesh.load(f, process=False); m.apply_scale(a.massstab / 1000.0); teile.append(m)
alle = trimesh.util.concatenate(teile); etik = np.concatenate([np.full(len(m.faces), i) for i, m in enumerate(teile)]); NB = len(teile)
kam = json.load(open(a.fotos)); fotos = sorted(kam) if not a.nur_fotos else a.nur_fotos.split(",")
if a.max_fotos: fotos = fotos[::max(1, len(fotos) // a.max_fotos)]
fest = dict(s.split("=", 1) for s in a.fest)
etik_g = torch.as_tensor(etik, device="cuda")
def zaehlen(mesh, et, k, s):
    W, H = int(k["W"] * s), int(k["H"] * s)
    _, fid, _ = RK.dreiecke_rastern(mesh, np.array(k["Rn"]), np.array(k["tn"]), k["f"] * s, k["cx"] * s, k["cy"] * s, W, H, als_torch=True)
    fid = fid.reshape(-1); fid = fid[fid >= 0]
    return torch.bincount(et[fid], minlength=NB).cpu().numpy() if len(fid) else np.zeros(NB, int)
sicht = np.zeros((len(fotos), NB)); proj = np.zeros((len(fotos), NB))
for i, fo in enumerate(fotos):
    k = kam[fo]; sicht[i] = zaehlen(alle, etik_g, k, a.stufe)
    if i % 50 == 0: print(f"  Foto {i + 1}/{len(fotos)}", flush=True)
# Sichtanteil: Teil allein gerastert (ohne Verdeckung), nur fuer die besten 5 Kandidaten je Teil (teuer)
# Zusatz (Runde 6, erster Lauf: Kameras UNTER der Arkade 'sahen' Giebel/Helm durch das nicht modellierte Gewoelbe): Fremdverdeckung aus der echten Wolke
# (--wolke: Wolkenpunkt > 0,5 m VOR der Modelltiefe auf einem Bauteilpixel = etwas Reales verdeckt das Teil) und Bildanteil (Teil-Ecken im Bild).
WOLKE = torch.as_tensor(np.load(a.wolke)[:, :3][::max(1, len(np.load(a.wolke, mmap_mode="r")) // 400000)].astype(np.float32), device="cuda") if a.wolke else None
def rahmen_und_fremd(b, k):
    s = a.stufe; W, H = int(k["W"] * s), int(k["H"] * s); R = np.array(k["Rn"]); t = np.array(k["tn"])
    V = np.asarray(teile[b].vertices) @ R.T + t; z = V[:, 2]; uu = k["f"] * V[:, 0] / np.maximum(z, 1e-3) + k["cx"]; vv = k["f"] * V[:, 1] / np.maximum(z, 1e-3) + k["cy"]
    im_bild = float(((z > 1) & (uu >= 0) & (uu < k["W"]) & (vv >= 0) & (vv < k["H"])).mean())
    if WOLKE is None: return im_bild, 0.0
    depth, fid, _ = RK.dreiecke_rastern(alle, R, t, k["f"] * s, k["cx"] * s, k["cy"] * s, W, H, als_torch=True)
    depth = torch.as_tensor(np.asarray(depth.cpu() if hasattr(depth, "cpu") else depth, np.float32), device="cuda").reshape(-1); fid = fid.reshape(-1)
    Rg = torch.as_tensor(R, dtype=torch.float32, device="cuda"); tg = torch.as_tensor(t, dtype=torch.float32, device="cuda"); X = WOLKE @ Rg.T + tg; zc = X[:, 2]
    ok = zc > 1; u_ = torch.round(k["f"] * s * X[:, 0] / zc.clamp(min=1e-3) + k["cx"] * s).long(); v_ = torch.round(k["f"] * s * X[:, 1] / zc.clamp(min=1e-3) + k["cy"] * s).long()
    ok &= (u_ >= 0) & (u_ < W) & (v_ >= 0) & (v_ < H); cw = torch.full((W * H,), float("inf"), device="cuda")
    cw.scatter_reduce_(0, (v_[ok] * W + u_[ok]), zc[ok], reduce="amin")
    meins = (fid >= 0) & (etik_g[fid.clamp(min=0)] == b)
    if int(meins.sum()) == 0: return im_bild, 0.0
    return im_bild, float(((cw[meins] < depth[meins] - 0.5).float().mean()))
ergebnis = {}
for b in range(NB):
    if namen[b] in fest and fest[namen[b]] in fotos: kand = [fotos.index(fest[namen[b]])]
    else: kand = list(np.argsort(-sicht[:, b])[:a.kandidaten])
    best = None
    for i in kand:
        if sicht[i, b] <= 0: continue
        allein = zaehlen(teile[b], torch.zeros(len(teile[b].faces), dtype=torch.long, device="cuda"), kam[fotos[i]], a.stufe)[0]
        ant = float(sicht[i, b] / max(allein, 1)); im_bild, fremd = rahmen_und_fremd(b, kam[fotos[i]])
        wert = float(sicht[i, b]) * ant * im_bild * (1.0 - fremd) ** 2
        if best is None or wert > best[0]: best = (wert, i, ant, im_bild, fremd)
    if best is None: ergebnis[namen[b]] = dict(foto=None, hinweis="in keinem Foto sichtbar -> ungeprueft"); continue
    ergebnis[namen[b]] = dict(foto=fotos[best[1]], pixel_sichtbar=int(sicht[best[1], b] / a.stufe ** 2), sichtanteil=round(best[2], 3), im_bild=round(best[3], 3), fremdverdeckt=round(best[4], 3))
# Overlays: Kanten des Bauteils mit Z-Puffer (ganzes Netz) gegen das Foto
def overlay(b, fo):
    k = kam[fo]; R = np.array(k["Rn"], float); t = np.array(k["tn"], float).ravel(); f, cx, cy = float(k["f"]), float(k["cx"]), float(k["cy"])
    im = cv2.imread(os.path.join(a.bilder, fo), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); H, W = im.shape[:2]
    depth, _, _ = RK.dreiecke_rastern(alle, R, t, f, cx, cy, W, H, als_torch=True); D = torch.as_tensor(np.asarray(depth.cpu() if hasattr(depth, "cpu") else depth, np.float32), device="cuda")
    mm = teile[b].copy(); mm.merge_vertices(); V = np.asarray(mm.vertices); C = -R.T @ t
    if len(mm.faces) < 2: return None
    fa = mm.face_adjacency; Nf = mm.face_normals; Fc = mm.triangles_center; vor = ((C[None] - Fc) * Nf).sum(1) > 0
    sel = (mm.face_adjacency_angles > a.winkel) | (vor[fa[:, 0]] != vor[fa[:, 1]]); ed = mm.face_adjacency_edges[sel]
    def pr(P): X = P @ R.T + t; z = np.maximum(X[:, 2], 1e-3); return f * X[:, :2] / z[:, None] + [cx, cy], X[:, 2]
    p0, z0 = pr(V[ed[:, 0]]); p1, z1 = pr(V[ed[:, 1]]); L = np.linalg.norm(p1 - p0, axis=1); ns = np.clip(np.ceil(L / 3.0), 1, 4000).astype(int)
    ei = np.repeat(np.arange(len(ed)), ns); off = np.arange(ns.sum()) - np.repeat(np.cumsum(ns) - ns, ns); s = (off + 0.5) / np.repeat(ns, ns)
    Pw = V[ed[ei, 0]] * (1 - s)[:, None] + V[ed[ei, 1]] * s[:, None]; X = Pw @ R.T + t; z = X[:, 2]
    u = np.round(f * X[:, 0] / np.maximum(z, 1e-3) + cx).astype(int); v = np.round(f * X[:, 1] / np.maximum(z, 1e-3) + cy).astype(int)
    drin = (z > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H); ok = np.zeros(len(Pw), bool)
    if drin.any(): dz = D[torch.as_tensor(v[drin], device="cuda"), torch.as_tensor(u[drin], device="cuda")].cpu().numpy(); ok[drin] = z[drin] <= dz + np.maximum(0.08, 0.008 * z[drin])
    nsr = np.repeat(ns, ns); A_ = p0[ei] + (p1 - p0)[ei] * (off / nsr)[:, None]; B_ = p0[ei] + (p1 - p0)[ei] * ((off + 1) / nsr)[:, None]
    for i in np.nonzero(ok)[0]: cv2.line(im, tuple(np.round(A_[i]).astype(int)), tuple(np.round(B_[i]).astype(int)), (0, 0, 255), 2)
    for i in np.nonzero(drin & ~ok & (off % 3 == 0))[0]: cv2.line(im, tuple(np.round(A_[i]).astype(int)), tuple(np.round(B_[i]).astype(int)), (255, 160, 0), 1)
    uv, zz = pr(np.asarray(teile[b].vertices)); g = zz > 1; uv = uv[g]
    if not len(uv): return None
    x0, y0 = np.clip(uv.min(0) - 120, 0, [W - 1, H - 1]).astype(int); x1, y1 = np.clip(uv.max(0) + 120, 0, [W - 1, H - 1]).astype(int)
    if x1 - x0 < 40 or y1 - y0 < 40: return None
    c = im[y0:y1, x0:x1]; sc = min(1.0, 900 / max(c.shape[:2])); c = cv2.resize(c, None, fx=sc, fy=sc)
    cv2.putText(c, f"{namen[b]} | {fo}", (6, 22), 0, 0.6, (0, 255, 255), 2); del D; torch.cuda.empty_cache()
    return c, [int(x0), int(y0), int(x1), int(y1)], float(ok[drin].mean()) if drin.any() else 0.0
kacheln = []
for b in range(NB):
    e = ergebnis[namen[b]]
    if not e.get("foto"): continue
    r = overlay(b, e["foto"])
    if r is None: e["hinweis"] = "Ausschnitt zu klein/leer"; continue
    c, box, ks = r; fn = namen[b].replace(":", "__") + ".jpg"; cv2.imwrite(os.path.join(a.out, fn), c); e.update(bild=fn, ausschnitt_px=box, kanten_sichtbar=round(ks, 3))
    k_ = cv2.resize(c, (360, int(360 * c.shape[0] / c.shape[1]))) if c.shape[1] else c; kacheln.append(k_[:360] if k_.shape[0] > 360 else np.vstack([k_, np.zeros((360 - k_.shape[0], 360, 3), np.uint8)]))
json.dump(dict(fotos_geprueft=len(fotos), stufe=a.stufe, bauteile=ergebnis), open(os.path.join(a.out, "sichtliste.json"), "w"), indent=1, ensure_ascii=False)
if kacheln:
    while len(kacheln) % 5: kacheln.append(np.zeros_like(kacheln[0]))
    cv2.imwrite(os.path.join(a.out, "uebersicht.jpg"), np.vstack([np.hstack(kacheln[i:i + 5]) for i in range(0, len(kacheln), 5)]))
for n_, e in ergebnis.items(): print(f"  {n_:28s} {str(e.get('foto')):42s} px {e.get('pixel_sichtbar', 0):>9} Sichtanteil {e.get('sichtanteil', 0)}")
print("geschrieben", os.path.join(a.out, "sichtliste.json"))
