#!/usr/bin/env python3
"""render_kern.py - EIN gemeinsamer Renderkern fuer alle Messwerkzeuge: Punktwolke projizieren + Z-Puffer rastern, auf GPU wenn vorhanden.

Warum zentral: dieselbe Rechnung steckte in vier Werkzeugen (pruefstand.silhouettenbreite, foto_breitenprofil.modell_maske,
fehlteile_finden.render, seiten_audit.ortho) - vier Implementierungen sind vier Fehlerquellen (sie wichen bereits voneinander ab:
8,58 m gegen 13,58 m, weil eine weniger Punkte nahm). Jetzt eine Funktion, ein Verhalten, ein Ort fuer Optimierungen.

GPU (torch+CUDA) wird genommen, wenn verfuegbar; sonst numpy. Ergebnis ist in beiden Faellen identisch (gleiche Rundung,
gleicher Z-Puffer per scatter-min). Abschalten mit RENDER_CPU=1.
"""
import os, numpy as np

_T = None
def _torch():
    global _T
    if _T is None:
        try:
            import torch; _T = torch if (torch.cuda.is_available() and not os.environ.get("RENDER_CPU")) else False
        except Exception: _T = False
    return _T

def geraet():
    return "cuda" if _torch() else "cpu"

class Szene:
    """Punktwolke EINMAL auf die GPU laden und dort halten. Lohnt, sobald dieselben Punkte mehrfach projiziert werden
    (Optimierung, Lagesuche, mehrere Hoehen/Fotos). Einmal-Projektionen sind auf der CPU genauso schnell - der Transfer frisst den Gewinn."""
    def __init__(self, P, N=None):
        self.T = _torch(); self.Pn = np.asarray(P, np.float32); self.Nn = None if N is None else np.asarray(N, np.float32)
        if self.T:
            self.P = self.T.as_tensor(self.Pn, device="cuda"); self.N = None if N is None else self.T.as_tensor(self.Nn, device="cuda")
    def tiefenbild(self, R, t, f, cx, cy, W, H):
        if not self.T: return tiefenbild(self.Pn, R, t, f, cx, cy, W, H)
        T = self.T
        Rg = T.as_tensor(np.asarray(R, np.float32), device="cuda"); tg = T.as_tensor(np.asarray(t, np.float32), device="cuda")
        Xc = self.P @ Rg.T + tg; z = Xc[:, 2]
        u = T.round(f * Xc[:, 0] / z + cx).long(); v = T.round(f * Xc[:, 1] / z + cy).long()
        ok = (z > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        flat = (v[ok] * W + u[ok]); zz = z[ok]
        d = T.full((H * W,), float("inf"), device="cuda"); d.scatter_reduce_(0, flat, zz, reduce="amin")
        gewinner = T.isclose(d[flat], zz); idx = T.full((H * W,), -1, dtype=T.long, device="cuda")
        idx[flat[gewinner]] = T.nonzero(ok, as_tuple=True)[0][gewinner]
        return d.reshape(H, W), idx.reshape(H, W)
    def maske_np(self, R, t, f, cx, cy, W, H, schliessen=5):
        import cv2
        d, _ = self.tiefenbild(R, t, f, cx, cy, W, H)
        M = (np.isfinite(d.cpu().numpy()) if self.T else np.isfinite(d)).astype(np.uint8)
        if schliessen: M = cv2.morphologyEx(M, cv2.MORPH_CLOSE, np.ones((schliessen, schliessen), np.uint8))
        return M.astype(bool)
    def schattiert_np(self, R, t, f, cx, cy, W, H, licht=(0.35, -0.45, 0.82), hintergrund=235):
        if not self.T: return schattiert(self.Pn, self.Nn, R, t, f, cx, cy, W, H, licht, hintergrund)
        T = self.T; d, idx = self.tiefenbild(R, t, f, cx, cy, W, H)
        lit = (self.N @ T.as_tensor(np.asarray(licht, np.float32), device="cuda")).clamp(0, 1)
        img = T.full((H, W), float(hintergrund), device="cuda"); tr = idx >= 0
        img[tr] = 70 + 170 * (0.25 + 0.75 * lit[idx[tr]])
        return img.to(T.uint8).cpu().numpy(), d.cpu().numpy()

def projiziere(P, R, t, f, cx, cy):
    """Punkte (N,3) -> Bildkoordinaten (N,2) und Tiefe (N,). Reines numpy (billig, keine GPU noetig)."""
    Xc = np.asarray(P) @ np.asarray(R).T + np.asarray(t)
    return np.c_[f * Xc[:, 0] / Xc[:, 2] + cx, f * Xc[:, 1] / Xc[:, 2] + cy], Xc[:, 2]

def tiefenbild(P, R, t, f, cx, cy, W, H, werte=None):
    """Z-Puffer: fuer jedes Pixel die kleinste Tiefe und (optional) den Wert des naechsten Punktes.
    Rueckgabe: depth (H,W) mit inf wo leer, idx (H,W) int32 mit -1 wo leer.
    Auf GPU per scatter_reduce(amin) - auf CPU per np.minimum.at; Ergebnis gleich."""
    uv, z = projiziere(P, R, t, f, cx, cy)
    u = np.rint(uv[:, 0]).astype(np.int64); v = np.rint(uv[:, 1]).astype(np.int64)
    ok = (z > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
    flat = (v[ok] * W + u[ok]); zz = z[ok].astype(np.float32); wo = np.nonzero(ok)[0]
    T = _torch()
    if T:
        d = T.full((H * W,), float("inf"), device="cuda")
        d.scatter_reduce_(0, T.as_tensor(flat, device="cuda"), T.as_tensor(zz, device="cuda"), reduce="amin")
        depth = d.cpu().numpy().reshape(H, W)
    else:
        depth = np.full(H * W, np.inf, np.float32); np.minimum.at(depth, flat, zz); depth = depth.reshape(H, W)
    idx = np.full(H * W, -1, np.int64)
    treffer = np.isclose(depth.ravel()[flat], zz)                      # Punkte, die den Z-Puffer gewonnen haben
    idx[flat[treffer]] = wo[treffer]
    return depth, idx.reshape(H, W)

def maske(P, R, t, f, cx, cy, W, H, schliessen=5):
    """Silhouettenmaske der Punktwolke (bool, H x W), Loecher mit einem Closing geschlossen."""
    import cv2
    depth, _ = tiefenbild(P, R, t, f, cx, cy, W, H)
    M = np.isfinite(depth).astype(np.uint8)
    if schliessen: M = cv2.morphologyEx(M, cv2.MORPH_CLOSE, np.ones((schliessen, schliessen), np.uint8))
    return M.astype(bool)

def schattiert(P, N, R, t, f, cx, cy, W, H, licht=(0.35, -0.45, 0.82), hintergrund=235):
    """Graustufenbild der Punktwolke mit Z-Puffer und Lambert-Schattierung (fuer Sichtblaetter und Foto-Render-Vergleiche)."""
    depth, idx = tiefenbild(P, R, t, f, cx, cy, W, H)
    img = np.full((H, W), hintergrund, np.uint8); tr = idx >= 0
    lit = np.clip(np.asarray(N) @ np.asarray(licht), 0, 1)
    img[tr] = (70 + 170 * (0.25 + 0.75 * lit[idx[tr]])).astype(np.uint8)
    return img, depth

def hypso_lagen(P, stufen, lagen, radius=9.0, raster=1.0, N=60):
    """Flaeche ueber mehreren Hoehen fuer VIELE Lagen (Drehung, dx, dy) auf einmal - der Kern der Lagesuche.
    Auf GPU werden alle Lagen gleichzeitig gerastert (scatter_reduce amax ueber ein Batch), sonst Schleife.
    Rueckgabe: Array (len(lagen), len(stufen)) mit Flaechen in m2."""
    P = np.asarray(P, np.float32); T = _torch(); L = len(lagen); S = len(stufen)
    if not T:
        return np.array([[hypso(P, z, *lg, radius, raster, N) for z in stufen] for lg in lagen], float)
    # Blockgroesse nach freiem GPU-Speicher: je Lage und Punkt fallen ~40 Byte an (x, y, ix, iy, Maske, flache Indizes).
    frei = T.cuda.mem_get_info()[0]; proLage = len(P) * 40
    blk = max(1, min(L, int(0.5 * frei / max(proLage, 1))))
    if blk < L:
        return np.concatenate([hypso_lagen(P, stufen, lagen[i:i + blk], radius, raster, N) for i in range(0, L, blk)], 0)
    Pg = T.as_tensor(P, device="cuda")
    ang = T.as_tensor(np.radians([l[0] for l in lagen]).astype(np.float32), device="cuda")
    dxs = T.as_tensor(np.array([l[1] for l in lagen], np.float32), device="cuda"); dys = T.as_tensor(np.array([l[2] for l in lagen], np.float32), device="cuda")
    c, s_ = T.cos(ang)[:, None], T.sin(ang)[:, None]
    x = (c * Pg[None, :, 0] - s_ * Pg[None, :, 1] + dxs[:, None]) / raster           # (L, Npunkte)
    y = (s_ * Pg[None, :, 0] + c * Pg[None, :, 1] + dys[:, None]) / raster
    ix = T.floor(x + N / 2).long(); iy = T.floor(N / 2 - y).long()
    ok = (ix >= 0) & (ix < N) & (iy >= 0) & (iy < N)
    lid = T.arange(L, device="cuda")[:, None].expand_as(ix)
    flat = (lid * N * N + iy * N + ix)[ok]
    H = T.zeros(L * N * N, device="cuda"); H.scatter_reduce_(0, flat, Pg[None, :, 2].expand(L, -1)[ok], reduce="amax")
    H = H.reshape(L, N, N)
    pk = H.reshape(L, -1).argmax(1); py, px = pk // N, pk % N
    yy, xx = T.meshgrid(T.arange(N, device="cuda"), T.arange(N, device="cuda"), indexing="ij")
    nah = (((yy[None] - py[:, None, None]) ** 2 + (xx[None] - px[:, None, None]) ** 2).sqrt() <= radius / raster)
    out = T.stack([((H > z) & nah).reshape(L, -1).sum(1) for z in stufen], 1).float() * raster ** 2
    return out.cpu().numpy()

def hypso(P, z, drehung=98.0, dx=-1.0, dy=-1.0, radius=9.0, raster=1.0, N=60):
    """Flaeche ueber Hoehe z wie die Laser-Hypsometrie (Zellen eines 1-m-Rasters). Auf GPU fuer die Lagesuche (viele Drehungen)."""
    P = np.asarray(P); c, s = np.cos(np.radians(drehung)), np.sin(np.radians(drehung))
    x = (c * P[:, 0] - s * P[:, 1] + dx) / raster; y = (s * P[:, 0] + c * P[:, 1] + dy) / raster
    ix = np.floor(x + N / 2).astype(np.int64); iy = np.floor(N / 2 - y).astype(np.int64)
    ok = (ix >= 0) & (ix < N) & (iy >= 0) & (iy < N)
    H = np.zeros(N * N, np.float32); np.maximum.at(H, iy[ok] * N + ix[ok], P[ok, 2].astype(np.float32)); H = H.reshape(N, N)
    pk = np.unravel_index(np.argmax(H), H.shape); yy, xx = np.mgrid[:N, :N]
    return float(((H > z) & (np.hypot(yy - pk[0], xx - pk[1]) <= radius / raster)).sum()) * raster ** 2
