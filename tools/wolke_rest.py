#!/usr/bin/env python3
"""wolke_rest.py - WAS FEHLT DEM MODELL ALS KOERPER? Rest der dichten Wolke, der nicht an der Modellflaeche liegt, als Haufen mit Ort und Grobform (21.11.2026).

Anlass (Nutzer 21.11.: "von null ... der Handstand darf keine Rolle spielen ... vielleicht braucht man die dichte Wolke doch"): die Ebenen-Schleife sieht nur, was an einer
Wandebene liegt. Ganze Koerper (Treppenturm, Laterne, Dachueberstand, Anbau) liegen auf keiner Wandebene -> kein Kandidat. Im Handstand kamen genau diese Koerper aus der
dichten Wolke (Treppenturm = Kreisausgleich der Wolke, Dach = Traufecken) - hier dasselbe ohne Vorwissen:
  1. Modellflaeche abtasten, Wolkenpunkte weiter als --fern (0,35 m) davon = REST.
  2. Rest in --zelle-Wuerfel (0,4 m), zusammenhaengende Haufen; nur Haufen, die das Modell beruehren (naechster Punkt <= --anschluss), sonst Umgebung (Nachbarhaus, Baum, Strasse).
  3. Je Haufen: Kasten, Punktzahl, groesster Abstand vom Modell, Grobform: 'rund' (Kreisausgleich im Grundriss, Rest <= 8 cm), 'platte' (duennste Hauptachse <= 0,25 m), sonst 'koerper'.
Kernmethode: die Wolke nennt nur WO und GROB WAS; die Masse kommen danach aus Fotokanten auf den Ebenen dieses Haufens.
Aufruf: wolke_rest.py <objekt.json> <wolke.npy> [--stl S] [--bild audit/wolke_rest.jpg]   Ausgabe: audit/wolke_rest.json
"""
import sys, os, json, argparse, numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER)


def kreis(xy):
    A = np.c_[2 * xy, np.ones(len(xy))]; b = (xy ** 2).sum(1); s = np.linalg.lstsq(A, b, rcond=None)[0]; r = float(np.sqrt(max(s[2] + s[0] ** 2 + s[1] ** 2, 0)))
    return float(s[0]), float(s[1]), r, float(np.median(np.abs(np.hypot(xy[:, 0] - s[0], xy[:, 1] - s[1]) - r)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("wolke"); ap.add_argument("--stl"); ap.add_argument("--fern", type=float, default=0.35); ap.add_argument("--zelle", type=float, default=0.4)
    ap.add_argument("--anschluss", type=float, default=0.8); ap.add_argument("--weit", type=float, default=4.0, help="Punkte weiter weg vom Modell = Umgebung, nicht betrachtet"); ap.add_argument("--min_p", type=int, default=150)
    ap.add_argument("--jeder", type=int, default=6); ap.add_argument("--boden", type=float, default=1.0); ap.add_argument("--bild", default=""); ap.add_argument("--uebernehmen", action="store_true", help="runde Haufen mit Drehprofil nach audit/koerper_auto.json (Eingang bauteile.drehkoerper_aus_wolkenrest)"); a = ap.parse_args()
    import trimesh
    from scipy.spatial import cKDTree
    from scipy import ndimage
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); obj = json.load(open(objp)); stl = a.stl or os.path.join(ROOT, obj["stl"]); m = trimesh.load(stl); m.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0)
    S = np.asarray(m.sample(1500000), np.float32); lo, hi = S.min(0), S.max(0); W = np.asarray(np.load(a.wolke, mmap_mode="r")[::a.jeder, :3], np.float32)
    ok = np.all((W > lo - a.weit) & (W < hi + a.weit), 1) & (W[:, 2] > lo[2] + a.boden); W = W[ok]; d, _ = cKDTree(S).query(W, workers=-1); R = W[(d > a.fern) & (d < a.weit)]; dR = d[(d > a.fern) & (d < a.weit)]
    print(f"Wolke im Kasten: {len(W)} Punkte, an der Modellflaeche (<= {a.fern} m): {(d <= a.fern).mean() * 100:.0f} %, Rest bis {a.weit} m: {len(R)}")
    g0 = R.min(0); I = ((R - g0) / a.zelle).astype(int); G = np.zeros(I.max(0) + 1, np.int32); np.add.at(G, tuple(I.T), 1); L, n = ndimage.label(G >= 3, structure=np.ones((3, 3, 3))); lab = L[tuple(I.T)]; H = []
    for k in range(1, n + 1):
        s = lab == k
        if s.sum() < a.min_p: continue
        P = R[s].astype(float); dk = dR[s]
        if dk.min() > a.anschluss: continue                                                   # beruehrt das Modell nicht -> Umgebung
        c = P - P.mean(0); ev = np.sqrt(np.maximum(np.linalg.eigvalsh(np.cov(c.T)), 0)); cx, cy, r, res = kreis(P[:, :2]); hoehe = float(P[:, 2].max() - P[:, 2].min())
        form = "rund" if (res <= 0.08 and 0.4 <= r <= 4.0 and hoehe >= 1.5) else ("platte" if ev[0] <= 0.25 and ev[1] >= 0.6 else "koerper")
        prof = None
        if form == "rund":                                                                    # DREHPROFIL r(z) aus der Wolke um die gefundene Achse: Schaft, Gesims, Haube ohne Musterteil
            rr = np.hypot(W[:, 0] - cx, W[:, 1] - cy); nah = (rr < r + 0.9) & (d > 0.15) & (W[:, 2] < P[:, 2].max() + 6.0); zz = W[nah, 2]; rq = rr[nah]; prof = []
            for z0 in np.arange(float(P[:, 2].min()), float(zz.max()) if nah.any() else 0.0, 0.25):
                q = rq[(zz >= z0) & (zz < z0 + 0.25)]
                if len(q) < 25:
                    if prof and z0 > P[:, 2].max(): break
                    continue
                hh, kk = np.histogram(q, bins=np.arange(0.0, r + 0.95, 0.05)); j = int(np.argmax(hh * kk[1:]))      # dichteste Schale (flaechengewichtet), nicht der Median: Innenpunkte/Nachbarwand stoeren
                prof.append([round(float(z0 + 0.125), 2), round(float(np.median(q[(q >= kk[j] - 0.05) & (q < kk[j + 1] + 0.05)])), 3), int(len(q))])
        H.append(dict(profil=prof, punkte=int(s.sum()), kasten=[round(float(x), 2) for x in np.r_[P.min(0), P.max(0)]], abstand_max=round(float(np.percentile(dk, 95)), 2), abstand_median=round(float(np.median(dk)), 2),
                      form=form, kreis=dict(x=round(cx, 2), y=round(cy, 2), r=round(r, 2), rest=round(res, 3)) if form == "rund" else None, staerke=[round(float(x), 2) for x in ev]))
    H.sort(key=lambda h: -h["punkte"])
    for i, h in enumerate(H):
        h["id"] = f"r{i:02d}"; k = h["kasten"]
        print(f"{h['id']}: {h['punkte']:6d} Punkte  x {k[0]:.1f}..{k[3]:.1f}  y {k[1]:.1f}..{k[4]:.1f}  z {k[2]:.1f}..{k[5]:.1f}  Abstand Median {h['abstand_median']} / 95 % {h['abstand_max']} m  Form: {h['form']}"
              + (f" (Kreis r {h['kreis']['r']} m, Rest {h['kreis']['rest']} m)" if h["kreis"] else ""))
    A = os.path.join(od, "audit"); os.makedirs(A, exist_ok=True); json.dump(dict(quelle="tools/wolke_rest.py", stl=os.path.relpath(stl, ROOT), wolke=a.wolke, fern=a.fern, an_flaeche=round(float((d <= a.fern).mean()), 3), haufen=H),
                                                                            open(os.path.join(A, "wolke_rest.json"), "w"), indent=1)
    if a.uebernehmen:                                                                         # gefundene Koerper DAUERHAFT ablegen: nach dem Bau liegt der Haufen am Modell und verschwindet aus dem Rest
        kp = os.path.join(A, "koerper_auto.json"); K = json.load(open(kp)).get("haufen", []) if os.path.exists(kp) else []
        for h in H:
            if h.get("profil") and len(h["profil"]) >= 4 and not any(np.hypot(k["kreis"]["x"] - h["kreis"]["x"], k["kreis"]["y"] - h["kreis"]["y"]) < 1.0 for k in K):
                K.append(dict(h, id=f"rund{len(K)}", an_flaeche_vorher=round(float((d <= a.fern).mean()), 3))); print(f"uebernommen als Kandidat: {K[-1]['id']} (r {h['kreis']['r']} m)")
        json.dump(dict(quelle="tools/wolke_rest.py --uebernehmen", haufen=K), open(kp, "w"), indent=1)
    if a.bild:
        import cv2
        px = 0.05; B = []
        for (i, j, nm) in ((0, 2, "von Sueden/Norden (x-z)"), (1, 2, "von Osten/Westen (y-z)"), (0, 1, "Grundriss (x-y)")):
            a0 = min(lo[i], R[:, i].min()) - 0.5; b0 = min(lo[j], R[:, j].min()) - 0.5; w_ = int((max(hi[i], R[:, i].max()) + 0.5 - a0) / px); h_ = int((max(hi[j], R[:, j].max()) + 0.5 - b0) / px); im = np.full((h_, w_, 3), 255, np.uint8)
            q = S[::6]; im[np.clip(h_ - 1 - ((q[:, j] - b0) / px).astype(int), 0, h_ - 1), np.clip(((q[:, i] - a0) / px).astype(int), 0, w_ - 1)] = (200, 200, 200)
            im[np.clip(h_ - 1 - ((R[:, j] - b0) / px).astype(int), 0, h_ - 1), np.clip(((R[:, i] - a0) / px).astype(int), 0, w_ - 1)] = (150, 170, 255)
            for h in H[:14]:
                k = h["kasten"]; p0 = (int((k[i] - a0) / px), h_ - 1 - int((k[j + 3] - b0) / px)); p1 = (int((k[i + 3] - a0) / px), h_ - 1 - int((k[j] - b0) / px)); cv2.rectangle(im, p0, p1, (0, 0, 200), 2)
                cv2.putText(im, h["id"], (p0[0] + 3, p0[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 200), 2)
            cv2.putText(im, nm, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2); B.append(im)
        hh = max(b.shape[0] for b in B); B = [cv2.copyMakeBorder(b, hh - b.shape[0], 0, 0, 12, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for b in B]; cv2.imwrite(a.bild, np.hstack(B), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"-> {os.path.join(A, 'wolke_rest.json')}: {len(H)} Haufen am Modell"); return 0


if __name__ == "__main__": sys.exit(main())
