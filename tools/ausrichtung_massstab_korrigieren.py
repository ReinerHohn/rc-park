#!/usr/bin/env python3
"""ausrichtung_massstab_korrigieren.py <SFM-AUSRICHTUNG.json> --faktor k --drehpunkt x y z --quelle "..." [--aus NEU.json] [--punkte a.npy b.npy ...] [--netz n.npz ...]

Massstab des Modellrahmens nachtraeglich korrigieren: X' = c + k (X - c) (Aehnlichkeit - Kameras bleiben Lochkameras, Fotowerkzeuge bleiben gueltig).
Lehre Schwabentor v3 15.11.2026: die uebertragene Ausrichtung war ~5,5 % zu gross. Belege: DOM1-Laser direkt abgefragt (Dachtraufe 37,2 m gegen 39,26 m
aus Foto-Triangulation, Vordach-Traufzone 16,4 gegen 17,3 m -> 0,946-0,948; Dachflaeche 169 m2 gegen 199,5 m2), Foto-GPS (Entfernung GPS/Modell 0,97),
Wolke je Seite schmaler als LoD2. Der Turm passte nur scheinbar zum LoD2-Grundriss (LoD2 = Sockelumring). Hoehe ist Sache des Lasers (KERNMETHODE).
'transformation' (X_m = R^T (X_sfm - t) / s): s' = s / k, t' = t - (s / k) (1 - k) R c. Kameras: R bleibt, t' = k t - (1 - k) R_c c, standort' = c + k (S - c).
--punkte / --netz: Punktwolken (npy, N x 3) und Netze (npz mit V) im alten Rahmen gleich mit umrechnen (an Ort und Stelle).
"""
import sys, json, argparse, numpy as np, cv2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ausrichtung"); ap.add_argument("--faktor", type=float, required=True); ap.add_argument("--drehpunkt", nargs=3, type=float, required=True)
    ap.add_argument("--quelle", required=True); ap.add_argument("--aus", default=""); ap.add_argument("--punkte", nargs="*", default=[]); ap.add_argument("--netz", nargs="*", default=[]); a = ap.parse_args()
    A = json.load(open(a.ausrichtung)); k = a.faktor; c = np.array(a.drehpunkt); T = A["transformation"]; s = T["s"]; R = cv2.Rodrigues(np.array(T["rvec"], float))[0]; t = np.array(T["t"], float)
    A["transformation"] = dict(T, s=s / k, t=(t - (s / k) * (1 - k) * (R @ c)).tolist())
    for q in A.get("kameras", {}).values():
        Rc = np.array(q["R"], float); q["t"] = (k * np.array(q["t"], float) - (1 - k) * (Rc @ c)).tolist(); q["standort"] = [round(float(v), 3) for v in (c + k * (np.array(q["standort"], float) - c))]
    A["massstabskorrektur"] = dict(werkzeug="ausrichtung_massstab_korrigieren.py", faktor=k, drehpunkt=c.tolist(), quelle=a.quelle)
    A["verfahren"] = A.get("verfahren", "") + f" | Massstab x {k} um {c.tolist()} ({a.quelle[:80]})"
    json.dump(A, open(a.aus or a.ausrichtung, "w"), indent=1, ensure_ascii=False); print(f"Massstab x {k} um {c.tolist()}: {len(A.get('kameras', {}))} Kameras -> {a.aus or a.ausrichtung}")
    for f in a.punkte: P = np.load(f); np.save(f, (c + k * (P.astype(np.float64) - c)).astype(np.float32)); print("  Punkte", f, len(P))
    for f in a.netz: Z = np.load(f); np.savez_compressed(f, **{**{n: Z[n] for n in Z.files}, "V": (c + k * (Z["V"].astype(np.float64) - c)).astype(np.float32)}); print("  Netz", f)


if __name__ == "__main__":
    main()
