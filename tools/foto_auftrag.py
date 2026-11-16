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


def osm_karte(lat, lon, radius_m, zoom=18):
    """Echter Stadtplan: OpenStreetMap-Kacheln um (lat, lon) laden und zusammensetzen (wenige Kacheln, einmal je Lauf; Quellenangabe auf der Seite Pflicht).
    Liefert (JPEG als data-URI, Breite, Höhe, Funktion (lat, lon) -> Pixel) oder None, wenn das Netz fehlt."""
    import urllib.request
    def kachel(la, lo): n = 2 ** zoom; return (lo + 180.0) / 360.0 * n, (1.0 - math.asinh(math.tan(math.radians(la))) / math.pi) / 2.0 * n
    xc, yc = kachel(lat, lon); mpk = 40075016.7 * math.cos(math.radians(lat)) / 2 ** zoom; rk = radius_m / mpk; x0, x1, y0, y1 = int(math.floor(xc - rk)), int(math.floor(xc + rk)), int(math.floor(yc - rk)), int(math.floor(yc + rk))
    if (x1 - x0 + 1) * (y1 - y0 + 1) > 30: return None
    bild = np.zeros(((y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256, 3), np.uint8)
    try:
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                rq = urllib.request.Request(f"https://tile.openstreetmap.org/{zoom}/{tx}/{ty}.png", headers={"User-Agent": "rc-park-modellbau/1.0 (Fotoauftrag, einzelne Kacheln)"})
                im = cv2.imdecode(np.frombuffer(urllib.request.urlopen(rq, timeout=30).read(), np.uint8), cv2.IMREAD_COLOR); bild[(ty - y0) * 256:(ty - y0 + 1) * 256, (tx - x0) * 256:(tx - x0 + 1) * 256] = im
    except Exception as e:
        print("Stadtplan nicht geladen:", str(e)[:100]); return None
    a0, b0 = int((xc - rk - x0) * 256), int((yc - rk - y0) * 256); gr = int(2 * rk * 256); bild = bild[b0:b0 + gr, a0:a0 + gr]; f = 900.0 / gr; bild = cv2.resize(bild, (900, 900), interpolation=cv2.INTER_CUBIC)
    def px(la, lo): kx, ky = kachel(la, lo); return ((kx - x0) * 256 - a0) * f, ((ky - y0) * 256 - b0) * f
    return "data:image/jpeg;base64," + base64.b64encode(cv2.imencode(".jpg", bild, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tobytes()).decode(), 900, 900, px


def himmelsrichtung(grad): return ["Norden", "Nordosten", "Osten", "Südosten", "Süden", "Südwesten", "Westen", "Nordwesten"][int(((grad % 360) + 22.5) // 45) % 8]


def proj(k, X):
    p = np.atleast_2d(X) @ k["R"].T + k["t"]; return np.c_[k["f"] * p[:, 0] / p[:, 2] + k["cx"], k["f"] * p[:, 1] / p[:, 2] + k["cy"]], p[:, 2]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ordner"); ap.add_argument("aus"); ap.add_argument("--wunsch"); ap.add_argument("--mpp", type=float, default=0.01, help="Soll-Auflösung fuer automatisch gefundene Luecken (m je Pixel)")
    ap.add_argument("--min_m2", type=float, default=8.0); ap.add_argument("--extra-umriss", nargs="*", type=float, default=[], help="weitere Rechtecke x0 y0 x1 y1 (Nachbargebaeude) fuer die Karte"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"]); mp = os.path.join(od, "messprotokoll"); FA = json.load(open(os.path.join(a.ordner, "fassaden.json")))["fassaden"]; KAM = kameras(mp, fd)
    def seite(F): n_ = F["n"]; return ("Nordseite" if n_[0] > 0 else "Südseite") if abs(n_[0]) > abs(n_[1]) else ("Westseite" if n_[1] > 0 else "Ostseite")      # Rahmen: +x Nord, +y West (objekt.json seiten_konvention)
    bedarf = []
    for i, F in enumerate(FA):                                             # automatisch: Wandbereiche ohne Bilddaten
        if F.get("flaeche_m2", 0) < 40: continue
        R = F["raster"]; im = cv2.imread(os.path.join(a.ordner, f"ortho_f{i:02d}.png")); c = 0.5; W = int((F["u"][1] - F["u"][0]) / c); H = int((F["z"][1] - F["z"][0]) / c)
        dat = cv2.resize((im.max(2) > 8).astype(np.float32), (R["nu"], R["nz"]))[int((R["z1"] - F["z"][1]) / R["zelle"]):int((R["z1"] - F["z"][0]) / R["zelle"]), int((F["u"][0] - R["u0"]) / R["zelle"]):int((F["u"][1] - R["u0"]) / R["zelle"])] if im is not None else np.zeros((10, 10), np.float32)
        leer = cv2.resize(dat, (W, H), interpolation=cv2.INTER_AREA) < 0.3; leer = ndi.binary_opening(leer, np.ones((3, 3))); lab, n = ndi.label(leer)
        for li, sl in enumerate(ndi.find_objects(lab), 1):
            fl = (lab[sl] == li).sum() * c * c
            if fl < a.min_m2: continue
            bedarf.append(dict(wand=i, u=[F["u"][0] + sl[1].start * c, F["u"][0] + sl[1].stop * c], z=[F["z"][1] - sl[0].stop * c, F["z"][1] - sl[0].start * c], mpp=a.mpp, titel=f"{seite(F)}: {fl:.0f} m² ohne Fotodaten", warum="Kein registriertes Foto zeigt diesen Wandbereich - dort ist das Modell geraten oder leer.", auto=True))
    if a.wunsch: bedarf += json.load(open(a.wunsch))
    rm = obj["rahmen"]; M0 = np.array(rm["mitte_utm"]); xh = np.array(rm["xhat_utm"]); yh = np.array(rm["yhat_utm"])
    def geo(x, y): e, n_ = M0 + x * xh + y * yh; return utm32_nach_geo(float(e), float(n_))
    def bilder(k, ex):
        im = cv2.imread(k["pfad"]); x0, y0 = ex.min(0); x1, y1 = ex.max(0); st = max(4, int(max(im.shape[:2]) / 250)); ganz = im.copy(); cv2.rectangle(ganz, (int(x0), int(y0)), (int(x1), int(y1)), (0, 0, 255), st)
        s_ = 640.0 / max(ganz.shape[:2]); ganz = cv2.resize(ganz, None, fx=s_, fy=s_, interpolation=cv2.INTER_AREA); out = dict(bild_ganz="data:image/jpeg;base64," + base64.b64encode(cv2.imencode(".jpg", ganz, [cv2.IMWRITE_JPEG_QUALITY, 74])[1].tobytes()).decode())
        m = 0.25 * max(x1 - x0, y1 - y0) + 20; a0, b0, a1, b1 = [int(v) for v in (max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, im.shape[1]), min(y1 + m, im.shape[0]))]
        if a1 - a0 > 20 and b1 - b0 > 20:
            cr = im[b0:b1, a0:a1].copy(); cv2.rectangle(cr, (int(x0 - a0), int(y0 - b0)), (int(x1 - a0), int(y1 - b0)), (0, 0, 255), max(2, int((a1 - a0) / 220))); s_ = 640.0 / max(cr.shape[:2]); cr = cv2.resize(cr, None, fx=s_, fy=s_, interpolation=cv2.INTER_AREA if s_ < 1 else cv2.INTER_CUBIC)
            out["bild"] = "data:image/jpeg;base64," + base64.b64encode(cv2.imencode(".jpg", cr, [cv2.IMWRITE_JPEG_QUALITY, 76])[1].tobytes()).decode()
        return out
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
            hoch = sorted([s_ for s_ in sehen if s_[1]["C"][2] > 10 and s_[2] < 130 and s_[1]["name"].startswith(("eigen", "online", "neu__"))], key=lambda s_: s_[0]); vorbild = hoch[0] if hoch else None; sehen = []   # ein erhoehtes Foto dient nur als Vorbild für den Standort
        nah = [s_ for s_ in sehen if s_[2] < 130]; sehen = nah if nah else sehen           # Kameras > 130 m entfernt sind meist falsch registrierte Nahaufnahmen
        sehen.sort(key=lambda s: s[0]); e = dict(nr=nr, seite=seite(F), titel=b["titel"], warum=b.get("warum", ""), wand=b["wand"], u=[round(v, 1) for v in b["u"]], z=[round(v, 1) for v in b["z"]], soll_mpp=b["mpp"], fotos_bisher=len(sehen), auto=bool(b.get("auto")))
        hoehe = zm - 1.6; rvec = nv[:2] / np.linalg.norm(nv[:2])
        if sehen:
            mpp, k, dist, cw, ex = sehen[0]; e.update(ist_mpp=round(mpp, 4), bestes_foto=k["name"], abstand_m=round(dist, 0), zoom=round(mpp / b["mpp"], 1), standort=[round(float(k["C"][0]), 1), round(float(k["C"][1]), 1), round(float(k["C"][2]), 1)])
            e.update(bilder(k, ex))
            if e["zoom"] <= 1.2: e["rat"] = f"Auflösung reicht ({mpp * 100:.1f} cm je Pixel). Es fehlen nur weitere Blickwinkel: 4-6 Fotos vom gleichen Abstand, zwischen den Fotos je 2-3 m zur Seite gehen."
            elif e["zoom"] <= 5: e["rat"] = f"Vom markierten Standort (dort entstand das Foto unten) mit {e['zoom']:.0f}-fachem Zoom auf den roten Bereich, 5 Fotos, dazwischen je 1-2 m zur Seite gehen."
            else: e["rat"] = f"Vom bisherigen Standort ({dist:.0f} m) reicht auch Zoom nicht ({e['zoom']:.0f}-fach nötig). Näher heran bis auf etwa {b['mpp'] * 2790 * 3:.0f} m (3-fach-Zoom) oder Teleobjektiv; 5 Fotos, je 1-2 m Seitenschritt."
        elif vorbild is not None:
            mpp, k, dist, cw, ex = vorbild; e.update(ist_mpp=None, bestes_foto=k["name"], standort=[round(float(v_), 1) for v_ in k["C"]], abstand_m=round(dist, 0), zoom=None)
            e.update(bilder(k, ex))
            e["rat"] = f"Im Fassadenbild fehlt dieser Bereich ganz. Das Foto unten (aus {dist:.0f} m, Standort {k['C'][2]:.0f} m über der Straße) zeigt, von wo man ihn sieht: von dort oder aus ähnlicher Richtung 6-8 Fotos mit Zoom auf den roten Bereich, dazwischen je 3-5 m zur Seite gehen."
        else:
            dh = min(max(8.0, 1.0 * (b['z'][1] - 1.6)), 20.0); S = P[:2] + rvec * dh; e.update(ist_mpp=None, standort=[round(float(S[0]), 1), round(float(S[1]), 1), 1.6], abstand_m=round(float(math.hypot(dh, hoehe)), 0), zoom=None)
            e["rat"] = f"Kein brauchbares Foto zeigt diese Fassade. Stell dich etwa {dh:.0f} m davor (rote Nummer im Plan, Pfeil = Blickrichtung) und fotografiere die ganze Fassade: 6-8 Fotos, dazwischen je 2-3 m zur Seite gehen. Steht dort ein Haus im Weg (Hof, Rückseite), dann von der nächsten freien Stelle in dieser Richtung."
        vv = (P[0] - e["standort"][0]) * xh + (P[1] - e["standort"][1]) * yh; e["peilung"] = round(float(np.degrees(np.arctan2(vv[0], vv[1])) % 360)); e["richtung"] = himmelsrichtung(e["peilung"]); zl = geo(float(P[0]), float(P[1])); e["ziel_geo"] = [round(zl[0], 6), round(zl[1], 6)]
        lat, lon = geo(e["standort"][0], e["standort"][1]); e["lat"], e["lon"] = round(lat, 6), round(lon, 6); e["ziel_xy"] = [round(float(P[0]), 1), round(float(P[1]), 1)]; karten.append(e)
    # Stadtplan (OpenStreetMap-Kacheln, eingebettet) mit Standorten und Blickpfeilen; ohne Netz: schematischer Plan
    rw = obj.get("rahmen_wand", {}); mitte = np.array([0.5 * (rw.get("u0", 0) + rw.get("u1", 0)), 0.5 * (rw.get("v0", 0) + rw.get("v1", 0))]); alle = np.array([e["standort"][:2] for e in karten] + [mitte.tolist()])
    r = float(min(np.linalg.norm(alle - mitte, axis=1).max() + 25, 160)); la0, lo0 = geo(*mitte); osm = osm_karte(la0, lo0, r); S = 900
    if osm: plan_uri, _, _, pxf = osm; X = lambda x, y: pxf(*geo(x, y))
    else: plan_uri = ""; sk = S / (2 * r); X = lambda x, y: (S / 2 - (y - mitte[1]) * sk, S / 2 - (x - mitte[0]) * sk)
    mpp_plan = 2 * r / S
    def pfeil(e, gross=True):
        x0, y0 = X(*e["standort"][:2]); x1, y1 = X(*e["ziel_xy"]); d_ = math.hypot(x1 - x0, y1 - y0) or 1.0; ux, uy = (x1 - x0) / d_, (y1 - y0) / d_; rr = 15 if gross else 0.045
        return x0, y0, x1, y1, ux, uy
    svg = [f'<svg viewBox="0 0 {S} {S}" role="img" aria-label="Stadtplan mit Fotostandorten und Blickrichtungen">'] + ([f'<image href="{plan_uri}" width="{S}" height="{S}"/>'] if osm else [f'<rect width="{S}" height="{S}" fill="var(--karte)"/>'])
    svg.append('<defs><marker id="spitze" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#c8321e"/></marker></defs>')
    for k in KAM:
        if k["C"][2] < 12 and np.linalg.norm(k["C"][:2] - mitte) < r: x, y = X(*k["C"][:2]); svg.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3" class="alt"/>')
    if not osm:
        def rechteck(x0, y0, x1, y1, cls): p_ = [X(x0, y0), X(x0, y1), X(x1, y1), X(x1, y0)]; svg.append(f'<polygon points="{" ".join(f"{u:.0f},{v:.0f}" for u, v in p_)}" class="{cls}"/>')
        for q in range(0, len(a.extra_umriss), 4): rechteck(*a.extra_umriss[q:q + 4], "nachbar")
        if rw: rechteck(rw["u0"], rw["v0"], rw["u1"], rw["v1"], "bau")
    for e in karten:
        x0, y0, x1, y1, ux, uy = pfeil(e); ins = 0 < x0 < S and 0 < y0 < S
        if not ins: x0, y0 = min(max(x0, 24), S - 24), min(max(y0, 24), S - 24)
        e["plan_px"] = [x0, y0, x1, y1]
        svg.append(f'<line x1="{x0 + ux * 18:.0f}" y1="{y0 + uy * 18:.0f}" x2="{x1 - ux * 4:.0f}" y2="{y1 - uy * 4:.0f}" class="blick" marker-end="url(#spitze)"/><circle cx="{x0:.0f}" cy="{y0:.0f}" r="16" class="punkt"/><text x="{x0:.0f}" y="{y0 + 6:.0f}" class="nr">{e["nr"]}</text>')
    bl = 20 / mpp_plan; svg.append(f'<rect x="14" y="{S - 50}" width="{bl + 20:.0f}" height="38" class="schild"/><line x1="24" y1="{S - 22}" x2="{24 + bl:.0f}" y2="{S - 22}" class="mass"/><text x="24" y="{S - 30}" class="leg">20 m</text></svg>')
    def miniplan(e):
        x0, y0, x1, y1 = e["plan_px"]; seite = min(max(math.hypot(x1 - x0, y1 - y0) * 1.7, 240), S); ox = min(max((x0 + x1) / 2 - seite / 2, 0), S - seite); oy = min(max((y0 + y1) / 2 - seite / 2, 0), S - seite); d_ = math.hypot(x1 - x0, y1 - y0) or 1.0; ux, uy = (x1 - x0) / d_, (y1 - y0) / d_; k_ = seite / 300.0
        grund = (f'background-image:var(--plan);background-size:{S / seite * 100:.1f}%;background-position:{(ox / (S - seite) * 100 if S > seite else 0):.1f}% {(oy / (S - seite) * 100 if S > seite else 0):.1f}%' if osm else 'background:var(--karte)')
        return (f'<div class="mini" style="{grund}"><svg viewBox="{ox:.0f} {oy:.0f} {seite:.0f} {seite:.0f}" aria-label="Standort und Blickrichtung"><line x1="{x0 + ux * 14 * k_:.0f}" y1="{y0 + uy * 14 * k_:.0f}" x2="{x1 - ux * 5 * k_:.0f}" y2="{y1 - uy * 5 * k_:.0f}" stroke="#c8321e" stroke-width="{5 * k_:.1f}" marker-end="url(#spitze)"/>'
                f'<circle cx="{x1:.0f}" cy="{y1:.0f}" r="{7 * k_:.1f}" fill="none" stroke="#c8321e" stroke-width="{3 * k_:.1f}"/><circle cx="{x0:.0f}" cy="{y0:.0f}" r="{13 * k_:.1f}" fill="#c8321e"/><text x="{x0:.0f}" y="{y0 + 5 * k_:.0f}" fill="#fff" font-family="monospace" font-weight="700" font-size="{14 * k_:.0f}" text-anchor="middle">{e["nr"]}</text></svg></div>')
    json.dump(dict(objekt=obj.get("name"), auftraege=[{k_: v for k_, v in e.items() if not k_.startswith("bild")} for e in karten]), open(os.path.splitext(a.aus)[0] + ".json", "w"), indent=1, ensure_ascii=False)
    def karte(e):
        zeile = lambda l, w: f'<div class="zeile"><dt>{l}</dt><dd>{w}</dd></div>'
        ist = "kein Foto im Fassadenbild" if e["ist_mpp"] is None else f'{e["ist_mpp"] * 100:.1f} cm je Pixel aus {e["abstand_m"]:.0f} m'; hoch = e["standort"][2] > 6
        wo = f'Blick nach <strong>{e["richtung"]}</strong> ({e["peilung"]} Grad), etwa {math.hypot(e["standort"][0] - e["ziel_xy"][0], e["standort"][1] - e["ziel_xy"][1]):.0f} m bis zur Wand' + (f', Standort liegt etwa {e["standort"][2]:.0f} m über der Straße (Hang, Turm oder Fenster)' if hoch else '')
        fotos = ""
        if e.get("bild_ganz"): fotos += f'<figure><img src="{e["bild_ganz"]}" alt="Foto von diesem Standort, Zielbereich rot markiert"><figcaption>{"So sieht man die Wand von dort" if e["ist_mpp"] is None else "Von diesem Standort aufgenommen"} ({e["bestes_foto"][-22:]})</figcaption></figure>'
        if e.get("bild"): fotos += f'<figure><img src="{e["bild"]}" alt="Zielbereich vergrößert"><figcaption>Das soll das neue Foto füllen</figcaption></figure>'
        return (f'<article class="auftrag" id="auftrag-{e["nr"]}"><header><span class="num">{e["nr"]}</span><h2>{e["titel"]}</h2><span class="marke {"leer" if e["ist_mpp"] is None else "grob"}">{"ungesehen" if e["ist_mpp"] is None else "zu grob" if (e["zoom"] or 0) > 1.2 else "mehr Blickwinkel"}</span></header>'
                f'<p class="rat">{e["rat"]}</p><div class="wo">{miniplan(e)}<div class="wotext"><p>{wo}</p><p><a href="https://www.google.com/maps/search/?api=1&query={e["lat"]},{e["lon"]}">Standort in Google Maps</a> &middot; <a href="https://www.openstreetmap.org/?mlat={e["lat"]}&mlon={e["lon"]}#map=19/{e["lat"]}/{e["lon"]}">OpenStreetMap</a></p><p class="koord">{e["lat"]}, {e["lon"]}</p></div></div>'
                + (f'<div class="fotos">{fotos}</div>' if fotos else "") + f'<p class="warum">{e["warum"]}</p>'
                + '<dl>' + zeile("Bereich", f'{e["seite"]}, Höhe {e["z"][0]:.0f}-{e["z"][1]:.0f} m') + zeile("Heute", ist) + zeile("Gebraucht", f'{e["soll_mpp"] * 100:.1f} cm je Pixel') + zeile("Fotos mit Blick darauf", str(e["fotos_bisher"]) + (" (im Fassadenbild)" if e["ist_mpp"] is None else " (rechnerisch)")) + '</dl></article>')
    html = VORLAGE.replace("__NAME__", str(obj.get("name", "Objekt"))).replace("__N__", str(len(karten))).replace("__SVG__", "\n".join(svg)).replace("__PLAN__", plan_uri).replace("__QUELLE__", "Karte: &copy; OpenStreetMap-Mitwirkende. " if osm else "").replace("__KARTEN__", "\n".join(karte(e) for e in karten))
    open(a.aus, "w").write(html); print(f"{a.aus}: {len(karten)} Auftraege ({sum(1 for e in karten if e['ist_mpp'] is None)} ungesehen), {os.path.getsize(a.aus) / 1e6:.1f} MB")
    for e in karten: print(f"  {e['nr']:2d} {e['titel'][:52]:52s} heute {'-' if e['ist_mpp'] is None else '%.1f cm/px' % (e['ist_mpp'] * 100)}, soll {e['soll_mpp'] * 100:.1f}, Fotos {e['fotos_bisher']}")


VORLAGE = """<title>Fotoauftrag __NAME__</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Aufbau: Feldblatt zum Mitnehmen - oben Lageplan mit nummerierten Standorten, darunter je Nummer eine Karte mit Foto, Anweisung und Zahlen */
:root { --plan: url("__PLAN__"); --grund: #f3f4f1; --blatt: #ffffff; --text: #1d2420; --leise: #5c665f; --linie: #d5dad4; --rot: #c8321e; --karte: #e6eae3; --bau: #2f3a34; --alt: #8c978f; --gelb: #f0c23b;
  --sans: "IBM Plex Sans", system-ui, sans-serif; --mono: "IBM Plex Mono", ui-monospace, monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --grund: #151916; --blatt: #1e2420; --text: #e7ece8; --leise: #9aa59d; --linie: #333c36; --rot: #ff6b55; --karte: #232a25; --bau: #cfd8d1; --alt: #6f7a72; --gelb: #f0c23b; color-scheme: dark } }
:root[data-theme="dark"] { --grund: #151916; --blatt: #1e2420; --text: #e7ece8; --leise: #9aa59d; --linie: #333c36; --rot: #ff6b55; --karte: #232a25; --bau: #cfd8d1; --alt: #6f7a72; --gelb: #f0c23b; color-scheme: dark }
body { background: var(--grund); color: var(--text); font-family: var(--sans); font-size: 16px; line-height: 1.5; padding-block: 24px 48px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
main { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
h1 { font-size: 1.6rem; font-weight: 600; margin: 0; text-wrap: balance; } .unter { color: var(--leise); margin: 6px 0 0; max-width: 60ch; }
.plan { background: var(--blatt); border: 1px solid var(--linie); border-radius: 6px; padding: 12px; } .plan svg { display: block; width: 100%; height: auto; border-radius: 3px; }
.plan p { margin: 10px 2px 0; color: var(--leise); font-size: 0.9rem; }
svg .bau { fill: var(--bau); } svg .nachbar { fill: var(--alt); opacity: 0.55; } svg .blick { stroke: #c8321e; stroke-width: 5; } svg .punkt { fill: #c8321e; stroke: #fff; stroke-width: 2; } svg .nr { fill: #fff; font: 700 17px var(--mono); text-anchor: middle; }
svg .mass { stroke: #1d2420; stroke-width: 4; } svg .leg { fill: #1d2420; font: 600 15px var(--mono); }
.auftrag { background: var(--blatt); border: 1px solid var(--linie); border-radius: 6px; padding: 16px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.auftrag header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; } .auftrag h2 { font-size: 1.05rem; font-weight: 600; margin: 0; flex: 1 1 12rem; min-width: 0; text-wrap: balance; }
.num { background: var(--rot); color: #fff; font: 600 0.85rem var(--mono); width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; flex: none; }
.marke { font: 500 0.72rem var(--mono); letter-spacing: 0.06em; text-transform: uppercase; padding: 3px 8px; border-radius: 3px; border: 1px solid var(--linie); color: var(--leise); } .marke.leer { border-color: var(--rot); color: var(--rot); }
.warum { margin: 0; color: var(--leise); } .rat { margin: 0; font-weight: 500; }
figure { margin: 0; } figure img { display: block; max-width: 100%; border-radius: 3px; } figcaption { color: var(--leise); font-size: 0.82rem; margin-top: 4px; overflow-wrap: anywhere; }
dl { margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 16px; border-top: 1px solid var(--linie); padding-top: 10px; }
.zeile { min-width: 0; } dt { font: 500 0.7rem var(--mono); letter-spacing: 0.06em; text-transform: uppercase; color: var(--leise); } dd { margin: 0; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
a { color: var(--rot); } a:focus-visible { outline: 2px solid var(--gelb); outline-offset: 2px; }
.wo { display: grid; grid-template-columns: minmax(0, 220px) minmax(0, 1fr); gap: 14px; align-items: start; } .wotext p { margin: 0 0 6px; } .koord { font: 0.82rem var(--mono); color: var(--leise); }
.mini { aspect-ratio: 1; max-width: 100%; border-radius: 4px; border: 1px solid var(--linie); background-repeat: no-repeat; overflow: hidden; } .mini svg { display: block; width: 100%; height: 100%; }
.fotos { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; align-items: start; }
@media (max-width: 480px) { .wo { grid-template-columns: 1fr; } .mini { max-width: 280px; } }
svg .alt { fill: #2b6cb0; stroke: #fff; stroke-width: 1; opacity: 0.75; } svg .schild { fill: #fff; opacity: 0.85; }
.regeln { background: var(--blatt); border: 1px solid var(--linie); border-radius: 6px; padding: 14px 16px; } .regeln h2 { font-size: 1rem; margin: 0 0 6px; } .regeln ul { margin: 0; padding-left: 1.1rem; } .regeln li { margin: 3px 0; }
</style>
<main>
<header><h1>Fotoauftrag __NAME__</h1><p class="unter">__N__ Stellen, an denen dem Modell Fotos fehlen. Die Nummern im Plan sind die Standorte, die Karten darunter sagen, was dort zu fotografieren ist.</p></header>
<section class="plan">__SVG__<p>Rote Nummer = dort hinstellen, roter Pfeil = in diese Richtung fotografieren. Blaue Punkte: Orte, an denen schon fotografiert wurde. Norden ist oben. __QUELLE__</p></section>
<section class="regeln"><h2>Für alle Fotos</h2><ul><li>Zwischen zwei Fotos immer 1-3 m zur Seite gehen, nicht nur drehen. Erst dadurch entsteht Tiefe.</li><li>Den rot markierten Bereich bildfüllend, Nachbarflaechen dürfen am Rand mit drauf.</li><li>Hochformat für hohe Bereiche, kein Digitalzoom über die Tele-Linse hinaus.</li><li>Lieber bedeckter Himmel als harte Schatten.</li></ul></section>
__KARTEN__
</main>
"""

if __name__ == "__main__":
    sys.exit(main())
