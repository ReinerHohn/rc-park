#!/usr/bin/env python3
"""test_formfamilie_nutzerfunde.py - Beweistest fuer tools/formfamilie_pruefen.py (Regel 3e, Spec modelle/SPEC_FORMFAMILIE_SICHTPRUEFUNG.md).

Die Testfaelle stehen NICHT im Code, sondern in modelle/<objekt>/masstabelle.json: jede Eintrag in `beobachtungen_offen` mit
  - 'nutzer' (klein geschrieben) im Feld `wer`,
  - `formfamilie_test` == true,
  - nicht erledigt (`erledigt` falsch/fehlt und `status` nicht erledigt/geschlossen),
ist ein Fall. Feld `teil` ("typ:name") -> Teil-STL "typ__name" (passt auch auf "typ__name..." als Praefix, z. B. ...__ausschnitt).
Auswertung (NICHT im Pruefer-Prompt, Selbstbezug-Verbot): Fall erkannt = mindestens eine Abweichung des Teils mit Sicherheit hoch/mittel, in deren
merkmal/foto/modell-Text (Umlaute normalisiert) ein Stichwort aus `pruef_stichworte` vorkommt. Neuer Nutzerfund = neuer Eintrag = neuer Testfall.
Gegenprobe-Teile (sollen keine groben Formfamilien-Abweichungen "hoch" melden): --gegenprobe a,b,c.

Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_formfamilie_nutzerfunde.py <objekt> --teile_dir D [--formliste F] [--arbeit A] [--neu] [--gegenprobe ...]
Streng (Hauptergebnis) = Pflichtwort aus `pruef_pflicht` (fehlt: erste zwei `pruef_stichworte`) im Feld `merkmal` einer Abweichung hoch/mittel des Teils; locker = beliebiges Stichwort in merkmal/foto/modell.
Exit 0 = alle Faelle streng erkannt (oder >= --min_quote, Standard 0.75) und hoechstens 1 Fehlalarm "hoch" in der Gegenprobe, sonst 1."""
import sys, os, re, json, glob, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formfamilie_pruefen as FP

R0 = FP.R0
GEGEN_STD = "helm_geschweift__o,helm_geschweift__w,zylinder__dienst_laube_u975_schaft,gaubenreihe__unten,freiform__tor_b2__ausschnitt"


def norm(s):
    s = str(s).lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")): s = s.replace(a, b)
    return s


def faelle_lesen(objekt):
    mt = json.load(open(os.path.join(R0, "modelle", objekt, "masstabelle.json")))
    out = []
    for i, b in enumerate(mt.get("beobachtungen_offen", [])):
        if not isinstance(b, dict) or not b.get("formfamilie_test"): continue
        if "nutzer" not in str(b.get("wer", "")).lower(): continue
        if b.get("erledigt") or str(b.get("status", "")).lower() in ("erledigt", "geschlossen"): continue
        out.append({"nr": i, "teil": str(b.get("teil", "")).replace(":", "__"), "merkmal": b.get("merkmal", ""), "stichworte": [norm(x) for x in b.get("pruef_stichworte", [])],
                    "pflicht": [norm(x) for x in (b.get("pruef_pflicht") or b.get("pruef_stichworte", [])[:2])], "pflicht_aus_feld": bool(b.get("pruef_pflicht"))})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--teile_dir", required=True)
    ap.add_argument("--formliste"); ap.add_argument("--arbeit", default=FP.ARBEIT_STD); ap.add_argument("--neu", action="store_true")
    ap.add_argument("--gegenprobe", default=GEGEN_STD); ap.add_argument("--min_quote", type=float, default=0.75)
    a = ap.parse_args()
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp))
    fdir = os.path.join(FP.ARBEIT_STD, "..", "..", "rc-park_kreis", a.objekt, "fotoform")
    fl = a.formliste or sorted(glob.glob(os.path.join(os.path.normpath(fdir), "*_v2_wolkenverdeckung_festbereich.json")), key=os.path.getmtime)[-1]
    faelle = faelle_lesen(a.objekt)
    alle = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(a.teile_dir, "*.stl")))
    gegen = [g for g in a.gegenprobe.split(",") if g in alle]
    for f in faelle: f["stls"] = [t for t in alle if t == f["teil"] or t.startswith(f["teil"] + "__")]
    teile = sorted({t for f in faelle for t in f["stls"]} | set(gegen))
    print(f"{len(faelle)} Faelle aus masstabelle.json, {len(teile)} Teile", flush=True)
    t0 = time.time()
    erg = FP.main([a.objekt, "--teile_dir", a.teile_dir, "--formliste", fl, "--arbeit", a.arbeit, "--teile", ",".join(teile), "--parallel", str(len(teile))] + (["--neu"] if a.neu else []))
    print(f"\nLaufzeit {time.time() - t0:.0f} s, neue claude-Aufrufe {erg.get('claude_aufrufe')}\n")
    ok_n = ok_l = 0
    for f in faelle:
        gef, gl, ungep = [], [], []
        for t in f["stls"]:
            r = erg["teile"].get(t, {})
            if r.get("status") != "ok": ungep.append(t); continue
            for ab in r.get("abweichungen", []):
                if ab.get("sicher") not in ("hoch", "mittel"): continue
                txt = norm(" ".join(str(ab.get(k, "")) for k in ("merkmal", "foto", "modell")))
                if any(w in txt for w in f["stichworte"]): gl.append((t, ab))
                # streng: Pflichtwort im Feld 'merkmal' selbst (= die Abweichung bezieht sich auf dieses Merkmal, nicht nur ein Nebensatz)
                if any(w in norm(ab.get("merkmal", "")) for w in f["pflicht"]): gef.append((t, ab))
        ok = bool(gef); ok_n += ok; ok_l += bool(gl)
        print(f"[streng {'JA ' if ok else 'NEIN'} | locker {'JA ' if gl else 'NEIN'}] #{f['nr']} {f['teil']}: {f['merkmal'][:90]}  Pflicht{'' if f['pflicht_aus_feld'] else '(Ersatz aus Stichworten)'}: {f['pflicht']}")
        for t, ab in (gef or gl)[:3]: print(f"       {ab['sicher']} | {ab['merkmal']} | Foto: {str(ab['foto'])[:90]} | Modell: {str(ab['modell'])[:90]}")
        if ungep: print("       ungeprueft:", ", ".join(ungep))
        elif not gl: print("       (Pruefer meldete nichts Passendes)")
    print(f"\nTrefferquote streng {ok_n} von {len(faelle)} (Hauptergebnis), locker {ok_l} von {len(faelle)} (Vergleich)")
    print("Gegenprobe:"); hoch = 0
    for t in gegen:
        r = erg["teile"].get(t, {}); abw = r.get("abweichungen", []) if r.get("status") == "ok" else []
        h = [x for x in abw if x.get("sicher") == "hoch"]; hoch += bool(h)
        print(f"  {t}: {r.get('status')}, " + ("; ".join(f"{x['sicher']}:{x['merkmal']}" for x in abw) or "keine Abweichung"))
    print(f"Fehlalarme hoch: {hoch}")
    sys.exit(0 if (faelle and ok_n >= a.min_quote * len(faelle) and hoch <= 1) else 1)


if __name__ == "__main__":
    main()
