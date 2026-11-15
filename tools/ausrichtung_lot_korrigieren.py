#!/usr/bin/env python3
"""ausrichtung_lot_korrigieren.py <SFM-AUSRICHTUNG.json> <lot_aus_fotos.json> --drehpunkt x y z [--aus NEU.json] - Rahmen starr so drehen, dass das Foto-Lot = z wird.

Lehre Schwabentor v3 15.11.2026 (Nutzer: "Fotowolke passt nicht ganz auf das Modell"): Die uebertragene Ausrichtung stand 0,77 Grad schief. Zwei unabhaengige
Belege: (1) Fluchtpunkte der Senkrechten in 84 Fotos (tools/lot_aus_fotos.py): up = (0,0123 / -0,0056 / 0,9999); (2) Wolkenwaende aller vier Turmseiten
wandern mit der Hoehe in dieselbe Richtung (+x, -y) um 0,3-0,4 m auf 30 m. Ursache: Lot aus der Kameraebene - die Strasse am Schwabentor steigt an.
Rechnung: Rt = kleinste Drehung, die up_welt auf (0,0,1) bringt; X' = Rt (X - c) + c mit Drehpunkt c (dort bleibt die Lage unveraendert - Hoehe waehlen,
in der Wolke und LoD2 schon passen). 'transformation' (X_m = R^T (X_sfm - t) / s) und alle 'kameras' (standort, R, t) werden umgerechnet; s bleibt.
Danach: kameras_aus_buendel.py --ueberschreiben, Wolke neu in den Rahmen (wolke_saeubern/wolke_neu_fusionieren), Tore und Fotomasse wiederholen.
"""
import sys, json, argparse, numpy as np, cv2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ausrichtung"); ap.add_argument("lot"); ap.add_argument("--drehpunkt", nargs=3, type=float, required=True); ap.add_argument("--aus", default=""); a = ap.parse_args()
    A = json.load(open(a.ausrichtung)); up = np.array(json.load(open(a.lot))["up_welt"], float); up /= np.linalg.norm(up); z = np.array([0, 0, 1.0]); c = np.array(a.drehpunkt)
    ax = np.cross(up, z); w = float(np.arcsin(np.linalg.norm(ax))); Rt = cv2.Rodrigues(ax / (np.linalg.norm(ax) + 1e-15) * w)[0]; d = c - Rt @ c       # X' = Rt X + d
    T = A["transformation"]; s = T["s"]; R = cv2.Rodrigues(np.array(T["rvec"], float))[0]; t = np.array(T["t"], float)
    R2 = R @ Rt.T; t2 = t - s * (R2 @ d); A["transformation"] = dict(T, rvec=cv2.Rodrigues(R2)[0].ravel().tolist(), t=t2.tolist())
    for k in A.get("kameras", {}).values():
        Rc = np.array(k["R"], float); tc = np.array(k["t"], float); Rc2 = Rc @ Rt.T; k["R"] = Rc2.tolist(); k["t"] = (tc - Rc2 @ d).tolist()
        k["standort"] = [round(float(v), 3) for v in (Rt @ np.array(k["standort"], float) + d)]
    if "kamerahoehen" in A and isinstance(A["kamerahoehen"], dict): A["kamerahoehen"]["hinweis_lot"] = "vor der Lotkorrektur berechnet"
    A["lotkorrektur"] = dict(werkzeug="ausrichtung_lot_korrigieren.py", up_welt_vorher=up.tolist(), winkel_grad=round(float(np.degrees(w)), 3), drehpunkt=c.tolist(), quelle=a.lot)
    A["verfahren"] = A.get("verfahren", "") + f" | Lotkorrektur {np.degrees(w):.2f} Grad aus Foto-Vertikalen (lot_aus_fotos.py), Drehpunkt {c.tolist()}"
    json.dump(A, open(a.aus or a.ausrichtung, "w"), indent=1, ensure_ascii=False); print(f"Lotkorrektur {np.degrees(w):.3f} Grad um {c.tolist()}; {len(A.get('kameras', {}))} Kameras umgerechnet -> {a.aus or a.ausrichtung}")


if __name__ == "__main__":
    main()
