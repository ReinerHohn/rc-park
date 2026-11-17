#!/usr/bin/env python3
"""druck_teilung.py <objekt> [--stl PFAD] - generische Druckteilung eines wasserdichten Generator-STL (nichts Objektspezifisches).

Ziel (Koordinator Runde 5, Nutzerregel: generisch): Teile so schneiden und hinlegen, dass Ueberhaenge > winkel minimal werden und jedes Teil auf das Druckbett passt.
Ablauf (alles automatisch, Parameter in objekt.json 'druck_teilung', sonst Standard):
  1. Schnittkandidaten = Hoehen mit viel NAHEZU WAAGERECHTER, NACH UNTEN zeigender Flaeche (Decken, Plattenunterseiten, Gesimsunterseiten; Histogramm 2 cm),
     gleiche Groesse wie druck_vorcheck (Ueberhang > winkel). Ein Schnitt genau in dieser Ebene macht die Unterseite zur Bettflaeche des oberen Teils.
  2. Gierig je Teil: besten Kandidaten waehlen (groesste Flaeche im Teil, nicht am Teilboden/-deckel), schneiden (manifold split_by_plane), nur behalten,
     wenn die Summe der Ueberhangflaechen (je Teil in seiner besten Lage) sinkt; bis Anteil <= ziel_anteil oder max_schnitte.
  3. Drucklage je Teil: 6 Achslagen (aufrecht, kopfueber, 4 Seitenlagen im Fassadenrahmen); Wahl = kleinste Ueberhangflaeche (Bettflaeche ausgenommen).
  4. Bett: passt ein Teil in seiner Lage nicht auf bett_mm (Standard Bambu P1S 256 mm, Rand 6 mm), senkrechter Schnitt in der Mitte der laengsten waagerechten Achse.
  5. Passstifte: je Schnitt 2-4 Bohrungen in beiden Haelften (Abstand zum Schnittrand >= stift_rand_mm), Durchmesser stift_mm + toleranz_mm, Tiefe je Seite
     stift_laenge_mm/2 + toleranz_mm; Stifte (stift_mm x stift_laenge_mm) als eigene STL - KEINE Zapfen am Teil (Bambu-Lehre: nie Zapfen unter breiter Flaeche).
  4b. LUFTINSELN (17.11.2026): je Teil in Drucklage tools/druck_luft.stuetzen (fuellen bis luft_frei_mm 1,2; 45-Grad-Konsolen im Innenraum bis luft_reich_mm 15);
     was bleibt, loest eine andere Achslage oder ein Schnitt genau in der Inselunterseite (Teil mindestens luft_min_teil_mm 8 hoch, sonst vorher mit dem Nachbarteil
     vereinigt, dessen Schnitt dann 'aufgehoben' ist). Am fertigen Teil werden die Stuetzen eingebaut; teilung.json je Teil 'luft' (Inseln vorher, gefuellt, Schraegen,
     Stuetzvolumen, verbleibende Inseln, stuetzen_noetig). --schicht_mm = Schichthoehe des Druckers (MK4S 0,8-Duese: 0.4); --ohne_luft = altes Verhalten.
Ausgabe: modelle/stl/<objekt>_teile/teil_NN.stl (mm, Drucklage, auf z=0), lage/teil_NN.stl (mm, Originallage fuer Overlay/Regel 9b), stifte.stl, teilung.json
(je Teil Lage, Bettmass, Ueberhang m2/Anteil, Schnitte, Stifte). Die Pruefung 'Ueberhang je Teil' liest teilung.json (pruefstand druck_teile_ueberhang)."""
import argparse, glob, json, math, os, sys
import numpy as np, trimesh, cv2
from manifold3d import Manifold as M, Mesh as MM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))


def zu_mf(tm):
    tm = tm.copy(); tm.merge_vertices(); tm.fix_normals()
    return M(MM(vert_properties=np.asarray(tm.vertices, np.float32), tri_verts=np.asarray(tm.faces, np.uint32)))


def zu_tm(mf):
    m = mf.to_mesh(); return trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3].astype(float), np.asarray(m.tri_verts), process=True)


def ohne_splitter(tm, v_min=1e-9):
    """Lappen ohne Volumen entfernen (17.11.2026: lag ein Schnitt bis auf Mikrometer in einer Stufenflaeche des Modells, blieben in der Schnittebene 34 Flaechenfetzen
    mit Volumen 0 am Teil - 'dicht=False', obwohl der Koerper selbst geschlossen war). Behaelt alle Stuecke mit Volumen > v_min m3."""
    if tm.is_watertight: return tm
    ks = [k for k in tm.split(only_watertight=False) if k.is_watertight and abs(k.volume) > v_min]
    return tm if not ks else (ks[0] if len(ks) == 1 else trimesh.util.concatenate(ks))


def lagen(B):
    """6 Achslagen: Rotationsmatrizen, die die Spalte 'oben' (Rahmenachse) auf +z drehen. B = Rahmen (u, n, z) als Spalten in Weltkoordinaten."""
    u, n, z = B[:, 0], B[:, 1], B[:, 2]; out = []
    for name, up, ax in (("aufrecht", z, u), ("kopfueber", -z, u), ("vorn_unten", -n, u), ("hinten_unten", n, u), ("seite_u+", u, n), ("seite_u-", -u, n)):
        ex = ax - up * (ax @ up); ex /= np.linalg.norm(ex); ey = np.cross(up, ex); out.append((name, np.vstack([ex, ey, up])))   # Zeilen = neue Achsen
    return out


def ueberhang(tm, Rr, cosg, bett_tol):
    N = tm.face_normals @ Rr.T; C = tm.triangles_center @ Rr.T; A = tm.area_faces; zb = C[:, 2].min() if len(C) else 0.0
    zmin = (tm.vertices @ Rr.T)[:, 2].min()
    ov = (N[:, 2] < -cosg) & (C[:, 2] > zmin + bett_tol)
    return float(A[ov].sum()), float(A.sum())


def kontakt(tm, Rr, bett_tol):
    """Auflageflaeche (m2) in dieser Lage: nach unten zeigende Flaechen innerhalb bett_tol ueber dem tiefsten Punkt."""
    N = tm.face_normals @ Rr.T; C = tm.triangles_center @ Rr.T; zmin = (tm.vertices @ Rr.T)[:, 2].min()
    return float(tm.area_faces[(N[:, 2] < -0.9) & (C[:, 2] <= zmin + bett_tol)].sum())


def beste_lage(tm, L, cosg, bett_tol, kontakt_min=0.25, bett_m=None):
    """Lage mit kleinster Ueberhangflaeche unter denen mit tragfaehiger Auflage (>= kontakt_min x groesste Auflage aller Lagen):
    sonst stuende z. B. ein Kegel auf der Spitze (Ueberhang 0, aber kein Stand)."""
    werte = []
    for name, Rr in L:
        o, a = ueberhang(tm, Rr, cosg, bett_tol); V = tm.vertices @ Rr.T; werte.append((name, o, a, Rr, V.max(0) - V.min(0), kontakt(tm, Rr, bett_tol)))
    kmax = max(w[5] for w in werte); ok = [w for w in werte if w[5] >= kontakt_min * kmax]
    if bett_m is not None and any(w[4].max() <= bett_m for w in ok): ok = [w for w in ok if w[4].max() <= bett_m]   # Lagen, die aufs Bett passen, zuerst
    return min(ok, key=lambda w: w[1])[:5]


def kandidaten(tm, B, cosg, schritt=0.02):
    """Hoehen (Rahmen-z) mit nahezu waagerechter Unterseite (|n_z| > 0,98, nach unten), Flaeche je 2-cm-Klasse, absteigend."""
    N = tm.face_normals @ B; C = tm.triangles_center @ B; A = tm.area_faces
    m = N[:, 2] < -0.98
    if not m.any(): return []
    k = np.round(C[m, 2] / schritt).astype(int); fl = {}
    for kk, aa, zz in zip(k, A[m], C[m, 2]): f_ = fl.setdefault(kk, [0.0, []]); f_[0] += aa; f_[1].append(zz)
    return sorted(((v[0], float(np.median(v[1]))) for v in fl.values()), reverse=True)


def rahmen_n(nvec):
    """Orthonormaler Rahmen (Spalten e1, e2, n) zu einer Schnittnormalen n."""
    n = np.asarray(nvec, float) / np.linalg.norm(nvec); h = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = h - n * (h @ n); e1 /= np.linalg.norm(e1); return np.c_[e1, np.cross(n, e1), n]


def schnittrahmen(s_, B):
    """-> (Rahmen, Achsindex) eines Schnitts: Achsschnitt im Fassadenrahmen B oder schraeger Schnitt (achse 'n', normal)."""
    return (rahmen_n(s_["normal"]), 2) if s_["achse"] == "n" else (B, "unz".index(s_["achse"]))


def schneide(mf, B, achse, wert):
    """Ebene (Rahmenachse 'achse' = wert): Rueckgabe (unten/hinten, oben/vorn) als Manifold."""
    nvec = B[:, achse]; oben, unten = mf.split_by_plane(tuple(float(x) for x in nvec), float(wert))
    return unten, oben


def weit_auseinander(dt, d_rand, lo, aufl, d_min, nmax):
    """Stiftpositionen aus der Distanzkarte dt: Kandidaten = Zellen mit dt >= d_rand; erster Punkt = groesster Randabstand, danach gierig 'weitester Punkt'
    (Kandidat mit dem groessten Mindestabstand zu den schon gewaehlten, solange dieser >= d_min).
    Vorher wurde bei jedem Schritt der ganze (N,k,3)-Abstandstensor neu gebildet (2-3 Mio Kandidaten x 8 Punkte: 74 s von 86 s Laufzeit des Werkzeugs).
    Jetzt Mindestabstand laufend fortgeschrieben (je Schritt nur die Abstaende zum NEUEN Punkt, O(N)) und Kandidatenliste + Suche auf der GPU
    (float64; Reihenfolge und Gleichstand-Regel wie numpy: kleinster Index) - Ergebnis gleich dem alten. Ohne CUDA oder RENDER_CPU=1: dieselbe Rechnung in numpy."""
    T = None
    if not os.environ.get("RENDER_CPU"):
        try:
            import torch
            if torch.cuda.is_available(): T = torch
        except Exception: T = None
    if T is not None:
        D = T.as_tensor(np.ascontiguousarray(dt), device="cuda"); idx = (D >= d_rand).nonzero()                  # (N,2) = (y,x), zeilenweise wie np.nonzero
        if not len(idx): return []
        v = D[idx[:, 0], idx[:, 1]]; i0 = int((v == v.max()).nonzero()[0, 0]); del D, v
        C = idx[:, [1, 0]].to(T.float64) * aufl; C = C + T.as_tensor(np.asarray(lo, np.float64), device="cuda"); del idx
        wahl = [C[i0]]; dd = None
        while len(wahl) < nmax:
            d = ((C - wahl[-1]) ** 2).sum(1).sqrt(); dd = d if dd is None else T.minimum(dd, d)
            m = dd.max()
            if float(m) < d_min: break
            wahl.append(C[int((dd == m).nonzero()[0, 0])])                                                    # kleinster Index unter Gleichstaenden (np.argmax)
        out = [w.cpu().numpy() for w in wahl]; del C, dd
        return out
    yy, xx = np.nonzero(dt >= d_rand)
    if not len(yy): return []
    cand = np.c_[xx, yy] * aufl + lo; wahl = [cand[np.argmax(dt[yy, xx])]]; dd = None
    while len(wahl) < nmax:
        d = np.sqrt(((cand - wahl[-1]) ** 2).sum(1)); dd = d if dd is None else np.minimum(dd, d)
        if dd.max() < d_min: break
        wahl.append(cand[np.argmax(dd)])
    return wahl


def stiftpunkte(mf, B, achse, wert, d_rand, d_min, nmax=4, aufl=0.01):
    """Punkte im Schnittquerschnitt mit Randabstand >= d_rand (Rasterung + Distanztransformation), gierig weit auseinander."""
    tm = zu_tm(mf); sec = tm.section(plane_origin=B[:, achse] * wert, plane_normal=B[:, achse])
    if sec is None: return []
    P = sec.vertices; j = [k for k in range(3) if k != achse]; Q = (P @ B)[:, j]
    lo = Q.min(0) - 0.1; hi = Q.max(0) + 0.1; W, H = (np.ceil((hi - lo) / aufl).astype(int) + 1)
    if W * H > 4e7: aufl *= math.sqrt(W * H / 4e7); W, H = (np.ceil((hi - lo) / aufl).astype(int) + 1)
    polys = []
    for ent in sec.entities:
        pts = (sec.vertices[ent.points] @ B)[:, j]; polys.append(np.round((pts - lo) / aufl).astype(np.int32))
    msk = np.zeros((H, W), np.uint8)                                                                # gerade-ungerade (XOR): Innenringe = Loecher bleiben leer
    for p_ in polys: t_ = np.zeros((H, W), np.uint8); cv2.fillPoly(t_, [p_], 1); msk ^= t_
    img = (msk > 0).astype(np.uint8)
    dt = cv2.distanceTransform(img, cv2.DIST_L2, 5) * aufl
    wahl = weit_auseinander(dt, d_rand, lo, aufl, d_min, nmax)
    if not wahl: return []
    out = []
    for w in wahl:
        p = np.zeros(3); p[j[0]], p[j[1]], p[achse] = w[0], w[1], wert; out.append(B @ p)
    return out


def bohrung(p, nvec, r, h):
    """Zylinder Radius r, Laenge h, Achse nvec, Mitte p (Welt)."""
    c = M.cylinder(h, r, r, 32, True); z = np.array([0, 0, 1.0]); v = np.cross(z, nvec); s = np.linalg.norm(v); cth = z @ nvec
    if s < 1e-9: Rm = np.eye(3) if cth > 0 else np.diag([1, -1, -1.0])
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]]) / s; ang = math.atan2(s, cth); Rm = np.eye(3) + math.sin(ang) * vx + (1 - math.cos(ang)) * vx @ vx
    T = np.c_[Rm, p]; return c.transform(T.tolist())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl"); ap.add_argument("--bett_mm", type=float, help="Kantenlaenge des Druckraums (kleinste Seite, z. B. 210 fuer Prusa MK4S 250x210x220); ersetzt objekt.json druck_teilung.bett_mm"); ap.add_argument("--toleranz_mm", type=float, help="Fuegespiel der Verbinder/Stifte (grobe Duese: 0.3)")
    ap.add_argument("--schicht_mm", type=float, help="Schichthoehe fuer die Luftinsel-Pruefung (druck_luft; Standard objekt.json druck_teilung.luft_schicht_mm, sonst 0.4)"); ap.add_argument("--luft_min_teil_mm", type=float, help="Mindesthoehe eines Teils bei Luft-Schnitten (Standard 8)")
    ap.add_argument("--ohne_luft", action="store_true", help="Luftinseln weder suchen noch beheben (nur Ueberhang-Teilung wie bis 17.11.2026)"); ap.add_argument("--aus", help="Ausgabeordner (Standard modelle/stl/<objekt>_teile)"); a = ap.parse_args()
    od = os.path.join(ROOT, "modelle", a.objekt); O = json.load(open(os.path.join(od, "objekt.json"))); cfg = O.get("druck_teilung") or {}
    sc = float(O.get("massstab") or os.environ.get("SCALE", 87)); K = 1000.0 / sc
    stl = a.stl or os.path.join(ROOT, "modelle", "stl", f"{a.objekt}_1-{int(sc)}.stl")
    if a.bett_mm: cfg = dict(cfg, bett_mm=a.bett_mm)
    if a.toleranz_mm: cfg = dict(cfg, toleranz_mm=a.toleranz_mm)
    winkel = float(cfg.get("winkel", 60)); cosg = math.cos(math.radians(90 - winkel)); ziel = float(cfg.get("ziel_anteil", 0.01)); bett = float(cfg.get("bett_mm", 256)) - 2 * float(cfg.get("bett_rand_mm", 6))
    max_schnitte = int(cfg.get("max_schnitte", 6)); bett_tol = float(cfg.get("bett_tol_m", 0.05)); min_flaeche = float(cfg.get("min_kandidat_m2", 2.0))
    sd, sl, tol = (float(cfg.get(k, d)) / K for k, d in (("stift_mm", 2.0), ("stift_laenge_mm", 6.0), ("toleranz_mm", 0.2)))
    srand = float(cfg.get("stift_rand_mm", 2.5)) / K; min_teil = float(cfg.get("min_teil_mm", 15.0)) / K      # Mindesthoehe eines Teils im Druck
    an = next((b["achse_n"] for b in O.get("bauteile", []) if b.get("achse_n") and b.get("aktiv", True) is not False), [0.0, 1.0])
    n_ = np.array(an + [0.0], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0], 0.0]); B = np.c_[u_, n_, [0, 0, 1.0]]
    tm0 = trimesh.load(stl, process=False); tm0.merge_vertices(); tm0.apply_scale(1.0 / K)
    if not tm0.is_watertight: sys.exit("druck_teilung: STL nicht wasserdicht - erst Druckpruefungen gruen machen")
    L = lagen(B); teile = [dict(mf=zu_mf(tm0), schnitte=[])]; schnitte = []; log = []
    bm = bett / K
    def lage_von(tm, t):
        if t.get("R") is not None or t.get("lage"):                                                # vom Luft-Schritt gewaehlte Lage (R: schraeg, Schnittebene aufs Bett)
            Rr = t["R"] if t.get("R") is not None else dict(L)[t["lage"]]; o, A_ = ueberhang(tm, Rr, cosg, bett_tol); V_ = tm.vertices @ Rr.T; return (t["lage"], o, A_, Rr, V_.max(0) - V_.min(0))
        return beste_lage(tm, L, cosg, bett_tol, bett_m=bm)
    def bewerte(t): tm = zu_tm(t["mf"]); bl = lage_von(tm, t); return tm, bl
    def zerlegen(ts): return [dict(mf=d_, schnitte=t["schnitte"]) for t in ts for d_ in t["mf"].decompose() if d_.volume() > 1e-4]
    def ueberhang_schnitte(teile, schnitte, log):
      for _ in range(max_schnitte):
          bestes = None
          for i, t in enumerate(teile):
              tm, bl = bewerte(t)
              if bl[1] / bl[2] <= ziel: continue
              V = tm.vertices @ B; zlo, zhi = V[:, 2].min(), V[:, 2].max()
              nk = 0
              for fl, zc in kandidaten(tm, B, cosg):
                  if fl < min_flaeche: break
                  if zc < zlo + min_teil or zc > zhi - min_teil: continue                             # 17.11.2026: am Turm entstanden Scheiben von 10 mm und ein Splitter von 0,8 mm Hoehe (Schnitte 0,9 m auseinander) - nicht druck- und steckbar
                  un, ob = schneide(t["mf"], B, 2, zc)
                  if un.is_empty() or ob.is_empty(): continue
                  if min(d_.volume() for x_ in (un, ob) for d_ in x_.decompose()) < 0.005 * t["mf"].volume(): continue      # kein Schnitt, der Splitter abtrennt
                  o2 = sum(beste_lage(zu_tm(x), L, cosg, bett_tol, bett_m=bm)[1] for x in (un, ob))
                  gew = bl[1] - o2
                  if gew > 0 and (bestes is None or gew > bestes[0]): bestes = (gew, i, zc, un, ob, fl)
                  nk += 1
                  if nk >= 5: break                                                                   # die 5 groessten Kandidaten je Teil (gierig, reproduzierbar)
          if bestes is None: return teile
          gew, i, zc, un, ob, fl = bestes; s_ = dict(achse="z", wert=round(zc, 4), grund=f"Unterseite {fl:.1f} m2 waagerecht nach unten -> Bettflaeche", gewinn_m2=round(gew, 2))
          schnitte.append(s_); t = teile.pop(i); teile += [dict(mf=un, schnitte=t["schnitte"] + [len(schnitte) - 1]), dict(mf=ob, schnitte=t["schnitte"] + [len(schnitte) - 1])]
          log.append(f"Schnitt z {zc:.3f}: Ueberhang -{gew:.2f} m2")
      return teile
    teile = ueberhang_schnitte(teile, schnitte, log)
    # 4: Bettgroesse (vorher zerlegen: ein Ueberhang-Schnitt kann Teile trennen)
    teile = zerlegen(teile)
    for _ in range(12):
        neu = []; geteilt = False
        for t in teile:
            tm, bl = bewerte(t); ext = bl[4] * K
            if ext.max() <= bett: neu.append(t); continue
            V = tm.vertices @ B; spann = V.max(0) - V.min(0); ax = int(np.argmax(spann))              # laengste Rahmenachse halbieren
            lo_, hi_ = V[:, ax].min(), V[:, ax].max(); best_ = None
            for w_ in np.linspace(lo_ + 0.35 * (hi_ - lo_), lo_ + 0.65 * (hi_ - lo_), 31):           # Schnittlage: kleinste Schnittflaeche im mittleren Drittel, keine Splitter (< 2 % Volumen)
                un_, ob_ = schneide(t["mf"], B, ax, float(w_))
                if un_.is_empty() or ob_.is_empty(): continue
                vmin_ = min(d_.volume() for x_ in (un_, ob_) for d_ in x_.decompose())
                if vmin_ < 0.02 * t["mf"].volume(): continue
                sec_ = tm.section(plane_origin=B[:, ax] * w_, plane_normal=B[:, ax]); fl_ = 0.0
                if sec_ is not None:
                    try: fl_ = float(sec_.to_planar()[0].area)
                    except Exception: fl_ = 0.0
                if best_ is None or fl_ < best_[0]: best_ = (fl_, float(w_), un_, ob_)
            if best_ is None: neu.append(t); continue
            wert, un, ob = best_[1], best_[2], best_[3]
            s_ = dict(achse="unz"[ax], wert=round(wert, 4), grund=f"Bett {bett:.0f} mm: Teil {ext.round(0).tolist()} mm, Mitte der laengsten Achse"); schnitte.append(s_)
            neu += [dict(mf=un, schnitte=t["schnitte"] + [len(schnitte) - 1]), dict(mf=ob, schnitte=t["schnitte"] + [len(schnitte) - 1])]; geteilt = True
            log.append(f"Bettschnitt {s_['achse']} {wert:.3f}")
        teile = zerlegen(neu)
        if not geteilt: break
    teile = ueberhang_schnitte(teile, schnitte, log)                                                # Bettschnitte aendern die Lagen: Ueberhang-Schnitte noch einmal
    # Zerfallene Teile (ein Schnitt trennt z. B. freistehende Helme) einzeln fuehren
    t2 = []
    for t in teile:
        for d_ in t["mf"].decompose(): t2.append(dict(mf=d_, schnitte=t["schnitte"]))
    teile = [t for t in t2 if t["mf"].volume() > 1e-4]
    # 4b: LUFTINSELN (17.11.2026, Turm-Bausatz: 6 von 7 Teilen hatten frei beginnende Flaechen; eine Uhr wurde heute Spaghetti). Je Teil in seiner Drucklage
    #     druck_luft.stuetzen (fuellen bis 1,2 mm, 45-Grad-Konsolen im Innenraum); was bleibt (aussen sichtbare Unterseiten, grosse flache Decken), wird
    #     a) durch eine andere Achslage geloest oder b) durch einen Schnitt genau in der Unterseite der Insel (sie wird Bettflaeche des oberen Teils);
    #     waere ein Stueck niedriger als luft_min_teil_mm, wird vorher mit dem Nachbarteil ueber dem/unter dem Schnitt vereinigt (Schnitt aufgehoben).
    #     Bewertung = verbleibende Inselflaeche (druck_luft, Schicht --schicht_mm); gierig, je Runde die beste Massnahme je Teil.
    import druck_luft as DL
    schicht = float(a.schicht_mm or cfg.get("luft_schicht_mm", 0.4)); luft_min = float(a.luft_min_teil_mm or cfg.get("luft_min_teil_mm", 8.0))
    luft_frei, luft_reich = float(cfg.get("luft_frei_mm", 1.2)), float(cfg.get("luft_reich_mm", 15.0)); cache = {}
    luft_saeule = float(cfg.get("luft_saeule_mm2", 40.0)); luft_gitter = float(cfg.get("luft_gitter_mm", 4.0)); gitter_d = 0.8      # Rest: Lamellen-Gitter (Stuetze im Modell, abbrechen)
    schnitt_kosten = float(cfg.get("luft_schnitt_mm3", 3000.0))                                    # ANNAHME: ein zusaetzliches Teil (Fuge, Verbinder, Kleben) wiegt so viel wie 3 cm3 Gitter (~3 min Druck + Nacharbeit)                                         # kleine Aussen-Inseln (Ecke eines flachen Pultdachs): Abbrech-Saeule statt Schnitt durchs ganze Gebaeude
    def druckform(t, lage=None):
        """-> (Manifold in Drucklage, Druck-mm, auf z=0 und xy-Mitte; 3x4-Matrix Welt(m) -> Druck(mm); Lagename)."""
        tm = zu_tm(t["mf"]); bl = lage_von(tm, dict(t, lage=lage, R=None) if lage else t); Rr = bl[3]; V_ = (tm.vertices @ Rr.T) * K
        sh = np.r_[(V_.min(0)[:2] + V_.max(0)[:2]) / 2, V_.min(0)[2]]; T = np.c_[Rr * K, -sh]
        return t["mf"].transform(T.tolist()), T, bl[0]
    gk = dict(gitter_schaetzen=luft_gitter, gitter_dicke=gitter_d)                                 # beim Bewerten ohne Gitter (Kosten = Gitterbedarf der Rest-Inseln), am Ende mit
    def luft(t, lage=None):
        k_ = (id(t["mf"]), lage or t.get("lage"))
        if k_ not in cache:
            mp, T, nm = druckform(t, lage); erg_, rest, prot = DL.stuetzen(mp, schicht, 45.0, 2.0, 5.0, luft_frei, luft_reich, saeule_mm2=luft_saeule, **gk)
            cache[k_] = dict(erg=erg_, rest=rest, prot=prot, T=T, lage=nm, R=T[:, :3] / K, mf=t["mf"], fl=sum(x["gitter_mm3"] for x in rest))      # Kosten = Lamellenvolumen (mm3), das die Rest-Inseln braeuchten
        return cache[k_]
    def hoehe_mm(mf, up): tm = zu_tm(mf); h_ = tm.vertices @ up; return (h_.max() - h_.min()) * K
    if not a.ohne_luft:
        for runde in range(int(cfg.get("luft_runden", 8))):
            besser = False
            for t in list(teile):
                r0 = luft(t)
                if not r0["rest"]: continue
                kand = []                                                                                 # (Restflaeche, Zahl neuer Teile, Art, Daten)
                tm = zu_tm(t["mf"]); kmax = max(kontakt(tm, Rr_, bett_tol) for _, Rr_ in L)
                for nm, Rr_ in L:                                                                          # a) andere Achslage (Auflage tragfaehig, passt aufs Bett)
                    if nm == r0["lage"]: continue
                    V_ = tm.vertices @ Rr_.T
                    if kontakt(tm, Rr_, bett_tol) < 0.25 * kmax or (V_.max(0) - V_.min(0)).max() > bm: continue
                    kand.append((luft(t, nm)["fl"] + 0.2 * schnitt_kosten, 0, "lage", nm))                       # andere Lage kostet etwas (Ueberhang/Druckzeit waren in der ersten Wahl schon guenstiger)
                Rr = r0["R"]; up = Rr[2]; ax = int(np.argmax(np.abs(up @ B))); sg = float(np.sign(up @ B[:, ax])); T = r0["T"]; achsig = abs(up @ B[:, ax]) > 0.9999
                N_ = tm.face_normals @ up; Pp = tm.triangles_center @ T[:, :3].T + T[:, 3]; Zp = Pp[:, 2]; Np = tm.face_normals @ Rr.T
                zi = []
                for x in sorted(r0["rest"], key=lambda x: -x["flaeche"]):
                    if all(abs(x["z"] - z_) > 1.5 * schicht for z_ in zi): zi.append(x["z"])
                ebenen = []
                for z_ in zi[:4]:                                                                         # b) Schnitt in der Unterseite der Insel
                    x_i = next(x for x in r0["rest"] if x["z"] == z_); bx = x_i["cs"].bounds()
                    m_ = (N_ < -0.98) & (Zp > z_ - 1.01 * schicht) & (Zp <= z_ + 1e-6)
                    zc = float(np.average(Zp[m_], weights=tm.area_faces[m_])) if m_.any() else z_ - 0.5 * schicht
                    if achsig: ebenen.append((z_, zc, ax, sg * (zc - T[2, 3]) / K, None))           # Druck-z -> Rahmenachse ax (Vorzeichen der Drucklage)
                    # SCHRAEGE Unterseite (17.11.2026: Traufkasten des Turms 1,5 Grad geneigt - jede waagerechte Schnittlage liess 0,5..8 cm2 Insel): Schnitt in IHRER Ebene, das obere Teil liegt mit ihr auf dem Bett
                    m2 = (Np[:, 2] < -0.97) & (Zp > z_ - 1.01 * schicht) & (Zp <= z_ + 1e-6) & (Pp[:, 0] > bx[0] - 1) & (Pp[:, 0] < bx[2] + 1) & (Pp[:, 1] > bx[1] - 1) & (Pp[:, 1] < bx[3] + 1)
                    if m2.any():
                        i2 = np.nonzero(m2)[0]; kd = i2[np.argsort(-tm.area_faces[i2])[:300]]                  # vorherrschende Flaechenrichtung (waagerechte Simse in derselben Hoehe mitteln sonst die Neigung weg)
                        ag = [(tm.area_faces[i2][Np[i2] @ Np[k] > 0.99996].sum(), k) for k in kd]; k0 = max(ag)[1]; m2 = np.zeros(len(Np), bool); m2[i2[Np[i2] @ Np[k0] > 0.99996]] = True
                        nm = -(Np[m2] * tm.area_faces[m2, None]).sum(0); nm /= np.linalg.norm(nm); c_ = np.average(Pp[m2], axis=0, weights=tm.area_faces[m2])
                        m3 = (Np @ -nm > 0.9997) & (np.abs((Pp - c_) @ nm) < 0.3)                         # alle Flaechen derselben Ebene (bis 1,4 Grad, 0,3 mm) -> Ebene neu mitteln
                        if m3.any(): nm = -(Np[m3] * tm.area_faces[m3, None]).sum(0); nm /= np.linalg.norm(nm); c_ = np.average(Pp[m3], axis=0, weights=tm.area_faces[m3])
                        kipp = math.degrees(math.acos(min(1.0, nm[2])))
                        if 0.3 < kipp < 10.0:
                            n_w = Rr.T @ nm; p_w = Rr.T @ (c_ - T[:, 3]) / K; ebenen.append((z_, float(c_[2]), None, float(n_w @ p_w), n_w))
                for z_, zc, ax_e, wert, n_w in ebenen:
                    for seite in (None, -1, 1):                                                           # ohne / mit Nachbar unten / oben vereinigt
                        basis, weg = t, None
                        if seite is not None:                                                                 # Nachbarn = Teile, die mit t an EINER Schnittebene anliegen (die Schnittliste eines Teils ist seine ganze Herkunft - 17.11.2026: so wurde ein entfernter Helm 'Nachbar')
                            ri = seite * sg; tl_, th_ = (tm.vertices @ B[:, ax]).min(), (tm.vertices @ B[:, ax]).max(); nb = []
                            for si in set(t["schnitte"]):
                                s0 = schnitte[si]
                                if s0.get("aufgehoben") or s0["achse"] != "unz"[ax] or abs((th_ if ri > 0 else tl_) - s0["wert"]) > 2e-3: continue
                                for q in teile:
                                    if q is t or si not in q["schnitte"]: continue
                                    vq = zu_tm(q["mf"]).vertices @ B[:, ax]
                                    if abs((vq.min() if ri > 0 else vq.max()) - s0["wert"]) <= 2e-3: nb.append((q, si))
                            if not nb: continue
                            sis = {si for _, si in nb}; qs = [q for q, _ in nb]; qs = [q for k__, q in enumerate(qs) if all(q is not q2 for q2 in qs[:k__])]
                            basis = dict(mf=M.batch_boolean([t["mf"]] + [q["mf"] for q in qs], __import__("manifold3d").OpType.Add), schnitte=sorted((set(t["schnitte"]).union(*[set(q["schnitte"]) for q in qs])) - sis)); weg = (qs, sis)
                        if n_w is None: un, ob = schneide(basis["mf"], B, ax, wert)
                        else: ob, un = basis["mf"].split_by_plane(tuple(float(v) for v in n_w), wert)
                        if un.is_empty() or ob.is_empty(): continue
                        if min(d_.volume() for x_ in (un, ob) for d_ in x_.decompose() if d_.volume() > 1e-6) < 0.002 * basis["mf"].volume(): continue      # Fetzen ohne Volumen (Schnitt genau in der Flaeche) zaehlen nicht
                        Rs = None if n_w is None else rahmen_n(n_w).T                                     # schraeg: Zeilen e1, e2, n -> Schnittebene = Bett des oberen Teils
                        neu_ = [dict(mf=d_, schnitte=basis["schnitte"] + ["neu"], **(dict(R=Rs, lage="schraeg") if (Rs is not None and k__ == 1) else {})) for k__, x_ in enumerate((un, ob)) for d_ in x_.decompose() if d_.volume() > 1e-4]
                        if min(hoehe_mm(n_["mf"], up) for n_ in neu_) < luft_min: continue                # je Stueck (17.11.2026: Hoehe ueber zwei getrennte Koerper gemessen liess ein 3-mm-Stueck durch)
                        if any(bewerte(n_)[1][4].max() > bm for n_ in neu_): continue
                        if r0["lage"] in dict(L):                                                          # neue Stuecke auch in der Lage des Ausgangsteils bewerten (17.11.2026: die abgetrennte Galerie lag sonst auf der Seite und ihr Gitterbedarf verdeckte den Gewinn des Schnitts)
                            for n_ in neu_:
                                if n_.get("R") is not None: continue
                                tq = zu_tm(n_["mf"]); Rq = dict(L)[r0["lage"]]; Vq = tq.vertices @ Rq.T
                                if (Vq.max(0) - Vq.min(0)).max() <= bm and kontakt(tq, Rq, bett_tol) >= 0.25 * max(kontakt(tq, R_, bett_tol) for _, R_ in L) and luft(n_, r0["lage"])["fl"] < luft(n_)["fl"]: n_["lage"] = r0["lage"]
                        dteile = len(neu_) - 1 - (len(weg[0]) if weg else 0)
                        kand.append((sum(luft(n_)["fl"] for n_ in neu_) - (sum(luft(q)["fl"] for q in weg[0]) if weg else 0.0) + schnitt_kosten * max(dteile, 0), dteile + (0.5 if n_w is not None else 0), "schnitt", (z_, zc, wert, ax, neu_, weg, basis, n_w)))
                        break                                                                             # ohne Vereinigung moeglich -> nicht noch mit Nachbarn
                if os.environ.get("LUFT_DEBUG"): print("  Kandidaten", r0["lage"], round(r0["fl"]), [(round(k_[0]), k_[2], k_[3] if k_[2] == "lage" else round(k_[3][0], 2)) for k_ in kand], flush=True)
                if not kand: continue
                rest_alt = r0["fl"] + 0.0; best = min(kand, key=lambda k_: (round(k_[0], 1), k_[1]))
                if best[0] >= rest_alt - 1e-6: continue
                if best[2] == "lage":
                    t["lage"] = best[3]; log.append(f"Luft: Lage {best[3]} statt {r0['lage']} - Gitterbedarf {rest_alt:.0f} -> {best[0]:.0f} mm3")
                else:
                    z_, zc, wert, ax_, neu_, weg, basis, n_w = best[3]
                    s_ = dict(achse="unz"[ax_] if n_w is None else "n", wert=round(wert, 5), grund=f"Luftinsel {z_:.1f} mm ueber dem Bett ({r0['lage']}): Schnitt in ihrer Unterseite -> Bettflaeche", luft=True)
                    if n_w is not None: s_["normal"] = np.round(n_w, 7).tolist(); s_["grund"] += f" (schraeg {math.degrees(math.acos(min(1.0, abs(float(n_w @ up))))):.1f} Grad)"
                    if weg:
                        for si in weg[1]: schnitte[si]["aufgehoben"] = True
                        s_["grund"] += f"; Schnitt {sorted(weg[1])} dafuer aufgehoben"
                        for q in weg[0]: teile.remove(q)
                    schnitte.append(s_); teile.remove(t)
                    for n_ in neu_: n_["schnitte"] = [len(schnitte) - 1 if x_ == "neu" else x_ for x_ in n_["schnitte"]]; teile.append(n_)
                    log.append(f"Luft-Schnitt {s_['achse']} {wert:.4f} (Insel {z_:.1f} mm, Unterseite {zc:.2f} mm{', mit Nachbar vereinigt' if weg else ''}): Gitterbedarf {rest_alt:.0f} -> {best[0]:.0f} mm3")
                print(log[-1]); besser = True
            if not besser: break
    # 5: Passstifte je Schnitt (Bohrung durch beide Haelften)
    stifte = []
    for si, s_ in enumerate(schnitte):
        if s_.get("aufgehoben"): continue
        Bf, ax = schnittrahmen(s_, B); nvec = Bf[:, ax]; pts = []; beteiligt = [zu_tm(t["mf"]) for t in teile if si in t["schnitte"]]
        def beidseitig(p):                                                                          # Bohrung muss auf BEIDEN Seiten ganz im Material liegen (Stiftlaenge/2 + Spiel, Ring mit Radius+Rand)
            ring = [np.zeros(3)] + [r_ * (Bf[:, (ax + 1) % 3] * math.cos(w_) + Bf[:, (ax + 2) % 3] * math.sin(w_)) for r_ in (sd / 2 + srand * 0.5,) for w_ in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
            for sg in (1, -1):
                P_ = np.array([p + sg * nvec * tt + o_ for tt in np.linspace(0.02 * sl, sl / 2 + tol, 4) for o_ in ring])
                if not any(m_.contains(P_).all() for m_ in beteiligt): return False
            return True
        for t in teile:
            if si not in t["schnitte"]: continue
            pts += [p for p in stiftpunkte(t["mf"], Bf, ax, s_["wert"], srand + sd / 2, 6 * sd, nmax=8) if all(np.linalg.norm(p - q) > 2 * sd for q in pts) and beidseitig(p)]
        s_["stifte"] = [np.round(p, 3).tolist() for p in pts]
        for p in pts:
            loch = bohrung(p, nvec, (sd + tol) / 2, sl + 2 * tol)
            for t in teile:
                if si in t["schnitte"]: t["mf"] = t["mf"] - loch
            stifte.append(bohrung(np.zeros(3), np.array([0, 0, 1.0]), sd / 2, sl).translate((len(stifte) * 3 * sd, 0, sl / 2)))
    # Ausgabe
    ad = a.aus or os.path.join(ROOT, "modelle", "stl", f"{a.objekt}_teile"); gross = "/media/oem/scan/rc-park_stl"
    if not a.aus and not os.path.exists(ad) and os.path.isdir(gross): os.makedirs(os.path.join(gross, f"{a.objekt}_teile"), exist_ok=True); os.symlink(os.path.join(gross, f"{a.objekt}_teile"), ad)      # 17.11.2026: 238 MB Druckteile des Turms landeten auf der Systemplatte (Regel: grosse Daten nur auf der Datenplatte, Verknuepfung im Repo)
    os.makedirs(os.path.join(ad, "lage"), exist_ok=True); bericht = []
    for alt_ in glob.glob(os.path.join(ad, "teil_*.stl")) + glob.glob(os.path.join(ad, "lage", "teil_*.stl")) + glob.glob(os.path.join(ad, "verbinder_*.stl")) + glob.glob(os.path.join(ad, "stifte.stl")): os.remove(alt_)      # 17.11.2026: Teile eines frueheren Laufs blieben liegen (7 neue + 3 alte Dateien = falscher Bausatz)
    stuetz_welt = []; gk = dict(gitter_mm=luft_gitter, gitter_dicke=gitter_d)
    for k_, t in enumerate(sorted(teile, key=lambda t: -t["mf"].volume())):
        tm = ohne_splitter(zu_tm(t["mf"])); name, o, A, Rr, ext = lage_von(tm, t); lu = None
        if not a.ohne_luft:                                                                         # Stuetzen (druck_luft.stuetzen) am FERTIGEN Teil (mit Stiftbohrungen) in Drucklage
            mp, T, _ = druckform(t); erg_, rest, prot = DL.stuetzen(mp, schicht, 45.0, 2.0, 5.0, luft_frei, luft_reich, saeule_mm2=luft_saeule, **gk)
            Ti = np.linalg.inv(np.r_[T, [[0, 0, 0, 1]]])[:3]; zus = erg_ - mp
            if prot["volumen_mm3"] > 0 and not zus.is_empty(): stuetz_welt.append(zus.transform(Ti.tolist()))
            lu = dict(schicht_mm=schicht, inseln_vorher=prot["inseln_vorher"], flaeche_vorher_mm2=prot["flaeche_vorher_mm2"], gefuellt=prot["fuellen"], schraegen=prot["schraege"],
                      stuetzen_mm3=prot["volumen_mm3"], saeulen_abbrechen=prot["saeulen"], gitter_abbrechen=prot["gitter"], luftinseln=len(rest), flaeche_mm2=prot["flaeche_rest_mm2"], stuetzen_noetig=bool(rest),
                      inseln=[dict(z_mm=round(x["z"], 2), flaeche_mm2=round(x["flaeche"], 1), mitte_mm=np.round(x["mitte"], 1).tolist()) for x in rest[:20]])
            td = zu_tm(erg_); tl = zu_tm(erg_.transform(Ti.tolist())); tl.apply_scale(K); tl.export(os.path.join(ad, "lage", f"teil_{k_ + 1:02d}.stl"))
            print(f"teil_{k_ + 1:02d}: Luftinseln {prot['inseln_vorher']} -> gestuetzt ({prot['fuellen']} gefuellt, {prot['schraege']} Schraegen, {len(prot['saeulen'])} Abbrech-Saeulen, {len(prot['gitter'])} Abbrech-Gitter ({sum(g_['volumen_mm3'] for g_ in prot['gitter']) / 1000:.1f} cm3), +{prot['volumen_mm3'] / 1000:.1f} cm3) -> {len(rest)} bleiben" + (" - STUETZEN NOETIG" if rest else ""))
        else:
            (tm.copy().apply_scale(K)).export(os.path.join(ad, "lage", f"teil_{k_ + 1:02d}.stl"))
            td = tm.copy(); td.apply_transform(np.r_[np.c_[Rr, np.zeros(3)], [[0, 0, 0, 1]]]); td.apply_translation(-np.r_[td.bounds[0, :2] + (td.bounds[1, :2] - td.bounds[0, :2]) / 2, td.bounds[0, 2]]); td.apply_scale(K)
        td.export(os.path.join(ad, f"teil_{k_ + 1:02d}.stl"))
        V = tm.vertices @ B
        bericht.append(dict(teil=f"teil_{k_ + 1:02d}", lage=name, bett_mm=np.round(ext * K, 1).tolist(), passt=bool(ext.max() * K <= bett), ueberhang_m2=round(o, 3), flaeche_m2=round(A, 2),
                            ueberhang_anteil=round(o / A, 5), wasserdicht=bool(tm.is_watertight), volumen_m3=round(float(tm.volume), 2),
                            rahmen_u=np.round([V[:, 0].min(), V[:, 0].max()], 2).tolist(), rahmen_n=np.round([V[:, 1].min(), V[:, 1].max()], 2).tolist(), rahmen_z=np.round([V[:, 2].min(), V[:, 2].max()], 2).tolist(),
                            schnitte=t["schnitte"], luft=lu))
    # 5b: Verbinderringe (17.11.2026): hohle Teile haben keine Wand fuer Stifte - am Turm 4 Schnitte, 0 Stifte, die Teile haetten sich nur stumpf stapeln lassen.
    #     Je waagerechtem Schnitt ohne Stift ein loser Ring, der innen an der Wand beider Teile anliegt (Spiel toleranz_mm), flach druckbar; unten einkleben, oberes Teil aufstecken.
    import manifold3d as _m3; verbinder = []; mf0 = zu_mf(tm0)
    if stuetz_welt: mf0 = mf0 + M.batch_boolean(stuetz_welt, _m3.OpType.Add)                        # Verbinderringe duerfen nicht in Konsolen/Fuellungen der Luft-Stuetzen stecken
    vh, vw = (float(cfg.get(k, d)) / K for k, d in (("verbinder_hoehe_mm", 3.0), ("verbinder_wand_mm", 1.2)))
    def gefuellt(cs):
        aus = [q for q in cs.to_polygons() if len(q) >= 3 and 0.5 * float(np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1])) > 0]
        return _m3.CrossSection(aus, _m3.FillRule.NonZero) if aus else _m3.CrossSection()
    for si, s_ in enumerate(schnitte):
        if s_["achse"] not in ("z", "n") or s_.get("stifte") or s_.get("aufgehoben"): continue
        mfr = mf0 if s_["achse"] == "z" else mf0.transform(np.c_[rahmen_n(s_["normal"]).T, np.zeros(3)].tolist())      # schraeger Schnitt: Modell so drehen, dass die Schnittebene waagerecht liegt
        zc = float(s_["wert"]); lo_, hi_ = mfr.slice(zc - 0.03), mfr.slice(zc + 0.03); hohl = (gefuellt(lo_) ^ gefuellt(hi_)) - (lo_ + hi_)
        ring = hohl.offset(-tol, _m3.JoinType.Round) - hohl.offset(-(tol + vw), _m3.JoinType.Round)
        if ring.is_empty() or ring.area() < 1e-3: s_["verbinder"] = "kein Hohlraum am Schnitt - stumpf kleben"; continue
        k3 = ring.extrude(2 * vh).translate((0, 0, zc - vh)) - mfr; st_ = [d_ for d_ in k3.decompose() if d_.volume() > min(0.2 * ring.area(), vw * 15.0 / K) * 2 * vh]      # 17.11.2026: Innenrippen (druck_rippen.py) teilen den Ring in Stuecke - Stuecke ab 15 mm Laenge bleiben (8 mm liess ein 5-mm-Eckstueck als Verbinder stehen)
        if not st_: s_["verbinder"] = "Ring kollidiert mit dem Modell - stumpf kleben"; continue
        k3 = M.batch_boolean(st_, _m3.OpType.Add) if len(st_) > 1 else st_[0]
        if k3.slice(zc - vh + 0.2 / K).area() < 0.3 * ring.area(): s_["verbinder"] = "Ring unten von Luft-Stuetzen verdraengt - stumpf kleben"; continue      # 17.11.2026: Konsolen im kopfueber gedruckten Teil am Schnitt liessen vom Ring unten nur Fetzen (Slicer: keine erste Schicht)
        nr_ = len(verbinder) + 1; verbinder.append(nr_)
        from bauteile import stl_schreiben                                                          # 17.11.2026: direkter Export eines an Luft-Stuetzen beschnittenen Rings war nicht wasserdicht (169 Fetzen, Slicer: "no extrusions in the first layer")
        vp_ = os.path.join(ad, f"verbinder_{nr_:02d}.stl"); k3s = k3.translate((0, 0, -(zc - vh))).scale((K, K, K)); stl_schreiben(k3s, vp_, b"rcpark verbinder")
        tv = trimesh.load(vp_, process=True)
        if not tv.is_watertight: tv = ohne_splitter(tv); tv.export(vp_)
        bb_ = tv.bounds
        s_["verbinder"] = dict(datei=f"verbinder_{nr_:02d}.stl", stuecke=len(st_), masse_mm=[round(float(bb_[1][j] - bb_[0][j]), 1) for j in range(3)], hinweis="in das untere Teil kleben, oberes Teil aufstecken")
        print(f"verbinder_{nr_:02d}: Schnitt {s_['achse']} {zc:.2f} m, {len(st_)} Stueck(e), {s_['verbinder']['masse_mm']} mm")
    if stifte:
        st = zu_tm(M.batch_boolean(stifte, __import__("manifold3d").OpType.Add)); st.apply_scale(K); st.export(os.path.join(ad, "stifte.stl"))
    erg = dict(stl=os.path.relpath(stl, ROOT), modell_volumen_m3=round(float(abs(tm0.volume)), 3), massstab=sc, winkel_grad=winkel, ziel_anteil=ziel, bett_mm_nutzbar=bett, stift=dict(d_mm=sd * K, laenge_mm=sl * K, toleranz_mm=tol * K, anzahl=len(stifte)),
               schnitte=schnitte, teile=bericht, luftinseln=(None if a.ohne_luft else sum(b["luft"]["luftinseln"] for b in bericht)), max_ueberhang_anteil=max(b["ueberhang_anteil"] for b in bericht), alle_passen=all(b["passt"] for b in bericht), log=log,
               hinweis="Ueberhang = Flaechen mit Normale steiler als winkel nach unten, ohne Bettflaeche (bett_tol_m); Lage = beste von 6 Achslagen. ANNAHME Stift 2 x 6 mm, Spiel 0,2 mm")
    json.dump(erg, open(os.path.join(ad, "teilung.json"), "w"), indent=1, ensure_ascii=False)
    for b in bericht: print(f"{b['teil']}: {b['lage']:12s} {b['bett_mm']} mm passt={b['passt']} Ueberhang {b['ueberhang_m2']} m2 = {100 * b['ueberhang_anteil']:.2f} % dicht={b['wasserdicht']} z {b['rahmen_z']}")
    print("Schnitte:", [(s['achse'], s['wert'], len(s.get('stifte', []))) for s in schnitte]); print("->", os.path.join(ad, "teilung.json"))


if __name__ == "__main__":
    main()
