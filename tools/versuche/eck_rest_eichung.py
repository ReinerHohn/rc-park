#!/usr/bin/env python3
"""eck_rest_eichung.py <selbsttest-k-ordner ...> --aus eichung.json  (22.11.2026)

EICHUNG DER KOPPLUNGS-GRENZEN (seiten_eck_koppeln, tiefenbezogenes Fehlermass) AN DATEN MIT BEKANNTER WAHRHEIT (eck_selbsttest.py-Ordner: teilA, teilB, stufe/eck.json).
(a) RICHTIG: jedes Zwischenmodell gegen Teil A und Teil B (Teile = Ausschnitte des wahren Modells) -> Rest, Anteil, Haelften, TREND (Rest im fernsten / naechsten
    Abstandsquartil zu den gemeinsamen Kameras).
(b) FALSCH (soll sicher abgelehnt werden), am selben Paar erzeugt:
    - Massstabsverlauf 2 % / 5 % ueber die Teil-Laenge (Punkt-Massstab 1 + a*u, u = Lage entlang der Hauptachse, -0,5..0,5),
    - Biegung 1 Grad / 3 Grad ueber die Teil-Laenge (Drehung um die Hochachse mit Winkel b*u, um die Teil-Mitte),
    - Verwechslung (Spiegelbild des Teils an seiner Hauptebene: symmetrischer Turm, falsche Seite),
    - Zufallspunkte.
Ausgabe: je Fall die Kennzahlen + Urteil der aktuellen Grenzen."""
import os, sys, json, argparse, numpy as np, pycolmap
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
import seiten_eck_koppeln as EK
from sim3_robust import anwenden


def kennzahlen(X, Y, td, ns_c, ausd, ausd_z):
    M, pr, ok, g = EK.kopplung_pruefen(X, Y, ausd, ausd_z, tiefe=td)
    if M is None: return dict(ok=False, grund=g, **pr)
    s = np.cbrt(np.linalg.det(M[:3, :3])); r = np.linalg.norm(anwenden(M, X) - Y, axis=1) / (s * td); d = np.linalg.norm(Y - ns_c, axis=1)
    q = np.percentile(d, [25, 75]); nah, fern = np.median(r[d <= q[0]]), np.median(r[d >= q[1]])
    return dict(ok=ok, grund=g, trend=round(float(fern / max(nah, 1e-12)), 3), **pr)


def verformen(Y, art, wert, P):
    """Verformung ueber die Teil-Laenge (P = alle Punkte des Teils fuer Achse/Mitte)."""
    c = np.median(P, 0); _, _, Vt = np.linalg.svd(P - c, full_matrices=False); ach = Vt[0]; L = np.percentile((P - c) @ ach, 95) - np.percentile((P - c) @ ach, 5)
    u = ((Y - c) @ ach) / L; Z = Y.copy()
    if art == "massstab": Z = c + (Y - c) * (1 + wert * u)[:, None]
    elif art == "biegung":
        hoch = Vt[2]; a = np.radians(wert) * u
        v = Y - c; k = np.cross(hoch, v); Z = c + v * np.cos(a)[:, None] + k * np.sin(a)[:, None] + np.outer(v @ hoch, hoch) * (1 - np.cos(a))[:, None]
    elif art == "spiegel": n = Vt[1]; Z = Y - 2 * np.outer((Y - c) @ n, n)
    elif art == "zufall": Z = c + np.random.default_rng(1).normal(0, L / 4, Y.shape)
    return Z


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ordner", nargs="+"); ap.add_argument("--aus", required=True); a = ap.parse_args(); erg = []
    for o in a.ordner:
        ej = json.load(open(os.path.join(o, "stufe", "eck.json"))); teile = {"0": pycolmap.Reconstruction(os.path.join(o, "teilA")), "1": pycolmap.Reconstruction(os.path.join(o, "teilB"))}
        for z in ej.get("zwischenmodelle", []):
            if not z.get("modell"): continue
            E = pycolmap.Reconstruction(z["modell"]); ausd = EK.ausdehnung([p.xyz for p in E.points3D.values()])
            for t, Z in teile.items():
                X, Y, ns, td = EK.punkte(E, Z, mit_tiefe=True)
                if len(ns) < EK.MIN_BILDER_TEIL or len(X) < EK.MIN_PUNKTE: continue
                P = np.array([p.xyz for p in Z.points3D.values()]); az = EK.ausdehnung(P)
                cz = np.array([im.projection_center() for im in Z.images.values() if im.name in set(ns)]).mean(0)
                fall = dict(ordner=o, modell=z["modell"], teil=t, nachmatchen=bool((z.get("nachmatchen") or {}).get("rc") == 0))
                erg.append(dict(fall, art="richtig", wert=0, **kennzahlen(X, Y, td, cz, ausd, az)))
                for art, werte in (("massstab", (0.02, 0.05)), ("biegung", (1.0, 3.0)), ("spiegel", (0,)), ("zufall", (0,))):
                    for w in werte: erg.append(dict(fall, art=art, wert=w, **kennzahlen(X, verformen(Y, art, w, P), td, cz, ausd, az)))
                print(o[-12:], t, [(e["art"], e["wert"], e.get("rest_rel"), e.get("anteil"), e.get("massstab_haelften_rel"), e.get("trend"), e["ok"]) for e in erg[-7:]], flush=True)
    json.dump(erg, open(a.aus, "w"), indent=1)


if __name__ == "__main__": main()
