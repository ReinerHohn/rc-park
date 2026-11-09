#!/usr/bin/env python3
"""koerper_v11.py - Kaufhaus-Koerper v11 (druckfertiges Rohteil): wie v10, aber Rumpf + Verlaengerung als EIN Koerper (Fuenfeck ueber die volle Laenge,
oberhalb der Traufe hinter den Giebelebenen abgeschnitten), Baluster aus formen/baluster_abgenommen.json (Zaehlprotokoll Z-6120-001), Konsolen
mit Wiederholungsregel (analyse_konsolen, Fotobeleg), Giebelwaende an den Giebelebenen. Gate: STL-Roundtrip + merge_vertices wasserdicht, 0 offene Kanten.

  analyse_konsolen (venv-seg): koerper_v11.py analyse_konsolen SEG.json KOERPER_v10.json KAM.json STABILDIR AUSDIR    -> AUSDIR/konsolen_v11.json
  bauen (venv rcpark):         koerper_v11.py bauen SEG.json ROH_v7.json FE_v9.json HELME.json BALUSTER.json AUSDIR   -> AUSDIR/koerper_v11.*
  pruefen (venv-seg):          koerper_v11.py pruefen AUSDIR WOLKE.npz KAM.json BILDDIR AUDITDIR                       -> + Ueberhaenge > 60 Grad, Mindeststege"""
import sys, os, json, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gitter_koerper as GK
from koerper_fenster_erker import fenstergruppe, cs, ABST, H0, T_OEFF, welt
from koerper_v10 import erker_mitte, steiger

NAME = "koerper_v11"
R_DRUCK_MIN = 0.026   # m: 0,6 mm Durchmesser bei 1:87 (ANNAHME druckbedingt)


def analyse_konsolen(seg_json, k10_json, kam_json, stabildir, ausdir):
    """Wiederholungsregel fuer die Konsolen: Periode = Pfeilerabstand / k (k = 2..4), Phase aus den gefundenen Bloecken, Inlier < 0,3 m;
    fehlende Positionen ergaenzen und je Position pruefen: Gitterkanten im Umfeld 20 cm (unter der Platte, vor der Wand) oder Fotobeleg (>= 2 Fotos), sonst ANNAHME."""
    from koerper_fenster_erker import fotobeleg
    d, P0, P1, L, dn, Q = GK.lade(seg_json); D = json.load(open(k10_json)); u = np.array(D["u"]); n = np.array(D["n"]); of = D["off_front"]
    kons = D["balkon"]["konsolen"]; pl = D["balkon"]["platte"]; pos = np.array([k["along"] for k in kons])
    sa = sorted(float(np.array([s["cx"], s["cy"], 0]) @ u) for s in d.get("saeulen", []) if abs(float(np.array([s["cx"], s["cy"], 0]) @ n) - of) < 1.0)
    sp = float(np.median(np.diff(sa))) if len(sa) > 1 else None; log = [f"Pfeiler Hauptlinie along {np.round(sa, 2).tolist()}, Abstand {sp}"]
    best = None
    for k in (2, 3, 4):
        P = sp / k
        for ph in pos:
            res = (pos - ph + P / 2) % P - P / 2; inl = int((np.abs(res) < 0.3).sum())
            sc = (inl, -abs(k - 3))   # Gleichstand: 3 je Joch (Foto 6120 lt. Auftrag), aber nur als Tiebreak
            if best is None or sc > best[0]: best = (sc, P, ph, res)
    (inl, _), P, ph, res = best; phase = float(ph + np.median(res[np.abs(res) < 0.3]))
    log.append(f"Periode {P:.3f} m (= Pfeilerabstand/{round(sp / P)}), Phase {phase:.2f}, Inlier {inl}/{len(pos)}; Residuen {np.round(res, 2).tolist()}")
    a0, a1 = pl["along"]; j0 = math.ceil((a0 + 0.3 - phase) / P); j1 = math.floor((a1 - 0.3 - phase) / P); grid = [phase + j * P for j in range(j0, j1 + 1)]
    M = (P0 + P1) / 2; al = M @ u; off = M @ n - of; zp0 = pl["z0"]; KAM = json.load(open(kam_json)); aus = []
    neu = [g for g in grid if np.min(np.abs(pos - g)) > 0.3]
    segs = [[welt(u, n, g, of + 1.0, zp0 - 1.0), welt(u, n, g, of + 1.0, zp0 - 0.1), 1, 1.0] for g in neu]
    ja, nein, fj = fotobeleg(segs, KAM, stabildir) if segs else (np.zeros(0), np.zeros(0), [])
    verworfen = [{"along": float(p_), "grund": f"Gitterblock {min(np.abs(np.array(grid) - p_)):.2f} m neben dem Periodenraster (Nutzerbefund: sitzt nicht auf einer echten Konsole)"} for p_ in pos if np.min(np.abs(np.array(grid) - p_)) > 0.3]
    for g in grid:
        i = int(np.argmin(np.abs(pos - g)))
        if abs(pos[i] - g) <= 0.3: aus.append({"along": float(g), "z0": kons[i]["z0"], "status": f"gitter_block (Rasterlage, Block {pos[i]:+.2f})"}); continue
        m = (np.abs(al - g) < 0.2) & (M[:, 2] > zp0 - 1.5) & (M[:, 2] < zp0) & (off > 0.1) & (off < 1.4); j = neu.index(g)
        if m.sum() >= 2: st = f"gitterkanten ({int(m.sum())} Segmente im Umfeld 20 cm)"; z0 = float(min(M[m, 2].min(), zp0 - 0.6))
        elif ja[j] >= 2: st = f"foto ({int(ja[j])} Fotos ja, {int(nein[j])} nein)"; z0 = zp0 - 0.9
        else: st = f"ANNAHME (Wiederholung; Gitter 0 Kanten, Fotos ja {int(ja[j])})"; z0 = zp0 - 0.9
        aus.append({"along": float(g), "z0": z0, "status": st})
    log.append(f"Gitterbloecke VERWORFEN (ausserhalb Raster): {[round(v['along'], 2) for v in verworfen]}")
    log.append(f"Konsolen gesamt {len(aus)}: gitter_block {sum(1 for a in aus if a['status'].startswith('gitter_block'))}, gitterkanten {sum(1 for a in aus if a['status'].startswith('gitterkanten'))}, foto {sum(1 for a in aus if a['status'].startswith('foto'))}, ANNAHME {sum(1 for a in aus if a['status'].startswith('ANNAHME'))}")
    for a in aus: log.append(f"  along {a['along']:6.2f} z0 {a['z0']:.2f} {a['status']}")
    print("\n".join(log)); json.dump({"periode": P, "phase": phase, "pfeilerabstand": sp, "konsolen": aus, "verworfen": verworfen, "log": log}, open(os.path.join(ausdir, "konsolen_v11.json"), "w"), indent=1)


def bauen(seg_json, roh_json, fe_json, helme_json, bal_json, ausdir):
    import manifold3d as m3, trimesh
    os.makedirs(ausdir, exist_ok=True); log = []; L_ = lambda s: (print(s), log.append(s)); annahmen = []
    d, P0, P1, L, dn, Q = GK.lade(seg_json); A = json.load(open(roh_json)); D9 = json.load(open(fe_json)); HL = json.load(open(helme_json))["helme"]
    u = np.array(A["u"]); n = np.array(A["n"]); of = A["off_front"]; zt = A["traufe"]["z"]; zf = A["first"]["z"]; offi = A["first"]["offset"]; zb = A["z_boden"]; ob = A["off_back"]
    M = (P0 + P1) / 2; horiz = np.abs(dn[:, 2]) < 0.2; vert = np.abs(dn[:, 2]) > 0.9; schr = ~horiz & ~vert
    par = horiz & (np.abs(dn @ u) > 0.95); perp = horiz & (np.abs(dn @ n) > 0.95); masken = (par, perp, vert, schr, M); al = M @ u; off = M @ n
    # ---------- Erker, Achse, Giebelebenen (wie v10)
    G = D9["erker_gemeinsam"]; erk = [dict(e, mitte_alt=e["mitte"], mitte=erker_mitte(e)) for e in D9["erker"]]
    achse = 0.5 * (erk[0]["mitte"] + erk[-1]["mitte"]); xw = G["x_wand"]
    kand = [e for e in A["enden"] if e["z_max"] > zt + 3.0]; best = None
    for w_ in [e for e in kand if e["along"] < achse]:
        for e_ in [e for e in kand if e["along"] > achse]:
            sc = abs(0.5 * (w_["along"] + e_["along"]) - achse) + 0.3 * ((not w_["belegt"]) + (not e_["belegt"]))
            if best is None or sc < best[0]: best = (sc, w_, e_)
    aw, ae = (best[1]["along"], best[2]["along"]) if best else (A["along_w"], A["along_e"])
    aw_u = min(aw, min(e["mitte"] for e in erk) - xw - ABST); ae_u = max(ae, max(e["mitte"] for e in erk) + xw + ABST)   # 2 cm ueber den Erker-Wandanschluss hinaus: Erkerkante nicht in der Stirnflaeche (Doppelpunkte im kette_video_alle-Lauf)
    L_(f"Erkermitten {[round(e['mitte'], 2) for e in erk]}, Achse {achse:.2f}; Giebelebenen {aw:.2f}/{ae:.2f}; Rumpf unten {aw_u:.2f}..{ae_u:.2f}")
    annahmen.append(f"ANNAHME: Rumpf (Boden..Traufe) bis zu den Erker-Wandanschluessen {aw_u:.2f}..{ae_u:.2f}; Dach/Giebel nur {aw:.2f}..{ae:.2f}; Laubenendboegen nicht gebaut")
    giebel = {}
    for name, al_end in (("ende_minus", aw), ("ende_plus", ae)):
        tr, st = steiger(P0, P1, L, dn, M, u, n, al_end, zt, offi, of); giebel[name] = {"stufen": tr, "alle_steiger": st, "form": "staffel" if len(tr) >= 3 else "gerade"}
    for a_, b_ in (("ende_minus", "ende_plus"), ("ende_plus", "ende_minus")):
        if giebel[a_]["form"] != "staffel" and giebel[b_]["form"] == "staffel":
            giebel[a_] = {"stufen": giebel[b_]["stufen"], "alle_steiger": giebel[a_]["alle_steiger"], "form": "staffel", "quelle": f"ANNAHME: Spiegel von {b_}"}; annahmen.append(f"ANNAHME: Staffelgiebel {a_} = Spiegel von {b_}")
    L_("Giebel: " + ", ".join(f"{k} {v['form']} ({len(v['stufen'])} Stufen{', ' + v['quelle'] if 'quelle' in v else ''})" for k, v in giebel.items()))
    # ---------- Rumpf als EIN Fuenfeck ueber die volle Laenge (gitter_koerper.baue ohne Giebelwaende/Vorsprung/Helme), dann oberhalb der Traufe hinter den Giebelebenen abschneiden
    A11 = dict(A); A11.update(along_w=aw_u, along_e=ae_u, giebel=giebel, vorspruenge=[], achse=achse, giebel_along=[aw, ae],
                             historie=A.get("historie", []) + [{"datum": "2026-11-09", "was": "v11: offene Laube (Flaeche-vs-Oeffnung-Test), Rumpf ueber volle Laenge, Giebelebenen aus symmetrischem Endebenen-Paar, Staffel beide Enden, Baluster Z-6120-001 (koerper_v11.py)"}])
    ann_gk = []; Mw = np.c_[u, n, [0, 0, 1], [0, 0, 0]]; Mi = np.linalg.inv(np.r_[Mw, [[0, 0, 0, 1]]])[:3]
    # ---------- Erdgeschoss aus dem Flaeche-vs-Oeffnung-Test (flaeche_oder_oeffnung.py): offene Laube statt Tunnel in einer Wand
    fl_p = os.path.join(ausdir, "flaechen_eg_v11_zpuffer.json") if os.path.exists(os.path.join(ausdir, "flaechen_eg_v11_zpuffer.json")) else os.path.join(ausdir, "flaechen_eg_v11.json")
    FL = {f["name"]: f for f in json.load(open(fl_p))["flaechen"]}; L_(f"Flaeche-vs-Oeffnung aus {os.path.basename(fl_p)} (Z-Puffer-Sichtbarkeit: {json.load(open(fl_p)).get('zpuffer')})")
    mb = horiz & (off - of > 0.3) & (M[:, 2] > zb + 4) & (M[:, 2] < D9["z_balkon"] + 0.3); Xb, wb = GK.stuetzpunkte(P0[mb], P1[mb], L[mb], 0.1)
    zp0 = min(e["offset"] for e in GK.ransac_1d(Xb[:, 2], wb, 0.06, 2.0) if e["offset"] < D9["z_balkon_unten"] + 1.0)   # Plattenunterkante = Laubendecke
    ol = A["off_laube"]; sgn = np.sign(of - offi); zt_b = zt
    # Obergeschoss + Dach: Fuenfeck von der Laubendecke (Plattenunterkante) bis First, volle Laenge; oberhalb der Traufe hinter den Giebelebenen abgeschnitten
    # EIN Querschnitt fuer Obergeschoss+Dach, Bogenbalken (Pfeilertiefe, ab Kaempfer-2cm) und Hinterhaus (Rueckwand..Rueckseite): keine koplanaren Naehte
    pf = sorted([(float(np.array([s["cx"], s["cy"], 0]) @ u), float(np.array([s["cx"], s["cy"], 0]) @ n), s["R"]) for s in d.get("saeulen", []) if abs(float(np.array([s["cx"], s["cy"], 0]) @ n) - of) < 1.0])
    ark_p = os.path.join(os.path.dirname(seg_json), "..", "kurven", "arkaden.json"); ark = json.load(open(ark_p)) if os.path.exists(ark_p) else None
    rund = [a_["rund"] for a_ in ark["arkaden"] if a_.get("typ") == "rund"] if ark else []
    zc = float(np.median([r["zc"] for r in rund])) if rund else float(np.median([a_["z_mittelpunkt"] for a_ in A["arkaden"]])); R_b = float(np.median([r["R"] for r in rund])) if rund else float(np.median([a_["R"] for a_ in A["arkaden"]]))
    tp_b = 2 * float(np.median([p[2] for p in pf])); y0b = of - tp_b
    quer = [[of, zc - ABST], [of, zt], [offi, zf], [ob, zt_b], [ob, zb], [ol, zb], [ol, zp0], [y0b, zp0], [y0b, zc - ABST]]
    huelle = m3.Manifold.extrude(cs(quer), ae_u - aw_u).transform(np.array([[0, 0, 1, aw_u], [1, 0, 0, 0], [0, 1, 0, 0]], float))
    lo, hi = min(of, ob) - 1.0, max(of, ob) + 1.0
    for a0, a1 in ((aw_u - 1.0, aw), (ae, ae_u + 1.0)):
        if a1 - a0 > 1.0 + 1e-6: huelle = huelle - m3.Manifold.cube([a1 - a0, hi - lo, zf + 3.0 - (zt + ABST)]).translate([a0, lo, zt + ABST])
    teile = [huelle]
    # Hinterhaus (Rueckwand der Laube bis Rueckseite) massiv, Boden..Decke
    # Rueckwand-Oeffnungen aus dem Test (Komponenten >= 5 Zellen) als Nischen 0,3 m (ANNAHME: Tiefe; dahinter unbekannt)
    for k in [k for k in FL["rueckwand_laube"]["oeffnungen"] if k["zellen"] >= 5]:
        x0, x1 = k["ax1"]; z0, z1 = k["ax2"]; teile[0] = teile[0] - m3.Manifold.cube([x1 - x0, 0.3 + 0.05, z1 - z0]).translate([x0, ol - 0.3, z0])
        annahmen.append(f"ANNAHME: Rueckwandoeffnung along {x0:.1f}..{x1:.1f} z {z0:.1f}..{z1:.1f} (Test hinter/auf {k['hinter']:.0f}/{k['auf']:.0f}) als Nische 0,3 m")
    # Pfeiler: Zylinder R aus saeulen (Hauptlinie), Boden..Kaempfer, Kapitellblock 0,2 m (ANNAHME)
    for a_, o_, R_ in pf:
        teile.append(m3.Manifold.cylinder(zc - zb, R_, R_, 32).translate([a_, o_, zb])); teile.append(m3.Manifold.cube([2 * R_ + 0.1, 2 * R_ + 0.1, 0.2 + ABST]).translate([a_ - R_ - 0.05, o_ - R_ - 0.05, zc - 0.2]))
    annahmen.append("ANNAHME: Kapitellblock 0,2 m ueber den Pfeilern; Laubendecke flach auf Plattenunterkante (Gewoelbe nicht gebaut)")
    L_(f"Laube: Pfeiler {len(pf)} (R {np.round([p[2] for p in pf], 2).tolist()}), Kaempfer/Bogenmitte z {zc:.2f}, Bogen R {R_b:.2f} ({'kurven/arkaden.json' if rund else 'rohkoerper'}), Decke {zp0:.2f}, Rueckwand {ol:.2f}")
    # Bogenzone: Balken Kaempfer..Decke in Pfeilertiefe, Oeffnungen je Joch nach Test (Anteil Oeffnungszellen unter z 7 im Joch >= 0,5)
    fe = FL["front_eg"]; KL = np.array(fe["klasse"], dtype=object); r1 = fe["ax1_bereich"]; r2 = fe["ax2_bereich"]; ZL = fe["zelle_m"]
    grenzen = [aw_u] + [p[0] for p in pf] + [ae_u]; joche = []; abz_eg = []
    for i in range(len(grenzen) - 1):
        x0 = grenzen[i] + (pf[i - 1][2] + ABST if i > 0 else 0.52 + 2 * ABST); x1 = grenzen[i + 1] - (pf[i][2] + ABST if i < len(pf) else 0.52 + 2 * ABST)   # Endjoch: 2 cm Abstand zur Stirnwand-Innenseite
        if x1 - x0 < 0.8: continue
        ci = slice(max(int((x0 - r1[0]) / ZL), 0), min(int(math.ceil((x1 - r1[0]) / ZL)), KL.shape[0])); cj = slice(0, min(int((7.0 - r2[0]) / ZL), KL.shape[1]))
        sub = KL[ci, cj]; ant = float((sub == "oeffnung").mean()) if sub.size else 0.0; offen = ant >= 0.5
        joche.append({"along": [x0, x1], "anteil_oeffnung": ant, "offen": offen, "typ": "joch" if 0 < i < len(pf) else "endjoch"})
        if offen:
            span = x1 - x0; xm = 0.5 * (x0 + x1); R = R_b if 0 < i < len(pf) and R_b > span / 2 else span / 2; zm = zc if R == R_b else zc
            if R > span / 2 + 0.01: z_s = zm + math.sqrt(R * R - (span / 2) ** 2); a0 = math.atan2(z_s - zm, span / 2); angs = np.linspace(a0, math.pi - a0, 25); poly = [[x0, zb - 0.5], [x1, zb - 0.5]] + [[xm + R * math.cos(t), zm + R * math.sin(t)] for t in angs]
            else: poly = [[x0, zb - 0.5], [x1, zb - 0.5], [x1, zm]] + [[xm + R * math.cos(t), zm + R * math.sin(t)] for t in np.linspace(0, math.pi, 25)[1:-1]] + [[x0, zm]]
            abz_eg.append(m3.Manifold.extrude(cs(poly), tp_b + 2.0).transform(np.array([[1, 0, 0, 0], [0, 0, 1, y0b - 1.0], [0, 1, 0, 0]], float)))
    L_("Joche: " + "; ".join(f"{j['typ']} {j['along'][0]:.1f}..{j['along'][1]:.1f} Oeffnung {j['anteil_oeffnung']:.2f} -> {'offen' if j['offen'] else 'WAND'}" for j in joche))
    # Stirnwaende EG (Giebelwand unten) mit Seitenbogen, wenn der Test Oeffnung sagt (Hinweis: Stirn-Test schwach belegt, siehe Log)
    for name, a0 in (("stirn_minus", aw_u + ABST), ("stirn_plus", ae_u - 0.52 - ABST)):   # 2 cm hinter der Stirnflaeche (keine koplanare Naht)
        wand = m3.Manifold.cube([0.52, abs(of - ol), zp0 + ABST - zb]).translate([a0, min(of, ol), zb]); f_ = FL[name]
        ant = f_["anteil"]["oeffnung"]; auf_n = f_["n_punkte_auf"]
        if ant >= 0.5:
            yl, yh = min(of, ol) + 0.6, max(of, ol) - tp_b - ABST; span = yh - yl; R = span / 2; zm = zc + R_b - R   # Scheitel wie Reihenboegen
            poly = [[yl, zb - 0.5], [yh, zb - 0.5], [yh, zm]] + [[0.5 * (yl + yh) + R * math.cos(t), zm + R * math.sin(t)] for t in np.linspace(0, math.pi, 25)[1:-1]] + [[yl, zm]]
            wand = wand - m3.Manifold.extrude(cs(poly), 0.52 + 2.0).transform(np.array([[0, 0, 1, a0 - 1.0], [1, 0, 0, 0], [0, 1, 0, 0]], float))
            annahmen.append(f"ANNAHME: Seitenbogen {name} (Test Oeffnung {ant:.2f}, aber nur {auf_n} Punkte AUF der Flaeche - Stirnwand kaum in der Wolke; Bogenmasse wie Reihenboegen, Scheitel {zc + R_b:.2f})")
        teile.append(wand)
    L_("Stirnwaende: " + "; ".join(f"{k} Oeffnung {FL[k]['anteil']['oeffnung']:.2f} Wand {FL[k]['anteil']['wand']:.2f} auf {FL[k]['n_punkte_auf']}" for k in ("stirn_minus", "stirn_plus")))
    # Giebelwaende (Staffel) an den Giebelebenen, Polygon wie gitter_koerper
    of_i, ob_i = of - ABST * np.sign(of - offi), ob + ABST * np.sign(of - offi)
    for name, al_end, sgn in (("ende_minus", aw, 1), ("ende_plus", ae, -1)):
        g = giebel[name]
        if g["form"] != "staffel": continue
        pts = [[of_i, zt]]
        for s in g["stufen"]: pts += [[s["off"], s["z_unten"]], [s["off"], s["z_oben"]]]
        pts.append([offi, max(zf, pts[-1][1])]); rueck = [[2 * offi - p[0], p[1]] for p in pts[::-1]]
        poly = pts + rueck[1:] + [[ob_i, zt - 0.3], [of_i, zt - 0.3]]
        teile.append(m3.Manifold.extrude(cs(poly), 0.52).transform(np.array([[0, 0, 1, al_end - ABST if sgn > 0 else al_end - 0.5], [1, 0, 0, 0], [0, 1, 0, 0]], float)))
    # ---------- Fenster (v9), Figuren (v10)
    F = D9["fenster"]; abz = list(abz_eg); add = []
    for g in [g for g in F["gruppen"] if g["belegt"]]:
        a_, s_ = fenstergruppe(m3, g["mitte"], F, 0, 0, F["n_licht"], F["w_licht"]); T = np.array([[1, 0, 0, g["mitte"]], [0, 1, 0, of], [0, 0, 1, 0]], float)
        abz += [x.transform(T) for x in a_]; add += [x.transform(T) for x in s_]
    Gm = np.array([g["mitte"] for g in F["gruppen"]]); dg = np.min(np.abs(al[:, None] - Gm[None]), axis=1)
    m = (np.abs(off - of) < 0.8) & (M[:, 2] > F["z_sohl"] - 0.3) & (M[:, 2] < zt - 0.3) & (dg > 1.5 * F["w_licht"] + 0.1) & (al > min(e["mitte"] for e in erk) + xw) & (al < max(e["mitte"] for e in erk) - xw)
    X, w = GK.stuetzpunkte(P0[m], P1[m], L[m], 0.1); figuren = []
    for e in sorted(GK.ransac_1d(X @ u, w, 0.3, 8.0), key=lambda e: e["offset"]):
        Xi = X[e["idx"]]; a0, a1 = np.percentile(Xi @ u, 5), np.percentile(Xi @ u, 95); z0, z1 = Xi[:, 2].min(), Xi[:, 2].max(); t_ = np.percentile(Xi @ n, 90) - of
        if z1 - z0 < 1.5: continue
        fig = {"along": float(e["offset"]), "breite": float(max(a1 - a0, 0.4)), "z0": float(z0), "z1": float(z1), "tiefe": float(max(t_, 0.3)), "laenge": e["laenge"]}; figuren.append(fig)
        add.append(m3.Manifold.cube([fig["breite"], fig["tiefe"] + 0.2, z1 - z0]).translate([fig["along"] - fig["breite"] / 2, of - 0.2, z0]))
    annahmen.append("ANNAHME: Figur + Konsole + Baldachin je Position ein Quader")
    # ---------- Balkon (v10) + Baluster (abgenommene Reihe) + Konsolen (Wiederholungsregel)
    al_b0, al_b1 = min(e["mitte"] for e in erk) + xw - 0.05, max(e["mitte"] for e in erk) - xw + 0.05
    m = horiz & (off - of > 0.3) & (M[:, 2] > zb + 4) & (M[:, 2] < D9["z_balkon"] + 0.3) & (al > al_b0) & (al < al_b1)
    X, w = GK.stuetzpunkte(P0[m], P1[m], L[m], 0.1); hz = [{"z": e["offset"], "laenge": e["laenge"], "vor": float(np.percentile(X[e["idx"]] @ n, 90) - of), "vor_min": float(np.percentile(X[e["idx"]] @ n, 10) - of)} for e in GK.ransac_1d(X[:, 2], w, 0.06, 2.0)]
    platte = [h for h in hz if h["z"] < D9["z_balkon_unten"] + 1.0]; rail = [h for h in hz if h["z"] > D9["z_balkon"] - 0.8]; balkon = {}
    zp1 = max(h["z"] for h in platte); zp0 = min(h["z"] for h in platte); tp = max(h["vor"] for h in platte)
    if zp1 - zp0 < 0.12: zp0 = zp1 - 0.2; annahmen.append("ANNAHME: Plattendicke 0,20 m")
    balkon["platte"] = {"z0": zp0, "z1": zp1, "tiefe": tp, "along": [al_b0, al_b1]}; teile.append(m3.Manifold.cube([al_b1 - al_b0, tp + 0.2, zp1 - zp0]).translate([al_b0, of - 0.2, zp0]))
    zr1 = max(h["z"] for h in rail); zr0 = min(h["z"] for h in rail); v0 = min(h["vor_min"] for h in rail); v1 = max(h["vor"] for h in rail)
    if zr1 - zr0 < 0.12: zr0 = zr1 - 0.18; annahmen.append("ANNAHME: Handlaufhoehe 0,18 m")
    ar0, ar1 = min(e["mitte"] for e in erk) + 0.8, max(e["mitte"] for e in erk) - 0.8
    balkon["handlauf"] = {"z0": zr0, "z1": zr1 + 0.05, "vor": [v0, v1], "along": [ar0, ar1]}; teile.append(m3.Manifold.cube([ar1 - ar0, v1 - v0, zr1 + 0.05 - zr0]).translate([ar0, of + v0, zr0]))
    # Baluster
    B = json.load(open(bal_json)); prof = eval(B["profil"]) if isinstance(B["profil"], str) else B["profil"]; r_prof = float(np.mean([p[0] for p in prof])); r_b = max(r_prof, R_DRUCK_MIN)
    if r_b > r_prof + 1e-6: annahmen.append(f"ANNAHME druckbedingt: Balusterradius {r_prof:.3f} -> {r_b:.3f} m (0,6 mm bei 1:87)")
    nb = 0; bal_pos = []
    for x in B["baluster"]:
        p = np.array(x["mitte"]); a_, v_ = float(p @ u), float(p @ n) - of
        if not (al_b0 < a_ < al_b1): continue
        teile.append(m3.Manifold.cylinder(zr0 + ABST - (zp1 - ABST), r_b, r_b, 12).translate([a_, of + v_, zp1 - ABST])); nb += 1; bal_pos.append([a_, v_])   # Platte-Oberkante -2 cm .. Handlauf-Unterkante +2 cm
    balkon["baluster"] = {"anzahl": nb, "r": r_b, "r_profil": r_prof, "periode": B.get("periode"), "beleg": B.get("beleg"), "quelle": bal_json}
    L_(f"Baluster: {nb} Zylinder r {r_b:.3f} (Profil {r_prof:.3f}), z {zp1 - ABST:.2f}..{zr0 + ABST:.2f}, Periode {B.get('periode')}, Beleg {str(B.get('beleg'))[:120]}")
    # Konsolen
    kp = os.path.join(ausdir, "konsolen_v11.json"); kons = json.load(open(kp))["konsolen"] if os.path.exists(kp) else None
    if kons is None:
        kons = []; m = (off - of > 0.1) & (M[:, 2] > zp0 - 1.8) & (M[:, 2] < zp1) & (al > al_b0) & (al < al_b1); X, w = GK.stuetzpunkte(P0[m], P1[m], L[m], 0.1)
        for e in sorted(GK.ransac_1d(X @ u, w, 0.25, 1.0), key=lambda e: e["offset"]):
            z0 = float(X[e["idx"]][:, 2].min())
            if zp0 - z0 < 0.5: continue
            if kons and e["offset"] - kons[-1]["along"] < 0.6: kons[-1]["along"] = 0.5 * (kons[-1]["along"] + e["offset"]); kons[-1]["z0"] = min(kons[-1]["z0"], z0); continue
            kons.append({"along": float(e["offset"]), "z0": z0, "status": "gitter_block"})
        annahmen.append("OFFEN: konsolen_v11.json fehlt - nur Gitter-Bloecke, keine Wiederholung")
    for k in kons:   # nach unten schmaler werdende Stuetze (Huelle): oben 0,45 breit / Platte-0,15 tief, unten 0,2 breit / 0,15 tief (ANNAHME Trapez; Gitter liefert keine Konsolenprofile)
        x_, zt_, zb_ = k["along"], zp0 + ABST, k["z0"]; d_ = tp - 0.15
        teile.append(m3.Manifold.hull_points([[x_ - 0.225, of - 0.2, zt_], [x_ + 0.225, of - 0.2, zt_], [x_ - 0.225, of + d_, zt_], [x_ + 0.225, of + d_, zt_], [x_ - 0.1, of - 0.2, zb_], [x_ + 0.1, of - 0.2, zb_], [x_ - 0.1, of + 0.15, zb_], [x_ + 0.1, of + 0.15, zb_]]))
    balkon["konsolen"] = kons; n_ann = sum(1 for k in kons if k["status"].startswith("ANNAHME"))
    L_(f"Konsolen: {len(kons)} ({n_ann} nur ANNAHME Wiederholung)"); annahmen.append("ANNAHME: Konsolenform Trapez (oben 0,45 x Platte-0,15, unten 0,2 x 0,15), Lagen nur aus dem Periodenraster (konsolen_v11.json, verworfene Gitterbloecke dort)")
    # ---------- Erker + Schaft + Helme (v10)
    erker_teile = []; helme_lok = []
    for h in HL:
        p = np.array([h["cx"], h["cy"], 0]); helme_lok.append({"along": float(p @ u), "off": float(p @ n), "z_fuss": h["z_fuss"], "z_spitze": h["z_spitze"], "r_fuss": h["r_fuss"], "phi": h.get("phi", 0), "sektoren": int(h.get("sektoren", 16))})
    t = G["tiefe"]; xf = G["x_front"]; b = F["b_rahmen"]
    for e in erk:
        c = e["mitte"]; hm = min(helme_lok, key=lambda h: abs(h["along"] - c)); hm = hm if abs(hm["along"] - c) < 1.5 else None
        poly = [[-xw, -0.3], [-xw, -ABST], [-xf, t], [xf, t], [xw, -ABST], [xw, -0.3]]; z_top = hm["z_fuss"] + 0.05 if hm else G["z_oben"]
        koerper = m3.Manifold.extrude(cs(poly), z_top - G["z_unten"]).translate([0, 0, G["z_unten"]])
        zu = D9["z_balkon_unten"] - 0.3; sx = (xw - ABST) / xw; pin = [[x * sx, y - ABST] for x, y in poly[1:5]]
        unters = m3.Manifold.hull_points([[x, y, G["z_unten"] + 0.05] for x, y in pin] + [[-xw * sx, -0.3 + ABST, G["z_unten"] + 0.05], [xw * sx, -0.3 + ABST, G["z_unten"] + 0.05], [-0.4, -0.3, zu], [0.4, -0.3, zu], [-0.4, -ABST, zu], [0.4, -ABST, zu]])
        polyr = [[-xw - b, -0.3], [-xw - b, -ABST], [-xf - b * 0.5, t + b], [xf + b * 0.5, t + b], [xw + b, -ABST], [xw + b, -0.3]]   # Gesimsring: Wandanschluss 2 cm in der Wand (Doppelpunkte im kette_video_alle-Lauf)
        ring = m3.Manifold.extrude(cs(polyr), 0.25 + ABST).translate([0, 0, G["z_oben"] - 0.25]); tl = [koerper, unters, ring]
        if hm:
            k = min(hm["sektoren"], 16); hh = hm["z_spitze"] - hm["z_fuss"]
            tl.append(m3.Manifold.cylinder(hh, hm["r_fuss"], 0.0, k).rotate([0, 0, math.degrees(hm["phi"])]).translate([hm["along"] - c, hm["off"] - of, hm["z_fuss"]]))
            dz = 0.6; r2 = hm["r_fuss"] * (1 - dz / hh) * 0.98; ang = np.linspace(0, 2 * math.pi, k, endpoint=False) + hm["phi"]
            tl.append(m3.Manifold.hull_points([[x, y, z_top - 0.05] for x, y in pin] + [[-xw * sx, -0.3 + ABST, z_top - 0.05], [xw * sx, -0.3 + ABST, z_top - 0.05]] + [[hm["along"] - c + r2 * math.cos(a_), hm["off"] - of + r2 * math.sin(a_), hm["z_fuss"] + dz] for a_ in ang]))
        E = m3.Manifold.batch_boolean(tl, m3.OpType.Add)
        for (xa, ya), (xb, yb) in (((-xw, 0), (-xf, t)), ((-xf, t), (xf, t)), ((xf, t), (xw, 0))):
            lng = math.hypot(xb - xa, yb - ya); n_l = max(1, int(round(lng / G["lichtbreite"]))); w_l = (lng - 2 * b) / n_l
            a_, s_ = fenstergruppe(m3, 0, dict(F), 0, 0, n_l, w_l, profil=False, z_sohl=G["z_sohl"], z_kaem=G["z_kaempfer"], z_schul=G["z_schulter"], z_scheit=G["z_schulter"] + 0.3)
            ex = np.array([xb - xa, yb - ya]) / lng; ey = np.array([ex[1], -ex[0]])
            if ey[1] < -1e-6: ey = -ey
            if abs(ey[1]) < 1e-6 and ey[0] * (xa + xb) < 0: ey = -ey
            T = np.array([[ex[0], ey[0], 0, 0.5 * (xa + xb)], [ex[1], ey[1], 0, 0.5 * (ya + yb)], [0, 0, 1, 0]], float)
            E = E - m3.Manifold.batch_boolean([x.transform(T) for x in a_], m3.OpType.Add) + m3.Manifold.batch_boolean([x.transform(T) for x in s_], m3.OpType.Add)
        erker_teile.append(E.translate([c, of, 0]))
    annahmen.append("ANNAHME: Erkerschaft = Erkerpolygon bis Helmfuss + Huelle zum Helm (0,6 m); Helme aus formen/helme.json (BEOBACHTUNG offen: Helmfuss im Foto ~2x so breit)")
    # ---------- Zusammenbau + Export + Gate
    k = m3.Manifold.batch_boolean(teile, m3.OpType.Add)
    if abz: k = k - m3.Manifold.batch_boolean(abz, m3.OpType.Add)
    if add: k = k + m3.Manifold.batch_boolean(add, m3.OpType.Add)
    k = k + m3.Manifold.batch_boolean(erker_teile, m3.OpType.Add)
    L_(f"manifold Status {k.status()}, Genus {k.genus()}")
    k = k.transform(Mw); me = k.to_mesh(); V = np.asarray(me.vert_properties)[:, :3]; Fc = np.asarray(me.tri_verts)
    tm = trimesh.Trimesh(V, Fc, process=False); stl = os.path.join(ausdir, NAME + ".stl"); tm.export(stl); tm.export(stl.replace(".stl", ".ply"))
    th = tm.copy(); th.apply_scale(H0); th.export(stl.replace(".stl", "_h0.stl"))
    tms = trimesh.load(stl, process=False); tms.merge_vertices(); e_ = tms.edges_sorted; eu, cnt = np.unique(e_, axis=0, return_counts=True); offen = int((cnt != 2).sum())
    uq, c = np.unique(np.round(V, 6), axis=0, return_counts=True); dopp = uq[c > 1]
    L_(f"Export {stl}: {len(Fc)} Dreiecke, wasserdicht manifold-Netz={tm.is_watertight}, STL-Roundtrip+merge={tms.is_watertight}, offene Kanten {offen}, Koerper {len(tms.split(only_watertight=False))}, doppelte Positionen {len(dopp)}, Volumen {tm.volume:.1f} m^3; H0 BBox mm {np.round(th.extents, 1).tolist()}")
    if len(dopp): L_("  doppelte Positionen (along, vor, z): " + str(np.round(np.c_[dopp @ u, dopp @ n - of, dopp[:, 2]], 2).tolist()[:8]))
    gate = bool(tms.is_watertight and offen == 0); L_(f"GATE STL-Roundtrip wasserdicht + 0 offene Kanten: {'BESTANDEN' if gate else 'NICHT bestanden'}")
    A11["wasserdicht"] = bool(tm.is_watertight); A11["volumen_m3"] = float(tm.volume); A11["quelle"] = seg_json; A11["giebel_gebaut"] = giebel; A11["log"] = log
    json.dump(A11, open(os.path.join(ausdir, "rohkoerper_v11.json"), "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    D11 = {"u": u.tolist(), "n": n.tolist(), "off_front": of, "achse": achse, "giebel_along": [aw, ae], "rumpf_along": [aw_u, ae_u], "fenster": F, "erker": erk, "erker_gemeinsam": G, "helme": helme_lok, "figuren": figuren, "balkon": balkon,
           "annahmen": annahmen + ann_gk_text(ann_gk), "quellen": {"gitter": seg_json, "rohkoerper": roh_json, "fenster_erker": fe_json, "helme": helme_json, "baluster": bal_json}, "log": log,
           "bau": {"wasserdicht": bool(tm.is_watertight), "wasserdicht_stl_roundtrip": bool(tms.is_watertight), "offene_kanten": offen, "gate": gate, "dreiecke": int(len(Fc)), "volumen_m3": float(tm.volume), "stl": stl}}
    json.dump(D11, open(os.path.join(ausdir, NAME + ".json"), "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


def ann_gk_text(a): return [x["annahme"] if isinstance(x, dict) else str(x) for x in a]


def pruefen(ausdir, wolke, kam_json, bilddir, auditdir):
    import trimesh
    from koerper_fenster_erker import pruefen as pr9
    stl = os.path.join(ausdir, NAME + ".stl"); pr9(stl, os.path.join(ausdir, NAME + ".json"), wolke, kam_json, bilddir, auditdir)
    D = json.load(open(os.path.join(ausdir, NAME + ".json"))); u = np.array(D["u"]); n = np.array(D["n"]); of = D["off_front"]
    th = trimesh.load(stl.replace(".stl", "_h0.stl"), process=False); th.merge_vertices(); tm = trimesh.load(stl, process=False); tm.merge_vertices()
    # Ueberhaenge > 60 Grad (Flaechennormale zeigt steiler als 60 Grad von der Senkrechten nach unten), ohne Bodenflaeche
    N = tm.face_normals; A_ = tm.area_faces; C = tm.triangles_center; zb = tm.bounds[0, 2]
    ov = (N[:, 2] < -math.cos(math.radians(30))) & (C[:, 2] > zb + 0.05); ueber = []
    if ov.any():
        Cl = np.c_[C[ov] @ u, C[ov] @ n - of, C[ov, 2]]; a_ = A_[ov]
        # grob nach Hoehenband/Bauteil gruppieren
        for z0 in np.arange(math.floor(Cl[:, 2].min()), math.ceil(Cl[:, 2].max()), 1.0):
            m = (Cl[:, 2] >= z0) & (Cl[:, 2] < z0 + 1)
            if m.sum(): ueber.append({"z": [float(z0), float(z0 + 1)], "flaeche_m2": float(a_[m].sum()), "n": int(m.sum()), "along": [float(Cl[m, 0].min()), float(Cl[m, 0].max())], "vor": [float(Cl[m, 1].min()), float(Cl[m, 1].max())]})
    erg = {"ueberhang_gt60_flaeche_m2": float(A_[ov].sum()), "ueberhang_gt60_anteil": float(A_[ov].sum() / A_.sum()), "ueberhang_baender": ueber}
    F = D["fenster"]; B = D["balkon"]
    erg["entwurf_mm"] = {"steg_rahmenbreite": F["b_rahmen"] * H0, "oeffnungstiefe": T_OEFF * H0, "baluster_durchmesser": 2 * B["baluster"]["r"] * H0 if B.get("baluster") else None,
                        "handlauf_hoehe": (B["handlauf"]["z1"] - B["handlauf"]["z0"]) * H0, "platte_dicke": (B["platte"]["z1"] - B["platte"]["z0"]) * H0, "konsole_breite": 0.45 * H0, "giebelwand": 0.52 * H0, "figurenblock_min": min(f["breite"] for f in D["figuren"]) * H0 if D["figuren"] else None}
    erg["unter_0.4mm"] = [k for k, v in erg["entwurf_mm"].items() if v is not None and v < 0.4]
    print(json.dumps(erg, indent=1)); json.dump(erg, open(os.path.join(ausdir, NAME + "_slicer_vorcheck.json"), "w"), indent=1)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("analyse_konsolen", "bauen", "pruefen"): print(__doc__); sys.exit(1)
    if a[0] == "analyse_konsolen": analyse_konsolen(a[1], a[2], a[3], a[4], a[5])
    elif a[0] == "bauen": bauen(a[1], a[2], a[3], a[4], a[5], a[6])
    else: pruefen(a[1], a[2], a[3], a[4], a[5])
