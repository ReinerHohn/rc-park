#!/usr/bin/env python3
"""foto_mass.py - REPRODUZIERBARE Fotomessung: zwei Bildpunkte + Massstabskette -> Meter, als Protokoll (JSON + markierter Ausschnitt).

Bisher standen Fotomasse als "44 px x 1,5 cm" in Kommentaren - nicht nachpruefbar. Jede Messung bekommt jetzt eine Protokollnummer, die in der
Masstabelle als Quelle steht (z. B. "M-049-003"), mit Pixelkoordinaten, Massstabsherkunft und Bild.

  foto_mass.py OBJEKT.json FOTO-NR  --mess x1 y1 x2 y2  --massstab-px x1 y1 x2 y2 --massstab-m L --massstab-von "Tafel 3,4 m (MASSPRUEFUNG Teil 5)"
  foto_mass.py OBJEKT.json FOTO-NR  --mess ... --px-pro-m 97 --massstab-von "..."          (Massstab aus frueherem Protokoll)
  [--name "Eckturm Durchmesser"] [--merkmal duennes_bauteil] [--richtung h|v|frei]
Schreibt modelle/<objekt>/messprotokoll/M-<foto>-<nr>.json + .jpg. Senkrechte Masse in Schraegaufnahmen sind gestaucht -> --richtung v mit --stauchung 0.88.
"""
import sys, os, json, glob, math, cv2, numpy as np

def main():
    a = sys.argv[1:]; obj = json.load(open(a[0])); nr = a[1]; root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0]))))
    def opt(k, n=1, d=None):
        if k not in a: return d
        i = a.index(k); return a[i + 1] if n == 1 else a[i + 1:i + 1 + n]
    mess = [float(x) for x in opt("--mess", 4)]; name = opt("--name", d="Messung"); richtung = opt("--richtung", d="frei"); st = float(opt("--stauchung", d="1.0"))
    von = opt("--massstab-von", d="?"); merkmal = opt("--merkmal", d="-")
    fn = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]; im = cv2.imread(fn); H, W = im.shape[:2]
    if opt("--px-pro-m"): ppm = float(opt("--px-pro-m")); mpx = None
    else:
        mpx = [float(x) for x in opt("--massstab-px", 4)]; L = float(opt("--massstab-m")); ppm = math.hypot(mpx[2] - mpx[0], mpx[3] - mpx[1]) / L
    dx, dy = mess[2] - mess[0], mess[3] - mess[1]
    px = abs(dx) if richtung == "h" else abs(dy) / st if richtung == "v" else math.hypot(dx, dy)
    meter = px / ppm
    d = os.path.join(root, os.path.dirname(obj["masstabelle"]), "messprotokoll"); os.makedirs(d, exist_ok=True)
    n = len(glob.glob(os.path.join(d, f"M-{nr}-*.json"))) + 1; pid = f"M-{nr}-{n:03d}"
    rec = dict(id=pid, foto=os.path.basename(fn), bild=[W, H], name=name, merkmal=merkmal, mess_px=mess, richtung=richtung, stauchung=st,
               massstab_px=mpx, px_pro_m=round(ppm, 2), massstab_von=von, pixel=round(px, 1), meter=round(meter, 3),
               unsicherheit_m=round(meter * 0.08 + 2 / ppm, 3), hinweis="+-8 % Ablesung/Perspektive + 2 px")
    json.dump(rec, open(os.path.join(d, pid + ".json"), "w"), indent=1, ensure_ascii=False)
    o = im.copy(); cv2.line(o, (int(mess[0]), int(mess[1])), (int(mess[2]), int(mess[3])), (0, 0, 255), 3)
    if mpx: cv2.line(o, (int(mpx[0]), int(mpx[1])), (int(mpx[2]), int(mpx[3])), (0, 200, 0), 3)
    xs = [mess[0], mess[2]] + ([mpx[0], mpx[2]] if mpx else []); ys = [mess[1], mess[3]] + ([mpx[1], mpx[3]] if mpx else [])
    x0, x1 = int(max(0, min(xs) - 150)), int(min(W, max(xs) + 150)); y0, y1 = int(max(0, min(ys) - 150)), int(min(H, max(ys) + 150))
    c = o[y0:y1, x0:x1]; cv2.putText(c, f"{pid}: {name} = {meter:.2f} m ({px:.0f} px, {ppm:.1f} px/m)", (8, 28), 0, 0.8, (0, 0, 255), 2)
    cv2.imwrite(os.path.join(d, pid + ".jpg"), c)
    print(f"{pid}: {name} = {meter:.2f} m +- {rec['unsicherheit_m']} m  ({px:.0f} px bei {ppm:.1f} px/m, Massstab: {von})  -> {d}/{pid}.json/.jpg")

if __name__ == "__main__":
    main()
