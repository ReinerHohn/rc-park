#!/usr/bin/env python3
"""kamera_plausibel.py <objekt.json> <SFM-AUSRICHTUNG.json> [--unter 1.5] [--gruppe 4] - Kameras unter dem Gelaende finden (falsch verortete Bildgruppen).

Lehre Schwabentor 15.11.2026: eine Geisterwand in der dichten Wolke (27 852 Punkte auf der Strasse) kam zu 92 % aus 6 Bildern EINES Videoclips,
deren Kameras 0,3-4,5 m UNTER dem Gelaende standen (70 m entfernt). Das Grundriss-Tor sah nur den Haufen, nicht die Ursache.
Pruefung: Kamerahoehe im Modellrahmen (z = 0 am Gelaende des Objekts, ANNAHME: Umgebung etwa eben; Hang -> --unter groesser waehlen) < -unter.
Je Quelle (Namensteil vor '__vf_' bzw. vor '__', sonst 'eigen') gezaehlt; >= --gruppe Kameras einer Quelle unter Gelaende = rc 3 + Liste
audit/kamera_plausibel.json ('ausschliessen': Bildnamen fuer die dichte Wolke/Fusion). Einzelne Ausreisser = nur Hinweis.
"""
import sys, os, json, collections


def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    opt = lambda n, d: float(a[a.index(n) + 1]) if n in a else d
    unter, gruppe = opt("--unter", 1.5), int(opt("--gruppe", 4)); od = os.path.dirname(os.path.abspath(a[0])); K = json.load(open(a[1]))["kameras"]
    quelle = lambda n: n.split("__vf_")[0] if "__vf_" in n else (n.split("__")[0] if "__" in n else "eigen")
    tief = {n: k["standort"][2] for n, k in K.items() if k["standort"][2] < -unter}; je = collections.Counter(quelle(n) for n in tief); alle = collections.Counter(quelle(n) for n in K)
    schlecht = {q: c for q, c in je.items() if c >= gruppe}; aus = sorted(tief)   # JEDE Kamera unter Gelaende ist fuer die dichte Wolke unbrauchbar (v2: Commons-Einzelbilder bis km tief = Ausreisser des globalen Mappers)
    print(f"{len(tief)} von {len(K)} Kameras tiefer als {unter} m unter dem Gelaende")
    for q, c in je.most_common(8): print(f"  {q[:50]:50s} {c:3d} von {alle[q]:3d}  (tiefste {min(tief[n] for n in tief if quelle(n) == q):.1f} m){'  <-- GRUPPE' if q in schlecht else ''}")
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(dict(werkzeug="kamera_plausibel.py", ausrichtung=a[1], unter_m=unter, n=len(K), tief=tief, gruppen=schlecht, ausschliessen=aus), open(os.path.join(od, "audit", "kamera_plausibel.json"), "w"), indent=1)
    if schlecht: print(f"WARNUNG: {len(schlecht)} Quelle(n) mit >= {gruppe} Kameras unter Gelaende - Bildgruppe falsch verortet? {len(aus)} Bilder aus der dichten Wolke nehmen (audit/kamera_plausibel.json)"); return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
