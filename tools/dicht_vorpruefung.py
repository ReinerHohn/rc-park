#!/usr/bin/env python3
"""dicht_vorpruefung.py - billige Schranke VOR einer teuren dichten Rechnung (Sweetspot-Ziel: viele Modelle in kurzer Zeit; Lehre aus der Bodenwolke 3.11., >1 h GPU).

Liest audit/abdeckung.json (von abdeckung_quellen.py: Kameras je Quelle und Seite, Standorthoehe) und entscheidet je QUELLE und SEITE, ob eine dichte Rechnung dieser Quelle
begruendet ist.  Regeln (alle Schwellen sind ANNAHMEN, Argumente; das Werkzeug ist selbst ein Versuch und wird gegen das Ergebnis der Bodenwolke bewertet):
  1. Quelle hat auf der Seite >= --min-kameras (10) Kameras, sonst 'zu wenige Kameras' (nichts zu rechnen).
  2. 'schliesst Luecke': alle ANDEREN Quellen zusammen haben auf der Seite < --ziel-kameras (30) Kameras.
  3. 'neue Hoehenlage': Median der Standorthoehe der Quelle unterscheidet sich um >= --hoehen-diff (15 m) von jeder anderen Quelle mit bekannter Hoehe auf der Seite
     (Stellvertreter fuer 'sieht andere Wandbereiche'; Fotos haben in abdeckung.json keine Hoehe -> zaehlen nur fuer Regel 2).
  Sonst 'nicht begruendet: Seite ist von anderen Quellen schon belegt'.  Quelle lohnt, wenn mindestens eine Seite 2 oder 3 erfuellt.
GRENZEN: Kamerazahl ist KEIN Mass fuer Punktdichte/Schaerfe (Drohne unten 73 Pkt/m2 trotz 161 Nordkameras); Hoehenregel ist grob; Ausrichtung/Seitenzuordnung der Videos haengt an der Nordausrichtung
(Symmetrie, Plan M8); Quellen ohne Seitenangabe werden ignoriert.  Die Schranke ersetzt nicht die Messung nach dem Lauf (wolken_vergleich.py).
  python3 -I tools/dicht_vorpruefung.py modelle/<objekt>/objekt.json [--quelle boden] [--ausgabe name]     Exit 0 = mindestens eine Quelle lohnt, 5 = keine Quelle begruendet
Ausgabe: audit/dicht_vorpruefung_<name>.json (Entscheidung + Begruendung je Quelle und Seite).
"""
import sys, os, json, argparse

def kameras(q):
    """-> {seite: (anzahl, hoehe_median|None)} aus einem Quellblock von abdeckung.json."""
    out = {}
    for s, v in (q.get("je_seite") or {}).items():
        if s not in ("Nord", "Sued", "Ost", "West"): continue
        out[s] = (int(v["bilder"]), v.get("hoehe_median_m")) if isinstance(v, dict) else (int(v), None)       # Fotos: nur Zahl; Video: dict mit bilder/Hoehe
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--quelle", help="nur diese Quelle bewerten"); ap.add_argument("--min-kameras", type=int, default=10); ap.add_argument("--ziel-kameras", type=int, default=30)
    ap.add_argument("--hoehen-diff", type=float, default=15.0); ap.add_argument("--ausgabe", default="boden"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); A = json.load(open(os.path.join(od, "audit", "abdeckung.json"))); Q = {k: kameras(v) for k, v in A["quellen"].items() if isinstance(v, dict)}
    Q = {k: v for k, v in Q.items() if v}; erg = {}; lohnt_irgendwo = False
    print(f"Quellen mit Kameras: {list(Q)}; Schwellen: min {a.min_kameras}, Ziel {a.ziel_kameras}, Hoehendifferenz {a.hoehen_diff} m (ANNAHMEN)\n")
    for q, S in Q.items():
        if a.quelle and q != a.quelle: continue
        erg[q] = dict(seiten={}, lohnt=False)
        for s in ("Nord", "Sued", "Ost", "West"):
            n, h = S.get(s, (0, None)); andere = {o: Q[o].get(s, (0, None)) for o in Q if o != q}; n_and = sum(v[0] for v in andere.values()); begruendung = None
            if n < a.min_kameras: urteil = "zu wenige Kameras"
            elif n_and < a.ziel_kameras: urteil, begruendung = "lohnt", f"schliesst Luecke: andere Quellen nur {n_and} Kameras (< {a.ziel_kameras})"
            else:
                hd = [abs(h - v[1]) for v in andere.values() if v[0] >= a.min_kameras and v[1] is not None and h is not None]
                if hd and min(hd) >= a.hoehen_diff: urteil, begruendung = "lohnt", f"neue Hoehenlage: Standorthoehe {h} m, naechste andere Quelle {min(hd):.0f} m entfernt (>= {a.hoehen_diff:.0f})"
                else: urteil = "nicht begruendet: Seite schon von anderen Quellen belegt" + (" (Hoehenlage nicht neu/unbekannt)" if h is not None or hd else "")
            erg[q]["seiten"][s] = dict(kameras=n, andere_kameras=n_and, hoehe_median_m=h, urteil=urteil, begruendung=begruendung)
            if urteil == "lohnt": erg[q]["lohnt"] = True; lohnt_irgendwo = True
        print(f"Quelle {q}: {'LOHNT' if erg[q]['lohnt'] else 'nicht begruendet'}")
        for s, r in erg[q]["seiten"].items(): print(f"   {s:5} {r['kameras']:4d} Kameras (andere {r['andere_kameras']:4d})  {r['urteil']}" + (f" - {r['begruendung']}" if r["begruendung"] else ""))
    pf = os.path.join(od, "audit", f"dicht_vorpruefung_{a.ausgabe}.json"); json.dump(dict(annahmen=dict(min_kameras=a.min_kameras, ziel_kameras=a.ziel_kameras, hoehen_diff_m=a.hoehen_diff), grenzen="Kamerazahl != Punktdichte; Hoehenregel grob; Seitenzuordnung der Videos haengt an der Nordausrichtung", quellen=erg), open(pf, "w"), indent=1, ensure_ascii=False); print("\nBericht:", pf)
    sys.exit(0 if lohnt_irgendwo else 5)

if __name__ == "__main__":
    main()
