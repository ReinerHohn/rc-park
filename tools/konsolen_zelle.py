#!/usr/bin/env python3
"""konsolen_zelle.py - Konsolenform aus der GEFALTETEN Musterzelle (wie baluster_fit: Profil aus der Faltung), danach Phase je Quelle, Entscheidregel.

Periode P = Pfeilerabstand / k (k = 3, Nutzerbefund '3 je Joch'). Faltung f = (along - x_ref) mod P ueber alle Konsolen der Platte.
  Wolke : Zone vor der Wand (> 8 cm) unter der Platte. Gefaltetes Histogramm (1 cm) -> Spitze = Phase, Halbwertsbreite = Breite;
          Profil: je z-Scheibe (5 cm) Ueberschuss der Konsolen-Spalte ueber die Hintergrund-Spalte (Zellmitte gegenueber) und Ausladung (90-%-Quantil 'off');
          Hoehe = unterste z-Scheibe mit signifikantem Ueberschuss (>= 3 sigma Poisson) in zusammenhaengender Folge von der Platte abwaerts.
  Fotos : Kantenstuetzung (Stabilitaetskarten) auf der Vorderflaeche des Wolkenprofils (je z die Ausladung), gefaltet ueber alle Fotos;
          Sweep Mitte c x Halbbreite b: Kontrast der beiden Seitenkanten gegen 0,1 m nach aussen -> Phase und Breite aus Fotokanten.
Entscheidregel (Nutzerentscheid): nie mitteln; die Quelle mit besseren Daten gewinnt (Datenmenge, Signifikanz MAD, Plateaubreite, Einigkeit je Instanz),
Suchgrenze disqualifiziert; Begruendung mit Zahlen.
  python -I konsolen_zelle.py KOERPER_v10.json KONSOLEN_v11.json KAM.json STABILDIR WOLKE [--k 3] [--bilder DIR --audit DIR] [--synth]
  -> schreibt KONSOLEN_v11.json: 'zelle' (Profil, Breite, Hoehe, Phase je Quelle, Entscheidung), 'konsolen' (Lagen, Quelle), 'beobachtungen_offen'."""
import sys, os, json, math, argparse
import numpy as np

DST = 0.01; KONTR = 0.10; TOL_M = 0.03


def mad_sig(prof):
    med = float(np.median(prof)); mad = float(np.median(np.abs(prof - med))); return (float(prof.max()) - med) / max(mad, 1e-9), med, mad


def glatt(x, k=3):
    if k <= 1: return x
    ker = np.ones(k) / k; xp = np.r_[x[-k:], x, x[:k]]; return np.convolve(xp, ker, "same")[k:-k]


def plateau_zirk(prof, b, frac=0.95):
    n = len(prof); thr = frac * prof[b] if prof[b] > 0 else prof[b]; lo = hi = b
    while lo > b - n + 1 and prof[(lo - 1) % n] >= thr: lo -= 1
    while hi < b + n - 1 and prof[(hi + 1) % n] >= thr: hi += 1
    return (hi - lo) * DST


def main():
    import torch, cv2
    ap = argparse.ArgumentParser(); ap.add_argument("k10"); ap.add_argument("kons"); ap.add_argument("kam"); ap.add_argument("stabil"); ap.add_argument("wolke")
    ap.add_argument("--k", type=int, default=3); ap.add_argument("--bilder"); ap.add_argument("--audit"); ap.add_argument("--fotos", default="ip_IMG_6120.jpg,ip_IMG_6261.jpg")
    ap.add_argument("--synth", type=float, default=None, help="Beweistest: Wolke + Fotos um diesen Phasenversatz (m) verschieben -> Phase muss um genau diesen Betrag wandern")
    ap.add_argument("--nicht_schreiben", action="store_true"); ap.add_argument("--dmax", type=float, default=45.0)
    a = ap.parse_args(); dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cuda": torch.cuda.set_per_process_memory_fraction(min(1.0, 2000 / (torch.cuda.get_device_properties(0).total_memory / 2**20)))
    D = json.load(open(a.k10)); u = np.array(D["u"]); n = np.array(D["n"]); of = D["off_front"]; pl = D["balkon"]["platte"]; zp0 = pl["z0"]; a0, a1 = pl["along"]; tiefe = pl["tiefe"]
    K = json.load(open(a.kons)); sp = K["pfeilerabstand"]; P = sp / a.k; x_ref = a0; nb = int(round(P / DST)); fgr = np.arange(nb) * DST
    log = []; L_ = lambda s: (print(s, flush=True), log.append(s))
    Wl = np.load(a.wolke, mmap_mode="r"); Pw = np.asarray((Wl["P"] if hasattr(Wl, "files") else Wl)[:, :3], dtype=np.float64)
    al = Pw @ u; off = Pw @ n - of; z = Pw[:, 2]; sh = a.synth or 0.0
    m = (al > a0 + 0.1) & (al < a1 - 0.1) & (off > 0.08) & (off < tiefe + 0.1) & (z > zp0 - 1.8) & (z < zp0 + 0.02)
    al, off, z = al[m] + sh, off[m], z[m]
    L_(f"Periode {P:.3f} (Pfeilerabstand {sp:.3f} / {a.k}); Zone along {a0:.2f}..{a1:.2f}, z {zp0 - 1.8:.2f}..{zp0:.2f}, vor der Wand 0,08..{tiefe + 0.1:.2f}: {m.sum()} Wolkenpunkte" + (f"; SYNTH Versatz {sh:+.2f} m" if a.synth else ""))
    # ---------------- Wolke: Instanzen EINZELN (ungefaltet) - Bloecke im Histogramm entlang der Front (5 cm, Kernband 0,05..0,6 m unter der Platte, 0,15..1,0 vor der Wand)
    mk_ = (off > 0.15) & (off < 1.0) & (z > zp0 - 0.6) & (z < zp0 - 0.05); hb = np.bincount(((al[mk_] - a0) / 0.05).astype(int), minlength=int((a1 - a0) / 0.05) + 1).astype(float)
    medb = float(np.median(hb)); madb = float(np.median(np.abs(hb - medb))) or 1.0; thr_b = medb + 10 * madb; on = hb > thr_b; bloecke = []; i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j + 1 < len(on) and (on[j + 1] or (j + 2 < len(on) and on[j + 2])): j += 1
            if (j - i + 1) * 0.05 >= 0.2: bloecke.append({"links": float(a0 + i * 0.05), "rechts": float(a0 + (j + 1) * 0.05), "mitte": float(a0 + (i + j + 1) * 0.025), "breite": float((j - i + 1) * 0.05), "punkte": int(hb[i:j + 1].sum())})
            i = j + 1
        else: i += 1
    ab = np.diff([b["mitte"] for b in bloecke])
    L_(f"Wolke einzeln: {len(bloecke)} Bloecke (Schwelle Median+10 MAD = {thr_b:.0f} Pkt/5 cm), Mitten {[round(b['mitte'], 2) for b in bloecke]}, Breiten {[round(b['breite'], 2) for b in bloecke]}, Abstaende {np.round(ab, 2).tolist()} (Mittel {ab.mean() if len(ab) else 0:.2f}, Periode-Annahme {P:.3f})")
    # ---------------- Wolke: gefaltetes Histogramm -> Phase, Breite
    fw = np.mod(al - x_ref, P); h = np.bincount(np.minimum((fw / DST).astype(int), nb - 1), minlength=nb).astype(float); hs = glatt(h, 5)
    bw = int(np.argmax(hs)); sig_w, med_w, mad_w = mad_sig(hs); halb = med_w + 0.5 * (hs[bw] - med_w); lo = hi = bw
    while hs[(lo - 1) % nb] >= halb and lo > bw - nb // 2: lo -= 1
    while hs[(hi + 1) % nb] >= halb and hi < bw + nb // 2: hi += 1
    breite_w = (hi - lo + 1) * DST; ph_w = float(fgr[bw]); pl_w = plateau_zirk(hs, bw)
    # je Instanz: Spitze im eigenen Fenster +-0,4 m
    J0 = int(math.floor((a0 - x_ref) / P)); J1 = int(math.ceil((a1 - x_ref) / P)); je_w = []
    for j in range(J0, J1 + 1):
        c = x_ref + ph_w + j * P
        if c < a0 + 0.3 or c > a1 - 0.3: continue
        mm = np.abs(al - c) <= 0.4; hh = np.bincount(((al[mm] - c + 0.4) / DST).astype(int), minlength=81)[:81].astype(float); hh = glatt(hh, 5)
        je_w.append({"along": float(c), "punkte": int(mm.sum()), "versatz": float(np.argmax(hh) * DST - 0.4) if mm.sum() else None, "genug": bool(mm.sum() >= 30)})
    vs = np.array([e["versatz"] for e in je_w if e["versatz"] is not None]); streu_w = float(np.median(np.abs(vs - np.median(vs)))) if len(vs) else 9.0
    rand_w = breite_w >= P / 2
    L_(f"Wolke: Phase {ph_w:.2f} ({x_ref + ph_w:.2f} abs.), Spitze {sig_w:.1f} MAD, Halbwertsbreite {breite_w:.2f} m, Plateau 95 % {pl_w:.2f} m, je Instanz Versatz {np.round(vs, 2).tolist()} (MAD {streu_w:.2f})")
    # ---------------- Wolke: Profil Ausladung ueber Hoehe (Spalte Konsole vs Spalte gegenueber)
    if bloecke:   # Zelle an den einzeln gefundenen Instanzen ausrichten (Periode nicht konstant), Hintergrund = Luecken > 0,3 m neben jedem Block
        dist_b = np.min([np.maximum(np.abs(al - b["mitte"]) - b["breite"] / 2, 0) for b in bloecke], axis=0); kon = dist_b <= 0; hint = dist_b > 0.3
    else:
        df = np.abs(((fw - ph_w + P / 2) % P) - P / 2); kon = df <= max(breite_w / 2, 0.1); hint = df >= P / 2 - max(breite_w / 2, 0.1)
    lk = sum(b["breite"] for b in bloecke) if bloecke else 1.0; lh = max(1e-6, (a1 - a0) - sum(b["breite"] + 0.6 for b in bloecke)) if bloecke else 1.0   # Laengen fuer die Dichte-Normierung
    zb = np.arange(zp0 - 1.8, zp0 + 1e-6, 0.05); prof = []
    for z0_ in zb[:-1]:
        mk = kon & (z >= z0_) & (z < z0_ + 0.05); mh = hint & (z >= z0_) & (z < z0_ + 0.05); nk, nh = int(mk.sum()), int(mh.sum())
        nhs = nh * lk / lh; ex = nk - nhs; sigp = ex / math.sqrt(nk + nhs * lk / lh + 1)   # Hintergrund auf die Konsolen-Laenge skaliert
        d90 = float(np.quantile(off[mk], 0.9)) if nk >= 10 else None; dh = float(np.quantile(off[mh], 0.9)) if nh >= 10 else None
        prof.append({"z": float(z0_ + 0.025), "n_konsole": nk, "n_hinter": nh, "sigma": float(sigp), "ausladung_90": d90, "ausladung_hinter_90": dh})
    sigs = [p_["sigma"] for p_ in prof]; top = len(prof) - 1
    while top >= 0 and sigs[top] < 3: top -= 1        # Plattenunterseite selbst kann gleichmaessig sein -> oberste signifikante Scheibe
    bot = top
    while bot - 1 >= 0 and sigs[bot - 1] >= 3: bot -= 1
    if top < 0: hoehe_w = None; L_("Wolke: kein signifikantes Konsolenprofil")
    else:
        hoehe_w = float(zp0 - (prof[bot]["z"] - 0.025)); z_unten = prof[bot]["z"] - 0.025
        L_(f"Wolke-Profil: signifikant (>= 3 sigma) von z {z_unten:.2f} bis {prof[top]['z'] + 0.025:.2f} -> Hoehe unter Platte {hoehe_w:.2f} m; Ausladung (90 %) je 5 cm: " +
           ", ".join(f"{p_['z']:.2f}:{p_['ausladung_90']:.2f}" for p_ in prof[bot:top + 1] if p_["ausladung_90"] is not None))
    # ---------------- Fotos: Kantenstuetzung auf der Vorderflaeche des Wolkenprofils, gefaltet
    KAM = json.load(open(a.kam)); fs = []
    for f in sorted(KAM):
        if not os.path.exists(os.path.join(a.stabil, os.path.splitext(f)[0] + ".png")): continue
        C = np.array(KAM[f]["C"])
        if C @ n - of < 1.5 or C[2] > zp0 - 0.2 or np.min(np.linalg.norm(np.array([x * u + (of + 0.5) * n + np.array([0, 0, zp0 - 0.6]) for x in np.linspace(a0, a1, 9)]) - C, axis=1)) > a.dmax: continue
        fs.append(f)
    if hoehe_w is None: zs_ = np.arange(zp0 - 0.9, zp0 - 0.05, 0.05); dz_ = [0.3] * len(zs_)
    else:
        zs_ = np.array([p_["z"] for p_ in prof[bot:top + 1]]); dz_ = [p_["ausladung_90"] if p_["ausladung_90"] is not None else 0.3 for p_ in prof[bot:top + 1]]
    xs = np.arange(a0 + 0.3, a1 - 0.3, DST); X, Zi = np.meshgrid(xs, np.arange(len(zs_)), indexing="ij")
    Q = X[..., None] * u + (of + np.array(dz_)[Zi])[..., None] * n + np.array(zs_)[Zi][..., None] * np.array([0, 0, 1.0]); Q = torch.tensor(Q.reshape(-1, 3), device=dev, dtype=torch.float32)
    Hs = torch.zeros(len(xs), device=dev); Ns = torch.zeros(len(xs), device=dev); nf_inst = {}
    for f in fs:
        k = KAM[f]; V = torch.from_numpy(cv2.imread(os.path.join(a.stabil, os.path.splitext(f)[0] + ".png"), 0)).to(dev).float() / 255.0
        if a.synth: V = torch.roll(V, shifts=0, dims=1)   # Fotos werden ueber die 3D-Lage verschoben (Q unten), nicht im Bild
        sj = V.shape[1] / k["W"]; dist = float(np.linalg.norm(np.array(k["C"]) - (0.5 * (a0 + a1) * u + of * n + np.array([0, 0, zp0]))))
        rad = int(np.clip(round(TOL_M * k["f"] * sj / max(dist, 1.0)), 1, 5)); Vm = torch.nn.functional.max_pool2d(V[None, None], 2 * rad + 1, 1, rad)[0, 0]; Hh, Ww = Vm.shape
        Qs = Q - torch.tensor(sh * u, device=dev, dtype=torch.float32)   # SYNTH: Messgitter um -sh verschoben = Szene um +sh
        R = torch.tensor(k["Rn"], device=dev, dtype=torch.float32); t = torch.tensor(k["tn"], device=dev, dtype=torch.float32); Xc = Qs @ R.T + t
        zc = Xc[:, 2].clamp(min=0.3); x_ = Xc[:, 0] / zc; y_ = Xc[:, 1] / zc; f1 = 1 + k["params"][3] * (x_ * x_ + y_ * y_)
        uu = ((k["f"] * x_ * f1 + k["cx"]) * sj).round().long(); vv = ((k["f"] * y_ * f1 + k["cy"]) * sj).round().long()
        ok = (Xc[:, 2] > 1) & (uu >= 0) & (uu < Ww) & (vv >= 0) & (vv < Hh); hit = torch.zeros(len(Qs), device=dev); hit[ok] = Vm[vv[ok], uu[ok]]
        okc = ok.view(len(xs), len(zs_)).all(1); Hs += torch.where(okc, hit.view(len(xs), len(zs_)).mean(1), torch.zeros_like(Hs)); Ns += okc.float()
        cv_ = np.array(k["C"]); nf_inst[f] = (okc.cpu().numpy(), math.degrees(math.atan2(*(((cv_ - (0.5 * (a0 + a1) * u)) @ np.c_[u, n]).tolist()))))
    g = (Hs / Ns.clamp(min=1)).cpu().numpy(); fx = np.mod(xs - x_ref, P); gf = np.zeros(nb); gn = np.zeros(nb); ib = np.minimum((fx / DST).astype(int), nb - 1)
    np.add.at(gf, ib, g); np.add.at(gn, ib, 1); gf = gf / np.maximum(gn, 1)
    bgr = np.arange(0.05, 0.61, DST); dk = int(KONTR / DST); S = np.zeros((nb, len(bgr)))
    for bi, b in enumerate(bgr):
        ib_ = int(round(b / DST)); L = np.roll(gf, ib_); R_ = np.roll(gf, -ib_); Lo = np.roll(gf, ib_ + dk); Ro = np.roll(gf, -ib_ - dk)
        S[:, bi] = (L - Lo) + (R_ - Ro)        # S[c]: Kanten bei c-b und c+b gegen aussen
    c_f, b_f = np.unravel_index(np.argmax(S), S.shape); ph_f = float(fgr[c_f]); breite_f = float(2 * bgr[b_f]); sig_f, _, _ = mad_sig(S.max(1)); pl_f = plateau_zirk(S.max(1), c_f)
    rand_f = b_f in (0, len(bgr) - 1)
    je_f = []
    for j in range(J0, J1 + 1):
        c = x_ref + ph_f + j * P
        if c < a0 + 0.6 or c > a1 - 0.6: continue
        mm = np.abs(xs - c) <= 0.4 + bgr[b_f] + KONTR; sc = []
        for d in np.arange(-0.4, 0.401, DST):
            gl = lambda x_: np.interp(x_, xs, g); sc.append(gl(c + d - bgr[b_f]) - gl(c + d - bgr[b_f] - KONTR) + gl(c + d + bgr[b_f]) - gl(c + d + bgr[b_f] + KONTR))
        seh = [f for f, (okc, ang) in nf_inst.items() if okc[np.abs(xs - c) <= 0.2].all()]; ri = {(-1 if nf_inst[f][1] < -15 else (1 if nf_inst[f][1] > 15 else 0)) for f in seh}
        je_f.append({"along": float(c), "fotos": len(seh), "richtungen": sorted(ri), "versatz": float(np.arange(-0.4, 0.401, DST)[int(np.argmax(sc))]), "genug": bool(len(seh) >= 3 and len(ri) >= 2)})
    vf = np.array([e["versatz"] for e in je_f]); streu_f = float(np.median(np.abs(vf - np.median(vf)))) if len(vf) else 9.0
    L_(f"Fotos ({len(fs)}): Phase {ph_f:.2f} ({x_ref + ph_f:.2f} abs.), Breite (Kante-Kante) {breite_f:.2f} m, Spitze {sig_f:.1f} MAD, Plateau 95 % {pl_f:.2f} m, Grenze {rand_f}, je Instanz Versatz {np.round(vf, 2).tolist()} (MAD {streu_f:.2f})")
    # ---------------- Fotos je Instanz (an den Wolkenbloecken): Mitte +-0,3 m x Halbbreite 0,05..0,45 m, Kantenkontrast gegen aussen
    gl = lambda x_: np.interp(x_, xs, g); dgr = np.arange(-0.3, 0.301, DST); bgr2 = np.arange(0.05, 0.451, DST); inst = []
    for b in bloecke:
        Sb = np.array([[gl(b["mitte"] + d - bh) - gl(b["mitte"] + d - bh - KONTR) + gl(b["mitte"] + d + bh) - gl(b["mitte"] + d + bh + KONTR) for bh in bgr2] for d in dgr])
        di, bi_ = np.unravel_index(np.argmax(Sb), Sb.shape); sgb, _, _ = mad_sig(Sb.max(1)); rnd = di in (0, len(dgr) - 1) or bi_ in (0, len(bgr2) - 1)
        seh = [f for f, (okc, ang) in nf_inst.items() if okc[np.abs(xs - b["mitte"]) <= 0.2].all()]; ri = {(-1 if nf_inst[f][1] < -15 else (1 if nf_inst[f][1] > 15 else 0)) for f in seh}
        foto = {"mitte": float(b["mitte"] + dgr[di]), "breite": float(2 * bgr2[bi_]), "sig": float(sgb), "grenze": bool(rnd), "fotos": len(seh), "richtungen": sorted(ri)}
        foto["qualifiziert"] = bool(sgb >= 3 and not rnd and len(seh) >= 3 and len(ri) >= 2)
        wo = {"mitte": b["mitte"], "breite": b["breite"], "punkte": b["punkte"], "qualifiziert": bool(b["punkte"] >= 30)}
        # Entscheidregel je Instanz: Wolkenblock gilt als scharf (Schwelle Median+10 MAD); Foto gewinnt nur, wenn qualifiziert und Wolke nicht
        if wo["qualifiziert"]: win_i, gr_ = "wolke", f"Wolke qualifiziert ({b['punkte']} Punkte, Block ueber Median+10 MAD)"; 
        elif foto["qualifiziert"]: win_i, gr_ = "foto", f"nur Foto qualifiziert ({sgb:.1f} MAD, {len(seh)} Fotos)"
        else: win_i, gr_ = None, "beide blind"
        gr_ += f"; Foto: Mitte {foto['mitte']:.2f} ({foto['mitte'] - b['mitte']:+.2f}), Breite {foto['breite']:.2f}, {sgb:.1f} MAD, {len(seh)} Fotos aus {len(ri)} Richtungen{', GRENZE' if rnd else ''}"
        inst.append({"wolke": wo, "foto": foto, "gewinner": win_i, "begruendung": gr_})
        L_(f"  Instanz {b['mitte']:6.2f}: Wolke Breite {b['breite']:.2f} ({b['punkte']} Pkt) | Foto Mitte {foto['mitte']:.2f} ({foto['mitte'] - b['mitte']:+.2f}) Breite {foto['breite']:.2f} {sgb:.1f} MAD{' GRENZE' if rnd else ''} -> {win_i}")
    # ---------------- Entscheidung
    qw = {"quelle": "wolke", "phase": ph_w, "breite": breite_w, "sig": sig_w, "plateau": pl_w, "streu": streu_w, "genug": sum(e["genug"] for e in je_w), "n": len(je_w), "grenze": bool(rand_w)}
    qf = {"quelle": "foto", "phase": ph_f, "breite": breite_f, "sig": sig_f, "plateau": pl_f, "streu": streu_f, "genug": sum(e["genug"] for e in je_f), "n": len(je_f), "grenze": bool(rand_f)}
    for q in (qw, qf): q["qualifiziert"] = bool(q["sig"] >= 3 and q["genug"] >= 3 and not q["grenze"])
    txt = lambda q: f"{q['quelle']}: Phase {q['phase']:.2f}, Breite {q['breite']:.2f}, {q['sig']:.1f} MAD, Plateau {q['plateau']:.2f} m, Instanz-MAD {q['streu']:.2f} m, Daten {q['genug']}/{q['n']}{', GRENZE' if q['grenze'] else ''}"
    kand = sorted([q for q in (qw, qf) if q["qualifiziert"]], key=lambda q: (q["streu"], q["plateau"], -q["sig"]))
    dph = abs(((ph_w - ph_f) + P / 2) % P - P / 2)
    if kand:
        win = kand[0]; begr = f"{win['quelle']} gewinnt ({'einzige qualifizierte Quelle' if len(kand) == 1 else 'kleinere Instanzstreuung/Plateau, dann Signifikanz'}); Quellenabstand Phase {dph:.2f} m. " + txt(qw) + " | " + txt(qf)
    else:
        win = None; begr = "beide Quellen disqualifiziert -> Lage bleibt ANNAHME. " + txt(qw) + " | " + txt(qf)
    L_("ENTSCHEIDUNG Phase/Breite: " + begr)
    if a.synth:
        ok = win is not None and abs(((win["phase"] - (K.get("zelle", {}).get("phase_rel", win["phase"] - sh) + sh)) + P / 2) % P - P / 2) <= 0.03
        L_(f"SYNTH: erwartet Phase = echte Phase + {sh:+.2f}; Wolke {ph_w:.2f}, Foto {ph_f:.2f}" + (f" (echte Phase aus vorigem Lauf {K['zelle']['phase_rel']:.2f}) -> {'BESTANDEN' if ok else 'NICHT BESTANDEN'}" if "zelle" in K else " (kein vorheriger echter Lauf)"))
        json.dump({"synth": sh, "wolke": ph_w, "foto": ph_f, "log": log}, open(os.path.splitext(a.kons)[0] + "_zelle_synth.json", "w"), indent=1); return
    profil = [[p_["z"], p_["ausladung_90"]] for p_ in prof[bot:top + 1] if p_["ausladung_90"] is not None] if hoehe_w is not None else None
    zelle = {"periode": P, "k": a.k, "x_ref": x_ref, "phase_rel": (win or qw)["phase"], "phase_abs": x_ref + (win or qw)["phase"], "lage_quelle": f"{win['quelle']}_zelle" if win else "ANNAHME",
             "breite": (win or qw)["breite"], "breite_quelle": f"{win['quelle']}_zelle" if win else "ANNAHME", "hoehe": hoehe_w, "profil_ausladung": profil, "profil_quelle": "wolke_zelle (an den Instanzen ausgerichtet, 90-%-Quantil, >= 3 sigma gegen Lueckenhintergrund)",
             "wolke": qw, "foto": qf, "je_instanz_wolke": je_w, "je_instanz_foto": je_f, "begruendung": begr, "profil_roh": prof, "log": log}
    if a.nicht_schreiben: print(json.dumps({k_: v_ for k_, v_ in zelle.items() if k_ not in ("profil_roh", "log", "je_instanz_wolke", "je_instanz_foto")}, indent=1)); return
    zelle["instanzen"] = inst; zelle["periode_hinweis"] = (f"OFFENE BEOBACHTUNG: Konsolenabstaende einzeln {np.round(ab, 2).tolist()} (Mittel {ab.mean():.2f}) widersprechen der Periode Pfeilerabstand/{a.k} = {P:.3f}; Lagen daher je Instanz, nicht im Raster" if len(ab) else None)
    K["zelle"] = zelle
    if bloecke and hoehe_w is not None:
        if "konsolen_raster_gitter" not in K: K["konsolen_raster_gitter"] = K["konsolen"]
        # Breite getrennt entschieden: Foto misst die Vorderkanten direkt (Kontrast in MAD), der Wolkenblock nur die Ausdehnung ueber einer Dichteschwelle
        # (schwellenabhaengig, Seitenflaechen/Voluten eingeschlossen) -> Foto gewinnt die Breite, wenn qualifiziert; sonst Wolke
        for it in inst: it["breite_quelle"] = "foto" if it["foto"]["qualifiziert"] else "wolke"
        K["konsolen"] = [{"along": (it["wolke"] if it["gewinner"] != "foto" else it["foto"])["mitte"], "z0": float(zp0 - hoehe_w),
                          "breite": it[it["breite_quelle"]]["breite"], "breite_quelle": it["breite_quelle"], "profil": profil,
                          "status": f"{it['gewinner']}_instanz: {it['begruendung']}", "quelle": f"{it['gewinner']}_zelle" if it["gewinner"] else "ANNAHME"} for it in inst]
        K["periode"] = None; K["phase"] = None
        K.setdefault("beobachtungen_offen", []).append(zelle["periode_hinweis"])
    elif win and hoehe_w is not None:
        if "konsolen_raster_gitter" not in K: K["konsolen_raster_gitter"] = K["konsolen"]
        ph = x_ref + win["phase"]; j0 = math.ceil((a0 + 0.3 - ph) / P); j1 = math.floor((a1 - 0.3 - ph) / P)
        K["konsolen"] = [{"along": float(ph + j * P), "z0": float(zp0 - hoehe_w), "breite": zelle["breite"], "profil": profil, "status": f"{zelle['lage_quelle']} (Faltung, Begruendung in zelle)", "quelle": zelle["lage_quelle"]} for j in range(j0, j1 + 1)]
        K["periode"] = P; K["phase"] = ph
    json.dump(K, open(a.kons, "w"), indent=1); print("->", a.kons, len(K["konsolen"]), "Konsolen")
    if a.bilder and a.audit:   # Overlay mit Fehlerliste je Konsole (Versatz je Instanz aus Wolke und Fotos)
        os.makedirs(a.audit, exist_ok=True); alt = K.get("konsolen_raster_gitter", []); dvor = tiefe - 0.15
        def poly(x, w, zt, zb_, d_t, d_b): return np.array([p[0] * u + p[1] * n + np.array([0, 0, p[2]]) for p in [(x - w / 2, of + d_t, zt), (x + w / 2, of + d_t, zt), (x + w / 2, of + d_b, zb_), (x - w / 2, of + d_b, zb_)]])
        for f in a.fotos.split(","):
            if f not in KAM: continue
            k = KAM[f]; im = cv2.imread(os.path.join(a.bilder, f)); sj = im.shape[1] / k["W"]; L0 = im.copy(); L1 = im.copy(); uvs = []
            def pr(Q3):
                X3 = Q3 @ np.array(k["Rn"]).T + np.array(k["tn"])
                if (X3[:, 2] < 1).any(): return None
                xx = X3[:, 0] / X3[:, 2]; yy = X3[:, 1] / X3[:, 2]; f1 = 1 + k["params"][3] * (xx * xx + yy * yy); return np.c_[(k["f"] * xx * f1 + k["cx"]) * sj, (k["f"] * yy * f1 + k["cy"]) * sj]
            for kz in alt:
                uv = pr(poly(kz["along"], 0.45, zp0, kz["z0"], dvor, 0.15))
                if uv is not None: uvs.append(uv); cv2.polylines(L0, [uv.round().astype(np.int32)], True, (0, 0, 255), 2)
            for kz in K["konsolen"]:
                d_t = max(p_[1] for p_ in profil) if profil else 0.5; d_b = profil[0][1] if profil else 0.15
                uv = pr(poly(kz["along"], kz["breite"], zp0, kz["z0"], d_t, d_b))
                if uv is None: continue
                uvs.append(uv); cv2.polylines(L1, [uv.round().astype(np.int32)], True, (0, 255, 0), 2)
                it = next((it for it in zelle.get("instanzen", []) if abs(it["wolke"]["mitte"] - kz["along"]) < 0.01 or abs(it["foto"]["mitte"] - kz["along"]) < 0.01), None)
                lab = (f"F{it['foto']['mitte'] - it['wolke']['mitte']:+.2f} b{it['foto']['breite']:.2f}" + ("" if it["foto"]["qualifiziert"] else "?")) if it else "-"
                cv2.putText(L1, lab, tuple(uv[2].round().astype(int) + [-60, 30]), 0, 0.7, (0, 255, 0), 2)
            if not uvs: continue
            U = np.concatenate(uvs); x0, y0 = np.clip(U.min(0) - 120, 0, None).astype(int); x1, y1 = np.minimum(U.max(0) + 140, [im.shape[1], im.shape[0]]).astype(int)
            c0 = L0[y0:y1, x0:x1]; c1 = L1[y0:y1, x0:x1]; sc = min(1.0, 1400 / max(1, c0.shape[1])); c0 = cv2.resize(c0, None, fx=sc, fy=sc); c1 = cv2.resize(c1, None, fx=sc, fy=sc)
            cv2.putText(c0, "VORHER Raster aus Gitterbloecken, Trapez 0,45/0,2", (10, 30), 0, 0.8, (0, 0, 255), 2)
            cv2.putText(c1, f"NACHHER Zelle: Lage {zelle['lage_quelle']} Phase {zelle['phase_abs']:.2f}, Breite {zelle['breite']:.2f}, Hoehe {hoehe_w or 0:.2f}; F = Foto-Versatz/-Breite je Konsole (? = Foto nicht qualifiziert)", (10, 30), 0, 0.6, (0, 255, 0), 2)
            out = os.path.join(a.audit, f"konsolen_zelle_vorher_nachher_{os.path.splitext(f)[0]}.jpg"); cv2.imwrite(out, np.vstack([c0, c1])); print("->", out)


if __name__ == "__main__":
    main()
