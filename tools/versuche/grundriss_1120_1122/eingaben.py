"""Eingaben-Diff + Kamera-Vergleich 1120 gegen 1122 (nur lesen)."""
import os, sys, json, re, collections
import numpy as np
import pycolmap
D = "/media/oem/scan/rc-park_daten"; M = "/home/oem/git/rc-park/modelle"; OUT = os.path.dirname(os.path.abspath(__file__))

def gruppe(n):
    if n.startswith("eigen__vf_") or n.startswith("eigen__IMG_") or n.startswith("eigen__"):
        if "__vf_" in n: return "eigen_video"
        if "IMG_2026" in n: return "eigen_IMG_2026"
        return "eigen_sonst"
    if n.startswith("video_frames_"): return "video:" + n.split("__")[0][len("video_frames_"):]
    if n.startswith("netz_"): return n.split("__")[0]
    return n.split("__")[0]

def stamm(n): return os.path.splitext(n)[0]

erg = {}
fotos = {o: sorted(os.listdir(f"{D}/{o}/fotos")) for o in ("schwabentor-1120", "schwabentor-1122")}
rec = {o: pycolmap.Reconstruction(f"{D}/{o}/pipe/sfm/sparse/0") for o in fotos}
reg = {o: {im.name: im for im in rec[o].images.values() if im.has_pose} for o in fotos}
seiten = json.load(open(f"{D}/schwabentor-1122/pipe/sfm/seiten.json")); fremd = set(seiten["fremd"])
gem = seiten["gemeinschaft"]
sm = json.load(open(f"{D}/schwabentor-1122/pipe/sfm/seiten_modelle.json"))
teil_von = {}
for e in sm["teile"]:
    if e.get("modell") and os.path.isdir(e["modell"]):
        r = pycolmap.Reconstruction(e["modell"])
        for im in r.images.values():
            if im.has_pose: teil_von[im.name] = e["teil"]
for o in fotos:
    F = set(fotos[o]); R = set(reg[o]); c = collections.Counter(gruppe(n) for n in F); cr = collections.Counter(gruppe(n) for n in R)
    erg[o] = dict(fotos=len(F), registriert=len(R), je_gruppe={g: [c[g], cr.get(g, 0)] for g in sorted(c)})
F0, F1 = set(fotos["schwabentor-1120"]), set(fotos["schwabentor-1122"])
erg["nur_1120_fotos"] = collections.Counter(gruppe(n) for n in F0 - F1); erg["nur_1122_fotos"] = collections.Counter(gruppe(n) for n in F1 - F0)
R0, R1 = set(reg["schwabentor-1120"]), set(reg["schwabentor-1122"])
erg["reg_beide"] = len(R0 & R1); erg["reg_nur_1120"] = collections.Counter(gruppe(n) for n in R0 - R1); erg["reg_nur_1122"] = collections.Counter(gruppe(n) for n in R1 - R0)
# Warum fehlen 1120-registrierte in 1122: fremd / Teil nicht vereint / nicht registriert
grund = collections.Counter()
for n in R0 - R1:
    if n not in F1: grund["foto_fehlt_1122"] += 1
    elif n in fremd: grund["fremd"] += 1
    elif n in teil_von: grund[f"in_teil{teil_von[n]}_nicht_vereint"] += 1
    elif n in gem: grund["seite_ohne_modell_oder_unregistriert"] += 1
    else: grund["ohne_gemeinschaft"] += 1
erg["fehlgrund_1120reg_in_1122"] = grund
# Kameras / Intrinsics
for o in fotos:
    r = rec[o]; cams = r.cameras; mods = collections.Counter(c.model.name for c in cams.values())
    fs = []; ks = []
    for im in reg[o].values():
        c = cams[im.camera_id]; p = np.array(c.params); f = p[0] / max(c.width, c.height); fs.append(f)
        ks.append(p[3] if len(p) > 3 else 0.0)
    fs = np.array(fs); ks = np.array(ks)
    erg[o]["kameras"] = dict(anzahl=len(cams), modelle=dict(mods), f_rel_median=round(float(np.median(fs)), 3), f_rel_p5_p95=[round(float(np.percentile(fs, 5)), 3), round(float(np.percentile(fs, 95)), 3)],
                             f_rel_ueber_3=int((fs > 3).sum()), k1_betrag_ueber_0_5=int((np.abs(ks) > 0.5).sum()))
json.dump(erg, open(f"{OUT}/eingaben.json", "w"), indent=1, ensure_ascii=False, default=dict)
print(json.dumps(erg, indent=1, ensure_ascii=False, default=dict)[:6000])
# Lagen im Objektrahmen fuer Kamera-Vergleich sichern
st = {}
for o in fotos:
    a = json.load(open(f"{M}/{o}/messprotokoll/SFM-AUSRICHTUNG-{o}.json")); st[o] = {k: v["standort"] for k, v in a["kameras"].items() if v.get("standort")}
np.save(f"{OUT}/teil_von.npy", teil_von, allow_pickle=True)
json.dump(dict(st=st, teil=teil_von, sfm={o: {n: list(map(float, im.projection_center())) for n, im in reg[o].items()} for o in fotos}), open(f"{OUT}/lagen.json", "w"))
