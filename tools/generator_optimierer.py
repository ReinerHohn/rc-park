#!/usr/bin/env python3
"""generator_optimierer.py - Kann der Martinstor-Generator noch besser werden? Oder ist er am Boden?  (GPU, wiederholbar)

Koordinatensuche ueber 16 Masse des Generators, bewertet gegen das amtliche LiDAR-DOM (hypso_gpu.py).
Eine Aenderung wird NUR uebernommen, wenn sie ROBUST besser ist:
  (1) Trainingsfehler (13 Stufen, feines Raster) um mehr als 2 sigma kleiner     [sigma: Bootstrap der Raster-Suche]
  (2) zurueckgehaltene Stufen (12 andere, an der Lage der Trainingsstufen)        nicht signifikant schlechter
  (3) punktweise Hoehe im 4,5-m-Umkreis der Spitze                                nicht schlechter als +0,15 m
Vertrauensbereich: +-2 Schritte um die Startwerte. Mehrfachstart (--multistart K): K zufaellige Startpunkte, feste Seeds.
Alles deterministisch (GPU-Scatter-Max ist ordnungsunabhaengig); Protokoll mit Versionen in modelle/optimierung_martinstor.json.

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/generator_optimierer.py [--multistart 4] [--runden 4] [--cpu]
"""
import os, re, sys, json, time, subprocess
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT + "/tools")
import hypso_gpu as H
GEN = ROOT + "/modelle/martinstor_v4_gen.py"; TMP = "/media/oem/scan/tmp/opt"; os.makedirs(TMP, exist_ok=True)
GPU = "--cpu" not in sys.argv

BASE = dict(DB=9.8, WB=11.3, D=9.3, W=10.3, ZZ=30.5, gx=4.0, gy=4.3, bh=5.0, rh=10.7, ov=1.5, tx=1.3, ty=3.0,
            TWs=2.6, T0=30.0, T1=32.7, OR=1.3)
STEP = dict(DB=.3, WB=.3, D=.3, W=.3, ZZ=.5, gx=.4, gy=.4, bh=.5, rh=.6, ov=.5, tx=.4, ty=.4, TWs=.3, T0=.5, T1=.5, OR=.15)
LO = {k: BASE[k] - 2 * STEP[k] for k in BASE}; HI = {k: BASE[k] + 2 * STEP[k] for k in BASE}
C = H.combos(H.ANG, H.PH); WIN = np.hypot(H.YY - H.PR[0], H.XX - H.PR[1]) <= 4.5
R0 = H.ref_areas(H.TS0, 9); R1 = H.ref_areas(H.TS1, 9)

def source(v):
    s = open(GEN).read()
    def sub(a, b):
        nonlocal s
        assert a in s, a
        s = s.replace(a, b, 1)
    sub("DB, WB, ZB = 9.8, 11.3, 6.2", f"DB, WB, ZB = {v['DB']:.3f}, {v['WB']:.3f}, 6.2")
    sub("D, W = 9.3, 10.3", f"D, W = {v['D']:.3f}, {v['W']:.3f}")
    sub("\nZZ = 30.5", f"\nZZ = {v['ZZ']:.3f}")
    sub("GX, GY, GZ0, GZ1 = D - 4.0, W - 4.3, ZZ + 2.0, ZZ + 5.0", f"GX, GY, GZ0, GZ1 = D - {v['gx']:.3f}, W - {v['gy']:.3f}, ZZ + 2.0, ZZ + {v['bh']:.3f}")
    sub("RZ0, RZ1 = GZ1, GZ1 + 10.7", f"RZ0, RZ1 = GZ1, GZ1 + {v['rh']:.3f}")
    sub("GX + 1.5, GY + 1.5, RZ1, 1.3, 3.0", f"GX + {v['ov']:.3f}, GY + {v['ov']:.3f}, RZ1, {v['tx']:.3f}, {v['ty']:.3f}")
    sub("TWs, T0, T1 = 2.6, 30.0, 32.7", f"TWs, T0, T1 = {v['TWs']:.3f}, {v['T0']:.3f}, {v['T1']:.3f}")
    sub("OR = 1.3 ", f"OR = {v['OR']:.3f} ")
    return re.sub(r"^OUT = .*\n.*\n", f"OUT = '{TMP}/cur.stl'\n", s, count=1, flags=re.M)

def build(v, name=None):
    name = name or f"cur{os.getpid()}"  # eindeutig je Prozess: parallele Laeufe teilten sich frueher cur.stl (Wettlauf)
    src = f"{TMP}/{name}_gen.py"; s = source(v).replace(f"{TMP}/cur.stl", f"{TMP}/{name}.stl"); open(src, "w").write(s)
    r = subprocess.run([os.path.expanduser("~/.venvs/rcpark/bin/python"), src], capture_output=True, text=True, env=dict(os.environ, SCALE="87", MINMM="0.8"))
    if r.returncode: raise RuntimeError(r.stderr[-400:])
    return f"{TMP}/{name}.stl"

def evaluate(v, boot=False):
    try: P = H.punkte(build(v))
    except (ValueError, RuntimeError): return None          # ungueltiges Modell (nicht wasserdicht / Generatorfehler)
    if GPU:
        import torch
        Ht = H.hmaps_gpu_t(P, C, zmin=19.0)                  # exakt: alle Stufen > 20 m, Punkte <= 19 m aendern keine Zelle
        e0 = H.fehler_gpu(Ht, H.TS0, 9, R0).abs().mean(1); k = int(e0.argmin())      # Lage nach Trainingsstufen
        eho = float(H.fehler_gpu(Ht[k:k + 1], H.TS1, 9, R1)[0].abs().mean())
        d0k = H.fehler_gpu(Ht[k:k + 1], H.TS0, 9, R0)[0].cpu().numpy()
        h1 = H.fehler_gpu(Ht, H.TS1, 9, R1).abs().mean(1).cpu().numpy() if boot else None
        e0 = e0.cpu().numpy(); top = np.argsort(e0, kind="stable")[:48]                 # punktweise: volle Punktzahl, beste 48 Lagen
        Hf = H.hmaps_gpu_t(P, C[top]); ept = float((Hf - torch.as_tensor(H.REF, device="cuda")[None]).abs()[:, WIN].mean(1).min())
    else:
        Pc = P[P[:, 2] > 19.0]; Hm = H.hmaps_cpu(Pc, C)
        d0 = H.fehler(Hm, H.TS0, 9, R0); e0 = np.abs(d0).mean(1); k = int(np.argmin(e0)); d0k = d0[k]
        eho = float(np.abs(H.fehler(Hm[k:k + 1], H.TS1, 9, R1)[0]).mean()); top = np.argsort(e0, kind="stable")[:48]
        Hf = H.hmaps_cpu(P, C[top]); ept = float(np.abs(Hf - H.REF[None])[:, WIN].mean(1).min())
        h1 = np.abs(H.fehler(Hm, H.TS1, 9, R1)).mean(1) if boot else None
    r = dict(e=float(e0[k]), med=float(np.median(np.abs(d0k))), eho=eho, ept=ept, kombi=C[k].tolist(), top=float(P[:, 2].max()))
    if boot:
        rng = np.random.default_rng(0); r["sigma"] = float(np.std([e0[rng.random(len(e0)) < .5].min() for _ in range(60)], ddof=1))
        r["sigma_ho"] = float(np.std([h1[rng.random(len(h1)) < .5].min() for _ in range(60)], ddof=1))
    return r

def robust_besser(r, cur, sig, sig_ho):
    return (cur["e"] - r["e"] > 2 * sig) and (r["eho"] - cur["eho"] < sig_ho) and (r["ept"] - cur["ept"] < 0.15)

def descend(start, cur_r, sig, sig_ho, runden, log, tag):
    cur = dict(start); rc = cur_r
    for rd in range(1, runden + 1):
        improved = False
        for k, st in STEP.items():
            best = None
            for sgn in (-1, 1):
                v = dict(cur); v[k] = round(v[k] + sgn * st, 3)
                if not (LO[k] - 1e-9 <= v[k] <= HI[k] + 1e-9): continue
                r = evaluate(v)
                if r is None: log.append(dict(tag=tag, runde=rd, param=k, wert=v[k], ungueltig=True)); continue
                log.append(dict(tag=tag, runde=rd, param=k, wert=v[k], **{x: r[x] for x in ("e", "eho", "ept", "med")}))
                if robust_besser(r, rc, sig, sig_ho) and (best is None or r["e"] < best[1]["e"]): best = (v, r, sgn)
            if best:
                cur, rc = best[0], best[1]; improved = True
                print(f"  [{tag}] R{rd} {k} -> {cur[k]}  e {rc['e']:.3f} (hold-out {rc['eho']:.3f}, punktweise {rc['ept']:.2f} m)", flush=True)
        if not improved: break
    return cur, rc

def main():
    arg = lambda n, d: int(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
    import torch, platform
    env = dict(torch=torch.__version__, cuda=torch.version.cuda, gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
               numpy=np.__version__, python=platform.python_version(), gpu_genutzt=GPU, kombinationen=len(C),
               git=subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip())
    print("UMGEBUNG", json.dumps(env), flush=True)
    t0 = time.time(); b = evaluate(BASE, boot=True)
    sig, sig_ho = max(b["sigma"], 0.02), max(b["sigma_ho"], 0.02)   # Boden = 1 Zelle auf der obersten Stufe (Zaehlwerte sind ganzzahlig)
    print(f"BASIS e={b['e']:.3f} (hold-out {b['eho']:.3f}, punktweise {b['ept']:.2f} m)  sigma {sig:.4f} / {sig_ho:.4f}  ({time.time()-t0:.0f} s/Auswertung)", flush=True)
    log = []; res = {"umgebung": env, "basis": b, "sigma": sig, "sigma_ho": sig_ho, "laeufe": {}}
    cur, rc = descend(BASE, b, sig, sig_ho, arg("--runden", 4), log, "start0")
    res["laeufe"]["start0"] = dict(params=cur, **{x: rc[x] for x in ("e", "eho", "ept", "med")})
    rng = np.random.default_rng(12345)
    for i in range(arg("--multistart", 0)):
        st = {k: round(float(np.clip(BASE[k] + rng.uniform(-1.5, 1.5) * STEP[k], LO[k], HI[k])), 3) for k in BASE}
        r0 = evaluate(st)
        while r0 is None:
            st = {k: round(float(np.clip(BASE[k] + rng.uniform(-1.5, 1.5) * STEP[k], LO[k], HI[k])), 3) for k in BASE}; r0 = evaluate(st)
        c2, r2 = descend(st, r0, sig, sig_ho, arg("--runden", 4), log, f"start{i+1}")
        res["laeufe"][f"start{i+1}"] = dict(start=st, params=c2, **{x: r2[x] for x in ("e", "eho", "ept", "med")})
        print(f"START {i+1}: e {r0['e']:.3f} -> {r2['e']:.3f}   Ende {json.dumps(c2)}", flush=True)
    # Umgebungsprobe am Ergebnis von start0: jedes Mass +-Schritt und +-halber Schritt -> keiner robust besser?
    probe = []
    for k, st in STEP.items():
        for f in (-1, -.5, .5, 1):
            v = dict(cur); v[k] = round(v[k] + f * st, 3)
            r = evaluate(v)
            if r is None: probe.append(dict(param=k, delta=round(f * st, 3), ungueltig=True, besser=False)); continue
            probe.append(dict(param=k, delta=round(f * st, 3), e=r["e"], eho=r["eho"], ept=r["ept"], besser=bool(robust_besser(r, rc, sig, sig_ho))))
    res["probe"] = probe; res["log"] = log
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "lauf"
    json.dump(res, open(f"{ROOT}/modelle/optimierung_martinstor_{tag}.json", "w"), indent=1, default=float)
    print("ENDE", json.dumps(cur), f"e={rc['e']:.3f} hold-out={rc['eho']:.3f} punktweise={rc['ept']:.2f} m", "Probe: robuste Verbesserungen:", sum(p["besser"] for p in probe), "von", len(probe), flush=True)

if __name__ == "__main__":
    main()
