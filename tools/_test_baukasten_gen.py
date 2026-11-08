#!/usr/bin/env python3
"""baukasten_gen.py - GENERISCHER Baukasten-Generator (Plan NULLSTART_GENERALITAET B1): ein Objekt = objekt.json['bauteile'], kein Objektcode.

Jedes Bauteil ist eine Funktion @bauteil("typ"), die ihre Masse NUR aus Daten liest (LoD2/DOM1/Wolkenprofile/Foto-Protokolle in modelle/<obj>/)
und sich mit beleg(seite, element, quelle, **masse) meldet. Reihenfolge der Liste = Bau-Reihenfolge; ein Bauteil darf adds (Koerper) und cuts
(Aussparungen) liefern. Modellrahmen = objekt.json['rahmen'] (x/y lokal, z ueber rahmen.gelaende), STL in mm im Massstab 1:SCALE.

  SCALE=87 ~/.venvs/rcpark/bin/python tools/baukasten_gen.py kaufhaus           (OBJ_DIR=<ordner> ueberschreibt, z. B. im Nullstart)
  objekt.json: "bauteile": [{"typ": "rumpf_lod2"}, ...]   (fehlt die Liste: nur rumpf_lod2)
"""
import os, sys, json, math, numpy as np
TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
from manifold3d import Manifold as M, CrossSection as C, OpType, JoinType
UNION = lambda L: M.batch_boolean(list(L), OpType.Add)

OBJ_DIR = os.environ.get("OBJ_DIR") or (sys.argv[1] if len(sys.argv) > 1 else sys.exit("Aufruf: baukasten_gen.py <objektordner unter modelle/>"))
OD = os.path.join(ROOT, "modelle", OBJ_DIR); OBJ = json.load(open(os.path.join(OD, "objekt.json")))
SCALE = float(os.environ.get("SCALE", OBJ.get("stl_massstab", 87))); K = 1000.0 / SCALE
MINMM = float(os.environ.get("MINMM", "0.8"))                                 # kleinste druckbare Relieftiefe (mm) -> Mindesttiefe in m = MINMM/K
STL_NAME = os.environ.get("STL_NAME") or os.path.basename(OBJ.get("stl", f"modelle/stl/{OBJ_DIR}_1-{SCALE:.0f}.stl"))
OUT = os.path.join(ROOT, "modelle", "stl", STL_NAME)
SEITEN = {k: v for k, v in OBJ.get("seiten_konvention", {}).items() if k in ("+x", "-x", "+y", "-y")}
ELEMENTE = []
def beleg(seite, element, quelle, **masse): ELEMENTE.append(dict(seite=seite, element=element, quelle=quelle, **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in masse.items()}))

BAUTEILE = {}
def bauteil(typ):
    def reg(f): BAUTEILE[typ] = f; return f
    return reg

# ------------------------------------------------------------------ Rahmen / Hilfen
R = OBJ["rahmen"]; C0 = np.array(R["mitte_utm"]); XH = np.array(R["xhat_utm"]); YH = np.array(R["yhat_utm"]); Z0 = float(R["gelaende"])
def lokal(P):
    """UTM (E, N, H) -> Modellrahmen (x, y, z ueber Gelaende)."""
    P = np.asarray(P, float); d = P[:, :2] - C0
    return np.c_[d @ XH, d @ YH, P[:, 2] - Z0]

def ccw(xy):
    xy = np.asarray(xy, float); a = 0.5 * np.sum(xy[:, 0] * np.roll(xy[:, 1], -1) - np.roll(xy[:, 0], -1) * xy[:, 1])
    return xy if a > 0 else xy[::-1]

def flaeche_xy(xy):
    xy = np.asarray(xy, float); return abs(0.5 * np.sum(xy[:, 0] * np.roll(xy[:, 1], -1) - np.roll(xy[:, 0], -1) * xy[:, 1]))

def lod2_flaechen():
    """Flaechen (typ, Nx3 lokal) des eigenen LoD2-Gebaeudes (objekt.json lod2.id) inkl. Gebaeudeteile."""
    import lod2_gebaeude as LG
    picked = LG.extract(OBJ["lod2"]["gml"], center=tuple(C0), radius=60.0)
    eig = [(m, p) for m, p in picked if m.get("id") == OBJ["lod2"]["id"]]
    if not eig: sys.exit(f"LoD2-Gebaeude {OBJ['lod2']['id']} nicht in {OBJ['lod2']['gml']}")
    meta, polys = eig[0]
    return meta, [(t, lokal(P[:-1] if np.allclose(P[0], P[-1]) else P)) for t, P in polys]

def naht_reparieren(k, naht, runden=4):
    """Koerper, die sich nur auf einer Kante beruehren (z. B. Dachflaechen zweier LoD2-Teile an einer Ecke), sind topologisch getrennt, aber
    lagegleich -> im STL nicht wasserdicht. Je lagegleichem Punktpaar ein Klotz 3*naht um die Kante (z-Spanne der Paare). Aendert < naht*1,5 m."""
    for _ in range(runden):
        V = np.asarray(k.to_mesh().vert_properties)[:, :3]; _, inv, cnt = np.unique(V.round(5), axis=0, return_inverse=True, return_counts=True)
        D = V[np.isin(inv.ravel(), np.where(cnt > 1)[0])]
        if not len(D): return k
        kl = []
        for xy in np.unique(D[:, :2].round(3), axis=0):
            z = D[np.all(np.abs(D[:, :2] - xy) < 2e-3, axis=1), 2]; z0, z1 = float(z.min()), float(z.max()); z1 = max(z1, z0 + 3 * naht)
            kl.append(M.cube((3 * naht, 3 * naht, z1 - z0)).translate((xy[0] - 1.5 * naht, xy[1] - 1.5 * naht, z0)))
        k = UNION([k] + kl)
    return k

# ------------------------------------------------------------------ Bauteile
def _im_poly(R, q, rand):
    """Punkt q (xy) im Polygon R oder naeher als rand an dessen Rand (Strahlkreuzung + Kantenabstand)."""
    a, b = R, np.roll(R, -1, 0); ab = b - a; t = np.clip(((q - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
    if np.min(np.linalg.norm(a + ab * t[:, None] - q, axis=1)) <= rand: return True
    c = ((a[:, 1] > q[1]) != (b[:, 1] > q[1])) & (q[0] < a[:, 0] + (q[1] - a[:, 1]) * ab[:, 0] / np.where(ab[:, 1] == 0, 1e-12, ab[:, 1]))
    return bool(c.sum() % 2)

@bauteil("rumpf_lod2")
def rumpf_lod2(cfg, ctx):
    """Rumpf + Dach als EIN Koerper aus LoD2: je Dachflaeche ein Prisma ueber ihrem Grundriss, oben von der Dachebene beschnitten;
    Vereinigung, dann auf den LoD2-Grundriss (GroundSurface) begrenzt. Quelle: LoD2 (amtlich) - sieht keine Aufbauten (Regel 4)."""
    meta, F = lod2_flaechen(); naht = float(cfg.get("naht_m", 0.02))
    dv, fv = float(cfg.get("dach_versatz_m", 0.0)), float(cfg.get("first_versatz_m", 0.0))
    if dv or fv:                                                                                # Korrektur gegen Fotos/Wolke (param_suche.py): LoD2-First liegt z. B. beim Kaufhaus auf Hoehe der Stufengiebel-Spitzen
        if not cfg.get("quelle"): sys.exit("rumpf_lod2: dach_versatz_m/first_versatz_m ohne 'quelle' (Regel 3b)")
        zr = np.concatenate([P[:, 2] for t, P in F if t == "RoofSurface"]); z_lo, z_hi = float(zr.min()), float(zr.max())
        def _neu(P):
            Q = P.copy(); Q[:, 2] = Q[:, 2] + dv + fv * (Q[:, 2] - z_lo) / max(z_hi - z_lo, 1e-6); return Q   # Traufe (z_lo) fest, First (z_hi) um fv, dazwischen anteilig; dv verschiebt alles
        F = [(t, _neu(P) if t == "RoofSurface" else P) for t, P in F]
        beleg("dach", "Dachkorrektur gegen LoD2", cfg["quelle"], dach_versatz_m=dv, first_versatz_m=fv, lod2_traufe_z=z_lo, lod2_first_z=z_hi)
    ek = cfg.get("ebenen_korrektur")                                                            # Ebene 1 Konvergenzschleife (5.11.): Dachflaechen an das Restfeld der Fotowolke
    if ek:                                                                                      # (tools/restfeld_fassade.py -> restfeld_ausgleich.py): passende LoD2-Flaeche (Normale < 5 Grad,
        K_ = json.load(open(ek if os.path.isabs(ek) else os.path.join(OD, ek)))["ebenen"]; n_k = 0; korr_ = []   # Abstand < 1,5 m) senkrecht um (a*v+b)/n_z -> Ebene um a*v+b entlang n; Grundriss bleibt
        def _ek(P):
            c = P.mean(0); _, _, Vt = np.linalg.svd(P - c); nr = Vt[2] if Vt[2][2] > 0 else -Vt[2]
            for E in K_:
                n_ = np.array(E["n"], float)
                if n_[2] > 0.2 and n_ @ nr > np.cos(np.radians(5)) and abs((c - np.array(E["o"])) @ n_) < 1.5:
                    v = (P - np.array(E["o"])) @ np.array(E["e"]); Q = P.copy(); Q[:, 2] += (E["a"] * v + E["b"]) / n_[2]
                    korr_.append((P[:, :2].copy(), nr, c, E)); return Q, 1
            return P, 0
        dz_ = {}                                                                                # Punktverschiebung, nicht Flaechenverschiebung: gemeinsame Punkte (First, Grat) der
        for t, P in F:                                                                          # unbeobachteten Nachbarflaechen ziehen mit (sonst Stufe am First, Foto 004 5.11.)
            if t == "RoofSurface":
                Q, ok = _ek(P); n_k += ok
                if ok:
                    for p_, q_ in zip(P, Q): dz_[tuple(np.round(p_[:2], 2))] = (p_[2], q_[2] - p_[2])
        F2 = []
        for t, P in F:
            if dz_:                                                                             # Punkte, die auf einer korrigierten Dachebene LAGEN (Giebelwand-Oberkanten, Traufpunkte,
                P = P.copy()                                                                    # gemeinsame Firstpunkte), folgen ihr: xy im Flaechengrundriss (+5 cm) und z auf der alten Ebene (+-0,15 m)
                for i_, p_ in enumerate(P):
                    w = dz_.get(tuple(np.round(p_[:2], 2)))
                    if w and abs(w[0] - p_[2]) < 0.05: P[i_, 2] += w[1]; continue
                    if t == "RoofSurface": continue
                    for (pfad, nr_, c_, E) in korr_:
                        if _im_poly(pfad, p_[:2], 0.05):
                            if abs((p_ - c_) @ nr_) < 1.0:
                                v = (p_ - np.array(E["o"])) @ np.array(E["e"]); P[i_, 2] += (E["a"] * v + E["b"]) / np.array(E["n"])[2]; break
                    if os.environ.get('GDEBUG') and t == 'WallSurface' and P[:,2].max()-P[:,2].min()>3: print('WAND', np.round(p_,2), [ (_im_poly(R_, p_[:2], 0.05), round(float(abs((p_ - c_) @ nr_)),2)) for (R_, nr_, c_, E_) in korr_])
            F2.append((t, P))
        F = F2; ctx["dach_korrigiert"] = n_k > 0; print(f"  ebenen_korrektur: {n_k} Dachflaeche(n) an Fotowolke angeglichen")
        beleg("dach", f"Dachflaechen an Fotowolke angeglichen ({n_k})", f"restfeld_fassade.py + restfeld_ausgleich.py {os.path.basename(ek)} (dichte Wolke >= 3 Kameras, Buendelausrichtung amtliche Anker); WIDERSPRUCH zu LoD2 moeglich (Regel 5)", n=n_k)
    boden = [P for t, P in F if t == "GroundSurface"]; dach = [P for t, P in F if t == "RoofSurface"]
    zb = min(float(P[:, 2].min()) for P in boden); zt = max(float(P[:, 2].max()) for P in dach) + 1.0
    g2 = C([ccw(boden[0][:, :2])])
    for P in boden[1:] + [P for P in dach if flaeche_xy(P[:, :2]) >= 0.05]: g2 = g2 + C([ccw(P[:, :2])])   # Grundriss = Boden- UND Dachflaechen-Projektion (LoD2-Bodenringe sind teils luecken-/eckenlos, z. B. Kaufhaus-Anbau)
    g2 = g2.offset(naht, JoinType.Miter).offset(-naht, JoinType.Miter)              # Schliessen: Haarspalte zwischen Gebaeudeteilen (LoD2-Rundung) zu, Aussenkontur unveraendert
    fuss = M.extrude(g2, zt - zb).translate((0, 0, zb))
    teile, n_fl = [], 0
    for P in dach:
        if flaeche_xy(P[:, :2]) < 0.05: continue                                 # senkrechte/entartete Dachflaeche: kein Grundriss
        c = P.mean(0); _, _, Vt = np.linalg.svd(P - c); nrm = Vt[2] if Vt[2][2] > 0 else -Vt[2]
        if nrm[2] < 0.05: continue
        pr = M.extrude(C([ccw(P[:, :2])]).offset(naht, JoinType.Miter), zt - zb).translate((0, 0, zb))
        teile.append(pr.trim_by_plane((-nrm[0], -nrm[1], -nrm[2]), float(-(nrm @ c)))); n_fl += 1
    k = naht_reparieren(UNION(teile) ^ fuss, naht)
    ext = np.vstack(boden)[:, :2]
    beleg("dach", "Rumpf + Dach aus LoD2 (je Dachflaeche Prisma unter der Dachebene, auf Grundriss begrenzt)", f"LoD2 {meta['id']} (LGL BW), {n_fl} Dachflaechen, {len(boden)} Grundflaechen",
          boden_z=zb, first_z=zt - 1.0, x0=float(ext[:, 0].min()), x1=float(ext[:, 0].max()), y0=float(ext[:, 1].min()), y1=float(ext[:, 1].max()))
    ctx["rumpf"] = k; ctx["boden_z"] = zb; ctx["lod2_flaechen"] = F; ctx["grundriss2d"] = g2
    return [k], []

# ------------------------------------------------------------------ Wandrahmen (u entlang der Wand, s nach aussen, z Hoehe)
class Wand:
    """Lokaler Rahmen einer Fassade: Wandlinie a->b (Modell-xy), s = Normale nach AUSSEN (weg von der Grundriss-Mitte), rechtshaendig gehalten."""
    def __init__(self, a, b, mitte):
        a, b = np.asarray(a, float), np.asarray(b, float); self.L = float(np.linalg.norm(b - a)); d = (b - a) / self.L; n = np.array([-d[1], d[0]])
        if (a + 0.5 * (b - a) - np.asarray(mitte)) @ n < 0: n = -n
        self.kipp = (d[0] * n[1] - d[1] * n[0]) < 0                                   # linkshaendig -> Wand von b nach a laufen lassen (u' = L - u)
        if self.kipp: a, d = b, -d
        self.a, self.d, self.n = a, d, n
        self.T = [[d[0], n[0], 0.0, a[0]], [d[1], n[1], 0.0, a[1]], [0.0, 0.0, 1.0, 0.0]]
    def u(self, u): return self.L - u if self.kipp else u
    def setzen(self, k): return k.transform(self.T)
    def seite(self):
        ax = max(((abs(self.n[0]), "+x" if self.n[0] > 0 else "-x"), (abs(self.n[1]), "+y" if self.n[1] > 0 else "-y")))[1]; return ax
    def xy(self, u, s): return self.a + self.d * self.u(u) + self.n * s

def quader(u0, u1, s0, s1, z0, z1):
    u0, u1 = sorted((u0, u1)); return M.cube((u1 - u0, s1 - s0, z1 - z0)).translate((u0, s0, z0))

def prisma_uz(poly_uz, s0, s1):
    """Polygon in der Wandebene (u, z), entlang s von s0 bis s1 extrudiert (ohne Spiegelung: (x,y,z) -> (x, s1 - z, y))."""
    k = M.extrude(C([ccw(poly_uz)]), s1 - s0); return k.transform([[1, 0, 0, 0], [0, 0, -1, s1], [0, 1, 0, 0]])

def segmentbogen(u0, u1, zk, zs, z_unten, n=24):
    """Oeffnung: Rechteck bis Kaempfer zk, darueber Segmentbogen durch (u0,zk), (u1,zk), Scheitel ((u0+u1)/2, zs)."""
    h, w = zs - zk, (u1 - u0) / 2; um = (u0 + u1) / 2
    if h <= 1e-3: return [(u0, z_unten), (u1, z_unten), (u1, zk), (u0, zk)]
    R = (w * w + h * h) / (2 * h); zc = zs - R; a0 = math.atan2(zk - zc, w)
    bog = [(um + R * math.cos(t), zc + R * math.sin(t)) for t in np.linspace(a0, math.pi - a0, n)]
    return [(u0, z_unten), (u1, z_unten)] + bog

def dach_z(F, x, y):
    """Hoechste LoD2-Dachflaeche ueber (x, y) (Modellrahmen) oder None."""
    def innen(Q, x, y):                                                                # Strahltest (gerade Anzahl Kantenschnitte = aussen)
        xs, ys = Q[:, 0], Q[:, 1]; xs2, ys2 = np.roll(xs, -1), np.roll(ys, -1)
        m = (ys > y) != (ys2 > y); xi = xs + (y - ys) * (xs2 - xs) / np.where(ys2 - ys == 0, 1e-12, ys2 - ys)
        return bool(np.sum(m & (x < xi)) % 2)
    best = None
    for t, P in F:
        if t != "RoofSurface" or flaeche_xy(P[:, :2]) < 0.05 or not innen(P[:, :2], x, y): continue
        c = P.mean(0); _, _, Vt = np.linalg.svd(P - c); nr = Vt[2]
        if abs(nr[2]) < 1e-3: continue
        z = c[2] - (nr[0] * (x - c[0]) + nr[1] * (y - c[1])) / nr[2]; best = z if best is None else max(best, z)
    return best

@bauteil("fassade_raster")
def fassade_raster(cfg, ctx):
    """Fassadenelemente aus einem Foto-Raster (modelle/<obj>/<datei>, Pixel eines frontalen Fotos + Massstabskette): Arkade (Segmentboegen),
    Fenster (Felder mit Pfosten), Figuren, Galerie, polygonale Erker mit Konsole + Helm, Gauben auf der LoD2-Dachflaeche. Jeder Abschnitt optional;
    Anzahlen kommen aus den Zaehlprotokollen im Raster (Regel 9), Tiefen aus der Datei (Quelle dort)."""
    R_ = json.load(open(os.path.join(OD, cfg["datei"]))); ms = R_["massstab"]; k = float(ms["px_pro_m"]); zs0 = float(ms.get("z_strasse", 0.0))
    U = lambda x: (x - ms["x0_px"]) / k; Z = lambda y: (ms["y0_px"] - y) / k + zs0
    F = ctx["lod2_flaechen"]; mitte = np.vstack([P for t, P in F if t == "GroundSurface"])[:, :2].mean(0)
    W = Wand(R_["wand"]["a"], R_["wand"]["b"], mitte); se = W.seite(); T = R_.get("tiefen", {}); adds, cuts = [], []
    q = f"Foto {R_['foto']} ({cfg['datei']})"; ohne = set(cfg.get("ohne_abschnitte", []))                       # qualitaetsstufen: einzelne Abschnitte durch die Automatik ersetzen
    def setze(lst, kk): lst.append(W.setzen(kk))
    if "traufe" in R_ and "traufe" not in ohne:                                                                                  # Traufueberstand: LoD2-Dachebene ueber die Wand hinaus verlaengert, bis sie die Rinnenhoehe am Foto erreicht
        Tr = R_["traufe"]; zr_ = Z(Tr["rinne_y"]); n_seg = 8; dicke = float(Tr.get("dicke_m", 0.25)); es = []
        for i in range(n_seg):
            u0, u1 = W.L * i / n_seg, W.L * (i + 1) / n_seg; pts = []
            for uu in (u0 + 0.01, u1 - 0.01):
                z0, z1 = dach_z(F, *W.xy(uu, -0.05)), dach_z(F, *W.xy(uu, -1.05))
                if z0 is None or z1 is None: break
                sl = z1 - z0; e = max(0.0, (z0 - zr_) / sl) if sl > 0.05 else 0.0; es.append(e)
                pts += [(uu, -0.6, z0 + 0.6 * sl), (uu, e, z0 - e * sl)]
            if len(pts) < 4: continue
            pts += [(x_, y_, z_ - dicke) for x_, y_, z_ in pts]; setze(adds, M.hull_points(pts))
        if es: beleg(se, f"Traufueberstand: Dachebene bis zur Rinne {zr_:.2f} m verlaengert, Ueberstand {np.median(es):.2f} m", f"{q}: Rinne (M-018-001); Dachneigung LoD2; {Tr.get('quelle', '')}", rinne=zr_, ueberstand=float(np.median(es)))
    if "arkade" in R_ and "arkade" not in ohne:
        A = R_["arkade"]; pf = A["pfeiler_px"]; zk, zs = Z(A["kaempfer_y"]), Z(A["scheitel_y"]); t = float(T.get("arkade_m", 3.0))
        for (_, r0), (l1, _) in zip(pf[:-1], pf[1:]):
            u0, u1 = sorted((W.u(U(r0)), W.u(U(l1)))); setze(cuts, prisma_uz(segmentbogen(u0, u1, zk, zs, zs0 - 1.0), -t, 0.3))
        beleg(se, f"Arkade: {len(pf) - 1} Segmentboegen, Kaempfer {zk:.2f} m, Scheitel {zs:.2f} m, Tiefe {t:.1f} m", f"{q}, Zaehlung {A['zaehlung']}; {A['quelle']}; Tiefe: {T.get('quelle', 'ANNAHME')}",
              n=len(pf) - 1, kaempfer=zk, scheitel=zs, tiefe=t)
    if "fenster" in R_ and "fenster" not in ohne:
        Fe = R_["fenster"]; z0, z1 = Z(Fe["bruestung_y"]), Z(Fe["sturz_y"]); nf = int(Fe.get("felder", 1)); pfo = float(Fe.get("pfosten_m", 0.1)); t = float(T.get("fenster_nische_m", 0.2))
        for x0, x1 in Fe["x_px"]:
            u0, u1 = sorted((W.u(U(x0)), W.u(U(x1)))); b = (u1 - u0 - (nf - 1) * pfo) / nf
            for i in range(nf): setze(cuts, quader(u0 + i * (b + pfo), u0 + i * (b + pfo) + b, -t, 0.3, z0, z1))
        beleg(se, f"Fenster: {len(Fe['x_px'])} Stueck, je {nf} Felder, Bruestung {z0:.2f} / Sturz {z1:.2f} m, Nische {t:.2f} m", f"{q}, Zaehlung {Fe['zaehlung']}; {Fe['quelle']}; Nische ANNAHME",
              n=len(Fe["x_px"]), unten=z0, oben=z1)
    if "figuren" in R_ and "figuren" not in ohne:
        Fg = R_["figuren"]; zs_, zf, zb_ = Z(Fg["sockel_y"]), Z(Fg["figur_oben_y"]), Z(Fg["baldachin_oben_y"]); b = Fg["breite_px"] / k
        for x in Fg["x_px"]:
            u = W.u(U(x)); setze(adds, quader(u - 0.35, u + 0.35, -0.05, 0.4, zs_ - 0.35, zs_))
            setze(adds, M.cylinder(zf - zs_, b * 0.75, b * 0.6, 24).translate((u, 0.22, zs_)))
            setze(adds, quader(u - 0.35, u + 0.35, -0.05, 0.4, zf + 0.05, zb_))
        beleg(se, f"Figuren: {len(Fg['x_px'])} auf Konsole mit Baldachin, Figur {zs_:.2f}-{zf:.2f} m", f"{q}, Zaehlung {Fg['zaehlung']}; {Fg['quelle']}; Figur als Kegelstumpf (ANNAHME Detailgrad H0)",
              n=len(Fg["x_px"]))
    if "galerie" in R_ and "galerie" not in ohne:
        G = R_["galerie"]; u0, u1 = sorted((W.u(U(G["x_px"][0])), W.u(U(G["x_px"][1])))); zu, zh = Z(G["unten_y"]), Z(G["handlauf_y"]); t = float(T.get("galerie_m", 0.7))
        setze(adds, quader(u0, u1, -0.1, t, zu, zu + 0.22))                                             # Platte
        setze(adds, quader(u0, u1, t - 0.12, t, zu + 0.22, zh))                                        # Bruestung (Docken als volle Bruestung, H0)
        for uu in (u0, u1 - 0.12): setze(adds, quader(uu, uu + 0.12, -0.1, t, zu + 0.22, zh))
        beleg(se, f"Galerie: Platte {zu:.2f} m, Handlauf {zh:.2f} m, Vorsprung {t:.2f} m, Laenge {u1 - u0:.1f} m", f"{q}; {G['quelle']}; Vorsprung: {T.get('quelle', 'ANNAHME')}; Docken als volle Bruestung (ANNAHME H0)",
              unten=zu, oben=zh, vorsprung=t)
    if "erker" in R_ and "erker" not in ohne:
        E = R_["erker"]; p = float(T.get("erker_m", 0.8)); zb_, zk_, zg = Z(E["brustung_unten_y"]), Z(E["konsole_unten_y"]), Z(E["gesims_y"]); ue = float(E.get("helm_fuss_ueberstand_m", 0.2))
        for i, ((x0, x1), (f0, f1)) in enumerate(zip(E["x_px"], E["frontfacette_px"])):
            us = sorted((W.u(U(x0)), W.u(U(x1)))); fs = sorted((W.u(U(f0)), W.u(U(f1)))); uc = 0.5 * (us[0] + us[1])
            poly = [(us[0], -0.02), (us[1], -0.02), (fs[1], p), (fs[0], p)]                              # Rueckseite 2 cm hinter der Fassade (keine Einbindekanten parallel zur Normalen: die schnitten Eck-Seitenwaende fast deckungsgleich -> Splitter)
            koerper = M.extrude(C([ccw(poly)]), zg - zb_).translate((0, 0, zb_)); setze(adds, koerper)
            pin = np.asarray(C([ccw(poly)]).offset(-0.04, JoinType.Miter).to_polygons()[0])           # Konsole oben 4 cm eingerueckt: keine deckungsgleichen Seitenflaechen mit dem Erkerkoerper
            pk = [(x, y, zb_ + 0.06) for x, y in pin] + [(uc + dx, 0.15 + dy, zk_) for dx in (-0.2, 0.2) for dy in (-0.15, 0.15)]   # 6 cm in den Koerper (keine deckungsgleichen Flaechen)
            setze(adds, M.hull_points(pk))                                                              # Konsole: Huelle Erkerboden -> Spitze ueber dem Eckpfeiler
            hs = Z(E["helm_spitze_y"][i] if isinstance(E["helm_spitze_y"], list) else E["helm_spitze_y"])
            base = [(us[0] - ue, -0.06), (us[1] + ue, -0.06), (fs[1] + ue * 0.6, p + ue), (fs[0] - ue * 0.6, p + ue)]
            setze(adds, M.hull_points([(x, y, zg - 0.06) for x, y in base] + [(x, y, zg + 0.15) for x, y in base] + [(uc, p * 0.35, hs)]))   # Helm: Pyramide ueber dem Erker
        beleg(se, f"Eckerker: {len(E['x_px'])} polygonal (Schraege-Front-Schraege), Vorsprung {p:.2f} m, Koerper {zb_:.2f}-{zg:.2f} m, Konsole bis {zk_:.2f} m, Helm bis {Z(min(E['helm_spitze_y'])):.1f} m",
              f"{q}, Zaehlung {E['zaehlung']}; {E['quelle']}; Vorsprung: {T.get('quelle', 'ANNAHME')}", n=len(E["x_px"]), vorsprung=p)
    if "gauben" in R_ and "gauben" not in ohne:
        Ga = R_["gauben"]; ka = R_["kamera"]; D = float(ka["abstand_m"]); cx, cy = ka["bildmitte_px"]; h_auge = Z(cy); w, hh, tg = Ga["breite_m"], Ga["hoehe_m"], Ga["tiefe_m"]; n_g = 0
        for rh in Ga["reihen"]:
            zbild = Z(rh["y_px"])
            for x in rh["x_px"]:
                best = None
                for dd in np.arange(0.0, 9.0, 0.05):                                                   # Bildhoehe eines Dachpunkts in d hinter der Wand: h + (z(d) - h) * D / (D + d)
                    uu = W.u(U(cx) + (x - cx) / k * (D + dd) / D); xy = W.xy(uu, -dd); zr = dach_z(F, *xy)
                    if zr is None: continue
                    e = abs(h_auge + (zr - h_auge) * D / (D + dd) - zbild)
                    if best is None or e < best[0]: best = (e, dd, uu, zr)
                if best is None: continue
                _, dd, uu, zr = best; print(f"    Gaube x={x}px: u {uu:.2f} m, {dd:.2f} m hinter der Wand, Dach z {zr:.2f} m (Bildrest {best[0]:.2f} m)")
                setze(adds, quader(uu - w / 2, uu + w / 2, -dd - tg, -dd, zr - 0.4, zr + hh))
                setze(adds, prisma_uz([(uu - w / 2 - 0.08, zr + hh), (uu + w / 2 + 0.08, zr + hh), (uu, zr + hh + 0.45)], -dd - tg, -dd + 0.1)); n_g += 1
        beleg("dach", f"Gauben Nordseite: {n_g} in {len(Ga['reihen'])} Reihen ({'+'.join(str(len(r['x_px'])) for r in Ga['reihen'])}), auf der LoD2-Dachflaeche", f"{q}, Zaehlung {', '.join(Ga['zaehlung'])}; {Ga['quelle']}", n=n_g)
    return adds, cuts

@bauteil("treppengiebel")
def treppengiebel(cfg, ctx):
    """Treppengiebel an beiden Enden des Hauptdachs (Satteldach mit dem hoechsten First): Giebelwaende = LoD2-Waende mit schraeger Oberkante, Normale ~ Firstrichtung;
    je Flanke n Stufen (Zaehlprotokoll, Regel 9) zwischen Traufe und First, Stufenoberkante = Dachlinie an der inneren Stufenkante + Kappe, Spitze ueber dem First.
    Geometrie: (Wandscheibe, nach innen 'dicke_m') geschnitten mit Stufenbaendern quer zum First."""
    F = ctx["lod2_flaechen"]; dach = [P for t, P in F if t == "RoofSurface" and flaeche_xy(P[:, :2]) > 1.0]
    zf = max(float(P[:, 2].max()) for P in dach); haupt = [P for P in dach if P[:, 2].max() > zf - 0.05]
    top = np.vstack([P[P[:, 2] > zf - 0.05] for P in haupt]); _, _, Vt = np.linalg.svd(top[:, :2] - top[:, :2].mean(0)); r = Vt[0] / np.linalg.norm(Vt[0]); pr = np.array([-r[1], r[0]])
    f0 = top[:, :2].mean(0)                                                                          # Punkt auf dem First
    sl = []; sl_s = {}                                                                               # Neigung je Dachseite (5.11.: Dachflaechen einzeln an die Fotowolke angeglichen -> asymmetrisch)
    for P in haupt:
        c = P.mean(0); _, _, V2 = np.linalg.svd(P - c); nn = V2[2] if V2[2][2] > 0 else -V2[2]; sl.append(math.hypot(nn[0], nn[1]) / nn[2])
        sl_s.setdefault(1 if (c[:2] - f0) @ pr > 0 else -1, []).append(sl[-1])
    slope = float(np.median(sl)); sl_s = {k: float(np.median(v)) for k, v in sl_s.items()} if ctx.get("dach_korrigiert") else {}; slq = lambda q: np.where(q > 0, sl_s.get(1, slope), sl_s.get(-1, slope)); n_st = int(cfg["stufen_je_flanke"]); dk, kp, sp = float(cfg.get("dicke_m", 0.6)), float(cfg.get("kappe_m", 0.35)), float(cfg.get("spitze_m", 1.0))
    mitte = np.vstack([P for t, P in F if t == "GroundSurface"])[:, :2].mean(0); adds = []; n_w = 0; giebel = {}
    for t, P in F:
        if t != "WallSurface": continue
        hi = P[P[:, 2] > P[:, 2].min() + 0.5]
        if len(hi) < 2 or hi[:, 2].max() - hi[:, 2].min() < 1.0: continue                         # Oberkante nicht schraeg -> keine Giebelwand
        e = P[:, :2].max(0) - P[:, :2].min(0); lo = P[P[:, 2] < P[:, 2].min() + 0.3][:, :2]
        if len(lo) < 2: continue
        a_, b_ = lo[np.argmin(lo @ pr)], lo[np.argmax(lo @ pr)]
        if np.linalg.norm(b_ - a_) < 0.5: continue
        d_ = (b_ - a_) / np.linalg.norm(b_ - a_)
        if abs(d_ @ pr) < 0.7: continue                                                              # Wand muss quer zum First laufen
        nin = np.array([-d_[1], d_[0]]); nin = nin if (mitte - a_) @ nin > 0 else -nin
        qh = (hi[:, :2] - f0) @ pr
        if np.median(np.abs(hi[:, 2] - (zf - slq(qh) * np.abs(qh)))) > 0.6: continue                  # Oberkante liegt nicht auf der Hauptdachlinie (Anbau-Giebel)
        aa, bb = a_ + nin * 0.02 + d_ * 0.03, b_ + nin * 0.02 - d_ * 0.03                            # 2 cm HINTER die Wandebene, Enden 3 cm eingerueckt: keine deckungsgleichen Flaechen, keine Splitter ausserhalb des Rumpfs (0,2 mm bei H0)
        ende = 1 if ((a_ + b_) / 2 - f0) @ r > 0 else -1                                               # welches Firstende
        gr = giebel.setdefault(ende, dict(poly=None, qs=[]))
        cs = C([ccw(np.array([aa, bb, bb + nin * dk, aa + nin * dk]))]); gr["poly"] = cs if gr["poly"] is None else gr["poly"] + cs
        gr["qs"] += [((a_ - f0) @ pr), ((b_ - f0) @ pr)]; gr.setdefault("wand", (a_, d_)); n_w += 1
    T_ = [[r[0], pr[0], 0, f0[0]], [r[1], pr[1], 0, f0[1]], [0, 0, 1, 0]]; tw = float(cfg.get("spitze_breite_m", 1.0)) / 2
    for ende, gr in giebel.items():                                                                   # je Giebel EINE Scheibe (Wandstuecke vereint), Stufen einmal geschnitten
        z_s = ctx["boden_z"] + 1.0                                                                   # Scheibe tief im Rumpf beginnen (Unterkante auf Traufhoehe beruehrte Rumpfkanten -> Splitter)
        g_ = gr["poly"].offset(0.01, JoinType.Miter).offset(-0.01, JoinType.Miter) ^ ctx["grundriss2d"].offset(-0.01, JoinType.Miter)   # nur innerhalb des Grundrisses
        scheibe = M.extrude(g_, zf + sp + 1.0 - z_s).translate((0, 0, z_s))
        if os.environ.get('GDEBUG'): print('GIEBEL', ende, [round(q,2) for q in gr['qs']], sl_s, round(slope,3), round(zf,2))
        for sgn in (-1, 1):
            qmax = max([q * sgn for q in gr["qs"]] + [0.0])
            if qmax <= tw: continue
            grenzen = np.linspace(qmax + 0.05, tw, n_st + 1)
            for k in range(n_st):
                qa, qb = grenzen[k + 1], grenzen[k]; zt = zf - float(slq(sgn)) * qa + kp
                band = M.cube((400, qb - qa + 0.01, zt)).translate((-200, qa if sgn > 0 else -qb - 0.01, 0))   # 1 cm Ueberlappung zur Nachbarstufe
                adds.append(scheibe ^ band.transform(T_))
        adds.append(scheibe ^ M.cube((400, 2 * tw, zf + sp)).translate((-200, -tw, 0)).transform(T_))
    adds = [k_ for k_ in adds if not k_.is_empty()]
    flanken = []                                                                                      # Flankenlinien (Traufe -> Spitze, Wandebene) fuer giebel_stufen_zaehlen.py: Stufen AM FOTO zaehlen (Regel 9)
    for ende, gr in giebel.items():
        a0, d0 = gr["wand"]
        for sgn in (-1, 1):
            qmax = max([q * sgn for q in gr["qs"]] + [0.0])
            if qmax <= tw: continue
            pts = []
            for q in (qmax, tw):
                s_ = ((f0 + pr * q * sgn) - a0) @ pr / max(1e-6, d0 @ pr); xy = a0 + d0 * s_; pts.append([round(float(xy[0]), 3), round(float(xy[1]), 3), round(float(zf - float(slq(sgn)) * q), 3)])
            flanken.append(dict(ende=int(ende), seite=int(sgn), linie=pts))
    beleg("dach", f"Treppengiebel: {len(giebel)} Giebel ({n_w} LoD2-Wandstuecke), je {n_st} Stufen je Flanke + Spitze, Kappe {kp:.2f} m, Spitze {sp:.1f} m ueber First, Scheibe {dk:.2f} m",
          f"Stufenzahl: {', '.join(cfg.get('zaehlung', []))} (Regel 9); Giebelwaende/First/Neigung LoD2; Kappe/Spitze/Dicke {cfg.get('quelle', 'ANNAHME')}", n=n_st, flanken=flanken, first_z=round(float(zf), 3), kappe_m=kp, spitze_m=sp)
    return adds, []

@bauteil("fassade_auto")
def fassade_auto(cfg, ctx):
    """Fassadenelemente VOLLAUTOMATISCH aus tools/fassade_parsing.py (elemente.json: OWLv2 auf den Einzelfoto-Orthobildern von fassade_ortho.py,
    Abstimmung ueber die Fotos, Reihenregel). Masse in Metern im Modellrahmen (Wandebene o + u*d, Normale n nach aussen), keine Handablesung.
    cfg: datei (Pfad, absolut oder relativ zum Objektordner), klassen (Liste: bogen, fenster, tuer, figur, balkon, gaube), mind_stimmen,
    nische_m / bogen_tiefe_m / figur_vorsprung_m / balkon_vorsprung_m / gauben_tiefe_m: Tiefen = ANNAHME (Fotos sehen keine Tiefe), Stufe 'parameter' sucht sie."""
    p = cfg["datei"]; p = p if os.path.isabs(p) else os.path.join(OD, p); E = json.load(open(p)); kl = set(cfg.get("klassen", ["bogen", "fenster"]))
    ms = int(cfg.get("mind_stimmen", 2)); t_n = float(cfg.get("nische_m", 0.25)); t_b = float(cfg.get("bogen_tiefe_m", 3.0)); t_f = float(cfg.get("figur_vorsprung_m", 0.35))
    t_g = float(cfg.get("balkon_vorsprung_m", 0.7)); g_t = float(cfg.get("gauben_tiefe_m", 1.2)); F = ctx["lod2_flaechen"]; adds, cuts = [], []; z_boden = ctx["boden_z"] - 1.0
    # Formparameter (Stufe 3 sucht sie gegen die Fotos; Standard = Erkennerkasten unveraendert): Massstab/Versatz in Fassadenrichtung (prueft den
    # Achsmass-Widerspruch Hand 3,07 / Automatik 2,84 m), Fensterfelder + Pfosten, Kasteneinzug (Erkennerkaesten umfassen Gewaende), Kaempferversatz
    sk = float(cfg.get("skala_u", 1.0)); vu = float(cfg.get("versatz_u_m", 0.0)); nf = max(1, int(round(float(cfg.get("felder", 1))))); pfo = float(cfg.get("pfosten_m", 0.12))
    ez_u = float(cfg.get("fenster_einzug_m", 0.0)); ez_z = float(cfg.get("fenster_einzug_z_m", 0.0)); kv = float(cfg.get("bogen_kaempfer_versatz_m", 0.0)); be = float(cfg.get("bogen_einzug_m", 0.0))
    q = f"fassade_parsing {os.path.basename(os.path.dirname(p))}/{os.path.basename(p)} ({E.get('modell', '?')}, {E.get('lizenz', '')})"
    nur = cfg.get("fassaden")                                                                         # None = alle Fassaden der Datei
    tg = bool(cfg.get("tiefen_gemessen", True)); n_gem = 0                                             # tiefe_m je Element (freiraum_oeffnungen.py) benutzen
    for fid, Fa in E["fassaden"].items():
        if nur is not None and fid not in nur: continue
        n = np.array(Fa["n"], float); d = -np.array(Fa["d"], float); o = np.array(Fa["o"], float)       # d' = -d: rechtshaendiger Rahmen (u' = -u)
        T = [[d[0], n[0], 0.0, o[0]], [d[1], n[1], 0.0, o[1]], [0.0, 0.0, 1.0, 0.0]]; se = max(((abs(n[0]), "+x" if n[0] > 0 else "-x"), (abs(n[1]), "+y" if n[1] > 0 else "-y")))[1]
        L = [e for e in Fa["elemente"] if e["klasse"] in kl and e["stimmen"] >= ms]; zahl = {}; n_gem = 0
        ext_ = []                                                                                    # Wandausdehnung aus dem Grundriss (Kanten in der Fassadenebene, < 0,5 m): Schnitte enden
        for R_ in ctx["grundriss2d"].to_polygons():                                                  # eckpfeiler_m vor der Hausecke (5.11.: Ostbogen f00 ragte 0,2 m ueber die Ecke ->
            R_ = np.asarray(R_)                                                                       # Luecke in der Front, Foto 004/040 rot); ANNAHME Mindestpfeiler 0,3 m
            for a_, b_ in zip(R_, np.roll(R_, -1, 0)):
                if abs((a_ - o) @ n) < 0.5 and abs((b_ - o) @ n) < 0.5: ext_ += [float((a_ - o) @ d), float((b_ - o) @ d)]
        ep_ = float(cfg.get("eckpfeiler_m", 0.3)); n_kl = 0; boegen_ = []
        for e in L:
            u0, u1 = sorted((-(e["u1"] * sk + vu), -(e["u0"] * sk + vu))); z0, z1 = e["z0"], e["z1"]; k = e["klasse"]
            if ext_ and ep_ > 0 and k in ("bogen", "oeffnung", "tuer", "fenster"):
                c0, c1 = max(u0, min(ext_) + ep_), min(u1, max(ext_) - ep_)
                if c1 - c0 < 0.3: continue
                n_kl += (c0, c1) != (u0, u1); u0, u1 = c0, c1
            tm_ = float(e["tiefe_m"]) if tg and e.get("tiefe_m") else None; n_gem += tm_ is not None   # gemessene Tiefe (freiraum_oeffnungen.py, Sichtstrahlen) statt ANNAHME
            if k == "bogen":
                u0, u1 = u0 + be, u1 - be; zk = min(z1 - 0.05, (e.get("kaempfer") or (z1 - 0.3 * (u1 - u0))) + kv); cuts.append(prisma_uz(segmentbogen(u0, u1, zk, z1, z_boden), -(tm_ or t_b), 0.3).transform(T))
                boegen_.append((u0, u1, zk, z1, tm_ or t_b, e.get("reihe", 0)))
            elif k == "oeffnung":                                                                     # Freiraumfeld ab Boden ohne erkanntes Element (Durchgang): Rechteck, Tiefe gemessen
                cuts.append(quader(u0, u1, -(tm_ or t_b), 0.3, z_boden if z0 < 2.5 else z0, z1).transform(T))
            elif k in ("fenster", "tuer"):
                if e.get("in_bogen"): continue                                                        # liegt auf der Arkaden-Rueckwand, nicht in der Frontebene
                if k == "tuer": cuts.append(quader(u0, u1, -(tm_ or t_n), 0.3, z_boden, z1).transform(T))
                else:
                    u0, u1, z0, z1 = u0 + ez_u, u1 - ez_u, z0 + ez_z, z1 - ez_z
                    if u1 - u0 < 0.2 or z1 - z0 < 0.2: continue
                    nf_ = max(1, int(e.get("felder", nf))) if cfg.get("felder_aus_foto", True) else nf   # Felder AM FOTO gezaehlt (fassade_parsing.felder_zaehlen, Regel 9), sonst cfg
                    b = (u1 - u0 - (nf_ - 1) * pfo) / nf_
                    if b < 0.1: b, nf_ = u1 - u0, 1
                    for i in range(nf_): cuts.append(quader(u0 + i * (b + pfo), u0 + i * (b + pfo) + b, -(tm_ or t_n), 0.3, z0, z1).transform(T))
            elif k == "figur":
                um = 0.5 * (u0 + u1); b = max(0.2, u1 - u0); adds.append(M.cylinder(z1 - z0, b * 0.45, b * 0.35, 24).translate((um, t_f * 0.6, z0)).transform(T))
                adds.append(quader(um - b * 0.6, um + b * 0.6, -0.05, t_f, z0 - 0.25, z0).transform(T))
            elif k == "balkon":
                adds.append(quader(u0, u1, -0.1, t_g, z0, z0 + 0.22).transform(T)); adds.append(quader(u0, u1, t_g - 0.12, t_g, z0 + 0.22, z1).transform(T))
            elif k == "gaube":
                best = None
                for dd in np.arange(0.0, 12.0, 0.1):                                                  # Gaubenfront dort, wo die LoD2-Dachflaeche die Gauben-Unterkante erreicht
                    xy = o + d * (0.5 * (u0 + u1)) - n * dd; zr = dach_z(F, *xy)
                    if zr is not None and abs(zr - z0) < (best[0] if best else 1e9): best = (abs(zr - z0), dd)
                if best is None or best[0] > 0.6: continue
                dd = best[1]; adds.append(quader(u0, u1, -dd - g_t, -dd, z0 - 0.4, z1 - 0.3).transform(T))
                adds.append(prisma_uz([(u0 - 0.08, z1 - 0.3), (u1 + 0.08, z1 - 0.3), (0.5 * (u0 + u1), z1)], -dd - g_t, -dd + 0.1).transform(T))
            zahl[k] = zahl.get(k, 0) + 1
        halle_ = ""                                                                                   # Arkade/Laubengang (5.11., Nutzer: "nur mehrere Tunnel ins Gebaeude"): >= 2 Boegen einer Reihe mit
        for r_ in sorted({b_[5] for b_ in boegen_}):                                                  # Pfeilern < pfeiler_max_m dazwischen -> EIN Hallenraum hinter den Pfeilern statt Tunneln
            B_ = sorted([b_ for b_ in boegen_ if b_[5] == r_]); gaps = [B_[i + 1][0] - B_[i][1] for i in range(len(B_) - 1)]
            if len(B_) < 2 or not cfg.get("arkadenhalle", True) or max(gaps) > float(cfg.get("pfeiler_max_m", 1.5)) or min(gaps) <= 0: continue
            tp = float(cfg.get("pfeiler_tiefe_m") or np.median(gaps)); tief = min(b_[4] for b_ in B_); top = min(b_[3] for b_ in B_)
            if tief <= tp + 0.3: continue
            cuts.append(quader(B_[0][0], B_[-1][1], -tief, -tp, z_boden, top).transform(T))
            halle_ += f"; Arkadenhalle Reihe {r_}: {len(B_)} Boegen, Pfeiler {min(gaps):.2f}-{max(gaps):.2f} m breit, Pfeilertiefe {tp:.2f} m (ANNAHME quadratisch = Median Pfeilerbreite), Halle bis Scheitel {top:.2f} m (ANNAHME Gewoelbe ~ Bogenscheitel), Tiefe {tief:.2f} m gemessen"
        if zahl:
            beleg(se, f"Fassade {fid} automatisch: " + ", ".join(f"{v} {k}" for k, v in sorted(zahl.items())),
                  f"{q}; Zaehlung am Foto (Erkenner auf {len(Fa.get('fotos', []))} Fotos, >= {ms} Stimmen); Form: Massstab {sk:.3f}, Versatz {vu:.2f} m, {nf} Felder/Pfosten {pfo:.2f}, Einzug {ez_u:.2f}/{ez_z:.2f}, Kaempfer {kv:+.2f}; "
                  + (f"Tiefen GEMESSEN fuer {n_gem} Elemente (freiraum_oeffnungen.py, Sichtstrahlen >= 3 Kameras), sonst " if n_gem else "") + f"Tiefen ANNAHME (Nische {t_n}, Bogen {t_b}, Figur {t_f}, Balkon {t_g}, Gaube {g_t} m)" + (f"; {n_kl} Schnitte auf Wand minus Eckpfeiler {ep_} m (ANNAHME) gekuerzt" if n_kl else "") + halle_,
                  **{f"n_{k}": v for k, v in zahl.items()})
    return adds, cuts

BAUTEILE["fassade_vorbau"] = fassade_auto                                                          # Erker-/Vorbaufenster: fassade_auto auf den Vorbauflaechen (qualitaetsstufen vorbau_fenster)

@bauteil("relief_wolke")
def relief_wolke(cfg, ctx):
    """Fassadenrelief aus der dichten SfM-Wolke (tools/fassade_relief.py -> relief.json): je Fassade gestufte Vorspruenge (adds, s0..s1 vor der
    Wandebene) und Ruecksprunge (cuts, Wandebene..-L) als Prismen ueber Polygonen (u, z) mit Loechern. Keine Bauteilklasse noetig (Erker, Galerie,
    Figuren, Arkaden kommen als Relief). cfg: datei, fassaden (Liste oder None), vor (bool), zurueck (bool), max_vor_m / max_tief_m (Kappung),
    faktor_tiefe (Skalierung der Tiefen, Standard 1). Tiefen = Wolke (Quelle), Massstab = Buendelkameras."""
    p = cfg["datei"]; p = p if os.path.isabs(p) else os.path.join(OD, p); E = json.load(open(p)); nur = cfg.get("fassaden"); adds, cuts = [], []
    fk = float(cfg.get("faktor_tiefe", 1.0)); mv = float(cfg.get("max_vor_m", 1.5)); mt = float(cfg.get("max_tief_m", 5.0)); zahl = {}
    for fid, Fa in E["fassaden"].items():
        if nur is not None and fid not in nur: continue
        n = np.array(Fa["n"], float); d = -np.array(Fa["d"], float); o = np.array(Fa["o"], float)
        T = [[d[0], n[0], 0.0, o[0]], [d[1], n[1], 0.0, o[1]], [0.0, 0.0, 1.0, 0.0]]; nv = nz_ = 0
        for S in Fa["stufen"]:
            vor = S["s1"] > 0
            if (vor and not cfg.get("vor", True)) or (not vor and not cfg.get("zurueck", True)): continue
            s0, s1 = sorted((S["s0"] * fk, S["s1"] * fk))
            if vor and s0 >= mv: continue
            if not vor and -s1 >= mt: continue
            kont = []
            for P_ in S["polys"]:
                Q = np.array([(-uu, zz) for uu, zz in P_["uz"]], float); Q = ccw(Q)                 # u' = -u (rechtshaendig), Loecher umgekehrt
                kont.append(Q[::-1] if P_["loch"] else Q)
            if not kont: continue
            cs = C([k_.tolist() for k_ in kont])
            if cs.is_empty(): continue
            if vor: a0, a1 = s0 - 0.02, min(s1, mv)                                                  # 2 cm in die Wand (keine deckungsgleichen Flaechen)
            else: a0, a1 = max(s0, -mt), (0.3 if abs(s1) < 1e-6 else s1 + 0.02)                      # Stufe -L..-(L-stufe); erste Stufe bis vor die Wand offen
            k_ = M.extrude(cs, a1 - a0).transform([[1, 0, 0, 0], [0, 0, -1, a1], [0, 1, 0, 0]])     # (u, z) -> (u, s, z), s von a0 bis a1
            (adds if vor else cuts).append(k_.transform(T)); nv += vor; nz_ += (not vor)
        if nv or nz_:
            se = max(((abs(n[0]), "+x" if n[0] > 0 else "-x"), (abs(n[1]), "+y" if n[1] > 0 else "-y")))[1]; zahl[fid] = (nv, nz_)
            beleg(se, f"Fassade {fid} Relief aus Wolke: {nv} Vorsprung-, {nz_} Ruecksprungstufen", f"fassade_relief.py {os.path.basename(p)} (Wolke {os.path.basename(E.get('wolke', '?'))}, Stufe {E['parameter']['stufe']} m); Tiefenfaktor {fk}")
    return adds, cuts

@bauteil("bloecke_wolke")
def bloecke_wolke(cfg, ctx):
    """Vorbauten aus den Relief-BLOECKEN der dichten Wolke (fassade_relief.py --block-*, 2026-11-05): zusammenhaengende Vorsprungflaechen je Fassade
    (u, z, Tiefe P90). Form nach Seitenverhaeltnis, keine Bauteilklasse vom Erkenner noetig:
      hoch (h >= hoch_faktor * b) -> Erker: Trapez (Front = front_anteil * Breite, ANNAHME), Konsole bis konsole_m unter den Block, Helm als Pyramide helm_m hoch
      breit (b >= breit_faktor * h) -> Galerie: Platte 0,22 m + volle Bruestung (H0), Seitenwangen
      sonst -> Quader.
    Tiefe = Block-P90 * faktor_tiefe (Wolke = Quelle). cfg: datei, fassaden, faktor_tiefe, front_anteil, konsole_m, helm_m, hoch_faktor, breit_faktor."""
    p = cfg["datei"]; p = p if os.path.isabs(p) else os.path.join(OD, p); E = json.load(open(p)); nur = cfg.get("fassaden"); adds = []
    fk = float(cfg.get("faktor_tiefe", 1.0)); fa = float(cfg.get("front_anteil", 0.5)); kon = float(cfg.get("konsole_m", 1.2)); hm = float(cfg.get("helm_m", 3.0))
    hf, bf = float(cfg.get("hoch_faktor", 1.5)), float(cfg.get("breit_faktor", 3.0)); spitzen = []; gemessen = cfg.get("spitzen_z") or []   # [[x, y, z_spitze], ...] aus spitze_hoehe.py
    for fid, Fa in E["fassaden"].items():
        if (nur is not None and fid not in nur) or not Fa.get("bloecke"): continue
        n = np.array(Fa["n"], float); d = -np.array(Fa["d"], float); o = np.array(Fa["o"], float)
        T = [[d[0], n[0], 0.0, o[0]], [d[1], n[1], 0.0, o[1]], [0.0, 0.0, 1.0, 0.0]]; zahl = {}
        se = max(((abs(n[0]), "+x" if n[0] > 0 else "-x"), (abs(n[1]), "+y" if n[1] > 0 else "-y")))[1]
        for B in Fa["bloecke"]:
            u0, u1 = sorted((-B["u"][0], -B["u"][1])); z0, z1 = B["z"]; b, h = u1 - u0, z1 - z0; t = max(0.1, float(B["tiefe_m"]) * fk)   # u' = -u wie relief_wolke
            if h >= hf * b:
                uc = 0.5 * (u0 + u1); fh = 0.5 * fa * b; gz = None
                if B.get("u_front") and cfg.get("profil", True):                                      # Profilform aus der Wolke (fassade_relief: Front, Koerper, Gesims, Helmneigung)
                    f0_, f1_ = sorted((-B["u_front"][0], -B["u_front"][1])); uc = 0.5 * (f0_ + f1_); fh = 0.5 * (f1_ - f0_)
                    t = max(0.1, float(B["plateau_m"]) * fk); z0 = float(B["koerper_z"][0]); gz = B.get("gesims_z")
                    if gz: z1 = float(gz)
                poly = [(u0, -0.02), (u1, -0.02), (uc + fh, t), (uc - fh, t)]
                adds.append(M.extrude(C([ccw(poly)]), z1 - z0).translate((0, 0, z0)).transform(T))
                pin = np.asarray(C([ccw(poly)]).offset(-0.04, JoinType.Miter).to_polygons()[0])
                adds.append(M.hull_points([(x, y, z0 + 0.06) for x, y in pin] + [(uc + dx, 0.1 + dy, z0 - kon) for dx in (-0.15, 0.15) for dy in (-0.08, 0.08)]).transform(T))
                ue = max(0.05, float(B["gesims_tiefe_m"]) * fk - t) if gz else 0.15                    # Gesims-/Helmfussueberstand gemessen (Gesimstiefe - Plateau)
                base = [(u0 - ue, -0.06), (u1 + ue, -0.06), (uc + fh + ue * 0.6, t + ue), (uc - fh - ue * 0.6, t + ue)]
                ax_ = [float(d[0] * uc + n[0] * t * 0.35 + o[0]), float(d[1] * uc + n[1] * t * 0.35 + o[1])]; spitzen.append(ax_ + [float(z1)])
                gm = [g for g in gemessen if np.hypot(g[0] - ax_[0], g[1] - ax_[1]) < 2.0]
                if gm: hm = float(np.median([g[2] for g in gm])) - z1                                    # Spitze aus der Himmelssilhouette (spitze_hoehe.py, inkl. Fahne)
                else: hm = float(cfg.get("helm_m", 3.0))
                if gz and B.get("helm_neigung"):                                                      # Glocke bis die Front auf 30 % zurueckgeht (Wolkenneigung), darueber Nadel bis helm_m (Silhouette offen -> ANNAHME/Suche)
                    zb = z1 + 0.7 * (t + ue) / float(B["helm_neigung"]); s_ = 0.3
                    ring = [(uc + (x - uc) * s_, t * 0.35 + (y - t * 0.35) * s_, zb) for x, y in base]
                    adds.append(M.hull_points([(x, y, z1 - 0.06) for x, y in base] + [(x, y, z1 + 0.15) for x, y in base] + ring).transform(T))
                    adds.append(M.hull_points([(x, y, zb - 0.05) for x, y, _ in ring] + [(uc, t * 0.35, max(zb + 0.3, z1 + hm))]).transform(T))
                else:
                    adds.append(M.hull_points([(x, y, z1 - 0.06) for x, y in base] + [(x, y, z1 + 0.15) for x, y in base] + [(uc, t * 0.35, z1 + hm)]).transform(T))
                k = "erker"
            elif b >= bf * h:
                zh = z1; z0 = max(z0, z1 - float(cfg.get("bruestung_m", 1.0)) - 0.22)                      # Handlauf = Blockoberkante (Wolke); Platte eine Bruestungshoehe tiefer (ANNAHME 1,0 m) - Blockunterkante enthaelt die Konsolen (Foto 017)
                adds.append(quader(u0, u1, -0.1, t, z0, z0 + 0.22).transform(T)); adds.append(quader(u0, u1, t - 0.12, t, z0 + 0.22, zh).transform(T))
                for uu in (u0, u1 - 0.12): adds.append(quader(uu, uu + 0.12, -0.1, t, z0 + 0.22, zh).transform(T))
                k = "galerie"
            else:
                adds.append(quader(u0, u1, -0.02, t, z0, z1).transform(T)); k = "quader"
            zahl[k] = zahl.get(k, 0) + 1
        if zahl:
            beleg(se, f"Fassade {fid} Vorbauten aus Wolkenbloecken: " + ", ".join(f"{v} {k}" for k, v in sorted(zahl.items())),
                  f"fassade_relief.py {os.path.basename(p)} Bloecke (Profil: Front, Koerper, Gesims, Helmneigung aus der Wolke, Tiefe x {fk}); Form nach Seitenverhaeltnis; ANNAHME Erkerfront {fa:.2f} x Breite, Konsole {kon:.2f} m, Helm {hm:.2f} m, Galerie-Bruestung 1,1 m",
                  spitzen=[sp for sp in spitzen], **{f"n_{k}": v for k, v in zahl.items()})
            spitzen = []
    return adds, []

@bauteil("figuren_netz")
def figuren_netz(cfg, ctx):
    """Figuren als Bild-zu-3D-Netze (zier_ausschnitt.py -> zier_3d.py, TripoSR MIT): Netz auf die Element-Box skaliert (Hoehe = Box z1-z0 aus den
    Buendelkameras; Breite/Tiefe proportional), Front nach aussen (TripoSR: z hoch, Front +x, Bild-rechts +y), Rueckseite tiefe_ein_m in die Wand
    (Figuren stehen auf Konsolen vor der Wand; ANNAHME Wandabstand). cfg: datei (ausschnitte.json), wand_abstand_m, skala (Faktor auf die Boxhoehe)."""
    p = cfg["datei"]; p = p if os.path.isabs(p) else os.path.join(OD, p); A = json.load(open(p)); E = json.load(open(A["elemente"])); adds = []
    wa = float(cfg.get("wand_abstand_m", 0.1)); sk = float(cfg.get("skala", 1.0)); zahl = {}
    for e in A["ausschnitte"]:
        if not e.get("netz") or not os.path.exists(e["netz"]): continue
        Fa = E["fassaden"][e["fassade"]]; n = np.array(Fa["n"], float); d = -np.array(Fa["d"], float); o = np.array(Fa["o"], float)
        T = [[d[0], n[0], 0.0, o[0]], [d[1], n[1], 0.0, o[1]], [0.0, 0.0, 1.0, 0.0]]
        V, Fi = [], []
        for ln in open(e["netz"]):
            if ln.startswith("v "): V.append([float(x) for x in ln.split()[1:4]])
            elif ln.startswith("f "): Fi.append([int(x.split("/")[0]) - 1 for x in ln.split()[1:4]])
        V = np.asarray(V); Fi = np.asarray(Fi, np.uint32)
        L = np.c_[-V[:, 1], V[:, 0], V[:, 2]]                                                          # TripoSR (x Front, y Bild-rechts, z) -> Fassade (u' = -rechts, s = Front, z)
        h = L[:, 2].max() - L[:, 2].min(); f_ = sk * (e["z"][1] - e["z"][0]) / h; L = L * f_
        uc = -0.5 * (e["u"][0] + e["u"][1])                                                             # u' = -u wie fassade_auto
        L += [uc - 0.5 * (L[:, 0].max() + L[:, 0].min()), wa - L[:, 1].min() - 0.05, e["z"][0] - L[:, 2].min()]
        try:
            m = M(mesh=__import__("manifold3d").Mesh(vert_properties=np.ascontiguousarray(L, np.float32), tri_verts=Fi))
        except Exception as ex:
            print(f"    Figur {e['index']}: Netz nicht mannigfaltig ({ex})"); continue
        if m.is_empty(): continue
        adds.append(m.transform(T)); adds.append(quader(uc - 0.1, uc + 0.1, -0.05, wa, e["z"][0] + 0.2, e["z"][0] + 0.6).transform(T))   # Halter in die Wand (Druck), 0,2 m breit und nur bis zur Figurrueckseite (zier_pruefen 2026-11-05: 0,5 m-Halter sichtbar)
        zahl[e["fassade"]] = zahl.get(e["fassade"], 0) + 1
    for fid, k in zahl.items():
        n = np.array(E["fassaden"][fid]["n"], float); se = max(((abs(n[0]), "+x" if n[0] > 0 else "-x"), (abs(n[1]), "+y" if n[1] > 0 else "-y")))[1]
        beleg(se, f"Fassade {fid}: {k} Figuren als Bild-zu-3D-Netz", f"zier_ausschnitt.py (OWLv2-Pruefung) + zier_3d.py (TripoSR MIT) {os.path.basename(p)}; Hoehe = Element-Box (Buendelkameras); Rueckseite geraten; ANNAHME Wandabstand {wa} m", n=k)
    return adds, []

# ------------------------------------------------------------------ Bau
def main():
    ctx = {}; adds, cuts = [], []
    ueber = json.loads(os.environ.get("BAUTEIL_PARAM", "{}"))                                    # param_suche.py: {"<typ>": {"<param>": wert, "quelle": "..."}} ohne objekt.json zu aendern
    liste = list(OBJ.get("bauteile") or [{"typ": "rumpf_lod2"}])
    liste += [dict(typ=t_, **{k: v for k, v in c_.items() if k != "anhaengen"}) for t_, c_ in ueber.items() if isinstance(c_, dict) and c_.get("anhaengen") and t_ not in {s_["typ"] for s_ in liste}]   # qualitaetsstufen: zusaetzliche Bauteile ohne objekt.json-Aenderung
    for spec in liste:
        if spec["typ"] in ueber: spec = {**spec, **{k: v for k, v in ueber[spec["typ"]].items() if k != "anhaengen"}}
        if spec.get("aktiv", True) is False: continue                                             # nach dem Ueberschreiben: BAUTEIL_PARAM darf Bauteile abschalten
        a, c = BAUTEILE[spec["typ"]](spec, ctx); adds += a; cuts += c
        print(f"  {spec['typ']}: +{len(a)} / -{len(c)}")
    model = UNION(adds)
    if cuts:                                                                                      # Schnitt, der die Aussenhaut nicht erreicht (ganz im Koerper, z. B. Wandfenster hinter einem Erker),
        innen = [c_ for c_ in cuts if (c_ - model).is_empty()]                                   # gaebe einen eingeschlossenen Hohlraum (unsichtbar, nicht druckbar, Pruefstand 'getrennte Koerper',
        if innen:                                                                                # null5e 2026-11-05: 8 Hohlraeume hinter dem Ost-Erker) -> weglassen und melden
            cuts = [c_ for c_ in cuts if not (c_ - model).is_empty()]; print(f"  {len(innen)} Schnitt(e) ganz im Koerper (verdeckt, Hohlraum) weggelassen")
            beleg("alle", f"{len(innen)} verdeckte Schnitte weggelassen", "baukasten_gen: Schnitt ohne Kontakt zur Aussenhaut = eingeschlossener Hohlraum (nicht sichtbar, nicht druckbar)")
        model = model - UNION(cuts)
    teile = model.decompose()                                                                     # Anbauteile ohne Kontakt (Figuren vor der Wand, s3_v6 5.11.: Tor verwarf sie trotz Fotogewinn t -11,9)
    if len(teile) > 1:                                                                           # -> Splitter < 1e-3 m3 weg, sonst Konsole: Huelle(untere 20 % + dieselben Punkte 0,1 m in die naechste Flaeche)
        import trimesh as _tm; from scipy.spatial import cKDTree
        teile = sorted(teile, key=lambda t_: -t_.volume()); haupt = teile[0]; hm = haupt.to_mesh()
        hT = _tm.Trimesh(np.asarray(hm.vert_properties)[:, :3], np.asarray(hm.tri_verts), process=False); P_, _ = _tm.sample.sample_surface_even(hT, 200000, seed=1); kd = cKDTree(P_)
        model, n_s, n_k = haupt, 0, 0
        for t_ in teile[1:]:
            if t_.volume() < 1e-3: n_s += 1; continue
            V_ = np.asarray(t_.to_mesh().vert_properties)[:, :3]; z_ = V_[:, 2]; un = V_[z_ <= z_.min() + 0.2 * (z_.max() - z_.min())]
            dd, ii = kd.query(un); ri = P_[ii] - un; ri /= np.maximum(np.linalg.norm(ri, axis=1, keepdims=True), 1e-9)
            model = model + t_ + M.hull_points(np.vstack([un, P_[ii] + 0.1 * ri]).tolist()); n_k += 1
        print(f"  Anbauteile: {n_k} mit Konsole angebunden, {n_s} Splitter verworfen")
        beleg("alle", f"Anbauteile ohne Kontakt: {n_k} Konsolen, {n_s} Splitter verworfen", "baukasten_gen Druckregel (tools/anbau_verbinden.py-Prototyp 5.11.): Konsole = Huelle der unteren 20 % des Teils + 0,1 m in die naechste Modellflaeche; Form des Teils unveraendert")
    model = model.simplify(float(os.environ.get("VEREINFACHEN_M", "0.005"))).scale((K, K, K))   # Splitter-Dreiecke (Naht-Offsets) entfernen; 5 mm << Druckaufloesung
    mesh = model.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]; Fi = np.asarray(mesh.tri_verts)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    try:                                                                                           # Druckreparatur (2026-11-05): fast deckungsgleiche Punkte (< 1 um) werden im STL zu Splittern ->
        import trimesh as _tm                                                                      # Pruefstand 'nicht wasserdicht / 8 Koerper' verwarf Fotowert First -0,63. Schweissen, entartete Dreiecke weg,
        tm = _tm.Trimesh(np.asarray(V, np.float32).astype(float), Fi, process=True)                                                    # Loecher schliessen; nur wenn noetig und nur bei Volumenaenderung < 0,1 %
        if not (tm.is_watertight and len(tm.split(only_watertight=False)) == 1):
            v0 = abs(model.volume()); tm.merge_vertices(digits_vertex=3); tm.update_faces(tm.nondegenerate_faces(height=1e-4)); tm.remove_unreferenced_vertices(); _tm.repair.fill_holes(tm)
            if tm.is_watertight and len(tm.split(only_watertight=False)) == 1 and abs(abs(tm.volume) - v0) < 1e-3 * v0:
                print(f"  Druckreparatur: Splitter geschweisst ({len(Fi)} -> {len(tm.faces)} Dreiecke)"); V, Fi = np.asarray(tm.vertices), np.asarray(tm.faces)
                beleg("alle", "Druckreparatur Splitter", "baukasten_gen: Punkte < 1 um verschweisst, entartete Dreiecke entfernt, Loecher geschlossen (trimesh MIT), Volumen +-0,1 %")
            else: print("  Druckreparatur fehlgeschlagen - Netz unveraendert")
    except ImportError: print("  (trimesh fehlt: keine Druckreparatur)")
    tri = V[Fi]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    rec = np.zeros(len(Fi), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri
    with open(OUT, "wb") as f: f.write(OBJ_DIR.encode()[:80].ljust(80, b" ")); f.write(np.uint32(len(Fi)).tobytes()); f.write(rec.tobytes())
    json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.environ.get("ELEMENTE_AUS") or os.path.join(OD, "elemente.json"), "w"), indent=1, ensure_ascii=False)   # ELEMENTE_AUS: Suchlaeufe (param_suche.py) schreiben nicht ins Objekt
    print(f"-> {OUT}  ({len(Fi)} Dreiecke, Volumen {model.volume() / K**3:.0f} m3, Hoehe {model.bounding_box()[5] / K:.2f} m)")

if __name__ == "__main__":
    main()
