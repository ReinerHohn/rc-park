#!/usr/bin/env python3
"""schlitze_wandbild.py - KLEINE OEFFNUNGEN OHNE ERKENNERKASTEN (Schlitze, Luken) aus dem Wandbild + Mehrfoto-Kanten (24.11.2026, Kettenstufe 'bauplan'
nach nischen_fenster.py, vor loch_gewaende.py). Grundsatz WANDBILD = BAUPLAN, Erkennen = nur Zone; nichts von Hand, kein Objektwissen.

ANLASS (Kettenlauf 1122w, Schwabentor West f03, audit/neben_detail_fenster_f03*.jpg, Offen-Punkt Doku/projekt/wolke-wandbild.md 24.11.): der schmale Lichtschlitz
oben (~0,12 x 1 m, z ~31-33) und die Luke unter der Traufe fehlen im Modell. Zwei Ursachen:
  1. Der Erkenner (OWLv2, fassade_parsing auf dem 5-cm-Wandbild) liefert fuer einen 2-3 Zellen breiten Schlitz ohne Gewaende keinen Kasten - die drei
     Fenster darunter fand er nur ueber ihre Sandstein-Felder. Alles nach dem Erkenner (fenster_aus_parsing, nischen_fenster, loch_gewaende) misst nur IN Kaesten.
  2. Das feine Wandbild (fassade_ortho 1 cm, --max-mpp 0,02) ist ueber z 27,5 leer: die Strassenfotos sehen den oberen Turm mit 2,4-3 cm/px (ueber 30 m hatte
     ein einziges Foto feine Zellen). Das grobe Wandbild (5 cm, <= 6 cm/px) zeigt die Zone in 15 Fotos, Schlitz und Luke deutlich.
METHODE (je Fassade):
  arbeitsbild()     feines Mosaik (Stufe 2 = 2 cm), wo leer: grobes Mosaik (ortho_<fid>.png des Fassadenordners) aufs Arbeitsraster abgetastet und per Verschiebung
                    aufs feine ausgerichtet (ortsteine.ausrichten); Aufloesungskarte je Zelle (fein / grob).
  kandidaten()      dunkle Zellen gegen den OERTLICHEN Hintergrund (60-%-Wert der Helligkeit L im 1-m-Fenster; L <= dunkel x Hintergrund, wie loch_gewaende),
                    zusammenhaengend (Schliessen 4 cm). Gueltig nur: kleinere Seite >= max(Druckmindestmass, 2 Zellen der oertlichen Aufloesung), Kastenflaeche <= max_flaeche
                    (groessere Oeffnungen kommen ueber Erkenner + loch_gewaende), Fuellung >= 50 % (Rechteck/Schlitz, kein Schattenfleck), Abstand zu Zellen ohne Foto
                    (angeschnitten = keine Aussage), innerhalb des Fassadenpolygons, nicht in schon bekannten Fenstern/Tueren/Boegen/Uhren (Fensterliste + Erkennerkaesten).
  bestaetigen()     MEHRFOTO-KANTEN: jedes Einzelfoto (fein, sonst grob - ortsteine.einzeln_vereinen, je Foto einmal) im Kastenumfeld: eigene dunkle Komponente nahe der Mitte
                    mit eigener Hintergrundhelligkeit -> Kanten links/rechts/unten/oben. Ein Foto bestaetigt, wenn es die Zone sieht und Breite/Hoehe zur Mosaikkomponente passen
                    (+-35 % bzw. 2 Zellen seiner Aufloesung). Formfamilie: >= min_fotos (3) bestaetigende Fotos UND Mehrheit (>= 60 %) der Fotos, die die Zone sehen
                    - ein Loch ist aus jedem Blick dunkel, ein dunkler Stein/Schatten nur bei passendem Licht (Schwabentor West: Schlitz 15 von 16, Luke 4 von 6,
                    dunkle Eckquader 4-12 von 14-30 = hoechstens 43 %); sonst verworfen (Grund im Bericht).
                    Masse = Median der Einzelfoto-Kanten (Streuung im Eintrag), Lage im Mosaikrahmen (Fotos aufs Mosaik ausgerichtet).
  Tiefe: Ebenen-Sweep im Loch gegen den Wandring (loch_gewaende.sweep_werte, Plausibilitaet dort), sonst ANNAHME wie nischen_fenster (0,12 m; Bau >= Druckmindestmass).
Ausgabe: Eintraege in der Fensterliste (fenster_auto.json; Eingang als fenster_auto_vor_schlitze.json daneben) mit 'loch' (loch_gewaende misst sie nicht nochmal),
  bogen gerade, form_quelle 'n von m Einzelfotos', quelle, aufloesung_m; Bericht schlitze_wandbild.json, Bild schlitze_<fid>.jpg (ANSEHEN: gruen = gebaut, rot = verworfen
  mit Grund, grau = bekannte Kaesten). Gebaut von bauteile.fenster_aus_json (Loch-Umriss mit Laibungstiefe).
Aufruf:  schlitze_wandbild.py <fenster_auto.json> <fassade-ordner (grob, elemente.json, tiefe_fNN.npz)> <fassade_fein-ordner> [--nur f03] [--aus ordner]
rc 0 = mindestens eine Oeffnung eingetragen, 3 = nichts gefunden/geaendert.
"""
import sys, os, json, argparse, shutil, glob
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import ortsteine as O

DUNKEL = 0.6          # Loch-Helligkeit hoechstens so viel x Hintergrund (wie loch_gewaende --dunkel)
HINTERGRUND_M = 1.0   # Fenster fuer die oertliche Hintergrundhelligkeit (m)
MAX_FLAECHE = 1.0     # Kastenflaeche (m2): groessere Oeffnungen liefert der Erkenner (OWLv2) mit Kasten -> loch_gewaende
FUELL_MIN = 0.5       # Anteil dunkler Zellen im Kasten (Rechteck/Schlitz statt Schattenfleck/Fuge)
TOL_FORM = 0.35       # Breite/Hoehe je Einzelfoto gegen das Mosaik
MEHRHEIT = 0.6        # Anteil der sehenden Fotos, die das Loch bestaetigen muessen (Loch dunkel aus jedem Blick; Stein/Schatten lichtabhaengig)
RING_STEIN_MAX = 0.4   # Ring 0,1-0,3 m um den Kandidaten hoechstens so viel Steinfarbe: im Quader-/Eckquaderwerk sind dunkle Steine und Schattenfugen nicht vom Loch zu trennen


def _L(rgb):
    """Helligkeit L (0..100) aus RGB uint8 (CIE-L* ueber die Luminanz, ohne cv2)."""
    a = np.asarray(rgb, np.float32) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4); Y = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    return np.where(Y > 0.008856, 116.0 * np.cbrt(Y) - 16.0, 903.3 * Y)


def hintergrund(L, bel, c, fenster_m=HINTERGRUND_M, q=60):
    """Oertliche Hintergrundhelligkeit: q-%-Wert von L der belegten Zellen im Fenster (auf 0,1-m-Bloecken gerechnet, Luecken vom naechsten Block gefuellt)."""
    from scipy import ndimage as ndi
    k = max(1, int(round(0.1 / c))); H, W = L.shape; h, w = -(-H // k), -(-W // k)
    Lp = np.zeros((h * k, w * k), np.float32); Lp[:H, :W] = np.where(bel, L, 0); Bp = np.zeros((h * k, w * k), np.float32); Bp[:H, :W] = bel
    s = Lp.reshape(h, k, w, k).sum((1, 3)); n = Bp.reshape(h, k, w, k).sum((1, 3)); ok = n >= 0.3 * k * k
    if not ok.any(): return np.zeros_like(L)
    m = np.where(ok, s / np.maximum(n, 1), np.nan)
    idx = ndi.distance_transform_edt(~ok, return_distances=False, return_indices=True); m = m[tuple(idx)]
    b = ndi.percentile_filter(m, q, size=max(3, int(round(fenster_m / 0.1)) | 1))
    return np.repeat(np.repeat(b, k, 0), k, 1)[:H, :W]


def _komponenten(dk, c):
    from scipy import ndimage as ndi
    r = max(1, int(round(0.02 / c))); st = np.ones((2 * r + 1, 2 * r + 1), bool)
    dk = ndi.binary_closing(dk, st) & ndi.binary_dilation(dk, st)      # Schliessen 4 cm (Gitterstaebe), nicht ueber den Rand hinaus wachsen
    lab, n = ndi.label(dk, np.ones((3, 3), bool))
    return lab, n, ndi.find_objects(lab)


def _kasten(m, i0, j0, u0, z1, c):
    """Kasten (u0, u1, z0, z1) einer Maske (2-/98-%-Werte der Zellen, halbe Zelle Rand)."""
    ii, jj = np.nonzero(m); U = u0 + (j0 + jj + 0.5) * c; Z = z1 - (i0 + ii + 0.5) * c
    a, b = np.percentile(U, (2, 98)); e, f = np.percentile(Z, (2, 98))
    return float(a - c / 2), float(b + c / 2), float(e - c / 2), float(f + c / 2)


def arbeitsbild(fein, grob, fid, stufe=2):
    """(rgb, bel, aufl, R) - feines Mosaik + grobes, wo das feine leer ist. R = dict(u0, z1, c, F)."""
    kl, hell, rgb, daten, _ = O.mosaik_karte(fein, fid, stufe)
    if kl is None: return None
    FF = {F["id"]: F for F in json.load(open(os.path.join(fein, "fassaden.json")))["fassaden"]}; F = FF[fid]; rs = F["raster"]; c = float(rs["zelle"]) * stufe
    aufl = np.where(daten, float(rs["zelle"]), np.nan).astype(np.float32); rgb = rgb.copy(); bel = daten.copy(); info = dict(grob=None); cg = None
    if grob and os.path.exists(os.path.join(grob, f"ortho_{fid}.png")):
        g = O.grob_auf_raster(os.path.join(grob, f"ortho_{fid}.png"), grob, fid, kl.shape, float(rs["u0"]), float(rs["z1"]), c)
        if g is not None:
            r = O.ausrichten(kl, O.klassen(g), c)
            if r and r["einig"] >= 0.8:
                g = O.verschieben(g, r["dy"], r["dx"]); gm = (g.astype(np.int32).sum(2) > 30) & ~daten
                rgb[gm] = g[gm]; bel |= gm
                try: cg = float({x["id"]: x for x in json.load(open(os.path.join(grob, "fassaden.json")))["fassaden"]}[fid]["raster"]["zelle"])
                except Exception: cg = 0.05
                aufl[gm] = cg; info["grob"] = dict(versatz_m=[round(-r["dy"] * c, 2), round(r["dx"] * c, 2)], einig=r["einig"], zellen_m2=round(float(gm.sum()) * c * c, 1))
            else: info["grob"] = dict(verworfen=f"grobes Mosaik nicht aufs feine ausgerichtet ({r})")
    return rgb, bel, aufl, dict(u0=float(rs["u0"]), z1=float(rs["z1"]), c=c, F=F, stufe=stufe, info=info, form=kl.shape, kl=kl, grob_zelle=cg)


def _im_polygon(F, u, z):
    """Punkt im Fassadenpolygon (polys_uz) - sonst im u/z-Rahmen."""
    P = F.get("polys_uz")
    if not P: return F["u"][0] <= u <= F["u"][1] and F["z"][0] <= z <= F["z"][1]
    for poly in P:
        p = np.asarray(poly, float); x, y = p[:, 0], p[:, 1]; inn = False
        for k in range(len(p)):
            a, b = k, (k + 1) % len(p)
            if (y[a] > z) != (y[b] > z) and u < x[a] + (z - y[a]) * (x[b] - x[a]) / (y[b] - y[a]): inn = not inn
        if inn: return True
    return False


def kandidaten(rgb, bel, aufl, R, bekannt, druck=None, dunkel=DUNKEL, max_flaeche=MAX_FLAECHE, fuell_min=FUELL_MIN, ring_stein_max=RING_STEIN_MAX):
    """Dunkle kleine Komponenten des Arbeitsbilds. bekannt = [(u0, u1, z0, z1)] schon erfasste Oeffnungen. Liefert (kandidaten, verworfen) als Listen von dict."""
    from scipy import ndimage as ndi
    c = R["c"]; druck = druck if druck is not None else O.druck_m(1.0)
    L = _L(rgb); bg = hintergrund(L, bel, c)
    a = rgb.astype(np.float32); blau = ((a[..., 2] - a[..., 0]) / (a.sum(2) + 1.0) > 0.03) & (a[..., 2] - a[..., 0] > 12)   # Himmel/blaue Flaechen sind kein Loch; dunkle Zellen haben keinen verlaesslichen Farbton (Rauschen) - nur deutlich blau zaehlt
    dk = bel & ~blau & (L <= dunkel * bg) & (bg > 0)
    lab, n, sl = _komponenten(dk, c)
    leer = ndi.binary_dilation(~bel, np.ones((5, 5), bool))
    stein, _ = O.stein_putz_karte(rgb)                                                               # Sandstein (rot/braun) bleibt auch im Schatten farbig - ein Loch nicht
    nr0, nr1 = max(1, int(round(0.10 / c))), max(2, int(round(0.30 / c)))
    out, weg = [], []
    for q, s in enumerate(sl, 1):
        if s is None: continue
        m = lab[s] == q; nz = int(m.sum())
        if nz * c * c < druck * druck: continue                                                      # Rauschen unter dem Druckmass: nicht einmal berichten
        u0, u1, z0, z1 = _kasten(m, s[0].start, s[1].start, R["u0"], R["z1"], c); b, h = u1 - u0, z1 - z0
        au = float(np.nanmedian(aufl[s][m])) if np.isfinite(aufl[s][m]).any() else 0.05
        k = dict(u0=round(u0, 3), u1=round(u1, 3), z0=round(z0, 3), z1=round(z1, 3), aufloesung_m=round(au, 3), L=round(float(np.median(L[s][m])), 1), hintergrund_L=round(float(np.median(bg[s][m])), 1))
        fuell = nz * c * c / max(b * h, 1e-9); k["fuellung"] = round(fuell, 2)
        min_s = max(druck, 2 * au)
        # Ring 0,10-0,30 m um die Komponente: das Loch muss auch gegen seine UNMITTELBARE Umgebung dunkel sein (dunkler Stein neben dunklem Stein ist keins)
        i0_, i1_ = max(0, s[0].start - nr1), min(L.shape[0], s[0].stop + nr1); j0_, j1_ = max(0, s[1].start - nr1), min(L.shape[1], s[1].stop + nr1)
        M = lab[i0_:i1_, j0_:j1_] == q; dist = ndi.distance_transform_edt(~M); rg = (dist >= nr0) & (dist <= nr1) & bel[i0_:i1_, j0_:j1_]
        L_ring = float(np.median(L[i0_:i1_, j0_:j1_][rg])) if rg.sum() >= 10 else float("nan"); k["ring_L"] = round(L_ring, 1)
        st_ant = float(stein[s][m].mean()); k["stein_anteil"] = round(st_ant, 2)
        st_ring = float(stein[i0_:i1_, j0_:j1_][rg].mean()) if rg.sum() >= 10 else 1.0; k["ring_stein"] = round(st_ring, 2)
        grund = None
        if min(b, h) < min_s: grund = f"zu schmal ({min(b, h):.2f} m < {min_s:.2f} m = max(Druckmass, 2 Zellen bei {au * 100:.0f} cm))"
        elif b * h > max_flaeche: grund = f"zu gross ({b * h:.2f} m2 > {max_flaeche} m2: Fall des Erkenners)"
        elif fuell < fuell_min: grund = f"fuellt den Kasten nur zu {fuell * 100:.0f} % (Schatten/Fuge, kein Loch)"
        elif st_ant >= 0.5: grund = f"fuellt zu {st_ant * 100:.0f} % Steinfarbe (dunkler Sandstein/Fuge, kein Loch)"
        elif st_ring >= ring_stein_max: grund = f"liegt im Mauerwerk (Ring zu {st_ring * 100:.0f} % Stein): dunkler Stein/Schatten dort nicht vom Loch zu trennen - Fall des Erkenners (Gewaende)"
        elif not (k["L"] <= dunkel * L_ring): grund = f"gegen den Ring 0,1-0,3 m nicht dunkel (L {k['L']:.0f} gegen {L_ring:.0f})"
        elif (leer[s] & m).any(): grund = "beruehrt Zellen ohne Foto (angeschnitten)"
        elif not _im_polygon(R["F"], (u0 + u1) / 2, (z0 + z1) / 2): grund = "ausserhalb des Fassadenpolygons"
        elif any(min(u1, x[1]) > max(u0, x[0]) and min(z1, x[3]) > max(z0, x[2]) for x in bekannt): grund = "in bekannter Oeffnung (Fensterliste/Erkennerkasten)"
        (weg if grund else out).append(dict(k, grund=grund) if grund else k)
    return out, weg


def kanten_im_foto(rgb, i0, i1, j0, j1, R, k, dunkel=DUNKEL, ring=(0.15, 0.45)):
    """Dunkle Komponente nahe der Mitte des Kastens k im Ausschnitt eines Einzelfotos -> (u0, u1, z0, z1) oder None. Hintergrund = Median des Rings um den Kasten."""
    from scipy import ndimage as ndi
    c = R["c"]; A = rgb[i0:i1, j0:j1]; bel = A.astype(np.int32).sum(2) > 30
    II, JJ = np.mgrid[i0:i1, j0:j1]; U = R["u0"] + (JJ + 0.5) * c; Z = R["z1"] - (II + 0.5) * c
    du = np.maximum(np.maximum(k["u0"] - U, U - k["u1"]), 0); dz = np.maximum(np.maximum(k["z0"] - Z, Z - k["z1"]), 0); d = np.hypot(du, dz)
    inn = d == 0; rg = (d >= ring[0]) & (d <= ring[1])
    if (bel & inn).mean() < 0.9 * inn.mean() or (bel & rg).sum() < 0.5 * rg.sum(): return None                 # sieht die Zone / ihren Ring nicht
    L = _L(A); Lr = float(np.median(L[bel & rg]))
    lab, n, sl = _komponenten(bel & (L <= dunkel * Lr) & (d <= max(k["u1"] - k["u0"], k["z1"] - k["z0"]) * 0.25 + 2 * c), c)
    mu, mz = (k["u0"] + k["u1"]) / 2, (k["z0"] + k["z1"]) / 2; best = None
    for q, s in enumerate(sl, 1):
        if s is None: continue
        m = lab == q
        if m.sum() < 4: continue
        cu, cz = float(U[m].mean()), float(Z[m].mean())
        if not (k["u0"] <= cu <= k["u1"] and k["z0"] <= cz <= k["z1"]): continue
        w = float(m.sum()) / (1.0 + np.hypot(cu - mu, cz - mz))
        if best is None or w > best[0]: best = (w, m)
    if best is None: return "dunkel_fehlt"
    return _kasten(best[1], i0, j0, R["u0"], R["z1"], c)


def bestaetigen(k, fotos, R, min_fotos=3, tol=TOL_FORM):
    """Mehrfoto-Kanten: je Einzelfoto (im Mosaikrahmen, ortsteine.einzeln_vereinen) Kanten der dunklen Komponente. Liefert (anzahl, gesehen, kanten-Median, streuung, je_foto)."""
    c = R["c"]; ru = max(0.5, 0.5 * (k["u1"] - k["u0"])); rz = max(0.5, 0.5 * (k["z1"] - k["z0"])); H, W = R["form"]
    i0 = max(0, int((R["z1"] - k["z1"] - rz) / c)); i1 = min(H, int((R["z1"] - k["z0"] + rz) / c) + 1)
    j0 = max(0, int((k["u0"] - ru - R["u0"]) / c)); j1 = min(W, int((k["u1"] + ru - R["u0"]) / c) + 1)
    b, h = k["u1"] - k["u0"], k["z1"] - k["z0"]; ja, je = [], {}; gesehen = 0
    for e in fotos:
        a = e["rgb"] if not (e.get("dy") or e.get("dx")) else O.verschieben(e["rgb"], e["dy"], e["dx"])
        fm = e.get("fein_maske"); ci, cj = (i0 + i1) // 2, (j0 + j1) // 2
        au = c if (fm is not None and fm[ci, cj]) else max(c, R.get("grob_zelle") or c)     # Aufloesung dieses Fotos am Kasten (fein = Arbeitszelle, sonst grobe Zelle)
        r = kanten_im_foto(a, i0, i1, j0, j1, R, k)
        nm = os.path.splitext(os.path.basename(e["datei"]))[0]
        if r is None: continue
        gesehen += 1
        if r == "dunkel_fehlt": je[nm] = "sieht die Zone, kein dunkles Loch"; continue
        tb, th = max(tol * b, 2 * au), max(tol * h, 2 * au); bb, hh = r[1] - r[0], r[3] - r[2]
        if abs(bb - b) <= tb and abs(hh - h) <= th: ja.append(r); je[nm] = "bestaetigt"
        else: je[nm] = f"andere Form {bb:.2f} x {hh:.2f} m"
    if not ja: return 0, gesehen, None, None, je
    A = np.array(ja); med = np.median(A, 0); st = A.std(0) if len(A) > 1 else np.zeros(4)
    return len(ja), gesehen, [round(float(x), 3) for x in med], [round(float(x), 3) for x in st], je


def eintrag(k, n, gesehen, kanten, streuung, npz, fenster_tiefe=0.12):
    u0, u1, z0, z1 = kanten
    e = dict(u0=u0, u1=u1, z0=z0, z1=z1, teiler=[], kaempfer=None, scheiben=1, stimmen_min=int(n), sprossen=[], bogen=dict(form="gerade", kaempfer=z1, scheitel=z1),
             klein=True, aufloesung_m=k["aufloesung_m"], form_quelle=f"{n} von {gesehen} Einzelfotos (Mehrfoto-Kanten, Streuung u0/u1/z0/z1 {streuung} m)",
             quelle="schlitze_wandbild: dunkle kleine Komponente im Wandbild (fein, sonst grob) ohne Erkennerkasten, Kanten = Median der Einzelfoto-Kanten",
             loch=dict(u0=u0, u1=u1, z0=z0, z1=z1, L=k["L"], wand_L=k["hintergrund_L"], fuellung=k["fuellung"], quelle="schlitze_wandbild: Mehrfoto-Kanten der dunklen Komponente"))
    t = None
    try:
        import loch_gewaende as LG
        _, t = LG.sweep_werte(npz, None, e)
    except Exception: t = None
    if t is not None: e["tiefe"] = t; e["tiefe_quelle"] = "Ebenen-Sweep: Loch gegen den Wandring (loch_gewaende.sweep_werte)"
    else: e["tiefe"] = fenster_tiefe; e["tiefe_quelle"] = f"ANNAHME {fenster_tiefe} m (Sweep im Loch nicht messbar); Bau mindestens Druckmindestmass"
    return e


def bekannte_kaesten(F, E, fid):
    """Schon erfasste Oeffnungen: Fensterliste (Eintrag, Zone vorher, Nische) + Erkennerkaesten tuer/bogen/uhr (Bau ueber andere Stufen)."""
    out = []
    for e in (F or {}).get("fenster", []):
        out.append((e["u0"], e["u1"], e["z0"], e["z1"]))
        for key in ("zone_vorher",):
            z = (e.get("loch") or {}).get(key)
            if z: out.append((z["u0"], z["u1"], z["z0"], z["z1"]))
        N = e.get("nische")
        if isinstance(N, dict) and all(x in N for x in ("u0", "u1", "z0", "z1")): out.append((N["u0"], N["u1"], N["z0"], N["z1"]))
    for x in ((E or {}).get(fid) or {}).get("elemente", []):
        if x.get("klasse") in ("tuer", "bogen", "uhr") and x.get("stimmen", 3) >= 3: out.append((x["u0"], x["u1"], x["z0"], x["z1"]))
    return out


def fotos_laden(fein, grob, fid, R, max_versatz=1.5, min_einig=0.8):
    """Einzelfotos im Mosaikrahmen (fein ausgerichtet; grob je Foto darunter), je Foto einmal."""
    kl = R["kl"]; c = R["c"]
    fs = sorted(glob.glob(os.path.join(fein, f"ortho_{fid}_einzeln", "*.png")))
    gut = []
    for e in O.einzeln_laden(fs, kl.shape, R["stufe"]):
        r = O.ausrichten(kl, e["kl"], c, max_m=max_versatz)
        if r and r["einig"] >= min_einig: e.update(r); gut.append(e)
    gr = O.grob_einzeln_laden(grob, fid, kl.shape, R["u0"], R["z1"], c) if grob else []
    return O.einzeln_vereinen(gut, gr, kl, c, max_m=max_versatz, min_einig=min_einig) if gr else \
        [dict(e, fein_maske=O.verschieben(e["rgb"], e["dy"], e["dx"]).astype(np.int32).sum(2) > 30) for e in gut]


def kontrollbild(rgb, R, neu, weg, bekannt, pfad, max_px=1400):
    from PIL import Image, ImageDraw
    im = Image.fromarray(rgb); d = ImageDraw.Draw(im); c = R["c"]
    P = lambda u, z: ((u - R["u0"]) / c, (R["z1"] - z) / c)
    for x in bekannt: d.rectangle([P(x[0], x[3]), P(x[1], x[2])], outline=(150, 150, 150), width=2)
    for x in weg:
        if x.get("grund", "").startswith(("zu schmal", "zu gross", "fuellt")): continue      # Massenfunde (Fugen, Schatten) nicht zeichnen
        d.rectangle([P(x["u0"] - 0.05, x["z1"] + 0.05), P(x["u1"] + 0.05, x["z0"] - 0.05)], outline=(255, 0, 0), width=2)
    for x in neu:
        d.rectangle([P(x["u0"] - 0.08, x["z1"] + 0.08), P(x["u1"] + 0.08, x["z0"] - 0.08)], outline=(0, 230, 0), width=4)
        d.text(P(x["u1"] + 0.15, x["z1"]), f"{x['u1'] - x['u0']:.2f}x{x['z1'] - x['z0']:.2f} m {x['stimmen_min']} Fotos", fill=(0, 160, 0))
    s = max_px / max(im.size)
    if s < 1: im = im.resize((int(im.size[0] * s), int(im.size[1] * s)))
    im.convert("RGB").save(pfad, quality=88)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("fenster"); ap.add_argument("ordner"); ap.add_argument("fein"); ap.add_argument("--nur", nargs="*"); ap.add_argument("--aus")
    ap.add_argument("--min_fotos", type=int, default=3, help="Formfamilie: so viele Einzelfotos muessen die Form bestaetigen")
    ap.add_argument("--mehrheit", type=float, default=MEHRHEIT, help="Anteil der sehenden Fotos, die bestaetigen muessen")
    ap.add_argument("--fenster_tiefe", type=float, default=0.12, help="ANNAHME wie nischen_fenster/loch_gewaende")
    a = ap.parse_args(argv)
    aus = a.aus or os.path.dirname(os.path.abspath(a.fenster)); os.makedirs(aus, exist_ok=True)
    J = json.load(open(a.fenster)) if os.path.exists(a.fenster) else {}
    try: E = json.load(open(os.path.join(a.ordner, "elemente.json")))["fassaden"]
    except Exception: E = {}
    FF = json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]
    bericht = {}; n_neu = 0
    for Fd in FF:
        fid = Fd["id"]
        if a.nur and fid not in a.nur: continue
        ab = arbeitsbild(a.fein, a.ordner, fid)
        if ab is None: bericht[fid] = dict(grund="kein feines Wandbild"); continue
        rgb, bel, aufl, R = ab
        bek = bekannte_kaesten(J.get(fid), E, fid)
        kand, weg = kandidaten(rgb, bel, aufl, R, bek)
        neu = []
        if kand:
            fotos = fotos_laden(a.fein, a.ordner, fid, R)
            nz = os.path.join(a.ordner, f"tiefe_{fid}.npz"); npz = dict(np.load(nz)) if os.path.exists(nz) else None
            for k in kand:
                n, ges, kanten, st, je = bestaetigen(k, fotos, R, a.min_fotos)
                k.update(fotos_bestaetigt=n, fotos_gesehen=ges, je_foto=je)
                if n < a.min_fotos: k["grund"] = f"Formfamilie nur in {n} von {ges} Einzelfotos bestaetigt (< {a.min_fotos})"; weg.append(k); continue
                if n < a.mehrheit * ges: k["grund"] = f"nur {n} von {ges} sehenden Fotos zeigen das Loch (< {a.mehrheit * 100:.0f} %: lichtabhaengig dunkel = Stein/Schatten)"; weg.append(k); continue
                e = eintrag(k, n, ges, kanten, st, npz, a.fenster_tiefe); neu.append(e)
            if neu:
                if fid not in J: J[fid] = dict(o=Fd["o"], d=Fd["d"], n=Fd["n"], fenster=[])
                J[fid].setdefault("fenster", []).extend(neu); n_neu += len(neu)
        bericht[fid] = dict(arbeitsbild=R["info"], neu=[{x: e[x] for x in ("u0", "u1", "z0", "z1", "stimmen_min", "form_quelle", "tiefe", "tiefe_quelle", "aufloesung_m")} for e in neu],
                            verworfen=[x for x in weg if not x.get("grund", "").startswith(("zu schmal", "zu gross", "fuellt"))],
                            verworfen_masse=len([x for x in weg if x.get("grund", "").startswith(("zu schmal", "zu gross", "fuellt"))]))
        if neu or kand: kontrollbild(rgb, R, neu, weg, bek, os.path.join(aus, f"schlitze_{fid}.jpg"))
        for e in neu: print(f"{fid} NEU {e['u1'] - e['u0']:.2f} x {e['z1'] - e['z0']:.2f} m bei u {e['u0']:.2f} z {e['z0']:.2f}-{e['z1']:.2f}: {e['form_quelle']}; Tiefe {e['tiefe']} ({e['tiefe_quelle'][:30]})")
        for x in bericht[fid]["verworfen"]: print(f"{fid} verworfen u {x['u0']:.2f}-{x['u1']:.2f} z {x['z0']:.2f}-{x['z1']:.2f}: {x['grund']}")
    json.dump(bericht, open(os.path.join(aus, "schlitze_wandbild.json"), "w"), indent=1, ensure_ascii=False)
    if not n_neu: print("keine kleine Oeffnung ohne Erkennerkasten gefunden - Fensterliste unveraendert"); return 3
    ziel = os.path.join(aus, os.path.basename(a.fenster))
    if os.path.abspath(ziel) == os.path.abspath(a.fenster) and os.path.exists(a.fenster): shutil.copy(a.fenster, a.fenster[:-5] + "_vor_schlitze.json")
    json.dump(J, open(ziel, "w"), indent=1, ensure_ascii=False)
    print(f"-> {ziel}: {n_neu} kleine Oeffnung(en) eingetragen"); return 0


if __name__ == "__main__": sys.exit(main())
