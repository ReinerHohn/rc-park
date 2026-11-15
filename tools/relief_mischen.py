#!/usr/bin/env python3
"""relief_mischen.py <fein.npz> <grob_voll.npz> <aus.npz> [--px 0.02] - feines Hoehenbild (tools/tiefe_lokal.py) mit dem groben Relief derselben Wand zu EINEM Einsatz mischen.

Die lokale Feinrechnung trifft nur 40-60 % der Zellen (Verdeckung, schwache Schnittwinkel). Regel je Zelle des feinen Feldes (Raster --px, Standard 2 cm =
0,23 mm bei 1:87; 1 cm waere unter der Druckaufloesung und macht das STL 4x so gross):
  1. Putz (Maske 'putz' des groben Reliefs) bleibt eben wie im groben Relief.
  2. sonst das FEINE Relief, wo es Daten hat (Median der gueltigen 1-cm-Zellen im Rasterfeld);
  3. sonst das grobe Relief (echt oder generiert). Das feine wird dazu auf das Niveau des groben gebracht (Median-Versatz auf der gemeinsamen Flaeche).
Beide Hoehenbilder werden dazu in absolute Abstaende vor der Wandebene umgerechnet (rel + Ausgleichsebene). Ausgabe im Format von relief_einsatz.py
(Feld = das feine Feld) + Masken 'fein' und 'generiert'; <aus>.jpg: gruen getoent = Putz, blau = aus dem groben Relief, grau = fein. ANSEHEN.
Im Generator: grobes Relief mit `tief_felder=[Feld]` zuruecksetzen und diesen Einsatz davor setzen.
"""
import sys, os, argparse, numpy as np, cv2


def ebene(Z, H, W):
    ii, jj = np.mgrid[0:H, 0:W]; px = float(Z["px"]); tu, tz = [float(v) for v in Z["trend_je_m"]]; return float(Z["ebene_abstand_m"]) + tu * (jj + 0.5) * px - tz * (ii + 0.5) * px


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("fein"); ap.add_argument("grob"); ap.add_argument("aus"); ap.add_argument("--px", type=float, default=0.02); a = ap.parse_args()
    Fz = np.load(a.fein); Gz = np.load(a.grob); rf = Fz["rel"].astype(np.float64); Hf, Wf = rf.shape; pf = float(Fz["px"]); k = max(1, int(round(a.px / pf))); px = pf * k
    if np.abs(Fz["a"] - Gz["a"]).max() > 1e-6 or np.abs(Fz["t"] - Gz["t"]).max() > 1e-6: print("ABBRUCH: fein und grob haben nicht dieselbe Wandgerade"); return 2
    df = rf + ebene(Fz, Hf, Wf); df[rf == 0.0] = np.nan; H = Hf // k; W = Wf // k; df = df[Hf - H * k:, :W * k]         # unten buendig (z0 bleibt)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings(): warnings.simplefilter("ignore"); dfe = np.nanmedian(df.reshape(H, k, W, k).transpose(0, 2, 1, 3).reshape(H, W, k * k), axis=2)
    anz = np.isfinite(df).reshape(H, k, W, k).transpose(0, 2, 1, 3).reshape(H, W, k * k).sum(2); dfe[anz < max(1, k * k // 2)] = np.nan      # mindestens die Haelfte der 1-cm-Zellen muss Daten haben (Suedwand 15.11.: mit einer einzigen Zelle wurde das feine Relief pockennarbig)
    u0 = float(Fz["u0"]); z0 = float(Fz["z0"]); ii, jj = np.mgrid[0:H, 0:W]; U = u0 + (jj + 0.5) * px; Zz = z0 + (H - 1 - ii + 0.5) * px
    rg = Gz["rel"].astype(np.float64); Hg, Wg = rg.shape; pg = float(Gz["px"]); dg = rg + ebene(Gz, Hg, Wg); ug = (U - float(Gz["u0"])) / pg - 0.5; vg = (Hg - 1) - ((Zz - float(Gz["z0"])) / pg - 0.5)
    dgo = cv2.remap(dg.astype(np.float32), ug.astype(np.float32), vg.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).astype(np.float64)
    def maske(name):
        if name not in Gz.files: return np.zeros((H, W), bool)
        m = Gz[name].astype(np.uint8); m = np.vstack([m, np.zeros((Hg - m.shape[0], Wg), np.uint8)]) if m.shape[0] < Hg else m
        return cv2.remap(m, ug.astype(np.float32), vg.astype(np.float32), cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE) > 0
    putz = maske("putz"); gen = maske("generiert"); null_g = cv2.remap((rg == 0.0).astype(np.uint8), ug.astype(np.float32), vg.astype(np.float32), cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE) > 0
    fein = np.isfinite(dfe) & ~putz; beide = fein & ~null_g & ~gen; vers = float(np.median(dfe[beide] - dgo[beide])) if beide.sum() > 500 else 0.0
    d = np.where(fein, dfe - vers, dgo); leer = ~fein & null_g; yy, xx = ii, jj; ok = ~leer       # das FEINE auf das Niveau des groben bringen (das grobe gilt fuer die ganze Wand; umgekehrt stand der Einsatz 1-3 cm versetzt -> Linie an seiner Oberkante)
    # Entstoeren (Kontrollbild 15.11.: schwarze Sprenkel = Einzelzellen-Ausreisser der Feinrechnung und Stufen an der Grenze fein/grob): Zellen, die > 2,5 cm vom 5x5-Median abweichen, auf den Median;
    # an der Grenze fein/grob das grobe Relief ueber 3 Zellen an das feine heranfuehren.
    dm = cv2.medianBlur(np.where(ok, d, 0).astype(np.float32), 5).astype(np.float64); aus_ = ok & (np.abs(d - dm) > 0.025); d[aus_] = dm[aus_]
    w_ = np.clip(cv2.distanceTransform((~fein).astype(np.uint8), cv2.DIST_L2, 3) / 3.0, 0, 1); gl = cv2.GaussianBlur(np.where(ok, d, 0).astype(np.float32), (0, 0), 1.5).astype(np.float64) / np.maximum(cv2.GaussianBlur(ok.astype(np.float32), (0, 0), 1.5), 1e-3)
    rand_ = ~fein & ok & (w_ < 1); d[rand_] = (w_ * d + (1 - w_) * gl)[rand_]
    G = np.c_[xx[ok], yy[ok], np.ones(ok.sum())]; ko = np.linalg.lstsq(G, d[ok], rcond=None)[0]; rel = d - (ko[0] * xx + ko[1] * yy + ko[2]); rel[leer] = 0.0; rel[(rel == 0.0) & ok] = 1e-4
    niv = float(np.median(rel[putz & ok])) if (putz & ok).sum() > 50 else 0.0
    np.savez_compressed(a.aus, rel=rel.astype(np.float32), a=Fz["a"], t=Fz["t"], n=Fz["n"], u0=u0, z0=z0, px=px, lochanteil=float(leer.mean()), hub_p5_p95=float(np.subtract(*np.percentile(rel[ok], [95, 5]))), ebene_abstand_m=float(ko[2]),
                        trend_je_m=np.array([ko[0] / px, -ko[1] / px]), fein=fein, generiert=gen & ~fein, generiert_anteil=float((gen & ~fein).mean()), putz=putz, putz_niveau_m=niv, oeffnung=np.zeros((H, W), bool))
    lx = np.gradient(rel, px, axis=1); lz = np.gradient(rel, px, axis=0); s = np.clip(0.7 - 0.35 * lx + 0.5 * lz, 0, 1); im = cv2.cvtColor((s * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    im[~fein & ok & ~putz] = (im[~fein & ok & ~putz] * np.array([1.0, 0.82, 0.72])).astype(np.uint8); im[putz] = (im[putz] * np.array([0.8, 1.0, 0.8])).astype(np.uint8); im[leer] = (0, 0, 255); cv2.imwrite(os.path.splitext(a.aus)[0] + ".jpg", im)
    print(f"{os.path.basename(a.aus)}: {W}x{H} Zellen a {px*100:.0f} cm; fein {fein.mean()*100:.0f} %, aus dem groben Relief {(~fein & ok & ~putz).mean()*100:.0f} % (davon generiert {(gen & ~fein).mean()*100:.0f} %), Putz {putz.mean()*100:.0f} %, leer {leer.mean()*100:.0f} %; Versatz grob->fein {vers*100:+.1f} cm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
