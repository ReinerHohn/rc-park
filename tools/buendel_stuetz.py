#!/usr/bin/env python3
"""buendel_stuetz.py - GENERISCH: Buendelausgleich eines COLMAP-Netzes MIT STUETZTERMEN (LoD2-Gebaeudekanten im Foto, Foto-GPS, robuste Verluste), GPU (torch).

Anlass 17.11.2026 (schwab_auto): Kameragruppen widersprachen sich an der Dachkante (Blick aus 120-180 / 180-240 Grad +1,2 m gegen die Nordgruppe), das Fernfoto
online_orig__od_08 hatte k1 -1,58 / f 13 385 px, GPS-Fit-Massstab 0,875 gegen Fernfotos 0,98. Die Ausrichtung (sfm_lod2_ausrichten.py) ist nur EINE Aehnlichkeit fuer das
ganze Netz - ein in sich verzerrtes Netz (Teilmodelle mit eigenem Massstab) bleibt verzerrt. Hier werden Kameras (Drehung, Lage, Brennweite, k1) und alle Netzpunkte
gemeinsam neu ausgeglichen:
  Bild     : Rueckprojektion jeder Spurbeobachtung (sigma --sigma-px, Huber)
  Kanten   : LoD2-Gebaeudekanten als Passkanten. Aus den WallSurfaces aller Gebaeude im Umkreis: senkrechte FREIE AUSSENECKEN (konvex, keine Nachbarwand anliegend),
             optional Traufkanten (--traufe; ACHTUNG Dachueberstand: LoD2-Wandoberkante ist nicht die Fotokante). Beobachtung AUTOMATISCH je Foto: Kante mit der aktuellen
             Kamera projizieren (mit k1), Verdeckung durch das LoD2-Netz pruefen, dann quer zur Linie den staerksten gleichsinnigen Grauwertsprung suchen (Profil ueber
             alle Stuetzstellen, Versatz und Kippung frei, Eindeutigkeit gegen das zweitbeste Maximum). Residuum = Abstand der projizierten Kante zur Fotolinie (Cauchy).
             Zwei Durchgaenge: Suchfenster --fenster (m), dann --fenster2 um die ausgeglichene Kamera.
  GPS      : EXIF-GPS als schwache Lageprior der Kameramitte (nur x/y, sigma --sigma-gps m, Cauchy). --ohne-gps schaltet ab (dann ist lage_gps_pruefen ein UNABHAENGIGES Tor).
  Prior    : k1 -> 0 (sigma 0,25), log f um den Startwert (sigma 0,5).
Ausreisser-Kameras werden MARKIERT, nicht verbogen: nach Durchgang 1 Kameras mit Kantenrest > --ausreisser-px UND > --ausreisser-m (Median), unplausibler Kamera (kamera_plausibel inkl. k1)
oder GPS-Rest > 40 m verlieren ihre Kanten-/GPS-Gewichte (Netz bleibt), stehen in bericht.json 'ausreisser' und werden mit --k-dateien NICHT geschrieben.
Loeser: Levenberg-Marquardt, Punkte per Schur-Komplement eliminiert, reduziertes Kamerasystem dicht auf der GPU (Cholesky). 500 Kameras / 100 000 Punkte: Sekunden je Schritt.
Pruefanteil: --pruef 0,25 der Kantenbeobachtungen gehen NICHT in den Ausgleich (Gegenprobe Passkanten vorher/nachher).

Aufruf (jedes Objekt mit COLMAP-Netz + LoD2 in objekt.json):
  JOB_GPU_MB=3000 tools/job_start.sh NAME LOG /media/oem/scan/venv-seg/bin/python -I tools/buendel_stuetz.py modelle/<obj>/objekt.json \\
      --sparse <sparse/0> --ausrichtung modelle/<obj>/messprotokoll/SFM-AUSRICHTUNG-<obj>.json --name stuetz [--ohne-gps] [--traufe] [--k-dateien PROBEORDNER]
Eingang: --ausrichtung = Aehnlichkeit X_sfm = s R X_modell + t (sfm_lod2_ausrichten.py); Fotos aus objekt.json fotos_dir (Namen wie in images.bin).
Ausgabe: /media/oem/scan/rc-park_daten/<obj>/buendel_stuetz/<name>/ (bericht.json, kanten_beob.json, sparse/ im Modellrahmen: cameras/images/points3D.bin - OHNE frames/rigs,
  lesbar fuer kamera_sfm_guete/kameras_aus_buendel, NICHT fuer pycolmap; kanten_<foto>.jpg Stichproben ANSEHEN), SFM-AUSRICHTUNG-<obj>_<name>.json
  (im Ausgabeordner; mit --uebernehmen auch nach modelle/<obj>/messprotokoll/; Einheitstransformation, Format wie sfm_lod2_ausrichten -> kameras_aus_buendel.py). --k-dateien P: legt unter P eine Probe-Objektkopie an (objekt.json, dach.json, Links
  auf Fotos/STL) und schreibt dort die K-Dateien - Tore (umriss_tor, dach_aus_fotos, lage_gps_pruefen) laufen auf der Probe, das echte Objekt bleibt unberuehrt.
Befund schwab_auto 17.11.2026 (Varianten a: Ecken+GPS, b: ohne GPS, c: +Traufe eben Cauchy 3, d2: +Traufe eben, Cauchy 30, sigma-kante 1; Berichte unter
  /media/oem/scan/rc-park_daten/schwab_auto/buendel_stuetz/<v>/bericht.json): senkrechte Ecken allein aendern fast nichts (Ecken stuetzen nur quer, Netz steif; Kamera-
  verschiebung Median 5 cm) und loesen den Dachkanten-Widerspruch NICHT. Mit 'Traufe eben' (d2) Ecken-Rest symmetrisch gemessen 0,54 -> 0,32 m (Sued 0,74 -> 0,26 m),
  Dach-Gegenprobe 65/110 -> 85/120 Fotos, Suedgruppen-Widerspruch weg - ABER Nordgruppe schlechter (Umriss 113646 0,12 -> 0,41 m, Dachgruppe 300-360 +0,52 -> +1,49 m):
  NICHT uebernommen. Der GPS-Massstab 0,875 ist ein GPS-Artefakt (Telefon-GPS glaettet/haengt nach: Wegverhaeltnis GPS/Modell 0,76 bei < 30 s Abstand, 0,98 bei > 10 min).
Grenzen: Kanten braucht freie LoD2-Ecken im Bild (eingebaute Zeilenhaeuser haben kaum welche); LoD2-Grundriss ist auf ~0,1-0,3 m genau, Eckquader/Putzkanten koennen
  daneben liegen (Cauchy faengt einzelne). Senkrechte Kanten stuetzen nur quer (Lage/Drehung/Massstab), nicht die Hoehe; die Hoehe folgt aus dem starren Netz.
  Ohne frames.bin: neue COLMAP-Formate (rigs) werden nicht mitgeschrieben. Kein Ersatz fuer ein neues SfM, wenn Teilmodelle gar nicht verbunden sind (dann fehlen Spuren).
"""
import sys, os, json, glob, argparse, time, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kamera_sfm_guete as KG
import kamera_plausibel as KP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = "cuda"


def rodr(w):
    th = np.linalg.norm(w)
    if th < 1e-12: return np.eye(3)
    k = w / th; Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * Kx + (1 - math.cos(th)) * Kx @ Kx


def rodr_t(w):
    import torch
    th = torch.linalg.norm(w, dim=1, keepdim=True).clamp(min=1e-15); k = w / th; z = torch.zeros_like(k[:, 0])
    Kx = torch.stack([z, -k[:, 2], k[:, 1], k[:, 2], z, -k[:, 0], -k[:, 1], k[:, 0], z], 1).view(-1, 3, 3)
    I = torch.eye(3, dtype=w.dtype, device=w.device)[None]; s = torch.sin(th)[..., None]; c = torch.cos(th)[..., None]
    return I + s * Kx + (1 - c) * Kx @ Kx


def kreuz(v):
    import torch
    z = torch.zeros_like(v[..., 0])
    return torch.stack([z, -v[..., 2], v[..., 1], v[..., 2], z, -v[..., 0], -v[..., 1], v[..., 0], z], -1).view(*v.shape[:-1], 3, 3)


# ---------------------------------------------------------------- LoD2-Kanten
def lod2_kanten(obj, radius, traufe=False):
    """-> (kanten: Liste dict(id, geb, art, a(3), b(3)), Netz-Dreiecke (F,3,3) im Modellrahmen)."""
    import lod2_gebaeude as LG
    from matplotlib.path import Path
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"], float); xh, yh = np.array(R["xhat_utm"], float), np.array(R["yhat_utm"], float)
    lok = lambda P: np.c_[(P[:, :2] - c0) @ xh, (P[:, :2] - c0) @ yh, P[:, 2] - R["gelaende"]]
    geb = LG.extract(obj["lod2"]["gml"], center=tuple(c0), radius=radius); tris = []; grund = []; senk = []; trauf = []
    for gi, (meta, polys) in enumerate(geb):
        for typ, P in polys:
            Q = lok(np.asarray(P, float))
            for tr in LG.planar_triangulate(Q): tris.append(Q[list(tr)])
            if typ == "GroundSurface": grund.append((gi, Path(Q[:, :2]), Q))
            if typ == "WallSurface": senk.append((gi, Q))
            if traufe and typ == "WallSurface":                # obere Wandkante: Kante mit beiden Enden auf der hoechsten Hoehe der Wand, waagerecht
                zt = Q[:, 2].max(); n = len(Q)
                for i in range(n):
                    p, q = Q[i], Q[(i + 1) % n]
                    if abs(p[2] - zt) < 0.4 and abs(q[2] - zt) < 0.4 and np.hypot(*(p[:2] - q[:2])) > 3.0: trauf.append((gi, p.copy(), q.copy()))
    # Ecken aus dem GRUNDRISS (GroundSurface-Ring): fast gerade Stuecke (< 20 Grad Knick) zusammenfassen - LoD2 teilt Waende in 0,5-m-Streifen und Rundungen in
    # viele kleine Facetten (Schwabentor: Nordwand 10,6 m + 0,5 m, Treppenturm 30 Facetten); Ecke = Knick 35-145 Grad mit beiden Schenkeln >= 1,5 m
    def vereinfachen(xy):
        xy = [p for i, p in enumerate(xy) if i == 0 or np.hypot(*(p - xy[i - 1])) > 0.02]
        if len(xy) > 1 and np.hypot(*(xy[0] - xy[-1])) <= 0.02: xy = xy[:-1]
        xy = np.array(xy); geaendert = True
        while geaendert and len(xy) > 3:
            geaendert = False; n = len(xy)
            for i in range(n):
                a_, b_, c_ = xy[i - 1], xy[i], xy[(i + 1) % n]; u_, v_ = b_ - a_, c_ - b_
                kn = abs(math.degrees(math.atan2(u_[0] * v_[1] - u_[1] * v_[0], u_ @ v_)))
                if kn < 20 and (np.linalg.norm(u_) < 1.5 or np.linalg.norm(v_) < 1.5 or kn < 6): xy = np.delete(xy, i, 0); geaendert = True; break
        return xy
    ring = np.c_[np.cos(np.linspace(0, 2 * np.pi, 16, endpoint=False)), np.sin(np.linspace(0, 2 * np.pi, 16, endpoint=False))] * 0.6
    kanten = []
    for gi, pa, Qg in grund:
        xy = vereinfachen(Qg[:, :2]); n = len(xy)
        for i in range(n):
            a_, b_, c_ = xy[i - 1], xy[i], xy[(i + 1) % n]; u_, v_ = b_ - a_, c_ - b_
            kn = abs(math.degrees(math.atan2(u_[0] * v_[1] - u_[1] * v_[0], u_ @ v_)))
            if not (35 <= kn <= 145) or np.linalg.norm(u_) < 1.5 or np.linalg.norm(v_) < 1.5: continue
            P = b_ + ring; eigen = np.zeros(16, bool); fremd = np.zeros(16, bool)
            for gj, pj, _ in grund:
                m = pj.contains_points(P)
                if gj == gi: eigen |= m
                else: fremd |= m
            if not (0.1 <= eigen.mean() <= 0.40): continue                      # nur konvexe Aussenecken
            zs = [Qw[:, 2] for gw, Qw in senk if gw == gi and np.min(np.hypot(*(Qw[:, :2] - b_).T)) < 0.6]
            if not zs or any(e["geb"] == gi and np.hypot(e["a"][0] - b_[0], e["a"][1] - b_[1]) < 0.3 for e in kanten): continue
            z1 = float(max(z.max() for z in zs)); z0 = float(Qg[:, 2].min())
            if fremd.any():                                                   # Nachbar angebaut: Kante erst ueber dessen Dach frei (Turm ueber den Nachbarhaeusern)
                nb = {gj for gj, pj, _ in grund if gj != gi and pj.contains_points(P).any()}
                z0 = max(float(lok(np.asarray(P_, float))[:, 2].max()) for gj in nb for t_, P_ in geb[gj][1]) + 1.0
                if z1 - z0 < 5: continue
            elif z1 - z0 < 3: continue
            kanten.append(dict(id=len(kanten), geb=gi, geb_id=geb[gi][0].get("id"), art="ecke", a=[float(b_[0]), float(b_[1]), z0], b=[float(b_[0]), float(b_[1]), z1]))
    for gi, p, q in trauf:
        mid = (p[:2] + q[:2]) / 2; nrm = np.array([-(q - p)[1], (q - p)[0]]); nrm /= np.linalg.norm(nrm)
        hoch = lambda gj: max(float(lok(np.asarray(P_, float))[:, 2].max()) for t_, P_ in geb[gj][1])
        frei = not any(pa.contains_points([mid + 0.6 * nrm, mid - 0.6 * nrm]).any() and hoch(gj) > min(p[2], q[2]) - 1.0 for gj, pa, _ in grund if gj != gi)   # Nachbar darunter stoert nicht
        if frei: kanten.append(dict(id=len(kanten), geb=gi, geb_id=geb[gi][0].get("id"), art="traufe", a=p.tolist(), b=q.tolist()))
    return kanten, np.array(tris, float)


# ---------------------------------------------------------------- Netz lesen
def netz_lesen(sparse, ausr):
    cams, pts, spur, im = KG.lesen(sparse)
    T = ausr["transformation"]; s = float(T["s"]); Ra = rodr(np.array(T["rvec"], float)); ta = np.array(T["t"], float)
    pid = np.array(sorted(pts), np.int64); P = np.array([pts[i] for i in pid], float); P = (P - ta) @ Ra / s       # X_m = R^T (X_s - t) / s
    idx = {int(p): j for j, p in enumerate(pid)}
    namen, Rm, tm, F, C, K1, WH, oi, oj, ouv = [], [], [], [], [], [], [], [], [], []
    for ci, (name, (q, t, cid, a)) in enumerate(sorted(im.items())):
        mod, w, h, p = cams[cid]
        if mod != 2: raise SystemExit(f"Kameramodell {mod} bei {name}: nur SIMPLE_RADIAL (2) umgesetzt")
        Rc = KG.quat_R(q); namen.append(name); Rm.append(Rc @ Ra); tm.append((Rc @ ta + np.array(t)) / s)
        F.append(p[0]); C.append([p[1], p[2]]); K1.append(p[3]); WH.append([w, h])
        g = a["p"] >= 0
        for x, y, pp in zip(a["x"][g], a["y"][g], a["p"][g]):
            j = idx.get(int(pp))
            if j is not None: oi.append(ci); oj.append(j); ouv.append((x, y))
    return dict(namen=namen, R=np.array(Rm), t=np.array(tm), f=np.array(F), c=np.array(C), k1=np.array(K1), wh=np.array(WH), P=P, pid=pid,
                oi=np.array(oi, np.int64), oj=np.array(oj, np.int64), ouv=np.array(ouv, float))


def projizieren(R, t, f, c, k1, X):
    """numpy: X (n,3) -> (uv (n,2), z (n,))."""
    Xc = X @ R.T + t; z = Xc[:, 2]; u = Xc[:, :2] / np.where(np.abs(z) < 1e-9, 1e-9, z)[:, None]; r2 = (u ** 2).sum(1)
    return f * u * (1 + k1 * r2)[:, None] + c, z


# ---------------------------------------------------------------- Kanten im Foto suchen
def bild_laden(pfad, wh_sfm, lang=2000):
    import cv2, torch
    im = cv2.imread(pfad, cv2.IMREAD_GRAYSCALE)
    if im is None: return None
    H0, W0 = im.shape; s0 = W0 / float(wh_sfm[0])                          # SfM-Pixel -> Original
    sc = min(1.0, lang / max(W0, H0)); im = cv2.resize(im, (int(W0 * sc), int(H0 * sc)), interpolation=cv2.INTER_AREA)
    g = torch.as_tensor(im, dtype=torch.float32, device=DEV)[None, None] / 255.0
    k = torch.tensor([math.exp(-x * x / (2 * 1.5 ** 2)) for x in range(-4, 5)], device=DEV); k = k / k.sum()
    F_ = torch.nn.functional; rp = lambda x, p: F_.pad(x, p, mode="replicate")          # Rand fortsetzen: Nullrand gab eine starke Scheinkante am Bildrand (Foto 127)
    g = F_.conv2d(rp(g, (4, 4, 0, 0)), k.view(1, 1, 1, 9)); g = F_.conv2d(rp(g, (0, 0, 4, 4)), k.view(1, 1, 9, 1))
    sx = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32, device=DEV) / 8
    gx = F_.conv2d(rp(g, (1, 1, 1, 1)), sx.view(1, 1, 3, 3))[0, 0]; gy = F_.conv2d(rp(g, (1, 1, 1, 1)), sx.T.contiguous().view(1, 1, 3, 3))[0, 0]
    return dict(gx=gx, gy=gy, sc=s0 * sc, W=im.shape[1], H=im.shape[0], gmed=max(float(torch.sqrt(gx ** 2 + gy ** 2).median()), 2e-3), grau=im)


def kante_suchen(B, uv, fenster_px, n_off=None):
    """uv (k,2) Stuetzstellen der projizierten Kante in Bildpixeln (verkleinert). -> dict(n, c0, guete, eindeutig, kohaerenz) oder None."""
    import torch
    if len(uv) < 8: return None
    a, b = uv[0], uv[-1]; L = np.linalg.norm(b - a)
    if L < 60: return None
    e = (b - a) / L; n = np.array([-e[1], e[0]]); m = (a + b) / 2; s = (uv - m) @ e
    W = int(min(max(fenster_px, 6), 220)); d = torch.arange(-W, W + 1, dtype=torch.float32, device=DEV)
    tau = torch.tensor(np.tan(np.radians(np.arange(-2.0, 2.01, 0.5))), dtype=torch.float32, device=DEV)
    U = torch.as_tensor(uv, dtype=torch.float32, device=DEV); S = torch.as_tensor(s, dtype=torch.float32, device=DEV); N = torch.as_tensor(n, dtype=torch.float32, device=DEV)
    off = d[None, :, None] + tau[:, None, None] * S[None, None, :]                       # (T, D, K)
    P = U[None, None] + off[..., None] * N                                             # (T, D, K, 2)
    gr = torch.stack([P[..., 0] / (B["W"] - 1) * 2 - 1, P[..., 1] / (B["H"] - 1) * 2 - 1], -1).view(1, -1, 1, 2)
    gx = torch.nn.functional.grid_sample(B["gx"][None, None], gr, align_corners=True, padding_mode="zeros").view(off.shape)
    gy = torch.nn.functional.grid_sample(B["gy"][None, None], gr, align_corners=True, padding_mode="zeros").view(off.shape)
    gn = gx * N[0] + gy * N[1]; prof = gn.mean(-1)                                      # (T, D) signiert
    sc = prof.abs(); best = int(torch.argmax(sc)); ti, di = divmod(best, sc.shape[1]); v = float(prof[ti, di])
    dd = (d - d[di]).abs()[None].expand_as(sc); zweit = float(torch.where(dd > 4, sc, torch.zeros_like(sc)).max())
    koh = float(((gn[ti, di] * math.copysign(1, v)) > 0.3 * abs(v)).float().mean())
    if abs(v) < 2.5 * B["gmed"] or abs(v) < 0.004: return None
    if abs(int(d[di])) >= W - 2: return None                                           # Maximum am Fensterrand = Kante liegt ausserhalb oder ist eine andere
    eind = abs(v) / max(zweit, 1e-9)
    if eind < 1.25 or koh < 0.5: return None
    tv = float(tau[ti]); e2 = (e + tv * n) / math.hypot(1, tv); n2 = np.array([-e2[1], e2[0]])
    return dict(n=n2, c0=m + float(d[di]) * n, guete=abs(v) / B["gmed"], eindeutig=eind, kohaerenz=koh, versatz_px=float(d[di]), kipp_grad=math.degrees(math.atan(tv)))


def kanten_beobachten(N, kanten, tris, fotos_dir, fenster_m, aus_dir=None, bilder_zeigen=12, nur=None):
    """Je Kamera und LoD2-Kante die Fotolinie suchen. -> Liste dict(ci, kid, n(2), c0(2) in SfM-Pixeln, ...)."""
    import trimesh, render_kern as rk, cv2
    mm = trimesh.Trimesh(vertices=tris.reshape(-1, 3), faces=np.arange(len(tris) * 3).reshape(-1, 3), process=False)
    beob = []; gezeigt = 0; t0 = time.time()
    for ci, name in enumerate(N["namen"]):
        if nur is not None and ci not in nur: continue
        R, t, f, c, k1 = N["R"][ci], N["t"][ci], N["f"][ci], N["c"][ci], N["k1"][ci]; w, h = N["wh"][ci]
        Cw = -R.T @ t; kand = []
        for k in kanten:
            A, Bp = np.array(k["a"]), np.array(k["b"])
            if k["art"] == "ecke": A = A + [0, 0, 1.5]; Bp = Bp - [0, 0, 0.5]
            X = A + np.linspace(0, 1, 48)[:, None] * (Bp - A); uv, z = projizieren(R, t, f, c, k1, X)
            ok = (z > 2) & (uv[:, 0] > 0.02 * w) & (uv[:, 0] < 0.98 * w) & (uv[:, 1] > 0.02 * h) & (uv[:, 1] < 0.98 * h)
            if ok.sum() >= 16: kand.append((k, X, uv, z, ok))
        if not kand: continue
        fp = os.path.join(fotos_dir, name)
        if not os.path.exists(fp): continue
        B = bild_laden(fp, (w, h))
        if B is None: continue
        ss = B["sc"]                                          # SfM-Pixel -> Bildpixel
        sr = 0.25; tiefe = np.asarray(rk.dreiecke_rastern(mm, R, t, f * sr, c[0] * sr, c[1] * sr, int(w * sr), int(h * sr), nur_tiefe=True)[0])
        mal = None
        for k, X, uv, z, ok in kand:
            # Verdeckung (Lochkamera fuer das Tiefenbild; k1-Versatz am Rand klein gegen 4 Nachbarpixel): sichtbar, wenn im 3x3-Umfeld nichts deutlich davor
            Xc = X @ R.T + t; ul = Xc[:, :2] / Xc[:, 2:3] * f * sr + c * sr; ix = np.clip(np.round(ul[:, 0]).astype(int), 1, tiefe.shape[1] - 2); iy = np.clip(np.round(ul[:, 1]).astype(int), 1, tiefe.shape[0] - 2)
            tmax = np.max(np.stack([tiefe[iy + dy, ix + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]), 0)
            vis = ok & (tmax >= z - 0.5 - 0.02 * z)
            # laengster zusammenhaengender sichtbarer Lauf
            best, cur, b0, bb = 0, 0, 0, (0, 0)
            for i, v in enumerate(vis):
                cur = cur + 1 if v else 0
                if cur == 1: b0 = i
                if cur > best: best, bb = cur, (b0, i + 1)
            if best < 16: continue
            sl = slice(*bb); uvb = uv[sl] * ss
            fen = fenster_m * f * ss / float(np.median(z[sl]))
            r = kante_suchen(B, uvb, fen)
            if r is None: continue
            if k["art"] == "traufe" and abs(r["n"][1]) < 0.7: continue          # Traufe von der Seite (im Bild steil) = keine Hoehenaussage, oft die Ecke
            beob.append(dict(ci=ci, foto=name, kid=k["id"], n=r["n"].tolist(), c0=(r["c0"] / ss).tolist(), X=X[sl][np.linspace(0, best - 1, 6).astype(int)].tolist(),
                             guete=round(r["guete"], 2), eindeutig=round(r["eindeutig"], 2), kohaerenz=round(r["kohaerenz"], 2), versatz_px=round(r["versatz_px"] / ss, 1),
                             kipp_grad=round(r["kipp_grad"], 2), tiefe_m=round(float(np.median(z[sl])), 1)))
            if aus_dir and gezeigt < bilder_zeigen:
                if mal is None: mal = cv2.cvtColor(B["grau"], cv2.COLOR_GRAY2BGR)
                p0, p1 = uvb[0], uvb[-1]; cv2.line(mal, tuple(int(v) for v in p0), tuple(int(v) for v in p1), (0, 200, 255), 1)
                nn = r["n"]; cc = r["c0"]; ee = np.array([nn[1], -nn[0]]); L = np.linalg.norm(p1 - p0) / 2 + 20
                cv2.line(mal, tuple(int(v) for v in cc - L * ee), tuple(int(v) for v in cc + L * ee), (40, 40, 255), 2)
        if mal is not None and aus_dir:
            cv2.imwrite(os.path.join(aus_dir, f"kanten_{os.path.splitext(name)[0]}.jpg"), mal); gezeigt += 1
        if ci % 50 == 0: print(f"  Kantensuche {ci}/{len(N['namen'])}: {len(beob)} Beobachtungen ({time.time() - t0:.0f} s)", flush=True)
    return beob


# ---------------------------------------------------------------- GPS
def gps_lesen(obj, namen, fotos_dir):
    from gps_ausrichtung import gps_exif
    from bilder_holen import wgs84_zu_utm
    r = obj["rahmen"]; m0 = np.array(r["mitte_utm"], float); xh = np.array(r["xhat_utm"], float); yh = np.array(r["yhat_utm"], float); aus = {}
    for ci, n in enumerate(namen):
        g = gps_exif(os.path.join(fotos_dir, n))
        if not g or not all(math.isfinite(float(x)) for x in g) or (abs(g[0]) < 1e-6 and abs(g[1]) < 1e-6): continue
        d = np.array(wgs84_zu_utm(*g)) - m0; aus[ci] = np.array([d @ xh, d @ yh])
    return aus


# ---------------------------------------------------------------- Ausgleich
class Ausgleich:
    def __init__(s, N, beob, gps, a):
        import torch
        s.th = torch; d = dict(dtype=torch.float64, device=DEV); s.d = d; s.a = a
        s.nc = len(N["namen"]); s.R = torch.as_tensor(N["R"], **d); s.t = torch.as_tensor(N["t"], **d); s.lf = torch.log(torch.as_tensor(N["f"], **d)); s.k1 = torch.as_tensor(N["k1"], **d)
        s.c = torch.as_tensor(N["c"], **d); s.lf0 = s.lf.clone()
        # nur Punkte mit >= 2 Beobachtungen
        cnt = np.bincount(N["oj"], minlength=len(N["P"])); keep = cnt[N["oj"]] >= 2
        oi, oj, ouv = N["oi"][keep], N["oj"][keep], N["ouv"][keep]; up, oj2 = np.unique(oj, return_inverse=True); s.pmap = up
        order = np.argsort(oj2, kind="stable"); oi, oj2, ouv = oi[order], oj2[order], ouv[order]
        s.oi = torch.as_tensor(oi, device=DEV); s.oj = torch.as_tensor(oj2, device=DEV); s.ouv = torch.as_tensor(ouv, **d); s.X = torch.as_tensor(N["P"][up], **d); s.np_ = len(up)
        # Paare (o1, o2) je Punkt fuer das Schur-Komplement
        starts = np.r_[0, np.cumsum(np.bincount(oj2, minlength=len(up)))]; L = np.diff(starts)
        p1 = np.concatenate([np.repeat(np.arange(starts[j], starts[j + 1]), L[j]) for j in range(len(up))]); p2 = np.concatenate([np.tile(np.arange(starts[j], starts[j + 1]), L[j]) for j in range(len(up))])
        s.p1 = torch.as_tensor(p1, device=DEV); s.p2 = torch.as_tensor(p2, device=DEV); s.pidx = s.oi[s.p1] * s.nc + s.oi[s.p2]
        s.cauchy = a.cauchy1; s.beob_setzen(beob); s.gps = gps; s.gw = torch.ones(s.nc, **d)        # GPS-/Kantengewicht je Kamera (Ausreisser -> 0)
        gi = sorted(gps); s.g_ci = torch.as_tensor(gi, device=DEV, dtype=torch.long); s.g_xy = torch.as_tensor(np.array([gps[i] for i in gi]).reshape(-1, 2), **d)
        print(f"Ausgleich: {s.nc} Kameras, {s.np_} Punkte, {len(oi)} Beobachtungen, {len(p1)} Paare, {len(gi)} GPS", flush=True)

    def beob_setzen(s, beob):
        th = s.th; d = s.d; s.beob = beob
        if not beob: s.l_ci = th.zeros(0, dtype=th.long, device=DEV); return
        ci, n, c0, X = [], [], [], []
        for b in beob:
            for x in b["X"]: ci.append(b["ci"]); n.append(b["n"]); c0.append(b["c0"]); X.append(x)
        s.l_ci = th.as_tensor(ci, device=DEV); s.l_n = th.as_tensor(n, **d); s.l_c0 = th.as_tensor(c0, **d); s.l_X = th.as_tensor(X, **d); s.l_m = len(beob[0]["X"])

    # Projektion + analytische Jacobi-Matrizen (Linearisierung bei Drehzuwachs 0: R = Exp(w) R)
    def proj_jac(s, ci, X, mit_p=True):
        th = s.th; R = s.R[ci]; Y = (R @ X[..., None])[..., 0]; Xc = Y + s.t[ci]; z = Xc[:, 2:3]; u = Xc[:, :2] / z; r2 = (u * u).sum(1, keepdim=True)
        f = th.exp(s.lf[ci])[:, None]; k1 = s.k1[ci][:, None]; dist = u * (1 + k1 * r2); p = f * dist + s.c[ci]
        zz = z[:, 0]; Du = th.zeros(len(ci), 2, 3, **s.d); Du[:, 0, 0] = 1 / zz; Du[:, 1, 1] = 1 / zz; Du[:, 0, 2] = -u[:, 0] / zz; Du[:, 1, 2] = -u[:, 1] / zz
        Dd = (1 + k1 * r2)[..., None] * th.eye(2, **s.d)[None] + 2 * k1[..., None] * u[:, :, None] * u[:, None, :]
        A = f[..., None] * (Dd @ Du)                                                     # (n,2,3) dp/dXc
        Jc = th.cat([A @ (-kreuz(Y)), A, (f * dist)[..., None], (f * u * r2)[..., None]], 2)    # (n,2,8)
        Jp = A @ R if mit_p else None
        return p, zz, Jc, Jp

    def kosten_teile(s, nur_kosten=False):
        th = s.th; a = s.a
        p, z, Jc, Jp = s.proj_jac(s.oi, s.X[s.oj], mit_p=not nur_kosten)
        r = (p - s.ouv) / a.sigma_px; rn = th.linalg.norm(r, dim=1); hk = a.huber
        w = th.where(rn <= hk, th.ones_like(rn), hk / rn.clamp(min=1e-12)); rho = th.where(rn <= hk, rn ** 2, 2 * hk * rn - hk ** 2)
        w = th.where(z > 0.2, w, th.zeros_like(w)); rho = th.where(z > 0.2, rho, th.zeros_like(rho))
        E = float(rho.sum()); teile = dict(bild=E)
        cam = []                                                                          # (ci, J (m,8), r (m,), wgt (m,))
        if len(s.l_ci):
            pl, zl, Jl, _ = s.proj_jac(s.l_ci, s.l_X, mit_p=False)
            rl = ((pl - s.l_c0) * s.l_n).sum(1) / a.sigma_kante; gl = s.gw[s.l_ci] / (s.l_m / 2.0)
            cc = s.cauchy; wl = 1 / (1 + (rl / cc) ** 2); rhol = cc ** 2 * th.log1p((rl / cc) ** 2) * gl
            teile["kanten"] = float(rhol.sum()); E += teile["kanten"]
            cam.append((s.l_ci, (s.l_n[:, None, :] @ Jl)[:, 0] / a.sigma_kante, rl, wl * gl))
        if len(s.g_ci) and not a.ohne_gps:
            ci = s.g_ci; R = s.R[ci]; tt = s.t[ci]; C = -(R.transpose(1, 2) @ tt[..., None])[..., 0]
            rg = (C[:, :2] - s.g_xy) / a.sigma_gps; cc = 2.0; rgn = th.linalg.norm(rg, dim=1); wg = 1 / (1 + (rgn / cc) ** 2) * s.gw[ci]
            teile["gps"] = float((cc ** 2 * th.log1p((rgn / cc) ** 2) * s.gw[ci]).sum()); E += teile["gps"]
            dCdw = -(R.transpose(1, 2) @ kreuz(tt)); dCdt = -R.transpose(1, 2)
            Jg = th.zeros(len(ci), 2, 8, **s.d); Jg[:, :, :3] = dCdw[:, :2]; Jg[:, :, 3:6] = dCdt[:, :2]; Jg /= a.sigma_gps
            for k in range(2): cam.append((ci, Jg[:, k], rg[:, k], wg))
        rk = s.k1 / 0.25; rf = (s.lf - s.lf0) / 0.5; teile["prior"] = float((rk ** 2).sum() + (rf ** 2).sum()); E += teile["prior"]
        ar = th.arange(s.nc, device=DEV); Jk = th.zeros(s.nc, 8, **s.d); Jk[:, 7] = 1 / 0.25; Jf = th.zeros(s.nc, 8, **s.d); Jf[:, 6] = 1 / 0.5
        cam += [(ar, Jk, rk, th.ones_like(rk)), (ar, Jf, rf, th.ones_like(rf))]
        if nur_kosten: return E, teile
        return E, teile, (r, w, Jc, Jp), cam

    def schritt(s, lam):
        th = s.th; a = s.a; nc, npt = s.nc, s.np_
        E, teile, (r, w, Jc, Jp), cam = s.kosten_teile()
        Jc = Jc / a.sigma_px; Jp = Jp / a.sigma_px; W = w[:, None, None]
        U = th.zeros(nc, 8, 8, **s.d); gc = th.zeros(nc, 8, **s.d); V = th.zeros(npt, 3, 3, **s.d); gp = th.zeros(npt, 3, **s.d)
        U.index_add_(0, s.oi, Jc.transpose(1, 2) @ (W * Jc)); gc.index_add_(0, s.oi, (Jc.transpose(1, 2) @ (w[:, None] * r)[..., None])[..., 0])
        V.index_add_(0, s.oj, Jp.transpose(1, 2) @ (W * Jp)); gp.index_add_(0, s.oj, (Jp.transpose(1, 2) @ (w[:, None] * r)[..., None])[..., 0])
        Wo = Jc.transpose(1, 2) @ (W * Jp)                                               # (o,8,3)
        for ci, J, rr, ww in cam:
            U.index_add_(0, ci, J[:, :, None] * J[:, None, :] * ww[:, None, None]); gc.index_add_(0, ci, J * (ww * rr)[:, None])
        Ud = U + lam * th.diag_embed(th.diagonal(U, dim1=1, dim2=2) + 1e-6); Vd = V + lam * th.diag_embed(th.diagonal(V, dim1=1, dim2=2) + 1e-9)
        Vi = th.linalg.inv(Vd); Y = Wo @ Vi[s.oj]                                        # (o,8,3)
        S = th.zeros(nc * nc, 8, 8, **s.d); ch = 400_000       # 2,5-GB-Budget
        for k in range(0, len(s.p1), ch):
            a1, a2 = s.p1[k:k + ch], s.p2[k:k + ch]; S.index_add_(0, s.pidx[k:k + ch], -(Y[a1] @ Wo[a2].transpose(1, 2)))
        S = S.view(nc, nc, 8, 8).permute(0, 2, 1, 3).reshape(nc * 8, nc * 8); ar = th.arange(nc, device=DEV)
        S.view(nc, 8, nc, 8)[ar, :, ar, :] += Ud
        tmp = (Vi @ gp[..., None])[..., 0]                                                # V^-1 g_p
        b = gc.clone(); b.index_add_(0, s.oi, -(Wo @ tmp[s.oj][..., None])[..., 0])           # g_c - W V^-1 g_p
        try: L = th.linalg.cholesky(0.5 * (S + S.T)); dc = -th.cholesky_solve(b.reshape(-1, 1), L).view(nc, 8)
        except Exception: return None, E, teile
        rhs = gp.clone(); rhs.index_add_(0, s.oj, (Wo.transpose(1, 2) @ dc[s.oi][..., None])[..., 0]); dp = -(Vi @ rhs[..., None])[..., 0]
        return (dc, dp), E, teile

    def anwenden(s, dc, dp, vor=True):
        th = s.th; alt = (s.R.clone(), s.t.clone(), s.lf.clone(), s.k1.clone(), s.X.clone())
        s.R = rodr_t(dc[:, :3]) @ s.R; s.t = s.t + dc[:, 3:6]; s.lf = s.lf + dc[:, 6]; s.k1 = s.k1 + dc[:, 7]; s.X = s.X + dp
        return alt

    def loesen(s, iters=20):
        lam = 1e-3; E0 = None
        E1 = None
        for it in range(iters):
            t0 = time.time(); erg, E, teile = s.schritt(lam); E1 = E
            if E0 is None: E0 = E; print(f"  Start: E {E:.4g} {json.dumps({k: round(v, 1) for k, v in teile.items()})}", flush=True)
            if erg is None: lam *= 10; continue
            alt = s.anwenden(*erg); E1, t1 = s.kosten_teile(nur_kosten=True)
            if E1 < E: lam = max(lam / 3, 1e-7); ok = "ok"
            else: s.R, s.t, s.lf, s.k1, s.X = alt; lam *= 8; ok = "verworfen"; E1 = E
            print(f"  LM {it}: E {E1:.6g} ({ok}, lam {lam:.1e}, {time.time() - t0:.1f} s) {json.dumps({k: round(v, 1) for k, v in t1.items()}) if ok == 'ok' else ''}", flush=True)
            if ok == "ok" and (E - E1) < 1e-6 * E: break
            if lam > 1e6: break
        return E0, E1

    def zustand(s):
        return dict(namen=None, R=s.R.cpu().numpy(), t=s.t.cpu().numpy(), f=np.exp(s.lf.cpu().numpy()), c=s.c.cpu().numpy(), k1=s.k1.cpu().numpy())


# ---------------------------------------------------------------- Auswertung
def kanten_rest(N, beob):
    """je Beobachtung mittlerer Abstand (px SfM, m) der projizierten Kante zur Fotolinie."""
    aus = []
    for b in beob:
        ci = b["ci"]; uv, z = projizieren(N["R"][ci], N["t"][ci], N["f"][ci], N["c"][ci], N["k1"][ci], np.array(b["X"]))
        rr = (uv - np.array(b["c0"])) @ np.array(b["n"]); aus.append((ci, b["kid"], float(np.mean(np.abs(rr))), float(np.mean(np.abs(rr) * z / N["f"][ci]))))
    return aus


def kamera_richtung(N, mitte):
    C = np.array([-R.T @ t for R, t in zip(N["R"], N["t"])]); az = np.degrees(np.arctan2(C[:, 1] - mitte[1], C[:, 0] - mitte[0])) % 360
    return C, az, np.hypot(C[:, 0] - mitte[0], C[:, 1] - mitte[1])


def gruppen_bericht(N, rest, pruef, mitte, gps):
    C, az, dist = kamera_richtung(N, mitte); g = {}
    for lo in range(0, 360, 60):
        sel = [i for i in range(len(az)) if lo <= az[i] < lo + 60]
        ra = [r[3] for r, p in zip(rest, pruef) if r[0] in sel and not p]; rp = [r[3] for r, p in zip(rest, pruef) if r[0] in sel and p]
        gg = [np.hypot(*(C[i, :2] - gps[i])) for i in sel if i in gps]
        g[f"{lo}-{lo + 60}"] = dict(kameras=len(sel), kanten_n=len(ra), kanten_med_m=round(float(np.median(ra)), 3) if ra else None,
                                    pruef_n=len(rp), pruef_med_m=round(float(np.median(rp)), 3) if rp else None, gps_n=len(gg), gps_rest_med_m=round(float(np.median(gg)), 1) if gg else None,
                                    abstand_med_m=round(float(np.median(dist[sel])), 1) if sel else None)
    return g


def gps_fit(N, gps, nah=100.0):
    from lage_gps_pruefen import fit2d, winkel
    C, _, _ = kamera_richtung(N, (0, 0)); ii = sorted(gps); M = C[ii, :2]; G = np.array([gps[i] for i in ii]); erg = {}
    for nm, sel in (("alle", np.ones(len(ii), bool)), ("nah", np.hypot(*G.T) < nah), ("fern", np.hypot(*G.T) >= nah)):
        if sel.sum() < 4: continue
        w = sel.copy()
        for _ in range(5):
            s, R, t = fit2d(M[w], G[w]); res = np.hypot(*(M @ R.T * s + t - G).T); w = sel & (res < max(np.percentile(res[sel], 80), 15))
        erg[nm] = dict(n=int(sel.sum()), massstab=round(float(s), 3), drehung_grad=round(winkel(R), 2), rest_med_m=round(float(np.median(res[w])), 2))
    return erg


def sparse_schreiben(src, dst, N, Xneu, pmap, pid, Palt_arr):
    """cameras/images/points3D.bin aus src kopieren und Posen/Intrinsik/Punkte im Modellrahmen einsetzen (Bytes ersetzen, Aufbau bleibt)."""
    import struct
    from scipy.spatial.transform import Rotation as Rot
    os.makedirs(dst, exist_ok=True); nidx = {n: i for i, n in enumerate(N["namen"])}
    b = bytearray(open(os.path.join(src, "images.bin"), "rb").read()); o = 8; cid_neu = {}
    for _ in range(struct.unpack_from("<Q", b, 0)[0]):
        cid = struct.unpack_from("<i", b, o + 60)[0]; e = b.index(b"\0", o + 64); name = b[o + 64:e].decode(); i = nidx[name]
        q = Rot.from_matrix(N["R"][i]).as_quat(); struct.pack_into("<4d", b, o + 4, q[3], q[0], q[1], q[2]); struct.pack_into("<3d", b, o + 36, *N["t"][i]); cid_neu[cid] = i
        o = e + 1; npt = struct.unpack_from("<Q", b, o)[0]; o += 8 + 24 * npt
    open(os.path.join(dst, "images.bin"), "wb").write(b)
    b = bytearray(open(os.path.join(src, "cameras.bin"), "rb").read()); o = 8
    for _ in range(struct.unpack_from("<Q", b, 0)[0]):
        cid, mod, w, h = struct.unpack_from("<iiQQ", b, o); n = KG._NP[mod]
        if cid in cid_neu: i = cid_neu[cid]; struct.pack_into("<4d", b, o + 24, N["f"][i], N["c"][i][0], N["c"][i][1], N["k1"][i])
        o += 24 + 8 * n
    open(os.path.join(dst, "cameras.bin"), "wb").write(b)
    b = bytearray(open(os.path.join(src, "points3D.bin"), "rb").read()); o = 8; pos = {int(pid[j]): k for k, j in enumerate(pmap)}; Palt = {int(p): Palt_arr[j] for j, p in enumerate(pid)}
    for _ in range(struct.unpack_from("<Q", b, 0)[0]):
        p_ = struct.unpack_from("<Q", b, o)[0]
        if p_ in pos: struct.pack_into("<3d", b, o + 8, *Xneu[pos[p_]])
        else: struct.pack_into("<3d", b, o + 8, *Palt[p_])                         # nicht ausgeglichen (< 2 Beobachtungen): alte Lage im Modellrahmen
        tl = struct.unpack_from("<Q", b, o + 43)[0]; o += 51 + 8 * tl
    open(os.path.join(dst, "points3D.bin"), "wb").write(b)


def ausrichtung_schreiben(pfad, N, vorlage, sparse_neu, bericht):
    kam = {}
    for i, n in enumerate(N["namen"]):
        R, t = N["R"][i], N["t"][i]; w, h = N["wh"][i]
        kam[os.path.splitext(n)[0]] = dict(standort=[round(float(v), 3) for v in -R.T @ t], f_px_original=float(N["f"][i]), fak=1.0, off=[0.0, 0.0], R=R.tolist(), t=t.tolist(),
                                           cx=float(N["c"][i][0]), cy=float(N["c"][i][1]), k=[float(N["k1"][i])], bild_b=int(w), bild_h=int(h), hinweis="buendel_stuetz.py (Modellrahmen, SfM-Pixel)")
    A = dict(verfahren="buendel_stuetz.py: Buendelausgleich mit LoD2-Passkanten im Foto + Foto-GPS (robust), Ausgang " + str(vorlage), sparse=sparse_neu,
             transformation=dict(beschreibung="Einheit: Kameras/Punkte bereits im Modellrahmen", s=1.0, s_sigma_prozent=None, rvec=[0.0, 0.0, 0.0], t=[0.0, 0.0, 0.0]),
             ausreisser=bericht.get("ausreisser"), kameras=kam)
    json.dump(A, open(pfad, "w"), indent=0)


def probe_anlegen(probe, od, obj, ausr_pfad):
    """Probe-Objektkopie: PROBE/modelle/<obj>/{objekt.json, dach.json, messprotokoll/, audit/}, PROBE/daten -> Repo/daten, PROBE/modelle/stl -> Repo/modelle/stl."""
    import shutil, subprocess
    name = os.path.basename(od); pod = os.path.join(probe, "modelle", name); os.makedirs(os.path.join(pod, "messprotokoll"), exist_ok=True); os.makedirs(os.path.join(pod, "audit"), exist_ok=True)
    for q, z in ((os.path.join(ROOT, "daten"), os.path.join(probe, "daten")), (os.path.join(ROOT, "modelle", "stl"), os.path.join(probe, "modelle", "stl"))):
        if not os.path.exists(z): os.symlink(q, z)
    for f in ("objekt.json", "dach.json", "masstabelle.json", "elemente.json"):
        if os.path.exists(os.path.join(od, f)): shutil.copy2(os.path.join(od, f), os.path.join(pod, f))
    hc = os.path.join(od, "audit", "himmel_cache")                                   # Himmelsmasken haengen nur am Foto, nicht an der Kamera
    if os.path.isdir(hc) and not os.path.exists(os.path.join(pod, "audit", "himmel_cache")): shutil.copytree(hc, os.path.join(pod, "audit", "himmel_cache"))
    shutil.copy2(ausr_pfad, os.path.join(pod, "messprotokoll", os.path.basename(ausr_pfad)))
    r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "kameras_aus_buendel.py"), os.path.join(pod, "objekt.json"), "--ausrichtung", os.path.join(pod, "messprotokoll", os.path.basename(ausr_pfad)),
                        "--ueberschreiben"], capture_output=True, text=True)
    print("\n".join((r.stdout + r.stderr).strip().splitlines()[-3:])); return pod


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("objekt"); ap.add_argument("--sparse", required=True); ap.add_argument("--ausrichtung", required=True); ap.add_argument("--name", default="stuetz")
    ap.add_argument("--fotos", default=""); ap.add_argument("--radius", type=float, default=40.0); ap.add_argument("--traufe", action="store_true", help="obere Wandkanten des ZIELGEBAEUDES (objekt.json lod2.id) als waagerechte Passkanten")
    ap.add_argument("--traufe-eben", action="store_true", help="ANNAHME Traufe ringsum waagerecht: alle Traufkanten auf die mittlere LoD2-Hoehe (LoD2-Traufhoehen schwanken je Wand um 0,5 m)")
    ap.add_argument("--ohne-gps", action="store_true"); ap.add_argument("--ohne-kanten", action="store_true")
    ap.add_argument("--sigma-px", type=float, default=1.0); ap.add_argument("--huber", type=float, default=2.0); ap.add_argument("--sigma-kante", type=float, default=2.0)
    ap.add_argument("--cauchy", type=float, default=3.0); ap.add_argument("--cauchy1", type=float, default=10.0, help="Durchgang 1 (weiter Kern: Startfehler 30-60 px sind echte Abweichungen)"); ap.add_argument("--sigma-gps", type=float, default=8.0)
    ap.add_argument("--fenster", type=float, default=2.0); ap.add_argument("--fenster2", type=float, default=0.6); ap.add_argument("--iter", type=int, default=25)
    ap.add_argument("--pruef", type=float, default=0.25); ap.add_argument("--ausreisser-px", type=float, default=8.0); ap.add_argument("--ausreisser-m", type=float, default=0.6)
    ap.add_argument("--aus", default=""); ap.add_argument("--uebernehmen", action="store_true", help="Ausrichtung zusaetzlich nach modelle/<obj>/messprotokoll/ (nur nach bestandenen Toren)"); ap.add_argument("--k-dateien", default="", help="Probeordner: Objektkopie mit K-Dateien der neuen Kameras")
    a = ap.parse_args(); t00 = time.time()
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); obj = json.load(open(objp)); on = os.path.basename(od)
    fd = a.fotos or (obj["fotos_dir"] if os.path.isabs(obj["fotos_dir"]) else os.path.join(ROOT, obj["fotos_dir"]))
    aus = a.aus or f"/media/oem/scan/rc-park_daten/{on}/buendel_stuetz/{a.name}"; os.makedirs(aus, exist_ok=True)
    A = json.load(open(a.ausrichtung)); N = netz_lesen(a.sparse, A)
    # Gegenprobe: Netz im Modellrahmen = Kameras der Ausrichtung?
    k0 = A["kameras"].get(os.path.splitext(N["namen"][0])[0])
    if k0: print(f"Rahmenpruefung {N['namen'][0]}: Standort Netz {np.round(-N['R'][0].T @ N['t'][0], 2).tolist()} / Ausrichtung {k0['standort']}")
    try: mitte = json.load(open(os.path.join(od, "dach.json")))["teile"][0]["mitte_uv"]
    except Exception: mitte = [0.5 * (obj["rahmen_wand"]["u0"] + obj["rahmen_wand"]["u1"]), 0.5 * (obj["rahmen_wand"]["v0"] + obj["rahmen_wand"]["v1"])] if "rahmen_wand" in obj else [0.0, 0.0]
    kanten, tris = lod2_kanten(obj, a.radius, a.traufe)
    if a.traufe:                                                                      # nur das Zielgebaeude: Nachbartraufen sind Dachueberstaende ohne LoD2-Gegenstueck
        kanten = [k for k in kanten if k["art"] != "traufe" or k["geb_id"] == obj["lod2"].get("id")]
        tr_ = [k for k in kanten if k["art"] == "traufe"]
        if a.traufe_eben and tr_:
            zt = float(np.median([z for k in tr_ for z in (k["a"][2], k["b"][2])]))
            for k in tr_: k["a"][2] = k["b"][2] = zt; k["annahme"] = f"ANNAHME: Traufe waagerecht auf {zt:.2f} m (Median LoD2)"
            print(f"Traufe eben: {len(tr_)} Kanten auf z {zt:.2f} m", flush=True)
        for i, k in enumerate(kanten): k["id"] = i
    print(f"LoD2: {len(kanten)} Passkanten ({sum(k['art'] == 'ecke' for k in kanten)} Ecken), {len(tris)} Dreiecke; Mitte {mitte}", flush=True)
    gps = gps_lesen(obj, N["namen"], fd); print(f"GPS: {len(gps)} Kameras mit EXIF-GPS", flush=True)
    N0 = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in N.items()}
    rng = np.random.default_rng(1)
    beob = [] if a.ohne_kanten else kanten_beobachten(N, kanten, tris, fd, a.fenster, aus)
    pruef_set = {(b["ci"], b["kid"]) for b in beob if rng.random() < a.pruef}
    print(f"Kantenbeobachtungen Durchgang 1: {len(beob)} ({len(pruef_set)} zur Pruefung zurueckgehalten)", flush=True)
    # Ausreisser markieren (nicht verbiegen): Kantenrest, Plausibilitaet, GPS
    def ausreisser_finden(M, beob_):
        rest = kanten_rest(M, beob_); je = {}
        for ci, kid, px, m in rest: je.setdefault(ci, []).append((px, m))
        C, _, _ = kamera_richtung(M, (0, 0)); aus_ = {}
        for ci, n in enumerate(M["namen"]):
            w, h = M["wh"][ci]; ok, grund = KP.plausibel(M["f"][ci], (w, h), C[ci], k1=float(M["k1"][ci]), bild_diag=float(np.hypot(w, h)))
            vz = abs(float(M["k1"][ci])) * (0.5 * float(np.hypot(w, h)) / float(M["f"][ci])) ** 2
            if not ok: aus_[ci] = "unplausibel: " + grund
            elif M["f"][ci] > 2 * max(w, h) and vz > 0.02: aus_[ci] = f"unplausibel: Tele (f {M['f'][ci]:.0f} px) mit {vz * 100:.0f} % Randverzeichnung (k1 {float(M['k1'][ci]):.2f}) - Brennweite/Abstand/k1 vertauscht"   # 17.11.: od_08 f 13 385 px, k1 -1,58
            elif ci in je and len(je[ci]) >= 2 and np.median([x[0] for x in je[ci]]) > a.ausreisser_px and np.median([x[1] for x in je[ci]]) > a.ausreisser_m:   # 17.11.: px allein traf gute Nahfotos (113646: 15 px = 7 cm)
                aus_[ci] = f"Kantenrest Median {np.median([x[0] for x in je[ci]]):.1f} px / {np.median([x[1] for x in je[ci]]):.2f} m ({len(je[ci])} Kanten)"
            elif ci in gps and np.hypot(*(C[ci, :2] - gps[ci])) > 40 and np.hypot(*gps[ci]) < 100: aus_[ci] = f"GPS-Rest {np.hypot(*(C[ci, :2] - gps[ci])):.0f} m"
        return aus_
    ar0 = {ci: g for ci, g in ausreisser_finden(N0, []).items() if g.startswith("unplausibel")}       # schon im Ausgangsnetz unmoeglich (k1 -1,6, Standort km weit): kein Stuetzgewicht
    print(f"Ausgangsnetz: {len(ar0)} unplausible Kameras (ohne Stuetzgewicht, als Ausreisser markiert)", flush=True)
    AG = Ausgleich(N, [b for b in beob if (b["ci"], b["kid"]) not in pruef_set], gps, a)
    for ci in ar0: AG.gw[ci] = 0.0
    E0, E1 = AG.loesen(a.iter)
    def stand():
        z = AG.zustand(); M = dict(N); M.update(R=z["R"], t=z["t"], f=z["f"], k1=z["k1"]); return M
    N1 = stand()
    ar1 = ausreisser_finden(N1, beob); print(f"Durchgang 1: {len(ar1)} Ausreisser-Kameras markiert", flush=True)
    # Durchgang 2: Kanten mit engem Fenster um die ausgeglichenen Kameras neu suchen, Ausreisser ohne Stuetzgewicht
    if not a.ohne_kanten:
        beob2 = kanten_beobachten(N1, kanten, tris, fd, a.fenster2, None)
        # Pruefmenge bleibt dieselbe (Kamera, Kante) - neu gefundene Paare per Zufall zuordnen
        alt_paare = {(x["ci"], x["kid"]) for x in beob}
        for b in beob2:
            if (b["ci"], b["kid"]) not in alt_paare and rng.random() < a.pruef: pruef_set.add((b["ci"], b["kid"]))
        beob = beob2; AG.beob_setzen([b for b in beob if (b["ci"], b["kid"]) not in pruef_set]); print(f"Kantenbeobachtungen Durchgang 2: {len(beob)}", flush=True)
    for ci in list(ar1) + list(ar0): AG.gw[ci] = 0.0
    AG.cauchy = a.cauchy                                                              # Durchgang 2: enger robuster Kern
    AG.loesen(a.iter); N2 = stand(); ar2 = ausreisser_finden(N2, beob)
    for ci, g in ar0.items(): ar2.setdefault(ci, "Ausgangsnetz " + g)
    # Bericht: vorher (Ausgangskameras) / nachher an denselben Beobachtungen (Durchgang 2, Fotolinien sind Messwerte, unabhaengig von der Kamera)
    pruef = [(b["ci"], b["kid"]) in pruef_set for b in beob]
    rv, rn = kanten_rest(N0, beob), kanten_rest(N2, beob)
    def zus(rest, sel):
        v = [r[3] for r, p in zip(rest, pruef) if p == sel]; px = [r[2] for r, p in zip(rest, pruef) if p == sel]
        return dict(n=len(v), med_m=round(float(np.median(v)), 3) if v else None, med_px=round(float(np.median(px)), 2) if px else None, p90_m=round(float(np.percentile(v, 90)), 3) if v else None)
    C0, _, _ = kamera_richtung(N0, mitte); C2, az, dist = kamera_richtung(N2, mitte); dC = np.linalg.norm(C2 - C0, axis=1)
    bericht = dict(werkzeug="buendel_stuetz.py", datum=time.strftime("%Y-%m-%d %H:%M"), objekt=on, sparse=a.sparse, ausrichtung=a.ausrichtung, optionen=vars(a),
                   passkanten=kanten, n_beob=len(beob), n_pruef=int(sum(pruef)), kosten=dict(start=E0),
                   kanten_ausgeglichen=dict(vorher=zus(rv, False), nachher=zus(rn, False)), kanten_pruef=dict(vorher=zus(rv, True), nachher=zus(rn, True)),
                   gruppen_vorher=gruppen_bericht(N0, rv, pruef, mitte, gps), gruppen_nachher=gruppen_bericht(N2, rn, pruef, mitte, gps),
                   gps_fit_vorher=gps_fit(N0, gps), gps_fit_nachher=gps_fit(N2, gps),
                   kamera_verschiebung=dict(median_m=round(float(np.median(dC)), 3), p90_m=round(float(np.percentile(dC, 90)), 3),
                                            je_richtung={f"{lo}-{lo + 60}": round(float(np.median(dC[(az >= lo) & (az < lo + 60)])), 3) for lo in range(0, 360, 60) if ((az >= lo) & (az < lo + 60)).any()}),
                   massstab_je_richtung={f"{lo}-{lo + 60}": round(float(np.median(dist[(az >= lo) & (az < lo + 60)] / np.maximum(kamera_richtung(N0, mitte)[2][(az >= lo) & (az < lo + 60)], 1e-6))), 4)
                                         for lo in range(0, 360, 60) if ((az >= lo) & (az < lo + 60)).any()},
                   ausreisser={os.path.splitext(N["namen"][ci])[0]: g for ci, g in ar2.items()}, ausreisser_durchgang1={os.path.splitext(N["namen"][ci])[0]: g for ci, g in ar1.items()},
                   brennweite_aenderung_med=round(float(np.median(np.abs(N2["f"] / N0["f"] - 1))), 4), k1_nachher_max=round(float(np.max(np.abs(N2["k1"]))), 3), sek=round(time.time() - t00))
    json.dump(bericht, open(os.path.join(aus, "bericht.json"), "w"), indent=1, ensure_ascii=False, default=float)
    json.dump(beob, open(os.path.join(aus, "kanten_beob.json"), "w"), default=float)
    Xn = AG.X.cpu().numpy(); sparse_schreiben(a.sparse, os.path.join(aus, "sparse"), N2, Xn, AG.pmap, N["pid"], N["P"]); np.save(os.path.join(aus, "punkte_modell.npy"), Xn.astype(np.float32))
    ap_ = os.path.join(aus, f"SFM-AUSRICHTUNG-{on}_{a.name}.json"); ausrichtung_schreiben(ap_, N2, a.ausrichtung, os.path.join(aus, "sparse"), bericht)
    if a.uebernehmen:                                                                 # erst nach bestandenen Toren (Probe): Ausrichtung ins Objekt, dann kameras_aus_buendel.py
        import shutil; ziel_ = os.path.join(od, "messprotokoll", os.path.basename(ap_)); shutil.copy2(ap_, ziel_); print(f"uebernommen: {ziel_}")
    print(json.dumps({k: bericht[k] for k in ("kanten_ausgeglichen", "kanten_pruef", "gps_fit_vorher", "gps_fit_nachher", "kamera_verschiebung", "massstab_je_richtung")}, ensure_ascii=False))
    for g in ("gruppen_vorher", "gruppen_nachher"): print(g, json.dumps(bericht[g], ensure_ascii=False))
    print(f"Ausreisser ({len(ar2)}): " + "; ".join(f"{os.path.splitext(N['namen'][c])[0]}: {g}" for c, g in list(ar2.items())[:20]))
    print(f"geschrieben: {ap_}, {aus}/bericht.json ({time.time() - t00:.0f} s)")
    if a.k_dateien:
        A2 = json.load(open(ap_)); A2["kameras"] = {k: v for k, v in A2["kameras"].items() if k not in bericht["ausreisser"]}; tmp = os.path.join(aus, os.path.basename(ap_)); json.dump(A2, open(tmp, "w"), indent=0)
        pod = probe_anlegen(a.k_dateien, od, obj, tmp); print(f"Probe-Objekt: {pod}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
