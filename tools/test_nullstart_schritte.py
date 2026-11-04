#!/usr/bin/env python3
"""test_nullstart_schritte.py - BEWEIS, dass jede gelernte Erkenntnis ein fester Nullstart-Schritt mit Tor ist (2026-11-04, Nutzerregel beweis-pflicht-nullstart).
Quelle der Pflicht: tools/nullstart_pflicht.json (Schritt, Werkzeug, Erkenntnis, Tor, Beweisdatei, Test, Status).
  statisch:   python3 tools/test_nullstart_schritte.py
              -> nullstart.py ruft jedes Pflicht-Werkzeug auf, jeder Pflicht-Schritt steht in der Schrittliste / als Berichtsname, jedes Werkzeug existiert.
  nach Lauf:  python3 tools/test_nullstart_schritte.py --bericht modelle/<ziel>/nullstart_bericht.json
              -> zusaetzlich: jeder Pflicht-Schritt kam im Bericht vor und war ok (oder begruendet uebersprungen), Beweisdatei existiert im Zielordner.
              Schreibt <ziel>/nullstart_beweise.json (je Pflicht: lauf_ok, beweis_da, status) - der Nachweis fuer den Nutzer.
Exit 0 = alles erfuellt, 1 = etwas fehlt (Liste wird gedruckt). Status 'offen' wird NICHT als bestanden gezaehlt, nur ehrlich ausgewiesen.
"""
import sys, os, re, json, argparse

HIER = os.path.dirname(os.path.abspath(__file__))


def statisch(pfl, quelltext):
    fehler = []
    liste = re.search(r'schritte = \["anlegen"\][^\n]*', quelltext); liste = liste.group(0) if liste else ""
    for p in pfl:
        w = p["werkzeug"]
        if not os.path.exists(os.path.join(HIER, w)): fehler.append(f"{p['schritt']}: Werkzeug {w} fehlt")
        if w != "nullstart.py" and f"tools/{w}" not in quelltext and f'"{w}"' not in quelltext: fehler.append(f"{p['schritt']}: nullstart.py ruft tools/{w} nicht auf")
        s = p["schritt"]; name_im_code = (f'"{s}' in quelltext) or (f"f\"{s}" in quelltext) or (f'"{s.rstrip("_")}"' in liste)
        if not name_im_code: fehler.append(f"{s}: Schrittname kommt in nullstart.py nicht vor")
        for k in ("erkenntnis", "quelle", "tor", "beweis", "test", "status"):
            if not p.get(k): fehler.append(f"{s}: Pflichtfeld '{k}' leer")
        if p.get("status") not in ("bewiesen", "teilbewiesen", "offen"): fehler.append(f"{s}: Status '{p.get('status')}' unbekannt")
    return fehler


def nach_lauf(pfl, bp):
    B = json.load(open(bp)); zd = os.path.dirname(os.path.abspath(bp)); erg = []; fehler = []
    letzte = {}
    for e_ in B.get("schritte", []): letzte[e_.get("schritt")] = e_                                     # Wiederaufnahme (--ab): nur der LETZTE Eintrag je Schrittname zaehlt
    B = dict(B, schritte=list(letzte.values()))
    for p in pfl:
        s = p["schritt"]; treffer = [e for e in B.get("schritte", []) if e.get("schritt") == s or (s.endswith("_") and e.get("schritt", "").startswith(s))
                                   or (s == "abgleich" and e.get("schritt", "").startswith(("foto_diff_", "fehlteile_")) and p["werkzeug"].split("_")[0] in e.get("schritt", ""))]
        if s == "abgleich": treffer += [e for e in B.get("schritte", []) if e.get("schritt") == "abgleich"]
        lauf_ok = bool(treffer) and all(e.get("ok") for e in treffer); ueb = [e.get("grund") for e in treffer if e.get("uebersprungen")]
        beweis_da = os.path.exists(os.path.join(zd, p["beweis"]))
        e = dict(schritt=s, werkzeug=p["werkzeug"], gelaufen=bool(treffer), lauf_ok=lauf_ok, uebersprungen=ueb, beweis=p["beweis"], beweis_da=beweis_da, status=p["status"], test=p["test"])
        erg.append(e)
        if not treffer: fehler.append(f"{s}: im Bericht nicht gelaufen")
        elif not lauf_ok: fehler.append(f"{s}: rc != ok ({[t.get('rc') for t in treffer]})")
        if not beweis_da: fehler.append(f"{s}: Beweis {p['beweis']} fehlt")
    json.dump(dict(bericht=os.path.relpath(bp), alle_gelaufen=not fehler, pflicht=erg, offen=[p["schritt"] for p in pfl if p["status"] == "offen"],
                   hinweis="Status offen = Werkzeug laeuft, aber sein synthetischer Beweis besteht noch nicht; Ergebnis nicht als Messung verwenden"),
              open(os.path.join(zd, "nullstart_beweise.json"), "w"), indent=1, ensure_ascii=False)
    return fehler, erg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--bericht"); ap.add_argument("--pflicht", default=os.path.join(HIER, "nullstart_pflicht.json")); a = ap.parse_args()
    pfl = json.load(open(a.pflicht))["pflicht"]; qt = open(os.path.join(HIER, "nullstart.py")).read()
    fehler = statisch(pfl, qt)
    print(f"statisch: {len(pfl)} Pflichtschritte, {len(fehler)} Fehler")
    if a.bericht:
        f2, erg = nach_lauf(pfl, a.bericht); fehler += f2
        for e in erg: print(f"  {'OK ' if e['lauf_ok'] and e['beweis_da'] else 'FEHLT'} {e['schritt']:<14} {e['werkzeug']:<28} Status {e['status']}" + (f"  (uebersprungen: {e['uebersprungen']})" if e['uebersprungen'] else ""))
    st = {}
    for p in pfl: st[p["status"]] = st.get(p["status"], 0) + 1
    print("Status:", st)
    for f in fehler: print("  FEHLER:", f)
    print("BEWEIS nullstart_schritte:", "BESTANDEN" if not fehler else "NICHT BESTANDEN"); sys.exit(0 if not fehler else 1)


if __name__ == "__main__":
    main()
