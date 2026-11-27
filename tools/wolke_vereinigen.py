#!/usr/bin/env python3
"""wolke_vereinigen.py - ALLE dichten Wolken EINES Objekts zu einer vereinen, in EINEM Modellrahmen (Nutzer 26./27.11.2026: "alles mergen", "Immer vereinen").

  NEU (Register):  tools/py tools/wolke_vereinigen.py --objekt modelle/<obj>/objekt.json --aus <ordner> [--voxel 0.02] [--max_abw 0.05] [--block 5]
                   tools/py tools/wolke_vereinigen.py --objekt ... --anmelden NAME=PFAD@RAHMEN[@LAGETOR]        (nur eintragen, nichts rechnen)
  ALT (wie 26.11.): tools/py tools/wolke_vereinigen.py <basis.ply> <aus.ply> --ausrichtung SFM-AUSRICHTUNG.json --quelle NAME=PFAD.ply [...]   (alles im SfM-Rahmen, Ausgabe SfM-Rahmen)

Register modelle/<obj>/wolken.json: {"quellen": [{"name", "pfad", "rahmen", "lagetor"}...]} - Reihenfolge = Vorrang (erste = Bezug fuer die Lagepruefung, gewinnt bei Gleichstand).
  pfad: .ply (x y z [nx ny nz] [red green blue], binaer) oder .npy (N x 3 Modellmeter, Farben in gleichnamiger *farben*.npy) - Normalen/Farben bleiben erhalten.
  rahmen: "modell" | "sfm:<SFM-AUSRICHTUNG.json>" (X_sfm = s R(rvec) X_modell + t) | "matrix:<datei.json>#<schluessel.pfad>" (4x4, X_modell = M X_quelle).
  lagetor: "" | "teilmodell:<ausrichtung.json>#<n>" (tools/teilmodell_ausrichten.tor, rc 0 = ausgerichtet) | "spuren:<einpassung.json>" (kandidaten.spuren.tor_rot leer).
DREI LAGE-TORE je Quelle (nie blind transformieren, Quellen nicht mitteln):
  (1) lagetor-Eintrag (UNSICHER -> Quelle nicht vereint, Grund im Bericht);
  (2) global: Stichprobe -> Abstand zur lokalen Ebene des Bezugs (8 Nachbarn < 1 m, PCA; Punkt-zu-Punkt hinge an der Bezugsdichte); Ueberlapp >= 1 000 und Median
      <= --max_abw (ANNAHME 5 cm) gesamt UND je Ebenenrichtung x/y/z (in der Ebene verschobene Wand), sonst ABGELEHNT;
  (3) je Raumblock (--block m, Wuerfel): hat der Bezug dort >= 500 Punkte und die Quelle >= 50 Stichproben mit Ueberlapp (Ebene < 0,5 m), Median > --max_abw -> Quelle in DIESEM Block
      weggelassen (Messung 27.11. Schwabentor: Handy-Wolke unten 1-2 cm am Hauptnetz, ueber z 15 m 4-24 cm daneben = Doppelwand, siehe Doku/projekt/foto-sfm/wolken-vereinen.md).
VEREINIGUNG je Voxel (--voxel m, ANNAHME 2 cm): je Voxel behaelt GENAU EINE Quelle ihre Punkte - die mit den meisten Punkten dort (Gleichstand: Vorrang). Damit
  - Duplikate verschiedener Quellen im selben Voxel weg, Eigendichte einer Quelle bleibt;
  - jede Zone aus ganzen Voxeln hat vereint >= max(Quelle) (Summe der Maxima >= Maximum der Summen) -> roter Test tools/test_wolke_vereinigen.py.
Speicher: Quellen werden in Bloecken (--bloecke Punkte) gelesen/transformiert (np.memmap), im RAM nur Voxelschluessel (16 B/Punkt) + Stichprobe; Ausgabe blockweise.
Ausgabe <aus>/: vereint_modell.ply (Modellrahmen, Normalen gedreht), vereint_modell.ply.quellen.npy (uint8 je Punkt = Index im Register),
  punkte_modell.npy (float64, wie modelle/<obj>/sfm/punkte_modell_<obj>.npy) + punkte_farben.npy, vereint.json (Tore, Zahlen je Quelle, je Zone ALT/NEU/VEREINT, rot).
ZONEN (--objekt): Waende aus objekt.json rahmen_wand + seiten_konvention (Wandebene = Haeufungsspitze des Bezugs +-2 m um die Rahmenlinie, Streifen +-0,5 m, z --zonen_z),
  Dach (im Rahmen ueber z --zonen_z oben), Sonderstellen aus abdeckung_zonen.json (zylinder; lage-Datei mit 'steg' = Bruecke). Zone je VOXELMITTE -> Garantie exakt.
  rc 3 = eine Zone hat vereint weniger Punkte als die beste (zugelassene) Quelle = ROT.
Verwandt: tools/kachel_vereinen.py (Entweder-Oder je Kachel), tools/kachelfusion.py, tools/quellfilter.py (Nachfilter), tools/dichte_diagnose.py, tools/wolken_vereinen_stufe.sh
  (Nachtketten), tools/gesamtkette.py (Schritt wolken_vereinen nach den Toren), tools/teilmodell_spuren_einpassen.py (liefert Handy-Wolke im Modellrahmen).
Vorlaeufer: diese Datei bis 26.11. (Basis unveraendert + Quellen nur in leere 1,5-cm-Voxel, ein Rahmen, alles im RAM, kein Blocktor) und kachel_vereinen.py (je Kachel nur eine Quelle).
"""
import os, sys, json, argparse, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DT = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
_PT = {"float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8", "uchar": "u1", "uint8": "u1", "char": "i1", "int8": "i1", "short": "<i2", "ushort": "<u2",
       "int": "<i4", "int32": "<i4", "uint": "<u4", "uint32": "<u4"}
_NAMEN = {"red": "r", "green": "g", "blue": "b", "diffuse_red": "r", "diffuse_green": "g", "diffuse_blue": "b"}


# ---------------------------------------------------------------- Lesen / Schreiben
class Quelle:
    """Eine Wolke als Blockleser: .ply (memmap, beliebige Eigenschaftsreihenfolge) oder .npy (Modellmeter + *farben*.npy)."""
    def __init__(self, pfad):
        self.pfad = pfad
        if pfad.endswith(".npy"):
            self.X = np.load(pfad, mmap_mode="r"); self.n = len(self.X); fp = farben_pfad(pfad)
            self.F = np.load(fp, mmap_mode="r") if fp and os.path.exists(fp) else None; self.ply = False; return
        with open(pfad, "rb") as f:
            kopf = b""
            while not kopf.endswith(b"end_header\n"):
                z = f.readline()
                if not z: raise ValueError(f"{pfad}: kein end_header")
                kopf += z
        zeilen = kopf.decode("ascii", "replace").splitlines()
        if not any(l.startswith("format binary_little_endian") for l in zeilen): raise ValueError(f"{pfad}: nur binary_little_endian")
        self.n = int([l for l in zeilen if l.startswith("element vertex")][0].split()[-1]); felder = []; im_vertex = False
        for l in zeilen:
            if l.startswith("element"): im_vertex = l.split()[1] == "vertex"
            elif l.startswith("property") and im_vertex: _, t, name = l.split()[:3]; felder.append((_NAMEN.get(name, name), _PT[t]))
        self.A = np.memmap(pfad, dtype=np.dtype(felder), mode="r", offset=len(kopf), shape=(self.n,)) if self.n else np.zeros(0, np.dtype(felder)); self.ply = True

    def block(self, i0, i1):
        """(X (k,3) float64, N (k,3) float32 oder None, F (k,3) uint8 oder None) der Punkte i0..i1 im Quellrahmen."""
        if not self.ply:
            F = np.asarray(self.F[i0:i1], np.uint8) if self.F is not None else None
            return np.asarray(self.X[i0:i1], np.float64), None, F
        a = np.asarray(self.A[i0:i1]); nm = a.dtype.names
        X = np.c_[a["x"], a["y"], a["z"]].astype(np.float64)
        N = np.c_[a["nx"], a["ny"], a["nz"]].astype(np.float32) if "nx" in nm else None
        F = np.c_[a["r"], a["g"], a["b"]].astype(np.uint8) if "r" in nm else None
        return X, N, F


def farben_pfad(p):
    d, b = os.path.split(p)
    for alt, neu in (("punkte_modell", "punkte_farben"), ("_modell.npy", "_farben.npy"), ("modell", "farben")):
        if alt in b: return os.path.join(d, b.replace(alt, neu, 1))
    return None


def ply_kopf(n):
    return ("ply\nformat binary_little_endian 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\n"
            "property float nz\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % n).encode()


# ---------------------------------------------------------------- Rahmen
def _pfad(p, basis=ROOT):
    return p if os.path.isabs(p) else os.path.join(basis, p)


def rahmen_lesen(spec, basis=ROOT):
    """(A (3,3), b (3,)) mit X_modell = A X_quelle + b. spec siehe Kopf."""
    spec = (spec or "modell").strip()
    if spec == "modell": return np.eye(3), np.zeros(3)
    art, _, rest = spec.partition(":")
    if art == "sfm":
        import cv2
        T = json.load(open(_pfad(rest, basis)))["transformation"]; s = float(T["s"]); R = cv2.Rodrigues(np.array(T["rvec"], float))[0]; t = np.array(T["t"], float)
        return R.T / s, -(R.T @ t) / s                                                    # X_modell = R^T (X_sfm - t) / s
    if art == "matrix":
        datei, _, schl = rest.partition("#"); d = json.load(open(_pfad(datei, basis)))
        for k in [k for k in schl.split(".") if k]: d = d[k]
        M = np.array(d, float); return M[:3, :3], M[:3, 3]
    raise ValueError(f"unbekannter Rahmen '{spec}' (modell | sfm:<json> | matrix:<json>#<schluessel>)")


def normalen_matrix(A):
    """Normalen transformieren mit der Inversen-Transponierten (fuer Sim3 = reine Drehung), danach normieren."""
    return np.linalg.inv(A).T


def _norm(N):
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def abstand_ebene(baum, Xb, S, k=8, r=0.5, k_min=5):
    """Abstand jedes Stichprobenpunkts zur LOKALEN EBENE der Bezugswolke (k Nachbarn < r, PCA). Punkt-zu-Punkt haengt an der Bezugsdichte
    (duenner Bezug = grosse Abstaende trotz gleicher Lage, Test 27.11.), Punkt-zu-Ebene nicht. inf = weniger als k_min Nachbarn (kein Ueberlapp)."""
    d, ii = baum.query(S, k=k, distance_upper_bound=r, workers=-1); gut = np.isfinite(d); n = gut.sum(1); ok = n >= k_min; out = np.full(len(S), np.inf); nrm = np.zeros((len(S), 3))
    if not ok.any(): return out, nrm
    ii = np.where(gut, ii, ii[:, :1]); P = Xb[ii[ok]]; w = gut[ok][..., None].astype(float); c = (P * w).sum(1) / w.sum(1)
    D = (P - c[:, None]) * w; C = np.einsum("nki,nkj->nij", D, D); _, V = np.linalg.eigh(C); nv = V[:, :, 0]
    out[ok] = np.abs(np.einsum("ni,ni->n", S[ok] - c, nv)); nrm[ok] = nv; return out, nrm


def global_tor(d, nrm, max_abw, n_min=1000, n_klasse=200):
    """(ok, median, je_richtung). Median je Ebenenrichtung (x/y/z dominant): eine IN der Ebene verschobene Wand zeigt Punkt-zu-Ebene 0 -
    die quer stehenden Waende verraten die Verschiebung (Test 27.11.: 1-m-Verschiebung haette sonst bestanden). Jede Richtung mit >= n_klasse Ueberlapp muss bestehen."""
    ue = np.isfinite(d); med = float(np.median(d[ue])) if ue.any() else float("nan"); kl = np.argmax(np.abs(nrm), 1); je = {}
    for k_, nm in enumerate("xyz"):
        m = ue & (kl == k_)
        if m.sum() >= n_klasse: je[nm] = round(float(np.median(d[m])), 4)
    ok = bool(ue.sum() >= n_min and med <= max_abw and all(v <= max_abw for v in je.values())); return ok, med, je


# ---------------------------------------------------------------- Lagetor-Eintrag
def lagetor_pruefen(spec, basis=ROOT):
    """(ok, text). Leer = kein Eintrag (ok, nur Daten-Tore)."""
    if not spec: return True, "kein Lagetor-Eintrag (nur Ueberlapp-Tore)"
    art, _, rest = spec.partition(":")
    if art == "teilmodell":
        import teilmodell_ausrichten as TA
        datei, _, n = rest.partition("#"); rc, txt = TA.tor(_pfad(datei, basis), n or "0"); return rc == 0, txt
    if art == "spuren":
        try: tr = json.load(open(_pfad(rest, basis)))["kandidaten"]["spuren"].get("tor_rot")
        except (OSError, ValueError, KeyError) as ex: return False, f"UNSICHER: Einpassung {rest} nicht lesbar ({type(ex).__name__})"
        return (tr == [], f"Spuren-Einpassung: tor_rot {tr}" if tr else "Spuren-Einpassung: alle Gegenproben gruen (tor_rot leer)")
    return False, f"UNSICHER: unbekanntes Lagetor '{spec}'"


# ---------------------------------------------------------------- Schluessel
def vkey(M, v):
    """int64-Voxelschluessel (21 Bit je Achse, +-20 km bei 2 cm)."""
    q = np.floor(M / v).astype(np.int64) + 1_048_576
    return (q[:, 0] << 42) | (q[:, 1] << 21) | q[:, 2]


def vmitte(k, v):
    k = np.asarray(k, np.int64); q = np.c_[(k >> 42) & 0x1FFFFF, (k >> 21) & 0x1FFFFF, k & 0x1FFFFF] - 1_048_576
    return (q + 0.5) * v


def gewinner(keys, src, prio):
    """bool je Punkt: behalten. Je Voxel gewinnt die Quelle mit den meisten Punkten (Gleichstand: kleinster prio-Wert)."""
    if len(keys) == 0: return np.zeros(0, bool)
    S = int(src.max()) + 1
    _, inv = np.unique(keys, return_inverse=True); comb = inv.astype(np.int64).ravel(); del inv; comb *= S; comb += src
    uc, cnt = np.unique(comb, return_counts=True); zelle = uc // S; q = uc % S
    o = np.lexsort((np.asarray(prio)[q], -cnt, zelle)); erst = np.r_[True, zelle[o][1:] != zelle[o][:-1]]
    sieger = np.sort(uc[o][erst]); pos = np.searchsorted(sieger, comb)
    return (pos < len(sieger)) & (sieger[np.minimum(pos, len(sieger) - 1)] == comb)


# ---------------------------------------------------------------- Zonen
def zonen_bauen(objekt, bezug_M=None, z_bereich=(3.0, 38.0), streifen=1.0):
    """Liste von Zonen {name, art, ...} aus objekt.json + abdeckung_zonen.json (nichts objektspezifisch im Code). bezug_M: Punkte des Bezugs (Modellmeter) fuer die Wandebene."""
    od = os.path.dirname(os.path.abspath(objekt)); obj = json.load(open(objekt)); out = []
    rw = obj.get("rahmen_wand") or {}; konv = {k: v for k, v in (obj.get("seiten_konvention") or {}).items() if k in ("+x", "-x", "+y", "-y")}
    cfg = json.load(open(os.path.join(od, "abdeckung_zonen.json"))) if os.path.exists(os.path.join(od, "abdeckung_zonen.json")) else {}
    if rw and len(konv) == 4:
        u0, u1, v0, v1 = (float(rw[k]) for k in ("u0", "u1", "v0", "v1"))
        for key, ax, pos, sg, a, b in (("+x", 0, u1, 1, v0, v1), ("-x", 0, u0, -1, v0, v1), ("+y", 1, v1, 1, u0, u1), ("-y", 1, v0, -1, u0, u1)):
            ebene, quelle = pos, "objekt.json rahmen_wand"
            if bezug_M is not None and len(bezug_M):
                q = bezug_M[:, 1 - ax]; z = bezug_M[:, 2]; d = (bezug_M[:, ax] - pos) * sg
                m = (q > a + 0.5) & (q < b - 0.5) & (z > z_bereich[0]) & (z < z_bereich[1]) & (np.abs(d) < 2.0)
                if m.sum() > 1000:
                    h, e = np.histogram(d[m], bins=80, range=(-2, 2)); k = int(np.argmax(h)); ebene = pos + sg * (e[k] + e[k + 1]) / 2
                    quelle = f"Haeufungsspitze Bezug {(e[k] + e[k + 1]) / 2:+.2f} m gegen rahmen_wand"
            out.append(dict(name=konv[key], art="wand", achse=ax, ebene=float(ebene), vz=sg, a=a + 0.5, b=b - 0.5, z=list(z_bereich), halb=streifen / 2, quelle=quelle))
        zo = float(cfg.get("dach_oben_m", obj.get("hoehe_m", 60.0))) + 2.0
        out.append(dict(name="Dach", art="kasten", x=[u0 + 0.3, u1 - 0.3], y=[v0 + 0.3, v1 - 0.3], z=[float(z_bereich[1]), zo], quelle="rahmen_wand innen, ueber Wandoberkante"))
    for s in cfg.get("sonderstellen", []):
        if s.get("form") == "zylinder" and s.get("mitte"):
            out.append(dict(name=s["name"], art="zylinder", mitte=s["mitte"], r=float(s["radius_m"]) + 0.5, z=s.get("z", [0, 50]), quelle=s.get("quelle", "")[:120]))
        elif s.get("lage"):
            lp = os.path.join(od, s["lage"])
            if not os.path.exists(lp): continue
            st = json.load(open(lp)).get("steg") or {}
            if st.get("mitte_modell_xy") and st.get("achse_modell_xy"):
                out.append(dict(name=s["name"] + "-Streifen", art="streifen", mitte=st["mitte_modell_xy"], achse=st["achse_modell_xy"], laenge=float(st.get("laenge_dach_m", 30)),
                                breite=float(st.get("breite_dach_m", 4)) + 1.0, z=[0.0, float(st.get("dach_first_z_m", 12)) + 1.5], quelle=s["lage"]))
    return out


def in_zone(Z, M):
    x, y, z = M[:, 0], M[:, 1], M[:, 2]
    if Z["art"] == "wand":
        d = (M[:, Z["achse"]] - Z["ebene"]); q = M[:, 1 - Z["achse"]]
        return (np.abs(d) <= Z["halb"]) & (q > Z["a"]) & (q < Z["b"]) & (z > Z["z"][0]) & (z < Z["z"][1])
    if Z["art"] == "kasten": return (x > Z["x"][0]) & (x < Z["x"][1]) & (y > Z["y"][0]) & (y < Z["y"][1]) & (z > Z["z"][0]) & (z < Z["z"][1])
    if Z["art"] == "zylinder": return (np.hypot(x - Z["mitte"][0], y - Z["mitte"][1]) <= Z["r"]) & (z > Z["z"][0]) & (z < Z["z"][1])
    if Z["art"] == "streifen":
        u = np.asarray(Z["achse"], float); u = u / np.linalg.norm(u); qn = np.array([-u[1], u[0]]); d = M[:, :2] - np.asarray(Z["mitte"], float)
        return (np.abs(d @ u) <= Z["laenge"] / 2) & (np.abs(d @ qn) <= Z["breite"] / 2) & (z > Z["z"][0]) & (z < Z["z"][1])
    raise ValueError(Z["art"])


def zonen_zaehlen(zonen, keys, v):
    """Anzahl Punkte je Zone, Zugehoerigkeit nach Voxelmitte (damit Zonen aus ganzen Voxeln bestehen)."""
    if len(keys) == 0: return {Z["name"]: 0 for Z in zonen}
    uk, cnt = np.unique(keys, return_counts=True); C = vmitte(uk, v)
    return {Z["name"]: int(cnt[in_zone(Z, C)].sum()) for Z in zonen}


def zonen_urteil(zahlen, namen_zugelassen):
    """zahlen: {quelle: {zone: n}, 'VEREINT': {...}}. Liste roter Zonen (vereint < beste zugelassene Quelle)."""
    rot = []
    for zn, nv in zahlen["VEREINT"].items():
        if not namen_zugelassen: continue
        bq = max(namen_zugelassen, key=lambda q: zahlen[q].get(zn, 0)); best = zahlen[bq].get(zn, 0)
        if nv < best: rot.append(dict(zone=zn, vereint=nv, beste_quelle=bq, beste=best))
    return rot


# ---------------------------------------------------------------- Kern
def vereinigen(quellen, aus, voxel=0.02, max_abw=0.05, block=5.0, stichprobe=300_000, bloecke=2_000_000, objekt=None, zonen_z=(3.0, 38.0),
               aus_rahmen=None, npy=True, basis=ROOT, log=lambda s: print(s, flush=True)):
    """quellen: Liste {name, pfad, rahmen, lagetor}. aus: Ordner (Modellrahmen) - oder mit aus_rahmen=(A, b) (Modell -> Ausgaberahmen) eine PLY-Datei (alter Aufruf).
    Rueckgabe Bericht (dict); bericht['rot'] = Liste roter Zonen."""
    from scipy.spatial import cKDTree
    t0 = time.time(); rng = np.random.default_rng(0); bericht = dict(voxel_m=voxel, max_abw_m=max_abw, block_m=block, quellen=[]); Q = []
    for i, q in enumerate(quellen):
        z = dict(name=q["name"], pfad=q["pfad"], rahmen=q.get("rahmen", "modell"), lagetor=q.get("lagetor", ""))
        if not os.path.exists(_pfad(q["pfad"], basis)): z.update(angenommen=False, grund="Datei fehlt"); bericht["quellen"].append(z); log("FEHLT " + q["pfad"]); continue
        ok, txt = lagetor_pruefen(q.get("lagetor", ""), basis); z["lagetor_text"] = txt
        if not ok: z.update(angenommen=False, grund="Lagetor: " + txt); bericht["quellen"].append(z); log(f"NICHT VEREINT {q['name']}: {txt}"); continue
        L = Quelle(_pfad(q["pfad"], basis)); A, b = rahmen_lesen(q.get("rahmen", "modell"), basis); z["punkte"] = int(L.n)
        keys = np.empty(L.n, np.int64); bk = np.empty(L.n, np.int64); idx = np.sort(rng.choice(L.n, min(stichprobe, L.n), replace=False)) if L.n else np.zeros(0, np.int64)
        S = np.empty((len(idx), 3)); j = 0
        for i0 in range(0, L.n, bloecke):
            X, _, _ = L.block(i0, min(L.n, i0 + bloecke)); M = X @ A.T + b; keys[i0:i0 + len(M)] = vkey(M, voxel); bk[i0:i0 + len(M)] = vkey(M, block)
            w = idx[(idx >= i0) & (idx < i0 + len(M))]; S[j:j + len(w)] = M[w - i0]; j += len(w)
        Q.append(dict(i=i, name=q["name"], L=L, A=A, b=b, keys=keys, bk=bk, S=S, Sb=bk[idx], z=z, behalten=np.ones(L.n, bool)))
        log(f"gelesen {q['name']}: {L.n} Punkte ({time.time() - t0:.0f} s)")
    if not Q: raise SystemExit("keine lesbare Quelle")
    bez = Q[0]; Xb = []; schritt = max(1, bez["L"].n // 6_000_000)                     # Bezug = erste lesbare Quelle; KD-Baum auf <= 6 Mio Punkten
    for i0 in range(0, bez["L"].n, bloecke):
        X, _, _ = bez["L"].block(i0, min(bez["L"].n, i0 + bloecke)); Xb.append((X @ bez["A"].T + bez["b"])[::schritt])
    Xb = np.concatenate(Xb); baum = cKDTree(Xb); ub, ucnt = np.unique(bez["bk"], return_counts=True); bez_block = dict(zip(ub.tolist(), ucnt.tolist()))
    bez["z"].update(angenommen=True, rolle="Bezug")
    for q in Q[1:]:
        dg, ng = abstand_ebene(baum, Xb, q["S"], r=1.0); ok, med, je = global_tor(dg, ng, max_abw)
        q["z"].update(ueberlapp_stichprobe=int(np.isfinite(dg).sum()), median_abstand_m=round(med, 4), median_je_richtung_m=je, angenommen=ok)
        if not ok:
            q["z"]["grund"] = f"Ueberlapp {int(np.isfinite(dg).sum())} (>= 1000) / Median {med:.3f} m, je Richtung {je} (<= {max_abw}) nicht erfuellt"; q["behalten"][:] = False
            log("ABGELEHNT " + json.dumps(q["z"], ensure_ascii=False)); continue
        d, _ = abstand_ebene(baum, Xb, q["S"], r=0.5); ue = np.isfinite(d); weg = []
        for bkey in np.unique(q["Sb"]):                                            # Blocktor
            m = (q["Sb"] == bkey) & ue
            if bez_block.get(int(bkey), 0) >= 500 and m.sum() >= 50:
                mb = float(np.median(d[m]))
                if mb > max_abw: weg.append((int(bkey), mb, int(m.sum())))
        if weg:
            wk = np.array(sorted(w[0] for w in weg), np.int64); pos = np.searchsorted(wk, q["bk"]); q["behalten"] &= ~((pos < len(wk)) & (wk[np.minimum(pos, len(wk) - 1)] == q["bk"]))
        q["z"]["bloecke_weg"] = [dict(mitte=[round(float(c), 1) for c in vmitte([k], block)[0]], median_m=round(mb, 3), stichproben=n) for k, mb, n in weg]
        q["z"]["punkte_weg_blocktor"] = int((~q["behalten"]).sum())
        log(f"OK {q['name']}: Median {med:.4f} m, Ueberlapp {int(ue.sum())}, Bloecke weg {len(weg)} ({q['z']['punkte_weg_blocktor']} Punkte)")
    del baum, Xb
    akt = [q for q in Q if q["z"].get("angenommen")]; zahlen = {}; zonen = []
    if objekt:                                                                     # Zonen der Quellen VOR dem Gewinnerschritt (danach Schluessel frei = weniger Spitzenspeicher)
        zonen = zonen_bauen(objekt, bez["S"], zonen_z)
        for q in Q: zahlen[q["name"]] = zonen_zaehlen(zonen, q["keys"], voxel)
        for q in akt: zahlen[q["name"] + "|zugelassen"] = zonen_zaehlen(zonen, q["keys"][q["behalten"]], voxel)
    keys = np.concatenate([q["keys"][q["behalten"]] for q in akt]); src = np.concatenate([np.full(int(q["behalten"].sum()), k, np.uint8) for k, q in enumerate(akt)])
    for q in Q: q.pop("keys", None); q.pop("bk", None)
    halt = gewinner(keys, src, np.arange(len(akt))); off = 0; del src
    for q in akt:
        nb = int(q["behalten"].sum()); w = halt[off:off + nb]; off += nb; q["wahl"] = np.flatnonzero(q["behalten"])[w]; q["z"]["punkte_vereint"] = int(len(q["wahl"]))
    keys_v = keys[halt]; del keys, halt
    n_ges = sum(len(q["wahl"]) for q in akt); bericht["punkte"] = int(n_ges); log(f"Gewinner je Voxel: {n_ges} Punkte ({time.time() - t0:.0f} s)")
    if objekt:
        zahlen["VEREINT"] = zonen_zaehlen(zonen, keys_v, voxel)
        bericht["zonen"] = zonen; bericht["zonen_zahlen"] = zahlen; bericht["rot"] = zonen_urteil(zahlen, [q["name"] + "|zugelassen" for q in akt])
    else: bericht["rot"] = []
    del keys_v
    sfm_aus = aus_rahmen is not None                                               # Schreiben (blockweise)
    os.makedirs(os.path.dirname(os.path.abspath(aus)) if sfm_aus else aus, exist_ok=True)
    ply = aus if sfm_aus else os.path.join(aus, "vereint_modell.ply"); qn = np.empty(n_ges, np.uint8)
    PM = np.lib.format.open_memmap(os.path.join(aus, "punkte_modell.npy.tmp"), "w+", np.float64, (n_ges, 3)) if (npy and not sfm_aus) else None
    PF = np.lib.format.open_memmap(os.path.join(aus, "punkte_farben.npy.tmp"), "w+", np.uint8, (n_ges, 3)) if (npy and not sfm_aus) else None
    o = 0
    with open(ply + ".tmp", "wb") as f:
        f.write(ply_kopf(n_ges))
        for q in akt:
            NA = normalen_matrix(q["A"]); sel = q["wahl"]
            for i0 in range(0, q["L"].n, bloecke):
                i1 = min(q["L"].n, i0 + bloecke); s = sel[(sel >= i0) & (sel < i1)] - i0
                if not len(s): continue
                X, N, F = q["L"].block(i0, i1); X = X[s]; N = N[s] if N is not None else None; F = F[s] if F is not None else None
                M = X @ q["A"].T + q["b"]; out = np.zeros(len(M), DT); Nm = _norm(N.astype(np.float64) @ NA.T) if N is not None else np.zeros((len(M), 3))
                if sfm_aus: Ai, bi = aus_rahmen; Mo = M @ Ai.T + bi; Nm = _norm(Nm @ normalen_matrix(Ai).T) if N is not None else Nm
                else: Mo = M
                out["x"], out["y"], out["z"] = Mo[:, 0], Mo[:, 1], Mo[:, 2]; out["nx"], out["ny"], out["nz"] = Nm[:, 0], Nm[:, 1], Nm[:, 2]
                if F is not None: out["r"], out["g"], out["b"] = F[:, 0], F[:, 1], F[:, 2]
                f.write(out.tobytes()); qn[o:o + len(M)] = q["i"]
                if PM is not None: PM[o:o + len(M)] = M; PF[o:o + len(M)] = F if F is not None else 0
                o += len(M)
    os.replace(ply + ".tmp", ply); np.save(ply + ".quellen.npy", qn)
    if PM is not None:
        PM.flush(); PF.flush(); del PM, PF
        for n_ in ("punkte_modell", "punkte_farben"): os.replace(os.path.join(aus, n_ + ".npy.tmp"), os.path.join(aus, n_ + ".npy"))
    namen = [x["name"] for x in quellen]
    bericht["quellen"] = sorted(bericht["quellen"] + [q["z"] for q in Q], key=lambda z: namen.index(z["name"]))
    bericht["quellen_index"] = {str(i): n for i, n in enumerate(namen)}; bericht["sekunden"] = round(time.time() - t0, 1); bericht["ply"] = ply
    json.dump(bericht, open((ply + ".vereinigt.json") if sfm_aus else os.path.join(aus, "vereint.json"), "w"), indent=1, ensure_ascii=False, default=float)
    return bericht


# ---------------------------------------------------------------- Register
def register_pfad(objekt): return os.path.join(os.path.dirname(os.path.abspath(objekt)), "wolken.json")


def register_lesen(objekt):
    p = register_pfad(objekt)
    return json.load(open(p)) if os.path.exists(p) else {"zweck": "dichte Wolken dieses Objekts fuer tools/wolke_vereinigen.py (Reihenfolge = Vorrang, erste = Bezug)", "quellen": []}


def quelle_aus_text(t):
    teile = t.split("@"); name, _, pfad = teile[0].partition("=")
    if not name or not pfad: raise ValueError(f"'{t}': NAME=PFAD[@RAHMEN[@LAGETOR]] erwartet")
    return dict(name=name, pfad=pfad, rahmen=teile[1] if len(teile) > 1 and teile[1] else "modell", lagetor=teile[2] if len(teile) > 2 else "")


def anmelden(objekt, q, vorne=False):
    """Quelle eintragen; gleicher Name = ersetzen an alter Stelle. vorne=True: an den Anfang (Bezug)."""
    R = register_lesen(objekt); q = dict(q, angemeldet=time.strftime("%Y-%m-%d %H:%M")); namen = [x["name"] for x in R["quellen"]]
    if vorne: R["quellen"] = [q] + [x for x in R["quellen"] if x["name"] != q["name"]]
    elif q["name"] in namen: R["quellen"][namen.index(q["name"])] = q
    else: R["quellen"].append(q)
    json.dump(R, open(register_pfad(objekt), "w"), indent=1, ensure_ascii=False); return R


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pos", nargs="*", help="ALT: <basis.ply> <aus.ply>"); ap.add_argument("--objekt"); ap.add_argument("--aus"); ap.add_argument("--ausrichtung")
    ap.add_argument("--quelle", action="append", default=[], metavar="NAME=PFAD[@RAHMEN[@LAGETOR]]"); ap.add_argument("--anmelden", action="append", default=[])
    ap.add_argument("--vorne", action="store_true", help="--anmelden: als Bezug an den Anfang"); ap.add_argument("--voxel", type=float, default=0.02)
    ap.add_argument("--max_abw", type=float, default=0.05); ap.add_argument("--block", type=float, default=5.0); ap.add_argument("--stichprobe", type=int, default=300_000)
    ap.add_argument("--bloecke", type=int, default=2_000_000); ap.add_argument("--zonen_z", type=float, nargs=2, default=[3.0, 38.0]); ap.add_argument("--ohne_npy", action="store_true")
    ap.add_argument("--npy", help="ALT: zusaetzlich <name>_modell.npy + <name>_farben.npy")
    a = ap.parse_args()
    if a.objekt: a.objekt = _pfad(a.objekt, os.getcwd()) if os.path.exists(_pfad(a.objekt, os.getcwd())) else _pfad(a.objekt)     # Dienst laeuft nicht im Repo-Ordner
    if a.anmelden:
        if not a.objekt: ap.error("--anmelden braucht --objekt")
        for t in a.anmelden: R = anmelden(a.objekt, quelle_aus_text(t), a.vorne)
        print("ANGEMELDET:", ", ".join(x["name"] for x in R["quellen"]), "->", register_pfad(a.objekt)); return 0
    if len(a.pos) == 2:                                                           # alter Aufruf: alles im SfM-Rahmen der --ausrichtung
        if not a.ausrichtung: ap.error("alter Aufruf braucht --ausrichtung")
        r = "sfm:" + os.path.abspath(a.ausrichtung); qs = [dict(name="basis", pfad=os.path.abspath(a.pos[0]), rahmen=r)]
        for t in a.quelle:
            q = quelle_aus_text(t); q["pfad"] = os.path.abspath(q["pfad"])
            if "@" not in t: q["rahmen"] = r
            qs.append(q)
        A, b = rahmen_lesen(r); Ai = np.linalg.inv(A)
        B = vereinigen(qs, os.path.abspath(a.pos[1]), a.voxel, a.max_abw, a.block, a.stichprobe, a.bloecke, a.objekt, tuple(a.zonen_z), aus_rahmen=(Ai, -Ai @ b))
        if a.npy:
            L = Quelle(B["ply"]); X, _, F = L.block(0, L.n); np.save(a.npy + "_modell.npy", (X @ A.T + b).astype(np.float32)); np.save(a.npy + "_farben.npy", F)
    else:
        if not (a.objekt and a.aus): ap.error("--objekt und --aus noetig (oder alter Aufruf <basis.ply> <aus.ply> --ausrichtung)")
        qs = register_lesen(a.objekt)["quellen"] + [quelle_aus_text(t) for t in a.quelle]
        if not qs: print("KEINE QUELLE im Register", register_pfad(a.objekt)); return 2
        B = vereinigen(qs, os.path.abspath(a.aus), a.voxel, a.max_abw, a.block, a.stichprobe, a.bloecke, a.objekt, tuple(a.zonen_z), npy=not a.ohne_npy)
    for z in B["quellen"]: print(("OK        " if z.get("angenommen") else "NICHT     ") + json.dumps({k: v for k, v in z.items() if k != "bloecke_weg"}, ensure_ascii=False), flush=True)
    if B.get("zonen_zahlen"):
        print("ZONEN (Punkte; NAME|zugelassen = nach den Lagetoren):")
        for zn in B["zonen_zahlen"]["VEREINT"]: print(f"  {zn:20s} " + "  ".join(f"{q}={B['zonen_zahlen'][q][zn]}" for q in B["zonen_zahlen"]))
    print(f"VEREINIGT {B['punkte']} Punkte in {B['sekunden']} s -> {B['ply']}")
    if B["rot"]: print("ROT: vereint < beste Quelle in", json.dumps(B["rot"], ensure_ascii=False)); return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
