#!/usr/bin/env python3
"""ebenen_stapel.py - EBENENFINDER Schichtstapel aus Kanten fuer die Abweichungsschleife (27.11.2026, Kandidat K7 aus modelle/SPEC_VERFAHREN_RUNPOD_2026-11-27.md).

Methode: modelle/METHODE_EBENEN_BAUPLAN.md Schritt 1 (Schichtstapel) + Regeln aus LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md Nachtrag 02:33 (Probe 14 x 0,3 m Stadtseite).
  1. Stapel je Wand: tools/ebenen_bauplan.py --stapel w0 w1 schritt (duenne parallele Ebenen, Band = halber Schritt) -> <aus>/schichten/ebenen.json.
     Suchbereich w0..w1 = Tiefen-Suchbereich des Ebenen-Sweeps je Wand (fassade/vorbauten_fNN.json 'w_bereich', gegen die gemessene Wandebene), kein fester Wert;
     Schritt = 2 x Toleranz der Abweichung (--tol 0,15 -> Schichten 0,3 m dick; jede Schicht ist so dick wie das, was ebenen_abweichung 'an der Flaeche' nennt).
  2. SPITZEN der Punktzahl je Wand = Ebenen: oertliches Maximum der Kantenpunkte ueber die Schichten UND >= 2 % der staerksten Schicht (Logbuch-Regel).
  3. GEGENPROBE dichte Wolke (Kernmethode: Wolke nur Veto): Anteil der Kantenpunkte der Schicht mit Wolkenpunkt <= 10 cm; >= 80 % = Ebene, 40-80 % = pruefen (nicht verwendet),
     darunter = Scheintreffer (Draehte, Mehrdeutigkeit). Ohne Wolke wird keine Schicht verwendet (rc 3, alter Weg).
  4. Ausgabe <aus>/ebenen.json = Ebenen der Kette (ebenen-ordner) + bestaetigte Schichten (art 'schicht', ohne die Schicht der Wand selbst) -> Eingang fuer tools/ebenen_schleife.py;
     Bericht <aus>/stapel_ebenen.json (alle Schichten mit Punktzahl, Spitze, Wolkenanteil, Urteil).
Aufruf: ebenen_stapel.py <objekt.json> <fassade-ordner> <kanten-ordner> <ebenen-ordner> <aus-ordner> [--wolke npy] [--tol 0.15] [--schichten stapel/ebenen.json]
  --schichten: vorhandenen Stapel auswerten statt ebenen_bauplan zu rufen (Test, Wiederholung).
Verwandt: tools/ebenen_bauplan.py (rechnet den Stapel), tools/ebenen_schleife.py (Verbraucher), tools/doppelschicht.py (zwei Ebenen in der Wolke, BIC), tools/fassade_tiefe.py (breiter Ebenen-Sweep).
rc 0 = mindestens eine bestaetigte Zusatzebene (aus/ebenen.json geschrieben), 3 = keine (aus/ebenen.json entfernt -> Kette nimmt die alten Ebenen), 2 = Eingabe fehlt.
"""
import sys, os, json, argparse, subprocess, numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
MIN_ANTEIL_STAERKSTE = 0.02            # Logbuch 21.11. Nachtrag 02:33: Schicht gilt als Ebene, wenn Punktzahl >= 2 % der staerksten Schicht ...
WOLKE_ABSTAND = 0.10                   # ... und die dichte Wolke >= 80 % ihrer Kantenpunkte bestaetigt (<= 10 cm); 40-80 % = pruefen
WOLKE_EBENE, WOLKE_PRUEFEN = 0.80, 0.40


def spitzen(punkte):
    """Indizes der oertlichen Maxima der Punktzahl ueber die (nach w sortierten) Schichten, die >= MIN_ANTEIL_STAERKSTE der staerksten erreichen.
    Rand zaehlt als 0; bei gleich hohen Nachbarn gilt die erste (p_j > p_{j-1} und p_j >= p_{j+1})."""
    p = np.asarray(punkte, float)
    if not len(p) or p.max() <= 0: return []
    q = np.r_[0.0, p, 0.0]; mx = p.max()
    return [j for j in range(len(p)) if q[j + 1] > q[j] and q[j + 1] >= q[j + 2] and p[j] >= MIN_ANTEIL_STAERKSTE * mx]


def urteil(anteil):
    if anteil is None: return "unbestaetigt"
    return "ebene" if anteil >= WOLKE_EBENE else ("pruefen" if anteil >= WOLKE_PRUEFEN else "schein")


def wolke_anteil(P, WO):
    """Anteil der Kantenpunkte P mit Wolkenpunkt <= WOLKE_ABSTAND (None ohne Wolke oder ohne Wolkenpunkte im Umfeld)."""
    if WO is None or not len(P): return None
    from scipy.spatial import cKDTree
    lo, hi = P.min(0) - 0.5, P.max(0) + 0.5; m = np.all((WO >= lo) & (WO <= hi), axis=1)
    if m.sum() < 10: return None
    d, _ = cKDTree(WO[m]).query(P, distance_upper_bound=WOLKE_ABSTAND + 1e-6); return float((d <= WOLKE_ABSTAND).mean())


def bereich(fassade, waende):
    """Stapel-Suchbereich (w0, w1) gegen die Wandebene: Vereinigung der Sweep-Suchbereiche (vorbauten_fNN.json 'w_bereich') minus Wandversatz je Wand. None = keiner vorhanden."""
    lo, hi = [], []
    for e in waende:
        vj = os.path.join(fassade, f"vorbauten_{e['id'][:3]}.json")
        if not os.path.exists(vj): continue
        wb = json.load(open(vj)).get("w_bereich")
        if wb and len(wb) == 2: lo.append(float(wb[0]) - float(e["w"])); hi.append(float(wb[1]) - float(e["w"]))
    return (min(lo), max(hi)) if lo else None


def auswerten(S, E, WO, schritt):
    """S = Schichten (art 'schicht'), E = Ebenen der Kette. -> (Bericht je Wand, bestaetigte Zusatzebenen)."""
    wand = {e["id"][:3]: e for e in E if e.get("art") == "wand"}; ber, neu = [], []
    for k in sorted({s["id"][:3] for s in S}):
        L = sorted([s for s in S if s["id"][:3] == k], key=lambda s: s["w"]); pk = set(spitzen([s.get("punkte", 0) for s in L])); w_wand = wand.get(k, {}).get("w")
        zeilen = []
        for j, s in enumerate(L):
            z = dict(id=s["id"], w=s["w"], punkte=int(s.get("punkte", 0)), spitze=j in pk)
            if j in pk and s.get("sweep") and os.path.exists(s["sweep"]):
                z["wolke_anteil"] = wolke_anteil(np.load(s["sweep"])["P"].astype(float), WO); z["urteil"] = urteil(z["wolke_anteil"])
                if w_wand is not None and abs(s["w"] - w_wand) <= schritt / 2 + 1e-6: z["rolle"] = "wand"          # Schicht der Wand selbst: Ebene f..._wand gibt es schon
                elif z["urteil"] == "ebene": neu.append({**s, "stapel_spitze": True, "wolke_anteil": round(z["wolke_anteil"], 3)}); z["rolle"] = "zusatzebene"
            zeilen.append(z)
        ber.append(dict(wand=k, w_wand=w_wand, schichten=zeilen))
    return ber, neu


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fassade"); ap.add_argument("kanten"); ap.add_argument("ebenen"); ap.add_argument("aus")
    ap.add_argument("--wolke"); ap.add_argument("--tol", type=float, default=0.15, help="Toleranz der Abweichung (ebenen_abweichung --tol); Schichtdicke = 2 x tol"); ap.add_argument("--schichten"); a = ap.parse_args()
    os.makedirs(a.aus, exist_ok=True); ej_aus = os.path.join(a.aus, "ebenen.json")
    if os.path.exists(ej_aus): os.remove(ej_aus)                                      # nie den Stand eines frueheren Laufs weiterreichen
    ej = os.path.join(a.ebenen, "ebenen.json")
    if not os.path.exists(ej): print(f"{ej} fehlt - erst Stufe bauplan_ebenen"); return 2
    E = json.load(open(ej))["ebenen"]; waende = [e for e in E if e.get("art") == "wand"]; schritt = round(2 * a.tol, 3)
    if not waende: print("keine Wandebene in ebenen.json - kein Stapel"); return 3
    sj = a.schichten
    if not sj:
        br = bereich(a.fassade, waende)
        if br is None: print("kein Sweep-Suchbereich (vorbauten_fNN.json 'w_bereich') - kein Stapel, alter Weg"); return 3
        sd = os.path.join(a.aus, "schichten"); sj = os.path.join(sd, "ebenen.json")
        cmd = [sys.executable, "-W", "ignore", "-I", os.path.join(HIER, "ebenen_bauplan.py"), a.objekt, a.fassade, a.kanten, sd, "--stapel", f"{br[0]:.3f}", f"{br[1]:.3f}", str(schritt),
               "--nur", ",".join(f"{e['id'][:3]}_s*" for e in waende), "--seiten", "0", "--bild", "0"]
        print("STAPEL:", " ".join(cmd[3:]), flush=True); r = subprocess.run(cmd)
        if r.returncode not in (0, 3) or not os.path.exists(sj): print(f"ebenen_bauplan --stapel rc {r.returncode} - kein Stapel, alter Weg"); return 3
    S = [s for s in json.load(open(sj))["ebenen"] if s.get("art") == "schicht"]
    WO = np.asarray(np.load(a.wolke, mmap_mode="r")[:, :3], dtype=np.float32) if a.wolke and os.path.exists(a.wolke) else None
    ber, neu = auswerten(S, E, WO, schritt)
    for b in ber:
        print(f"{b['wand']}: " + ", ".join(f"{z['id']} w {z['w']:+.2f} {z['punkte']}" + (f" SPITZE Wolke {z['wolke_anteil'] * 100:.0f} % {z['urteil']}" if z.get("wolke_anteil") is not None else (" SPITZE ohne Wolke" if z["spitze"] else ""))
                                       + (f" [{z['rolle']}]" if z.get("rolle") else "") for z in b["schichten"]))
    json.dump(dict(quelle="tools/ebenen_stapel.py", schritt=schritt, wolke=bool(WO is not None), waende=ber, zusatzebenen=[s["id"] for s in neu]), open(os.path.join(a.aus, "stapel_ebenen.json"), "w"), indent=1)
    if not neu: print("STAPEL: keine bestaetigte Zusatzebene" + ("" if WO is not None else " (ohne Wolke keine Gegenprobe)") + " - Schleife nimmt die Ebenen der Kette"); return 3
    json.dump(dict(quelle="tools/ebenen_stapel.py", ebenen=E + neu), open(ej_aus, "w"), indent=1)
    print(f"STAPEL: {len(neu)} bestaetigte Zusatzebenen ({', '.join(s['id'] for s in neu)}) -> {ej_aus}"); return 0


if __name__ == "__main__": sys.exit(main())
