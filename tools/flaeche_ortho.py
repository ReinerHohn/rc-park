#!/usr/bin/env python3
"""flaeche_ortho.py - Wandbild fuer BELIEBIGE Flaechen: ebene Flaeche in jeder Lage (Erker-Teilflaechen), Vieleck-Erker (n-Eck), Zylinder, Rotationsflaeche (Kegel, Helm, Turm).
18.11.2026 (Nutzerauftrag: runde Elemente + Erker mit mehreren Teilflaechen). Gleiche Idee wie fassade_ortho.py (Zelle -> Foto, Median ueber die besten Fotos), aber die Flaeche
ist parametrisch: jede Rasterzelle hat einen 3D-Punkt UND eine Aussennormale (Sichtbarkeit cos(Blickwinkel), Aufloesung m/Pixel). Bei Rundungen ist das Raster eine ABWICKLUNG:
Spalte = Bogenlaenge u = phi * r_ref (r_ref = groesster Radius des Profils, Meter), Zeile = Hoehe z. Ein Foto sieht nur einen Streifen (Blickwinkel < --max-winkel zur Normalen),
die Abdeckung (abdeckung_<id>.png) zeigt, wo Fotos rundherum fehlen.

flaechen.json = Liste von Flaechen:
  {"id":"e1","typ":"ebene","o":[x,y,0],"d":[dx,dy,0],"n":[nx,ny,0],"u":[u0,u1],"z":[z0,z1]}          X = o + u*d + (0,0,z); n = Aussennormale
  {"id":"erker","typ":"polygon","achse":[x,y],"apothem":1.2,"n":8,"winkel0":0,"flaechen":[0,1,7],"z":[6,9]}   n-Eck: Flaeche k hat Aussennormale winkel0 + k*360/n Grad (0 = +x, links herum)
  {"id":"turm","typ":"zylinder","achse":[x,y],"r":1.5,"phi":[0,360],"z":[0,12]}
  {"id":"kegel","typ":"rotation","achse":[x,y],"profil":[[z,r],[z,r],...],"phi":[a0,a1]}                  Profil = Radius je Hoehe (z aufsteigend), phi in Grad (0 = +x, links herum)
Aufruf: python3 tools/flaeche_ortho.py objekt.json --flaechen flaechen.json --aus ORDNER [--zelle 0.02] [--fotos a,b] [--stl modell.stl]
Ausgabe: ortho_<id>.png, abdeckung_<id>.png, flaechen_ortho.json (Raster + Abbildung Pixel -> 3D). Lizenz: nur numpy/OpenCV."""
import os, sys, json, glob, math, argparse
import numpy as np, cv2

HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER)


def flaechen_expandieren(spec):
    """n-Eck-Erker (typ polygon) in ebene Teilflaechen aufloesen; alles andere unveraendert."""
    out = []
    for s in spec:
        if s["typ"] != "polygon": out.append(s); continue
        n = int(s.get("n", 8)); a = float(s["apothem"]); cx, cy = s["achse"]; th0 = math.radians(float(s.get("winkel0", 0.0))); w = 2 * a * math.tan(math.pi / n)
        for k in s.get("flaechen", list(range(n))):
            th = th0 + 2 * math.pi * k / n; nn = [math.cos(th), math.sin(th), 0.0]
            out.append(dict(id=f"{s['id']}_{k}", typ="ebene", o=[cx + a * nn[0], cy + a * nn[1], 0.0], d=[-nn[1], nn[0], 0.0], n=nn, u=[-w / 2, w / 2], z=list(s["z"])))
    return out


def raster(F, zelle):
    """Zellpunkte X (N,3), Aussennormalen Nn (N,3) und Rastermasse der Flaeche; Zeile 0 = oben, Spalte 0 = links (von aussen gesehen)."""
    if F["typ"] == "ebene":
        o, d, n = (np.asarray(F[k], float) for k in ("o", "d", "n")); n = n / np.linalg.norm(n); d = d / np.linalg.norm(d)
        u0, u1 = F["u"]; z0, z1 = F["z"]; nu, nz = int(math.ceil((u1 - u0) / zelle)), int(math.ceil((z1 - z0) / zelle))
        uu = u0 + (np.arange(nu) + 0.5) * (u1 - u0) / nu; zz = z1 - (np.arange(nz) + 0.5) * (z1 - z0) / nz; U, Z = np.meshgrid(uu, zz)
        X = o[None, :] + U.reshape(-1, 1) * d[None, :] + np.c_[np.zeros(U.size), np.zeros(U.size), Z.ravel()]
        return X, np.tile(n, (len(X), 1)), dict(nu=nu, nz=nz, u0=u0, u1=u1, z0=z0, z1=z1, masstab_u_m=1.0, abbildung="X = o + u*d + (0,0,z)")
    if F["typ"] == "zylinder": prof = [[F["z"][0], F["r"]], [F["z"][1], F["r"]]]
    else: prof = F["profil"]
    prof = np.asarray(prof, float); zs, rs = prof[:, 0], prof[:, 1]; cx, cy = F["achse"]; rref = float(rs.max())
    p0, p1 = (math.radians(v) for v in F["phi"]); z0, z1 = float(zs.min()), float(zs.max())
    nu = int(math.ceil((p1 - p0) * rref / zelle)); nz = int(math.ceil((z1 - z0) / zelle))
    ph = p0 + (np.arange(nu) + 0.5) * (p1 - p0) / nu; zz = z1 - (np.arange(nz) + 0.5) * (z1 - z0) / nz
    r = np.interp(zz, zs, rs); steig = np.gradient(rs, zs) if len(zs) > 1 else np.zeros(1)
    drdz = np.interp(zz, zs, steig); P, Rr = np.meshgrid(ph, r); _, Dz = np.meshgrid(ph, drdz); _, Z = np.meshgrid(ph, zz)
    X = np.c_[cx + Rr.ravel() * np.cos(P.ravel()), cy + Rr.ravel() * np.sin(P.ravel()), Z.ravel()]
    N = np.c_[np.cos(P.ravel()), np.sin(P.ravel()), -Dz.ravel()]; N /= np.linalg.norm(N, axis=1, keepdims=True)
    return X, N, dict(nu=nu, nz=nz, phi0=p0, phi1=p1, z0=z0, z1=z1, r_ref=rref, masstab_u_m=rref,
                      abbildung="Spalte i: phi = phi0 + (i+0.5)*(phi1-phi0)/nu, Bogenlaenge u = phi*r_ref; Zeile j: z = z1 - (j+0.5)*(z1-z0)/nz; X = (cx + r(z)cos phi, cy + r(z)sin phi, z)")


def kameras_laden(objekt, fotos=None):
    obj = json.load(open(objekt)); od = os.path.dirname(os.path.abspath(objekt)); out = {}
    for k in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        nr = os.path.basename(k)[2:-5]
        if fotos and nr not in fotos: continue
        c = json.load(open(k)).get("kamera")
        if not (isinstance(c, dict) and "rvec" in c and "cx" in c): continue
        if not fotos:
            if nr.startswith(("dl_", "neu__")) and not c.get("vertrauen"): continue
            if "buendel_tor" in c and not c["buendel_tor"].get("ok"): continue
        pf = glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + ".*")) or glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + "_*"))
        if pf: out[nr] = (c, pf[0])
    return obj, out


def projektion(X, c):
    R = cv2.Rodrigues(np.asarray(c["rvec"], float))[0]; t = np.asarray(c["t"], float); tr = np.asarray(c.get("rahmen_verschiebung", [0, 0, 0]), float)
    Xc = (X + tr) @ R.T + t; z = Xc[:, 2]; xn = Xc[:, 0] / np.where(np.abs(z) < 1e-9, 1e-9, z); yn = Xc[:, 1] / np.where(np.abs(z) < 1e-9, 1e-9, z)
    s = 1 + float(c.get("k1") or 0.0) * (xn * xn + yn * yn); f = c["f_px"]
    return np.c_[f * xn * s + c["cx"], f * yn * s + c["cy"]], z, -R.T @ t - tr


def fusionieren(F, X, N, cams, a, stl=None, cache=None):
    """Je Rasterzelle die besten --max-fotos Beobachtungen (Guete = cos / Meter je Pixel) behalten, Farbe = Median ueber sie."""
    n = len(X); K = a.max_fotos; col = np.zeros((K, n, 3), np.uint8); w = np.full((K, n), -1.0, np.float32); benutzt = {}
    for nr, (c, pfad) in cams.items():
        px, z, C = projektion(X, c); v = C[None, :] - X; dist = np.linalg.norm(v, axis=1); cosw = (v * N).sum(1) / np.maximum(dist, 1e-9)
        W, H = c["cx"] * 2, c["cy"] * 2; mpp = dist / (c["f_px"] * np.maximum(cosw, 1e-3))
        ok = (cosw > math.cos(math.radians(a.max_winkel))) & (z > 1) & (px[:, 0] >= 0) & (px[:, 0] < W - 1) & (px[:, 1] >= 0) & (px[:, 1] < H - 1) & (mpp < a.max_mpp) & (dist > 0.5) & (dist < 2000)
        if ok.sum() < 50: continue
        idx = np.where(ok)[0]
        if stl is not None:                                                                          # Verdecker: erster Treffer vor der Zelle -> verdeckt
            d_ = -v[idx] / dist[idx, None]; ti, ri, loc = stl.intersects_id(np.broadcast_to(C, (len(idx), 3)), d_, multiple_hits=False, return_locations=True)
            vor = np.full(len(idx), np.inf); vor[ri] = np.linalg.norm(loc - C, axis=1); ok2 = np.abs(vor - dist[idx]) < a.tol + 0.002 * dist[idx]; idx = idx[ok2]
            if len(idx) < 50: continue
        im = cache[nr] if cache is not None and nr in cache else cv2.imread(pfad)
        if im is None: continue
        if im.shape[1] != int(W): px = px * (im.shape[1] / W)                                      # Bild in anderer Groesse als in der K-Datei
        smp = np.concatenate([cv2.remap(im, px[idx[s:s + 30000], 0].reshape(1, -1).astype(np.float32), px[idx[s:s + 30000], 1].reshape(1, -1).astype(np.float32), cv2.INTER_LINEAR)[0]
                              for s in range(0, len(idx), 30000)])                                  # cv2.remap: Zielbreite < 32767
        g = (cosw[idx] / mpp[idx]).astype(np.float32); sl = np.argmin(w[:, idx], axis=0); wm = w[sl, idx]; neu = g > wm
        col[sl[neu], idx[neu]] = smp[neu]; w[sl[neu], idx[neu]] = g[neu]; benutzt[nr] = int(neu.sum())
    gueltig = w >= 0; cnt = gueltig.sum(0); stack = np.where(gueltig[..., None], col.astype(np.float32), np.nan)
    with np.errstate(all="ignore"): med = np.nanmedian(stack, axis=0)
    img = np.clip(np.nan_to_num(med, nan=0.0) + 0.5, 0, 255).astype(np.uint8)
    with np.errstate(all="ignore"):                                                                    # UNEINIGKEIT: Streuung (MAD) der Grauwerte ueber die Fotos je Zelle; klein = die Fotos liegen deckungsgleich = Geometrie stimmt
        gr = stack.mean(-1); mad = np.nanmedian(np.abs(gr - np.nanmedian(gr, axis=0)), axis=0); mad[cnt < 3] = np.nan
    return img, cnt, benutzt, mad


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--flaechen", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--zelle", type=float, default=0.02, help="Zellgroesse in m (Rundung: entlang Bogen und Hoehe)"); ap.add_argument("--max-winkel", type=float, default=70.0)
    ap.add_argument("--max-fotos", type=int, default=12, help="je Zelle die besten N Beobachtungen (Speicher: N x Zellen x 3 Byte)"); ap.add_argument("--max-mpp", type=float, default=0.05)
    ap.add_argument("--tol", type=float, default=0.10); ap.add_argument("--fotos"); ap.add_argument("--stl", help="Modell als Verdecker-Pruefung (Massstab stl_massstab des Objekts)")
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True)
    obj, cams = kameras_laden(a.objekt, a.fotos.split(",") if a.fotos else None); stl = None
    if a.stl:
        import trimesh; m = trimesh.load(a.stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); stl = trimesh.ray.ray_triangle.RayMeshIntersector(m)
    spec = flaechen_expandieren(json.load(open(a.flaechen))); bericht = []
    print(f"{len(cams)} Kameras, {len(spec)} Flaechen", flush=True)
    for F in spec:
        X, N, r = raster(F, a.zelle); img, cnt, benutzt, mad = fusionieren(F, X, N, cams, a, stl)
        cv2.imwrite(os.path.join(a.aus, f"ortho_{F['id']}.png"), img.reshape(r["nz"], r["nu"], 3)); cv2.imwrite(os.path.join(a.aus, f"abdeckung_{F['id']}.png"), np.clip(cnt * 20, 0, 255).astype(np.uint8).reshape(r["nz"], r["nu"]))
        bericht.append(dict(id=F["id"], typ=F["typ"], raster=r, zelle=a.zelle, abgedeckt=round(float((cnt > 0).mean()), 3), mind3=round(float((cnt >= 3).mean()), 3), uneinig_mad=round(float(np.nanmedian(mad)), 2) if np.isfinite(mad).any() else None, fotos=benutzt))
        print(f"  {F['id']} ({F['typ']}): {r['nu']} x {r['nz']} Zellen, abgedeckt {bericht[-1]['abgedeckt']*100:.0f} %, >= 3 Fotos {bericht[-1]['mind3']*100:.0f} %, Uneinigkeit (MAD) {bericht[-1]['uneinig_mad']}, {len(benutzt)} Fotos", flush=True)
    json.dump(bericht, open(os.path.join(a.aus, "flaechen_ortho.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__": main()
