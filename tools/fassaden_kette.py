#!/usr/bin/env python3
"""fassaden_kette.py <objekt.json> --netz <mesh.npz> [--wand NAME ax ay bx by aussen_x aussen_y z1 ...] [--min_laenge 3] [--px 0.05] - Fassaden-Kette AUTOMATISCH je Wand.

Was am 15.11.2026 am Schwabentor von Hand lief, in einem Lauf (Nutzer: "Baue alles automatisch in die Pipeline, was irgendwie geht"):
  1. Waende: --wand (gemessene Wandgerade) oder alle Aussenkanten des LoD2-Grundrisses aus dach.json (>= --min_laenge), Hoehe bis hoechster Dachpunkt des Teils.
  2. Fotos je Wand automatisch waehlen (fotos_fuer_wand): Abdeckung der Wandflaeche x Aufloesung x Frontalitaet aus den K-Dateien, beste 3.
  3. relief_einsatz.py (Hoehenbild aus dem Netz, ab z 0, mit Oeffnungsmaske) -> relief/<wand>.npz
  4. relief_putz.py (Putz eben ueber die Fotofarbe) -> <wand>_putz.npz        (faellt weg, wenn kein Putz gefunden)
  5. steine_generieren.py (Loecher ausserhalb von Putz und Oeffnungen) -> <wand>_voll.npz
  5c. mit --fotosteine: steine_aus_foto.py --foto auto oberhalb --foto_ab -> <wand>_foto.npz (anbauen() setzt es vor das grobe Relief)
  5b. mit --fein SPARSE BILDER: tiefe_lokal.py fuer die Steinzone der Wand (1 cm, GPU) + relief_mischen.py -> <wand>_misch.npz (2 cm), wird von anbauen() vor das grobe Relief gesetzt.
  6. Bericht audit/fassaden_kette.json (Wand, Fotos, Loch-/Putz-/Generiert-Anteile) + je Wand das Bild relief/<wand>_voll.jpg zum ANSEHEN.
Im Generator: `from fassaden_kette import anbauen; koerper = anbauen(koerper, OBJ)` vereinigt alle *_voll.npz (nur innerhalb der nach aussen verschobenen Koerperhuelle).
17.11.2026 (kaufhaus_gk, Putzbau): (a) Wandflaeche je Kante aus den LoD2-Wandpolygonen (wand_flaeche): Hoehe = Wandoberkante statt First, Lochanteil nur in der freien Wand ohne Oeffnungen,
  angebaute Flaechen (Nachbar-LoD2 < 1 m davor) sind keine Fassade (Wand 'aus: Brandwand'); (b) LoD2-Nachbarn als Verdecker der Fotostufe (relief/nachbarn_lod2.stl);
  (c) QUADER-TOR (steine_aus_foto.py --tor, rc 5) vor Putzglaetten/Steine-Generieren: zeigt das beste Foto kein Fugenraster, bleibt das Netz-Relief roh (kleine Loecher glatt gefuellt), nichts wird generiert.
Grenzen: Auskragungen/Erker (Band 0,6 m) und regelmaessige Bauteile (Fenster, Boegen, Uhr) bleiben Sache von bauteile.py; generierte Steine sind ANNAHME.
"""
import sys, os, json, glob, argparse, subprocess, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); PY = "/media/oem/scan/venv-seg/bin/python"


def fotos_fuer_wand(od, a, b, n, z0, z1, k=3, max_winkel=65.0):
    """Beste Fotos fuer eine Wandflaeche: Anteil der 5 x 7 Rasterpunkte im Bild x Pixel je Meter x cos(Blickwinkel). Keine Verdeckungspruefung."""
    import cv2
    if HIER not in sys.path: sys.path.insert(0, HIER)                    # kamera_rahmen (Aufruf als Skript mit -I)
    a = np.array(a, float); b = np.array(b, float); G = np.array([[*(a + s * (b - a)), z] for s in np.linspace(0.08, 0.92, 5) for z in np.linspace(z0 + 0.08 * (z1 - z0), z1 - 0.08 * (z1 - z0), 7)]); c = G.mean(0); erg = []
    for f in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
        K = json.load(open(f)).get("kamera")
        if not K or "rvec" not in K or not __import__("kamera_rahmen").kamera_ok(f, K, os.path.dirname(f)): continue      # 23.11.2026: alter Rahmen (kamera_rahmen.py)
        R = cv2.Rodrigues(np.array(K["rvec"]))[0]; t = np.array(K["t"]); S = -R.T @ t; d = S - c; L = float(np.linalg.norm(d)); w = np.degrees(np.arccos(np.clip(d[:2] @ n / max(np.linalg.norm(d[:2]), 1e-9), -1, 1)))
        if w > max_winkel or L > 400: continue
        p = G @ R.T + t; ok = (p[:, 2] > 0); x = K["f_px"] * p[:, 0] / np.where(ok, p[:, 2], 1) + K["cx"]; y = K["f_px"] * p[:, 1] / np.where(ok, p[:, 2], 1) + K["cy"]
        ab = float((ok & (x > 0) & (x < 2 * K["cx"]) & (y > 0) & (y < 2 * K["cy"])).mean())
        if ab >= 0.4: erg.append((ab * min(K["f_px"] / L, 250.0) * np.cos(np.radians(w)), ab, os.path.basename(f)[2:-5]))
    erg.sort(reverse=True); return [e[2] for e in erg[:k]], erg[:k]


def waende_aus_lod2(od, min_laenge):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    D = json.load(open(os.path.join(od, "dach.json"))); teile = [Polygon(t["grundriss_uv"]).buffer(0) for t in D["teile"]]; U = unary_union(teile).buffer(0.05).buffer(-0.05)
    U = max(U.geoms, key=lambda g: g.area) if U.geom_type == "MultiPolygon" else U; zmax = max(float(t.get("beste", {}).get("first") or t.get("dom1_p95") or 10.0) for t in D["teile"])
    P = np.array(U.exterior.coords)[:-1]; m = np.array(U.centroid.coords[0]); W = []
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]; L = float(np.linalg.norm(b - a))
        if L < min_laenge: continue
        t = (b - a) / L; n = np.array([t[1], -t[0]]); n = n if (0.5 * (a + b) - m) @ n > 0 else -n
        W.append(dict(name="w%02d" % len(W), a=a.tolist(), b=b.tolist(), aussen=(0.5 * (a + b) + 10 * n).tolist(), z1=zmax))
    return W


_LOD2 = {}


def lod2_netze(objekt_json):
    """LoD2-Wandpolygone des eigenen Gebaeudes + Netz der Nachbargebaeude (Modellrahmen), je Objekt einmal. (None, None) ohne LoD2 oder wenn die Werkzeuge fehlen."""
    if objekt_json not in _LOD2:
        try:
            sys.path.insert(0, HIER); import fassade_ortho as FO; obj = json.load(open(objekt_json))
            _LOD2[objekt_json] = (FO.lod2_waende(obj)[0], FO.nachbarn_netz(obj)[0]) if obj.get("lod2", {}).get("id") else (None, None)
        except Exception as e: print(f"    LoD2-Wandflaechen nicht lesbar ({type(e).__name__}: {str(e)[:120]}) - Wandhoehe = Firsthoehe wie frueher", flush=True); _LOD2[objekt_json] = (None, None)
    return _LOD2[objekt_json]


def wand_flaeche(objekt_json, A, B, n, px, angebaut=1.0):
    """ECHTE Wandflaeche einer Grundrisskante (17.11.2026, kaufhaus_gk). Vorher galt fuer JEDE Wand 'z bis zum hoechsten Dachpunkt': an der Traufseite ist ueber der Traufe aber Dach.
    Folge am Kaufhaus: die Hauptfassade (Traufe 11,6 m, Feld bis 21 m) hatte '65 % Loecher' > 60 % -> das gute Netz-Relief (Arkaden, Fenster, Figuren) wurde als 'Netz deckt die Wand nicht' VERWORFEN
    und durch Foto-'Quader' ersetzt. Hier: LoD2-WallSurface-Polygone in der Wandebene (Normale < 8 Grad, Abstand < 0,4 m) als Maske im Reliefraster; z1 = ihre Oberkante.
    Dazu 'frei': Zellen, vor denen kein Nachbargebaeude (LoD2) naeher als `angebaut` m steht - angebaute Flaechen (Brandwand) sieht kein Foto, dort zeigte die Fotostufe das NACHBARHAUS.
    Rueckgabe (wand HxW bool, frei HxW bool, z1) im Raster von relief_einsatz (u 0.1..L-0.1, z 0..z1, Zeile 0 oben) oder None (kein LoD2 / keine passende Flaeche)."""
    import cv2
    W_, nb = lod2_netze(objekt_json)
    if not W_: return None
    A = np.asarray(A, float); B = np.asarray(B, float); L = float(np.linalg.norm(B - A)); t = (B - A) / L; pol = []
    for P in W_:
        c = P.mean(0); _, _, V = np.linalg.svd(P - c); pn = V[2][:2]
        if np.linalg.norm(pn) < 0.9 or abs(pn @ n) / np.linalg.norm(pn) < np.cos(np.radians(8.0)) or abs((c[:2] - A) @ n) > 0.4: continue
        u = (P[:, :2] - A) @ t
        if min(u.max(), L) - max(u.min(), 0.0) < 0.2: continue
        pol.append(np.c_[u, P[:, 2]])
    if not pol: return None
    z1 = float(max(q[:, 1].max() for q in pol)); u0 = 0.1; Wn = int(round((L - 0.2) / px)); Hn = int(round(z1 / px)); wand = np.zeros((Hn, Wn), np.uint8)
    if Wn < 2 or Hn < 2: return None
    for q in pol: cv2.fillPoly(wand, [np.c_[(q[:, 0] - u0) / px, Hn - q[:, 1] / px].round().astype(np.int32)], 1)
    wand = wand.astype(bool); frei = wand.copy()
    if nb is not None and wand.any():
        try:
            import trimesh, fassade_ortho as FO
            k = max(1, int(round(0.25 / px))); ii, jj = np.mgrid[0:Hn:k, 0:Wn:k]; uu = u0 + (jj + 0.5) * px; zz = (Hn - ii - 0.5) * px; n3 = np.array([n[0], n[1], 0.0])
            S0 = np.c_[(A[0] + uu * t[0]).ravel(), (A[1] + uu * t[1]).ravel(), zz.ravel()] - n3 * 0.3      # Start 0,3 m hinter der Ebene: die Nachbarwand liegt oft genau in der eigenen Wandebene
            RI = trimesh.ray.ray_pyembree.RayMeshIntersector if hasattr(trimesh.ray, "ray_pyembree") else trimesh.ray.ray_triangle.RayMeshIntersector
            ti, ri = FO.erster_treffer(RI(nb), S0, n3); zu = np.zeros(len(S0), bool)
            if len(ri): nn = np.asarray(nb.face_normals)[ti]; nen = nn @ n3; d_ = np.einsum("ij,ij->i", np.asarray(nb.triangles[:, 0])[ti] - S0[ri], nn) / np.where(np.abs(nen) < 1e-12, 1e-12, nen); zu[ri[(d_ >= 0) & (d_ < angebaut + 0.3)]] = True
            frei &= ~cv2.resize(zu.reshape(ii.shape).astype(np.uint8), (Wn, Hn), interpolation=cv2.INTER_NEAREST).astype(bool)
        except Exception as e: print(f"    Nachbarpruefung ausgefallen ({type(e).__name__}: {str(e)[:120]})", flush=True)
    return wand, frei, z1


def nachbarn_stl(objekt_json, rd):
    """LoD2-Nachbarn als STL im Massstab des Objekt-STL (fuer die Verdeckungspruefung von steine_aus_foto.py --stl). '' ohne LoD2."""
    nb = lod2_netze(objekt_json)[1]
    if nb is None: return ""
    f = os.path.join(rd, "nachbarn_lod2.stl"); m = nb.copy(); m.apply_scale(1000.0 / float(json.load(open(objekt_json)).get("stl_massstab", 87))); m.export(f); return f


def loecher_glatt(rel, zu, max_m2, px):
    """Kleine Loecher (rel == 0, nicht Oeffnung, in der Wand) aus der Umgebung auffuellen (gewichtetes Mittel, 15 cm) - fuer Waende OHNE Quaderwerk statt generierter Steine."""
    import cv2
    from scipy import ndimage as ndi
    lab, m = ndi.label(zu)
    if not m: return rel, 0.0
    gr = ndi.sum(zu, lab, np.arange(1, m + 1)) * px * px; klein = np.isin(lab, 1 + np.flatnonzero(gr < max_m2)); da = (rel != 0.0).astype(np.float32); neu = rel.copy()
    for _ in range(8):                                                    # von den Raendern nach innen
        offen = klein & (da == 0)
        if not offen.any(): break
        g = cv2.GaussianBlur(neu * da, (0, 0), 3.0); wg = cv2.GaussianBlur(da, (0, 0), 3.0); ok = offen & (wg > 0.05); neu[ok] = (g[ok] / wg[ok]); neu[ok & (neu == 0.0)] = 1e-4; da[ok] = 1.0
    return neu.astype(np.float32), float(klein.mean())


def putz_eben(rel, m, px, band=0.05, kachel=1.0):
    """Glatte Wandflaeche (Putz ohne Quaderwerk) aus dem Netz-Relief: Wandniveau = Median je 1-m-Kachel (3x3-Umgebung, nur Wandzellen m), bilinear;
    Zellen naeher als 'band' am Niveau = Wand -> genau auf das Niveau; Rest (Gewaende, Gesimse, Figuren, Pfosten) bleibt, Median 3x3 + Gauss 0,6 Zellen gegen Einzelspitzen.
    GRUND (kaufhaus_gk 17.11.2026, drei Bilder Foto | grob3 Hand | gk Kette): das rohe Netz (Rausch-Sigma 6,6 cm) machte die glatt verputzte Hauptfassade zu 'Brei',
    grob3 hatte glatte Wand + Teile. 5 cm = 0,6 mm bei 1:87 (ANNAHME: Putzunebenheit unter 5 cm ist Netzrauschen, kein Bauteil)."""
    import cv2
    from scipy import ndimage as ndi
    H_, W_ = rel.shape; k = max(2, int(round(kachel / px))); gy = np.arange(0, H_, k); gx = np.arange(0, W_, k); G = np.full((len(gy), len(gx)), np.nan)
    for i, y in enumerate(gy):
        for j, x in enumerate(gx):
            sl = (slice(max(0, y - k), y + 2 * k), slice(max(0, x - k), x + 2 * k)); v = rel[sl][m[sl]]
            if v.size > 20: G[i, j] = np.median(v)
    if np.isnan(G).all(): return rel, 0.0
    G = np.where(np.isnan(G), np.nanmedian(G), G); L = cv2.resize(G.astype(np.float32), (W_, H_), interpolation=cv2.INTER_LINEAR)
    flach = m & (np.abs(rel - L) < band); x = np.where(flach, L, rel); x = cv2.GaussianBlur(ndi.median_filter(x, 3).astype(np.float32), (0, 0), 0.6)
    return np.where(m, x, rel).astype(np.float32), float(flach.sum() / max(m.sum(), 1))


def wandniveau(rel, m, px, kachel=1.0):
    """Wandniveau je Zelle = Median je kachel-m-Kachel (3x3-Umgebung, nur Zellen m), bilinear (wie putz_eben; ohne cv2, laeuft auch in der Generator-Umgebung)."""
    from scipy.interpolate import RegularGridInterpolator
    H_, W_ = rel.shape; k = max(2, int(round(kachel / px))); gy = np.arange(0, H_, k); gx = np.arange(0, W_, k); G = np.full((len(gy), len(gx)), np.nan)
    for i, y in enumerate(gy):
        for j, x in enumerate(gx):
            sl = (slice(max(0, y - k), y + 2 * k), slice(max(0, x - k), x + 2 * k)); v = rel[sl][m[sl]]
            if v.size > 20: G[i, j] = np.median(v)
    if np.isnan(G).all(): return None
    G = np.where(np.isnan(G), np.nanmedian(G), G)
    if len(gy) < 2 or len(gx) < 2: return np.full((H_, W_), float(np.median(G)), np.float32)
    f = RegularGridInterpolator((gy + k / 2.0, gx + k / 2.0), G, bounds_error=False, fill_value=None)
    yy, xx = np.meshgrid(np.arange(H_), np.arange(W_), indexing="ij"); return f(np.c_[np.clip(yy.ravel(), gy[0] + k / 2.0, gy[-1] + k / 2.0), np.clip(xx.ravel(), gx[0] + k / 2.0, gx[-1] + k / 2.0)]).reshape(H_, W_).astype(np.float32)


def relief_bereinigen(f_in, f_out, ersetzt=(), band=0.05, lang=1.5, dick=0.45, erhalten=(), fuell=0.5):
    """RESTBREI WEG (17.11.2026 Runde 3, kaufhaus_gk: zwischen den Fenstern der Hauptfassade blieben nach putz_eben wellige Netzklumpen 5-30 cm stehen, Foto zeigt glatten Putz).
    Auf einem fertigen Relief (<wand>_voll.npz, Wand ohne Quaderwerk) jede Abweichung >= band vom Wandniveau (wandniveau) als zusammenhaengendes Stueck pruefen:
      BLEIBT, wenn linienhaft: waagerecht (Breite >= lang, Hoehe <= dick: Gesims, Band) oder senkrecht (Hoehe >= lang, Breite <= dick: Gewaende, Lisene)
              UND gerade (fuellt >= fuell seines Rahmens; wellige Breistreifen fuellen weniger),
              oder im Rechteck 'erhalten' (u0, u1, z0, z1 in Reliefkoordinaten).
      FAELLT (auf das Wandniveau), wenn klumpig (Netzrauschen, Figurenbrei) oder in einem Rechteck 'ersetzt' (dort baut der Generator das Bauteil aus Fotomassen:
              Fenster mit Gewaende, Balkon, Figuren, Laube - das Netz-Relief davor waere doppelt).
    ersetzt/erhalten = Liste (u0, u1, z0, z1) in Reliefkoordinaten (u entlang Z['t'] ab Z['a'], z absolut). Schreibt f_out (+ .jpg Schummerung), Rueckgabe dict Anteile.
    ANNAHME: linienhafte Formen im Netz sind echte Bauteile (Gesimse/Gewaende), Klumpen ohne Bauteil-Beleg sind Rauschen; Figuren kommen als eigene Bauteile (Klipsteile)."""
    from scipy import ndimage as ndi
    Z = dict(np.load(f_in)); rel = Z["rel"].astype(np.float32); px = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"]); H_, W_ = rel.shape
    wand = Z["wand"] if "wand" in Z else np.ones_like(rel, bool); m = wand & ~Z["oeffnung"] & (rel > 0.0)
    L = wandniveau(rel, m & (rel > 0.011), px)
    if L is None: return dict(unveraendert=True)
    def recht(u_a, u_b, z_a, z_b):
        r = np.zeros_like(m); j0, j1 = int(max(0, (u_a - u0) / px)), int(min(W_, np.ceil((u_b - u0) / px))); i0, i1 = int(max(0, H_ - (z_b - z0) / px)), int(min(H_, np.ceil(H_ - (z_a - z0) / px)))
        if j1 > j0 and i1 > i0: r[i0:i1, j0:j1] = True
        return r
    ers = np.zeros_like(m); erh = np.zeros_like(m)
    for q in ersetzt: ers |= recht(*q)
    for q in erhalten: erh |= recht(*q)
    D = m & ~ers & (np.abs(rel - L) >= band); lab, n = ndi.label(D, np.ones((3, 3)))     # Stuecke OHNE die Bauteilflaechen beurteilen (sonst bleiben angeschnittene Reste eines 'senkrechten' Klumpens stehen)
    weg = np.zeros_like(m); n_lin = 0
    for k, sl in enumerate(ndi.find_objects(lab), 1):
        if sl is None: continue
        h = (sl[0].stop - sl[0].start) * px; b = (sl[1].stop - sl[1].start) * px; c = lab[sl] == k
        linie = ((b >= lang and h <= dick) or (h >= lang and b <= dick)) and c.mean() >= fuell     # gerade Leiste fuellt ihren Rahmen; welliger Brei-Streifen nicht
        if (erh[sl] & c).any() or linie: n_lin += 1; continue
        weg[sl] |= c
    weg = (weg | (ers & m)) & ~erh; weg = ndi.binary_dilation(weg, np.ones((3, 3), bool)) & m & ~erh   # Rand der Klumpen mit
    neu = np.where(weg, L, rel).astype(np.float32); neu[ers & m] = L[ers & m]; Z["rel"] = neu; np.savez_compressed(f_out, **Z)
    from PIL import Image
    lx = np.gradient(neu, px, axis=1); lz = np.gradient(neu, px, axis=0); g_ = (np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1) * 255).astype(np.uint8); im_ = np.stack([g_] * 3, -1)
    im_[~wand] = (90, 90, 90); im_[Z["oeffnung"] & wand] = (0, 60, 120); im_[weg & ~ers] = (im_[weg & ~ers] * 0.6 + np.array([120, 0, 0])).astype(np.uint8); im_[ers & m] = (im_[ers & m] * 0.6 + np.array([0, 0, 110])).astype(np.uint8)
    Image.fromarray(np.repeat(np.repeat(im_, 3, 0), 3, 1)).save(f_out[:-4] + ".jpg", quality=88)     # rotstichig = Brei entfernt, blaustichig = durch Fotobauteil ersetzt (beides auf Wandniveau)
    return dict(brei_weg=round(float((weg & ~ers).sum() / max(m.sum(), 1)), 3), ersetzt=round(float((ers & m).sum() / max(m.sum(), 1)), 3), linienhaft_behalten=n_lin)


def relief_roh(r0, r2, px, putz_band=0.05):
    """Wand OHNE Quaderwerk: Netz-Relief unveraendert als <wand>_voll.npz. Kleine Loecher glatt, Oeffnungen (Loch mit Netz dahinter: Arkade, Tor) auf das tiefste Niveau (Ruecksprung statt Wandflaeche),
    'vorstand' = das ganze Relief so weit vor die Wandebene, dass sein tiefster Ruecksprung 1 cm davor liegt (hoechstens Klemme + 1 cm = 11 cm = 1,3 mm bei 1:87), OHNE den Ebenentrend des Netzes.
    GRUND (kaufhaus_gk 17.11.2026, Bild Modell neben Foto): die Netzflaeche lag im Mittel 1,5 cm HINTER der LoD2-Ebene - alles unter der Ebene verschwand im Grundkoerper, von Fenstern/Arkaden blieben nur
    ein paar Grate. Mit Trend waeren es 25-81 cm Vorstand geworden (LoD2-Ebene der Seitenstreifen 23-34 cm neben dem Netz, Neigung bis 10 cm/m) - die LAGE bleibt deshalb die des Grundkoerpers (LoD2),
    das Netz liefert nur die Form. Der Vorstand ist Darstellung, kein Mass (ANNAHME)."""
    import cv2
    Zr = dict(np.load(r0)); H_, W_ = Zr["rel"].shape; wand = Zr["wand"] if "wand" in Zr else np.ones((H_, W_), bool); zu = (Zr["rel"] == 0.0) & ~Zr["oeffnung"] & wand
    Zr["rel"], gef = loecher_glatt(Zr["rel"], zu, 1.5, px); da = wand & (Zr["rel"] != 0.0); eben = 0.0
    if putz_band: Zr["rel"], eben = putz_eben(Zr["rel"], da & ~Zr["oeffnung"], px, band=putz_band); Zr["rel"][~da] = 0.0      # 17.11.2026 glatter Putz statt Netzrauschen (putz_eben)
    tief = float(Zr["rel"][da].min()) if da.any() else 0.0; vor = round(0.01 - tief, 3)
    loch = (Zr["rel"] == 0.0) & wand & ~Zr["oeffnung"]; neu = np.where(wand, Zr["rel"] + vor, 0.0); neu[Zr["oeffnung"] & wand] = 0.01      # Oeffnung = tiefster Ruecksprung; grosse Loecher = mittlere Wandflaeche; ausserhalb der Wand nichts
    Zr["rel"] = neu.astype(np.float32); Zr["loch"] = loch; Zr["generiert_anteil"] = 0.0; np.savez_compressed(r2, **Zr)
    lx = np.gradient(neu, px, axis=1); lz = np.gradient(neu, px, axis=0); im_ = cv2.cvtColor((np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR); im_[loch] = (0, 0, 255); im_[Zr["oeffnung"] & wand] = (120, 60, 0); im_[~wand] = (90, 90, 90)
    cv2.imwrite(r2[:-4] + ".jpg", cv2.resize(im_, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))      # rot = Loch in der Wand (bleibt glatt), blau = Oeffnung (Ruecksprung), dunkelgrau = keine Wand (Dach, Himmel, Nachbar)
    return dict(gefuellt=round(gef, 3), generiert=0.0, vorstand=vor, ohne_trend=True, putz_eben=round(eben, 3), putz_band=putz_band)


_NETZ = {}


def netz_vorn(netz, r0, band=0.6, weit=2.0):
    """Maske 'vorn' ins Relief r0: Zellen, in denen das Netz VOR dem Suchband der Wand steht (band .. band + weit m vor der Ebene) = dort steht etwas vor der Wand (Erker, Balkon, Vordach;
    unten auch Marktstand/Baum). relief_einsatz.py kennt nur 'Netz dahinter' (Oeffnung). Fuer fenster_fuer_bau: ein erkanntes Fenster hinter einem Vorbau wird nicht in die Wand geschnitten."""
    import cv2
    if netz not in _NETZ: Zn = np.load(netz); _NETZ[netz] = Zn["V"].astype(np.float64)[Zn["F"]].mean(1)
    c = _NETZ[netz]; Z = dict(np.load(r0)); H, W = Z["rel"].shape; px = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"]); uu = (c[:, :2] - Z["a"][:2]) @ Z["t"][:2]; dd = (c[:, :2] - Z["a"][:2]) @ Z["n"][:2]
    g = (uu > u0) & (uu < u0 + W * px) & (dd > band) & (dd < band + weit) & (c[:, 2] > z0) & (c[:, 2] < z0 + H * px); v = np.zeros((H, W), np.uint8)
    v[np.clip((H - 1 - (c[g, 2] - z0) / px).astype(int), 0, H - 1), np.clip(((uu[g] - u0) / px).astype(int), 0, W - 1)] = 1
    Z["vorn"] = cv2.morphologyEx(v, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool); np.savez_compressed(r0, **Z); return float(Z["vorn"].mean())


def fenster_fuer_bau(objekt_json, fenster_json, vorbau=0.3):
    """Erkannte Fenster (audit/fenster_auto.json) gegen das Netz-Relief der Wand pruefen -> audit/fenster_bau.json (Pfad zurueck; ohne Kette/Relief der unveraenderte Pfad).
    Ein 'Fenster', in dessen Rechteck auf > `vorbau` der Flaeche Netz VOR der Wand steht (Maske 'vorn' von netz_vorn: 0,6-2,6 m vor der Ebene), liegt hinter einem Vorbau (Erker, Balkon):
    es wird NICHT als Loch in die Wand geschnitten (kaufhaus_gk 17.11.2026: die zwei Eckerker der Hauptfassade standen als 2,3 m breite 'Fenster' in der Liste). Netz = Lage-Veto, kein Mass."""
    od = os.path.dirname(os.path.abspath(objekt_json)); B = os.path.join(od, "audit", "fassaden_kette.json")
    if not os.path.exists(B) or not os.path.exists(fenster_json): return fenster_json
    D = json.load(open(fenster_json)); R = []
    for w in json.load(open(B))["waende"]:
        f = os.path.join(od, "relief", w["name"] + ".npz")
        if w.get("aus") or w.get("nur_foto") or not os.path.exists(f): continue
        Z = np.load(f); R.append((Z["a"], Z["t"], Z["n"], float(Z["u0"]), float(Z["z0"]), float(Z["px"]), Z["vorn"] if "vorn" in Z.files else np.zeros(Z["rel"].shape, bool), w["name"]))
    if not R: return fenster_json
    n_weg = 0
    for fid, F in D.items():
        o = np.array(F["o"], float); d = np.array(F["d"], float); n = np.array(F["n"], float)
        for fe in F.get("fenster", []):
            for A, t, nw, u0, z0, px, loch, name in R:
                if n @ nw[:2] < 0.95 or abs((o + 0.5 * (fe["u0"] + fe["u1"]) * d - A[:2]) @ nw[:2]) > 0.6: continue
                ua, ub = sorted(((o + fe["u0"] * d - A[:2]) @ t[:2], (o + fe["u1"] * d - A[:2]) @ t[:2])); H, W = loch.shape
                j0, j1 = int(max((ua - u0) / px, 0)), int(min((ub - u0) / px, W)); i0, i1 = int(max(H - (fe["z1"] - z0) / px, 0)), int(min(H - (fe["z0"] - z0) / px, H))
                if j1 - j0 < 2 or i1 - i0 < 2: continue
                fe["netz_davor"] = round(float(loch[i0:i1, j0:j1].mean()), 2); fe["wand"] = name
                if fe["netz_davor"] > vorbau: fe["vorbau"] = True; n_weg += 1
                break
        F["fenster_vorbau"] = [fe for fe in F.get("fenster", []) if fe.get("vorbau")]; F["fenster"] = [fe for fe in F.get("fenster", []) if not fe.get("vorbau")]
    aus = os.path.join(od, "audit", "fenster_bau.json"); json.dump(D, open(aus, "w"), indent=1, ensure_ascii=False); print(f"fenster_fuer_bau: {sum(len(F['fenster']) for F in D.values())} Fenster zum Bauen, {n_weg} hinter einem Vorbau (Netz vor der Wand) zurueckgestellt -> {aus}")
    return aus


def koerper_flaeche(basis, a, t, n, felder, w_aussen=1.0, w_innen=-1.5, schritt=0.01):
    """Lage der Koerperflaeche vor einer Wandebene (a, t, n) messen: je Probe (u, z) die aeusserste Tiefe w, bei der ein 10-cm-Stab von w bis w_aussen den Koerper trifft
    (Halbierung). Liefert den Median der getroffenen Proben (Fensterloecher/Vorbauten fallen als Ausreisser heraus) oder None."""
    from manifold3d import Manifold as M_
    a = np.asarray(a, float); t = np.asarray(t, float); n = np.asarray(n, float); ws = []
    for u, z in felder:
        def trifft(w):
            k = M_.hull_points([[*(a + uu * t + ww * n), zz] for uu in (u - 0.05, u + 0.05) for ww in (w, w_aussen) for zz in (z - 0.05, z + 0.05)])
            return (basis ^ k).volume() > 1e-7
        if not trifft(w_innen): continue
        lo, hi = w_innen, w_aussen                       # trifft(lo) = True, trifft(hi) = False
        while hi - lo > schritt:
            m_ = 0.5 * (lo + hi)
            if trifft(m_): lo = m_
            else: hi = m_
        ws.append(lo)
    return float(np.median(ws)) if ws else None


def fein_ordner(objekt_json):
    """Ordner des feinen Wandbilds (Kettenstufe fenster: fassade_ortho --zelle 0.01 --einzeln -> <daten>/fassade_fein). objekt.json 'fassade_fein' (relativ zum Repo oder absolut)
    geht vor, sonst /media/oem/scan/rc-park_daten/<objektordner>/fassade_fein wie tools/gesamtkette.py. '' wenn nicht da."""
    od = os.path.dirname(os.path.abspath(objekt_json)); q = json.load(open(objekt_json)).get("fassade_fein")
    for p in ([q if os.path.isabs(q) else os.path.join(os.path.dirname(os.path.dirname(od)), q)] if q else []) + [os.path.join("/media/oem/scan/rc-park_daten", os.path.basename(od), "fassade_fein")]:
        if os.path.exists(os.path.join(p, "fassaden.json")): return p
    return ""


def uhren_frei(od, Z, parallel=0.95, abstand=1.0):
    """Uhrscheiben aus audit/uhren_auto.json (tools/uhren_wandbild.py) als Kreise (u, z, r) im Relief-Raster Z, wenn ihre Fassade zu dieser Wand passt.
    Dort baut bauteile.uhren_aus_json das Zifferblatt - Netz-Relief davor waere doppelt (Nutzerbild 21.11.: Uhr nur flacher Kreis im Relief)."""
    f = os.path.join(od, "audit", "uhren_auto.json")
    if not os.path.exists(f): return []
    a = np.asarray(Z["a"], float)[:2]; t = np.asarray(Z["t"], float)[:2]; nw = np.asarray(Z["n"], float)[:2]; r = []
    for F in json.load(open(f)).values():
        o = np.asarray(F["o"], float); d = np.asarray(F["d"], float); n = np.asarray(F["n"], float)
        if n @ nw < parallel: continue
        for U in F.get("uhren", []):
            p = o + float(U["u"]) * d
            if abs((p - a) @ nw) <= abstand: r.append((float((p - a) @ t), float(U["z"]), 0.5 * float(U["d_aussen"]) + 0.05))
    return r


def steinzone_oben(rel, putz, px, anteil=0.3, sockel=1.5, max_z=12.0):
    """Oberkante (m ueber z0) der Steinzone fuer die lokale Feinrechnung: Zeilen mit >= anteil echtem Nicht-Putz-Relief, zusammenhaengender Block von unten, hoechstens max_z.
    Unterste 'sockel' m zaehlen immer mit (Strassenrand, Sockel). 23.11.2026 (Kette 1122t, Schwabentor West w00): unten fehlte das Netz 1,55 m (Leerstreifen,
    darueber 2-4 Zeilen Uebergang mit 20-30 % Relief), die alte Schleife brach an der ersten Zeile nach 1,5 m ab -> 1,5 m < 2 m -> KEINE Feinrechnung,
    obwohl die Quaderzone 2-8,5 m zu 98 % Relief hat. Jetzt: es zaehlt der hoechste Steinblock, der im Sockel ODER hoechstens 'sockel' m darueber beginnt
    (Leerstreifen = fehlendes Netz, keine Putzgrenze); Putzzeilen (Putzmaske) beenden den Block wie bisher. Steine erst weiter oben -> wie bisher nur der Sockel."""
    rel = np.asarray(rel); H_ = rel.shape[0]
    pz = np.zeros_like(rel, bool) if putz is None else np.asarray(putz, bool)
    if pz.shape[0] < H_: pz = np.vstack([pz, np.zeros((H_ - pz.shape[0], pz.shape[1]), bool)])
    stein = (((rel != 0) & ~pz[:H_]).mean(1) >= anteil)[::-1]                  # Index 0 = unterste Zeile
    ns = int(round(sockel / px)); stein[:min(ns, H_)] = True                   # Sockel zaehlt immer mit (wie bisher)
    oben = min(ns, H_); i = 0                                                    # hoechstes Ende eines Steinblocks, der spaetestens 'sockel' m ueber dem Sockel beginnt
    while i < min(2 * ns, H_):                                                   # (einzelne Zufallszeilen im Uebergang sind kurze Bloecke - der hoechste zaehlt)
        if stein[i]:
            j = i
            while j < H_ and stein[j]: j += 1
            oben = max(oben, j); i = j
        else: i += 1
    return round(min(oben * px, max_z), 2)


def wandende_ist_ecke(waende, w, ende, abstand=0.8, parallel=0.95):
    """Gebaeudeecke = Wandende ('a'/'b'), an dem KEINE gleichgerichtete Nachbarwand weiterlaeuft (Ende an Anfang innerhalb 'abstand' m, |cos| >= parallel).
    Wandabschnitte derselben Flucht (eine Fassade in mehrere LoD2-Stuecke zerlegt) sind so keine Ecke (21.11.2026, Eckquader-Erkennung)."""
    p = np.asarray(w[ende], float); d = np.asarray(w["b"], float) - np.asarray(w["a"], float); d /= np.linalg.norm(d) + 1e-9
    for v in waende:
        if v is w or v.get("name") == w.get("name"): continue
        e_ = np.asarray(v["b"], float) - np.asarray(v["a"], float); e_ /= np.linalg.norm(e_) + 1e-9
        if abs(float(e_ @ d)) < parallel: continue
        if min(np.linalg.norm(np.asarray(v["a"], float) - p), np.linalg.norm(np.asarray(v["b"], float) - p)) <= abstand: return False
    return True


_CODEFEHLER = []   # Programmierfehler in abgefangenen Teilschritten -> Stufe rot (wie Teilwerkzeug-Absturz)


def quadern(f, objekt_json, Z_basis, art, ecken=(False, False)):
    """Quaderraster aus dem Wandbild auf ein gebautes Relief (tools/quader_raster.py, 21.11.2026): je Stein ebene Stirnflaeche (Median der Tiefe), druckbare Rillen.
    art: 'fein' (mono/misch, Steinzone unten), 'foto' (Fotorelief: nur wo es Stein ist), 'wand' (Wand ohne Quader-Tor: nur Steinzone von unten).
    Liefert (pfad, info) - pfad = f, wenn nichts zu tun ist (kein Wandbild, kein Raster) oder OHNE_QUADER_RASTER=1."""
    if os.environ.get("OHNE_QUADER_RASTER") == "1" or not f or not os.path.exists(f): return f, None
    ffn = fein_ordner(objekt_json)
    if not ffn: return f, None
    sys.path.insert(0, HIER); from quader_raster import quader_datei
    od = os.path.dirname(os.path.abspath(objekt_json)); Zf = np.load(f)
    kw = dict(vorn_quelle=dict(Z_basis) if Z_basis is not None and "vorn" in Z_basis.files else None, frei=uhren_frei(od, Zf))
    if art == "foto": kw["nur_in"] = np.asarray(Zf["rel"]) > (float(Zf["putz_niveau_m"]) if "putz_niveau_m" in Zf.files else 0.0) + 0.01
    if art == "wand": kw["zone_unten"] = True
    if any(ecken): kw["rand_ecke"] = tuple(ecken)                         # Eckquader am Gebaeudeende: Bloecke mit gemessener Hoehe/Laenge
    oa_ = os.path.join(od, "audit", "oeffnungen_auto.json")                # 21.11.2026 spaet: Boegen (Form/Lage aus Wandbild-Kanten) -> Keilsteine mit radialen Fugen
    if os.path.exists(oa_) and os.environ.get("OHNE_KEILSTEINE") != "1":
        try: kw["boegen"] = {fid: [x for x in F_.get("oeffnungen", []) if x.get("form", "gerade") != "gerade" and all(k in x for k in ("u", "breite", "kaempfer", "scheitel"))]
                             for fid, F_ in json.load(open(oa_)).items() if isinstance(F_, dict)}
        except Exception as e: print(f"    quader_raster: oeffnungen_auto.json nicht lesbar ({type(e).__name__}) - ohne Keilsteine", flush=True)
    try: p, info = quader_datei(f, ffn, **kw)
    except Exception as e:
        print(f"    quader_raster {os.path.basename(f)}: FEHLER {type(e).__name__}: {str(e)[:160]} - Relief unveraendert", flush=True)
        if isinstance(e, (NameError, TypeError, AttributeError, IndexError, KeyError, ValueError)): _CODEFEHLER.append(f"quader_raster {os.path.basename(f)}: {type(e).__name__}: {str(e)[:120]}")   # 22.11.2026: Lauf 1122a - UnboundLocalError fiel als Warnung durch, Stufe 'in Ordnung', Quader weg
        return f, None
    if p != f: print(f"    quader_raster {os.path.basename(f)}: {info.get('relief_steine')} Steine, Rillen {info.get('relief_rille_mm')} mm, Bild {os.path.basename(p)[:-4]}.jpg", flush=True)
    return p, (info if p != f else None)


def anbauen(koerper, objekt_json, tiefe=0.4, fenster=None, bereinigen=None):
    """Fuer Generatoren: alle relief/*_voll.npz der Fassaden-Kette als Platten anfuegen, begrenzt auf die nach aussen verschobene Koerperhuelle.
    fenster = Pfad der Fensterliste (fenster_fuer_bau), wenn die Fenster VOR dem Relief geschnitten wurden: die Reliefplatte bleibt dann in den Fensterrechtecken offen.
    GRUND (kaufhaus_gk 17.11.2026): bauteile.fenster_aus_json laesst Fenster aus, vor denen im Modell etwas steht - nach dem Relief gebaut fielen 5 von 9 erkannten Fenstern weg (Platte davor),
    mit dem Netz-Relief der Hauptfassade alle. Reihenfolge im Generator daher: fenster_aus_json(koerper, FJ) -> anbauen(koerper, OBJ, fenster=FJ) -> aushoehlen.
    bereinigen (17.11.2026 Runde 3) = dict(ersetzt=[(Wand, u0, u1, z0, z1) oder ("rund", (x, y), r, z0, z1)], erhalten=[...], band, lang, dick) oder {}: Waende ohne Quaderwerk (quader False/None) vorher
    durch relief_bereinigen (Restbrei weg, Bauteil-Rechtecke auf Wandniveau) -> relief/<wand>_rein.npz/.jpg; Wand = bauteile.Wand der Bauteile (Rechtecke werden auf
    die Reliefwand umgerechnet, nur gleiche Richtung n.n > 0,9 und Abstand < 1,5 m)."""
    sys.path.insert(0, HIER); from relief_einsatz import koerper as relief_koerper
    od = os.path.dirname(os.path.abspath(objekt_json)); B = os.path.join(od, "audit", "fassaden_kette.json")
    if not os.path.exists(B): return koerper, []
    frei = []
    if fenster and os.path.exists(fenster):
        from bauteile import Wand
        for F_ in json.load(open(fenster)).values():
            o_ = np.array(F_["o"], float); W_ = Wand(o_, o_ + np.array(F_["d"], float), aussen=o_ + np.array(F_["n"], float))
            frei += [(np.array(F_["n"], float), W_.kasten(q_["u0"], q_["u1"], q_["z0"], q_["z1"], -tiefe - 0.2, 1.0)) for q_ in F_.get("fenster", [])]
    belege = []; basis = koerper      # 16.11.2026: Huelle je Wand aus dem GRUNDKOERPER, nicht aus dem wachsenden Koerper (sonst wird jede weitere Wand gegen alle frueheren Reliefs geschnitten: schwab_auto, 8 Waende, 13,6 GB -> vom System beendet)
    for w in json.load(open(B))["waende"]:
        f = os.path.join(od, "relief", w["name"] + "_voll.npz")
        if not os.path.exists(f) or w.get("aus"): continue
        Z = np.load(f); n = Z["n"]; hu = basis + basis.translate((0.8 * n[0], 0.8 * n[1], 0.0)); koerper.num_tri();      # num_tri: Zwischenergebnis ausrechnen, damit der Rechenbaum nicht ueber alle Waende waechst
        fm = os.path.join(od, "relief", w["name"] + "_misch.npz"); tf = [tuple(w["fein_feld"])] if w.get("fein_feld") and os.path.exists(fm) else []
        ff = os.path.join(od, "relief", w["name"] + "_foto.npz"); hat_foto = bool(w.get("foto_feld")) and os.path.exists(ff)
        # 21.11.2026 (Kettenluecke 2, Nutzer: "was wir damals manuell gemacht haben, muss jetzt automatisch laufen"): Stufe 'mono' rechnet <wand>_mono.npz, gebaut wurde es nur von
        # Hand (schwab_v3_gen Z.85-95). Wie dort: Feld der Mono-Datei = tief_feld des groben Reliefs, Mono-Relief mit trend=True, rand_auslauf=False; die Feinrechnung (_misch)
        # steckt im Tiefpass der Mono-Datei und entfaellt dann. OHNE_MONO=1 schaltet ab.
        fmo = os.path.join(od, "relief", w["name"] + "_mono.npz"); mono_ = (w.get("mono") or {}).get("datei") and os.path.exists(fmo) and os.environ.get("OHNE_MONO") != "1"
        if mono_:
            zm_ = np.load(fmo); hm_, wm_ = zm_["rel"].shape; pm_ = float(zm_["px"]); feld_mo = (float(zm_["u0"]), float(zm_["u0"]) + wm_ * pm_, float(zm_["z0"]), float(zm_["z0"]) + hm_ * pm_); tf = [feld_mo]
        def offen(pl):                                                   # Fensterrechtecke dieser Wandrichtung aus der Platte nehmen
            for nf_, k_ in frei:
                if nf_ @ n[:2] > 0.9: pl = pl - k_
            return pl
        if bereinigen is not None and w.get("quader") is not True and not w.get("nur_foto"):
            def um(lst):
                r = []
                for W_, a_, b_, za, zb in lst:
                    if isinstance(W_, str):                                      # ("rund", Mitte xy, Radius, z0, z1): senkrechter Zylinder (Erker) - auf JEDE nahe Wand projiziert
                        c_ = np.asarray(a_, float) - Z["a"][:2]
                        if abs(c_ @ n[:2]) <= b_ + 0.5: uc = c_ @ Z["t"][:2]; r.append((uc - b_, uc + b_, za, zb))
                        continue
                    if W_.n @ n[:2] < 0.9 or abs((W_.a + 0.5 * (a_ + b_) * W_.t - Z["a"][:2]) @ n[:2]) > 1.5: continue
                    ua, ub = sorted(((W_.a + a_ * W_.t - Z["a"][:2]) @ Z["t"][:2], (W_.a + b_ * W_.t - Z["a"][:2]) @ Z["t"][:2])); r.append((ua, ub, za, zb))
                return r
            f2 = os.path.join(od, "relief", w["name"] + "_rein.npz")
            info = relief_bereinigen(f, f2, um(bereinigen.get("ersetzt", [])), band=bereinigen.get("band", 0.05), lang=bereinigen.get("lang", 1.5), dick=bereinigen.get("dick", 0.45), erhalten=um(bereinigen.get("erhalten", [])))
            if not info.get("unveraendert"):
                f = f2; belege.append(dict(seite="wand", element=f"Relief Fassade {w['name']}: Restbrei auf Wandniveau, Bauteilflaechen ersetzt", quelle="fassaden_kette.relief_bereinigen (Netz-Relief, linienhafte Formen bleiben)",
                                           hinweis=f"ANNAHME: Klumpen ohne Bauteil = Netzrauschen; Brei weg {info['brei_weg'] * 100:.0f} %, durch Fotobauteile ersetzt {info['ersetzt'] * 100:.0f} %, {info['linienhaft_behalten']} linienhafte Stuecke behalten; Bild relief/{w['name']}_rein.jpg"))
        fl_w = None
        if w.get("quader") is False and not w.get("nur_foto") and os.environ.get("OHNE_PUTZ_WANDBILD") != "1":
            # 21.11.2026 (Nutzerbild umgang_bau_ansicht, w02 Stadtseite): Putzwand ohne Quaderwerk. (a) 'Kruemel' auf dem glatten Putz = Netzrauschen auf texturarmem Putz
            # (39 % Netzloecher, Einzelzellen 5-15 cm daneben; putz_eben liess > 5 cm stehen). Putz jetzt aus dem WANDBILD (tools/putz_wandbild.py: mehrere entzerrte Einzelfotos
            # einig glatt) -> dort ein Niveau; die Uhrscheiben (audit/uhren_auto.json) baut bauteile.uhren_aus_json, dort ebenfalls Niveau.
            # (b) das Relief stand ohne Trend auf der LoD2-Ebene (+0,11 m Vorstand), die gemessene Koerperflaeche lag nach der Abweichungsschleife bei -0,15 m (Platte 0,26 m davor);
            # jetzt Putzniveau genau auf die gemessene Koerperflaeche (koerper_flaeche). RELIEF_LOD2_EBENE=1 = alter Stand.
            ffn = fein_ordner(objekt_json)
            if ffn:
                from putz_wandbild import putz_auf_relief, relief_putz_glatt
                M_ = putz_auf_relief(np.load(f), ffn)
                if M_ is not None:
                    f3 = os.path.join(od, "relief", w["name"] + "_glatt.npz"); info = relief_putz_glatt(f, f3, M_, frei=uhren_frei(od, Z))
                    if not info.get("unveraendert"):
                        f = f3; belege.append(dict(seite="wand", element=f"Putz Fassade {w['name']} glatt aus dem Wandbild ({info['putz_anteil'] * 100:.0f} % der Wand, {info['frei']} Uhrfeld(er) frei)",
                                                   quelle="tools/putz_wandbild.py: entzerrte Einzelfotos (fassade_fein/ortho_<fid>_einzeln), Putz = >= 3 Fotos sehen die Zelle und >= 60 % davon ohne Feinstruktur",
                                                   putz_anteil=info["putz_anteil"], rausch_vorher_cm=info["rausch_vorher_cm"], hinweis=f"Netzrauschen auf dem Putz vorher {info['rausch_vorher_cm']} cm (Streuung); relief/{w['name']}_glatt.jpg ansehen"))
            if os.environ.get("RELIEF_LOD2_EBENE") != "1":
                Zf_ = np.load(f); hh_, ww_ = Zf_["rel"].shape; px_ = float(Zf_["px"]); u0_, z0_ = float(Zf_["u0"]), float(Zf_["z0"])
                fl_w = koerper_flaeche(basis, Zf_["a"], Zf_["t"], Zf_["n"], [(u0_ + fu * ww_ * px_, z0_ + fz * hh_ * px_) for fu in (0.3, 0.5, 0.7) for fz in (0.3, 0.6, 0.9)])
                if fl_w is not None and "putz_niveau_m" not in Zf_.files:          # Relief ohne Putzniveau (kein Wandbild): Niveau = Median der Wandzellen (relief_roh: 'vorstand')
                    mw_ = (Zf_["wand"] if "wand" in Zf_.files else np.ones(Zf_["rel"].shape, bool)) & ~Zf_["oeffnung"] & (Zf_["rel"] > 0); fl_w -= float(np.median(Zf_["rel"][mw_])) if mw_.any() else 0.0
                if fl_w is not None: belege.append(dict(seite="wand", element=f"Relief Fassade {w['name']} auf der gemessenen Koerperflaeche ({fl_w:+.2f} m zur Wandebene)", quelle="fassaden_kette.koerper_flaeche (Stab-Sonde gegen den Grundkoerper nach Wandversatz)", relief_auf_flaeche_m=round(fl_w, 3)))
        if os.environ.get("OHNE_VORBAU_FLACH") != "1":
            # 21.11.2026 (Nutzerbild neben_eigen__IMG_20261106_113231: Wandgemaelde unter dem Vordach als Klumpen): hinter/unter Vorbauten Relief nur mit Tiefensprung in den
            # triangulierten Fotokanten der Wandebene (putz_wandbild.relief_vorbau_flach); gilt fuer das Netzrelief und das Fotorelief. OHNE_VORBAU_FLACH=1 = alter Stand.
            from putz_wandbild import vorbau_zonen, kanten_wand, relief_vorbau_flach
            ffn_ = fein_ordner(objekt_json); ej_ = os.path.join(os.path.dirname(ffn_), "ebenen", "ebenen.json") if ffn_ else ""
            for art_ in (("f", f), ("ff", ff if hat_foto else None)):
                if not art_[1]: continue
                Zv_ = np.load(art_[1]); zon_ = vorbau_zonen(od, Zv_)
                if not zon_: continue
                fo_ = art_[1][:-4] + "_vorbau.npz"; inf_ = relief_vorbau_flach(art_[1], fo_, zon_, kanten_wand(ej_, Zv_) if ej_ else None)
                if inf_.get("unveraendert") or not inf_.get("flach_m2"): continue
                if art_[0] == "f": f = fo_
                else: ff = fo_
                belege.append(dict(seite="wand", element=f"Relief {os.path.basename(art_[1])} hinter Vorbau: {inf_['flach_m2']} m2 ohne Kantenbeleg auf Wandniveau, {inf_['belegt_m2']} m2 Tiefensprung belegt",
                                   quelle="putz_wandbild.relief_vorbau_flach (Fotokanten der Wandebene, ebenen.json)", hinweis=f"Bild relief/{os.path.basename(fo_)[:-4]}.jpg; Zone {inf_['zone_m2']} m2"))
        # 21.11.2026 QUADERRASTER aus dem Wandbild (Nutzer: unterer Turm "geschmolzen", Eckquader "Rauschen"): Reliefs wurden 1:1 gebaut - Fugen 0,1-0,4 mm H0,
        # Beulen bis 1 mm H0. Jetzt je Stein ebene Stirnflaeche + druckbare Rillen; Wand ohne Quader-Tor (w02: unten Quader, oben Putz) nur in der Steinzone von unten.
        qbel = []
        if w.get("quader") is False and not w.get("nur_foto"):
            f, qi_ = quadern(f, objekt_json, Z, "wand"); qbel.append(("Wand", qi_))
        if hat_foto:
            WLq_ = json.load(open(B))["waende"]; ff, qi_ = quadern(ff, objekt_json, Z, "foto", (wandende_ist_ecke(WLq_, w, "a"), wandende_ist_ecke(WLq_, w, "b"))); qbel.append(("Fotorelief", qi_))
        if mono_: fmo, qi_ = quadern(fmo, objekt_json, Z, "fein"); qbel.append(("Feinrelief mono", qi_))
        elif tf and os.path.exists(fm): fm, qi_ = quadern(fm, objekt_json, Z, "fein"); qbel.append(("Feinrelief misch", qi_))
        for nm_, qi_ in qbel:
            if qi_: belege.append(dict(seite="wand", element=f"Quaderraster {nm_} Fassade {w['name']}: {qi_.get('relief_steine')} Steine eben, Rillen {qi_.get('relief_rille_mm')} mm (Breite, Tiefe H0)",
                                       quelle=f"tools/quader_raster.py: Lagen/Fugen aus {qi_.get('fotos')} entzerrten Einzelfotos (Mehrfoto-Mittel, Fassade {qi_.get('fassade')}), Stirnflaeche = Median der Tiefe je Stein",
                                       lagen_m=qi_.get("lagen_m", [])[:40], keilsteine=[{k_: v_ for k_, v_ in x_.items() if k_ not in ("ruecken_je_stein", "bogenbreite_je_stein_m")} for x_ in (qi_.get("keilsteine") or [])], eckquader={k_: {kk: v_ for kk, v_ in e_.items() if kk != "bloecke"} | dict(n=len(e_.get("bloecke", []))) for k_, e_ in (qi_.get("eckquader") or {}).items()}, front_p5_p95_m=qi_.get("relief_front_p5_p95_m"), verworfen=qi_.get("verworfen"),
                                       hinweis="ANNAHME: Rillenbreite/-tiefe = Druckmass (MINMM x SCALE), echte Fugen 1-3 cm; Stirnflaeche eben (Bossen nicht gemessen); Bild relief/<datei>_q.jpg ansehen"))
        if not w.get("nur_foto"): koerper = koerper + offen(relief_koerper(f, tiefe=tiefe, trend=not w.get("ohne_trend"), tief_felder=tf + ([tuple(w["foto_feld"])] if hat_foto else []), flaeche=fl_w) ^ hu)
        fl_ = None
        if hat_foto and os.environ.get("FOTOSTEINE_NETZEBENE") != "1":   # 21.11.2026: Fotosteine auf die gemessene Koerperflaeche (Netzebene lag 0,24-0,5 m hinter der korrigierten Wand -> Steine unsichtbar)
            zf0_ = np.load(ff); hh_, ww_ = zf0_["rel"].shape; px_ = float(zf0_["px"]); u0_, z0_ = float(zf0_["u0"]), float(zf0_["z0"])
            fl_ = koerper_flaeche(basis, zf0_["a"], zf0_["t"], zf0_["n"], [(u0_ + fu * ww_ * px_, z0_ + fz * hh_ * px_) for fu in (0.3, 0.5, 0.7) for fz in (0.3, 0.6, 0.9)])
        if hat_foto: koerper = koerper + offen(relief_koerper(ff, tiefe=tiefe, trend=True, rand_auslauf=False, flaeche=fl_) ^ hu); belege.append(dict(seite="wand", element=f"Quader mit Fugen aus dem Foto, Fassade {w['name']} ab z {w['foto_feld'][2]:.0f} m", quelle="tools/steine_aus_foto.py --foto auto (bestes Foto, Verdeckung, Gegenfoto)", steine=w.get("foto_steine"), hinweis="Fugenlage aus dem Foto, Fugentiefe/Bosse ANNAHME; relief/<wand>_foto.jpg ansehen"))
        if hat_foto and os.environ.get("OHNE_ECKQUADER_BELEG") != "1":     # 21.11.2026: Eckquader sind Teil des Fotoreliefs - hier benennen, was davon an einer Gebaeudeecke steht (nur gebaute Steine)
            from bauteile import eckquader_aus_relief
            zf_ = np.load(ff); WL_ = json.load(open(B))["waende"]
            for q_ in eckquader_aus_relief(zf_["rel"], float(zf_["px"]), float(zf_["z0"]), float(zf_["putz_niveau_m"]) if "putz_niveau_m" in zf_.files else 0.0, wandende_ist_ecke(WL_, w, "a"), wandende_ist_ecke(WL_, w, "b")):
                belege.append(dict(seite="wand", element=f"Eckquader Fassade {w['name']} am Wand{q_['ende']} (z {q_['z0']:.1f}..{q_['z1']:.1f}, {q_['lagen']} Lagen verzahnt)",
                                   quelle="bauteile.eckquader_aus_relief auf dem gebauten Fotorelief relief/" + os.path.basename(ff) + " (tools/steine_aus_foto.py): Randstreifen Stein, Wandinneres Putz",
                                   eck_z0=q_["z0"], eck_z1=q_["z1"], eck_lagen=q_["lagen"], breite_lang=q_["breite_lang"], breite_kurz=q_["breite_kurz"],
                                   relief_auf_flaeche_m=None if fl_ is None else round(fl_, 3),
                                   hinweis="Quader = Fotorelief (Fugenlage aus dem Foto, Bosse ANNAHME); Ecke = Wandende ohne gleichgerichtete Nachbarwand; Relief auf der gemessenen Koerperflaeche (fassaden_kette.koerper_flaeche)"))
        if mono_:
            koerper = koerper + offen(relief_koerper(fmo, tiefe=tiefe, trend=True, rand_auslauf=False) ^ hu)
            belege.append(dict(seite="wand", element=f"Feinrelief Fassade {w['name']} aus Einzelfotos (Feld u {feld_mo[0]:.1f}..{feld_mo[1]:.1f}, z {feld_mo[2]:.1f}..{feld_mo[3]:.1f})", quelle="Kettenstufe mono: tools/relief_aus_fotos_mono.py (Tiefpass Scan/Feinrechnung + Hochpass Depth Anything V2 Small, Apache-2.0), Tor Korrelation >= 0,2",
                               korrelation=(w.get("mono") or {}).get("korrelation"), hinweis="relief/<wand>_mono.jpg ansehen"))
        elif tf: koerper = koerper + (relief_koerper(fm, tiefe=tiefe, trend=True) ^ hu)                 # lokale Feinrechnung (tools/tiefe_lokal.py + relief_mischen.py) vor dem groben Relief
        belege.append(dict(seite="wand", element=f"Relief Fassade {w['name']} (Fassaden-Kette)", quelle=("Netz der dichten Wolke (Hoehenbild 5 cm), roh: das Foto zeigt kein Quaderwerk (Quader-Tor), kleine Loecher glatt gefuellt" if w.get("quader") is False else "Netz der dichten Wolke (Hoehenbild 5 cm); Putz ueber Fotofarbe (" + ", ".join(w.get("fotos", [])[:3]) + "); Loecher generiert"),
                           generiert_anteil=w.get("generiert"), hinweis="Scan-Relief, kein Mass" + (f"; ANNAHME: Relief {w.get('vorstand', 0) * 100:.0f} cm vor die LoD2-Wandebene gesetzt (Ruecksprunge sichtbar), Oeffnungen nur als Ruecksprung" + (f"; ANNAHME: {w['putz_eben'] * 100:.0f} % der Wand naeher als {w.get('putz_band', 0.05) * 100:.0f} cm am Wandniveau = glatter Putz (Netzrauschen weg)" if w.get("putz_eben") else "") if w.get("quader") is False else "; generierte Steine = ANNAHME")))
    if os.environ.get("OHNE_ORTSTEINE") != "1":                         # 24.11.2026 (Befund 1122u/v: Turmkanten glatt, Foto zeigt verzahnte Sandstein-Eckquader): Ortsteine aus dem Wandbild, vor die gebaute Flaeche
        from ortsteine import ortsteine_anbauen
        koerper, bel_o = ortsteine_anbauen(koerper, objekt_json); belege += bel_o
    return koerper, belege


class _Weiche:
    """stdout je Thread puffern: jede Wand schreibt in ihren eigenen Puffer, ausgegeben wird Wand fuer Wand in der Reihenfolge von W (Log wie beim seriellen Lauf)."""
    def __init__(s, echt): s.echt = echt; s.lokal = __import__("threading").local()
    def write(s, x):
        b = getattr(s.lokal, "buf", None)
        if b is None: return s.echt.write(x)
        b.append(x); return len(x)
    def flush(s):
        if getattr(s.lokal, "buf", None) is None: s.echt.flush()
    def __getattr__(s, k): return getattr(s.echt, k)


_GPU_SEM = [None]
FEIN_AUS = [""]                                                         # Meldung des tiefe_lokal-Guards (rc 2) -> keine weitere Wand versucht die Feinrechnung


GPU_TEILE = {"steine_aus_foto.py", "tiefe_lokal.py"}      # Teilwerkzeuge mit GPU: steine_aus_foto (render_kern/torch, 0,8-2 GB), tiefe_lokal (PatchMatch ~2,2 GB); 21.11.: 6 steine_aus_foto gleichzeitig = CUDA OOM


def _gpu_run(cmd, **k):
    """subprocess.run fuer GPU-Teilwerkzeuge (GPU_TEILE): hoechstens so viele gleichzeitig wie GPU-Plaetze (_waende_parallel) - mit 1 Platz nie mehr VRAM als der serielle Lauf."""
    s = _GPU_SEM[0]
    if s is None: return subprocess.run(cmd, **k)
    with s: return subprocess.run(cmd, **k)


_WIEDERHOL = __import__("threading").Lock()   # Wiederholungen nach Systemabbruch laufen nacheinander

def parallel_plaetze(n_waende, env=None, fein=None):
    """(Waende gleichzeitig, GPU-Plaetze). 21.11.2026 (Tempo, Kettenlauf 1121o: fassaden_kette 1356 s, Waende nacheinander, 28 Kerne):
    CPU: FASSADEN_PARALLEL oder min(Waende, Kerne/4, verfuegbarer RAM / 2,6 GB - gemessen 21.11.: Spitze 2,5 GB Teilprozesse je Wand); 1 = alter serieller Ablauf.
    GPU: FASSADEN_GPU_PARALLEL oder aus der Job-Buchung RCPARK_GPU_MB (tools/job_start.sh): je PatchMatch-Lauf (3200 px) ~2,2 GB -> Buchung // 2300, hoechstens 2, mindestens 1
    (PatchMatch laeuft mit 100 % GPU - ein zweiter Lauf bringt nur die Ueberlappung von Entzerren/Fusion, kostet aber VRAM)."""
    env = os.environ if env is None else env
    fein = ("--fein" in sys.argv) if fein is None else fein
    g = int(env["FASSADEN_GPU_PARALLEL"]) if env.get("FASSADEN_GPU_PARALLEL") else max(1, min(2, int(env.get("RCPARK_GPU_MB") or 0) // 2300))
    if env.get("FASSADEN_PARALLEL"): n = int(env["FASSADEN_PARALLEL"])
    else:
        try: frei_mb = int([z.split()[1] for z in open("/proc/meminfo") if z.startswith("MemAvailable")][0]) // 1024
        except Exception: frei_mb = 3000
        # 21.11.2026 (1121p: w03 Signal 6 nach Kernel-OOM): Feinrechnung tiefe_lokal braucht gemessen 5,2 GB je GPU-Platz -> vorab abziehen; Obergrenze = Job-Buchung (RCPARK_RAM_MB, job_start) minus 1,5 GB Kette selbst
        if env.get("RCPARK_RAM_MB"): frei_mb = min(frei_mb, int(env["RCPARK_RAM_MB"]) - 1500)
        frei_mb -= 5300 * g if fein else 0
        n = min(n_waende, max(1, (os.cpu_count() or 4) // 4), max(1, frei_mb // 2600))
    return max(1, min(n, n_waende)), max(1, g)


def _waende_parallel(W, f, objekt=None):
    """f(w) fuer jede Wand. Die Waende sind unabhaengig (eigene Dateien relief/<wand>*, eigener Arbeitsordner tiefe_lokal/<wand>_fein; Objekt-STL und LoD2-Nachbarn
    werden nur gelesen) -> Threads (die Arbeit steckt in den Teilprozessen), Ausgabe in Wandreihenfolge, GPU-Teil begrenzt (_gpu_run)."""
    import threading, traceback
    from concurrent.futures import ThreadPoolExecutor
    n, g = parallel_plaetze(len(W)); _GPU_SEM[0] = threading.Semaphore(g)
    if n <= 1:
        for w in W: f(w)
        return
    print(f"Waende parallel: {n} gleichzeitig, GPU-Plaetze {g} (FASSADEN_PARALLEL=1 = seriell)", flush=True)
    if objekt:                                                            # gemeinsame Zwischenspeicher VOR den Threads fuellen (trimesh rechnet Eigenschaften sonst je Thread nach)
        nb = lod2_netze(objekt)[1]
        if nb is not None: nb.face_normals; nb.triangles
    echt = sys.stdout; we = _Weiche(echt); sys.stdout = we
    def eins(w):
        we.lokal.buf = []; fe = None
        try: f(w)
        except BaseException as e: fe = e; we.lokal.buf.append(traceback.format_exc())
        t = "".join(we.lokal.buf); we.lokal.buf = None; return t, fe
    try:
        with ThreadPoolExecutor(n) as ex:
            for fu in [ex.submit(eins, w) for w in W]:
                t, fe = fu.result(); echt.write(t); echt.flush()
                if fe is not None: raise fe
    finally: sys.stdout = echt


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--netz", required=True); ap.add_argument("--wand", nargs=8, action="append", default=[]); ap.add_argument("--min_laenge", type=float, default=3.0)
    ap.add_argument("--px", type=float, default=0.05); ap.add_argument("--massstab", nargs=4, help="wie relief_putz.py (Relief im Rohrahmen)")
    ap.add_argument("--fotosteine", action="store_true", help="Stufe 5c: Quader mit Fugen aus dem besten Foto oberhalb --foto_ab (tools/steine_aus_foto.py --foto auto)"); ap.add_argument("--foto_ab", type=float, default=10.0); ap.add_argument("--nachbar_stl", default="", help="STL der Nachbarobjekte fuer die Verdeckung"); ap.add_argument("--fein", nargs=2, metavar=("SPARSE", "BILDER"), help="je Wand zusaetzlich die lokale Feinrechnung der Tiefe fuer die Steinzone (tools/tiefe_lokal.py, GPU, ~11 min je Wand) und relief_mischen.py"); ap.add_argument("--fein_max_size", default="3200"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); rd = os.path.join(od, "relief"); os.makedirs(rd, exist_ok=True)
    W = [dict(name=w[0], a=[float(w[1]), float(w[2])], b=[float(w[3]), float(w[4])], aussen=[float(w[5]), float(w[6])], z1=float(w[7])) for w in a.wand] or waende_aus_lod2(od, a.min_laenge)
    abstuerze = []                                                        # 17.11.2026 (Durchsicht, nur Rueckgabecode/Meldung): Abstuerze der Teilwerkzeuge wurden wie 'kein Putz'/'kein Ergebnis' behandelt und verschwanden
    def absturz_merken(r, cmd):                                           # Absturz = Python-Traceback oder vom System beendet; rc 1-4 mit eigener Meldung ('kein Putz gefunden', 'ABBRUCH: ...') bleibt ein regulaeres 'geht nicht'
        if r.returncode < 0 or (r.returncode != 0 and "Traceback (most recent call last)" in (r.stderr or "")):
            t_ = f"{os.path.basename([c_ for c_ in cmd if str(c_).endswith('.py')][0])}: " + (f"vom System beendet (Signal {-r.returncode})" if r.returncode < 0 else (r.stderr.strip().splitlines() or ["?"])[-1][:200])
            abstuerze.append(t_); print("    FEHLER (Werkzeug abgestuerzt, NICHT 'kein Ergebnis'):", t_, flush=True)
    def lauf(cmd):
        lf_ = _gpu_run if os.path.basename(cmd[0]) in GPU_TEILE else subprocess.run
        r = lf_([PY, "-W", "ignore", "-I"] + cmd, capture_output=True, text=True)
        if r.returncode < 0:                                              # 21.11.2026 (Nutzer: "wiederholst du Sachen, wo du wegen Arbeitsspeicher gescheitert bist?" - nein, w03 blieb in 1121p weg): vom System beendet -> EINMAL wiederholen, Wiederholungen nacheinander
            print(f"    WIEDERHOLUNG: {os.path.basename(cmd[0])} vom System beendet (Signal {-r.returncode}) - einmal neu, nacheinander", flush=True)
            with _WIEDERHOL: __import__("time").sleep(20); r = lf_([PY, "-W", "ignore", "-I"] + cmd, capture_output=True, text=True)
        z = (r.stdout.strip().splitlines() or [r.stderr.strip()[-200:]])[-1]; print("   ", z[:200], flush=True); absturz_merken(r, cmd); return r.returncode
    nb_stl = nachbarn_stl(a.objekt, rd) if not a.wand else ""            # 17.11.2026: LoD2-Nachbarn als Verdecker der Fotostufe (am Kaufhaus zeigte das "beste Foto" der Ostwand das Nachbarhaus davor)
    def _wand(w):                                                     # 21.11.2026 (Tempo): Rumpf einer Wand; die Waende laufen parallel (_waende_parallel), Ablauf je Wand unveraendert
        A = np.array(w["a"]); Bp = np.array(w["b"]); L = float(np.linalg.norm(Bp - A)); t = (Bp - A) / L; n = np.array([t[1], -t[0]]); n = n if (np.array(w["aussen"]) - A) @ n > 0 else -n
        for q_ in ("_putz", "_voll", "_foto", "_tor"):                   # 17.11.2026: eigene Ergebnisse eines FRUEHEREN Laufs dieser Wand weg, bevor neu gerechnet wird - sonst liegen neben einer Wand, die jetzt 'aus' ist,
            for e_ in (".npz", ".jpg"):                                  # noch alte Bilder (kaufhaus_gk: w07_foto.jpg mit dem Nachbarhaus als "Quader"). _misch (lokale Feinrechnung, teuer) bleibt.
                if os.path.exists(os.path.join(rd, w["name"] + q_ + e_)): os.remove(os.path.join(rd, w["name"] + q_ + e_))
        wf = wand_flaeche(a.objekt, A, Bp, n, a.px) if not a.wand else None      # nur fuer LoD2-Kanten; --wand = gemessene Wandgerade mit eigener Hoehe
        if wf is not None:
            w["z1_first"] = w["z1"]; w["z1"] = round(wf[2], 2); w["wand_m2"] = round(float(wf[0].sum()) * a.px ** 2, 1); w["frei_m2"] = round(float(wf[1].sum()) * a.px ** 2, 1)
            if wf[1].sum() < max(0.1 * wf[0].sum(), 2.0 / a.px ** 2):
                w["aus"] = f"Brandwand: von {w['wand_m2']} m2 Wandflaeche (LoD2) nur {w['frei_m2']} m2 frei, davor steht ein Nachbargebaeude (LoD2 < 1 m)"; w["fotos"] = []; w["laenge"] = round(L, 2); print(f"WAND {w['name']}: {L:.1f} m - AUS: {w['aus']}", flush=True); return
        fotos, bew = fotos_fuer_wand(od, A, Bp, n, 0.0, w["z1"]); w["fotos"] = fotos; w["laenge"] = round(L, 2); print(f"WAND {w['name']}: {L:.1f} m, z bis {w['z1']:.1f}, Fotos {[(f[-12:], round(s_)) for s_, _, f in bew]}", flush=True)
        r0 = os.path.join(rd, w["name"] + ".npz"); r1 = os.path.join(rd, w["name"] + "_putz.npz"); r2 = os.path.join(rd, w["name"] + "_voll.npz")
        rc = lauf([os.path.join(HIER, "relief_einsatz.py"), a.netz, r0, "--ecke_a", *map(str, w["a"]), "--ecke_b", *map(str, w["b"]), "--aussen", *map(str, w["aussen"]), "--feld", "0.1", str(round(L - 0.1, 2)), "0", str(w["z1"]), "--px", str(a.px), "--klemme", "-0.10", "0.15"])
        leer = bool(rc) or not os.path.exists(r0) or float(np.load(r0)["lochanteil"]) > 0.6
        def wand_eintragen(f_):                                           # Wandmaske ins Relief: ausserhalb (Dach, Himmel, angebauter Nachbar) kein Relief; steine_aus_foto.py liest 'wand'
            Z_ = dict(np.load(f_)); H_, W_ = Z_["rel"].shape; m_ = np.zeros((H_, W_), bool); h_ = min(H_, wf[1].shape[0]); b_ = min(W_, wf[1].shape[1]); m_[H_ - h_:, :b_] = wf[1][wf[1].shape[0] - h_:, :b_]
            Z_["rel"] = np.where(m_, Z_["rel"], 0.0).astype(np.float32); Z_["wand"] = m_; Z_["oeffnung"] = Z_["oeffnung"] & m_; np.savez_compressed(f_, **Z_); return Z_, m_
        if wf is not None and not rc and os.path.exists(r0):              # 17.11.2026: Lochanteil nur INNERHALB der freien Wandflaeche und ohne Oeffnungen (Arkaden, Tore sind kein fehlendes Netz)
            netz_vorn(a.netz, r0); Z_, m_ = wand_eintragen(r0); zaehl = m_ & ~Z_["oeffnung"]; w["loch_wand"] = round(float(((Z_["rel"] == 0.0) & zaehl).sum() / max(zaehl.sum(), 1)), 3); leer = w["loch_wand"] > 0.6
            print(f"    Wandflaeche (LoD2) {w['wand_m2']} m2 bis z {w['z1']:.1f}, frei {w['frei_m2']} m2; Loecher in der freien Wand ohne Oeffnungen {w['loch_wand'] * 100:.0f} %", flush=True)
        if leer:                                                          # 16.11.2026 (Haertetest ober_tvdr): Netz deckt die Wand nicht -> frueher AUS. Jetzt: leeres Relief als Traeger, Putz und Steine NUR aus Fotos (Stufe 5c ab Boden)
            w["netz"] = "deckt die Wand nicht"; print("    Netz deckt die Wand nicht - nur Fotostufe", flush=True)
            if not a.fotosteine or not fotos or lauf([os.path.join(HIER, "relief_einsatz.py"), "-", r0, "--ecke_a", *map(str, w["a"]), "--ecke_b", *map(str, w["b"]), "--aussen", *map(str, w["aussen"]), "--feld", "0.1", str(round(L - 0.1, 2)), "0", str(w["z1"]), "--px", str(a.px)]) != 0: w["aus"] = "kein Netz, keine Fotostufe"; return
            if wf is not None: wand_eintragen(r0)
        Z = np.load(r0); w["loch"] = round(float(Z["lochanteil"]), 3); w["oeffnung"] = round(float(Z["oeffnung"].mean()), 3)
        quelle = r0
        # 17.11.2026 QUADER-TOR VOR Putzglaetten und Steine-Generieren: beide Stufen setzen einen Putzbau mit Werkstein voraus (Schwabentor). Am Kaufhaus (roter Putz) erklaerte relief_putz 90 % der Wand zu "Stein"
        # und steine_generieren ueberschrieb Fenster und Figuren des echten Netz-Reliefs mit erfundenen Kissen (30 % der Flaeche). Probe: steine_aus_foto.py auf der ganzen Wand (bestes Foto, Verdeckung gegen
        # Modell + LoD2-Nachbarn); rc 5 = das Foto zeigt KEIN Fugenraster -> Netz-Relief bleibt roh (nur kleine Loecher glatt gefuellt), keine Fotosteine. rc 0 = Quaderwerk -> Ablauf wie bisher.
        # Anderer Ausgang (kein Foto, kein Gegenfoto, zu grob) = unbekannt -> Ablauf wie bisher.
        stl_ = os.path.join(os.path.dirname(os.path.dirname(od)), json.load(open(a.objekt))["stl"]); verd = ",".join(q_ for q_ in (stl_, nb_stl, a.nachbar_stl) if q_); rpr = os.path.join(rd, w["name"] + "_tor.npz")
        if a.fotosteine and os.path.exists(stl_):
            rc_t = lauf([os.path.join(HIER, "steine_aus_foto.py"), r0, rpr, "-", "0", "-", "--foto", "auto", "--objekt", a.objekt, "--stl", verd, "--feld", "0.1", str(round(L - 0.1, 2)), "0", str(w["z1"]), "--px", "0.03", "--nah", "0", "--streng"] + (["--massstab", *a.massstab] if a.massstab else []))
            w["quader"] = True if rc_t == 0 else (False if rc_t == 5 else None)
            for q_ in (rpr, rpr[:-4] + ".jpg"):
                if os.path.exists(q_) and rc_t != 0: os.remove(q_)
        if w.get("quader") is False:
            if leer: w["aus"] = "kein Netz in der Wand und kein Quaderwerk im Foto (Quader-Tor) - nichts zu tun"; print("    AUS:", w["aus"], flush=True); return
            w.update(relief_roh(r0, r2, a.px)); print(f"    kein Quaderwerk im Foto: Netz-Relief roh, kleine Loecher glatt gefuellt ({w['gefuellt'] * 100:.1f} % der Flaeche), Oeffnungen als Ruecksprung, Relief {w['vorstand'] * 100:.0f} cm vor die Wandebene, keine generierten Steine", flush=True)
            for q_ in (r1, r1[:-4] + ".jpg", os.path.join(rd, w["name"] + "_foto.npz"), os.path.join(rd, w["name"] + "_foto.jpg")):      # Reste eines frueheren Laufs (Putzmaske/Fotosteine) gelten nicht mehr
                if os.path.exists(q_): os.remove(q_)
            return
        if fotos and lauf([os.path.join(HIER, "relief_putz.py"), r0, r1, a.objekt, *fotos, "--feld", "0", str(L), "0", str(w["z1"])] + (["--massstab", *a.massstab] if a.massstab else [])) == 0:
            quelle = r1; w["putz"] = round(float(np.load(r1)["putz"].mean()), 3)
        if leer:
            if quelle != r1: w["aus"] = "kein Netz und kein Putz erkannt (Fotofarbe) - nichts zu tun"; print("    AUS:", w["aus"]); return
            import shutil; shutil.copy(r1, r2); w["generiert"] = 0.0
        elif lauf([os.path.join(HIER, "steine_generieren.py"), quelle, r2, "--max_loch_m2", "1.5"]) == 0: w["generiert"] = round(float(np.load(r2)["generiert_anteil"]), 3)
        else: w["aus"] = "steine_generieren fehlgeschlagen"; return
        fab = 0.0 if leer else a.foto_ab
        if a.fotosteine and "putz" in np.load(quelle).files and w["z1"] > fab + 2.0:      # 16.11.2026 Stufe 5c: oberhalb --foto_ab (Strassenfotos zu flach fuer brauchbares Scan-Relief) Quader/Gewaende/Baender
            rfo = os.path.join(rd, w["name"] + "_foto.npz")                                 # mit Fugen aus dem BESTEN Foto, direkt auf der Wandebene, Verdeckung gegen das Modell + Gegenfoto (Baeume)
            if os.path.exists(stl_) and lauf([os.path.join(HIER, "steine_aus_foto.py"), quelle, rfo, "-", "0", "-", "--foto", "auto", "--objekt", a.objekt, "--stl", verd,
                                              "--feld", "0.1", str(round(L - 0.1, 2)), str(fab), str(w["z1"]), "--px", "0.03", "--nah", "0", "--streng"] + (["--massstab", *a.massstab] if a.massstab else [])) == 0 and os.path.exists(rfo):
                w["foto_feld"] = [0.0, round(L, 2), fab, round(float(w["z1"]), 2)]; w["foto_steine"] = int(np.load(rfo)["steine"])
        if leer:
            if not w.get("foto_feld"): w["aus"] = "kein Netz und kein brauchbares Foto fuer Steine"; print("    AUS:", w["aus"]); return
            w["nur_foto"] = True                                          # anbauen(): nur die Fotoplatte, keine leere Grundplatte (gab 193 Splitterkoerper am Haertetest)
        if a.fein and not leer and FEIN_AUS[0]:                           # 21.11.2026: Guard von tiefe_lokal (Buendel/Bilder unpassend) gilt fuer alle Waende - nicht je Wand 10 min neu versuchen
            w["fein_aus"] = FEIN_AUS[0]
        if a.fein and not leer and not FEIN_AUS[0]:                       # Steinzone = Zeilen mit >= 30 % echtem Nicht-Putz-Relief; zusammenhaengender Block von unten, hoechstens 12 m
            Zv = np.load(r2); z1f = steinzone_oben(Zv["rel"], Zv["putz"] if "putz" in Zv.files else None, a.px)
            w["steinzone_z1"] = z1f
            if z1f >= 2.0:
                feld = ["0.1", str(round(L - 0.1, 2)), "0", str(z1f)]; rf_ = _gpu_run(["/media/oem/scan/venv-colmap/bin/python", "-I", os.path.join(HIER, "tiefe_lokal.py"), a.objekt, a.fein[0], a.fein[1], "--name", w["name"] + "_fein", "--a", *map(str, w["a"]), "--b", *map(str, w["b"]),
                                                                                                           "--aussen", *map(str, w["aussen"]), "--feld", *feld, "--max_size", a.fein_max_size] + (["--massstab", *a.massstab] if a.massstab else []), capture_output=True, text=True)
                print("   ", (rf_.stdout.strip().splitlines() or [rf_.stderr.strip()[-200:]])[-1][:200], flush=True); absturz_merken(rf_, [os.path.join(HIER, "tiefe_lokal.py")]); rfe = os.path.join(rd, w["name"] + "_fein.npz")
                if rf_.returncode == 2:                                   # Guard: Buendel und Bildordner passen nicht (z. B. entzerrtes Buendel + Originalfotos) -> Feinrechnung fuer ALLE Waende aus, laut
                    FEIN_AUS[0] = (rf_.stdout.strip().splitlines() or ["?"])[-1][:400]; w["fein_aus"] = FEIN_AUS[0]; print("    FEIN UEBERSPRUNGEN (alle Waende):", FEIN_AUS[0], flush=True)
                elif rf_.returncode == 3: w["fein_aus"] = (rf_.stdout.strip().splitlines() or ["?"])[-1][:300]; print("    FEIN OHNE ABDECKUNG:", w["fein_aus"], flush=True)
                if rf_.returncode == 0 and os.path.exists(rfe) and lauf([os.path.join(HIER, "relief_mischen.py"), rfe, r2, os.path.join(rd, w["name"] + "_misch.npz")]) == 0:
                    w["fein_feld"] = [0.0, round(L, 2), 0.0, round(z1f - 0.1, 2)]; w["fein_anteil"] = round(float(np.load(os.path.join(rd, w["name"] + "_misch.npz"))["fein"].mean()), 3)
    _waende_parallel(W, _wand, a.objekt if not a.wand else None)
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(dict(netz=a.netz, waende=W), open(os.path.join(od, "audit", "fassaden_kette.json"), "w"), indent=1, ensure_ascii=False)
    print("->", os.path.join(od, "audit", "fassaden_kette.json"), "| ANSEHEN: relief/<wand>_voll.jpg")
    n_rel = sum(1 for w in W if not w.get("aus"))                         # 17.11.2026 (Durchsicht): die Stufe endete IMMER mit rc 0 - auch ohne ein einziges Relief und nach Abstuerzen der Teilwerkzeuge
    abstuerze += _CODEFEHLER
    if abstuerze: print(f"FEHLER: {len(abstuerze)} Teilwerkzeug-Absturz/Abstuerze (Ergebnis der betroffenen Waende unvollstaendig): " + " | ".join(abstuerze[:4]), flush=True); return 3
    if n_rel == 0: print(f"FEHLER: KEIN Relief fuer irgendeine der {len(W)} Waende (alle 'aus': " + "; ".join(sorted({str(w.get('aus')) for w in W}))[:300] + ") - die Stufe hat nichts geliefert", flush=True); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
