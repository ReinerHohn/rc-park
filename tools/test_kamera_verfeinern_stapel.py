#!/usr/bin/env python3
"""test_kamera_verfeinern_stapel.py - Stapelmodus von tools/kamera_verfeinern.py (--liste) == Folge der Einzelaufrufe (23.11.2026, Kette 1122q: 327 Einzelprozesse
= 75 von 165 min der Stufe seiten_luecken).
Vorgespielte Szene, NUR CPU (keine GPU, < 1 GB, Sekunden): Quader-Netz, 8 Referenzfotos rundum mit wahrer Kamera, 3 neue Fotos mit gestoerter Startkamera
(wie kameras_nachtragen). ALIKED/LightGlue/Renderer sind Ersatzteile: Merkmale = Projektion fester Quaderpunkte mit der WAHREN Kamera des Fotos (sichtbare Seiten),
Zuordnung ueber die Punktnummer, Tiefenbild = exakter Strahlschnitt mit dem Netz. Die Rechnung von kamera_verfeinern (Referenzwahl, Heben, PnP, Ausgleich, Tore,
Schreiben) laeuft unveraendert.
Prueft:
  (1) Einzelaufrufe nacheinander (je Aufruf frische Zwischenspeicher = eigener Prozess) und EIN Stapelaufruf schreiben BITGLEICHE K-Dateien;
  (2) die Szene enthaelt den kritischen Fall (Foto n1 ist erst Referenz von n0, wird dann selbst nachgezogen, dann Referenz von n2) - mit einem Tiefenbild-Schluessel
      nur nach Name weicht der Stapel ab (Gegenprobe: der Test sieht den Fehler, den tiefen_schluessel verhindert);
  (3) winzige Zwischenspeicher (RCPARK_KV_TIEFE_MB, RCPARK_KV_MERKMALE: Verdraengen) aendern nichts;
  (4) seiten_luecken.kamera_verfeinern_zeile: eine Liste in Reihenfolge von kameras_nachtragen.json 'neu', EIN Aufruf mit --liste, leere Liste -> kein Aufruf.
Aufruf: tools/py tools/test_kamera_verfeinern_stapel.py   Exit 0 = alles bestanden."""
import os, sys, json, types, shutil, subprocess
os.environ.setdefault("RCPARK_NACHHOL_CACHE", "0")      # 24.11.2026: Ergebnis-Zwischenspeicher aus - dieser Test vergleicht echte Rechnungen (eigener Test: tests/test_nachhol_zwischenspeicher.py)
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import numpy as np, cv2, torch, trimesh
from pfade import temp_ordner

fehler = 0
W, H, F = 320, 240, 300.0
WAHR = {}          # Fotoname -> (R, t) der wahren Kamera (Ersatz-Merkmale)
PUNKTE = None      # (N,3) Quaderpunkte, NORMALEN (N,3)


def pruef(ok, text):
    global fehler
    print(("ok   " if ok else "FEHLER ") + text, flush=True); fehler += 0 if ok else 1


def kamera_zu(C, ziel):
    z = np.asarray(ziel, float) - C; z /= np.linalg.norm(z); x = np.cross(z, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(z, x); R = np.vstack([x, y, z])
    return R, -R @ np.asarray(C, float)


# ---------- Ersatzteile (CPU) ----------
class Bild:
    def __init__(self, p): self.pfad = p; self.shape = (3, H, W)
    def to(self, _): return self


class ErsatzALIKED:
    def __init__(self, **_): pass
    def eval(self): return self
    def to(self, _): return self
    def extract(self, im, resize=None):
        R, t = WAHR[os.path.splitext(os.path.basename(im.pfad))[0]]; C = -R.T @ t
        Xc = PUNKTE @ R.T + t; u = F * Xc[:, 0] / Xc[:, 2] + W / 2; v = F * Xc[:, 1] / Xc[:, 2] + H / 2
        sicht = (Xc[:, 2] > 1) & (u > 3) & (u < W - 4) & (v > 3) & (v < H - 4) & (((C - PUNKTE) * NORMALEN).sum(1) > 0.05 * np.linalg.norm(C - PUNKTE, axis=1))
        i = np.nonzero(sicht)[0]
        return {"keypoints": torch.tensor(np.stack([u[i], v[i]], 1)[None], dtype=torch.float32), "ids": torch.tensor(i[None])}


class ErsatzLightGlue:
    def __init__(self, **_): pass
    def eval(self): return self
    def to(self, _): return self
    def __call__(self, d):
        a, b = d["image0"]["ids"][0].numpy(), d["image1"]["ids"][0].numpy(); pb = {int(x): j for j, x in enumerate(b)}
        m = np.array([(i, pb[int(x)]) for i, x in enumerate(a) if int(x) in pb], np.int64).reshape(-1, 2)
        return {"matches": [torch.tensor(m)]}


def rbd(d): return {k: (v[0] if isinstance(v, (list, torch.Tensor)) else v) for k, v in d.items()}


def ersatz_rastern(mm, R, t, f, cx, cy, Wr, Hr, **_):
    """Exakter Strahlschnitt je Pixelmitte (Moeller-Trumbore, alle Dreiecke): Tiefe = Kamera-z, Dreiecksnummer, -1 leer (wie render_kern.dreiecke_rastern)."""
    R = np.asarray(R, float); t = np.asarray(t, float).ravel(); C = -R.T @ t; uu, vv = np.meshgrid(np.arange(Wr, dtype=float), np.arange(Hr, dtype=float))
    D = np.stack([(uu - cx) / f, (vv - cy) / f, np.ones_like(uu)], -1).reshape(-1, 3) @ R       # Welt-Strahl, Kamera-z = 1 -> Strahlparameter = Tiefe
    best = np.full(len(D), np.inf); fid = np.full(len(D), -1, np.int64); Tr = np.asarray(mm.triangles)
    for k, (A, B, Cc) in enumerate(Tr):
        e1, e2 = B - A, Cc - A; p = np.cross(D, e2); det = p @ e1; ok = np.abs(det) > 1e-12; inv = np.where(ok, 1 / np.where(ok, det, 1), 0); s = C - A
        uu_ = (p @ s) * inv; q = np.cross(s, e1); vv_ = (D @ q) * inv; tt = (q @ e2) * inv
        hit = ok & (uu_ >= 0) & (vv_ >= 0) & (uu_ + vv_ <= 1) & (tt > 1) & (tt < best); best[hit] = tt[hit]; fid[hit] = k
    return best.reshape(Hr, Wr).astype(np.float32), fid.reshape(Hr, Wr), None


def module_einsetzen():
    lg = types.ModuleType("lightglue"); lg.ALIKED = ErsatzALIKED; lg.LightGlue = ErsatzLightGlue
    lu = types.ModuleType("lightglue.utils"); lu.load_image = Bild; lu.rbd = rbd; lg.utils = lu
    sys.modules["lightglue"] = lg; sys.modules["lightglue.utils"] = lu
    import kamera_verfeinern as KV
    KV.GERAET = "cpu"; KV.rk = types.SimpleNamespace(dreiecke_rastern=ersatz_rastern)
    return KV


# ---------- Szene ----------
def szene(d):
    global PUNKTE, NORMALEN
    root = d; od = os.path.join(root, "modelle", "q"); mp = os.path.join(od, "messprotokoll"); fd = os.path.join(root, "fotos"); os.makedirs(mp); os.makedirs(fd)
    box = trimesh.creation.box(extents=[8, 6, 10]); box.apply_translation([0, 0, 5]); os.makedirs(os.path.join(root, "stl")); box.export(os.path.join(root, "stl", "q.stl"))
    P, N = [], []
    g = np.linspace(-0.85, 0.85, 11)
    for ax, halb in ((0, 4), (1, 3)):
        for sg in (-1, 1):
            for a_ in g:
                for b_ in g:
                    x = np.zeros(3); x[ax] = sg * halb; x[1 - ax] = a_ * (3 if ax == 0 else 4); x[2] = 5 + b_ * 5; n = np.zeros(3); n[ax] = sg; P.append(x); N.append(n)
    PUNKTE, NORMALEN = np.array(P), np.array(N)
    json.dump(dict(name="q", fotos_dir="fotos", stl="stl/q.stl", stl_massstab=1000), open(os.path.join(od, "objekt.json"), "w"))
    json.dump(dict(fassaden=[]), open(os.path.join(od, "fassaden.json"), "w"))
    def foto(n, az, r, h, stoer=None):
        C = np.array([r * np.cos(np.radians(az)), r * np.sin(np.radians(az)), h]); R, t = kamera_zu(C, [0, 0, 5]); WAHR[n] = (R, t)
        cv2.imwrite(os.path.join(fd, n + ".jpg"), np.full((H, W, 3), 90, np.uint8))
        if stoer is None: k = dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=t.tolist(), f_px=F, cx=W / 2, cy=H / 2, k1=0.0, quelle="buendel")
        else:
            R2, t2 = kamera_zu(C + np.array(stoer), [0.4, -0.3, 5.3]); k = dict(rvec=cv2.Rodrigues(R2)[0].ravel().tolist(), t=t2.tolist(), f_px=F * 1.15, cx=W / 2, cy=H / 2, k1=0.0, quelle="nachregistriert (sparse_handy)")
        json.dump(dict(foto=n, kamera=k), open(os.path.join(mp, f"K-{n}.json"), "w"))
    for i in range(8): foto(f"eigen__r{i}", 45 * i + 3, 22 + (i % 3), 3 + i % 2)
    foto("commons_n0", 38, 21, 3.5, [0.9, -0.6, 0.3]); foto("commons_n1", 52, 23, 3.0, [-0.8, 0.7, -0.4]); foto("commons_n2", 66, 22, 4.0, [0.6, 0.9, 0.2])
    return od, mp


def k_lesen(mp): return {f: open(os.path.join(mp, f)).read() for f in sorted(os.listdir(mp))}


def main():
    KV = module_einsetzen(); neu = ["commons_n0", "commons_n1", "commons_n2"]
    d = temp_ordner("kv_stapel_")
    od, mp = szene(d); start = os.path.join(d, "start"); shutil.copytree(mp, start)
    O, FJ = os.path.join(od, "objekt.json"), os.path.join(od, "fassaden.json"); L = os.path.join(d, "liste.txt"); open(L, "w").write("\n".join(neu))
    def neu_start(): shutil.rmtree(mp); shutil.copytree(start, mp)
    for n in neu: KV.main([O, FJ, n, "--schreiben"])
    einzel = k_lesen(mp)
    bestimmt = [n for n in neu if json.loads(einzel[f"K-{n}.json"]).get("kamera", {}).get("vertrauen")]
    pruef(len(bestimmt) == 3, f"Einzelaufrufe: alle 3 neuen Kameras am Modell nachgezogen ({bestimmt})")
    q2 = json.loads(einzel["K-commons_n2.json"])["kamera"]["quelle"]; q0 = json.loads(einzel["K-commons_n0.json"])["kamera"]["quelle"]
    pruef("commons_n1" in q0 and "commons_n1" in q2, "Szene: n1 ist Referenz von n0 (vor seinem Nachziehen) UND von n2 (danach) - der kritische Fall fuer den Zwischenspeicher")
    for n in neu:
        R, t = WAHR[n]; k = json.loads(einzel[f"K-{n}.json"])["kamera"]; C = -cv2.Rodrigues(np.array(k["rvec"]))[0].T @ np.array(k["t"])
        pruef(np.linalg.norm(C - (-R.T @ t)) < 0.3 and abs(k["f_px"] / F - 1) < 0.03, f"Einzelaufruf {n}: Standort {np.linalg.norm(C - (-R.T @ t)):.3f} m neben der Wahrheit, f {k['f_px']:.1f} (wahr {F:.0f})")
    neu_start(); KV.main([O, FJ, "-", "--liste", L, "--schreiben"]); stapel = k_lesen(mp)
    pruef(stapel == einzel, "Stapel (--liste, EIN Prozess) == Einzelaufrufe: K-Dateien bitgleich" + ("" if stapel == einzel else f" ABWEICHEND: {[f for f in einzel if stapel.get(f) != einzel[f]]}"))
    neu_start(); os.environ["RCPARK_KV_TIEFE_MB"] = "0.000001"; os.environ["RCPARK_KV_MERKMALE"] = "1"
    KV.main([O, FJ, "-", "--liste", L, "--schreiben"]); klein = k_lesen(mp); del os.environ["RCPARK_KV_TIEFE_MB"], os.environ["RCPARK_KV_MERKMALE"]
    pruef(klein == einzel, "Stapel mit winzigen Zwischenspeichern (Verdraengen) == Einzelaufrufe")
    neu_start(); alt = KV.tiefen_schluessel; KV.tiefen_schluessel = lambda n, k: n
    try: KV.main([O, FJ, "-", "--liste", L, "--schreiben"]); nur_name = k_lesen(mp)
    finally: KV.tiefen_schluessel = alt
    pruef(nur_name["K-commons_n2.json"] != einzel["K-commons_n2.json"] and nur_name["K-commons_n0.json"] == einzel["K-commons_n0.json"],
          "Gegenprobe: Tiefenbild-Schluessel nur nach Name -> n2 weicht ab (veraltetes Tiefenbild von n1), n0 gleich - der Test erkennt den Fehler")
    # (4) Zeile im Nachhol-Skript
    import seiten_luecken as SL
    au = os.path.join(d, "audit"); Z = os.path.join(d, "Z"); os.makedirs(au); os.makedirs(Z)
    json.dump(dict(neu=[dict(foto=n) for n in ["b_2", "a_1", "c 3"]]), open(os.path.join(au, "kameras_nachtragen.json"), "w"))
    z = SL.kamera_verfeinern_zeile("echo AUFRUF", "/T", "/o/objekt.json", "/o/fassaden.json", au, Z)
    r = subprocess.run(["bash", "-c", "set -e\n" + z + "\necho ENDE"], capture_output=True, text=True)
    liste = open(os.path.join(Z, "kamera_verfeinern_liste.txt")).read().split("\n")
    pruef(r.returncode == 0 and r.stdout.count("AUFRUF") == 1 and "--liste " + os.path.join(Z, "kamera_verfeinern_liste.txt") in r.stdout and "--schreiben" in r.stdout and "ENDE" in r.stdout,
          f"Nachhol-Skript: EIN Aufruf kamera_verfeinern --liste --schreiben ({r.stdout.strip()[:160]} {r.stderr[-160:]})")
    pruef(liste == ["b_2", "a_1", "c 3"], f"Nachhol-Skript: Liste in der Reihenfolge von kameras_nachtragen.json, ein Name je Zeile ({liste})")
    json.dump(dict(neu=[]), open(os.path.join(au, "kameras_nachtragen.json"), "w"))
    r = subprocess.run(["bash", "-c", "set -e\n" + z + "\necho ENDE"], capture_output=True, text=True)
    pruef(r.returncode == 0 and "AUFRUF" not in r.stdout and "ENDE" in r.stdout, "Nachhol-Skript: keine neue Kamera -> kein Aufruf, kein Abbruch")
    os.remove(os.path.join(au, "kameras_nachtragen.json"))
    r = subprocess.run(["bash", "-c", "set -e\n" + z + "\necho ENDE"], capture_output=True, text=True)
    pruef(r.returncode == 0 and "AUFRUF" not in r.stdout and "ENDE" in r.stdout, "Nachhol-Skript: kameras_nachtragen.json fehlt -> kein Aufruf, kein Abbruch (wie die alte Schleife)")
    print("ALLE BESTANDEN" if not fehler else f"{fehler} FEHLER"); return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
