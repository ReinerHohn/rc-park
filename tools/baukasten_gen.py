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

@bauteil("rumpf_wolke")
def rumpf_wolke(cfg, ctx):
    """Rumpf + Dach aus der dichten Punktwolke (Wolke = erste Wahrheit; LoD2 nur Luecken-Ersatz). Logik: tools/bauteil_rumpf_wolke.py."""
    import bauteil_rumpf_wolke as BW
    if "lod2_flaechen" not in ctx: ctx["lod2_flaechen"] = lod2_flaechen()[1]   # fuer Folgebauteile (treppengiebel); LoD2 nur Bauteil-Kontext, Rumpf bleibt aus der Wolke
    return BW.bauteil(cfg, ctx, dict(M=M, C=C, ROOT=ROOT, OD=OD, beleg=beleg, lod2_flaechen=lod2_flaechen))

@bauteil("element_wolke")
def element_wolke(cfg, ctx):
    """Elemente der automatischen Elementschleife (tools/generator_elemente_schleife.py): Daten in objekt.json, Familien in tools/bauteil_element_wolke.py."""
    import bauteil_element_wolke as BE
    return BE.bauteil(cfg, ctx, dict(M=M, C=C, ROOT=ROOT, OD=OD, beleg=beleg))

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
        ep_ = float(cfg.get("eckpfeiler_m", 0.3)); n_kl = 0; boegen_ = []; geo_ = []                  # geo_: Geometrie je gebautes Element (S1b Elementbuch: lokale Pruefung, tools/elementbuch.py)
        for e in L:
            form_ = []; sz_ = (0.0, 0.0)
            u0, u1 = sorted((-(e["u1"] * sk + vu), -(e["u0"] * sk + vu))); z0, z1 = e["z0"], e["z1"]; k = e["klasse"]
            if ext_ and ep_ > 0 and k in ("bogen", "oeffnung", "tuer", "fenster"):
                c0, c1 = max(u0, min(ext_) + ep_), min(u1, max(ext_) - ep_)
                if c1 - c0 < 0.3: continue
                n_kl += (c0, c1) != (u0, u1); u0, u1 = c0, c1
            tm_ = float(e["tiefe_m"]) if tg and e.get("tiefe_m") else None; n_gem += tm_ is not None   # gemessene Tiefe (freiraum_oeffnungen.py, Sichtstrahlen) statt ANNAHME
            if k == "bogen":
                u0, u1 = u0 + be, u1 - be; zk = min(z1 - 0.05, (e.get("kaempfer") or (z1 - 0.3 * (u1 - u0))) + kv); cuts.append(prisma_uz(segmentbogen(u0, u1, zk, z1, z_boden), -(tm_ or t_b), 0.3).transform(T))
                boegen_.append((u0, u1, zk, z1, tm_ or t_b, e.get("reihe", 0))); form_ = [zk, tm_ or t_b]; sz_ = (-(tm_ or t_b), 0.3)
            elif k == "oeffnung":                                                                     # Freiraumfeld ab Boden ohne erkanntes Element (Durchgang): Rechteck, Tiefe gemessen
                cuts.append(quader(u0, u1, -(tm_ or t_b), 0.3, z_boden if z0 < 2.5 else z0, z1).transform(T)); form_ = [tm_ or t_b]; sz_ = (-(tm_ or t_b), 0.3)
            elif k in ("fenster", "tuer"):
                if e.get("in_bogen"): continue                                                        # liegt auf der Arkaden-Rueckwand, nicht in der Frontebene
                if k == "tuer": cuts.append(quader(u0, u1, -(tm_ or t_n), 0.3, z_boden, z1).transform(T)); form_ = [tm_ or t_n]; sz_ = (-(tm_ or t_n), 0.3)
                else:
                    u0, u1, z0, z1 = u0 + ez_u, u1 - ez_u, z0 + ez_z, z1 - ez_z
                    if u1 - u0 < 0.2 or z1 - z0 < 0.2: continue
                    nf_ = max(1, int(e.get("felder", nf))) if cfg.get("felder_aus_foto", True) else nf   # Felder AM FOTO gezaehlt (fassade_parsing.felder_zaehlen, Regel 9), sonst cfg
                    b = (u1 - u0 - (nf_ - 1) * pfo) / nf_
                    if b < 0.1: b, nf_ = u1 - u0, 1
                    for i in range(nf_): cuts.append(quader(u0 + i * (b + pfo), u0 + i * (b + pfo) + b, -(tm_ or t_n), 0.3, z0, z1).transform(T))
                    form_ = [nf_, pfo, tm_ or t_n]; sz_ = (-(tm_ or t_n), 0.3)
            elif k == "figur":
                um = 0.5 * (u0 + u1); b = max(0.2, u1 - u0); adds.append(M.cylinder(z1 - z0, b * 0.45, b * 0.35, 24).translate((um, t_f * 0.6, z0)).transform(T))
                adds.append(quader(um - b * 0.6, um + b * 0.6, -0.05, t_f, z0 - 0.25, z0).transform(T)); form_ = [t_f]; sz_ = (-0.05, t_f)
            elif k == "balkon":
                adds.append(quader(u0, u1, -0.1, t_g, z0, z0 + 0.22).transform(T)); adds.append(quader(u0, u1, t_g - 0.12, t_g, z0 + 0.22, z1).transform(T)); form_ = [t_g]; sz_ = (-0.1, t_g)
            elif k == "gaube":
                best = None
                for dd in np.arange(0.0, 12.0, 0.1):                                                  # Gaubenfront dort, wo die LoD2-Dachflaeche die Gauben-Unterkante erreicht
                    xy = o + d * (0.5 * (u0 + u1)) - n * dd; zr = dach_z(F, *xy)
                    if zr is not None and abs(zr - z0) < (best[0] if best else 1e9): best = (abs(zr - z0), dd)
                if best is None or best[0] > 0.6: continue
                dd = best[1]; adds.append(quader(u0, u1, -dd - g_t, -dd, z0 - 0.4, z1 - 0.3).transform(T))
                adds.append(prisma_uz([(u0 - 0.08, z1 - 0.3), (u1 + 0.08, z1 - 0.3), (0.5 * (u0 + u1), z1)], -dd - g_t, -dd + 0.1).transform(T)); form_ = [dd, g_t]; sz_ = (-dd - g_t, -dd + 0.1)
            geo_.append(dict(klasse=k, u0=round(float(u0), 3), u1=round(float(u1), 3), z0=round(float(z0), 3), z1=round(float(z1), 3), s0=round(float(sz_[0]), 3), s1=round(float(sz_[1]), 3), form=[round(float(x), 3) for x in form_]))
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
                  fassade=fid, rahmen=dict(o=[round(float(x), 4) for x in o], d=[round(float(x), 5) for x in d], n=[round(float(x), 5) for x in n]), geo_elemente=geo_,   # Rahmen: Welt = o + d*u + n*s, z = z
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
        T = [[d[0], n[0], 0.0, o[0]], [d[1], n[1], 0.0, o[1]], [0.0, 0.0, 1.0, 0.0]]; zahl = {}; geo_ = []
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
            geo_.append(dict(klasse=k, u0=round(float(u0), 3), u1=round(float(u1), 3), z0=round(float(z0), 3), z1=round(float(z1), 3), s0=-0.1, s1=round(float(t), 3), form=[round(float(t), 3)]))   # Erker: Helm/Konsole nicht in der Box (ROI-Rand 0,5 m)
            zahl[k] = zahl.get(k, 0) + 1
        if zahl:
            beleg(se, f"Fassade {fid} Vorbauten aus Wolkenbloecken: " + ", ".join(f"{v} {k}" for k, v in sorted(zahl.items())),
                  f"fassade_relief.py {os.path.basename(p)} Bloecke (Profil: Front, Koerper, Gesims, Helmneigung aus der Wolke, Tiefe x {fk}); Form nach Seitenverhaeltnis; ANNAHME Erkerfront {fa:.2f} x Breite, Konsole {kon:.2f} m, Helm {hm:.2f} m, Galerie-Bruestung 1,1 m",
                  spitzen=[sp for sp in spitzen], fassade=fid, rahmen=dict(o=[round(float(x), 4) for x in o], d=[round(float(x), 5) for x in d], n=[round(float(x), 5) for x in n]), geo_elemente=geo_,
                  **{f"n_{k}": v for k, v in zahl.items()})
            spitzen = []
    return adds, []

@bauteil("figuren_netz")
def figuren_netz(cfg, ctx):
    """Figuren als Bild-zu-3D-Netze (zier_ausschnitt.py -> zier_3d.py, TripoSR MIT): Netz auf die Element-Box skaliert (Hoehe = Box z1-z0 aus den
    Buendelkameras; Breite/Tiefe proportional), Front nach aussen (TripoSR: z hoch, Front +x, Bild-rechts +y), Rueckseite tiefe_ein_m in die Wand
    (Figuren stehen auf Konsolen vor der Wand; ANNAHME Wandabstand). cfg: datei (ausschnitte.json), wand_abstand_m, skala (Faktor auf die Boxhoehe)."""
    p = cfg["datei"]; p = p if os.path.isabs(p) else os.path.join(OD, p); A = json.load(open(p)); E = json.load(open(A["elemente"])); adds = []
    wa = float(cfg.get("wand_abstand_m", 0.1)); sk = float(cfg.get("skala", 1.0)); zahl = {}; verworfen = {}; neu_info = {}
    duese = float((OBJ.get("druck") or {}).get("duese_mm", cfg.get("duese_mm", 0.4))); zelle = duese * SCALE / 1000.0           # ANNAHME Duese 0,4 mm; Zelle in Modellmetern (1:87 -> 3,5 cm)
    neu = cfg.get("neu_vernetzen", os.environ.get("NETZ_NEU_VERNETZEN", "1") != "0")
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
        if neu:                                                                                        # S4: Neuvernetzung auf Druckaufloesung (bauteile.netz_druckbar), sonst werden Feinstrukturen beim Export zu Beruehrkanten
            from bauteile import netz_druckbar
            L2, Fi2, inf = netz_druckbar(L, Fi, zelle)
            if not inf["ok"]: print(f"    Figur {e['index']}: {inf['grund']} - verworfen"); verworfen[e["fassade"]] = verworfen.get(e["fassade"], 0) + 1; continue
            L, Fi = L2, Fi2.astype(np.uint32); neu_info.setdefault(e["fassade"], []).append(inf["anteil"])
        try:
            m = M(mesh=__import__("manifold3d").Mesh(vert_properties=np.ascontiguousarray(L, np.float32), tri_verts=Fi))
        except Exception as ex:
            print(f"    Figur {e['index']}: Netz nicht mannigfaltig ({ex})"); continue
        if m.is_empty(): continue
        adds.append(m.transform(T)); adds.append(quader(uc - 0.1, uc + 0.1, -0.05, wa, e["z"][0] + 0.2, e["z"][0] + 0.6).transform(T))   # Halter in die Wand (Druck), 0,2 m breit und nur bis zur Figurrueckseite (zier_pruefen 2026-11-05: 0,5 m-Halter sichtbar)
        zahl[e["fassade"]] = zahl.get(e["fassade"], 0) + 1
    for fid, k in zahl.items():
        n = np.array(E["fassaden"][fid]["n"], float); se = max(((abs(n[0]), "+x" if n[0] > 0 else "-x"), (abs(n[1]), "+y" if n[1] > 0 else "-y")))[1]
        beleg(se, f"Fassade {fid}: {k} Figuren als Bild-zu-3D-Netz", f"zier_ausschnitt.py (OWLv2-Pruefung) + zier_3d.py (TripoSR MIT) {os.path.basename(p)}; Hoehe = Element-Box (Buendelkameras); Rueckseite geraten; ANNAHME Wandabstand {wa} m"
              + (f"; neu vernetzt auf Druckaufloesung (bauteile.netz_druckbar, Zelle {zelle * 100:.1f} cm = Duese {duese} mm x 1:{SCALE:.0f}, ANNAHME Duese 0,4 mm; Volumenanteil {min(neu_info.get(fid, [0])):.2f}-{max(neu_info.get(fid, [0])):.2f})" if neu else "; OHNE Neuvernetzung (Gegenprobe)"), n=k)
    for fid, k in verworfen.items():
        n = np.array(E["fassaden"][fid]["n"], float); se = max(((abs(n[0]), "+x" if n[0] > 0 else "-x"), (abs(n[1]), "+y" if n[1] > 0 else "-y")))[1]
        beleg(se, f"Fassade {fid}: {k} Figuren-Netze verworfen (Netz unter Druckaufloesung)", f"bauteile.netz_druckbar: Zelle {zelle * 100:.1f} cm (Duese {duese} mm x 1:{SCALE:.0f}, ANNAHME), Volumenanteil ausserhalb 90-100 % des Originals oder Netz nicht geschlossen", n=k)
    return adds, []


# ------------------------------------------------------------------ stl_teil: fertige Teil-STL als Bauteil mit Lage-/Skalenparametern (Grobgenerator aus Teilen)
def stl_lesen(pfad):
    """Binaer-STL -> (n,3,3) float64 Dreiecke (Einheit der Datei)."""
    b = open(pfad, "rb").read()
    if b[:5] == b"solid" and b"facet" in b[:400]: sys.exit(f"stl_teil: {pfad} ist ASCII-STL (nur binaer unterstuetzt)")
    n = int(np.frombuffer(b, "<u4", 1, 80)[0]); rec = np.frombuffer(b, np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), n, 84)
    return rec["v"].astype(float)

@bauteil("stl_teil")
def stl_teil(cfg, ctx):
    """Gruppe fertiger Teil-STLs (Dateien in mm im Massstab 1:SCALE, Rahmen = Modellrahmen/Netzrahmen) als EIN Bauteil mit gemeinsamer Transformation:
    Verschiebung dn/du/dz (m; n = horizontale Fassadennormale, u = horizontale Fassadenrichtung, z = Hoehe) und Skalierung sn/su/sz (Faktor) um den Anker
    (Standard: Mitte der Gruppen-Huelle in n/u, Unterkante in z; oder anker_m = [x, y, z]). Keine Boolesche Vereinigung: die Dreiecke gehen unverschweisst
    in die STL (ctx['roh'], Foto-Diff braucht keine Wasserdichtigkeit; Druck NICHT moeglich, solange Teile nicht verschweisst sind). Nichts Objektspezifisches:
    cfg: dateien [Pfade rel. zum Objektordner oder absolut], achse_n [nx, ny] (+ achse_quelle), gruppe (Name fuer beleg), quelle (Pflicht), aktiv.
    Alle Werte stehen in objekt.json['bauteile']; die Schleife ueberschreibt sie ueber BAUTEIL_PARAM['stl_teil:<name>']."""
    if not cfg.get("quelle"): sys.exit("stl_teil: 'quelle' fehlt (Regel 3b)")
    if not cfg.get("achse_n") or not cfg.get("achse_quelle"): sys.exit("stl_teil: achse_n/achse_quelle fehlen (Regel 3b)")
    n_ = np.array(cfg["achse_n"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])                 # u = n um -90 Grad (rechts herum), horizontal
    dn, du, dz = (float(cfg.get(k, 0.0)) for k in ("dn", "du", "dz")); sn, su, sz = (float(cfg.get(k, 1.0)) for k in ("sn", "su", "sz"))
    T = [stl_lesen(f if os.path.isabs(f) else os.path.join(OD, f)) / K for f in cfg["dateien"]]                      # mm -> m (1 mm = SCALE/1000 m)
    nT = [len(t_) for t_ in T]; T = np.concatenate(T); P = T.reshape(-1, 3)
    if cfg.get("anker_m"): A = np.array(cfg["anker_m"], float)
    else: lo, hi = P.min(0), P.max(0); A = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    d = P - A; c_n = d[:, :2] @ n_; c_u = d[:, :2] @ u_
    c_n, c_u, c_z = c_n * sn + dn, c_u * su + du, d[:, 2] * sz + dz
    rl, gi = float(cfg.get("roll_grad", 0.0)), float(cfg.get("gier_grad", 0.0))      # Drehung NACH Skalierung/Verschiebung (tools/editor_modell.py): roll = in der Fassadenebene (u,z), gier = um die Senkrechte (n,u); Pivot rot_pivot = [n,u,z] im Ankerrahmen
    if rl or gi:
        pn, pu, pz = (float(v) for v in cfg["rot_pivot"]); rot = lambda a_, b_, w: (np.cos(np.radians(w)) * a_ - np.sin(np.radians(w)) * b_, np.sin(np.radians(w)) * a_ + np.cos(np.radians(w)) * b_)
        if rl: c_u, c_z = (v + q for v, q in zip(rot(c_u - pu, c_z - pz, rl), (pu, pz)))
        if gi: c_n, c_u = (v + q for v, q in zip(rot(c_n - pn, c_u - pu, gi), (pn, pu)))
    Q = np.c_[A[0] + c_n * n_[0] + c_u * u_[0], A[1] + c_n * n_[1] + c_u * u_[1], A[2] + c_z]
    if cfg.get("koerper"):                                                                           # Druckstufe (Runde 4, 2026-11-09): Teil-STL als manifold-Koerper in die Vereinigung statt Rohdreiecke.
        import trimesh as _tm                                                                        # Je Zusammenhangsteil: wasserdicht -> exakt (Form unveraendert); sonst konvexe Huelle (ANNAHME, beleg + Zaehler).
        from manifold3d import Mesh as _Mesh
        tm = _tm.Trimesh(Q, np.arange(len(Q)).reshape(-1, 3), process=True); tm.merge_vertices()
        koerper, n_ok, n_huelle, n_flach = [], 0, 0, 0
        vmin = float(cfg.get("koerper_min_m3", 1e-5))                                                 # flache Restflaechen (Volumen ~0, z. B. Nischenrueckwand ohne Dicke) sind nicht druckbar und gaeben entartete Huellen -> verwerfen, zaehlen
        dh = float(cfg.get("koerper_dehnung") or 0.0)                                                 # relative Dehnung je Teil um seinen Schwerpunkt (Druck: sich nur beruehrende Teile ueberlappen dann; Form +-dh)
        for t_ in tm.split(only_watertight=False):
            if dh: c_ = t_.centroid.copy(); t_.apply_translation(-c_); t_.apply_scale(1.0 + dh); t_.apply_translation(c_)
            if t_.is_watertight: t_.fix_normals(); n_ok += 1
            else: t_ = t_.convex_hull; n_huelle += 1
            mf = M(_Mesh(vert_properties=np.asarray(t_.vertices, np.float32), tri_verts=np.asarray(t_.faces, np.uint32)))
            if mf.status() != mf.status().__class__.NoError or mf.is_empty(): mf = M.hull_points(np.asarray(t_.vertices, float).tolist()); n_huelle += 1
            if mf.is_empty() or abs(mf.volume()) < vmin: n_flach += 1; continue
            koerper.append(mf)
        beleg("alle", f"{cfg.get('gruppe', cfg['typ'])}: {len(koerper)} Teilkoerper manifold ({n_ok} exakt, {n_huelle} Huelle, {n_flach} flach verworfen)", cfg["quelle"] + f" | Druckstufe koerper=true: Teile als manifold-Koerper vereinigt (wasserdichte Teile exakt, sonst konvexe Huelle = ANNAHME; Teile < {vmin:g} m3 = flache Restflaechen ohne Dicke verworfen)",
              n_teile=len(koerper), exakt=n_ok, huelle=n_huelle, flach=n_flach)
        return [UNION(koerper)], []
    ctx.setdefault("roh", []).append(Q.reshape(-1, 3, 3))
    i0 = 0
    for f, n_t in zip(cfg["dateien"], nT):                                                                           # ein beleg je Teil (Regel 3b), Quelle = Gruppenquelle + Teilquelle
        q_ = Q.reshape(-1, 3, 3)[i0:i0 + n_t].reshape(-1, 3); i0 += n_t; tq = (cfg.get("teil_quellen") or {}).get(os.path.basename(f), "")
        beleg("alle", f"{cfg.get('gruppe', cfg['typ'])}/{os.path.basename(f)[:-4]}: {n_t} Dreiecke", cfg["quelle"] + (" | " + tq if tq else ""), dn=dn, du=du, dz=dz, sn=sn, su=su, sz=sz,
              x0=float(q_[:, 0].min()), x1=float(q_[:, 0].max()), y0=float(q_[:, 1].min()), y1=float(q_[:, 1].max()), z0=float(q_[:, 2].min()), z1=float(q_[:, 2].max()))
    return [], []

@bauteil("bogenreihe")
def bogenreihe(cfg, ctx):
    """Arkade/Laube: Reihe von n_boegen Rund-/Segmentboegen auf n_boegen+1 Pfeilern, entlang der Fassadenrichtung u, in der Horizontalen um die Normale achse_n gedreht
    (gleiche Konvention wie stl_teil: u = n um -90 Grad). Alle Werte aus objekt.json (Messung: tools/wolke_bogenreihe_messen.py -> Wolke; Zaehlung n_boegen am Foto, Regel 9).
    Geometrie (u, s=Normale, z): Pfeilerschaefte (rund = Ellipse breite x tiefe | rechteck) von boden_z bis kaempfer_z; darueber ein Wandband (u0-b/2 .. u0+(n)*pitch+b/2,
    s = pfeiler_n +- laibung_tiefe/2, z = kaempfer_z .. oberkante_z) mit je einer Bogenoeffnung (Rechteck bis kaempfer_z, darueber Segment-/Halbkreis ueber oeffnung_breite,
    Scheitel scheitel_z) mittig zwischen zwei Pfeilern. Ein Koerper, wasserdicht (manifold3d), Druckmass: Mindestwand pfeiler_breite/laibung_tiefe >> 0,8 mm H0.
    Pflicht: n_boegen, u0 (Mitte 1. Pfeiler), pitch, pfeiler_breite, pfeiler_tiefe, pfeiler_n, boden_z, kaempfer_z, scheitel_z, oberkante_z, achse_n+achse_quelle, quelle.
    Optional: sockel_weite/sockel_hoehe/fase_hoehe (achteckiger Pfeilersockel mit Schraegfase), oeffnung_breite (sonst pitch-pfeiler_breite), laibung_tiefe (sonst pfeiler_tiefe), pfeiler_form 'rund'|'rechteck', werte_quellen {param: quelle}, aktiv."""
    for k in ("n_boegen", "u0", "pitch", "pfeiler_breite", "pfeiler_tiefe", "pfeiler_n", "boden_z", "kaempfer_z", "scheitel_z", "oberkante_z", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"bogenreihe: '{k}' fehlt (Regel 3b: jedes Mass mit Quelle)")
    nb = int(cfg["n_boegen"]); u0, pitch = float(cfg["u0"]), float(cfg["pitch"]); pb, pt, pn = float(cfg["pfeiler_breite"]), float(cfg["pfeiler_tiefe"]), float(cfg["pfeiler_n"])
    zb, zk, zs, zo = (float(cfg[k]) for k in ("boden_z", "kaempfer_z", "scheitel_z", "oberkante_z")); ob = float(cfg.get("oeffnung_breite") or (pitch - pb)); lt = float(cfg.get("laibung_tiefe") or pt)
    form = cfg.get("pfeiler_form", "rund"); wq = cfg.get("werte_quellen") or {}
    sw, shh, fh = float(cfg.get("sockel_weite", 0.0)), float(cfg.get("sockel_hoehe", 0.0)), float(cfg.get("fase_hoehe", 0.0))   # optional: achteckiger Sockel (Eck-zu-Eck), Hoehe, Fasenhoehe
    if nb < 1 or pitch <= pb or ob > pitch - 0.02 or not (zb < zk < zs < zo) or min(pb, pt, lt) < 0.01: sys.exit(f"bogenreihe: unplausible Masse (n={nb}, pitch={pitch}, ob={ob}, z={zb}/{zk}/{zs}/{zo})")
    n_ = np.array(cfg["achse_n"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
    T = [[u_[0], n_[0], 0.0, 0.0], [u_[1], n_[1], 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]            # (u, s, z) -> (x, y, z), rechtshaendig
    teile = []
    for i in range(nb + 1):                                                                       # Pfeilerschaefte (leicht in das Wandband hinein: ein Koerper)
        uc = u0 + i * pitch; h = zk - zb + (0.0 if cfg.get("druck_verbinder") else 0.02)          # druck_verbinder: Schaft endet am Kaempfer, Verbinder = Schaft geschnitten mit dem Band (s.u.; vorher 2-cm-Absatz ragte ueber die Bandflucht -> Splitter im STL)
        if form == "rechteck": sh = quader(uc - pb / 2, uc + pb / 2, pn - pt / 2, pn + pt / 2, zb, zb + h)
        else: sh = M.extrude(C.circle(0.5, 48).scale((pb, pt)).translate((uc, pn)), h).translate((0, 0, zb))
        teile.append(sh)
        if sw > 0 and form != "rechteck":                                                         # Sockel: Oktogon (Eck-zu-Eck sockel_weite, Flaeche zur Fassade) + Schraegfase zum Schaft (Nutzerfotos 8.11.)
            okt = M.extrude(C.circle(0.5, 8).rotate(22.5).scale((sw, sw)), shh).translate((uc, pn, zb)); teile.append(okt)
            fw = sw * np.cos(np.radians(22.5))
            if fh > 0.01: teile.append(M.extrude(C.circle(0.5, 48).scale((fw, fw)), fh, scale_top=(pb / fw, pt / fw)).translate((uc, pn, zb + shh)))
    ul, ur = u0 - pb / 2, u0 + nb * pitch + pb / 2
    ab, at = float(cfg.get("archivolt_breite", 0.0)), float(cfg.get("archivolt_tiefe", 0.0))      # optional: gestufter Bogenrand (Steinring ab breit buendig mit der Bandfront, Laibung um at zurueckgesetzt; Foto 6117)
    def archivolt_schnitt():
        """Aussparung der Stirn: konzentrischer Bogen (Radius R+ab um denselben Mittelpunkt wie der Laibungsbogen) von der Bandfront at tief."""
        R_ = ((ob / 2) ** 2 + (zs - zk) ** 2) / (2 * (zs - zk)); hw = math.sqrt((R_ + ab) ** 2 - (zk - (zs - R_)) ** 2); cut = None
        for i in range(nb):
            um = u0 + (i + 0.5) * pitch; p_ = prisma_uz(np.array(segmentbogen(um - hw, um + hw, zk, zs + ab, zk - 0.05, n=48), float), pn + lt / 2 - at, pn + lt / 2 + 0.05)
            cut = p_ if cut is None else cut + p_
        return cut
    band = M.cube((ur - ul, lt, zo - zk)).translate((ul, pn - lt / 2, zk))
    for i in range(nb):
        um = u0 + (i + 0.5) * pitch; poly = np.array(segmentbogen(um - ob / 2, um + ob / 2, zk, zs, zk - 0.05, n=48), float)
        band = band - prisma_uz(poly, pn - lt / 2 - 0.05, pn + lt / 2 + 0.05)
    if ab > 0 and at > 0: band = band - archivolt_schnitt()
    teile.append(band)
    if cfg.get("druck_verbinder"):                                                                # Kaempferstueck: Schaft (zk-0,05..zk+0,15) geschnitten mit Band (unten 0,05 verlaengert, Boegen ausgeschnitten) -> nie ueber Bandflucht/Laibung, keine Beruehrflaechen
        bl = M.cube((ur - ul, lt, zo - zk + 0.05)).translate((ul, pn - lt / 2, zk - 0.05))
        for i in range(nb):
            um = u0 + (i + 0.5) * pitch; bl = bl - prisma_uz(np.array(segmentbogen(um - ob / 2, um + ob / 2, zk, zs, zk - 0.10, n=48), float), pn - lt / 2 - 0.05, pn + lt / 2 + 0.05)
        if ab > 0 and at > 0: bl = bl - archivolt_schnitt()
        for i in range(nb + 1):
            uc = u0 + i * pitch; pe = quader(uc - pb / 2, uc + pb / 2, pn - pt / 2, pn + pt / 2, zk - 0.05, zk + 0.15) if form == "rechteck" else M.extrude(C.circle(0.5, 48).scale((pb, pt)).translate((uc, pn)), 0.2).translate((0, 0, zk - 0.05))
            teile.append(pe ^ bl)
    k = UNION(teile).transform(T)
    q = lambda p_: (wq.get(p_) or cfg["quelle"])
    for i in range(nb + 1):
        beleg("alle", f"Arkade Pfeiler {i + 1}/{nb + 1} ({form})", q("pfeiler_breite") + " | Lage u0+i*pitch: " + q("pitch"), u_pfeiler=u0 + i * pitch, breite=pb, tiefe=pt, n=pn, z0=zb, z1=zk)
    if ab > 0 and at > 0: beleg("alle", f"Arkade Archivolt-Absatz (Ring {ab:.2f} m breit, Laibung {at:.2f} m zurueck)", q("archivolt_breite") + " | Tiefe: " + q("archivolt_tiefe"), archivolt_breite=ab, archivolt_tiefe=at, scheitel_aussen_z=zs + ab)
    beleg("alle", f"Arkade {nb} Boegen (Wandband)", f"Anzahl {', '.join(cfg.get('zaehlung', [])) or 'Foto'} (Regel 9); " + q("kaempfer_z"), n_boegen=nb, pitch=pitch, oeffnung_breite=ob, kaempfer_z=zk, scheitel_z=zs, oberkante_z=zo, laibung_tiefe=lt)
    return [k], []


def _uszT(cfg):
    n_ = np.array(cfg["achse_n"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
    return [[u_[0], n_[0], 0.0, 0.0], [u_[1], n_[1], 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]            # (u, s, z) -> (x, y, z), wie bogenreihe/stl_teil

@bauteil("konsolenreihe")
def konsolenreihe(cfg, ctx):
    """Reihe von Konsolen (Kragsteine) unter einer Platte, Lage JE INSTANZ (kein Raster): je Lage u (Mitte), breite, profil [[z, ausladung], ...] (Ausladung vor der
    Wandebene wand_n, aufsteigend in z); Koerper = konvexe Huelle der Profilpunkte (+-breite/2), hinten einbindung m in die Wand, oben bis z_oben (in die Platte),
    vorn hoechstens max_ausladung (nicht buendig mit der Plattenfront: deckungsgleiche Flaechen = Splitter im Druck). Voluten/Schnitzwerk nicht modelliert (ANNAHME Huelle).
    Lagen entweder inline (lagen: [{u, breite, profil?, quelle}], profil sonst cfg.profil) oder aus einer Messdatei: lagen_datei (JSON, Liste unter lagen_schluessel,
    Felder along/breite/profil/breite_quelle/status) im Quellrahmen quell_rahmen {u: [ux, uy], n: [nx, ny], off_front} (along/off der Datei -> Welt -> eigener Rahmen achse_n;
    Ausladung der Datei bezieht sich auf off_front). Pflicht: wand_n, z_oben, achse_n, achse_quelle, quelle, lagen|lagen_datei."""
    for k in ("wand_n", "z_oben", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"konsolenreihe: '{k}' fehlt (Regel 3b)")
    n_ = np.array(cfg["achse_n"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
    wn, zo = float(cfg["wand_n"]), float(cfg["z_oben"]); ein = float(cfg.get("einbindung", 0.2)); amax = float(cfg.get("max_ausladung", 1e9))
    lagen = []
    if cfg.get("lagen_datei"):
        pf = cfg["lagen_datei"]; pf = pf if os.path.isabs(pf) else os.path.join(OD, pf); Dd = json.load(open(pf))
        qr = cfg.get("quell_rahmen") or {}; uq = np.array(qr.get("u", u_), float); nq = np.array(qr.get("n", n_), float); ofq = float(qr.get("off_front", wn))
        for e in Dd[cfg.get("lagen_schluessel", "konsolen")]:
            xy0 = uq * float(e["along"]) + nq * ofq                                                  # Wandpunkt der Instanz (Welt)
            pr_ = [[float(z), float(d) + float((xy0 @ n_) - wn)] for z, d in e.get("profil") or cfg["profil"]]   # Ausladung auf die eigene Wandebene umgerechnet
            lagen.append(dict(u=float(xy0 @ u_), breite=float(e["breite"]), profil=pr_, quelle=f"{os.path.basename(pf)}: {e.get('quelle', '')}, Breite {e.get('breite_quelle', '?')}; {str(e.get('status', ''))[:160]}"))
    else:
        lagen = [dict(l_, profil=l_.get("profil") or cfg["profil"]) for l_ in cfg["lagen"]]
    teile = []
    for l_ in lagen:
        hw = float(l_["breite"]) / 2; pr_ = sorted(l_["profil"]); uc = float(l_["u"]); pts = []
        for z, d in pr_ + [[zo, pr_[-1][1]]]:
            d = min(d, amax); pts += [[uc - hw, wn - ein, z], [uc + hw, wn - ein, z], [uc - hw, wn + d, z], [uc + hw, wn + d, z]]
        teile.append(M.hull_points(pts))
        beleg("alle", f"Konsole u {uc:.2f} (b {2 * hw:.2f})", (l_.get("quelle") or cfg["quelle"]) + " | Form: konvexe Huelle des Profils (ANNAHME, Voluten nicht modelliert)",
              u=uc, breite=2 * hw, z_unten=pr_[0][0], z_oben=zo, ausladung_max=min(max(d for _, d in pr_), amax), wand_n=wn)
    beleg("alle", f"Konsolenreihe {len(lagen)} Konsolen", cfg["quelle"] + (f" | Zaehlung {', '.join(cfg.get('zaehlung', []))}" if cfg.get("zaehlung") else ""), n=len(lagen))
    return [UNION(teile).transform(_uszT(cfg))], []

@bauteil("figurenreihe")
def figurenreihe(cfg, ctx):
    """Reihe freistehender Figuren auf Rundkonsolen vor einer Wand (Statuen auf Pendelkonsolen). Jede Figur = Konsole (Rotationsprofil konsole [[z, r], ...], Kreisringe)
    + Koerper (Querschnittsprofil koerper [[z, breite_u, tiefe_n], ...], Ellipsenringe um die Achse); Teilkoerper = konvexe Huelle je zwei benachbarter Ringe, Vereinigung.
    Lage JE FIGUR (kein Raster): figuren [{u, s, z_scheitel?, dz?, quelle}] (u entlang der Wand, s = Abstand auf der Wandnormalen, Achse senkrecht);
    Koerperringe ueber kopf_ab werden so verschoben, dass der letzte Ring auf z_scheitel der Figur liegt (Kopf/Krone je Figur gemessen), dz verschiebt die ganze Figur.
    Arme/Schwert/Reichsapfel/Gesicht nicht modelliert (ANNAHME: Huellkoerper, H0-Detailgrad). Pflicht: achse_n, achse_quelle, quelle, konsole, koerper, figuren."""
    for k in ("achse_n", "achse_quelle", "quelle", "konsole", "koerper", "figuren"):
        if cfg.get(k) in (None, ""): sys.exit(f"figurenreihe: '{k}' fehlt (Regel 3b)")
    nseg = int(cfg.get("segmente", 16)); th = np.linspace(0, 2 * np.pi, nseg, endpoint=False); kab = float(cfg.get("kopf_ab", 1e9))
    def ring(u, s, z, b, d): return [[u + 0.5 * b * math.cos(t), s + 0.5 * d * math.sin(t), z] for t in th]
    def huellen(rs): return [M.hull_points(rs[i] + rs[i + 1]) for i in range(len(rs) - 1)]
    teile = []; info = []
    for f in cfg["figuren"]:
        u, s = float(f["u"]), float(f["s"]); dz = float(f.get("dz", 0.0))
        kon = sorted([[float(z) + dz, float(r)] for z, r in (f.get("konsole") or cfg["konsole"])])
        kor = sorted([[float(z), float(b), float(d)] for z, b, d in (f.get("koerper") or cfg["koerper"])])
        if f.get("z_scheitel") is not None:
            ztop = kor[-1][0]; sh = float(f["z_scheitel"]) - ztop; kor = [[z + (sh if z >= kab else 0.0), b, d] for z, b, d in kor]
        else: sh = 0.0
        kor = [[z + dz, b, d] for z, b, d in kor]
        teile += huellen([ring(u, s, z, 2 * r, 2 * r) for z, r in kon]) + huellen([ring(u, s, z, b, d) for z, b, d in kor])
        beleg("alle", f"Figur u {u:.2f} (Konsole z {kon[0][0]:.2f}-{kon[-1][0]:.2f}, Figur z {kor[0][0]:.2f}-{kor[-1][0]:.2f})", (f.get("quelle") or cfg["quelle"]) + " | Form: Rotationskonsole + Ellipsen-Koerperprofil (ANNAHME Huelle, Arme/Schwert nicht modelliert)",
              u=u, s=s, z_unten=kon[0][0], z_scheitel=kor[-1][0], konsole_r_max=max(r for _, r in kon), koerper_b_max=max(b for _, b, _ in kor))
        info.append(u)
    beleg("alle", f"Figurenreihe {len(info)} Figuren", cfg["quelle"] + (f" | Zaehlung {', '.join(cfg.get('zaehlung', []))}" if cfg.get("zaehlung") else ""), n=len(info))
    return [UNION(teile).transform(_uszT(cfg))], []

@bauteil("erker")
def erker(cfg, ctx):
    """Erker: Kasten (u = mitte_u +- breite/2, s = wand_n .. wand_n+auskragung, z = unterkante_z .. oberkante_z) mit verjuengendem Dach (Helm/Zelt) bis spitze_z.
    Dachprofil = Liste {t, fn, fu}: t = (z-oberkante)/(spitze-oberkante) in 0..1, fn = n_ueber_wand/auskragung, fu = u_breite/breite (aus Wolkenschnitten, erker_messung.json);
    das Dach folgt so den Parametern breite/auskragung/oberkante/spitze (Optimierer). Je Stufe ein Rechteck, benachbarte Stufen per Huelle verbunden. Ein Koerper.
    Pflicht: mitte_u, breite, wand_n, auskragung, unterkante_z, oberkante_z, spitze_z, dachprofil, achse_n, achse_quelle, quelle. Optional: werte_quellen, aktiv."""
    for k in ("mitte_u", "breite", "wand_n", "auskragung", "unterkante_z", "oberkante_z", "spitze_z", "dachprofil", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"erker: '{k}' fehlt (Regel 3b: jedes Mass mit Quelle)")
    um, b, wn, au = (float(cfg[k]) for k in ("mitte_u", "breite", "wand_n", "auskragung")); zu, zo, zs = (float(cfg[k]) for k in ("unterkante_z", "oberkante_z", "spitze_z"))
    if min(b, au) < 0.1 or not (zu < zo < zs): sys.exit(f"erker: unplausible Masse (b={b}, au={au}, z={zu}/{zo}/{zs})")
    EIN = 0.3                                                                                      # Einbindung in die Wand (m): Koerper beruehrt so die Bogenreihe/Wand -> kein Konsolen-Huellkoerper; verdeckt durch das Wandnetz
    kasten = quader(um - b / 2, um + b / 2, wn - EIN, wn + au, zu - 0.1, zo)
    def rechteck(z, fn, fu): return [(um - fu * b / 2, wn - EIN, z), (um + fu * b / 2, wn - EIN, z), (um - fu * b / 2, wn + max(fn * au, 0.02), z), (um + fu * b / 2, wn + max(fn * au, 0.02), z)]
    stufen = [(0.0, 1.0, 1.0)] + [(float(d["t"]), float(d["fn"]), float(d["fu"])) for d in sorted(cfg["dachprofil"], key=lambda d: d["t"])] + [(1.0, 0.08, 0.06)]
    teile = [kasten]
    if cfg.get("ohne_dach"): stufen = stufen[:1]                                                   # 2026-11-09 R6: Dach = eigenes Bauteil (helm_geschweift), Erker endet flach an oberkante_z
    for (t0, n0, u0_), (t1, n1, u1_) in zip(stufen, stufen[1:]):
        pts = rechteck(zo + t0 * (zs - zo), n0, u0_) + rechteck(zo + t1 * (zs - zo), n1, u1_)
        teile.append(M.hull_points([list(map(float, p_)) for p_ in pts]))
    k = UNION(teile).transform(_uszT(cfg)); wq = cfg.get("werte_quellen") or {}; q = lambda p_: (wq.get(p_) or cfg["quelle"])
    beleg("alle", f"Erker u={um:.2f}", q("breite") + " | Lage: " + q("mitte_u"), mitte_u=um, breite=b, wand_n=wn, auskragung=au, unterkante_z=zu, oberkante_z=zo, spitze_z=zs)
    return [k], []

@bauteil("erker_polygon")
def erker_polygon(cfg, ctx):
    """Erker als Teil-Vieleck (Runde 7, Foto-Formfamilie): Grundriss = Front (seite_front) + je eine Schraegflaeche (seite_schraeg, winkel_grad zur Front, regelmaessiges Achteck = 45 Grad) + Rueckkehr zur Wand.
    Zonen von unten nach oben (alle Hoehen aus Foto/Wolke, in cfg): Unterbau (nach unten spitz zulaufende Pyramide: Profil [[z, vorsprung_vor_wand], ...], Spitze an der Wand, optional Rippen = Grate + Mittelrippen),
    Gesims unten, Bruestung/Wappenband (je Flaeche ein vertieftes Wappenfeld mit stehendem Schild), Fensterbank-Gesims, Fensterband (je Flaeche n_lichter Lichter in zwei Reihen unter/ueber dem Kaempfer, Vorhangbogen-Sack oben),
    Traufgesims. Dach = eigenes Bauteil (helm_geschweift). u = Achse quer zur Wand, s = Normale (wie alle Bauteile), achse_n dreht in x/y.
    Pflicht: u_mitte, n_front, seite_front, seite_schraeg, winkel_grad, wand_n, einbindung, zonen {z_unterbau_spitze, z_unterbau_oben, z_wappen_unten, z_wappen_oben, z_bank_oben, z_trauf_unten, z_trauf_oben},
    unterbau {profil, vorsprung_spitze}, gesims [{name, z0, z1, aus}], fenster {n_lichter, rahmen_b, pfosten_b, z_kaempfer, kaempfer_h, z_licht_unten, z_licht_oben_seite, z_licht_oben_mitte, tiefe},
    wappen {rand_u, rand_z, tiefe, schild_b, schild_h}, achse_n, achse_quelle, quelle (+ werte_quellen, zaehlung)."""
    for k in ("u_mitte", "n_front", "seite_front", "seite_schraeg", "winkel_grad", "wand_n", "einbindung", "zonen", "unterbau", "gesims", "fenster", "wappen", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"erker_polygon: '{k}' fehlt (Regel 3b: jedes Mass mit Quelle)")
    um, nf, s_f, s_d, wn, ein = (float(cfg[k]) for k in ("u_mitte", "n_front", "seite_front", "seite_schraeg", "wand_n", "einbindung")); al = math.radians(float(cfg["winkel_grad"])); Zn = {k: float(v) for k, v in cfg["zonen"].items()}
    hu, ne = s_f / 2 + s_d * math.cos(al), nf - s_d * math.sin(al)
    if not (0 < al < math.pi / 2 and s_f > 0.3 and s_d > 0.3 and ne > wn - ein): sys.exit(f"erker_polygon: unplausibler Grundriss (hu={hu:.2f}, ne={ne:.2f}, wand {wn})")
    base = [(hu, wn - ein), (hu, ne), (s_f / 2, nf), (-s_f / 2, nf), (-hu, ne), (-hu, wn - ein)]                  # (u relativ, n absolut), gegen den Uhrzeigersinn; Rueckkehr (hu, ne)->Wand
    def prisma(z0, z1, aus=0.0):
        cs = C([ccw(np.array(base, float))]); cs = cs.offset(aus, JoinType.Miter) if aus else cs
        return M.extrude(cs, z1 - z0).translate((um, 0.0, z0))
    teile = []; z_o = Zn["z_unterbau_oben"]; ub = cfg["unterbau"]; prof = [(float(z), float(p)) for z, p in ub["profil"]]; v0 = float(ub["vorsprung_spitze"]); pmax = nf - wn
    if not (prof and all(b[0] > a[0] for a, b in zip(prof, prof[1:])) and Zn["z_unterbau_spitze"] < prof[0][0] and prof[-1][0] < z_o): sys.exit("erker_polygon: unplausibles Unterbau-Profil")
    ringe = [(Zn["z_unterbau_spitze"], v0)] + prof + [(z_o, pmax)]
    def ring(z, p):                                                                                                  # Grundriss auf die Pyramide skaliert: Spitze liegt in der Wandebene (u=0, n=wand_n)
        f = max(p, 0.02) / pmax; return [[um + f * u_, (wn + f * (n_ - wn)) if n_ > wn else n_, z] for u_, n_ in base]
    for (za, pa), (zb, pb) in zip(ringe, ringe[1:]): teile.append(M.hull_points(ring(za, pa) + ring(zb, pb)))
    if ub.get("rippen"):                                                                                              # ANNAHME: vereinfachte Rippen (4 Grate + 3 Mittelrippen); das echte Netzwerk (gekruemmte Rippen, Rosetten) ist nicht nachgebildet
        rb_, rv = float(ub["rippen_b"]), float(ub["rippen_vor"]); fl = [(base[1], base[2]), (base[2], base[3]), (base[3], base[4])]
        def nrm(a, b): d_ = np.array(b, float) - np.array(a, float); d_ /= np.linalg.norm(d_); return np.array([d_[1], -d_[0]]), d_             # (aussen, tangente) fuer Kante a->b (gegen den Uhrzeigersinn)
        anker = [(np.array(base[i], float), (nrm(base[i - 1], base[i])[0] + nrm(base[i], base[i + 1])[0]) / 2) for i in (1, 2, 3, 4)] + [((np.array(a, float) + np.array(b, float)) / 2, nrm(a, b)[0]) for a, b in fl]
        for P_, nv in anker:
            nv = nv / np.linalg.norm(nv); tv = np.array([-nv[1], nv[0]]); pts_ = []
            for z, p in ringe[1:] + [(z_o + 0.05, pmax)]:                                                              # Rippe endet 5 cm im Gesims (Ueberlappung, keine Beruehrflaeche)
                f = max(p, 0.02) / pmax; q = np.array([f * P_[0], wn + f * (P_[1] - wn)]) - nv * 0.05; q_o = q + nv * (rv + 0.05)   # 5 cm in die Pyramide eingebunden (Druck: sonst deckungsgleiche Flaechen -> Henkel/Splitter, Pruefung genus)
                pts_.append([[um + (q + s_ * tv * rb_ / 2)[0], (q + s_ * tv * rb_ / 2)[1], z] for s_ in (-1, 1)] + [[um + (q_o + s_ * tv * rb_ / 2)[0], (q_o + s_ * tv * rb_ / 2)[1], z] for s_ in (-1, 1)])
            for a_, b_ in zip(pts_, pts_[1:]): teile.append(M.hull_points(a_ + b_))
    for g_ in cfg["gesims"]: teile.append(prisma(float(g_["z0"]), float(g_["z1"]), float(g_["aus"])))
    k0 = prisma(Zn["z_wappen_unten"] - 0.01, Zn["z_trauf_unten"] + 0.01)                                               # Koerper Bruestung + Fensterband (Frontebene n_front)
    fl3 = [(np.array(base[i], float), np.array(base[i + 1], float)) for i in (1, 2, 3)]
    fz, wz = cfg["fenster"], cfg["wappen"]; nl = int(fz["n_lichter"]); rb, pf, kh, td = float(fz["rahmen_b"]), float(fz["pfosten_b"]), float(fz["kaempfer_h"]), float(fz["tiefe"]); zk = float(fz["z_kaempfer"])
    zl0, zls, zlm = float(fz["z_licht_unten"]), float(fz["z_licht_oben_seite"]), float(fz["z_licht_oben_mitte"]); schnitte = []
    def flaechen_matrix(a, b, tief):                                                                                 # lokal (x entlang -t, y = z, z = nach innen) -> (u, n, z); Rechtssystem
        w = float(np.linalg.norm(b - a)); t = (b - a) / w; nu = np.array([t[1], -t[0]]); c = (a + b) / 2 + nu * 0.05
        return w, [[-t[0], 0, -nu[0], um + c[0]], [-t[1], 0, -nu[1], c[1]], [0, 1, 0, 0]], tief + 0.05
    for a, b in fl3:
        w, T_, dep = flaechen_matrix(a, b, td); wl = (w - 2 * rb - (nl - 1) * pf) / nl
        for j in range(nl):
            x0 = -w / 2 + rb + j * (wl + pf); x1 = x0 + wl; xm = (x0 + x1) / 2; hw = wl / 2
            unten = [(x0, zl0), (x1, zl0), (x1, zk - kh / 2), (x0, zk - kh / 2)]
            ob = [(x0, zk + kh / 2), (x1, zk + kh / 2)] + [(xm + (x1 - xm) * s_, zlm + (zls - zlm) * s_ ** 2) for s_ in np.linspace(1, -1, 13)]
            for poly in (unten, ob): schnitte.append(M.extrude(C([ccw(np.array(poly, float))]), dep).transform(T_))
        wa, T2, dp2 = flaechen_matrix(a, b, float(wz["tiefe"])); z0w, z1w = Zn["z_wappen_unten"] + float(wz["rand_z"]), Zn["z_wappen_oben"] - float(wz["rand_z"])
        feld = C([ccw(np.array([(-wa / 2 + float(wz["rand_u"]), z0w), (wa / 2 - float(wz["rand_u"]), z0w), (wa / 2 - float(wz["rand_u"]), z1w), (-wa / 2 + float(wz["rand_u"]), z1w)], float))])
        schild = C.circle(1.0, 40).scale((float(wz["schild_b"]) / 2, float(wz["schild_h"]) / 2)).translate((0.0, (z0w + z1w) / 2)); schnitte.append(M.extrude(feld - schild, dp2).transform(T2))
    k0 = k0 - UNION(schnitte)
    teile.append(k0)
    teile.append(prisma(Zn["z_wappen_oben"] - 0.01, Zn["z_bank_oben"], float(cfg.get("bank_aus", 0.0))))                    # Fensterbank-Gesims
    k = UNION(teile).transform(_uszT(cfg)); wq = cfg.get("werte_quellen") or {}; q = lambda p_: (wq.get(p_) or cfg["quelle"]); zaehl = ", ".join(cfg.get("zaehlung", [])) or "Foto"
    beleg("alle", f"Erker-Polygon u={um:.2f}: Teil-Achteck 3 Flaechen (Front {s_f:.2f} m + 2 Schraegflaechen {s_d:.2f} m, {math.degrees(al):.0f} Grad)", q("grundriss") + f" | Flaechenzahl/Lichter/Wappen: Zaehlung {zaehl} (Regel 9)", u_mitte=um, n_front=nf, seite_front=s_f, seite_schraeg=s_d, winkel_grad=math.degrees(al), n_flaechen=3)
    beleg("alle", "Erker-Polygon: Unterbau (umgekehrte Pyramide, Spitze an der Wand" + (", 7 Rippen ANNAHME" if ub.get("rippen") else "") + ")", q("unterbau"), z_spitze=Zn["z_unterbau_spitze"], z_oben=z_o, profil=prof)
    beleg("alle", f"Erker-Polygon: Bruestung/Wappenband z {Zn['z_wappen_unten']:.2f}-{Zn['z_wappen_oben']:.2f} (je Flaeche 1 Wappenfeld)", q("zonen") + f" | Anzahl: Zaehlung {zaehl}", z_unten=Zn["z_wappen_unten"], z_oben=Zn["z_wappen_oben"], n_wappen=3)
    beleg("alle", f"Erker-Polygon: Fensterband z {zl0:.2f}-{zlm:.2f} ({nl} Lichter je Flaeche, Kaempfer {zk:.2f})", q("fenster") + f" | Anzahl: Zaehlung {zaehl}", z_kaempfer=zk, z_licht_unten=zl0, z_licht_oben_mitte=zlm, n_lichter=nl)
    beleg("alle", "Erker-Polygon: Gesimse " + ", ".join(f"{g_['name']} z {g_['z0']}-{g_['z1']} aus {g_['aus']}" for g_ in cfg["gesims"]), q("gesims"), gesims=cfg["gesims"])
    return [k], []

@bauteil("balkonband")
def balkonband(cfg, ctx):
    """Durchgehendes Balkon-/Bruestungsband vor der Wand: Kasten u = u_von .. u_bis, s = wand_n .. wand_n+auskragung, z = unterseite_z .. oberseite_z (druckbar massiv; die Bruestung ist
    in der Wolke eine duenne Front, Innenraum nicht messbar = ANNAHME massiv). Pflicht: u_von, u_bis, wand_n, auskragung, unterseite_z, oberseite_z, achse_n, achse_quelle, quelle."""
    for k in ("u_von", "u_bis", "wand_n", "auskragung", "unterseite_z", "oberseite_z", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"balkonband: '{k}' fehlt (Regel 3b: jedes Mass mit Quelle)")
    u0, u1, wn, au, z0, z1 = (float(cfg[k]) for k in ("u_von", "u_bis", "wand_n", "auskragung", "unterseite_z", "oberseite_z"))
    if u1 - u0 < 0.5 or au < 0.05 or z1 - z0 < 0.1: sys.exit(f"balkonband: unplausible Masse (u={u0}..{u1}, au={au}, z={z0}..{z1})")
    k = quader(u0, u1, wn - 0.3, wn + au, z0 - 0.1, z1).transform(_uszT(cfg))     # 0,3 m in die Wand, 0,1 m nach unten: Beruehrung mit der Bogenreihe (Oberkante 4,85), sonst Konsolen-Huellkoerper
    wq = cfg.get("werte_quellen") or {}; q = lambda p_: (wq.get(p_) or cfg["quelle"])
    beleg("alle", "Balkonband", q("auskragung") + " | Lage: " + q("unterseite_z"), u_von=u0, u_bis=u1, wand_n=wn, auskragung=au, unterseite_z=z0, oberseite_z=z1)
    return [k], []


@bauteil("satteldach")
def satteldach(cfg, ctx):
    """Satteldach als Prisma: Querschnitt (s=n, z) = Vorderkante unten, Traufe vorn, First, Traufe hinten, Hinterkante unten; entlang u von u0 bis u1 extrudiert.
    Optional ziegel_abstand/ziegel_tiefe/ziegel_anteil (Leisten quer zum Hang). Walm/Giebelschraege nicht enthalten (Staffelgiebel = eigenes Bauteil). Parameter: u0, u1, n_traufe_v, z_traufe_v, n_first, z_first, n_traufe_h, z_traufe_h, z_unten.
    Pflicht auch achse_n, achse_quelle, quelle. Druckbar massiv. werte_quellen {param: quelle}."""
    for k in ("u0", "u1", "n_traufe_v", "z_traufe_v", "n_first", "z_first", "n_traufe_h", "z_traufe_h", "z_unten", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"satteldach: '{k}' fehlt (Regel 3b: jedes Mass mit Quelle)")
    u0, u1, ntv, ztv, nf, zf, nth, zth, zu = (float(cfg[k]) for k in ("u0", "u1", "n_traufe_v", "z_traufe_v", "n_first", "z_first", "n_traufe_h", "z_traufe_h", "z_unten"))
    if cfg.get("symmetrisch"): nth, zth = 2 * nf - ntv, ztv                                          # ANNAHME: Rueckhang spiegelt den Vorderhang (Wolke sieht nur den Vorderhang, Regel 4); cfg['symmetrisch_quelle'] nennen
    if not (u1 - u0 > 1 and nth < nf < ntv and zu < ztv < zf and zu < zth < zf): sys.exit(f"satteldach: unplausible Masse (u={u0}..{u1}, n={nth}/{nf}/{ntv}, z={zu}/{ztv}/{zth}/{zf})")
    poly = [(ntv, zu), (ntv, ztv), (nf, zf), (nth, zth), (nth, zu)]
    q = M.extrude(C([ccw(np.array(poly, float))]), u1 - u0)                                          # x=n, y=z, Extrusion z=u
    q = q.transform([[0, 0, 1, u0], [1, 0, 0, 0], [0, 1, 0, 0]])                                    # (n,z,u) -> (u,n,z): x=u0+extr, y=n, z=z
    ab, tf, an = float(cfg.get("ziegel_abstand") or 0), float(cfg.get("ziegel_tiefe") or 0), float(cfg.get("ziegel_anteil") or 0.4); ze = float(cfg.get("ziegel_einbindung") or 0.0)                    # Ziegelreihen: Leisten quer zum Hang (Kanten fuer den Foto-Diff); 0 = glatt
    if ab > 0.05 and tf > 0.005:
        streifen = []
        for (na, za, nb_, zb_) in ((ntv, ztv, nf, zf), (nf, zf, nth, zth)):                                                                        # Vorder- und Hinterhang
            L = math.hypot(nb_ - na, zb_ - za); t_ = np.array([(nb_ - na) / L, (zb_ - za) / L]); n_out = np.array([t_[1], -t_[0]]) * (1 if za < zb_ else -1) if False else np.array([-t_[1], t_[0]]) * (1 if (nb_ < na) else -1)
            if (n_out[1] < 0): n_out = -n_out                                                                                                          # Aussenseite zeigt nach oben
            for i in range(int(L / ab)):
                s0 = (i + 0.5) * ab; p0 = np.array([na, za]) + t_ * s0 - n_out * ze; p1 = p0 + t_ * ab * an                                       # ze = ziegel_einbindung (m) in die Dachflaeche (Druck: sonst Beruehrflaeche -> Splitterkanten im STL)
                poly = [tuple(p0), tuple(p1), tuple(p1 + n_out * (tf + ze)), tuple(p0 + n_out * (tf + ze))]
                e = M.extrude(C([ccw(np.array(poly, float))]), u1 - u0).transform([[0, 0, 1, u0], [1, 0, 0, 0], [0, 1, 0, 0]]); streifen.append(e)
        if streifen: q = UNION([q] + streifen)
    ctx["dach"] = dict(ntv=ntv, ztv=ztv, nf=nf, zf=zf, u0=u0, u1=u1)                              # fuer gaubenreihe (sitzt auf dem Vorderhang)
    k = q.transform(_uszT(cfg)); wq = cfg.get("werte_quellen") or {}; qq = lambda p_: (wq.get(p_) or cfg["quelle"])
    beleg("alle", "Satteldach", qq("z_first") + " | Traufe: " + qq("z_traufe_v"), u0=u0, u1=u1, n_traufe_v=ntv, z_traufe_v=ztv, n_first=nf, z_first=zf, n_traufe_h=nth, z_traufe_h=zth, z_unten=zu)
    return [k], []


@bauteil("gaubenreihe")
def gaubenreihe(cfg, ctx):
    """Reihe gleicher Dachgauben auf dem Vorderhang des vorher gebauten Satteldachs (ctx['dach']). Je Gaube: form 'schlepp' (Standard, Fotobefund 8.11.): senkrechte Stirn + flaches Pultdach (Huelle) bis zum Hang; form 'giebel': Wandkasten + Giebeldach (Prisma, First parallel zur Hangfallinie).
    Pflicht: n_gauben (ZAEHLUNG am Foto, Regel 9: 'zaehlung': [Z-Protokolle]), u_mitte (Mitte der Reihe), pitch, t (Lage am Hang: 0 Traufe .. 1 First), breite, wandhoehe, vor (Stirnwand vor dem Hang),
    tiefe (Kasten hinter der Stirnwand in den Hang), firsthoehe (Giebel ueber der Wand), achse_n, achse_quelle, quelle. werte_quellen {param: quelle}.
    Optional (form schlepp, Fensterkasten + Vordach, 2026-11-10): vordach_vor (Vordach steht so weit vor der Stirn), vordach_breite (> breite), vordach_dicke, dach_tiefe (Stirn bis Anschluss Hang); dann ist wandhoehe die Stirnhoehe bis zur Vordach-UNTERkante und breite die Stirnbreite."""
    for k in ("n_gauben", "u_mitte", "pitch", "t", "breite", "wandhoehe", "vor", "tiefe", "firsthoehe", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"gaubenreihe: '{k}' fehlt (Regel 3b)")
    D = ctx.get("dach") or sys.exit("gaubenreihe: braucht ein Satteldach davor in der Bauteilliste")
    ng = int(cfg["n_gauben"]); um, pitch, t, b, hw, vor, ti, hf = (float(cfg[k]) for k in ("u_mitte", "pitch", "t", "breite", "wandhoehe", "vor", "tiefe", "firsthoehe"))
    if ng < 1 or b <= 0.2 or hw <= 0.2 or ti <= 0.1 or hf <= 0.1 or not (0 < t < 1) or (ng > 1 and pitch <= b + 0.1): sys.exit(f"gaubenreihe: unplausible Masse (n={ng}, pitch={pitch}, b={b}, t={t})")
    ntv, ztv, nf, zf = D["ntv"], D["ztv"], D["nf"], D["zf"]; sl = (zf - ztv) / (ntv - nf)                # Hang steigt mit sinkendem n: z(n) = ztv + (ntv - n) * sl
    nc, zc = ntv + t * (nf - ntv), ztv + t * (zf - ztv); nfront = nc + vor; zfront = ztv + (ntv - nfront) * sl
    teile = []
    for i in range(ng):
        uc = um + (i - (ng - 1) / 2.0) * pitch
        n0, n1 = nfront - ti - vor, nfront                                                           # Kasten von im Hang bis Stirnwand
        z0 = zfront - 0.05; z1 = zfront + hw
        if cfg.get("form", "schlepp") == "schlepp" and cfg.get("vordach_vor") is not None:           # Schleppgaube MIT Fensterkasten + Vordach (Foto 2026-11-10): schmale Stirn (breite) mit Fensterbank, darueber ziegelgedecktes Vordach (vordach_breite) das vordach_vor vor der Stirn steht; Pultdach laeuft dach_tiefe hinter der Stirn in den Hang
            vv, bh, dh, xd = (float(cfg[k_]) for k_ in ("vordach_vor", "vordach_breite", "vordach_dicke", "dach_tiefe"))
            if bh <= b or vv <= 0 or dh <= 0.02 or xd <= 0.3: sys.exit(f"gaubenreihe: unplausibles Vordach (breite {b}, vordach_breite {bh}, vor {vv}, dicke {dh}, tiefe {xd})")
            nb_ = nfront - xd; zm = zfront + xd * sl; zlow = z1                                       # z1 = Unterkante des Vordachs (Stirnhoehe wandhoehe ueber dem Hang an der Stirn)
            stirn = [(u_, nfront, zfront - 0.05) for u_ in (uc - b / 2, uc + b / 2)] + [(u_, nfront, zlow + 0.2) for u_ in (uc - b / 2, uc + b / 2)] + [(u_, nb_, zm + e_) for u_ in (uc - b / 2, uc + b / 2) for e_ in (-0.05, -0.1)]
            dach = [(u_, nfront + vv, z_) for u_ in (uc - bh / 2, uc + bh / 2) for z_ in (zlow, zlow + dh)] + [(u_, nb_, zm + e_) for u_ in (uc - bh / 2, uc + bh / 2) for e_ in (0.0, -0.05)]
            teile.append(UNION([M.hull_points(stirn), M.hull_points(dach)]))
            continue
        if cfg.get("form", "schlepp") == "schlepp":                                                  # Schleppgaube ('Sprungschanze', Nutzer 8.11. nach Fotos): senkrechte Stirn, flaches Pultdach steigt zum Hang
            x = max(ti, hw / max(sl - 0.12, 0.2)); nb_ = nfront - x; zm = zfront + x * sl                # Pultdach schneidet den Hang bei x hinter der Stirn
            pts = [(u_, nfront, zfront - 0.05) for u_ in (uc - b / 2, uc + b / 2)] + [(u_, nfront, z1) for u_ in (uc - b / 2, uc + b / 2)] + [(u_, nb_, zm + e_) for u_ in (uc - b / 2, uc + b / 2) for e_ in (0.0, -0.05)]
            teile.append(M.hull_points(pts))
            continue
        kasten = quader(uc - b / 2, uc + b / 2, n0, n1, z0, z1)
        gi = prisma_uz(np.array([(uc - b / 2, z1 - 0.01), (uc + b / 2, z1 - 0.01), (uc, z1 + hf)], float), n0, n1)                                  # Giebel zur Strasse: Dreieck (u, z), entlang n extrudiert
        teile.append(kasten + gi)
    k = UNION(teile).transform(_uszT(cfg)); wq = cfg.get("werte_quellen") or {}; qq = lambda p_: (wq.get(p_) or cfg["quelle"])
    if cfg.get("vordach_vor") is not None: beleg("alle", f"Gauben {cfg.get('gruppe', '')}: Vordach", qq("vordach_vor") + " | Breite: " + qq("vordach_breite") + " | Tiefe: " + qq("dach_tiefe") + " | Dicke: " + qq("vordach_dicke"), vordach_vor=cfg["vordach_vor"], vordach_breite=cfg["vordach_breite"], vordach_dicke=cfg["vordach_dicke"], dach_tiefe=cfg["dach_tiefe"])
    beleg("alle", f"Gauben {cfg.get('gruppe', '')} ({ng})", f"Anzahl {', '.join(cfg.get('zaehlung', [])) or 'Foto'} (Regel 9); Lage/Masse: " + qq("t"), n_gauben=ng, u_mitte=um, pitch=pitch, t=t, breite=b, wandhoehe=hw, vor=vor, tiefe=ti, firsthoehe=hf)
    return [k], []


@bauteil("staffelgiebel")
def staffelgiebel(cfg, ctx):
    """Staffel-/Treppengiebel an EINEM Hausende: Scheibe (Dicke in u) mit Treppenprofil in (n, z): Rueckkante senkrecht bei n_hinten bis z_spitze, Spitzenbreite, dann n_stufen Stufen
    entlang der Giebellinie nach vorn (n_vorn, z_traufe), Stufenoberkante = Linie am inneren Stufenende + kappe. Alle Masse aus objekt.json (Messung: Wolke, param_wolke_fit.py), n_stufen = ZAEHLUNG am Foto (Regel 9).
    Pflicht: n_stufen, u_aussen, richtung (+1 Ostende: Scheibe von u_aussen nach innen = -u, -1 Westende), dicke, n_hinten, n_vorn, z_unten, z_traufe, z_spitze, spitze_breite, kappe, achse_n, achse_quelle, quelle."""
    for k in ("n_stufen", "u_aussen", "richtung", "dicke", "n_hinten", "n_vorn", "z_unten", "z_traufe", "z_spitze", "spitze_breite", "kappe", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"staffelgiebel: '{k}' fehlt (Regel 3b)")
    ns = int(cfg["n_stufen"]); ua, rd, dk, nb, nv, zu, zt, zs, sb, kp = (float(cfg[k]) for k in ("u_aussen", "richtung", "dicke", "n_hinten", "n_vorn", "z_unten", "z_traufe", "z_spitze", "spitze_breite", "kappe"))
    n2 = nb + sb
    if ns < 1 or dk < 0.1 or not (nb < n2 < nv) or not (zu < zt < zs): sys.exit(f"staffelgiebel: unplausible Masse (n={ns}, n={nb}/{n2}/{nv}, z={zu}/{zt}/{zs})")
    w = (nv - n2) / ns; lin = lambda n_: zs - (n_ - n2) * (zs - zt) / (nv - n2)                      # Giebellinie von der Spitzenecke (n2, zs) zur Traufe (nv, zt)
    oben = [(n2, zs)]
    for i in range(ns):
        zk = lin(n2 + i * w) + kp if i else zs; zk = min(zk, zs)
        oben += [(n2 + i * w, zk), (n2 + (i + 1) * w, zk)]
    if cfg.get("spiegel"):                                                                            # Stufen beidseitig: Rueckflanke = Spiegel der Vorderflanke an der Spitzenmitte (nb+n2)/2 (cfg['spiegel_quelle'] nennen)
        nm = (nb + n2) / 2; poly = [(2 * nm - nv, zu)] + [(2 * nm - n_, z_) for n_, z_ in reversed(oben)] + oben + [(nv, zu)]
    else: poly = [(nb, zu), (nb, zs)] + oben + [(nv, zu)]
    q = M.extrude(C([ccw(np.array(poly, float))]), dk).transform([[0, 0, 1, (ua - dk) if rd > 0 else ua], [1, 0, 0, 0], [0, 1, 0, 0]])
    k = q.transform(_uszT(cfg)); wq = cfg.get("werte_quellen") or {}; qq = lambda p_: (wq.get(p_) or cfg["quelle"])
    beleg("alle", f"Staffelgiebel {cfg.get('gruppe', '')} ({ns} Stufen)", f"Stufenzahl {', '.join(cfg.get('zaehlung', [])) or 'Foto'} (Regel 9); " + qq("z_spitze") + (" | Rueckflanke gespiegelt: " + qq("spiegel") if cfg.get("spiegel") else ""), n_stufen=ns, u_aussen=ua, dicke=dk, n_hinten=nb, n_vorn=nv, z_traufe=zt, z_spitze=zs, spitze_breite=sb, kappe=kp, **({"spiegel": True} if cfg.get("spiegel") else {}))
    return [k], []


@bauteil("fensterreihe")
def fensterreihe(cfg, ctx):
    """Reihe gotischer Kielbogenfenster in der Wandebene (u entlang, s Normale, z): je Fenster Rahmen (Aussenkontur Rechteck bis kaempfer_z, darueber Kielbogen bis scheitel_z; Rahmenbreite rahmen_b),
    ein Mittelpfosten (pfosten_b) und ein Kaempfer-Riegel (riegel_z, riegel_h). Frei: kiel (-1..1) = Schulterform (0 = Spitzgiebel, >0 Eselsruecken). Plexi/Glas fehlt bewusst (Wolke blind, spaeter).
    Pflicht: n_fenster, u_mitte (Mitte 1. Fenster), pitch, breite, unterseite_z, kaempfer_z, scheitel_z, wand_n, tiefe, rahmen_b, pfosten_b, riegel_z, riegel_h, achse_n, achse_quelle, quelle (+ zaehlung).
    Anzahl n_fenster NUR aus Foto-Zaehlprotokoll (Regel 9); Lage/Masse per tools/param_wolke_fit.py gegen die Wolke.
    Optional n_lichter (Standard 2 = ein Mittelpfosten, unveraendertes Altverhalten): Lichter je Fenster, n_lichter-1 gleich breite Pfosten (Kantengitter 2026-11-09: 3 Lichter je Gruppe); Zaehlart -> 'zaehlung'."""
    for k in ("n_fenster", "u_mitte", "pitch", "breite", "unterseite_z", "kaempfer_z", "scheitel_z", "wand_n", "tiefe", "rahmen_b", "pfosten_b", "riegel_z", "riegel_h", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"fensterreihe: '{k}' fehlt (Regel 3b: jedes Mass mit Quelle)")
    nf = int(cfg["n_fenster"]); u0, pitch, b = float(cfg["u_mitte"]), float(cfg["pitch"]), float(cfg["breite"]); nl = max(1, int(cfg.get("n_lichter", 2)))
    z0, zk, zs = float(cfg["unterseite_z"]), float(cfg["kaempfer_z"]), float(cfg["scheitel_z"]); wn, td = float(cfg["wand_n"]), float(cfg["tiefe"])
    rb, pf, rz, rh = float(cfg["rahmen_b"]), float(cfg["pfosten_b"]), float(cfg["riegel_z"]), float(cfg["riegel_h"]); kiel = float(cfg.get("kiel", 0.4)); gd, go = float(cfg.get("glas_d", 0.0)), float(cfg.get("glas_n", 0.1)); wq = cfg.get("werte_quellen") or {}; ein = float(cfg.get("einbindung", 0.0))   # optional Einbindung (m) von Rahmen/Pfosten/Riegel hinter wand_n
    if nf < 1 or b >= pitch or not (z0 < zk < zs) or rb * 2 >= b or td < 0.01: sys.exit(f"fensterreihe: unplausible Masse (n={nf}, b={b}, pitch={pitch}, z={z0}/{zk}/{zs})")
    n_ = np.array(cfg["achse_n"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
    T = [[u_[0], n_[0], 0.0, 0.0], [u_[1], n_[1], 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]
    teile = []
    for i in range(nf):
        uc = u0 + i * pitch; h = zs - zk; t = np.linspace(0, 1, 16)
        zz = zk + h * (t - kiel * np.sin(2 * np.pi * t) / (2 * np.pi)); right = [(uc + b / 2 * (1 - tt), z_) for tt, z_ in zip(t, zz)]; left = [(uc - b / 2 * (1 - tt), z_) for tt, z_ in zip(t[::-1], zz[::-1])]
        poly = np.array([(uc - b / 2, z0), (uc + b / 2, z0)] + right + left[1:], float)
        if cfg.get("kontur"): poly = np.array([(uc + float(x_), z0 + float(z_)) for x_, z_ in cfg["kontur"]], float)   # frei gezeichnete Fensterkontur (tools/editor_modell.py): [[u rel. Fenstermitte, z rel. unterseite_z], ...]
        outer = C([ccw(poly)]); inner = outer.offset(-rb, JoinType.Miter)
        rahmen = M.extrude(outer - inner, td + ein).transform([[1, 0, 0, 0], [0, 0, -1, wn + td], [0, 1, 0, 0]])   # ein = Einbindung hinter die Wandebene (Druck: sonst nur flaechige Beruehrung = eigener Koerper)
        teile.append(rahmen)
        if gd > 0: teile.append(M.extrude(outer.offset(-rb + min(0.01, rb / 2), JoinType.Miter) if ein > 0 else inner, gd + ein / 2).transform([[1, 0, 0, 0], [0, 0, -1, wn + go + gd], [0, 1, 0, 0]]))   # mit Einbindung: Platte reicht ein/2 nach hinten (nicht ein: Rueckseite sonst koplanar mit Pfosten/Riegel -> Splitter) (Druck: Platte vor der Wand beruehrt sonst nur die Rahmenkanten)   # Verglasung (Wolke sieht die Scheibe): duenne Platte in der Rahmenoeffnung
        wl = (b - 2 * rb - (nl - 1) * pf) / nl                                                        # Lichtbreite; nl = 2 ergibt exakt den alten Mittelpfosten bei uc
        for j in range(1, nl):
            up = uc - b / 2 + rb + j * wl + (j - 0.5) * pf; teile.append(quader(up - pf / 2, up + pf / 2, wn - ein, wn + td, z0 + rb * 0.5, zs - rb * 1.5))
        lk, ls = cfg.get("licht_riegel_z"), cfg.get("licht_scheitel_z")                              # optional je Licht (von aussen zur Mitte, gespiegelt): Riegelhoehe / Lichtoberkante
        if not lk: teile.append(quader(uc - b / 2 + rb * 0.5, uc + b / 2 - rb * 0.5, wn - ein, wn + td, rz - rh / 2, rz + rh / 2))
        for j in range(nl):
            a_ = uc - b / 2 + rb + j * (wl + pf); e_ = a_ + wl; sp = min(j, nl - 1 - j)                  # Licht j: a_..e_; sp = Spiegelindex (0 = aussen)
            a2, e2 = a_ - (rb * 0.5 if j == 0 else pf / 2), e_ + (rb * 0.5 if j == nl - 1 else pf / 2)   # bis in Rahmen/Pfosten (Ueberlappung, keine Splitter)
            if lk: zr = float(lk[min(sp, len(lk) - 1)]); teile.append(quader(a2, e2, wn - ein, wn + td, zr - rh / 2, zr + rh / 2))
            if ls and ls[min(sp, len(ls) - 1)] is not None:                                          # Lichtoberkante tiefer als die Kontur: Fuellung zwischen Scheitel und Rahmen
                zt = float(ls[min(sp, len(ls) - 1)]); fuell = C([ccw(np.array([(a2, zt), (e2, zt), (e2, zs + 1.0), (a2, zs + 1.0)]))]) ^ outer
                teile.append(M.extrude(fuell, td + ein).transform([[1, 0, 0, 0], [0, 0, -1, wn + td], [0, 1, 0, 0]]))
    k = UNION(teile).transform(T); q = lambda p_: (wq.get(p_) or cfg["quelle"])
    if cfg.get("licht_riegel_z") or cfg.get("licht_scheitel_z"):
        beleg("alle", "Fensterreihe: Kaempferriegel/Scheitel je Licht (gespiegelt, aussen->Mitte)", q("licht_riegel_z") + (" | Scheitel: " + q("licht_scheitel_z") if cfg.get("licht_scheitel_z") else ""),
              licht_riegel_z=cfg.get("licht_riegel_z"), licht_scheitel_z=cfg.get("licht_scheitel_z"))
    beleg("alle", f"Fensterreihe {nf} Kielbogenfenster" + (f" ({nl} Lichter)" if nl != 2 else ""), f"Anzahl {', '.join(cfg.get('zaehlung', [])) or 'Foto'} (Regel 9); " + (q("n_lichter") + "; " if nl != 2 else "") + q("breite") + " | Lage: " + q("u_mitte"), n_fenster=nf, n_lichter=nl, pitch=pitch, breite=b, unterseite_z=z0, kaempfer_z=zk, scheitel_z=zs, wand_n=wn, tiefe=td)
    return [k], []

@bauteil("quader")
def quader_bt(cfg, ctx):
    """Allgemeiner Quader in Fassadenkoordinaten (u entlang, n Normale, z Hoehe): modus 'anbau' (Standard, Koerper) oder 'ausschnitt' (Aussparung, z. B. Fensternische).
    Pflicht: u0, u1, n0, n1, z0, z1, achse_n, achse_quelle, quelle. Optional: modus, werte_quellen, aktiv. Formenkatalog fuer fehlstellen_3d (Leiste/Gesims/Nische)."""
    for k in ("u0", "u1", "n0", "n1", "z0", "z1", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"quader: '{k}' fehlt (Regel 3b: jedes Mass mit Quelle)")
    u0, u1, n0, n1, z0, z1 = (float(cfg[k]) for k in ("u0", "u1", "n0", "n1", "z0", "z1"))
    if abs(u1 - u0) < 0.02 or abs(n1 - n0) < 0.01 or abs(z1 - z0) < 0.02: sys.exit(f"quader: unplausible Masse ({u0}..{u1}, {n0}..{n1}, {z0}..{z1})")
    k = quader(u0, u1, min(n0, n1), max(n0, n1), min(z0, z1), max(z0, z1)).transform(_uszT(cfg)); modus = cfg.get("modus", "anbau")
    beleg("alle", f"Quader ({modus})", cfg["quelle"], u0=u0, u1=u1, n0=n0, n1=n1, z0=z0, z1=z1)
    return ([k], []) if modus != "ausschnitt" else ([], [k])

@bauteil("freiform")
def freiform_bt(cfg, ctx):
    """Frei gezeichnete Form (Nutzer im Foto, tools/editor_modell.py): Kontur [[u, v], ...] auf einer Ebene, ausgezogen um 'tiefe' senkrecht zur Ebene (+ = nach aussen, zur Strasse).
    Ebene: n-Koordinate ebene_s bei Hoehe ebene_z, Neigung neigung_grad (0 = senkrechte Wand, -40 = Dachflaeche nach hinten ansteigend): Punkt (u, v) -> (u, ebene_s + v sin a, ebene_z + v cos a).
    modus 'anbau' (Standard, Koerper) oder 'ausschnitt' (Aussparung). Pflicht: kontur (>= 3 Punkte), ebene_s, ebene_z, neigung_grad, tiefe, achse_n, achse_quelle, quelle (Regel 3b)."""
    for k in ("kontur", "ebene_s", "ebene_z", "neigung_grad", "tiefe", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"freiform: '{k}' fehlt (Regel 3b: jedes Mass mit Quelle)")
    P = np.array(cfg["kontur"], float); s0, z0, al, td = float(cfg["ebene_s"]), float(cfg["ebene_z"]), np.radians(float(cfg["neigung_grad"])), float(cfg["tiefe"])
    if len(P) < 3 or td < 0.005: sys.exit(f"freiform: unplausibel ({len(P)} Punkte, tiefe {td})")
    sa, ca = np.sin(al), np.cos(al); poly = ccw(np.c_[-P[:, 0], P[:, 1]])                          # x = -u (damit die Abbildung nach (u,s,z) eigentlich = Drehung bleibt)
    solid = M.extrude(C([poly]), td).transform([[-1, 0, 0, 0], [0, sa, ca, s0], [0, ca, -sa, z0]]).transform(_uszT(cfg)); modus = cfg.get("modus", "anbau")
    beleg("alle", f"Freiform {cfg.get('typ', '')} ({modus})", cfg["quelle"], punkte=len(P), ebene_s=s0, ebene_z=z0, neigung_grad=float(cfg["neigung_grad"]), tiefe=td)
    return ([solid], []) if modus != "ausschnitt" else ([], [solid])

@bauteil("zylinder")
def zylinder_bt(cfg, ctx):
    """Senkrechter Zylinder/Kegelstumpf (Saeule, Pfeiler, Rundturm) bei (u, n): radius unten, radius_oben (Standard = radius), z0..z1. modus 'anbau'|'ausschnitt'.
    Pflicht: u, n, z0, z1, radius, achse_n, achse_quelle, quelle."""
    for k in ("u", "n", "z0", "z1", "radius", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"zylinder: '{k}' fehlt (Regel 3b)")
    u_, n_, z0, z1, r = (float(cfg[k]) for k in ("u", "n", "z0", "z1", "radius")); ro = float(cfg.get("radius_oben") or r)
    if z1 - z0 < 0.02 or r < 0.01: sys.exit("zylinder: unplausible Masse")
    k = M.cylinder(z1 - z0, r, ro, 40).translate((u_, n_, z0)).transform(_uszT(cfg)); modus = cfg.get("modus", "anbau")
    beleg("alle", f"Zylinder ({modus})", cfg["quelle"], u=u_, n=n_, z0=z0, z1=z1, radius=r)
    return ([k], []) if modus != "ausschnitt" else ([], [k])

@bauteil("helm_geschweift")
def helm_geschweift(cfg, ctx):
    """Geschweifter (glockenfoermiger) Polygonhelm bei (u, n) (Nutzerbefund 2026-11-09: Erkerhelme sind konkav ausgeschweift, Fuss fast erkerbreit; ein gerader Kegel
    aus dem Wolkenfit sah nur die Nadel). Grundriss = regelmaessiges n_seiten-Eck, drehung_grad (0 = eine Seite zeigt nach +n), Profil r(z) = Apothema (halbe Breite
    ueber die Flaechen) als Liste [[z, r], ...] aufsteigend; zwischen zwei Ringen konvexe Huelle (Kegelstumpf je Abschnitt) -> konkave Gesamtkurve.
    Optional: kranz {z0, z1, r} (Traufkranz/Unterbau unter der Traufe, gleiches Polygon), knauf {z, r} (Kugel als 12-Eck-Doppelpyramide), z_spitze/r_spitze (Nadel).
    Pflicht: u, n, n_seiten, profil, z_spitze, achse_n, achse_quelle, quelle. Druck: Nadelradius >= r_spitze."""
    for k in ("u", "n", "n_seiten", "profil", "z_spitze", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"helm_geschweift: '{k}' fehlt (Regel 3b)")
    u_, n_ = float(cfg["u"]), float(cfg["n"]); N = int(cfg["n_seiten"]); dr = np.radians(float(cfg.get("drehung_grad", 0.0))); zs = float(cfg["z_spitze"]); rs = float(cfg.get("r_spitze", 0.02))
    prof = sorted([(float(z), float(r)) for z, r in cfg["profil"]]) + [(zs, rs)]
    if N < 3 or any(b[0] <= a[0] for a, b in zip(prof, prof[1:])) or min(r for _, r in prof) <= 0: sys.exit(f"helm_geschweift: unplausibles Profil {prof}")
    ph = dr + np.pi / 2 + np.pi / N                                                                  # Ecken so, dass eine Flaechenmitte bei Winkel dr+90 Grad (= +n) liegt
    def ring(z, r): R = r / np.cos(np.pi / N); return [[u_ + R * np.cos(ph + 2 * np.pi * i / N), n_ + R * np.sin(ph + 2 * np.pi * i / N), z] for i in range(N)]
    teile = [M.hull_points(ring(z0, r0) + ring(z1, r1)) for (z0, r0), (z1, r1) in zip(prof, prof[1:])]
    kr = cfg.get("kranz")
    if kr: teile.append(M.hull_points(ring(float(kr["z0"]), float(kr["r"])) + ring(float(kr["z1"]) + 0.01, float(kr["r"]))))
    kn = cfg.get("knauf")
    if kn:
        zk, rk = float(kn["z"]), float(kn["r"]); kug = [[u_ + rk * np.cos(a) * np.cos(b), n_ + rk * np.sin(a) * np.cos(b), zk + rk * np.sin(b)] for a in np.linspace(0, 2 * np.pi, 12, endpoint=False) for b in (-1.2, -0.6, 0, 0.6, 1.2)]
        teile.append(M.hull_points(kug + [[u_, n_, zk - rk], [u_, n_, zk + rk]]))
    k = UNION(teile).transform(_uszT(cfg)); wq = cfg.get("werte_quellen") or {}; q = lambda p_: (wq.get(p_) or cfg["quelle"])
    beleg("alle", f"Geschweifter Helm ({N}-Eck) u={u_:.2f}", q("profil") + " | Lage: " + q("u") + " | Grundriss: " + q("n_seiten"), u=u_, n=n_, n_seiten=N, profil=prof, kranz=kr, knauf=kn)
    return [k], []

@bauteil("bruestung")
def bruestung_bt(cfg, ctx):
    """Balkonbruestung: n_baluster gleiche Baluster (Zylinder, Radius r) im Raster pitch ab u0 (Achse n), zwischen Platten-Oberkante z0 und Handlauf
    (z_handlauf_unten..z_handlauf_oben, Breite handlauf_b quer). Anzahl/Periode NUR aus Foto-Zaehlung (Regel 9: 'zaehlung' = Z-Protokolle). Baluster als Zylinder = ANNAHME H0
    (Vasenform nicht druckbar). Pflicht: n_baluster, u0, pitch, n, r, z0, z_handlauf_unten, z_handlauf_oben, handlauf_b, achse_n, achse_quelle, quelle."""
    for k in ("n_baluster", "u0", "pitch", "n", "r", "z0", "z_handlauf_unten", "z_handlauf_oben", "handlauf_b", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"bruestung: '{k}' fehlt (Regel 3b)")
    nb = int(cfg["n_baluster"]); u0, pitch, n_, r, z0, zh0, zh1, hb = (float(cfg[k]) for k in ("u0", "pitch", "n", "r", "z0", "z_handlauf_unten", "z_handlauf_oben", "handlauf_b"))
    if nb < 1 or pitch <= 2 * r or r < 0.01 or not (z0 < zh0 < zh1): sys.exit(f"bruestung: unplausible Masse (n={nb}, pitch={pitch}, r={r}, z={z0}/{zh0}/{zh1})")
    # Optional Pfosten (Felder): pfosten_alle = Rasterplaetze je Feld+Pfosten (z. B. 12 = 11 Baluster + 1 Pfosten, Zaehlung am Foto), pfosten_erster = Rasterplatz des
    # ersten Pfostens (0-basiert ab u0), pfosten_b/pfosten_t = Breite (u) / Tiefe (n) des Pfostens. Der Pfosten ERSETZT den Baluster auf seinem Rasterplatz.
    pa = int(cfg.get("pfosten_alle") or 0); pe = int(cfg.get("pfosten_erster") or 0); pb_, pt_ = float(cfg.get("pfosten_b") or 0.0), float(cfg.get("pfosten_t") or 0.0)
    if pa and (pa < 2 or pb_ <= 2 * r or pb_ >= 2 * pitch or pt_ < 2 * r): sys.exit(f"bruestung: unplausible Pfosten (alle={pa}, b={pb_}, t={pt_})")
    ist_pf = lambda i: pa > 0 and i >= pe and (i - pe) % pa == 0
    teile = [M.cylinder(zh0 - z0 + 0.04, r, r, 16).translate((u0 + i * pitch, n_, z0 - 0.02)) for i in range(nb) if not ist_pf(i)]   # 2 cm in Platte und Handlauf eingebunden (ein Koerper)
    pf_u = [u0 + i * pitch for i in range(nb) if ist_pf(i)]
    teile += [quader(uc - pb_ / 2, uc + pb_ / 2, n_ - pt_ / 2, n_ + pt_ / 2, z0 - 0.02, zh0 + 0.02) for uc in pf_u]
    teile.append(quader(u0 - pitch / 2, u0 + (nb - 1) * pitch + pitch / 2, n_ - hb / 2, n_ + hb / 2, zh0, zh1))
    k = UNION(teile).transform(_uszT(cfg)); wq = cfg.get("werte_quellen") or {}; q = lambda p_: (wq.get(p_) or cfg["quelle"])
    beleg("alle", f"Bruestung: {nb - len(pf_u)} Baluster (Zylinder r {r:.3f}) + Handlauf", f"Anzahl/Periode {', '.join(cfg.get('zaehlung', [])) or 'Foto'} (Regel 9); " + q("pitch") + " | Lage: " + q("u0") + " | Handlauf: " + q("z_handlauf_oben"),
          n_baluster=nb - len(pf_u), u0=u0, pitch=pitch, n=n_, r=r, z0=z0, z_handlauf_unten=zh0, z_handlauf_oben=zh1)
    if pf_u: beleg("alle", f"Bruestung: {len(pf_u)} Pfosten (je {pa - 1} Baluster je Feld)", f"Feldteilung {', '.join(cfg.get('zaehlung', [])) or 'Foto'} (Regel 9); Lage: " + q("pfosten_erster") + " | Breite: " + q("pfosten_b") + " | Tiefe: " + q("pfosten_t"),
                   n_pfosten=len(pf_u), pfosten_u=[round(v, 3) for v in pf_u], pfosten_b=pb_, pfosten_t=pt_)
    return [k], []

@bauteil("pyramide")
def pyramide_bt(cfg, ctx):
    """Pyramide/Helm: Rechteckgrundflaeche (breite_u x breite_n) bei (u, n) auf z0, Spitze bei z0+hoehe (Versatz spitze_du/spitze_dn optional), Huelle ueber Grundflaeche und Spitze.
    Pflicht: u, n, z0, hoehe, breite_u, breite_n, achse_n, achse_quelle, quelle."""
    for k in ("u", "n", "z0", "hoehe", "breite_u", "breite_n", "achse_n", "achse_quelle", "quelle"):
        if cfg.get(k) in (None, ""): sys.exit(f"pyramide: '{k}' fehlt (Regel 3b)")
    u_, n_, z0, h, bu, bn = (float(cfg[k]) for k in ("u", "n", "z0", "hoehe", "breite_u", "breite_n")); du, dn = float(cfg.get("spitze_du") or 0), float(cfg.get("spitze_dn") or 0)
    if h < 0.05 or bu < 0.05 or bn < 0.05: sys.exit("pyramide: unplausible Masse")
    pts = [[u_ + a * bu / 2, n_ + b * bn / 2, z0] for a in (-1, 1) for b in (-1, 1)] + [[u_ + du, n_ + dn, z0 + h]]
    k = M.hull_points(pts).transform(_uszT(cfg)); modus = cfg.get("modus", "anbau")
    beleg("alle", f"Pyramide ({modus})", cfg["quelle"], u=u_, n=n_, z0=z0, hoehe=h)
    return ([k], []) if modus != "ausschnitt" else ([], [k])

# ------------------------------------------------------------------ Bau
def main():
    ctx = {}; adds, cuts = [], []
    ueber = json.loads(os.environ.get("BAUTEIL_PARAM", "{}"))                                    # param_suche.py: {"<typ>": {"<param>": wert, "quelle": "..."}} ohne objekt.json zu aendern
    liste = list(OBJ.get("bauteile") or [{"typ": "rumpf_lod2"}])
    liste += [dict(typ=t_, **{k: v for k, v in c_.items() if k != "anhaengen"}) for t_, c_ in ueber.items() if isinstance(c_, dict) and c_.get("anhaengen") and t_ not in {s_["typ"] for s_ in liste}]   # qualitaetsstufen: zusaetzliche Bauteile ohne objekt.json-Aenderung
    for spec in liste:
        if spec["typ"] in ueber: spec = {**spec, **{k: v for k, v in ueber[spec["typ"]].items() if k != "anhaengen"}}
        if os.environ.get("NUR_BAUTEIL") and spec["typ"] not in os.environ["NUR_BAUTEIL"].split(","): continue   # param_wolke_fit.py: nur dieses Bauteil bauen (schnelle Wolken-Anpassung)
        if spec.get("aktiv", True) is False: continue                                             # nach dem Ueberschreiben: BAUTEIL_PARAM darf Bauteile abschalten
        a, c = BAUTEILE[spec["typ"] if spec["typ"] in BAUTEILE else spec["typ"].split(":")[0]](spec, ctx); adds += a; cuts += c   # "typ:name" = Instanz eines Typs (eigener Schluessel in BAUTEIL_PARAM/Parameterraum)
        print(f"  {spec['typ']}: +{len(a)} / -{len(c)}")
        if os.environ.get("BAUTEILE_AUS") and (a or c):                                               # 2026-11-09 R6 Sichtliste je Bauteil: jedes Bauteil einzeln als STL (mm, gleicher Rahmen wie das Modell)
            os.makedirs(os.environ["BAUTEILE_AUS"], exist_ok=True); m_ = UNION(a or c).scale((K, K, K)).to_mesh()
            _V, _F = np.asarray(m_.vert_properties)[:, :3], np.asarray(m_.tri_verts)
            if len(_F):
                import trimesh as _tmb; _fn = spec["typ"].replace(":", "__") + ("__ausschnitt" if not a else "") + ".stl"; _tmb.Trimesh(_V, _F, process=False).export(os.path.join(os.environ["BAUTEILE_AUS"], _fn))
                _lp = os.path.join(os.environ["BAUTEILE_AUS"], "liste.json"); _l = json.load(open(_lp)) if os.path.exists(_lp) and ctx.get("_liste_neu") else {}; ctx["_liste_neu"] = True   # Liste DIESES Laufs (alte STL im Ordner bleiben liegen, zaehlen nicht)
                _l[spec["typ"]] = dict(datei=_fn, modus="anbau" if a else "ausschnitt"); json.dump(_l, open(_lp, "w"), indent=1)
    if not adds:                                                                                  # nur Rohdreiecke (stl_teil): kein Manifold-Koerper
        model = None; V = np.zeros((0, 3)); Fi = np.zeros((0, 3), int)
    else:
        model = UNION(adds)
        if cuts:                                                                                      # Schnitt, der die Aussenhaut nicht erreicht (ganz im Koerper, z. B. Wandfenster hinter einem Erker),
            innen = [c_ for c_ in cuts if (c_ - model).is_empty()]                                   # gaebe einen eingeschlossenen Hohlraum (unsichtbar, nicht druckbar, Pruefstand 'getrennte Koerper',
            if innen:                                                                                # null5e 2026-11-05: 8 Hohlraeume hinter dem Ost-Erker) -> weglassen und melden
                cuts = [c_ for c_ in cuts if not (c_ - model).is_empty()]; print(f"  {len(innen)} Schnitt(e) ganz im Koerper (verdeckt, Hohlraum) weggelassen")
                beleg("alle", f"{len(innen)} verdeckte Schnitte weggelassen", "baukasten_gen: Schnitt ohne Kontakt zur Aussenhaut = eingeschlossener Hohlraum (nicht sichtbar, nicht druckbar)")
            model = model - UNION(cuts)
        teile = model.decompose()                                                                     # Anbauteile ohne Kontakt (Figuren vor der Wand, s3_v6 5.11.: Tor verwarf sie trotz Fotogewinn t -11,9)
        if len(teile) > 1 and (OBJ.get("druck") or {}).get("anbau_konsolen", True):                  # objekt.json druck.anbau_konsolen=false: Anpassungsphase ohne Rumpf-Volumen (Huelle fuellte Arkadenboegen); Druckstufe: true
            # -> Splitter < 1e-3 m3 weg, sonst Konsole: Huelle(untere 20 % + dieselben Punkte 0,1 m in die naechste Flaeche)
            import trimesh as _tm; from scipy.spatial import cKDTree
            teile = sorted(teile, key=lambda t_: -t_.volume()); haupt = teile[0]; hm = haupt.to_mesh()
            hT = _tm.Trimesh(np.asarray(hm.vert_properties)[:, :3], np.asarray(hm.tri_verts), process=False); P_, _ = _tm.sample.sample_surface_even(hT, 200000, seed=1); kd = cKDTree(P_)
            model, n_s, n_k = haupt, 0, 0; rund = float((OBJ.get('druck') or {}).get('konsole_rundung_m', 0.002))   # ANNAHME 2 mm Modellmass = 0,023 mm im Druck, weit unter jeder Duese
            for t_ in teile[1:]:
                if t_.volume() < 1e-3: n_s += 1; continue
                V_ = np.asarray(t_.to_mesh().vert_properties)[:, :3]; z_ = V_[:, 2]; un = V_[z_ <= z_.min() + 0.2 * (z_.max() - z_.min())]
                dd, ii = kd.query(un); ri = P_[ii] - un; ri /= np.maximum(np.linalg.norm(ri, axis=1, keepdims=True), 1e-9)
                hp = np.vstack([un, P_[ii] + 0.1 * ri]); hp = np.unique(np.round(hp / rund) * rund, axis=0)             # S4 (2026-11-05): Hüllpunkte auf `rund` runden/entdoppeln - fast deckungsgleiche Punkte (Netzpunkte + Wandpunkte) gaben Splitterflaechen, die im STL zu Beruehrkanten wurden
                model = model + t_ + M.hull_points(hp.tolist()); n_k += 1                                                # (T3b: ohne Rundung 61 Koerper/Loecher nach Druckreparatur, mit 2 mm: 1 Koerper, wasserdicht)
            print(f"  Anbauteile: {n_k} mit Konsole angebunden, {n_s} Splitter verworfen")
            beleg("alle", f"Anbauteile ohne Kontakt: {n_k} Konsolen, {n_s} Splitter verworfen", "baukasten_gen Druckregel (tools/anbau_verbinden.py-Prototyp 5.11.): Konsole = Huelle der unteren 20 % des Teils + 0,1 m in die naechste Modellflaeche; Form des Teils unveraendert")
        os.makedirs(os.path.dirname(OUT), exist_ok=True); roh_model = model; t0_ = float(os.environ.get("VEREINFACHEN_M", "0.005"))
        for tol_ in [t0_] + [t0_ * f_ for f_ in (0.8, 1.2, 0.6, 1.4)]:                                  # 2026-11-09 R6: Simplify-Toleranz ist ein Zufallsschalter fuer Splitter (Union-Numerik);
            model = roh_model.simplify(tol_).scale((K, K, K))                                             # bei gescheiterter Reparatur naechste Toleranz (alle <= 7 mm << Druckaufloesung), erste wasserdichte gewinnt
            mesh = model.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]; Fi = np.asarray(mesh.tri_verts); ok_ = True
            try:                                                                                           # Druckreparatur (2026-11-05): fast deckungsgleiche Punkte (< 1 um) werden im STL zu Splittern ->
                import trimesh as _tm                                                                      # Pruefstand 'nicht wasserdicht / 8 Koerper' verwarf Fotowert First -0,63. Schweissen, entartete Dreiecke weg,
                tm = _tm.Trimesh(np.asarray(V, np.float32).astype(float), Fi, process=True)                                                    # Loecher schliessen; nur wenn noetig und nur bei Volumenaenderung < 0,1 %
                if not (tm.is_watertight and len(tm.split(only_watertight=False)) == 1):
                    v0 = abs(model.volume()); tm.merge_vertices(digits_vertex=3); tm.update_faces(tm.nondegenerate_faces(height=1e-4)); tm.remove_unreferenced_vertices(); _tm.repair.fill_holes(tm)
                    if tm.is_watertight and len(tm.split(only_watertight=False)) == 1 and abs(abs(tm.volume) - v0) < 1e-3 * v0:
                        print(f"  Druckreparatur: Splitter geschweisst ({len(Fi)} -> {len(tm.faces)} Dreiecke, Vereinfachung {tol_ * 1000:.1f} mm)"); V, Fi = np.asarray(tm.vertices), np.asarray(tm.faces)
                        beleg("alle", "Druckreparatur Splitter", f"baukasten_gen: Punkte < 1 um verschweisst, entartete Dreiecke entfernt, Loecher geschlossen (trimesh MIT), Volumen +-0,1 %, Vereinfachung {tol_ * 1000:.1f} mm")
                    else: print(f"  Druckreparatur fehlgeschlagen bei Vereinfachung {tol_ * 1000:.1f} mm" + (" - naechste Toleranz" if tol_ != t0_ * 1.4 else " - Netz unveraendert")); ok_ = False
            except ImportError: print("  (trimesh fehlt: keine Druckreparatur)")
            if ok_: break
    roh = ctx.get("roh") or []
    if roh:                                                                                        # stl_teil: Rohdreiecke (m) -> mm, unverschweisst an das Netz haengen
        R_ = np.concatenate(roh) * K; V = np.vstack([V, R_.reshape(-1, 3)]); Fi = np.vstack([Fi, np.arange(len(R_) * 3).reshape(-1, 3) + len(V) - len(R_) * 3])
        print(f"  {len(R_)} Rohdreiecke (stl_teil) angehaengt, nicht verschweisst")
    tri = V[Fi]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    rec = np.zeros(len(Fi), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri
    with open(OUT, "wb") as f: f.write(OBJ_DIR.encode()[:80].ljust(80, b" ")); f.write(np.uint32(len(Fi)).tobytes()); f.write(rec.tobytes())
    json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.environ.get("ELEMENTE_AUS") or os.path.join(OD, "elemente.json"), "w"), indent=1, ensure_ascii=False)   # ELEMENTE_AUS: Suchlaeufe (param_suche.py) schreiben nicht ins Objekt
    print(f"-> {OUT}  ({len(Fi)} Dreiecke, Volumen {(model.volume() / K**3) if model is not None else float('nan'):.0f} m3, Hoehe {V[:, 2].max() / K:.2f} m)")

if __name__ == "__main__":
    main()
