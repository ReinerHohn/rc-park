#!/usr/bin/env python3
"""seiten_wiederholung.py - Entscheidung der Kette, ob nachgeholte Kameras Wandbild/Bau im SELBEN Lauf noch einmal speisen (Stufe seiten, tools/gesamtkette.py).

Kettenluecke 23.11.2026 (Lauf 1122q, schwabentor-1122): seiten_luecken holte fuer die ungesehenen Waende f01 (4,6 %) und f02 (4,8 %) Fotos nach, 327 Kameras wurden
eingetragen - aber die Stufe laeuft NACH Wandbild (fenster), Bauplan und Bau; danach kamen nur Fotoauftrag/html/neben_details/Befundliste. Die Kette schrieb
"nach dem Nachregistrieren fassade_ortho/fassade_fein neu" in den Bericht, und niemand tat es. Ablauf jetzt (gesamtkette.seiten_wiederholen):
  1. kandidaten(): ungesehene Waende aus audit/seiten_luecken.json, die laut audit/kameras_nachtragen_tor.json (Gueltigkeits-Tor, DIESES Laufs) mindestens eine
     BELEGTE neue Kamera sieht. Keine -> wie bisher (kein Wiederholen).
  2. fassade_ortho --nur <diese Waende> in <daten>/fassade_nachgeholt (Messflaeche eben, wie fenster_ortho; Sekunden je Wand).
  3. gewinn() (dieses Programm, Unterbefehl 'gewinn'): Abdeckung je Wand mit DEMSELBEN Mass wie seiten_luecken (seiten_luecken.wand_abdeckung) vorher/nachher.
     Steigt sie bei einer Wand um >= MIN_GEWINN (absolut), wiederholt die Kette EINMAL die Stufen ab RCPARK_SEITEN_WIEDERHOLUNG_AB (Standard 'fenster':
     Wandbild 5 cm + 1 cm, Parsing, Fenster/Oeffnungen, Bauplan mit Tiefe/Vorbauten/Tore, Bau + Abnahme, seiten-Bericht neu) als Teillauf (RCPARK_TEILLAUF=1:
     kein Nachholen, kein zweites Wiederholen, Schlussberichte macht der aeussere Lauf auf dem Endstand: html, neben_details, Befundliste).
Warum ALLE Waende im Teillauf und nicht nur die betroffenen: das Wandbild selbst kostet ~2 min fuer alle Waende; die Zeit (~29 min, Lauf 1122p) liegt in Bau,
Koerper-Schleife und Abnahme, die ohnehin das ganze Modell betreffen - ein Mischstand aus alten und neuen fassaden.json-Eintraegen waere die groessere Gefahr.
ANNAHME MIN_GEWINN 0,05: ein Viertel der Ungesehen-Schwelle von seiten_luecken (0,2); an einer 400-m2-Wand 20 m2 neue Bilddaten, weit ueber Raster-/Randrauschen.
  /media/oem/scan/venv-seg/bin/python -I tools/seiten_wiederholung.py gewinn <audit/seiten_luecken.json> <neuer fassaden-ordner> --aus <json> [--min-gewinn 0.05] [--alt <fassade>] [--sperre-aus <json>]
23.11.2026 (Lauf 1122t): GEWINN verlangt zusaetzlich Deckungsgleichheit (tools/wandbild_einigkeit.py) - Abdeckung allein liess ein verschmiertes Wandbild durch.
Exit (gewinn): 0 = mindestens eine Wand gewinnt -> wiederholen, 3 = keine, 2 = Eingaben fehlen.
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MIN_GEWINN = float(os.environ.get("RCPARK_SEITEN_MIN_GEWINN", "0.05"))


def kandidaten(tor_json, seiten_json, seit=None):
    """-> (waende, grund). waende = [{nr, id, abdeckung_vorher, neu_sicht}] der ungesehenen Waende mit >= 1 belegter neuer Kamera.
    seit: Zeitstempel - ein Tor-Bericht, der aelter ist, gilt nicht (Nachholen dieses Laufs uebersprungen oder abgebrochen)."""
    if not os.path.exists(seiten_json): return [], "kein seiten_luecken.json"
    S = json.load(open(seiten_json)); ung = set(S.get("ungesehen") or [])
    if not ung: return [], "keine ungesehene Wand"
    if not os.path.exists(tor_json): return [], "kein kameras_nachtragen_tor.json (Nachholen ohne Tor-Schritt oder nicht gelaufen)"
    if seit is not None and os.path.getmtime(tor_json) < seit: return [], "kameras_nachtragen_tor.json stammt nicht aus diesem Lauf (Nachholen uebersprungen/abgebrochen)"
    T = json.load(open(tor_json))
    if not T.get("belegt"): return [], f"keine belegte neue Kamera ({T.get('neu', 0)} nachgetragen, {len(T.get('gesperrt') or [])} gesperrt)"
    sicht = {w["nr"]: w for w in T.get("waende") or []}
    raus = []
    for w in S.get("waende") or []:
        if w["nr"] in ung and sicht.get(w["nr"], {}).get("neu_sicht", 0) >= 1:
            raus.append(dict(nr=w["nr"], id=w.get("id") or sicht[w["nr"]].get("id") or "f%02d" % w["nr"], abdeckung_vorher=w.get("abdeckung"), neu_sicht=sicht[w["nr"]]["neu_sicht"]))
    return raus, ("" if raus else "keine belegte neue Kamera sieht eine ungesehene Wand")


def gewinn(seiten_json, neu_dir, min_gewinn=MIN_GEWINN, alt_dir=None, e_min=None):
    """Abdeckung vorher (seiten_luecken.json) gegen nachher (ortho_<id>.png in <neu_dir>, fassaden.json dort) je Wand gleicher Kennung - UND Deckungsgleichheit.
    23.11.2026 (Lauf 1122t): f01 Abdeckung 0,037 -> 0,998 = 'GEWINN', das Wandbild war aber verschmiert (Kameras ungenau). Jetzt zaehlt eine Wand nur, wenn
    (a) die Abdeckung um >= min_gewinn steigt UND (b) die EINIGE Flaeche (tools/wandbild_einigkeit.py: Zellen mit >= 3 Fotos und Struktur-Uneinigkeit
    <= S_GRENZE, Anteil an der Wand) um >= min_gewinn steigt UND der einige Anteil unter den beurteilbaren Zellen >= e_min ist. Die Quote vorher wird nicht
    verlangt (auf 4 % Abdeckung ist sie zufaellig hoch oder unbeurteilbar); alt_dir (Wandbild VOR dem Nachholen) liefert die einige Flaeche vorher, sonst 0.
    Ist (a) erfuellt, (b) nicht: Meldung 'Abdeckung ohne Deckungsgleichheit - Kameras ungenau' und, wenn <neu_dir>/ortho_<id>_einzeln da ist,
    ausschluss_vorschlag (Fotos mit r < R_MIN); reicht er (Rest einig), steht er in 'sperre' (gesamtkette.seiten_wiederholen probiert ihn EINMAL).
    -> dict(waende=[{id, vorher, nachher, gewinn, einig_*, ok, meldung}], wiederholen=bool, sperre={waende:[{id, n, ohne}]} | None)."""
    import seiten_luecken as SL, wandbild_einigkeit as WE
    e_min = WE.E_MIN if e_min is None else e_min
    S = json.load(open(seiten_json)); vor = {w.get("id") or "f%02d" % w["nr"]: w for w in S.get("waende") or []}
    FN = json.load(open(os.path.join(neu_dir, "fassaden.json")))["fassaden"]; raus = []; sperre = []
    FA = {}
    if alt_dir and os.path.exists(os.path.join(alt_dir, "fassaden.json")): FA = {F_.get("id"): F_ for F_ in json.load(open(os.path.join(alt_dir, "fassaden.json")))["fassaden"]}
    for F in FN:
        fid = F.get("id"); w = vor.get(fid)
        if w is None: continue
        nach = SL.wand_abdeckung(neu_dir, F, w["nr"])
        g = None if nach is None else round(nach - float(w.get("abdeckung") or 0.0), 3)
        ok_abd = bool(g is not None and g >= min_gewinn)
        en = WE.wand_einigkeit(neu_dir, F); ev = WE.wand_einigkeit(alt_dir, FA[fid]) if fid in FA else None
        fl_v = (ev or {}).get("einig_flaeche_anteil") or 0.0; fl_n = (en or {}).get("einig_flaeche_anteil") or 0.0; q_n = (en or {}).get("einig_anteil")
        ok_ein = bool(en is not None and q_n is not None and q_n >= e_min and fl_n - fl_v >= min_gewinn)
        meldung = ""
        if ok_abd and not ok_ein:
            meldung = ("Einigkeit nicht messbar (struktur_/abdeckung_ fehlen)" if en is None else
                       f"Abdeckung ohne Deckungsgleichheit - Kameras ungenau (einig {q_n} < {e_min} unter beurteilbar {en['beurteilt_anteil']})")
            if os.path.isdir(os.path.join(neu_dir, f"ortho_{fid}_einzeln")):
                v = WE.ausschluss_vorschlag(neu_dir, F, e_min=e_min)
                if v and v["reicht"]:
                    sperre.append(dict(id=fid, n=F.get("n"), ohne=v["ohne"])); meldung += f"; ohne {len(v['ohne'])} uneinige Fotos einig {v['einig_nachher']} (bedeckt {v['bedeckt_vorher']} -> {v['bedeckt_nachher']}) -> Sperre vorgeschlagen"
                elif v: meldung += f"; Ausschluss der {len(v['ohne'])} uneinigsten Fotos reicht nicht (einig {v['einig_nachher']})"
        raus.append(dict(id=fid, nr=w["nr"], vorher=w.get("abdeckung"), nachher=None if nach is None else round(nach, 3), gewinn=g, fotos_vorher=w.get("fotos"), fotos_nachher=len(F.get("fotos") or {}),
                         einig_anteil=q_n, einig_flaeche_vorher=round(fl_v, 3), einig_flaeche_nachher=round(fl_n, 3), beurteilt=(en or {}).get("beurteilt_anteil"),
                         ok_abdeckung=ok_abd, ok_einig=ok_ein, ok=ok_abd and ok_ein, meldung=meldung))
    return dict(waende=raus, wiederholen=any(r["ok"] for r in raus), min_gewinn=min_gewinn, e_min=e_min, sperre=dict(waende=sperre) if sperre else None)


def teillauf_befehl(py, quelle, ziel, ab="fenster", trotz_lage=False):
    """Befehl des Teillaufs (nur Stufen ab <ab> bis 'seiten'; RCPARK_TEILLAUF=1 setzt der Aufrufer)."""
    return [py, "-u", "-I", "tools/gesamtkette.py", quelle, "--ziel", ziel, "--ab", ab, "--bis", "seiten"] + (["--trotz-lage"] if trotz_lage else [])


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="befehl", required=True)
    g = sp.add_parser("gewinn"); g.add_argument("seiten_json"); g.add_argument("neu_dir"); g.add_argument("--aus", required=True); g.add_argument("--min-gewinn", type=float, default=MIN_GEWINN)
    g.add_argument("--alt", help="Wandbild-Ordner VOR dem Nachholen (einige Flaeche vorher); fehlt er, gilt vorher 0"); g.add_argument("--sperre-aus", help="Sperrvorschlag (Fotos je Wand) hierhin schreiben")
    a = ap.parse_args()
    if not os.path.exists(a.seiten_json) or not os.path.exists(os.path.join(a.neu_dir, "fassaden.json")): print("FEHLER: seiten_luecken.json oder neues fassaden.json fehlt"); return 2
    erg = gewinn(a.seiten_json, a.neu_dir, a.min_gewinn, alt_dir=a.alt)
    __import__("json_sicher").schreiben(a.aus, erg)
    if a.sperre_aus and erg.get("sperre"): __import__("json_sicher").schreiben(a.sperre_aus, erg["sperre"])
    for r in erg["waende"]:
        print(f"Wand {r['id']}: Abdeckung {r['vorher']} -> {r['nachher']} (Fotos {r['fotos_vorher']} -> {r['fotos_nachher']}), einig {r['einig_anteil']} (einige Flaeche {r['einig_flaeche_vorher']} -> {r['einig_flaeche_nachher']})"
              + ("   <-- GEWINN, wiederholen" if r["ok"] else "") + (f"   {r['meldung']}" if r["meldung"] else ""))
    print("WIEDERHOLEN" if erg["wiederholen"] else f"kein messbarer Gewinn (< {a.min_gewinn:g})"); return 0 if erg["wiederholen"] else 3


if __name__ == "__main__":
    sys.exit(main())
