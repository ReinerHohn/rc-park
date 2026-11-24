#!/usr/bin/env python3
"""fusion_vorab.py - EINE Fusion je Kettenlauf statt zwei (24.11.2026, Laufzeit-Bericht 1122z: TEILFUSION 470 s in 'sfm' + 445 s in 'neu_fusionieren').

URSACHE der Doppelfusion: die Kettenstufe 'tore' (tools/gesamtkette.py) fusioniert neu (tools/wolke_neu_fusionieren.py), wenn die Tore Bilder zum Ausschluss
nennen: audit/kamera_plausibel.json (tools/kamera_gelaende.py, braucht die AUSRICHTUNG), audit/kette_insel.json (tools/kette_insel_pruefen.py, nur SfM-Netz) und
audit/wolke_gruppen.json (tools/wolke_gruppen_pruefen.py, SfM-Netz + Ausrichtung). Keine der drei Listen braucht die dichte Wolke - sie liefen nur NACH ihr, weil die
Ausrichtung der Kette (pipeline_objekt.py Schritt 5) erst auf der dichten Wolke rechnet. Die Vorstufe 'Lage frueh' (tools/lage_frueh.py) hat aber schon VOR der dichten
Wolke dieselbe Ausrichtung (Loesung 0) auf dem duennen Netz - damit lassen sich die Listen und die Ausloese-Regel vorab rechnen.

ABLAUF:
  1. plan()      - in lage_frueh.sfm_mit_vorstufe nach der Vorstufe: die drei Listen-Werkzeuge auf <P>/lage_frueh (Objekt-Kopie + Ausrichtung des duennen Netzes),
                   Regel noetig() mit 'Lage bestanden' angenommen (die Regel ist darin monoton: feuert sie dann, feuert sie immer) -> <P>/lage_frueh/fusion_vorab_plan.json
  2. anwenden()  - in dicht_kette.py (pipeline_objekt.py) direkt vor der ersten Fusion: Plan sicher und vom selben SfM-Netz -> fusion.cfg nach DERSELBEN Regel
                   (wolke_neu_fusionieren.plan_berechnen) kuerzen, Marke <pipe>/dicht/stereo/fusion_vorab.json (aktiv_vorher, bleibt).
  3. Kette 'tore' wie bisher: noetig() -> wolke_neu_fusionieren.py prueft mit den Listen NACH der dichten Wolke nach: gleich = rc 2 (keine zweite Fusion),
     abweichend = RUECKFALL (Logzeile, zweite Fusion wie vorher). Feuert die Regel spaet NICHT, aber die erste Fusion war gekuerzt: offen() -> --vorab-zurueck (Fusion
     mit der fusion.cfg von vorher, Logzeile). Ergebnis-Wolke damit in jedem Fall nach derselben Regel wie vor dem 24.11.
ANNAHME: die Ausrichtung der dichten Wolke rechnet jetzt auf der schon bereinigten Wolke (Fit auf 600 000 Zufallspunkten; 1122z: 3 von 625 Bildern weg) - nicht bitgleich.
Abschalten: RCPARK_FUSION_VORAB=0 (dann kein Plan, alte Doppelfusion)."""
import os, sys, json, time

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
PLAN = "fusion_vorab_plan.json"


def noetig(erg, bestanden, gruppen_aus):
    """Ausloese-Regel der Neufusion in gesamtkette 'tore' (15.11./19.11.2026, unveraendert hierher gezogen): Geisterwand aus Kameras unter Gelaende / Insel-Ketten bei
    GPS ohne Widerspruch, oder das Wolken-Gruppen-Tor nennt Bilder. bestanden(erg) = lage_proben.lage_bestanden, gruppen_aus() = Liste des Gruppen-Tors nicht leer."""
    return bool(((not bestanden(erg) or erg.get("insel") == 3) and (erg.get("kamera_gelaende") == 3 or erg.get("insel") == 3) and erg.get("gps") in (0, None))
                or (erg.get("gruppen") == 3 and gruppen_aus()))


def sicher(erg, gruppen_aus):
    """Feuert noetig() unabhaengig vom Lage-Urteil (das Grundriss/Lot der dichten Wolke braucht)? 'not bestanden' steht nur in einem ODER -> mit bestanden=True pruefen."""
    return noetig(erg, lambda e: True, gruppen_aus)


def stempel(P):
    """Kennung des SfM-Netzes (images.bin + points3D.bin: Groesse, Zeit) - Plan und Fusion muessen zum selben Netz gehoeren."""
    sp = os.path.join(P, "sfm", "sparse", "0"); s = []
    for n in ("images.bin", "points3D.bin"):
        q = os.path.join(sp, n)
        if not os.path.isfile(q): return None
        st = os.stat(q); s.append([n, st.st_size, int(st.st_mtime)])
    return s


def _liste(p):
    try: return bool(json.load(open(p)).get("ausschliessen"))
    except Exception: return False


def plan(P, ziel, lauf, B, log, py_col=sys.executable, py=None):
    """Schritt 1 (Kette, nach lage_frueh). lauf = Stufenfunktion der Kette. Schreibt immer <P>/lage_frueh/fusion_vorab_plan.json (auch 'nicht sicher' mit Grund)."""
    L = os.path.join(P, "lage_frueh"); pj = os.path.join(L, PLAN); py = py or py_col
    def ende(ok, grund, **k):
        R = dict(werkzeug="fusion_vorab.py", zeit=time.strftime("%Y-%m-%d %H:%M:%S"), sicher=ok, grund=grund, stempel=stempel(P), audit=L, **k)
        os.makedirs(L, exist_ok=True); json.dump(R, open(pj, "w"), indent=1, ensure_ascii=False)
        print(f"FUSION VORAB: {'SICHER' if ok else 'nicht sicher'} - {grund}", flush=True); return R
    if os.environ.get("RCPARK_FUSION_VORAB", "1") == "0": return ende(False, "abgeschaltet (RCPARK_FUSION_VORAB=0)")
    ok_ = os.path.join(L, "objekt.json"); au = os.path.join(L, "messprotokoll", f"SFM-AUSRICHTUNG-{ziel}.loesung0.json"); sp = os.path.join(P, "sfm", "sparse", "0")
    if not os.path.isfile(au): au = au.replace(".loesung0.json", ".json")      # Vorstufe vor dem 24.11.: nur die zuletzt geschriebene Loesung (unten geprueft)
    try: J = json.load(open(os.path.join(L, "lage_frueh.json")))
    except Exception: J = {}
    la = J.get("laeufe") or []
    fehlt = [q for q in (ok_, au, os.path.join(sp, "images.bin")) if not os.path.isfile(q)]
    if fehlt: return ende(False, "Eingaben fehlen: " + ", ".join(fehlt))
    if not la or la[0].get("loesung") != 0 or la[0].get("kaputt") or (not au.endswith(".loesung0.json") and la[-1].get("loesung") != 0):
        return ende(False, f"keine Ausrichtung Loesung 0 der Vorstufe (Laeufe {[l.get('loesung') for l in la]}, Datei {os.path.basename(au)}) - die Kette richtet die dichte Wolke mit Loesung 0 aus")
    erg = dict(gps=(la[0].get("tore") or {}).get("gps"))
    for p_ in ("kamera_plausibel.json", "kette_insel.json", "wolke_gruppen.json"):          # alte Listen eines frueheren Laufs nie mitlesen
        q = os.path.join(L, "audit", p_)
        if os.path.exists(q): os.remove(q)
    erg["insel"] = lauf(B, "vorab_insel", [py_col, "-I", "tools/kette_insel_pruefen.py", ok_, sp], log, ok=(0, 3))[0]
    erg["kamera_gelaende"] = lauf(B, "vorab_kamera_gelaende", [py, "-I", "tools/kamera_gelaende.py", ok_, au], log, ok=(0, 3))[0]
    erg["gruppen"] = lauf(B, "vorab_gruppen", [py_col, "-I", "tools/wolke_gruppen_pruefen.py", ok_, au, sp, "--schreiben"], log, ok=(0, 3))[0]
    if any(erg[k] not in (0, 3) for k in ("insel", "kamera_gelaende", "gruppen")) or not os.path.isfile(os.path.join(L, "audit", "kamera_plausibel.json")):
        return ende(False, f"Listen-Werkzeug ohne Urteil {erg}", tore=erg)
    if not sicher(erg, lambda: _liste(os.path.join(L, "audit", "wolke_gruppen.json"))):
        return ende(False, f"Neufusion nach den Toren nicht sicher (Tore {erg}) - erste Fusion mit allen Bildern, die Kette entscheidet nach der dichten Wolke", tore=erg)
    return ende(True, f"Tore auf dem duennen Netz {erg} loesen die Neufusion in jedem Fall aus - Ausschluesse schon vor der ersten Fusion", tore=erg)


def anwenden(D, P):
    """Schritt 2 (dicht_kette.py, direkt vor der ersten Fusion). -> Marke (dict) oder None (fusion.cfg unveraendert). Nie Ausnahme nach aussen: im Zweifel alte Fusion."""
    try:
        import wolke_neu_fusionieren as WNF
        cfg = os.path.join(D, "stereo", "fusion.cfg"); vm = os.path.join(D, "stereo", WNF.VORAB); alt = WNF.vorab_marke(D)
        if alt and alt.get("aktiv_vorher"):                                     # Marke eines nicht abgeschlossenen Laufs (oder Wiederholung nach Speichermangel): erst zurueck auf vorher
            WNF.text_atomar(cfg, "\n".join(alt["aktiv_vorher"]) + "\n"); os.remove(vm); print(f"Vorab-Ausschluss: alte Marke zurueckgenommen ({len(alt['aktiv_vorher'])} Bilder)", flush=True)
        elif os.path.exists(vm): os.remove(vm)
        if os.environ.get("RCPARK_FUSION_VORAB", "1") == "0": print("Vorab-Ausschluss: abgeschaltet (RCPARK_FUSION_VORAB=0)", flush=True); return None
        try: pl = json.load(open(os.path.join(P, "lage_frueh", PLAN)))
        except Exception: print("Vorab-Ausschluss: kein Plan (Vorstufe 'Lage frueh' nicht gelaufen) - erste Fusion mit fusion.cfg wie vorgefunden, ggf. zweite Fusion in der Kette", flush=True); return None
        if not pl.get("sicher"): print(f"Vorab-Ausschluss: nicht angewandt - {pl.get('grund')}", flush=True); return None
        if pl.get("stempel") is None or pl.get("stempel") != stempel(P): print("Vorab-Ausschluss: Plan gehoert zu einem anderen SfM-Netz - nicht angewandt (RUECKFALL: ggf. zweite Fusion)", flush=True); return None
        if not os.path.isfile(cfg): print(f"Vorab-Ausschluss: keine {cfg} - nicht angewandt", flush=True); return None
        r = WNF.plan_berechnen(pl["audit"], D)
        if r["bleibt"] == r["aktiv"]: print("Vorab-Ausschluss: kein Bild der fusion.cfg steht in den Listen - nichts zu kuerzen", flush=True); return None
        if len(r["bleibt"]) < 2: print("Vorab-Ausschluss: es bliebe kein Bild - nicht angewandt", flush=True); return None
        if not os.path.exists(cfg + ".alle"): WNF.text_atomar(cfg + ".alle", "\n".join(r["alle"]) + "\n")
        M = dict(werkzeug="fusion_vorab.py", zeit=time.strftime("%Y-%m-%d %H:%M:%S"), grund=pl.get("grund"), aktiv_vorher=r["aktiv"], bleibt=r["bleibt"], stempel=pl.get("stempel"))
        WNF.text_atomar(vm, json.dumps(M, indent=1, ensure_ascii=False)); WNF.text_atomar(cfg, "\n".join(r["bleibt"]) + "\n")
        print(f"FUSION VORAB: {len(r['aktiv']) - len(r['bleibt'])} Bilder schon vor der ersten Fusion ausgeschlossen ({len(r['bleibt'])} bleiben) - die Kette prueft nach den Toren nach, Marke {vm}", flush=True)
        return M
    except Exception as e:
        print(f"Vorab-Ausschluss: Fehler {type(e).__name__}: {e} - erste Fusion mit fusion.cfg wie vorgefunden", flush=True); return None


def offen(P):
    """Schritt 3: liegt eine Marke mit gekuerzter erster Fusion, die die Kette noch nicht nachgeprueft hat?"""
    try: m = json.load(open(os.path.join(P, "dicht", "stereo", "fusion_vorab.json")))
    except Exception: return False
    return bool(m.get("aktiv_vorher")) and m.get("aktiv_vorher") != m.get("bleibt")


if __name__ == "__main__":
    print(__doc__)
