#!/usr/bin/env python3
"""fassade_fein.py <ortho-ordner> [--nur f02,e17] [--k 6] - FEINES, nahtfreies Fassadenbild aus den Einzelfoto-Orthos (fassade_ortho.py --einzeln --zelle 0.01).

Warum (Nutzer 15.11.2026: Sechseck-Verglasung am Kaufhaus, Steinrelief-Details an Martins-/Schwabentor): bei 1 cm Zelle zeigt die zellweise Mischung von
fassade_ortho Naehte und Geister - die Fotos liegen 0,1-1 m gegeneinander versetzt (Modellflaeche != echte Tiefe, Kamerareste). Ein EINZELNES entzerrtes
Foto ist in sich scharf. Verdecker (Baum, Mast, Schild, Passanten) werden OHNE Farbregel erkannt - Nutzer: "nicht Laub ausblenden, zu spezifisch; was ist bei
einem gruenen oder gelben Gebaeude?" Grundsatz: was VOR der Wand steht, wandert von Foto zu Foto (Parallaxe); die Wand selbst bleibt deckungsgleich.
  1. SIFT je Foto, Homographie + RANSAC zwischen allen Fotopaaren im Ortho-Raum. Eine Homographie passt nur auf die WANDEBENE - Merkmale auf dem Baum
     werden keine Inlier. Bezugsfoto = groesste Inlier-Summe zu den anderen (zeigt am meisten Wand, die auch andere sehen), nicht die groesste Bildflaeche.
  2. Alle Fotos mit >= 40 Inliern und Eckversatz <= 2 m auf das Bezugsfoto ziehen.
  3. Uebereinstimmung je Zelle: Median der ausgerichteten Fotos; ein Foto gilt an einer Stelle als VERDECKT, wenn es dort grossflaechig vom Median abweicht
     (geglaettete Farbdifferenz > --abw). Verdeckte Stellen zaehlen als nicht gesehen. Ergebnis = Median der nicht verdeckten Fotos (>= 3), sonst das beste nicht verdeckte.
     Wo nur EIN Foto hinsieht, laesst sich nichts pruefen - die Stelle bleibt wie fotografiert und steht als 'ungeprueft' in abdeckung_<id>_fein.png (grau).
Ausgabe ortho_<id>_fein.png, abdeckung_<id>_fein.png (weiss = >= 3 Fotos einig, grau = 1-2 Fotos, schwarz = nichts), Bericht fein.json.
Massstab und Lage = Bezugsfoto auf der Modellebene; das Bild ist fuer MUSTER und Kanten, Masse weiter ueber foto_mass.py.
"""
import sys, os, json, argparse, numpy as np, cv2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ortho"); ap.add_argument("--nur"); ap.add_argument("--k", type=int, default=6); ap.add_argument("--abw", type=float, default=38.0); a = ap.parse_args()
    FA = json.load(open(os.path.join(a.ortho, "fassaden.json")))["fassaden"]; bericht = {}; sift = cv2.SIFT_create(8000); bf = cv2.BFMatcher()
    for F in FA:
        fid = F.get("id"); ed = os.path.join(a.ortho, f"ortho_{fid}_einzeln")
        if (a.nur and fid not in a.nur.split(",")) or not os.path.isdir(ed) or not F.get("fotos"): continue
        rang = sorted(F["fotos"].items(), key=lambda kv: -kv[1]["zellen"] * kv[1]["guete_median"])[:a.k]; B = []
        for nr, _ in rang:
            im = cv2.imread(os.path.join(ed, nr + ".png"))
            if im is None: continue
            m = (im.sum(2) > 0).astype(np.uint8) * 255; kp, de = sift.detectAndCompute(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), cv2.erode(m, np.ones((9, 9), np.uint8))); B.append(dict(nr=nr, im=im, kp=kp, de=de))
        if not B: continue
        H_, W_ = B[0]["im"].shape[:2]; zl = F["raster"]["zelle"]; n = len(B); HM = {}; INL = np.zeros((n, n), int); ecken = np.float32([[0, 0], [W_, 0], [W_, H_], [0, H_]]).reshape(-1, 1, 2)
        for i in range(n):                                                 # Homographie j -> i fuer alle Paare
            for j in range(n):
                if i == j or B[i]["de"] is None or B[j]["de"] is None or len(B[j]["kp"]) < 50 or len(B[i]["kp"]) < 50: continue
                mm = bf.knnMatch(B[j]["de"], B[i]["de"], k=2); gut = [p for p, q in (x for x in mm if len(x) == 2) if p.distance < 0.75 * q.distance]
                if len(gut) < 40: continue
                src = np.float32([B[j]["kp"][p.queryIdx].pt for p in gut]); dst = np.float32([B[i]["kp"][p.trainIdx].pt for p in gut]); Hm, inl = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
                if Hm is None or inl is None or int(inl.sum()) < 40: continue
                vers = float(np.abs(cv2.perspectiveTransform(ecken, Hm) - ecken).max()) * zl
                if vers > 2.0: continue
                sel = inl.ravel() > 0; HM[(i, j)] = (Hm, int(inl.sum()), vers, float(np.linalg.norm(cv2.perspectiveTransform(src[sel].reshape(-1, 1, 2), Hm).reshape(-1, 2) - src[sel], axis=1).mean()) * zl); INL[i, j] = int(inl.sum())
        ref = int(np.argmax(INL.sum(1))) if INL.sum() > 0 else 0; stapel = [B[ref]["im"]]; info = [dict(foto=B[ref]["nr"], rolle="bezug", inlier_summe=int(INL[ref].sum()))]
        for j in range(n):
            if j == ref: continue
            if (ref, j) not in HM: info.append(dict(foto=B[j]["nr"], rolle="verworfen", grund="keine sichere Homographie zum Bezug")); continue
            Hm, ni, vers, mv = HM[(ref, j)]; stapel.append(cv2.warpPerspective(B[j]["im"], Hm, (W_, H_), flags=cv2.INTER_LINEAR)); info.append(dict(foto=B[j]["nr"], rolle="ausgerichtet", inlier=ni, eckversatz_m=round(vers, 2), mittel_versatz_m=round(mv, 3)))
        S = np.stack(stapel).astype(np.float32); gueltig = S.sum(3) > 0
        def median(S, g):
            T = S.copy(); T[~g] = np.nan
            with np.errstate(all="ignore"):
                import warnings
                with warnings.catch_warnings(): warnings.simplefilter("ignore"); return np.nanmedian(T, axis=0)
        med = median(S, gueltig); n_s = gueltig.sum(0); verdeckt = np.zeros_like(gueltig); kern = max(5, int(0.12 / zl) | 1)
        for i in range(len(stapel)):                                       # Verdecker: grossflaechige Abweichung vom Median, nur wo >= 3 Fotos pruefen koennen
            d = np.abs(S[i] - np.nan_to_num(med)).max(2); d[~gueltig[i] | (n_s < 3)] = 0; d = cv2.blur(d, (kern, kern)); v = (d > a.abw).astype(np.uint8)
            v = cv2.dilate(cv2.morphologyEx(v, cv2.MORPH_OPEN, np.ones((kern, kern), np.uint8)), np.ones((2 * kern + 1, 2 * kern + 1), np.uint8)).astype(bool); verdeckt[i] = v & gueltig[i]
        g2 = gueltig & ~verdeckt; med2 = median(S, g2); n2 = g2.sum(0); erst = np.zeros((H_, W_, 3), np.float32); belegt = np.zeros((H_, W_), bool)
        for g_ in (g2, gueltig):                                           # Rueckfall: bestes nicht verdecktes Foto, dann irgendeines
            for i in range(len(stapel)):
                nimm = g_[i] & ~belegt; erst[nimm] = S[i][nimm]; belegt |= g_[i]
        aus = np.where((n2 >= 3)[..., None], np.nan_to_num(med2), erst).astype(np.uint8); cv2.imwrite(os.path.join(a.ortho, f"ortho_{fid}_fein.png"), aus)
        cv2.imwrite(os.path.join(a.ortho, f"abdeckung_{fid}_fein.png"), np.where(n2 >= 3, 255, np.where(belegt, 110, 0)).astype(np.uint8))
        for k_, i_ in enumerate([x for x in info if x["rolle"] != "verworfen"]): i_["verdeckt_anteil"] = round(float(verdeckt[k_].sum()) / max(int(gueltig[k_].sum()), 1), 3)
        bericht[fid] = dict(fotos=info, abdeckung=round(float(belegt.mean()), 3), einig_ab_3_fotos=round(float((n2 >= 3).mean()), 3), zelle=zl)
        print(f"{fid}: Bezug {B[ref]['nr'][-14:]} (Inlier-Summe {int(INL[ref].sum())}), " + ", ".join(f"{i_['foto'][-10:]} " + (f"{i_['inlier']} Inl. {i_['mittel_versatz_m']*100:.0f} cm verdeckt {i_['verdeckt_anteil']:.0%}" if i_["rolle"] == "ausgerichtet" else "verworfen") for i_ in info[1:]) + f"; Bezug verdeckt {info[0]['verdeckt_anteil']:.0%}; einig (>= 3 Fotos) {(n2 >= 3).mean():.0%}, Abdeckung {belegt.mean():.0%}")
    json.dump(bericht, open(os.path.join(a.ortho, "fein.json"), "w"), indent=1); return 0


if __name__ == "__main__":
    sys.exit(main())
