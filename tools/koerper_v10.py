#!/usr/bin/env python3
"""koerper_v10.py - Kaufhaus-Koerper v10 aus dem Kantengitter: Rohkoerper (gitter_koerper.baue mit korrigierten Enden/Staffelgiebeln) + Fensterfamilie
+ Erker mit senkrechtem Schaft und Helmen aus formen/helme.json + Balkon (Platte, Handlauf) + Konsolen + Figurenbloecke.
Keine Objektkonstanten: alles aus SEG.json, ROH.json (gitter_koerper), FE.json (koerper_fenster_erker analyse), HELME.json.

  bauen   (venv rcpark):  koerper_v10.py bauen SEG.json ROH_v7.json FE_v9.json HELME.json AUSDIR            -> AUSDIR/rohkoerper_v10.json, koerper_v10.json, koerper_v10.stl/.ply/_h0.stl
  pruefen (venv-seg):     koerper_v10.py pruefen AUSDIR WOLKE.npz KAM.json BILDDIR AUDITDIR                  -> Wolkennaehe, Vergleichsbilder, Mindestdicke H0

Enden: Giebelebenen = Paar der Endebenen (z_max > Traufe + 3 m), dessen Mitte der Erkerachse am naechsten liegt (Fenster/Erker sind symmetrisch);
unterer Rumpf (Boden..Traufe) bis zu den Erker-Wandanschluessen verlaengert (ANNAHME). Staffelgiebel: Steiger-Cluster je Ende, fehlt die Treppe an einem Ende -> Spiegel (ANNAHME)."""
import sys, os, json, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gitter_koerper as GK
from koerper_fenster_erker import fenstergruppe, cs, ABST, H0, T_OEFF

NAME = "koerper_v10"


def erker_mitte(e):
    """Erkermitte aus dem aeussersten Frontpfosten-Paar (vor > 0,85 Tiefe), nicht aus dem gewichteten Mittel aller Pfosten."""
    fr = [p for p in e["pfosten"] if p["vor"] > 0.85 * e["tiefe"]]; fr.sort(key=lambda p: p["along"])
    return 0.5 * (fr[0]["along"] + fr[-1]["along"]) if len(fr) >= 2 else e["mitte"]


def steiger(P0, P1, L, dn, M, u, n, al_end, zt, offi, of):
    """Staffelgiebel-Steiger (vertikale Kanten +-1 m um die Endebene, ueber der Traufe, Fronthaelfte) -> monotone Treppe wie in gitter_koerper."""
    vert = np.abs(dn[:, 2]) > 0.9
    m = vert & (np.abs(M @ u - al_end) < 1.0) & (M[:, 2] > zt) & (((M @ n) - offi) * (of - offi) > 0)
    if m.sum() == 0: return [], []
    Xg, wg = GK.stuetzpunkte(P0[m], P1[m], L[m], 0.1); zc = GK.ransac_1d(Xg[:, 2], wg, 0.5, 0.5); st = []
    for c in zc:
        Xi = Xg[c["idx"]]; st.append({"off": float(np.median(Xi @ n)), "z_unten": float(Xi[:, 2].min()), "z_oben": float(Xi[:, 2].max()), "laenge": c["laenge"]})
    st.sort(key=lambda s: -abs(s["off"] - offi)); tr = []
    for s in st:
        if not tr or (abs(s["off"] - offi) < abs(tr[-1]["off"] - offi) - 0.3 and s["z_unten"] > tr[-1]["z_oben"] - 0.3): tr.append(s)
    return tr, st


def bauen(seg_json, roh_json, fe_json, helme_json, ausdir):
    import manifold3d as m3, trimesh
    os.makedirs(ausdir, exist_ok=True); log = []; L_ = lambda s: (print(s), log.append(s)); annahmen = []
    d, P0, P1, L, dn, Q = GK.lade(seg_json); A = json.load(open(roh_json)); D9 = json.load(open(fe_json)); HL = json.load(open(helme_json))["helme"]
    u = np.array(A["u"]); n = np.array(A["n"]); of = A["off_front"]; zt = A["traufe"]["z"]; zf = A["first"]["z"]; offi = A["first"]["offset"]; zb = A["z_boden"]
    M = (P0 + P1) / 2; horiz = np.abs(dn[:, 2]) < 0.2; vert = np.abs(dn[:, 2]) > 0.9; schr = ~horiz & ~vert
    par = horiz & (np.abs(dn @ u) > 0.95); perp = horiz & (np.abs(dn @ n) > 0.95); masken = (par, perp, vert, schr, M)
    hist = A.get("historie", []) + [{"datum": "2026-11-09", "von": os.path.basename(roh_json), "was": "v10: Giebelebenen aus symmetrischem Endebenen-Paar, Staffelgiebel beide Enden, Erker/Fenster/Balkon/Konsolen/Figuren angebaut (koerper_v10.py)"}]
    # ---------- Erker: Mitte aus Frontpfosten-Paar, Achse
    G = D9["erker_gemeinsam"]; erk = []
    for e in D9["erker"]:
        c = erker_mitte(e); erk.append(dict(e, mitte_alt=e["mitte"], mitte=c)); L_(f"Erker: Mitte {e['mitte']:.2f} (gewichtet) -> {c:.2f} (Frontpfosten-Paar)")
    achse = 0.5 * (erk[0]["mitte"] + erk[-1]["mitte"]) if len(erk) >= 2 else D9["achse"]
    L_(f"Erkerachse along {achse:.2f}; Fenstergruppenmitte {np.mean([g['mitte'] for g in D9['fenster']['gruppen']]):.2f}")
    # ---------- Giebelebenen: Paar der Endebenen (hoch) mit Mitte nahe der Achse
    kand = [e for e in A["enden"] if e["z_max"] > zt + 3.0]; links = [e for e in kand if e["along"] < achse]; rechts = [e for e in kand if e["along"] > achse]
    best = None
    for w_ in links:
        for e_ in rechts:
            sc = abs(0.5 * (w_["along"] + e_["along"]) - achse) + 0.3 * ((not w_["belegt"]) + (not e_["belegt"]))
            if best is None or sc < best[0]: best = (sc, w_, e_)
    if best:
        _, ew, ee = best; aw, ae = ew["along"], ee["along"]
        L_(f"Giebelebenen: along {aw:.2f} ({ew['laenge']:.0f} m, {'belegt' if ew['belegt'] else 'schwach'}, z bis {ew['z_max']:.1f}) / {ae:.2f} ({ee['laenge']:.0f} m, {'belegt' if ee['belegt'] else 'schwach'}, z bis {ee['z_max']:.1f}); Mitte {(aw + ae) / 2:.2f} vs Achse {achse:.2f} (v7: {A['along_w']:.2f}/{A['along_e']:.2f})")
        for e in (ew, ee):
            if not e["belegt"]: annahmen.append(f"ANNAHME: Giebelebene along {e['along']:.2f} nur schwach belegt ({e['laenge']:.0f} m)")
    else:
        aw, ae = A["along_w"], A["along_e"]; annahmen.append("ANNAHME: Giebelebenen wie v7 (kein hohes Endebenen-Paar)")
    # unterer Rumpf bis zu den Erker-Wandanschluessen
    xw = G["x_wand"]; aw_u = min(aw, min(e["mitte"] for e in erk) - xw); ae_u = max(ae, max(e["mitte"] for e in erk) + xw)
    annahmen.append(f"ANNAHME: unterer Rumpf (Boden..Traufe, Front bis Laubenrueckwand) bis zu den Erker-Wandanschluessen along {aw_u:.2f}..{ae_u:.2f} verlaengert; Endbogen der Laube nicht gebaut")
    L_(f"Unterer Rumpf along {aw_u:.2f}..{ae_u:.2f} (Erker-Wandanschluesse), Dach/Giebel {aw:.2f}..{ae:.2f}")
    # ---------- Staffelgiebel beide Enden
    giebel = {}
    for name, al_end in (("ende_minus", aw), ("ende_plus", ae)):
        tr, st = steiger(P0, P1, L, dn, M, u, n, al_end, zt, offi, of)
        giebel[name] = {"stufen": tr, "alle_steiger": st, "form": "staffel" if len(tr) >= 3 else "gerade"}
        L_(f"Giebel {name} (along {al_end:.2f}): {len(st)} Steiger, {len(tr)} als Treppe -> {giebel[name]['form']}: " + ", ".join(f"off {s['off']:.2f} z {s['z_unten']:.1f}-{s['z_oben']:.1f}" for s in tr))
    for a_, b_ in (("ende_minus", "ende_plus"), ("ende_plus", "ende_minus")):
        if giebel[a_]["form"] != "staffel" and giebel[b_]["form"] == "staffel":
            giebel[a_] = {"stufen": giebel[b_]["stufen"], "alle_steiger": giebel[a_]["alle_steiger"], "form": "staffel", "quelle": f"ANNAHME: Spiegel von {b_}"}
            annahmen.append(f"ANNAHME: Staffelgiebel {a_} = Spiegel von {b_} (am eigenen Ende keine Treppe im Gitter; Steiger dort = Erkerturm)"); L_(f"Giebel {a_}: Treppe gespiegelt von {b_} (ANNAHME)")
    # Staffel-Treppe: erster Steiger muss an der Traufe beginnen, sonst Wand von Traufe bis Stufe 1 an der Front (gitter_koerper erwartet pts ab [of, zt])
    # ---------- Rohkoerper bauen (gitter_koerper.baue) mit korrigierten Enden, ohne Vorsprung/Helme
    A10 = dict(A); A10.update(along_w=aw, along_e=ae, giebel=giebel, vorspruenge=[], historie=hist, achse=achse, along_w_unten=aw_u, along_e_unten=ae_u)
    d10 = dict(d); d10["helme"] = []
    Mw = np.c_[u, n, [0, 0, 1], [0, 0, 0]]; Mi = np.linalg.inv(np.r_[Mw, [[0, 0, 0, 1]]])[:3]
    roh = GK.baue(d10, A10, annahmen, P0, P1, L, dn, Q, masken, L_).transform(Mi)   # lokal (along, off, z)
    teile = [roh]
    # unterer Rumpf-Verlaengerung: Kasten Front..Laubenrueckwand (bzw. 6 m), Boden..Traufe
    ol = A["off_laube"] if A.get("off_laube") is not None else of - 6.0
    for a0, a1 in ((aw_u, aw + ABST), (ae - ABST, ae_u)):
        if a1 - a0 > 0.05: teile.append(m3.Manifold.cube([a1 - a0, abs(of - ol), zt - zb]).translate([a0, min(of, ol), zb]))   # Front koplanar mit der Hauptfront (2 cm Ruecksprung machte den STL-Roundtrip schlechter: 13 statt 5 Koerper)
    # ---------- Fenstergruppen (wie v9)
    F = D9["fenster"]; abz = []; add = []
    for g in [g for g in F["gruppen"] if g["belegt"]]:
        a_, s_ = fenstergruppe(m3, g["mitte"], F, 0, 0, F["n_licht"], F["w_licht"]); T = np.array([[1, 0, 0, g["mitte"]], [0, 1, 0, of], [0, 0, 1, 0]], float)
        abz += [x.transform(T) for x in a_]; add += [x.transform(T) for x in s_]
    # ---------- Figurenkonsolen/Baldachine: Kantencluster zwischen den Gruppen -> Bloecke
    al = M @ u; off = M @ n; Gm = np.array([g["mitte"] for g in F["gruppen"]]); dg = np.min(np.abs(al[:, None] - Gm[None]), axis=1)
    m = (np.abs(off - of) < 0.8) & (M[:, 2] > F["z_sohl"] - 0.3) & (M[:, 2] < zt - 0.3) & (dg > 1.5 * F["w_licht"] + 0.1) & (al > min(e["mitte"] for e in erk) + xw) & (al < max(e["mitte"] for e in erk) - xw)
    X, w = GK.stuetzpunkte(P0[m], P1[m], L[m], 0.1); figuren = []
    for e in sorted(GK.ransac_1d(X @ u, w, 0.3, 8.0), key=lambda e: e["offset"]):
        Xi = X[e["idx"]]; a0, a1 = np.percentile(Xi @ u, 5), np.percentile(Xi @ u, 95); z0, z1 = Xi[:, 2].min(), Xi[:, 2].max(); t_ = np.percentile(Xi @ n, 90) - of
        if z1 - z0 < 1.5: continue
        fig = {"along": float(e["offset"]), "breite": float(max(a1 - a0, 0.4)), "z0": float(z0), "z1": float(z1), "tiefe": float(max(t_, 0.3)), "laenge": e["laenge"]}; figuren.append(fig)
        add.append(m3.Manifold.cube([fig["breite"], fig["tiefe"] + 0.2, z1 - z0]).translate([fig["along"] - fig["breite"] / 2, of - 0.2, z0]))
    L_(f"Figurenbloecke: {len(figuren)} bei along " + ", ".join(f"{f['along']:.2f} (B {f['breite']:.2f}, T {f['tiefe']:.2f}, z {f['z0']:.1f}-{f['z1']:.1f}, {f['laenge']:.0f} m)" for f in figuren))
    annahmen.append("ANNAHME: Figur + Konsole + Baldachin je Position als ein Quader (Breite/Hoehe/Tiefe aus dem Kantencluster), keine Figur")
    # ---------- Balkon: Platte + Handlauf aus horizontalen Kanten vor der Front, between den Erkern
    al_b0, al_b1 = min(e["mitte"] for e in erk) + xw - 0.05, max(e["mitte"] for e in erk) - xw + 0.05
    m = horiz & (off - of > 0.3) & (M[:, 2] > zb + 4) & (M[:, 2] < D9["z_balkon"] + 0.3) & (al > al_b0) & (al < al_b1)
    X, w = GK.stuetzpunkte(P0[m], P1[m], L[m], 0.1); hz = sorted(GK.ransac_1d(X[:, 2], w, 0.06, 2.0), key=lambda e: e["offset"])
    hz = [{"z": e["z"] if "z" in e else e["offset"], "laenge": e["laenge"], "vor": float(np.percentile(X[e["idx"]] @ n, 90) - of), "vor_min": float(np.percentile(X[e["idx"]] @ n, 10) - of)} for e in hz]
    for h in hz: L_(f"  Balkon-Horizontale z {h['z']:.2f} L {h['laenge']:.0f} m vor {h['vor_min']:.2f}..{h['vor']:.2f}")
    platte = [h for h in hz if h["z"] < D9["z_balkon_unten"] + 1.0]; rail = [h for h in hz if h["z"] > D9["z_balkon"] - 0.8]
    balkon = {}
    if platte:
        zp1 = max(h["z"] for h in platte); zp0 = min(h["z"] for h in platte)
        if zp1 - zp0 < 0.12: zp0 = zp1 - 0.2; annahmen.append("ANNAHME: Plattendicke 0,20 m (nur eine Plattenkante im Gitter)")
        tp = max(h["vor"] for h in platte); balkon["platte"] = {"z0": zp0, "z1": zp1, "tiefe": tp, "along": [al_b0, al_b1]}
        teile.append(m3.Manifold.cube([al_b1 - al_b0, tp + 0.2, zp1 - zp0]).translate([al_b0, of - 0.2, zp0]))
    if rail:
        zr1 = max(h["z"] for h in rail); zr0 = min(h["z"] for h in rail)
        if zr1 - zr0 < 0.12: zr0 = zr1 - 0.18; annahmen.append("ANNAHME: Handlaufhoehe 0,18 m")
        v0 = min(h["vor_min"] for h in rail); v1 = max(h["vor"] for h in rail); balkon["handlauf"] = {"z0": zr0, "z1": zr1 + 0.05, "vor": [v0, v1], "along": [al_b0, al_b1]}
        ar0, ar1 = min(e["mitte"] for e in erk) + 0.8, max(e["mitte"] for e in erk) - 0.8   # Handlauf bis in die Erker-Schraegflaechen (dort vor > 0,95 m), sonst schwebt er
        balkon["handlauf"]["along"] = [ar0, ar1]
        teile.append(m3.Manifold.cube([ar1 - ar0, v1 - v0, zr1 + 0.05 - zr0]).translate([ar0, of + v0, zr0]))   # +5 cm: ueberlappt die Erkerunterkante
    L_(f"Balkon: Platte {balkon.get('platte')} Handlauf {balkon.get('handlauf')}")
    # Baluster: nur mit bestandener Formdatei (quelle 13) - Datei formen/baluster.json ist laut eigenem Hinweis UNVERIFIZIERT -> weggelassen
    annahmen.append("OFFEN: Baluster nicht gebaut - formen/baluster.json: 'UNVERIFIZIERT ... automatischer Kantentest nicht bestanden'; Handlauf haengt nur an den Erkern")
    # Konsolen unter der Platte: Kantencluster (alle Quellen) z Platte-1,8 .. Platte, vor der Front
    if platte:
        m = (off - of > 0.1) & (M[:, 2] > zp0 - 1.8) & (M[:, 2] < zp1) & (al > al_b0) & (al < al_b1)
        X, w = GK.stuetzpunkte(P0[m], P1[m], L[m], 0.1); kons = []
        for e in sorted(GK.ransac_1d(X @ u, w, 0.25, 1.0), key=lambda e: e["offset"]):
            Xi = X[e["idx"]]; z0 = float(Xi[:, 2].min())
            if zp0 - z0 < 0.5: continue
            if kons and e["offset"] - kons[-1]["along"] < 0.6: kons[-1]["along"] = 0.5 * (kons[-1]["along"] + e["offset"]); kons[-1]["z0"] = min(kons[-1]["z0"], z0); continue
            kons.append({"along": float(e["offset"]), "z0": z0, "laenge": e["laenge"]})
        for k in kons: teile.append(m3.Manifold.cube([0.45, tp - 0.15 + 0.2, zp0 + ABST - k["z0"]]).translate([k["along"] - 0.225, of - 0.2, k["z0"]]))
        balkon["konsolen"] = kons; L_(f"Konsolen: {len(kons)} Bloecke bei along " + ", ".join(f"{k['along']:.2f} (z ab {k['z0']:.1f})" for k in kons))
        annahmen.append("ANNAHME: Konsolen 0,45 m breit, Tiefe Platte - 0,15 m; Anzahl aus dem Gitter (Foto zeigt mehr: 3 je Joch) - offen")
    # ---------- Erker mit senkrechtem Schaft bis zum Helmfuss, Helme aus HELME.json
    erker_teile = []; helme_lok = []
    for h in HL:
        p = np.array([h["cx"], h["cy"], 0]); helme_lok.append({"along": float(p @ u), "off": float(p @ n), "z_fuss": h["z_fuss"], "z_spitze": h["z_spitze"], "r_fuss": h["r_fuss"], "phi": h.get("phi", 0), "sektoren": int(h.get("sektoren", 16))})
    t = G["tiefe"]; xf = G["x_front"]; b = F["b_rahmen"]
    for e in erk:
        c = e["mitte"]; hm = min(helme_lok, key=lambda h: abs(h["along"] - c)); hm = hm if abs(hm["along"] - c) < 1.5 else None
        poly = [[-xw, -0.3], [-xw, -ABST], [-xf, t], [xf, t], [xw, -ABST], [xw, -0.3]]
        z_top = hm["z_fuss"] + 0.05 if hm else G["z_oben"]
        koerper = m3.Manifold.extrude(cs(poly), z_top - G["z_unten"]).translate([0, 0, G["z_unten"]])   # Erker + senkrechter Schaft bis Helmfuss
        zu = D9["z_balkon_unten"] - 0.3; sx = (xw - ABST) / xw; pin = [[x * sx, y - ABST] for x, y in poly[1:5]]
        unters = m3.Manifold.hull_points([[x, y, G["z_unten"] + 0.05] for x, y in pin] + [[-xw * sx, -0.3 + ABST, G["z_unten"] + 0.05], [xw * sx, -0.3 + ABST, G["z_unten"] + 0.05], [-0.4, -0.3, zu], [0.4, -0.3, zu], [-0.4, -ABST, zu], [0.4, -ABST, zu]])   # Trichterspitze 2 cm in der Wand
        polyr = [[-xw - b, -0.3], [-xw - b, 0], [-xf - b * 0.5, t + b], [xf + b * 0.5, t + b], [xw + b, 0], [xw + b, -0.3]]
        ring = m3.Manifold.extrude(cs(polyr), 0.25 + ABST).translate([0, 0, G["z_oben"] - 0.25])   # Gesims an der Erker-Oberkante
        tl = [koerper, unters, ring]
        if hm:
            k = hm["sektoren"] if hm["sektoren"] <= 16 else 16; hh = hm["z_spitze"] - hm["z_fuss"]
            tl.append(m3.Manifold.cylinder(hh, hm["r_fuss"], 0.0, k).rotate([0, 0, math.degrees(hm["phi"])]).translate([hm["along"] - c, hm["off"] - of, hm["z_fuss"]]))
            # Uebergang Schaftpolygon -> Helm (Huelle bis 0,6 m ueber dem Helmfuss), damit kein Absatz bleibt (ANNAHME)
            dz = 0.6; r2 = hm["r_fuss"] * (1 - dz / hh) * 0.98; ang = np.linspace(0, 2 * math.pi, k, endpoint=False) + hm["phi"]
            tl.append(m3.Manifold.hull_points([[x, y, z_top - 0.05] for x, y in pin] + [[-xw * sx, -0.3 + ABST, z_top - 0.05], [xw * sx, -0.3 + ABST, z_top - 0.05]] + [[hm["along"] - c + r2 * math.cos(a_), hm["off"] - of + r2 * math.sin(a_), hm["z_fuss"] + dz] for a_ in ang]))
            L_(f"Erker {c:.2f}: Schaft bis {z_top:.2f}, Helm along {hm['along']:.2f} off {hm['off']:.2f} (hinter Front {of - hm['off']:.2f}), Fuss {hm['z_fuss']:.2f}, Spitze {hm['z_spitze']:.2f}, r {hm['r_fuss']:.2f}")
        else: L_(f"Erker {c:.2f}: KEIN Helm in HELME.json innerhalb 1,5 m")
        E = m3.Manifold.batch_boolean(tl, m3.OpType.Add)
        Fe = dict(F)
        for (xa, ya), (xb, yb) in (((-xw, 0), (-xf, t)), ((-xf, t), (xf, t)), ((xf, t), (xw, 0))):
            lng = math.hypot(xb - xa, yb - ya); n_l = max(1, int(round(lng / G["lichtbreite"]))); w_l = (lng - 2 * b) / n_l
            a_, s_ = fenstergruppe(m3, 0, Fe, 0, 0, n_l, w_l, profil=False, z_sohl=G["z_sohl"], z_kaem=G["z_kaempfer"], z_schul=G["z_schulter"], z_scheit=G["z_schulter"] + 0.3)
            ex = np.array([xb - xa, yb - ya]) / lng; ey = np.array([ex[1], -ex[0]])
            if ey[1] < -1e-6: ey = -ey
            if abs(ey[1]) < 1e-6 and ey[0] * (xa + xb) < 0: ey = -ey
            T = np.array([[ex[0], ey[0], 0, 0.5 * (xa + xb)], [ex[1], ey[1], 0, 0.5 * (ya + yb)], [0, 0, 1, 0]], float)
            E = E - m3.Manifold.batch_boolean([x.transform(T) for x in a_], m3.OpType.Add) + m3.Manifold.batch_boolean([x.transform(T) for x in s_], m3.OpType.Add)
        erker_teile.append(E.translate([c, of, 0]))
    annahmen.append("ANNAHME: Erkerschaft = Erkerpolygon senkrecht bis Helmfuss + Huelle zum Helm (0,6 m); Helm-Pyramiden aus formen/helme.json (Wolkenfit, Fototest bestanden)")
    # ---------- Zusammenbau
    k = m3.Manifold.batch_boolean(teile, m3.OpType.Add)
    if abz: k = k - m3.Manifold.batch_boolean(abz, m3.OpType.Add)
    if add: k = k + m3.Manifold.batch_boolean(add, m3.OpType.Add)
    if erker_teile: k = k + m3.Manifold.batch_boolean(erker_teile, m3.OpType.Add)
    L_(f"manifold Status {k.status()}, Genus {k.genus()}")
    k = k.transform(Mw); me = k.to_mesh(); V = np.asarray(me.vert_properties)[:, :3]; Fc = np.asarray(me.tri_verts)
    tm = trimesh.Trimesh(V, Fc, process=False); stl = os.path.join(ausdir, NAME + ".stl"); tm.export(stl); tm.export(stl.replace(".stl", ".ply"))
    th = tm.copy(); th.apply_scale(H0); th.export(stl.replace(".stl", "_h0.stl"))
    tms = trimesh.load(stl, process=False); tms.merge_vertices()
    L_(f"Export {stl}: {len(Fc)} Dreiecke, wasserdicht manifold-Netz={tm.is_watertight}, STL-Roundtrip={tms.is_watertight}, Koerper {len(tms.split(only_watertight=False))}, Volumen {tm.volume:.1f} m^3; H0 BBox mm {np.round(th.extents, 1).tolist()}")
    A10["wasserdicht"] = bool(tm.is_watertight); A10["volumen_m3"] = float(tm.volume); A10["quelle"] = seg_json; A10["log"] = log
    json.dump(A10, open(os.path.join(ausdir, "rohkoerper_v10.json"), "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    D10 = {"u": u.tolist(), "n": n.tolist(), "off_front": of, "achse": achse, "giebel_along": [aw, ae], "rumpf_unten_along": [aw_u, ae_u], "fenster": F, "erker": erk, "erker_gemeinsam": G, "helme": helme_lok,
           "figuren": figuren, "balkon": balkon, "annahmen": annahmen, "quellen": {"gitter": seg_json, "rohkoerper": roh_json, "fenster_erker": fe_json, "helme": helme_json}, "log": log,
           "bau": {"wasserdicht": bool(tm.is_watertight), "wasserdicht_stl_roundtrip": bool(tms.is_watertight), "dreiecke": int(len(Fc)), "volumen_m3": float(tm.volume), "stl": stl}}
    json.dump(D10, open(os.path.join(ausdir, NAME + ".json"), "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    L_(f"Annahmen {len(annahmen)}: " + " | ".join(annahmen))


def pruefen(ausdir, wolke, kam_json, bilddir, auditdir):
    import trimesh
    from koerper_fenster_erker import pruefen as pr9
    stl = os.path.join(ausdir, NAME + ".stl"); pr9(stl, os.path.join(ausdir, NAME + ".json"), wolke, kam_json, bilddir, auditdir)
    # Mindestdicke bei 1:87: Kugel-Dicke an Oberflaechenpunkten (trimesh.proximity.thickness), 4000 Punkte, plus Entwurfswerte
    th = trimesh.load(stl.replace(".stl", "_h0.stl"), process=False); th.merge_vertices()
    pts, fid = trimesh.sample.sample_surface(th, 4000); nrm = th.face_normals[fid]
    try:
        dk = trimesh.proximity.thickness(th, pts, exterior=False, normals=nrm, method="max_sphere"); dk = dk[np.isfinite(dk) & (dk > 0)]
        erg = {"dicke_mm_min": float(dk.min()), "dicke_mm_q01": float(np.percentile(dk, 1)), "dicke_mm_q05": float(np.percentile(dk, 5)), "anteil_unter_0.4mm": float((dk < 0.4).mean()), "anteil_unter_0.8mm": float((dk < 0.8).mean()), "n": int(len(dk))}
    except Exception as ex: erg = {"fehler": str(ex)}
    D = json.load(open(os.path.join(ausdir, NAME + ".json"))); F = D["fenster"]
    erg["entwurf_mm"] = {"steg_rahmenbreite": F["b_rahmen"] * H0, "oeffnungstiefe": T_OEFF * H0, "handlauf_hoehe": (D["balkon"]["handlauf"]["z1"] - D["balkon"]["handlauf"]["z0"]) * H0 if D["balkon"].get("handlauf") else None,
                        "platte_dicke": (D["balkon"]["platte"]["z1"] - D["balkon"]["platte"]["z0"]) * H0 if D["balkon"].get("platte") else None, "staffelgiebel_wand": 0.52 * H0, "helmspitze": 0.0}
    print(json.dumps(erg, indent=1)); json.dump(erg, open(os.path.join(ausdir, NAME + "_dicke.json"), "w"), indent=1)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("bauen", "pruefen"): print(__doc__); sys.exit(1)
    if a[0] == "bauen": bauen(a[1], a[2], a[3], a[4], a[5])
    else: pruefen(a[1], a[2], a[3], a[4], a[5])
