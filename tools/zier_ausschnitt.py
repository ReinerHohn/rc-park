#!/usr/bin/env python3
"""zier_ausschnitt.py - Ausschnitte erkannter Zierteile (Figuren, Wappen ...) in VOLLER Fotoaufloesung aus den Originalfotos (2026-11-05).

Warum: Fassaden-Orthos haben 5 cm/Zelle (eine 1,6-m-Figur = 32 px) - zu grob fuer Bild-zu-3D (TripoSR/TripoSG). Die Elemente aus fassade_parsing
(elemente.json: Fassade o, d, n; Box u0..u1, z0..z1 in m) werden mit den Buendelkameras (K-Dateien, k1) in jedes Foto projiziert; je Element
gewinnt das Foto mit der groessten Pixelhoehe * Blickkosinus (frontal und nah), Box ganz im Bild. Sichtpruefung: Strahl Kamera -> Boxmitte gegen
Modell + LoD2-Nachbarn (fassade_ortho), erster Treffer nahe der Wand. Ausgabe je Element <aus>/<klasse>_<fassade>_<i>.png + ausschnitte.json.

  /media/oem/scan/venv-seg/bin/python -I tools/zier_ausschnitt.py <objekt.json> --elemente <elemente.json> --stl <modell.stl> --aus DIR [--klassen figur]
"""
import os, sys, json, glob, math, argparse
import numpy as np, cv2, trimesh
TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
import fehlteile_finden as FF
from fassade_ortho import projizieren, nachbarn_netz


ZIEL = {"figur": ["a statue of a person", "a sculpture of a knight"]}
GEGEN = ["a wrought iron sign", "a shop sign", "a canopy", "roof tiles", "a window", "a lamp", "a plain wall"]


class Pruefer:
    """OWLv2 (Apache-2.0, wie fassade_parsing) auf dem hochaufloesenden Ausschnitt: hoechster Box-Score je Begriff; ok, wenn ein Zielbegriff vor
    allen Gegenbegriffen liegt (2026-11-05: Ausschnitte zeigten Schilder/Baldachine statt Figuren, Figur 19 hinter einem Wirtshausschild)."""
    def __init__(self, min_hoehe=0.5, min_score=0.5):   # min_score 0.5: Kaufhaus echte Figuren 0,60-0,66, Fehltreffer <= 0,44 (VORLAEUFIG, am 2. Objekt pruefen)
        self.min_hoehe, self.min_score = min_hoehe, min_score
        import torch
        from transformers import Owlv2Processor, Owlv2ForObjectDetection
        self.t = torch; self.dev = "cuda" if torch.cuda.is_available() else "cpu"; M_ = "google/owlv2-base-patch16-ensemble"
        self.P = Owlv2Processor.from_pretrained(M_); self.M = Owlv2ForObjectDetection.from_pretrained(M_).eval().to(self.dev)
    def __call__(self, bgr, klasse):
        ziel = ZIEL.get(klasse, [f"a {klasse}"]); txt = ziel + GEGEN; rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        with self.t.no_grad():
            inp = self.P(text=[txt], images=rgb, return_tensors="pt").to(self.dev); out = self.M(**inp)
            lg = out.logits[0].sigmoid()                                                                  # (Boxen, Begriffe)
            bx = out.pred_boxes[0]                                                                        # (cx, cy, w, h) normiert auf das gepolsterte Quadrat
        H, W = rgb.shape[:2]; hn = bx[:, 3] * max(H, W) / H                                               # Boxhoehe relativ zur Ausschnitthoehe
        gross = hn >= self.min_hoehe                                                                       # Ziel zaehlt nur, wenn es den Ausschnitt fuellt (Element = Box; abgeschnittener Kopf unten im Baldachin-Ausschnitt zaehlt nicht)
        sc = {t_: float((lg[gross, j] if t_ in ziel else lg[:, j]).max()) if (t_ not in ziel or gross.any()) else 0.0 for j, t_ in enumerate(txt)}; b = max(sc, key=sc.get)
        return dict(ok=b in ziel and sc[b] >= self.min_score, bester=b, scores={k: round(v, 3) for k, v in sc.items()})


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--elemente", required=True); ap.add_argument("--stl", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--pruefen", action="store_true", help="Ausschnitt per OWLv2 gegen Gegenbegriffe pruefen, sonst naechstes Foto (Schilder/Baldachine vor der Figur)")
    ap.add_argument("--klassen", default="figur"); ap.add_argument("--rand", type=float, default=0.15, help="Rand um die Box (Anteil)"); ap.add_argument("--min-cos", type=float, default=0.5); ap.add_argument("--max-versuche", type=int, default=6)
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    E = json.load(open(a.elemente)); kl = set(a.klassen.split(",")); pruefer = Pruefer() if a.pruefen else None
    m = trimesh.load(a.stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); nb, _ = nachbarn_netz(obj); szene = trimesh.util.concatenate([m, nb]) if nb is not None else m
    RI = trimesh.ray.ray_pyembree.RayMeshIntersector if hasattr(trimesh.ray, "ray_pyembree") else trimesh.ray.ray_triangle.RayMeshIntersector; ray = RI(szene)
    fotos = sorted(os.path.basename(k)[2:-5] for k in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")) if json.load(open(k)).get("kamera", {}).get("buendel_tor", {}).get("ok"))
    kams = {}
    for nr in fotos:
        pf = glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + "_*"))
        if not pf: continue
        K = json.load(open(FF.k_datei(a.objekt, obj, ROOT, nr))); kk = K["kamera"]; H, W = cv2.imread(pf[0]).shape[:2]
        R, t, f, _, _ = FF.kamera_laden(K, obj, nr, ROOT, W, H); tr = np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float)
        kams[nr] = dict(pf=pf[0], R=R, t=np.asarray(t, float), f=f, cx=float(kk.get("cx", W / 2)), cy=float(kk.get("cy", H / 2)), k1=float(kk.get("k1") or 0.0), W=W, H=H, tr=tr, C=-R.T @ np.asarray(t, float) - tr)
    erg = []
    for fid, Fa in E["fassaden"].items():
        o, d, n = np.array(Fa["o"], float), np.array(Fa["d"], float), np.array(Fa["n"], float)
        for i, e in enumerate(Fa["elemente"]):
            if e["klasse"] not in kl: continue
            uu = np.array([e["u0"], e["u1"], e["u1"], e["u0"]]); zz = np.array([e["z0"], e["z0"], e["z1"], e["z1"]])
            X = np.c_[o[0] + uu * d[0], o[1] + uu * d[1], zz]; M_ = X.mean(0); best = None; kand = []
            for nr, k in kams.items():
                v = k["C"] - M_; dist = np.linalg.norm(v); cosw = float(v[:2] @ n / max(1e-6, np.linalg.norm(v[:2]))) * float(np.linalg.norm(v[:2]) / dist)
                if cosw < a.min_cos: continue
                px, z = projizieren(X + k["tr"], k["R"], k["t"], k["f"], k["cx"], k["cy"], k["k1"])
                if (z <= 1).any(): continue
                x0, y0 = px.min(0); x1, y1 = px.max(0); hpx = y1 - y0; rx, ry = (x1 - x0) * a.rand, hpx * a.rand
                if x0 - rx < 0 or y0 - ry < 0 or x1 + rx >= k["W"] or y1 + ry >= k["H"]: continue
                loc, _, _ = ray.intersects_location(k["C"][None], (-v / dist)[None], multiple_hits=False)
                if len(loc) and np.linalg.norm(loc[0] - k["C"]) < dist - 1.5: continue                   # verdeckt (Nachbar, Baum aus LoD2, eigenes Bauteil)
                kand.append((hpx * cosw, nr, (int(x0 - rx), int(y0 - ry), int(x1 + rx), int(y1 + ry)), hpx, cosw))
            kand.sort(key=lambda k_: -k_[0]); urteil = None
            for best in kand[:a.max_versuche]:
                g, nr, (x0, y0, x1, y1), hpx, cosw = best; im = cv2.imread(kams[nr]["pf"]); cut = im[y0:y1, x0:x1]
                if not a.pruefen: break
                urteil = pruefer(cut, e["klasse"])
                print(f"    {fid}/{i} Foto {nr}: {urteil['bester']} ({urteil['scores'][urteil['bester']]:.2f})", flush=True)
                if urteil["ok"]: break
            else: best = None
            if best is None: print(f"  {e['klasse']} {fid}/{i}: kein Foto zeigt es frei/erkennbar"); continue
            p = os.path.join(a.aus, f"{e['klasse']}_{fid}_{i}.png"); cv2.imwrite(p, cut)
            erg.append(dict(datei=p, klasse=e["klasse"], fassade=fid, index=i, foto=nr, box_px=[x0, y0, x1, y1], hoehe_px=round(float(hpx)), cos=round(cosw, 2),
                            u=[e["u0"], e["u1"]], z=[e["z0"], e["z1"]], pruefung=urteil, hoehe_m=round(e["z1"] - e["z0"], 2), breite_m=round(e["u1"] - e["u0"], 2)))
            print(f"  {e['klasse']} {fid}/{i}: Foto {nr}, {hpx:.0f} px hoch, cos {cosw:.2f} -> {os.path.basename(p)}", flush=True)
    json.dump(dict(objekt=a.objekt, elemente=a.elemente, ausschnitte=erg), open(os.path.join(a.aus, "ausschnitte.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
