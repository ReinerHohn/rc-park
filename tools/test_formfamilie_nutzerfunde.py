#!/usr/bin/env python3
"""test_formfamilie_nutzerfunde.py - Beweistest fuer tools/formfamilie_pruefen.py (Regel 3e, Spec modelle/SPEC_FORMFAMILIE_SICHTPRUEFUNG.md).
Laeuft das Werkzeug auf den Teilen der 7 Nutzerfunde (11.11.) und der Gegenprobe und wertet aus. Die Stichwoerter stehen NUR hier (Auswertung),
nie im Pruefer-Prompt (Selbstbezug-Verbot). Erkannt = passende Abweichung mit Sicherheit hoch/mittel an dem genannten Teil.
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_formfamilie_nutzerfunde.py [--teile_dir D] [--formliste F] [--arbeit A] [--neu]
Exit 0 = Ziel erreicht (>= 6 von 7 erkannt, <= 1 Fehlalarm hoch), sonst 1."""
import sys, os, re, json, glob, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formfamilie_pruefen as FP

FF_DIR = "/media/oem/scan/rc-park_kreis/kaufhaus_grob3/fotoform"
# Fund-Nr: (Beschreibung, [Teile], Stichwort-Regex ueber merkmal+foto+modell)
FUNDE = {
    "1a Staffelgiebel Ost: Treppe statt Saegezahn": (["staffelgiebel__ost"], r"stufenform|treppe|zack|s(ae|ä)gezahn|kontur"),
    "1b Staffelgiebel West: Treppe statt Saegezahn": (["staffelgiebel__west"], r"stufenform|treppe|zack|s(ae|ä)gezahn|kontur"),
    "2 Brüstung Balkon: seitliche Gelaender fehlen": (["bruestung__balkon"], r"seiten|ende|enden|stirn|gel(ae|ä)nder|r(ue|ü)ckf|zur wand"),
    "3 Baldachine: Masswerk-Aufsatz fehlt": (["baldachinreihe__baldachine"], r"ma(ss|ß)werk|aufsatz|fiale|bekr(oe|ö)nung|kr(oe|ö)nung"),
    "4 Laube: Saeulensockel zu niedrig": (["bogenreihe__laube", "zylinder__dienst_laube_u975_sockel"], r"(sockel|fu(ss|ß)).*(hoch|niedrig|proportion|h(oe|ö)he|verh)|(hoch|niedrig|proportion|h(oe|ö)he).*(sockel|fu(ss|ß))"),
    "5 Laube: Seitendurchgang Bogen statt Rechteck": (["bogenreihe__laube", "quader__laube_rueck", "kreuzgewoelbe__laube"], r"durchgang|seiten(oe|ö)ffnung|(seiten|ecke|ende).*bogen|bogenart|(rund|spitz).*rechteck|rechteck.*(rund|spitz|bogen)"),
    "6 Tor B2: rund statt spitz": (["freiform__tor_b2__ausschnitt"], r"bogen|spitz|rund|segment"),
    "7 Erker 0: Rippennetz/Masswerk fehlt": (["erker_polygon__0"], r"rippe|ma(ss|ß)werk|netz"),
}
GEGEN = ["helm_geschweift__o", "helm_geschweift__w", "zylinder__dienst_laube_u975_schaft", "gaubenreihe__unten"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--teile_dir", default="/media/oem/scan/rc-park_tmp/viewer/teile_akt.neu")
    ap.add_argument("--formliste"); ap.add_argument("--arbeit", default=FP.ARBEIT_STD); ap.add_argument("--neu", action="store_true")
    a = ap.parse_args()
    fl = a.formliste or sorted(glob.glob(os.path.join(FF_DIR, "*_v2_wolkenverdeckung_festbereich.json")), key=os.path.getmtime)[-1]
    teile = sorted({t for ts, _ in FUNDE.values() for t in ts} | set(GEGEN))
    t0 = time.time()
    arg = ["kaufhaus_grob3", "--teile_dir", a.teile_dir, "--formliste", fl, "--arbeit", a.arbeit, "--teile", ",".join(teile), "--parallel", str(len(teile))]
    erg = FP.main(arg + (["--neu"] if a.neu else []))
    print(f"\nLaufzeit {time.time() - t0:.0f} s, claude-Aufrufe {erg.get('claude_aufrufe')}\n")
    treffer = 0; gezaehlt = {}
    for nm, (ts, rx) in FUNDE.items():
        gef = []
        for t in ts:
            r = erg["teile"].get(t, {})
            for ab in r.get("abweichungen", []) if r.get("status") == "ok" else []:
                if ab.get("sicher") in ("hoch", "mittel") and re.search(rx, ab.get("merkmal", ""), re.I): gef.append((t, ab))
        ok = bool(gef); gezaehlt[nm[0]] = gezaehlt.get(nm[0], 0) or int(ok)
        print(f"[{'JA ' if ok else 'NEIN'}] {nm}")
        for t, ab in gef: print(f"       {t}: {ab['sicher']} | {ab['merkmal']} | Foto: {ab['foto'][:100]} | Modell: {ab['modell'][:100]}")
        if not ok: print("       ungeprueft: " + ", ".join(t for t in ts if erg['teile'].get(t, {}).get('status') != 'ok') if any(erg['teile'].get(t, {}).get('status') != 'ok' for t in ts) else "       (Prüfer meldete nichts Passendes)")
    treffer = sum(g for g in gezaehlt.values()); print(f"\nTrefferquote {treffer} von 7 (Fund 1 = Ost ODER West erkannt)")
    print("Gegenprobe:")
    hoch = 0
    for t in GEGEN:
        r = erg["teile"].get(t, {}); abw = r.get("abweichungen", []) if r.get("status") == "ok" else []
        h = [x for x in abw if x.get("sicher") == "hoch"]; hoch += bool(h)
        print(f"  {t}: {r.get('status')}, " + ("; ".join(f"{x['sicher']}:{x['merkmal']}" for x in abw) or "keine Abweichung"))
    print(f"Fehlalarme hoch: {hoch}")
    sys.exit(0 if (treffer >= 6 and hoch <= 1) else 1)


if __name__ == "__main__":
    main()
