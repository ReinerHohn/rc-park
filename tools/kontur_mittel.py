"""Konturen mitteln und Boegen anpassen (rein numerisch, ohne Objektbezug).
 - mittelform(): gleiche Elemente (z. B. 5 Fenster) ausrichten (Verschiebung, Skalierung, zyklische Startpunkt-Verschiebung) und per Median/Mittel zu EINER Form zusammenfassen.
 - kreis_fit()/boegen_finden(): Kreisbogen-RANSAC auf Kantenpunkten (GPU wenn vorhanden), liefert Mittelpunkt, Radius, Oeffnungswinkel.
Quelle der Methoden: modelle/RECHERCHE_FASSADE_FLAECHEN_2026-11-08.md (Procrustes-Mittelung, Kreis-RANSAC); Eigenentwurf des Medians je Punkt (kein fertiges Verfahren belegt).
Beweis: tools/test_kontur_mittel.py --synth"""
import numpy as np

def flaeche(P):
    x, y = P[:, 0], P[:, 1]; return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))

def ccw(P):
    P = np.asarray(P, float); return P if flaeche(P) >= 0 else P[::-1].copy()

def umtasten(P, n=48):
    """geschlossenen Polygonzug gleichmaessig nach Bogenlaenge auf n Punkte umtasten"""
    P = np.asarray(P, float); Q = np.vstack([P, P[:1]]); d = np.hypot(*np.diff(Q, axis=0).T); s = np.r_[0, np.cumsum(d)]; t = np.linspace(0, s[-1], n, endpoint=False)
    return np.c_[np.interp(t, s, Q[:, 0]), np.interp(t, s, Q[:, 1])]

def mittelform(polys, n=48, median=True, iter=4):
    """polys: Liste von Polygonen (Nx2). Rueckgabe dict: form (n x 2, normiert, Schwerpunkt 0, Flaechenmass 1), skala (Median sqrt(Flaeche)), schwerpunkte, skalen,
    abweichung (mittlere Punktabweichung je Instanz in Einheiten der Eingabe), ausgerichtet (normierte Instanzen)."""
    R = [umtasten(ccw(p), n) for p in polys]; c = [r.mean(0) for r in R]; S = [np.sqrt(abs(flaeche(ccw(p)))) for p in polys]
    N = [(r - ci) / si for r, ci, si in zip(R, c, S)]; ref = N[0]; A = N
    for _ in range(iter):
        A = []
        for r in N:
            k = int(np.argmin([np.sum((np.roll(r, j, axis=0) - ref) ** 2) for j in range(n)])); A.append(np.roll(r, k, axis=0))
        M = np.array(A); ref = np.median(M, 0) if median else M.mean(0)
        ref = ref - ref.mean(0)
    sm = float(np.median(S)); ab = [float(np.mean(np.hypot(*((a - ref) * s).T))) for a, s in zip(A, S)]
    return dict(form=ref, skala=sm, schwerpunkte=np.array(c), skalen=np.array(S), abweichung=ab, ausgerichtet=A)

def platzieren(m, i, eigene_skala=False):
    """gemittelte Form an Instanz i (Schwerpunkt der Instanz, Skala: Median oder eigene)"""
    return m["form"] * (m["skalen"][i] if eigene_skala else m["skala"]) + m["schwerpunkte"][i]

def vereinfachen(P, eps):
    import cv2
    a = cv2.approxPolyDP(np.asarray(P, np.float32).reshape(-1, 1, 2), eps, True)[:, 0, :]; return a.astype(float)

def kreis_fit(P):
    """algebraischer Kreisfit (Kasa), Rueckgabe (cx, cy, r)"""
    P = np.asarray(P, float); A = np.c_[2 * P[:, 0], 2 * P[:, 1], np.ones(len(P))]; b = (P ** 2).sum(1); x = np.linalg.lstsq(A, b, rcond=None)[0]
    return float(x[0]), float(x[1]), float(np.sqrt(max(x[2] + x[0] ** 2 + x[1] ** 2, 0)))

def _kreis3(p):
    a, b, c = p[:, 0], p[:, 1], p[:, 2]; ax, ay = a[:, 0], a[:, 1]; bx, by = b[:, 0], b[:, 1]; cx, cy = c[:, 0], c[:, 1]
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by)); ok = np.abs(d) > 1e-6; d = np.where(ok, d, 1)
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
    return ux, uy, np.hypot(ax - ux, ay - uy), ok

def boegen_finden(P, rmin, rmax, D=None, tol=2.5, minpts=25, minwinkel=70, maxwinkel=215, versuche=3000, maxbogen=30, seed=3, tangente_grad=15, abdeckung=0.75):
    """Kreisbogen-RANSAC auf Kantenpunkten P (Nx2, Pixel) mit Richtungen D (Nx2, Einheitsvektoren). Ein Punkt zaehlt nur, wenn er nahe am Kreis liegt UND seine Kante
    tangential zum Kreis verlaeuft (sonst finden dichte Kantenfelder Zufallskreise). Zusaetzlich muss der Bogen zu >= 'abdeckung' durchgehend belegt sein.
    Rueckgabe Liste dict(cx,cy,r,a0,a1,spann_grad,n). a0..a1 (rad, Bildkoordinaten, y nach unten) ist der besetzte Bereich."""
    import torch
    rng = np.random.default_rng(seed); P = np.asarray(P, float); D = None if D is None else np.asarray(D, float); rem = np.ones(len(P), bool); out = []; dev = "cuda" if torch.cuda.is_available() else "cpu"; st = np.sin(np.radians(tangente_grad))
    for _ in range(maxbogen):
        idx = np.nonzero(rem)[0]
        if len(idx) < minpts: break
        Q = P[idx]
        if D is not None:                                   # 2 Punkte + Tangentenrichtung des ersten legen den Kreis fest: viel hoehere Trefferquote als 3 Zufallspunkte im dichten Kantenfeld
            i1 = rng.integers(0, len(Q), versuche * 6); i2 = rng.integers(0, len(Q), versuche * 6); p1, q2 = Q[i1], Q[i2]; n1 = np.c_[-D[idx][i1][:, 1], D[idx][i1][:, 0]]; v = q2 - p1; den = 2 * (n1 * v).sum(1); ok = np.abs(den) > 1e-6
            rs = np.where(ok, (v ** 2).sum(1) / np.where(ok, den, 1), 0); cx = p1[:, 0] + n1[:, 0] * rs; cy = p1[:, 1] + n1[:, 1] * rs; r = np.abs(rs); ok &= (r >= rmin) & (r <= rmax)
            keep = np.nonzero(ok)[0][:versuche * 4]; cx, cy, r = cx[keep], cy[keep], r[keep]; ok = np.ones(len(cx), bool)
        else:
            tri = rng.integers(0, len(Q), (versuche, 3)); cx, cy, r, ok = _kreis3(Q[tri]); ok &= (r >= rmin) & (r <= rmax)
        if ok.sum() == 0: break
        Qt = torch.tensor(Q, dtype=torch.float32, device=dev); Dt = None if D is None else torch.tensor(D[idx], dtype=torch.float32, device=dev); best = (0, None)
        for ch in range(0, len(cx), 200):
            c0 = torch.tensor(np.c_[cx[ch:ch + 200], cy[ch:ch + 200]], dtype=torch.float32, device=dev); rr = torch.tensor(r[ch:ch + 200], dtype=torch.float32, device=dev); okc = torch.tensor(ok[ch:ch + 200], device=dev)
            dist = torch.cdist(c0, Qt); inl = (dist - rr[:, None]).abs() < tol
            if Dt is not None:
                rad = (Qt[None, :, :] - c0[:, None, :]) / dist.clamp(min=1e-6)[:, :, None]; inl &= (rad * Dt[None, :, :]).sum(2).abs() < st      # Kantenrichtung senkrecht zum Radius = tangential
            cnt = inl.sum(1); cnt[~okc] = 0; j = int(cnt.argmax())
            if int(cnt[j]) > best[0]: best = (int(cnt[j]), (float(c0[j, 0]), float(c0[j, 1]), float(rr[j])))
        if best[0] < minpts: break
        c = best[1]

        def inliers(c):
            m = np.abs(np.hypot(Q[:, 0] - c[0], Q[:, 1] - c[1]) - c[2]) < tol
            if D is not None:
                rad = (Q - [c[0], c[1]]) / np.maximum(np.hypot(Q[:, 0] - c[0], Q[:, 1] - c[1]), 1e-6)[:, None]; m &= np.abs((rad * D[idx]).sum(1)) < st
            return m
        for _ in range(8):                                                   # Nachziehen: wachsende Inlier-Menge, bis der Kreis sich nicht mehr aendert
            inl = inliers(c)
            if inl.sum() < 5: break
            c2 = kreis_fit(Q[inl]); ch = abs(c2[2] - c[2]) + abs(c2[0] - c[0]) + abs(c2[1] - c[1]); c = c2
            if ch < 0.05: break
        inl = inliers(c); rem[idx[inl]] = False
        if inl.sum() < minpts or not (rmin <= c[2] <= rmax): continue
        ang = np.sort(np.arctan2(Q[inl, 1] - c[1], Q[inl, 0] - c[0])); dd = np.abs(((ang[:, None] - ang[None, :] + np.pi) % (2 * np.pi)) - np.pi); ang = ang[(dd < np.radians(5)).sum(1) >= 4]          # Einzelpunkte ohne Nachbarn (Ausreisser) verlaengern den Bogen nicht
        if len(ang) < minpts // 2: continue
        gaps = np.diff(np.r_[ang, ang[0] + 2 * np.pi]); g = int(np.argmax(gaps)); a0 = ang[(g + 1) % len(ang)]; spann = 2 * np.pi - gaps[g]
        if not (minwinkel <= np.degrees(spann) <= maxwinkel): continue
        rel = ((ang - a0) % (2 * np.pi)); bins = np.unique((rel / np.radians(3)).astype(int)); nb = int(np.degrees(spann) / 3) + 1
        if len(bins) < abdeckung * nb: continue                                                      # Bogen muss durchgehend belegt sein, nicht nur an einzelnen Stellen
        out.append(dict(cx=c[0], cy=c[1], r=c[2], a0=float(a0), a1=float(a0 + spann), spann_grad=float(np.degrees(spann)), n=int(inl.sum())))
    return out

def bogenlinie(b, schritt_grad=4.0):
    n = max(3, int(b["spann_grad"] / schritt_grad) + 1); a = np.linspace(b["a0"], b["a1"], n); return np.c_[b["cx"] + b["r"] * np.cos(a), b["cy"] + b["r"] * np.sin(a)]
