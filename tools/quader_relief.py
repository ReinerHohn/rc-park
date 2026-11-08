#!/usr/bin/env python3
"""quader_relief.py - Fassade als ADAPTIVER QUADERBAUM aus der Punktwolke (Nutzeridee 6.11.: 'Modell aus Quadern, Diff gegen Wolke, je genauer es passt, desto feiner die Quader').
Rahmen einer Fassade (n, d, o aus fassaden.json): u laengs, z Hoehe, s nach aussen. Die Wolke gibt je (u,z)-Zelle die aeusserste Flaeche s_vorn (robuster Perzentil-Wert);
ein Quader = Zelle (u0..u1, z0..z1) mit Tiefe s (Flaeche) bis zur Wand-Rueckseite s_hinten. Teilung NUR wo die Streuung von s_vorn in der Zelle > TOL (Fehler) und Zelle > MIN;
Zellen ohne Wolkenpunkte (Luecken/Schatten) werden NICHT geteilt (kein Fehler messbar) und erben die Nachbarschaft nicht erfunden: Status 'leer'.
Nachbarquader gleicher Tiefe (+-TOL/2) werden verschmolzen (glatte Waende). ANNAHMEN: TOL 0,05 m, MIN 0,10 m, Perzentil 10 (aeusserste Flaeche), Raster 0,05 m.
Bewertung: Fehler s_vorn(Modell) gegen s_vorn(Wahrheit/Wolke) je Zelle, p50/p90/p99, Zahl Quader; Vergleich gegen gleichmaessiges Raster gleicher Zellgroesse (= Carving-Analogon)."""
import numpy as np


def raster(P, Z0, Z1, U0, U1, g=0.05, perz=10, mind=3):
    """P = (N,3) [u,s,z] -> s_vorn (Zeilen z, Spalten u); nan = keine Punkte. Aeusserste Flaeche = hoher s (s nach aussen): Perzentil 100-perz."""
    nu, nz = int(round((U1 - U0) / g)), int(round((Z1 - Z0) / g)); iu = np.clip(((P[:, 0] - U0) / g).astype(int), 0, nu - 1); iz = np.clip(((P[:, 2] - Z0) / g).astype(int), 0, nz - 1)
    k = iz * nu + iu; o = np.argsort(k); ks, ss = k[o], P[o, 1]; b = np.r_[0, np.nonzero(np.diff(ks))[0] + 1, len(ks)]; D = np.full(nu * nz, np.nan)
    for a, e in zip(b[:-1], b[1:]):
        if e - a >= mind: D[ks[a]] = np.percentile(ss[a:e], 100 - perz)
    return D.reshape(nz, nu)


def baum(D, tol=0.05, minz=1):
    """Quadtree ueber das Raster D; Rueckgabe Liste (z0,z1,u0,u1,s) in Zellindizes; s = Median der gueltigen Zellen; nan-Zellen -> 'leer' (s = nan)."""
    out = []
    def rec(z0, z1, u0, u1):
        w = D[z0:z1, u0:u1]; v = w[np.isfinite(w)]
        if v.size == 0: out.append((z0, z1, u0, u1, np.nan)); return
        streu = np.percentile(v, 99) - np.percentile(v, 1)
        if streu <= tol or ((z1 - z0) <= minz and (u1 - u0) <= minz): out.append((z0, z1, u0, u1, float(np.median(v)))); return
        zm, um = (z0 + z1) // 2, (u0 + u1) // 2
        for a, b in ((z0, zm), (zm, z1)):
            for c, d in ((u0, um), (um, u1)):
                if b > a and d > c: rec(a, b, c, d)
    rec(0, D.shape[0], 0, D.shape[1]); return out


def verschmelzen(Q, D, tol):
    """Spaltenweise: gleich hohe Zellen (gleiche z-Spanne) mit gleichem s (+-tol/2) in einer Zeile nebeneinander -> ein Quader. Gibt Anzahl nach Verschmelzung (Zaehlung genuegt fuer den Vergleich)."""
    Q = sorted([q for q in Q if np.isfinite(q[4])], key=lambda q: (q[0], q[1], q[2])); n = 0; last = None
    for q in Q:
        if last and q[0] == last[0] and q[1] == last[1] and q[2] == last[3] and abs(q[4] - last[4]) <= tol / 2: last = (last[0], last[1], last[2], q[3], last[4])
        else:
            n += last is not None; last = q
    return n + (last is not None)


def modell_raster(Q, shape):
    M = np.full(shape, np.nan)
    for z0, z1, u0, u1, s in Q: M[z0:z1, u0:u1] = s
    return M


def fehler(M, T):
    k = np.isfinite(M) & np.isfinite(T); e = np.abs(M[k] - T[k]); return dict(zellen=int(k.sum()), p50=float(np.percentile(e, 50)), p90=float(np.percentile(e, 90)), p99=float(np.percentile(e, 99)), max=float(e.max()))


def gleichmaessig(D, k):
    """Carving-Analogon: festes Raster mit Zellgroesse k Rasterzellen, s = Median."""
    Q = []
    for z in range(0, D.shape[0], k):
        for u in range(0, D.shape[1], k):
            w = D[z:z + k, u:u + k]; v = w[np.isfinite(w)]; Q.append((z, min(z + k, D.shape[0]), u, min(u + k, D.shape[1]), float(np.median(v)) if v.size else np.nan))
    return Q


def luecken_fuellen(M, tol=0.05, max_breite=40):
    """Leere Zellen (nan) einer Zeile werden NUR gefuellt, wenn links und rechts der Luecke dieselbe Flaeche (+-tol) steht und die Luecke <= max_breite Zellen ist
    (Waende ueber Schatten/Autos). Steht links etwas anderes als rechts (Kante in der Luecke), bleibt sie leer (nichts erfunden)."""
    M = M.copy()
    for z in range(M.shape[0]):
        r = M[z]; nn = np.isfinite(r); idx = np.nonzero(nn)[0]
        for a, b in zip(idx[:-1], idx[1:]):
            if b - a > 1 and b - a - 1 <= max_breite and abs(r[a] - r[b]) <= tol: r[a + 1:b] = 0.5 * (r[a] + r[b])
    return M
