#!/usr/bin/env python3
"""massstab_quelle_normobjekte.py - Massstabsquelle "Normobjekte in Fotos": Personen als Laengennormal (ANNAHME Erwachsene Median 1,70 m).

Je kalibriertem Foto (SFM-AUSRICHTUNG-<seite>.json["kameras"]: R, t, f_px_original, fak, off, cx, cy, k im Modellsystem in Metern) werden Personen
mit einem Objektdetektor (transformers YOLOS/DETR, NUR CPU) gesucht. Je Detektion: Fusspunkt (Mitte Unterkante der Box) -> Strahl -> Schnitt mit der
Bodenebene z = ZBODEN (Modellrahmen, Meter) -> senkrechte Gerade ueber dem Fusspunkt; Kopfstrahl (Mitte Oberkante) -> naechster Punkt auf der Geraden
= Kopfhoehe h_modell. Faktor s = 1,70 / h_modell  (s = wahre Meter / Modellmeter; 1.0 = Modell konsistent). Ergebnis Median + MAD ueber alle Detektionen.

ABHAENGIGKEIT (ehrlich): die Kameraposen stammen aus der Ausrichtung auf Bodenanker. Die Quelle prueft die LOKALE Metrik nahe Bodenniveau
(Person 1,7 m gegen Kamerahoehe/Entfernung im Modell), NICHT die Turmhoehe. Unabhaengig ist sie von den Hoehenpunkten (DOM1, Dokument), den LoD2-Traufen
und der Wolkenform; abhaengig von Posen/Maßstab aus den Bodenankern und von der Annahme ZBODEN = 0 (Strassenniveau = Gelaende DGM1).
Verzerrungen: Box-Oberkante liegt ueber dem Kopf/Hut (s zu klein), verdeckte Fuesse (Box endet am Knie -> Entfernung zu gross -> h zu gross -> s zu klein),
Kinder/Sitzende (Filter nur ueber Seitenverhaeltnis), Hang/Stufen (Boden nicht z=0). Median/MAD filtern Ausreisser, nicht diese gleichgerichteten Fehler.

  CUDA_VISIBLE_DEVICES= /media/oem/scan/venv-seg/bin/python -W ignore tools/massstab_quelle_normobjekte.py modelle/martinstor_null/objekt.json [--seite nord]
      [--modell hustvl/yolos-small] [--score 0.7] [--zboden 0] [--hoehe 1.70] [--fotos 001,005] [--bilder 3]
Ausgabe: <objekt>/audit/massstab_normobjekte.json (+ Blickprobe audit/massstab_normobjekte_blick.jpg) und Kurztabelle auf stdout.
"""
import os, sys, json, glob, argparse, time
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")          # KEINE GPU (ein GPU-Job zur Zeit)
import numpy as np, cv2

class Kam:
    def __init__(self, nr, d):
        self.nr = nr; self.R = np.array(d["R"]); self.t = np.array(d["t"]); self.fak = float(d.get("fak", 1.0)); self.off = np.array(d.get("off", (0.0, 0.0)), float)
        self.f = float(d["f_px_original"]) * self.fak; self.cx, self.cy = float(d["cx"]), float(d["cy"]); self.k = list(d.get("k", []))
        self.c = -self.R.T @ self.t
    def bild(self, uv): return (np.asarray(uv, float) - self.off) * self.fak           # Original-Pixel -> SfM-Bildpixel
    def strahl(self, uv_orig):
        """Original-Pixel -> (Zentrum, Richtung im Modellsystem), Radialverzeichnung iterativ entzerrt."""
        u, v = self.bild(uv_orig); xd, yd = (u - self.cx) / self.f, (v - self.cy) / self.f; x, y = xd, yd
        for _ in range(8):
            r2 = x * x + y * y; d = 1.0 + sum(kk * r2 ** (i + 1) for i, kk in enumerate(self.k)); x, y = xd / d, yd / d
        dr = self.R.T @ np.array([x, y, 1.0]); return self.c, dr / np.linalg.norm(dr)

def hoehe_aus_box(K, box, zboden):
    """box = (x0, y0, x1, y1) in Original-Pixeln. -> dict(h, dist, fuss) oder None."""
    x0, y0, x1, y1 = box; xm = 0.5 * (x0 + x1)
    c, d = K.strahl((xm, y1))
    if d[2] > -0.01: return None                                   # Fusspunkt-Strahl geht nicht nach unten
    lam = (zboden - c[2]) / d[2]; G = c + lam * d; dist = float(np.hypot(*(G[:2] - c[:2])))
    c2, d2 = K.strahl((xm, y0))                                    # Kopfstrahl; naechster Punkt auf der Senkrechten (G + z*e_z)
    # Minimiere |c2 + mu*d2 - (G + h*ez)|: lineares Problem in (mu, h)
    A = np.array([[d2[0], 0.0], [d2[1], 0.0], [d2[2], -1.0]]); b = np.array([G[0] - c2[0], G[1] - c2[1], G[2] - c2[2]])
    (mu, h), *_ = np.linalg.lstsq(A, b, rcond=None)
    if mu <= 0: return None
    return dict(h=float(h), dist=dist, fuss=G.round(2).tolist())

def nms(dets, thr=0.5):
    dets = sorted(dets, key=lambda d: -d["score"]); out = []
    for d in dets:
        ok = True
        for e in out:
            ix = max(0, min(d["box"][2], e["box"][2]) - max(d["box"][0], e["box"][0])); iy = max(0, min(d["box"][3], e["box"][3]) - max(d["box"][1], e["box"][1]))
            ua = (d["box"][2] - d["box"][0]) * (d["box"][3] - d["box"][1]) + (e["box"][2] - e["box"][0]) * (e["box"][3] - e["box"][1]) - ix * iy
            if ua > 0 and ix * iy / ua > thr: ok = False; break
        if ok: out.append(d)
    return out

def erkennen(pipe, img, score):
    """Ganzes Bild + 2x2-Kacheln (25 % Ueberlappung) -> Personenboxen in Bildpixeln (kleine Personen werden sonst uebersehen)."""
    from PIL import Image
    H, W = img.shape[:2]; rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB); dets = []
    fenster = [(0, 0, W, H)] + [(int(i * W * 0.4), int(j * H * 0.4), int(i * W * 0.4 + W * 0.6), int(j * H * 0.4 + H * 0.6)) for i in (0, 1) for j in (0, 1)]
    for (a, b, c, d) in fenster:
        for r in pipe(Image.fromarray(rgb[b:d, a:c]), threshold=score):
            if r["label"] != "person": continue
            bx = r["box"]; dets.append(dict(score=float(r["score"]), box=[bx["xmin"] + a, bx["ymin"] + b, bx["xmax"] + a, bx["ymax"] + b]))
    return nms(dets)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--seite", default="nord"); ap.add_argument("--modell", default="hustvl/yolos-small")
    ap.add_argument("--score", type=float, default=0.7); ap.add_argument("--zboden", type=float, default=0.0); ap.add_argument("--hoehe", type=float, default=1.70)
    ap.add_argument("--sd-person", type=float, default=0.10); ap.add_argument("--fotos"); ap.add_argument("--bilder", type=int, default=3); ap.add_argument("--min-box-px", type=float, default=60.0)
    ap.add_argument("--suffix", default="", help="Dateiname-Zusatz fuer Sensitivitaetslaeufe"); ap.add_argument("--dist", nargs=2, type=float, default=[4.0, 70.0]); ap.add_argument("--aspekt", nargs=2, type=float, default=[1.8, 4.6])
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    obj = json.load(open(a.objekt)); AU = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{a.seite}.json")))
    kams = {nr: Kam(nr, d) for nr, d in AU["kameras"].items()}
    if a.fotos: kams = {nr: k for nr, k in kams.items() if nr in a.fotos.split(",")}
    root = os.path.realpath(os.path.join(repo, obj["fotos_dir"])) if not os.path.isabs(obj["fotos_dir"]) else obj["fotos_dir"]
    import torch; from transformers import pipeline; torch.set_num_threads(max(1, (os.cpu_count() or 8) // 2))
    pipe = pipeline("object-detection", model=a.modell, device=-1)
    schaetz, verworfen, zeigen = [], {}, []
    def verw(grund): verworfen[grund] = verworfen.get(grund, 0) + 1
    t0 = time.time()
    for nr, K in sorted(kams.items()):
        fs = glob.glob(os.path.join(root, nr + "_*")) + glob.glob(os.path.join(root, nr + ".*"))
        if not fs: verw("kein Originalfoto"); continue
        img = cv2.imread(fs[0]); H, W = img.shape[:2]
        if abs(W * K.fak - 2 * K.cx) > 4: verw("Bildgroesse passt nicht zur Kamera (Ausschnitt/Drehung)"); continue
        D = erkennen(pipe, img, a.score); n0 = len(schaetz)
        for k, d in enumerate(D):
            x0, y0, x1, y1 = d["box"]; bh, bw = y1 - y0, x1 - x0
            if x0 < 3 or y0 < 3 or x1 > W - 3 or y1 > H - 3: verw("Box beruehrt Bildrand"); continue
            if bh < a.min_box_px: verw(f"Box < {a.min_box_px:.0f} px hoch"); continue
            if not (a.aspekt[0] <= bh / max(bw, 1) <= a.aspekt[1]): verw("Seitenverhaeltnis nicht stehend"); continue
            r = hoehe_aus_box(K, d["box"], a.zboden)
            if r is None: verw("Strahl ohne Bodenschnitt"); continue
            if not (a.dist[0] <= r["dist"] <= a.dist[1]): verw("Entfernung ausserhalb"); continue
            if not (0.8 <= r["h"] <= 3.0): verw("Kopfhoehe unplausibel (0,8..3,0 m)"); continue
            s = a.hoehe / r["h"]; e = dict(id=f"{nr}-{k}", foto=nr, wert_s=round(float(s), 4), sigma=round(float(s * a.sd_person / a.hoehe), 4),
                                         beleg=f"Person Box {int(x0)},{int(y0)}-{int(x1)},{int(y1)} score {d['score']:.2f}; h_modell {r['h']:.2f} m bei {r['dist']:.1f} m Entfernung, Fusspunkt {r['fuss']}", h_modell=round(r["h"], 3), entfernung=round(r["dist"], 1), box=[round(float(v), 1) for v in d["box"]])
            schaetz.append(e)
        print(f"  {nr}: {len(D)} Personen erkannt, {len(schaetz) - n0} verwertbar  ({time.time() - t0:.0f} s)", flush=True)
    n = len(schaetz); S = np.array([e["wert_s"] for e in schaetz])
    out = dict(quelle="Normobjekte: Personen (Detektor %s, CPU)" % a.modell, richtung="vertikal_boden",
               unabhaengig_von=["DOM1/DGM1-Hoehenpunkte", "LoD2-Traufen", "Dokumenthoehen", "Wolkenform/Bandwahl", "Gedenktafel"],
               abhaengig_von=["Kameraposen und Modellmassstab aus den Bodenankern (SFM-AUSRICHTUNG)", "ANNAHME Bodenebene z=%.2f" % a.zboden],
               s_definition="wahre Meter / Modellmeter, 1.0 = konsistent", schaetzungen=schaetz, n=n,
               annahmen=[f"ANNAHME: erwachsene Person im Bild ist im Median {a.hoehe:.2f} m gross (Mischbevoelkerung, SD {a.sd_person:.2f} m = {100 * a.sd_person / a.hoehe:.0f} % je Person)",
                         f"ANNAHME: Bodenebene unter den Personen liegt bei z = {a.zboden:.2f} m im Modellrahmen (Strassenniveau)",
                         "ANNAHME: Box-Oberkante = Scheitel (Hut/Haare/Rucksack machen Personen scheinbar groesser -> s zu klein)",
                         f"Filter: Box ganz im Bild, >= {a.min_box_px:.0f} px hoch, Seitenverhaeltnis {a.aspekt[0]}..{a.aspekt[1]}, Entfernung {a.dist[0]}..{a.dist[1]} m, h_modell 0,8..3,0 m"],
               blind=["Turmhoehe/Vertikalmassstab in 30-65 m (nur Boden bis ~2 m)", "Querverzerrung der Wolke", "gleichgerichtete Fehler: verdeckte Fuesse, Huete, Kinder, Hang"],
               verworfen=verworfen, modell=a.modell, datum=time.strftime("%Y-%m-%d %H:%M"))
    if n:
        md = float(np.median(S)); mad = float(np.median(np.abs(S - md))); out.update(median=round(md, 4), mad=round(mad, 4), mad_normal=round(1.4826 * mad, 4), standardfehler_median=round(1.253 * 1.4826 * mad / np.sqrt(n), 4))
        fotos = {}
        for e in schaetz: fotos.setdefault(e["foto"], []).append(e["wert_s"])
        out["je_foto"] = {f: dict(n=len(v), median=round(float(np.median(v)), 3)) for f, v in sorted(fotos.items())}
        if n < 8: out["warnung"] = f"nur {n} Detektionen (< 8): Ergebnis nicht belastbar"
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(out, open(os.path.join(od, "audit", f"massstab_normobjekte{a.suffix}.json"), "w"), indent=1, ensure_ascii=False)
    print(f"\n{n} verwertbare Detektionen; verworfen: {verworfen}")
    if n:
        print(f"s = wahre/Modell-m: Median {out['median']:.3f}  MAD {out['mad']:.3f} (robuste SD {out['mad_normal']:.3f}; Standardfehler des Medians ~{out['standardfehler_median']:.3f} wenn unabhaengig)  | je Foto: {out['je_foto']}")
        if n < 8: print("WARNUNG:", out["warnung"])
        # Blickprobe: die a.bilder Detektionen mit s naechst am Median, aus verschiedenen Fotos
        wahl, benutzt = [], set()
        for e in sorted(schaetz, key=lambda e: abs(e["wert_s"] - out["median"])):
            if e["foto"] in benutzt: continue
            wahl.append(e); benutzt.add(e["foto"])
            if len(wahl) >= a.bilder: break
        tiles = []
        for e in wahl:
            fs = glob.glob(os.path.join(root, e["foto"] + "_*")) + glob.glob(os.path.join(root, e["foto"] + ".*")); im = cv2.imread(fs[0]); x0, y0, x1, y1 = [int(v) for v in e["box"]]
            cv2.rectangle(im, (x0, y0), (x1, y1), (0, 255, 0), max(2, im.shape[1] // 500))
            m = int(0.6 * (y1 - y0)); cx0, cx1 = max(0, x0 - m), min(im.shape[1], x1 + m); cy0, cy1 = max(0, y0 - m // 2), min(im.shape[0], y1 + m // 2)
            t = im[cy0:cy1, cx0:cx1]; sc = 520.0 / t.shape[0]; t = cv2.resize(t, None, fx=sc, fy=sc)
            cv2.putText(t, f"{e['foto']} s={e['wert_s']:.2f} h={e['h_modell']:.2f}m d={e['entfernung']:.0f}m", (4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2); tiles.append(t)
        if tiles:
            hh = 520; tiles = [cv2.copyMakeBorder(t, 0, hh - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) if t.shape[0] < hh else t for t in tiles]
            cv2.imwrite(os.path.join(od, "audit", f"massstab_normobjekte_blick{a.suffix}.jpg"), np.hstack(tiles)); print("Blickprobe: audit/massstab_normobjekte_blick.jpg")
    print("geschrieben: audit/massstab_normobjekte.json")

if __name__ == "__main__":
    main()
