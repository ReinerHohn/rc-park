"""gitter_kurven.py - Kettenbildung von 3D-Kantenpunkten (Tiefen-Sweep) zu geordneten Zuegen mit Modellwahl Gerade / Kreisbogen / kubische Bezier
(Idee: 3D Curvix / 3D Edge Sketch, Brown/Kimia; Eigenbau, modelle/RECHERCHE_KANTENGITTER_NEU_2026-11-09.md Eintrag 2).
Aufruf: gitter_kurven.py SWEEP.npz[,SWEEP2.npz,...] GITTER_IN.json OUT.json [--kam kam_lot2.json --stabil STABILDIR [--wolke KANTEN.npz --ztol 0.5]] [--ohne_verbinden] [--vox 0.06] [--kmin 3] [--tol 0.03] [--minlen 0.3] [--minpkt 8] [--rlink 0.10] [--winkel 30]
        [--k 12] [--lin 0.5] [--maxabw 0.10] [--rand 2.0] [--abtast 0.10] [--kref 0]
Schritte: (1) Konsens: Voxel `vox`, nur Voxel mit >= kmin verschiedenen Referenzfotos (`ref`), Mittelpunkt je Voxel (GPU).
          (2) Punkte, die ein Gitter-Segment schon erklaert (Abstand < vox), fallen weg -> Kurvenkandidaten.
          (3) Tangente je Punkt per PCA ueber k Nachbarn (GPU, pytorch3d knn); Linearitaetsfilter lambda2/lambda1 < lin;
              Kettenbildung: je Punkt EIN Vorwaerts- und EIN Rueckwaertsnachbar (Abstand < rlink, Winkel Verbindung/Tangente < winkel, Tangenten
              untereinander < winkel); Kante nur bei Gegenseitigkeit -> Grad <= 2 (1D-Mannigfaltigkeit), Traversal -> geordnete Ketten.
          (4) Modellwahl je Kette (0,5-Regel): Gerade wenn max. Abweichung < tol; sonst Kreisbogen (Ebene per PCA, Kreis-Fit Kasa + Gauss-Newton)
              wenn < tol und halbe Geradenabweichung; sonst kubische Bezier (LS, Chord-Length); sonst Teilung an der groessten Abweichung (max. 4 Teile).
          (5) Ausgabe: Eingabegitter + neue Segmente [p0,p1,quelle,score] (quelle 10 Bogen, 11 Bezier, 12 Gerade aus Kette), Schluessel "kurven";
              OUT_neu.json = nur die neuen Segmente (fuer gitter_overlay.py), OUT.bericht.json = Zahlen, OUT_abgelehnt.json = von der Fotopruefung verworfene.
          (4b) Fragmente verbinden (ko-zirkular: Ebene +-10 Grad, Zentrum +-8 cm, Radius +-5 cm, Luecke < 40 cm; kollinear: < 3 Grad, < 4 cm, Luecke < 30 cm), Neufit.
          (4c) Fotopruefung PFLICHT mit --kam/--stabil: jedes Stueck gegen die Stabilitaetskarten (>= nmin Fotos mit >= stuetz der Punkte auf Kante UND mehr Ja als Nein).
Score je Segment = mittlerer Sweep-Score `s` der Kettenpunkte (Daten, kein Handwert). Quelle 10/11/12 sind KEINE Wahrheit: Pruefung per Overlay (Regel 3)."""
import sys, os, json, time, argparse
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import numpy as np, torch
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from gpu_knn import min_abstand
sys.path.insert(0, "/media/oem/scan/p3d_site"); from pytorch3d.ops import knn_points
DEV = "cuda"
Q_BOGEN, Q_BEZIER, Q_GERADE = 10, 11, 12


def konsens(P, ref, s, vox, kmin):
    """Voxel mit >= kmin verschiedenen Referenzfotos; Rueckgabe Mittelpunkt, Anzahl Refs, mittlerer Score (alles GPU)."""
    Pt = torch.as_tensor(P, device=DEV); rt = torch.as_tensor(ref, device=DEV).long(); st = torch.as_tensor(s, device=DEV)
    g = torch.floor(Pt / vox).long() + 20000; key = (g[:, 0] * 40000 + g[:, 1]) * 40000 + g[:, 2]
    u, inv = torch.unique(key, return_inverse=True); nv = len(u)
    mult = int(rt.max()) + 1; vr = torch.unique(inv * mult + rt) // mult; nref = torch.bincount(vr, minlength=nv)       # verschiedene Refs je Voxel
    n = torch.bincount(inv, minlength=nv).float()
    C = torch.zeros(nv, 3, device=DEV).index_add_(0, inv, Pt) / n[:, None]; sm = torch.zeros(nv, device=DEV).index_add_(0, inv, st) / n
    keep = nref >= kmin
    return C[keep].cpu().numpy(), nref[keep].cpu().numpy(), sm[keep].cpu().numpy()


def segment_punkte(S, schritt):
    out = []
    for sg in S:
        a = np.array(sg[0], np.float32); b = np.array(sg[1], np.float32); n = max(2, int(np.linalg.norm(b - a) / schritt) + 1)
        out.append(a + (b - a) * np.linspace(0, 1, n, dtype=np.float32)[:, None])
    return np.vstack(out)


def tangenten_und_ketten(X, k, rlink, winkel, lin):
    """PCA-Tangente je Punkt (Nachbarn im Radius ~rlink), Linearitaet, Glaettung (Projektion auf lokale Gerade = Moving-Least-Squares 1. Ordnung,
    nimmt den Voxel-Treppenjitter weg), dann Verkettung als gieriges Slot-Matching: Kandidatenkanten (Abstand < rlink, Winkel Verbindung/Tangente
    < winkel, Tangenten untereinander < winkel) nach Abstand sortiert; eine Kante kommt, wenn bei BEIDEN Punkten der zugewandte Slot
    (vorn/hinten entlang der eigenen Tangente) noch frei ist -> Grad <= 2 (1D-Mannigfaltigkeit). Rueckgabe nb (M,2), Xg (geglaettet), tang, linmass."""
    Xt = torch.as_tensor(X, device=DEV)[None]; kk = min(k + 1, len(X))
    r = knn_points(Xt, Xt, K=kk); idx = r.idx[0]; d = r.dists[0].sqrt()                       # idx[:,0] = Punkt selbst
    rp = max(rlink * 1.5, 0.15); w = (d < rp).float()                                        # +-2 Nachbarn bei 6-cm-Abstand
    N = Xt[0][idx]; m = (N * w[..., None]).sum(1) / w.sum(1).clamp(min=1)[:, None]; D = (N - m[:, None]) * w[..., None]
    cov = torch.einsum("nki,nkj->nij", D, D) / w.sum(1).clamp(min=1)[:, None, None]
    ev, vec = torch.linalg.eigh(cov.cpu()); ev, vec = ev.to(DEV), vec.to(DEV)                    # aufsteigend; CUDA-eigh (cusolver) forderte 3,3 GiB Arbeitsspeicher fuer 13k 3x3-Matrizen -> CPU
    tang = vec[:, :, 2]; linm = 1 - ev[:, 1] / ev[:, 2].clamp(min=1e-12); genug = w.sum(1) >= 3      # selbst + 2
    gut = (linm >= lin) & genug
    Xg = m + ((Xt[0] - m) * tang).sum(1, keepdim=True) * tang                                   # Glaettung
    Xg = torch.where(gut[:, None], Xg, Xt[0])
    # Beinahe-Doppelte nach der Glaettung (zwei Voxelmittel auf derselben lokalen Geraden, < vox/4) zusammenlegen: Richtung sonst unbestimmt, Slots blockiert
    r2 = knn_points(Xg[None], Xg[None], K=kk); ji = r2.idx[0][:, 1:]; dj = r2.dists[0][:, 1:].sqrt(); ar = torch.arange(len(X), device=DEV)
    doppelt = ((dj < rlink / 4) & (ji < ar[:, None])).any(1); behalten = ~doppelt
    Xg, tang, linm, gut = Xg[behalten], tang[behalten], linm[behalten], gut[behalten]; kk = min(kk, len(Xg))
    r2 = knn_points(Xg[None], Xg[None], K=kk); ji = r2.idx[0][:, 1:]; dj = r2.dists[0][:, 1:].sqrt()
    vec_ij = Xg[ji] - Xg[:, None]; cosv = (vec_ij * tang[:, None]).sum(-1) / dj.clamp(min=1e-9)
    cosj = -(vec_ij * tang[ji]).sum(-1) / dj.clamp(min=1e-9)                                     # Richtung von j aus gesehen
    cost = (tang[ji] * tang[:, None]).sum(-1).abs(); cw = float(np.cos(np.radians(winkel)))
    ok = (dj < rlink) & (cost > cw) & (cosv.abs() > cw) & (cosj.abs() > cw) & gut[:, None] & gut[ji]
    ii = torch.arange(len(Xg), device=DEV)[:, None].expand_as(ji)
    I = ii[ok]; J = ji[ok]; Dd = dj[ok]; Si = (cosv[ok] > 0).long(); Sj = (cosj[ok] > 0).long()
    halt = I < J; I, J, Dd, Si, Sj = I[halt], J[halt], Dd[halt], Si[halt], Sj[halt]            # jede ungerichtete Kante einmal (i<j)
    o = torch.argsort(Dd); I, J, Si, Sj = (t[o].cpu().numpy() for t in (I, J, Si, Sj))
    slot = np.full((len(Xg), 2), -1, np.int64)
    for a_, b_, sa, sb in zip(I, J, Si, Sj):
        if slot[a_, sa] < 0 and slot[b_, sb] < 0: slot[a_, sa] = b_; slot[b_, sb] = a_
    return slot, Xg.cpu().numpy(), tang.cpu().numpy(), linm.cpu().numpy(), behalten.cpu().numpy()


def ketten_traversieren(nb):
    M = len(nb); besucht = np.zeros(M, bool); grad = (nb >= 0).sum(1); ketten = []
    def lauf(start):
        kette = [start]; besucht[start] = True; prev = -1; cur = start
        while True:
            nxt = [j for j in nb[cur] if j >= 0 and j != prev and not besucht[j]]
            if not nxt: break
            prev, cur = cur, int(nxt[0]); kette.append(cur); besucht[cur] = True
        return kette
    for i in np.where(grad == 1)[0]:
        if not besucht[i]: ketten.append(lauf(int(i)))
    for i in np.where(grad == 2)[0]:                                                             # Reste = Zyklen
        if not besucht[i]: ketten.append(lauf(int(i)))
    return ketten


# ---- Modelle ----
def fit_gerade(X):
    c = X.mean(0); _, _, vt = np.linalg.svd(X - c, full_matrices=False); d = vt[0]; t = (X - c) @ d
    dev = np.linalg.norm((X - c) - t[:, None] * d, axis=1)
    return dict(typ="gerade", _X=X, punkte=[(c + t.min() * d).tolist(), (c + t.max() * d).tolist()], abweichung_m=float(dev.max()), dev=dev, laenge_m=float(t.max() - t.min()))


def fit_bogen(X, abtast):
    c = X.mean(0); _, sv, vt = np.linalg.svd(X - c, full_matrices=False); nrm = vt[2]; e1 = vt[0]; e2 = np.cross(nrm, e1)
    Y = np.stack([(X - c) @ e1, (X - c) @ e2], 1); h = (X - c) @ nrm
    A = np.column_stack([2 * Y, np.ones(len(Y))]); b = (Y ** 2).sum(1)
    try: sol = np.linalg.lstsq(A, b, rcond=None)[0]
    except np.linalg.LinAlgError: return None
    cx, cy = sol[0], sol[1]; R2 = sol[2] + cx * cx + cy * cy
    if R2 <= 0: return None
    R = float(np.sqrt(R2)); cc = np.array([cx, cy])
    for _ in range(10):                                                                           # Gauss-Newton geometrisch
        v = Y - cc; rn = np.linalg.norm(v, axis=1); res = rn - R
        J = np.column_stack([-v / rn[:, None].clip(1e-9), -np.ones(len(Y))])
        try: dx = np.linalg.lstsq(J, -res, rcond=None)[0]
        except np.linalg.LinAlgError: break
        cc = cc + dx[:2]; R = R + dx[2]
        if np.abs(dx).max() < 1e-6: break
    if not np.isfinite(R) or R <= 0 or R > 30: return None
    v = Y - cc; rn = np.linalg.norm(v, axis=1); dev = np.sqrt((rn - R) ** 2 + h ** 2)
    th = np.unwrap(np.arctan2(v[:, 1], v[:, 0])); span = th[-1] - th[0]
    if abs(span) < np.radians(5) or abs(span) > 2 * np.pi: return None
    n = max(2, int(abs(span) * R / abtast) + 1); ts = np.linspace(th[0], th[-1], n)
    Z3 = c + (cc[0] + R * np.cos(ts))[:, None] * e1 + (cc[1] + R * np.sin(ts))[:, None] * e2
    zen = c + cc[0] * e1 + cc[1] * e2
    return dict(typ="bogen", _X=X, punkte=Z3.tolist(), zentrum=zen.tolist(), radius=R, normale=nrm.tolist(), winkel_grad=float(np.degrees(abs(span))),
                abweichung_m=float(dev.max()), dev=dev, laenge_m=float(abs(span) * R))


def bezier_auswerten(K, t):
    t = t[:, None]; return ((1 - t) ** 3) * K[0] + 3 * ((1 - t) ** 2) * t * K[1] + 3 * (1 - t) * t ** 2 * K[2] + t ** 3 * K[3]


def fit_bezier(X, abtast):
    seg = np.linalg.norm(np.diff(X, axis=0), axis=1); L = seg.sum()
    if L <= 0: return None
    t = np.concatenate([[0], np.cumsum(seg)]) / L; tt = np.linspace(0, 1, 400)
    alt = 9e9
    for _ in range(30):                                                                           # LS (Endpunkte fest; frei = Ueberschwingen am Rand, getestet) + Reparametrisierung (naechster Kurvenpunkt), wie Schneider 1990
        B1 = 3 * (1 - t) ** 2 * t; B2 = 3 * (1 - t) * t ** 2; rest = X - ((1 - t) ** 3)[:, None] * X[0] - (t ** 3)[:, None] * X[-1]
        sol = np.linalg.lstsq(np.column_stack([B1, B2]), rest, rcond=None)[0]; K = np.stack([X[0], sol[0], sol[1], X[-1]])
        dicht = bezier_auswerten(K, tt); D2 = ((X[:, None] - dicht[None]) ** 2).sum(-1); dev = np.sqrt(D2.min(1)); t = tt[D2.argmin(1)]
        t[0], t[-1] = 0.0, 1.0
        if alt - dev.max() < 0.001: break
        alt = dev.max()
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(dicht, axis=0), axis=1))]); n = max(2, int(cum[-1] / abtast) + 1)
    Z = np.stack([np.interp(np.linspace(0, cum[-1], n), cum, dicht[:, i]) for i in range(3)], 1)
    return dict(typ="bezier", _X=X, punkte=Z.tolist(), kontrollpunkte=K.tolist(), abweichung_m=float(dev.max()), dev=dev, laenge_m=float(cum[-1]))


def modellwahl(X, tol, abtast, tiefe=0, maxtiefe=2):
    r = _modellwahl(X, tol, abtast, tiefe, maxtiefe)
    return r


def _modellwahl(X, tol, abtast, tiefe, maxtiefe):
    g = fit_gerade(X)
    if g["abweichung_m"] < tol: return [g]
    b = fit_bogen(X, abtast)
    if b is not None and b["abweichung_m"] < tol and b["abweichung_m"] < 0.5 * g["abweichung_m"]: return [b]
    z = fit_bezier(X, abtast)
    best = min([m for m in (g, b, z) if m is not None], key=lambda m: m["abweichung_m"])
    if z is not None and z["abweichung_m"] < tol and z["abweichung_m"] < 0.5 * (b["abweichung_m"] if b else g["abweichung_m"]): return [z]
    if tiefe < maxtiefe and len(X) >= 8:
        i = int(np.argmax(best["dev"])); i = min(max(i, 4), len(X) - 5)
        return _modellwahl(X[:i + 1], tol, abtast, tiefe + 1, maxtiefe) + _modellwahl(X[i:], tol, abtast, tiefe + 1, maxtiefe)
    return [best]

def fit_bogen_ungeordnet(X, abtast):
    """Kreisbogen durch ungeordnete Punkte (Vereinigung mehrerer Fragmente): Ebene/Kreis wie fit_bogen, Bogenbereich = Komplement der groessten Winkelluecke."""
    c = X.mean(0); _, sv, vt = np.linalg.svd(X - c, full_matrices=False); nrm = vt[2]; e1 = vt[0]; e2 = np.cross(nrm, e1)
    Y = np.stack([(X - c) @ e1, (X - c) @ e2], 1); h = (X - c) @ nrm
    A = np.column_stack([2 * Y, np.ones(len(Y))]); b = (Y ** 2).sum(1)
    try: sol = np.linalg.lstsq(A, b, rcond=None)[0]
    except np.linalg.LinAlgError: return None
    cx, cy = sol[0], sol[1]; R2 = sol[2] + cx * cx + cy * cy
    if R2 <= 0: return None
    R = float(np.sqrt(R2)); cc = np.array([cx, cy])
    for _ in range(10):
        v = Y - cc; rn = np.linalg.norm(v, axis=1); res = rn - R; J = np.column_stack([-v / rn[:, None].clip(1e-9), -np.ones(len(Y))])
        try: dx = np.linalg.lstsq(J, -res, rcond=None)[0]
        except np.linalg.LinAlgError: break
        cc = cc + dx[:2]; R = R + dx[2]
        if np.abs(dx).max() < 1e-6: break
    if not np.isfinite(R) or R <= 0 or R > 30: return None
    v = Y - cc; rn = np.linalg.norm(v, axis=1); dev = np.sqrt((rn - R) ** 2 + h ** 2)
    th = np.sort(np.arctan2(v[:, 1], v[:, 0])); gaps = np.diff(np.concatenate([th, [th[0] + 2 * np.pi]])); i = int(np.argmax(gaps))
    t0 = th[(i + 1) % len(th)]; span = 2 * np.pi - gaps[i]                                         # Bogen von t0 ueber alle Punkte bis t0+span
    if span < np.radians(5): return None
    n = max(2, int(span * R / abtast) + 1); ts = t0 + np.linspace(0, span, n)
    Z3 = c + (cc[0] + R * np.cos(ts))[:, None] * e1 + (cc[1] + R * np.sin(ts))[:, None] * e2; zen = c + cc[0] * e1 + cc[1] * e2
    return dict(typ="bogen", _X=X, punkte=Z3.tolist(), zentrum=zen.tolist(), radius=R, normale=nrm.tolist(), winkel_grad=float(np.degrees(span)),
                abweichung_m=float(dev.max()), dev=dev, laenge_m=float(span * R))


def _luecke(A, B):
    """kleinster Abstand zwischen den Endpunkten zweier Polylinien (Abtastpunkte)."""
    PA = np.array(A["punkte"]); PB = np.array(B["punkte"]); ea = PA[[0, -1]]; eb = PB[[0, -1]]
    return float(np.sqrt(((ea[:, None] - eb[None]) ** 2).sum(-1)).min())


def verschmelzen(modelle, tol, abtast, maxabw, b_norm=10.0, b_zen=0.08, b_rad=0.05, b_luecke=0.40, g_wink=3.0, g_abst=0.04, g_luecke=0.30):
    """Fragmente verbinden: ko-zirkulare Boegen (Ebene +-b_norm Grad, Zentrum +-b_zen, Radius +-b_rad, Luecke < b_luecke) und kollineare Geraden
    (Winkel < g_wink, Abstand < g_abst, Luecke < g_luecke) paarweise zusammenfassen, Vereinigung der Kettenpunkte neu fitten; wiederholen bis nichts mehr passt.
    Ein Verbund wird nur angenommen, wenn der Neufit <= maxabw bleibt (sonst bleiben die Teile getrennt)."""
    modelle = [dict(m, teile=m.get("teile", 1)) for m in modelle]; runden = 0; verbunden = 0
    while runden < 6:
        runden += 1; passiert = False; i = 0
        while i < len(modelle):
            A = modelle[i]; j = i + 1; fusion = None
            while j < len(modelle):
                B = modelle[j]; fusion = None                                                      # je Paar neu (Fehler im ersten Lauf: alter Verbund blieb stehen -> alles verschmolz)
                if A["typ"] == "bogen" == B["typ"]:
                    cosn = abs(np.dot(A["normale"], B["normale"]))
                    if (cosn >= np.cos(np.radians(b_norm)) and np.linalg.norm(np.array(A["zentrum"]) - np.array(B["zentrum"])) <= b_zen
                            and abs(A["radius"] - B["radius"]) <= b_rad and _luecke(A, B) < b_luecke):
                        fusion = fit_bogen_ungeordnet(np.vstack([A["_X"], B["_X"]]), abtast)
                elif A["typ"] == "gerade" == B["typ"]:
                    pa = np.array(A["punkte"]); pb = np.array(B["punkte"]); da = pa[1] - pa[0]; db = pb[1] - pb[0]; la = np.linalg.norm(da); lb = np.linalg.norm(db)
                    if la > 0 and lb > 0:
                        da /= la; db /= lb; cosw = abs(np.dot(da, db))
                        if cosw >= np.cos(np.radians(g_wink)):
                            dq = max(np.linalg.norm(np.cross(pb - pa[0], da), axis=1).max(), np.linalg.norm(np.cross(pa - pb[0], db), axis=1).max())
                            ta = np.sort((pa - pa[0]) @ da); tb = np.sort((pb - pa[0]) @ da); luecke = max(0.0, max(ta[0], tb[0]) - min(ta[1], tb[1]))
                            if dq < g_abst and luecke < g_luecke: fusion = fit_gerade(np.vstack([A["_X"], B["_X"]]))
                if fusion is None and {A["typ"], B["typ"]} <= {"gerade", "bogen"} and _luecke(A, B) < b_luecke:
                    # Erweiterung (Befund 9.11.): 0,4-0,5-m-Stuecke eines R-1,9-m-Bogens haben 1 cm Pfeilhoehe < tol und werden GERADEN -> Ko-Zirkularitaet unter
                    # 'bogen' greift nie. Darum: benachbarte Gerade/Gerade (nicht kollinear) oder Gerade/Bogen gemeinsam als Kreis fitten; nur wenn < tol, Spanne >= 15 Grad.
                    ta = np.array(A["punkte"][-1]) - np.array(A["punkte"][0]); tb = np.array(B["punkte"][-1]) - np.array(B["punkte"][0])
                    cosw = abs(np.dot(ta, tb)) / max(np.linalg.norm(ta) * np.linalg.norm(tb), 1e-9)
                    if cosw < np.cos(np.radians(5)):
                        kand = fit_bogen_ungeordnet(np.vstack([A["_X"], B["_X"]]), abtast)
                        if kand is not None and kand["abweichung_m"] <= tol and kand["winkel_grad"] >= 15 and 0.3 <= kand["radius"] <= 5.0: fusion = kand
                if fusion is not None and fusion["abweichung_m"] <= maxabw:
                    fusion["teile"] = A["teile"] + B["teile"]; modelle[i] = fusion; A = fusion; del modelle[j]; passiert = True; verbunden += 1
                else: j += 1
            i += 1
        if not passiert: break
    return modelle, verbunden


def fotopruefung(stuecke, kam, stabildir, thr=0.3, dmax=45.0, tolm=0.12, stuetz=0.5, wolke=None, ztol=0.5):
    """Jedes Kurvenstueck gegen die Stabilitaetskarten (Vorlage gitter_zurueck.stuetzung_alle, vektorisiert): Abtastpunkte (verdichtet auf 5 cm) in jedes
    Foto projizieren, das naeher als dmax ist und >= 90 % der Punkte im Bild hat; Kante = Karte >= thr, dilatiert um tolm Meter in Pixel (aus Kameraabstand).
    Foto sagt JA, wenn >= stuetz der Punkte auf Kante liegen, sonst NEIN. Rueckgabe ja, nein je Stueck. Karten werden je Foto geladen und wieder verworfen (VRAM).
    wolke (N,3): Z-Puffer-Sichtbarkeit wie gitter_pruefblatt.proj --wolke (1/4 Aufloesung, 3x3-Min-Splat, Loecher aus 9x9, ztol): verdeckte Punkte zaehlen weder ja noch nein
    (ein Foto zaehlt nur, wenn >= 90 % der Punkte des Stuecks sichtbar und im Bild sind)."""
    import cv2
    Qs, idx, mids = [], [], []
    for k, st in enumerate(stuecke):
        Pm = np.array(st["punkte"], np.float32); dense = np.vstack([Pm, (Pm[:-1] + Pm[1:]) / 2]) if len(Pm) > 1 else Pm
        Qs.append(dense); idx.append(np.full(len(dense), k)); mids.append(Pm.mean(0))
    Q = torch.as_tensor(np.vstack(Qs), device=DEV); idx = torch.as_tensor(np.concatenate(idx), device=DEV); mids = np.array(mids); M = len(stuecke)
    cnt = torch.bincount(idx, minlength=M).float(); ja = torch.zeros(M, device=DEV, dtype=torch.int32); nein = torch.zeros(M, device=DEV, dtype=torch.int32)
    fs = [f for f in sorted(kam) if os.path.exists(os.path.join(stabildir, os.path.splitext(f)[0] + ".png"))]; benutzt = 0
    Wt = torch.as_tensor(np.asarray(wolke, np.float32), device=DEV) if wolke is not None else None
    for f in fs:
        k = kam[f]; C = np.array(k["C"]); dC = np.linalg.norm(mids - C, axis=1); nah_np = dC < dmax
        if not nah_np.any(): continue
        img = cv2.imread(os.path.join(stabildir, os.path.splitext(f)[0] + ".png"), 0)
        if img is None: continue
        benutzt += 1; dist = float(np.median(dC[nah_np])); sj = img.shape[1] / k["W"]; rad = int(np.clip(round(tolm * k["f"] * sj / max(dist, 1.0)), 2, 8))
        Vm = torch.nn.functional.max_pool2d((torch.from_numpy(img).to(DEV) >= 255 * thr).float()[None, None], 2 * rad + 1, 1, rad)[0, 0]
        R = torch.tensor(k["Rn"], device=DEV, dtype=torch.float32); t = torch.tensor(k["tn"], device=DEV, dtype=torch.float32); X = Q @ R.T + t; z = X[:, 2].clamp(min=0.3)
        x = X[:, 0] / z; y = X[:, 1] / z; f1 = 1 + k["params"][3] * (x * x + y * y)
        u = ((k["f"] * x * f1 + k["cx"]) * sj).round().long(); v = ((k["f"] * y * f1 + k["cy"]) * sj).round().long(); H, W = Vm.shape
        ok = (X[:, 2] > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        if Wt is not None:                                                                        # Z-Puffer der Wolke (Vorlage gitter_pruefblatt.proj)
            Xw = Wt @ R.T + t; zw = Xw[:, 2]; mw = zw > 0.5; xw = Xw[mw, 0] / zw[mw]; yw = Xw[mw, 1] / zw[mw]; fw = 1 + k["params"][3] * (xw * xw + yw * yw)
            uw = ((k["f"] * xw * fw + k["cx"]) * sj / 4).long(); vw = ((k["f"] * yw * fw + k["cy"]) * sj / 4).long(); Hq, Wq = H // 4 + 1, W // 4 + 1
            inb = (uw >= 0) & (uw < Wq) & (vw >= 0) & (vw < Hq); zb = torch.full((Hq * Wq,), 1e9, device=DEV); zb.scatter_reduce_(0, vw[inb] * Wq + uw[inb], zw[mw][inb], reduce="amin"); zb = zb.view(Hq, Wq)
            zb = -torch.nn.functional.max_pool2d(-zb[None, None], 3, 1, 1)[0, 0]
            leer = zb > 1e8; zb9 = -torch.nn.functional.max_pool2d(-zb[None, None], 9, 1, 4)[0, 0]; zb = torch.where(leer, zb9, zb)
            uq = (u / 4).long().clamp(0, Wq - 1); vq = (v / 4).long().clamp(0, Hq - 1); ok = ok & (X[:, 2] <= zb[vq, uq] + ztol)
        hit = torch.zeros(len(Q), device=DEV); hit[ok] = Vm[v[ok], u[ok]]
        okm = torch.bincount(idx, ok.float(), minlength=M) / cnt; hm = torch.bincount(idx, hit, minlength=M) / torch.bincount(idx, ok.float(), minlength=M).clamp(min=1)
        g_ = torch.as_tensor(nah_np, device=DEV) & (okm >= 0.9); ja += (g_ & (hm >= stuetz)).int(); nein += (g_ & (hm < stuetz)).int()
        del Vm
    return ja.cpu().numpy(), nein.cpu().numpy(), benutzt


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("sweep"); ap.add_argument("gitter_in"); ap.add_argument("out")
    ap.add_argument("--vox", type=float, default=0.06); ap.add_argument("--kmin", type=int, default=3); ap.add_argument("--tol", type=float, default=0.03)
    ap.add_argument("--minlen", type=float, default=0.3); ap.add_argument("--minpkt", type=int, default=8); ap.add_argument("--rlink", type=float, default=0.10)
    ap.add_argument("--winkel", type=float, default=30); ap.add_argument("--k", type=int, default=12); ap.add_argument("--lin", type=float, default=0.5)
    ap.add_argument("--maxabw", type=float, default=0.10); ap.add_argument("--rand", type=float, default=2.0); ap.add_argument("--abtast", type=float, default=0.10)
    ap.add_argument("--gpu_mb", type=int, default=2000); ap.add_argument("--kam", default=None, help="kam_lot2.json: Fotopruefung Pflichtfilter"); ap.add_argument("--stabil", default=None)
    ap.add_argument("--nmin", type=int, default=3); ap.add_argument("--stuetz", type=float, default=0.5); ap.add_argument("--thr", type=float, default=0.3); ap.add_argument("--dmax", type=float, default=45.0); ap.add_argument("--tolm", type=float, default=0.12)
    ap.add_argument("--ohne_verbinden", action="store_true"); ap.add_argument("--wolke", default=None, help="Kantenwolke .npz/.npy fuer Z-Puffer-Sichtbarkeit in der Fotopruefung"); ap.add_argument("--ztol", type=float, default=0.5); ap.add_argument("--kref", type=float, default=0, help="Kette nur, wenn Median der Ref-Anzahl je Voxel >= kref (0 = aus)"); a = ap.parse_args()
    t0 = time.time(); torch.cuda.set_per_process_memory_fraction(min(1.0, a.gpu_mb / (torch.cuda.get_device_properties(0).total_memory / 2 ** 20)))
    P, ref, s, off = [], [], [], 0
    for sw in a.sweep.split(","):                                                                  # mehrere Sweeps: ref-Indizes verschieben, damit Referenzfotos verschieden bleiben
        z = np.load(sw); P.append(z["P"].astype(np.float32)); r = z["ref"].astype(np.int64); ref.append(r + off); s.append(z["s"].astype(np.float32)); off += int(r.max()) + 1
        print("Sweep", sw.split("/")[-1], len(z["P"]), "Pkt, Refs", len(np.unique(r)))
    P, ref, s = np.concatenate(P), np.concatenate(ref), np.concatenate(s)
    G = json.load(open(a.gitter_in)); S = G["segmente"] if isinstance(G, dict) else G
    if not isinstance(G, dict): G = {"segmente": S}
    E = np.array([[sg[0], sg[1]] for sg in S], np.float32).reshape(-1, 3); lo = E.min(0) - a.rand; hi = E.max(0) + a.rand
    m = np.all((P > lo) & (P < hi), axis=1); P, ref, s = P[m], ref[m], s[m]
    C, nref, sm = konsens(P, ref, s, a.vox, a.kmin); t1 = time.time()
    print("Sweep %d Pkt im Quader -> %d Konsens-Voxel (>= %d Refs)  %.1f s" % (len(P), len(C), a.kmin, t1 - t0))
    Q = segment_punkte(S, a.vox / 2); dG = min_abstand(C, Q); frei = dG >= a.vox
    X = np.ascontiguousarray(C[frei]); sX = sm[frei]; nX = nref[frei].astype(np.float32); t2 = time.time()
    print("durch Gitter erklaert %d, Kurvenkandidaten %d  %.1f s" % ((~frei).sum(), len(X), t2 - t1))
    nb, X, tang, linm, behalten = tangenten_und_ketten(X, a.k, a.rlink, a.winkel, a.lin); sX = sX[behalten]; nX = nX[behalten]; t3 = time.time()   # X = geglaettet, ohne Doppelte
    print("nach Doppelten %d, linear (>= %.2f) %d, Punkte mit Nachbar %d  %.1f s" % (len(X), a.lin, (linm >= a.lin).sum(), (nb >= 0).any(1).sum(), t3 - t2))
    ketten = ketten_traversieren(nb)
    def laenge(ix): return float(np.linalg.norm(np.diff(X[ix], axis=0), axis=1).sum())
    kurz = sum(1 for kt in ketten if len(kt) < a.minpkt or laenge(kt) < a.minlen)
    ketten = [kt for kt in ketten if len(kt) >= a.minpkt and laenge(kt) >= a.minlen]
    refs_med = [float(np.median(nX[kt])) for kt in ketten]; schwach = sum(1 for r in refs_med if r < a.kref)       # Stuetzung je Kette: Median der Ref-Anzahl je Voxel
    ketten = [kt for kt, r in zip(ketten, refs_med) if r >= a.kref]; t4 = time.time()
    print("Ketten %d (verworfen kurz %d, schwach gestuetzt < %g Refs %d), Punkte in Ketten %d  %.1f s" % (len(ketten), kurz, a.kref, schwach, sum(len(k) for k in ketten), t4 - t3))
    if refs_med: print("  Refs-Median je Kette (vor Filter): Quantile 10/25/50/75/90 =", np.percentile(refs_med, [10, 25, 50, 75, 90]).round(1).tolist())
    modelle = []; verworfen = 0
    for ki, kt in enumerate(ketten):
        Xk = X[kt].astype(np.float64); sc = float(sX[kt].mean()); rm = float(np.median(nX[kt]))
        for mdl in modellwahl(Xk, a.tol, a.abtast):
            if mdl["abweichung_m"] > a.maxabw: verworfen += 1; continue
            mdl.update(kette=ki, n_punkte=len(mdl["_X"]), score=sc, refs_median=rm); modelle.append(mdl)
    n_vor = len(modelle); zaehl_vor = {t: sum(1 for m in modelle if m["typ"] == t) for t in ("gerade", "bogen", "bezier")}
    verbunden = 0
    if not a.ohne_verbinden:
        modelle, verbunden = verschmelzen(modelle, a.tol, a.abtast, a.maxabw)
        for m in modelle:
            if "kette" not in m: m.update(kette=-1, n_punkte=len(m["_X"]), score=float(np.mean([0])), refs_median=0.0)
    # Score/Refs fuer Verbuende neu aus den Teilen: Mittel der Fragmente ist nicht gespeichert -> Score aus Punkten nicht verfuegbar, daher Score = Fotostuetzung (unten) oder Kettenscore
    zaehl_verb = {t: sum(1 for m in modelle if m["typ"] == t) for t in ("gerade", "bogen", "bezier")}
    print("Modelle vor Verbinden %d %s -> nach Verbinden %d %s (Verbindungen %d, max. Teile %d)" % (n_vor, zaehl_vor, len(modelle), zaehl_verb, verbunden, max([m.get("teile", 1) for m in modelle] + [0])))
    t5 = time.time(); fotos_benutzt = 0; abgelehnt = []
    if a.kam:
        kam = json.load(open(a.kam)); wolke = None
        if a.wolke: w_ = np.load(a.wolke); wolke = (w_["P"] if hasattr(w_, "files") else w_)[:, :3]
        ja, nein, fotos_benutzt = fotopruefung(modelle, kam, a.stabil, a.thr, a.dmax, a.tolm, a.stuetz, wolke, a.ztol)
        beh = []
        for m, j, n_ in zip(modelle, ja, nein):
            m.update(fotos_ja=int(j), fotos_nein=int(n_)); (beh if (j >= a.nmin and j > n_) else abgelehnt).append(m)
        print("Fotopruefung (%d Fotos mit Karte): behalten %d, abgelehnt %d  (%.1f s)" % (fotos_benutzt, len(beh), len(abgelehnt), time.time() - t5))
        for t in ("gerade", "bogen", "bezier"): print("  %s: %d -> %d" % (t, sum(1 for m in modelle if m["typ"] == t), sum(1 for m in beh if m["typ"] == t)))
        modelle = beh
    kurven = []; neu = []; zaehl = {"gerade": 0, "bogen": 0, "bezier": 0}; ungenau = 0
    def eintrag(mdl):
        q = {"gerade": Q_GERADE, "bogen": Q_BOGEN, "bezier": Q_BEZIER}[mdl["typ"]]
        sc = round(mdl["fotos_ja"] / max(mdl["fotos_ja"] + mdl["fotos_nein"], 1), 3) if "fotos_ja" in mdl else mdl["score"]
        e = {k: v for k, v in mdl.items() if k not in ("dev", "_X")}; e.update(quelle=q, score=sc, ungenau=bool(mdl["abweichung_m"] > a.tol)); return e, q, sc
    for mdl in modelle:
        if mdl["abweichung_m"] > a.tol: ungenau += 1
        e, q, sc = eintrag(mdl); pts = mdl["punkte"]
        for i in range(len(pts) - 1): neu.append([pts[i], pts[i + 1], q, sc])
        kurven.append(e); zaehl[mdl["typ"]] += 1
    abgelehnt_seg = []; abgelehnt_k = []
    for mdl in abgelehnt:
        e, q, sc = eintrag(mdl); pts = mdl["punkte"]; abgelehnt_k.append(e)
        for i in range(len(pts) - 1): abgelehnt_seg.append([pts[i], pts[i + 1], q, sc])
    t5 = time.time()
    G["segmente"] = S + neu; G["kurven"] = kurven
    bericht = dict(sweep=a.sweep, gitter_in=a.gitter_in, parameter=vars(a), punkte_quader=int(len(P)), konsens_voxel=int(len(C)), durch_gitter_erklaert=int((~frei).sum()),
                   kandidaten=int(len(X)), linear=int((linm >= a.lin).sum()), ketten=len(ketten), ketten_kurz_verworfen=kurz, ketten_schwach_verworfen=schwach, modelle_vor_verbinden=zaehl_vor, verbindungen=verbunden, modelle_nach_verbinden=zaehl_verb, fotos_benutzt=fotos_benutzt, abgelehnt_foto={t: sum(1 for m in abgelehnt_k if m['typ'] == t) for t in ('gerade', 'bogen', 'bezier')}, modelle=zaehl, ungenau_ueber_tol=ungenau,
                   verworfen_ueber_maxabw=verworfen, segmente_neu=len(neu), segmente_gesamt=len(G["segmente"]),
                   laenge_neu_m=float(sum(k["laenge_m"] for k in kurven)), zeit_s=dict(konsens=t1 - t0, gitterfilter=t2 - t1, tangenten=t3 - t2, ketten=t4 - t3, fits=t5 - t4, gesamt=t5 - t0))
    G.setdefault("historie", []).append({"schritt": "gitter_kurven", "bericht": {k: v for k, v in bericht.items() if k not in ("parameter",)}})
    json.dump(G, open(a.out, "w")); stamm = a.out[:-5] if a.out.endswith(".json") else a.out
    json.dump({"segmente": neu, "kurven": kurven}, open(stamm + "_neu.json", "w")); json.dump(bericht, open(stamm + ".bericht.json", "w"), indent=1)
    if a.kam: json.dump({"segmente": abgelehnt_seg, "kurven": abgelehnt_k}, open(stamm + "_abgelehnt.json", "w"))
    np.savez_compressed(stamm + "_kandidaten.npz", X=X, tang=tang, lin=linm, nb=nb, ketten_idx=np.concatenate([np.array(k) for k in ketten]) if ketten else np.zeros(0, int),
                        ketten_off=np.cumsum([0] + [len(k) for k in ketten]))
    print("Modelle", zaehl, "| ungenau (> tol) %d, verworfen (> maxabw) %d | neue Segmente %d, Laenge %.1f m | gesamt %.1f s" % (ungenau, verworfen, len(neu), bericht["laenge_neu_m"], time.time() - t0))
    print("geschrieben", a.out, stamm + "_neu.json", stamm + ".bericht.json")


if __name__ == "__main__":
    main()
