#!/usr/bin/env python3
"""konsolen_sweep.py - Konsolen-Phase und -Form per GPU-Sweep gegen die Stabilitaetskarten ALLER Fotos, die die Konsolenzone sehen (Wiederholungsprior).

Raster: Periode P = Pfeilerabstand / k (k fest, Standard 3 = Nutzerbefund Foto 6120 '3 je Joch'; k = 2/4 nur als Vergleich berichtet).
Gesucht: Phase (0..P), Breite w (Vorderansicht, konstant), Hoehe h (unter der Plattenunterseite), Ausladung oben dt (Seitenprofil schraeg auf db unten).
Je Konsole drei Kanten (links/rechts schraeg in der Ausladung, Unterkante); Projektion in jede Kamera (SIMPLE_RADIAL), Kantenstuetzung = Wert der
(um tol_m geweiteten) Stabilitaetskarte; Score = Summe Stuetzung / Summe sichtbarer Punkte ueber alle Fotos und alle Konsolen (alle Konsolen teilen Phase/Form).
Zerlegung fuer Tempo: Seitenkante haengt nur von (Kantenlage, h, dt) ab, Unterkante von (Mitte, w, h) -> zwei Tabellen, dann Kombination.
Fotos: Kamera vor der Front, unter der Platte (sonst verdeckt die Platte), < dmax, Zone im Bild.

  python -I konsolen_sweep.py KOERPER_v10.json KONSOLEN_v11.json KAM.json STABILDIR [--k 3] [--synth] [--bilder DIR --audit DIR --fotos a.jpg,b.jpg]
  -> schreibt in KONSOLEN_v11.json den Block "foto_sweep" und ersetzt "konsolen" (Quelle "foto_sweep"); alte Liste unter "konsolen_raster_gitter".
  --synth: Beweistest - Stabilitaetskarten durch verschobenen Hintergrund (np.roll) + gezeichnete Konsolen bekannter Phase/Form ersetzen, wiederfinden.
"""
import sys, os, json, math, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB = 0.15          # ANNAHME: Ausladung der Konsole unten 0,15 m (Gitter/Fotos liefern kein Profil-Ende; geht nur in die Unterkante ein)
NPT = 8            # Punkte je Kante
TOL_M = 0.04       # Weitung der Kantenkarte in m (in Pixel je Foto umgerechnet, 1..6 px)
W_GR = np.round(np.arange(0.10, 0.901, 0.05), 3)
H_GR = np.round(np.arange(0.3, 1.51, 0.1), 3)
H_U = np.round(np.append(H_GR, H_GR[-1] + 0.1), 3)   # Unterkante zusaetzlich 0,1 m tiefer (Kontrastlinie)
DT_GR = np.round(np.arange(0.2, 1.41, 0.1), 3)
KONTRAST = 0.10    # m: Kontrast = Stuetzung der Kante minus Stuetzung derselben Kante 0,1 m nach aussen versetzt (freie Wand)
D_STEP = 0.01
DZ_GR = np.round(np.arange(-0.2, 0.41, 0.1), 3)   # Lage der Konsolenoberkante relativ zur Plattenunterseite des Koerpers (Platten-z ist selbst Gittermass, Fehler ~0,3 m)
AUSSEN = 0.15      # m: Wandstreifen links/rechts der Konsole fuer den Flaechenkontrast


def kameras(KAM, sd, u, n, of, zp0, a0, a1, dmax):
    zone = np.array([(0.5 * (a0 + a1)) * u + (of + 0.5) * n + np.array([0, 0, zp0 - 0.6])])
    fs = []
    for f in sorted(KAM):
        if not os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png")): continue
        k = KAM[f]; C = np.array(k["C"])
        if C @ n - of < 1.5 or C[2] > zp0 - 0.2: continue
        # Zone (Plattenlaenge) muss teilweise im Bild liegen und nah genug sein
        pts = np.array([a * u + (of + 0.5) * n + np.array([0, 0, zp0 - 0.6]) for a in np.linspace(a0, a1, 9)])
        d = np.linalg.norm(pts - C, axis=1)
        if d.min() > dmax: continue
        X = pts @ np.array(k["Rn"]).T + np.array(k["tn"]); okz = X[:, 2] > 1
        if not okz.any(): continue
        x = X[okz, 0] / X[okz, 2] * k["f"] + k["cx"]; y = X[okz, 1] / X[okz, 2] * k["f"] + k["cy"]
        if ((x >= 0) & (x < k["W"]) & (y >= 0) & (y < k["H"])).sum() >= 2: fs.append(f)
    return fs


def projiziere(Q, k, sj, torch):
    R = torch.tensor(k["Rn"], device=Q.device, dtype=torch.float32); t = torch.tensor(k["tn"], device=Q.device, dtype=torch.float32)
    X = Q @ R.T + t; z = X[:, 2].clamp(min=0.3); x = X[:, 0] / z; y = X[:, 1] / z; f1 = 1 + k["params"][3] * (x * x + y * y)
    return ((k["f"] * x * f1 + k["cx"]) * sj).round().long(), ((k["f"] * y * f1 + k["cy"]) * sj).round().long(), X[:, 2] > 1


def kanten_punkte(u, n, of, zp0, xs, kind, w=None, h=None, dt=None, torch=None, dev="cuda"):
    """xs: Lage entlang der Front (Kante bzw. Mitte). kind 'seite': Gerade (x, of+dt, zp0) -> (x, of+DB', zp0-h); 'unten': (x-w/2..x+w/2, of+DB', zp0-h)."""
    tt = torch.linspace(0, 1, NPT, device=dev)
    uu = torch.tensor(u, device=dev, dtype=torch.float32); nn = torch.tensor(n, device=dev, dtype=torch.float32); ez = torch.tensor([0., 0., 1.], device=dev)
    if kind == "seite":
        x, hh, d_ = xs, h, dt   # Tensoren gleicher Form
        db = torch.clamp(d_, max=DB)
        al = x[..., None].expand(*x.shape, NPT); off = of + d_[..., None] + (db - d_)[..., None] * tt; z = zp0 - hh[..., None] * tt
    else:
        x, ww, hh = xs, w, h
        db = DB
        al = x[..., None] + ww[..., None] * (tt - 0.5); off = of + db + 0 * al; z = (zp0 - hh)[..., None] + 0 * al
    return al[..., None] * uu + off[..., None] * nn + z[..., None] * ez


def tabellen(u, n, of, zp0, x_ref, P, J, fs, KAM, karte, dev, torch):
    """je dz eigene Tabellen (Oberkante zp0+dz); Rueckgabe e_gr, c_gr, Liste je dz."""
    res = []
    for dz in DZ_GR:
        e_gr, c_gr, T = tabellen1(u, n, of, zp0 + float(dz), x_ref, P, J, fs, KAM, karte, dev, torch); res.append(T)
    return e_gr, c_gr, res


def tabellen1(u, n, of, zp0, x_ref, P, J, fs, KAM, karte, dev, torch):
    """H/N-Tabellen: seite[j, e, h, dt], unten[j, c, w, h] fuer Konsole j an x_ref + j*P + Versatz."""
    e_gr = np.arange(-W_GR.max() / 2 - max(KONTRAST, AUSSEN) - 0.05, P + W_GR.max() / 2 + max(KONTRAST, AUSSEN) + 0.05, D_STEP); c_gr = np.arange(0, P, D_STEP)
    jj = torch.arange(J, device=dev, dtype=torch.float32) * P + x_ref
    E = torch.tensor(e_gr, device=dev, dtype=torch.float32); Cc = torch.tensor(c_gr, device=dev, dtype=torch.float32)
    Hg = torch.tensor(H_GR, device=dev, dtype=torch.float32); Dg = torch.tensor(DT_GR, device=dev, dtype=torch.float32); Wg = torch.tensor(W_GR, device=dev, dtype=torch.float32)
    xs = (jj[:, None, None, None] + E[None, :, None, None]).expand(J, len(E), len(Hg), len(Dg))
    hS = Hg[None, None, :, None].expand_as(xs); dS = Dg[None, None, None, :].expand_as(xs)
    QS = kanten_punkte(u, n, of, zp0, xs, "seite", h=hS, dt=dS, torch=torch, dev=dev)            # J,E,H,D,NPT,3
    Hu = torch.tensor(H_U, device=dev, dtype=torch.float32)
    xb = (jj[:, None, None, None] + Cc[None, :, None, None]).expand(J, len(Cc), len(Wg), len(Hu))
    wB = Wg[None, None, :, None].expand_as(xb); hB = Hu[None, None, None, :].expand_as(xb)
    QB = kanten_punkte(u, n, of, zp0, xb, "unten", w=wB, h=hB, torch=torch, dev=dev)              # J,C,W,H,NPT,3
    out = {}
    for name, Q in (("seite", QS), ("unten", QB)):
        sh = Q.shape[:-2]; Qf = Q.reshape(-1, 3); Hs = torch.zeros(Qf.shape[0] // NPT, device=dev); Ns = torch.zeros_like(Hs)
        for f in fs:
            k = KAM[f]; V = karte(f); sj = V.shape[1] / k["W"]
            dist = float(np.linalg.norm(np.array(k["C"]) - (x_ref + J * P / 2) * np.array(u) - (of * np.array(n)) - np.array([0, 0, zp0])))
            rad = int(np.clip(round(TOL_M * k["f"] * sj / max(dist, 1.0)), 1, 6))
            Vm = torch.nn.functional.max_pool2d(V[None, None], 2 * rad + 1, 1, rad)[0, 0]; Hh, Ww = Vm.shape
            for s in range(0, Qf.shape[0], 1_500_000):
                q = Qf[s:s + 1_500_000]; uu, vv, okz = projiziere(q, k, sj, torch)
                ok = okz & (uu >= 0) & (uu < Ww) & (vv >= 0) & (vv < Hh); hit = torch.zeros(len(q), device=dev); hit[ok] = Vm[vv[ok], uu[ok]]
                # nur ganz sichtbare Kanten zaehlen (sonst bevorzugt der Rand des Bildes Teilkanten)
                okk = ok.view(-1, NPT).float().mean(1) >= 0.99; i0 = s // NPT
                Hs[i0:i0 + len(okk)] += torch.where(okk, hit.view(-1, NPT).sum(1), torch.zeros_like(okk, dtype=torch.float32))
                Ns[i0:i0 + len(okk)] += okk.float() * NPT
        out[name] = (Hs.view(sh), Ns.view(sh))
    return e_gr, c_gr, out


def kombiniere1(e_gr, c_gr, T, sel=None, modus="beide"):
    """Score[c, w, h, dt] fuer eine dz-Scheibe. Kanten: je Kante mittlere Stuetzung minus dieselbe Kante 0,1 m nach aussen (freie Wand).
    Flaeche: mittlere Stuetzung der Vorderflaeche (Streifen = Seitenlinien zwischen den Kanten) minus Wandstreifen AUSSEN links/rechts.
    modus 'kanten' | 'flaeche' | 'beide' (Summe) | 'roh' (nur Stuetzung der Kanten, ohne Kontrast)."""
    import torch
    HS, NS = T["seite"]; HU, NU = T["unten"]
    if sel is not None: HS, NS, HU, NU = HS[sel], NS[sel], HU[sel], NU[sel]
    HS, NS, HU, NU = HS.sum(0), NS.sum(0), HU.sum(0), NU.sum(0)                 # E,H,D / C,W,Hu
    iL = np.array([[int(round((c - w / 2 - e_gr[0]) / D_STEP)) for w in W_GR] for c in c_gr]); iR = np.array([[int(round((c + w / 2 - e_gr[0]) / D_STEP)) for w in W_GR] for c in c_gr])
    iL = torch.tensor(iL, device=HS.device); iR = torch.tensor(iR, device=HS.device); dk = int(round(KONTRAST / D_STEP)); da = int(round(AUSSEN / D_STEP))
    mS = HS / NS.clamp(min=1); mU = HU / NU.clamp(min=1)
    N_ = NS[iL] + NS[iR] + NU[:, :, :-1, None]  # C,W,H,D
    if modus == "roh": return (mS[iL] + mS[iR] + mU[:, :, :-1, None]) / 3, N_
    K_ = ((mS[iL] - mS[iL - dk]) + (mS[iR] - mS[iR + dk]) + (mU[:, :, :-1] - mU[:, :, 1:])[:, :, :, None]) / 3
    CS = torch.cat([torch.zeros_like(mS[:1]), torch.cumsum(mS, 0)], 0)          # (E+1),H,D
    innen = (CS[iR + 1] - CS[iL]) / (iR - iL + 1)[..., None, None].float()
    aussen = ((CS[iL] - CS[iL - da]) + (CS[iR + 1 + da] - CS[iR + 1])) / (2 * da)
    F_ = innen - aussen
    if modus == "kanten": return K_, N_
    if modus == "flaeche": return F_, N_
    return K_ + F_, N_


def kombiniere(e_gr, c_gr, TL, sel=None, modus="beide"):
    """Score[c, w, h, dt, dz] ueber alle dz-Scheiben."""
    import torch
    out = [kombiniere1(e_gr, c_gr, T, sel, modus) for T in TL]
    return torch.stack([o[0] for o in out], -1), torch.stack([o[1] for o in out], -1)


def wolke_tabelle(Pw, u, n, of, zp0, x_ref, P, J, a0, a1, dev, torch):
    """Wolken-Sweep (eigenes Signal, nicht mit Fotos gemischt): je Profil (h, dt, dz) Punkte im Seitenprofil der Konsole (vor der Wand ab 8 cm,
    Ausladung linear dt oben -> DB unten), Histogramm entlang der Front (1 cm). Signal je Konsole = Kasten-Mittel minus Wandstreifen-Mittel, / sqrt(Profilflaeche)
    (Median ueber die ganze Plattenlaenge = Hintergrund, Konsolen belegen nur ~15 %). Rueckgabe S_j[J, C, W, H, D, Z]."""
    al = Pw @ u; off = Pw @ n - of; z = Pw[:, 2]
    m = (al > a0 - 0.5) & (al < a1 + 0.5) & (off > 0.08) & (off < DT_GR.max() + 0.05) & (z > zp0 + DZ_GR.min() - H_GR.max() - 0.05) & (z < zp0 + DZ_GR.max() + 0.05)
    al = torch.tensor(al[m], device=dev, dtype=torch.float32); off = torch.tensor(off[m], device=dev, dtype=torch.float32); z = torch.tensor(z[m], device=dev, dtype=torch.float32)
    A0 = a0 - 0.5; nA = int(math.ceil((a1 + 0.5 - A0) / D_STEP)); ib = ((al - A0) / D_STEP).long().clamp(0, nA - 1)
    prof = [(h, d, dz) for h in H_GR for d in DT_GR for dz in DZ_GR]; Hst = torch.zeros(len(prof), nA, device=dev)
    for i, (h, d, dz) in enumerate(prof):
        zt = zp0 + dz; zb = zt - h; tz = (z - zb) / h
        inn = (z >= zb) & (z <= zt) & (off <= DB + (d - DB) * tz) if d > DB else (z >= zb) & (z <= zt) & (off <= d)
        Hst[i].index_add_(0, ib[inn], torch.ones(int(inn.sum()), device=dev))
    # Signal = mittlere Punktzahl je cm im Kasten minus Mittel der Wandstreifen AUSSEN links/rechts (gleiches Profil); geteilt durch sqrt(Profilflaeche)
    # (Matched-Filter bei gleichfoermigem Hintergrund: zu grosse Kaesten verduennen, zu kleine verlieren Signal, zu breite heben den Streifen nicht ab)
    area = torch.tensor([h * (min(d, DB) + d) / 2 for h, d, dz in prof], device=dev)
    CS = torch.cat([torch.zeros(len(prof), 1, device=dev), torch.cumsum(Hst, 1)], 1); da = int(round(AUSSEN / D_STEP))
    c_gr = np.arange(0, P, D_STEP); out = torch.zeros(J, len(c_gr), len(W_GR), len(prof), device=dev)
    for j in range(J):
        for wi, w in enumerate(W_GR):
            lo = np.round((x_ref + j * P + c_gr - w / 2 - A0) / D_STEP).astype(int); hi = np.round((x_ref + j * P + c_gr + w / 2 - A0) / D_STEP).astype(int)
            lo = torch.tensor(np.clip(lo, da, nA - da), device=dev); hi = torch.tensor(np.clip(hi, da, nA - da), device=dev)
            inn = (CS[:, hi] - CS[:, lo]) / (hi - lo).clamp(min=1).float()[None]; aus = ((CS[:, lo] - CS[:, lo - da]) + (CS[:, hi + da] - CS[:, hi])) / (2 * da)
            out[j, :, wi, :] = ((inn - aus) / area.sqrt()[:, None]).T
    return c_gr, out.view(J, len(c_gr), len(W_GR), len(H_GR), len(DT_GR), len(DZ_GR)), int(m.sum())


def plateau(S, best_idx, frac):
    """Breite (Anzahl Gitterschritte) je Achse, in der der Score >= frac*max bleibt (andere Achsen am Optimum)."""
    out = []
    for ax in range(S.ndim):
        idx = list(best_idx); line = []
        for i in range(S.shape[ax]): idx[ax] = i; line.append(float(S[tuple(idx)]))
        line = np.array(line); b = best_idx[ax]; thr = frac * line[b]; lo = b; hi = b; nL = len(line)
        if ax == 0:   # Phase zirkulaer (Werte ausserhalb 0..n-1 = ueber die Periode hinaus)
            while lo > b - nL + 1 and line[(lo - 1) % nL] >= thr: lo -= 1
            while hi < b + nL - 1 and line[(hi + 1) % nL] >= thr: hi += 1
        else:
            while lo > 0 and line[lo - 1] >= thr: lo -= 1
            while hi < nL - 1 and line[hi + 1] >= thr: hi += 1
        out.append((lo, hi))
    return out


def projekt_poly(Q, k, sj):
    X = Q @ np.array(k["Rn"]).T + np.array(k["tn"])
    if (X[:, 2] < 1).any(): return None
    xx = X[:, 0] / X[:, 2]; yy = X[:, 1] / X[:, 2]; f1 = 1 + k["params"][3] * (xx * xx + yy * yy)
    return np.c_[(k["f"] * xx * f1 + k["cx"]) * sj, (k["f"] * yy * f1 + k["cy"]) * sj]


def konsole_poly(u, n, of, x, wt, wb, to, tu, zt, zb):
    """Umriss Vorderflaeche (oben Ausladung to, unten tu)."""
    poly = [(x - wt / 2, of + to, zt), (x + wt / 2, of + to, zt), (x + wb / 2, of + tu, zb), (x - wb / 2, of + tu, zb)]
    return np.array([p[0] * u + p[1] * n + np.array([0, 0, p[2]]) for p in poly])


def entscheiden(k10, kons, f_json, w_json):
    """Nutzerregel: Foto- und Wolken-Sweep getrennt; uebernommen nur, was beide entschieden UND einig ist (Phase <= 10 % der Periode, Masse <= 0,05 m
    bzw. ein Gitterschritt). Sonst offene Beobachtung mit beiden Werten, Wert bleibt (ANNAHME). Nie mitteln."""
    D = json.load(open(k10)); pl = D["balkon"]["platte"]; zp0 = pl["z0"]; a0, a1 = pl["along"]
    K = json.load(open(kons)); F = json.load(open(f_json)); W = json.load(open(w_json)); P = F["periode"]; log = []
    assert abs(W["periode"] - P) < 1e-6
    dph = abs(((F["phase_abs"] - W["phase_abs"]) + P / 2) % P - P / 2); beide = F["entschieden"] and W["entschieden"]
    ph_ok = beide and dph <= 0.1 * P and "phase" not in F["auf_grenze"] and "phase" not in W["auf_grenze"]
    masse = {}
    for m, tol in (("breite", 0.05), ("hoehe", 0.1), ("tiefe_oben", 0.1), ("dz_platte", 0.1)):
        ok = beide and abs(F[m] - W[m]) <= tol + 1e-9 and m not in F["auf_grenze"] and m not in W["auf_grenze"]
        masse[m] = {"foto": F[m], "wolke": W[m], "einig": bool(ok), "toleranz": tol}
    log.append(f"Phase: Foto {F['phase_abs']:.2f} ({F['signifikanz_mad']:.1f} MAD, {'entschieden' if F['entschieden'] else 'blind'}), Wolke {W['phase_abs']:.2f} ({W['signifikanz_mad']:.1f} MAD, {'entschieden' if W['entschieden'] else 'blind'}), Abstand {dph:.2f} m (Grenze 10 % P = {0.1 * P:.2f}) -> {'EINIG' if ph_ok else 'OFFEN'}")
    for m, v in masse.items(): log.append(f"{m}: Foto {v['foto']} / Wolke {v['wolke']} (Grenzlagen Foto {F['auf_grenze']}, Wolke {W['auf_grenze']}) -> {'EINIG' if v['einig'] else 'OFFEN (Widerspruch oder Grenze; nicht gemittelt, Form bleibt ANNAHME)'}")
    if ph_ok:
        phase = W["phase_abs"]; quelle = "foto_sweep+wolke_sweep einig (Phase der Wolke uebernommen, Foto innerhalb 10 % P)"
        log.append(f"Phase uebernommen: {phase:.2f} (Wolken-Optimum; nicht gemittelt)")
        j0 = math.ceil((a0 + 0.3 - phase) / P); j1 = math.floor((a1 - 0.3 - phase) / P); alt = K.get("konsolen_raster_gitter", K["konsolen"])
        if "konsolen_raster_gitter" not in K: K["konsolen_raster_gitter"] = K["konsolen"]
        K["konsolen"] = [{"along": float(phase + j * P), "z0": float(zp0 - 0.9), "status": "foto_sweep+wolke_sweep (Lage); Form ANNAHME Trapez", "quelle": "foto_sweep"} for j in range(j0, j1 + 1)]
        K["periode"] = P; K["phase"] = phase
    else:
        log.append("Phase NICHT uebernommen: konsolen bleiben wie vorher (offene Beobachtung)")
    K["sweep_entscheidung"] = {"phase": {"foto": F["phase_abs"], "wolke": W["phase_abs"], "abstand": dph, "einig": bool(ph_ok)}, "masse": masse, "foto_datei": f_json, "wolke_datei": w_json, "log": log}
    K.setdefault("beobachtungen_offen", [])
    for m, v in masse.items():
        if not v["einig"]: K["beobachtungen_offen"].append(f"Konsole {m}: Foto {v['foto']} vs Wolke {v['wolke']} - Widerspruch/Grenze, Form bleibt ANNAHME (Trapez 0,45/0,2); naechster Schritt: Profil aus Seitenansicht-Fotos messen")
    json.dump(K, open(kons, "w"), indent=1); print("\n".join(log)); print("->", kons)


def main():
    import torch, cv2
    if sys.argv[1] == "--entscheiden": entscheiden(*sys.argv[2:6]); return
    ap = argparse.ArgumentParser(); ap.add_argument("k10"); ap.add_argument("kons"); ap.add_argument("kam"); ap.add_argument("stabil")
    ap.add_argument("--k", type=int, default=3); ap.add_argument("--synth", action="store_true"); ap.add_argument("--dmax", type=float, default=45.0)
    ap.add_argument("--karte", default="stabil", choices=["stabil", "grad"], help="stabil = Stabilitaetskarten, grad = Gradientenbetrag des Fotos (--bilder noetig)")
    ap.add_argument("--modus", default="beide", choices=["beide", "kanten", "flaeche"])
    ap.add_argument("--quelle", default="foto", choices=["foto", "wolke"], help="foto = Fotokanten allein, wolke = Punktdichte allein (getrennte Sweeps, Nutzerregel: nie gemischt)")
    ap.add_argument("--wolke", help="Punktwolke .npy/.npz (N x 3+), fuer --quelle wolke")
    ap.add_argument("--bilder"); ap.add_argument("--audit"); ap.add_argument("--fotos", default="ip_IMG_6120.jpg,ip_IMG_6261.jpg"); ap.add_argument("--nur_bilder", action="store_true")
    ap.add_argument("--nicht_schreiben", action="store_true", help="konsolen_v11.json nicht aendern (Vergleichslauf)")
    ap.add_argument("--synth_phase", type=float, default=0.67); ap.add_argument("--synth_form", default="0.25,0.8,0.6,0.1", help="w,h,dt,dz")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cuda": torch.cuda.set_per_process_memory_fraction(min(1.0, 2400 / (torch.cuda.get_device_properties(0).total_memory / 2**20)))
    D = json.load(open(a.k10)); u = np.array(D["u"]); n = np.array(D["n"]); of = D["off_front"]; pl = D["balkon"]["platte"]; zp0 = pl["z0"]; a0, a1 = pl["along"]
    K = json.load(open(a.kons)); sp = K["pfeilerabstand"]; KAM = json.load(open(a.kam))
    fs = kameras(KAM, a.stabil, u, n, of, zp0, a0, a1, a.dmax); log = []; L_ = lambda s_: (print(s_, flush=True), log.append(s_))
    L_(f"Konsolenzone along {a0:.2f}..{a1:.2f}, Plattenunterseite z {zp0:.2f}, Front {of:.2f}; Fotos (vor der Front, unter der Platte, < {a.dmax} m, Zone im Bild): {len(fs)}; Karte {a.karte}, Modus {a.modus}")
    cache = {}; synth = None
    if a.synth:
        ws, hs, ds, dzs = [float(x) for x in a.synth_form.split(",")]; synth = (a.synth_phase, ws, hs, ds, dzs)
        L_(f"SYNTH: Hintergrund = echte Karte np.roll(300 px, 250 px)*0,8, Konsolen (Umriss) gezeichnet mit Phase {a.synth_phase:.3f} (rel. Plattenanfang+0,3), w {ws}, h {hs}, dt {ds}, dz {dzs}")

    def karte(f):
        if f in cache: return cache[f].to(dev).float() / 255.0
        Vs = cv2.imread(os.path.join(a.stabil, os.path.splitext(f)[0] + ".png"), 0)
        if a.karte == "grad":
            im = cv2.imread(os.path.join(a.bilder, f), 0); im = cv2.resize(im, (Vs.shape[1], Vs.shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32)
            g = np.hypot(cv2.Sobel(im, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(im, cv2.CV_32F, 0, 1, ksize=3)); V = np.clip(g / max(np.percentile(g, 99), 1e-3), 0, 1)
        else:
            V = Vs.astype(np.float32) / 255.0
        if synth is not None:
            V = np.roll(np.roll(V, 300, 1), 250, 0) * 0.8
            k = KAM[f]; sj = V.shape[1] / k["W"]; ph, ws, hs, ds, dzs = synth; P = sp / a.k
            for j in range(-1, int((a1 - a0) / P) + 2):
                x = a0 + 0.3 + ph + j * P
                if x < a0 or x > a1: continue
                uv = projekt_poly(konsole_poly(u, n, of, x, ws, ws, ds, min(ds, DB), zp0 + dzs, zp0 + dzs - hs), k, sj)
                if uv is not None: cv2.polylines(V, [uv.round().astype(np.int32)], True, 1.0, 1)
        cache[f] = torch.from_numpy((np.clip(V, 0, 1) * 255).astype(np.uint8)); return cache[f].to(dev).float() / 255.0   # Cache auf CPU (Hunderte Karten > VRAM-Budget)

    def achsen(c_gr):
        return [c_gr, W_GR, H_GR, DT_GR, DZ_GR]

    x_ref = a0 + 0.3; ergebnisse = {}
    for kk in ([a.k] + [x for x in (2, 3, 4) if x != a.k]) if not a.nur_bilder else []:
        P = sp / kk; J = int(math.floor((a1 - 0.3 - x_ref - P) / P)) + 1
        if a.quelle == "wolke":
            if "Pw" not in dir():
                Wl = np.load(a.wolke, mmap_mode="r"); Pw = np.asarray((Wl["P"] if hasattr(Wl, "files") else Wl)[:, :3], dtype=np.float64)
            c_gr, Sj_all, nz = wolke_tabelle(Pw, u, n, of, zp0, x_ref, P, J, a0, a1, dev, torch); e_gr = None; TL = Sj_all
            S = Sj_all.median(0).values; Sn = S.cpu().numpy(); bi = np.unravel_index(np.argmax(Sn), Sn.shape); a.modus = "wolke_kontrast"   # Median ueber die Instanzen (Wiederholungsprior)
            L_(f"k={kk}: Wolke {a.wolke}: {nz} Punkte in der Konsolenzone")
        else:
            e_gr, c_gr, TL = tabellen(u, n, of, zp0, x_ref, P, J, fs, KAM, karte, dev, torch)
            Sl = []
            for j in range(J):
                sel = torch.zeros(J, dtype=torch.bool, device=dev); sel[j] = True; Sl.append(kombiniere(e_gr, c_gr, TL, sel, a.modus)[0])
            S = torch.stack(Sl, 0).median(0).values; Sn = S.cpu().numpy(); bi = np.unravel_index(np.argmax(Sn), Sn.shape)   # Median ueber die Instanzen
        ergebnisse[kk] = dict(P=P, J=J, e_gr=e_gr, c_gr=c_gr, T=TL, S=Sn, bi=bi)
        ax = achsen(c_gr); fmt = lambda b: f"Phase {ax[0][b[0]]:.2f} w {ax[1][b[1]]} h {ax[2][b[2]]} dt {ax[3][b[3]]} dz {ax[4][b[4]]:+.1f}"
        L_(f"k={kk}: Periode {P:.3f} m, {J} Konsolen ganz in der Zone; bester Score {Sn[bi]:.4f} bei {fmt(bi)}; Median aller Konfigurationen {np.median(Sn):.4f}")
        if kk != a.k: continue
        for md in (("roh", "kanten", "flaeche") if a.quelle == "foto" else ()):
            if md == a.modus: continue
            S0 = kombiniere(e_gr, c_gr, TL, modus=md)[0].cpu().numpy(); b0 = np.unravel_index(np.argmax(S0), S0.shape); L_(f"  Vergleich Modus {md}: Optimum {fmt(b0)} (Score {S0[b0]:.4f})")
        for frac in (0.98, 0.95):
            pw = plateau(Sn, bi, frac)
            L_(f"  Plateau >= {frac:.0%} max: Phase {(pw[0][1] - pw[0][0]) * D_STEP:.2f} m breit, w {W_GR[pw[1][0]]}..{W_GR[pw[1][1]]}, h {H_GR[pw[2][0]]}..{H_GR[pw[2][1]]}, dt {DT_GR[pw[3][0]]}..{DT_GR[pw[3][1]]}, dz {DZ_GR[pw[4][0]]}..{DZ_GR[pw[4][1]]}")
        ph_line = Sn[:, bi[1], bi[2], bi[3], bi[4]]; L_(f"  Phasenprofil (alle 0,1 m ab 0): {np.round(ph_line[::10], 3).tolist()}")
    if a.nur_bilder:
        best = K["foto_sweep"]; P = best["periode"]
    else:
        R = ergebnisse[a.k]; P = R["P"]; bi = R["bi"]; Sn = R["S"]; ph = float(R["c_gr"][bi[0]])
        w, h, dt, dz = float(W_GR[bi[1]]), float(H_GR[bi[2]]), float(DT_GR[bi[3]]), float(DZ_GR[bi[4]])
        je = []
        for j in range(R["J"]):
            sel = torch.zeros(R["J"], dtype=torch.bool, device=dev); sel[j] = True
            if a.quelle == "wolke": Sj = R["T"][j][:, bi[1], bi[2], bi[3], bi[4]].cpu().numpy(); Nj = np.zeros_like(Sj)
            else: Sj, Nj = kombiniere(R["e_gr"], R["c_gr"], R["T"], sel, a.modus); Sj = Sj[:, bi[1], bi[2], bi[3], bi[4]].cpu().numpy(); Nj = Nj[:, bi[1], bi[2], bi[3], bi[4]].cpu().numpy()
            c = R["c_gr"]; dd = ((c - ph + P / 2) % P) - P / 2; m = np.abs(dd) <= 0.3; ib = np.where(m)[0][np.argmax(Sj[m])]
            je.append({"along": float(x_ref + ph + j * P), "score_raster": float(Sj[bi[0]]), "punkte": int(Nj[bi[0]]), "bester_versatz": float(dd[ib]), "score_versatz": float(Sj[ib])})
        for e in je: L_(f"  Konsole along {e['along']:6.2f}: Score {e['score_raster']:.3f} ({e['punkte']} Punkte), bester eigener Versatz {e['bester_versatz']:+.2f} m (Score {e['score_versatz']:.3f})")
        vs = np.array([e["bester_versatz"] for e in je]); L_(f"  eigene Versaetze: Median {np.median(vs):+.2f}, |Versatz| <= 0,1 m bei {int((np.abs(vs) <= 0.1).sum())}/{len(vs)}")
        pw98 = plateau(Sn, bi, 0.98); pw95 = plateau(Sn, bi, 0.95); phase_abs = x_ref + ph
        # Datenmenge + Signifikanz (Nutzerregel: Quelle zaehlt nur mit genug Daten; Schwellen wie muster_fit --pruefen: Spitze - Median >= 3 MAD,
        # Wolke >= 30 Punkte je Instanz und >= 3 Instanzen, Fotos >= 3 sehende Fotos je Instanz aus >= 2 Richtungen)
        prof = Sn.reshape(Sn.shape[0], -1).max(1); med_ = float(np.median(prof)); mad_ = float(np.median(np.abs(prof - med_))); sig = (float(prof.max()) - med_) / max(mad_, 1e-9)
        inst = []
        for j in range(R["J"]):
            x = x_ref + ph + j * P; zt = zp0 + dz; zb = zt - h
            if a.quelle == "wolke":
                al_ = Pw @ u; off_ = Pw @ n - of; z_ = Pw[:, 2]; tz = (z_ - zb) / h
                inn = (np.abs(al_ - x) <= w / 2) & (z_ >= zb) & (z_ <= zt) & (off_ > 0.08) & (off_ <= (DB + (dt - DB) * tz if dt > DB else dt))
                inst.append({"along": float(x), "punkte": int(inn.sum()), "genug": bool(inn.sum() >= 30)})
            else:
                Q = konsole_poly(u, n, of, x, w, w, dt, min(dt, DB), zt, zb); seh = []; ri = set()
                for f in fs:
                    k = KAM[f]; uv = projekt_poly(Q, k, 1.0)
                    if uv is None or not ((uv[:, 0] >= 0) & (uv[:, 0] < k["W"]) & (uv[:, 1] >= 0) & (uv[:, 1] < k["H"])).all(): continue
                    dv = np.array(k["C"]) - Q.mean(0); dv[2] = 0; ang = math.degrees(math.atan2(dv @ u, dv @ n)); seh.append(f); ri.add(-1 if ang < -15 else (1 if ang > 15 else 0))
                inst.append({"along": float(x), "fotos": len(seh), "richtungen": sorted(ri), "genug": bool(len(seh) >= 3 and len(ri) >= 2)})
        n_ok = sum(i["genug"] for i in inst); entsch = bool(sig >= 3 and n_ok >= 3)
        L_(f"  Signifikanz: Spitze-Median = {sig:.1f} MAD (Profil max ueber Form je Phase), Instanzen mit genug Daten {n_ok}/{len(inst)} -> {'ENTSCHIEDEN' if entsch else 'BLIND/unentschieden'}")
        pl_ = lambda pw: {"phase_breite_m": (pw[0][1] - pw[0][0]) * D_STEP, "breite": [float(W_GR[pw[1][0]]), float(W_GR[pw[1][1]])], "hoehe": [float(H_GR[pw[2][0]]), float(H_GR[pw[2][1]])],
                          "tiefe_oben": [float(DT_GR[pw[3][0]]), float(DT_GR[pw[3][1]])], "dz": [float(DZ_GR[pw[4][0]]), float(DZ_GR[pw[4][1]])]}
        k_vgl = {str(kk): {"periode": float(r["P"]), "score": float(r["S"][r["bi"]])} for kk, r in ergebnisse.items()}
        rand = [nm for nm, gr, i in (("breite", W_GR, bi[1]), ("hoehe", H_GR, bi[2]), ("tiefe_oben", DT_GR, bi[3]), ("dz", DZ_GR, bi[4])) if i in (0, len(gr) - 1)]
        if rand: L_(f"  WARNUNG: Optimum auf Suchgrenze bei {rand} (Regel 9c: Grenze erweitern, nicht uebernehmen)")
        best = {"quelle": "foto_sweep" if a.quelle == "foto" else "wolke_sweep", "karte": a.karte if a.quelle == "foto" else os.path.basename(a.wolke), "modus": a.modus, "k": a.k, "periode": P, "phase_abs": phase_abs, "breite": w, "hoehe": h, "tiefe_oben": dt, "tiefe_unten": min(dt, DB),
                "z_oben": zp0 + dz, "dz_platte": dz, "auf_grenze": rand,
                "annahme": f"ANNAHME: Ausladung unten {DB} m (nur Unterkante); Vorderansicht Rechteck konstanter Breite (Volute nicht modelliert); Kantentoleranz {TOL_M} m",
                "score": float(Sn[bi]), "score_median": float(np.median(Sn)), "fotos": len(fs), "plateau_98": pl_(pw98), "plateau_95": pl_(pw95), "k_vergleich": k_vgl, "je_konsole": je, "signifikanz_mad": sig, "instanzen_daten": inst, "instanzen_genug": n_ok, "entschieden": entsch,
                "schwellen": "Spitze-Median >= 3 MAD; Wolke >= 30 Punkte/Instanz; Fotos >= 3 sehende Fotos aus >= 2 Richtungen/Instanz; >= 3 Instanzen", "log": log}
        if a.synth:
            ph_s, ws, hs, ds, dzs = synth
            ok = abs(((ph - ph_s + P / 2) % P) - P / 2) <= 0.03 and abs(w - ws) < 0.051 and abs(h - hs) < 0.11 and abs(dt - ds) < 0.11 and abs(dz - dzs) < 0.11
            L_(f"SYNTH-ERGEBNIS: wahr Phase {ph_s:.3f} w {ws} h {hs} dt {ds} dz {dzs} | gefunden Phase {ph:.3f} w {w} h {h} dt {dt} dz {dz} -> {'BESTANDEN' if ok else 'NICHT BESTANDEN'}")
            out = os.path.splitext(a.kons)[0] + f"_synth_{a.karte if a.quelle == 'foto' else 'wolke'}.json"; json.dump({"synth": synth, "gefunden": [ph, w, h, dt, dz], "bestanden": bool(ok), "log": log}, open(out, "w"), indent=1); print("->", out); return
        if a.nicht_schreiben:
            out = os.path.splitext(a.kons)[0] + (f"_sweep_{a.karte}_{a.modus}.json" if a.quelle == "foto" else "_sweep_wolke.json"); json.dump(best, open(out, "w"), indent=1); print("->", out); K = dict(K, foto_sweep=best, konsolen=[])
        else:
            alle = []; j0 = math.ceil((a0 + 0.3 - phase_abs) / P); j1 = math.floor((a1 - 0.3 - phase_abs) / P)
            for j in range(j0, j1 + 1):
                x = phase_abs + j * P; e = next((e for e in je if abs(e["along"] - x) < 0.01), None)
                st = f"foto_sweep (Score {e['score_raster']:.3f}, eigener Versatz {e['bester_versatz']:+.2f})" if e else "foto_sweep (Rasterplatz am Zonenrand, nicht einzeln gemessen: ANNAHME Wiederholung)"
                alle.append({"along": float(x), "z_oben": float(zp0 + dz), "z0": float(zp0 + dz - h), "breite": w, "tiefe_oben": dt, "tiefe_unten": min(dt, DB), "status": st, "quelle": "foto_sweep"})
            if "konsolen_raster_gitter" not in K: K["konsolen_raster_gitter"] = K["konsolen"]
            K["konsolen"] = alle; K["foto_sweep"] = best; K["periode"] = P; K["phase"] = phase_abs
            json.dump(K, open(a.kons, "w"), indent=1); print("->", a.kons, f"({len(alle)} Konsolen)")
    if a.bilder and a.audit:
        os.makedirs(a.audit, exist_ok=True); alt = K.get("konsolen_raster_gitter", []); B = K["foto_sweep"]; dvor = pl["tiefe"] - 0.15
        if not K["konsolen"]:   # Vergleichslauf: Raster aus dem Ergebnis zeichnen
            j0 = math.ceil((a0 + 0.3 - B["phase_abs"]) / B["periode"]); j1 = math.floor((a1 - 0.3 - B["phase_abs"]) / B["periode"])
            K["konsolen"] = [{"along": B["phase_abs"] + j * B["periode"]} for j in range(j0, j1 + 1)]
        for f in a.fotos.split(","):
            if f not in KAM: continue
            k = KAM[f]; im = cv2.imread(os.path.join(a.bilder, f))
            if im is None: continue
            sj = im.shape[1] / k["W"]; L0 = im.copy(); L1 = im.copy(); uv_all = []
            for kz in alt:
                uv = projekt_poly(konsole_poly(u, n, of, kz["along"], 0.45, 0.2, dvor, 0.15, zp0, kz["z0"]), k, sj)
                if uv is not None: uv_all.append(uv); cv2.polylines(L0, [uv.round().astype(np.int32)], True, (0, 0, 255), 2)
            for kz in K["konsolen"]:
                uv = projekt_poly(konsole_poly(u, n, of, kz["along"], B["breite"], B["breite"], B["tiefe_oben"], B["tiefe_unten"], B["z_oben"], B["z_oben"] - B["hoehe"]), k, sj)
                if uv is not None: uv_all.append(uv); cv2.polylines(L1, [uv.round().astype(np.int32)], True, (0, 255, 0), 2)
            if not uv_all: continue
            U = np.concatenate(uv_all); x0, y0 = np.clip(U.min(0) - 120, 0, None).astype(int); x1, y1 = (U.max(0) + 120).astype(int)
            x1 = min(x1, im.shape[1]); y1 = min(y1, im.shape[0])
            c0 = L0[y0:y1, x0:x1]; c1 = L1[y0:y1, x0:x1]; sc = min(1.0, 1400 / max(1, c0.shape[1]))
            c0 = cv2.resize(c0, None, fx=sc, fy=sc); c1 = cv2.resize(c1, None, fx=sc, fy=sc)
            cv2.putText(c0, "VORHER Raster aus Gitterbloecken, Trapez 0,45/0,2", (10, 30), 0, 0.8, (0, 0, 255), 2)
            cv2.putText(c1, f"NACHHER {B['quelle']} ({B['karte']}/{B['modus']}) Phase {B['phase_abs']:.2f} w {B['breite']} h {B['hoehe']} dt {B['tiefe_oben']} dz {B['dz_platte']:+.1f}", (10, 30), 0, 0.7, (0, 255, 0), 2)
            out = os.path.join(a.audit, f"konsolen_vorher_nachher_{os.path.splitext(f)[0]}_{B['karte'] if B['quelle'] == 'foto_sweep' else 'wolke'}.jpg"); cv2.imwrite(out, np.vstack([c0, c1])); print("->", out)


if __name__ == "__main__":
    main()
