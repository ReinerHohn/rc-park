#!/usr/bin/env python3
"""kamera_gueterating.py - AUTOMATISCH bewerten, ob die Kamera eines Fotos (messprotokoll/K-<foto>.json, 'kamera') fuer Messungen/Textur taugt (Plan M5).

Je Foto: RMS der Pick-Residuen in PROZENT der Bildhoehe (Richtwert foto_kalibrieren: < 0,5 %), Plausibilitaet der Lage (Abstand, Hoehe ueber Gelaende), der Brennweite (f/Bildlaenge) und
die Kameraart (Strasse/Luft). Klassen:
  gut          RMS <= --rms-gut-proz (0,5 %) UND plausibel
  grob         RMS <= --rms-max-proz (3,0 %) UND plausibel   (fuer Vorschau/Textur mit Vorsicht, NICHT fuer Detailmasse)
  unbrauchbar  RMS > --rms-max-proz ODER unplausibel (Brennweite unphysikalisch, Abstand/Hoehe unmoeglich) ODER keine geloeste Kamera
Aufruf:  python3 -I tools/kamera_gueterating.py modelle/<objekt>/objekt.json [--rms-gut-proz 0.5] [--rms-max-proz 3.0] [--f-bereich 0.3 20] [--abstand-max-m 500]
Ausgabe: modelle/<objekt>/audit/kamera_gueterating.json (je Foto Klasse, RMS %, Gruende) und Tabelle. Andere Werkzeuge (textur_projektion, foto_mass) koennen die JSON lesen.
ANNAHMEN (alle als Argument, keine Messwerte): 0,5 % = Richtwert aus foto_kalibrieren; 3 % = Grenze, die textur_projektion schon benutzt; f/Bildlaenge 0,3..20 (Weitwinkel bis starkes Tele);
Abstand <= 500 m und Hoehe <= 20 m fuer 'Strassenfoto'; Luftbilder (Hoehe > --hoehe-max-m) gelten fuer Strassen-Messungen/Textur als unbrauchbar, bleiben aber als Art 'luft' kenntlich.
Grenze: RMS misst nur, wie gut die gepickten Anker passen - ein Foto mit wenigen Picks kann ein kleines RMS haben und trotzdem falsch liegen (Freiheitsgrade: Zahl der Picks steht im Bericht).
"""
import sys, os, json, glob, argparse

def bewerten(k, rms_gut, rms_max, fb, abst_max, hoehe_max):
    gruende = []; art = "strasse"
    if not k or "f_px" not in k: return "unbrauchbar", None, "strasse", ["keine geloeste Kamera (Picks fehlen oder Loesung gescheitert)"]
    W, H = (k.get("bild") or [2 * k.get("cx", 0), 2 * k.get("cy", 0)])[:2]; L = max(W, H) or 1; Hb = H or 1
    rms = k.get("rms_px"); proz = 100.0 * rms / Hb if rms is not None else None
    if k.get("hoehe_ueber_gelaende", 0) > hoehe_max: art = "luft"; gruende.append(f"Kamerahoehe {k['hoehe_ueber_gelaende']:.0f} m > {hoehe_max:.0f} m (Luftbild)")
    fr = k["f_px"] / L
    if not (fb[0] <= fr <= fb[1]): gruende.append(f"Brennweite unphysikalisch: f = {k['f_px']:.3g} px = {fr:.3g} x Bildlaenge (erlaubt {fb[0]}..{fb[1]})")
    if k.get("abstand_zur_achse", 0) > abst_max: gruende.append(f"Abstand {k['abstand_zur_achse']:.0f} m > {abst_max:.0f} m")
    if k.get("plausibel_strassenfoto") is False and art != "luft": gruende.append("foto_kalibrieren: nicht plausibel als Strassenfoto")
    if proz is None: gruende.append("kein RMS in der Kamera")
    elif proz > rms_max: gruende.append(f"RMS {proz:.1f} % der Bildhoehe > {rms_max} %")
    if gruende: return "unbrauchbar", proz, art, gruende
    return ("gut" if proz <= rms_gut else "grob"), proz, art, ([] if proz <= rms_gut else [f"RMS {proz:.1f} % > {rms_gut} % (Richtwert)"])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--rms-gut-proz", type=float, default=0.5); ap.add_argument("--rms-max-proz", type=float, default=3.0)
    ap.add_argument("--f-bereich", type=float, nargs=2, default=[0.3, 20.0]); ap.add_argument("--abstand-max-m", type=float, default=500.0); ap.add_argument("--hoehe-max-m", type=float, default=20.0); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od))
    aud = os.path.join(root, obj.get("audit", os.path.join(os.path.dirname(obj["masstabelle"]), "audit"))); os.makedirs(aud, exist_ok=True)
    res = {}; zaehl = {"gut": 0, "grob": 0, "unbrauchbar": 0}
    for kp in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        nr = os.path.basename(kp)[2:-5]; d = json.load(open(kp)); k = d.get("kamera")
        kl, proz, art, gr = bewerten(k, a.rms_gut_proz, a.rms_max_proz, a.f_bereich, a.abstand_max_m, a.hoehe_max_m); zaehl[kl] += 1
        res[nr] = dict(klasse=kl, rms_prozent_bildhoehe=None if proz is None else round(proz, 2), rms_px=(k or {}).get("rms_px"), art=art, picks=len(d.get("punkte", {})) + len(d.get("linien", {})),
                       seite=obj.get("fotos", {}).get(nr, {}).get("seite"), gruende=gr)
    json.dump(dict(parameter=dict(rms_gut_proz=a.rms_gut_proz, rms_max_proz=a.rms_max_proz, f_bereich=a.f_bereich, abstand_max_m=a.abstand_max_m, hoehe_max_m=a.hoehe_max_m), zaehler=zaehl, fotos=res,
                   hinweis="ANNAHMEN siehe Kopf von tools/kamera_gueterating.py; RMS misst nur den Sitz der gepickten Anker"), open(os.path.join(aud, "kamera_gueterating.json"), "w"), indent=1, ensure_ascii=False)
    print(f"Kameraguete: {zaehl}  ->  {aud}/kamera_gueterating.json")
    for nr, r in res.items(): print(f"  {nr}  {r['klasse']:11s} RMS {('%.2f %%' % r['rms_prozent_bildhoehe']) if r['rms_prozent_bildhoehe'] is not None else '   -   '} {r['art']:7s} Picks {r['picks']:2d}  {r['seite'] or ''}  {'; '.join(r['gruende'])[:110]}")

if __name__ == "__main__":
    main()
