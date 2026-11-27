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
  (3) je Raumblock (--block m, Wuerfel): hat der Bezug dort >= 500 Punkte und die Quelle >= 50 Stichproben mit Ueberlapp (Ebene < 0,5 m), Median > --max_abw -> Block
      NACHPASSEN statt verwerfen (27.11. Nutzerbefund Anbau/Treppe/Steg: das alte Verwerfen nahm dort 0,8-1,0 Mio Handy-Punkte je Zone weg):
      block_icp (Punkt-zu-Ebene, Grenzen Verschiebung <= 0,6 m, Drehung <= 3 Grad, Median danach <= --max_abw); angewandt als STETIGES Feld (feld(): trilinear
      ueber Blockmitten, Stuetzstellen = nachgepasste Bloecke + gepruefte passende Bloecke mit 0) - starr je Block gab Naehte (Median 0,23 m);
      scheitert der ICP -> EIGENE SCHICHT: Quelle bleibt, nur Punkte <= r_frei (0,3 m) neben einer Bezugs-Ebene, aber > --max_abw davon = Doppelwand (grund 1), auch in Nachbarbloecken;
      DICHTERE QUELLE FUEHRT: hat die Quelle im Block >= FUEHRT_FAKTOR (ANNAHME 4) x so viele Punkte wie der Bezug, bleibt sie ganz und Bezugspunkte neben IHRER Flaeche fallen;
      ohne_zonen je Quelle (z. B. ["Dach"]: Dach nur Hauptnetz) -> grund 2.
  ZELLENTEST (rot, rc 3): je 5-m-Zelle und je Pruefzone (wolken.json "pruefzonen", kreis/zone) vereint >= Punkte jeder Quelle OHNE Begruendung (grund 0);
      Mutation BLOCKTOR_STRENG = True (altes Verwerfen ohne Grund) -> rot.
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


FUEHRT_FAKTOR = 4.0          # ANNAHME 27.11.: Quelle fuehrt einen Block, wenn sie dort >= 4x so viele Punkte hat wie der Bezug (Anbau: Handy 1,23 Mio gegen Hauptnetz 0,19 Mio)
BLOCKTOR_STRENG = False      # nur fuer den Mutationstest: alter Blocktor (ganzer Block weg, ohne Begruendung) -> Zellentest muss rot werden


def block_icp(P, baum, Xb, max_abw, max_t=0.6, max_grad=3.0, it=12, r=0.75):
    """Starre Nachpassung EINES Blocks der Quelle an die Bezugsflaeche (Punkt-zu-Ebene-ICP, kleine Drehung um den Blockschwerpunkt). Grenzen: Verschiebung <= max_t m,
    Drehung <= max_grad, >= 50 Paare, danach Median <= max_abw. Unbestimmte Richtungen (nur eine Wandrichtung) bleiben ungedreht/unverschoben (lstsq, rcond).
    Rueckgabe dict(ok, R, t (M' = M R^T + t), median_nachher_m, verschiebung_m, drehung_grad, paare | grund)."""
    c0 = P.mean(0); R = np.eye(3); t = np.zeros(3); d = None
    for _ in range(it):
        Q_ = (P - c0) @ R.T + c0 + t; d, nv, cc = _ebene(baum, Xb, Q_, r)
        ok = np.isfinite(d)
        if ok.sum() < 50: return dict(ok=False, grund=f"nur {int(ok.sum())} Paare")
        sch = max(3 * float(np.median(d[ok])), 0.05); ok &= d <= sch
        q = Q_[ok] - (c0 + t); n = nv[ok]; res = np.einsum("ni,ni->n", Q_[ok] - cc[ok], n)
        J = np.c_[np.cross(q, n), n]; x = np.linalg.lstsq(J, -res, rcond=1e-3)[0]
        import cv2
        dR = cv2.Rodrigues(x[:3].reshape(3, 1))[0]; R = dR @ R; t = t + x[3:]
        if np.linalg.norm(x) < 1e-4: break
    Q_ = (P - c0) @ R.T + c0 + t; d, _, _ = _ebene(baum, Xb, Q_, 0.5); ok = np.isfinite(d)
    med = float(np.median(d[ok])) if ok.sum() else float("inf"); ang = float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))
    tt = c0 - R @ c0 + t; vs = float(np.linalg.norm(t))
    erg = dict(R=R, t=tt, median_nachher_m=round(med, 4), verschiebung_m=round(vs, 3), drehung_grad=round(ang, 2), paare=int(ok.sum()))
    gr = [g for g, b in ((f"Median nachher {med:.3f} > {max_abw}", med > max_abw), (f"Verschiebung {vs:.2f} > {max_t} m", vs > max_t), (f"Drehung {ang:.1f} > {max_grad} Grad", ang > max_grad), (f"{int(ok.sum())} Paare < 50", ok.sum() < 50)) if b]
    erg.update(ok=not gr, grund="; ".join(gr)); return erg


def feld(M, T, null, block):
    """STETIGES Korrekturfeld (27.11., Naehte bei starrer Korrektur je Block: Median 0,23 m, 216 von 282 Grenzen > 10 cm): trilineare Interpolation ueber die
    Blockmitten; Stuetzstellen = nachgepasste Bloecke (Korrektur R p + t - p) und gepruefte passende Bloecke (0); andere Bloecke tragen nicht bei.
    Rueckgabe Verschiebung (n,3). Ohne Stuetzstelle in der Umgebung = 0."""
    if not T or len(M) == 0: return np.zeros_like(M)
    g = M / block - 0.5; b0 = np.floor(g); fr = g - b0; num = np.zeros_like(M); den = np.zeros(len(M))
    tks = np.array(sorted(T), np.int64); nks = np.array(sorted(null), np.int64)
    for ox in (0, 1):
        for oy in (0, 1):
            for oz in (0, 1):
                w = (fr[:, 0] if ox else 1 - fr[:, 0]) * (fr[:, 1] if oy else 1 - fr[:, 1]) * (fr[:, 2] if oz else 1 - fr[:, 2])
                kk = vkey((b0 + [ox, oy, oz] + 0.5) * block, block)
                inT = np.isin(kk, tks); inN = np.isin(kk, nks); den += w * (inT | inN)
                for k in np.unique(kk[inT]):
                    m = kk == k; R, t = T[int(k)]; num[m] += w[m, None] * (M[m] @ R.T + t - M[m])
    out = np.zeros_like(M); ok = den > 1e-9; out[ok] = num[ok] / den[ok, None]; return out


def naehte(T, belegt, block):
    """Spruenge der Blockkorrektur an den Blockgrenzen (Mitte jeder Seitenflaeche): |Korrektur Block - Korrektur Nachbar| (Nachbar ohne Korrektur = 0).
    Grosse Spruenge = Stufe in einer Flaeche, die ueber zwei Bloecke reicht (ANZEIGE, kein Tor)."""
    sp = []
    for k, (R, t) in T.items():
        c = vmitte([k], block)[0]
        for ax in range(3):
            for sg in (-1, 1):
                f = c.copy(); f[ax] += sg * block / 2; nb = c.copy(); nb[ax] += sg * block; kn = int(vkey(nb[None], block)[0])
                if kn not in belegt: continue
                a_ = f @ R.T + t - f; b_ = (f @ T[kn][0].T + T[kn][1] - f) if kn in T else np.zeros(3); sp.append(float(np.linalg.norm(a_ - b_)))
    if not sp: return {}
    sp = np.array(sp); return dict(anzahl=int(len(sp)), median_m=round(float(np.median(sp)), 3), max_m=round(float(sp.max()), 3), ueber_10cm=int((sp > 0.10).sum()))


def _ebene(baum, Xb, S, r, k=8, k_min=5):
    """wie abstand_ebene, dazu Ebenenpunkt (Schwerpunkt der Nachbarn) je Punkt."""
    d, ii = baum.query(S, k=k, distance_upper_bound=r, workers=-1); gut = np.isfinite(d); ok = gut.sum(1) >= k_min
    out = np.full(len(S), np.inf); nrm = np.zeros((len(S), 3)); cc = np.zeros((len(S), 3))
    if not ok.any(): return out, nrm, cc
    ii = np.where(gut, ii, ii[:, :1]); P = Xb[ii[ok]]; w = gut[ok][..., None].astype(float); c = (P * w).sum(1) / w.sum(1)
    D = (P - c[:, None]) * w; _, V = np.linalg.eigh(np.einsum("nki,nkj->nij", D, D)); nv = V[:, :, 0]
    out[ok] = np.abs(np.einsum("ni,ni->n", S[ok] - c, nv)); nrm[ok] = nv; cc[ok] = c; return out, nrm, cc


def _zell_zaehlen(keys, block, voxel):
    """{zellschluessel: Anzahl} - Zelle nach VOXELMITTE (Zellen bestehen so aus ganzen Voxeln, Garantie des Voxel-Gewinners gilt exakt)."""
    if len(keys) == 0: return np.zeros(0, np.int64), np.zeros(0, np.int64)
    uk, cnt = np.unique(keys, return_counts=True); zk = vkey(vmitte(uk, voxel), block); u2, inv = np.unique(zk, return_inverse=True)
    return u2, np.bincount(inv.ravel(), weights=cnt).astype(np.int64)


def _pz_zaehlen(pz, keys, voxel):
    if len(keys) == 0 or not pz: return [0] * len(pz)
    uk, cnt = np.unique(keys, return_counts=True); C = vmitte(uk, voxel); return [int(cnt[pz_maske(Z, C)].sum()) for Z in pz]


def pz_maske(Z, M):
    if Z["art"] == "kreis": return (np.hypot(M[:, 0] - Z["mitte"][0], M[:, 1] - Z["mitte"][1]) <= Z["r"]) & (M[:, 2] >= Z["z"][0]) & (M[:, 2] <= Z["z"][1])
    return in_zone(Z, M)


def zellen_soll(Q, block, voxel, pz):
    """Je Quelle: Punkte OHNE anerkannte Begruendung (grund 0 = behalten, 4 = strenger Blocktor) je 5-m-Zelle und je Pruefzone.
    Anerkannt: 1 Doppelwand (nahe der Bezugsflaeche), 2 Zone ausgeschlossen (z. B. Dach nur Hauptnetz), 3 ganze Quelle abgelehnt (Lagetor)."""
    out = []
    for q in Q:
        g = q.get("grund"); m = np.ones(len(q["keys"]), bool) if g is None else np.isin(g, (0, 4))
        out.append((q["name"], _zell_zaehlen(q["keys"][m], block, voxel), _pz_zaehlen(pz, q["keys"][m], voxel)))
    return out


def zellen_urteil(soll, keys_v, block, voxel, pz):
    """ROTER Zellentest (Nutzerbefund 27.11. Anbau/Treppe): keine 5-m-Zelle und keine Pruefzone hat vereint weniger Punkte als eine Quelle ohne Begruendung."""
    uv, cv = _zell_zaehlen(keys_v, block, voxel); rot = []
    for name, (uk, ck), _ in soll:
        pos = np.searchsorted(uv, uk); hat = (pos < len(uv)) & (uv[np.minimum(pos, len(uv) - 1)] == uk); nv = np.where(hat, cv[np.minimum(pos, len(uv) - 1)], 0)
        for i in np.flatnonzero(nv < ck)[:50]: rot.append(dict(zelle=[round(float(c), 1) for c in vmitte([uk[i]], block)[0]], quelle=name, quelle_n=int(ck[i]), vereint=int(nv[i])))
    pv = _pz_zaehlen(pz, keys_v, voxel); pzb = []
    for j, Z in enumerate(pz):
        e = dict(name=Z["name"], vereint=pv[j], **{f"{n}_ohne_grund": c[j] for n, _, c in soll}); pzb.append(e)
        for n, _, c in soll:
            if pv[j] < c[j]: rot.append(dict(pruefzone=Z["name"], quelle=n, quelle_n=c[j], vereint=pv[j]))
    return rot, pzb


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
               aus_rahmen=None, npy=True, basis=ROOT, log=lambda s: print(s, flush=True), r_frei=0.3, pruefzonen=None):
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
        Q.append(dict(i=i, name=q["name"], ohne_zonen=q.get("ohne_zonen", []), L=L, A=A, b=b, keys=keys, bk=bk, S=S, Sb=bk[idx], z=z, behalten=np.ones(L.n, bool)))
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
        d, _ = abstand_ebene(baum, Xb, q["S"], r=0.5); ue = np.isfinite(d); nach = []; q["null"] = set()
        for bkey in np.unique(q["Sb"]):                                            # Blocktor: abweichende Bloecke markieren
            m = (q["Sb"] == bkey) & ue
            if bez_block.get(int(bkey), 0) >= 500 and m.sum() >= 50:
                mb = float(np.median(d[m]))
                if mb > max_abw: nach.append((int(bkey), mb, int(m.sum())))
                else: q["null"].add(int(bkey))                                     # geprueft und passend = Stuetzstelle "keine Korrektur" fuer das Feld
        q["T"] = {}; q["frei"] = set(); q["z"]["bloecke_nachgepasst"] = []; q["z"]["bloecke_eigene_schicht"] = []
        for k, mb, n in nach:                                                      # 27.11. (Nutzerbefund Anbau/Treppe): nicht verwerfen, sondern je Block nachpassen
            P = q["S"][q["Sb"] == k]; T = block_icp(P, baum, Xb, max_abw)
            mi = [round(float(c), 1) for c in vmitte([k], block)[0]]
            if T["ok"] and not BLOCKTOR_STRENG: q["T"][k] = (T["R"], T["t"]); q["z"]["bloecke_nachgepasst"].append(dict(mitte=mi, median_vorher_m=round(mb, 3), **{x: T[x] for x in ("median_nachher_m", "verschiebung_m", "drehung_grad", "paare")}))
            else: q["frei"].add(k); q["z"]["bloecke_eigene_schicht"].append(dict(mitte=mi, median_m=round(mb, 3), stichproben=n, grund=T.get("grund")))
        q["z"]["naehte_je_block"] = naehte(q["T"], set(np.unique(q["bk"]).tolist()), block)     # Spruenge, wenn jeder Block starr fuer sich korrigiert wuerde
        if q["T"]:                                                                 # stetiges Feld: Rest je nachgepasstem Block nach dem Glaetten
            rest = []
            for k in q["T"]:
                P = q["S"][q["Sb"] == k]; dd, _ = abstand_ebene(baum, Xb, P + feld(P, q["T"], q["null"], block), r=0.5); f_ = np.isfinite(dd)
                if f_.sum() >= 20: rest.append(float(np.median(dd[f_])))
            q["z"]["feld_rest_median_m"] = dict(bloecke=len(rest), median=round(float(np.median(rest)), 4) if rest else None, max=round(float(np.max(rest)), 4) if rest else None,
                                                ueber_max_abw=int(sum(r_ > max_abw for r_ in rest)))
        q["z"]["naehte"] = q["z"]["feld_rest_median_m"] if q["T"] else {}
        log(f"OK {q['name']}: Median {med:.4f} m, Ueberlapp {int(ue.sum())}, Bloecke nachgepasst {len(q['T'])}, eigene Schicht {len(q['frei'])}, Naehte {q['z']['naehte']}")
    zonen = zonen_bauen(objekt, bez["S"], zonen_z) if objekt else []; zn_name = {Z["name"]: Z for Z in zonen}
    for q in Q[1:]:                                                                # zweiter Durchgang: Nachpassen anwenden, Doppelwand/Zonen begruenden
        if not q["z"].get("angenommen"): q["grund"] = np.full(q["L"].n, 3, np.uint8); continue
        q["grund"] = np.zeros(q["L"].n, np.uint8); oz = [zn_name[n] for n in q.get("ohne_zonen", []) if n in zn_name]
        if not (q["T"] or q["frei"] or oz): continue
        off27 = np.array([[i, j, k] for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)], float) * block
        tk = np.unique(vkey((vmitte(np.array(sorted(q["T"]), np.int64), block)[:, None, :] + off27[None]).reshape(-1, 3), block)) if q["T"] else np.zeros(0, np.int64)   # Traeger des Feldes
        fk = np.array(sorted(q["frei"]), np.int64)
        if len(fk) or len(tk): fk = np.union1d(fk, tk)                             # Doppelwand-Regel auch im Feld-Traeger (Reste an Kanten des Feldes)
        if len(fk):                                                                # Nachbarbloecke gescheiterter Bloecke mitpruefen (Blockgrenze teilt eine Wand, Test 27.11.)
            off = np.array([[i, j, k] for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)], float) * block
            nb_ = np.unique(vkey((vmitte(fk, block)[:, None, :] + off[None]).reshape(-1, 3), block)); fk = nb_
        # DICHTERE QUELLE FUEHRT (Nutzer 27.11.: "keine Zelle verliert gegen die dichtere Quelle"): hat die Quelle im Block >= 2x so viele Punkte wie der Bezug,
        # (FUEHRT_FAKTOR, ANNAHME 4; nie in gescheiterten = verrauschten Bloecken) bleibt sie dort ganz; stattdessen fallen Bezugspunkte, die neben IHRER Flaeche liegen (gleiche Doppelwand-Regel, Rollen getauscht).
        uq, cq = np.unique(q["bk"], return_counts=True); nq = dict(zip(uq.tolist(), cq.tolist()))
        fuehrt = np.array(sorted(k for k in fk.tolist() if k not in q["frei"] and nq.get(k, 0) >= FUEHRT_FAKTOR * bez_block.get(k, 0)), np.int64) if not BLOCKTOR_STRENG else np.zeros(0, np.int64)
        q["z"]["bloecke_quelle_fuehrt"] = int(len(fuehrt)); Pf = []
        for i0 in range(0, q["L"].n, bloecke):
            i1 = min(q["L"].n, i0 + bloecke); bkp = q["bk"][i0:i1]; mt = np.isin(bkp, tk); mf = np.isin(bkp, fk); mfu = np.isin(bkp, fuehrt); mf &= ~mfu
            if not (mt.any() or mf.any() or mfu.any() or oz): continue
            if BLOCKTOR_STRENG: mf &= np.isin(bkp, np.array(sorted(q["frei"]), np.int64))
            X, _, _ = q["L"].block(i0, i1); M = X @ q["A"].T + q["b"]
            if mt.any(): M[mt] += feld(M[mt], q["T"], q["null"], block); q["keys"][i0:i1][mt] = vkey(M[mt], voxel)
            g = q["grund"][i0:i1]
            if mf.any():
                if BLOCKTOR_STRENG: g[mf] = 4
                else:                                                              # nahe (< r_frei) an der Bezugsflaeche, aber > max_abw neben ihr (oder dort keine Ebene) = Doppelwand
                    de, _, _ = _ebene(baum, Xb, M[mf], 0.5)                       # Ebene nur, wo der Bezug >= 5 Punkte in 0,5 m hat; duenner Bezug = keine Wand = Quelle bleibt
                    g[np.flatnonzero(mf)[np.isfinite(de) & (de > max_abw) & (de <= r_frei)]] = 1
            for Z in oz: g[in_zone(Z, M) & (g == 0)] = 2
            if mfu.any(): Pf.append(M[mfu & (g == 0)])
        q["Pf"] = (np.concatenate(Pf) if Pf else np.zeros((0, 3))), fuehrt
        q["behalten"] &= q["grund"] == 0
        q["z"]["punkte_weg"] = {n_: int((q["grund"] == c).sum()) for c, n_ in ((1, "doppelwand"), (2, "zone_ohne"), (4, "blocktor_streng")) if (q["grund"] == c).any()}
        log(f"  {q['name']}: weg {q['z']['punkte_weg']}")
    bez["grund"] = np.zeros(bez["L"].n, np.uint8); weg_b = 0
    for q in Q[1:]:                                                                # Bezugspunkte neben der Flaeche einer fuehrenden (dichteren) Quelle
        Pf, fuehrt = q.pop("Pf", (np.zeros((0, 3)), np.zeros(0, np.int64)))
        if len(Pf) < 50: continue
        bq = cKDTree(Pf)
        for i0 in range(0, bez["L"].n, bloecke):
            i1 = min(bez["L"].n, i0 + bloecke); mb_ = np.isin(bez["bk"][i0:i1], fuehrt)
            if not mb_.any(): continue
            X, _, _ = bez["L"].block(i0, i1); M = X[mb_] @ bez["A"].T + bez["b"]; de, _, _ = _ebene(bq, Pf, M, 0.5)
            hit = np.flatnonzero(mb_)[np.isfinite(de) & (de > max_abw) & (de <= r_frei)]; bez["grund"][i0:i1][hit] = 1; weg_b += len(hit)
        del bq
    bez["behalten"] &= bez["grund"] == 0; bez["z"]["punkte_weg"] = {"doppelwand_neben_dichterer_quelle": int(weg_b)} if weg_b else {}
    if weg_b: log(f"  {bez['name']}: weg {bez['z']['punkte_weg']}")
    del baum, Xb
    akt = [q for q in Q if q["z"].get("angenommen")]; zahlen = {}
    if objekt:                                                                     # Zonen der Quellen VOR dem Gewinnerschritt (danach Schluessel frei = weniger Spitzenspeicher)
        for q in Q: zahlen[q["name"]] = zonen_zaehlen(zonen, q["keys"], voxel)
        for q in akt: zahlen[q["name"] + "|zugelassen"] = zonen_zaehlen(zonen, q["keys"][q["behalten"]], voxel)
    pz = [dict(z_, art=z_.get("art", "kreis")) for z_ in (pruefzonen or [])]
    soll_z = zellen_soll(Q, block, voxel, pz)                                        # je 5-m-Zelle + Pruefzone: Punkte ohne Begruendung je Quelle
    keys = np.concatenate([q["keys"][q["behalten"]] for q in akt]); src = np.concatenate([np.full(int(q["behalten"].sum()), k, np.uint8) for k, q in enumerate(akt)])
    for q in Q: q.pop("keys", None); q.pop("grund", None)
    halt = gewinner(keys, src, np.arange(len(akt))); off = 0; del src
    for q in akt:
        nb = int(q["behalten"].sum()); w = halt[off:off + nb]; off += nb; q["wahl"] = np.flatnonzero(q["behalten"])[w]; q["z"]["punkte_vereint"] = int(len(q["wahl"]))
    keys_v = keys[halt]; del keys, halt
    n_ges = sum(len(q["wahl"]) for q in akt); bericht["punkte"] = int(n_ges); log(f"Gewinner je Voxel: {n_ges} Punkte ({time.time() - t0:.0f} s)")
    bericht["zellen_rot"], bericht["pruefzonen"] = zellen_urteil(soll_z, keys_v, block, voxel, pz)
    if objekt:
        zahlen["VEREINT"] = zonen_zaehlen(zonen, keys_v, voxel)
        bericht["zonen"] = zonen; bericht["zonen_zahlen"] = zahlen; bericht["rot"] = zonen_urteil(zahlen, [q["name"] + "|zugelassen" for q in akt])
    else: bericht["rot"] = []
    bericht["rot"] = bericht["rot"] + [dict(zelle=z_) for z_ in bericht["zellen_rot"]]
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
                if q.get("T"): M = M + feld(M, q["T"], q["null"], block)            # Normalen nicht mitgedreht (Drehung <= 3 Grad)
                if sfm_aus: Ai, bi = aus_rahmen; Mo = M @ Ai.T + bi; Nm = _norm(Nm @ normalen_matrix(Ai).T) if N is not None else Nm
                else: Mo = M
                out["x"], out["y"], out["z"] = Mo[:, 0], Mo[:, 1], Mo[:, 2]; out["nx"], out["ny"], out["nz"] = Nm[:, 0], Nm[:, 1], Nm[:, 2]
                if F is not None: out["r"], out["g"], out["b"] = F[:, 0], F[:, 1], F[:, 2]
                f.write(out.tobytes()); qn[o:o + len(M)] = q["i"]
                if PM is not None: PM[o:o + len(M)] = M; PF[o:o + len(M)] = F if F is not None else 0
                o += len(M)
    for q in Q: q.pop("bk", None)
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
        B = vereinigen(qs, os.path.abspath(a.aus), a.voxel, a.max_abw, a.block, a.stichprobe, a.bloecke, a.objekt, tuple(a.zonen_z), npy=not a.ohne_npy,
                       pruefzonen=register_lesen(a.objekt).get("pruefzonen"))
    for z in B["quellen"]: print(("OK        " if z.get("angenommen") else "NICHT     ") + json.dumps({k: v for k, v in z.items() if k != "bloecke_weg"}, ensure_ascii=False), flush=True)
    if B.get("zonen_zahlen"):
        print("ZONEN (Punkte; NAME|zugelassen = nach den Lagetoren):")
        for zn in B["zonen_zahlen"]["VEREINT"]: print(f"  {zn:20s} " + "  ".join(f"{q}={B['zonen_zahlen'][q][zn]}" for q in B["zonen_zahlen"]))
    print(f"VEREINIGT {B['punkte']} Punkte in {B['sekunden']} s -> {B['ply']}")
    if B["rot"]: print("ROT: vereint < beste Quelle in", json.dumps(B["rot"], ensure_ascii=False)); return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
