#!/usr/bin/env python3
"""kanten_pipelines.py - S10 Teil A: vier Kantenkarten-Pipelines je Foto (weiche Karten, 0..1 je Pixel, Bildraster unveraendert).

P1 hell   : mehrstufiges Canny ueber Skalen x Belichtungen (Gamma/CLAHE); Karte = Anteil bestaetigender Varianten (innerhalb 1 px), leicht verbreitert.
P2 farbe  : Stufenhoehe (Kontrast in Lab-Delta-E bzw. Farbton*Saettigung) aus Gauss-Gradient x Sigma x sqrt(2 pi) -> skalenfrei;
            Non-Maximum-Suppression quer zur Kante; p = glatte Stufe zwischen DE_LO und DE_HI. Trennt rot/gold bei gleicher Helligkeit.
P3 gelernt: DexiNed (kornia, Apache-2.0-Code; Gewichte BIPED, siehe LIZENZ_WERKZEUGE.md), sigmoid der fusionierten Ausgabe, Mehrskalen-Mittel.
P4 segment: Grenzen automatisch erzeugter SAM-Masken (transformers facebook/sam-vit-base, Apache-2.0); Karte = gewichtete Grenzdichte
            (stability/pred_iou-gewichtet), verbreitert. Objekt-/Materialgrenzen, keine Textur.
Gemeinsame Ausgabe: <aus>/<pipeline>/<name>.png (8 bit, Wert/255 = Kantenwahrscheinlichkeit). Keine Objektnamen, keine Festwerte aus einem Objekt;
die Schwellen unten sind physikalisch begruendete Konstanten (ANNAHME: Delta-E 2,3 = gerade sichtbar, 25 = starke Kante), nicht am Pruefbild getunt.

Aufruf:  kanten_pipelines.py --bilder ORDNER|DATEI... --aus ORDNER [--pipelines p1,p2,p3,p4] [--fotos 001,004]
Funktionen (Import): karte_p1(bgr), karte_p2(bgr), karte_p3(bgr, modell=None), karte_p4(bgr, modell=None)
"""
import argparse, glob, os, sys, time
import numpy as np, cv2

DE_LO, DE_HI = 4.0, 22.0         # Delta-E-Stufe: darunter p=0, darueber p=1 (ANNAHME, fest, nicht getunt)
HUE_SAT_MIN = 0.15               # Farbton zaehlt erst ab dieser Saettigung (HSV, 0..1)
PIPES = ("p1", "p2", "p3", "p4")
NAMEN = {"p1": "hell", "p2": "farbe", "p3": "gelernt", "p4": "segment"}


def _smooth01(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- P1
def karte_p1(bgr, sigmas=(1.0, 2.0, 4.0), low=12, high=36):
    """Canny ueber Skalen (Gauss sigma auf Originalraster) x 4 Belichtungen; p = Anteil der 12 Varianten, die innerhalb 1 px bestaetigen."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g0 = g.astype(np.float32) / 255.0
    bel = [g, (np.power(g0, 0.4) * 255).astype(np.uint8), (np.power(g0, 2.2) * 255).astype(np.uint8),
           cv2.createCLAHE(clipLimit=3.0, tileGridSize=(16, 16)).apply(g)]
    acc = np.zeros(g.shape, np.float32); n = 0
    k3 = np.ones((3, 3), np.uint8)
    for b in bel:
        for s in sigmas:
            e = cv2.Canny(cv2.GaussianBlur(b, (0, 0), s), low, high) > 0
            acc += cv2.dilate(e.astype(np.uint8), k3).astype(np.float32); n += 1
    p = acc / n                                             # 0..1, Plateau 3 px breit
    return np.clip(p, 0, 1).astype(np.float32)


# ---------------------------------------------------------------- P2
def _nms(mag, gx, gy):
    """Non-Maximum-Suppression quer zur Kante (Richtung des Gradienten, 4 Klassen), Plateau-tolerant (>=)."""
    ang = (np.degrees(np.arctan2(gy, gx)) + 180.0) % 180.0
    H, W = mag.shape
    out = np.zeros_like(mag)
    pad = np.pad(mag, 1, mode="edge")
    c = pad[1:-1, 1:-1]
    sh = lambda dy, dx: pad[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
    cls = [((ang < 22.5) | (ang >= 157.5), sh(0, -1), sh(0, 1)), ((ang >= 22.5) & (ang < 67.5), sh(-1, -1), sh(1, 1)),
           ((ang >= 67.5) & (ang < 112.5), sh(-1, 0), sh(1, 0)), ((ang >= 112.5) & (ang < 157.5), sh(-1, 1), sh(1, -1))]
    for m, a, b in cls:
        k = m & (c >= a) & (c >= b)
        out[k] = c[k]
    return out


def karte_p2(bgr, sigmas=(1.5, 3.0)):
    """Farbkanten: Lab-Delta-E-Stufe und Farbton-Stufe (gewichtet mit Saettigung); Stufenhoehe = |grad| * sigma * sqrt(2 pi)."""
    f = bgr.astype(np.float32) / 255.0
    lab = cv2.cvtColor(f, cv2.COLOR_BGR2Lab)                 # L 0..100, a/b ~ -128..127 (float32-Konvention)
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)                 # H 0..360, S 0..1
    h = np.deg2rad(hsv[..., 0]); s = hsv[..., 1]
    hx, hy = np.cos(h), np.sin(h)                            # Farbton als Einheitsvektor (kein Sprung bei 360)
    sw = np.clip(s / HUE_SAT_MIN, 0, 1)
    out = np.zeros(bgr.shape[:2], np.float32)
    for sg in sigmas:
        k = sg * np.sqrt(2 * np.pi)
        gxs, gys, mags = [], [], []
        for ch in (lab[..., 0], lab[..., 1], lab[..., 2]):
            b = cv2.GaussianBlur(ch, (0, 0), sg)
            gxs.append(cv2.Sobel(b, cv2.CV_32F, 1, 0, ksize=3) / 8.0); gys.append(cv2.Sobel(b, cv2.CV_32F, 0, 1, ksize=3) / 8.0)
        gx = np.sqrt(sum(a * a for a in gxs)); gy = np.sqrt(sum(a * a for a in gys))
        # Richtung aus der Struktur-Summe (Vorzeichen der staerksten Kanalkomponente nicht noetig: nur Orientierung)
        Jxx = sum(a * a for a in gxs); Jyy = sum(a * a for a in gys); Jxy = sum(a * b_ for a, b_ in zip(gxs, gys))
        th = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)           # Orientierung des Gradienten
        mag = np.sqrt(Jxx + Jyy)
        # Farbton-Beitrag (in Delta-E-aehnlichen Einheiten: Farbtonwinkel 1 rad ~ Chroma-Abstand bei S*100 ... ANNAHME: C = 100*S)
        bx = cv2.GaussianBlur(hx * sw, (0, 0), sg); by = cv2.GaussianBlur(hy * sw, (0, 0), sg)
        hxx = cv2.Sobel(bx, cv2.CV_32F, 1, 0, ksize=3) / 8.0; hxy = cv2.Sobel(bx, cv2.CV_32F, 0, 1, ksize=3) / 8.0
        hyx = cv2.Sobel(by, cv2.CV_32F, 1, 0, ksize=3) / 8.0; hyy = cv2.Sobel(by, cv2.CV_32F, 0, 1, ksize=3) / 8.0
        hmag = 60.0 * np.sqrt(hxx ** 2 + hxy ** 2 + hyx ** 2 + hyy ** 2)
        tot = np.sqrt(mag ** 2 + hmag ** 2)
        gxn = np.cos(th) * tot; gyn = np.sin(th) * tot
        step = _nms(tot * k, gxn, gyn)
        out = np.maximum(out, _smooth01(step, DE_LO, DE_HI))
    return cv2.GaussianBlur(cv2.dilate(out, np.ones((3, 3), np.uint8)), (0, 0), 0.7).clip(0, 1).astype(np.float32)


# ---------------------------------------------------------------- P3
_DEXI = {}


def _dexined(dev):
    if "m" not in _DEXI:
        import torch
        from kornia.models.dexined import DexiNed
        m = DexiNed(pretrained=True).to(dev).eval()
        _DEXI["m"] = m
    return _DEXI["m"]


def karte_p3(bgr, skalen=(1.0, 0.5), dev=None):
    """DexiNed (Eingang BGR 0..255 minus Mittel, Seiten Vielfache von 16). Mittel ueber Eingangsskalen (Textur feiner/gröber)."""
    import torch
    dev = dev or ("cuda" if torch.cuda.is_available() else "cpu")
    m = _dexined(dev)
    H, W = bgr.shape[:2]
    mean = np.array([103.939, 116.779, 123.68], np.float32)
    acc = np.zeros((H, W), np.float32)
    for sc in skalen:
        im = cv2.resize(bgr, (max(16, int(round(W * sc / 16)) * 16), max(16, int(round(H * sc / 16)) * 16)), interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_LINEAR)
        x = torch.from_numpy((im.astype(np.float32) - mean).transpose(2, 0, 1)[None]).to(dev)
        with torch.no_grad():
            p = torch.sigmoid(m(x))[0, 0].float().cpu().numpy()
        acc += cv2.resize(p, (W, H), interpolation=cv2.INTER_LINEAR)
    return np.clip(acc / len(skalen), 0, 1).astype(np.float32)


# ---------------------------------------------------------------- P4
_SAM = {}


def _sam(dev):
    if "m" not in _SAM:
        from transformers import SamModel, SamProcessor
        nm = os.environ.get("KANTEN_SAM", "facebook/sam-vit-base")
        _SAM["m"] = (SamModel.from_pretrained(nm).to(dev).eval(), SamProcessor.from_pretrained(nm))
    return _SAM["m"]


def karte_p4(bgr, dev=None, raster=24, min_anteil=0.0005, stab=0.85, iou=0.80, lang=1024, batch=48):
    """Grenzdichte der automatischen SAM-Masken: Punktraster raster x raster, je Punkt 3 Masken; behalten bei pred_iou >= iou und Stabilitaet >= stab
    (SAM-Stabilitaet: Flaeche bei Logit +1 / Flaeche bei Logit -1) und Flaeche zwischen min_anteil und 90 %. Je Maske 1-px-Grenze, gewichtet mit
    iou*stabilitaet; p = 1 - exp(-Summe/1,5) (mehrere Masken teilen eine Grenze -> sicherer). Alles auf der GPU (Masken nie auf Originalgroesse)."""
    import torch, torch.nn.functional as F
    from PIL import Image
    dev = dev or ("cuda" if torch.cuda.is_available() else "cpu")
    model, proc = _sam(dev)
    H, W = bgr.shape[:2]
    s = lang / max(H, W)
    sm = cv2.resize(bgr, (int(round(W * s)), int(round(H * s))), interpolation=cv2.INTER_AREA) if s < 1 else bgr
    h, w = sm.shape[:2]
    pil = Image.fromarray(cv2.cvtColor(sm, cv2.COLOR_BGR2RGB))
    inp = proc(images=pil, return_tensors="pt")
    rh, rw = [int(v) for v in inp["reshaped_input_sizes"][0]]              # Bild im 1024er Rahmen (lange Seite 1024)
    with torch.no_grad():
        emb = model.get_image_embeddings(inp["pixel_values"].to(dev))
    f = 1024.0 / max(h, w)
    ys, xs = np.meshgrid((np.arange(raster) + 0.5) / raster * h, (np.arange(raster) + 0.5) / raster * w, indexing="ij")
    pts = np.stack([xs.ravel() * f, ys.ravel() * f], 1).astype(np.float32)
    acc = torch.zeros((1, 1, h, w), device=dev)
    for i in range(0, len(pts), batch):
        pb = torch.from_numpy(pts[i:i + batch]).to(dev)[None, :, None, :]      # (1,N,1,2)
        with torch.no_grad():
            out = model(image_embeddings=emb, input_points=pb, multimask_output=True)
            lg = out.pred_masks[0].float()                                     # (N,3,256,256)
            n = lg.shape[0]
            lg = F.interpolate(lg.reshape(n * 3, 1, 256, 256), size=(1024, 1024), mode="bilinear", align_corners=False)[:, :, :rh, :rw]
            lg = F.interpolate(lg, size=(h, w), mode="bilinear", align_corners=False)    # (n*3,1,h,w)
            sc = out.iou_scores[0].float().reshape(n * 3)
            m = (lg > 0).float(); a0 = m.sum((1, 2, 3))
            st = (lg > 1).float().sum((1, 2, 3)) / (lg > -1).float().sum((1, 2, 3)).clamp(min=1)
            ok = (sc >= iou) & (st >= stab) & (a0 >= min_anteil * h * w) & (a0 <= 0.9 * h * w)
            if not ok.any(): continue
            m = m[ok]; wt = (sc[ok] * st[ok])[:, None, None, None]
            gr = (F.max_pool2d(m, 3, 1, 1) - (-F.max_pool2d(-m, 3, 1, 1))).clamp(0, 1)   # morphologischer Gradient
            acc += (gr * wt).sum(0, keepdim=True)
    p = (1.0 - torch.exp(-acc / 1.5))[0, 0].cpu().numpy()
    p = cv2.GaussianBlur(p, (0, 0), 0.7)
    if (h, w) != (H, W): p = cv2.resize(p, (W, H), interpolation=cv2.INTER_LINEAR)
    return np.clip(p, 0, 1).astype(np.float32)


KARTEN = {"p1": karte_p1, "p2": karte_p2, "p3": karte_p3, "p4": karte_p4}


def speichern(p, pfad):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    cv2.imwrite(pfad, np.round(np.clip(p, 0, 1) * 255).astype(np.uint8))


def laden(pfad):
    return cv2.imread(pfad, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bilder", nargs="+", required=True, help="Ordner (*.jpg/png) oder Dateien (Bilder moeglichst unverzerrt = Lochkamera)")
    ap.add_argument("--aus", required=True)
    ap.add_argument("--pipelines", default="p1,p2,p3,p4")
    ap.add_argument("--fotos", help="Komma-Liste Dateinamen-Stamm (z. B. 001,004); sonst alle")
    ap.add_argument("--vorhanden-ueberspringen", action="store_true")
    a = ap.parse_args(argv)
    files = []
    for b in a.bilder:
        files += sorted(glob.glob(os.path.join(b, "*.jpg")) + glob.glob(os.path.join(b, "*.png"))) if os.path.isdir(b) else [b]
    if a.fotos:
        w = set(a.fotos.split(",")); files = [f for f in files if os.path.splitext(os.path.basename(f))[0] in w]
    pipes = [p for p in a.pipelines.split(",") if p]
    t0 = time.time()
    for i, f in enumerate(files):
        nm = os.path.splitext(os.path.basename(f))[0]
        bgr = cv2.imread(f)
        if bgr is None: print("nicht lesbar", f); continue
        for p in pipes:
            ziel = os.path.join(a.aus, p, nm + ".png")
            if a.vorhanden_ueberspringen and os.path.exists(ziel): continue
            t1 = time.time(); k = KARTEN[p](bgr); speichern(k, ziel)
            print(f"[{i + 1}/{len(files)}] {nm} {p} {time.time() - t1:5.1f}s mittel={k.mean():.4f} anteil>0.5={(k > 0.5).mean():.4f}", flush=True)
    print(f"fertig {len(files)} Bilder in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
