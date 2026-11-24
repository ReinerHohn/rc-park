#!/usr/bin/env python3
"""quellfilter.py <workspace> [--ply <workspace>/fused.ply] [--stichprobe N] [--nur_messen] [--threads 4]
FREIRAUM-NACHFILTER DER DICHTEN WOLKE (24.11.2026, Kette schwabentor 1122z: blaeuliches "Geisterblatt" vor der Nordwand, x 4,8..9, ~12 200 Punkte,
faecherfoermig von Erker/Vordach). URSACHE (belegt): Silhouettenkanten in fast gleichen Videobildern bekommen verschleppte Kantentiefe und gelten in der
Fusion als mehrsichtig bestaetigt (96 % der Quellen eines Blattpunkts aus EINEM Video). Die Himmelsmaske (drahtmaske.py) nimmt nur ~3 % davon.
PRINZIP (Sichtbarkeit, wie Freiraum-Pruefung in MVS): jede Kamera, die den Punkt im Bild hat, sagt per Tiefenkarte entweder
  QUELLE    |d - z| < 1 % z         (sie sieht dort genau diese Flaeche)
  FREIRAUM  d > 1,05 z (d > 0)      (sie sieht durch die Stelle des Punktes HINDURCH auf etwas Ferneres -> dort ist Luft)
  (d < z = Verdeckung, sagt nichts). Ein Geisterpunkt im Freien wird von vielen ANDEREN Kameras durchschaut; ein echter Flaechenpunkt kaum.
REGEL (ANNAHME aus Messung 24.11., Tiefenkarten-Projektion 1122z, Unterstichprobe: Blatt 12 186 Punkte, echt 60 000 Zufallspunkte ausserhalb des Blattkastens):
  weg, wenn FREIRAUM >= 20 UND FREIRAUM >= 2,0 x QUELLE.
  Verteilungen FREIRAUM (10/25/50/75/90 %): Blatt 55/68/82/92/98, echt 6/9/12/18/26. Verhaeltnis F/Q: Blatt 2,4/2,9/3,6/4,3/7,3, echt 0,06/0,10/0,18/0,35/0,73.
  Mindestzahl 20 = Schutz fuer kleine Fotosaetze (wenige Kameras -> Filter greift nicht, statt zu raten).
SILHOUETTENSCHUTZ RAND = 1: Freiraum zaehlt nur, wenn auch die naechste Tiefe im 3x3-Fenster der Karte dahinter liegt. Ohne Fenster (RAND 0) fielen Punkte am
  Torbogen/Gewoelbe der Durchfahrt (Draufsicht z 2,5..9: Zellen bis 47-60 % weg) - Kantenpunkte, deren Nachbarpixel schon den Hintergrund zeigen.
  WIRKUNG (1/6-Unterstichprobe Gebaeudekasten, 2,69 Mio. Punkte, Bild /media/oem/scan/rc-park_tmp/quellfilter/vorher_nachher_r1.jpg):
    RAND 1: Blatt (blau) 89,5 % weg, Blattkasten nicht-blau 50,8 %; echt ausserhalb Blattkasten z >= 3: 1,05 % (Torbogen/untere Wand 1,27, Wand Mitte/Fenster 0,95,
            Wand oben 0,93, Dach/Helm 0,52, Helm/Laterne 0,43), Boden z < 3: 2,14 %; gesamt 1,7 %.
    RAND 2: Blatt 84,0 %, echt z >= 3: 0,86 %, Boden 1,5 % (Blatt-Rest zu gross).
    RAND 0: Blatt 95,3 %, echt z >= 3: 1,56 %, Boden 4,8 % -> RAND 1 gewaehlt (echte Punkte zuerst; Blatt-Ziel > 80 % bleibt erfuellt).
GUARD: wuerde der Filter > 10 % der Wolke nehmen, wird NICHTS geaendert (ACHTUNG-Zeile, Bericht trotzdem) - dann stimmt etwas mit Karten/Kameras nicht.
AUSGABE: <ply> gefiltert (in place, alter Stand wird nicht doppelt gehalten), entfernte Punkte -> <workspace>/fused_quellfilter_weg.ply (zur Sichtpruefung),
<ply>.quellfilter.json (Stand = code_stand(quellfilter.py), Punkte vorher/nachher, Regel). Ist <ply>.vis vorhanden, wird sie mitgefiltert.
Kette: tools/pipeline_objekt.py ruft nach der dichten Stufe quellfilter_noetig() -> dieses Werkzeug (RCPARK_QUELLFILTER=0 = aus).
Nur CPU (numpy), Speicher: Punkte in Bloecken (2 Mio.), je Thread eigene Zaehler."""
import os, sys, json, time, argparse, numpy as np
from concurrent.futures import ThreadPoolExecutor

DT = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
TOL_Q, TOL_V = 0.01, 0.05          # relative Tiefentoleranz Quelle / Freiraum (Quelle wie COLMAP-Fusion max_depth_error 0,01)
MIN_V, VERH = 20, 2.0              # ANNAHME (Messung oben)
GUARD = 0.10
RAND = 1                           # Silhouettenschutz-Fenster (Pixel der Tiefenkarte), siehe zaehlen_bild
BLOCK = 2_000_000


def tiefe_lesen(f):
    """COLMAP-Tiefenkarte (.bin: 'w&h&c&' + float32) -> (h, w)."""
    b = open(f, "rb").read(); k = 0; teile = []
    for _ in range(3):
        j = b.index(b"&", k); teile.append(int(b[k:j])); k = j + 1
    w, h, _c = teile
    return np.frombuffer(b, "<f4", offset=k, count=w * h).reshape((h, w))


def min_karte(tiefe, r):
    """Kleinste gueltige Tiefe im (2r+1)^2-Fenster (0 = ungueltig zaehlt nicht); ganz ungueltig -> 0."""
    if r <= 0: return tiefe
    t = np.where(tiefe > 0, tiefe, np.inf).astype(np.float32); h, w = t.shape; p = np.pad(t, r, constant_values=np.inf); m = t.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1): np.minimum(m, p[r + dy:r + dy + h, r + dx:r + dx + w], out=m)
    m[~np.isfinite(m)] = 0; return m


def zaehlen_bild(X, K, R, t, breite, hoehe, tiefe, nq, nv, rand=None):
    """Eine Kamera: K = (fx, fy, cx, cy) im Bildmassstab breite x hoehe, Welt->Kamera R, t, Tiefenkarte (beliebige Aufloesung). Zaehlt in nq/nv (in place).
    FREIRAUM nur, wenn auch die NAECHSTE Tiefe im Fenster +-rand Pixel dahinter liegt (Silhouettenschutz: Punkte auf Kanten/Bogenrand, deren Nachbarpixel
    schon den Hintergrund zeigen, gelten nicht als durchschaut; Messung 24.11.: ohne Fenster fielen Torbogen-Gewoelbe-Punkte, siehe Kopf)."""
    rand = RAND if rand is None else rand; tmin = min_karte(tiefe, rand)
    sx = tiefe.shape[1] / breite; sy = tiefe.shape[0] / hoehe; R = np.asarray(R, np.float32); t = np.asarray(t, np.float32)
    for a in range(0, len(X), BLOCK):
        Q = X[a:a + BLOCK] @ R.T + t; z = Q[:, 2]; ok = z > 0.1
        if not ok.any(): continue
        idx = np.where(ok)[0]; zq = z[idx]; u = K[0] * Q[idx, 0] / zq + K[2]; v = K[1] * Q[idx, 1] / zq + K[3]
        im = (u >= 0) & (u < breite - 1) & (v >= 0) & (v < hoehe - 1)
        if not im.any(): continue
        idx = idx[im]; zq = zq[im]
        ui = np.clip(np.round(u[im] * sx).astype(np.int64), 0, tiefe.shape[1] - 1); vi = np.clip(np.round(v[im] * sy).astype(np.int64), 0, tiefe.shape[0] - 1)
        d = tiefe[vi, ui]
        dm_ = tmin[vi, ui]; q = idx[np.abs(d - zq) < TOL_Q * zq] + a; f = idx[(d > 0) & (dm_ > (1 + TOL_V) * zq)] + a
        nq[q] += 1; nv[f] += 1


def zaehlen(X, kameras, threads=4):
    """kameras: Liste (K, R, t, breite, hoehe, laden()) - laden() liefert die Tiefenkarte oder None. -> nq, nv (int32)."""
    X = np.ascontiguousarray(X, np.float32); n = len(X); threads = max(1, min(threads, len(kameras) or 1))
    Z = [(np.zeros(n, np.uint16), np.zeros(n, np.uint16)) for _ in range(threads)]
    def arbeit(j):
        nq, nv = Z[j]
        for K, R, t, b, h, laden in kameras[j::threads]:
            dm = laden()
            if dm is not None: zaehlen_bild(X, K, R, t, b, h, dm, nq, nv)
    with ThreadPoolExecutor(threads) as ex: list(ex.map(arbeit, range(threads)))
    nq = np.sum([z[0] for z in Z], 0, dtype=np.int32); nv = np.sum([z[1] for z in Z], 0, dtype=np.int32); return nq, nv


def entscheiden(nq, nv, min_v=MIN_V, verh=VERH):
    """True = Punkt weg (Freiraum >= min_v und >= verh x Quellen)."""
    return (nv >= min_v) & (nv >= verh * nq)


def kameras_aus_workspace(ws):
    """Kameras + Tiefenkarten aus einem COLMAP-Workspace (entzerrt: sparse/, stereo/depth_maps). geometric bevorzugt, sonst photometric."""
    import pycolmap
    rec = pycolmap.Reconstruction(os.path.join(ws, "sparse")); dm = os.path.join(ws, "stereo", "depth_maps"); kam = []
    for _iid, im in sorted(rec.images.items()):
        c = rec.cameras[im.camera_id]; m = str(c.model).split(".")[-1]; p = list(c.params)
        if m == "SIMPLE_PINHOLE": K = (p[0], p[0], p[1], p[2])
        elif m == "PINHOLE": K = tuple(p[:4])
        else: continue                                                  # Workspace ist entzerrt; andere Modelle hier nicht erwartet
        f = next((os.path.join(dm, im.name + e) for e in (".geometric.bin", ".photometric.bin") if os.path.exists(os.path.join(dm, im.name + e))), None)
        if f is None: continue
        T = im.cam_from_world().matrix(); kam.append((K, T[:, :3], T[:, 3], c.width, c.height, (lambda f=f: tiefe_lesen(f))))
    return kam


def ply_lesen(p):
    raw = open(p, "rb").read(); h = raw.index(b"end_header\n") + 11
    kopf = raw[:h].decode(errors="replace"); n = int([l for l in kopf.splitlines() if l.startswith("element vertex")][0].split()[-1])
    assert "property float nx" in kopf and "property uchar red" in kopf, "unerwartetes PLY-Format (erwartet COLMAP x y z nx ny nz rgb)"
    return np.frombuffer(raw[h:h + n * DT.itemsize], DT).copy()


def ply_schreiben(p, P):
    tmp = p + ".tmp"
    with open(tmp, "wb") as f:
        f.write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\nproperty float nz\n"
                 "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % len(P)).encode()); f.write(P.tobytes())
    os.replace(tmp, p)


def vis_filtern(p, behalten):
    """fused.ply.vis (u64 n, je Punkt u32 k + k x u32) auf die behaltenen Punkte kuerzen."""
    v = np.fromfile(p, np.uint8); n = int(v[:8].view("<u8")[0])
    if n != len(behalten): print(f"HINWEIS quellfilter: {p} hat {n} statt {len(behalten)} Eintraege - nicht gefiltert, beiseitegelegt", flush=True); os.replace(p, p + ".alt"); return
    u = v[8:].view("<u4"); laengen = np.empty(n, np.int64); o = 0
    for i in range(n): k = int(u[o]) + 1; laengen[i] = k; o += k
    rest = u[:o][np.repeat(behalten, laengen)]; tmp = p + ".tmp"
    with open(tmp, "wb") as f: f.write(np.array([int(behalten.sum())], "<u8").tobytes()); f.write(rest.astype("<u4").tobytes())
    os.replace(tmp, p)


def stand():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import code_stand
    return code_stand.code_stand("quellfilter.py")


def quellfilter_noetig(ply):
    """True, wenn <ply> Punkte hat und nicht mit dem aktuellen Stand dieses Filters gefiltert ist (Marke <ply>.quellfilter.json)."""
    if os.environ.get("RCPARK_QUELLFILTER", "1") == "0" or not os.path.exists(ply): return False
    try: m = json.load(open(ply + ".quellfilter.json"))
    except Exception: return True
    try: n = int([l for l in open(ply, "rb").read(4000).decode(errors="replace").splitlines() if l.startswith("element vertex")][0].split()[-1])
    except Exception: n = -1
    return not (m.get("stand") == stand() and m.get("punkte_nachher") == n)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ws"); ap.add_argument("--ply", default=""); ap.add_argument("--stichprobe", type=int, default=0, help="nur jeden N-ten Punkt messen (Probe, schreibt nichts)")
    ap.add_argument("--nur_messen", action="store_true"); ap.add_argument("--threads", type=int, default=4); a = ap.parse_args(); t0 = time.time()
    ply = a.ply or os.path.join(a.ws, "fused.ply"); P = ply_lesen(ply); n0 = len(P)
    sel = np.arange(0, n0, a.stichprobe) if a.stichprobe > 1 else None
    X = np.stack([P["x"], P["y"], P["z"]], 1) if sel is None else np.stack([P["x"][sel], P["y"][sel], P["z"][sel]], 1)
    kam = kameras_aus_workspace(a.ws); print(f"quellfilter: {len(X)} Punkte, {len(kam)} Kameras mit Tiefenkarte", flush=True)
    if not kam: print("HINWEIS quellfilter: keine Tiefenkarten - nichts gefiltert", flush=True); return 0
    nq, nv = zaehlen(X, kam, a.threads); weg = entscheiden(nq, nv); anteil = float(weg.mean()) if len(weg) else 0.0
    bericht = dict(stand=stand(), punkte_vorher=n0, gemessen=int(len(X)), weg=int(weg.sum()), anteil_weg=round(anteil, 5), regel=f"Freiraum >= {MIN_V} und >= {VERH} x Quellen",
                   toleranz=dict(quelle=TOL_Q, freiraum=TOL_V), kameras=len(kam), sekunden=round(time.time() - t0),
                   quellen_quantile=np.percentile(nq, [10, 50, 90]).tolist(), freiraum_quantile=np.percentile(nv, [10, 50, 90]).tolist())
    print(f"quellfilter: {weg.sum()} von {len(X)} Punkten weg ({100 * anteil:.2f} %), {time.time() - t0:.0f} s", flush=True)
    if a.nur_messen or sel is not None: print(json.dumps(bericht), flush=True); return 0
    if anteil > GUARD:
        print(f"ACHTUNG quellfilter: {100 * anteil:.1f} % > {100 * GUARD:.0f} % - Wolke NICHT geaendert (Karten/Kameras pruefen)", flush=True)
        bericht.update(angewandt=False, punkte_nachher=n0); json.dump(bericht, open(ply + ".quellfilter.json", "w"), indent=1); return 0
    ply_schreiben(os.path.join(os.path.dirname(os.path.abspath(ply)), "fused_quellfilter_weg.ply"), P[weg])
    if os.path.exists(ply + ".vis"): vis_filtern(ply + ".vis", ~weg)
    ply_schreiben(ply, P[~weg]); bericht.update(angewandt=True, punkte_nachher=int((~weg).sum()))
    json.dump(bericht, open(ply + ".quellfilter.json", "w"), indent=1); return 0


if __name__ == "__main__": sys.exit(main())
