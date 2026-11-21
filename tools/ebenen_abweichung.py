#!/usr/bin/env python3
"""ebenen_abweichung.py - ABWEICHUNG Modell gegen Bauplan JE EBENE, mit Ort (21.11.2026, Kettenstufe 'bauplan', Schritt 3 der Schleife).

Leitbild Nutzer 21.11.: "du musst mich ersetzen durch eine automatische Bauplanabweichung, Fotokantenabweichung ... und dort die Abweichungen mit diesen Bauplaenen abgleichen."
Eingang: <daten>/ebenen/ebenen.json (tools/ebenen_bauplan.py: dichte triangulierte Fotokanten je Wand-/Sweep-Ebene) + Modell-STL (objekt.json).
Je Ebene werden die Fotokantenpunkte (u, z, Tiefe w) gegen das Modell gestellt:
  FORM FEHLT    Fotokante liegt > --tol (0,15 m) neben jeder Modellflaeche: dort steht in Wirklichkeit etwas, das im Modell fehlt oder an anderer Tiefe/Lage sitzt.
  DETAIL FEHLT  Fotokante liegt auf der Modellflaeche, aber keine Modellkante in --tol: Flaeche stimmt, Gliederung fehlt (Fenster, Fuge, Gesims, Ziffer).
  ERFUNDEN      Modellkante (Knick > 30 Grad) ohne Fotokante in --tol, obwohl Fotos dort Kanten sehen (naechste Fotokante < 1 m): Modell behauptet eine Kante, die kein Foto zeigt.
Die Punkte werden auf einem (u, z)-Raster (--zelle 0,25 m) zu Flecken zusammengefasst -> ARBEITSLISTE je Ebene, groesste zuerst (Kasten u/z, Punktzahl, mittlere Tiefe gegen die Ebene).
Ausgabe: audit/ebenen_abweichung.json (+ Verlauf .jsonl mit git-Stand) und je Ebene audit/abweichung_<id>.jpg
  (gruen = Fotokante trifft Modellkante, gelb = Detail fehlt, rot = Form fehlt, blau = erfundene Modellkante; Kaesten = die groessten Flecken).
Aufruf: ebenen_abweichung.py <objekt.json> <ebenen-ordner> [--stl X] [--tol 0.15]     rc 0 (Bericht, kein Tor).
Grenzen: 'Detail fehlt' zaehlt auf Bruchstein jede Fuge (viel Gelb ist dort normal - Rangfolge nach ROT zuerst). Ebenen ohne Kantenpunkte fehlen im Bericht (Fotoluecke, kein 'passt').
"""
import sys, os, json, argparse, time, subprocess, numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER); sys.path.insert(0, HIER)


def flecken(u, z, w, zone, zelle, min_p):
    from scipy import ndimage as ndi
    if not len(u): return []
    nu = max(1, int(np.ceil((zone[1] - zone[0]) / zelle))); nz = max(1, int(np.ceil((zone[3] - zone[2]) / zelle)))
    iu = np.clip(((u - zone[0]) / zelle).astype(int), 0, nu - 1); iz = np.clip(((zone[3] - z) / zelle).astype(int), 0, nz - 1); H = np.zeros((nz, nu), int); np.add.at(H, (iz, iu), 1)
    L, n = ndi.label(H >= min_p, structure=np.ones((3, 3))); lab = L[iz, iu]; out = []
    for k in range(1, n + 1):
        m = lab == k
        if m.sum() < 4 * min_p: continue
        out.append(dict(u0=round(float(u[m].min()), 2), u1=round(float(u[m].max()), 2), z0=round(float(z[m].min()), 2), z1=round(float(z[m].max()), 2), punkte=int(m.sum()), tiefe=round(float(np.median(w[m])), 2)))
    return sorted(out, key=lambda e: -e["punkte"])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ebenen"); ap.add_argument("--stl"); ap.add_argument("--tol", type=float, default=0.15); ap.add_argument("--zelle", type=float, default=0.25)
    ap.add_argument("--min_p", type=int, default=12); ap.add_argument("--name", default=""); ap.add_argument("--wolke", help="dichte Wolke im Modellrahmen (npy N x 3): GEGENPROBE der Form (nur grob, Kernmethode: Wolke = Lage-Veto/Gegenprobe)"); a = ap.parse_args()
    import trimesh, cv2
    from scipy.spatial import cKDTree
    from kantenstufe import modellkanten
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); obj = json.load(open(objp)); stl = a.stl or os.path.join(ROOT, obj["stl"]); skala = float(obj.get("stl_massstab", 87)) / 1000.0
    WO = np.asarray(np.load(a.wolke, mmap_mode="r")[::4, :3], dtype=np.float32) if a.wolke and os.path.exists(a.wolke) else None      # jeder 4. Punkt reicht fuer die Gegenprobe
    m = trimesh.load(stl); m.apply_scale(skala); EJ = json.load(open(os.path.join(a.ebenen, "ebenen.json")))["ebenen"]; A = os.path.join(od, "audit"); os.makedirs(A, exist_ok=True); ber = []
    for e in EJ:
        if not e.get("sweep") or not os.path.exists(e["sweep"]): continue
        o = np.array(e["o"]); d = np.array(e["d"]); n = np.array(e["n"]); u0, u1, z0, z1 = e["zone"]; z0 = max(z0, 0.0); P = np.load(e["sweep"])["P"].astype(float)
        uz = lambda X: ((X[:, :2] - o) @ d, X[:, 2], (X[:, :2] - o) @ n - e["w"])
        u, z, w = uz(P); ok = (u >= u0) & (u <= u1) & (z >= z0) & (z <= z1); P, u, z, w = P[ok], u[ok], z[ok], w[ok]
        if len(P) < 200: continue
        C = m.triangles_center; cu, cz, cw = uz(C); fm = (cu > u0 - 2) & (cu < u1 + 2) & (cz > z0 - 2) & (cz < z1 + 2) & (np.abs(cw) < e["band"] + 3.0)
        if fm.sum() < 2: continue
        mm = trimesh.Trimesh(m.vertices, m.faces[fm], process=False); mm.remove_unreferenced_vertices()
        Q, _ = trimesh.sample.sample_surface_even(mm, int(min(3e6, max(4e5, mm.area * 900)))); d_fl, _ = cKDTree(Q).query(P)
        K = modellkanten(mm); ku, kz, kw = uz(K); km = (ku >= u0) & (ku <= u1) & (kz >= z0) & (kz <= z1) & (np.abs(kw) <= e["band"]); K, ku, kz, kw = K[km], ku[km], kz[km], kw[km]
        d_ka = cKDTree(K).query(P)[0] if len(K) else np.full(len(P), 9.0); d_kp = cKDTree(P).query(K)[0] if len(K) else np.zeros(0)
        form = d_fl > a.tol; detail = (~form) & (d_ka > a.tol); trifft = (~form) & (~detail); erf = (d_kp > a.tol) & (d_kp < 1.0); belegt = d_kp < 1.0
        zone = (u0, u1, z0, z1)
        L_form = flecken(u[form], z[form], w[form], zone, a.zelle, a.min_p); L_det = flecken(u[detail], z[detail], w[detail], zone, a.zelle, a.min_p * 3); L_erf = flecken(ku[erf], kz[erf], kw[erf], zone, a.zelle, a.min_p)
        b = dict(id=e["id"], art=e["art"], fassade=e["fassade"], w=e["w"], fotokanten=int(len(P)), an_flaeche=round(float((~form).mean()), 3), an_kante=round(float(trifft.mean()), 3), form_fehlt=round(float(form.mean()), 3),
                 detail_fehlt=round(float(detail.mean()), 3), modellkanten=int(len(K)), erfunden=round(float(erf.sum() / max(belegt.sum(), 1)), 3), liste_form=L_form[:15], liste_detail=L_det[:15], liste_erfunden=L_erf[:15])
        if WO is not None:      # GEGENPROBE dichte Wolke (unabhaengig vom Kanten-Sweep, gleiche Kameras): liegt die Wolke an der Modellflaeche? Flecken > 0,3 m daneben = Form fehlt grob
            wu, wz, wwq = uz(WO); wm = (wu >= u0) & (wu <= u1) & (wz >= z0) & (wz <= z1) & (np.abs(wwq) <= e["band"] + 0.5)
            if wm.sum() >= 2000:
                dw, _ = cKDTree(Q).query(WO[wm]); fern = dw > 0.30; Lw = flecken(wu[wm][fern], wz[wm][fern], wwq[wm][fern], zone, 0.5, 60)
                b.update(wolke_punkte=int(wm.sum()), wolke_an_flaeche=round(float((dw <= a.tol).mean()), 3), wolke_grob_daneben=round(float(fern.mean()), 3), liste_wolke=Lw[:10])
        ber.append(b)
        px = 0.02 if (u1 - u0) * (z1 - z0) < 200 else 0.03; W_, H_ = int((u1 - u0) / px), int((z1 - z0) / px); vis = np.full((H_, W_, 3), 40, np.uint8)
        if e.get("bild") and os.path.exists(e["bild"]): vis = (cv2.resize(cv2.imread(e["bild"]), (W_, H_)) * 0.4).astype(np.uint8)
        X = lambda uu: np.clip(((uu - u0) / px).astype(int), 0, W_ - 1); Y = lambda zz: np.clip(((z1 - zz) / px).astype(int), 0, H_ - 1)
        vis[Y(z[trifft]), X(u[trifft])] = (60, 200, 60); vis[Y(z[detail]), X(u[detail])] = (0, 210, 240); vis[Y(kz[erf]), X(ku[erf])] = (255, 120, 40); vis[Y(z[form]), X(u[form])] = (40, 40, 255)
        for i_, f_ in enumerate(L_form[:8]):
            cv2.rectangle(vis, (int((f_["u0"] - u0) / px), int((z1 - f_["z1"]) / px)), (int((f_["u1"] - u0) / px), int((z1 - f_["z0"]) / px)), (255, 255, 255), 1); cv2.putText(vis, str(i_ + 1), (int((f_["u0"] - u0) / px) + 2, int((z1 - f_["z1"]) / px) + 13), 0, 0.45, (255, 255, 255), 1)
        cv2.imwrite(os.path.join(A, f"abweichung_{e['id']}{a.name}.jpg"), vis, [1, 85])
        print(f"{e['id']:10s} {len(P):6d} Fotokanten: an der Modellflaeche {b['an_flaeche'] * 100:3.0f} %, an einer Modellkante {b['an_kante'] * 100:3.0f} % | FORM FEHLT {b['form_fehlt'] * 100:3.0f} % ({len(L_form)} Flecken), DETAIL FEHLT {b['detail_fehlt'] * 100:3.0f} %, ERFUNDEN {b['erfunden'] * 100:3.0f} % der Modellkanten")
        if b.get("wolke_punkte"):
            print(f"     Gegenprobe dichte Wolke ({b['wolke_punkte']} Punkte): an der Modellflaeche {b['wolke_an_flaeche'] * 100:.0f} %, > 0,3 m daneben {b['wolke_grob_daneben'] * 100:.0f} %" + "".join(f" | Fleck u {f_['u0']:.1f}..{f_['u1']:.1f} z {f_['z0']:.1f}..{f_['z1']:.1f} ({f_['punkte']} P., {f_['tiefe']:+.2f} m)" for f_ in b["liste_wolke"][:3]))
        for i_, f_ in enumerate(L_form[:4]): print(f"     Form fehlt {i_ + 1}: u {f_['u0']:.1f}..{f_['u1']:.1f}  z {f_['z0']:.1f}..{f_['z1']:.1f}  {f_['punkte']} Punkte, {f_['tiefe']:+.2f} m gegen die Ebene")
    try: rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=od).stdout.strip()
    except Exception: rev = "?"
    ges = dict(zeit=time.strftime("%Y-%m-%d %H:%M"), git=rev, stl=os.path.relpath(stl, ROOT), tol=a.tol, ebenen=ber)
    if ber:
        nP = sum(b["fotokanten"] for b in ber); ges.update(fotokanten=nP, an_flaeche=round(sum(b["an_flaeche"] * b["fotokanten"] for b in ber) / nP, 3), an_kante=round(sum(b["an_kante"] * b["fotokanten"] for b in ber) / nP, 3))
        print(f"GESAMT {nP} Fotokanten auf {len(ber)} Ebenen: an der Modellflaeche {ges['an_flaeche'] * 100:.0f} %, an einer Modellkante {ges['an_kante'] * 100:.0f} %")
    json.dump(ges, open(os.path.join(A, f"ebenen_abweichung{a.name}.json"), "w"), indent=1)
    with open(os.path.join(A, "ebenen_abweichung_verlauf.jsonl"), "a") as f_: f_.write(json.dumps(dict(zeit=ges["zeit"], git=rev, name=a.name, an_flaeche=ges.get("an_flaeche"), an_kante=ges.get("an_kante"), ebenen={b["id"]: [b["an_flaeche"], b["an_kante"], b["erfunden"], b.get("wolke_an_flaeche")] for b in ber})) + "\n")
    return 0


if __name__ == "__main__": sys.exit(main())
