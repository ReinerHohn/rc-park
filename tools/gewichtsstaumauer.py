#!/usr/bin/env python3
"""gewichtsstaumauer.py — parametrische GERADE/gekrümmte Gewichtsstaumauer als STL.
Für Schluchsee-Staumauer (Seebrugg): Trapez-Querschnitt (vertikale Wasserseite,
geneigte Luftseite) entlang der echten OSM-Kronenachse geloftet.

Masse Schluchsee: H=63,5 m, Kronenlänge 250 m, Kronenbreite 3,7 m (Recherche).

Aufruf:
  python3 tools/gewichtsstaumauer.py --H 63.5 --crown 3.7 --base 50 --nscale 1.0 \
      --lat 47.80064 --lon 8.18361 --out /tmp/schluchsee/staumauer.stl
"""
import argparse, sys, urllib.request, urllib.parse, json
import numpy as np


OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]


def osm_axis(lat, lon, radius=400):
    q = (f'[out:json][timeout:30];way["waterway"="dam"](around:{radius},{lat},{lon});out geom;')
    from pyproj import Transformer
    T = Transformer.from_crs(4326, 25832, always_xy=True)
    for base in OVERPASS:
        for _ in range(2):
            try:
                url = base + '?' + urllib.parse.urlencode({'data': q})
                req = urllib.request.Request(url, headers={'User-Agent': 'modellbau/1.0'})
                d = json.load(urllib.request.urlopen(req, timeout=40))
                for e in d.get('elements', []):
                    g = e.get('geometry', [])
                    if len(g) >= 2:
                        pts = np.array([T.transform(p['lon'], p['lat']) for p in g])
                        return pts, e.get('tags', {}).get('name', 'dam')
            except Exception as ex:
                last = ex
    # Fallback: synthetische leicht gekrümmte Achse aus bekannter BBox (Schluchsee)
    print(f"  (OSM nicht erreichbar: {last}; nutze synthetische Achse aus BBox)")
    E0, E1, N0, N1 = 438822, 438900, 5294338, 5294560
    tN = np.linspace(N0, N1, 40)
    tE = (E0 + E1) / 2 + 18 * np.sin(np.linspace(0, np.pi, 40))   # leichte Krümmung
    return np.c_[tE, tN], "Schluchsee-Staumauer (synthetisch)"


def centerline(pts, nbins=60):
    """OSM-Weg tracet die Kronen-Kontur (beide Kanten, hin+zurück) → echte MITTELlinie:
    auf Hauptachse (PCA) projizieren, in Bins entlang der Achse die Punkte MITTELN
    (kollabiert die zwei parallelen Kanten zu einer Linie), dann leicht glätten."""
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c)
    ax1, ax2 = vt[0], vt[1]
    t = (pts - c) @ ax1
    tmin, tmax = t.min(), t.max()
    edges = np.linspace(tmin, tmax, nbins + 1)
    mids = []
    for i in range(nbins):
        m = (t >= edges[i]) & (t <= edges[i + 1])
        if m.sum():
            mids.append(pts[m].mean(0))
    line = np.array(mids)
    # glätten (gleitender Mittelwert)
    if len(line) >= 5:
        k = np.ones(3) / 3
        line[:, 0] = np.convolve(line[:, 0], k, mode='same')
        line[:, 1] = np.convolve(line[:, 1], k, mode='same')
        line = line[1:-1]
    return line


def build(center, H, crown, base, nscale, face_prof=None):
    """Loft Querschnitt entlang Mittellinie. face_prof=(z_rel, dev_rel) → echte Luftseiten-KURVE
    (Dicke-Abweichung über Höhe) statt gerader Böschung. Gibt (verts, faces) in Modell-mm."""
    c0 = center.mean(0)
    cen = (center - c0) * nscale          # Meter→mm, zentriert
    H *= nscale; crown *= nscale; base *= nscale
    # lokale Normale je Stützpunkt
    tang = np.gradient(cen, axis=0); tang /= (np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9)
    nrm = np.c_[-tang[:, 1], tang[:, 0]]  # 90°
    # Querschnitt (u über Mauerdicke, z vertikal) — ECHTE Gewichtsmauer: Wasserseite SENKRECHT
    # (u=0 von Fuß bis Krone), Luftseite GEBÖSCHT (base am Fuß → crown an der Krone).
    if face_prof is None:
        sec = [(0.0, 0), (base, 0), (crown, H), (0.0, H)]
    else:
        zr, dr = face_prof
        sec = [(0.0, 0)]
        for t in np.linspace(0, 1, 40):          # Luftseite als gemessene Kurve
            z = t * H
            u = base + (crown - base) * t + np.interp(t, zr, dr) * H  # +dev (Meter→mm via H-skaliert)
            sec.append((u, z))
        sec.append((0.0, H))
    N = len(cen); V = []
    for i in range(N):
        P = cen[i]; nx, ny = nrm[i]
        for (u, z) in sec:
            V.append([P[0] + u * nx, P[1] + u * ny, z])
    V = np.array(V)
    F = []
    ns = len(sec)
    for i in range(N - 1):
        a = i * ns; b = (i + 1) * ns
        for k in range(ns):
            k2 = (k + 1) % ns
            F += [[a + k, b + k, a + k2], [a + k2, b + k, b + k2]]
    # Endkappen (Dreiecks-Fan)
    for ring, flip in [(0, False), ((N - 1) * ns, True)]:
        for k in range(1, ns - 1):
            tri = [ring, ring + k, ring + k + 1]
            F.append(tri[::-1] if flip else tri)
    return V, np.array(F)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--H", type=float, default=63.5)
    ap.add_argument("--crown", type=float, default=3.7)
    ap.add_argument("--base", type=float, default=50.0)
    ap.add_argument("--nscale", type=float, default=1.0, help="mm je echtem Meter (1.0 = 1:1000)")
    ap.add_argument("--lat", type=float, default=47.80064)
    ap.add_argument("--lon", type=float, default=8.18361)
    ap.add_argument("--out", default="/tmp/schluchsee/staumauer.stl")
    ap.add_argument("--face-profile", default="", help="gemessenes Luftseiten-Profil (JSON) statt gerader Böschung")
    a = ap.parse_args()
    import trimesh, json
    fprof = None
    if a.face_profile:
        d = json.load(open(a.face_profile))
        fprof = (np.array(d["z_rel"]), np.array(d["dev_rel"]))
        print(f"Luftseite: gemessenes Profil {a.face_profile} (echte Kurve, keine Gerade)")

    pts, name = osm_axis(a.lat, a.lon)
    if pts is None:
        sys.exit("keine OSM-Mauer gefunden")
    cen = centerline(pts)
    length_m = np.linalg.norm(np.diff(cen, axis=0), axis=1).sum()
    print(f"OSM '{name}': Kronenachse {len(cen)} Pkt, Länge {length_m:.0f} m")
    V, F = build(cen, a.H, a.crown, a.base, a.nscale, face_prof=fprof)
    m = trimesh.Trimesh(vertices=V, faces=F, process=True)
    m.fix_normals()
    import os; os.makedirs(os.path.dirname(a.out), exist_ok=True)
    m.export(a.out)
    bb = m.bounding_box.extents
    print(f"-> {a.out}  {bb[0]:.0f}×{bb[1]:.0f}×{bb[2]:.0f} mm  "
          f"watertight={m.is_watertight}  vol={m.volume/1000:.1f} cm³")


if __name__ == "__main__":
    main()
