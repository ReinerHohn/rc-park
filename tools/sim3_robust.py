#!/usr/bin/env python3
"""sim3_robust.py - EINE gemeinsame robuste Sim3 (Aehnlichkeit X -> Y) mit fester Meter-Schwelle im Zielrahmen (22.11.2026).
ANLASS: wand_dicke_tor.teile_laden legte ein Modell per Umeyama ueber ALLE Kameras -> eine einzige Kamera "am Mond" (globaler Mapper, schwabentor-1122 Durchblick-Beleg)
verschob die ganze Wolke, Rest 4372 m, Tor-Urteil wertlos; dieselbe Ursache verfaelschte an diesem Tag drei Auswertungen. Hier: RANSAC ueber Dreiergruppen, Inlier =
Abstand im ZIELRAHMEN < schwelle_m (Meter, wenn Y in Metern), Nachrechnung ueber alle Inlier, zweimal nachschaerfen. Ohne genug Inlier: None (nie stillschweigend alle).
Funktionen: umeyama(X, Y) -> (s, R, t); matrix(s, R, t) -> 4x4; sim3_meter(X, Y, schwelle_m, ...) -> dict(M, inlier, n, n_inlier, rest_median_m) oder None."""
import numpy as np

SCHWELLE_M = 1.0      # ANNAHME wie die Ketten-Ausrichtung (--tol-m 1.0): Kamera-Standort > 1 m neben der Ausrichtung = Ausreisser
MIN_INLIER = 5
MIN_ANTEIL = 0.5      # weniger als die Haelfte stimmig = keine belastbare Lage


def umeyama(X, Y):
    X = np.asarray(X, float); Y = np.asarray(Y, float); mx, my = X.mean(0), Y.mean(0)
    U, S, Vt = np.linalg.svd((Y - my).T @ (X - mx)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt)) or 1.0; R = U @ D @ Vt
    s = float((S * np.diag(D)).sum() / max(((X - mx) ** 2).sum(), 1e-18)); return s, R, my - s * R @ mx


def matrix(s, R, t):
    M = np.eye(4); M[:3, :3] = s * np.asarray(R); M[:3, 3] = t; return M


def anwenden(M, X): return np.asarray(X, float) @ np.asarray(M)[:3, :3].T + np.asarray(M)[:3, 3]


def sim3_meter(X, Y, schwelle_m=SCHWELLE_M, runden=1000, saat=0, min_inlier=MIN_INLIER, min_anteil=MIN_ANTEIL):
    X = np.asarray(X, float); Y = np.asarray(Y, float); n = len(X)
    if n < 3: return None
    rng = np.random.default_rng(saat); best, nb = None, -1
    for _ in range(runden if n > 3 else 1):
        ix = rng.choice(n, 3, replace=False)
        if np.linalg.norm(np.cross(Y[ix[1]] - Y[ix[0]], Y[ix[2]] - Y[ix[0]])) < 1e-6 * max(1e-12, np.linalg.norm(Y[ix[1]] - Y[ix[0]]) ** 2): continue
        s, R, t = umeyama(X[ix], Y[ix])
        if not np.isfinite(s) or s <= 0: continue
        inl = np.linalg.norm(s * X @ R.T + t - Y, axis=1) < schwelle_m
        if inl.sum() > nb: best, nb = inl, int(inl.sum())
    if best is None or nb < max(3, min_inlier) or nb < min_anteil * n: return None
    inl = best
    for _ in range(3):
        M = matrix(*umeyama(X[inl], Y[inl])); neu = np.linalg.norm(anwenden(M, X) - Y, axis=1) < schwelle_m
        if neu.sum() < max(3, min_inlier) or (neu == inl).all(): break
        inl = neu
    M = matrix(*umeyama(X[inl], Y[inl])); r = np.linalg.norm(anwenden(M, X) - Y, axis=1); inl = r < schwelle_m
    return dict(M=M, inlier=inl, n=n, n_inlier=int(inl.sum()), rest_median_m=float(np.median(r[inl])) if inl.any() else float("nan"))
