#!/usr/bin/env python3
"""test_nullstart_schritte.py - BEWEIS, dass jede gelernte Erkenntnis ein fester Nullstart-Schritt mit Tor ist (2026-11-04, Nutzerregel beweis-pflicht-nullstart).
Quelle der Pflicht: tools/nullstart_pflicht.json (Schritt, Werkzeug, Erkenntnis, Tor, Beweisdatei, Test, Status).
  statisch:   python3 tools/test_nullstart_schritte.py
              -> nullstart.py ruft jedes Pflicht-Werkzeug auf, jeder Pflicht-Schritt steht in der Schrittliste / als Berichtsname, jedes Werkzeug existiert.
  nach Lauf:  python3 tools/test_nullstart_schritte.py --bericht modelle/<ziel>/nullstart_bericht.json
              -> zusaetzlich: jeder Pflicht-Schritt kam im Bericht vor und war ok (oder begruendet uebersprungen), Beweisdatei existiert im Zielordner.
              Schreibt <ziel>/nullstart_beweise.json (je Pflicht: lauf_ok, beweis_da, status) - der Nachweis fuer den Nutzer.
  Foto-Diff-Beweis (S2, 2026-11-05): python3 tools/test_nullstart_schritte.py --foto-diff [--bericht ...]
              -> tools/test_foto_diff.py an den Beweisobjekten aus nullstart_pflicht.json (Eintrag foto_diff.py, Feld 'beweisobjekte'); Exit je Objekt 0 = bestanden,
              1 = durchgefallen (Fehler), 3 = NICHT BEURTEILBAR (Gueltigkeitstor/keine Buendelkamera) = nur 'teilbewiesen', kein Fehler. Schreibt foto_diff_beweise.json
              (neben dem Bericht, sonst Arbeitsordner). GPU, Minuten je Objekt: im Nullstart-Schritt 'beweise' nur mit NULLSTART_FD_BEWEIS=1.
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


def foto_diff_beweise(pfl, aus):
    """test_foto_diff an den Beweisobjekten (nullstart_pflicht.json, Eintrag werkzeug foto_diff.py, Feld beweisobjekte). Rueckgabe (Fehlerliste, Ergebnisliste)."""
    import subprocess
    py = "/media/oem/scan/venv-seg/bin/python"; objekte = [b for p in pfl if p["werkzeug"] == "foto_diff.py" for b in p.get("beweisobjekte", [])]; erg = []; fehler = []
    root = os.path.dirname(HIER)
    for b in objekte:
        nm = b["objekt"].replace("/", "_").replace(".json", "") + "_" + b["foto"]; ad = os.path.join(aus, nm); os.makedirs(ad, exist_ok=True)
        cmd = [py, "-W", "ignore", "-I", os.path.join(HIER, "test_foto_diff.py"), b["objekt"], "--foto", b["foto"], "--audit-aus", ad, "--arbeit", os.path.join(ad, "arbeit")] + (["--stl", b["stl"]] if b.get("stl") else [])
        if b.get("fd"): cmd.append("--fd=" + b["fd"])
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True); st = {0: "bestanden", 1: "durchgefallen", 3: "teilbewiesen (nicht beurteilbar)"}.get(r.returncode, f"Fehler rc {r.returncode}")
        erg.append(dict(objekt=b["objekt"], foto=b["foto"], rc=r.returncode, status=st, ende=(r.stdout.strip().splitlines() or [""])[-1][:300]))
        if r.returncode not in (0, 3): fehler.append(f"foto_diff-Beweis {b['objekt']} {b['foto']}: {st}")
    return fehler, erg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--bericht"); ap.add_argument("--pflicht", default=os.path.join(HIER, "nullstart_pflicht.json")); ap.add_argument("--foto-diff", action="store_true"); a = ap.parse_args()
    pfl = json.load(open(a.pflicht))["pflicht"]; qt = open(os.path.join(HIER, "nullstart.py")).read()
    fehler = statisch(pfl, qt)
    print(f"statisch: {len(pfl)} Pflichtschritte, {len(fehler)} Fehler")
    if a.bericht:
        f2, erg = nach_lauf(pfl, a.bericht); fehler += f2
        for e in erg: print(f"  {'OK ' if e['lauf_ok'] and e['beweis_da'] else 'FEHLT'} {e['schritt']:<14} {e['werkzeug']:<28} Status {e['status']}" + (f"  (uebersprungen: {e['uebersprungen']})" if e['uebersprungen'] else ""))
    if a.foto_diff:
        zd = os.path.dirname(os.path.abspath(a.bericht)) if a.bericht else os.getcwd(); f3, e3 = foto_diff_beweise(pfl, os.path.join(zd, "foto_diff_beweise")); fehler += f3
        json.dump(e3, open(os.path.join(zd, "foto_diff_beweise.json"), "w"), indent=1, ensure_ascii=False)
        for e in e3: print(f"  foto_diff {e['objekt']} {e['foto']}: {e['status']}")
    st = {}
    for p in pfl: st[p["status"]] = st.get(p["status"], 0) + 1
    print("Status:", st)
    for f in fehler: print("  FEHLER:", f)
    print("BEWEIS nullstart_schritte:", "BESTANDEN" if not fehler else "NICHT BESTANDEN"); sys.exit(0 if not fehler else 1)


if __name__ == "__main__":
    main()
