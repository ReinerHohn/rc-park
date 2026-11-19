#!/usr/bin/env python3
"""seiten_anhang_wachsen_1119.py <modell_mit_anhang> <seitenmodell_vorher> <kontrolle.txt> [--min-punkte 300] [--min-flaeche 0.3] [--aus liste.txt] - VERSUCH 19.11.2026 ('Post-its'):
angehaengte Bilder nur annehmen, wenn sie am GERUEST haengen. Vertrauenswuerdig sind zuerst die Bilder des Seitenmodells; ein 3D-Punkt ist vertrauenswuerdig, wenn ihn
>= 2 vertrauenswuerdige Bilder sehen; ein Bild wird angenommen, wenn es >= min-punkte solche Punkte auf >= min-flaeche seiner Bildflaeche (6x6-Raster) sieht. Wiederholen bis
nichts mehr dazukommt. Kontrolle: absichtlich mit angehaengte Bilder der ANDEREN Seite - sie duerfen in keiner Runde angenommen werden."""
import sys, argparse, collections
import numpy as np, pycolmap
ap = argparse.ArgumentParser(); ap.add_argument("modell"); ap.add_argument("vorher"); ap.add_argument("kontrolle"); ap.add_argument("--min-punkte", type=int, default=300); ap.add_argument("--min-flaeche", type=float, default=0.3); ap.add_argument("--aus"); a = ap.parse_args()
r = pycolmap.Reconstruction(a.modell); alt = {im.name for im in pycolmap.Reconstruction(a.vorher).images.values() if im.has_pose}; ko = set(l.strip() for l in open(a.kontrolle) if l.strip())
B = {}
for im in r.images.values():
    if not im.has_pose: continue
    cam = r.cameras[im.camera_id]; xy = np.array([p.xy for p in im.points2D]); pid = np.array([p.point3D_id if p.has_point3D() else -1 for p in im.points2D], dtype=np.int64)
    z = np.clip((xy[:, 1] / cam.height * 6).astype(int), 0, 5) * 6 + np.clip((xy[:, 0] / cam.width * 6).astype(int), 0, 5); B[im.name] = (pid, z, np.bincount(z, minlength=36) >= 20)
gut = set(n for n in B if n in alt); runde = 0
while True:
    cnt = collections.Counter()
    for n in gut: cnt.update(set(B[n][0][B[n][0] >= 0].tolist()))
    pg = np.array(sorted(k for k, c in cnt.items() if c >= 2), dtype=np.int64); neu = set()
    for n, (pid, z, voll) in B.items():
        if n in gut: continue
        m = np.isin(pid, pg)
        if m.sum() >= a.min_punkte and ((np.bincount(z[m], minlength=36) >= 3) & voll).sum() / max(1, voll.sum()) >= a.min_flaeche: neu.add(n)
    runde += 1; print(f"Runde {runde}: +{len(neu)} Bilder (davon Kontrolle {len(neu & ko)}), vertrauenswuerdige Punkte {len(pg)}", flush=True)
    if not neu: break
    gut |= neu
kand = [n for n in B if n not in alt and n not in ko]; q = lambda x: x.split("__vf_")[0][-11:] if "__vf_" in x else x.split("__")[0]
print(f"angenommen: {len(gut) - len(alt & set(B))} neue Bilder; Kandidaten {sum(n in gut for n in kand)} von {len(kand)} registrierten; Kontrolle (falsche Seite) {len(gut & ko)} von {len(ko & set(B))}")
print("angenommen je Quelle:", dict(collections.Counter(q(n) for n in gut if n not in alt).most_common(12))); print("abgelehnt je Quelle:", dict(collections.Counter(q(n) for n in kand if n not in gut).most_common(12)))
if a.aus: open(a.aus, "w").write("\n".join(sorted(gut)) + "\n")
