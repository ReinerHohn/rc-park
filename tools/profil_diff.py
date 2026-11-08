#!/usr/bin/env python3
"""profil_diff.py - Lage-/Breitenvergleich Modell gegen Punktwolke ENTLANG einer Fassade (Erker, Pfeiler, Oeffnungen), je Hoehenband.
Automatische Fassung der Handmessung 6.11. (Nutzer: 'rechter Erker zu weit links, 5. Oeffnung'). Nichts objektbezogen: Fassade (n, d, o) aus einer fassaden.json,
Baender/Schwellen als Argumente (ANNAHME-Standard unten). Zahlen aus der Wolke sind hier NUR Lage/Breite; Anzahlen entscheidet das Foto (Regel 9) -> Bericht markiert 'Anzahl abweichend' nur als Hinweis.

  venv-seg/bin/python -I tools/profil_diff.py --stl M.stl --massstab 87 --wolke W.npy --fassaden F.json --id f02 [--baender 5,8,11 | 1.5,3] [--aus bericht.json] [--tol 0.3]
Rahmen: STL mm -> Meter (x massstab/1000), Wolke Meter, beide im Modellrahmen (zentrierung 'achse').
Mass je Band: u-Bins 0,25 m; 'Vorsprung' = 90. Perzentil der Aussenlage s > --schwelle (0,4 m); 'Oeffnung' (Baender unter 3 m): Anteil Punkte in der Pfeilerflucht < 5 %.
Laeufe aus Vorsprung bzw. Oeffnung (Mindestbreite 0,5 m / 1,0 m); je Modelllauf der naechste Wolkenlauf: Versatz Anfang/Ende. Modelllauf ohne Wolkenpartner = 'ohne Gegenstueck' (Hinweis)."""
import argparse, json, numpy as np, trimesh


def laeufe(maske, bins, minb):
    r = []; st = None
    for a, o in zip(bins, maske):
        if o and st is None: st = a
        if not o and st is not None:
            if a - st >= minb: r.append((round(float(st), 2), round(float(a), 2)))
            st = None
    if st is not None and bins[-1] + 0.25 - st >= minb: r.append((round(float(st), 2), round(float(bins[-1] + 0.25), 2)))
    return r


def profil(Q, F, z0, z1, art, schwelle=0.4, bw=0.25, urange=(-14, 14)):
    n = np.array(F["n"][:2]); d = np.array(F["d"][:2]); o = np.array(F["o"][:2]); q = Q[:, :2] - o; u, s, z = q @ d, q @ n, Q[:, 2]
    bins = np.arange(urange[0], urange[1], bw)
    if art == "vorsprung":
        k = (z >= z0) & (z < z1) & (s > -1) & (s < 3); u, s = u[k], s[k]
        v = np.array([np.percentile(s[(u >= a) & (u < a + bw)], 90) if ((u >= a) & (u < a + bw)).sum() > 8 else np.nan for a in bins])
        return bins, np.nan_to_num(v, nan=-1) > schwelle, 0.5
    k = (z >= z0) & (z < z1) & (s > -6) & (s < 0.25); u, s = u[k], s[k]
    fr = np.array([(s[(u >= a) & (u < a + bw)] > -0.5).mean() if ((u >= a) & (u < a + bw)).sum() > 8 else np.nan for a in bins])
    return bins, np.nan_to_num(fr, nan=0.0) < 0.05, 1.0       # Oeffnung = kaum Punkte in der Pfeilerflucht (Wolke-Luecken zaehlen hier NICHT als Oeffnung unten, siehe 'luecke')


def vergleich(Pm, Xw, F, baender, art, tol):
    out = []
    for z0, z1 in zip(baender[:-1], baender[1:]):
        b, mm, mb = profil(Pm, F, z0, z1, art); _, mw, _ = profil(Xw, F, z0, z1, art)
        lm, lw = laeufe(mm, b, mb), laeufe(mw, b, mb); zeilen = []
        for a0, a1 in lm:
            best = min(lw, key=lambda r: abs(0.5 * (r[0] + r[1]) - 0.5 * (a0 + a1)), default=None)
            if best is None or abs(0.5 * (best[0] + best[1]) - 0.5 * (a0 + a1)) > 3.0: zeilen.append(dict(modell=[a0, a1], wolke=None, urteil="ohne Gegenstueck in der Wolke (Hinweis)")); continue
            da, de = round(a0 - best[0], 2), round(a1 - best[1], 2)
            zeilen.append(dict(modell=[a0, a1], wolke=list(best), d_anfang=da, d_ende=de, urteil="ok" if max(abs(da), abs(de)) <= tol else "ABWEICHUNG"))
        for r in lw:
            if not any(abs(0.5 * (r[0] + r[1]) - 0.5 * (a + b_)) <= 3.0 for a, b_ in lm): zeilen.append(dict(modell=None, wolke=list(r), urteil="Wolke hat Lauf ohne Modell (fehlt im Modell)"))
        out.append(dict(z0=z0, z1=z1, art=art, laeufe=zeilen))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--stl", required=True); ap.add_argument("--massstab", type=float, default=87); ap.add_argument("--wolke", required=True)
    ap.add_argument("--fassaden", required=True); ap.add_argument("--id", required=True); ap.add_argument("--baender", default="5,8,11"); ap.add_argument("--oeffnung", default="1.5,3.0")
    ap.add_argument("--tol", type=float, default=0.3); ap.add_argument("--aus"); ap.add_argument("--n", type=int, default=800000); a = ap.parse_args()
    F = [f for f in json.load(open(a.fassaden))["fassaden"] if f["id"] == a.id][0]
    m = trimesh.load(a.stl); m.apply_scale(a.massstab / 1000.0); Pm = m.sample(a.n); Xw = np.load(a.wolke)
    erg = vergleich(Pm, Xw, F, [float(x) for x in a.baender.split(",")], "vorsprung", a.tol) + vergleich(Pm, Xw, F, [float(x) for x in a.oeffnung.split(",")], "oeffnung", a.tol)
    bad = 0
    for e in erg:
        print(f"z {e['z0']}-{e['z1']} m  {e['art']}")
        for z in e["laeufe"]:
            print("   ", z["urteil"], "| Modell", z.get("modell"), "Wolke", z.get("wolke"), "dAnfang", z.get("d_anfang"), "dEnde", z.get("d_ende")); bad += z["urteil"] == "ABWEICHUNG"
    if a.aus: json.dump(dict(fassade=a.id, tol=a.tol, ergebnis=erg, abweichungen=bad), open(a.aus, "w"), indent=1, ensure_ascii=False)
    print("ABWEICHUNGEN:", bad); raise SystemExit(1 if bad else 0)
