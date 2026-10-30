#!/usr/bin/env python3
"""arch_profile.py — GENERISCH: echte Bogen-Intrados-Kurve aus einem Foto messen (nicht
eine Kreis-/Halbkreis-ANNAHME aufzwingen) und als wiederverwendbare „Bogen-Signatur"
(Radius-Abweichung über Winkel) speichern. Jeder Generator kann damit die ECHTE Kurve
bauen statt eines idealen Halbkreises.

Pipeline:  Foto-Bogen → extract_profile() → δ(θ)-Signatur (.npy/.json)
           Generator   → build_arch_polygon(..., prof=Signatur) → echter Intrados
Validierung: measure_built() reproduziert die Signatur → Residuum ~0.

Nicht bauwerksspezifisch: funktioniert für Viadukt, Staumauer-Bogen, Tor, Fenster …
"""
import json
import numpy as np
import cv2
from scipy.ndimage import uniform_filter1d


# ---------- MESSEN: echte Intrados-Kurve aus Grau-Bild + grober Kreis ----------

def extract_profile(gray, cx, cy, R, amin=16, amax=164, step=0.6, nsamp=61):
    """Sub-pixel-Intrados radial messen → normierte Signatur δ(θ) (Springer auf 0 verankert,
    symmetrisiert). δ>0 = echter Bogen weiter außen als der Mittelkreis."""
    g = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), 1.2)
    rr = np.linspace(0.80*R, 1.20*R, 120)
    angs = np.deg2rad(np.arange(amin, amax, step))
    th_meas, r_meas = [], []
    for th in angs:
        xs = (cx + rr*np.cos(th)).astype(np.float32).reshape(-1, 1)
        ys = (cy - rr*np.sin(th)).astype(np.float32).reshape(-1, 1)
        val = uniform_filter1d(cv2.remap(g, xs, ys, cv2.INTER_LINEAR).ravel(), 5)
        grad = np.gradient(val)
        k = int(np.argmax(grad))
        if 2 < k < len(rr)-2 and grad[k] > 0.8:
            d = 0.5*(grad[k-1]-grad[k+1])/(grad[k-1]-2*grad[k]+grad[k+1]+1e-9)
            th_meas.append(th); r_meas.append(np.interp(k+d, range(len(rr)), rr))
    th_meas, r_meas = np.array(th_meas), np.array(r_meas)
    # auf feste θ-Gitter resamplen (0..π), symmetrisieren, glätten
    th_grid = np.linspace(0, np.pi, nsamp)
    r_grid = np.interp(th_grid, th_meas, r_meas, left=r_meas[0], right=r_meas[-1])
    r_grid = 0.5*(r_grid + r_grid[::-1])                 # symmetrisch (links=rechts)
    r_grid = uniform_filter1d(r_grid, 5)
    delta = r_grid/R - 1.0
    delta = delta - np.interp(th_grid, [0, np.pi], [delta[0], delta[-1]])  # Springer→0
    return th_grid, delta


def save_profile(path, th, delta, meta=None):
    json.dump({"theta": th.tolist(), "delta": delta.tolist(), "meta": meta or {}},
              open(path, "w"), indent=1)


def load_profile(path):
    d = json.load(open(path))
    return np.array(d["theta"]), np.array(d["delta"])


def profile_fn(th, delta):
    return lambda t: np.interp(t % np.pi if False else t, th, delta, left=0.0, right=0.0)


# ---------- BAUEN: Bogen-Öffnung mit ECHTER Kurve (prof=None → Halbkreis) ----------

def build_arch_polygon(xc, span, spring_z, prof=None, batter=0.04, nseg=64):
    """Öffnungs-Polygon: senkrechte Pfeiler-Leibung bis spring_z, dann Bogen nach prof.
    prof = (theta, delta) oder None (=idealer Halbkreis). Generisch."""
    from shapely.geometry import Polygon
    R = span/2
    f = (lambda t: 0.0) if prof is None else profile_fn(prof[0], prof[1])
    bw = R - batter*spring_z
    pts = [(xc-bw, 0), (xc-R, spring_z)]
    for t in np.linspace(np.pi, 0, nseg):
        r = R*(1.0 + f(t))
        pts.append((xc + r*np.cos(t), spring_z + r*np.sin(t)))
    pts.append((xc+bw, 0))
    return Polygon(pts)


# ---------- KORBBOGEN: echte 3-zentrige Bogenform (generisch) ----------

def basket_arch_xz(span, rise, haunch_ratio=0.5, nseg=200):
    """3-zentriger Korbbogen (anse de panier): Scheitelbogen (groß) + zwei Kämpferbögen
    (klein), tangentenstetig. a=Halbspann, h=Stich. Freier Parameter = Kämpfer-Radius
    rho=haunch_ratio·a (auf <h geklemmt). rise=span/2 ⇒ exakter Halbkreis.
    Rückgabe: (x,z)-Punkte Kämpfer(-a,0) → Scheitel(0,h) → Kämpfer(a,0). GENERISCH."""
    a = span/2.0; h = float(rise)
    if h >= a - 1e-9:                                  # Halbkreis-Sonderfall
        t = np.linspace(np.pi, 0.0, 2*nseg)
        return np.column_stack([a*np.cos(t), a*np.sin(t)])
    rho = min(haunch_ratio*a, 0.95*h)                  # Kämpfer-Radius (klein)
    R = ((a-rho)**2 + h**2 - rho**2) / (2.0*(h-rho))   # Scheitel-Radius aus Tangenten-Bedingung
    C1 = np.array([0.0, h-R]); C2 = np.array([a-rho, 0.0])
    u = (C2-C1)/np.hypot(*(C2-C1)); T = C1 + R*u       # Übergangspunkt (Tangente stetig)
    a1 = np.linspace(np.arctan2(h-C1[1], -C1[0]), np.arctan2(T[1]-C1[1], T[0]-C1[0]), nseg)
    p1 = C1 + R*np.column_stack([np.cos(a1), np.sin(a1)])          # Scheitelbogen
    a2 = np.linspace(np.arctan2(T[1]-C2[1], T[0]-C2[0]), np.arctan2(-C2[1], a-C2[0]), nseg)
    p2 = C2 + rho*np.column_stack([np.cos(a2), np.sin(a2)])        # Kämpferbogen
    right = np.vstack([p1, p2])                        # Scheitel → Kämpfer (rechts)
    left = right[::-1].copy(); left[:, 0] *= -1        # gespiegelt
    return np.vstack([left, right])


def basket_arch_profile(span, rise, haunch_ratio=0.5, nsamp=61):
    """Korbbogen als (theta, delta)-Signatur rel. zu R=span/2 → plug-in für profile_fn /
    build_arch_polygon / archivolt_band (genau wie ein gemessenes Foto-Profil).
    rise=span/2 ⇒ delta≈0 (Halbkreis). So wird der Korbbogen zum allgemeinen Default."""
    xz = basket_arch_xz(span, rise, haunch_ratio)
    R = span/2.0
    th = np.arctan2(xz[:, 1], xz[:, 0]); r = np.hypot(xz[:, 0], xz[:, 1])
    o = np.argsort(th); grid = np.linspace(0.0, np.pi, nsamp)
    rg = np.interp(grid, th[o], r[o])
    return grid, rg/R - 1.0


# ---------- STIRNBOGEN / ARCHIVOLT: Bogen-Verdickung (generisch) ----------

def archivolt_band(xc, half, spring_z, rise=None, d_crown=1.0, d_spring=1.8,
                   skirt=1.6, prof=None, nseg=96):
    """Stirnbogen-/Archivolt-BAND (2D x-z) um EINE Bogenöffnung: innere Kante = Intrados,
    äußere = Intrados nach außen versetzt um eine Bogendicke, die vom Scheitel (d_crown)
    zum Kämpfer (d_spring) wächst → die charakteristische „Verdickung unterhalb der Bögen".

    Versatz entlang der ECHTEN Kurven-Normalen ⇒ gilt für Halbkreis (rise=half),
    Korbbogen-Ellipse (rise≠half) UND gemessenes Profil (prof). `skirt` läuft senkrecht
    unter den Kämpfer. Rückgabe = ein geschlossenes shapely-Polygon (Band).

    Nicht bauwerksspezifisch — jeder Bogen-Generator extrudiert das Band selbst und legt
    es (vorspringend) auf seine Stirnfläche(n)."""
    from shapely.geometry import Polygon
    if rise is None:
        rise = half
    f = (lambda t: 0.0) if prof is None else profile_fn(prof[0], prof[1])
    aa = np.linspace(np.pi, 0.0, nseg)
    g = 1.0 + f(aa)
    ix = xc + half * g * np.cos(aa)
    iz = spring_z + rise * g * np.sin(aa)                  # Intrados (Kreis/Ellipse/Profil)
    tx, tz = np.gradient(ix), np.gradient(iz)              # Tangente → Normale (90°-Drehung)
    nx, nz = tz.copy(), -tx.copy()
    ln = np.hypot(nx, nz) + 1e-9; nx /= ln; nz /= ln
    out = ((ix - xc) * nx + (iz - spring_z) * nz) < 0      # nach außen (weg von der Bogenmitte)
    nx[out] *= -1; nz[out] *= -1
    t = d_crown + (d_spring - d_crown) * (np.abs(aa - np.pi/2) / (np.pi/2))  # Scheitel→Kämpfer
    ox, oz = ix + t * nx, iz + t * nz                      # Extrados (äußere Bandkante)
    zlo = spring_z - skirt
    outer = [(xc-half-d_spring, zlo)] + list(zip(ox, oz)) + [(xc+half+d_spring, zlo)]
    inner = [(xc-half, zlo)]        + list(zip(ix, iz)) + [(xc+half, zlo)]
    return Polygon(outer + inner[::-1])                    # geschlossenes Band (offen nach unten)


# ---------- VALIDIEREN: gebauten Bogen rastern + Signatur zurückmessen ----------

def measure_built(xc, span, spring_z, prof=None, pxm=10.0):
    poly = build_arch_polygon(xc, span, spring_z, prof)
    minx, miny, maxx, maxy = poly.bounds
    W = int((maxx-minx)*pxm)+20; H = int((maxy-miny)*pxm)+20
    img = np.full((H, W), 255, np.uint8)        # Stein=hell
    def px(xy): return np.array([[int((x-minx)*pxm)+10, H-10-int((z-miny)*pxm)] for x, z in xy], np.int32)
    cv2.fillPoly(img, [px(poly.exterior.coords)], 0)   # Öffnung=dunkel (wie Durchsicht im Foto)
    # Mittelkreis-Schätzung = Halbkreis um Springer-Mitte
    cxp = (xc-minx)*pxm+10; cyp = H-10-(spring_z-miny)*pxm; Rp = (span/2)*pxm
    return extract_profile(img, cxp, cyp, Rp)   # Öffnung=schwarz(0), Stein=weiß(255): radial dunkel→hell


def residual_pct(delta):
    sm = uniform_filter1d(delta, 5)
    return float((np.percentile(sm, 95)-np.percentile(sm, 5))*100)


if __name__ == "__main__":
    import argparse, sys
    sys.path.insert(0, ".")
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", help="Foto zum Profil-Extrahieren")
    ap.add_argument("--save", default="")
    a = ap.parse_args()
    if a.img:
        import foto_metrologie as fm
        img = cv2.imread(a.img); H, W = img.shape[:2]; sc = 2000/W
        img = cv2.resize(img, (2000, int(H*sc)))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        best = None
        for c in fm.opening_masks(img):
            m = fm.measure_arch(c)
            if m and m["semicircle"] and (best is None or m["span"] > best["span"]):
                best = m
        th, delta = extract_profile(gray, best["cx"], best["cy"], best["R"])
        print(f"Profil gemessen: Abweichung vom Kreis {residual_pct(delta):.2f} % von R")
        if a.save:
            save_profile(a.save, th, delta, {"src": a.img, "R_px": best["R"]})
            print("gespeichert:", a.save)
