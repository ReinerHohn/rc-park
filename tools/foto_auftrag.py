#!/usr/bin/env python3
"""foto_auftrag.py <objekt.json> <fassaden-ordner> <aus.html> [--wunsch wuensche.json] [--mpp 0.01] [--extra-umriss x0 y0 x1 y1 ...]

FOTOAUFTRAG: zeigt dem Nutzer, WELCHE Fotos fehlen und WO er dafuer stehen soll.
Nutzer 16.11.2026: "wenn du mehr Daten willst, brauchst du ein Verfahren, wie du mir zeigen willst, welche Daten du brauchst."
Bedarf entsteht aus zwei Quellen:
  automatisch  je Wand aus <fassaden-ordner>/fassaden.json + ortho_fNN.png: zusammenhaengende Wandbereiche ohne Bilddaten (>= 8 m2);
  Wuensche     wuensche.json = [{"wand": 0, "u": [u0, u1], "z": [z0, z1], "mpp": 0.004, "titel": "...", "warum": "..."}] in Fassadenkoordinaten
               (u entlang der Wand ab fassaden.json 'o', z Hoehe) - fuer Teile, die zu grob aufgeloest sind (Figuren, Reliefs, Fugen).
Je Bedarf: alle Messkameras (K-*.json), die den Bereich sehen -> bestes vorhandenes Foto (kleinste Meter je Pixel am Ziel, Blickwinkel < 70 Grad);
  Empfehlung = gleicher Standort mit Zoom-Faktor (Ist-Aufloesung / Soll-Aufloesung) oder naeher heran; Standort als Karte (Modellrahmen -> UTM -> Breite/Laenge),
  Ausschnitt des besten Fotos mit rot markiertem Zielbereich ("so, aber schaerfer/naeher"). Bereiche ganz ohne Foto: bestes Fremdfoto als Vorbild, falls eines da ist.
Ausgabe: <aus.html> (eine Seite mit Karte und Karten je Auftrag, Bilder eingebettet) und <aus>.json. Die Seite ist zum Mitnehmen aufs Handy gedacht.
Grenzen: kennt keine Strassen/Zaeune - Standorte sind Orte, an denen schon einmal fotografiert wurde, oder eine Richtung; Verdeckung nur ueber vorhandene Fotos.
"""
import sys, os, json, glob, argparse, base64, math, numpy as np, cv2
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seiten_luecken import utm32_nach_geo


def kameras(mp, fd):
    out = []
    for p in glob.glob(os.path.join(mp, "K-*.json")):
        n = os.path.basename(p)[2:-5]; k = json.load(open(p)).get("kamera")
        if not isinstance(k, dict) or "rvec" not in k or "cx" not in k: continue
        g = glob.glob(os.path.join(fd, n + ".*"))
        if not g: continue
        R = cv2.Rodrigues(np.array(k["rvec"]))[0]; t = np.array(k["t"]); out.append(dict(name=n, R=R, t=t, C=-R.T @ t, f=k["f_px"], cx=k["cx"], cy=k["cy"], pfad=g[0]))
    return out


def proj(k, X):
    p = np.atleast_2d(X) @ k["R"].T + k["t"]; return np.c_[k["f"] * p[:, 0] / p[:, 2] + k["cx"], k["f"] * p[:, 1] / p[:, 2] + k["cy"]], p[:, 2]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ordner"); ap.add_argument("aus"); ap.add_argument("--wunsch"); ap.add_argument("--mpp", type=float, default=0.01, help="Soll-Aufloesung fuer automatisch gefundene Luecken (m je Pixel)")
    ap.add_argument("--min_m2", type=float, default=8.0); ap.add_argument("--extra-umriss", nargs="*", type=float, default=[], help="weitere Rechtecke x0 y0 x1 y1 (Nachbargebaeude) fuer die Karte"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"]); mp = os.path.join(od, "messprotokoll"); FA = json.load(open(os.path.join(a.ordner, "fassaden.json")))["fassaden"]; KAM = kameras(mp, fd)
    bedarf = []
    for i, F in enumerate(FA):                                             # automatisch: Wandbereiche ohne Bilddaten
        if F.get("flaeche_m2", 0) < 40: continue
        R = F["raster"]; im = cv2.imread(os.path.join(a.ordner, f"ortho_f{i:02d}.png")); c = 0.5; W = int((F["u"][1] - F["u"][0]) / c); H = int((F["z"][1] - F["z"][0]) / c)
        dat = cv2.resize((im.max(2) > 8).astype(np.float32), (R["nu"], R["nz"]))[int((R["z1"] - F["z"][1]) / R["zelle"]):int((R["z1"] - F["z"][0]) / R["zelle"]), int((F["u"][0] - R["u0"]) / R["zelle"]):int((F["u"][1] - R["u0"]) / R["zelle"])] if im is not None else np.zeros((10, 10), np.float32)
        leer = cv2.resize(dat, (W, H), interpolation=cv2.INTER_AREA) < 0.3; leer = ndi.binary_opening(leer, np.ones((3, 3))); lab, n = ndi.label(leer)
        for li, sl in enumerate(ndi.find_objects(lab), 1):
            fl = (lab[sl] == li).sum() * c * c
            if fl < a.min_m2: continue
            bedarf.append(dict(wand=i, u=[F["u"][0] + sl[1].start * c, F["u"][0] + sl[1].stop * c], z=[F["z"][1] - sl[0].stop * c, F["z"][1] - sl[0].start * c], mpp=a.mpp, titel=f"Wand {i}: Bereich ohne Fotodaten ({fl:.0f} m2)", warum="Kein registriertes Foto zeigt diesen Wandbereich - dort ist das Modell geraten oder leer.", auto=True))
    if a.wunsch: bedarf += json.load(open(a.wunsch))
    rm = obj["rahmen"]; M0 = np.array(rm["mitte_utm"]); xh = np.array(rm["xhat_utm"]); yh = np.array(rm["yhat_utm"])
    def geo(x, y): e, n_ = M0 + x * xh + y * yh; return utm32_nach_geo(float(e), float(n_))
    karten = []
    for nr, b in enumerate(bedarf, 1):
        F = FA[b["wand"]]; o = np.array(F["o"]); d = np.array(F["d"]); nv = np.array([F["n"][0], F["n"][1], 0.0]); um = 0.5 * (b["u"][0] + b["u"][1]); zm = 0.5 * (b["z"][0] + b["z"][1]); P = np.array([o[0] + um * d[0], o[1] + um * d[1], zm])
        ecken = np.array([[o[0] + u_ * d[0], o[1] + u_ * d[1], z_] for u_ in b["u"] for z_ in b["z"]]); sehen = []
        for k in KAM:
            v = k["C"] - P; dist = np.linalg.norm(v); cw = float(v @ nv / dist); px, zc = proj(k, np.vstack([P, ecken]))
            if cw < 0.34 or zc.min() <= 1 or not (0 < px[0, 0] < 2 * k["cx"] and 0 < px[0, 1] < 2 * k["cy"]): continue
            sehen.append((dist / (k["f"] * cw), k, dist, cw, px[1:]))
        vorbild = None
        if b.get("auto"):                                                 # Luecke im Fassadenbild: die Geometrie allein taeuscht (Verdeckung durch Nachbarn, falsch registrierte Videobilder) -> gilt als ungesehen;
            hoch = sorted([s_ for s_ in sehen if s_[1]["C"][2] > 10 and not s_[1]["name"].startswith("video")], key=lambda s_: s_[0]); vorbild = hoch[0] if hoch else None; sehen = []   # ein erhoehtes Foto dient nur als Vorbild fuer den Standort
        sehen.sort(key=lambda s: s[0]); e = dict(nr=nr, titel=b["titel"], warum=b.get("warum", ""), wand=b["wand"], u=[round(v, 1) for v in b["u"]], z=[round(v, 1) for v in b["z"]], soll_mpp=b["mpp"], fotos_bisher=len(sehen), auto=bool(b.get("auto")))
        hoehe = zm - 1.6; rvec = nv[:2] / np.linalg.norm(nv[:2])
        if sehen:
            mpp, k, dist, cw, ex = sehen[0]; e.update(ist_mpp=round(mpp, 4), bestes_foto=k["name"], abstand_m=round(dist, 0), zoom=round(mpp / b["mpp"], 1), standort=[round(float(k["C"][0]), 1), round(float(k["C"][1]), 1), round(float(k["C"][2]), 1)])
            im = cv2.imread(k["pfad"]); x0, y0 = ex.min(0); x1, y1 = ex.max(0); m = 0.8 * max(x1 - x0, y1 - y0) + 60; a0, b0, a1, b1 = [int(v) for v in (max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, im.shape[1]), min(y1 + m, im.shape[0]))]
            if a1 - a0 > 20 and b1 - b0 > 20:
                cv2.rectangle(im, (int(x0), int(y0)), (int(x1), int(y1)), (0, 0, 255), max(3, int((a1 - a0) / 200))); cr = im[b0:b1, a0:a1]; s = 560.0 / max(cr.shape[:2]); cr = cv2.resize(cr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
                e["bild"] = "data:image/jpeg;base64," + base64.b64encode(cv2.imencode(".jpg", cr, [cv2.IMWRITE_JPEG_QUALITY, 72])[1].tobytes()).decode()
            if e["zoom"] <= 1.2: e["rat"] = f"Aufloesung reicht ({mpp * 100:.1f} cm je Pixel). Es fehlen nur weitere Blickwinkel: 4-6 Fotos vom gleichen Abstand, zwischen den Fotos je 2-3 m zur Seite gehen."
            elif e["zoom"] <= 5: e["rat"] = f"Vom markierten Standort (dort entstand das Foto unten) mit {e['zoom']:.0f}-fachem Zoom auf den roten Bereich, 5 Fotos, dazwischen je 1-2 m zur Seite gehen."
            else: e["rat"] = f"Vom bisherigen Standort ({dist:.0f} m) reicht auch Zoom nicht ({e['zoom']:.0f}-fach noetig). Naeher heran bis auf etwa {b['mpp'] * 2790 * 3:.0f} m (3-fach-Zoom) oder Teleobjektiv; 5 Fotos, je 1-2 m Seitenschritt."
        elif vorbild is not None:
            mpp, k, dist, cw, ex = vorbild; e.update(ist_mpp=None, bestes_foto=k["name"], standort=[round(float(v_), 1) for v_ in k["C"]], abstand_m=round(dist, 0), zoom=None)
            im = cv2.imread(k["pfad"]); x0, y0 = ex.min(0); x1, y1 = ex.max(0); m = 0.5 * max(x1 - x0, y1 - y0) + 60; a0, b0, a1, b1 = [int(v) for v in (max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, im.shape[1]), min(y1 + m, im.shape[0]))]
            if a1 - a0 > 20 and b1 - b0 > 20:
                cv2.rectangle(im, (int(x0), int(y0)), (int(x1), int(y1)), (0, 0, 255), max(3, int((a1 - a0) / 200))); cr = im[b0:b1, a0:a1]; s_ = 560.0 / max(cr.shape[:2]); cr = cv2.resize(cr, None, fx=s_, fy=s_, interpolation=cv2.INTER_AREA if s_ < 1 else cv2.INTER_LINEAR)
                e["bild"] = "data:image/jpeg;base64," + base64.b64encode(cv2.imencode(".jpg", cr, [cv2.IMWRITE_JPEG_QUALITY, 72])[1].tobytes()).decode()
            e["rat"] = f"Im Fassadenbild fehlt dieser Bereich ganz. Das Foto unten (aus {dist:.0f} m, Standort {k['C'][2]:.0f} m ueber der Strasse) zeigt, von wo man ihn sieht: von dort oder aus aehnlicher Richtung 6-8 Fotos mit Zoom auf den roten Bereich, dazwischen je 3-5 m zur Seite gehen."
        else:
            dh = max(12.0, 1.2 * hoehe); S = P[:2] + rvec * dh; e.update(ist_mpp=None, standort=[round(float(S[0]), 1), round(float(S[1]), 1), 1.6], abstand_m=round(float(math.hypot(dh, hoehe)), 0), zoom=None)
            e["rat"] = f"Kein Foto zeigt diesen Bereich. Gesucht ist ein Standort etwa {dh:.0f} m vor der Wand (Pfeil in der Karte) - wenn dort ein Haus steht: von einem erhoehten Punkt in dieser Richtung (Hang, Turm, Fenster gegenueber). 6-8 Fotos, dazwischen je 2-3 m zur Seite."
        lat, lon = geo(e["standort"][0], e["standort"][1]); e["lat"], e["lon"] = round(lat, 6), round(lon, 6); e["ziel_xy"] = [round(float(P[0]), 1), round(float(P[1]), 1)]; karten.append(e)
    # Karte (SVG): Modellrahmen +x Nord, +y West -> Bild x = -y, Bild y = -x
    rw = obj.get("rahmen_wand", {}); pts = np.array([k["C"][:2] for k in KAM if k["C"][2] < 12] + [[rw.get("u0", 0), rw.get("v0", 0)], [rw.get("u1", 0), rw.get("v1", 0)]] + [e["standort"][:2] for e in karten]); mitte = np.array([0.5 * (rw.get("u0", 0) + rw.get("u1", 0)), 0.5 * (rw.get("v0", 0) + rw.get("v1", 0))])
    r = float(min(np.percentile(np.linalg.norm(pts - mitte, axis=1), 97) + 10, 140)); S = 640; sk = S / (2 * r); X = lambda x, y: (S / 2 - (y - mitte[1]) * sk, S / 2 - (x - mitte[0]) * sk)
    svg = [f'<svg viewBox="0 0 {S} {S}" role="img" aria-label="Lageplan mit Fotostandorten">', f'<rect width="{S}" height="{S}" fill="var(--karte)"/>']
    for k in KAM:
        if k["C"][2] < 12 and np.linalg.norm(k["C"][:2] - mitte) < r: x, y = X(*k["C"][:2]); svg.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="2.2" fill="var(--alt)"/>')
    def rechteck(x0, y0, x1, y1, cls):
        p = [X(x0, y0), X(x0, y1), X(x1, y1), X(x1, y0)]; svg.append(f'<polygon points="{" ".join(f"{u:.0f},{v:.0f}" for u, v in p)}" class="{cls}"/>')
    for q in range(0, len(a.extra_umriss), 4): rechteck(*a.extra_umriss[q:q + 4], "nachbar")
    if rw: rechteck(rw["u0"], rw["v0"], rw["u1"], rw["v1"], "bau")
    for e in karten:
        x0, y0 = X(*e["standort"][:2]); x1, y1 = X(*e["ziel_xy"]); ins = np.linalg.norm(np.array(e["standort"][:2]) - mitte) < r
        if not ins: v = np.array(e["standort"][:2]) - mitte; x0, y0 = X(*(mitte + v / np.linalg.norm(v) * (r - 6)))
        svg.append(f'<line x1="{x0:.0f}" y1="{y0:.0f}" x2="{x1:.0f}" y2="{y1:.0f}" class="blick"/><circle cx="{x0:.0f}" cy="{y0:.0f}" r="11" class="punkt"/><text x="{x0:.0f}" y="{y0 + 4:.0f}" class="nr">{e["nr"]}</text>')
    bl = 20 * sk; svg.append(f'<line x1="18" y1="{S - 18}" x2="{18 + bl:.0f}" y2="{S - 18}" class="mass"/><text x="18" y="{S - 26}" class="leg">20 m</text><text x="{S - 20}" y="24" class="leg" text-anchor="end">Norden oben</text></svg>')
    json.dump(dict(objekt=obj.get("name"), auftraege=[{k_: v for k_, v in e.items() if k_ != "bild"} for e in karten]), open(os.path.splitext(a.aus)[0] + ".json", "w"), indent=1, ensure_ascii=False)
    def karte(e):
        zeile = lambda l, w: f'<div class="zeile"><dt>{l}</dt><dd>{w}</dd></div>'
        ist = "kein Foto" if e["ist_mpp"] is None else f'{e["ist_mpp"] * 100:.1f} cm je Pixel aus {e["abstand_m"]:.0f} m'
        return (f'<article class="auftrag" id="auftrag-{e["nr"]}"><header><span class="num">{e["nr"]}</span><h2>{e["titel"]}</h2><span class="marke {"leer" if e["ist_mpp"] is None else "grob"}">{"ungesehen" if e["ist_mpp"] is None else "zu grob" if (e["zoom"] or 0) > 1.2 else "mehr Blickwinkel"}</span></header>'
                f'<p class="warum">{e["warum"]}</p><p class="rat">{e["rat"]}</p>' + (f'<figure><img src="{e["bild"]}" alt="Vorhandenes Foto, Zielbereich rot markiert"><figcaption>{"Vorbild fuer den Standort" if e["ist_mpp"] is None else "Bestes vorhandenes Foto"} ({e["bestes_foto"][-22:]}), Ziel rot markiert</figcaption></figure>' if e.get("bild") else "")
                + '<dl>' + zeile("Bereich", f'Wand {e["wand"]}, Hoehe {e["z"][0]:.0f}-{e["z"][1]:.0f} m') + zeile("Heute", ist) + zeile("Gebraucht", f'{e["soll_mpp"] * 100:.1f} cm je Pixel') + zeile("Fotos mit Blick darauf", str(e["fotos_bisher"]) + (" (im Fassadenbild)" if e["ist_mpp"] is None else " (rechnerisch, ohne Verdeckung)"))
                + zeile("Standort", f'<a href="https://www.openstreetmap.org/?mlat={e["lat"]}&mlon={e["lon"]}#map=19/{e["lat"]}/{e["lon"]}">{e["lat"]}, {e["lon"]}</a>') + '</dl></article>')
    html = VORLAGE.replace("__NAME__", str(obj.get("name", "Objekt"))).replace("__N__", str(len(karten))).replace("__SVG__", "\n".join(svg)).replace("__KARTEN__", "\n".join(karte(e) for e in karten))
    open(a.aus, "w").write(html); print(f"{a.aus}: {len(karten)} Auftraege ({sum(1 for e in karten if e['ist_mpp'] is None)} ungesehen), {os.path.getsize(a.aus) / 1e6:.1f} MB")
    for e in karten: print(f"  {e['nr']:2d} {e['titel'][:52]:52s} heute {'-' if e['ist_mpp'] is None else '%.1f cm/px' % (e['ist_mpp'] * 100)}, soll {e['soll_mpp'] * 100:.1f}, Fotos {e['fotos_bisher']}")


VORLAGE = """<title>Fotoauftrag __NAME__</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Aufbau: Feldblatt zum Mitnehmen - oben Lageplan mit nummerierten Standorten, darunter je Nummer eine Karte mit Foto, Anweisung und Zahlen */
:root { --grund: #f3f4f1; --blatt: #ffffff; --text: #1d2420; --leise: #5c665f; --linie: #d5dad4; --rot: #c8321e; --karte: #e6eae3; --bau: #2f3a34; --alt: #8c978f; --gelb: #f0c23b;
  --sans: "IBM Plex Sans", system-ui, sans-serif; --mono: "IBM Plex Mono", ui-monospace, monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --grund: #151916; --blatt: #1e2420; --text: #e7ece8; --leise: #9aa59d; --linie: #333c36; --rot: #ff6b55; --karte: #232a25; --bau: #cfd8d1; --alt: #6f7a72; --gelb: #f0c23b; color-scheme: dark } }
:root[data-theme="dark"] { --grund: #151916; --blatt: #1e2420; --text: #e7ece8; --leise: #9aa59d; --linie: #333c36; --rot: #ff6b55; --karte: #232a25; --bau: #cfd8d1; --alt: #6f7a72; --gelb: #f0c23b; color-scheme: dark }
body { background: var(--grund); color: var(--text); font-family: var(--sans); font-size: 16px; line-height: 1.5; padding-block: 24px 48px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
main { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
h1 { font-size: 1.6rem; font-weight: 600; margin: 0; text-wrap: balance; } .unter { color: var(--leise); margin: 6px 0 0; max-width: 60ch; }
.plan { background: var(--blatt); border: 1px solid var(--linie); border-radius: 6px; padding: 12px; } .plan svg { display: block; width: 100%; height: auto; border-radius: 3px; }
.plan p { margin: 10px 2px 0; color: var(--leise); font-size: 0.9rem; }
svg .bau { fill: var(--bau); } svg .nachbar { fill: var(--alt); opacity: 0.55; } svg .blick { stroke: var(--rot); stroke-width: 2; stroke-dasharray: 5 4; } svg .punkt { fill: var(--rot); } svg .nr { fill: #fff; font: 600 12px var(--mono); text-anchor: middle; }
svg .mass { stroke: var(--text); stroke-width: 3; } svg .leg { fill: var(--leise); font: 12px var(--mono); }
.auftrag { background: var(--blatt); border: 1px solid var(--linie); border-radius: 6px; padding: 16px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.auftrag header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; } .auftrag h2 { font-size: 1.05rem; font-weight: 600; margin: 0; flex: 1 1 12rem; min-width: 0; text-wrap: balance; }
.num { background: var(--rot); color: #fff; font: 600 0.85rem var(--mono); width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; flex: none; }
.marke { font: 500 0.72rem var(--mono); letter-spacing: 0.06em; text-transform: uppercase; padding: 3px 8px; border-radius: 3px; border: 1px solid var(--linie); color: var(--leise); } .marke.leer { border-color: var(--rot); color: var(--rot); }
.warum { margin: 0; color: var(--leise); } .rat { margin: 0; font-weight: 500; }
figure { margin: 0; } figure img { display: block; max-width: 100%; border-radius: 3px; } figcaption { color: var(--leise); font-size: 0.82rem; margin-top: 4px; overflow-wrap: anywhere; }
dl { margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 16px; border-top: 1px solid var(--linie); padding-top: 10px; }
.zeile { min-width: 0; } dt { font: 500 0.7rem var(--mono); letter-spacing: 0.06em; text-transform: uppercase; color: var(--leise); } dd { margin: 0; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
a { color: var(--rot); } a:focus-visible { outline: 2px solid var(--gelb); outline-offset: 2px; }
.regeln { background: var(--blatt); border: 1px solid var(--linie); border-radius: 6px; padding: 14px 16px; } .regeln h2 { font-size: 1rem; margin: 0 0 6px; } .regeln ul { margin: 0; padding-left: 1.1rem; } .regeln li { margin: 3px 0; }
</style>
<main>
<header><h1>Fotoauftrag __NAME__</h1><p class="unter">__N__ Stellen, an denen dem Modell Fotos fehlen. Die Nummern im Plan sind die Standorte, die Karten darunter sagen, was dort zu fotografieren ist.</p></header>
<section class="plan">__SVG__<p>Rote Nummern: empfohlener Standort, gestrichelt die Blickrichtung zum Ziel. Graue Punkte: Orte, an denen schon fotografiert wurde. Dunkel: das Gebaeude.</p></section>
<section class="regeln"><h2>Fuer alle Fotos</h2><ul><li>Zwischen zwei Fotos immer 1-3 m zur Seite gehen, nicht nur drehen. Erst dadurch entsteht Tiefe.</li><li>Den rot markierten Bereich bildfuellend, Nachbarflaechen duerfen am Rand mit drauf.</li><li>Hochformat fuer hohe Bereiche, kein Digitalzoom ueber die Tele-Linse hinaus.</li><li>Lieber bedeckter Himmel als harte Schatten.</li></ul></section>
__KARTEN__
</main>
"""

if __name__ == "__main__":
    sys.exit(main())
