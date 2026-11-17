#!/usr/bin/env python3
"""druck_rippen.py <ein.stl> <aus.stl> [--abstand_mm 60] [--dicke_mm 0.9] [--tiefe_mm 6] [--schritt_mm 0.8] [--ecke_mm 0 (aus)] [--dick_mm 2.4] [--bild PFAD.png]
Duenne Gebaeudewaende von INNEN mit senkrechten Rippen und Eckzwickeln aussteifen (Druck-Nachlauf; Generator und abgenommenes STL bleiben unberuehrt). Masse in Druck-mm, z = Druckrichtung.

Anlass 17.11.2026: Demodruck Turmschaft auf dem MK4S (129 x 136 x 102 mm, Wand 1 mm, 0,8-mm-Duese = EINE Bahn, kein Brim): die lange Wand bog sich durch.
Nutzer: "wir werden sehr viele grosse Gebaeude haben mit moeglichst duenner Wand, die wir mit Rippen verstaerken muessen, damit wir schnell drucken."
Quellenlage (Recherche 17.11.2026): Rippen steifen staerker aus als eine dickere Wand (dicke Waende schrumpfen und verziehen mehr); konkrete Rippenabstaende fand sich
in keiner Quelle -> Standardwerte hier sind ANNAHME, am Probedruck zu pruefen.
Druckzeit gemessen (17.11.2026, Turmschaft 129 x 136 x 102 mm, MK4S 0,8-Duese, Schicht 0,4, PrusaSlicer): ohne Rippen 1 h 33 min; Abstand 35 / 1,6 mm / mit Eckzwickeln
3 h 04 min; 60 / 1,6 mit Zwickeln 2 h 38; 60 / 1,6 ohne 2 h 12; 50 / 1,0 mit Zwickeln 2 h 18; 60 / 0,9 (EINE Bahn) ohne Zwickel 1 h 49 (+18 %) = Standard.
Zwickel kosten ~25 min (Dreiecke werden gefuellt) -> nur auf Wunsch (--ecke_mm 6).

Verfahren (generisch, aus waagerechten Scheiben - kein Wissen ueber das Gebaeude):
  1. Scheiben der Hoehe --schritt_mm. Je Scheibe: Material S; Umriss F = S mit Fenstern bis 2 x 7 mm zugeschlossen; Innenraum C = (F - S), nur wo darueber Material liegt
     (ein oben offener Hof bleibt frei - dort waeren Rippen sichtbar), schmale Ausbuchtungen (< 3 mm) weggeoeffnet.
  2. Fensterluecken = Teile von F - S - C, die sowohl an den Innenraum als auch an die Aussenseite grenzen; Rippen halten --fenster_mm Abstand davon (nicht durchs Fenster sichtbar).
  3. Rippenrichtungen: aus allen Innenkanten (laengengewichtet, modulo 180 Grad) die Hauptrichtungen des Gebaeudes. Rippen stehen senkrecht auf der Wand an FESTEN Stellen
     k x --abstand_mm entlang der Hauptrichtung (gleiche Stelle in jeder Scheibe -> durchgehende senkrechte Rippe), --rand_mm Abstand von den Kantenenden.
     Kanten keiner Hauptrichtung (schraeg, >= --kante_mm lang) bekommen Rippen ab Kantenmitte. Gerundete Waende (kurze Kanten) bekommen keine (Kruemmung steift selbst aus).
  4. Eckzwickel: an konvexen Gebaeudeecken (Innenwinkel < 150 Grad) innen ein Dreieck mit Schenkeln --ecke_mm.
  5. Wandstuecke dicker als --dick_mm brauchen keine Rippe (dort entfallen sie).
  6. Druckbarkeit von UNTEN: eine Rippe darf je Scheibe nur um Scheibenhoehe (45 Grad) aus der Wand oder der Rippe darunter herauswachsen -> nach einem Fenster
     setzt sie mit einer 45-Grad-Schraege wieder an, nie frei in der Luft.
  7. Modell + Rippen; Pruefung: wasserdicht, Koerperzahl gleich, Volumen.
rc 3, wenn das Ergebnis nicht wasserdicht ist oder in mehr Koerper zerfaellt. Bild (--bild): Querschnitte, Modell grau, Rippen rot - ANSEHEN.
Grenzen: nur aufrecht gedruckte Modelle; Hohlraeume, die oben offen sind (Druckteil ohne Dach), bekommen Rippen nur, wenn das ganze Modell (vor der Teilung) gegeben wird
-> im Bausatz VOR druck_teilung auf den ganzen Koerper anwenden. Verbinderringe der Teilung werden von Rippen in Stuecke geteilt (druck_teilung behaelt Stuecke ab 8 mm).
"""
import sys, os, argparse, numpy as np, trimesh
from manifold3d import Manifold as M, Mesh, CrossSection as CS, FillRule, JoinType, OpType
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))
RUND = JoinType.Round; ECKIG = JoinType.Miter


def _fl(q):
    return 0.5 * float(np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1]))


def gefuellt(cs):
    aus = [q for q in cs.to_polygons() if len(q) >= 3 and _fl(q) > 0]
    return CS(aus, FillRule.NonZero) if aus else CS()


def ringe(cs, eps=0.8):
    """Umrisse des Innenraums als Punktfolgen; links der Kante liegt der Innenraum (CCW aussen, CW Loecher - Clipper-Konvention)."""
    return [q.astype(float) for q in cs.simplify(eps).to_polygons() if len(q) >= 3]


def kanten(cs, eps=0.8):
    return [(a, b) for q in ringe(cs, eps) for a, b in zip(q, np.roll(q, -1, 0)) if np.hypot(*(b - a)) > 1e-6]


def richtungen(alle_kanten, min_anteil=0.05, spreiz=12.0):
    """Hauptrichtungen (Grad, modulo 180) aus laengengewichtetem Histogramm."""
    w = np.zeros(180)
    for a, b in alle_kanten:
        d = b - a; L = float(np.hypot(*d)); w[int(np.degrees(np.arctan2(d[1], d[0])) % 180) % 180] += L
    if w.sum() <= 0: return []
    g = np.zeros(180)
    for s in range(-2, 3): g += np.roll(w, s)                                         # 5-Grad-Glaettung (zyklisch)
    fam = []; rest = g.copy()
    while rest.max() > min_anteil * g.sum() / 5.0 and len(fam) < 6:
        k = int(rest.argmax()); idx = np.arange(k - 5, k + 6) % 180; ww = w[idx]
        ang = (k + float(np.sum(ww * (np.arange(-5, 6))) / max(ww.sum(), 1e-9))) % 180; fam.append(ang)
        rest[np.arange(int(k - spreiz), int(k + spreiz) + 1) % 180] = 0
    return fam


def zwickel(cs, ecke, eps=0.8, max_winkel=150.0):
    """Dreieckszwickel (Schenkel = ecke) an konvexen Ecken des Innenraums (= Aussenecken des Gebaeudes), Innenwinkel < max_winkel."""
    out = []
    for q in cs.simplify(eps).to_polygons():
        if len(q) < 3: continue
        for a, v, b in zip(np.roll(q, 1, 0), q, np.roll(q, -1, 0)):
            e1 = a - v; e2 = b - v; l1 = float(np.hypot(*e1)); l2 = float(np.hypot(*e2))
            if l1 < ecke or l2 < ecke: continue
            kr = float((v - a)[0] * (b - v)[1] - (v - a)[1] * (b - v)[0])
            w = np.degrees(np.arccos(np.clip(np.dot(e1, e2) / (l1 * l2), -1, 1)))
            if kr > 0 and w < max_winkel: out.append(np.array([v - (e1 / l1) * 0.8 - (e2 / l2) * 0.8, v + e1 / l1 * ecke, v + e2 / l2 * ecke], float))
    return out


def rippen_flaechen(rr, fam, abstand, dicke, tiefe, rand, kante_min, spreiz=12.0, eingriff=1.5, kurz=4.0):
    """Rechtecke der Rippen (2D). Gleichgerichtete Kanten eines Umrisses werden zu EINER Wand zusammengefasst (17.11.2026: an welligen Reliefwaenden zerfiel die Wand
    in kurze Teilkanten, der Randabstand je Teilkante liess die Rippen in jeder zweiten Scheibe fallen); kurze Zacken (< kurz mm) ohne Richtung gehoeren zur Wand."""
    re = []; ohne = 0.0
    fd = [np.array([np.cos(np.radians(f)), np.sin(np.radians(f))]) for f in fam]
    def rechteck(q, d):
        nv = np.array([-d[1], d[0]]); a = q - d * dicke / 2; b = q + d * dicke / 2       # links = Innenraum
        re.append(np.array([a - nv * eingriff, b - nv * eingriff, b + nv * tiefe, a + nv * tiefe]))
    for q in rr:
        E = [(a, b) for a, b in zip(q, np.roll(q, -1, 0)) if np.hypot(*(b - a)) > 1e-6]
        if not E: continue
        fz = []
        for a, b in E:
            e = b - a; ang = np.degrees(np.arctan2(e[1], e[0])) % 360; best = None
            for k, f in enumerate(fam):
                for s_, ff in ((1, f), (-1, (f + 180) % 360)):
                    dw = abs((ang - ff + 180) % 360 - 180)
                    if dw <= spreiz and (best is None or dw < best[0]): best = (dw, k, s_)
            fz.append(None if best is None else (best[1], best[2]))
        L = [float(np.hypot(*(b - a))) for a, b in E]
        for j in range(len(E)):                                                    # kurze Zacken ohne Richtung: Richtung des Vorgaengers
            if fz[j] is None and L[j] < kurz: fz[j] = ("zacke",)
        st = next((j for j in range(len(E)) if fz[j] != fz[j - 1] and fz[j] != ("zacke",)), None)
        if st is None: st = 0
        runs = []; cur = None
        for jj in range(len(E)):
            j = (st + jj) % len(E); f = fz[j]
            if f == ("zacke",) and cur is not None: cur[1].append(j); continue
            if cur is None or f != cur[0]: cur = [f, [j]]; runs.append(cur)
            else: cur[1].append(j)
        for f, js in runs:
            if f is None or f == ("zacke",):
                for j in js:
                    if f is None and L[j] >= kante_min:
                        a, b = E[j]; d = (b - a) / L[j]; m = 0.5 * (a + b); nn = int((L[j] / 2 - rand) // abstand)
                        for i_ in range(-nn, nn + 1): rechteck(m + i_ * abstand * d, d)
                    elif f is None: ohne += L[j]
                continue
            d = fd[f[0]] * f[1]; ta = float(np.dot(E[js[0]][0], d)); tb = float(np.dot(E[js[-1]][1], d))
            for k in range(int(np.ceil((ta + rand) / abstand)), int(np.floor((tb - rand) / abstand)) + 1):
                tk = k * abstand; fuss = None
                for j in js:
                    a, b = E[j]; t0, t1 = float(np.dot(a, d)), float(np.dot(b, d))
                    if min(t0, t1) <= tk <= max(t0, t1) and abs(t1 - t0) > 1e-9: fuss = a + (tk - t0) / (t1 - t0) * (b - a); break
                if fuss is not None: rechteck(fuss, d)
    return re, ohne


def rippen(modell, abstand=60.0, dicke=0.9, tiefe=6.0, schritt=0.8, ecke=0.0, dick=2.4, schliess=7.0, fenster=2.0, rand=6.0, kante_min=20.0, melde=None, ohne_decke=False):
    bb = modell.bounding_box(); zs = np.arange(bb[2], bb[5], schritt); n = len(zs)
    S = [modell.slice(float(z + schritt / 2)).simplify(0.02) for z in zs]
    D = [None] * n; decke = CS()
    for i in range(n - 1, -1, -1): D[i] = decke; decke = (decke + S[i]).simplify(0.05)
    C = [CS()] * n; F = [CS()] * n
    for i in range(n):
        if S[i].is_empty() or (D[i].is_empty() and not ohne_decke): continue
        F[i] = gefuellt(S[i].offset(schliess, ECKIG, 2.0)).offset(-schliess, ECKIG, 2.0)
        c = (F[i] - S[i]) if ohne_decke else (F[i] - S[i]) ^ D[i]
        if not c.is_empty(): C[i] = c.offset(-1.5, RUND, 2.0, 12).offset(1.5, RUND, 2.0, 12)
    alle = [k for i in range(0, n, 5) for k in kanten(C[i])]; fam = richtungen(alle)
    if melde: melde(f"Hauptrichtungen der Innenwaende: {', '.join(f'{f:.1f}' for f in fam) or 'keine'} Grad; {n} Scheiben je {schritt} mm")
    R = [CS()] * n; teile = []; ohne = 0.0; prot = []
    for i in range(n):
        if C[i].is_empty(): continue
        re, o = rippen_flaechen(ringe(C[i]), fam, abstand, dicke, tiefe, rand, kante_min); ohne += o
        roh = CS([q for q in re], FillRule.NonZero) if re else CS()
        ec = zwickel(C[i], ecke) if ecke > 0.5 else []                                                        # 17.11.2026: Ausrunden per Oeffnung fuellte an welligen Reliefwaenden lange Streifen - jetzt Dreiecke nur an echten Ecken
        if ec: roh = roh + CS(ec, FillRule.NonZero)
        if roh.is_empty(): continue
        roh = roh ^ (C[i].offset(0.05, ECKIG, 2.0) + S[i])                              # 0,05: Innenraum und Wand beruehren sich nur - ohne Ueberlapp zerfiel die Rippe in zwei Stuecke
        rest = ((F[i] - S[i]) - C[i]) ^ C[i].offset(fenster + 1.5, RUND, 2.0, 8)
        win = [g for g in rest.decompose() if g.area() > 0.05 and not (g.offset(0.05, RUND) ^ C[i]).is_empty() and not (g.offset(0.05, RUND) - F[i]).is_empty()]      # Luecke geht DURCH die Wand (17.11.2026: mit 0,4 mm galten Steinfugen aussen auf der 1-mm-Wand als Fenster)
        if win: roh = roh - CS.batch_boolean(win, OpType.Add).offset(fenster, RUND, 2.0, 12)
        th = S[i].offset(-dick / 2, RUND, 2.0, 8)
        if not th.is_empty(): roh = roh - th.offset(dick / 2 + 1.0 + tiefe, RUND, 2.0, 8)
        if i > 0: roh = roh ^ ((R[i - 1] - S[i]) + S[i]).offset(schritt, RUND, 2.0, 8)              # 45 Grad: nie frei in der Luft ansetzen
        roh = roh.simplify(0.02)                                                      # Rippe greift in die Wand ein (17.11.2026: "- S" liess Rippen 0,1..0,8 mm vor der Wand frei stehen, 28 Koerper)
        if roh.is_empty(): continue
        st_ = [g for g in roh.decompose() if (g - S[i]).area() > 0.2 and (g ^ S[i]).area() > 0.3]      # nur Stuecke, die WIRKLICH in die Wand greifen (Zwickel an Fensterschlitzen beruehrten sie nur -> 24 lose Koerper)
        if not st_: continue
        roh = CS.batch_boolean(st_, OpType.Add)
        if roh.area() < 0.2: continue
        R[i] = roh; prot.append((float(zs[i]), roh.area()))
        teile.append(roh.offset(0.05, ECKIG, 2.0).extrude(schritt * 1.25).translate((0, 0, float(zs[i]) - schritt * 0.25)))
        if melde and len(teile) % 200 == 0: melde(f"  {len(teile)} Scheiben mit Rippen ...")
    return (M.batch_boolean(teile, OpType.Add) if teile else M()), dict(richtungen=fam, ohne_rippe_kante_mm=round(ohne / max(n, 1), 1), scheiben=len(prot)), (zs, S, R)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("aus")
    for k, d in (("abstand_mm", 60.0), ("dicke_mm", 0.9), ("tiefe_mm", 6.0), ("schritt_mm", 0.8), ("ecke_mm", 0.0), ("dick_mm", 2.4), ("fenster_mm", 2.0), ("rand_mm", 6.0), ("kante_mm", 20.0)):
        ap.add_argument("--" + k, type=float, default=d)
    ap.add_argument("--ohne_decke", action="store_true", help="einzelnes, oben offenes Druckteil: jeder umschlossene Innenraum zaehlt (sonst nur Innenraum unter Material)")
    ap.add_argument("--bild", default=""); a = ap.parse_args()
    m = trimesh.load(a.ein, process=True); modell = M(Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
    if modell.is_empty(): print(f"FEHLER: {a.ein} ist kein geschlossener Koerper ({modell.status()})"); return 2
    v0 = modell.volume(); n0 = len(modell.decompose()); print(f"Modell {os.path.basename(a.ein)}: {modell.num_tri()} Dreiecke, {v0 / 1000:.1f} cm3, {n0} Koerper")
    rp, info, (zs, S, R) = rippen(modell, a.abstand_mm, a.dicke_mm, a.tiefe_mm, a.schritt_mm, a.ecke_mm, a.dick_mm, 7.0, a.fenster_mm, a.rand_mm, a.kante_mm, print, a.ohne_decke)
    if rp.is_empty(): print("keine Rippe noetig/moeglich (kein geschlossener Innenraum mit duenner Wand) - Modell unveraendert kopiert"); import shutil; shutil.copy(a.ein, a.aus); return 0
    erg = modell + rp; st = sorted(erg.decompose(), key=lambda x: -x.volume())
    if len(st) > n0 and sum(x.volume() for x in st[n0:]) < 1e-4 * v0: erg = M.batch_boolean(st[:n0], OpType.Add) if n0 > 1 else st[0]
    v1 = erg.volume(); n1 = len(erg.decompose()); from bauteile import stl_schreiben; stl_schreiben(erg, a.aus, b"rcpark rippen")
    w = trimesh.load(a.aus, process=True); dicht = bool(w.is_watertight)
    print(f"Rippen: {info['scheiben']} Scheiben, +{(v1 - v0) / 1000:.1f} cm3 ({(v1 - v0) / v0 * 100:.0f} % mehr Material); Abstand {a.abstand_mm:g}, Dicke {a.dicke_mm:g}, Tiefe {a.tiefe_mm:g} mm (ANNAHME)")
    print(f"  Innenkante ohne Rippe (rund/kurz) im Mittel je Scheibe: {info['ohne_rippe_kante_mm']} mm")
    print(f"Volumen vorher {v0 / 1000:.1f} cm3 -> nachher {v1 / 1000:.1f} cm3; {n1} Koerper (vorher {n0}); wasserdicht: {'ja' if dicht else 'NEIN'}; {len(w.faces)} Dreiecke -> {a.aus}")
    if a.bild:
        import cv2
        bb = modell.bounding_box(); px = 0.2; rd = 4.0; W = int((bb[3] - bb[0] + 2 * rd) / px); H = int((bb[4] - bb[1] + 2 * rd) / px); bl = []
        mit = [i for i in range(len(zs)) if not R[i].is_empty()]
        for i in [mit[int(len(mit) * f)] for f in (0.1, 0.4, 0.7, 0.95)] if mit else []:
            im = np.full((H, W, 3), 255, np.uint8)
            for cs, col in ((S[i], (150, 150, 150)), (R[i], (40, 40, 220))):
                mk = np.zeros((H, W), np.uint8)
                for q in sorted(cs.to_polygons(), key=lambda q_: -abs(_fl(q_))):
                    c = np.stack([(q[:, 0] - bb[0] + rd) / px, H - (q[:, 1] - bb[1] + rd) / px], 1).astype(np.int32); cv2.fillPoly(mk, [c], 1 if _fl(q) > 0 else 0)
                im[mk > 0] = col
            cv2.putText(im, f"z = {zs[i]:.1f} mm  grau Modell, rot Rippen", (8, 22), 0, 0.6, (0, 0, 0), 2); bl.append(im)
        if bl:
            rows = [np.hstack(bl[j:j + 2]) if j + 1 < len(bl) else np.hstack([bl[j], np.full_like(bl[j], 255)]) for j in range(0, len(bl), 2)]
            cv2.imwrite(a.bild, np.vstack(rows)); print(f"Bild (ansehen): {a.bild}")
    return 0 if (dicht and n1 <= n0) else 3


if __name__ == "__main__":
    sys.exit(main())
