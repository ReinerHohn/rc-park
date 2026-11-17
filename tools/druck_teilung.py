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
Ausgabe: modelle/stl/<objekt>_teile/teil_NN.stl (mm, Drucklage, auf z=0), lage/teil_NN.stl (mm, Originallage fuer Overlay/Regel 9b), stifte.stl, teilung.json
(je Teil Lage, Bettmass, Ueberhang m2/Anteil, Schnitte, Stifte). Die Pruefung 'Ueberhang je Teil' liest teilung.json (pruefstand druck_teile_ueberhang)."""
import argparse, glob, json, math, os, sys
import numpy as np, trimesh, cv2
from manifold3d import Manifold as M, Mesh as MM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl"); ap.add_argument("--bett_mm", type=float, help="Kantenlaenge des Druckraums (kleinste Seite, z. B. 210 fuer Prusa MK4S 250x210x220); ersetzt objekt.json druck_teilung.bett_mm"); ap.add_argument("--toleranz_mm", type=float, help="Fuegespiel der Verbinder/Stifte (grobe Duese: 0.3)"); a = ap.parse_args()
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
    def bewerte(t): tm = zu_tm(t["mf"]); bl = beste_lage(tm, L, cosg, bett_tol, bett_m=bm); return tm, bl
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
    # 5: Passstifte je Schnitt (Bohrung durch beide Haelften)
    stifte = []
    for si, s_ in enumerate(schnitte):
        ax = "unz".index(s_["achse"]); nvec = B[:, ax]; pts = []; beteiligt = [zu_tm(t["mf"]) for t in teile if si in t["schnitte"]]
        def beidseitig(p):                                                                          # Bohrung muss auf BEIDEN Seiten ganz im Material liegen (Stiftlaenge/2 + Spiel, Ring mit Radius+Rand)
            ring = [np.zeros(3)] + [r_ * (B[:, (ax + 1) % 3] * math.cos(w_) + B[:, (ax + 2) % 3] * math.sin(w_)) for r_ in (sd / 2 + srand * 0.5,) for w_ in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
            for sg in (1, -1):
                P_ = np.array([p + sg * nvec * tt + o_ for tt in np.linspace(0.02 * sl, sl / 2 + tol, 4) for o_ in ring])
                if not any(m_.contains(P_).all() for m_ in beteiligt): return False
            return True
        for t in teile:
            if si not in t["schnitte"]: continue
            pts += [p for p in stiftpunkte(t["mf"], B, ax, s_["wert"], srand + sd / 2, 6 * sd, nmax=8) if all(np.linalg.norm(p - q) > 2 * sd for q in pts) and beidseitig(p)]
        s_["stifte"] = [np.round(p, 3).tolist() for p in pts]
        for p in pts:
            loch = bohrung(p, nvec, (sd + tol) / 2, sl + 2 * tol)
            for t in teile:
                if si in t["schnitte"]: t["mf"] = t["mf"] - loch
            stifte.append(bohrung(np.zeros(3), np.array([0, 0, 1.0]), sd / 2, sl).translate((len(stifte) * 3 * sd, 0, sl / 2)))
    # Ausgabe
    ad = os.path.join(ROOT, "modelle", "stl", f"{a.objekt}_teile"); gross = "/media/oem/scan/rc-park_stl"
    if not os.path.exists(ad) and os.path.isdir(gross): os.makedirs(os.path.join(gross, f"{a.objekt}_teile"), exist_ok=True); os.symlink(os.path.join(gross, f"{a.objekt}_teile"), ad)      # 17.11.2026: 238 MB Druckteile des Turms landeten auf der Systemplatte (Regel: grosse Daten nur auf der Datenplatte, Verknuepfung im Repo)
    os.makedirs(os.path.join(ad, "lage"), exist_ok=True); bericht = []
    for alt_ in glob.glob(os.path.join(ad, "teil_*.stl")) + glob.glob(os.path.join(ad, "lage", "teil_*.stl")) + glob.glob(os.path.join(ad, "verbinder_*.stl")) + glob.glob(os.path.join(ad, "stifte.stl")): os.remove(alt_)      # 17.11.2026: Teile eines frueheren Laufs blieben liegen (7 neue + 3 alte Dateien = falscher Bausatz)
    for k_, t in enumerate(sorted(teile, key=lambda t: -t["mf"].volume())):
        tm = ohne_splitter(zu_tm(t["mf"])); name, o, A, Rr, ext = beste_lage(tm, L, cosg, bett_tol, bett_m=bm)
        (tm.copy().apply_scale(K)).export(os.path.join(ad, "lage", f"teil_{k_ + 1:02d}.stl"))
        td = tm.copy(); td.apply_transform(np.r_[np.c_[Rr, np.zeros(3)], [[0, 0, 0, 1]]]); td.apply_translation(-np.r_[td.bounds[0, :2] + (td.bounds[1, :2] - td.bounds[0, :2]) / 2, td.bounds[0, 2]])
        td.apply_scale(K); td.export(os.path.join(ad, f"teil_{k_ + 1:02d}.stl"))
        V = tm.vertices @ B
        bericht.append(dict(teil=f"teil_{k_ + 1:02d}", lage=name, bett_mm=np.round(ext * K, 1).tolist(), passt=bool(ext.max() * K <= bett), ueberhang_m2=round(o, 3), flaeche_m2=round(A, 2),
                            ueberhang_anteil=round(o / A, 5), wasserdicht=bool(tm.is_watertight), volumen_m3=round(float(tm.volume), 2),
                            rahmen_u=np.round([V[:, 0].min(), V[:, 0].max()], 2).tolist(), rahmen_n=np.round([V[:, 1].min(), V[:, 1].max()], 2).tolist(), rahmen_z=np.round([V[:, 2].min(), V[:, 2].max()], 2).tolist(),
                            schnitte=t["schnitte"]))
    # 5b: Verbinderringe (17.11.2026): hohle Teile haben keine Wand fuer Stifte - am Turm 4 Schnitte, 0 Stifte, die Teile haetten sich nur stumpf stapeln lassen.
    #     Je waagerechtem Schnitt ohne Stift ein loser Ring, der innen an der Wand beider Teile anliegt (Spiel toleranz_mm), flach druckbar; unten einkleben, oberes Teil aufstecken.
    import manifold3d as _m3; verbinder = []; mf0 = zu_mf(tm0)
    vh, vw = (float(cfg.get(k, d)) / K for k, d in (("verbinder_hoehe_mm", 3.0), ("verbinder_wand_mm", 1.2)))
    def gefuellt(cs):
        aus = [q for q in cs.to_polygons() if len(q) >= 3 and 0.5 * float(np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1])) > 0]
        return _m3.CrossSection(aus, _m3.FillRule.NonZero) if aus else _m3.CrossSection()
    for si, s_ in enumerate(schnitte):
        if s_["achse"] != "z" or s_.get("stifte"): continue
        zc = float(s_["wert"]); lo_, hi_ = mf0.slice(zc - 0.03), mf0.slice(zc + 0.03); hohl = (gefuellt(lo_) ^ gefuellt(hi_)) - (lo_ + hi_)
        ring = hohl.offset(-tol, _m3.JoinType.Round) - hohl.offset(-(tol + vw), _m3.JoinType.Round)
        if ring.is_empty() or ring.area() < 1e-3: s_["verbinder"] = "kein Hohlraum am Schnitt - stumpf kleben"; continue
        k3 = ring.extrude(2 * vh).translate((0, 0, zc - vh)) - mf0; st_ = [d_ for d_ in k3.decompose() if d_.volume() > min(0.2 * ring.area(), vw * 8.0 / K) * 2 * vh]      # 17.11.2026: Innenrippen (druck_rippen.py) teilen den Ring in Stuecke - Stuecke ab 8 mm Laenge bleiben
        if not st_: s_["verbinder"] = "Ring kollidiert mit dem Modell - stumpf kleben"; continue
        k3 = M.batch_boolean(st_, _m3.OpType.Add) if len(st_) > 1 else st_[0]; nr_ = len(verbinder) + 1; verbinder.append(nr_)
        tv = zu_tm(k3.translate((0, 0, -(zc - vh)))); tv.apply_scale(K); tv.export(os.path.join(ad, f"verbinder_{nr_:02d}.stl")); bb_ = tv.bounds
        s_["verbinder"] = dict(datei=f"verbinder_{nr_:02d}.stl", stuecke=len(st_), masse_mm=[round(float(bb_[1][j] - bb_[0][j]), 1) for j in range(3)], hinweis="in das untere Teil kleben, oberes Teil aufstecken")
        print(f"verbinder_{nr_:02d}: Schnitt z {zc:.2f} m, {len(st_)} Stueck(e), {s_['verbinder']['masse_mm']} mm")
    if stifte:
        st = zu_tm(M.batch_boolean(stifte, __import__("manifold3d").OpType.Add)); st.apply_scale(K); st.export(os.path.join(ad, "stifte.stl"))
    erg = dict(stl=os.path.relpath(stl, ROOT), modell_volumen_m3=round(float(abs(tm0.volume)), 3), massstab=sc, winkel_grad=winkel, ziel_anteil=ziel, bett_mm_nutzbar=bett, stift=dict(d_mm=sd * K, laenge_mm=sl * K, toleranz_mm=tol * K, anzahl=len(stifte)),
               schnitte=schnitte, teile=bericht, max_ueberhang_anteil=max(b["ueberhang_anteil"] for b in bericht), alle_passen=all(b["passt"] for b in bericht), log=log,
               hinweis="Ueberhang = Flaechen mit Normale steiler als winkel nach unten, ohne Bettflaeche (bett_tol_m); Lage = beste von 6 Achslagen. ANNAHME Stift 2 x 6 mm, Spiel 0,2 mm")
    json.dump(erg, open(os.path.join(ad, "teilung.json"), "w"), indent=1, ensure_ascii=False)
    for b in bericht: print(f"{b['teil']}: {b['lage']:12s} {b['bett_mm']} mm passt={b['passt']} Ueberhang {b['ueberhang_m2']} m2 = {100 * b['ueberhang_anteil']:.2f} % dicht={b['wasserdicht']} z {b['rahmen_z']}")
    print("Schnitte:", [(s['achse'], s['wert'], len(s.get('stifte', []))) for s in schnitte]); print("->", os.path.join(ad, "teilung.json"))


if __name__ == "__main__":
    main()
