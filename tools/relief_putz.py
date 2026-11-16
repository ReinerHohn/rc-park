#!/usr/bin/env python3
"""relief_putz.py <relief.npz> <aus.npz> <objekt.json> FOTO [FOTO ...] [--feld u0 u1 z0 z1] [--massstab k x y z] [--s 0.22] [--v 0.45] - Putzflaechen eines Relief-Einsatzes glaetten.

Warum (Nutzer 15.11.2026: "guck dir mal die Details an"; Kontrollbild Modell neben Foto): auf GLATTEM PUTZ ist das Scan-Relief nur Rauschen (Beulen, Loecher),
waehrend die Eckquader daneben echt sind. Die Grenze Putz/Stein steht scharf im Foto (weisser Putz gegen roten Sandstein) - also Form aus Fotokanten:
  je Reliefzelle den Punkt auf der Ausgleichsebene in jedes Foto projizieren (Kamera K-<FOTO>.json, k1), Farbe lesen; Putz = wenig Saettigung (< --s) und hell (> --v);
  Mehrheit ueber die Fotos, kleine Flecken weg, eingeschlossene Loecher (Wandbild, Uhr, Fenstergewaende) zum Putz; im Putz rel = Median (ebene Flaeche).
--feld begrenzt die Anwendung (z. B. nur oberhalb des Bruchsteinsockels). --massstab: Relief liegt im ROHRAHMEN (Schwabentor Nord), Punkt vor der Projektion
X' = M + k (X - M). aus.npz traegt die Maske 'putz'; aus.jpg zeigt sie gruen - ANSEHEN. Danach ggf. tools/steine_generieren.py (laesst Putz in Ruhe).
"""
import sys, os, json, glob, argparse, numpy as np, cv2
from scipy import ndimage as ndi


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("relief"); ap.add_argument("aus"); ap.add_argument("objekt"); ap.add_argument("fotos", nargs="+"); ap.add_argument("--feld", nargs=4, type=float)
    ap.add_argument("--massstab", nargs=4, type=float); ap.add_argument("--kern", nargs=4, type=float, action="append", default=[], help="Feld u0 u1 z0 z1, das sicher ganz Putz ist (Draehte, Rohre, Vordachschatten im Foto ueberstimmen)"); ap.add_argument("--s", type=float, default=0.22); ap.add_argument("--v", type=float, default=0.45); ap.add_argument("--min_m2", type=float, default=0.5); a = ap.parse_args()
    Z = dict(np.load(a.relief)); rel = Z["rel"].astype(np.float64); H, W = rel.shape; px = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"]); A = Z["a"]; t = Z["t"]; n = Z["n"]
    ii, jj = np.mgrid[0:H, 0:W]; U = u0 + (jj + 0.5) * px; ZZ = z0 + (H - 1 - ii + 0.5) * px; tu, tz = [float(v) for v in Z["trend_je_m"]]
    d = float(Z["ebene_abstand_m"]) + tu * (jj + 0.5) * px - tz * (ii + 0.5) * px
    X = np.c_[(A[0] + U * t[0] + d * n[0]).ravel(), (A[1] + U * t[1] + d * n[1]).ravel(), ZZ.ravel()]
    if a.massstab: k = a.massstab[0]; Mp = np.array(a.massstab[1:]); X = Mp + k * (X - Mp)
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); fd = json.load(open(a.objekt))["fotos_dir"]; stimmen = np.zeros(H * W); gesehen = np.zeros(H * W)
    for nm in a.fotos:
        K = json.load(open(os.path.join(od, "messprotokoll", "K-" + nm + ".json")))["kamera"]; R = cv2.Rodrigues(np.array(K["rvec"]))[0]; tt = np.array(K["t"])
        fl_ = glob.glob(os.path.join(root, fd, nm + ".*")) or glob.glob(os.path.join(root, fd, nm + "_*")); im = cv2.imread(fl_[0]) if fl_ else None
        if im is None: print(f"    Foto {nm} nicht im fotos_dir {fd} - uebersprungen (objekt.json fotos_dir pruefen)"); continue      # 16.11.2026: Kettenlauf brach hier 16x mit IndexError ab
        p = X @ R.T + tt; x = p[:, 0] / p[:, 2]; y = p[:, 1] / p[:, 2]; f_ = 1 + float(K.get("k1") or 0) * (x * x + y * y); mx = (K["f_px"] * x * f_ + K["cx"]).astype(np.float32); my = (K["f_px"] * y * f_ + K["cy"]).astype(np.float32)
        ppm = K["f_px"] / np.median(p[:, 2]); im = cv2.GaussianBlur(im, (0, 0), max(0.5, 0.4 * px * ppm))            # auf Zellgroesse glaetten
        ok = (p[:, 2] > 0) & (mx > 2) & (mx < im.shape[1] - 3) & (my > 2) & (my < im.shape[0] - 3)
        c = cv2.remap(im, mx.reshape(H, W), my.reshape(H, W), cv2.INTER_LINEAR); hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float64)
        putz = (hsv[:, 1] / 255.0 < a.s) & (hsv[:, 2] / 255.0 > a.v); stimmen += putz & ok; gesehen += ok
        print(f"{nm}: {ok.mean()*100:.0f} % der Zellen im Bild, davon Putz {100 * (putz & ok).sum() / max(ok.sum(), 1):.0f} %")
    putz = ((stimmen >= 0.5 * np.maximum(gesehen, 1)) & (gesehen > 0)).reshape(H, W)
    if a.feld: f0, f1, g0, g1 = a.feld; putz &= (U >= f0) & (U <= f1) & (ZZ >= g0) & (ZZ <= g1)
    for f0_, f1_, g0_, g1_ in a.kern: putz |= (U >= f0_) & (U <= f1_) & (ZZ >= g0_) & (ZZ <= g1_)
    putz = ndi.binary_closing(ndi.binary_opening(putz, iterations=1), iterations=2); lab, m = ndi.label(putz)
    if m: gr = ndi.sum(putz, lab, np.arange(1, m + 1)); putz = np.isin(lab, 1 + np.flatnonzero(gr * px * px >= a.min_m2))
    putz = ndi.binary_fill_holes(putz)
    if a.feld: putz &= (U >= f0) & (U <= f1) & (ZZ >= g0) & (ZZ <= g1)
    if putz.sum() < 100: print("kein Putz gefunden"); return 2
    echt = putz & (rel != 0.0); niveau = float(np.median(rel[echt])) if echt.sum() > 50 else 0.0; stein = ~putz & (rel != 0.0)
    neu = rel.copy(); neu[putz] = niveau if abs(niveau) > 1e-6 else 1e-4
    Z["rel"] = neu.astype(np.float32); Z["putz"] = putz; Z["putz_niveau_m"] = niveau; np.savez_compressed(a.aus, **Z)
    lx = np.gradient(neu, px, axis=1); lz = np.gradient(neu, px, axis=0); s = np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1); im = cv2.cvtColor((s * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    im[putz] = (im[putz] * np.array([0.8, 1.0, 0.8])).astype(np.uint8); cv2.imwrite(os.path.splitext(a.aus)[0] + ".jpg", cv2.resize(im, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
    print(f"{os.path.basename(a.aus)}: Putz {putz.mean()*100:.1f} % der Flaeche ({putz.sum()*px*px:.0f} m2), Putzniveau {niveau*100:+.1f} cm, Stein im Mittel {np.median(rel[stein])*100:+.1f} cm")


if __name__ == "__main__":
    sys.exit(main())
