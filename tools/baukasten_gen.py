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
@bauteil("rumpf_lod2")
def rumpf_lod2(cfg, ctx):
    """Rumpf + Dach als EIN Koerper aus LoD2: je Dachflaeche ein Prisma ueber ihrem Grundriss, oben von der Dachebene beschnitten;
    Vereinigung, dann auf den LoD2-Grundriss (GroundSurface) begrenzt. Quelle: LoD2 (amtlich) - sieht keine Aufbauten (Regel 4)."""
    meta, F = lod2_flaechen(); naht = float(cfg.get("naht_m", 0.02))
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
    q = f"Foto {R_['foto']} ({cfg['datei']})"
    def setze(lst, kk): lst.append(W.setzen(kk))
    if "traufe" in R_:                                                                                  # Traufueberstand: LoD2-Dachebene ueber die Wand hinaus verlaengert, bis sie die Rinnenhoehe am Foto erreicht
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
    if "arkade" in R_:
        A = R_["arkade"]; pf = A["pfeiler_px"]; zk, zs = Z(A["kaempfer_y"]), Z(A["scheitel_y"]); t = float(T.get("arkade_m", 3.0))
        for (_, r0), (l1, _) in zip(pf[:-1], pf[1:]):
            u0, u1 = sorted((W.u(U(r0)), W.u(U(l1)))); setze(cuts, prisma_uz(segmentbogen(u0, u1, zk, zs, zs0 - 1.0), -t, 0.3))
        beleg(se, f"Arkade: {len(pf) - 1} Segmentboegen, Kaempfer {zk:.2f} m, Scheitel {zs:.2f} m, Tiefe {t:.1f} m", f"{q}, Zaehlung {A['zaehlung']}; {A['quelle']}; Tiefe: {T.get('quelle', 'ANNAHME')}",
              n=len(pf) - 1, kaempfer=zk, scheitel=zs, tiefe=t)
    if "fenster" in R_:
        Fe = R_["fenster"]; z0, z1 = Z(Fe["bruestung_y"]), Z(Fe["sturz_y"]); nf = int(Fe.get("felder", 1)); pfo = float(Fe.get("pfosten_m", 0.1)); t = float(T.get("fenster_nische_m", 0.2))
        for x0, x1 in Fe["x_px"]:
            u0, u1 = sorted((W.u(U(x0)), W.u(U(x1)))); b = (u1 - u0 - (nf - 1) * pfo) / nf
            for i in range(nf): setze(cuts, quader(u0 + i * (b + pfo), u0 + i * (b + pfo) + b, -t, 0.3, z0, z1))
        beleg(se, f"Fenster: {len(Fe['x_px'])} Stueck, je {nf} Felder, Bruestung {z0:.2f} / Sturz {z1:.2f} m, Nische {t:.2f} m", f"{q}, Zaehlung {Fe['zaehlung']}; {Fe['quelle']}; Nische ANNAHME",
              n=len(Fe["x_px"]), unten=z0, oben=z1)
    if "figuren" in R_:
        Fg = R_["figuren"]; zs_, zf, zb_ = Z(Fg["sockel_y"]), Z(Fg["figur_oben_y"]), Z(Fg["baldachin_oben_y"]); b = Fg["breite_px"] / k
        for x in Fg["x_px"]:
            u = W.u(U(x)); setze(adds, quader(u - 0.35, u + 0.35, -0.05, 0.4, zs_ - 0.35, zs_))
            setze(adds, M.cylinder(zf - zs_, b * 0.75, b * 0.6, 24).translate((u, 0.22, zs_)))
            setze(adds, quader(u - 0.35, u + 0.35, -0.05, 0.4, zf + 0.05, zb_))
        beleg(se, f"Figuren: {len(Fg['x_px'])} auf Konsole mit Baldachin, Figur {zs_:.2f}-{zf:.2f} m", f"{q}, Zaehlung {Fg['zaehlung']}; {Fg['quelle']}; Figur als Kegelstumpf (ANNAHME Detailgrad H0)",
              n=len(Fg["x_px"]))
    if "galerie" in R_:
        G = R_["galerie"]; u0, u1 = sorted((W.u(U(G["x_px"][0])), W.u(U(G["x_px"][1])))); zu, zh = Z(G["unten_y"]), Z(G["handlauf_y"]); t = float(T.get("galerie_m", 0.7))
        setze(adds, quader(u0, u1, -0.1, t, zu, zu + 0.22))                                             # Platte
        setze(adds, quader(u0, u1, t - 0.12, t, zu + 0.22, zh))                                        # Bruestung (Docken als volle Bruestung, H0)
        for uu in (u0, u1 - 0.12): setze(adds, quader(uu, uu + 0.12, -0.1, t, zu + 0.22, zh))
        beleg(se, f"Galerie: Platte {zu:.2f} m, Handlauf {zh:.2f} m, Vorsprung {t:.2f} m, Laenge {u1 - u0:.1f} m", f"{q}; {G['quelle']}; Vorsprung: {T.get('quelle', 'ANNAHME')}; Docken als volle Bruestung (ANNAHME H0)",
              unten=zu, oben=zh, vorsprung=t)
    if "erker" in R_:
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
    if "gauben" in R_:
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
    sl = []
    for P in haupt:
        c = P.mean(0); _, _, V2 = np.linalg.svd(P - c); nn = V2[2] if V2[2][2] > 0 else -V2[2]; sl.append(math.hypot(nn[0], nn[1]) / nn[2])
    slope = float(np.median(sl)); n_st = int(cfg["stufen_je_flanke"]); dk, kp, sp = float(cfg.get("dicke_m", 0.6)), float(cfg.get("kappe_m", 0.35)), float(cfg.get("spitze_m", 1.0))
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
        if np.median(np.abs(hi[:, 2] - (zf - slope * np.abs(qh)))) > 0.6: continue                  # Oberkante liegt nicht auf der Hauptdachlinie (Anbau-Giebel)
        aa, bb = a_ + nin * 0.02 + d_ * 0.03, b_ + nin * 0.02 - d_ * 0.03                            # 2 cm HINTER die Wandebene, Enden 3 cm eingerueckt: keine deckungsgleichen Flaechen, keine Splitter ausserhalb des Rumpfs (0,2 mm bei H0)
        ende = 1 if ((a_ + b_) / 2 - f0) @ r > 0 else -1                                               # welches Firstende
        gr = giebel.setdefault(ende, dict(poly=None, qs=[]))
        cs = C([ccw(np.array([aa, bb, bb + nin * dk, aa + nin * dk]))]); gr["poly"] = cs if gr["poly"] is None else gr["poly"] + cs
        gr["qs"] += [((a_ - f0) @ pr), ((b_ - f0) @ pr)]; n_w += 1
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
                qa, qb = grenzen[k + 1], grenzen[k]; zt = zf - slope * qa + kp
                band = M.cube((400, qb - qa + 0.01, zt)).translate((-200, qa if sgn > 0 else -qb - 0.01, 0))   # 1 cm Ueberlappung zur Nachbarstufe
                adds.append(scheibe ^ band.transform(T_))
        adds.append(scheibe ^ M.cube((400, 2 * tw, zf + sp)).translate((-200, -tw, 0)).transform(T_))
    adds = [k_ for k_ in adds if not k_.is_empty()]
    beleg("dach", f"Treppengiebel: {len(giebel)} Giebel ({n_w} LoD2-Wandstuecke), je {n_st} Stufen je Flanke + Spitze, Kappe {kp:.2f} m, Spitze {sp:.1f} m ueber First, Scheibe {dk:.2f} m",
          f"Stufenzahl: {', '.join(cfg.get('zaehlung', []))} (Regel 9); Giebelwaende/First/Neigung LoD2; Kappe/Spitze/Dicke {cfg.get('quelle', 'ANNAHME')}", n=n_st)
    return adds, []

# ------------------------------------------------------------------ Bau
def main():
    ctx = {}; adds, cuts = [], []
    for spec in OBJ.get("bauteile") or [{"typ": "rumpf_lod2"}]:
        if spec.get("aktiv", True) is False: continue
        a, c = BAUTEILE[spec["typ"]](spec, ctx); adds += a; cuts += c
        print(f"  {spec['typ']}: +{len(a)} / -{len(c)}")
    model = UNION(adds)
    if cuts: model = model - UNION(cuts)
    model = model.simplify(float(os.environ.get("VEREINFACHEN_M", "0.005"))).scale((K, K, K))   # Splitter-Dreiecke (Naht-Offsets) entfernen; 5 mm << Druckaufloesung
    mesh = model.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]; Fi = np.asarray(mesh.tri_verts)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tri = V[Fi]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    rec = np.zeros(len(Fi), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri
    with open(OUT, "wb") as f: f.write(OBJ_DIR.encode()[:80].ljust(80, b" ")); f.write(np.uint32(len(Fi)).tobytes()); f.write(rec.tobytes())
    json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.path.join(OD, "elemente.json"), "w"), indent=1, ensure_ascii=False)
    print(f"-> {OUT}  ({len(Fi)} Dreiecke, Volumen {model.volume() / K**3:.0f} m3, Hoehe {model.bounding_box()[5] / K:.2f} m)")

if __name__ == "__main__":
    main()
