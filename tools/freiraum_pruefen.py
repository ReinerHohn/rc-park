#!/usr/bin/env python3
"""freiraum_pruefen.py - ALLGEMEINE Pruefung "Modell gegen gesehenen Freiraum" (Nutzer 5.11. 13:53: keine Spezialfaelle wie "Seitenbogen = Durchgang").

Prinzip (Sichtbarkeitskonsistenz / Space Carving): jeder Punkt der dichten Rekonstruktion wurde von bestimmten Kameras gesehen (COLMAP fused.ply.vis).
Der Strahl Kamera -> Punkt muss also frei sein. Schneidet er das Modell (vor dem Punkt, Rand --rand m), steht im Modell Material, wo die Fotos
hindurchsehen: Durchgang zugemauert, Nische zu flach, Bauteil zu weit vorn. Umgekehrt (--fehl): Punkt liegt AUSSERHALB des Modells und weit von dessen
Oberflaeche -> fehlendes Bauteil (Erker, Balkon, Gaube) oder Fremdobjekt (Baum, Nachbarhaus) - nur Hinweis, Fremdobjekte sind nicht trennbar.
Ergebnis: Verletzungsvoxel (Groesse --voxel) mit Anzahl Strahlen und Anzahl verschiedener Kameras (>= --min-kameras zaehlt), Bild Grundriss + Ansichten.
Zuordnung vis-Index -> Bild: Reihenfolge der aufsteigenden Bild-IDs der dichten Arbeitsumgebung; wird durch Rueckprojektion GEPRUEFT (Anteil im Bild, vor Kamera).
  /media/oem/scan/venv-seg/bin/python -I tools/freiraum_pruefen.py <objekt.json> --stl M.stl --dicht <dicht_ordner> --ausrichtung SFM-AUSRICHTUNG.json [--aus DIR]
  ACHTUNG Ausrichtung = die, mit der sfm_dicht die Wolke gerechnet hat (--netz buendel -> SFM-AUSRICHTUNG-buendel.json); falsche Datei -> 0 Treffer
"""
import os, sys, json, argparse, struct, time
import numpy as np, cv2, trimesh


def ply_lesen(p):
    with open(p, "rb") as f:
        hd = []
        while True:
            l = f.readline().decode("ascii").strip(); hd.append(l)
            if l == "end_header": break
        n = int([h for h in hd if h.startswith("element vertex")][0].split()[-1]); props = [h.split()[1:] for h in hd if h.startswith("property")]
        dt = np.dtype([(q[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[q[0]]) for q in props]); a = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    return np.c_[a["x"], a["y"], a["z"]].astype(np.float64)


def vis_namen(dicht, fallback_ids=None):
    """Bildnamen (ohne .jpg) in der Reihenfolge der vis-Indizes von fused.ply.vis = aufsteigende Bild-ID in dicht/sparse/images.bin (NICHT Namensreihenfolge!
    Register CV: bei Kaufhaus weicht die ID-Reihenfolge ab Index 72 von der Namensreihenfolge ab (216, 222 vor 205); Rueckprojektion 98 % gegen 67 %).
    Fehlt images.bin, wird NICHT still die Namensreihenfolge geraten: FileNotFoundError. Nur mit ausdruecklich uebergebenem fallback_ids (Wissen des Aufrufers,
    z.B. synthetische Wolke) wird dieser benutzt - mit lauter Warnung auf stderr (Register CW, tools/test_vis_mapping.py)."""
    pf = os.path.join(dicht, "sparse", "images.bin")
    if not os.path.exists(pf):
        if fallback_ids is None: raise FileNotFoundError(f"{pf} fehlt: vis-Index -> Bild nicht bestimmbar (Namensreihenfolge waere oft falsch, Register CV)")
        print(f"WARNUNG vis_namen: {pf} fehlt, benutze uebergebene Reihenfolge ({len(fallback_ids)} Bilder) UNGEPRUEFT", file=sys.stderr); return list(fallback_ids)
    b = open(pf, "rb").read(); n = struct.unpack_from("<Q", b, 0)[0]; o = 8; out = []
    for _ in range(n):
        iid = struct.unpack_from("<I", b, o)[0]; o += 4 + 32 + 24 + 4; e = b.index(b"\0", o); nm = b[o:e].decode(); o = e + 1
        npts = struct.unpack_from("<Q", b, o)[0]; o += 8 + 24 * npts; out.append((iid, nm.rsplit(".", 1)[0]))
    return [nm for _, nm in sorted(out)]


def vis_ids(dicht, K, fallback_ids=None):
    """Kamera-Schluessel von kameras_unverzerrt.json (K) in vis-Index-Reihenfolge. EINZIGE Stelle, an der Werkzeuge die vis-Zuordnung beziehen
    (keine Kopien der Logik, kein sorted(K, key=int)). Bricht ab, wenn images.bin und K nicht dieselben Bilder nennen."""
    vn = vis_namen(dicht, fallback_ids)
    if set(vn) != set(K): raise ValueError(f"images.bin und kameras_unverzerrt.json nennen verschiedene Bilder: nur images.bin {sorted(set(vn) - set(K))[:5]}, nur K {sorted(set(K) - set(vn))[:5]}")
    return vn


def images_bin_schreiben(dicht, namen):
    """Schreibt ein minimales sparse/images.bin (Bild-ID = Position in `namen`, 1-basiert; keine 2D-Punkte) fuer SYNTHETISCHE oder abgeleitete Wolken, deren
    vis-Index der Reihenfolge `namen` folgt. So bleibt vis_ids() der einzige Weg zur Zuordnung (kein Sonderpfad fuer Testdaten)."""
    os.makedirs(os.path.join(dicht, "sparse"), exist_ok=True)
    with open(os.path.join(dicht, "sparse", "images.bin"), "wb") as f:
        f.write(struct.pack("<Q", len(namen)))
        for k, nm in enumerate(namen): f.write(struct.pack("<I", k + 1) + b"\0" * 32 + b"\0" * 24 + struct.pack("<I", 1) + f"{nm}.jpg".encode() + b"\0" + struct.pack("<Q", 0))


def vis_lesen(p):
    b = np.fromfile(p, dtype="<u4"); n = int(b[0]) | (int(b[1]) << 32); i = 2; pt, im = [], []
    for k in range(n):
        c = int(b[i]); pt.append(np.full(c, k, np.int32)); im.append(b[i + 1:i + 1 + c]); i += 1 + c
    return np.concatenate(pt), np.concatenate(im).astype(np.int32)


def sd_bloecke(m, X, n=4000):
    """signed_distance in Bloecken (trimesh braucht ~65 kB je Punkt bei 27k Dreiecken: Martinstor 5.11. OOM). > 0 = innen."""
    from trimesh.proximity import ProximityQuery
    q = ProximityQuery(m); out = np.empty(len(X))
    for i in range(0, len(X), n): out[i:i + n] = q.signed_distance(X[i:i + n])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl", required=True); ap.add_argument("--dicht", required=True); ap.add_argument("--ausrichtung", required=True)
    ap.add_argument("--aus"); ap.add_argument("--rand", type=float, default=0.4, help="Strahl endet so weit (m) vor dem Punkt (Rauschen der Wolke, Wanddicke der Punkte)")
    ap.add_argument("--voxel", type=float, default=0.5); ap.add_argument("--min-kameras", type=int, default=3); ap.add_argument("--max-strahlen", type=int, default=600000)
    ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--fehl-abstand", type=float, default=0.6); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--zmin", type=float, default=0.3, help="Strahlen zu Punkten darunter ignorieren (Pflaster)")
    a = ap.parse_args(argv); t0 = time.time(); rng = np.random.default_rng(a.seed)
    od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit", "freiraum"); os.makedirs(aus, exist_ok=True)
    tr = json.load(open(a.ausrichtung))["transformation"]; s = float(tr["s"]); Ra = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; ta = np.array(tr["t"], float)
    zu_modell = lambda X: ((X - ta) @ Ra) / s
    X = zu_modell(ply_lesen(os.path.join(a.dicht, "fused.ply"))); pi, ii = vis_lesen(os.path.join(a.dicht, "fused.ply.vis"))
    K = json.load(open(os.path.join(a.dicht, "kameras_unverzerrt.json"))); ids = vis_ids(a.dicht, K)
    if ii.max() >= len(ids): sys.exit(f"vis-Index {ii.max()} >= {len(ids)} Kameras - Zuordnung unbekannt")
    Rc = np.array([K[i]["R"] for i in ids]); tc = np.array([K[i]["t"] for i in ids]); Cc = zu_modell(np.einsum("kji,kj->ki", Rc, -tc))   # C = -R^T t
    # Gegenprobe Zuordnung: Rueckprojektion der Punkte in die zugeordnete Kamera (COLMAP-Rahmen)
    Xs = ply_lesen(os.path.join(a.dicht, "fused.ply")); j = rng.choice(len(pi), min(20000, len(pi)), replace=False)
    pc = np.einsum("kij,kj->ki", Rc[ii[j]], Xs[pi[j]]) + tc[ii[j]]; fx = np.array([K[i]["fx"] for i in ids])[ii[j]]; cx = np.array([K[i]["cx"] for i in ids])[ii[j]]
    cy = np.array([K[i]["cy"] for i in ids])[ii[j]]; W = np.array([K[i]["W"] for i in ids])[ii[j]]; H = np.array([K[i]["H"] for i in ids])[ii[j]]
    u = fx * pc[:, 0] / pc[:, 2] + cx; v = fx * pc[:, 1] / pc[:, 2] + cy; ok = (pc[:, 2] > 0) & (u >= 0) & (u < W) & (v >= 0) & (v < H); anteil = float(ok.mean())
    print(f"Zuordnung vis->Kamera: {anteil:.1%} der Beobachtungen projizieren ins eigene Bild")
    je = np.array([ok[ii[j] == q].mean() if (ii[j] == q).sum() >= 20 else 1.0 for q in range(len(ids))]); schlecht = np.where(je < 0.97)[0]
    if len(schlecht): print("  Kameras mit Rueckprojektion < 97 % werden NICHT benutzt:", {ids[q]: round(float(je[q]), 3) for q in schlecht})
    gut = ~np.isin(ii[j], schlecht); anteil = float(ok[gut].mean()); print(f"  Rest: {anteil:.1%} (Soll >= 99 %)")
    if anteil < 0.99 or len(schlecht) > 0.2 * len(ids): sys.exit("Zuordnung falsch - Abbruch (keine Aussage)")
    k = ~np.isin(ii, schlecht); pi, ii = pi[k], ii[k]
    m = trimesh.load(a.stl); m.apply_scale(a.massstab / 1000.0)                                  # STL mm bei 1:massstab -> m
    k = X[pi, 2] > a.zmin; pi, ii = pi[k], ii[k]
    if len(pi) > a.max_strahlen: j = rng.choice(len(pi), a.max_strahlen, replace=False); pi, ii = pi[j], ii[j]
    P = X[pi]; C = Cc[ii]; d = P - C; L = np.linalg.norm(d, axis=1); d /= L[:, None]
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    rmi = RayMeshIntersector(m); LO, RI = [], []                                                     # in Bloecken (Speicher: Martinstor 5.11. OOM bei 600k Strahlen am Stueck)
    for i in range(0, len(C), 50000):
        l_, r_, _ = rmi.intersects_location(C[i:i + 50000], d[i:i + 50000], multiple_hits=True); LO.append(l_); RI.append(r_ + i)
    loc, ri = np.concatenate(LO), np.concatenate(RI)
    t = np.einsum("ij,ij->i", loc - C[ri], d[ri]); vor = (t > 0.5) & (t < L[ri] - a.rand)
    # Verletzung, robust gegen streifende Strahlen in flache Fensterlaibungen (erste Fassung: 24 %% aller Strahlen, Fassade ueberall rot):
    #  (a) der gesehene Punkt liegt TIEFER als --rand im Modellkoerper (Modell steht vor einer gesehenen Flaeche, z. B. Arkadenrueckwand)
    #  (b) der Strahl durchquert vor dem Punkt ein ganzes Modellstueck (>= 2 Schnitte: hinein UND hinaus, z. B. zugemauerter Durchgang)
    nvor = np.bincount(ri[vor], minlength=len(P)); up, inv_p = np.unique(pi, return_inverse=True)
    from trimesh.proximity import ProximityQuery
    sd_p = sd_bloecke(m, X[up])[inv_p]                                          # > 0 = innen
    va = sd_p > a.rand; vb = nvor >= 2; hr = np.where(va | vb)[0]
    erst_t = np.full(len(P), np.inf); np.minimum.at(erst_t, ri[vor], t[vor])
    hp = np.where(va[hr, None], P[hr], C[hr] + d[hr] * np.where(np.isfinite(erst_t[hr]), erst_t[hr], L[hr])[:, None])
    np.savez_compressed(os.path.join(aus, "strahlen.npz"), C=C[hr], d=d[hr], t0=np.where(np.isfinite(erst_t[hr]), erst_t[hr], L[hr]), t1=L[hr] - a.rand, kam=ii[hr], art_a=va[hr])
    print(f"{len(P)} Strahlen: (a) Punkt > {a.rand} m im Modell {va.sum()} ({va.mean():.1%}), (b) Strahl durchquert Modellstueck {vb.sum()} ({vb.mean():.1%})")
    vx = np.floor(hp / a.voxel).astype(np.int64); key, inv = np.unique(vx, axis=0, return_inverse=True); inv = inv.ravel()
    nstr = np.bincount(inv); kam = np.array([len(np.unique(ii[hr][inv == q])) for q in range(len(key))]) if len(key) else np.zeros(0, int)
    gilt = kam >= a.min_kameras; V = (key[gilt] + 0.5) * a.voxel
    # Fehlvolumen: gesehene Punkte ausserhalb des Modells, weit von der Oberflaeche
    Xk = X[(X[:, 2] > a.zmin)]; Xk = Xk[rng.choice(len(Xk), min(200000, len(Xk)), replace=False)]
    from trimesh.proximity import ProximityQuery
    sd = sd_bloecke(m, Xk); fehl = Xk[sd < -a.fehl_abstand]
    bb = m.bounds; nah = np.all((fehl > bb[0] - 1.0) & (fehl < bb[1] + 1.0), axis=1); fehl = fehl[nah]
    erg = dict(stl=a.stl, modell_volumen_m3=round(float(abs(m.volume)), 3), strahlen=int(len(P)), verletzende_strahlen=int(len(hr)), voxel_m=a.voxel, min_kameras=a.min_kameras, zuordnung_anteil=round(anteil, 4),
               verletzungsvolumen_m3=round(float(gilt.sum() * a.voxel ** 3), 2), verletzungsvoxel=[dict(p=[round(float(c), 2) for c in V[q]], strahlen=int(nstr[gilt][q]), kameras=int(kam[gilt][q])) for q in range(len(V))],
               fehlpunkte_ausserhalb=int(len(fehl)), fehl_abstand_m=a.fehl_abstand, quelle="freiraum_pruefen.py: COLMAP fused.ply.vis Sichtstrahlen gegen Modell-STL")
    json.dump(erg, open(os.path.join(aus, "freiraum.json"), "w"), indent=1)
    np.save(os.path.join(aus, "freiraum_voxel.npy"), np.c_[V, nstr[gilt], kam[gilt]]); np.save(os.path.join(aus, "fehlpunkte.npy"), fehl.astype(np.float32))
    print(f"Verletzung: {gilt.sum()} Voxel ({erg['verletzungsvolumen_m3']} m3) mit >= {a.min_kameras} Kameras; Fehlpunkte ausserhalb > {a.fehl_abstand} m: {len(fehl)}  ({time.time()-t0:.0f} s)")
    bild(m, V, kam[gilt], fehl, os.path.join(aus, "freiraum.jpg"))
    print("->", os.path.join(aus, "freiraum.json"))


def bild(m, V, kam, fehl, pfad):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    f, ax = plt.subplots(1, 3, figsize=(21, 7))
    for a_, z in zip(ax[:2], [2.0, 6.0]):
        sec = m.section([0, 0, 1], [0, 0, z])
        if sec is not None:
            for e in sec.discrete: a_.plot(e[:, 0], e[:, 1], "k-", lw=1)
        q = np.abs(V[:, 2] - z) < 1.5 if len(V) else np.zeros(0, bool)
        if q.any(): sc = a_.scatter(V[q, 0], V[q, 1], c=kam[q], cmap="autumn_r", s=18, vmin=3, vmax=15, marker="s"); plt.colorbar(sc, ax=a_, label="Kameras, die durch das Modell sehen")
        qf = np.abs(fehl[:, 2] - z) < 1.0
        a_.scatter(fehl[qf, 0], fehl[qf, 1], s=1, c="tab:blue", alpha=0.3)
        a_.set_aspect("equal"); a_.set_title(f"Schnitt z={z:.0f} m: rot = Modell steht im gesehenen Freiraum, blau = Wolke ausserhalb Modell"); a_.grid(alpha=.3)
    a_ = ax[2]; T = m.vertices
    a_.scatter(T[:, 0], T[:, 2], s=0.2, c="0.7")
    if len(V): a_.scatter(V[:, 0], V[:, 2], c=kam, cmap="autumn_r", s=14, vmin=3, vmax=15, marker="s")
    a_.set_aspect("equal"); a_.set_title("Ansicht x-z (alle Hoehen)"); a_.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(pfad, dpi=75)


if __name__ == "__main__":
    main()
