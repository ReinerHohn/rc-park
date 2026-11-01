#!/usr/bin/env python3
"""sfm_verzerrung_test.py - Ist ein SfM-Netz METRISCH oder projektiv verbogen? (Lehre Register AI, Suednetz Martinstor)

Idee: Ein gesundes Netz laesst sich mit EINER Aehnlichkeitstransformation (7 Parameter) auf bekannte Punkte legen - oben UND unten.
Ein verbogenes Netz passt entweder oben oder unten. Deshalb drei Umeyama-Fits der triangulierten Picks auf Referenzpunkte:
alle, nur obere (Dach), nur untere (Boden); dann Fehler der jeweils NICHT benutzten Punkte und Kamerahoehen ansehen.
Referenzen: Bodenecken aus anker3d.json (amtlich); Dachpunkte wahlweise aus der Ausrichtung der Gegenseite (gespiegelt, ANNAHME
Symmetrie des Dachs) oder aus einer JSON {name: [x,y,z]}.
  /media/oem/scan/venv-colmap/bin/python -I tools/sfm_verzerrung_test.py modelle/<objekt>/objekt.json --sparse <sparse/0> --fotos 000 030 041
        [--spiegel messprotokoll/SFM-AUSRICHTUNG-nord.json] [--referenz punkte.json] [--grenze 2.0]
Exit 0 = metrisch (Fehler der ausgelassenen Punkte < Grenze), 1 = verbogen, 2 = zu wenig Punkte.
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfm_ausrichten as SA

def umeyama(a, b):
    ma, mb = a.mean(0), b.mean(0); A_ = a - ma; B_ = b - mb; U, S, Vt = np.linalg.svd(B_.T @ A_); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt; s = np.trace(np.diag(S) @ D) / np.sum(A_ ** 2); return s, R, mb - s * R @ ma

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--sparse", required=True); ap.add_argument("--fotos", nargs="*")
    ap.add_argument("--spiegel", help="SFM-AUSRICHTUNG-<gegenseite>.json: Dachpunkte an x gespiegelt (N<->S) als Referenz; Namen NE/NW -> SE/SW")
    ap.add_argument("--referenz", help="JSON {name: [x,y,z]} im Modellsystem"); ap.add_argument("--grenze", type=float, default=2.0)
    ap.add_argument("--nicht-spiegeln", action="store_true", help="--spiegel-Datei ist die EIGENE Seite (Selbsttest): Punkte unveraendert uebernehmen")
    a = ap.parse_args(); obj, root, od, A, rec, kams, Ks = SA.lade(a.objekt, a.sparse)
    if a.fotos: Ks = {nr: K for nr, K in Ks.items() if nr in a.fotos}
    ref = {n: np.array(A[n]["xyz"]) for n in A if n.startswith("ecke_boden")}
    if a.spiegel:
        T = json.load(open(os.path.join(od, a.spiegel) if not os.path.isabs(a.spiegel) else a.spiegel))["trianguliert"]
        for n, t in T.items():
            if a.nicht_spiegeln: ref[n] = np.array(t["xyz"]); continue
            m = n.replace("NE", "SE").replace("NW", "SW") if "N" in n.split("_")[-1] else n.replace("SE", "NE").replace("SW", "NW")
            ref[m] = np.array(t["xyz"]) * np.array([-1, 1, 1])
    if a.referenz: ref.update({n: np.array(v) for n, v in json.load(open(a.referenz)).items()})
    src, dst, names = [], [], []
    for n, X in ref.items():
        beob = [(kams[nr], kams[nr].bild(Ks[nr]["punkte"][n])) for nr in Ks if n in Ks[nr].get("punkte", {})]
        if len(beob) < 2: continue
        Xs, sx, px = SA.triangulieren(kams, beob); src.append(Xs); dst.append(X); names.append(n)
    src, dst = np.array(src), np.array(dst)
    if len(names) < 4: print("zu wenig gemeinsame Punkte:", names); sys.exit(2)
    unten = np.array([n.startswith("ecke_boden") for n in names]); print("Punkte:", names)
    verdict_ok = True
    for sel, txt in [(np.ones(len(names), bool), "alle"), (~unten, "nur OBEN (Dach)"), (unten, "nur UNTEN (Boden)")]:
        if sel.sum() < 3: print(f"\n{txt}: weniger als 3 Punkte, uebersprungen"); continue
        s, R, t = umeyama(src[sel], dst[sel]); fit = s * (src @ R.T) + t; err = np.linalg.norm(fit - dst, axis=1)
        C = np.array([s * R @ kams[nr].zentrum() + t for nr in sorted(kams)])
        print(f"\nFit {txt}: Massstab {1 / s:.4f} SfM/m; Fehler benutzt {err[sel].mean():.2f} m, ausgelassen {err[~sel].mean() if (~sel).any() else float('nan'):.2f} m; Kamerahoehen Median {np.median(C[:, 2]):.1f} m")
        for n, e, u in zip(names, err, sel): print(f"   {n:14s} {e:5.2f} m {'(benutzt)' if u else '(ausgelassen)'}")
        if (~sel).any() and err[~sel].mean() > a.grenze: verdict_ok = False
    print("\nURTEIL:", "metrisch (Aehnlichkeit passt oben und unten)" if verdict_ok else f"VERBOGEN - ausgelassene Punkte > {a.grenze} m daneben; nachtraegliche Ausrichtung sinnlos, Netz reparieren (Brennweiten/Verzeichnung/zweite Seite)")
    sys.exit(0 if verdict_ok else 1)

if __name__ == "__main__":
    main()
