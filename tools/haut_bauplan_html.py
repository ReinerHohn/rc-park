#!/usr/bin/env python3
"""haut_bauplan_html.py — interaktiver Bauplan (HTML) mit SUCHFELD.

Erzeugt EINE HTML-Datei: Hillshade-Karte + alle Teil-Nummern an ihrer Stelle +
Suchfeld (Nummer eintippen -> Teil leuchtet rot auf). Selbst-enthaltend (Bild als
base64 eingebettet), funktioniert offline im Browser.

  python3 tools/haut_bauplan_html.py --dir modelle/hirschsprung_haut
"""
import argparse, os, re, io, base64, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from scipy.ndimage import gaussian_filter

DEM = "daten/hoellental/dgm025_full.npy"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="modelle/hirschsprung_haut")
    ap.add_argument("--dem", default=DEM)
    ap.add_argument("--mm", type=float, default=1.5625); ap.add_argument("--nscale", type=float, default=6.25)
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--vscale", type=float, default=0.85)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or os.path.join(a.dir, "bauplan_interaktiv.html")

    pos = {}
    for ln in open(os.path.join(a.dir, "MANIFEST.txt"), errors="ignore"):
        m = re.search(r"Nr\s+(\d+).*@ Szene \((-?\d+),(-?\d+)\)", ln)
        if m: pos[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))

    win = np.load(a.dem)[a.r0:a.r1, a.c0:a.c1].astype(float)
    win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    Z = gaussian_filter(win[::-1] - win.min(), 0.6) * a.nscale * a.vscale
    cell = a.mm; NY, NX = Z.shape; W, D = NX*cell, NY*cell

    # Hillshade als PNG (base64), ohne Achsen/Rand
    fig = plt.figure(figsize=(10, 10*D/W)); ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ls = LightSource(azdeg=315, altdeg=45)
    ax.imshow(ls.hillshade(Z, vert_exag=1, dx=cell, dy=cell), cmap="gray", origin="lower")
    ax.imshow(Z, cmap="terrain", alpha=0.45, origin="lower")
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120); plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode()

    # Labels als %-Position (HTML: top von oben -> Nord oben => top=100-cy%)
    dots = "".join(
        f'<div class="pt" id="p{n}" data-n="{n}" style="left:{cx/W*100:.2f}%;top:{(1-cy/D)*100:.2f}%">{n}</div>'
        for n, (cx, cy) in pos.items())

    html = f"""<!doctype html><html lang=de><meta charset=utf-8>
<title>Haut-Bauplan ({len(pos)} Teile)</title>
<style>
 body{{font-family:sans-serif;margin:0;background:#222;color:#eee}}
 #bar{{position:sticky;top:0;background:#111;padding:10px;z-index:10;box-shadow:0 2px 8px #000}}
 #bar input{{font-size:20px;padding:6px 10px;width:120px}} #bar button{{font-size:18px;padding:6px 14px}}
 #info{{margin-left:14px;font-size:17px}}
 #map{{position:relative;width:96vw;max-width:1100px;margin:12px auto}}
 #map img{{width:100%;display:block;border:1px solid #444}}
 .pt{{position:absolute;transform:translate(-50%,-50%);font-size:9px;font-weight:bold;color:#000;
      background:rgba(255,255,255,.65);border-radius:50%;width:15px;height:15px;line-height:15px;text-align:center;cursor:pointer}}
 .pt.hit{{background:red;color:#fff;width:30px;height:30px;line-height:30px;font-size:15px;
          border:3px solid yellow;z-index:5;box-shadow:0 0 12px red}}
 .legend{{text-align:center;color:#aaa;font-size:14px;margin:6px}}
</style>
<div id=bar>
 🔎 Teil-Nr: <input id=q type=number min=1 placeholder="z.B. 60" autofocus>
 <button onclick=find()>finden</button>
 <button onclick=clr()>alle zeigen</button>
 <span id=info></span>
</div>
<div class=legend>Nord oben · Ost rechts · Klick auf eine Nummer markiert sie · Nummer = Gravur unten am Teil</div>
<div id=map><img src="data:image/png;base64,{b64}">{dots}</div>
<script>
const POS={{{','.join(f'"{n}":[{cx:.0f},{cy:.0f}]' for n,(cx,cy) in pos.items())}}};
function clr(){{document.querySelectorAll('.pt.hit').forEach(e=>e.classList.remove('hit'));document.getElementById('info').textContent=''}}
function mark(n){{const el=document.getElementById('p'+n);if(!el){{document.getElementById('info').textContent='Teil '+n+' gibt es nicht';return}}
 el.classList.add('hit');el.scrollIntoView({{block:'center',behavior:'smooth'}});
 document.getElementById('info').textContent='Teil '+n+' @ Szene ('+POS[n][0]+','+POS[n][1]+') mm';}}
function find(){{clr();const v=document.getElementById('q').value.trim();if(v)mark(parseInt(v))}}
document.getElementById('q').addEventListener('keydown',e=>{{if(e.key==='Enter')find()}});
document.querySelectorAll('.pt').forEach(e=>e.onclick=()=>{{clr();mark(e.dataset.n)}});
</script></html>"""
    open(out, "w").write(html)
    print(f"interaktiver Bauplan -> {os.path.abspath(out)}  ({len(pos)} Teile, Suchfeld)")


if __name__ == "__main__":
    main()
