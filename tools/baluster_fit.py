"""Balkonbruestung als Reihe gleicher Rotationskoerper (Baluster) aus Wolke + Tiefen-Sweep, Periode per Autokorrelation, Profil aus der gefalteten Musterzelle.
Ablauf: (1) Hoehenband automatisch: nahezu waagerechte Gittersegmente (SEG.json) nach z gebuendelt (0,1 m, Gewicht Laenge); bestes Paar Unter-/Oberkante mit Abstand
--dmin..--dmax (0,8..1,2 m) und ueberlappender Lage = Bruestung; Fassadenlinie (Richtung d, Querversatz q0) aus diesen Segmenten (PCA); (--band zlo,zhi erzwingt das Band),
(2) Punkte (Wolke + Sweep) im Band und |q-q0| < --quer (0,3 m) -> Koordinaten (t laengs, q quer, z), (3) Periode: Dichte entlang t (1 cm), Autokorrelation ueber Lags
--pmin..--pmax (0,15..0,5 m) auf der GPU, (4) Phase: Faltung t mod Periode, Phase mit der symmetrischsten gefalteten Dichte (Baluster = Rotationskoerper, Kanten symmetrisch zur Achse),
(5) Profil r(z) = Median |u| (Abstand zur Achse in der Musterzelle) je 2-cm-Scheibe, Douglas-Peucker auf --knoten Stuetzen, (6) Instanzen = Achsen phi + i*Periode im
t-Bereich der Bruestung, jede am Foto geprueft (Stabilitaetskarte >= 0,3 an >= 50 % der projizierten Mantelpunkte, Toleranz 3 px, in >= --nfoto (3) Fotos) ->
Anzahl Baluster = fotogeprueft (Regel 9), (7) Ausgabe je bestandener Instanz Achse + 8 Mantellinien als Polylinien, Segmente quelle 13.
Aufruf: baluster_fit.py WOLKE.npz SWEEP.npz SEG.json OUT.json --kam KAM.json --stabil DIR [--zmin 4 --zmax 12] [--dmin 0.8 --dmax 1.2] [--quer 0.3]
        [--pmin 0.15 --pmax 0.5] [--knoten 10] [--nfoto 3] [--band zlo,zhi]
Keine Objektkonstanten; Band, Periodenbereich und Toleranzen sind Parameter."""
import sys, os, json, numpy as np, torch, cv2
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
ZMIN, ZMAX, DMIN, DMAX, QUER, PMIN, PMAX, KNOTEN, NFOTO = g("--zmin", 4.0), g("--zmax", 12.0), g("--dmin", 0.8), g("--dmax", 1.5), g("--quer", 0.3), g("--pmin", 0.15), g("--pmax", 0.5), g("--knoten", 10, int), g("--nfoto", 3, int)
FANTEIL = g("--fanteil", 0.3); KANTE_ANTEIL = g("--kante_anteil", 0.5); PX = g("--px", 3, int)                     # bestanden: Kante in >= NFOTO Fotos UND in >= 30 % der Fotos, die die Instanz sehen (bei ~100 Sichtfotos reichen 3 Zufallstreffer sonst immer)
dev = "cuda"; torch.cuda.set_per_process_memory_fraction(float(os.environ.get("RCPARK_GPU_ANTEIL", "0.18")))
W = np.load(a[1]); W = (W["P"] if hasattr(W, "files") else W)[:, :3].astype(np.float32); SW = np.load(a[2])["P"].astype(np.float32); SEG = json.load(open(a[3]))["segmente"]

# (1) Band + Fassadenlinie aus den waagerechten Gittersegmenten
S = np.array([[s[0], s[1]] for s in SEG], dtype=float); L = np.linalg.norm(S[:, 1] - S[:, 0], axis=1); dz = np.abs(S[:, 1, 2] - S[:, 0, 2]); zm = S[:, :, 2].mean(1)
hz = (L > 0.6) & (dz < 0.1 * L) & (zm > ZMIN) & (zm < ZMAX)
if "--band" in a:
    zlo, zhi = [float(x) for x in g("--band", "", str).split(",")]; sel = hz & (np.abs(zm - zlo) < 0.15) | hz & (np.abs(zm - zhi) < 0.15)
else:
    e = np.arange(ZMIN, ZMAX + 0.1, 0.1); hist = np.zeros(len(e) - 1)
    for i in np.where(hz)[0]: hist[min(int((zm[i] - ZMIN) / 0.1), len(hist) - 1)] += L[i]
    # Kandidatenpaare (lokale Maxima der Laengensumme, Abstand DMIN..DMAX, gleiche Lage); Entscheidung NICHT nach Laenge (Lauf v3 nahm Konsolen/Boden 7,35-8,25 statt Boden/Handlauf),
    # sondern nach der Periodizitaet der Punktdichte IM Band (Autokorrelations-Spitze): Baluster sind das einzige periodische Band
    peaks = [i for i in range(1, len(hist) - 1) if hist[i] >= 3 and hist[i] >= hist[i - 1] and hist[i] >= hist[i + 1]]
    paare = []
    for i in peaks:
        for j in peaks:
            dd = (j - i) * 0.1
            if dd < DMIN or dd > DMAX: continue
            mi = hz & (np.abs(zm - (e[i] + 0.05)) < 0.15); mj = hz & (np.abs(zm - (e[j] + 0.05)) < 0.15)
            if np.linalg.norm(S[mi][:, :, :2].mean((0, 1)) - S[mj][:, :, :2].mean((0, 1))) > 6: continue        # grob gleiche Lage (Schwerpunkte < 6 m; Handlauf-Buendel enthaelt auch Fensterstuerze)
            paare.append((e[i] + 0.05, e[j] + 0.05, hist[i], hist[j]))
    if not paare: print("kein Bruestungsband gefunden"); json.dump({"baluster": [], "segmente": []}, open(a[4], "w")); sys.exit(0)
    def periodizitaet(zl, zh):
        pts2 = S[hz & ((np.abs(zm - zl) < 0.15) | (np.abs(zm - zh) < 0.15))][:, :, :2].reshape(-1, 2); c = pts2.mean(0); dd_ = np.linalg.svd(pts2 - c, full_matrices=False)[2][0]; nn_ = np.array([-dd_[1], dd_[0]])
        m_ = (W[:, 2] > zl + 0.05) & (W[:, 2] < zh - 0.05); rel = W[m_][:, :2] - c; q = rel @ nn_ - np.median((pts2 - c) @ nn_); tt_ = (rel @ dd_)[np.abs(q) < QUER]
        if len(tt_) < 500: return 0.0
        h_ = np.histogram(tt_, bins=np.arange(tt_.min(), tt_.max() + 0.01, 0.01))[0].astype(float); h_ -= h_.mean(); var = (h_ * h_).mean()
        acs = [((h_[:-s] * h_[s:]).sum() / (len(h_) - s)) / var for s in range(int(PMIN / 0.01), int(PMAX / 0.01))]
        return max([acs[k] for k in range(4, len(acs) - 4) if acs[k] >= acs[k - 4] and acs[k] >= acs[k + 4]] or [0.0])
    bew = [(periodizitaet(zl, zh), zl, zh, li, lj) for zl, zh, li, lj in paare]; bew.sort(reverse=True)
    print("Bandkandidaten (Periodizitaet, z unten, z oben, Laenge unten, Laenge oben):", [(round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 1), round(b[4], 1)) for b in bew[:6]], flush=True)
    zlo, zhi = bew[0][1], bew[0][2]; sel = hz & ((np.abs(zm - zlo) < 0.15) | (np.abs(zm - zhi) < 0.15))
pts2 = S[sel][:, :, :2].reshape(-1, 2); c2 = pts2.mean(0); U_, S_, Vt = np.linalg.svd(pts2 - c2, full_matrices=False); d = Vt[0]; nrm = np.array([-d[1], d[0]])
# t-Bereich = Ueberlappung von Unter- und Oberkante (nur wo BEIDE Kanten belegt sind, ist Bruestung); q0 = Median-Querversatz
tl_ = (S[hz & (np.abs(zm - zlo) < 0.15)][:, :, :2].reshape(-1, 2) - c2) @ d; th_ = (S[hz & (np.abs(zm - zhi) < 0.15)][:, :, :2].reshape(-1, 2) - c2) @ d
t0, t1 = float(max(tl_.min(), th_.min())), float(min(tl_.max(), th_.max())); q0 = float(np.median((pts2 - c2) @ nrm))
print("Bruestungsband z %.2f..%.2f (Gitterlaenge unten %.1f m, oben %.1f m), Fassadenlinie Mitte %s Richtung %s, t %.1f..%.1f, q0 %.2f" % (zlo, zhi, L[hz & (np.abs(zm - zlo) < 0.15)].sum(), L[hz & (np.abs(zm - zhi) < 0.15)].sum(), c2.round(2), d.round(3), t0, t1, q0), flush=True)

# (2) Punkte im Band
def koord(P):
    rel = P[:, :2] - c2; return np.stack([rel @ d, rel @ nrm - q0, P[:, 2]], 1)
alle = np.concatenate([koord(W), koord(SW)]); quelle = np.concatenate([np.zeros(len(W), np.int8), np.ones(len(SW), np.int8)])
m = (alle[:, 2] > zlo + 0.05) & (alle[:, 2] < zhi - 0.05) & (np.abs(alle[:, 1]) < QUER) & (alle[:, 0] > t0 - 0.5) & (alle[:, 0] < t1 + 0.5); B = alle[m]; qb = quelle[m]
print("Punkte im Band: %d (Wolke %d, Sweep %d)" % (len(B), (qb == 0).sum(), (qb == 1).sum()), flush=True)
Bt = torch.tensor(B, device=dev)

# (3) Periode per Autokorrelation der t-Dichte (1 cm)
tb = torch.arange(t0 - 0.5, t1 + 0.5, 0.01, device=dev); dens = torch.histc(Bt[:, 0], bins=len(tb), min=float(tb[0]), max=float(tb[-1]) + 0.01); dens = dens - dens.mean()
lags = torch.arange(PMIN, PMAX, 0.005, device=dev); ac = torch.zeros(len(lags), device=dev)
for i, lg in enumerate(lags):
    s = int(round(float(lg) / 0.01)); ac[i] = (dens[:-s] * dens[s:]).sum() / (len(dens) - s)
ac = ac / (dens * dens).mean()
# Periode = staerkstes LOKALES Maximum (Spitze mindestens 2 cm breit: groesser als beide Nachbarn im Abstand 4 Lags), nicht der Randanstieg bei kleinen Lags (Kantendicke)
acn = ac.cpu().numpy(); lok = [i for i in range(4, len(acn) - 4) if acn[i] >= acn[i - 4] and acn[i] >= acn[i + 4] and acn[i] >= acn[i - 1] and acn[i] >= acn[i + 1]]
if not lok: print("keine periodische Struktur im Band"); json.dump({"baluster": [], "segmente": []}, open(a[4], "w")); sys.exit(0)
lokm = sorted([(float(lags[i]), float(acn[i])) for i in lok], key=lambda x: -x[1]); print("lokale Maxima der Autokorrelation (Lag, Wert):", [(round(l, 3), round(v, 2)) for l, v in lokm[:6]], flush=True)
# Periodenkandidaten: lokale Maxima mit >= 95 % des besten Werts, Nachbarn < 2 cm zusammengefasst (Lauf v5/v6: 0,23 und 0,28 gleichauf 0,56 - die Wolke allein entscheidet nicht,
# Fenstersprossen hinter der Bruestung sind auch periodisch); bei mehreren Kandidaten entscheidet die FOTOPRUEFUNG (mittlerer Kantenanteil der Instanzen, jedes 5. Sichtfoto)
pk = []
for l, v in lokm:
    if v < 0.95 * lokm[0][1]: break
    if all(abs(l - p) > 0.02 for p in pk): pk.append(l)
KAM = json.load(open(g("--kam", "", str))); sd = g("--stabil", "", str); NM = 8
def welt(t, q, z): return np.array([c2[0] + t * d[0] + (q + q0) * nrm[0], c2[1] + t * d[1] + (q + q0) * nrm[1], z])
def dp(prof, zs, idx, eps):
    if len(idx) < 3: return list(idx)
    p0, p1 = np.array([prof[idx[0]], zs[idx[0]]]), np.array([prof[idx[-1]], zs[idx[-1]]]); v = p1 - p0; v /= max(np.linalg.norm(v), 1e-9)
    dd = [abs((np.array([prof[i], zs[i]]) - p0) @ np.array([-v[1], v[0]])) for i in idx[1:-1]]; k = int(np.argmax(dd))
    if dd[k] < eps: return [idx[0], idx[-1]]
    return dp(prof, zs, idx[:k + 2], eps)[:-1] + dp(prof, zs, idx[k + 1:], eps)

def foto_signal():
    """Kantensignal entlang der 3D-Bruestungslinie aus den Stabilitaetskarten: Punkte (t, q0, z) fuer 5 Hoehen im Band in jedes Sichtfoto projiziert, Kartenwert summiert.
    Lauf v7: Wolken-Autokorrelation gab 0,225/0,275 m, Sichtkontrolle 6120 zeigte ~0,34 m (Fenstersprossen hinter der Bruestung sind auch periodisch) -> Periode/Phase aus den Fotos."""
    tg = np.arange(t0 - 0.2, t1 + 0.2, 0.01); zz = np.linspace(zlo + 0.25, zhi - 0.25, 5); sig = np.zeros(len(tg)); nf_ = 0
    P3 = np.stack([welt(t, 0, z) for z in zz for t in tg])                                         # [5*T, 3]
    for f in sorted(KAM):
        pf = os.path.join(sd, os.path.splitext(f)[0] + ".png")
        if not os.path.exists(pf): continue
        k = KAM[f]; R = np.array(k["Rn"]); t_ = np.array(k["tn"]); X = R @ P3.T + t_[:, None]
        if (X[2] < 3).any() or (X[2] > 40).all(): continue
        x = X[0] / X[2]; y = X[1] / X[2]
        if (np.abs(x) > 0.6).mean() > 0.5 or (np.abs(y) > 0.6).mean() > 0.5: continue
        V = cv2.imread(pf, 0); H, Wd = V.shape; sj = Wd / k["W"]; f1 = 1 + k["params"][3] * (x * x + y * y)
        u = np.round((k["f"] * x * f1 + k["cx"]) * sj).astype(int); v = np.round((k["f"] * y * f1 + k["cy"]) * sj).astype(int); okp = (u >= 0) & (u < Wd) & (v >= 0) & (v < H)
        # Aufloesung: Pixel je Meter entlang t (Nachbarabstand der Projektionen); zu grob (< 60 px/m = Periode 0,3 m unter 18 px) traegt nichts bei
        du = np.abs(np.diff(u[:len(tg)])).mean() * 100
        if du < 60: continue
        val = np.zeros(len(P3)); val[okp] = V[v[okp], u[okp]] / 255.0; sig += val.reshape(5, len(tg)).mean(0); nf_ += 1
    return tg, sig / max(nf_, 1), nf_

def auswerten(periode, schritt=1, still=False, phase_fest=None):
    """Phase (symmetrischste Faltung), Profil r(z) (Median |u| je 2 cm, Douglas-Peucker), Instanzen, Fotopruefung (jedes `schritt`-te Sichtfoto). Gibt dict oder None."""
    # (4) Phase
    phis = torch.arange(0, periode, 0.005, device=dev); nb = 40; best = (1e9, 0.0)
    for ph in phis:
        u = torch.remainder(Bt[:, 0] - ph + periode / 2, periode) - periode / 2; h = torch.histc(u, bins=nb, min=-periode / 2, max=periode / 2)
        asym = float((h - h.flip(0)).abs().sum() / h.sum().clamp(min=1))
        if asym < best[0]: best = (asym, float(ph))
    phase = best[1] if phase_fest is None else phase_fest; U = torch.remainder(Bt[:, 0] - phase + periode / 2, periode) - periode / 2
    if not still: print("Periode %.3f: Phase %.3f m (Asymmetrie %.3f)" % (periode, phase, best[0]), flush=True)
    # (5) Profil
    zs = np.arange(zlo + 0.05, zhi - 0.05, 0.02); prof = []
    for z in zs:
        s = (Bt[:, 2] >= z) & (Bt[:, 2] < z + 0.02); prof.append(float(U[s].abs().median()) if int(s.sum()) >= 20 else np.nan)
    prof = np.array(prof); ok = ~np.isnan(prof)
    if ok.sum() < 5: return None
    prof = np.clip(np.interp(zs, zs[ok], prof[ok]), 0.01, periode / 2); eps = 0.002; kn = dp(prof, zs, list(range(len(zs))), eps)
    while len(kn) > KNOTEN: eps *= 1.5; kn = dp(prof, zs, list(range(len(zs))), eps)
    knoten = [(float(prof[i]), float(zs[i] + 0.01)) for i in kn]
    if not still: print("Profil: r min %.3f max %.3f m, %d Knoten: %s" % (prof.min(), prof.max(), len(knoten), [(round(r, 3), round(z, 2)) for r, z in knoten]), flush=True)
    # (6) Instanzen + Fotopruefung
    mantel = lambda t: np.array([[welt(t + r * np.cos(2 * np.pi * j / NM), r * np.sin(2 * np.pi * j / NM), z) for r, z in knoten] for j in range(NM)])    # [8, K, 3]
    i0 = int(np.floor((t0 - phase) / periode)); i1 = int(np.ceil((t1 - phase) / periode)); kand = [(i, phase + i * periode) for i in range(i0, i1 + 1) if t0 - 0.2 <= phase + i * periode <= t1 + 0.2]
    def stuetz(t):
        M = mantel(t); out = []
        for j in range(NM):
            for k in range(len(knoten) - 1):
                n = max(2, int(abs(knoten[k + 1][1] - knoten[k][1]) / 0.02)); out.append(M[j, k][None] + (M[j, k + 1] - M[j, k])[None] * np.linspace(0, 1, n)[:, None])
        return np.concatenate(out)
    # Fotopruefung an der SILHOUETTE (Lauf v10: 8 feste Mantellinien koennen je Foto hoechstens 2 auf Kanten treffen -> 50 % nie erreichbar; Mitte Median 0,2 trotz passendem Overlay):
    # je Foto die beiden Umrisslinien Achse +- r(z) * p, p = waagerecht senkrecht zur Blickrichtung; Profil alle 2 cm interpoliert
    zp = np.arange(knoten[0][1], knoten[-1][1] + 1e-6, 0.02); rp = np.interp(zp, [z for _, z in knoten], [r for r, _ in knoten])
    achsen = [np.stack([welt(t, 0, z) for z in zp]) for _, t in kand]                                   # [K,3] je Instanz
    mitte = np.array([welt(t, 0, (zlo + zhi) / 2) for _, t in kand]); treffer = np.zeros(len(kand), int); gesehen = np.zeros(len(kand), int); nf = 0; anteile = [[] for _ in kand]
    fotos = [f for f in sorted(KAM) if os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png"))][::schritt]
    for f in fotos:
        pf = os.path.join(sd, os.path.splitext(f)[0] + ".png")
        k = KAM[f]; R = np.array(k["Rn"]); t_ = np.array(k["tn"]); Cc = np.array(k["C"]); Xc = (R @ mitte.T + t_[:, None]); sicht = (Xc[2] > 3) & (Xc[2] < 40) & (np.abs(Xc[0] / Xc[2]) < 0.55) & (np.abs(Xc[1] / Xc[2]) < 0.55)
        if not sicht.any(): continue
        V = cv2.imread(pf, 0); Vd = cv2.dilate(V, np.ones((2 * PX + 1, 2 * PX + 1), np.uint8)); H, Wd = V.shape; sj = Wd / k["W"]; nf += 1
        for i in np.where(sicht)[0]:
            bl = mitte[i] - Cc; p = np.array([-bl[1], bl[0], 0.0]); p /= max(np.linalg.norm(p), 1e-9)
            S_ = np.concatenate([achsen[i] + rp[:, None] * p[None], achsen[i] - rp[:, None] * p[None]])                    # Silhouettenpunkte [2K,3]
            X = R @ S_.T + t_[:, None]; x = X[0] / X[2]; y = X[1] / X[2]; f1 = 1 + k["params"][3] * (x * x + y * y)
            u = np.round((k["f"] * x * f1 + k["cx"]) * sj).astype(int); v = np.round((k["f"] * y * f1 + k["cy"]) * sj).astype(int); okp = (u >= 0) & (u < Wd) & (v >= 0) & (v < H)
            if okp.mean() < 0.9 or (u[okp].max() - u[okp].min()) < 6: continue                      # Mindestgroesse im Bild > 6 px, sonst keine Aussage
            gesehen[i] += 1; an = float((Vd[v[okp], u[okp]] >= 0.3 * 255).mean()); anteile[i].append(an)
            if an >= KANTE_ANTEIL: treffer[i] += 1
    return dict(periode=periode, phase=phase, U=U, knoten=knoten, mantel=mantel, kand=kand, treffer=treffer, gesehen=gesehen, nf=nf, anteile=anteile,
                guete=float(np.mean([np.median(x) for x in anteile if x])) if any(anteile) else 0.0)

phase_foto = None
if g("--periode_quelle", "foto", str) == "foto":
    tg, sig, nf_ = foto_signal(); s_ = sig - sig.mean(); var = (s_ * s_).mean()
    acf = np.array([((s_[:-s] * s_[s:]).sum() / (len(s_) - s)) / max(var, 1e-9) for s in range(int(PMIN / 0.01), int(PMAX / 0.01))]); lf = np.arange(int(PMIN / 0.01), int(PMAX / 0.01)) * 0.01
    lokf = [i for i in range(4, len(acf) - 4) if acf[i] >= acf[i - 4] and acf[i] >= acf[i + 4] and acf[i] >= acf[i - 1] and acf[i] >= acf[i + 1]]
    print("Fotosignal aus %d Fotos; lokale Maxima der Foto-Autokorrelation:" % nf_, sorted([(round(float(lf[i]), 3), round(float(acf[i]), 2)) for i in lokf], key=lambda x: -x[1])[:6], flush=True)
    if lokf:
        ipf = max(lokf, key=lambda i: acf[i]); periode = float(lf[ipf])
        if 0 < ipf < len(acf) - 1:
            y0, y1, y2 = acf[ipf - 1], acf[ipf], acf[ipf + 1]; den = y0 - 2 * y1 + y2
            if abs(den) > 1e-9: periode += 0.01 * 0.5 * (y0 - y2) / den
        # Phase aus dem gefalteten Fotosignal: Baluster symmetrisch -> Faltung F(u) symmetrisch um die Achse
        best = (1e9, 0.0)
        for ph in np.arange(0, periode, 0.005):
            u = np.remainder(tg - ph + periode / 2, periode) - periode / 2; F = np.histogram(u, bins=24, range=(-periode / 2, periode / 2), weights=sig)[0]
            asym = np.abs(F - F[::-1]).sum() / max(F.sum(), 1e-9)
            if asym < best[0]: best = (asym, float(ph))
        phase_foto = best[1]; print("Periode aus Fotos %.3f m (Autokorrelation %.2f), Phase %.3f (Asymmetrie %.3f)" % (periode, float(acf[ipf]), phase_foto, best[0]), flush=True)
        # Periodenfeinkorrektur ueber die Phasendrift (Lauf v8: Phase lief ueber 20 m um ~1/3 Periode weg = Periodenfehler ~0,5 %): Phase im linken und rechten Drittel getrennt
        def phase_in(m_):
            best_ = (1e9, 0.0)
            for ph in np.arange(0, periode, 0.0025):
                u = np.remainder(tg[m_] - ph + periode / 2, periode) - periode / 2; F = np.histogram(u, bins=24, range=(-periode / 2, periode / 2), weights=sig[m_])[0]
                asym = np.abs(F - F[::-1]).sum() / max(F.sum(), 1e-9)
                if asym < best_[0]: best_ = (asym, float(ph))
            return best_[1]
        L3 = (tg.max() - tg.min()) / 3; ml = tg < tg.min() + L3; mr = tg > tg.max() - L3; pl, pr = phase_in(ml), phase_in(mr)
        dphi = (pr - pl + periode / 2) % periode - periode / 2; nper = (tg[mr].mean() - tg[ml].mean()) / periode
        korr = dphi / nper
        if abs(korr) < 0.02:
            periode += korr; phase_foto = (pl + korr * (tg[ml].mean() - 0) / periode) % periode   # Phase am Nullpunkt t=0 nachziehen
            print("Driftkorrektur: Phase links %.3f rechts %.3f (Differenz %.3f ueber %.1f Perioden) -> Periode %.4f m, Phase %.3f" % (pl, pr, dphi, nper, periode, phase_foto), flush=True)
        else: print("Driftkorrektur verworfen (|%.3f| >= 2 cm): Phasen links/rechts %.3f/%.3f" % (korr, pl, pr), flush=True)
    else: print("Fotosignal ohne Periode - nehme Wolkenperiode", flush=True); periode = pk[0]
elif len(pk) > 1:
    vor = [(auswerten(p, schritt=5, still=True), p) for p in pk]; vor = [(r["guete"] if r else -1, p) for r, p in vor]
    print("Periodenkandidaten (Fotoguete = mittlerer Median-Kantenanteil, jedes 5. Foto):", [(round(p, 3), round(gq, 3)) for gq, p in vor], flush=True); periode = max(vor)[1]
else: periode = pk[0]
if phase_foto is None:
    ip = int(np.argmin(np.abs(lags.cpu().numpy() - periode)))                                    # Feinschritt: Parabel durch Nachbarn
    if 0 < ip < len(lags) - 1:
        y0, y1, y2 = float(ac[ip - 1]), float(ac[ip]), float(ac[ip + 1]); den = y0 - 2 * y1 + y2
        if abs(den) > 1e-9: periode += 0.005 * 0.5 * (y0 - y2) / den
    print("Periode %.3f m (Wolken-Autokorrelation %.2f)" % (periode, float(ac[ip])), flush=True)
E = auswerten(periode, phase_fest=phase_foto)
if E is None: print("Profil zu duenn"); json.dump({"baluster": [], "segmente": []}, open(a[4], "w")); sys.exit(0)
phase, U, knoten, mantel, kand, treffer, gesehen, nf, anteile = E["phase"], E["U"], E["knoten"], E["mantel"], E["kand"], E["treffer"], E["gesehen"], E["nf"], E["anteile"]; inst = []
for n_, ((i, t), tr, ge) in enumerate(zip(kand, treffer, gesehen)):
    s = (U.abs() < periode / 2) & ((Bt[:, 0] - t).abs() < periode / 2)
    inst.append(dict(index=i, t=t, mitte=[float(x) for x in welt(t, 0, (zlo + zhi) / 2)], punkte=int(s.sum()), fotos_gesehen=int(ge), fotos_kante=int(tr), kantenanteil_median=float(np.median(anteile[n_])) if anteile[n_] else None,
                     kantenanteil_q90=float(np.quantile(anteile[n_], 0.9)) if anteile[n_] else None, bestanden=bool(tr >= NFOTO and tr >= FANTEIL * ge)))
best_n = sum(1 for x in inst if x["bestanden"]); print("Instanzen im t-Bereich: %d, fotogeprueft bestanden: %d (Fotos mit Sicht auf die Bruestung: %d)" % (len(inst), best_n, nf), flush=True)
for x in inst: print("  Baluster %3d t %6.2f  Punkte %4d  Fotos gesehen %3d  Kante %3d  Kantenanteil Median %.2f q90 %.2f  %s" % (x["index"], x["t"], x["punkte"], x["fotos_gesehen"], x["fotos_kante"], x["kantenanteil_median"] or 0, x["kantenanteil_q90"] or 0, "OK" if x["bestanden"] else "--"))
# Sichtkontrolle: ALLE Instanzen (auch nicht bestandene) als eigene Datei fuer das Overlay
dbg = []
for x in inst:
    M = mantel(x["t"]); dbg.append([[float(v) for v in welt(x["t"], 0, knoten[0][1])], [float(v) for v in welt(x["t"], 0, knoten[-1][1])], 13 if x["bestanden"] else 14, 1.0])
    for j in range(0, NM, 2):
        for k in range(len(knoten) - 1): dbg.append([[float(v) for v in M[j, k]], [float(v) for v in M[j, k + 1]], 13 if x["bestanden"] else 14, 1.0])
json.dump({"segmente": dbg}, open(a[4] + ".alle.json", "w"))

# (7) Segmente quelle 13
seg = []
for x in inst:
    if not x["bestanden"]: continue
    t = x["t"]; M = mantel(t); seg.append([[float(v) for v in welt(t, 0, knoten[0][1])], [float(v) for v in welt(t, 0, knoten[-1][1])], 13, 1.0])
    for j in range(NM):
        for k in range(len(knoten) - 1): seg.append([[float(v) for v in M[j, k]], [float(v) for v in M[j, k + 1]], 13, 1.0])
json.dump({"band": [zlo, zhi], "fassade": dict(mitte=[float(x) for x in c2], richtung=[float(x) for x in d], q0=q0, t0=t0, t1=t1), "periode": periode, "phase": phase,
           "profil": knoten, "anzahl_fotogeprueft": best_n, "baluster": inst, "segmente": seg}, open(a[4], "w"), indent=1)
print("fertig: %d Baluster, %d Segmente" % (best_n, len(seg)))
