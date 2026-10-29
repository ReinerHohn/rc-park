#!/usr/bin/env python3
"""bauwerk_generator.py — GENERISCHE Bauwerk-Engine als BIBLIOTHEK VON ELEMENT-GENERATOREN.

Idee (vom Nutzer): statt ein Gebäude am Stück zu verdrahten, hat man einen Satz
EINZELNER, generischer Element-Generatoren — Putzfassade-, Fenster-, Fensterläden-,
Blumenkästen-, Tür/Erdgeschoss-, (Sattel)Dach-, Gauben-, Dachluken-, Schornstein-,
Dachrinnen-, Gesims-, Ausleger-Generator … — und JEDES Haus ist eine KOMPOSITION:
die Config listet, welche Generatoren mit welchen Parametern angewandt werden.

  bauwerke/<name>.json:  "elements": { "putzfassade": {...}, "fensterraster": {...}, ... }

Spezialfälle (z.B. Historisches Kaufhaus mit Arkade/Erker/Statuen) sind einfach
ZUSÄTZLICHE Element-Generatoren, die nur die jeweilige Config aufruft — die Engine
bleibt gleich. Neue Generatoren registriert man mit @element("name").

  python3 tools/bauwerk_generator.py --config bauwerke/hotel_oberkirch.json
"""
import argparse, colorsys, json, math, os
import numpy as np
import trimesh
from trimesh.creation import extrude_polygon, box as tbox, cylinder as tcyl, cone as tcone
from shapely.geometry import Polygon, box as sbox


# ============================================================ Geometrie-Helfer
def _stand(m, y0=0.0):
    V = m.vertices.copy()
    m.vertices = np.c_[V[:, 0], y0 + V[:, 2], V[:, 1]]
    return m


def _valid(poly):
    if poly.is_empty:
        return None
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly if (not poly.is_empty and poly.area > 1e-4) else None


def panel(x0, x1, z0, z1, holes=(), thick=0.5, y0=0.0):
    """Wandpaneel [x0,x1]x[z0,z1] minus Löcher (Rechteck ODER shapely-Polygon) -> Mesh."""
    poly = sbox(x0, z0, x1, z1)
    for h in holes:
        hp = h if hasattr(h, "difference") else sbox(h[0], h[2], h[1], h[3])
        poly = poly.difference(hp)
    poly = _valid(poly)
    if poly is None:
        return None
    geoms = list(poly.geoms) if poly.geom_type == "MultiPolygon" else [poly]   # Loch kann Wand teilen
    return cat([_stand(extrude_polygon(g, thick), y0=y0) for g in geoms])


def slab(cx, cy, cz, sx, sy, sz):
    b = tbox(extents=(sx, sy, sz)); b.apply_translation((cx, cy, cz)); return b


def disc(radius, thick, cx, cy, cz, squash=1.0, sections=24):
    d = tcyl(radius=radius, height=thick, sections=sections)
    d.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    if squash != 1.0:
        d.apply_scale([1.0, 1.0, squash])
    d.apply_translation((cx, cy, cz)); return d


def arch_poly(cx, w, z0, zspring, ztop, n=16):
    s = w / 2.0; h = max(ztop - zspring, 1e-4)
    R = (s * s + h * h) / (2 * h); zc = ztop - R
    pts = [(cx - s, z0), (cx + s, z0), (cx + s, zspring)]
    for i in range(1, n):
        x = cx + s * math.cos(math.pi * i / n)
        pts.append((x, math.sqrt(max(R * R - (x - cx) ** 2, 0)) + zc))
    pts.append((cx - s, zspring))
    return Polygon(pts)


def cat(parts):
    parts = [p for p in parts if p is not None and len(p.faces)]
    return trimesh.util.concatenate(parts) if parts else None


def _vivid(rgb):
    """generische Farb-Korrektur: Foto-Medians sind matt (Schatten) + der Render hellt auf.
    Chromatische Flächen (Putz/Läden/Blumen) satter+leicht heller; graue (Dach) abdunkeln."""
    h, s, v = colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
    if s < 0.12:
        v *= 0.78
    else:
        s = min(1.0, s * 1.5); v = min(1.0, v * 1.12)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return [int(r * 255), int(g * 255), int(b * 255), 255]


def _facade_texture(cfg, region):
    """Fassadenstreifen aus dem Foto holen (für Wand-Textur). Front zeigt -Y -> horizontal spiegeln."""
    meas = cfg.get("measure")
    if not (meas and region):
        return None
    from PIL import Image
    im = Image.open(meas["foto"]).convert("RGB"); W0, H0 = im.size
    crop = im.crop((int(region[0] * W0), int(region[1] * H0), int(region[2] * W0), int(region[3] * H0)))
    return crop.transpose(Image.FLIP_LEFT_RIGHT)


def texture_panel(mesh, image, x0, x1, z0, z1):
    """planare Textur-Projektion (x->u, z->v) auf ein Wand-Panel; Fensterlöcher bleiben Löcher,
    die Geometrie-Fenster sitzen davor -> die Textur zeigt nur die Wandflächen (inkl. Schrift/Band)."""
    if mesh is None:
        return mesh
    V = mesh.vertices
    u = (V[:, 0] - x0) / max(x1 - x0, 1e-6)
    v = (z1 - V[:, 2]) / max(z1 - z0, 1e-6)
    mesh.visual = trimesh.visual.TextureVisuals(uv=np.c_[u, v], image=image)
    return mesh


# ============================================================ Kontext (Masse + Raster)
class Ctx:
    """gemeinsamer Bau-Kontext: aufgelöste Masse + Fassaden-Raster. Alle Element-
    Generatoren bekommen diesen Kontext und lesen W/eave/winx/floor_z0 etc. daraus."""
    def __init__(self, cfg):
        self.cfg = cfg; self.measured = {}
        m = cfg["massing"]; f = cfg["facade"]
        self.eave = float(m["eave"]); self.front_t = float(m.get("wall_thick", 0.5))
        # Fallbacks aus Config
        W = m.get("W"); eg_top = f.get("eg_top"); axes = f.get("axes_x_frac")
        # --- DATENERKENNUNG IN DER PIPELINE: Fassade automatisch vermessen ---
        meas = cfg.get("measure")
        if meas:
            import sys as _s, os as _o
            _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
            from fassade_messen import measure as _measure
            n = int(meas.get("n_axes", len(axes) if axes else 4))
            md = _measure(meas["foto"], meas["box"], self.eave, n)[0]
            W, eg_top, axes = md["W_m"], md["eg_top_m"], md["axes_x_frac"]
            self.measured = md
            print(f"   [auto-gemessen aus Foto] W={W} m  EG-Oberkante={eg_top} m  Achsen={axes}")
        self.W = float(W); self.eg_top = float(eg_top)
        # --- DACH: First aus GEMESSENER Front-Dachhöhe (perspektiv-echt), Tiefe separat gekappt ---
        self.lod2_depth = float(m["lod2_depth"]); self.lod2_ridge = float(m["lod2_ridge"])
        cap = float(m.get("streetfront_depth") or max(self.W, 8.0))
        self.D = min(self.lod2_depth, cap)
        rise = (self.measured.get("roof_rise_m") if meas else None) or m.get("roof_rise_m")
        if rise and float(rise) > 0.5:
            self.ridge = self.eave + float(rise)              # GEMESSEN am Foto (Dach nicht zu lang)
        elif m.get("roof_pitch_deg"):
            self.ridge = self.eave + math.tan(math.radians(float(m["roof_pitch_deg"]))) * (self.D / 2)
        else:                                                  # LOD2-Neigung über gekappte Tiefe
            self.ridge = self.eave + math.tan(math.atan2(self.lod2_ridge - self.eave, self.lod2_depth / 2)) * (self.D / 2)
        self.pitch = math.atan2(self.ridge - self.eave, self.D / 2)
        # --- Fassaden-Raster ---
        self.nfl = int(f["floors"])
        self.winx = [x * self.W for x in axes]
        self.fh = (self.eave - self.eg_top) / self.nfl
        self.floor_z0 = [self.eg_top + i * self.fh for i in range(self.nfl)]
        self.win = dict(f.get("window", {}))
        # Farben: kuratierte Defaults sind meist satter als Foto-Medians (Schatten/Licht machen
        # die Messung matt) -> Mess-Farben nur opt-in (use_measured_colors). Config schlägt alles.
        # Kuratierte Defaults sind auf den ersten Schlag am besten; Mess-Farben nur opt-in.
        mc = {k: _vivid(v) for k, v in (self.measured.get("colors") or {}).items()} \
            if cfg.get("use_measured_colors", False) else {}
        if mc.get("fassade"):
            mc.setdefault("gaube", mc["fassade"]); mc.setdefault("giebel", mc["fassade"])
            mc.setdefault("gesims", [min(v + 16, 255) for v in mc["fassade"][:3]] + [255])
        if mc.get("dach"):
            mc.setdefault("gaube_dach", mc["dach"])
        self.col = {**DEFAULT_COL, **mc, **cfg.get("colors", {})}
        # EG-WAND = Fassadenfarbe (nicht das Holz); nur Sockel/Rahmen sind Holz
        self.col["eg_sockel"] = cfg.get("colors", {}).get("eg_sockel", self.col["fassade"])
        # Zierband-Farbe aus dem Foto (Weißabgleich-korrigiert)
        zb = self.measured.get("zierband")
        if zb and "zierband" not in cfg.get("colors", {}):
            self.col["zierband"] = _vivid(zb["color"])

    def floors_windows(self):
        """iteriert (sill, cx) über alle OG-Fenster."""
        so = self.win.get("sill_off", 0.78)
        for z0 in self.floor_z0:
            for cx in self.winx:
                yield z0 + so, cx


# ============================================================ Element-Registry
ELEMENTS = {}


def element(name):
    def deco(fn):
        ELEMENTS[name] = fn
        return fn
    return deco


# ---- Putzfassade-Generator -------------------------------------------------
@element("putzfassade")
def gen_facade(c, p):
    w = c.win; ww, wh, so = w["w"], w["h"], w["sill_off"]
    holes = [(cx - ww / 2, cx + ww / 2, sill, sill + wh) for sill, cx in c.floors_windows()]
    out = {"fassade": panel(0, c.W, c.eg_top, c.eave, holes, c.front_t)}
    if p.get("textured", False) and c.measured.get("facade_region_upper"):   # Fassadentextur aus Foto (opt-in)
        tex = _facade_texture(c.cfg, c.measured["facade_region_upper"])
        if tex is not None:
            texture_panel(out["fassade"], tex, 0, c.W, c.eg_top, c.eave)
    # Traufgesims + Sockelband
    g = [slab(c.W / 2, -0.18, c.eave - 0.12, c.W + 0.2, 0.36, 0.22)]
    if p.get("string_course", True):
        g.append(slab(c.W / 2, -0.1, c.eg_top, c.W + 0.08, 0.2, 0.14))
    out["gesims"] = cat(g)
    return out


# ---- Zierband-Generator (gemalte Gurtlinie, z.B. blauer Strich) ------------
@element("zierband")
def gen_band(c, p):
    zb = c.measured.get("zierband") if c.measured else None
    h = (zb or {}).get("h_m") or p.get("h")
    if not h:
        return {}
    return {"zierband": slab(c.W / 2, -0.11, float(h), c.W + 0.08, 0.1, float(p.get("height", 0.13)))}


# ---- Beschriftungs-Generator: Fassadenstreifen (Schriftzug) aus Foto als TEXTUR ----
@element("beschriftung")
def gen_lettering(c, p):
    """'Foto lesen und aufs Modell matchen': schneidet einen Fassadenstreifen (z.B. den
    Schriftzug) aus dem Foto und legt ihn als Textur auf ein Quad an der Höhe h."""
    meas = c.cfg.get("measure")
    if not meas:
        return {}
    ml = (c.measured.get("lettering") or {}) if c.measured else {}
    reg = p.get("photo_region") or ml.get("photo_region")      # AUTO-erkannt, sonst Config
    if not reg:
        return {}
    from PIL import Image, ImageEnhance
    im = Image.open(meas["foto"]).convert("RGB"); W0, H0 = im.size
    strip = im.crop((int(reg[0] * W0), int(reg[1] * H0), int(reg[2] * W0), int(reg[3] * H0)))
    strip = strip.transpose(Image.FLIP_LEFT_RIGHT)       # Betrachter bei -Y spiegelt X -> vorkompensieren
    strip = ImageEnhance.Brightness(strip).enhance(float(p.get("brighten", 1.22)))
    z = float(p.get("h") or ml.get("h_m") or (c.eg_top - 0.35))
    hh = float(p.get("height", 0.5)); m = float(p.get("margin", 0.3))
    y = -0.26
    # V: [unten-links, unten-rechts, oben-rechts, oben-links]; GLTF-v=0 unten -> v unten=0, oben=1
    V = np.array([[m, y, z - hh / 2], [c.W - m, y, z - hh / 2], [c.W - m, y, z + hh / 2], [m, y, z + hh / 2]])
    mesh = trimesh.Trimesh(vertices=V, faces=np.array([[0, 1, 2], [0, 2, 3]]), process=False)
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, image=strip)
    return {"beschriftung": mesh}


# ---- Tür-und-Fenster-Generator (ein einzelnes Fenster als Baustein) --------
def muntin_grid(cx, sill, w, h, cols, rows, y, t=0.055):
    """GENERISCHE Sprossen (Fensterteilung): cols-1 senkrechte + rows-1 waagrechte Stege.
    cols/rows = Anzahl Scheiben waagrecht/senkrecht. Für feinere Fenster höher setzen."""
    bars = []
    for cc in range(1, cols):
        bars.append(slab(cx - w / 2 + cc * w / cols, y, sill + h / 2, t, 0.055, h))
    for rr in range(1, rows):
        bars.append(slab(cx, y, sill + rr * h / rows, w, 0.055, t))
    return bars


def one_window(c, cx, sill, ww, wh, cols, rows):
    """Rahmen + Sprossenkreuz (cols×rows) + Sohlbank PROUD vor der Fassade (Betrachter -Y),
    Glas in der Leibung dahinter. Gibt (glas, rahmen)."""
    yf = -0.035
    glass = slab(cx, 0.16, sill + wh / 2, ww - 0.04, 0.06, wh - 0.04)
    t, mt = 0.09, 0.07
    x0, x1 = cx - ww / 2, cx + ww / 2
    bars = [slab(cx, yf, sill + wh, ww + 0.12, 0.07, t), slab(cx, yf, sill, ww + 0.12, 0.07, t),
            slab(x0, yf, sill + wh / 2, t, 0.07, wh), slab(x1, yf, sill + wh / 2, t, 0.07, wh)]
    bars += muntin_grid(cx, sill, ww, wh, cols, rows, yf, mt)           # Sprossenteilung (generisch)
    bars.append(slab(cx, -0.07, sill - 0.05, ww + 0.2, 0.18, 0.09))      # Sohlbank
    bars.append(slab(cx, -0.14, sill + wh + 0.09, ww + 0.34, 0.22, 0.06))  # Verdachung (Leiste über dem Fenster)
    return glass, cat(bars)


@element("fensterraster")
def gen_windows(c, p):
    w = c.win; ww, wh = w["w"], w["h"]
    cols, rows = int(p.get("cols", w.get("cols", 2))), int(p.get("rows", w.get("rows", 2)))
    glass, frames = [], []
    for sill, cx in c.floors_windows():
        g, fr = one_window(c, cx, sill, ww, wh, cols, rows)
        glass.append(g); frames.append(fr)
    return {"fenster": cat(glass), "rahmen": cat(frames)}


# ---- Fensterläden-Generator ------------------------------------------------
@element("fensterlaeden")
def gen_shutters(c, p):
    w = c.win; ww, wh, so = w["w"], w["h"], w["sill_off"]
    sw = ww * float(p.get("width_frac", 0.52)); slats = int(p.get("slats", 4)); parts = []
    for sill, cx in c.floors_windows():
        for side in (-1, 1):
            sx = cx + side * (ww / 2 + sw / 2)
            parts.append(slab(sx, -0.03, sill + wh / 2, sw, 0.05, wh + 0.04))
            for k in range(slats):
                zz = sill + 0.18 + k * (wh - 0.3) / max(slats - 1, 1)
                parts.append(slab(sx, -0.065, zz, sw - 0.06, 0.02, 0.05))
    return {"laeden": cat(parts)}


# ---- Blumenkästen-Generator ------------------------------------------------
@element("blumenkaesten")
def gen_flowerboxes(c, p):
    w = c.win; ww, wh, so = w["w"], w["h"], w["sill_off"]
    boxes, blooms = [], []
    for sill, cx in c.floors_windows():
        boxes.append(slab(cx, -0.18, sill + 0.03, ww + 0.1, 0.24, 0.2))      # auf der Fensterbank
        for j in range(5):
            s = tcyl(radius=0.095, height=0.13, sections=8)
            s.apply_translation((cx - ww / 2 + (j + 0.5) * (ww + 0.1) / 5, -0.21, sill + 0.17)); blooms.append(s)
    return {"kasten": cat(boxes), "blumen": cat(blooms)}


# ---- Erdgeschoss-Generator (Tür + Schaufenster + Band + Wappen + Laternen) --
def shop_window(cx, w, z0, ztop):
    """Schaufenster wie im Foto: NORMALES rechteckiges Fenster, brauner Holzrahmen, OBEN warmes
    Licht/Lampen, UNTERE Hälfte weiße Café-Gardine. Gibt (holzrahmen, warm_glas, gardine)."""
    s = w / 2; h = ztop - z0; frame, warm, curt = [], [], []
    yf = -0.04
    frame.append(slab(cx - s, yf, (z0 + ztop) / 2, 0.12, 0.16, h))                  # Rahmen links
    frame.append(slab(cx + s, yf, (z0 + ztop) / 2, 0.12, 0.16, h))                  # Rahmen rechts
    frame.append(slab(cx, yf, ztop, w + 0.24, 0.16, 0.14))                          # Sturz (gerade)
    frame.append(slab(cx, -0.07, z0, w + 0.24, 0.24, 0.18))                         # Brüstung/Sohlbank
    frame.append(slab(cx, yf, (z0 + ztop) / 2, 0.07, 0.12, h))                      # Mittelpfosten
    frame.append(slab(cx, yf, z0 + 0.52 * h, w, 0.1, 0.06))                         # Kämpfer
    warm.append(slab(cx, 0.17, z0 + 0.76 * h, w - 0.12, 0.06, 0.44 * h))            # warmes Licht oben
    curt.append(slab(cx, 0.12, z0 + 0.27 * h, w - 0.14, 0.05, 0.46 * h))            # weiße Gardine unten
    return cat(frame), cat(warm), cat(curt)


@element("erdgeschoss")
def gen_groundfloor(c, p):
    holes, out = [], {}
    frames, warms, curts, darkglass, door_parts = [], [], [], [], []
    xs = float(p.get("x_shift", 0.0))                       # ganze EG-Reihe gemeinsam verschieben (m)
    dx = c.W * float(p.get("door_x_frac", 0.5)) + xs
    if p.get("door", True):
        holes.append((dx - 0.6, dx + 0.6, 0.0, 2.6))
        door_parts.append(slab(dx, -0.02, 1.12, 1.14, 0.08, 2.24))     # braunes Türblatt (eigene Gruppe, nicht weiß)
        door_parts.append(slab(dx, -0.05, 2.52, 1.32, 0.1, 0.14))      # Türsturz
        door_parts.append(slab(dx, -0.05, 1.12, 0.06, 0.08, 2.24))     # Mittelstab
        warms.append(slab(dx, 0.06, 2.3, 0.88, 0.06, 0.42))        # oberes Türfenster (warm)
    win_xf = p.get("window_x_frac")
    if win_xf is None:
        n = int(p.get("arched_windows", 0)); win_xf = [(i + 0.5) / n for i in range(n)] if n else []
    ww = float(p.get("shop_w", 1.5))
    sz0 = float(p.get("shop_z0", 0.85)); sz1 = float(p.get("shop_z1", 2.65))   # GROSSES Schaufenster: tiefer Sockel bis knapp unter Markise
    grille = []
    for xf in win_xf:
        sx = c.W * float(xf) + xs
        holes.append((sx - ww / 2, sx + ww / 2, sz0, sz1))       # rechteckige Öffnung (kein Bogen)
        fr, wm, cu = shop_window(sx, ww, sz0, sz1)
        frames.append(fr); warms.append(wm); curts.append(cu)
        if p.get("shop_grille"):                                  # RAUTEN-SCHUTZGITTER vorm Schaufenster (Foto Bohrer)
            gz0, gz1, yg = sz0 + 0.1, sz1 - 0.1, -0.17; cz = (gz0 + gz1) / 2; cw = ww - 0.06; gh = gz1 - gz0
            L = min(cw, gh) * 1.12; step = 0.17; nx = int(cw / step) + 1
            for sgn in (1, -1):
                Rm = trimesh.transformations.rotation_matrix(sgn * np.pi / 4, [0, 1, 0])
                for i in range(-nx, nx + 1):
                    bar = tbox(extents=(0.02, 0.03, L)); bar.apply_transform(Rm)
                    bar.apply_translation((sx + i * step, yg, cz)); grille.append(bar)
        else:
            for side in (-1, 1):                                  # sonst braune Klappläden flankierend
                frames.append(slab(sx + side * (ww / 2 + 0.22), -0.05, 1.75, 0.34, 0.06, 1.7))
    if grille:
        g = cat(grille); clip = tbox(extents=(ww - 0.05, 0.4, (sz1 - 0.1) - (sz0 + 0.1) - 0.05))
        clip.apply_translation((c.W * float(win_xf[0]) + xs, -0.17, (sz0 + sz1) / 2))
        try:
            from trimesh.boolean import intersection
            g = intersection([g, clip])
        except Exception:
            pass
        out["gitter"] = g
    out["eg_sockel"] = panel(0, c.W, 0.0, c.eg_top, holes, c.front_t + 0.12, y0=-0.12)
    if p.get("textured", False) and c.measured.get("facade_region_eg"):      # EG-Wandtextur (opt-in)
        tex = _facade_texture(c.cfg, c.measured["facade_region_eg"])
        if tex is not None:
            texture_panel(out["eg_sockel"], tex, 0, c.W, 0.0, c.eg_top)
    # EG-Wand bleibt CREMEFARBEN (kein dunkler Sockel) — opt-in per wainscot_h
    wh_ = float(p.get("wainscot_h", 0.0))
    if wh_ > 0:
        out["sockel_holz"] = panel(0, c.W, 0.0, wh_, [(dx - 0.6, dx + 0.6, 0.0, wh_)], c.front_t + 0.16, y0=-0.16)
    out["eg_glas"] = cat(darkglass)
    out["schaufenster"] = cat(frames); out["gardine"] = cat(curts); out["tuer"] = cat(door_parts)
    if p.get("lettering"):
        out["band"] = slab(c.W / 2, -0.14, c.eg_top - 0.35, c.W - 0.7, 0.12, 0.42)
    wap = [disc(0.26, 0.1, (c.W * 0.12, c.W * 0.88)[i % 2] + xs, -0.18, c.eg_top - 0.3, sections=20)
           for i in range(int(p.get("wappen", 0)))]
    out["wappen"] = cat(wap)
    lant, glow = [], []
    for i in range(int(p.get("lanterns", 0))):          # Laternen flankieren die TÜR
        sx = dx + (-0.9 if i % 2 == 0 else 0.9); z = 2.55
        lant += [slab(sx, -0.3, z + 0.28, 0.045, 0.55, 0.045), slab(sx, -0.02, z + 0.1, 0.05, 0.05, 0.5)]
        b = tcyl(radius=0.13, height=0.34, sections=6); b.apply_translation((sx, -0.55, z)); lant.append(b)
        cp = tcone(radius=0.16, height=0.15, sections=6); cp.apply_translation((sx, -0.55, z + 0.24)); lant.append(cp)
        gl = tcyl(radius=0.1, height=0.26, sections=6); gl.apply_translation((sx, -0.55, z)); glow.append(gl)
    # RESTAURANT-KLASSE: Menükasten gehört typisch dazu -> bei style=="restaurant" default an
    is_restaurant = p.get("style") == "restaurant"
    if p.get("menu_board", is_restaurant):
        mx = dx + float(p.get("menu_board_dx", 1.05))
        out["aushang"] = cat([slab(mx, -0.12, 1.55, 0.6, 0.1, 0.95),          # Rahmen dunkel
                              slab(mx, -0.16, 1.55, 0.5, 0.04, 0.82)])         # heller Aushang
    out["laterne"] = cat(lant); out["warmlicht"] = cat(glow + warms)
    return out


# ---- Markise-Generator (gestreifte Laden-Markise überm EG) -----------------
@element("markise")
def gen_markise(c, p):
    x0 = c.W * float(p.get("x0_frac", 0.1)); x1 = c.W * float(p.get("x1_frac", 0.95))
    w = x1 - x0; stripes = int(p.get("stripes", 7)); sw = w / stripes
    ztop = c.eg_top - 0.05                               # knapp unter EG-Oberkante
    proj = float(p.get("proj", 1.0)); drop = float(p.get("drop", 0.42))
    tilt = math.atan2(drop, proj)                        # nach vorn-unten geneigt
    red, white = [], []
    for i in range(stripes):
        xx = x0 + (i + 0.5) * sw
        sl = tbox(extents=(sw * 0.98, proj / math.cos(tilt), 0.04))     # geneigtes Streifenfeld
        sl.apply_transform(trimesh.transformations.rotation_matrix(tilt, [1, 0, 0]))
        sl.apply_translation((xx, -proj / 2, ztop - drop / 2))
        v = tbox(extents=(sw * 0.98, 0.04, 0.2))                        # herabhängender Volant vorn
        v.apply_translation((xx, -proj - 0.02, ztop - drop - 0.07))
        (red if i % 2 == 0 else white).append(sl)
        (red if i % 2 == 0 else white).append(v)
    return {"markise_rot": cat(red), "markise_weiss": cat(white)}


# ---- Dach-Generator (traufständiges Satteldach, mit Tiefen-Regel) ----------
@element("satteldach")
def gen_roof(c, p):
    W, D, ea, ri = c.W, c.D, c.eave, c.ridge
    V = [(0, 0, ea), (W, 0, ea), (W, D, ea), (0, D, ea), (0, D / 2, ri), (W, D / 2, ri)]
    F = [(0, 1, 5), (0, 5, 4), (3, 4, 5), (3, 5, 2), (0, 4, 3), (1, 2, 5), (0, 3, 2), (0, 2, 1)]
    dach = trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F))
    gab = []
    for x in (0.0, W - 0.4):
        tri = Polygon([(0, ea), (D, ea), (D / 2, ri)]); m = extrude_polygon(tri, 0.4); Vv = m.vertices.copy()
        m.vertices = np.c_[x + Vv[:, 2], Vv[:, 0], Vv[:, 1]]; gab.append(m)
    return {"dach": dach, "giebel": cat(gab)}


# ---- Dachziegel-Generator (echte 3D-Ziegel zum Drucken) --------------------
@element("dachziegel")
def gen_tiles(c, p):
    """echte überlappende 3D-Ziegel auf den Dachschrägen (versetzt wie Verband) — druckbar.
    tile_w/course_h/relief parametrisch; slopes=front|both."""
    tw = float(p.get("tile_w", 0.34)); th = float(p.get("course_h", 0.30)); relief = float(p.get("relief", 0.07))
    a = c.D / 2; b = c.ridge - c.eave; Ls = math.hypot(a, b)
    if Ls < 0.1:
        return {}

    def slope(su, nrm, start):
        parts = []; xv = np.cross(su, nrm)
        Rm = np.eye(4); Rm[:3, 0] = xv; Rm[:3, 1] = su; Rm[:3, 2] = nrm
        nc = max(2, int(Ls / th))
        for ci in range(nc):
            t = (ci + 0.5) * th
            if t > Ls - 0.04:
                break
            base = start + su * t
            x = (tw / 2) if (ci % 2) else 0.0          # jede 2. Reihe versetzt
            while x + tw <= c.W + 0.01:
                box = tbox(extents=(tw * 0.9, th * 1.3, relief))   # länger als Reihe -> Überlappung
                box.apply_transform(Rm)
                box.apply_translation(np.array([x + tw / 2, base[1], base[2]]) + nrm * (relief * 0.5))
                parts.append(box); x += tw
        return parts

    tiles = slope(np.array([0, a, b]) / Ls, np.array([0, -b, a]) / Ls, np.array([0.0, 0.0, c.eave]))
    if p.get("slopes", "both") == "both":
        tiles += slope(np.array([0, -a, b]) / Ls, np.array([0, b, a]) / Ls, np.array([0.0, c.D, c.eave]))
    return {"dachziegel": cat(tiles)}


# ---- Dach-Gauben-Generator -------------------------------------------------
@element("gauben")
def gen_dormers(c, p):
    n = int(c.measured.get("n_dormers", p.get("n", 0))) if c.measured else int(p.get("n", 0))
    if n <= 0:
        return {}
    dw, dh = float(p.get("w", 1.05)), float(p.get("h", 1.55))
    xs = c.winx if (p.get("align_windows", True) and n == len(c.winx)) else \
        [c.W * (i + 0.5) / n for i in range(n)]
    zf, yf = c.eave + 0.15, -0.1
    bodies, roofs, glass, frames = [], [], [], []
    shape = p.get("shape", "hip")
    for cx in xs:
        wx0, wx1, wz0, wz1 = cx - dw / 2 + 0.18, cx + dw / 2 - 0.18, zf + 0.25, zf + dh - 0.2
        bodies.append(panel(cx - dw / 2, cx + dw / 2, zf, zf + dh, [(wx0, wx1, wz0, wz1)], 1.0, y0=yf))
        top = zf + dh
        if shape == "gable":                                  # DREIECKIGER Giebel (Zwerchgiebel) + Satteldach
            gh = float(p.get("gable_h", 0.75)); apex = top + gh; o = 0.12; yb = yf + 0.95
            TV = [(cx - dw / 2, yf, top), (cx + dw / 2, yf, top), (cx, yf, apex),
                  (cx - dw / 2, yf + 0.22, top), (cx + dw / 2, yf + 0.22, top), (cx, yf + 0.22, apex)]
            bodies.append(trimesh.Trimesh(vertices=np.array(TV, float),       # Giebel-Dreieck (Prisma), Verkleidung
                          faces=np.array([(0, 1, 2), (3, 5, 4), (0, 2, 5), (0, 5, 3), (1, 4, 5), (1, 5, 2)])))
            RV = [(cx - dw / 2 - o, yf - o, top), (cx + dw / 2 + o, yf - o, top),
                  (cx + dw / 2 + o, yb, top), (cx - dw / 2 - o, yb, top),
                  (cx, yf - o, apex), (cx, yb, apex)]
            roofs.append(trimesh.Trimesh(vertices=np.array(RV, float),        # 2 Dachschrägen + Stirnen
                         faces=np.array([(0, 3, 5), (0, 5, 4), (1, 4, 5), (1, 5, 2), (0, 4, 1), (2, 5, 3)])))
        else:
            V = [(cx - dw / 2 - 0.1, yf - 0.05, top), (cx + dw / 2 + 0.1, yf - 0.05, top),
                 (cx + dw / 2 + 0.1, yf + 0.9, top), (cx - dw / 2 - 0.1, yf + 0.9, top),
                 (cx - dw / 4, yf + 0.45, top + 0.4), (cx + dw / 4, yf + 0.45, top + 0.4)]
            roofs.append(trimesh.Trimesh(vertices=np.array(V, float),
                         faces=np.array([(0, 1, 5), (0, 5, 4), (3, 4, 5), (3, 5, 2), (0, 4, 3), (1, 2, 5)])))
        glass.append(slab(cx, yf + 0.05, (wz0 + wz1) / 2, wx1 - wx0, 0.06, wz1 - wz0))
        wy, mcx, mcz = yf - 0.14, (wx0 + wx1) / 2, (wz0 + wz1) / 2       # weißes Kreuz PROUD vor der Gaube
        frames += [slab(mcx, wy, wz1, wx1 - wx0 + 0.06, 0.05, 0.05), slab(mcx, wy, wz0, wx1 - wx0 + 0.06, 0.05, 0.05),
                   slab(wx0, wy, mcz, 0.05, 0.05, wz1 - wz0), slab(wx1, wy, mcz, 0.05, 0.05, wz1 - wz0),
                   slab(mcx, wy, mcz, 0.04, 0.05, wz1 - wz0), slab(mcx, wy, mcz, wx1 - wx0, 0.05, 0.04)]
    return {"gaube": cat(bodies), "gaube_dach": cat(roofs), "fenster": cat(glass), "rahmen": cat(frames)}


# ---- Dachluken-Generator ---------------------------------------------------
@element("dachluken")
def gen_skylights(c, p):
    n = int(c.measured.get("n_skylights", p.get("n", 0))) if c.measured else int(p.get("n", 0))
    if n <= 0:
        return {}
    ang = math.atan2(c.ridge - c.eave, c.D / 2); t = float(p.get("pos", 0.62))
    yy, zz = t * c.D / 2, c.eave + t * (c.ridge - c.eave); parts = []
    xf = c.measured.get("skylight_x_frac") if c.measured else None     # GEMESSENE Positionen
    for i in range(n):
        cx = c.W * (xf[i] if (xf and i < len(xf)) else (i + 0.5) / n)
        s = tbox(extents=(0.55, 0.55, 0.1))
        s.apply_transform(trimesh.transformations.rotation_matrix(-ang, [1, 0, 0]))
        s.apply_translation((cx, yy - 0.05, zz + 0.05)); parts.append(s)
    return {"luke": cat(parts)}


# ---- Schornstein-Generator -------------------------------------------------
@element("schornsteine")
def gen_chimneys(c, p):
    # GEGEN HALLUZINATION: wenn aus dem Foto gemessen, schlägt die Messung die Config.
    n = int(c.measured.get("n_chimneys", p.get("n", 0))) if c.measured else int(p.get("n", 0))
    parts = []
    for i in range(n):
        cx = c.W * (0.3 + 0.4 * i); yy = c.D / 2 + (0.6 if i % 2 else -0.6)
        parts.append(slab(cx, yy, c.ridge - 0.3, 0.7, 0.7, 2.2))
    return {"schornstein": cat(parts)}


# ---- Dachrinnen-Generator (Rinne + Fallrohre) ------------------------------
@element("dachrinne")
def gen_gutter(c, p):
    parts = []
    g = tcyl(radius=0.09, height=c.W + 0.1, sections=12)
    g.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    g.apply_translation((c.W / 2, -0.17, c.eave - 0.02)); parts.append(g)
    for xf in p.get("downpipe_x_frac", [0.97]):
        ds = tcyl(radius=0.06, height=c.eave, sections=10)
        ds.apply_translation((c.W * xf, -0.17, c.eave / 2)); parts.append(ds)
    return {"rinne": cat(parts)}


# ---- Ausleger-Generator (Hero-Schild) --------------------------------------
def _curl(cx, yy, zz, rr):
    """Schmiede-Schnörkel (Ring) in der X-Z-Ebene (zur Straße -Y sichtbar)."""
    t = trimesh.creation.torus(rr, max(0.025, rr * 0.18))
    t.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    t.apply_translation((cx, yy, zz)); return t


@element("ausleger")
def gen_sign(c, p):
    """schmiedeeisernes Nasenschild: Wandpfosten + horizontaler Arm + Diagonalstrebe +
    Schnörkel-Ringe, ovale Schildtafel hängt am Armende (projiziert waagerecht zur Straße)."""
    cx = c.W / 2; z = c.floor_z0[0] + c.fh * 0.72; L = float(p.get("arm", 1.5))
    parts = [slab(cx, -0.06, z + 0.05, 0.1, 0.12, 1.0),           # Wandpfosten
             slab(cx, -L / 2, z + 0.62, 0.05, L, 0.06)]            # horizontaler Hauptarm
    br = slab(cx, -L * 0.34, z + 0.3, 0.045, L * 0.72, 0.045)      # Diagonalstrebe
    br.apply_transform(trimesh.transformations.rotation_matrix(
        math.atan2(0.42, L * 0.68), [1, 0, 0], point=[cx, -0.05, z + 0.08]))
    parts.append(br)
    for yy, rr in [(-0.4, 0.17), (-0.72, 0.14), (-1.02, 0.12), (-0.56, 0.1)]:   # Schnörkel
        parts.append(_curl(cx, yy, z + 0.5, rr))
    parts.append(slab(cx, -L + 0.02, z + 0.28, 0.04, 0.04, 0.34))  # Aufhängung zum Schild
    plate = disc(0.5, 0.08, cx, -L, z - 0.05, squash=0.7, sections=28)
    ring = disc(0.58, 0.05, cx, -L, z - 0.05, squash=0.7, sections=28)
    return {"schild_arm": cat(parts), "schild": plate, "gold": ring}


# ============================================================ Engine
def build(cfg):
    c = Ctx(cfg)
    groups = {}
    for name, params in cfg["elements"].items():
        if params is False or (isinstance(params, dict) and params.get("enabled") is False):
            continue
        if name not in ELEMENTS:
            print(f"  !! unbekannter Element-Generator: {name}"); continue
        for gname, mesh in ELEMENTS[name](c, params if isinstance(params, dict) else {}).items():
            groups[gname] = cat([groups.get(gname), mesh])
    return c, groups


def export(cfg):
    c, groups = build(cfg)
    out = cfg["out_dir"]; pre = cfg.get("prefix", "bw"); os.makedirs(out, exist_ok=True)
    sc = trimesh.Scene(); nf = 0
    for nm, m in groups.items():
        if m is None or not len(m.faces):
            continue
        if not isinstance(m.visual, trimesh.visual.texture.TextureVisuals):   # Textur nicht übermalen
            m.visual.face_colors = c.col.get(nm, [180, 180, 180, 255])
        sc.add_geometry(m, geom_name=nm); nf += len(m.faces)
        print(f"  {nm}: {len(m.faces)} F")
    glb = f"{out}/{cfg.get('glb', pre + '_measured.glb')}"
    sc.export(glb); cat(list(groups.values())).export(glb.replace(".glb", ".stl"))
    print(f"-> {glb}  ({nf} F)")
    print(f"   Dach-Regel: LOD2 Tiefe{c.lod2_depth:.1f}/First{c.lod2_ridge:.1f} -> "
          f"Neigung{math.degrees(c.pitch):.0f}° modelliert Tiefe{c.D:.1f}/First{c.ridge:.1f} "
          f"(Dachanteil {100*(c.ridge-c.eave)/c.ridge:.0f}%)")
    return glb


DEFAULT_COL = {
    "fassade": [228, 208, 150, 255], "gesims": [238, 232, 214, 255],
    "eg_sockel": [228, 208, 150, 255], "sockel_holz": [70, 52, 40, 255], "fenster": [40, 46, 54, 255],
    "eg_glas": [70, 54, 44, 255], "warmlicht": [240, 200, 120, 255],
    "schaufenster": [92, 62, 42, 255], "gardine": [240, 237, 230, 255],
    "rinne": [120, 120, 126, 255], "rahmen": [244, 243, 238, 255],
    "laterne": [26, 24, 22, 255], "aushang": [44, 34, 28, 255],
    "laeden": [138, 156, 138, 255], "kasten": [58, 44, 34, 255],
    "blumen": [184, 72, 82, 255], "laterne": [48, 44, 42, 255],
    "dach": [72, 73, 66, 255], "giebel": [220, 203, 160, 255],
    "gaube": [228, 208, 150, 255], "gaube_dach": [72, 73, 66, 255],
    "luke": [34, 33, 34, 255], "schornstein": [128, 80, 60, 255],
    "schild_arm": [40, 36, 34, 255], "schild": [224, 214, 180, 255],
    "gold": [196, 162, 84, 255], "band": [96, 74, 52, 255], "wappen": [176, 150, 90, 255],
    "zierband": [120, 140, 185, 255], "dachziegel": [96, 78, 70, 255],
    "gitter": [46, 42, 38, 255], "markise_rot": [198, 120, 132, 255], "markise_weiss": [240, 234, 226, 255],
    "tuer": [96, 64, 44, 255],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    print(f"== {cfg.get('name', 'Bauwerk')} ==  Elemente: {', '.join(cfg['elements'])}")
    export(cfg)


if __name__ == "__main__":
    main()
