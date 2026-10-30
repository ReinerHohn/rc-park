#!/usr/bin/env python3
"""proportion_check.py — AUTOMATISCHER Proportions-Abgleich Modell↔Foto, MIT BELEG-BILD.

Lehre aus dem Fehlschlag: ein Messwerkzeug, das nur Zahlen ausgibt, ist nicht vertrauenswürdig —
es kann das Falsche messen (hier: die NACHBARHÄUSER statt der Kaufhaus-Erker) und man glaubt der
„✓". Darum: (1) gezielt das ROTE Kaufhaus segmentieren (Nachbarn raus), (2) immer ein BELEG-BILD
mit eingezeichneten Messlinien speichern → man SIEHT, was gemessen wurde.

Aufruf:  /tmp/rv/bin/python tools/proportion_check.py <foto.jpg> <modell_front.png> [beleg.png]
"""
import sys, numpy as np
from PIL import Image, ImageDraw


def _analyze(im, mode):
    h, w, _ = im.shape
    r, g, b = im[:, :, 0], im[:, :, 1], im[:, :, 2]
    red = (r > g+15) & (r > b+8) & (r > 70)
    green = (g > r+4) & (g > b+4)
    br = im.mean(2); sat = im.max(2) - im.min(2)
    sky = (br > 180) & (sat < 16) if mode == "model" else (br > 148) & (sat < 28)

    # Kaufhaus = größte zusammenhängende Spaltengruppe mit viel ROT (schließt Nachbarn aus)
    rc = red.sum(0); thr = max(8, rc.max()*0.35); cmax = int(np.argmax(rc))
    xl = cmax
    while xl > 0 and rc[xl-1] > thr:
        xl -= 1
    xr = cmax
    while xr < w-1 and rc[xr+1] > thr:
        xr += 1
    bw = max(1, xr-xl)

    def top(x0, x1):
        band = ~sky[:, max(0, x0):min(w, x1)]
        rows = np.where(band.any(1))[0]
        return int(rows.min()) if len(rows) else None

    cL, cR = xl+int(bw*0.42), xl+int(bw*0.58)
    oL = (xl+int(bw*0.02), xl+int(bw*0.13)); oR = (xr-int(bw*0.13), xr-int(bw*0.02))
    ridge = top(cL, cR); spL = top(*oL); spR = top(*oR)
    grows = np.where(green[:, cL:cR].any(1))[0]; grows = grows[grows < int(h*0.74)]
    eave = int(grows.max()) if len(grows) else ridge
    rrows = np.where(red[:, xl+int(bw*0.3):xl+int(bw*0.7)].any(1))[0]
    base = int(rrows.max()) if len(rrows) else h-1
    fac = max(1, base-eave)
    sub = im[:, xl+int(bw*0.1):xr-int(bw*0.1)]; sg = sub.mean(2); yy = np.arange(h)[:, None]
    dark = (sg < 95) & (yy > eave+0.1*fac) & (yy < base)
    heights = [base-np.where(dark[:, c])[0].min() for c in range(sg.shape[1]) if dark[:, c].any()]
    # WAAGRECHTE dunkle Zonen unter der Traufe (markant+sicher): Fensterband (oben), ... , Arkade (unten).
    rowdark = dark.mean(1)
    thrd = max(0.12, float(rowdark[eave:base].max())*0.4) if base > eave else 0.12
    on = rowdark > thrd; runs = []; i = eave
    while i < base:
        if on[i]:
            j = i
            while j < base and on[j]:
                j += 1
            runs.append((i, j)); i = j
        else:
            i += 1
    runs = [rn for rn in runs if rn[1]-rn[0] > fac*0.03]
    wtop = wbot = None
    if runs:
        wtop, wbot = runs[0]                                  # erstes dunkles Band unter der Traufe = Fenster
    return dict(xl=xl, xr=xr, oL=oL, oR=oR, ridge=ridge, eave=eave, base=base, spL=spL, spR=spR,
                wtop=wtop, wbot=wbot,
                roof=(eave-ridge)/fac, spireL=(eave-spL)/fac, spireR=(eave-spR)/fac,
                fenster_h=((wbot-wtop)/fac) if wtop is not None else None,       # Fensterhöhe / Fassade — fängt gedrungene Fenster
                arcade=(max(heights)/fac) if heights else None,
                spire_over_ridge=(min(spL, spR) < ridge))


def _draw(path, A, title):
    im = Image.open(path).convert("RGB"); d = ImageDraw.Draw(im); w = im.width
    for y, c, t in [(A["ridge"], (255, 0, 0), "First"), (A["eave"], (0, 120, 255), "Traufe"),
                    (A.get("wtop"), (200, 0, 200), "Fenster-Sturz"), (A.get("wbot"), (200, 0, 200), "Sohlbank"),
                    (A["base"], (0, 200, 0), "Sockel")]:
        if y is not None:
            d.line([(A["xl"], y), (A["xr"], y)], fill=c, width=4); d.text((A["xl"]+6, y+3), t, fill=c)
    for (ox, sp, lbl) in [(A["oL"], A["spL"], "ErkerL"), (A["oR"], A["spR"], "ErkerR")]:
        xmid = (ox[0]+ox[1])//2
        d.rectangle([ox[0], 0, ox[1], im.height], outline=(255, 150, 0), width=3)
        if sp is not None:
            d.line([(xmid-30, sp), (xmid+30, sp)], fill=(255, 150, 0), width=5)
    d.text((A["xl"]+6, 6), title, fill=(0, 0, 0))
    return im


def main():
    photo, model = sys.argv[1], sys.argv[2]
    beleg = sys.argv[3] if len(sys.argv) > 3 else "/tmp/proportion_beleg.png"
    imP = np.asarray(Image.open(photo).convert("RGB")).astype(int)
    imM = np.asarray(Image.open(model).convert("RGB")).astype(int)
    P, M = _analyze(imP, "photo"), _analyze(imM, "model")
    print(f"{'Metrik (Höhe/Fassade)':<22}{'FOTO':>9}{'MODELL':>9}{'Δ':>9}")
    for k in ("roof", "fenster_h", "arcade", "spireL", "spireR"):
        pv, mv = P.get(k), M.get(k)
        if pv is None or mv is None:
            print(f"{k:<22}{str(pv):>9}{str(mv):>9}")
        else:
            print(f"{k:<22}{pv:>9.2f}{mv:>9.2f}{mv-pv:>+9.2f}")
    print(f"\nErkerspitze ÜBER First?  Foto={P['spire_over_ridge']}  Modell={M['spire_over_ridge']}")
    fl = []
    if P.get("fenster_h") and M.get("fenster_h") and abs(M["fenster_h"]-P["fenster_h"]) > 0.08:
        fl.append(f"Fensterhöhe/Fassade {M['fenster_h']:.2f} vs {P['fenster_h']:.2f} — Fenster {'zu gedrungen' if M['fenster_h']<P['fenster_h'] else 'zu hoch'} (WIN_ASPECT angleichen).")
    if M["spire_over_ridge"] != P["spire_over_ridge"]:
        fl.append(f"Erkerspitze/First: Foto={P['spire_over_ridge']} aber Modell={M['spire_over_ridge']} — angleichen.")
    if abs(M["roof"]-P["roof"]) > 0.08:
        fl.append(f"Dach/Fassade {M['roof']:.2f} vs {P['roof']:.2f} — Dach {'zu hoch' if M['roof']>P['roof'] else 'zu niedrig'}.")
    for k in ("spireL", "spireR"):
        if abs(M[k]-P[k]) > 0.1:
            fl.append(f"{k} {M[k]:.2f} vs {P[k]:.2f} — Erker {'zu hoch' if M[k]>P[k] else 'zu niedrig'}.")
    print("\n".join("⚠ "+f for f in fl) if fl else "✓ Proportionen im Rahmen.")
    # BELEG-BILD: Messlinien eingezeichnet, Foto neben Modell
    a, c = _draw(photo, P, "FOTO"), _draw(model, M, "MODELL")
    H = 700; a = a.resize((int(a.width*H/a.height), H)); c = c.resize((int(c.width*H/c.height), H))
    out = Image.new("RGB", (a.width+c.width+12, H), (255, 255, 255)); out.paste(a, (0, 0)); out.paste(c, (a.width+12, 0))
    out.save(beleg); print(f"-> Beleg mit Messlinien: {beleg}")


if __name__ == "__main__":
    main()
