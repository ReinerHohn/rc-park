#!/usr/bin/env python3
"""rippen_greedy.py - Rippen automatisch auswaehlen: Kandidatenpfade (kanten_ketten/pfad_tiefe_dp) werden EINZELN ins Objekt gebaut und bleiben nur, wenn (1) Abnahme besteht und (2) das feine Rippen-F1 (rippen_f1.py, fester Schlauch = Vereinigung aller Kandidaten + vorhandener Pfade) um mindestens --min_gewinn steigt. Sonst Rueckgabe. Reihenfolge: laengste zuerst.
Aufruf: rippen_greedy.py OBJ.json KANDIDATEN.json --pfad bauteile/10/unterbau/rippen_pfade --box "..." [--u 13 18.5 --z 5.8 8.8] [--min_m 0.6] [--min_gewinn 0.004] [--max_kand 25] [--aus DIR]
Kandidaten: Liste mit pfad_xyz (Welt) und normale_xyz. Ergebnis: OBJ.json mit den behaltenen Pfaden (NICHT committet), DIR/greedy.json (Protokoll je Kandidat: F1 vorher/nachher, Abnahme, Entscheidung)."""
import sys, os, json, subprocess, shutil, re
import numpy as np
a = sys.argv[1:]
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
objp = os.path.abspath(a[0]); C = json.load(open(a[1])); pt = opt("--pfad", "").split("/"); bx = opt("--box", ""); aus = opt("--aus", "."); os.makedirs(aus, exist_ok=True)
ur = [float(v) for v in a[a.index("--u") + 1:a.index("--u") + 3]] if "--u" in a else [-1e9, 1e9]; zr = [float(v) for v in a[a.index("--z") + 1:a.index("--z") + 3]] if "--z" in a else [-1e9, 1e9]
MINM = float(opt("--min_m", 0.6)); MING = float(opt("--min_gewinn", 0.004)); MAXK = int(opt("--max_kand", 25)); REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
n = np.array([0.3338, 0.9426]); n /= np.linalg.norm(n); u = np.array([n[1], -n[0]]); su = None
uvz = lambda Q: np.c_[np.array(Q)[:, :2] @ u, np.array(Q)[:, :2] @ n, np.array(Q)[:, 2]]
xyz = lambda A: np.c_[np.outer(A[:, 0], u) + np.outer(A[:, 1], n), A[:, 2]]
def rip(o):
    r = o
    for k in pt: r = r[int(k)] if isinstance(r, list) else r[k]
    return r
def pfade_alle(o):
    r = rip(o); L = []
    for q in r.get("pfade", []): A = np.array(q["pfad"] if isinstance(q, dict) else q); L.append(A); B = A.copy(); B[:, 0] = 2 * r["spiegel_u"] - B[:, 0]; L.append(B)
    for q in r.get("pfade_ohne_spiegel", []): L.append(np.array(q["pfad"] if isinstance(q, dict) else q))
    return L
def rs(A, k=24):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(A, axis=0), axis=1))]; t = np.linspace(0, s[-1], k); return np.c_[[np.interp(t, s, A[:, i]) for i in range(3)]].T
def bauen():
    r = subprocess.run(["bash", REPO + "/tools/bauen_abnehmen.sh", os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(objp))) if False else "kaufhaus_grob3")], capture_output=True, text=True, cwd=REPO); t = r.stdout + r.stderr
    return ("alle Pruefungen bestanden" in t), t
def f1(schlauch):
    r = subprocess.run(["/media/oem/scan/venv-seg/bin/python", "-W", "ignore", "-I", REPO + "/tools/rippen_f1.py", REPO + "/modelle/stl/kaufhaus_grob3_1-87.stl", "--box", bx, "--n", "80", "--radius", "25", "--pfade_json", schlauch], capture_output=True, text=True)
    m = re.search(r"Rippen-F1 Mittel ([0-9.]+) Median ([0-9.]+)", r.stdout); return (float(m.group(1)), float(m.group(2))) if m else (None, None)
obj = json.load(open(objp)); kand = []
for c in C:
    A = uvz(c["pfad_xyz"])
    if c.get("laenge_m", 9) < MINM or not (ur[0] < A[:, 0].min() and A[:, 0].max() < ur[1] and zr[0] < A[:, 2].min() and A[:, 2].max() < zr[1]): continue
    kand.append((A, c.get("normale_xyz")))
kand = kand[:MAXK]; nuvz = lambda v: [round(float(v[0] * u[0] + v[1] * u[1]), 3), round(float(v[0] * n[0] + v[1] * n[1]), 3), round(float(v[2]), 3)]
schl = os.path.join(aus, "schlauch.json"); json.dump([xyz(A).tolist() for A in pfade_alle(obj)] + [xyz(A).tolist() for A, _ in kand], open(schl, "w"))
ok0, _ = bauen(); F0 = f1(schl); print("Start: Abnahme", ok0, "F1", F0, flush=True); prot = [dict(start=F0)]; cur = F0
for i, (A, nm) in enumerate(kand):
    if min(np.linalg.norm(rs(A) - rs(W), axis=1).mean() for V in pfade_alle(obj) for W in (V, V[::-1])) < 0.08: prot.append(dict(i=i, entscheidung="Duplikat")); continue
    sicher = json.dumps(obj); r = rip(obj); r.setdefault("pfade_ohne_spiegel", []).append(dict(pfad=np.round(A, 3).tolist(), **({"normale": nuvz(nm)} if nm else {}), spiegeln=False)); json.dump(obj, open(objp, "w"), indent=1, ensure_ascii=False)
    ok, t = bauen(); F = f1(schl) if ok else (None, None); gew = (F[0] - cur[0]) if F[0] is not None else None
    keep = bool(ok and gew is not None and gew >= MING)
    print(f"Kandidat {i} L={float(np.linalg.norm(np.diff(A, axis=0), axis=1).sum()):.2f} Abnahme {ok} F1 {F} Gewinn {gew} -> {'BEHALTEN' if keep else 'verworfen'}", flush=True); prot.append(dict(i=i, abnahme=ok, f1=F, gewinn=gew, entscheidung="behalten" if keep else "verworfen"))
    if keep: cur = F
    else: obj = json.loads(sicher); json.dump(obj, open(objp, "w"), indent=1, ensure_ascii=False)
bauen(); json.dump(prot, open(os.path.join(aus, "greedy.json"), "w"), indent=1); print("Ende: F1", F0, "->", cur, "behalten:", sum(1 for p in prot if p.get("entscheidung") == "behalten"))
