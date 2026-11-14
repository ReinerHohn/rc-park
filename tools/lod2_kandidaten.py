#!/usr/bin/env python3
"""lod2_kandidaten.py --gml DATEI --e E --n N [--radius 40] [--soll-hoehe H --toleranz 0.1] - Gebaeude im LOD2 nahe einer Koordinate.

Lehre Schwabentor 13.11.2026: Die Gebaeude-Suche wurde von Hand gemacht, eine Ausgabe wurde abgeschnitten, und das
Hoehen-Widerspruch (26 m Katalog gegen 51 m Wikipedia) blieb ungeklaert. Dieses Werkzeug listet ALLE Kandidaten
im Umkreis, sortiert nach Abstand, mit Traufe, First und Fussflaeche. Mit --soll-hoehe wird geprueft, ob ein
Kandidat im Toleranzband liegt; sonst WIDERSPRUCH (nichts still uebernehmen).
Lehre Schwabentor 14.11.2026: Gewaehlt wurde Tvdv (First 25,8 m, Katalog 26 m) - das Nachbarhaus. Das GML traegt beim echten Turm PLcp
das Attribut name='Schwabentor'. Darum: Spalte Name, und mit --name wird ein Namenstreffer bevorzugt; Name passt nicht zum Hoehen-Kandidaten -> WIDERSPRUCH.
Dauer: GML-Einlesen ~2 Minuten -> ueber tools/job_start.sh starten.
"""
import sys, os, argparse, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as L

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gml", required=True); ap.add_argument("--e", type=float, required=True); ap.add_argument("--n", type=float, required=True)
    ap.add_argument("--radius", type=float, default=40.0); ap.add_argument("--soll-hoehe", type=float, default=None); ap.add_argument("--toleranz", type=float, default=0.1)
    ap.add_argument("--name", default=None, help="Objektname (z. B. Schwabentor): GML-Namensattribut hat Vorrang vor der Hoehe")
    a = ap.parse_args()
    treffer = []
    for m, _ in L.extract(a.gml, center=(a.e, a.n), radius=a.radius):
        ctr = m["center_utm"]; d = math.hypot(ctr[0] - a.e, ctr[1] - a.n)
        treffer.append((d, m))
    treffer.sort(key=lambda t: t[0])
    print(f"{len(treffer)} Gebaeude im Umkreis {a.radius} m um E{a.e:.0f} N{a.n:.0f}")
    print(f"{'Abstand':>8} {'First':>7} {'Traufe':>7} {'Tiefe':>6}  id  name")
    for d, m in treffer:
        print(f"{d:8.1f} {m.get('ridge_m', float('nan')):7.2f} {m.get('eave_m', float('nan')):7.2f} {m.get('depth_m', float('nan')):6.2f}  {m['id']}  {m.get('name') or ''}")
    namentreffer = [(d, m) for d, m in treffer if a.name and (m.get("name") or "").lower().find(a.name.lower()) >= 0]
    if a.name:
        if namentreffer: print(f"NAME: {namentreffer[0][1]['id']} heisst '{namentreffer[0][1]['name']}' ({namentreffer[0][0]:.1f} m) - dieses Gebaeude nehmen")
        else: print(f"HINWEIS: kein Gebaeude mit Namen '{a.name}' im Umkreis - Zuordnung am Foto belegen (markante Form, z. B. Rundanbau)")
    if a.soll_hoehe is not None:
        lo, hi = a.soll_hoehe * (1 - a.toleranz), a.soll_hoehe * (1 + a.toleranz)
        ok = [(d, m) for d, m in treffer if lo <= m.get("ridge_m", -1) <= hi]
        if ok and namentreffer and ok[0][1]["id"] != namentreffer[0][1]["id"]:
            print(f"WIDERSPRUCH: Hoehen-Kandidat {ok[0][1]['id']} ist nicht das Gebaeude mit Namen '{a.name}' ({namentreffer[0][1]['id']}) - Namen folgen, Hoehenquelle pruefen")
            return 1
        if ok:
            print(f"OK: {len(ok)} Kandidat(en) im Band {lo:.1f}..{hi:.1f} m, naechster: {ok[0][1]['id']} ({ok[0][0]:.1f} m)")
        else:
            print(f"WIDERSPRUCH: kein Gebaeude mit First {lo:.1f}..{hi:.1f} m im Umkreis - Quelle oder Koordinate pruefen, NICHT uebernehmen")
            return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
