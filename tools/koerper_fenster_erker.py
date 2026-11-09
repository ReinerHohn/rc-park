#!/usr/bin/env python3
"""koerper_fenster_erker.py - Fenster- und Erkerfamilie als parametrische Koerper AUS dem Kantengitter, zusammengebaut mit dem Rohkoerper.
Keine Objektkonstanten: Fassadenrahmen (u, n, Front-Offset), Traufe, Balkonoberkante kommen aus ROHKOERPER.json (gitter_koerper.py),
alle Fenster-/Erkermasse aus dem Gitter (SEG.json), Anzahl/Lage nur mit Fotobeleg (Stabilitaetskarten, >= 3 Fotos; Regel 9).

  analyse (venv-seg, torch):     koerper_fenster_erker.py analyse SEG.json ROHKOERPER.json KAM.json STABILDIR AUS.json [--helme HELME.json]
  bauen   (venv rcpark, manifold3d): koerper_fenster_erker.py bauen AUS.json ROHKOERPER.stl KOERPER_OUT.stl
  pruefen (venv-seg, torch/cv2): koerper_fenster_erker.py pruefen KOERPER.stl AUS.json WOLKE.npz KAM.json BILDDIR AUDITDIR

Fensterfamilie (Hauptfassade): Fensterband = Balkonoberkante (Vorsprung z_max_voll) .. Traufe. Pfosten = vertikale Gitterkanten in der Frontebene
(1D-RANSAC, Toleranz 6 cm); Gruppen = Pfostenpaare mit gleichem Abstand (Mittellicht), Gruppenmitte, Periode; je Gruppe 3 Lichter (Pfosten auf +-1,5 Lichtbreiten
im Gitter belegt oder ANNAHME); Hoehen (Sohlbank, Kaempfer, Schulter, Scheitel) aus horizontalen Kanten; Bekroenung = Hoehenprofil der schraegen Kanten ueber |x - Mitte|.
Gleichheitsregel: alle Gruppen gleiche Masse (Median), Abweichung je Gruppe im Bericht.
Erkerfamilie: vertikale Kanten vor der Front (Offset > Front + 0,25 m) -> 2D-Cluster (along, offset) = Fensterpfosten der Erkerflaechen -> Polygon (Spiegelung an der Erkermitte),
Hoehen aus den horizontalen Erkerkanten; Untersicht = Huelle Polygon -> Wandlinie (ANNAHME Hoehe = Balkonunterkante); Helm aus HELME (Wolkenfit), zweiter Helm = Spiegel (ANNAHME).
Koerper: Oeffnungen 10 cm tief (ANNAHME), Pfosten/Kaempfer-Stege 2 cm hinter der Flaeche, Rahmenbreite aus Gitter-Doppelkanten; alle Boolean-Abstaende >= 2 cm."""
import sys, os, json, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gitter_koerper import lade, stuetzpunkte, ransac_1d, cs, H0

TOL = 0.06        # Rastertoleranz Fenster (m)
T_OEFF = 0.10     # ANNAHME: Oeffnungstiefe
T_RAHM = 0.15     # ANNAHME: Rahmentiefe in der Wand
ABST = 0.02       # Boolean-Abstand


def rahmen(A):
    u = np.array(A["u"]); n = np.array(A["n"]); return u, n, float(A["off_front"])


# ----------------------------------------------------------------------------- Fotobeleg (wie stuetzung_alle in gitter_zurueck.py)
def fotobeleg(segs, KAM, sd, thr=0.3, stuetz=0.5, dmax=45.0, tolm=0.12):
    """Je Segment: Zahl der Fotos (Kamera < dmax, Segment ganz im Bild), in denen >= stuetz der Punkte auf einer Kante der Stabilitaetskarte liegen, und Gegenstimmen."""
    import torch, cv2
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    fs = [f for f in sorted(KAM) if os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png"))]
    n = 24; A = torch.tensor([s[0] for s in segs], device=dev, dtype=torch.float32); B = torch.tensor([s[1] for s in segs], device=dev, dtype=torch.float32)
    tt = torch.linspace(0, 1, n, device=dev); Q = (A[:, None] + (B - A)[:, None] * tt[None, :, None]).reshape(-1, 3); M = len(segs); mid = ((A + B) / 2).cpu().numpy()
    ja = torch.zeros(M, device=dev, dtype=torch.int32); nein = torch.zeros(M, device=dev, dtype=torch.int32); KART = {}; fotos_ja = [[] for _ in range(M)]
    for f in fs:
        k = KAM[f]; C = np.array(k["C"]); dist_i = np.linalg.norm(mid - C, axis=1); nah = torch.from_numpy(dist_i < dmax).to(dev)
        if not nah.any(): continue
        if f not in KART: KART[f] = torch.from_numpy(cv2.imread(os.path.join(sd, os.path.splitext(f)[0] + ".png"), 0)).to(dev) >= 255 * thr
        V0 = KART[f]; sj = V0.shape[1] / k["W"]; rad = int(np.clip(round(tolm * k["f"] * sj / max(float(np.median(dist_i[dist_i < dmax])), 1.0)), 2, 8))
        Vm = torch.nn.functional.max_pool2d(V0.float()[None, None], 2 * rad + 1, 1, rad)[0, 0]
        R = torch.tensor(k["Rn"], device=dev); t = torch.tensor(k["tn"], device=dev); X = Q @ R.T + t; z = X[:, 2].clamp(min=0.3)
        x = X[:, 0] / z; y = X[:, 1] / z; f1 = 1 + k["params"][3] * (x * x + y * y)
        uu = ((k["f"] * x * f1 + k["cx"]) * sj).round().long(); vv = ((k["f"] * y * f1 + k["cy"]) * sj).round().long(); Hh, Ww = Vm.shape
        ok = (X[:, 2] > 1) & (uu >= 0) & (uu < Ww) & (vv >= 0) & (vv < Hh); hit = torch.zeros(len(Q), device=dev); hit[ok] = Vm[vv[ok], uu[ok]]
        okm = ok.view(M, n).float().mean(1); hm = hit.view(M, n).sum(1) / ok.view(M, n).float().sum(1).clamp(min=1)
        g_ = nah & (okm >= 0.9); j = g_ & (hm >= stuetz); ja += j.int(); nein += (g_ & (hm < stuetz)).int()
        for i in torch.where(j)[0].tolist(): fotos_ja[i].append(f)
    return ja.cpu().numpy(), nein.cpu().numpy(), fotos_ja


def welt(u, n, al, off, z):
    return (al * u + off * n + np.array([0, 0, z])).tolist()


# ----------------------------------------------------------------------------- Analyse
def analyse(seg_json, roh_json, kam_json, stabildir, aus_json, helme_json=None):
    d, P0, P1, L, dn, Q = lade(seg_json); A = json.load(open(roh_json)); u, n, of = rahmen(A)
    M = (P0 + P1) / 2; off = M @ n; al = M @ u; vert = np.abs(dn[:, 2]) > 0.9; horiz = np.abs(dn[:, 2]) < 0.2; schr = ~vert & ~horiz
    log = []; L_ = lambda s: (print(s), log.append(s))
    zt = A["traufe"]["z"]; vs = A.get("vorspruenge", []); zb = vs[0].get("z_max_voll", vs[0]["z_min"]) if vs else A["z_boden"] + 8.0
    L_(f"Fensterband Front: z {zb:.2f} (Balkonoberkante aus Vorsprung) .. {zt:.2f} (Traufe); Front-Offset {of:.2f}")
    band = (np.abs(off - of) < 0.5) & (M[:, 2] > zb) & (M[:, 2] < zt)
    # --- Pfosten
    m = band & vert; X, w = stuetzpunkte(P0[m], P1[m], L[m], 0.1); eb = ransac_1d(X @ u, w, TOL, 0.6); eb.sort(key=lambda e: e["offset"])
    pf = [{"along": e["offset"], "laenge": e["laenge"], "z0": float(X[e["idx"]][:, 2].min()), "z1": float(X[e["idx"]][:, 2].max())} for e in eb]
    for p in pf: L_(f"  Pfosten along {p['along']:6.2f} L {p['laenge']:5.1f} z {p['z0']:.2f}..{p['z1']:.2f}")
    # --- Horizontale
    m = band & horiz; Xh, wh = stuetzpunkte(P0[m], P1[m], L[m], 0.1); ebh = ransac_1d(Xh[:, 2], wh, 0.08, 1.0); ebh.sort(key=lambda e: e["offset"])
    hz = [{"z": e["offset"], "laenge": e["laenge"]} for e in ebh]
    for h in hz: L_(f"  Horizontal z {h['z']:5.2f} L {h['laenge']:5.1f}")
    # Rahmenbreite aus Doppelkanten: Abstand benachbarter Horizontalcluster < 0,3 m
    zs = np.array([h["z"] for h in hz]); dz = np.diff(zs); b_rahmen = float(np.median(dz[(dz > 0.06) & (dz < 0.3)])) if ((dz > 0.06) & (dz < 0.3)).any() else 0.12
    L_(f"Rahmenbreite aus Doppelkanten (Median benachbarter Horizontalcluster 6-30 cm): {b_rahmen:.3f} m")
    # --- Gruppen: Pfostenpaare mit Abstand = haeufigster Abstand (Mittellicht), hohe Pfosten (z1 nahe Maximum)
    zmax = np.percentile([p["z1"] for p in pf], 80); hoch = [p for p in pf if p["z1"] > zmax - 0.4]
    paare = []
    for i, p in enumerate(hoch[:-1]):
        q = hoch[i + 1]; dd = q["along"] - p["along"]
        if 0.5 < dd < 1.6: paare.append((p, q, dd))
    w_licht = float(np.median([t[2] for t in paare])); paare = [t for t in paare if abs(t[2] - w_licht) < 0.12]
    gruppen = [{"mitte": (p["along"] + q["along"]) / 2, "w_licht_lokal": dd, "z1_mittelpfosten": max(p["z1"], q["z1"]), "z0_mittelpfosten": min(p["z0"], q["z0"])} for p, q, dd in paare]
    mitten = np.array([g["mitte"] for g in gruppen]); periode = float(np.median(np.diff(mitten))) if len(mitten) > 1 else None
    L_(f"Gruppen (Mittellicht-Pfostenpaare, Lichtbreite {w_licht:.2f} m): {len(gruppen)} bei along {np.round(mitten, 2).tolist()}, Periode {periode}")
    # Aussenpfosten je Gruppe (bei +-1,5 Lichtbreiten) im Gitter?
    n_licht = 3   # Lichter je Gruppe: Aussenpfosten-Suche entscheidet (2 oder 3)
    for g in gruppen:
        g["aussenpfosten"] = [p["along"] for p in pf if any(abs(p["along"] - (g["mitte"] + s * 1.5 * w_licht)) < 0.12 for s in (-1, 1))]
    n_aussen = sum(len(g["aussenpfosten"]) for g in gruppen)
    L_(f"Aussenpfosten bei +-1,5 Lichtbreiten im Gitter: {n_aussen} von {2 * len(gruppen)} -> Lichter je Gruppe = 3 (Mitte + 2 Seiten)" + ("" if n_aussen else " ANNAHME (kein Aussenpfosten im Gitter)"))
    # Hoehen: Sohlbank = Median Pfosten-z0; Kaempfer = staerkste Horizontale zwischen Sohlbank+0,5 und Scheitel-0,5; Scheitel = Median Mittelpfosten z1; Schulter = staerkste Horizontale zwischen Kaempfer+0,2 und Scheitel-0,3
    z_sohl = float(np.median([g["z0_mittelpfosten"] for g in gruppen])); z_scheit = float(np.median([g["z1_mittelpfosten"] for g in gruppen]))
    kand = [h for h in hz if z_sohl + 0.5 < h["z"] < z_scheit - 0.5]; z_kaem = max(kand, key=lambda h: h["laenge"])["z"] if kand else z_sohl + 0.5 * (z_scheit - z_sohl)
    kand = [h for h in hz if z_kaem + 0.2 < h["z"] < z_scheit - 0.3]; z_schul = max(kand, key=lambda h: h["laenge"])["z"] if kand else z_scheit - 0.6
    kand = [h for h in hz if abs(h["z"] - z_scheit) < 0.25]; z_scheit_h = max(kand, key=lambda h: h["laenge"])["z"] if kand else z_scheit
    L_(f"Hoehen: Sohlbank {z_sohl:.2f} (Pfostenfuss), Kaempfer {z_kaem:.2f}, Schulter {z_schul:.2f}, Scheitel {z_scheit_h:.2f} (Horizontale), Mittelpfosten bis {z_scheit:.2f}")
    # Bekroenung: Hoehenprofil der schraegen Kanten ueber |x - Mitte| (alle Gruppen uebereinander), Bins 10 cm
    m = band & schr & (M[:, 2] > z_kaem); Xs, ws = stuetzpunkte(P0[m], P1[m], L[m], 0.05); xs = Xs @ u
    dx = np.min(np.abs(xs[:, None] - mitten[None, :]), axis=1); prof = []
    for b0 in np.arange(0, 1.5 * w_licht + 0.05, 0.1):
        s = (dx >= b0) & (dx < b0 + 0.1)
        if s.sum() >= 5: prof.append([float(b0 + 0.05), float(np.percentile(Xs[s, 2], 75)), int(s.sum())])
    L_(f"Bekroenungsprofil (|dx| -> z, 75%-Quantil der schraegen Kanten): " + ", ".join(f"{p[0]:.2f}:{p[1]:.2f}({p[2]})" for p in prof))
    # --- Fotobeleg je Gruppe (Rahmen: Aussenpfosten, Mittelpfosten, Sohlbank, Kaempfer)
    KAM = json.load(open(kam_json)); segs = []; idx = []
    for gi, g in enumerate(gruppen):
        c = g["mitte"]; xs_ = [c - 1.5 * w_licht, c - 0.5 * w_licht, c + 0.5 * w_licht, c + 1.5 * w_licht]
        for x_ in xs_: segs.append([welt(u, n, x_, of, z_sohl), welt(u, n, x_, of, z_schul), 1, 1.0]); idx.append(gi)
        for z_ in (z_sohl, z_kaem): segs.append([welt(u, n, xs_[0], of, z_), welt(u, n, xs_[-1], of, z_), 1, 1.0]); idx.append(gi)
    ja, nein, fj = fotobeleg(segs, KAM, stabildir); idx = np.array(idx)
    for gi, g in enumerate(gruppen):
        s = idx == gi; fotos = set(); [fotos.update(fj[i]) for i in np.where(s)[0]]
        # Gruppe belegt, wenn jedes Rahmensegment in >= 3 Fotos (Median ueber Segmente) und mehr Ja als Nein
        g["fotos_ja_min"] = int(ja[s].min()); g["fotos_ja_median"] = float(np.median(ja[s])); g["fotos_nein_median"] = float(np.median(nein[s])); g["fotos"] = sorted(fotos)[:12]
        g["belegt"] = bool(ja[s].min() >= 3 and np.median(ja[s]) >= np.median(nein[s]))
        g["abweichung"] = {"w_licht": g["w_licht_lokal"] - w_licht, "z_scheitel": g["z1_mittelpfosten"] - z_scheit, "z_sohl": g["z0_mittelpfosten"] - z_sohl}
        L_(f"  Gruppe {gi} along {g['mitte']:6.2f}: Fotos ja min {g['fotos_ja_min']} / median {g['fotos_ja_median']:.0f}, nein median {g['fotos_nein_median']:.0f} -> {'BELEGT' if g['belegt'] else 'NICHT belegt'}; Abw. Lichtbreite {g['abweichung']['w_licht']:+.3f}, Scheitel {g['abweichung']['z_scheitel']:+.2f}, Sohl {g['abweichung']['z_sohl']:+.2f}")
    fenster = {"z_sohl": z_sohl, "z_kaempfer": z_kaem, "z_schulter": z_schul, "z_scheitel": z_scheit_h, "w_licht": w_licht, "n_licht": n_licht, "b_rahmen": b_rahmen, "periode": periode,
               "profil": prof, "gruppen": gruppen, "pfosten": pf, "horizontale": hz, "anzahl_gitter": len(gruppen), "anzahl_fotobelegt": sum(g["belegt"] for g in gruppen)}
    # --- Erker: vertikale Kanten vor der Front, 2D-Cluster (along, offset)
    me = vert & (off - of > 0.25) & (off - of < 3.0) & (np.minimum(P0[:, 2], P1[:, 2]) > zb - 0.3) & (M[:, 2] < zt)   # Erkerfenster-Pfosten: Fuss ueber der Balkonoberkante (darunter Balustrade)
    Xe, we = stuetzpunkte(P0[me], P1[me], L[me], 0.1); pts = np.c_[Xe @ u, Xe @ n - of]; frei = np.ones(len(pts), bool); cl = []
    while frei.sum():
        i = np.where(frei)[0]; dd = np.linalg.norm(pts[i][:, None] - pts[i][None], axis=2); cnt = (dd < 0.15) @ we[i]; j = i[np.argmax(cnt)]
        sel = i[np.linalg.norm(pts[i] - pts[j], axis=1) < 0.15]; c = np.average(pts[sel], axis=0, weights=we[sel])
        cl.append({"along": float(c[0]), "vor": float(c[1]), "laenge": float(we[sel].sum()), "z0": float(Xe[sel][:, 2].min()), "z1": float(Xe[sel][:, 2].max())}); frei[sel] = False
    cl = [c for c in cl if c["laenge"] > 0.5 and c["z1"] - c["z0"] > 0.8]; cl.sort(key=lambda c: c["along"])
    # Erker-Kandidaten = Haufen von Pfosten mit Luecken < 1,0 m, mindestens 5 Pfosten
    haufen = []; akt = []
    for c in cl:
        if akt and c["along"] - akt[-1]["along"] > 1.0: haufen.append(akt); akt = []
        akt.append(c)
    if akt: haufen.append(akt)
    erker = []
    for h in haufen:
        if len(h) < 5: continue
        mitte = float(np.average([c["along"] for c in h], weights=[c["laenge"] for c in h])); tief = max(c["vor"] for c in h)
        # Frontflaeche: Pfosten mit vor > 0,85*tief; Schraegflaechen: Rest, Spiegelung an der Mitte -> Halbprofil (|dx|, vor)
        halb = sorted([(abs(c["along"] - mitte), c["vor"], c["laenge"]) for c in h], key=lambda t: t[0])
        front = [t for t in halb if t[1] > 0.85 * tief]; x_front = float(max(t[0] for t in front)) if front else 0.6   # aeusserster Frontpfosten = Frontkante (innere = Mittelpfosten)
        schraeg = [t for t in halb if t[1] <= 0.85 * tief]
        # Schraegflaeche: Gerade durch (x_front, tief) und die Schraeg-Pfosten -> Wandanschluss x_wand bei vor = 0
        if len(schraeg) >= 2:
            xs_ = np.array([t[0] for t in schraeg] + [x_front]); vs_ = np.array([t[1] for t in schraeg] + [tief]); k, b0 = np.polyfit(xs_, vs_, 1); x_wand = float(-b0 / k)
        else: x_wand = x_front + tief; k = -1.0
        # Pfosten-Abstand in der Flaeche (Lichtbreite Erker)
        la = [math.hypot(h[i + 1]["along"] - h[i]["along"], h[i + 1]["vor"] - h[i]["vor"]) for i in range(len(h) - 1)]   # Abstand IN der Flaeche (2D)
        # Hoehen aus horizontalen Erkerkanten (ab Balkonoberkante - 0,6 m: Erkerunterkante liegt knapp unter der Balkonoberkante)
        mh = horiz & (off - of > 0.25) & (al > h[0]["along"] - 0.8) & (al < h[-1]["along"] + 0.8) & (M[:, 2] > zb - 0.6) & (M[:, 2] < zt + 0.5)
        Xh2, wh2 = stuetzpunkte(P0[mh], P1[mh], L[mh], 0.1); eh = sorted(ransac_1d(Xh2[:, 2], wh2, 0.08, 0.8), key=lambda e: e["offset"]); hz_e = [{"z": e["offset"], "laenge": e["laenge"]} for e in eh]
        z0p = float(np.median([c["z0"] for c in h])); z1p = float(np.median([c["z1"] for c in h]))
        unten = [x for x in hz_e if x["z"] < z0p - 0.2]; z_unten = max(unten, key=lambda x: x["laenge"])["z"] if unten else z0p - 0.5
        oben = [x for x in hz_e if x["z"] > z1p + 0.2]; z_oben = min(oben, key=lambda x: abs(x["z"] - z1p - 0.6))["z"] if oben else z1p + 0.5
        kand = [x for x in hz_e if z0p + 0.4 < x["z"] < z1p - 0.4]; z_kaem_e = max(kand, key=lambda x: x["laenge"])["z"] if kand else 0.5 * (z0p + z1p)
        kand = [x for x in hz_e if z1p - 0.5 < x["z"] < z1p + 0.2]; z_schul_e = max(kand, key=lambda x: x["laenge"])["z"] if kand else z1p
        e = {"mitte": mitte, "tiefe": tief, "x_front": x_front, "x_wand": x_wand, "neigung_schraeg": float(math.degrees(math.atan(abs(k)))), "pfosten": h, "lichtbreite": float(np.median(la)),
             "z_unten": z_unten, "z_sohl": z0p, "z_kaempfer": z_kaem_e, "z_schulter": z_schul_e, "z_oben": z_oben, "horizontale": hz_e}
        L_(f"Erker along {mitte:.2f}: {len(h)} Pfosten, Tiefe {tief:.2f} m, Frontflaeche +-{x_front:.2f}, Wandanschluss +-{x_wand:.2f} (Schraege {e['neigung_schraeg']:.0f} Grad), Lichtbreite {e['lichtbreite']:.2f}; z unten {z_unten:.2f} / Sohl {z0p:.2f} / Kaempfer {z_kaem_e:.2f} / Schulter {z_schul_e:.2f} / oben {z_oben:.2f}")
        erker.append(e)
    # Spiegelregel: gemeinsame Masse = Median; Erkermitte-Achse
    if len(erker) >= 2:
        achse = 0.5 * (erker[0]["mitte"] + erker[-1]["mitte"]); L_(f"Symmetrieachse aus beiden Erkern: along {achse:.2f}; Fenstergruppen-Mitte {mitten.mean():.2f} (Differenz {mitten.mean() - achse:+.2f} m); Gebaeudeenden {A['along_w']:.2f}/{A['along_e']:.2f} (Mitte {(A['along_w'] + A['along_e']) / 2:.2f})")
    else: achse = mitten.mean() if len(mitten) else None
    gem = {}
    for k in ("tiefe", "x_front", "x_wand", "lichtbreite", "z_unten", "z_sohl", "z_kaempfer", "z_schulter", "z_oben"):
        gem[k] = float(np.median([e[k] for e in erker])) if erker else None
    for e in erker: e["abweichung"] = {k: e[k] - gem[k] for k in gem}
    # Erker-Fotobeleg: Frontflaeche-Pfosten + Sohl-/Oberkante
    if erker:
        segs = []; idx = []
        for ei, e in enumerate(erker):
            for s in (-1, 1):
                segs.append([welt(u, n, e["mitte"] + s * gem["x_front"], of + gem["tiefe"], gem["z_sohl"]), welt(u, n, e["mitte"] + s * gem["x_front"], of + gem["tiefe"], gem["z_schulter"]), 1, 1.0]); idx.append(ei)
            for z_ in (gem["z_unten"], gem["z_oben"]): segs.append([welt(u, n, e["mitte"] - gem["x_front"], of + gem["tiefe"], z_), welt(u, n, e["mitte"] + gem["x_front"], of + gem["tiefe"], z_), 1, 1.0]); idx.append(ei)
        ja, nein, fj = fotobeleg(segs, KAM, stabildir); idx = np.array(idx)
        for ei, e in enumerate(erker):
            s = idx == ei; e["fotos_ja_min"] = int(ja[s].min()); e["fotos_ja_median"] = float(np.median(ja[s])); e["belegt"] = bool(ja[s].min() >= 3 and np.median(ja[s]) >= np.median(nein[s]))
            L_(f"  Erker {ei} Fotobeleg: ja min {e['fotos_ja_min']} median {e['fotos_ja_median']:.0f} -> {'BELEGT' if e['belegt'] else 'NICHT belegt'}; Abweichung vom Median: " + ", ".join(f"{k} {v:+.2f}" for k, v in e["abweichung"].items()))
    # Helme
    helme = d.get("helme", []) or (json.load(open(helme_json)).get("helme", []) if helme_json and os.path.exists(helme_json) else [])
    hl = []
    for h in helme:
        p = np.array([h["cx"], h["cy"], 0]); hl.append({"along": float(p @ u), "off": float(p @ n), "z_fuss": h["z_fuss"], "z_spitze": h["z_spitze"], "r_fuss": h["r_fuss"], "phi": h.get("phi", 0), "sektoren": int(h.get("sektoren", 8)), "quelle": "Wolkenfit helme"})
    annahmen = []
    for e in erker:
        if not any(abs(h["along"] - e["mitte"]) < 1.5 for h in hl) and hl and achse is not None:
            h0 = min(hl, key=lambda h: abs(h["along"] - (2 * achse - e["mitte"])))
            if abs(h0["along"] - (2 * achse - e["mitte"])) < 1.5:
                sp = dict(h0); sp["along"] = 2 * achse - h0["along"]; sp["quelle"] = f"ANNAHME: Spiegel des Helms along {h0['along']:.2f} an der Erkerachse {achse:.2f}"
                # Fotobeleg der gespiegelten Helmkanten (4 Gratlinien)
                segs = [[welt(u, n, sp["along"] + sp["r_fuss"] * math.cos(a), sp["off"] + sp["r_fuss"] * math.sin(a), sp["z_fuss"]), welt(u, n, sp["along"], sp["off"], sp["z_spitze"]), 1, 1.0] for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
                ja, nein, fj = fotobeleg(segs, KAM, stabildir, dmax=80.0); sp["fotos_ja"] = ja.tolist(); sp["fotos_nein"] = nein.tolist(); sp["belegt"] = bool(np.median(ja) >= 3)
                L_(f"Gespiegelter Helm along {sp['along']:.2f}: Gratkanten Fotos ja {ja.tolist()} nein {nein.tolist()} -> {'fotobelegt' if sp['belegt'] else 'nur ANNAHME'}")
                hl.append(sp); annahmen.append(sp["quelle"])
    annahmen += [f"ANNAHME: Oeffnungstiefe {T_OEFF} m, Rahmentiefe {T_RAHM} m, Stege 2 cm hinter der Flaeche", "ANNAHME: Erker-Untersicht = Trichter vom Erkerpolygon (z_unten) zur Wandlinie auf Balkonunterkante",
                 "ANNAHME: Erkerschaft zwischen Erkeroberkante und Helmfuss = Huelle Polygon -> Helmkreis", "ANNAHME: Lichter je Gruppe = 3, wenn Aussenpfosten fehlen"]
    aus = {"quelle": seg_json, "rohkoerper": roh_json, "u": u.tolist(), "n": n.tolist(), "off_front": of, "z_balkon": zb, "z_traufe": zt, "achse": achse, "fenster": fenster, "erker": erker, "erker_gemeinsam": gem,
           "helme": hl, "z_balkon_unten": vs[0].get("z_min_voll", vs[0]["z_min"]) if vs else zb - 2.0, "annahmen": annahmen, "log": log}
    json.dump(aus, open(aus_json, "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)); print("->", aus_json)


# ----------------------------------------------------------------------------- Bauen
def profil_z(prof, dx, z_schul, z_scheit, w_licht):
    """Bekroenungshoehe ueber |dx| aus dem Gitterprofil (Interpolation), begrenzt auf [Schulter, Scheitel]."""
    if not prof: return z_schul + (z_scheit - z_schul) * max(0, 1 - dx / (0.5 * w_licht))
    xs = np.array([p[0] for p in prof]); zs = np.array([p[1] for p in prof]); return float(np.clip(np.interp(dx, xs, zs), z_schul, z_scheit))


def fenstergruppe(m3, mitte, F, basis_z, tief_face, n_licht, w_licht, profil=True, z_sohl=None, z_kaem=None, z_schul=None, z_scheit=None):
    """Oeffnungen (Abzug) und Stege (Zugabe) einer Fenstergruppe in der lokalen Flaeche: x entlang der Flaeche (Mitte 0), y = Tiefe (0 = Flaeche, negativ = in die Wand), z.
    Liefert (abzuege, stege) als Manifold-Listen in lokalen Koordinaten (x, y, z)."""
    z_sohl = F["z_sohl"] if z_sohl is None else z_sohl; z_kaem = F["z_kaempfer"] if z_kaem is None else z_kaem; z_schul = F["z_schulter"] if z_schul is None else z_schul; z_scheit = F["z_scheitel"] if z_scheit is None else z_scheit
    b = F["b_rahmen"]; abz = []; stege = []
    for i in range(n_licht):
        x0 = (i - n_licht / 2) * w_licht + b / 2; x1 = x0 + w_licht - b; xm = 0.5 * (x0 + x1)
        # Oberkante: Bekroenungsprofil ueber |x| (Gruppenmitte), fuer Erker/2 Lichter: Schulter mit kleinem Vorhangbogen
        xs = np.linspace(x0, x1, 9);
        if profil: top = [profil_z(F["profil"], abs(x), z_schul, z_scheit, w_licht) - b for x in xs]
        else: top = [z_schul - b + 0.25 * (1 - abs(x - xm) / (0.5 * (x1 - x0))) ** 2 for x in xs]   # ANNAHME Erker: kleiner Vorhangbogen 25 cm
        poly = [[x0, z_sohl + b], [x1, z_sohl + b]] + [[x, z] for x, z in zip(xs[::-1], top[::-1])]
        o = m3.Manifold.extrude(cs(poly), T_OEFF + 0.05).transform(np.array([[1, 0, 0, 0], [0, 0, 1, -T_OEFF], [0, 1, 0, 0]], float))   # y von -T_OEFF bis +0.05
        abz.append(o)
        # Stege: Mittelpfosten (vertikal) und Kaempfer (horizontal), 2 cm hinter der Flaeche, bis zur Oeffnungsrueckwand (ueberlappend)
        ty0, ty1 = -T_OEFF - ABST, -ABST
        stege.append(m3.Manifold.cube([b, ty1 - ty0, max(top) - z_sohl + ABST]).translate([xm - b / 2, ty0, z_sohl]))   # 2 cm ueber den Scheitel in die Wand (kein Punkt auf dem Scheitel)
        stege.append(m3.Manifold.cube([x1 - x0 + 2 * ABST, ty1 - ty0, b]).translate([x0 - ABST, ty0, z_kaem - b / 2]))
    return abz, stege


def bauen(aus_json, roh_stl, out_stl):
    import manifold3d as m3, trimesh
    D = json.load(open(aus_json)); u = np.array(D["u"]); n = np.array(D["n"]); of = D["off_front"]; F = D["fenster"]; log = []
    L_ = lambda s: (print(s), log.append(s))
    tm = trimesh.load(roh_stl, process=True); tm.merge_vertices()
    Mw = np.c_[u, n, [0, 0, 1], [0, 0, 0]]; Mi = np.linalg.inv(np.r_[Mw, [[0, 0, 0, 1]]])[:3]
    roh = m3.Manifold(m3.Mesh(vert_properties=np.asarray(tm.vertices, np.float32), tri_verts=np.asarray(tm.faces, np.uint32))).transform(Mi)   # in (along, off, z)
    L_(f"Rohkoerper: {len(tm.faces)} Dreiecke, Volumen {tm.volume:.1f}, Status {roh.status()}")
    sgn = 1.0  # Front-Normale zeigt zu groesserem Offset (Erker liegen bei off > of)
    abz_all = []; add_all = []; belege = []
    # --- Fenstergruppen Hauptfassade: lokale Flaeche x=along-mitte, y=off-of (aussen positiv), z
    gr = [g for g in F["gruppen"] if g["belegt"]]; n_nicht = len(F["gruppen"]) - len(gr)
    for g in gr:
        abz, st = fenstergruppe(m3, g["mitte"], F, 0, 0, F["n_licht"], F["w_licht"])
        T = np.array([[1, 0, 0, g["mitte"]], [0, 1, 0, of], [0, 0, 1, 0]], float)
        abz_all += [a.transform(T) for a in abz]; add_all += [s.transform(T) for s in st]
    belege.append({"element": "Fenstergruppen Hauptfassade", "quelle": f"{len(gr)} Gruppen x {F['n_licht']} Lichter aus Gitter-Pfostenpaaren, fotobelegt (>= 3 Fotos); {n_nicht} Gruppen ohne Beleg weggelassen"})
    L_(f"Fenster: {len(gr)} Gruppen x {F['n_licht']} Lichter gebaut ({n_nicht} ohne Fotobeleg weggelassen)")
    # --- Erker
    G = D["erker_gemeinsam"]; erker_teile = []
    for e in D["erker"]:
        c = e["mitte"]; t = G["tiefe"]; xf = G["x_front"]; xw = G["x_wand"]
        # Polygon im Grundriss (x relativ Mitte, y = vor der Front): Wand (-xw,0) -> (-xf,t) -> (xf,t) -> (xw,0), hinten in die Wand (y = -0.3)
        poly = [[-xw, -0.3], [-xw, -ABST], [-xf, t], [xf, t], [xw, -ABST], [xw, -0.3]]   # Wandanschluss 2 cm IN der Wand (keine Kante auf der Frontflaeche)
        koerper = m3.Manifold.extrude(cs(poly), G["z_oben"] - G["z_unten"]).translate([0, 0, G["z_unten"]])
        # Untersicht: Huelle Polygon(z_unten) -> Wandlinie (z_balkon_unten)
        zu = D["z_balkon_unten"] - 0.3   # ANNAHME: Trichterspitze 30 cm unter der Balkonunterkante (keine koplanare Flaeche zum Balkonkasten)
        sx = (xw - ABST) / xw; pin = [[x * sx, y - ABST] for x, y in poly[1:5]]   # Polygon 2 cm nach innen: Huellen-Seitenflaechen nicht koplanar mit dem Erkerkoerper
        pts_u = [[x, y, G["z_unten"] + 0.05] for x, y in pin] + [[-xw * sx, -0.3 + ABST, G["z_unten"] + 0.05], [xw * sx, -0.3 + ABST, G["z_unten"] + 0.05], [-0.4, -0.3, zu], [0.4, -0.3, zu], [-0.4, 0.0, zu], [0.4, 0.0, zu]]
        unters = m3.Manifold.hull_points(pts_u)
        # Dachring (Gesims) an der Oberkante: Polygon um b_rahmen vergroessert, Hoehe 0,25 m (ANNAHME)
        b = F["b_rahmen"]; polyr = [[-xw - b, -0.3], [-xw - b, 0], [-xf - b * 0.5, t + b], [xf + b * 0.5, t + b], [xw + b, 0], [xw + b, -0.3]]
        ring = m3.Manifold.extrude(cs(polyr), 0.25 + ABST).translate([0, 0, G["z_oben"] - 0.25])
        teile = [koerper, unters, ring]
        # Schaft zum Helm: Huelle Polygon(z_oben) -> Helmkreis(z_fuss)
        hm = [h for h in D["helme"] if abs(h["along"] - c) < 1.5]
        if hm:
            h = hm[0]; k = h["sektoren"] if h["sektoren"] <= 16 else 8; ang = np.linspace(0, 2 * math.pi, k, endpoint=False) + h["phi"]
            kreis = [[h["along"] - c + 0.97 * h["r_fuss"] * math.cos(a), h["off"] - of + 0.97 * h["r_fuss"] * math.sin(a), h["z_fuss"] + 0.10] for a in ang]   # Schaftkopf 10 cm im Helm, 3 % kleiner (innerhalb der Pyramide)
            schaft = m3.Manifold.hull_points([[x, y, G["z_oben"] - 0.05] for x, y in pin] + [[-xw * sx, -0.3 + ABST, G["z_oben"] - 0.05], [xw * sx, -0.3 + ABST, G["z_oben"] - 0.05]] + kreis)
            teile.append(schaft)
            if h["quelle"].startswith("ANNAHME"):   # gespiegelter Helm: Pyramide selbst bauen (der Wolken-Helm steckt schon im Rohkoerper)
                teile.append(m3.Manifold.cylinder(h["z_spitze"] - h["z_fuss"], h["r_fuss"], 0.0, k).rotate([0, 0, math.degrees(h["phi"])]).translate([h["along"] - c, h["off"] - of, h["z_fuss"]]))
        E = m3.Manifold.batch_boolean(teile, m3.OpType.Add)
        # Fensterkranz: je Flaeche 2 Lichter (Lichtbreite Erker); Flaechen: schraeg links, front, schraeg rechts
        flaechen = [((-xw, 0), (-xf, t)), ((-xf, t), (xf, t)), ((xf, t), (xw, 0))]
        Fe = dict(F); Fe["b_rahmen"] = F["b_rahmen"]
        for (xa, ya), (xb, yb) in flaechen:
            lng = math.hypot(xb - xa, yb - ya); n_l = max(1, int(round(lng / G["lichtbreite"]))); w_l = (lng - 2 * F["b_rahmen"]) / n_l
            abz, st = fenstergruppe(m3, 0, Fe, 0, 0, n_l, w_l, profil=False, z_sohl=G["z_sohl"], z_kaem=G["z_kaempfer"], z_schul=G["z_schulter"], z_scheit=G["z_schulter"] + 0.3)
            ex = np.array([xb - xa, yb - ya]) / lng; ey = np.array([ex[1], -ex[0]])   # Aussen-Normale (nach aussen bei CCW... hier nach +y gewuenscht)
            if ey[1] < 0 and abs(ey[1]) > 1e-6: ey = -ey
            if abs(ey[1]) < 1e-6 and ey[0] * (xa + xb) < 0: ey = -ey
            mx, my = 0.5 * (xa + xb), 0.5 * (ya + yb)
            T = np.array([[ex[0], ey[0], 0, mx], [ex[1], ey[1], 0, my], [0, 0, 1, 0]], float)
            E = E - m3.Manifold.batch_boolean([a.transform(T) for a in abz], m3.OpType.Add) + m3.Manifold.batch_boolean([s.transform(T) for s in st], m3.OpType.Add)
        erker_teile.append(E.translate([c, of, 0]))
        L_(f"Erker along {c:.2f}: Polygon Wand +-{xw:.2f}, Front +-{xf:.2f}, Tiefe {t:.2f}, z {G['z_unten']:.2f}..{G['z_oben']:.2f}, Helm {'ja' if hm else 'nein'}, Fensterkranz {len(flaechen)} Flaechen")
    belege.append({"element": "Erker", "quelle": f"{len(D['erker'])} Erker aus 2D-Pfostenclustern vor der Front (Spiegelregel: Median-Masse), Hoehen aus horizontalen Erkerkanten"})
    # --- Zusammenbau
    k = roh
    if abz_all: k = k - m3.Manifold.batch_boolean(abz_all, m3.OpType.Add)
    if add_all: k = k + m3.Manifold.batch_boolean(add_all, m3.OpType.Add)
    if erker_teile: k = k + m3.Manifold.batch_boolean(erker_teile, m3.OpType.Add)
    k = k.transform(Mw)
    me = k.to_mesh(); V = np.asarray(me.vert_properties)[:, :3]; Fc = np.asarray(me.tri_verts); tm2 = trimesh.Trimesh(V, Fc, process=False)   # indiziertes Netz direkt aus manifold (keine Entfernung degenerierter Dreiecke: die halten die Topologie)
    tm2.export(out_stl); tm2.export(out_stl.replace(".stl", ".ply")); th = tm2.copy(); th.apply_scale(H0); th.export(out_stl.replace(".stl", "_h0.stl"))
    L_(f"Export {out_stl}: {len(Fc)} Dreiecke, wasserdicht={tm2.is_watertight}, Volumen {tm2.volume:.1f} m^3, Koerper {len(tm2.split(only_watertight=False))}; H0 BBox mm {np.round(th.extents, 1).tolist()}")
    D["bau"] = {"belege": belege, "log": log, "wasserdicht": bool(tm2.is_watertight), "volumen_m3": float(tm2.volume), "dreiecke": int(len(Fc)), "stl": out_stl}
    json.dump(D, open(aus_json, "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


# ----------------------------------------------------------------------------- Pruefen
def pruefen(stl, aus_json, wolke, kam_json, bilddir, auditdir):
    import trimesh, cv2, subprocess
    from gpu_knn import min_abstand
    os.makedirs(auditdir, exist_ok=True); D = json.load(open(aus_json)); u = np.array(D["u"]); n = np.array(D["n"]); of = D["off_front"]
    ply = stl.replace(".stl", ".ply"); tm = trimesh.load(ply if os.path.exists(ply) else stl, process=False); tm.merge_vertices()
    tms = trimesh.load(stl, process=False); tms.merge_vertices()
    erg = {"wasserdicht": bool(tm.is_watertight), "wasserdicht_stl_roundtrip": bool(tms.is_watertight), "volumen_m3": float(tm.volume), "dreiecke": int(len(tm.faces)), "koerper": len(tm.split(only_watertight=False)), "euler": int(tm.euler_number)}
    P = np.load(wolke)["P"].astype(np.float32); S, _ = trimesh.sample.sample_surface(tm, 3_000_000); S = np.asarray(S, np.float32)
    dP = min_abstand(P, S); dP = np.asarray(dP.cpu() if hasattr(dP, "cpu") else dP)
    erg["wolke_naeher_20cm_gesamt"] = float((dP < 0.2).mean()); erg["wolke_median"] = float(np.median(dP)); baender = []
    for z0 in np.arange(math.floor(P[:, 2].min()), math.ceil(P[:, 2].max()), 2.0):
        m = (P[:, 2] >= z0) & (P[:, 2] < z0 + 2)
        if m.sum() < 100: continue
        baender.append({"z": [float(z0), float(z0 + 2)], "n": int(m.sum()), "lt20": float((dP[m] < 0.2).mean()), "lt50": float((dP[m] < 0.5).mean()), "median": float(np.median(dP[m]))})
    erg["hoehenbaender"] = baender
    # Netzkanten -> Segmente, Overlay
    adj_ang = tm.face_adjacency_angles; kant = tm.face_adjacency_edges[adj_ang > math.radians(30)]
    seg = [[tm.vertices[a].tolist(), tm.vertices[b].tolist(), 1, 1.0] for a, b in kant]; segp = stl.replace(".stl", "_kanten.json"); json.dump({"segmente": seg}, open(segp, "w")); erg["netzkanten"] = len(seg)
    kam = json.load(open(kam_json)); V = tm.vertices; F = tm.faces
    def proj(k, X):
        sc_ = 1.0; Rk = np.array(k["Rn"]); tk = np.array(k["tn"]); Xc = X @ Rk.T + tk; z = Xc[:, 2]; x = Xc[:, 0] / np.maximum(z, 0.1); y = Xc[:, 1] / np.maximum(z, 0.1)
        f1 = 1 + k["params"][3] * (x * x + y * y); return np.c_[(k["f"] * x * f1 + k["cx"]), (k["f"] * y * f1 + k["cy"])], z
    def render_kamera(foto, roi=None, name=None):
        """Modell aus der Fotokamera gerendert (Painter), daneben das Foto, gleicher Ausschnitt; Overlay Kanten."""
        k = kam[foto]; im = cv2.imread(os.path.join(bilddir, foto), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); sc = im.shape[1] / k["W"]
        P2, z = proj(k, V); P2 = P2 * sc; tri = V[F]; nn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nn /= (np.linalg.norm(nn, axis=1) + 1e-9)[:, None]
        rend = np.full_like(im, 255); zt = z[F].mean(1); ok = (z[F] > 0.5).all(1)
        licht = np.array([0.3, 0.5, 0.8])
        for t in np.argsort(-zt):
            if not ok[t]: continue
            c = int(60 + 160 * abs(float(nn[t] @ licht))); cv2.fillConvexPoly(rend, P2[F[t]].astype(np.int32), (c, c + 15, c + 25))
        ov = im.copy()
        for a, b in kant:
            pa, pb = P2[a], P2[b]
            if z[a] > 1 and z[b] > 1: cv2.line(ov, tuple(pa.astype(int)), tuple(pb.astype(int)), (0, 220, 255), 3, cv2.LINE_AA)
        if roi: x0, y0, x1, y1 = roi; im, rend, ov = im[y0:y1, x0:x1], rend[y0:y1, x0:x1], ov[y0:y1, x0:x1]
        h = 900; f_ = h / im.shape[0]; out = np.hstack([cv2.resize(im, None, fx=f_, fy=f_), cv2.resize(rend, None, fx=f_, fy=f_), cv2.resize(ov, None, fx=f_, fy=f_)])
        fn = os.path.join(auditdir, f"vergleich_{name or os.path.splitext(foto)[0]}.jpg"); cv2.imwrite(fn, out); return fn
    erg["vergleiche"] = []
    for foto in ("ip_IMG_6120.jpg", "an_handy_2026-11-06_c_handy_c_12.jpg", "nu_9e1944dc-image.jpg", "ip_IMG_6261.jpg"):
        if foto in kam and os.path.exists(os.path.join(bilddir, foto)):
            try: erg["vergleiche"].append(render_kamera(foto))
            except Exception as ex: erg["vergleiche"].append(f"FEHLER {foto}: {ex}")
    # Erker-Ausschnitt: ROI um den Erker in c_12 bzw. 9e1944 ueber die Projektion der Erkermitte
    for foto in ("an_handy_2026-11-06_c_handy_c_12.jpg", "nu_9e1944dc-image.jpg"):
        if foto not in kam or not D["erker"]: continue
        k = kam[foto]; im_shape = cv2.imread(os.path.join(bilddir, foto), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION).shape; sc = im_shape[1] / k["W"]
        for ei, e in enumerate(D["erker"]):
            G = D["erker_gemeinsam"]; X = np.array([welt(u, n, e["mitte"], of + G["tiefe"], 0.5 * (G["z_unten"] + G["z_oben"]))]); p2, z = proj(k, X); p2 = p2[0] * sc
            if z[0] <= 0: continue
            r = int(3.0 * k["f"] * sc / z[0]); x0, y0 = int(max(p2[0] - r, 0)), int(max(p2[1] - r * 1.6, 0)); x1, y1 = int(min(p2[0] + r, im_shape[1])), int(min(p2[1] + r * 1.2, im_shape[0]))
            if x1 - x0 > 50 and y1 - y0 > 50: erg["vergleiche"].append(render_kamera(foto, (x0, y0, x1, y1), f"erker{ei}_{os.path.splitext(foto)[0]}"))
    for foto in ("ip_IMG_6261.jpg", "ip_IMG_6120.jpg"):
        ov = os.path.join(auditdir, f"overlay_{os.path.splitext(foto)[0]}.jpg")
        r = subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gitter_overlay.py"), kam_json, os.path.join(bilddir, foto), segp, ov], capture_output=True, text=True)
        erg.setdefault("overlays", []).append(ov if r.returncode == 0 else f"FEHLER {r.stderr[-300:]}")
    # orthografische Renders vorn/schraeg
    Cm = V.mean(0)
    def render(dv, fn, W=1600):
        dv = dv / np.linalg.norm(dv); up = np.array([0, 0, 1.0]); r = np.cross(up, dv); r /= np.linalg.norm(r); up2 = np.cross(dv, r)
        X = (V - Cm) @ np.c_[r, up2, dv]; ext = max(np.abs(X[:, 0]).max(), np.abs(X[:, 1]).max()); sc = W * 0.46 / ext
        P2 = np.c_[X[:, 0] * sc + W / 2, -X[:, 1] * sc + W * 0.5]; tri = X[F]; nn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nn /= (np.linalg.norm(nn, axis=1) + 1e-9)[:, None]
        lam = 0.3 + 0.7 * np.clip(np.abs(nn @ np.array([0.3, 0.5, 0.8])), 0, 1); zt = tri[:, :, 2].mean(1); im = np.full((W, W, 3), 255, np.uint8)
        for t in np.argsort(zt):
            c = int(200 * lam[t]); cv2.fillConvexPoly(im, P2[F[t]].astype(np.int32), (c, c + 20, c + 30))
        cv2.imwrite(fn, im)
    render(n, os.path.join(auditdir, "render_vorn.jpg")); render(n + 0.8 * u + 0.6 * np.array([0, 0, 1.0]), os.path.join(auditdir, "render_schraeg.jpg"))
    render(n - 0.8 * u + 0.4 * np.array([0, 0, 1.0]), os.path.join(auditdir, "render_schraeg2.jpg"))
    json.dump(erg, open(stl.replace(".stl", "_pruefung.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in erg.items() if k != "hoehenbaender"}, indent=1))
    for b in baender: print(f"  z {b['z'][0]:5.1f}-{b['z'][1]:5.1f}: n={b['n']:8d} <20cm {b['lt20']:.2f} <50cm {b['lt50']:.2f} median {b['median']:.2f}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("analyse", "bauen", "pruefen"): print(__doc__); sys.exit(1)
    if a[0] == "analyse": analyse(a[1], a[2], a[3], a[4], a[5], a[a.index("--helme") + 1] if "--helme" in a else None)
    elif a[0] == "bauen": bauen(a[1], a[2], a[3])
    else: pruefen(a[1], a[2], a[3], a[4], a[5], a[6])
