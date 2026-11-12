#!/usr/bin/env python3
"""teil_ansichten.py - GUTE ANSICHTEN JE BAUTEIL und fehlende Richtungen (Azimut/Hoehe) - Datenluecken-Messung fuer die Online-Foto-Suche.

Je Bauteil-STL (BAUTEILE_AUS-Export, mm, gleicher Rahmen wie das Gesamt-STL * stl_massstab/1000) werden Oberflaechenpunkte mit Normalen
gezogen. Je Kamera (kam*.json: Rn,tn,f,cx,cy,W,H): Punkt im Bild, Einfallswinkel < 60 Grad (Nutzer 10.11.), Tiefentest gegen das
GESAMT-Modell (render_kern.dreiecke_rastern, GPU, 1/4 Aufloesung). Eine Kamera ist "gute Ansicht" des Teils, wenn sie >= 25 % der Punkte
gut sieht (ANNAHME wie foto_luecken MIN_FLECK_SICHT). Punkte mit < 3 guten Kameras = Luecke; deren Normalen-Azimut (Kompass) und Hoehe
zeigen, AUS WELCHER Richtung das Foto fehlt (Standort = Normalenrichtung).
Aufruf: venv-seg python -I tools/teil_ansichten.py <objekt> --teile_dir D --daten DIR --kameras a.json,b.json [--aus out.json] [--teile name1,name2]
Generisch (nur objekt.json: stl, stl_massstab, rahmen/georef optional)."""
import sys, os, json, glob, argparse, math
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_kern as RK
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EINFALL = 60.0; MIN_ANTEIL = 0.25; GUT_N = 3; SKALE = 0.25
TOL = (0.15, 0.01)   # ANNAHME: Tiefentoleranz 0,15 m + 1 % (Teile liegen auf dem Gesamtmodell)


def kameras(pfade):
    cams, namen = [], set()
    for p in pfade:
        for n, v in json.load(open(p)).items():
            if not isinstance(v, dict) or "Rn" not in v or n in namen: continue
            namen.add(n); R = np.array(v["Rn"], float); t = np.array(v["tn"], float)
            cams.append(dict(name=n, R=R, t=t, C=-R.T @ t, f=float(v["f"]), cx=float(v["cx"]), cy=float(v["cy"]), W=int(v["W"]), H=int(v["H"]), quelle=os.path.basename(p)))
    keep = []
    for c in cams:   # fast gleiche Pose = eine Ansicht
        z = c["R"][2]
        if any(np.linalg.norm(c["C"] - k["C"]) < 0.25 and math.degrees(math.acos(np.clip(z @ k["R"][2], -1, 1))) < 2 for k in keep): continue
        keep.append(c)
    return keep


def kompass(az_modell_deg, xhat):
    # Modellvektor (sin az, cos az) -> UTM -> Kompass (0 = Nord, 90 = Ost); yhat = (-xhat_y, xhat_x)
    dx, dy = math.sin(math.radians(az_modell_deg)), math.cos(math.radians(az_modell_deg))
    E = dx * xhat[0] + dy * (-xhat[1]); N = dx * xhat[1] + dy * xhat[0]
    return (math.degrees(math.atan2(E, N)) + 360) % 360


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--teile_dir", required=True); ap.add_argument("--kameras", required=True)
    ap.add_argument("--aus"); ap.add_argument("--teile"); ap.add_argument("--georef"); ap.add_argument("--n", type=int, default=4000)
    a = ap.parse_args()
    import gpu_slot; gpu_slot.belegen("teil_ansichten")
    import torch
    obj = json.load(open(os.path.join(R0, "modelle", a.objekt, "objekt.json"))); sk = obj.get("stl_massstab", 87) / 1000.0
    ges = trimesh.load(os.path.join(R0, obj["stl"]), force="mesh"); ges.apply_scale(sk)
    zg = float(ges.bounds[0, 2])
    xhat = (0.9992, 0.0411)
    if a.georef and os.path.exists(a.georef): xhat = json.load(open(a.georef))["xhat_utm"]
    wahl = set(a.teile.split(",")) if a.teile else None
    teile = {}
    for p in sorted(glob.glob(os.path.join(a.teile_dir, "*.stl"))):
        n = os.path.basename(p)[:-4]
        if wahl and n not in wahl: continue
        m = trimesh.load(p, force="mesh")
        if not isinstance(m, trimesh.Trimesh) or len(m.faces) == 0: continue
        m.apply_scale(sk); P, fi = m.sample(a.n, return_index=True); teile[n] = (P, m.face_normals[fi], m)
    cams = kameras(a.kameras.split(","))
    print(f"{len(cams)} Kameras (dedupliziert), {len(teile)} Teile", flush=True)
    namen = list(teile); alleP = np.vstack([teile[n][0] for n in namen]); alleN = np.vstack([teile[n][1] for n in namen])
    off = np.cumsum([0] + [len(teile[n][0]) for n in namen])
    zaehl = np.zeros(len(alleP), np.int32); sicht = np.zeros((len(cams), len(alleP)), bool)
    Pt = torch.as_tensor(alleP, dtype=torch.float64, device="cuda"); Nt = torch.as_tensor(alleN, dtype=torch.float64, device="cuda")
    for ci, c in enumerate(cams):
        s = SKALE; W, H = int(c["W"] * s), int(c["H"] * s)
        d, fid, pos = RK.dreiecke_rastern(ges, c["R"], c["t"], c["f"] * s, c["cx"] * s, c["cy"] * s, W, H)
        D = torch.as_tensor(np.asarray(d), device="cuda", dtype=torch.float64)
        Rg = torch.as_tensor(c["R"], device="cuda"); tg = torch.as_tensor(c["t"], device="cuda")
        X = Pt @ Rg.T + tg; z = X[:, 2]; u = c["f"] * s * X[:, 0] / z.clamp(min=1e-6) + c["cx"] * s; v = c["f"] * s * X[:, 1] / z.clamp(min=1e-6) + c["cy"] * s
        ok = (z > 1) & (u >= 1) & (u < W - 1) & (v >= 1) & (v < H - 1)
        ui = u.clamp(0, W - 1).long(); vi = v.clamp(0, H - 1).long(); dd = D[vi, ui]
        vis = ok & (z <= dd + TOL[0] + TOL[1] * z)
        Cg = torch.as_tensor(c["C"], device="cuda"); r = Cg - Pt; r = r / r.norm(dim=1, keepdim=True)
        cosb = (Nt * r).sum(1); gut = vis & (cosb > math.cos(math.radians(EINFALL)))
        sicht[ci] = gut.cpu().numpy()
        if ci % 100 == 0: print(f"  Kamera {ci}/{len(cams)}", flush=True)
    C = np.array([c["C"] for c in cams]); out = {}
    for k, n in enumerate(namen):
        sl = slice(off[k], off[k + 1]); S = sicht[:, sl]; Pk, Nk, m = teile[n]
        anteil = S.mean(1); gute = np.nonzero(anteil >= MIN_ANTEIL)[0]; cnt = S.sum(0)
        zen = Pk.mean(0); vec = C[gute] - zen if len(gute) else np.zeros((0, 3))
        az = (np.degrees(np.arctan2(vec[:, 0], vec[:, 1])) + 360) % 360 if len(gute) else np.zeros(0)
        el = np.degrees(np.arctan2(vec[:, 2], np.hypot(vec[:, 0], vec[:, 1]))) if len(gute) else np.zeros(0)
        luecke = cnt < GUT_N
        # Normalen-Azimut/Hoehe der Luecken-Punkte: aus dieser Richtung muss das Foto kommen
        naz = (np.degrees(np.arctan2(Nk[:, 0], Nk[:, 1])) + 360) % 360; nel = np.degrees(np.arcsin(np.clip(Nk[:, 2], -1, 1)))
        sek = {}
        for i in np.nonzero(luecke)[0]:
            kz = int(naz[i] // 45) * 45; kh = "Dach/oben (>45)" if nel[i] > 45 else ("schraeg oben" if nel[i] > 10 else ("unten/unter" if nel[i] < -10 else "waagerecht"))
            sek[f"Modellaz {kz}-{kz+45} / {kh}"] = sek.get(f"Modellaz {kz}-{kz+45} / {kh}", 0) + 1
        sek = {k2: round(v / len(Pk), 3) for k2, v in sorted(sek.items(), key=lambda kv: -kv[1])[:6]}
        kmp = {}
        for k2 in sek:
            a0 = int(k2.split()[1].split("-")[0]); kmp[k2] = round(kompass(a0 + 22.5, xhat))
        out[n] = dict(gute_ansichten=int(len(gute)), anteil_punkte_unter_3_kameras=round(float(luecke.mean()), 3), anteil_ohne_kamera=round(float((cnt == 0).mean()), 3),
                      kamera_az_modell_hist_45grad=np.bincount((az // 45).astype(int) % 8, minlength=8).tolist(), kamera_hoehenwinkel_median=(round(float(np.median(el)), 1) if len(el) else None),
                      hoehe_teil_m=[round(float(Pk[:, 2].min() - zg), 1), round(float(Pk[:, 2].max() - zg), 1)], luecken_richtungen=sek, luecken_kompass_mitte=kmp,
                      beste_kameras=[cams[i]["name"] for i in gute[np.argsort(-anteil[gute])][:5]])
    if a.aus:
        json.dump(dict(objekt=a.objekt, n_kameras=len(cams), kriterien=f"Einfall<{EINFALL}, >= {MIN_ANTEIL} der Punkte gut = gute Ansicht; Luecke = Punkt mit < {GUT_N} Kameras", teile=out), open(a.aus, "w"), indent=1, ensure_ascii=False)
    for n, v in out.items(): print(n, v["gute_ansichten"], v["anteil_punkte_unter_3_kameras"], v["luecken_richtungen"])


if __name__ == "__main__":
    main()
