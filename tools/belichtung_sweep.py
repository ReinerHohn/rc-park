#!/usr/bin/env python3
"""BS2: Belichtungs-/Kontrast-Sweep. Stufen: auswahl | varianten | merkmale | tri.
Arbeitsordner (gross) nur unter /media/oem/scan/rc-park_null/belichtung_kh. Buendel nur gelesen, Kameras fest.
Stufe auswahl: venv-colmap (pycolmap). Stufen varianten|merkmale|tri|bericht: /media/oem/scan/venv-seg/bin/python -I (torch GPU, cv2, scipy).
Aufruf: <python> -I tools/belichtung_sweep.py <stufe> [--objekt modelle/kaufhaus_null5] [--arbeit DIR] [--n 14]
Eigene Triangulation (feste Kameras) statt pycolmap.triangulate_points: Rig-Konflikt der DB (Register DF)."""
import sys, os, json, argparse, time, numpy as np, cv2

def args():
    p = argparse.ArgumentParser(); p.add_argument('stufe')
    p.add_argument('--objekt', default='modelle/kaufhaus_null5')
    p.add_argument('--arbeit', default='/media/oem/scan/rc-park_null/belichtung_kh')
    p.add_argument('--n', type=int, default=16)
    p.add_argument('--sift-max', type=int, default=int(os.environ.get('RCPARK_SIFT_MAX', 1600)))
    return p.parse_args()

def dach_hulle(R, t, K, WH, anker, first):
    """Bildregion des Dachvolumens: Grundrissecken von Traufhoehe bis First (Hohe aus LoD2/anker3d)."""
    pts = []
    for i in range(0, 20):
        b = anker.get(f'ecke_boden_{i}'); o = anker.get(f'ecke_wandoben_{i}')
        if not b or not o: break
        for z in (o['xyz'][2], first):
            pts.append([b['xyz'][0], b['xyz'][1], z])
    P = np.array(pts); c = (R @ P.T).T + t
    if (c[:, 2] <= 0.5).any(): return None, 0.0
    uv = (K @ c.T).T; uv = uv[:, :2] / uv[:, 2:3]
    hull = cv2.convexHull(uv.astype(np.float32))
    m = np.zeros((WH[1], WH[0]), np.uint8)
    cv2.fillConvexPoly(m, hull.astype(np.int32), 255)
    voll = cv2.contourArea(hull)
    return m, float(m.astype(bool).sum() / max(voll, 1))  # Anteil im Bild

def lade(o):
    import pycolmap
    r = pycolmap.Reconstruction(os.path.join(o, 'sfm/dicht_alle/sparse'))
    an = json.load(open(os.path.join(o, 'anker3d.json')))['anker']
    ob = json.load(open(os.path.join(o, 'objekt.json')))
    return r, an, ob['lod2']['first_m']

def auswahl(a):
    r, an, first = lade(a.objekt); res = []
    for im in r.images.values():
        cam = r.cameras[im.camera_id]; W, H = cam.width, cam.height
        T = im.cam_from_world().matrix(); R, t = T[:, :3], T[:, 3]
        K = cam.calibration_matrix()
        m, anteil = dach_hulle(R, t, K, (W, H), an, first)
        if m is None: continue
        flaeche = m.astype(bool).sum() / (W * H)
        pts = [p for p in im.points2D if p.has_point3D()]
        res.append(dict(name=im.name, dach_flaeche=float(flaeche), anteil_im_bild=float(anteil), n_punkte=len(pts)))
    # Auswahl quer ueber alle Gruppen/Seiten (Nutzerkorrektur): Gruppe = Brennweitenklasse (f gerundet), Seite = Azimut der Kamera um die Gebaeudemitte
    kam = json.load(open(os.path.join(a.objekt, 'sfm/dicht_alle/kameras_unverzerrt.json')))
    for x in res:
        c = kam[x['name'][:-4]]; R = np.array(c['R']); C = -R.T @ np.array(c['t'])
        x['azimut'] = float(np.degrees(np.arctan2(C[1] - 3.0, C[0] - 0.0)) % 360); x['dist'] = float(np.hypot(C[0], C[1] - 3.0)); x['f'] = float(c['fx'])
        x['hoehe_cam'] = float(C[2]); x['n_obs'] = x['n_punkte']
    sel = []; rest = [x for x in res if x['n_obs'] >= 150]
    sektor = lambda x: int(x['azimut'] // 45)
    # je Azimutsektor (8) das Bild mit den meisten Beobachtungen, dann Auffuellen nach Brennweiten-/Entfernungsvielfalt (abwechselnd nah/fern, nach f verschieden)
    for sk in range(8):
        c = sorted([x for x in rest if sektor(x) == sk], key=lambda x: -x['n_obs'])
        if c: sel.append(c[0])
    while len(sel) < a.n and len(sel) < len(rest):
        cand = [x for x in rest if x not in sel]
        cand.sort(key=lambda x: -min(abs(np.log(x['f'] / y['f'])) * 3 + abs(np.log(x['dist'] / y['dist'])) + abs(x['azimut'] - y['azimut']) / 90 for y in sel))
        sel.append(cand[0])
    json.dump(dict(alle=res, auswahl=[x['name'] for x in sel], kriterium='quer ueber Seiten: je 45-Grad-Azimutsektor das Bild mit den meisten Bundle-Beobachtungen (>=150), Rest nach Vielfalt Brennweite/Entfernung/Azimut'),
              open(os.path.join(a.arbeit, 'auswahl.json'), 'w'), indent=1)
    print(len(res), 'Bilder;', [(x['name'], round(x['azimut']), round(x['dist']), round(x['f'])) for x in sel])


# ---------------------------------------------------------------- Varianten
def gamma(g, x):
    lut = (255 * (np.arange(256) / 255.0) ** g).clip(0, 255).astype(np.uint8); return cv2.LUT(x, lut)

def varianten_von(bgr):
    """Name -> (Graubild uint8 fuer SIFT). Reihenfolge: orig zuerst."""
    gr = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY); V = {'orig': gr}
    for n, g in (('gam05', 0.5), ('gam07', 0.7), ('gam14', 1.4)): V[n] = gamma(g, gr)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB); L = lab[:, :, 0]
    V['clahe3'] = cv2.createCLAHE(3.0, (8, 8)).apply(L); V['clahe8'] = cv2.createCLAHE(8.0, (8, 8)).apply(L)
    f = gr.astype(np.float32); mu = cv2.GaussianBlur(f, (0, 0), 20); sd = np.sqrt(cv2.GaussianBlur((f - mu) ** 2, (0, 0), 20)) + 4.0
    V['lokal'] = np.clip(128 + 45 * (f - mu) / sd, 0, 255).astype(np.uint8)
    V['hell_p'] = cv2.convertScaleAbs(gr, alpha=1.0, beta=40); V['hell_m'] = cv2.convertScaleAbs(gr, alpha=1.0, beta=-40)
    for n, i in (('ch_b', 0), ('ch_g', 1), ('ch_r', 2)): V[n] = bgr[:, :, i].copy()
    V['hsv_v'] = bgr.max(axis=2); V['sat'] = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 1]
    stack = [cv2.cvtColor(gamma(g, gr), cv2.COLOR_GRAY2BGR) for g in (0.5, 1.0, 1.8)]
    # Mehrfachbelichtung: Mertens-Fusion aus Gamma 0.5 / 1.0 / 1.8 der Farbbilder
    col = [np.clip(255 * (bgr / 255.0) ** g, 0, 255).astype(np.uint8) for g in (0.5, 1.0, 1.8)]
    mf = cv2.createMergeMertens().process(col); V['mertens'] = cv2.cvtColor(np.clip(mf * 255, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY)
    return V

KONTROLLE = {'orig_ct02': 0.02, 'orig_ct01': 0.01}   # Kontrolle: nur Schwelle senken (gleiches Bild)

def sel_namen(a):
    return [n[:-4] for n in json.load(open(os.path.join(a.arbeit, 'auswahl.json')))['auswahl']]

def varianten(a):
    d = os.path.join(a.arbeit, 'varianten'); os.makedirs(d, exist_ok=True); stat = {}
    for n in sel_namen(a):
        bgr = cv2.imread(os.path.join(a.objekt, 'sfm/dicht_alle/images', n + '.jpg'))
        for k, g in varianten_von(bgr).items():
            cv2.imwrite(os.path.join(d, f'{n}_{k}.jpg'), g, [cv2.IMWRITE_JPEG_QUALITY, 93])
            stat.setdefault(k, []).append(float(g.mean()))
    print({k: round(float(np.mean(v)), 1) for k, v in stat.items()})

# ---------------------------------------------------------------- Merkmale
def sift_kp(gr, ct, cap):
    s = cv2.SIFT_create(nfeatures=0, contrastThreshold=ct); kp, de = s.detectAndCompute(gr, None)
    if de is None: return np.zeros((0, 2), np.float32), np.zeros((0, 128), np.float32), np.zeros(0, np.float32)
    resp = np.array([k.response for k in kp], np.float32); xy = np.array([k.pt for k in kp], np.float32)
    o = np.argsort(-resp)[:cap]; de = de[o]; de = de / (np.abs(de).sum(1, keepdims=True) + 1e-9); de = np.sqrt(de)   # RootSIFT
    return xy[o], de.astype(np.float32), resp[o]

REGIONEN = ['boden', 'fassade', 'dach', 'giebel', 'aussen']

def region_masken(a, n, WH, kam, an, first):
    """Bildregionen aus Hoehenband-Huellen des Grundrissvolumens: boden z0-4, fassade 4-9, dach 9-14 (ohne tiefere), giebel 14-First, aussen = Rest (Nachbarn/Platz/Himmel)."""
    c = kam[n]; K = np.array([[c['fx'], 0, c['cx']], [0, c['fy'], c['cy']], [0, 0, 1]]); R = np.array(c['R']); t = np.array(c['t'])
    ecken = [(an[f'ecke_boden_{i}']['xyz'][0], an[f'ecke_boden_{i}']['xyz'][1]) for i in range(4)]
    def hull(z0, z1):
        P = np.array([(x, y, z) for x, y in ecken for z in (z0, z1)]); cc = (R @ P.T).T + t
        m = np.zeros((WH[1], WH[0]), np.uint8)
        if (cc[:, 2] <= 0.3).any(): return m > 0
        uv = (K @ cc.T).T; uv = uv[:, :2] / uv[:, 2:3]; cv2.fillConvexPoly(m, cv2.convexHull(uv.astype(np.float32)).astype(np.int32), 255); return m > 0
    h4, h9, h14, hf = hull(0, 4), hull(0, 9), hull(0, 14), hull(0, first)
    boden = h4; fassade = h9 & ~h4; dach = h14 & ~h9; giebel = hf & ~h14; aussen = ~hf
    return dict(boden=boden, fassade=fassade, dach=dach, giebel=giebel, aussen=aussen)

def merkmale(a):
    kam = json.load(open(os.path.join(a.objekt, 'sfm/dicht_alle/kameras_unverzerrt.json'))); an = json.load(open(os.path.join(a.objekt, 'anker3d.json')))['anker']
    first = json.load(open(os.path.join(a.objekt, 'objekt.json')))['lod2']['first_m']
    names = sel_namen(a); out = {}; stat = []; cap = 20000
    for n in names:
        vd = {k: cv2.imread(os.path.join(a.arbeit, 'varianten', f'{n}_{k}.jpg'), 0) for k in varianten_von(np.zeros((8, 8, 3), np.uint8))}
        WH = (vd['orig'].shape[1], vd['orig'].shape[0]); MR = region_masken(a, n, WH, kam, an, first)
        # Himmel grob: sehr helle/blaue Pixel ohne Textur im Original ausschliessen
        bgr = cv2.imread(os.path.join(a.objekt, 'sfm/dicht_alle/images', n + '.jpg')); hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        gr = vd['orig'].astype(np.float32); lv = cv2.GaussianBlur((gr - cv2.GaussianBlur(gr, (0, 0), 5)) ** 2, (0, 0), 5)
        himmel = (lv < 9) & (hsv[:, :, 2] > 170) & ((hsv[:, :, 1] < 70) | ((hsv[:, :, 0] > 90) & (hsv[:, :, 0] < 130)))
        hd = cv2.dilate(himmel.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        MR = {r: m & ~hd for r, m in MR.items()}      # Himmel in keiner Region
        lab = np.full(vd['orig'].shape, -1, np.int8)
        for ri, r in enumerate(REGIONEN): lab[MR[r]] = ri
        for k, g in list(vd.items()) + [(k, vd['orig']) for k in KONTROLLE]:
            ct = KONTROLLE.get(k, 0.04); xy, de, rs = sift_kp(g, ct, cap)
            ij = np.clip(np.round(xy).astype(int), 0, [WH[0] - 1, WH[1] - 1]); rl = lab[ij[:, 1], ij[:, 0]]
            out[f'xy_{n}_{k}'] = xy; out[f'de_{n}_{k}'] = de.astype(np.float16); out[f'rs_{n}_{k}'] = rs
            for ri, r in enumerate(REGIONEN):
                im = rl == ri; mk = MR[r]
                stat.append(dict(bild=n, variante=k, region=r, n_kp=int(len(xy)), n_reg=int(im.sum()), reg_px=int(mk.sum()), reg_in_top1600=int(im[:1600].sum()),
                                 helligkeit=float(vd['orig'][mk].mean()) if mk.any() else None))
        print(n, {s['variante']: s['n_kp'] for s in stat if s['bild'] == n and s['region'] == 'boden'}, flush=True)
    np.savez_compressed(os.path.join(a.arbeit, 'merkmale.npz'), namen=np.array(names), **out)
    json.dump(stat, open(os.path.join(a.arbeit, 'merkmale_stat.json'), 'w'), indent=0)

# ---------------------------------------------------------------- Triangulation (feste Kameras)
def kamera(c):
    K = np.array([[c['fx'], 0, c['cx']], [0, c['fy'], c['cy']], [0, 0, 1.0]]); R = np.array(c['R']); t = np.array(c['t']); return K, R, t

def fund(c1, c2):
    K1, R1, t1 = kamera(c1); K2, R2, t2 = kamera(c2); R = R2 @ R1.T; t = t2 - R @ t1
    tx = np.array([[0, -t[2], t[1]], [t[2], 0, -t[0]], [-t[1], t[0], 0]]); E = tx @ R
    return np.linalg.inv(K2).T @ E @ np.linalg.inv(K1)

def epi_dist(F, x1, x2):
    h1 = np.c_[x1, np.ones(len(x1))]; h2 = np.c_[x2, np.ones(len(x2))]; l2 = h1 @ F.T; l1 = h2 @ F
    d2 = np.abs((h2 * l2).sum(1)) / np.hypot(l2[:, 0], l2[:, 1]); d1 = np.abs((h1 * l1).sum(1)) / np.hypot(l1[:, 0], l1[:, 1]); return np.maximum(d1, d2)

def match_gpu(d1, d2, ratio=0.8):
    import torch
    A = torch.from_numpy(d1).cuda().half(); B = torch.from_numpy(d2).cuda().half()
    if len(A) < 2 or len(B) < 2: return np.zeros((0, 2), int)
    S = []; I = []
    for i in range(0, len(A), 4096):
        sim = A[i:i + 4096] @ B.T; v, ix = sim.topk(2, dim=1); S.append(v.float()); I.append(ix)
    S = torch.cat(S); I = torch.cat(I); d = torch.sqrt(torch.clamp(2 - 2 * S, min=0))   # Abstand RootSIFT (L2=1)
    ok = d[:, 0] < ratio * d[:, 1]
    # gegenseitig
    best_b = []
    for j in range(0, len(B), 4096):
        sim = B[j:j + 4096] @ A.T; best_b.append(sim.argmax(1))
    best_b = torch.cat(best_b); idx = torch.arange(len(A), device=A.device); mut = best_b[I[:, 0]] == idx
    m = (ok & mut).nonzero().squeeze(1)
    r = np.stack([m.cpu().numpy(), I[m, 0].cpu().numpy()], 1); del A, B; torch.cuda.empty_cache(); return r

def dlt(Ps, uvs):
    A = []
    for P, uv in zip(Ps, uvs): A += [uv[0] * P[2] - P[0], uv[1] * P[2] - P[1]]
    _, _, vt = np.linalg.svd(np.array(A)); X = vt[-1]; return X[:3] / X[3]

def triangulieren(P, K, R, t, namen, tracks, max_err=2.0, min_winkel=3.0):
    """tracks: Liste von [(bildindex, xy_colmap)]. Gibt Punkte, Fehler, Zahl Beobachtungen, Winkel."""
    Pm = [K[i] @ np.c_[R[i], t[i]] for i in range(len(namen))]; C = [-R[i].T @ t[i] for i in range(len(namen))]
    res = []
    for tr in tracks:
        obs = list(tr)
        for _ in range(4):
            if len(obs) < 2: break
            X = dlt([Pm[i] for i, _ in obs], [uv for _, uv in obs])
            e = []
            for i, uv in obs:
                c = R[i] @ X + t[i]
                if c[2] <= 0: e.append(1e9); continue
                p = K[i] @ c; e.append(np.hypot(*(p[:2] / p[2] - uv)))
            e = np.array(e)
            if e.max() <= max_err: break
            obs.pop(int(e.argmax()))
        if len(obs) < 2 or e.max() > max_err: continue
        v = [(X - C[i]) / np.linalg.norm(X - C[i]) for i, _ in obs]; w = max(np.degrees(np.arccos(np.clip(np.dot(v[i], v[j]), -1, 1))) for i in range(len(v)) for j in range(i + 1, len(v)))
        if w < min_winkel: continue
        res.append((X, float(np.median(e)), float(e.max()), len(obs), float(w)))
    return res

class UF:
    def __init__(s): s.p = {}
    def f(s, x):
        s.p.setdefault(x, x)
        while s.p[x] != x: s.p[x] = s.p[s.p[x]]; x = s.p[x]
        return x
    def u(s, a, b): s.p[s.f(a)] = s.f(b)

def tri(a):
    from scipy.spatial import cKDTree
    from matplotlib.path import Path
    kam = json.load(open(os.path.join(a.objekt, 'sfm/dicht_alle/kameras_unverzerrt.json'))); an = json.load(open(os.path.join(a.objekt, 'anker3d.json')))['anker']
    D = np.load(os.path.join(a.arbeit, 'merkmale.npz')); names = [str(n) for n in D['namen']]
    Ks, Rs, ts = zip(*[kamera(kam[n]) for n in names]); Ks, Rs, ts = list(Ks), list(Rs), list(ts)
    foot = Path([an[f'ecke_boden_{i}']['xyz'][:2] for i in range(4)]); dense = np.load(os.path.join(a.objekt, 'sfm/dicht_alle_modell.npy')); tree = cKDTree(dense)
    sp = np.load(os.path.join(a.arbeit, 'sparse_punkte.npz'))['xyz']; zt = max(an[f'ecke_wandoben_{i}']['xyz'][2] for i in range(4)); first = 21.6
    varn = [k.split('_', 2)[2] for k in D.files if k.startswith('xy_' + names[0] + '_')]
    bed = {v: [v] for v in varn}; bed['UNION_alle'] = varn
    bed['UNION_ohne_kontrolle'] = [v for v in varn if v not in KONTROLLE]
    bed['UNION_orig+gam05+clahe3+lokal'] = ['orig', 'gam05', 'clahe3', 'lokal']
    Fm = {(i, j): fund(kam[names[i]], kam[names[j]]) for i in range(len(names)) for j in range(i + 1, len(names))}
    nur = os.environ.get('BS2_NUR'); erg = []; ptsout = {}
    for bn, vl in bed.items():
        if nur and bn not in nur.split(','): continue
        t0 = time.time(); kp = []; de = []; tag = []
        for n in names:
            xs = []; ds = []; tg = []
            for vi, v in enumerate(vl):
                c_ = int(os.environ.get('BS2_CAP', 8000)); xs.append(D[f'xy_{n}_{v}'][:c_]); ds.append(D[f'de_{n}_{v}'][:c_].astype(np.float32)); tg.append(np.full(len(xs[-1]), vi))   # nach Antwort sortiert (Top-N)
            xy = np.vstack(xs); dd = np.vstack(ds); tg = np.concatenate(tg)
            if len(vl) > 1:   # Duplikate (< 1 px, spaetere Variante) weg
                key = np.round(xy).astype(int); _, first_i = np.unique(key[:, 0] * 100000 + key[:, 1], return_index=True); o = np.sort(first_i); xy, dd, tg = xy[o], dd[o], tg[o]
            kp.append(xy); de.append(dd); tag.append(tg)
        uf = UF(); n_m = n_e = 0; paare = 0
        for (i, j), F in Fm.items():
            m = match_gpu(de[i], de[j]); n_m += len(m)
            if len(m) == 0: continue
            x1 = kp[i][m[:, 0]] + 0.5; x2 = kp[j][m[:, 1]] + 0.5; ok = epi_dist(F, x1, x2) < 1.5; m = m[ok]; n_e += len(m)
            for p, q in m: uf.u((i, int(p)), (j, int(q)))
        groups = {}
        for x in list(uf.p): groups.setdefault(uf.f(x), []).append(x)
        tracks = []
        for g in groups.values():
            imgs = [i for i, _ in g]
            if len(g) < 2 or len(set(imgs)) != len(imgs): continue       # Track mit zwei Merkmalen im selben Bild = mehrdeutig, verworfen
            tracks.append([(i, kp[i][k] + 0.5) for i, k in g])
        pts = triangulieren(None, Ks, Rs, ts, names, tracks)
        X = np.array([p[0] for p in pts]).reshape(-1, 3); med = np.array([p[1] for p in pts]); mx = np.array([p[2] for p in pts]); nob = np.array([p[3] for p in pts]); wi = np.array([p[4] for p in pts])
        dnn = tree.query(X)[0] if len(X) else np.zeros(0)
        inf = foot.contains_points(X[:, :2], radius=-1.5) if len(X) else np.zeros(0, bool)     # innerhalb Grundriss (Wandpunkte liegen auf dem Rand: Puffer 1.5 m nach aussen)
        env = foot.contains_points(X[:, :2], radius=1.5) if len(X) else np.zeros(0, bool)
        # 3D-Baender: aussen = ausserhalb Huelle (Nachbarn/Platz); boden z<4, fassade 4-9 (nur Huelle), dach 9-14 und giebel >14 (nur innerhalb Grundriss, z<=First+0.5)
        band = {'aussen': ~env, 'boden': env & (X[:, 2] < 4), 'fassade': env & (X[:, 2] >= 4) & (X[:, 2] < 9), 'dach': env & (X[:, 2] >= 9) & (X[:, 2] < 14), 'giebel': env & (X[:, 2] >= 14) & (X[:, 2] <= first + 0.5)}
        # Abstand zum Anker: zu den LoD2-Grundrisskanten (2D, Wandlage) fuer boden/fassade; Dach/Giebel: Ueberstand ueber LoD2-First
        E = np.array([an[f'ecke_boden_{i}']['xyz'][:2] for i in range(4)])
        def kante(xy):
            d = []
            for i in range(4):
                p, q = E[i], E[(i + 1) % 4]; u = q - p; tt = np.clip(((xy - p) @ u) / (u @ u), 0, 1); d.append(np.linalg.norm(xy - (p + tt[:, None] * u), axis=1))
            return np.min(d, axis=0)
        wd = kante(X[:, :2]) if len(X) else np.zeros(0)
        inroof = band['dach'] | band['giebel']
        def q(v, p): return float(np.percentile(v, p)) if len(v) else None
        r = dict(bedingung=bn + ('' if os.environ.get('BS2_CAP', '8000') == '8000' else '@cap' + os.environ['BS2_CAP']), varianten=vl, kp_gesamt=int(sum(len(k) for k in kp)), matches_ratio=int(n_m), matches_epi=int(n_e), tracks=len(tracks), punkte=int(len(X)),
                                  reproj_med_px=q(med, 50), reproj_p90_px=q(med, 90), obs_med=q(nob, 50), winkel_med=q(wi, 50),
                 alle_dnn_dicht_med_m=q(dnn, 50), alle_dnn_dicht_p90_m=q(dnn, 90), sek=round(time.time() - t0, 1), regionen={})
        for rg, mk in band.items():
            r['regionen'][rg] = dict(punkte=int(mk.sum()), reproj_med_px=q(med[mk], 50), reproj_p90_px=q(med[mk], 90), obs_med=q(nob[mk], 50), dnn_dicht_med_m=q(dnn[mk], 50), dnn_dicht_p90_m=q(dnn[mk], 90),
                                     neu_ab_10cm=int((dnn[mk] > 0.10).sum()), neu_ab_30cm=int((dnn[mk] > 0.30).sum()), neu_ab_100cm=int((dnn[mk] > 1.0).sum()),
                                     wandabstand_med_m=q(wd[mk & (wd < 1.5)], 50) if rg in ('boden', 'fassade') else None,
                                     ueber_first_anteil=float((X[mk, 2] > first).mean()) if rg == 'giebel' and mk.any() else None)
        erg.append(r); print(json.dumps(r), flush=True)
        np.save(os.path.join(a.arbeit, f"punkte_{r['bedingung']}.npy"), X)
    f = os.path.join(a.arbeit, 'tri_ergebnis.json'); alt = json.load(open(f)) if os.path.exists(f) and nur else []
    json.dump([x for x in alt if x['bedingung'] not in [e['bedingung'] for e in erg]] + erg, open(f, 'w'), indent=1)

if __name__ == '__main__':
    a = args(); os.makedirs(a.arbeit, exist_ok=True)
    globals()[a.stufe](a)
