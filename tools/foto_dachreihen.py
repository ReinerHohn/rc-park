#!/usr/bin/env python3
"""foto_dachreihen.py - Reihenabstand der Dachdeckung (Biberschwanz-Reihen) aus kalibrierten Fotos (2026-11-12, kreis1 r1).
Hang-Ebene (aus Traufe/First in (u,n,z)) wird je Foto metrisch entzerrt (1 cm/px), die Helligkeit entlang des Hangs (s) gemittelt (Hochpass), die Autokorrelation
liefert die Reihenperiode (Peaks bei k * Abstand). Messprotokoll messprotokoll/ZR-dachreihen.json. Kein Zugriff auf Generator-/Wolkendaten ausser der Hangebene.
Aufruf: python -I tools/foto_dachreihen.py modelle/<objekt>/objekt.json <teilindex-oder-typ> FOTO[,FOTO..] [--u 5,8] [--s 3.5,9.5]
"""
import sys, os, json, glob, numpy as np, cv2


def main():
    a = sys.argv[1:]; obj = json.load(open(a[0])); typ = a[1]; fotos = a[2].split(","); R0 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0]))))
    ur = [float(x) for x in a[a.index("--u") + 1].split(",")] if "--u" in a else [5.0, 8.0]; sr = [float(x) for x in a[a.index("--s") + 1].split(",")] if "--s" in a else [3.5, 9.5]
    cfg = next(b for b in obj["bauteile"] if b.get("typ") == typ); nn = np.array(cfg["achse_n"], float); nn /= np.linalg.norm(nn); uu = np.array([nn[1], -nn[0]])
    ntv, ztv, nf, zf = (float(cfg[k]) for k in ("n_traufe_v", "z_traufe_v", "n_first", "z_first")); L = np.hypot(ntv - nf, zf - ztv); t = np.array([(nf - ntv) / L, (zf - ztv) / L])
    od = os.path.join(R0, os.path.dirname(obj["masstabelle"])); res = 0.01; erg = {}
    for nr in fotos:
        K = json.load(open(os.path.join(od, "messprotokoll", f"K-{nr}.json")))["kamera"]; Rm, _ = cv2.Rodrigues(np.array(K["rvec"]))
        fn = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))[0]; im = cv2.imread(fn, 0)
        s = np.arange(sr[0], sr[1], res); u = np.arange(ur[0], ur[1], res); S, U = np.meshgrid(s, u, indexing="ij")
        X = np.stack([U * uu[0] + (ntv + t[0] * S) * nn[0], U * uu[1] + (ntv + t[0] * S) * nn[1], ztv + t[1] * S], -1)
        c = X @ Rm.T + np.array(K["t"]); x, y = c[..., 0] / c[..., 2], c[..., 1] / c[..., 2]; d = 1 + K.get("k1", 0.0) * (x * x + y * y)
        o = cv2.remap(im, (K["cx"] + K["f_px"] * x * d).astype(np.float32), (K["cy"] + K["f_px"] * y * d).astype(np.float32), cv2.INTER_LINEAR)
        g = o.astype(np.float32); g -= cv2.GaussianBlur(g, (0, 0), 30); prof = g.mean(1); prof -= prof.mean()
        ac = np.correlate(prof, prof, "full")[len(prof) - 1:]; ac /= ac[0]
        pk = [(round(i * res, 3), round(float(ac[i]), 2)) for i in range(6, len(ac) - 1) if ac[i] > ac[i - 1] and ac[i] >= ac[i + 1]][:5]
        erg[nr] = dict(peaks_m_korr=pk, erste_periode_m=pk[0][0] if pk else None)
        print(nr, "Hang-Autokorr Peaks (m, Korr.):", pk)
    per = [v["erste_periode_m"] for v in erg.values() if v["erste_periode_m"]]
    rec = dict(id="ZR-dachreihen", typ="dachreihen_autokorrelation", bauteil=typ, fotos=fotos, u_bereich=ur, s_bereich=sr, je_foto=erg, reihenabstand_m=round(float(np.median(per)), 3) if per else None,
               massstab_von="Kameras aus SfM-Buendel (K-*.json), Hangebene aus Traufe/First des Bauteils; Reihenabstand intern (nur relativ zur Hangebene, Fehler = Hangneigungsfehler)")
    os.makedirs(os.path.join(od, "messprotokoll"), exist_ok=True); json.dump(rec, open(os.path.join(od, "messprotokoll", "ZR-dachreihen.json"), "w"), indent=1, ensure_ascii=False)
    print("Reihenabstand Median", rec["reihenabstand_m"], "m")


if __name__ == "__main__": main()
