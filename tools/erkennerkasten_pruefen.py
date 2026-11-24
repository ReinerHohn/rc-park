#!/usr/bin/env python3
"""erkennerkasten_pruefen.py - ERKENNERKASTEN VOR DER VERWENDUNG PRUEFEN (24.11.2026): eine 'tuer'/'fenster'-Box des Erkenners (OWLv2, fassade_parsing ->
elemente.json bzw. oeffnungen_aussen.json) zaehlt nur, wenn das Wandbild bzw. die Tiefe darin eine OEFFNUNG belegt. Sonst ist sie ein falscher Erkennerkasten:
verworfen (Grund im Bericht) und die Flaeche ist frei fuer schlitze_wandbild (kleine Oeffnungen ohne Kasten); loch_gewaende macht daraus keine Tuer.

ANLASS (Kettenlauf 1122zb, Schwabentor f04 = Sehne des runden Treppenturms): im Foto drei Schlitze (z 4,6-5,3 / 7,6-8,2 / 9,8-10,5), gebaut einer. Der
Erkenner lieferte zwei FALSCHE 'tuer'-Kaesten 1,6 x 5,9 m auf weissem Putz (z 2,1-8,0 und 6,6-12,0). schlitze_wandbild.bekannte_kaesten sperrte damit alle drei
Schlitze ('in bekannter Oeffnung'); loch_gewaende machte aus dem einen Kasten eine ZWEITE Tuer (Doppelung der echten Tuer unten) und aus dem anderen den einen
gebauten Schlitz (je Zone nur ein Loch). Bekannt seit 20.11. (modelle/PERFORMANCE_BREMSEN_2026-11-20.md:260: falsche 'fenster'-Kaesten auf f00 = helle Felder
zwischen den Erker-Konsolen, 'tuer' ueber die ganze Turmhoehe) - bisher ohne Pruefung in der Kette. Die Regel 'Ring hell = Wand -> Kasten zaehlt nicht' trennt
nicht (echte Oeffnungen f00 z 33 haben auch hellen Ring). Darum hier: die BOX muss eine Oeffnung belegen, nicht der Ring.

BELEGE (je einer genuegt; Erkennen = nur Zone, Wandbild = Bauplan):
  dunkel   dunkle Komponente (L <= DUNKEL x Wandring-L, Schliessen 4 cm) mit Mitte in der Box, die die Box FUELLT: Breite UND Hoehe >= SPANNE_MIN der Box
           (Tuerblatt, Glas, Gitter im Schatten). Ein Schlitz von 0,1 x 0,6 m in einer 1,6 x 5,9-m-Box fuellt sie nicht.
  rahmen   Box zu >= RAHMEN_MIN aus Nicht-Wand-Farbe (Lab-Abstand zum Wandring > max(10, 1,5 x Ringstreuung): Sandsteingewaende, Rahmen) UND darin ein dunkles
           Loch (>= Druckmindestmass): Schlitz/Fenster im Gewaende - die Box umfasst Gewaende + Loch (loch_gewaende misst das Loch).
  tiefe    Ebenen-Sweep (tiefe_fNN.npz, w positiv = vor der Wand): Box-Inneres >= TIEFE_MIN hinter dem Wandring, auf >= 50 % der gueltigen Innenzellen
           (offene Durchfahrt, tiefe Nische ohne Dunkel).
  TUER zusaetzlich: Unterkante am Boden (Box- oder Lochunterkante <= Fassadenboden unter der Boxmitte + BODEN_TOL) ODER Schwelle (Nicht-Wand-Band 0-0,15 m
           unter dem Loch auf >= 60 % der Lochbreite: Balkon, Sohlbank, Podest). Eine 'Tuer' 2 m ueber dem Boden ohne Schwelle ist keine.
  KEINE AUSSAGE (Box < 30 % mit Fotozellen oder kein Wandring): Box gilt weiter (nichts verwerfen ohne Beleg dagegen).
Aufruf (Diagnose, alle tuer/fenster-Kaesten einer Kette):
  erkennerkasten_pruefen.py <fassade-ordner (elemente.json, tiefe_fNN.npz)> <fassade_fein-ordner> [--aus bericht.json] [--nur f04]
  Verwendung in der Kette: schlitze_wandbild.bekannte_kaesten und loch_gewaende.tueren rufen pruefen() auf (Bericht: 'erkennerkaesten_verworfen').
"""
import sys, os, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RING = (0.15, 0.45)      # Wandring um die Box (m)
DUNKEL = 0.6             # Loch: L hoechstens so viel x Wandring-L (wie loch_gewaende/schlitze_wandbild)
SPANNE_MIN = 0.5         # dunkel-Beleg: Loch ueber >= so viel der Boxbreite UND -hoehe (ANNAHME; echte Tuer f04 0,61/0,85, Schlitz in falscher Tuerbox 0,08/0,11)
RAHMEN_MIN = 0.4         # rahmen-Beleg: Anteil Nicht-Wand-Farbe in der Box (ANNAHME; Schlitz im Sandsteinfeld f03 ~0,9)
TIEFE_MIN = 0.15         # tiefe-Beleg: Box-Inneres so weit hinter dem Wandring (m; ANNAHME > Sweep-Rauschen glatter Putz ~0,1)
BODEN_TOL = 0.6          # Tuer: Unterkante hoechstens so weit ueber dem Fassadenboden (m; ANNAHME Sockel/Stufen)
BELEGT_MIN = 0.3         # Box mit so wenig Fotozellen: keine Aussage
FUELL_MIN = 0.4          # Loch fuellt seinen eigenen Kasten (wie loch_gewaende): Konsolenbalken/Fugen spannen die Box nur auf (f00 Erker: 'Loch' = 2 Balken)
AUSSEN_MAX = 0.3         # Loch begrenzt: hoechstens so viel seiner Zellen ausserhalb der Box (+ Rand max(0,1 m, 10 %)); sonst dunkle Flaeche, die weiterlaeuft


def druck_min():
    return float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0


def _lab(rgb):
    import cv2
    return cv2.cvtColor(np.ascontiguousarray(rgb, np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32) * np.array([100 / 255.0, 1, 1], np.float32) - np.array([0, 128, 128], np.float32)


def boden(F, u, z_max):
    """Fassadenboden unter u: tiefste Polygonkante der Polygone, die u ueberdecken und unter z_max beginnen (sonst F['z'][0], sonst None)."""
    P = (F or {}).get("polys_uz")
    if isinstance(P, str):
        try: P = json.loads(P)
        except Exception: P = None
    zs = []
    for poly in P or []:
        p = np.asarray(poly, float)
        if len(p) >= 3 and p[:, 0].min() <= u <= p[:, 0].max() and p[:, 1].min() <= z_max: zs.append(float(p[:, 1].min()))
    if zs: return min(zs)
    z = (F or {}).get("z")
    return float(z[0]) if z else None


def tiefe_beleg(npz, kasten, ring=RING, min_gut=0.3):
    """(wand - innen) in m aus der Sweep-Karte und Anteil tiefer Innenzellen, oder None (keine/zu wenig gueltige Zellen)."""
    if npz is None: return None
    w, gut = np.asarray(npz["w"], float), np.asarray(npz["gut"]).astype(bool); c = float(npz["zelle"]); u0, z1 = float(npz["u0"]), float(npz["z1"])
    H, W = w.shape; U = u0 + (np.arange(W) + 0.5) * c; Z = z1 - (np.arange(H) + 0.5) * c; UU, ZZ = np.meshgrid(U, Z)
    a0, a1, b0, b1 = kasten
    du = np.maximum(np.maximum(a0 - UU, UU - a1), 0.0); dz = np.maximum(np.maximum(b0 - ZZ, ZZ - b1), 0.0); d = np.hypot(du, dz)
    inn, rg = d == 0, (d >= ring[0]) & (d <= ring[1])
    if inn.sum() < 5 or rg.sum() < 5 or gut[inn].mean() < min_gut or gut[rg].mean() < min_gut: return None
    wand = float(np.median(w[rg & gut])); wi = w[inn & gut]
    return dict(sprung=round(wand - float(np.median(wi)), 3), anteil_tief=round(float((wi <= wand - TIEFE_MIN).mean()), 2))


def pruefen(rgb, bel, u0, z1, c, kasten, klasse, npz=None, F=None, dunkel=DUNKEL):
    """Prueft EINE Erkennerbox [u0, u1, z0, z1] der Klasse 'tuer'/'fenster' im Wandbild (rgb uint8 RGB, bel = Zellen mit Foto, Raster u0/z1/Zelle c).
    Liefert dict(gilt=bool, grund=str, belege=[...], werte={...})."""
    import cv2
    a0, a1, b0, b1 = map(float, kasten[:4]); bu, bz = max(a1 - a0, c), max(b1 - b0, c)
    H, W = bel.shape; r = RING[1] + 0.05
    j0, j1 = max(0, int((a0 - r - u0) / c)), min(W, int(np.ceil((a1 + r - u0) / c)) + 1)
    i0, i1 = max(0, int((z1 - b1 - r) / c)), min(H, int(np.ceil((z1 - b0 + r) / c)) + 1)
    out = dict(kasten=[round(x, 3) for x in (a0, a1, b0, b1)], klasse=klasse, belege=[], werte={})
    if i1 - i0 < 3 or j1 - j0 < 3: return dict(out, gilt=True, grund="keine Aussage: Box ausserhalb des Wandbilds")
    A = np.asarray(rgb[i0:i1, j0:j1]); B = np.asarray(bel[i0:i1, j0:j1]).astype(bool)
    U = u0 + (np.arange(j0, j1) + 0.5) * c; Z = z1 - (np.arange(i0, i1) + 0.5) * c; UU, ZZ = np.meshgrid(U, Z)
    du = np.maximum(np.maximum(a0 - UU, UU - a1), 0.0); dz = np.maximum(np.maximum(b0 - ZZ, ZZ - b1), 0.0); d = np.hypot(du, dz)
    inn_all = d == 0; inn = inn_all & B; ring = (d >= RING[0]) & (d <= RING[1]) & B
    if inn_all.sum() == 0 or inn.sum() < BELEGT_MIN * inn_all.sum(): return dict(out, gilt=True, grund=f"keine Aussage: Box nur zu {inn.sum() / max(inn_all.sum(), 1) * 100:.0f} % mit Fotozellen")
    if ring.sum() < 20: return dict(out, gilt=True, grund="keine Aussage: kein Wandring mit Fotozellen um die Box")
    lab = _lab(A); L = lab[..., 0]
    wand = np.median(lab[ring], axis=0); dr = np.linalg.norm(lab[ring] - wand, axis=1); rausch = float(np.median(dr))
    Lw = float(wand[0]); fremd = (np.linalg.norm(lab - wand, axis=2) > max(10.0, 1.5 * rausch)) & B
    dk = ((L <= dunkel * Lw) & B).astype(np.uint8)
    k = max(3, 2 * int(round(0.02 / c)) + 1); dk = cv2.morphologyEx(dk, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    n, lk, st, _ = cv2.connectedComponentsWithStats(dk, 8)
    # Loch = BEGRENZTE dunkle Komponente: hoechstens AUSSEN_MAX ihrer Zellen ausserhalb der um RAND_M gewachsenen Box (eine dunkle Mauerflaeche/Schattenbahn,
    # die ueber die Box hinauslaeuft, ist kein Loch der Box - f00 Sandstein: 'Loch' 1,6 x 1,9 m = ganze Box, Komponente lief weiter)
    rand = max(0.1, 0.1 * max(bu, bz)); nah = d <= rand; best = None; v_ = out["werte"]; v_["unbegrenzt"] = 0
    for q in range(1, n):
        m = lk == q; cu, cz = float(UU[m].mean()), float(ZZ[m].mean())
        if not (a0 <= cu <= a1 and b0 <= cz <= b1): continue
        fl = float(m.sum())
        if (m & ~nah).sum() > AUSSEN_MAX * fl: v_["unbegrenzt"] += 1; continue
        mi = m & inn_all
        if not mi.any(): continue
        fuell = float(mi.sum()) / max(((UU[mi].max() - UU[mi].min()) / c + 1) * ((ZZ[mi].max() - ZZ[mi].min()) / c + 1), 1.0)
        if fuell < FUELL_MIN: v_["duenn"] = v_.get("duenn", 0) + 1; continue      # duenne Balken/Konsolen/Fugen spannen die Box auf, fuellen sie nicht
        if best is None or fl > best[0]: best = (fl, q)
    loch = None
    if best is not None:
        m = (lk == best[1]) & inn_all
        if m.any():
            lu0, lu1 = float(UU[m].min()) - c / 2, float(UU[m].max()) + c / 2; lz0, lz1 = float(ZZ[m].min()) - c / 2, float(ZZ[m].max()) + c / 2
            loch = dict(u0=round(lu0, 3), u1=round(lu1, 3), z0=round(lz0, 3), z1=round(lz1, 3), spanne_u=round((lu1 - lu0) / bu, 2), spanne_z=round((lz1 - lz0) / bz, 2),
                        L=round(float(np.median(L[m])), 1))
    v = out["werte"]; v.update(wand_L=round(Lw, 1), fotozellen=round(float(inn.sum() / inn_all.sum()), 2), nicht_wand=round(float(fremd[inn].mean()), 2), loch=loch)
    if loch and loch["spanne_u"] >= SPANNE_MIN and loch["spanne_z"] >= SPANNE_MIN: out["belege"].append(f"dunkel (Loch {loch['u1'] - loch['u0']:.2f} x {loch['z1'] - loch['z0']:.2f} m fuellt die Box zu {loch['spanne_u']:.0%} x {loch['spanne_z']:.0%})")
    dm = druck_min()
    if v["nicht_wand"] >= RAHMEN_MIN and loch and min(loch["u1"] - loch["u0"], loch["z1"] - loch["z0"]) >= dm:
        out["belege"].append(f"rahmen (Box zu {v['nicht_wand']:.0%} Nicht-Wand-Farbe mit Loch {loch['u1'] - loch['u0']:.2f} x {loch['z1'] - loch['z0']:.2f} m)")
    tb = tiefe_beleg(npz, (a0, a1, b0, b1)); v["tiefe"] = tb
    if tb and tb["sprung"] >= TIEFE_MIN and tb["anteil_tief"] >= 0.5: out["belege"].append(f"tiefe (Inneres {tb['sprung']:.2f} m hinter dem Wandring, {tb['anteil_tief']:.0%} der Zellen)")
    if klasse == "tuer":
        zb = boden(F, (a0 + a1) / 2, b1); unten = min(b0, loch["z0"]) if loch else b0
        am_boden = zb is not None and unten <= zb + BODEN_TOL
        schwelle = False
        if loch:
            sb = (UU >= loch["u0"]) & (UU <= loch["u1"]) & (ZZ < loch["z0"]) & (ZZ >= loch["z0"] - 0.15) & B
            schwelle = bool(sb.sum() >= 10 and fremd[sb].mean() >= 0.6)
        v.update(boden_z=None if zb is None else round(zb, 2), unterkante=round(unten, 2), am_boden=am_boden, schwelle=schwelle)
        if not (am_boden or schwelle):
            return dict(out, gilt=False, grund=f"Tuer ohne Boden/Schwelle: Unterkante {unten:.2f} m, Fassadenboden {zb if zb is None else round(zb, 2)} m (+{BODEN_TOL}), kein Nicht-Wand-Band unter dem Loch"
                        + (f"; Belege sonst: {', '.join(out['belege'])}" if out["belege"] else ""))
    if out["belege"]: return dict(out, gilt=True, grund="belegt: " + "; ".join(out["belege"]))
    lt = f"groesstes dunkles Loch {loch['u1'] - loch['u0']:.2f} x {loch['z1'] - loch['z0']:.2f} m fuellt die Box nur zu {loch['spanne_u']:.0%} x {loch['spanne_z']:.0%}" if loch else "kein dunkles Loch mit Mitte in der Box"
    tt = f"Tiefensprung {tb['sprung']:.2f} m" if tb else "Tiefe nicht messbar"
    return dict(out, gilt=False, grund=f"keine Oeffnung belegt: {lt}; Box zu {v['nicht_wand']:.0%} Nicht-Wand-Farbe (< {RAHMEN_MIN:.0%} oder ohne Loch); {tt} (< {TIEFE_MIN} m)")


def wandbild(fein, fid):
    """Feines Wandbild (RGB) + belegt + Raster wie loch_gewaende.wandbild. None = keins da."""
    import loch_gewaende as LG
    bgr = LG.wandbild(fein, fid)
    if bgr is None: return None
    FF = {F["id"]: F for F in json.load(open(os.path.join(fein, "fassaden.json")))["fassaden"]}
    if fid not in FF: return None
    rs = FF[fid]["raster"]; rgb = np.ascontiguousarray(bgr[..., ::-1])
    return rgb, rgb.astype(np.int32).sum(2) > 0, float(rs["u0"]), float(rs["z1"]), float(rs["zelle"]), FF[fid]


def npz_laden(ordner, fid):
    p = os.path.join(ordner, f"tiefe_{fid}.npz")
    return dict(np.load(p)) if ordner and os.path.exists(p) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("ordner"); ap.add_argument("fein")
    ap.add_argument("--aus"); ap.add_argument("--nur", nargs="*"); ap.add_argument("--klassen", nargs="*", default=["tuer", "fenster"])
    a = ap.parse_args(argv)
    E = json.load(open(os.path.join(a.ordner, "elemente.json")))["fassaden"]; bericht = {}; n_weg = 0
    for fid in sorted(E):
        if a.nur and fid not in a.nur: continue
        ks = [x for x in (E[fid] or {}).get("elemente", []) if x.get("klasse") in a.klassen]
        if not ks: continue
        wb = wandbild(a.fein, fid)
        if wb is None: bericht[fid] = "kein feines Wandbild"; continue
        rgb, bel, u0, z1, c, F = wb; npz = npz_laden(a.ordner, fid); br = []
        for x in ks:
            r = pruefen(rgb, bel, u0, z1, c, (x["u0"], x["u1"], x["z0"], x["z1"]), x["klasse"], npz, F); r["stimmen"] = x.get("stimmen"); br.append(r)
            n_weg += not r["gilt"]
            print(f"{fid} {x['klasse']:7s} u {x['u0']:6.2f}..{x['u1']:6.2f} z {x['z0']:6.2f}..{x['z1']:6.2f}: {'GILT ' if r['gilt'] else 'VERWORFEN'} {r['grund'][:170]}")
        bericht[fid] = br
    if a.aus: json.dump(bericht, open(a.aus, "w"), indent=1, ensure_ascii=False)
    print(f"{n_weg} Erkennerkasten verworfen"); return 0


if __name__ == "__main__": sys.exit(main())
