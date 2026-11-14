"""dach_bauen.py - Baukoerper je Objekt automatisch aus LoD2-Grundriss + gemessenem Dach (dach.json aus tools/dach_vermessen.py).

Allgemein fuer jedes Objekt (Nullstart-Schritt 'dach', Generator-Vorlage aus tools/objekt_anlegen.py):
  gebaeude_aus_lod2(objekt_json) -> (Manifold im Rahmen u/v/z ueber rahmen.gelaende, belege)
Je LoD2-GroundSurface (gleiche Reihenfolge wie dach_vermessen: Teil-Index = GroundSurface-Index):
  - Prisma des Grundrisses; kleinere Teile bekommen eine Bruecke offset(teil,0,3) ^ offset(nachbarn,0,3): fuellt LoD2-Spalten < 0,6 m und ueberlappt
    (Schwabentor: Treppentuerm-Polygon beruehrt den Turm nicht -> zwei Koerper)
  - Teil mit Dachmessung: Prisma 0..first, geschnitten mit z <= first - steigung * (ca a + cb b + d) je Ebene (Achsen mitte_uv/achse_a)
  - Teil ohne Messung (zu klein / keine Pixel): Flachdach auf LoD2-Wandoberkante der eigenen Waende; ANNAHME im Beleg
  - 'spitze' (DOM1 > Dachflaeche + 2 m): schlanke Pyramide bis Zielhoehe (objekt.json hoehe_m, sonst DOM1-max); Grundseite ANNAHME sqrt(Pixel) m
Lehre Schwabentor 2026-11-14: Huelle (hull_points) auf Schaftecken erzeugt Quetschpunkte (STL in 15 Koerper zerfallen); Ebenenschnitt nicht.
"""
import sys, os, json
import numpy as np
from manifold3d import Manifold as M, CrossSection, JoinType
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lod2_gebaeude import grundflaechen

UEBERLAPP = 0.3


def entdoppeln(p, d=0.05):
    out = [p[0]]
    for q in p[1:]:
        if np.hypot(*(q - out[-1])) >= d: out.append(q)
    if len(out) > 2 and np.hypot(*(out[0] - out[-1])) < d: out.pop()
    return np.asarray(out, float)


def ccw(p):
    p = entdoppeln(np.asarray(p, float)); a = 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]); return p if a > 0 else p[::-1]


def _abstand_rand(pt, poly):
    """kleinster Abstand Punkt -> Polygonrand."""
    a, b = poly, np.roll(poly, -1, 0); ab = b - a; t = np.clip(((pt - a) * ab).sum(1) / np.maximum((ab ** 2).sum(1), 1e-12), 0, 1)
    return float(np.min(np.hypot(*(a + t[:, None] * ab - pt).T)))


def dach_schneiden(prisma, t):
    """Prisma mit allen Dachebenen von dach.json-Teil t schneiden (z <= zf - k * (ca a + cb b + d))."""
    b = t["beste"]; zf, k = float(b["first"]), float(b["steigung"])
    c = np.array(t["mitte_uv"], float); ea = np.array(t["achse_a"], float); ea /= np.linalg.norm(ea); eb = np.array([-ea[1], ea[0]])
    for ca, cb, d in b["ebenen"]:
        wxy = k * (ca * ea + cb * eb); w = np.array([wxy[0], wxy[1], 1.0]); rhs = zf - k * d + k * (ca * (c @ ea) + cb * (c @ eb))
        nw = np.linalg.norm(w); prisma = prisma.trim_by_plane((-w / nw).tolist(), float(-rhs / nw))
    return prisma


def dach_hoehe(t, uv):
    b = t["beste"]; c = np.array(t["mitte_uv"], float); ea = np.array(t["achse_a"], float); ea /= np.linalg.norm(ea); eb = np.array([-ea[1], ea[0]])
    a_, b_ = (np.asarray(uv) - c) @ ea, (np.asarray(uv) - c) @ eb
    g = max([ca * a_ + cb * b_ + d for ca, cb, d in b["ebenen"]] or [0.0])
    return float(b["first"]) - float(b["steigung"]) * g


def seiten_aus_rahmen(obj):
    """+x/-x/+y/-y -> Himmelsrichtung aus rahmen.xhat_utm/yhat_utm (Lehre Schwabentor: Vorlage hatte fest '+x Sued', Audit falsch beschriftet)."""
    r = obj["rahmen"]; nm = lambda v: ["Nord", "Ost", "Sued", "West"][int(((np.degrees(np.arctan2(v[0], v[1])) + 45) % 360) // 90)]
    xh, yh = np.array(r["xhat_utm"], float), np.array(r["yhat_utm"], float)
    return {"+x": nm(xh), "-x": nm(-xh), "+y": nm(yh), "-y": nm(-yh)}


def gebaeude_aus_lod2(objekt_json, dach_json=None, zielhoehe=None):
    obj = json.load(open(objekt_json)); od = os.path.dirname(os.path.abspath(objekt_json)); r = obj["rahmen"]
    m0 = np.array(r["mitte_utm"], float); xh = np.array(r["xhat_utm"], float); yh = np.array(r["yhat_utm"], float); g0 = float(r["gelaende"])
    meta, gr, wa = grundflaechen(obj, obj["lod2"]["gml"])
    if meta is None: raise SystemExit(f"LoD2 {obj['lod2']['id']} nicht in {obj['lod2']['gml']}")
    dp = dach_json or os.path.join(od, "dach.json")
    dach = {t["teil"]: t for t in json.load(open(dp))["teile"]} if os.path.exists(dp) else {}
    zielhoehe = zielhoehe if zielhoehe is not None else obj.get("hoehe_m")
    polys = [ccw(np.c_[(p[:, :2] - m0) @ xh, (p[:, :2] - m0) @ yh]) for p in gr]
    fl = [0.5 * abs(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])) for p in polys]
    haupt = int(np.argmax(fl)); lid = obj["lod2"]["id"]
    belege = []; teile = []
    for i, uv in enumerate(polys):
        if fl[i] < 0.5: continue
        cs = CrossSection([uv.tolist()])
        if i != haupt:                                                                  # nur in Nachbarteile hineinwachsen, aussen unveraendert
            andere = [CrossSection([q.tolist()]) for j, q in enumerate(polys) if j != i and fl[j] >= 0.5]
            nb = andere[0]
            for q in andere[1:]: nb = nb + q
            cs = cs + (cs.offset(UEBERLAPP, JoinType.Miter) ^ nb.offset(UEBERLAPP, JoinType.Miter))   # Bruecke: LoD2-Teile haben oft Spalt (Schwabentor ~5 cm)
        t = dach.get(i)
        if t:
            b = t["beste"]; zf = float(b["first"])
            k = dach_schneiden(M.extrude(cs, zf), t)
            belege.append(dict(seite="dach", element=f"Dach Teil {i} ({b['form']})", quelle=f"Laser DOM1 (tools/dach_vermessen.py) ueber LoD2 {lid}-Grundriss Teil {i}",
                               first=round(zf, 2), neigung_grad=round(float(b["neigung_grad"]), 1), rms_m=round(float(b["rms_m"]), 2),
                               eindeutig=bool(t.get("eindeutig")), **({} if t.get("eindeutig") else {"hinweis": "ANNAHME: Form nicht eindeutig (BIC)"})))
            sp = t.get("spitze")
            if sp:
                ziel = max(float(zielhoehe or 0), float(sp["dom1_max"]))
                s = max(np.sqrt(sp["pixel"]), 1.0) / 2; p = np.array(sp["lage_uv"], float)
                c_ = np.array(t["mitte_uv"], float)
                if np.hypot(*(p - c_)) < 2 * s + 1.0: p = c_                   # DOM1-Maximum (1-m-Raster) nahe Dachmitte -> Spitze auf den First/die Mitte
                z0 = dach_hoehe(t, p) - 1.0
                basis = [[p[0] + dx, p[1] + dy, z0] for dx in (-s, s) for dy in (-s, s)]
                k = k + M.hull_points(basis + [[p[0], p[1], ziel]])
                belege.append(dict(seite="dach", element=f"Spitze Teil {i}", quelle=f"DOM1 {sp['pixel']} Pixel bis {sp['dom1_max']:.1f} m; Hoehe "
                                   + ("objekt.json hoehe_m" if zielhoehe and float(zielhoehe) >= sp["dom1_max"] else "DOM1-max"),
                                   hoehe=round(ziel, 2), hinweis=f"ANNAHME: Pyramide Grundseite {2 * s:.1f} m (sqrt Pixel), Form nicht gemessen"))
        else:
            eig = [w for w in wa if len(w) >= 3 and _abstand_rand(np.r_[(w[:, :2].mean(0) - m0) @ xh, (w[:, :2].mean(0) - m0) @ yh], uv) < 0.3
                   and all(_abstand_rand(np.r_[(w[:, :2].mean(0) - m0) @ xh, (w[:, :2].mean(0) - m0) @ yh], q) > 0.5 for j, q in enumerate(polys) if j != i)]
            if eig: h = float(max(w[:, 2].max() for w in eig) - g0); q = f"LoD2 {lid} Wandoberkante ({len(eig)} eigene Waende)"
            else:
                hs = meta.get("heights") or []; h = float(hs[i]) if i < len(hs) else float(max(w[:, 2].max() for w in wa) - g0); q = f"LoD2 {lid} heights"
            k = M.extrude(cs, h)
            belege.append(dict(seite="wand", element=f"Teil {i} (ohne Dachmessung)", quelle=q, hoehe=round(h, 2),
                               hinweis="ANNAHME: Flachdach auf Wandoberkante (Teil zu klein fuer DOM1-Dachfit)"))
        teile.append(k)
        su, sv = np.ptp(uv[:, 0]), np.ptp(uv[:, 1])
        belege.append(dict(seite="wand", element=f"Grundriss Teil {i}", quelle=f"LoD2 {lid} GroundSurface {i}", breite_u=round(su, 2), tiefe_v=round(sv, 2),
                           flaeche_m2=round(fl[i], 1)))
    k = teile[0]
    for t in teile[1:]: k = k + t
    return k, belege, polys[haupt]


if __name__ == "__main__":
    k, bl, _ = gebaeude_aus_lod2(sys.argv[1])
    mesh = k.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]
    print(f"Koerper {k.decompose().__len__()}, Volumen {k.volume():.0f} m3, z max {V[:, 2].max():.2f}")
    for b in bl: print(" ", b["element"], "|", b["quelle"][:80], "|", {x: y for x, y in b.items() if x in ("first", "hoehe", "neigung_grad")})
