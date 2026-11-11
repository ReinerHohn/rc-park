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
    # Bloecke (2026-11-04): vorher 8 M Punkte auf einmal -> ~0,7 GB Zwischenfelder je Aufruf (begrenzte die parallelen foto_diff-Arbeiter).
    # Z-Puffer = Minimum (reihenfolgeunabhaengig); Gewinnerzuordnung in derselben Punktreihenfolge (letzter gewinnt wie vorher) -> bitgleich.
    B = 1 << 20; n = len(P); T = _torch(); teile = []
    d = T.full((H * W,), float("inf"), device="cuda") if T else np.full(H * W, np.inf, np.float32)
    for s in range(0, n, B):
        uv, z = projiziere(P[s:s + B], R, t, f, cx, cy)
        u = np.rint(uv[:, 0]).astype(np.int64); v = np.rint(uv[:, 1]).astype(np.int64)
        ok = (z > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        flat = (v[ok] * W + u[ok]); zz = z[ok].astype(np.float32); wo = np.nonzero(ok)[0] + s; del uv, z, u, v, ok
        if T: d.scatter_reduce_(0, T.as_tensor(flat, device="cuda"), T.as_tensor(zz, device="cuda"), reduce="amin")
        else: np.minimum.at(d, flat, zz)
        teile.append((flat, zz, wo))
    depth = (d.cpu().numpy() if T else d).reshape(H, W); dr = depth.ravel()
    idx = np.full(H * W, -1, np.int64)
    for flat, zz, wo in teile:
        treffer = np.isclose(dr[flat], zz)                             # Punkte, die den Z-Puffer gewonnen haben
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

def dreiecke_rastern_alt(mm, R, t, f, cx, cy, W, H, block=None, als_torch=False):
    """Netz (trimesh, Weltrahmen) auf der GPU EXAKT rastern (Z-Puffer je Pixel, perspektivisch korrekte Tiefe), kein Punkt-Abtasten mehr.
    Warum (2026-11-04): Punkt-Abtastung liess Pixel ohne Punkt auf der Vorderflaeche -> dahinterliegende (dunkle) Flaeche schien durch = Pixel-Pfeffer und
    Scheinkanten im 'Foto'. Streuungsmessung Martinstor 014: T1 je Saat CPU 24,8/32,2/29,8/27,5 %, GPU-Punkte 26,4/25,0/25,6/23,8 % (Grenze 25 %) - der Beweis
    hing an der Saat. Exakt gerastert gibt es weder Loecher noch Zufall. Pixel i deckt [i-0.5, i+0.5] wie der Punktrenderer (Rundung), Pruefpunkt = Pixelmitte.
    Gleichstand (deckungsgleiche Flaechen, relativ 1e-6 der Tiefe): zur Kamera
    gewandt vor abgewandt, dann kleinste Dreiecksnummer. ANNAHME: Dreiecke mit einer Ecke <= 1 m vor der Kamera fallen weg (wie z > 1 im Punktrenderer).
    Rueckgabe depth (H,W float32, inf leer), fid (H,W, Dreiecksnummer, -1 leer), pos (H,W,3 Weltpunkt der Pixelmitte); numpy, mit als_torch=True fid/pos als GPU-Tensoren."""
    import torch
    Rg = torch.as_tensor(np.asarray(R, float), dtype=torch.float64, device="cuda"); tg = torch.as_tensor(np.asarray(t, float).ravel(), dtype=torch.float64, device="cuda")
    Tw = torch.as_tensor(np.asarray(mm.triangles), dtype=torch.float64, device="cuda"); X = Tw @ Rg.T + tg; z = X[..., 2]   # (F,3) Kameratiefe der Ecken
    Nc = torch.as_tensor(np.asarray(mm.face_normals), dtype=torch.float64, device="cuda") @ Rg.T
    zs = z.clamp(min=1e-9); u = f * X[..., 0] / zs + cx; v = f * X[..., 1] / zs + cy
    x0 = torch.ceil(u.min(1).values - 0.5).clamp(min=0); x1 = torch.floor(u.max(1).values + 0.5).clamp(max=W - 1)
    y0 = torch.ceil(v.min(1).values - 0.5).clamp(min=0); y1 = torch.floor(v.max(1).values + 0.5).clamp(max=H - 1)
    fl2 = (u[:, 1] - u[:, 0]) * (v[:, 2] - v[:, 0]) - (u[:, 2] - u[:, 0]) * (v[:, 1] - v[:, 0])
    gut = (z > 1).all(1) & (x1 >= x0) & (y1 >= y0) & (fl2.abs() > 1e-12)
    ids = torch.nonzero(gut, as_tuple=True)[0]; nx = (x1 - x0 + 1)[ids].long(); ny = (y1 - y0 + 1)[ids].long(); cnt = nx * ny
    # RCPARK_RASTER_F32=1 (Versuch 10.11. abends, Profil: 40 von 50 s je Foto in paare()): Pixel-Schleife in float32 statt float64 - GeForce-Karten
    # rechnen float64 mit ~1/64 der Rate. Je-Dreieck-Werte bleiben in float64 berechnet und werden nur gerundet. NICHT bitgleich -> Gegenprobe Pflicht.
    if os.environ.get("RCPARK_RASTER_F32") == "1":
        u, v, z, fl2, Nc, x0, y0 = (q.float() for q in (u, v, z, fl2, Nc, x0, y0))
    if block is None:   # 10.11.: feste 1<<20 Paare -> 2612 Python-Durchlaeufe je Foto (32 s von ~50). Block nach freiem VRAM (~200 Byte je Paar, 25 %), 1<<20..1<<24.
        block = int(min(1 << 24, max(1 << 20, 0.25 * torch.cuda.mem_get_info()[0] / 200)))   # amin-Reduktion ist reihenfolgefrei -> Ergebnis bitgleich
    grenzen = [0]; summe = 0                                                                        # Dreiecks-Bloecke mit <= block Pixel-Paaren
    for i, c in enumerate(cnt.tolist()):
        if summe + c > block and i > grenzen[-1]: grenzen.append(i); summe = 0
        summe += c
    grenzen.append(len(ids))
    def paare():                                                                                    # (Dreiecksnummer, flacher Pixelindex, Tiefe, abgewandt) je ueberdecktem Pixel
        for a_, b_ in zip(grenzen[:-1], grenzen[1:]):
            if b_ <= a_: continue
            fi = ids[a_:b_]; c = cnt[a_:b_]; k = torch.repeat_interleave(torch.arange(b_ - a_, device="cuda"), c)
            off = torch.cumsum(c, 0) - c; lok = torch.arange(int(c.sum()), device="cuda") - off[k]; f_ = fi[k]
            px = x0[f_] + (lok % nx[a_:b_][k]); py = y0[f_] + (lok // nx[a_:b_][k])
            U, V = u[f_], v[f_]; A = fl2[f_]
            w1 = ((px - U[:, 0]) * (V[:, 2] - V[:, 0]) - (U[:, 2] - U[:, 0]) * (py - V[:, 0])) / A
            w2 = ((U[:, 1] - U[:, 0]) * (py - V[:, 0]) - (px - U[:, 0]) * (V[:, 1] - V[:, 0])) / A; w0 = 1 - w1 - w2
            drin = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            Z = z[f_]; tief = 1.0 / (w0 / Z[:, 0] + w1 / Z[:, 1] + w2 / Z[:, 2])                    # perspektivisch korrekt: 1/z linear im Bild
            f_, px, py, tief = f_[drin], px[drin].long(), py[drin].long(), tief[drin]
            Xp = torch.stack([(px - cx) / f * tief, (py - cy) / f * tief, tief], 1)
            yield f_, py * W + px, tief, ((Nc[f_] * Xp).sum(1) > 0).long()
    d = torch.full((H * W,), float("inf"), dtype=z.dtype, device="cuda")
    for _, fl, tief, _ in paare(): d.scatter_reduce_(0, fl, tief, reduce="amin")
    # Gleichstand nur fuer wirklich deckungsgleiche Flaechen: relative Toleranz 1e-6 der Tiefe (~30 um, float64 exakt gerastert). Erst 2 cm (aus der Punktfassung)
    # -> Kaufhaus-Gauben 1-2 cm vor der Dachflaeche verschwanden hinter dem Dach (kleinere Dreiecksnummer gewann), Sichtpruefung 2026-11-04.
    EPS_REL = 1e-6
    # Speicher (2026-11-04, Kaufhaus 023/000 mit 24-86 MP liefen ueber): Auswahl in int32, Weltpunkte blockweise statt H*W x 3 in 64 Bit am Stueck. Werte gleich.
    GROSS = len(mm.faces) + 1; it = torch.int32 if 2 * GROSS < 2 ** 31 else torch.long; fw = torch.full((H * W,), 2 * GROSS, dtype=it, device="cuda")
    for f_, fl, tief, ab in paare():
        dm = d[fl]; w = tief <= dm * (1 + EPS_REL) + 1e-9; fw.scatter_reduce_(0, fl[w], (ab[w] * GROSS + f_[w]).to(it), reduce="amin")
    fid = torch.where(fw >= 2 * GROSS, torch.full_like(fw, -1), fw % GROSS).long(); del fw
    pos = torch.zeros((H * W, 3), dtype=torch.float32, device="cuda")
    for s in range(0, H * W, 1 << 22):
        pi = torch.arange(s, min(s + (1 << 22), H * W), device="cuda"); dd = d[s:s + len(pi)]; dd = torch.where(torch.isfinite(dd), dd, torch.zeros_like(dd))
        Xp = torch.stack([((pi % W) - cx) / f * dd, ((pi // W) - cy) / f * dd, dd], 1); pos[s:s + len(pi)] = ((Xp - tg) @ Rg).float()   # Welt = R^T (X - t)
    pos[fid < 0] = 0; dn = d.float().reshape(H, W).cpu().numpy(); del d
    if als_torch: return dn, fid.reshape(H, W), pos.reshape(H, W, 3)
    out = (dn, fid.reshape(H, W).cpu().numpy(), pos.reshape(H, W, 3).cpu().numpy())
    del Tw, X, Nc, fid, pos; torch.cuda.empty_cache(); return out


def dreiecke_rastern(mm, R, t, f, cx, cy, W, H, block=None, als_torch=False, nur_tiefe=False):
    """Standard seit 11.11.: schnelle Fassung (Zeilen-Spannen + Einzeldurchlauf), BITGLEICH zu dreiecke_rastern_alt (Gegenprobe 37 Fotos x 4 Netze, tools/regression).
    RCPARK_RASTER_ALT=1 = alte Fassung. nur_tiefe=True: nur Tiefenbild (fid/pos = None), fuer Aufrufer, die nur depth brauchen."""
    if os.environ.get("RCPARK_RASTER_ALT") == "1":
        r = dreiecke_rastern_alt(mm, R, t, f, cx, cy, W, H, block, als_torch)
        return (r[0], None, None) if nur_tiefe else r
    return _raster_schnell(mm, R, t, f, cx, cy, W, H, block, als_torch, nur_tiefe)


def _raster_schnell(mm, R, t, f, cx, cy, W, H, block=None, als_torch=False, nur_tiefe=False):
    """Siehe dreiecke_rastern_alt (gleiche Rechnung, gleiches Ergebnis bitgleich). Beschleunigung (11.11., Nutzerauftrag teil_fotoform halbe Laufzeit):
    (1) Zeilen-Spannen statt Bounding-Box: je Dreieck und Bildzeile wird das x-Intervall, in dem alle drei Randfunktionen >= 0 sein koennen, analytisch (float64)
        bestimmt und um 1,5 px erweitert (konservativ: Obermenge der Pixel mit drin=True); der EXAKTE Innentest bleibt derselbe -> Ergebnis gleich, nur 5-6x weniger Paare.
    (2) EIN Durchlauf statt zwei: nach jedem Block werden Paare behalten, die gegen die laufende Minimaltiefe noch gewinnen koennten (laufend >= endgueltig -> Obermenge),
        am Ende gegen die endgueltige Tiefe gefiltert. Gleiche Rechnung je Paar, amin ist reihenfolgefrei."""
    import torch
    Rg = torch.as_tensor(np.asarray(R, float), dtype=torch.float64, device="cuda"); tg = torch.as_tensor(np.asarray(t, float).ravel(), dtype=torch.float64, device="cuda")
    Tw = torch.as_tensor(np.array(mm.triangles), dtype=torch.float64, device="cuda"); X = Tw @ Rg.T + tg; z = X[..., 2]
    Nc = torch.as_tensor(np.asarray(mm.face_normals), dtype=torch.float64, device="cuda") @ Rg.T
    zs = z.clamp(min=1e-9); u = f * X[..., 0] / zs + cx; v = f * X[..., 1] / zs + cy
    x0 = torch.ceil(u.min(1).values - 0.5).clamp(min=0); x1 = torch.floor(u.max(1).values + 0.5).clamp(max=W - 1)
    y0 = torch.ceil(v.min(1).values - 0.5).clamp(min=0); y1 = torch.floor(v.max(1).values + 0.5).clamp(max=H - 1)
    fl2 = (u[:, 1] - u[:, 0]) * (v[:, 2] - v[:, 0]) - (u[:, 2] - u[:, 0]) * (v[:, 1] - v[:, 0])
    gut = (z > 1).all(1) & (x1 >= x0) & (y1 >= y0) & (fl2.abs() > 1e-12)
    ids = torch.nonzero(gut, as_tuple=True)[0]; nrow = (y1 - y0 + 1)[ids].long()
    # --- Zeilen-Spannen: (Dreieck, Zeile) -> [lo, lo+len) ---
    RB = 1 << 22; tri_l, py_l, lo_l, len_l = [], [], [], []
    cs = torch.cumsum(nrow, 0); tot = int(cs[-1]) if len(cs) else 0; s = 0
    while s < tot:
        a_ = int(torch.searchsorted(cs, s, right=True)); b_ = int(torch.searchsorted(cs, s + RB, right=True)); b_ = max(b_, a_ + 1); b_ = min(b_, len(ids))
        fi = ids[a_:b_]; c = nrow[a_:b_]; k = torch.repeat_interleave(torch.arange(b_ - a_, device="cuda"), c)
        off = torch.cumsum(c, 0) - c; lok = torch.arange(int(c.sum()), device="cuda") - off[k]; f_ = fi[k]; py = y0[f_] + lok
        U, V = u[f_], v[f_]; lo = x0[f_].clone(); hi = x1[f_].clone(); A = fl2[f_]; sg = torch.sign(A)
        # w1*A = a1*px + c1 mit a1 = (V2-V0), c1 = -U0*(V2-V0) - (U2-U0)*(py-V0); w2*A = a2*px + c2, a2 = -(V1-V0), c2 = (U1-U0)*(py-V0) + U0*(V1-V0); w0*A = A - w1*A - w2*A
        a1 = V[:, 2] - V[:, 0]; c1 = -U[:, 0] * a1 - (U[:, 2] - U[:, 0]) * (py - V[:, 0])
        a2 = -(V[:, 1] - V[:, 0]); c2 = (U[:, 1] - U[:, 0]) * (py - V[:, 0]) - U[:, 0] * a2
        a0 = -a1 - a2; c0 = A - c1 - c2
        for ai, ci in ((a1, c1), (a2, c2), (a0, c0)):
            asg = ai * sg; fest = ai.abs() >= 1e-3; bound = -ci / torch.where(fest, ai, torch.ones_like(ai))
            lo = torch.where(fest & (asg > 0), torch.maximum(lo, torch.ceil(bound - 1.5)), lo)
            hi = torch.where(fest & (asg < 0), torch.minimum(hi, torch.floor(bound + 1.5)), hi)
        ln = (hi - lo + 1).clamp(min=0).long(); ok = ln > 0
        tri_l.append(f_[ok].int()); py_l.append(py[ok].int()); lo_l.append(lo[ok].int()); len_l.append(ln[ok].int())
        s = int(cs[b_ - 1]); del fi, c, k, off, lok, f_, py, U, V, lo, hi, A, sg, a1, c1, a2, c2, a0, c0, ln, ok
    if tri_l:
        tri_a, py_a, lo_a, len_a = (torch.cat(q) for q in (tri_l, py_l, lo_l, len_l))
    else:
        tri_a = py_a = lo_a = len_a = torch.zeros(0, dtype=torch.int32, device="cuda")
    del tri_l, py_l, lo_l, len_l
    if os.environ.get("RCPARK_RASTER_F32") == "1":
        u, v, z, fl2, Nc, x0, y0 = (q.float() for q in (u, v, z, fl2, Nc, x0, y0))
    if block is None:
        block = int(min(1 << 24, max(1 << 20, 0.25 * torch.cuda.mem_get_info()[0] / 200)))
    cl = torch.cumsum(len_a.long(), 0); nz = len(len_a); grenzen = [0]
    if nz:
        tl = int(cl[-1]); g = block
        while g < tl:
            i = int(torch.searchsorted(cl, g, right=True))
            if i > grenzen[-1] and i < nz: grenzen.append(i)
            g = int(cl[min(i, nz - 1)]) + block if i < nz else tl
        grenzen.append(nz)
    GROSS = len(mm.faces) + 1; it = torch.int32 if 2 * GROSS < 2 ** 31 else torch.long
    d = torch.full((H * W,), float("inf"), dtype=z.dtype, device="cuda"); EPS_REL = 1e-6
    bw_fl, bw_t, bw_k = [], [], []; held = 0; limit = 1 << 24
    def filt(lst_fl, lst_t, lst_k):
        fl_, t_, k_ = torch.cat(lst_fl), torch.cat(lst_t), torch.cat(lst_k); w = t_ <= d[fl_] * (1 + EPS_REL) + 1e-9
        return [fl_[w]], [t_[w]], [k_[w]]
    for a_, b_ in zip(grenzen[:-1], grenzen[1:]):
        if b_ <= a_: continue
        c = len_a[a_:b_].long(); n = int(c.sum()); k = torch.repeat_interleave(torch.arange(b_ - a_, device="cuda"), c)
        off = torch.cumsum(c, 0) - c; lok = torch.arange(n, device="cuda") - off[k]
        f_ = tri_a[a_:b_][k].long(); px = (lo_a[a_:b_][k].long() + lok).to(z.dtype if z.dtype == torch.float64 else torch.float32); py = py_a[a_:b_][k].to(px.dtype)
        U, V = u[f_], v[f_]; A = fl2[f_]
        w1 = ((px - U[:, 0]) * (V[:, 2] - V[:, 0]) - (U[:, 2] - U[:, 0]) * (py - V[:, 0])) / A
        w2 = ((U[:, 1] - U[:, 0]) * (py - V[:, 0]) - (px - U[:, 0]) * (V[:, 1] - V[:, 0])) / A; w0 = 1 - w1 - w2
        drin = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        Z = z[f_]; tief = 1.0 / (w0 / Z[:, 0] + w1 / Z[:, 1] + w2 / Z[:, 2])
        f_, px, py, tief = f_[drin], px[drin].long(), py[drin].long(), tief[drin]
        Xp = torch.stack([(px - cx) / f * tief, (py - cy) / f * tief, tief], 1); ab = ((Nc[f_] * Xp).sum(1) > 0).long(); fl = py * W + px
        d.scatter_reduce_(0, fl, tief, reduce="amin")
        if nur_tiefe: del c, k, off, lok, f_, px, py, U, V, A, w1, w2, w0, drin, Z, tief, Xp, ab, fl; continue   # nur Tiefe (teil_fotoform Teilraster): keine Gewinnerzuordnung, kein pos
        w = tief <= d[fl] * (1 + EPS_REL) + 1e-9
        bw_fl.append(fl[w]); bw_t.append(tief[w]); bw_k.append((ab[w] * GROSS + f_[w]).to(it)); held += int(w.sum())
        if held > limit:
            bw_fl, bw_t, bw_k = filt(bw_fl, bw_t, bw_k); held = len(bw_fl[0]); limit = max(1 << 24, 2 * held)
        del c, k, off, lok, f_, px, py, U, V, A, w1, w2, w0, drin, Z, tief, Xp, ab, fl, w
    if nur_tiefe:
        dn = d.float().reshape(H, W).cpu().numpy(); del d, Tw, X, Nc; return dn, None, None
    fw = torch.full((H * W,), 2 * GROSS, dtype=it, device="cuda")
    if bw_fl:
        fl_, t_, k_ = torch.cat(bw_fl), torch.cat(bw_t), torch.cat(bw_k); w = t_ <= d[fl_] * (1 + EPS_REL) + 1e-9
        fw.scatter_reduce_(0, fl_[w], k_[w], reduce="amin")
    fid = torch.where(fw >= 2 * GROSS, torch.full_like(fw, -1), fw % GROSS).long(); del fw
    pos = torch.zeros((H * W, 3), dtype=torch.float32, device="cuda")
    for s in range(0, H * W, 1 << 22):
        pi = torch.arange(s, min(s + (1 << 22), H * W), device="cuda"); dd = d[s:s + len(pi)]; dd = torch.where(torch.isfinite(dd), dd, torch.zeros_like(dd))
        Xp = torch.stack([((pi % W) - cx) / f * dd, ((pi // W) - cy) / f * dd, dd], 1); pos[s:s + len(pi)] = ((Xp - tg) @ Rg).float()
    pos[fid < 0] = 0; dn = d.float().reshape(H, W).cpu().numpy(); del d
    if als_torch: return dn, fid.reshape(H, W), pos.reshape(H, W, 3)
    out = (dn, fid.reshape(H, W).cpu().numpy(), pos.reshape(H, W, 3).cpu().numpy())
    del Tw, X, Nc, fid, pos; torch.cuda.empty_cache(); return out


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
