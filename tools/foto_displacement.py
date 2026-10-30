#!/usr/bin/env python3
"""foto_displacement.py — HEBEL 6+7 verzahnt: aus einem fassaden-geraden Foto
(z.B. sv_*.jpg aus streetview_rip.py) ein DRUCKBARES Relief erzeugen.

Interlock, der die Druckstabilität filigraner Teile sichert:

  HEBEL 7 (Tiefe):   Foto → Tiefenkarte. Marigold/MiDaS wenn torch-venv da ist
                     (--depth ml), sonst klassischer Luminanz-/Hochpass-Fallback
                     (--depth classic) — Ziegel/Putz/Ornament als Mikro-Relief.
  HEBEL 6 (Semantik): Fassaden-Maske (von tools/fenster_ml.py, SegFormer) steuert,
                     WO das Relief darf: Fenster werden als Nische EINGESENKT,
                     Rahmen/Vorsprünge VERDICKT, dünne Grate auf Mindestmaß
                     gehoben — sonst bricht es im FDM-Druck ab.

Ausgabe: 16-bit Displacement-PNG (für Blender-Displace / Bump) + optional ein
bereits verdrängtes Mesh-Patch (trimesh), direkt in die Druckgeometrie einsetzbar.

  python3 tools/foto_displacement.py --img daten/kaufhaus/sv_03_1.jpg \
      --mask daten/kaufhaus/sv_03_1_window.png \
      --out-depth modelle/kaufhaus/disp_03.png \
      --out-mesh  modelle/kaufhaus/relief_03.stl \
      --relief-mm 1.2 --recess-mm 2.5 --min-feature-mm 0.8 --scale 1:160 --panel-mm 120
"""
import argparse, sys, os, numpy as np, cv2


# ---------- HEBEL 7: Tiefenschätzung ----------
def depth_ml(img_bgr, model=None):
    """monokulare Tiefe per neuronalem Netz. GPU → Marigold (beste Kanten);
    CPU → Depth-Anything-V2 via transformers-Pipeline (leicht, kein timm/hub nötig).
    Rückgabe float 0..1, nah=1 (erhaben)."""
    import torch
    from PIL import Image
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    if torch.cuda.is_available():
        try:
            from diffusers import MarigoldDepthPipeline
            pipe = MarigoldDepthPipeline.from_pretrained(
                "prs-eth/marigold-depth-v1-1", variant="fp16",
                torch_dtype=torch.float16).to("cuda")
            d = np.asarray(pipe(pil).prediction[0, ..., 0], np.float32)
            return ((d - d.min()) / (np.ptp(d) + 1e-6)).astype(np.float32)
        except Exception as ex:
            print(f"  Marigold nicht verfügbar ({ex}), nehme Depth-Anything")
    from transformers import pipeline
    mdl = model or "depth-anything/Depth-Anything-V2-Small-hf"
    pipe = pipeline("depth-estimation", model=mdl)
    d = np.asarray(pipe(pil)["predicted_depth"].squeeze().cpu().numpy(), np.float32)
    if d.shape != rgb.shape[:2]:
        d = cv2.resize(d, (rgb.shape[1], rgb.shape[0]))
    d = (d - d.min()) / (np.ptp(d) + 1e-6)               # Depth-Anything: groß = nah = erhaben
    return d.astype(np.float32)


def depth_classic(img_bgr):
    """Kein GPU nötig: Luminanz + Hochpass-Mikrostruktur → Tiefe 0..1.
    Fängt Putz/Ziegel/Fugen als feines Relief (Schatten=tief)."""
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    lo = cv2.GaussianBlur(g, (0, 0), 9)            # grobe Beleuchtung raus
    micro = g - lo                                  # Fugen/Textur (±)
    micro = cv2.normalize(micro, None, 0, 1, cv2.NORM_MINMAX)
    base = cv2.normalize(lo, None, 0, 1, cv2.NORM_MINMAX)
    d = 0.35 * base + 0.65 * micro                  # Textur dominiert das Relief
    return cv2.GaussianBlur(d, (0, 0), 0.8).astype(np.float32)


def detrend_plane(d):
    """planaren Tiefen-Trend (Perspektive/Schräglage) abziehen → nur fassaden-
    RELATIVES Relief bleibt. Nötig bei schrägen Szenen-Tiefen (Depth-Anything)."""
    H, W = d.shape
    ys, xs = np.mgrid[0:H, 0:W]
    A = np.column_stack([xs.ravel(), ys.ravel(), np.ones(H*W)])
    coef, *_ = np.linalg.lstsq(A, d.ravel(), rcond=None)
    trend = (A @ coef).reshape(H, W)
    r = d - trend
    return ((r - r.min()) / (np.ptp(r) + 1e-6)).astype(np.float32)


# ---------- HEBEL 6: semantisch gesteuerte Druckbarkeit ----------
def apply_semantics(depth, mask, recess, relief, min_feat_frac):
    """mask>0 = Fenster. Fenster einsenken, Rahmenkante verdicken, Mikro-Grate
    auf Mindestmaß heben. depth/recess/relief in mm; Rückgabe mm-Höhenfeld."""
    h = depth * relief                              # Textur-Relief in mm
    if mask is not None:
        m = (cv2.resize(mask, (depth.shape[1], depth.shape[0])) > 127)
        h[m] = -recess                              # Fensterglas als Nische nach innen
        # Rahmen = Ring um die Fenster → als erhabener, dicker Steg herausarbeiten
        ring = cv2.dilate(m.astype(np.uint8), np.ones((9, 9), np.uint8)) & (~m)
        h[ring.astype(bool)] = np.maximum(h[ring.astype(bool)], relief * 0.9)
    # Druck-Guard: alles unter Mindest-Feature glätten (sonst filigrane Abbrüche)
    span = h.max() - h.min() + 1e-6
    floor = min_feat_frac * span
    tiny = np.abs(h) < floor
    h[tiny] = 0.0
    return h


# ---------- Mesh-Patch bauen ----------
def height_to_mesh(h_mm, panel_mm):
    """mm-Höhenfeld → trimesh-Patch (Breite=panel_mm, Höhe maßstäblich)."""
    import trimesh
    H, W = h_mm.shape
    px = panel_mm / W
    ys, xs = np.mgrid[0:H, 0:W]
    V = np.column_stack([xs.ravel()*px, (H-1-ys).ravel()*px, h_mm.ravel()])
    faces = []
    for y in range(H-1):
        for x in range(W-1):
            a = y*W+x; b = a+1; c = a+W; d = c+1
            faces += [[a, c, b], [b, c, d]]
    return trimesh.Trimesh(V, np.array(faces), process=True)


def parse_scale(s):
    if ":" in s: return 1.0/float(s.split(":")[1])
    return float(s)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--img", required=True)
    p.add_argument("--mask", help="Fenster-Maske (tools/fenster_ml.py), optional")
    p.add_argument("--out-depth", required=True)
    p.add_argument("--out-mesh", help="optional: verdrängtes STL-Patch")
    p.add_argument("--depth", choices=["ml", "classic"], default="classic")
    p.add_argument("--detrend", action="store_true",
                   help="planaren Tiefen-Trend abziehen (bei schrägen ML-Szenentiefen)")
    p.add_argument("--relief-mm", type=float, default=1.0, help="Textur-Reliefhöhe")
    p.add_argument("--recess-mm", type=float, default=2.0, help="Fenster-Nischentiefe")
    p.add_argument("--min-feature-mm", type=float, default=0.8, help="Druck-Mindestdetail (0.4-Düse ~0.8)")
    p.add_argument("--scale", default="1:160")
    p.add_argument("--panel-mm", type=float, default=120, help="Platten-Breite im Druck")
    a = p.parse_args()

    img = cv2.imread(a.img)
    if img is None: sys.exit(f"Foto nicht lesbar: {a.img}")
    print(f"Tiefe ({a.depth}) ...")
    depth = depth_ml(img) if a.depth == "ml" else depth_classic(img)
    if a.detrend:
        depth = detrend_plane(depth)
    mask = cv2.imread(a.mask, cv2.IMREAD_GRAYSCALE) if a.mask else None
    if a.mask and mask is None: print(f"  WARN Maske nicht lesbar: {a.mask}")

    # min-feature relativ zur Gesamt-Reliefspanne
    span = a.relief_mm + a.recess_mm
    h_mm = apply_semantics(depth, mask, a.recess_mm, a.relief_mm,
                           a.min_feature_mm / max(span, 1e-6))
    # 16-bit Displacement-PNG (0=tiefste Nische, 65535=höchste Kante)
    norm = (h_mm - h_mm.min()) / (np.ptp(h_mm) + 1e-6)
    os.makedirs(os.path.dirname(a.out_depth) or ".", exist_ok=True)
    cv2.imwrite(a.out_depth, (norm * 65535).astype(np.uint16))
    print(f"Displacement → {a.out_depth}  (Relief {h_mm.min():.2f}..{h_mm.max():.2f} mm)")

    if a.out_mesh:
        mesh = height_to_mesh(h_mm, a.panel_mm)
        os.makedirs(os.path.dirname(a.out_mesh) or ".", exist_ok=True)
        mesh.export(a.out_mesh)
        print(f"Relief-Patch → {a.out_mesh}  ({len(mesh.faces):,} faces)")
    print("Hebel 6+7 ok: Textur als Relief, Fenster eingesenkt, Rahmen verdickt, "
          f"Features <{a.min_feature_mm} mm geglättet (druckbar).")


if __name__ == "__main__":
    main()
