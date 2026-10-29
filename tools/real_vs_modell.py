#!/usr/bin/env python3
"""real_vs_modell.py — scharfe Bewertung REALITÄT gegen MODELL.

Richtet Foto-Fassade und Modell-Render auf GLEICHE Silhouetten-Box aus (Breite+Höhe),
legt die Modell-KANTEN (Canny) rot aufs Foto und misst:
  - Silhouetten-IoU (grobe Form/Proportion)
  - vertikale Profile der Breite (Treppengiebel-Stufen: Breite über Höhe) real vs modell
  - Score 0..1 + annotiertes Overlay

  python3 tools/real_vs_modell.py <foto> <fotobox x0,y0,x1,y1 frac> <model_render.png> <out.png>
"""
import argparse
import numpy as np
import cv2


def silhouette(bgr, bg_is_white=True):
    """Vordergrund-Maske (Gebäude) — alles was nicht Hintergrund (Himmel/weiss) ist."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if bg_is_white:
        m = (g < 243).astype(np.uint8)
    else:
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        sky = (hsv[:, :, 2] > 150) & (hsv[:, :, 1] < 45) & (bgr[:, :, 0].astype(int) >= bgr[:, :, 2].astype(int))
        m = (~sky).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA])); m = (lab == i).astype(np.uint8)
    return m


def width_profile(mask, nb=40):
    """Breite (in Maskenbreiten-Anteil) über die Höhe — die Treppengiebel-Signatur."""
    H, W = mask.shape
    prof = []
    for b in range(nb):
        y0, y1 = int(b / nb * H), int((b + 1) / nb * H)
        band = mask[y0:y1]
        cols = np.where(band.any(0))[0]
        prof.append((cols.max() - cols.min()) / W if len(cols) else 0.0)
    return np.array(prof)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("foto"); ap.add_argument("box"); ap.add_argument("model"); ap.add_argument("out")
    a = ap.parse_args()
    img = cv2.imread(a.foto); H0, W0 = img.shape[:2]
    f = [float(t) for t in a.box.split(",")]
    ph = img[int(f[1] * H0):int(f[3] * H0), int(f[0] * W0):int(f[2] * W0)]
    mo = cv2.imread(a.model)

    pm = silhouette(ph, bg_is_white=False)
    mm = silhouette(mo, bg_is_white=True)
    # auf Bounding-Box beider Silhouetten zuschneiden
    def bbox(m):
        ys, xs = np.where(m); return xs.min(), ys.min(), xs.max(), ys.max()
    px0, py0, px1, py1 = bbox(pm); mx0, my0, mx1, my1 = bbox(mm)
    phc = ph[py0:py1, px0:px1]; pmc = pm[py0:py1, px0:px1]
    moc = mo[my0:my1, mx0:mx1]; mmc = mm[my0:my1, mx0:mx1]
    Ht, Wt = phc.shape[:2]
    moR = cv2.resize(moc, (Wt, Ht)); mmR = cv2.resize(mmc, (Wt, Ht))

    # Silhouetten-IoU
    inter = int((pmc & mmR).sum()); uni = int((pmc | mmR).sum())
    iou = inter / max(uni, 1)
    # Breiten-Profile
    pp = width_profile(pmc); mp = width_profile(mmR)
    prof_err = float(np.mean(np.abs(pp - mp)))

    # Overlay: Modell-Kanten rot aufs Foto
    edges = cv2.Canny(moR, 60, 160)
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8))
    ov = phc.copy(); ov[edges > 0] = (0, 0, 255)
    # Breiten-Profil-Balken rechts anhängen
    bar = np.full((Ht, 220, 3), 255, np.uint8)
    for i in range(len(pp)):
        y0 = int(i / len(pp) * Ht); y1 = int((i + 1) / len(pp) * Ht)
        cv2.rectangle(bar, (0, y0), (int(pp[i] * 100), y1), (120, 120, 120), -1)      # real grau
        cv2.rectangle(bar, (110, y0), (110 + int(mp[i] * 100), y1), (0, 0, 255), -1)  # modell rot
    cv2.putText(bar, "real|modell", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    out = np.hstack([ov, bar])
    score = 0.6 * iou + 0.4 * (1 - min(prof_err * 3, 1))
    cv2.putText(out, f"IoU={iou:.3f} profErr={prof_err:.3f} score={score:.3f}",
                (6, Ht - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 80, 0), 2)
    cv2.imwrite(a.out, out)
    print(f"Silhouetten-IoU   = {iou:.3f}")
    print(f"Breiten-Profil-Fehler = {prof_err:.3f}  (0=perfekt)")
    print(f"SCORE = {score:.3f}")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
