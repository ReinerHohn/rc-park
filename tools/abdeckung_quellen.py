#!/usr/bin/env python3
"""abdeckung_quellen.py - AUTOMATISCH zaehlen, aus welchen Richtungen/Hoehen/Abstaenden jede Quelle das Objekt sieht, und Luecken je Seite melden (Plan 3.7).

Quellen: (a) Fotos mit `seite` in objekt.json, (b) jedes Video-SfM unter video_stufe.ordner/<name>/ mit sparse/<n> und einer Ausrichtung
(<name>/ausrichtung.json oder audit/video_ausrichtung_<name>.json). Kamerapositionen werden mit derselben Transformation wie video_dicht.py in den
Modellrahmen gebracht (Skala*R*X+t, dann SFM-AUSRICHTUNG-nord). Seiten kommen aus objekt.json["seiten_konvention"] ('+x': 'Sued = ...' usw.), nicht aus Handwahl.
  /media/oem/scan/venv-colmap/bin/python -I tools/abdeckung_quellen.py modelle/<objekt>/objekt.json [--dichte-grenze 0.1]
Ausgabe: modelle/<objekt>/audit/abdeckung.json und eine Tabelle. Keine Datei ausser dieser wird geschrieben.
GRENZEN / ANNAHMEN (ehrlich):
 - ANNAHME: Ausreisser = Abstand > 10 x Median der Quelle (Bildposition ausser Kontrolle, z.B. 1,9 Mio. m); werden gezaehlt, aber nicht bewertet.
 - ANNAHME: Seite 'duenn' = Anteil < --dichte-grenze (0,1) der staerksten Seite; 'LUECKE' = 0 Bilder. Die Grenze ist eine Voreinstellung, kein Messwert.
 - Die Seitenzuordnung haengt an der Ausrichtung ans Nordnetz. Bei symmetrischen Objekten kann sie gespiegelt sein (Register AH): Warnung steht im Ergebnis.
 - Zaehlt Kameras, nicht Qualitaet: viele Bilder auf einer Seite heissen nicht, dass das Netz dort stimmt (Register AI: verbogenes Suednetz).
"""
import sys, os, re, json, glob, argparse, collections, numpy as np

def seiten_aus_konvention(obj):
    """{'+x': 'Sued = ...', ...} -> {'+x': 'Sued', ...}; Seiten ohne erkennbares erstes Wort entfallen."""
    out = {}
    for k, v in (obj.get("seiten_konvention") or {}).items():
        m = re.match(r"\s*([A-Za-z]+)", str(v))
        if k in ("+x", "-x", "+y", "-y") and m: out[k] = m.group(1)
    return out

def seite_von(x, y, konv):
    k = ("+x" if x > 0 else "-x") if abs(x) >= abs(y) else ("+y" if y > 0 else "-y")
    return konv.get(k, k)

def zusammenfassen(eintraege, seiten, dichte_grenze):
    """eintraege: [(seite, abstand, hoehe, neigung)] ohne Ausreisser."""
    z = {s: [e for e in eintraege if e[0] == s] for s in seiten}; nmax = max([len(v) for v in z.values()] + [1]); res = {}
    for s, v in z.items():
        a = np.array([[e[1], e[2], e[3]] for e in v]) if v else np.zeros((0, 3))
        status = "LUECKE" if not len(v) else ("duenn" if len(v) < dichte_grenze * nmax else "belegt")
        res[s] = dict(bilder=len(v), status=status,
                      abstand_median_m=round(float(np.median(a[:, 0])), 1) if len(v) else None, abstand_min_m=round(float(a[:, 0].min()), 1) if len(v) else None, abstand_max_m=round(float(a[:, 0].max()), 1) if len(v) else None,
                      hoehe_median_m=round(float(np.median(a[:, 1])), 1) if len(v) else None, hoehe_max_m=round(float(a[:, 1].max()), 1) if len(v) else None,
                      blick_neigung_grad=round(float(np.median(a[:, 2])), 1) if len(v) else None)
    return res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--dichte-grenze", type=float, default=0.1); a = ap.parse_args()
    import pycolmap
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); konv = seiten_aus_konvention(obj); seiten = sorted(set(konv.values()))
    if not seiten: sys.exit("objekt.json: seiten_konvention ohne '+x/-x/+y/-y' - Seiten nicht bestimmbar")
    ergebnis = dict(objekt=obj.get("name"), seiten=konv, quellen={}, warnungen=[])
    # (a) Fotos mit Seitenangabe
    fz = collections.Counter(); fo = obj.get("fotos", {}); it = fo.values() if isinstance(fo, dict) else fo
    for v in it: fz[(v.get("seite") if isinstance(v, dict) else None) or "ohne Seitenangabe"] += 1
    ergebnis["quellen"]["fotos"] = dict(je_seite=dict(fz), gesamt=sum(fz.values()))
    # (b) Video-SfM
    vs = obj.get("video_stufe", {}).get("ordner"); sp = os.path.join(od, "messprotokoll", "SFM-AUSRICHTUNG-nord.json")
    if vs and os.path.isdir(vs) and os.path.exists(sp):
        S = json.load(open(sp))["transformation"]; Rm = pycolmap.Rotation3d(np.array(S["rvec"])).matrix(); tm = np.array(S["t"])
        for d in sorted(glob.glob(os.path.join(vs, "*", "sparse"))):
            name = os.path.basename(os.path.dirname(d)); kand = [os.path.join(vs, name, "ausrichtung.json"), os.path.join(od, "audit", f"video_ausrichtung_{name}.json")]
            ap_ = next((k for k in kand if os.path.exists(k)), None)
            if not ap_: ergebnis["quellen"][name] = dict(hinweis="keine Ausrichtung gefunden (" + ", ".join(os.path.basename(k) for k in kand) + ")"); continue
            ms = sorted(glob.glob(os.path.join(d, "*")), key=lambda p: -len(pycolmap.Reconstruction(p).images) if os.path.isdir(p) else 0)
            if not ms: continue
            rec = pycolmap.Reconstruction(ms[0]); o = json.load(open(ap_)); s, R, t = o["skala_video_zu_nord"], np.array(o["R"]), np.array(o["t"]); roh = []
            for im in rec.images.values():
                c = np.array(im.projection_center()); cm = ((s * (c @ R.T) + t - tm) @ Rm) / S["s"]; z = im.cam_from_world().rotation.matrix().T @ np.array([0, 0, 1.0]); zm = (s * (z @ R.T)) @ Rm
                roh.append((seite_von(cm[0], cm[1], konv), float(np.hypot(cm[0], cm[1])), float(cm[2]), float(np.degrees(np.arctan2(zm[2], np.hypot(zm[0], zm[1]))))))
            med = float(np.median([r[1] for r in roh])) if roh else 0.0; gut = [r for r in roh if r[1] <= 10 * med]
            ergebnis["quellen"][name] = dict(modell=os.path.basename(ms[0]), bilder_gesamt=len(roh), ausreisser=len(roh) - len(gut), ausrichtung=os.path.relpath(ap_, od) if ap_.startswith(od) else ap_, je_seite=zusammenfassen(gut, seiten, a.dichte_grenze))
    else: ergebnis["warnungen"].append("video_stufe.ordner oder messprotokoll/SFM-AUSRICHTUNG-nord.json fehlt: keine Video-Abdeckung")
    ergebnis["warnungen"].append("Seitenzuordnung der Videos haengt an der Ausrichtung ans Nordnetz; bei zwei fast gleichen Seiten (Register AH) kann sie gespiegelt sein - nicht unabhaengig geprueft.")
    out = os.path.join(od, "audit", "abdeckung.json"); os.makedirs(os.path.dirname(out), exist_ok=True); json.dump(ergebnis, open(out, "w"), indent=1, ensure_ascii=False)
    print("Fotos je Seite:", dict(fz))
    for name, q in ergebnis["quellen"].items():
        if "je_seite" not in q or name == "fotos": continue
        print(f"== {name}: {q['bilder_gesamt']} Bilder, {q['ausreisser']} Ausreisser")
        for s in seiten:
            r = q["je_seite"][s]; print(f"  {s:5s} {r['status']:7s} {r['bilder']:4d} Bilder" + (f"  Abstand {r['abstand_median_m']} m  Hoehe {r['hoehe_median_m']} (max {r['hoehe_max_m']}) m  Blick {r['blick_neigung_grad']:+} Grad" if r["bilder"] else ""))
    for w in ergebnis["warnungen"]: print("WARNUNG:", w)
    print("->", out)

if __name__ == "__main__": main()
