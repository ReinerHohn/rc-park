#!/usr/bin/env python3
"""foto_luecken_plan.py <objekt.json> <sparse_modell> [--schritt 1.5] [--min 3] - Welche Turmseite / Hoehe hat zu wenig Ansichten?

Rechnet fuer Zielpunkte auf den vier Wandseiten (Rahmen aus objekt.json, Hoehe 0..Traufe bzw. First), in wie vielen
Fotos der Punkt liegt (vor der Kamera, im Bildrahmen, Blickwinkel <= 70 Grad zur Wandnormalen). Gibt je Seite und
Hoehenband die Anzahl Ansichten aus und eine Liste der Luecken mit Empfehlung, von wo fotografiert werden muss.

Grenzen (ehrlich): Verdeckung durch Nachbargebaeude und Baeume wird NICHT geprueft; es zaehlt nur 'im Bild und vorne'.
Gilt in der Koordinate des SfM-Netzes; dafuer wird die Ausrichtung messprotokoll/SFM-AUSRICHTUNG-<name>.json genutzt.
Ausgabe: JSON neben objekt.json (foto_luecken.json) + Tabelle im Log.
"""
import sys, os, json, math, argparse
import numpy as np
sys_path_tools = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, sys_path_tools)

BAND = [0, 5, 10, 15, 20, 25, 30]

def himmel(vec_en):
    """Himmelsrichtung eines Vektors (E, N) -> 'nord' | 'ost' | 'sued' | 'west'."""
    e, n = vec_en
    if abs(n) >= abs(e): return "nord" if n > 0 else "sued"
    return "ost" if e > 0 else "west"

def seiten_map(rahmen):
    """Modellnormale -> Himmelsrichtung ueber den Gebaeuderahmen (u entlang xhat, v entlang yhat)."""
    xh = np.array(rahmen["xhat_utm"]); yh = np.array(rahmen["yhat_utm"])
    out = {}
    for nu, nv in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        vec = nu * xh + nv * yh
        out[himmel(vec)] = (nu, nv)
    return out

def wand_ziele(rahmen, hoehe, schritt):
    """Punkte auf den 4 Wandseiten (Modell-Rahmen). Liefert [(seite, normale, punkt)]; seite = Himmelsrichtung."""
    u0, u1 = rahmen["u0"], rahmen["u1"]; v0, v1 = rahmen["v0"], rahmen["v1"]
    sm = seiten_map(rahmen)
    punkte = {(0, -1): [(u, v0) for u in np.arange(u0, u1 + 1e-6, schritt)],
              (0, 1): [(u, v1) for u in np.arange(u0, u1 + 1e-6, schritt)],
              (-1, 0): [(u0, v) for v in np.arange(v0, v1 + 1e-6, schritt)],
              (1, 0): [(u1, v) for v in np.arange(v0, v1 + 1e-6, schritt)]}
    out = []
    for seite, n in sm.items():
        for (u, v) in punkte[n]:
            for zz in np.arange(0.5, hoehe, schritt):
                out.append((seite, (n[0], n[1], 0), (u, v, zz)))
    return out

def kameras_json(pfad):
    """Kameras aus kamera_export.py-JSON (ohne pycolmap): gleiche Tupel wie kameras()."""
    import json as _j
    KJ = _j.load(open(pfad)); cams = []
    for b in KJ["bilder"]:
        k = KJ["kameras"][str(b["cam"])]
        Rw = np.asarray(b["R"]); tw = np.asarray(b["t"]); K = np.asarray(k["K"])
        cams.append((b["name"], K @ np.c_[Rw, tw], -Rw.T @ tw, int(k["width"]), int(k["height"])))
    return cams


def kameras(sparse_dir):
    import pycolmap
    rec = pycolmap.Reconstruction(sparse_dir)
    cams = []
    for im in rec.images.values():
        if not im.has_pose: continue
        cam = rec.cameras[im.camera_id]
        Rw = np.asarray(im.cam_from_world().rotation.matrix()); tw = np.asarray(im.cam_from_world().translation)
        K = np.asarray(cam.calibration_matrix())
        P = K @ np.c_[Rw, tw]                      # 3x4 SfM-Koordinaten
        C = -Rw.T @ tw
        cams.append((im.name, P, C, cam.width, cam.height))
    return cams


def sichtbare_ansichten(Pf, Nf, cams, blickwinkel_grad=70.0):
    """Anzahl Fotos je Punkt: Punkt vor der Kamera, im Bildrahmen, Blickwinkel <= 70 Grad zur Wandnormalen.
    Alle Punkte x alle Kameras in einem Schritt (torch auf der GPU, sonst numpy)."""
    Pm = np.stack([c[1] for c in cams]); Cc = np.stack([c[2] for c in cams])
    Wc = np.array([c[3] for c in cams], float); Hc = np.array([c[4] for c in cams], float)
    cos_g = math.cos(math.radians(blickwinkel_grad))
    try:
        import torch
        if not torch.cuda.is_available(): raise ImportError("keine GPU")
        dev = "cuda"; T_ = lambda a: torch.as_tensor(np.asarray(a, np.float64), device=dev)
        Pm_, Cc_, Pf_, Nf_ = T_(Pm), T_(Cc), T_(Pf), T_(Nf)
        X = torch.cat([Pf_, torch.ones(len(Pf_), 1, dtype=torch.float64, device=dev)], 1)   # (M,4)
        x = torch.einsum("kij,mj->kim", Pm_, X)                                              # (K,3,M)
        z = x[:, 2, :]; px = x[:, 0, :] / z; py = x[:, 1, :] / z
        inb = (z > 0) & (px >= 0) & (px < T_(Wc)[:, None]) & (py >= 0) & (py < T_(Hc)[:, None])
        blick = Pf_[None, :, :] - Cc_[:, None, :]; blick = blick / (blick.norm(dim=-1, keepdim=True) + 1e-12)
        dot = -(blick * Nf_[None, :, :]).sum(-1)
        ok = inb & (dot >= cos_g)
        return ok.sum(0).cpu().numpy()
    except ImportError:
        X = np.c_[Pf, np.ones(len(Pf))]
        x = np.einsum("kij,mj->kim", Pm, X); z = x[:, 2, :]; px = x[:, 0, :] / z; py = x[:, 1, :] / z
        inb = (z > 0) & (px >= 0) & (px < Wc[:, None]) & (py >= 0) & (py < Hc[:, None])
        blick = Pf[None] - Cc[:, None]; blick = blick / (np.linalg.norm(blick, axis=-1, keepdims=True) + 1e-12)
        dot = -(blick * Nf[None]).sum(-1)
        return (inb & (dot >= cos_g)).sum(0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("objekt"); ap.add_argument("sparse", nargs="?", default=None); ap.add_argument("--kameras", default=None, help="kamera_export-JSON (GPU-Umgebung, ohne pycolmap)"); ap.add_argument("--schritt", type=float, default=1.5)
    ap.add_argument("--min", type=int, default=3); ap.add_argument("--ausrichtung", default=None)
    a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    rahmen = obj.get("rahmen_wand") or {}
    if not rahmen:
        print("FEHLT: objekt.json rahmen_wand {u0,u1,v0,v1} (Wandextreme im Gebaeuderahmen)"); return 2
    hoehe = float(obj.get("hoehe_m", 25.8))
    # Ausrichtung SfM <- Modell: X_sfm = s R X_mod + t
    aus = a.ausrichtung or os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{obj.get('name','schwab').lower()}.json")
    if not os.path.exists(aus):
        cand = [p for p in __import__('glob').glob(os.path.join(od, "messprotokoll", "SFM-AUSRICHTUNG-*.json"))]
        if not cand: print("FEHLT: Ausrichtung SFM-AUSRICHTUNG-*.json (sfm_lod2_ausrichten.py --schreiben)"); return 2
        aus = cand[0]
    T = json.load(open(aus))["transformation"]
    from scipy.spatial.transform import Rotation as Rot
    R = Rot.from_rotvec(T["rvec"]).as_matrix(); s = float(T["s"]); t = np.array(T["t"])
    cams = kameras_json(a.kameras) if a.kameras else kameras(a.sparse)
    rahmen = dict(rahmen, xhat_utm=obj["rahmen"]["xhat_utm"], yhat_utm=obj["rahmen"]["yhat_utm"])
    ziele = wand_ziele(rahmen, hoehe, a.schritt)
    # Tabelle: seite x band -> Ansichten (max je Ziel, gemittelt ueber Punkte)
    zaehl = {}
    Pf = np.array([s * R @ np.array(p, float) + t for _, _, p in ziele])
    Nf = np.array([R @ np.array(n, float) for _, n, _ in ziele])
    counts = sichtbare_ansichten(Pf, Nf, cams)           # GPU (torch) wenn vorhanden, sonst numpy
    for (seite, n, p), anz in zip(ziele, counts):
        pm = np.array(p, float)
        b = int(pm[2] // 5) * 5
        zaehl.setdefault((seite, b), []).append(int(anz))
    L = []
    print(f"{len(cams)} Kameras; Ziele je Seite/Band (Median Ansichten):")
    print("seite  " + " ".join(f"{b:>3}m" for b in BAND[:-1]))
    luecken = []
    for seite in ["sued", "nord", "ost", "west"]:
        row = []
        for b in BAND[:-1]:
            v = zaehl.get((seite, b), [])
            med = int(np.median(v)) if v else -1
            row.append(med)
            if v and med < a.min:
                mu = (rahmen["u0"] + rahmen["u1"]) / 2; mv = (rahmen["v0"] + rahmen["v1"]) / 2
                nrm = seiten_map(rahmen)[seite]
                wand = {(0, -1): (mu, rahmen["v0"]), (0, 1): (mu, rahmen["v1"]), (-1, 0): (rahmen["u0"], mv), (1, 0): (rahmen["u1"], mv)}[nrm]
                abst = 25.0; hz = b + 2.5
                pos = (round(wand[0] + abst * nrm[0], 1), round(wand[1] + abst * nrm[1], 1), round(hz, 1))
                # Modell -> UTM ueber den Gebaeuderahmen (u entlang xhat, v entlang yhat); unabhaengig von der Ausrichtung
                rf = obj["rahmen"]; c = np.array(rf["mitte_utm"]); xh = np.array(rf["xhat_utm"]); yh = np.array(rf["yhat_utm"])
                E, N = c + pos[0] * xh + pos[1] * yh
                wE, wN = c + wand[0] * xh + wand[1] * yh
                from bilder_holen import utm_zu_wgs84
                lat, lon = utm_zu_wgs84(E, N)
                # Blickrichtung: Kompass vom Standort zur Wandmitte (0 = Nord, 90 = Ost)
                dE, dN = wE - E, wN - N
                peil = (math.degrees(math.atan2(dE, dN)) + 360) % 360
                luecken.append({"seite": seite, "band_m": f"{b}-{b+5}", "median": med, "aufnahmeort_modell_m": pos,
                                "standort_wgs84": [round(lat, 6), round(lon, 6)], "blick_kompass_grad": round(peil),
                                "empfehlung": f"{seite}-Seite, {b}-{b+5} m Hoehe: stehe bei {lat:.6f}, {lon:.6f}, Hoehe {hz:.1f} m, Blick Kompass {peil:.0f} Grad (Wand); mind. {a.min} Fotos. Jetzt {med} Ansichten."})
        print(f"{seite:6s} " + " ".join(f"{v:>4d}" for v in row))
    json.dump({"kameras": len(cams), "luecken": luecken, "min": a.min}, open(os.path.join(od, "foto_luecken.json"), "w"), indent=1, ensure_ascii=False)
    print(f"Luecken (< {a.min} Ansichten): {len(luecken)}")
    for l in luecken: print("  -", l["empfehlung"], f"(jetzt {l['median']})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
