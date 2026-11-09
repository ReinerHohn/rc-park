"""Gauben Runde 4 (9.11.): Form aus den Fotos an bekannten Lagen. Eingabe = gauben_r3.json (5 Lagen t0/s0 in Dachebenen-Koordinaten + Dachebene aus gauben_ortho.py).
Je Gaube und Foto (sieht die Lage, Kamera < --maxdist 40 m, bis --kfotos 12 naechste): Fenster um die projizierte Lage auf der Stabilitaetskarte, HoughLinesP auf Karte >= 0,3,
Linien nach erwarteter Bildrichtung sortiert (Richtungen aus 3D-Vorgabe projiziert: Fronttraufe = Traufrichtung et, Kehle links/rechts = Frontecke -> Firstende, Ortgang = Frontecke -> Scheitel),
2D-Schnittpunkte: Frontecken (Front x Kehle), Firstende (Kehle x Kehle), Scheitel (Ortgang x Ortgang, optional). Triangulation jedes Punkts als Strahlenschnitt (kleinste Quadrate)
ueber >= --ntri 3 Fotos (Punkte liegen NICHT in der Dachebene), Residuum berichtet. Primitiv: Breite = |L-R|, Fronttraufe h_t = Hoehe der Frontmitte ueber der Ebene, Tiefe = waagerechter
Abstand Frontmitte -> Firstende, Scheitel h_f aus Ortgang-Triangulation, sonst Sweep-Raster (ANNAHME-Kennzeichnung). Reihenregel (Median, 15 cm), Gate: Umriss-Kantenbelegung
>= --fotomin 0,5 in >= --nfoto 3 Fotos je Gaube UND alle 5 -> gauben_abgenommen.json (quelle 14), sonst gauben_r4.json.
Aufruf: gauben_tri.py SWEEP.npz GAUBEN_R3.json OUT.json --kam KAM.json --stabil DIR [--maxdist 40 --kfotos 12 --ntri 3 --fotomin 0.5 --nfoto 3] [--audit DIR]"""
import sys, os, json, numpy as np, torch, cv2
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
MAXD, KF, NTRI, FOTOMIN, NFOTO = g("--maxdist", 40.0), g("--kfotos", 12, int), g("--ntri", 3, int), g("--fotomin", 0.5), g("--nfoto", 3, int)
dev = "cuda"; torch.cuda.set_per_process_memory_fraction(float(os.environ.get("RCPARK_GPU_ANTEIL", "0.1")))
SW = np.load(a[1])["P"].astype(np.float32); G3 = json.load(open(a[2])); KAM = json.load(open(g("--kam", "", str))); sd = g("--stabil", "", str); audit = g("--audit", os.path.dirname(a[3]), str)
E = G3["dachebene"]; n = np.array(E["n"]); d = E["d"]; et = np.array(E["et"]); eh = np.array(E["eh"]); alpha = E["alpha"]; up = np.array([0, 0, 1.0])
def ebene_punkt(t, s): z = -(d + s * (n @ eh)) / n[2]; return t * et + s * eh + np.array([0, 0, z])
def hoehe(X): return float(X @ n + d) / n[2] * 1.0                                               # senkrechte Hoehe ueber der Ebene (n.X + d = Abstand, / nz = lotrecht)
lagen = [gb for gb in G3["gauben"] if gb["tiefe"] <= 3.0]; print("Lagen:", [(round(gb["t0"], 2), round(gb["s0"], 2)) for gb in lagen], flush=True)
KARTEN = {}
def karte(f):
    if f not in KARTEN: KARTEN[f] = cv2.imread(os.path.join(sd, os.path.splitext(f)[0] + ".png"), 0)
    return KARTEN[f]
def proj(k, X, sj):
    R = np.array(k["Rn"]); t = np.array(k["tn"]); Xc = R @ np.atleast_2d(X).T + t[:, None]; x = Xc[0] / Xc[2]; y = Xc[1] / Xc[2]; f1 = 1 + k["params"][3] * (x * x + y * y)
    return np.stack([(k["f"] * x * f1 + k["cx"]) * sj, (k["f"] * y * f1 + k["cy"]) * sj], 1), Xc[2]
def strahl(k, uv, sj):
    """Weltstrahl (C, Richtung) durch Kartenpixel uv (Verzeichnung rueckwaerts, 3 Iterationen)."""
    u, v = uv[0] / sj, uv[1] / sj; x0, y0 = (u - k["cx"]) / k["f"], (v - k["cy"]) / k["f"]; x, y = x0, y0
    for _ in range(3): r2 = x * x + y * y; x, y = x0 / (1 + k["params"][3] * r2), y0 / (1 + k["params"][3] * r2)
    r = np.array(k["Rn"]).T @ np.array([x, y, 1.0]); return np.array(k["C"]), r / np.linalg.norm(r)
def triang(strahlen):
    """Kleinste-Quadrate-Schnitt von Strahlen [(C, r)]: Punkt X mit minimaler Summe der Abstandsquadrate; gibt X, mittleres Residuum (m)."""
    A = np.zeros((3, 3)); b = np.zeros(3)
    for C, r in strahlen: P = np.eye(3) - np.outer(r, r); A += P; b += P @ C
    X = np.linalg.solve(A, b); res = [np.linalg.norm((np.eye(3) - np.outer(r, r)) @ (X - C)) for C, r in strahlen]; return X, float(np.mean(res))
def schnitt(l1, l2):
    """Schnittpunkt zweier Bildgeraden (x1,y1,x2,y2)."""
    x1, y1, x2, y2 = l1; x3, y3, x4, y4 = l2; den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-6: return None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den; py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den; return np.array([px, py])
def winkel(l): return np.arctan2(l[3] - l[1], l[2] - l[0])
def wdiff(a1, a2): dd = abs((a1 - a2 + np.pi / 2) % np.pi - np.pi / 2); return dd

ergebnis = []
for gi, gb in enumerate(lagen):
    t0, s0 = gb["t0"], gb["s0"]; F0 = ebene_punkt(t0, s0) + 0.4 * up                                     # Vorgabe: Frontmitte ~0,4 m ueber der Ebene
    w0, L0, hf0 = 1.2, g("--l0", 3.5), 1.2; cL0, cR0 = F0 - w0 / 2 * et, F0 + w0 / 2 * et; E0 = ebene_punkt(t0, s0 + L0); A0 = ebene_punkt(t0, s0) + hf0 * up   # Vorgabe-Tiefe 3,5 m (Kehlen in 6261/nu laenger als 2,5 m)
    box3 = np.array([ebene_punkt(t0 + dt, s0 + ds) + dh * up for dt in (-1.3, 1.3) for ds in (-0.6, 3.6) for dh in (0.0, 1.8)])
    # Fotos: sehen die Lage, Kamera < MAXD, naechste KF
    fs = []
    for f in sorted(KAM):
        k = KAM[f]
        if not os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png")): continue
        dist = np.linalg.norm(np.array(k["C"]) - F0)
        if dist > MAXD: continue
        V = karte(f); H, W = V.shape; sj = W / k["W"]; uv, z = proj(k, box3, sj)
        if (z < 2).any() or uv[:, 0].min() < 0 or uv[:, 1].min() < 0 or uv[:, 0].max() >= W or uv[:, 1].max() >= H: continue
        fs.append((dist, f))
    fs = [f for _, f in sorted(fs)[:KF]] + ([f for f in g("--fotos", "", str).split(",") if f in dict((f_, 1) for _, f_ in fs) and f not in [f2 for _, f2 in sorted(fs)[:KF]]] if "--fotos" in a else []); beob = {"ecke_L": [], "ecke_R": [], "firstende": [], "scheitel": []}; protokoll = []
    for f in fs:
        k = KAM[f]; V = karte(f); H, W = V.shape; sj = W / k["W"]; uv, _ = proj(k, box3, sj); x0, y0 = int(uv[:, 0].min()), int(uv[:, 1].min()); x1, y1 = int(uv[:, 0].max()) + 1, int(uv[:, 1].max()) + 1
        crop = (V[y0:y1, x0:x1] >= g("--kthr", 0.15) * 255).astype(np.uint8) * 255                 # Kehlen stehen in den Karten nur mit 0,15-0,4 (Lauf 4: 1-6 Linien bei >= 0,3)
        lines = cv2.HoughLinesP(crop, 1, np.pi / 180, threshold=10, minLineLength=max(10, int(0.15 * min(crop.shape))), maxLineGap=8)
        if lines is None: protokoll.append((f, "keine Linien")); continue
        lines = lines.reshape(-1, 4).astype(float) + np.array([x0, y0, x0, y0])
        # erwartete Bildrichtungen aus der 3D-Vorgabe
        P2 = lambda X: proj(k, X, sj)[0][0]
        aF = winkel(np.r_[P2(cL0), P2(cR0)]); aKL = winkel(np.r_[P2(cL0), P2(E0)]); aKR = winkel(np.r_[P2(cR0), P2(E0)]); aOL = winkel(np.r_[P2(cL0), P2(A0)]); aOR = winkel(np.r_[P2(cR0), P2(A0)])
        pF, pE, pcL, pcR, pA = P2(F0), P2(E0), P2(cL0), P2(cR0), P2(A0); achse = pE - pF; achse /= max(np.linalg.norm(achse), 1e-9); quer = np.array([-achse[1], achse[0]])
        if (pcL - pF) @ quer > 0: quer = -quer                                                            # quer zeigt zur linken Ecke
        dbg = []
        def waehle(ang, seite=None, tol=np.deg2rad(14), nahe=None, maxabst=None):
            best = None; n_ang = n_seite = n_nahe = 0
            for l in lines:
                if wdiff(winkel(l), ang) > tol: continue
                n_ang += 1; m = np.array([(l[0] + l[2]) / 2, (l[1] + l[3]) / 2]); q = (m - pF) @ quer
                if seite == "L" and q < 0: continue
                if seite == "R" and q > 0: continue
                n_seite += 1
                if nahe is not None and maxabst is not None and np.linalg.norm(m - nahe) > maxabst: continue
                n_nahe += 1; ln = np.hypot(l[2] - l[0], l[3] - l[1])
                # Auswahl nach NAEHE zur erwarteten Linie (Mittelpunktabstand / Skala + 2 x Winkelfehler), nicht nach Laenge (Lauf 7: laengste Linie = First-/Traufkante)
                sc_ = (np.linalg.norm(m - nahe) / max(skala, 1e-6) if nahe is not None else 0) + 2 * wdiff(winkel(l), ang) - 0.002 * ln
                if best is None or sc_ < best[0]: best = (sc_, l)
            dbg.append((n_ang, n_seite, n_nahe)); return None if best is None else best[1]
        skala = np.linalg.norm(pcR - pcL) / w0                                                             # px je Meter an der Gaube
        # Lauf 8: Mittelpunkt-Naehe zu streng/zu lasch. Jetzt REGION: erwartetes Dreieck (Ecken, Firstende) um --rand_m (0,7 m) aufgeweitet; Kehlen = Linien mit BEIDEN Endpunkten
        # in der Region, Winkel < 25 Grad zur erwarteten Kehle, Seite nach Achse, je Seite die laengste; Front = Linie in der Region nahe pF (< 0,8 m) mit Frontwinkel
        rm = g("--rand_m", 0.7) * skala; ctr = (pcL + pcR + pE) / 3; poly = np.array([P_ + (P_ - ctr) / max(np.linalg.norm(P_ - ctr), 1e-9) * rm for P_ in (pcL, pcR, pE)], np.float32)
        inpoly = lambda P_: cv2.pointPolygonTest(poly, (float(P_[0]), float(P_[1])), False) >= 0
        dbg = []
        def waehle(ang, seite=None, tol=np.deg2rad(g("--wtol", 25.0)), nahe=None, maxabst=None):
            best = None; n_ang = n_seite = n_reg = 0
            for l in lines:
                if wdiff(winkel(l), ang) > tol: continue
                n_ang += 1; m = np.array([(l[0] + l[2]) / 2, (l[1] + l[3]) / 2]); q = (m - pF) @ quer
                if seite == "L" and q < 0: continue
                if seite == "R" and q > 0: continue
                n_seite += 1
                if not inpoly(m): continue                                                         # Mittelpunkt in der Region (Lauf 9: beide Endpunkte war zu streng, Hough-Linien laufen weit)
                if nahe is not None and maxabst is not None and np.linalg.norm(m - nahe) > maxabst: continue
                n_reg += 1; ln = np.hypot(l[2] - l[0], l[3] - l[1])
                if best is None or ln > best[0]: best = (ln, l)
            dbg.append((n_ang, n_seite, n_reg)); return None if best is None else best[1]
        lF = waehle(aF, nahe=pF, maxabst=0.8 * skala); lKL = waehle(aKL, "L"); lKR = waehle(aKR, "R")
        lOL = waehle(aOL, "L", tol=np.deg2rad(18), nahe=(pcL + pA) / 2, maxabst=0.9 * skala); lOR = waehle(aOR, "R", tol=np.deg2rad(18), nahe=(pcR + pA) / 2, maxabst=0.9 * skala)
        got = []; grund = []
        if lKL is not None and lKR is not None and np.allclose(lKL, lKR): lKR = None
        if lKL is not None and lKR is not None:
            pe = schnitt(lKL, lKR)
            if pe is not None and np.linalg.norm(pe - pE) < 3.0 * skala: beob["firstende"].append((f, pe)); got.append("E")
            elif pe is not None: grund.append("E-Abstand %.1f m" % (np.linalg.norm(pe - pE) / skala))
            if lF is not None:
                cl_ = schnitt(lF, lKL); cr_ = schnitt(lF, lKR)
                if cl_ is not None and cr_ is not None and 0.3 * skala < np.linalg.norm(cl_ - cr_) < 2.5 * skala and np.linalg.norm((cl_ + cr_) / 2 - pF) < 1.5 * skala:
                    beob["ecke_L"].append((f, cl_)); beob["ecke_R"].append((f, cr_)); got.append("LR")
                elif cl_ is not None and cr_ is not None: grund.append("Ecken: Breite %.1f m, Mitte-Abstand %.1f m" % (np.linalg.norm(cl_ - cr_) / skala, np.linalg.norm((cl_ + cr_) / 2 - pF) / skala))
            else: grund.append("keine Frontlinie")
        else: grund.append("Kehle fehlt L" if lKL is None else "Kehle fehlt R")
        if lOL is not None and lOR is not None:
            pa = schnitt(lOL, lOR)
            if pa is not None and np.linalg.norm(pa - pA) < 1.0 * skala and (pa - pF) @ (pA - pF) > 0: beob["scheitel"].append((f, pa)); got.append("A")
        protokoll.append((f, len(lines), "".join(got) or "-", "Filter F/KL/KR/OL/OR (Winkel,Seite,Nahe):", dbg, "Skala px/m %.0f" % skala, grund))
        if "--audit" in a and (got or fs.index(f) < 3 or f in g("--fotos", "", str).split(",")):
            vis = cv2.cvtColor(V[y0:y1, x0:x1], cv2.COLOR_GRAY2BGR)
            for l in lines: cv2.line(vis, (int(l[0] - x0), int(l[1] - y0)), (int(l[2] - x0), int(l[3] - y0)), (120, 120, 120), 1)
            for P_, col in ((pF, (0, 255, 255)), (pE, (0, 0, 255)), (pcL, (255, 0, 0)), (pcR, (255, 0, 0)), (pA, (255, 0, 255))): cv2.circle(vis, (int(P_[0] - x0), int(P_[1] - y0)), 3, col, -1)
            cv2.polylines(vis, [np.round(poly - np.array([x0, y0], np.float32)).astype(np.int32)], True, (0, 160, 0), 1)
            for l in lines:
                if wdiff(winkel(l), aKL) <= np.deg2rad(25): cv2.line(vis, (int(l[0] - x0), int(l[1] - y0)), (int(l[2] - x0), int(l[3] - y0)), (0, 200, 255), 1)   # orange = Winkel passt zu Kehle L
            for l, col in ((lF, (0, 255, 255)), (lKL, (0, 0, 255)), (lKR, (0, 0, 255)), (lOL, (255, 0, 255)), (lOR, (255, 0, 255))):
                if l is not None: cv2.line(vis, (int(l[0] - x0), int(l[1] - y0)), (int(l[2] - x0), int(l[3] - y0)), col, 1)
            cv2.imwrite(os.path.join(audit, "gauben_tri_g%d_%s.png" % (gi, os.path.splitext(f)[0])), cv2.resize(vis, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
    print("Gaube %d (t %.2f s %.2f): %d Fotos; Beobachtungen Ecken %d, Firstende %d, Scheitel %d; je Foto %s" % (gi, t0, s0, len(fs), len(beob["ecke_L"]), len(beob["firstende"]), len(beob["scheitel"]), protokoll), flush=True)
    # Triangulation
    P3 = {}
    for key in ("ecke_L", "ecke_R", "firstende", "scheitel"):
        if len(beob[key]) >= NTRI:
            X, res = triang([strahl(KAM[f], uv, karte(f).shape[1] / KAM[f]["W"]) for f, uv in beob[key]]); P3[key] = dict(X=X, res=res, n=len(beob[key]))
    out = dict(index=gi, t0=t0, s0=s0, fotos=len(fs), beobachtungen={k_: len(v) for k_, v in beob.items()}, punkte3d={k_: dict(X=[round(float(x), 3) for x in v["X"]], residuum_m=round(v["res"], 3), fotos=v["n"], hoehe_ueber_ebene=round(hoehe(v["X"]), 2)) for k_, v in P3.items()})
    if all(k_ in P3 for k_ in ("ecke_L", "ecke_R", "firstende")):
        L_, R_, E_ = P3["ecke_L"]["X"], P3["ecke_R"]["X"], P3["firstende"]["X"]; F_ = (L_ + R_) / 2
        out.update(breite=float(np.linalg.norm((R_ - L_)[:2])), h_traufe=hoehe(F_), tiefe=float((E_ - F_) @ eh), t0_tri=float(F_ @ et), s0_tri=float(F_ @ eh), firstende_hoehe=hoehe(E_))
        if "scheitel" in P3: out.update(h_first=hoehe(P3["scheitel"]["X"]), h_first_quelle="Triangulation Ortgaenge")
        else: out.update(h_first=out["h_traufe"] + out["breite"] / 2, h_first_quelle="ANNAHME Giebel 45 Grad (Ortgaenge in < %d Fotos)" % NTRI)
        out["form_aus_foto"] = True
        print("  -> Breite %.2f, Fronttraufe +%.2f, Tiefe %.2f, Scheitel +%.2f (%s), Firstende %.2f ueber Ebene; Residuen L/R/E %.2f/%.2f/%.2f m" % (out["breite"], out["h_traufe"], out["tiefe"], out["h_first"], out["h_first_quelle"], out["firstende_hoehe"], P3["ecke_L"]["res"], P3["ecke_R"]["res"], P3["firstende"]["res"]), flush=True)
    else: out["form_aus_foto"] = False; print("  -> Form nicht trianguliert (zu wenige Fotos mit Ecken/Firstende)", flush=True)
    ergebnis.append(out)

# Reihenregel (obere/untere Reihe nach s0), Kanten, Gate
def kanten(o):
    F = ebene_punkt(o["t0_tri"], o["s0_tri"]); cl, cr = F - o["breite"] / 2 * et, F + o["breite"] / 2 * et; tl, tr = cl + o["h_traufe"] * up, cr + o["h_traufe"] * up
    apex = F + o["h_first"] * up; fend = ebene_punkt(o["t0_tri"], o["s0_tri"] + o["tiefe"])
    return [(apex, fend), (apex, tl), (apex, tr), (tl, tr), (tl, cl), (tr, cr), (tl, fend), (tr, fend)]
gut = [o for o in ergebnis if o["form_aus_foto"]]; reihen = []
for o in sorted(gut, key=lambda x: x["s0"]):
    if reihen and abs(o["s0"] - reihen[-1][0]["s0"]) < 1.2: reihen[-1].append(o)
    else: reihen.append([o])
for ri, R_ in enumerate(reihen):
    for o in R_: o["reihe"] = ri
    if len(R_) < 2: continue
    for key in ("breite", "h_traufe", "tiefe", "h_first"):
        med = float(np.median([o[key] for o in R_]))
        for o in R_:
            o[key + "_einzeln"] = o[key]
            if abs(o[key] - med) <= 0.15: o[key] = med
            else: o.setdefault("abweichend", []).append(key)
    print("Reihe %d (%d Gauben): Median Breite %.2f Traufe %.2f Tiefe %.2f Scheitel %.2f; Abweichungen %s" % (ri, len(R_), *[np.median([o[k_] for o in R_]) for k_ in ("breite", "h_traufe", "tiefe", "h_first")], [(round(o["breite_einzeln"] - o["breite"], 2), round(o["tiefe_einzeln"] - o["tiefe"], 2), round(o["h_traufe_einzeln"] - o["h_traufe"], 2)) for o in R_]), flush=True)
def belegung(K, mitte):
    pts = np.concatenate([p0[None] + (p1 - p0)[None] * np.linspace(0, 1, max(2, int(np.linalg.norm(p1 - p0) / 0.1)))[:, None] for p0, p1 in K]); vals = {}
    for f in sorted(KAM):
        k = KAM[f]
        if not os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png")) or np.linalg.norm(np.array(k["C"]) - mitte) > MAXD: continue
        V = karte(f); H, W = V.shape; sj = W / k["W"]; uv, z = proj(k, pts, sj); ok = (z > 1) & (uv[:, 0] >= 3) & (uv[:, 0] < W - 3) & (uv[:, 1] >= 3) & (uv[:, 1] < H - 3)
        if ok.mean() < 0.9: continue
        Vd = cv2.dilate(V, np.ones((7, 7), np.uint8)); vals[f] = float((Vd[uv[ok, 1].astype(int), uv[ok, 0].astype(int)] >= 0.3 * 255).mean())
    return vals
seg = []
for o in gut:
    K = kanten(o); vals = belegung(K, ebene_punkt(o["t0_tri"], o["s0_tri"])); o["belegung_fotos"] = len(vals); o["belegung_ueber"] = int(sum(v >= FOTOMIN for v in vals.values())); o["belegung_median"] = float(np.median(list(vals.values()))) if vals else None
    o["bestanden"] = o["belegung_ueber"] >= NFOTO
    print("Gaube %d Gate: %d Fotos, Belegung >= %.2f in %d, Median %.2f -> %s" % (o["index"], len(vals), FOTOMIN, o["belegung_ueber"], o["belegung_median"] or 0, "bestanden" if o["bestanden"] else "nicht bestanden"), flush=True)
    for p0, p1 in K: seg.append([[float(x) for x in p0], [float(x) for x in p1], 14, round(o["belegung_median"] or 0, 3)])
familie = len(gut) == len(lagen) and all(o["bestanden"] for o in gut)
out_path = a[3] if not familie else a[3].replace("gauben_r4", "gauben_abgenommen")
json.dump({"dachebene": E, "lagen": len(lagen), "form_aus_foto": len(gut), "familiengate": familie, "gauben": ergebnis, "segmente": seg}, open(out_path, "w"), indent=1)
print("fertig: %d Lagen, %d Formen trianguliert, %d bestanden, Familiengate %s -> %s" % (len(lagen), len(gut), sum(o.get("bestanden", False) for o in gut), familie, out_path))
