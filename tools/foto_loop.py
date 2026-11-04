#!/usr/bin/env python3
"""foto_loop.py - iterierende, selbstverbessernde Foto-Schleife (Analyse durch Synthese, GPU; Register BW, PIPELINE_H0.md Abschnitt 8).

Modell (Generator-STL) wird mit je einer eigenen Kamera pro Foto gegen die Himmelsmaske der Fotos verglichen. Abwechselnd:
  A. Kamera je Foto verfeinern (CEM ab der letzten Kamera) - Modell fest;
  B. Modellparameter (Tuermchen-Kegel: Achse nach aussen dx/dy, Hoehenmassstab hs, Radialmassstab rs) per Koordinatensuche verbessern - Kameras fest.
Ein Schritt wird NUR uebernommen, wenn (1) das mittlere IoU ueber alle Fotos um > eps steigt UND (2) die Mehrheit (>= --mehrheit) der Fotos nicht schlechter wird
(Gleichrichtung statt Mittelwert: ein Foto kann sich nicht allein die Form verbiegen). Schrittweiten halbieren sich, wenn nichts mehr geht; Abbruch bei Konvergenz.
Fotos mit Start-IoU < --min-iou (Kamera nicht auffindbar) entfallen. Ergebnis: audit/foto_loop/foto_loop.json (je Runde Parameter, IoU je Foto, uebernommen/verworfen),
Ueberlagerungsbilder start/ende, VORSCHLAG fuer Generator-Masse (wird NICHT automatisch geschrieben: masse.json nur mit Quelle+historie und bauen_abnehmen.sh).
Nur ein GPU-Job zur Zeit: wartet, bis der GPU-Speicher < 1500 MiB belegt ist.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_loop.py [--fotos 031 042 ...] [--runden 8] [--objekt modelle/martinstor]
"""
import sys, os, json, time, math, argparse, subprocess, numpy as np, cv2, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_silhouette_gpu as F, foto_profil_gpu as PG, foto_dach_gemeinsam as G
dev = "cuda"

def gpu_warten(max_mib=1500, max_s=3600):
    t0 = time.time()
    while time.time() - t0 < max_s:
        try: used = int(subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).decode().split()[0])
        except Exception: return
        if used < max_mib: return
        time.sleep(20)

PARAM = ["dx", "dy", "hs", "rs"]; START = dict(dx=0.0, dy=0.0, hs=1.0, rs=1.0); SCHRITT = dict(dx=0.4, dy=0.4, hs=0.08, rs=0.08)
Z0 = 37.0

def modell(P0, mask, q):
    """Tuermchen-Punkte (mask): Achse (sx*4,sy*4,4) nach aussen verschieben, Kegel in z um Z0 und radial um die Achse skalieren."""
    P = P0.clone(); Q = P0[mask]; sx = torch.sign(Q[:, 0]); sy = torch.sign(Q[:, 1])
    ax = sx * 4.0; ay = sy * 4.4
    x = ax + (Q[:, 0] - ax) * q["rs"] + sx * q["dx"]; y = ay + (Q[:, 1] - ay) * q["rs"] + sy * q["dy"]; z = Z0 + (Q[:, 2] - Z0) * q["hs"]
    P[mask] = torch.stack([x, y, z], 1); return P

def iou_je_foto(P, ph):
    out = []
    for nr, d in ph.items():
        s, iou = F.score(P, d["th"][None], d["T"], d["roi"], d["f0"], d["W"], d["H"]); out.append(float(iou[0]))
    return np.array(out)

def kameras_verfeinern(P, ph, iters=30):
    for nr, d in ph.items():
        PG.lo, PG.hi = G.grenzen(d["seite"]); sd = (PG.hi - PG.lo) * 0.01
        s, th = PG.cem(P, d["T"], d["roi"], d["H"], d["W"], d["f0"], d["th"].clone(), sd, iters, seed=0); d["th"] = th.detach().clone() if torch.is_tensor(th) else torch.tensor(th, device=dev)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fotos", nargs="*"); ap.add_argument("--runden", type=int, default=8); ap.add_argument("--min-iou", type=float, default=0.75)
    ap.add_argument("--eps", type=float, default=0.002); ap.add_argument("--mehrheit", type=float, default=0.6); ap.add_argument("--objekt", default="modelle/martinstor"); ap.add_argument("--max-fotos", type=int, default=12)
    a = ap.parse_args(); gpu_warten()
    obj = json.load(open(os.path.join(a.objekt, "objekt.json"))); nrs = a.fotos or [n for n, v in obj["fotos"].items() if v.get("silhouette_frei") and v.get("seite") in ("Nord", "Sued", "Ost", "West")][:a.max_fotos]
    out = os.path.join(a.objekt, "audit", "foto_loop"); os.makedirs(out, exist_ok=True); log = dict(start=time.strftime("%Y-%m-%d %H:%M"), fotos=[], runden=[])
    P0, _ = F.load_points(200000); mask = (P0[:, 2] > 36.5) & (P0[:, 0].abs() > 2.8) & (P0[:, 1].abs() > 2.8); print("Tuermchenpunkte", int(mask.sum()), "von", len(P0), flush=True)
    ph = {}
    for nr in nrs:
        try: im, N, roi = G.load(nr)
        except Exception as e: print(nr, "laedt nicht:", e); continue
        H, W = N.shape; T = torch.as_tensor(N, device=dev); seite = obj["fotos"][nr].get("seite")
        (s, th), f0 = G.fit(P0, T, roi, H, W, seite=seite); th = th.detach().clone() if torch.is_tensor(th) else torch.tensor(th, device=dev)
        print(f"Foto {nr} ({seite}) Start-IoU {float(s):.3f}", flush=True)
        if float(s) < a.min_iou: print("   entfaellt (Kamera nicht auffindbar)"); continue
        ph[nr] = dict(T=T, roi=tuple(roi), H=H, W=W, f0=f0, th=th, seite=seite, im=im)
    if len(ph) < 3: sys.exit("zu wenige brauchbare Fotos (< 3)")
    log["fotos"] = list(ph); q = dict(START); st = dict(SCHRITT); P = modell(P0, mask, q); base = iou_je_foto(P, ph); print("Start mittleres IoU", round(float(base.mean()), 4), flush=True)
    for nr, d in ph.items(): G.overlay(d["im"], P0, d["th"], d["f0"], d["W"], d["H"], d["roi"], f"{out}/start_{nr}.png")
    for r in range(a.runden):
        kameras_verfeinern(P, ph); cur = iou_je_foto(P, ph); acc = []
        for k in PARAM:
            best = None
            for sg in (+1, -1):
                q2 = dict(q); q2[k] = q[k] + sg * st[k]
                if k in ("hs", "rs") and not (0.5 < q2[k] < 1.6): continue
                new = iou_je_foto(modell(P0, mask, q2), ph); gain = float(new.mean() - cur.mean()); mehrh = float((new >= cur - 0.003).mean())
                if gain > a.eps and mehrh >= a.mehrheit and (best is None or gain > best[0]): best = (gain, q2, new, mehrh)
            if best: q = best[1]; cur = best[2]; acc.append(dict(param=k, neu=round(q[k], 3), gewinn=round(best[0], 4), gleichgerichtet=round(best[3], 2)))
        P = modell(P0, mask, q); cur = iou_je_foto(P, ph)
        log["runden"].append(dict(runde=r, schritt=dict(st), parameter={k: round(v, 3) for k, v in q.items()}, iou_mittel=round(float(cur.mean()), 4), iou={n: round(float(v), 3) for n, v in zip(ph, cur)}, uebernommen=acc))
        print(f"Runde {r}: IoU {cur.mean():.4f} Parameter {({k: round(v, 3) for k, v in q.items()})} uebernommen {[x['param'] for x in acc]}", flush=True)
        json.dump(log, open(f"{out}/foto_loop.json", "w"), indent=1, ensure_ascii=False)
        if not acc:
            st = {k: v / 2 for k, v in st.items()}
            if st["dx"] < 0.05: print("Konvergenz (kleinste Schrittweite ohne Verbesserung)"); break
    for nr, d in ph.items(): G.overlay(d["im"], P, d["th"], d["f0"], d["W"], d["H"], d["roi"], f"{out}/ende_{nr}.png")
    e = iou_je_foto(P, ph)
    log["ergebnis"] = dict(iou_start=round(float(base.mean()), 4), iou_ende=round(float(e.mean()), 4), parameter={k: round(v, 3) for k, v in q.items()}, je_foto={n: [round(float(b), 3), round(float(c), 3)] for n, b, c in zip(ph, base, e)},
        vorschlag=dict(hinweis="NICHT automatisch geschrieben. TUERM_ACHSE_DX = 0,5 - dx, TUERM_ACHSE_DY = 0,6 - dy (Achse nach aussen); Kegelhoehe ueber Z0=37 m mit hs, Radius mit rs skalieren; nur mit Quelle+historie, dann bauen_abnehmen.sh", dx_m=round(q["dx"], 3), dy_m=round(q["dy"], 3), hs=round(q["hs"], 3), rs=round(q["rs"], 3)))
    json.dump(log, open(f"{out}/foto_loop.json", "w"), indent=1, ensure_ascii=False); print(json.dumps(log["ergebnis"], ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
