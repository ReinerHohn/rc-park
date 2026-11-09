#!/usr/bin/env python3
"""kamera_linienfein.py - VERSUCH Linien-Feinlage: Pose je Foto (6 DoF, f/k1 fest) gegen die Kantengitter-v12-Segmente (3D) ausgleichen.
Kosten: Tukey-robuster Abstand der projizierten Segment-Stuetzpunkte zur naechsten Fotokante (Distanztransformation der Canny-Kanten). GPU (PyTorch).
Liest NUR: kam_lot2.json, segmente_gitter_v12.json, Fotos (bilder_alle). Kein STL/Netz/objekt.json.
OFFENER PUNKT Z2: segmente_gitter_v12.json speichert KEINE tragenden Fotos je Segment -> Eigenbezug nicht ausschliessbar -> Ergebnis nie uebernehmbar.
Modi: --synth (Rueckholung bekannter Stoerung), --halb (Halbierung raeumlich getrennter Bloecke).
  /media/oem/scan/venv-seg/bin/python -I tools/kamera_linienfein.py --synth|--halb [--n 20]"""
import sys, os, json, argparse, numpy as np, cv2, torch

D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"; SCR = D + "/agent_scratch_kam"; BILD = D + "/bilder_alle"
dev = "cuda"
DS = 4        # Verkleinerung fuer DT


def kante_dt(name):
    pf = f"{SCR}/dt_{name}.npy"
    if os.path.exists(pf): return np.load(pf)
    im = cv2.imread(f"{BILD}/{name}", cv2.IMREAD_GRAYSCALE); im = cv2.resize(im, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA); im = cv2.GaussianBlur(im, (0, 0), 1.2)
    med = float(np.median(im)); e = cv2.Canny(im, 0.66 * med, 1.33 * med)
    dt = cv2.distanceTransform((e == 0).astype(np.uint8), cv2.DIST_L2, 3) * 2.0                 # in Pixeln des Originals
    dt = cv2.resize(dt, (dt.shape[1] // 2, dt.shape[0] // 2), interpolation=cv2.INTER_AREA).astype(np.float16)   # 1/4
    np.save(pf, dt); return dt


def segment_punkte(pfad=D + "/segmente_gitter_v12.json", schritt=0.12, minlen=0.4, klasse=None):
    S = json.load(open(pfad))["segmente"]; P = []; sid = []; mid = []
    for k, s in enumerate(S):
        a = np.array(s[0]); b = np.array(s[1]); L = np.linalg.norm(b - a)
        if L < minlen or (klasse == 'nonzero' and s[2] == 0) or (klasse == 'zero' and s[2] != 0): continue
        n = max(2, int(L / schritt)); t = np.linspace(0, 1, n)[:, None]; P.append(a + t * (b - a)); sid += [k] * n; mid.append((k, (a + b) / 2))
    return np.vstack(P), np.array(sid), dict(mid)


def pose(k):
    return torch.tensor(k["Rn"], dtype=torch.float64, device=dev), torch.tensor(k["tn"], dtype=torch.float64, device=dev)


def rodr(w):
    th = w.norm() + 1e-12; k = w / th; K = torch.zeros(3, 3, dtype=w.dtype, device=w.device); K[0, 1], K[0, 2], K[1, 0], K[1, 2], K[2, 0], K[2, 1] = -k[2], k[1], k[2], -k[0], -k[1], k[0]
    return torch.eye(3, dtype=w.dtype, device=w.device) + torch.sin(th) * K + (1 - torch.cos(th)) * K @ K


def projiziere(R, t, kam, X):
    Xc = X @ R.T + t; z = Xc[:, 2]; u = Xc[:, :2] / z[:, None].clamp(min=1e-3); k1 = kam["params"][3] if len(kam["params"]) > 3 else 0.0
    d = u * (1 + k1 * (u * u).sum(1)[:, None])
    return kam["f"] * d + torch.tensor([kam["cx"], kam["cy"]], dtype=d.dtype, device=d.device), z


def tukey(r, c):
    m = (r < c).to(r.dtype); return (c * c / 6) * (1 - (1 - (r / c) ** 2) ** 3) * m + (c * c / 6) * (1 - m)


def kosten(R, t, kam, X, dt, c, maske=None):
    uv, z = projiziere(R, t, kam, X); H, W = dt.shape[2] * DS, dt.shape[3] * DS
    ok = (z > 2) & (z < 60) & (uv[:, 0] > 0) & (uv[:, 0] < W) & (uv[:, 1] > 0) & (uv[:, 1] < H)
    if maske is not None: ok = ok & maske
    if ok.sum() < 200: return None, int(ok.sum())
    g = torch.stack([uv[ok, 0] / W * 2 - 1, uv[ok, 1] / H * 2 - 1], 1).float()[None, None]
    r = torch.nn.functional.grid_sample(dt, g, align_corners=False, padding_mode="border")[0, 0, 0].double()
    return tukey(r, c).mean(), int(ok.sum())


def ausgleich(kam, X, dt, maske=None, schritte=(60, 60, 60), stufen=(24.0, 12.0, 6.0)):
    R0, t0 = pose(kam); w = torch.zeros(3, dtype=torch.float64, device=dev, requires_grad=True); dtv = torch.zeros(3, dtype=torch.float64, device=dev, requires_grad=True)
    for n, c in zip(schritte, stufen):
        opt = torch.optim.Adam([{"params": [w], "lr": 0.002}, {"params": [dtv], "lr": 0.01}])
        for _ in range(n):
            opt.zero_grad(); Rd = rodr(w); R = Rd @ R0; t = Rd @ t0 + dtv; k, nn = kosten(R, t, kam, X, dt, c, maske)
            if k is None: return None
            k.backward(); opt.step()
    with torch.no_grad(): Rd = rodr(w); R = Rd @ R0; t = Rd @ t0 + dtv; k, nn = kosten(R, t, kam, X, dt, 6.0, maske)
    return R.detach(), t.detach(), float(k)


def flaechenfehler_m(kamA, RB, tB, tief, n=5):
    """Mittlerer Versatz (m) auf einer Flaeche im Abstand tief: Bildgitter-Strahlen mit Pose A -> Punkte -> Pose B."""
    RA, tA = pose(kamA); f = kamA["f"]; W, H = kamA["W"], kamA["H"]
    gx, gy = torch.meshgrid(torch.linspace(.15, .85, n, dtype=torch.float64) * W, torch.linspace(.15, .85, n, dtype=torch.float64) * H, indexing="xy")
    uv = torch.stack([gx.ravel(), gy.ravel()], 1).to(dev); u = (uv - torch.tensor([kamA["cx"], kamA["cy"]], dtype=torch.float64, device=dev)) / f
    Xc = torch.cat([u, torch.ones(len(u), 1, dtype=torch.float64, device=dev)], 1) * tief; Xw = (Xc - tA) @ RA
    pb, _ = projiziere(RB, tB, kamA, Xw); pa, _ = projiziere(RA, tA, kamA, Xw)
    return float((pb - pa).norm(dim=1).mean() * tief / f)


def stoere(kam, dm, dg, rng):
    R, t = pose(kam); C = -R.T @ t; v = rng.normal(size=3); v /= np.linalg.norm(v); ax = rng.normal(size=3); ax /= np.linalg.norm(ax)
    Rd = rodr(torch.tensor(ax * np.radians(dg), dtype=torch.float64, device=dev)); Rn = Rd @ R; Cn = C + torch.tensor(v * dm, dtype=torch.float64, device=dev); return Rn, -Rn @ Cn


def tiefe_median(kam, X):
    R, t = pose(kam); uv, z = projiziere(R, t, kam, X); ok = (z > 2) & (uv[:, 0] > 0) & (uv[:, 0] < kam["W"]) & (uv[:, 1] > 0) & (uv[:, 1] < kam["H"])
    return float(z[ok].median()) if ok.sum() > 200 else None


KLASSE = None


def laden(n_foto, seed):
    kam = json.load(open(D + "/sfm/kam_lot2.json")); P, sid, mid = segment_punkte(klasse=KLASSE); X = torch.tensor(P, dtype=torch.float64, device=dev)
    rng = np.random.default_rng(seed); namen = list(kam); rng.shuffle(namen); return kam, X, sid, mid, namen, rng


def synth(n_foto, seed=1):
    kam, X, sid, mid, namen, rng = laden(n_foto, seed); zeilen = []
    for name in namen:
        if len(zeilen) >= n_foto * 3: break
        k = kam[name]; z = tiefe_median(k, X)
        if z is None: continue
        dt = torch.tensor(kante_dt(name).astype(np.float32), device=dev)[None, None]
        for dm, dg in ((0.1, 0.3), (0.05, 0.15), (0.3, 0.5)):
            Rn, tn = stoere(k, dm, dg, rng); k2 = dict(k); k2["Rn"] = Rn.cpu().numpy().tolist(); k2["tn"] = tn.cpu().numpy().tolist()
            f0 = flaechenfehler_m(k, Rn, tn, z); res = ausgleich(k2, X, dt)
            if res is None: continue
            R1, t1, kost = res; f1 = flaechenfehler_m(k, R1, t1, z)
            # Kosten an Wahrheit zum Vergleich
            R0, t0 = pose(k); kw, _ = kosten(R0, t0, k, X, dt, 6.0); ks, _ = kosten(Rn, tn, k, X, dt, 6.0)
            zeilen.append(dict(foto=name, dm=dm, dg=dg, tiefe_m=round(z, 1), fehler_vorher_m=round(f0, 4), fehler_nachher_m=round(f1, 4), verhaeltnis=round(f1 / f0, 3), kosten_wahrheit=round(float(kw), 3), kosten_start=round(float(ks), 3), kosten_ende=round(kost, 3)))
            print(zeilen[-1], flush=True)
    return zeilen


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--synth", action="store_true"); ap.add_argument("--n", type=int, default=12); ap.add_argument("--aus", default=SCR + "/linienfein_synth.json"); ap.add_argument("--klasse"); ap.add_argument("--real", action="store_true"); a = ap.parse_args(); KLASSE = a.klasse
    if a.synth:
        z = synth(a.n); json.dump(z, open(a.aus, "w"), indent=0)
        for st in sorted({(r["dm"], r["dg"]) for r in z}):
            rr = [r for r in z if (r["dm"], r["dg"]) == st]; v = np.array([r["verhaeltnis"] for r in rr])
            print(st, "n", len(rr), "Verhaeltnis nachher/vorher med", np.median(v).round(2), "Anteil <=0.3:", (v <= .3).mean().round(2), "Anteil >1:", (v > 1).mean().round(2),
                  "Kosten Wahrheit<Ende:", np.mean([r["kosten_wahrheit"] < r["kosten_ende"] for r in rr]).round(2))


def real(n_foto, seed=2, aus=D + "/sfm/kam_lot2_linienfein.json"):
    """Echte Fotos: (b) Halbierung in raeumlich getrennte Bloecke (3-m-Zellen, Schachbrett), (c) Holdout gegen SfM-Punkte. Vorschlag nur, bestanden=False wegen Z2 (Segment-Herkunft unbekannt)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from kamera_guete_lot2 import Szene, aehnlichkeit
    Sz = Szene(); ids = list(Sz.im); s, Rr, tr = aehnlichkeit(np.array([Sz.im[i]["C"] for i in ids]), np.array([Sz.kam[Sz.im[i]["name"]]["C"] for i in ids]))
    kam, X, sid, mid, namen, rng = laden(n_foto, seed); Xn = X.cpu().numpy(); par = ((np.floor(Xn / 3.0).astype(int)).sum(1) % 2) == 0; mA = torch.tensor(par, device=dev); mB = ~mA
    vor = {}; zeilen = []
    for name in namen:
        if len(zeilen) >= n_foto: break
        k = kam[name]
        if tiefe_median(k, X) is None: continue
        dt = torch.tensor(kante_dt(name).astype(np.float32), device=dev)[None, None]; R0, t0 = pose(k)
        rA = ausgleich(k, X, dt, mA); rB = ausgleich(k, X, dt, mB); rG = ausgleich(k, X, dt)
        if rA is None or rB is None or rG is None: continue
        kB0, _ = kosten(R0, t0, k, X, dt, 6.0, mB); kB1, _ = kosten(rA[0], rA[1], k, X, dt, 6.0, mB); kA0, _ = kosten(R0, t0, k, X, dt, 6.0, mA); kA1, _ = kosten(rB[0], rB[1], k, X, dt, 6.0, mA)
        z = tiefe_median(k, X); shift = flaechenfehler_m(k, rG[0], rG[1], z)
        # Holdout SfM-Punkte: Reprojektion (px, Median) alte vs neue Pose
        iid = Sz.name2id[name]; v = Sz.im[iid]; m = v["pid"] >= 0; Pp = np.array([Sz.pts[p][0] for p in v["pid"][m]]); Pw = s * Pp @ Rr.T + tr; xy = v["xy"][m]
        def rep(R, t):
            Xc = Pw @ R.T + t; u = Xc[:, :2] / Xc[:, 2:3]; k1 = k["params"][3]; px = k["f"] * u * (1 + k1 * (u * u).sum(1)[:, None]) + [k["cx"], k["cy"]]; return float(np.median(np.linalg.norm(px - xy, axis=1)))
        r_alt = rep(R0.cpu().numpy(), t0.cpu().numpy()); r_neu = rep(rG[0].cpu().numpy(), rG[1].cpu().numpy())
        ok_halb = bool(float(kB1) < float(kB0) and float(kA1) < float(kA0)); ok_hold = r_neu <= r_alt * 1.0
        zeilen.append(dict(foto=name, tiefe_m=round(z, 1), verschiebung_m=round(shift, 4), kontrolle_B_vorher=round(float(kB0), 3), kontrolle_B_nachher=round(float(kB1), 3), kontrolle_A_vorher=round(float(kA0), 3), kontrolle_A_nachher=round(float(kA1), 3),
                           halbierung_besser=ok_halb, reproj_alt_px=round(r_alt, 3), reproj_neu_px=round(r_neu, 3), holdout_ok=ok_hold, bestanden=False,
                           grund="Z2 offen: Gittersegmente ohne Foto-Herkunft; Uebernahme untersagt" if (ok_halb and ok_hold) else "Halbierung/Holdout nicht bestanden"))
        vor[name] = dict(k, Rn=rG[0].cpu().numpy().tolist(), tn=rG[1].cpu().numpy().tolist(), C=(-rG[0].T @ rG[1]).cpu().numpy().tolist(), linienfein=zeilen[-1])
        print(zeilen[-1], flush=True)
    json.dump(vor, open(aus, "w")); json.dump(zeilen, open(SCR + "/linienfein_real.json", "w"), indent=0)
    print("Halbierung beide besser:", sum(r["halbierung_besser"] for r in zeilen), "/", len(zeilen), "| Holdout ok:", sum(r["holdout_ok"] for r in zeilen), "| beide:", sum(r["halbierung_besser"] and r["holdout_ok"] for r in zeilen))
    print("Verschiebung m med", np.median([r["verschiebung_m"] for r in zeilen]).round(3))


if __name__ == "__main__" and a.__dict__.get("real"):
    real(a.n)
