#!/usr/bin/env python3
"""fassade_fein.py <ortho-ordner> [--nur f02,e17] [--k 4] - FEINES, nahtfreies Fassadenbild aus den Einzelfoto-Orthos (fassade_ortho.py --einzeln --zelle 0.01).

Warum (Nutzer 15.11.2026: Sechseck-Verglasung am Kaufhaus, Steinrelief-Details an Martins-/Schwabentor): bei 1 cm Zelle zeigt die zellweise Mischung von
fassade_ortho Naehte und Geister - die Fotos liegen 0,1-1 m gegeneinander versetzt, weil die Modellflaeche (grobes Stufenmodell) nicht die echte Tiefe hat
und die Kameras Reste haben. Ein EINZELNES entzerrtes Foto ist dagegen in sich scharf. Also:
  1. Bezugsfoto je Fassade = groesste Summe (Zellen x Guete) aus fassaden.json.
  2. Die naechstbesten k-1 Fotos per SIFT + RANSAC-Homographie IM ORTHO-RAUM auf das Bezugsfoto ziehen (ebene Fassade -> Homographie; Kontrolle: Inlier >= 40,
     Verschiebung der Bildecken <= 2 m, sonst Foto verworfen).
  3. Ergebnis: Median der ausgerichteten Fotos, wo >= 3 die Zelle sehen (Passanten, Draehte, Spiegelungen fallen heraus), sonst das beste vorhandene.
Ausgabe ortho_<id>_fein.png + Bericht fein.json (Bezugsfoto, Inlier, Versatz je Foto). Massstab und Lage bleiben die des Bezugsfotos auf der Modellebene
(Lagefehler der Ebene geht 1:1 ein - das Bild ist fuer MUSTER und Kanten, Masse weiter ueber foto_mass.py).
"""
import sys, os, json, argparse, numpy as np, cv2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ortho"); ap.add_argument("--nur"); ap.add_argument("--k", type=int, default=4); a = ap.parse_args()
    FA = json.load(open(os.path.join(a.ortho, "fassaden.json")))["fassaden"]; bericht = {}; sift = cv2.SIFT_create(8000)
    for F in FA:
        fid = F.get("id"); ed = os.path.join(a.ortho, f"ortho_{fid}_einzeln")
        if (a.nur and fid not in a.nur.split(",")) or not os.path.isdir(ed) or not F.get("fotos"): continue
        rang = sorted(F["fotos"].items(), key=lambda kv: -kv[1]["zellen"] * kv[1]["guete_median"])[:a.k]; bilder = []
        for nr, _ in rang:
            im = cv2.imread(os.path.join(ed, nr + ".png"))
            if im is not None: bilder.append((nr, im))
        if not bilder: continue
        ref_nr, ref = bilder[0]; H_, W_ = ref.shape[:2]; g0 = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY); m0 = (ref.sum(2) > 0).astype(np.uint8) * 255; k0, d0 = sift.detectAndCompute(g0, cv2.erode(m0, np.ones((9, 9), np.uint8)))
        stapel = [ref]; info = [dict(foto=ref_nr, rolle="bezug")]
        for nr, im in bilder[1:]:
            g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); m = (im.sum(2) > 0).astype(np.uint8) * 255; k1, d1 = sift.detectAndCompute(g, cv2.erode(m, np.ones((9, 9), np.uint8)))
            if d0 is None or d1 is None or len(k1) < 50: info.append(dict(foto=nr, rolle="verworfen", grund="zu wenig Merkmale")); continue
            mm = cv2.BFMatcher().knnMatch(d1, d0, k=2); gut = [p for p, q in (x for x in mm if len(x) == 2) if p.distance < 0.75 * q.distance]
            if len(gut) < 40: info.append(dict(foto=nr, rolle="verworfen", grund=f"{len(gut)} Paare")); continue
            src = np.float32([k1[p.queryIdx].pt for p in gut]); dst = np.float32([k0[p.trainIdx].pt for p in gut]); Hm, inl = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
            n_in = int(inl.sum()) if inl is not None else 0
            if Hm is None or n_in < 40: info.append(dict(foto=nr, rolle="verworfen", grund=f"{n_in} Inlier")); continue
            ecken = np.float32([[0, 0], [W_, 0], [W_, H_], [0, H_]]).reshape(-1, 1, 2); vers = float(np.abs(cv2.perspectiveTransform(ecken, Hm) - ecken).max()) * F["raster"]["zelle"]
            if vers > 2.0: info.append(dict(foto=nr, rolle="verworfen", grund=f"Eckversatz {vers:.1f} m")); continue
            w = cv2.warpPerspective(im, Hm, (W_, H_), flags=cv2.INTER_LINEAR); stapel.append(w); info.append(dict(foto=nr, rolle="ausgerichtet", inlier=n_in, eckversatz_m=round(vers, 2), mittel_versatz_m=round(float(np.linalg.norm(cv2.perspectiveTransform(src[inl.ravel() > 0].reshape(-1, 1, 2), Hm).reshape(-1, 2) - src[inl.ravel() > 0], axis=1).mean()) * F["raster"]["zelle"], 3)))
        S = np.stack(stapel).astype(np.float32); gueltig = S.sum(3) > 0; n = gueltig.sum(0); S[~gueltig] = np.nan
        with np.errstate(all="ignore"): med = np.nanmedian(S, axis=0)
        erst = np.zeros((H_, W_, 3), np.float32); belegt = np.zeros((H_, W_), bool)
        for i in range(len(stapel)):
            nimm = gueltig[i] & ~belegt; erst[nimm] = np.nan_to_num(S[i])[nimm]; belegt |= gueltig[i]
        aus = np.where((n >= 3)[..., None], np.nan_to_num(med), erst).astype(np.uint8); cv2.imwrite(os.path.join(a.ortho, f"ortho_{fid}_fein.png"), aus)
        bericht[fid] = dict(fotos=info, abdeckung=round(float(belegt.mean()), 3), zelle=F["raster"]["zelle"]); print(f"{fid}: Bezug {ref_nr[-14:]}, " + ", ".join(f"{i_['foto'][-10:]} {i_['rolle']}" + (f" ({i_['inlier']} Inl., {i_['mittel_versatz_m']*100:.0f} cm)" if i_["rolle"] == "ausgerichtet" else f" ({i_.get('grund', '')})" if i_["rolle"] == "verworfen" else "") for i_ in info[1:]) + f"; Abdeckung {belegt.mean():.0%}")
    json.dump(bericht, open(os.path.join(a.ortho, "fein.json"), "w"), indent=1); return 0


if __name__ == "__main__":
    sys.exit(main())
