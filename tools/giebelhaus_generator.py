#!/usr/bin/env python3
"""giebelhaus_generator.py — GENERISCHER Generator für GIEBELSTÄNDIGE Häuser mit TREPPENGIEBEL
(Staffelgiebel) — der zweite Gebäudetyp neben dem traufständigen bauwerk_generator.py.

Die Fassade IST der Giebel (Gable zur Straße). Aufbau: Putzfassade (stepped-gable-Polygon)
+ Sandstein-Zier (Stufen-Abdeckung, Fenstergewände, Eckquader, Arkadenbögen) als eigene
Farbgruppe + Arkade im EG + Fenster (Zahl nach oben abnehmend) + einfaches Dach dahinter.

Erstbeleg: Kornhaus Freiburg (bauwerke/kornhaus.json). Config-getrieben → nächstes Giebelhaus
per Config.

  python3 tools/giebelhaus_generator.py --config bauwerke/kornhaus.json
"""
import argparse, json, math, os
import numpy as np
import trimesh
from trimesh.creation import extrude_polygon, box as tbox, cylinder as tcyl, cone as tcone
from shapely.geometry import Polygon, box as sbox


def _stand(m, y0=0.0):
    V = m.vertices.copy(); m.vertices = np.c_[V[:, 0], y0 + V[:, 2], V[:, 1]]; return m


def _poly_mesh(poly, thick, y0=0.0):
    if poly is None or poly.is_empty:
        return None
    if not poly.is_valid:
        poly = poly.buffer(0)
    geoms = list(poly.geoms) if poly.geom_type == "MultiPolygon" else [poly]
    ms = [_stand(extrude_polygon(g, thick), y0=y0) for g in geoms if g.area > 1e-4]
    return trimesh.util.concatenate(ms) if ms else None


def slab(cx, cy, cz, sx, sy, sz):
    b = tbox(extents=(sx, sy, sz)); b.apply_translation((cx, cy, cz)); return b


def cat(parts):
    parts = [p for p in parts if p is not None and len(p.faces)]
    return trimesh.util.concatenate(parts) if parts else None


def stepped_gable_outline(W, z_body, peak, nsteps, inset):
    """Umriss-Polygon (x,z) eines Hauses mit Treppengiebel: Rechteck 0..z_body, darüber
    gestufter Giebel bis peak (nsteps Stufen je Seite, je inset nach innen)."""
    sh = (peak - z_body) / nsteps
    pts = [(0, 0), (W, 0), (W, z_body)]
    x = W
    for i in range(nsteps):                      # rechte Seite hoch
        z = z_body + (i + 1) * sh
        pts.append((x, z)); x -= inset; pts.append((x, z))
    xr = x                                        # rechte Kante des Giebel-Kopfs
    xl = W - x                                    # symmetrische linke Kante
    pts.append((xl, peak))                        # Giebel-Kopf (flach)
    x = xl
    for i in range(nsteps - 1, -1, -1):           # linke Seite runter
        z = z_body + (i + 1) * sh
        pts.append((x, z)); x += 0  # tread already at xl? build mirror
    # linke Seite sauber spiegeln:
    pts = pts[:4 + 2 * nsteps]                    # bis Kopf rechts
    # neu: Kopf + linke Treppe
    left = []
    x = xl
    for i in range(nsteps - 1, -1, -1):
        z = z_body + (i + 1) * sh
        left.append((x, z)); left.append((x - inset, z)); x -= inset
    pts = pts + [(xr, peak), (xl, peak)] + left + [(0, z_body)]
    return Polygon(pts).buffer(0)


def gable_level_x(W, z_body, peak, nsteps, inset, level):
    """verfügbare Breite + Mitte auf Giebel-Stufe `level` (0=unten)."""
    halfcut = level * inset
    return halfcut, W - halfcut                   # x_links, x_rechts der Stufe


class Giebelhaus:
    def __init__(self, cfg):
        self.cfg = cfg
        m = cfg["massing"]
        self.W = float(m["W"]); self.D = float(m.get("depth", 12.0)); self.t = float(m.get("wall_thick", 0.6))
        self.z_body = float(m["gable_start_z"]); self.peak = float(m["peak_z"])
        self.nsteps = int(m["gable_steps"])
        self.inset = (self.W - float(m.get("gable_top_w", 1.8))) / 2 / self.nsteps
        self.eg_top = float(cfg["facade"]["eg_top"])
        self.col = {**DEFAULT_COL, **cfg.get("colors", {})}

    # -- Fenster-Rechteck (x0,x1,z0,z1) --
    def _win(self, cx, zc, w, h):
        return (cx - w / 2, cx + w / 2, zc - h / 2, zc + h / 2)

    def window_specs(self):
        """alle Fenster (cx, zc, w, h, arched). Primär AUTOMATISCH aus dem Fenster-Detektor
        (fenster_zaehler.py JSON), sonst Fallback auf handgepflegte Config-Reihen."""
        if self.cfg["facade"].get("fenster_auto"):
            return self._windows_from_detector(self.cfg["facade"]["fenster_auto"])
        f = self.cfg["facade"]; specs = []
        for row in f.get("body_rows", []):
            z = row["z"]; n = row["n"]; w = row.get("w", 0.85); h = row.get("h", 1.5)
            margin = row.get("margin", 1.6)
            xs = np.linspace(margin, self.W - margin, n)
            for cx in xs:
                specs.append((cx, z, w, h, row.get("arched", False)))
        # Giebel-Stufen
        g = f.get("gable_rows", [])
        sh = (self.peak - self.z_body) / self.nsteps
        for gr in g:
            lv = gr["level"]; n = gr["n"]; w = gr.get("w", 0.8); h = gr.get("h", 1.2)
            xl, xr = gable_level_x(self.W, self.z_body, self.peak, self.nsteps, self.inset, lv)
            z = self.z_body + (lv + 0.5) * sh
            xs = np.linspace(xl + 1.0, xr - 1.0, n) if n > 1 else [self.W / 2]
            for cx in xs:
                specs.append((cx, z, w, h, gr.get("arched", False)))
        return specs

    def _windows_from_detector(self, path):
        """Detektor-JSON (Fraktionen der Gebäude-Box) -> Fenster in Modell-Metern. Box-Höhe ≈
        First (LOD2), Box-Breite ≈ W. z_frac 0=unten. KEIN Hardcoding: Zahl/Lage kommt vom
        Foto-Detektor fenster_zaehler.py."""
        d = json.load(open(path)); specs = []
        for row in d["rows"]:
            z = row["z_frac"] * self.peak                     # Box-Oberkante ≈ First-Höhe
            w = row["w_frac"] * self.W
            h = row["h_frac"] * self.peak
            arched = (h / max(w, 0.1)) > 1.55                 # hohe schmale = Bogenfenster
            for xf in row["x_fracs"]:
                specs.append((xf * self.W, z, w, h, arched))
        print(f"  Fenster AUS DETEKTOR {path}: {len(specs)} ({d['n_rows']} Reihen)")
        return specs

    def arcade_openings(self):
        n = int(self.cfg["facade"].get("arcade", {}).get("n", 3))
        pitch = self.W / n; aw = pitch * 0.72; spring = 1.8; apex = self.eg_top - 0.2
        out = []
        for i in range(n):
            xc = (i + 0.5) * pitch
            out.append((xc, aw, spring, apex))
        return out

    # -- Putzfassade (weiß) mit Fenster- + Arkadenlöchern --
    def facade(self):
        outline = stepped_gable_outline(self.W, self.z_body, self.peak, self.nsteps, self.inset)
        poly = outline
        for cx, zc, w, h, _ in self.window_specs():
            poly = poly.difference(sbox(cx - w / 2, zc - h / 2, cx + w / 2, zc + h / 2))
        for xc, aw, spring, apex in self.arcade_openings():     # Arkade: Spitzbogen-Öffnung
            poly = poly.difference(self._arch_poly(xc, aw, 0.0, spring, apex))
        return _poly_mesh(poly.buffer(0), self.t)

    def _arch_poly(self, xc, w, z0, spring, apex):
        s = w / 2; pts = [(xc - s, z0), (xc + s, z0), (xc + s, spring)]
        for k in range(1, 11):
            a = math.pi * k / 10
            pts.append((xc + s * math.cos(a), spring + (apex - spring) * math.sin(a)))
        pts.append((xc - s, spring))
        return Polygon(pts).buffer(0)

    # -- Sandstein-Zier (rosa): Stufen-Abdeckung, Gewände, Eckquader, Arkadenbögen, Fiale --
    def sandstone(self):
        parts = []
        # Treppengiebel-Abdeckung: entlang der Stufenkanten dünne vorstehende Leisten
        sh = (self.peak - self.z_body) / self.nsteps
        for i in range(self.nsteps + 1):
            xl, xr = gable_level_x(self.W, self.z_body, self.peak, self.nsteps, self.inset, i)
            z = self.z_body + i * sh
            parts.append(slab((xl + xr) / 2, -0.12, z, (xr - xl) + 0.1, 0.24, 0.18))     # waagrechte Stufen-Abdeckung
            if i < self.nsteps:                                                           # senkrechte Riser-Kanten
                for xe in (xl, xr):
                    parts.append(slab(xe, -0.12, z + sh / 2, 0.22, 0.24, sh))
        # Gesims-/Gurtbänder (rosa Sandstein-Stringcourse): über der Arkade (das 'Kornhaus'-Band)
        # und am Giebelfuß (Traufgesims, auf dem der Treppengiebel aufsetzt)
        for zb_band, hb in self.cfg["facade"].get("string_courses", []):
            parts.append(slab(self.W / 2, -0.12, zb_band, self.W + 0.2, 0.26, hb))
        # Eckquader (Eckquaderung) links + rechts im Body (abwechselnd)
        for xe in (0.0, self.W):
            for k in range(int(self.z_body / 0.7)):
                if k % 2 == 0:
                    parts.append(slab(xe, -0.1, 0.35 + k * 0.7, 0.7, 0.22, 0.5))
        # Fenstergewände (rosa Rahmen um jedes Fenster)
        for cx, zc, w, h, arched in self.window_specs():
            t = 0.16
            parts.append(slab(cx, -0.08, zc + h / 2 + t / 2, w + 2 * t, 0.18, t))
            parts.append(slab(cx, -0.08, zc - h / 2 - t / 2, w + 2 * t, 0.18, t))
            parts.append(slab(cx - w / 2 - t / 2, -0.08, zc, t, 0.18, h + 2 * t))
            parts.append(slab(cx + w / 2 + t / 2, -0.08, zc, t, 0.18, h + 2 * t))
        # Arkadenbögen (Spitzbogen-Ring, rosa)
        for xc, aw, spring, apex in self.arcade_openings():
            ring = self._arch_poly(xc, aw + 0.3, 0.0, spring + 0.15, apex + 0.22).difference(
                self._arch_poly(xc, aw, 0.0, spring, apex)).buffer(0)
            parts.append(_poly_mesh(ring, 0.3, y0=-0.3))
        # Fiale an der Spitze
        fin = tcone(radius=0.3, height=1.0, sections=6); fin.apply_translation((self.W / 2, -0.2, self.peak)); parts.append(fin)
        kn = trimesh.creation.icosphere(subdivisions=0, radius=0.18); kn.apply_translation((self.W / 2, -0.2, self.peak + 0.9)); parts.append(kn)
        return cat(parts)

    def windows_glass(self):
        parts = []
        for cx, zc, w, h, _ in self.window_specs():
            parts.append(slab(cx, self.t - 0.1, zc, w - 0.04, 0.06, h - 0.04))
        return cat(parts)

    def window_muntins(self):
        parts = []
        for cx, zc, w, h, _ in self.window_specs():
            parts.append(slab(cx, -0.02, zc, 0.05, 0.05, h))         # Pfosten
            parts.append(slab(cx, -0.02, zc, w, 0.05, 0.05))         # Kämpfer
        return cat(parts)

    def arcade_recess(self):
        back = tbox(extents=(self.W, 0.3, self.eg_top)); back.apply_translation((self.W / 2, 2.0, self.eg_top / 2))
        return back

    def arcade_glow(self):
        parts = []
        for xc, aw, spring, apex in self.arcade_openings():
            g = slab(xc, 0.4, apex * 0.55, aw * 0.9, 0.1, apex * 0.9); parts.append(g)
        return cat(parts)

    def roof(self):
        """Satteldach HINTER dem Treppengiebel: First läuft front->hinten (parallel zur Tiefe),
        Traufen auf z_body an x=0/x=W. WICHTIG (giebelständig/Zackenhaus): das Dach darf in der
        FRONTANSICHT NICHT sichtbar sein — die Giebel-Treppenwand schirmt es ab. Deshalb:
        - Dach beginnt HINTER der Fassade (y0 = Wandstärke t, nicht y=0)
        - First-Höhe < peak (Giebelwand ragt als Staffel über das Dach) -> von vorn voll verdeckt
        - KEINE vordere Giebel-Dreiecksfläche (die war der sichtbare 'Scheindach'-Fehler)."""
        W, D, zb, pk, t = self.W, self.D, self.z_body, self.peak, self.t
        z_ridge = zb + (pk - zb) * 0.60             # First deutlich unter Giebelspitze -> verdeckt
        y0 = t                                      # hinter der Fassadenwand
        V = [(0, y0, zb), (W, y0, zb), (0, D, zb), (W, D, zb),
             (W / 2, y0, z_ridge), (W / 2, D, z_ridge)]
        F = [(0, 4, 5), (0, 5, 2), (1, 3, 5), (1, 5, 4),   # nur die zwei Dachflächen (Satteldach)
             (2, 5, 3)]                                     # hinterer Giebel geschlossen
        # KEINE vordere Giebelfläche: die würde als Dreieck in den Himmel-Lücken zwischen den
        # Treppenstufen sichtbar = genau der 'Scheindach'-Fehler. Die Dachschrägen selbst liegen
        # unter jeder Stufen-Tread -> von vorn unsichtbar. Front bleibt offen (Dach ist eigenes
        # Druckteil, bei Bedarf separat solidifizieren).
        return trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F))

    def lanterns(self):
        parts = []
        for sx in (0.7, self.W - 0.7):
            b = tcyl(radius=0.16, height=0.4, sections=6); b.apply_translation((sx, -0.45, self.eg_top - 1.0)); parts.append(b)
            parts.append(slab(sx, -0.25, self.eg_top - 0.7, 0.05, 0.5, 0.05))
        return cat(parts)

    def build(self):
        parts = {
            "fassade": self.facade(),
            "sandstein": self.sandstone(),
            "fenster": self.windows_glass(),
            "sprossen": self.window_muntins(),
            "laube": self.arcade_recess(),
            "warmlicht": self.arcade_glow(),
            "dach": self.roof(),
            "laterne": self.lanterns(),
        }
        return parts

    def export(self):
        parts = self.build(); out = self.cfg["out_dir"]; pre = self.cfg.get("prefix", "gh")
        os.makedirs(out, exist_ok=True); sc = trimesh.Scene(); nf = 0
        for nm, mdl in parts.items():
            if mdl is None or not len(mdl.faces):
                print(f"  (leer {nm})"); continue
            mdl.visual.face_colors = self.col.get(nm, [180, 180, 180, 255])
            mdl.export(f"{out}/{pre}_{nm}.stl"); sc.add_geometry(mdl, geom_name=nm); nf += len(mdl.faces)
            print(f"  {nm}: {len(mdl.faces)} F")
        glb = f"{out}/{self.cfg.get('glb', pre + '_measured.glb')}"
        sc.export(glb); cat(list(parts.values())).export(glb.replace(".glb", ".stl"))
        print(f"-> {glb}  ({nf} F)  W{self.W} Giebel {self.z_body}->{self.peak} ({self.nsteps} Stufen)")
        return glb


DEFAULT_COL = {
    "fassade": [236, 230, 224, 255], "sandstein": [204, 150, 142, 255],
    "fenster": [48, 52, 60, 255], "sprossen": [210, 210, 205, 255],
    "laube": [60, 48, 44, 255], "warmlicht": [240, 198, 120, 255],
    "dach": [120, 96, 86, 255], "laterne": [40, 38, 36, 255],
}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True); a = ap.parse_args()
    cfg = json.load(open(a.config)); print(f"== {cfg.get('name', 'Giebelhaus')} ==")
    Giebelhaus(cfg).export()


if __name__ == "__main__":
    main()
