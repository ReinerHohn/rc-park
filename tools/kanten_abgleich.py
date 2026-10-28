#!/usr/bin/env python3
"""kanten_abgleich.py — ZENTRALE automatische Kanten-Gate: Struktur-Kanten Foto↔Modell je Region.

Prinzip (gehärtet): die markanten Kanten eines Bauwerks sind die GRENZEN zwischen Farbzonen
(Wand↔Gold-Zier↔dunkle Öffnung↔Dach), NICHT die Grautonkanten (die ersaufen in Textur wie Waben/
Schuppen). Also: beide Bilder in Zonen klassifizieren → Zonengrenzen = Strukturkanten → je Region
fein ausrichten (Shift-Suche) → Recall/Precision + Overlay. Wo ROT ohne Gelb: Kante im Foto, die dem
Modell FEHLT. Läuft über die GANZE Fassade (Regionen-Sweep) → nichts rutscht durch.

Lauf:
  Sweep:   python3 tools/kanten_abgleich.py --sweep <foto.jpg> <modell_render.png> [out_dir]
  Einzeln: python3 tools/kanten_abgleich.py <foto_crop.png> <modell_crop.png> [out.png]
"""
import sys, os
import numpy as np
from PIL import Image
from scipy import ndimage


def classify(a):
    """Pixel → Zone: 0 bg/Himmel, 1 Wand(rot), 2 Zier(gold), 3 Öffnung(dunkel), 4 Dach(grün)."""
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    lab = np.zeros(a.shape[:2], np.uint8)
    dark = (r < 95) & (g < 100) & (b < 115)
    green = (g >= r-5) & (g > b+6) & (g > 55)
    gold = (r > 120) & (g > 100) & (r > b+25) & (g > b+12) & ~green
    red = (r > g+14) & (r > b+8) & (r > 60)
    bg = (r > 200) & (g > 200) & (b > 200)
    lab[red] = 1; lab[green] = 4; lab[gold] = 2; lab[dark] = 3; lab[bg] = 0
    return lab


def struct_edges(lab):
    """Zonengrenzen = Strukturkanten (Label wechselt zum Nachbarn)."""
    e = np.zeros_like(lab, bool)
    e[:-1] |= lab[:-1] != lab[1:]
    e[:, :-1] |= lab[:, :-1] != lab[:, 1:]
    e &= (lab != 0)                                  # Grenzen am Himmel/bg ignorieren
    return e


def best_shift(ref, mov, frac=0.08):
    """kleine Translationssuche: Shift von mov, der die Kanten-Überdeckung mit ref maximiert."""
    H, W = ref.shape; sy = int(H*frac); sx = int(W*frac); best = (0, 0, -1)
    rd = ndimage.distance_transform_edt(~ref)
    for dy in range(-sy, sy+1, max(1, sy//6)):
        for dx in range(-sx, sx+1, max(1, sx//6)):
            m = np.roll(np.roll(mov, dy, 0), dx, 1)
            score = float((m & (rd <= 3)).sum()) / max(1, m.sum())
            if score > best[2]:
                best = (dy, dx, score)
    return best[0], best[1]


def compare(pc, mc, size=(300, 400), tol=4):
    pe = struct_edges(classify(np.asarray(pc.convert("RGB").resize(size))))
    me = struct_edges(classify(np.asarray(mc.convert("RGB").resize(size))))
    dy, dx = best_shift(pe, me)
    me = np.roll(np.roll(me, dy, 0), dx, 1)
    pd = ndimage.distance_transform_edt(~pe); md = ndimage.distance_transform_edt(~me)
    recall = float((pe & (md <= tol)).sum())/max(1, pe.sum())
    prec = float((me & (pd <= tol)).sum())/max(1, me.sum())
    H, W = size[1], size[0]; ov = (np.asarray(pc.convert("L").resize(size))[:, :, None]//3).repeat(3, 2).astype(np.uint8)
    ov[pe] = [255, 40, 40]; ov[me] = [40, 220, 40]; ov[pe & (md <= tol)] = [240, 240, 40]
    return recall, prec, Image.fromarray(ov), (pe & (md > tol))


def tight_building(img, is_model):
    a = np.asarray(img.convert("RGB"))
    if is_model:
        g = a.sum(2); ys, xs = np.where(g < 720)              # nicht-weiß
    else:
        lab = classify(a); ys, xs = np.where(ndimage.binary_opening(lab == 4, iterations=2))  # grünes Dach
        if len(xs) < 20:
            ys, xs = np.where(lab != 0)
    if len(xs) < 20:
        return img
    x0, x1 = xs.min(), xs.max()
    # nach unten bis zur untersten roten Zeile (Fassade) erweitern
    lab = classify(a); red = lab == 1
    rr = np.where(red[:, x0:x1].mean(1) > 0.15)[0]
    y0 = ys.min(); y1 = rr.max() if len(rr) else ys.max()
    return img.crop((x0, y0, x1, y1))


def detect_bands(img):
    """markante waagrechte GRENZEN je Bild selbst finden (FEATURE-verankert, nicht feste Bruchteile):
    Traufe (grünes Dach unten), Fenster-Sturz/Sohlbank (1. dunkle Zone), Arkaden-Scheitel (unterste
    dunkle Zone), Boden. Gibt y-Bruchteile 0..1 der Gebäudehöhe zurück → Regionen passen trotz
    anderer Proportionen."""
    a = np.asarray(img.convert("RGB")); H, W = a.shape[:2]
    lab = classify(a)
    xc0, xc1 = int(W*0.25), int(W*0.75)
    green = (lab[:, xc0:xc1] == 4).mean(1); dark = (lab[:, xc0:xc1] == 3).mean(1)
    anyb = (lab[:, xc0:xc1] != 0).mean(1)
    rows = np.where(anyb > 0.15)[0]
    if len(rows) < 10:
        return None
    top, ground = rows.min(), rows.max(); Hs = max(1, ground-top)
    grows = np.where(green > 0.2)[0]
    eave = grows.max() if len(grows) else top+int(Hs*0.35)
    dark = ndimage.uniform_filter1d(dark, 5)
    on = dark > max(0.12, dark[eave:ground].max()*0.4) if ground > eave else dark > 0.12
    runs = []; i = eave
    while i < ground:
        if on[i]:
            j = i
            while j < ground and on[j]:
                j += 1
            if j-i > Hs*0.02:
                runs.append((i, j))
            i = j
        else:
            i += 1
    win = runs[0] if runs else (eave, eave)
    arc = runs[-1] if len(runs) >= 2 else (ground-int(Hs*0.2), ground)
    def f(y): return (y-top)/Hs
    return {"top": 0.0, "eave": f(eave), "win_top": f(win[0]), "win_bot": f(win[1]),
            "arc_top": f(arc[0]), "ground": 1.0}


def regions_from_bands(bd):
    """benannte Regionen (x0,y0,x1,y1) aus den erkannten Bändern."""
    e, wt, wb, at = bd["eave"], bd["win_top"], bd["win_bot"], bd["arc_top"]
    pad = 0.02
    return {
        "Dach+Gauben": (0.06, 0.0, 0.94, e+pad),
        "Statuen+Baldachine": (0.12, max(0, e-pad), 0.88, wt+pad),
        "Fenster": (0.12, wt-pad, 0.88, wb+pad),
        "Balkon": (0.08, wb-pad, 0.92, at+pad),
        "Arkade": (0.04, at-pad, 0.96, 1.0),
        "Erker-links": (0.0, e*0.6, 0.17, min(1.0, at)),
        "Erker-rechts": (0.83, e*0.6, 1.0, min(1.0, at)),
    }


def main():
    if "--sweep" in sys.argv:
        i = sys.argv.index("--sweep"); foto, modell = sys.argv[i+1], sys.argv[i+2]
        outdir = sys.argv[i+3] if len(sys.argv) > i+3 else "/tmp/kanten_sweep"
        os.makedirs(outdir, exist_ok=True)
        pb = tight_building(Image.open(foto), False); mb = tight_building(Image.open(modell), True)
        PW, PH = pb.size; MW, MH = mb.size
        pbd = detect_bands(pb); mbd = detect_bands(mb)                 # Bänder je Bild SELBST erkennen
        preg = regions_from_bands(pbd); mreg = regions_from_bands(mbd)
        print(f"{'Region':<22}{'Recall':>8}{'Prec':>7}  Urteil")
        rows = []
        for name in preg:
            x0, y0, x1, y1 = preg[name]; mx0, my0, mx1, my1 = mreg[name]
            pc = pb.crop((int(PW*x0), int(PH*y0), int(PW*x1), int(PH*y1)))
            mc = mb.crop((int(MW*mx0), int(MH*my0), int(MW*mx1), int(MH*my1)))
            rec, pre, ov, _ = compare(pc, mc)
            v = "PASS" if rec >= 0.6 else ("ok" if rec >= 0.45 else "WARN fehlende Kanten")
            ov.save(f"{outdir}/{name}.png")
            print(f"{name:<22}{rec:>8.2f}{pre:>7.2f}  {v}")
            rows.append((name, rec))
        worst = min(rows, key=lambda r: r[1])
        print(f"\nOverlays: {outdir}/   schwächste Region: {worst[0]} (Recall {worst[1]:.2f})")
    else:
        fp, mp = sys.argv[1], sys.argv[2]
        out = sys.argv[3] if len(sys.argv) > 3 else "/tmp/kanten_overlay.png"
        rec, pre, ov, _ = compare(Image.open(fp), Image.open(mp)); ov.save(out)
        print(f"Recall {rec:.2f}  Precision {pre:.2f}  → {out}  ({'PASS' if rec>=0.6 else 'WARN'})")


if __name__ == "__main__":
    main()
