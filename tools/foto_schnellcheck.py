#!/usr/bin/env python3
"""foto_schnellcheck.py <objekt.json> <fassaden-ordner> <auftrag.json> <FOTODATEI> [--auftrag NR] [--stl a.stl,...] [--aus bild.jpg]

SOFORT-ANTWORT fuer den Nutzer vor Ort: "passt" oder "passt nicht - und was aendern".
Nutzer 16.11.2026: "ich mache ein Foto, lade es dir hoch und du musst sagen, ja, passt oder passt nicht, weil ich bin dann in der Stadt und kann nicht immer hin und her fahren."
Ablauf (GPU, ~20-40 s):
  1. Foto unter fotos_dir ablegen (neu__<name>.jpg).
  2. Kamera ohne Vorwissen: ALIKED+LightGlue gegen Referenzfotos mit guter Kamera (beste Fotos der Auftraege, je Wand die besten des Fassadenbilds), Treffer ueber das
     Tiefenbild des Modells in 3D, PnP mit freier Brennweite (wie kamera_verfeinern.py). Zu wenige Treffer = "nicht zuordenbar" (zu weit weg, verdeckt, anderes Gebaeude).
  3. Je Auftrag aus <auftrag.json> (foto_auftrag.py): Anteil des Zielbereichs im Bild, Aufloesung am Ziel (cm je Pixel) gegen Soll, Blickwinkel zur Wand, Schaerfe im Ziel,
     Zahl der wiedererkannten Punkte im Zielbereich (0 = wahrscheinlich verdeckt), Seitenabstand zu schon angenommenen Fotos desselben Auftrags (Parallaxe).
  4. Urteil je Auftrag: PASST / PASST NICHT mit einem Satz, was zu aendern ist. Bild mit eingezeichnetem Zielbereich (gruen/rot) als --aus.
  5. Angenommene Fotos stehen in <audit>/fotoauftrag_eingang.json (Standort, Auftrag) und bekommen eine K-Datei - sie sind danach normale Messfotos.
Schwellen: Ziel zu >= 80 % im Bild, Aufloesung <= 1,3 x Soll, Blickwinkel <= 65 Grad, >= 8 wiedererkannte Punkte im Ziel (bei bisher ungesehenen Waenden entfaellt das),
Seitenabstand >= 1 m zum naechsten angenommenen Foto. Alles Richtwerte vom 16.11.2026, an keinem echten Feldeinsatz geprueft.
"""
import sys, os, json, glob, argparse, shutil, time, numpy as np, cv2, torch, trimesh
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_kern as rk


def main():
    from lightglue import LightGlue, ALIKED
    from lightglue.utils import load_image, rbd
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ordner"); ap.add_argument("auftrag"); ap.add_argument("foto"); ap.add_argument("--auftrag-nr", type=int); ap.add_argument("--stl"); ap.add_argument("--aus"); a = ap.parse_args(); t0 = time.time()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"]); mp = os.path.join(od, "messprotokoll"); au = os.path.join(root, obj.get("audit", os.path.join(od, "audit")))
    FA = json.load(open(os.path.join(a.ordner, "fassaden.json")))["fassaden"]; AUF = json.load(open(a.auftrag))["auftraege"]
    name = "neu__" + os.path.splitext(os.path.basename(a.foto))[0]; ziel = os.path.join(fd, name + ".jpg")
    if os.path.abspath(a.foto) != ziel: bild0 = cv2.imread(a.foto); cv2.imwrite(ziel, bild0, [cv2.IMWRITE_JPEG_QUALITY, 95])
    bild = cv2.imread(ziel); H, W = bild.shape[:2]
    def kam(n):
        p = os.path.join(mp, "K-" + n + ".json")
        if not os.path.exists(p): return None
        k = json.load(open(p)).get("kamera"); return k if isinstance(k, dict) and "rvec" in k and "cx" in k else None
    def pfad(n): g = glob.glob(os.path.join(fd, n + ".*")); return g[0] if g else None
    refs = [e["bestes_foto"] for e in AUF if e.get("bestes_foto")]
    for F in FA:
        if F.get("flaeche_m2", 0) >= 40: refs += sorted(F.get("fotos", {}), key=lambda k_: -F["fotos"][k_].get("zellen", 0))[:3]
    refs = [n for n in dict.fromkeys(refs) if kam(n) and pfad(n) and n != name]
    ms = [trimesh.load(q_) for q_ in ([os.path.join(root, obj["stl"])] + (a.stl.split(",") if a.stl else []))]; mm = trimesh.util.concatenate(ms) if len(ms) > 1 else ms[0]; mm.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0)
    dev = "cuda"; ex = ALIKED(max_num_keypoints=4096).eval().to(dev); mt = LightGlue(features="aliked").eval().to(dev)
    def merk(p): im = load_image(p); h, w = im.shape[1:]; return ex.extract(im.to(dev), resize=int(max(h, w) * min(1.0, 1600.0 / max(h, w))))
    fA = merk(ziel); P2, P3 = [], []
    for n in refs:
        k = kam(n); fB = merk(pfad(n))
        with torch.no_grad(): m = rbd(mt({"image0": fA, "image1": fB}))["matches"].cpu().numpy()
        if len(m) < 25: continue
        xa = rbd(fA)["keypoints"].cpu().numpy()[m[:, 0]]; xb = rbd(fB)["keypoints"].cpu().numpy()[m[:, 1]]; R = cv2.Rodrigues(np.array(k["rvec"]))[0]; C = -R.T @ np.array(k["t"])
        D = np.stack([(xb[:, 0] - k["cx"]) / k["f_px"], (xb[:, 1] - k["cy"]) / k["f_px"], np.ones(len(xb))], 1) @ R; hb, wb = int(round(2 * k["cy"])), int(round(2 * k["cx"])); sk = min(1.0, 1800.0 / max(hb, wb)); Wr, Hr = int(wb * sk), int(hb * sk)
        tiefe, fid = [np.asarray(v_) for v_ in rk.dreiecke_rastern(mm, R, np.array(k["t"]), k["f_px"] * sk, k["cx"] * sk, k["cy"] * sk, Wr, Hr)[:2]]
        ui = np.clip((xb[:, 0] * sk).astype(int), 0, Wr - 1); vi = np.clip((xb[:, 1] * sk).astype(int), 0, Hr - 1); tf = tiefe[vi, ui].astype(np.float64); tr = fid[vi, ui] >= 0
        for du, dv in ((-2, 0), (2, 0), (0, -2), (0, 2)): tr &= np.abs(tiefe[np.clip(vi + dv, 0, Hr - 1), np.clip(ui + du, 0, Wr - 1)] - tf) < 0.15
        P2.append(xa[tr]); P3.append(C + tf[tr, None] * D[tr])
    erg = dict(foto=name, datei=ziel, zeit=time.strftime("%Y-%m-%d %H:%M"), urteile=[])
    if not P2 or sum(len(p) for p in P2) < 40:
        erg["kamera"] = None; erg["gesamt"] = "NICHT ZUORDENBAR: Im Foto wurden zu wenige Stellen des Gebaeudes wiedererkannt (zu weit weg, stark verdeckt, Gegenlicht oder anderes Gebaeude). Naeher heran oder mehr vom Turm ins Bild nehmen."
        print(erg["gesamt"]); json.dump(erg, open(os.path.join(au, "foto_schnellcheck_letztes.json"), "w"), indent=1, ensure_ascii=False); return 3
    P2 = np.vstack(P2).astype(np.float64); P3 = np.vstack(P3).astype(np.float64); cx, cy = W / 2, H / 2; best = None
    for f in np.geomspace(0.4 * max(W, H), 12 * max(W, H), 30):
        ok, r, t, inl = cv2.solvePnPRansac(P3, P2, np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]]), None, reprojectionError=max(4.0, 0.004 * max(W, H)), iterationsCount=300, flags=cv2.SOLVEPNP_EPNP)
        if ok and inl is not None and (best is None or len(inl) > len(best[3])): best = (f, r, t, inl.ravel())
    if best is None or len(best[3]) < 30:
        erg["kamera"] = None; erg["gesamt"] = "NICHT ZUORDENBAR: wiedererkannte Stellen ergeben keine eindeutige Kameralage. Bitte ein Foto mit mehr vom Gebaeude."
        print(erg["gesamt"]); json.dump(erg, open(os.path.join(au, "foto_schnellcheck_letztes.json"), "w"), indent=1, ensure_ascii=False); return 3
    f, r, t, inl = best
    def res(p): pr, _ = cv2.projectPoints(P3[inl], p[:3], p[3:6], np.array([[p[6], 0, cx], [0, p[6], cy], [0, 0, 1.0]]), None); return (pr.reshape(-1, 2) - P2[inl]).ravel()
    p = least_squares(res, np.r_[r.ravel(), t.ravel(), f], loss="soft_l1", f_scale=3.0).x; R = cv2.Rodrigues(p[:3])[0]; tt = p[3:6]; C = -R.T @ tt; fpx = float(p[6]); err = float(np.median(np.sqrt((res(p) ** 2).reshape(-1, 2).sum(1))))
    erg["kamera"] = dict(rvec=p[:3].tolist(), t=tt.tolist(), f_px=fpx, cx=cx, cy=cy, k1=0.0, standort=C.tolist(), quelle=f"foto_schnellcheck.py: {len(inl)} Inlier, Rest {err:.1f} px"); erg["inlier"] = int(len(inl))
    ep = os.path.join(au, "fotoauftrag_eingang.json"); EIN = json.load(open(ep)) if os.path.exists(ep) else []; inl2 = P2[inl]; mal = bild.copy(); st = max(4, int(max(H, W) / 300))
    for e in AUF:
        if a.auftrag_nr and e["nr"] != a.auftrag_nr: continue
        F = FA[e["wand"]]; o = np.array(F["o"]); d = np.array(F["d"]); nv = np.array([F["n"][0], F["n"][1], 0.0]); gu = np.linspace(e["u"][0], e["u"][1], 12); gz = np.linspace(e["z"][0], e["z"][1], 12); G = np.array([[o[0] + u_ * d[0], o[1] + u_ * d[1], z_] for u_ in gu for z_ in gz])
        pc = G @ R.T + tt; px = np.c_[fpx * pc[:, 0] / pc[:, 2] + cx, fpx * pc[:, 1] / pc[:, 2] + cy]; drin = (pc[:, 2] > 0.5) & (px[:, 0] >= 0) & (px[:, 0] < W) & (px[:, 1] >= 0) & (px[:, 1] < H); anteil = float(drin.mean())
        if anteil < 0.15: continue
        Pm = G.mean(0); v = C - Pm; dist = float(np.linalg.norm(v)); cw = float(v @ nv / dist); winkel = float(np.degrees(np.arccos(np.clip(cw, -1, 1)))); mpp = dist / (fpx * max(cw, 0.05))
        if cw < 0.17: continue                                             # Wand abgewandt oder flacher als 80 Grad gesehen: nicht Gegenstand dieses Fotos
        x0, y0 = px[drin].min(0); x1, y1 = px[drin].max(0); imz = int(((inl2[:, 0] >= x0) & (inl2[:, 0] <= x1) & (inl2[:, 1] >= y0) & (inl2[:, 1] <= y1)).sum())
        cr = cv2.cvtColor(bild[int(max(y0, 0)):int(min(y1, H)), int(max(x0, 0)):int(min(x1, W))], cv2.COLOR_BGR2GRAY); s_ = min(1.0, 800.0 / max(cr.shape + (1,))); schaerfe = float(cv2.Laplacian(cv2.resize(cr, None, fx=s_, fy=s_), cv2.CV_64F).var()) if cr.size > 400 else 0.0
        fr = [q for q in EIN if q["auftrag"] == e["nr"] and q.get("passt")]; seit = min([float(np.linalg.norm(np.array(q["standort"]) - C)) for q in fr], default=None); gruende = []
        if anteil < 0.8: gruende.append(f"Nur {anteil * 100:.0f} % des Zielbereichs sind im Bild - weiter zurueck oder weniger Zoom, Ziel in die Bildmitte.")
        if mpp > 1.3 * e["soll_mpp"]: gruende.append(f"Zu grob: {mpp * 100:.1f} cm je Pixel, gebraucht {e['soll_mpp'] * 100:.1f}. " + (f"{mpp / e['soll_mpp']:.1f}-fach zoomen" if mpp / e["soll_mpp"] <= 5 else f"das waere {mpp / e['soll_mpp']:.0f}-facher Zoom - mit dem Handy kaum moeglich: Tele-Kamera oder ein Standort etwa {dist * e['soll_mpp'] / mpp:.0f} m vor der Wand") + ".")
        if 0 < cw and winkel > 65: gruende.append(f"Zu schraeg ({winkel:.0f} Grad zur Wand) - weiter vor die Wand stellen.")
        if e.get("ist_mpp") is not None and imz < 8: gruende.append(f"Im Zielbereich wurde fast nichts wiedererkannt ({imz} Punkte) - wahrscheinlich verdeckt (Baum, Haus, Fahrzeug) oder unscharf.")
        if schaerfe < 25: gruende.append("Zielbereich wirkt unscharf oder strukturlos - ruhiger halten, auf die Wand scharfstellen.")
        if seit is not None and seit < 1.0: gruende.append(f"Fast derselbe Standort wie ein schon angenommenes Foto ({seit:.1f} m) - 1-3 m zur Seite gehen.")
        passt = not gruende; u_ = dict(auftrag=e["nr"], titel=e["titel"], passt=passt, anteil=round(anteil, 2), mpp_cm=round(mpp * 100, 2), soll_cm=round(e["soll_mpp"] * 100, 2), winkel=round(winkel), punkte_im_ziel=imz, schaerfe=round(schaerfe), abstand_m=round(dist), seitenabstand_m=None if seit is None else round(seit, 1), gruende=gruende)
        erg["urteile"].append(u_); farbe = (60, 190, 60) if passt else (40, 40, 230); hull = cv2.convexHull(px[drin].astype(np.float32)).astype(np.int32); cv2.polylines(mal, [hull], True, farbe, st); cv2.putText(mal, f"{e['nr']} {'PASST' if passt else 'NEIN'}", (int(x0) + 8, int(y0) + 14 * st), 0, st / 2.5, farbe, st)
        if passt or a.auftrag_nr: EIN.append(dict(foto=name, auftrag=e["nr"], passt=passt, standort=C.tolist(), mpp_cm=u_["mpp_cm"], zeit=erg["zeit"]))
    json.dump(EIN, open(ep, "w"), indent=1, ensure_ascii=False); json.dump(dict(foto=name, seite="unbekannt", punkte={}, linien={}, kamera=erg["kamera"]), open(os.path.join(mp, "K-" + name + ".json"), "w"), indent=1)
    gut = [u_ for u_ in erg["urteile"] if u_["passt"]]; erg["gesamt"] = ("PASST fuer Auftrag " + ", ".join(str(u_["auftrag"]) for u_ in gut)) if gut else ("PASST NICHT" if erg["urteile"] else "Kein Auftragsbereich im Bild - das Foto zeigt eine Stelle, fuer die nichts offen ist.")
    if a.aus: s_ = 1400.0 / max(H, W); cv2.imwrite(a.aus, cv2.resize(mal, None, fx=min(s_, 1.0), fy=min(s_, 1.0), interpolation=cv2.INTER_AREA))
    json.dump(erg, open(os.path.join(au, "foto_schnellcheck_letztes.json"), "w"), indent=1, ensure_ascii=False)
    print(f"{name}: {len(inl)} wiedererkannte Punkte, Rest {err:.1f} px, Standort {np.round(C, 1).tolist()}, f {fpx:.0f} px, {time.time() - t0:.0f} s -> {erg['gesamt']}")
    for u_ in erg["urteile"]:
        print(f"  Auftrag {u_['auftrag']} ({u_['titel'][:40]}): {'PASST' if u_['passt'] else 'PASST NICHT'} | {u_['anteil'] * 100:.0f} % im Bild, {u_['mpp_cm']} cm/px (Soll {u_['soll_cm']}), {u_['winkel']} Grad, {u_['punkte_im_ziel']} Punkte im Ziel")
        for g in u_["gruende"]: print("     -", g)
    return 0 if gut else 1


if __name__ == "__main__":
    sys.exit(main())
