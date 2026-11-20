"""gitter_verfeinern.py - 3D-Kantengitter direkt gegen die 2D-Stabilitaetskarten verfeinern (Idee SketchSplat/EMAP, Eigenbau, GPU).
Endpunkte jedes Segments so verschieben, dass die Projektion in allen SEHENDEN Fotos auf Kanten liegt; danach Topologie-Operationen.
Aufruf: gitter_verfeinern.py GITTER_IN.json KAM.json STABILDIR OUT.json [--wolke KANTEN.npz] [--schritte 60] [--maxshift 0.15] [--lr 0.01]
        [--maxwinkel 5] [--maxdist 40] [--merge 0.06] [--kollinear 0.04] [--kollwinkel 3] [--stuetz_px 4] [--loesch 0.70] [--nur N]
Verfahren:
 1. Je Foto Distanztransformation der Kantenmaske (Karte >= 0,3*255) = Verlustbild, Deckel 20 px; auf der GPU als uint8 (0,1 px Aufloesung; 440 Karten = 1,3 GB,
    float16 waere 2,6 GB > VRAM-Budget 2 GB). Zur Abtastung wird die Karte je Foto nach float gewandelt (grid_sample, bilinear).
 2. Sehende Fotos je Segment: >= 12 der 24 Abtastpunkte im Bild UND sichtbar per Z-Puffer der Wolke (Logik aus gitter_pruefblatt.py) UND Mittelpunkt < maxdist m.
    Verlust = Mittel der Distanz (px) der 24 Abtastpunkte, ueber die sehenden Fotos gemittelt, ueber die Segmente laengengewichtet summiert.
    Optimierung der 6 Endpunktkoordinaten je Segment: Adam (lr 1 cm, 60 Schritte); Verschiebung je Endpunkt hart <= maxshift (tanh-Reparametrisierung),
    Richtungsaenderung > maxwinkel Grad per quadratischer Strafe. Alle Segmente gleichzeitig (Batch), Schleife nur ueber die Fotos.
 3. Topologie: (a) Endpunkte < merge m verschmelzen (Mittel; nie die beiden Enden desselben Segments); (b) kollineare, sich beruehrende/ueberlappende Segmente
    (Winkel < kollwinkel Grad, Senkrechtabstand < kollinear m, Luecke < kollinear m) zu einem vereinen; (c) Segmente loeschen, die in >= loesch der sehenden Fotos
    keine Kante stuetzen (Median-Distanz der sichtbaren Abtastpunkte > stuetz_px) - nie Quelle 4/7 (Helm/Pfeiler-Formen), nie Segmente ohne sehende Fotos.
 4. OUT.json im Eingabeformat (uebrige Schluessel durchgereicht) + "verfeinerung": {verschoben_median_cm, verschmolzen, vereint, geloescht, ...}.
Keine Objektkonstanten; alles kommt aus den uebergebenen Dateien."""
import sys, os, json, time, numpy as np, cv2, torch
from concurrent.futures import ThreadPoolExecutor
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
if len(a) < 5: print(__doc__); sys.exit(2)
GIN, KAMF, SD, OUT = a[1], a[2], a[3], a[4]
SCHRITTE, MAXSHIFT, LR, MAXWINKEL, MAXDIST = g("--schritte", 60, int), g("--maxshift", 0.05), g("--lr", 0.01), g("--maxwinkel", 5.0), g("--maxdist", 40.0)
# maxshift-Standard 0,05 (nicht 0,15): gemessen 9.11. am Kaufhaus v7 - 15 cm: Abdeckung Wolkenkanten z<12 0,90->0,86, 12-15 0,82->0,75 (Doppellinien rasten auf EINE Kante);
# 8 cm: 0,88/0,78; 5 cm: 0,89/0,80 (Tor: nicht > 2 Punkte schlechter) bei Stuetzung 0,469->0,50. Siehe modelle/archiv/LOG_VERFEINERN_2026-11-09.md.
MERGE, KOLL, KOLLW, STUETZ_PX, LOESCH, NUR = g("--merge", 0.06), g("--kollinear", 0.04), g("--kollwinkel", 3.0), g("--stuetz_px", 4.0), g("--loesch", 0.70), g("--nur", 0, int)
THR, NS, MINSICHT, DECKEL, Q = 0.3, 24, 12, 20.0, 10.0   # Kantenschwelle, Abtastpunkte je Segment, Mindestzahl sichtbarer Punkte, DT-Deckel px, DT-Quantisierung (1/Q px)
SCHUTZ = {4, 7}                                             # Quellen, die (c) nie loescht (Helm-/Pfeiler-Formen)
dev = "cuda"; T0 = time.time()
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
tot = torch.cuda.get_device_properties(0).total_memory; torch.cuda.set_per_process_memory_fraction(min(1.0, 2000 * 2 ** 20 / tot))
def log(*s): print("[%6.1f s]" % (time.time() - T0), *s, flush=True)

# ---------------- Eingaben ----------------
D = json.load(open(GIN)); S = D["segmente"]
P0 = torch.tensor([s[0] for s in S], device=dev, dtype=torch.float32); P1 = torch.tensor([s[1] for s in S], device=dev, dtype=torch.float32)
QU = np.array([int(s[2]) for s in S]); SC = np.array([float(s[3]) if len(s) > 3 else 0.0 for s in S]); N = len(S)
KAM = json.load(open(KAMF)); fs = [f for f in sorted(KAM) if os.path.exists(os.path.join(SD, os.path.splitext(f)[0] + ".png"))]
if NUR: fs = fs[:NUR]
WOLKE = None
if "--wolke" in a:
    W_ = np.load(g("--wolke", "", str)); W_ = W_["P"] if hasattr(W_, "files") else W_; WOLKE = torch.tensor(W_[:, :3], device=dev, dtype=torch.float32)
log("Segmente", N, "Fotos mit Karte", len(fs), "Wolke", None if WOLKE is None else tuple(WOLKE.shape))

# ---------------- 1. Distanztransformation je Foto (CPU parallel, GPU uint8) ----------------
def dt_karte(f):
    V = cv2.imread(os.path.join(SD, os.path.splitext(f)[0] + ".png"), 0)
    d = cv2.distanceTransform((V < THR * 255).astype(np.uint8), cv2.DIST_L2, 5)        # Abstand jedes Pixels zur naechsten Kante (Kante = 0)
    return np.minimum(d * Q, DECKEL * Q).astype(np.uint8)
with ThreadPoolExecutor(8) as ex: karten = list(ex.map(dt_karte, fs))
DT = {f: torch.from_numpy(k).to(dev) for f, k in zip(fs, karten)}; del karten
log("DT-Karten auf GPU: %.2f GB" % (sum(v.numel() for v in DT.values()) / 2 ** 30))

# ---------------- Kamera / Projektion ----------------
def kam_t(k, karte):
    R = torch.tensor(k["Rn"], device=dev, dtype=torch.float32); t = torch.tensor(k["tn"], device=dev, dtype=torch.float32); sj = karte.shape[1] / k["W"]
    return dict(R=R, t=t, f=k["f"] * sj, cx=k["cx"] * sj, cy=k["cy"] * sj, k1=k["params"][3], H=karte.shape[0], W=karte.shape[1], sj=sj)
KT = {f: kam_t(KAM[f], DT[f]) for f in fs}
def projiziere(c, X3):
    """X3 (...,3) Welt -> u, v (Karten-Pixel), z (Kameratiefe)."""
    X = X3 @ c["R"].T + c["t"]; z = X[..., 2]; zc = z.clamp(min=0.3); x = X[..., 0] / zc; y = X[..., 1] / zc; f1 = 1 + c["k1"] * (x * x + y * y)
    return c["f"] * x * f1 + c["cx"], c["f"] * y * f1 + c["cy"], z
def zpuffer(c, ztol=0.5):
    """Z-Puffer der Wolke bei 1/4 Aufloesung (3x3-Splat, 9x9-Lochfuellung) - Logik aus gitter_pruefblatt.py."""
    if WOLKE is None: return None
    uw, vw, zw = projiziere(c, WOLKE); m = zw > 0.5; Hq, Wq = c["H"] // 4 + 1, c["W"] // 4 + 1
    uq = (uw[m] / 4).long(); vq = (vw[m] / 4).long(); inb = (uq >= 0) & (uq < Wq) & (vq >= 0) & (vq < Hq)
    zb = torch.full((Hq * Wq,), 1e9, device=dev); zb.scatter_reduce_(0, vq[inb] * Wq + uq[inb], zw[m][inb], reduce="amin"); zb = zb.view(Hq, Wq)
    zb = -torch.nn.functional.max_pool2d(-zb[None, None], 3, 1, 1)[0, 0]
    leer = zb > 1e8; zb7 = -torch.nn.functional.max_pool2d(-zb[None, None], 9, 1, 4)[0, 0]; return torch.where(leer, zb7, zb)
TT = torch.linspace(0, 1, NS, device=dev)
def abtast(A, B): return A[:, None, :] + (B - A)[:, None, :] * TT[None, :, None]            # (K,NS,3)

# ---------------- 2. Sichtbarkeit je (Segment, Foto) ----------------
def sicht_paare(A, B):
    """Je Foto: Indizes der sehenden Segmente + Maske (K,NS) der sichtbaren Abtastpunkte (im Bild, Z-Puffer, Tiefe)."""
    paare = {}; X = abtast(A, B)
    for f in fs:
        c = KT[f]; u, v, z = projiziere(c, X); ok = (z > 1) & (z < MAXDIST) & (u >= 0) & (u < c["W"] - 1) & (v >= 0) & (v < c["H"] - 1)
        zb = zpuffer(c)
        if zb is not None:
            Hq, Wq = zb.shape; uq = (u / 4).long().clamp(0, Wq - 1); vq = (v / 4).long().clamp(0, Hq - 1); ok = ok & (z <= zb[vq, uq] + 0.5)
        n = ok.sum(1); idx = torch.nonzero(n >= MINSICHT)[:, 0]
        if len(idx): paare[f] = (idx, ok[idx])
    return paare
with torch.no_grad(): paare = sicht_paare(P0, P1)
anz = torch.zeros(N, device=dev)
for f, (idx, _) in paare.items(): anz[idx] += 1
log("Sichtpaare %d | Segmente mit >=1 Foto %d / %d | Fotos je Segment Median %.0f" % (sum(len(v[0]) for v in paare.values()), int((anz > 0).sum()), N, anz[anz > 0].median().item() if (anz > 0).any() else 0))

# ---------------- Verlust ----------------
def distanzen(f, A, B, idx, vis):
    """Mittlere DT-Distanz (px) je Segment im Foto f, nur sichtbare Abtastpunkte; zusaetzlich die rohen Distanzen (K,NS) (unsichtbar = nan)."""
    c = KT[f]; X = abtast(A[idx], B[idx]); u, v, _ = projiziere(c, X)
    grid = torch.stack([u / (c["W"] - 1) * 2 - 1, v / (c["H"] - 1) * 2 - 1], -1)[None]                           # (1,K,NS,2)
    d = torch.nn.functional.grid_sample(DT[f][None, None].float() / Q, grid, mode="bilinear", padding_mode="border", align_corners=True)[0, 0]
    vis = vis.float(); return (d * vis).sum(1) / vis.sum(1).clamp(min=1), torch.where(vis > 0, d, torch.full_like(d, float("nan")))
def verlust(A, B, paare, fotos=None):
    """Summe der mittleren Distanzen je Segment ueber die Fotos (fotos=None: alle) + Anzahl Fotos je Segment."""
    Ls = torch.zeros(N, device=dev); cnt = torch.zeros(N, device=dev)
    for f in (fotos or paare):
        idx, vis = paare[f]; m, _ = distanzen(f, A, B, idx, vis); Ls = Ls.index_add(0, idx, m); cnt = cnt.index_add(0, idx, torch.ones(len(idx), device=dev))
    return Ls, cnt
CHUNK = 24   # Fotos je Rueckwaertsschritt (Gradienten-Akkumulation): grid_sample haelt sonst je Foto die 12-MB-Float-Karte im Graphen -> 440 Fotos = 5 GB (OOM)

# ---------------- Optimierung ----------------
L0 = (P1 - P0).norm(dim=1); w = (L0 / L0.mean()).detach(); dir0 = (P1 - P0) / L0.clamp(min=1e-6)[:, None]
FEST = torch.tensor(np.isin(QU, list(SCHUTZ)), device=dev)                           # Formen (Helm/Pfeiler) sind als Ganzes gefittet: Einzelsegmente nicht bewegen (sonst zerfallen die Ringe/Kanten)
FREI = (~FEST).float()[:, None, None]
d = torch.zeros(N, 2, 3, device=dev, requires_grad=True); opt = torch.optim.Adam([d], lr=LR)
with torch.no_grad(): Ls0, cnt = verlust(P0, P1, paare); hat = cnt > 0; cntc = cnt.clamp(min=1); Lseg0 = Ls0 / cntc; wn = w / w[hat].sum()
log("Start: mittlere Distanz %.2f px (laengengew. %.2f) ueber %d Segmente mit Fotos" % (Lseg0[hat].mean(), (Lseg0 * w)[hat].sum() / w[hat].sum(), int(hat.sum())))
def lage(d): dd = MAXSHIFT * torch.tanh(d) * FREI; return P0 + dd[:, 0], P1 + dd[:, 1]
fl = list(paare); chunks = [fl[i:i + CHUNK] for i in range(0, len(fl), CHUNK)]
for it in range(SCHRITTE):
    opt.zero_grad(); tot = 0.0
    for ch in chunks:                                                                                                # Daten-Term chunkweise rueckwaerts (Speicher)
        A, B = lage(d); Ls, _ = verlust(A, B, paare, ch); teil = (wn * Ls / cntc)[hat].sum(); teil.backward(); tot += teil.item()
    A, B = lage(d); dir1 = (B - A); dir1 = dir1 / dir1.norm(dim=1, keepdim=True).clamp(min=1e-6)
    ang = torch.rad2deg(torch.atan2(torch.cross(dir0, dir1, dim=1).norm(dim=1), (dir0 * dir1).sum(1)))                 # stabil bei 0 Grad (acos nicht)
    strafe = ((torch.relu(ang - MAXWINKEL) ** 2 * 2.0) * wn)[hat].sum(); strafe.backward(); opt.step()                 # 1 Grad zu viel = 2 px
    if it % 10 == 0 or it == SCHRITTE - 1: log("Schritt %2d  Verlust %.3f px (+Strafe %.4f)  Winkel max %.1f Grad  Verschiebung max %.1f cm" % (it, tot, strafe.item(), ang.max().item(), 100 * MAXSHIFT * torch.tanh(d).norm(dim=2).max().item()))
with torch.no_grad():
    A, B = lage(d); A = A.detach(); B = B.detach(); shift = (MAXSHIFT * torch.tanh(d) * FREI).norm(dim=2)[hat & ~FEST].flatten() * 100
    Ls1, _ = verlust(A, B, paare); Lseg1 = Ls1 / cntc
    # Segmente ohne Foto behalten ihre Lage (tanh(0)=0 -> automatisch)
    stat = dict(verschoben_median_cm=round(shift.median().item(), 2), verschoben_mittel_cm=round(shift.mean().item(), 2), verschoben_q90_cm=round(shift.quantile(0.9).item(), 2),
                distanz_vorher_px=round(Lseg0[hat].mean().item(), 3), distanz_nachher_px=round(Lseg1[hat].mean().item(), 3), segmente_mit_fotos=int(hat.sum()), schritte=SCHRITTE, maxshift_m=MAXSHIFT)
log("Verschiebung Median %.2f cm, Q90 %.2f cm | Distanz %.3f -> %.3f px" % (stat["verschoben_median_cm"], stat["verschoben_q90_cm"], stat["distanz_vorher_px"], stat["distanz_nachher_px"]))

# ---------------- 3. Topologie ----------------
def komponenten(n, paare_ij):
    """Union-Find ueber Kanten (i,j) -> Label je Knoten."""
    lab = np.arange(n)
    def find(x):
        while lab[x] != x: lab[x] = lab[lab[x]]; x = lab[x]
        return x
    for i, j in paare_ij:
        ri, rj = find(i), find(j)
        if ri != rj: lab[max(ri, rj)] = min(ri, rj)
    return np.array([find(i) for i in range(n)])
A_ = A.clone(); B_ = B.clone(); qu = QU.copy(); sc = SC.copy()
if "--nur_opt" in a:                                                                   # Diagnose: nur Optimierung, keine Topologie
    seg_out = [[[float(x) for x in A_[i]], [float(x) for x in B_[i]], int(qu[i]), round(float(sc[i]), 4)] for i in range(len(A_))]
    out = {k: v for k, v in D.items() if k != "segmente"}; out["segmente"] = seg_out; out["verfeinerung"] = stat; json.dump(out, open(OUT, "w")); log("geschrieben (nur Optimierung)", OUT); sys.exit(0)
# (a) Endpunkte verschmelzen
with torch.no_grad():
    E = torch.cat([A_, B_], 0); M2 = len(E); dist = torch.cdist(E, E); seg_id = torch.arange(M2, device=dev) % N
    nah = (dist < MERGE) & (seg_id[:, None] != seg_id[None, :]); nah = torch.triu(nah, 1); ij = torch.nonzero(nah).cpu().numpy()
lab = komponenten(M2, ij); En = E.cpu().numpy().copy(); verschmolzen = 0; festE = np.tile(FEST.cpu().numpy(), 2)
for l in np.unique(lab[ij.flatten()]) if len(ij) else []:
    m = lab == l; fm = m & festE; En[m] = En[fm].mean(0) if fm.any() else En[m].mean(0); verschmolzen += int(m.sum()) - 1   # Form-Endpunkte bleiben, andere rasten darauf ein
A_ = torch.tensor(En[:N], device=dev); B_ = torch.tensor(En[N:], device=dev)
behalten = ((B_ - A_).norm(dim=1) > 0.02).cpu().numpy(); entartet = int((~behalten).sum())
A_, B_, qu, sc = A_[behalten], B_[behalten], qu[behalten], sc[behalten]
log("(a) verschmolzen %d Endpunkte (%d Gruppen), %d entartete Segmente entfernt" % (verschmolzen, len(np.unique(lab[ij.flatten()])) if len(ij) else 0, entartet))
# (b) kollineare Segmente vereinen
with torch.no_grad():
    n = len(A_); L = (B_ - A_).norm(dim=1); U = (B_ - A_) / L.clamp(min=1e-6)[:, None]
    def senk(Pt):   # Senkrechtabstand der Punkte Pt (n,3) zu allen Linien (A_,U): (n_punkte, n_linien)
        Dv = Pt[:, None, :] - A_[None, :, :]; proj = (Dv * U[None]).sum(2); return (Dv - proj[..., None] * U[None]).norm(dim=2), proj
    fest_b = torch.tensor(np.isin(qu, list(SCHUTZ)), device=dev)
    kand = torch.zeros((n, n), dtype=torch.bool, device=dev); BL = 512                                                  # blockweise (OOM 9.11. bei 3135 Segmenten)
    for j0 in range(0, n, BL):
        j1 = min(n, j0 + BL); cosw = (U[j0:j1] @ U.T).abs().clamp(max=1); parallel = torch.rad2deg(torch.acos(cosw)) < KOLLW
        sA, pA = senk(A_[j0:j1]); sB, pB = senk(B_[j0:j1])                                                             # [j, i]: Endpunkte von j gegen Linie i
        nahe = torch.maximum(sA, sB) < KOLL; lo = torch.minimum(pA, pB); hi = torch.maximum(pA, pB)
        beruehrt = torch.maximum(lo - L[None, :], -hi) < KOLL
        kand[j0:j1] = parallel & nahe & beruehrt & ~fest_b[j0:j1, None] & ~fest_b[None, :]                          # Formen nie vereinen
        del cosw, parallel, sA, pA, sB, pB, nahe, lo, hi, beruehrt
    kand = kand & kand.T; kand = torch.triu(kand, 1); ij = torch.nonzero(kand).cpu().numpy()
lab = komponenten(n, ij); An = A_.cpu().numpy(); Bn = B_.cpu().numpy(); Ln = L.cpu().numpy(); Un = U.cpu().numpy(); vereint = 0; neuA, neuB, neuq, neus = [], [], [], []
for l in np.unique(lab):
    m = np.where(lab == l)[0]
    if len(m) == 1: neuA.append(An[m[0]]); neuB.append(Bn[m[0]]); neuq.append(qu[m[0]]); neus.append(sc[m[0]]); continue
    ref = Un[m[np.argmax(Ln[m])]]; dirs = Un[m] * np.sign(Un[m] @ ref)[:, None]; u = (dirs * Ln[m, None]).sum(0); u /= np.linalg.norm(u)
    c = ((An[m] + Bn[m]) / 2 * Ln[m, None]).sum(0) / Ln[m].sum(); pts = np.vstack([An[m], Bn[m]]); t = (pts - c) @ u
    neuA.append(c + u * t.min()); neuB.append(c + u * t.max()); neuq.append(qu[m[np.argmax(Ln[m])]]); neus.append(sc[m].max()); vereint += len(m) - 1
A_ = torch.tensor(np.array(neuA), device=dev, dtype=torch.float32); B_ = torch.tensor(np.array(neuB), device=dev, dtype=torch.float32); qu = np.array(neuq); sc = np.array(neus)
log("(b) vereint %d Segmente -> %d" % (vereint, len(A_)))
# (c) Segmente ohne Kantenstuetzung loeschen
with torch.no_grad():
    N = len(A_); paare2 = sicht_paare(A_, B_); seh = torch.zeros(N, device=dev); ohne = torch.zeros(N, device=dev)
    for f, (idx, vis) in paare2.items():
        _, draw = distanzen(f, A_, B_, idx, vis); med = torch.nanmedian(draw, dim=1).values
        seh[idx] += 1; ohne[idx] += (med > STUETZ_PX).float()
    anteil = ohne / seh.clamp(min=1); schutz = torch.tensor(np.isin(qu, list(SCHUTZ)), device=dev)
    loesch = (seh > 0) & (anteil >= LOESCH) & ~schutz
    stuetz_anteil = 1 - anteil[seh > 0]
log("(c) geloescht %d (von %d mit Fotos; %d ohne Fotos behalten, %d geschuetzt) | Stuetzanteil je Segment Median %.2f" % (int(loesch.sum()), int((seh > 0).sum()), int((seh == 0).sum()), int(((seh > 0) & (anteil >= LOESCH) & schutz).sum()), stuetz_anteil.median().item()))
keep = (~loesch).cpu().numpy(); A_ = A_[~loesch].cpu().numpy(); B_ = B_[~loesch].cpu().numpy(); qu = qu[keep]; sc = sc[keep]

# ---------------- 4. Ausgabe ----------------
seg_out = [[[float(x) for x in A_[i]], [float(x) for x in B_[i]], int(qu[i]), round(float(sc[i]), 4)] for i in range(len(A_))]
stat.update(verschmolzen=verschmolzen, entartet_entfernt=entartet, vereint=vereint, geloescht=int(loesch.sum()), n_vorher=len(S), n_nachher=len(seg_out),
            laenge_vorher_m=round(L0.sum().item(), 1), laenge_nachher_m=round(float(np.linalg.norm(B_ - A_, axis=1).sum()), 1), fotos=len(fs), laufzeit_s=round(time.time() - T0, 1),
            parameter=dict(schritte=SCHRITTE, lr=LR, maxshift=MAXSHIFT, maxwinkel=MAXWINKEL, maxdist=MAXDIST, merge=MERGE, kollinear=KOLL, kollwinkel=KOLLW, stuetz_px=STUETZ_PX, loesch=LOESCH, thr=THR, abtast=NS, deckel_px=DECKEL),
            quelle=GIN, kameras=KAMF, stabil=SD)
out = {k: v for k, v in D.items() if k != "segmente"}; out["segmente"] = seg_out; out["verfeinerung"] = stat
json.dump(out, open(OUT, "w")); log("geschrieben", OUT, json.dumps({k: v for k, v in stat.items() if k not in ("parameter", "quelle", "kameras", "stabil")}))
