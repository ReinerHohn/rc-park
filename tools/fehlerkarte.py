#!/usr/bin/env python3
"""fehlerkarte.py - Fehlerkarte je Flaeche (Wand, Vorbau, Dach) fuer die Konvergenzschleife (SPEC_S3_KONVERGENZ Abschnitt 1, nur MESSUNG, 2026-11-05).

Je Flaeche ein Zellraster (u, z) bzw. (u, v) mit `zelle_m` (Plan konvergenz), identisch zum Raster von restfeld_fassade.py (dessen Ausgabe wird gelesen).
Je Zelle und Foto (nur Fotos, die die Zelle SEHEN: im Bild, vor der Kamera, nicht streifend, in der Bewertungsmaske, per Embree nicht vom Modell verdeckt):
  rot  = im Fenster +- `fenster_m` um die projizierte Zellmitte liegen >= `min_kantenpixel` Modellkantenpixel ohne Fotokante (Kostenkarte dF >= kante_tol, Modellkantenmaske mkp)
         und deren Anteil an allen Modellkantenpixeln im Fenster ist >= `min_anteil`;
  gelb = dasselbe fuer Fotokantenpixel ohne Modellkante (fkp, dM).
Der je Foto geschaetzte globale Versatz (foto_diff JSON `versatz`, wenn `deutlich`) wird eingerechnet: Modellkanten in Modell-, Fotokanten in Fotokoordinaten
(Foto = Modell + Versatz); die Zellmitte wird fuer rot unverschoben, fuer gelb um den Versatz verschoben abgetastet, dF/dM werden entsprechend verschoben gelesen.
Stimmen: rot/gelb = Anteil der sehenden Fotos mit Treffer; n_fotos = Zahl der sehenden Fotos.
Restfeld (rest, n_pkt) kommt aus restfeld_fassade.py (Wand: Daten = dichte Wolke). QUELLENSPERRE DACH (Spec 0b): Dachflaechen (id d..) benutzen die dichte Wolke NICHT;
rest je Quelle getrennt aus DOM1 (naechste 1-m-Zelle), Stadt-LoD2-Dachebene und Stadtmesh (vertikaler Strahl), nie gemittelt; Widerspruch der Quellen-Mediane > widerspruch_m = Cluster-Art
'quellen_widerspruch' (kein Kandidat). Freiraum (optional): freiraum_fassaden.json -> frei je Zelle.
Cluster: 8er-Zusammenhang der Zellen mit n_fotos >= min_fotos und (gelb >= stimmen oder rot >= stimmen), je Art getrennt; < min_flaeche_m2 verworfen.
Kennzahl F = sum ueber Zellen mit n_fotos >= min_fotos (gelb + rot) x zelle_m^2 je Flaeche und gesamt (nur sie entscheidet ueber Konvergenz).
Bekannte Luecken (ehrlich): Verdeckermaske (Personen/Fahrzeuge) aus foto_diff liegt nicht in der Kostenkarte -> nur Embree-Sicht gegen das Modell; n_pkt statt Kamerazahl (restfeld
speichert Punkte je Zelle); rot/gelb-Projektion der Zellmitte erfolgt auf der Modelloberflaeche (Tiefe aus restfeld `modell`) bzw. der Datenflaeche (`daten`).
Schwellen: NUR aus Plan konvergenz (modelle/PLAN_STANDARD_qualitaetsstufen.json), keine Festwerte im Code.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/fehlerkarte.py modelle/<obj>/objekt.json --karten-dir DIR --restfeld DIR --aus DIR [--masken DIR] [--stl S.stl] [--elemente E.json]
"""
import os, sys, json, glob, argparse, time
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elementbuch as EB

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PLAN_STANDARD = os.path.join(ROOT, "modelle", "PLAN_STANDARD_qualitaetsstufen.json")


def schwellen_laden(plan=None):
    """Plan-Schluessel 'konvergenz' (Standard: PLAN_STANDARD_qualitaetsstufen.json); fehlende Schluessel kommen aus dem Standardplan, nie aus dem Code."""
    std = json.load(open(PLAN_STANDARD))["stufen"]; std = next(s for s in std if s.get("verfahren") == "konvergenz")["konvergenz"]
    s = dict(std)
    if plan:
        pk = plan.get("konvergenz") or next((x.get("konvergenz") for x in plan.get("stufen", []) if x.get("verfahren") == "konvergenz"), None) or {}
        s.update(pk)
    return s


# ------------------------------------------------------------------ Kamera, Karten
def projizieren(P, kam):
    R, t, f, cx, cy = kam; Pc = P @ R.T + t; z = Pc[:, 2]; zz = np.where(z > 1e-6, z, np.nan)
    return np.c_[f * Pc[:, 0] / zz + cx, f * Pc[:, 1] / zz + cy], z


def integral(b):
    """Summenbild (H+1, W+1) int32 eines bool-Bildes."""
    S = np.zeros((b.shape[0] + 1, b.shape[1] + 1), np.int32); S[1:, 1:] = np.cumsum(np.cumsum(b.astype(np.int32), 0), 1); return S


def fenster_summe(S, x, y, w):
    """Summe im Quadrat +-w (px, je Zelle) um (x, y); ausserhalb des Bildes abgeschnitten."""
    H, W = S.shape[0] - 1, S.shape[1] - 1
    x0 = np.clip(np.round(x - w).astype(int), 0, W); x1 = np.clip(np.round(x + w).astype(int) + 1, 0, W); y0 = np.clip(np.round(y - w).astype(int), 0, H); y1 = np.clip(np.round(y + w).astype(int) + 1, 0, H)
    return S[y1, x1] - S[y0, x1] - S[y1, x0] + S[y0, x0]


class FotoKarte:
    """Eine Kostenkarte: rot-/gelb-Masken mit eingerechnetem Versatz, Summenbilder fuer schnelle Fensterzaehlung."""
    def __init__(self, pfad, kante_tol, versatz_anwenden):
        z = np.load(pfad); mkp, fkp, dF, dM = z["mkp"], z["fkp"], z["dF"], z["dM"]; self.H, self.W = mkp.shape; self.v = (0, 0); self.versatz = None
        jp = os.path.join(os.path.dirname(pfad), "foto_diff_" + os.path.basename(os.path.dirname(pfad)) + ".json")
        if versatz_anwenden and os.path.exists(jp):
            vs = (json.load(open(jp)).get("versatz") or {})
            if vs.get("deutlich") and vs.get("versatz_px"): self.v = (int(vs["versatz_px"][0]), int(vs["versatz_px"][1])); self.versatz = vs
        dx, dy = self.v
        rot = np.zeros_like(mkp); gelb = np.zeros_like(fkp)
        ys, xs = np.nonzero(mkp); yy, xx = ys + dy, xs + dx; ok = (yy >= 0) & (yy < self.H) & (xx >= 0) & (xx < self.W)                  # rot[x] = mkp[x] & dF[x + v] >= tol
        rot[ys[ok], xs[ok]] = (dF[yy[ok], xx[ok]] >= kante_tol)
        ys, xs = np.nonzero(fkp); yy, xx = ys - dy, xs - dx; ok = (yy >= 0) & (yy < self.H) & (xx >= 0) & (xx < self.W)                  # gelb[y] = fkp[y] & dM[y - v] >= tol
        gelb[ys[ok], xs[ok]] = (dM[yy[ok], xx[ok]] >= kante_tol)
        self.S_rot, self.S_mk, self.S_gelb, self.S_fk = integral(rot), integral(mkp), integral(gelb), integral(fkp)


def stimme(S_flag, S_all, x, y, w, min_px, min_anteil):
    a = fenster_summe(S_flag, x, y, w); n = fenster_summe(S_all, x, y, w)
    return (a >= min_px) & (n > 0) & (a >= min_anteil * np.maximum(n, 1))


# ------------------------------------------------------------------ Flaechen und Dachquellen
def flaechen_laden(restfeld_dir):
    """restfeld.json + restfeld_<fid>.npz -> {fid: dict(n, o, dd, e, daten, modell, anzahl, u0, z1, zelle)}; Rest wie restfeld_fassade (kein Modell im Band = -tief)."""
    R = json.load(open(os.path.join(restfeld_dir, "restfeld.json"))); tief = float(R["parameter"]["tief"]); out = {}
    for fid, F in R["fassaden"].items():
        p = os.path.join(restfeld_dir, f"restfeld_{fid}.npz")
        if not os.path.exists(p): continue
        z = np.load(p); out[fid] = dict(n=np.array(F["n"], float), o=np.array(F["o"], float), dd=np.array(F["dd"], float), e=np.array(F["e"], float), daten=z["daten"], modell=z["modell"], anzahl=z["anzahl"],
                                       u0=float(z["u0"]), z1=float(z["z1"]), zelle=float(z["zelle"]), tief=tief, dach=fid.startswith("d"), flaeche_kenn=F)
    return out, R


def zellmitten(F):
    nz, nu = F["daten"].shape; z = F["zelle"]; gu, gz = np.meshgrid(F["u0"] + (np.arange(nu) + 0.5) * z, F["z1"] - (np.arange(nz) + 0.5) * z)
    o, dd, e, n = F["o"], F["dd"], F["e"], F["n"]; oz = o[2] if e[2] > 0.999 else 0.0
    return o[None] + gu.reshape(-1, 1) * dd[None] + (gz.reshape(-1, 1) - oz) * e[None]


class DachQuellen:
    """DOM1, Stadt-LoD2-Dachebenen, Stadtmesh im Modellrahmen. Jede Quelle liefert z(x, y) ueber Gelaende oder NaN; keine wird mit einer anderen gemittelt (Spec 0b)."""
    def __init__(self, objp, obj, schw):
        self.od = os.path.dirname(os.path.abspath(objp)); self.quellen = {}; self.fehlt = {}
        try:
            import beweis_ansatz as BA
            D = BA.dom1_laden(dict(obj=obj, od=self.od))
            if D is None: raise RuntimeError("keine DOM1-Kachel")
            self.D = D; self.quellen["dom1"] = f"DOM1 {D['quelle']} (bilinear; 1-m-Raster, auf Hang sonst Treppen)"
        except Exception as ex: self.fehlt["dom1"] = f"{type(ex).__name__}: {ex}"
        sp = os.path.join(self.od, "stadt_lod2.json")
        try:
            from matplotlib.path import Path
            J = json.load(open(sp)); self.sl = []
            for g in J["stadt"]["gebaeude"]:
                for f in g["flaechen"]:
                    if f["typ"] != "Dach": continue
                    Q = np.array(f["lokal"], float); nv = np.cross(Q[1] - Q[0], Q[2] - Q[0]); nv = nv / (np.linalg.norm(nv) + 1e-12)
                    if nv[2] < 0: nv = -nv
                    if nv[2] < schw["dach_nz_min"]: continue
                    self.sl.append(dict(n=nv, d=-nv @ Q.mean(0), path=Path(Q[:, :2])))
            if not self.sl: raise RuntimeError("keine Dachflaechen")
            self.quellen["stadt_lod2"] = f"{os.path.basename(sp)} ({len(self.sl)} Dachflaechen)"
        except Exception as ex: self.fehlt["stadt_lod2"] = f"{type(ex).__name__}: {ex}"
        mp = os.path.join(self.od, "audit", "referenz_stadtmesh", "mesh.ply")
        try:
            import trimesh; from trimesh.ray.ray_pyembree import RayMeshIntersector
            self.mesh = RayMeshIntersector(trimesh.load(mp)); self.quellen["stadtmesh"] = "audit/referenz_stadtmesh/mesh.ply (roh; Strassenniveau-ANNAHME +-1 m)"
        except Exception as ex: self.fehlt["stadtmesh"] = f"{type(ex).__name__}: {ex}"

    def z(self, quelle, x, y, reserve=0.0):
        z = np.full(len(x), np.nan)
        if quelle == "dom1" and "dom1" in self.quellen:
            from scipy.ndimage import map_coordinates
            D = self.D; E = D["c0"][0] + x * D["xh"][0] + y * D["yh"][0]; N = D["c0"][1] + x * D["xh"][1] + y * D["yh"][1]               # Modellrahmen -> UTM (wie beweis_ansatz.dom1_laden)
            z = map_coordinates(D["Z"], [D["N"][0, 0] - N, E - D["E"][0, 0]], order=1, mode="constant", cval=np.nan)
        elif quelle == "stadt_lod2" and "stadt_lod2" in self.quellen:
            for f in self.sl:
                ins = f["path"].contains_points(np.c_[x, y]); zz = -(f["n"][0] * x + f["n"][1] * y + f["d"]) / f["n"][2]; upd = ins & (~np.isfinite(z) | (zz > z)); z[upd] = zz[upd]
        elif quelle == "stadtmesh" and "stadtmesh" in self.quellen:
            hoch = float(np.nanmax(self.mesh.mesh.bounds[:, 2])) + reserve; o = np.c_[x, y, np.full(len(x), hoch)]; loc, ri, _ = self.mesh.intersects_location(o, np.tile([0, 0, -1.0], (len(x), 1)), multiple_hits=True)
            for i_, p in zip(ri, loc):
                if not (z[i_] >= p[2]): z[i_] = p[2]
        return z


QUELLEN = ("dom1", "stadt_lod2", "stadtmesh")


# ------------------------------------------------------------------ Cluster
def cluster_finden(F, art, schw, fid, stand_el, quellen_je_zelle=None):
    """8er-Zusammenhang; je Cluster Box, Flaeche, Stimmen, Rest. Rueckgabe Liste (unsortiert)."""
    from scipy import ndimage
    z = F["zelle_m"]; nf = F["n_fotos"]; stim = F[art]; m = (nf >= schw["min_fotos"]) & (stim >= schw["stimmen"])
    lab, n = ndimage.label(m, structure=np.ones((3, 3), int)); out = []
    for j in range(1, n + 1):
        zz, uu = np.nonzero(lab == j); fl = len(zz) * z * z
        if fl < schw["min_flaeche_m2"]: continue
        u0, u1 = F["u0"] + uu.min() * z, F["u0"] + (uu.max() + 1) * z; z1_, z0_ = F["z1"] - zz.min() * z, F["z1"] - (zz.max() + 1) * z
        c = dict(fid=fid, art=art, u0=round(float(u0), 3), u1=round(float(u1), 3), z0=round(float(z0_), 3), z1=round(float(z1_), 3), flaeche_m2=round(float(fl), 3), zellen=int(len(zz)),
                 stimmen=round(float(stim[zz, uu].mean()), 3), n_fotos_mittel=round(float(nf[zz, uu].mean()), 2), dach=bool(F["dach"]))
        rj = {}
        for q, R_ in F["rest_je_quelle"].items():
            r = R_[zz, uu]; r = r[np.isfinite(r)]; rj[q] = (round(float(np.median(r)), 3), int(len(r))) if len(r) else None
        c["rest_je_quelle"] = rj
        if F["dach"]:
            med = {q: v[0] for q, v in rj.items() if v and v[1] >= schw["rest_n_min"]}; c["rest_median"] = None; c["rest_n"] = 0
            for q in QUELLEN:                                                                           # Reihenfolge der Vorrang-Quelle, nie gemittelt
                if q in med: c["rest_median"], c["rest_n"] = med[q], rj[q][1]; c["rest_quelle"] = q; break
            if len(med) >= 2 and max(med.values()) - min(med.values()) > schw["widerspruch_m"]: c["art_detail"] = c["art"]; c["art"] = "quellen_widerspruch"
        else:
            v = rj.get("wolke"); c["rest_median"], c["rest_n"] = (v if v else (None, 0)); c["rest_quelle"] = "wolke"
        fr = F.get("frei"); c["frei_anteil"] = round(float((fr[zz, uu] > schw["frei_tiefe_m"]).mean()), 3) if fr is not None else None
        sees = F["sieht"]; c["fotos"] = sorted(nr for nr, S in sees.items() if S[zz, uu].mean() >= schw["stimmen"])
        c["stand_elemente"] = [k for k, g in stand_el.get(fid, []) if g["u0"] < u1 and g["u1"] > u0 and g["z0"] < z1_ and g["z1"] > z0_]
        out.append(c)
    return out


# ------------------------------------------------------------------ Hauptrechnung
def rechnen(objp, obj, karten, restfeld_dir, aus, k=0, schw=None, stl=None, elemente=None, masken=None, freiraum=None, fotos=None, bilder=True, log=print):
    """karten {nr: pfad kostenkarte.npz}; Rueckgabe dict(cluster=[...], F=..., F_je_flaeche=..., ...); schreibt <aus>/fehlerkarte_k<k>/<fid>.npz/.jpg + cluster.json."""
    t0 = time.time(); schw = schw or schwellen_laden(); od = os.path.join(aus, f"fehlerkarte_k{k}"); os.makedirs(od, exist_ok=True)
    fotos = sorted(fotos or karten); FL, R = flaechen_laden(restfeld_dir); kam = EB.Kameras(os.path.abspath(objp), obj, ROOT)
    for fid, F in FL.items(): F["zelle_m"] = F["zelle"]
    Q = DachQuellen(objp, obj, schw) if any(F["dach"] for F in FL.values()) else None
    rmi = None
    if stl:
        import trimesh; from trimesh.ray.ray_pyembree import RayMeshIntersector
        m = trimesh.load(stl); m.apply_scale(float(obj["stl_massstab"]) / 1000.0); rmi = RayMeshIntersector(m)
    stand_el = {}
    if elemente and os.path.exists(elemente):
        E, _ = EB.elemente_laden(elemente)
        for kk, g in E.items():                                                                      # Elementdatei des Baus: u in Generatorrichtung d' = -d (u' = -u) -> in die Richtung dd der Flaeche drehen
            F_ = FL.get(g["fassade"]); sg = -1.0 if (F_ is not None and float(np.dot(g["rahmen"]["d"][:2], F_["dd"][:2])) < 0) else 1.0
            g = dict(g, u0=min(sg * g["u0"], sg * g["u1"]), u1=max(sg * g["u0"], sg * g["u1"])); stand_el.setdefault(g["fassade"], []).append((kk, g))
    fr_json = json.load(open(freiraum))["fassaden"] if freiraum and os.path.exists(freiraum) else {}
    # Geometrie je Flaeche
    for fid, F in FL.items():
        P = zellmitten(F); nz, nu = F["daten"].shape; F["P"] = P; mo = F["modell"].ravel(); da = F["daten"].ravel()
        F["P_modell"] = P + F["n"][None] * np.where(np.isfinite(mo), mo, 0.0)[:, None]
        F["P_daten"] = P + F["n"][None] * np.where(np.isfinite(da), da, np.where(np.isfinite(mo), mo, 0.0))[:, None]
        F["n_fotos"] = np.zeros((nz, nu), np.int16); F["rot"] = np.zeros((nz, nu), np.float32); F["gelb"] = np.zeros((nz, nu), np.float32); F["sieht"] = {}
        modell_r = np.where(np.isnan(F["modell"]), -F["tief"], F["modell"])
        if F["dach"]:
            rj = {}; x, y = P[:, 0], P[:, 1]; nzv = F["n"][2]; zp = P[:, 2]
            for q in QUELLEN:
                if q not in Q.quellen: continue
                zq = Q.z(q, x, y, schw["strahl_reserve_m"]); r = ((zq - zp) * nzv).reshape(nz, nu) - np.where(np.isnan(F["modell"]), np.nan, F["modell"]); rj[q] = np.where(np.isfinite(F["modell"]), r, np.nan)
            F["rest_je_quelle"] = rj
        else: F["rest_je_quelle"] = dict(wolke=np.where(np.isnan(F["daten"]), np.nan, F["daten"] - modell_r))
        F["frei"] = None
        if fid in fr_json:
            fz = fr_json[fid]; M = np.array(fz["raster"]); zf = fz["zelle"]; uu = F["u0"] + (np.arange(nu) + 0.5) * F["zelle"]; zz_ = F["z1"] - (np.arange(nz) + 0.5) * F["zelle"]
            iu = np.clip(((uu - fz["u"][0]) / zf).astype(int), 0, M.shape[1] - 1); iz = np.clip(((zz_ - fz["z"][0]) / zf).astype(int), 0, M.shape[0] - 1); F["frei"] = M[np.ix_(iz, iu)]
    # Fotos
    vers = {}
    for nr in fotos:
        mask = None
        if masken and os.path.exists(os.path.join(masken, f"{nr}.png")): mask = cv2.imread(os.path.join(masken, f"{nr}.png"), 0) > 0
        FK = FotoKarte(karten[nr], schw["kante_tol"], schw["versatz_anwenden"]); vers[nr] = FK.versatz or dict(versatz_px=[0, 0], deutlich=False); R_, t_, f_, cx, cy = kam.holen(nr, FK.W, FK.H); C = -R_.T @ t_; kc = (R_, t_, f_, cx, cy)
        w_mod = lambda tiefe: np.clip(schw["fenster_m"] * f_ / np.maximum(tiefe, 1.0), schw["fenster_min_px"], None)
        for fid, F in FL.items():
            nz, nu = F["daten"].shape; xy, dep = projizieren(F["P_modell"], kc); sicht = np.isfinite(xy[:, 0]) & (dep > 0.5) & (xy[:, 0] >= 0) & (xy[:, 0] < FK.W) & (xy[:, 1] >= 0) & (xy[:, 1] < FK.H)
            v = F["P_modell"] - C[None]; dist = np.linalg.norm(v, axis=1); cosw = -(v @ F["n"]) / np.maximum(dist, 1e-9); sicht &= cosw > schw["streif_cos"]
            if mask is not None and sicht.any():
                ix = np.clip(np.round(xy[sicht, 0]).astype(int), 0, FK.W - 1); iy = np.clip(np.round(xy[sicht, 1]).astype(int), 0, FK.H - 1); s2 = sicht.copy(); s2[sicht] = mask[iy, ix]; sicht = s2
            if rmi is not None and sicht.any():
                idx = np.flatnonzero(sicht); d_ = v[idx] / dist[idx, None]; loc, ri, _ = rmi.intersects_location(np.repeat(C[None], len(idx), 0), d_, multiple_hits=False)
                th = np.full(len(idx), np.inf); th[ri] = np.linalg.norm(loc - C[None], axis=1); sicht[idx[th < dist[idx] - schw["sicht_toleranz_m"]]] = False
            if not sicht.any(): F["sieht"][nr] = np.zeros((nz, nu), bool); continue
            xy_g, dep_g = projizieren(F["P_daten"], kc); w = w_mod(dep)
            rot = stimme(FK.S_rot, FK.S_mk, xy[:, 0], xy[:, 1], w, schw["min_kantenpixel"], schw["min_anteil"])
            gelb = stimme(FK.S_gelb, FK.S_fk, xy_g[:, 0] + FK.v[0], xy_g[:, 1] + FK.v[1], w_mod(np.where(np.isfinite(dep_g), dep_g, dep)), schw["min_kantenpixel"], schw["min_anteil"])
            s = sicht.reshape(nz, nu); F["sieht"][nr] = s; F["n_fotos"] += s; F["rot"] += (rot & sicht).reshape(nz, nu); F["gelb"] += (gelb & sicht).reshape(nz, nu)
        del FK
    cl = []; Fje = {}; zq = {}
    for fid, F in FL.items():
        nf = np.maximum(F["n_fotos"], 1); F["rot"] = np.where(F["n_fotos"] > 0, F["rot"] / nf, 0.0).astype(np.float32); F["gelb"] = np.where(F["n_fotos"] > 0, F["gelb"] / nf, 0.0).astype(np.float32)
        gueltig = F["n_fotos"] >= schw["min_fotos"]; fl = F["zelle"] ** 2
        Fje[fid] = dict(F=round(float(((F["gelb"] + F["rot"]) * gueltig).sum() * fl), 4), gelb_m2=round(float((F["gelb"] * gueltig).sum() * fl), 3), rot_m2=round(float((F["rot"] * gueltig).sum() * fl), 3),
                        zellen_sicht=int(gueltig.sum()), flaeche_sicht_m2=round(float(gueltig.sum() * fl), 2), gelb_mittel=round(float(F["gelb"][gueltig].mean()), 4) if gueltig.any() else None,
                        rot_mittel=round(float(F["rot"][gueltig].mean()), 4) if gueltig.any() else None, fotos_je_zelle_median=float(np.median(F["n_fotos"][gueltig])) if gueltig.any() else 0.0)
        for art in ("gelb", "rot"): cl += cluster_finden(F, art, schw, fid, stand_el, F["rest_je_quelle"])
        np.savez_compressed(os.path.join(od, f"{fid}.npz"), n_fotos=F["n_fotos"], rot=F["rot"], gelb=F["gelb"], u0=F["u0"], z1=F["z1"], zelle=F["zelle"],
                            **{f"rest_{q}": v.astype(np.float16) for q, v in F["rest_je_quelle"].items()}, **({"frei": F["frei"]} if F["frei"] is not None else {}))
    cl.sort(key=lambda c: (-c["flaeche_m2"] * c["stimmen"], c["fid"], c["u0"], c["z0"], c["art"]))                     # deterministisch: Gleichstand nach fid, u0, z0
    for i, c in enumerate(cl): c["id"] = i
    Fges = round(sum(v["F"] for v in Fje.values()), 4)
    erg = dict(k=k, schwellen=schw, F=Fges, F_je_flaeche=Fje, cluster=cl, fotos=fotos, versatz=vers, dachquellen=(Q.quellen if Q else {}), dachquellen_fehlen=(Q.fehlt if Q else {}), stl=stl,
               elemente=elemente, restfeld=restfeld_dir, sekunden=round(time.time() - t0, 1),
               luecken="keine Verdeckermaske (nur Embree-Sicht gegen Modell); n_pkt statt Kamerazahl; Dach: dichte Wolke gesperrt (Spec 0b)")
    json.dump(erg, open(os.path.join(od, "cluster.json"), "w"), indent=1, ensure_ascii=False)
    if bilder:
        for fid, F in FL.items():
            if F["n_fotos"].max() > 0 or F["dach"]: bild_schreiben(os.path.join(od, f"{fid}.jpg"), fid, F, [c for c in cl if c["fid"] == fid], schw, Fje[fid])
    log(f"fehlerkarte k{k}: {len(FL)} Flaechen, {len(fotos)} Fotos, {len(cl)} Cluster, F = {Fges} m2  ({time.time() - t0:.0f} s) -> {od}")
    return erg


def bild_schreiben(pfad, fid, F, cl, schw, kenn):
    """Tafeln gelb | rot | rest (Wand: Wolke; Dach: je Quelle) | n_fotos; feste Farbskalen, Legende im Bild, Clusterboxen weiss (gelb) / cyan (rot)."""
    nz, nu = F["n_fotos"].shape
    sk = max(1, min(int(round(360 / max(nz, 1))), int(round(520 / max(nu, 1)))))                          # Pixel je Zelle: Tafel hoechstens ~360 x 520
    g = lambda A: cv2.resize(A, (nu * sk, nz * sk), interpolation=cv2.INTER_NEAREST)
    gueltig = F["n_fotos"] >= schw["min_fotos"]
    def tafel(A, lo, hi, titel, cmap=cv2.COLORMAP_INFERNO, gueltig_noetig=True):
        b = cv2.applyColorMap(np.clip((np.nan_to_num(A) - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8), cmap)
        if gueltig_noetig: b[~gueltig] = 60
        b = g(b); cv2.rectangle(b, (0, 0), (b.shape[1], 20), (0, 0, 0), -1); cv2.putText(b, titel, (3, 14), 0, 0.42, (255, 255, 255), 1)
        return b
    T = [tafel(F["gelb"], 0, 1, f"gelb 0..1 ({schw['min_fotos']}+ Fotos)"), tafel(F["rot"], 0, 1, "rot 0..1", cv2.COLORMAP_VIRIDIS)]
    for q, A in F["rest_je_quelle"].items():
        B = np.where(np.isfinite(A), A, np.nan); b = cv2.applyColorMap(np.clip((np.nan_to_num(B, nan=0.0) + 1.0) / 2.0 * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_JET)
        b[~np.isfinite(B)] = 40; b[np.isfinite(B) & (np.abs(np.nan_to_num(B)) <= schw["rest_tol_m"])] = (255, 255, 255); b = g(b)
        cv2.rectangle(b, (0, 0), (b.shape[1], 20), (0, 0, 0), -1); cv2.putText(b, f"rest {q} -1..+1 m (weiss <= {schw['rest_tol_m']})", (3, 14), 0, 0.42, (255, 255, 255), 1); T.append(b)
    T.append(tafel(F["n_fotos"].astype(float), 0, max(6, int(F["n_fotos"].max())), f"n_fotos 0..{max(6, int(F['n_fotos'].max()))}", cv2.COLORMAP_VIRIDIS, False))
    z = F["zelle"]
    for c in cl:                                                                                                  # Clusterboxen auf gelb (weiss) und rot (cyan)
        x0, x1 = int((c["u0"] - F["u0"]) / z * sk), int((c["u1"] - F["u0"]) / z * sk); y0, y1 = int((F["z1"] - c["z1"]) / z * sk), int((F["z1"] - c["z0"]) / z * sk)
        if c["art"] == "gelb": cv2.rectangle(T[0], (x0, y0), (x1, y1), (255, 255, 255), 1)
        elif c["art"] == "rot": cv2.rectangle(T[1], (x0, y0), (x1, y1), (255, 255, 0), 1)
        else: cv2.rectangle(T[0], (x0, y0), (x1, y1), (0, 0, 255), 1)
    spalten = 2; reihen = [T[i:i + spalten] for i in range(0, len(T), spalten)]
    for r in reihen:
        while len(r) < spalten: r.append(np.zeros_like(T[0]))
    zeilen = [cv2.hconcat(r) for r in reihen]; bild = cv2.vconcat(zeilen)
    kopf = np.zeros((26, bild.shape[1], 3), np.uint8)
    cv2.putText(kopf, f"{fid}{' (Dach)' if F['dach'] else ''}: F = {kenn['F']} m2 (gelb {kenn['gelb_m2']}, rot {kenn['rot_m2']}), Cluster {len(cl)}, Zelle {z} m, grau = < {schw['min_fotos']} Fotos", (3, 17), 0, 0.5, (255, 255, 255), 1)
    cv2.imwrite(pfad, cv2.vconcat([kopf, bild]), [cv2.IMWRITE_JPEG_QUALITY, 85])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("objekt"); ap.add_argument("--karten-dir", required=True, help="Ordner mit <nr>/kostenkarte.npz (und foto_diff_<nr>.json)"); ap.add_argument("--restfeld", required=True, help="restfeld_fassade.py-Ausgabe (mit --dach)")
    ap.add_argument("--aus", required=True); ap.add_argument("--k", type=int, default=0); ap.add_argument("--masken"); ap.add_argument("--stl"); ap.add_argument("--elemente"); ap.add_argument("--freiraum")
    ap.add_argument("--plan"); ap.add_argument("--fotos"); a = ap.parse_args(argv)
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); karten = {os.path.basename(os.path.dirname(p)): p for p in sorted(glob.glob(os.path.join(a.karten_dir, "*", "kostenkarte.npz")))}
    schw = schwellen_laden(json.load(open(a.plan)) if a.plan else None)
    rechnen(objp, obj, karten, a.restfeld, a.aus, a.k, schw, a.stl, a.elemente, a.masken, a.freiraum, a.fotos.split(",") if a.fotos else None)


if __name__ == "__main__":
    main()
