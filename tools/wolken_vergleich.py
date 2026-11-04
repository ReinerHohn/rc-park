#!/usr/bin/env python3
"""wolken_vergleich.py - mehrere Punktwolken derselben Seite MIT GLEICHEM SCHAETZER nebeneinander (Bewertung der Bodenwolke, Nutzerwunsch Sweetspot).

Je Quelle und 5-m-Band der Nordwand (Mittelstreifen |v| < --streifen, Tiefe 2..8 m): Punktzahl, Dichte je m2 Wandflaeche, Tiefen-Streuung (MAD der Flaechentiefe um den Modus, 5-cm-Histogramm),
Anteil der Punkte im Modus-Band +-0,15 m (Flaechenschaerfe), sowie Neigung (lotpruefung.neigung) und Doppelschicht-Zaehler (doppelschicht.schicht) im stufenfreien Abschnitt --lot-z.
Zweck: nach Jobende entscheiden, ob eine Quelle (z. B. Bodenwolke) gegenueber den anderen etwas Messbares bringt - Dichte UND Schaerfe UND Lot, nicht nur Punktzahl.
ANNAHMEN: Flaechenschaerfe und Dichte sind Stellvertreter fuer Nutzen; ob das Modell besser wird, entscheidet erst eine Pruefzeile (nullstart/treppe mit und ohne Quelle).
Seiten ohne Daten werden als solche gemeldet (Nord-/Sued-Luecken sichtbar). Keine Eingriffe, nur lesen.
  python3 -I tools/wolken_vergleich.py modelle/<objekt>/objekt.json --wolke NAME=pfad.npy [--wolke ...] [--seite Nord(-x)] [--ausgabe name]
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lotpruefung as LP, doppelschicht as DS

def baender(P, u, a):
    u = np.array(u, float); v = np.array([-u[1], u[0]]); d = P[:, :2] @ u; l = P[:, :2] @ v; out = []
    for z0 in np.arange(a.zlo, a.zhi, a.band):
        k = (P[:, 2] >= z0) & (P[:, 2] < z0 + a.band) & (np.abs(l) < a.streifen) & (d > 2.0) & (d < 8.0); n = int(k.sum()); r = dict(z=[float(z0), float(z0 + a.band)], n=n, dichte_je_m2=round(n / (2 * a.streifen * a.band), 1))
        if n >= 100:
            dd = d[k]; h, e = np.histogram(dd, bins=np.arange(2.0, 8.05, 0.05)); hs = np.convolve(h, np.ones(3) / 3, "same"); m = int(np.argmax(hs)); d0 = 0.5 * (e[m] + e[m + 1]); b = np.abs(dd - d0) <= 0.15
            r.update(modus_tiefe=round(float(np.median(dd[b])), 3), scharf_anteil=round(float(b.mean()), 3), mad_m=round(float(np.median(np.abs(dd - np.median(dd[b])))), 3))
        out.append(r)
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", action="append", required=True, help="NAME=pfad.npy"); ap.add_argument("--seite", default="Nord(-x)", choices=list(LP.SEITEN))
    ap.add_argument("--zlo", type=float, default=5.0); ap.add_argument("--zhi", type=float, default=45.0); ap.add_argument("--band", type=float, default=5.0); ap.add_argument("--streifen", type=float, default=1.8)
    ap.add_argument("--lot-z", nargs=2, type=float, default=[7.0, 23.0], help="stufenfreier Abschnitt fuer Lot/Doppelschicht (aus lotpruefung, Generator-Abschnitt)"); ap.add_argument("--ausgabe", default="vergleich")
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); u = LP.SEITEN[a.seite]; erg = {}
    la = argparse.Namespace(zlo=a.lot_z[0], zhi=a.lot_z[1], dz=0.5, schritt=1.0, streifen=a.streifen, dmin=2.0, dmax=8.0, minpts=300, anteil=0.15)
    da = argparse.Namespace(zlo=a.lot_z[0], zhi=a.lot_z[1], dz=0.5, schritt=1.0, tmax=7.0, quer=1.0, minpts=300, maxpts=60000, abstand_m=0.4, gewicht=0.05, bic_min=20.0)
    for s in a.wolke:
        nm, p = s.split("=", 1); P = np.load(p).astype(float)
        if P.ndim != 2 or P.shape[1] != 3: print(f"{nm}: keine Nx3-Wolke, uebersprungen"); continue
        z, d, l, n = LP.schichten(P, u, la); lot = LP.neigung(z, d) if len(z) >= 5 else None
        ds = [x for x in DS.analysiere(P, u, da) if x.get("status") == "ok"]
        erg[nm] = dict(punkte=len(P), baender=baender(P, u, a), lot_mm_je_m=(lot or {}).get("mm_je_m"), lot_ci95=(lot or {}).get("ci95_mm_je_m"), lot_schichten=int(len(z)), doppelschichten=f"{sum(1 for x in ds if x['doppelt'])}/{len(ds)}")
    bz = [f"{r['z'][0]:.0f}-{r['z'][1]:.0f}" for r in next(iter(erg.values()))["baender"]] if erg else []
    print(f"Seite {a.seite}, Mittelstreifen +-{a.streifen} m\n\nPunkte je m2 Wandflaeche (Band z in m):\n{'Quelle':22}" + "".join(f"{b:>9}" for b in bz))
    for nm, r in erg.items(): print(f"{nm:22}" + "".join(f"{x['dichte_je_m2']:9.1f}" for x in r["baender"]))
    print(f"\nFlaechenschaerfe (Anteil im Modus-Band +-0,15 m; hoeher = schaerfere Flaeche) und MAD in m:\n{'Quelle':22}" + "".join(f"{b:>13}" for b in bz))
    for nm, r in erg.items(): print(f"{nm:22}" + "".join((f"{x['scharf_anteil']:7.2f}/{x['mad_m']:.2f}" if 'scharf_anteil' in x else f"{'-':>13}") for x in r["baender"]))
    print(f"\nLot z {a.lot_z[0]:.0f}-{a.lot_z[1]:.0f} m (mm/m, 0 = senkrecht; Generator-Verjuengung -13) und Doppelschichten:")
    for nm, r in erg.items(): print(f"  {nm:22} Lot {r['lot_mm_je_m']} (CI {r['lot_ci95']}, {r['lot_schichten']} Schichten)  Doppelschichten {r['doppelschichten']}")
    pf = os.path.join(od, "audit", f"wolken_vergleich_{a.ausgabe}.json"); os.makedirs(os.path.dirname(pf), exist_ok=True)
    json.dump(dict(seite=a.seite, annahme="Dichte/Schaerfe/Lot sind Stellvertreter, kein Modellgewinn; Entscheidung erst per Pruefzeile mit/ohne Quelle", quellen=erg), open(pf, "w"), indent=1, ensure_ascii=False); print("\nBericht:", pf)

if __name__ == "__main__":
    main()
