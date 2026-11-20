#!/usr/bin/env python3
"""konvergenz_bericht.py - Konvergenz je Bau: wird das Modell von Lauf zu Lauf besser? (Nutzerziel 9.11.: 'konvergieren gegen ein druckbares Modell, alle Kanten beschrieben')

Je Lauf eine Zeile in modelle/<objekt>/konvergenz.jsonl, Vergleich mit der letzten Zeile, Exit 3 bei Rueckschritt.
Kennzahlen (alle modellfremd belegt, keine Selbstbezuege):
  1. Kanten-Recall je Hoehenband: Anteil der Kantengitter-Punkte (3D-Kanten aus allen Fotos trianguliert), die
     naeher als --tol am Modell liegen. "Fotokante hat Modell" (Regel 'nie belegte Kanten verlieren').
  2. Kanten-Praezision je Hoehenband: Anteil der Modell-Formkanten (Flaechenwinkel > --winkel), die naeher als --tol an
     einer Gitterkante liegen. "Modellkante hat Fotobeleg". Nur aussagekraeftig, wo das Gitter dicht ist (Dach > 15 m: Abdeckung ~0,2)
     -> je Band wird die Gitterdichte (Punkte je m Modellkante) mitgeschrieben.
  3. Pruefstand: bestanden, Anzahl ok/fehler/widerspruch (pruefbericht.json).
  4. Bauteil-Sichtpruefung (optional --teile_sicht JSON von tools/teile_sichtpruefung.py): GRUEN/ROT/UNGEPRUEFT.
     Zaehlt erst als Konvergenzmass, wenn das Werkzeug als Gate bewiesen ist (Feld 'gate_bewiesen' in der Eingabe oder --ts_gate).
  5. foto_diff je kalibriertem Foto (audit/foto_diff_<foto>.json): rot/gelb-Anteil.
Druckschwelle: Kanten feiner als --min_kante (Standard 0,035 m = 0,4-mm-Duese in H0) sind nicht druckbar und zaehlen nicht:
  Gittersegmente kuerzer als --min_kante werden verworfen.

Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/konvergenz_bericht.py <objekt> --stl STL_IN_M_ODER_H0 [--skala 0.087]
        --gitter SEGMENTE.json [--teile_sicht JSON] [--wolke VOLLE_WOLKE.npy --teile_dir BAUTEILE_STL_DIR [--nah 1.0 --beleg 0.15] [--kameras KAM.json --sicht_min 3 --sicht_max 100]] [--tol 0.10] [--winkel 25] [--baender 0,5,10,15,20,40] [--etikett TEXT] [--trocken]
  --stl: Modell; --skala multipliziert die Koordinaten (H0-STL in mm -> m: 0.087). Modell und Gitter muessen im selben Rahmen liegen
  (Kaufhaus: H0-STL * 0,087 = lot2-Rahmen, wie der Viewer). --trocken: nichts anhaengen.
Rueckschritt = eine Kennzahl faellt um mehr als --rausch (Standard 0,01) gegen die letzte Zeile (Recall/Praezision je Band mit >= 200 Punkten,
GRUEN-Anteil, Pruefstand). Exit 3, Grund in der Zeile ('rueckschritt').
Pflicht: --stl und --gitter (Kantengitter, npy). Weitere: --teile_sicht, --tol 0.10, --winkel 25, --min_kante 0.035, --baender, --rausch, --etikett.
Oder `tools/py tools/konvergenz_bericht.py ...` (torch/trimesh -> venv-seg). Exit: 0 = kein Rueckschritt, 1 = Aufruf falsch, 3 = Rueckschritt.
"""
import sys, os, json, time, subprocess
import numpy as np

a = sys.argv
def opt(k, d=None, t=str):
    return t(a[a.index(k) + 1]) if k in a else d

if len(a) < 2 or a[1].startswith("-"):
    print(__doc__); sys.exit(1)
OBJ = a[1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODIR = os.path.join(ROOT, "modelle", OBJ)
STL = opt("--stl"); SK = opt("--skala", 1.0, float); GIT = opt("--gitter"); TS = opt("--teile_sicht")
TOL = opt("--tol", 0.10, float); WINKEL = opt("--winkel", 25.0, float); MINK = opt("--min_kante", 0.035, float)
BAND = [float(x) for x in opt("--baender", "0,5,10,15,20,40").split(",")]
RAUSCH = opt("--rausch", 0.01, float); ETIKETT = opt("--etikett", ""); TROCKEN = "--trocken" in a
if not STL or not GIT:
    print("--stl und --gitter sind Pflicht"); sys.exit(1)

import trimesh, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gpu_slot; gpu_slot.belegen("konvergenz_bericht")   # gemeinsame GPU-Schlange (10.11.)
from gpu_knn import min_abstand
assert torch.cuda.is_available(), "GPU erwartet (Nutzerregel: neue Rechenwerkzeuge auf der GPU)"

def entlang(P0, P1, schritt=0.05):
    """Punkte entlang von Segmenten (je Segment mind. 2)."""
    L = np.linalg.norm(P1 - P0, axis=1); n = np.maximum(2, np.ceil(L / schritt).astype(int))
    idx = np.repeat(np.arange(len(P0)), n); t = np.concatenate([np.linspace(0, 1, k) for k in n])
    return (P0[idx] + (P1[idx] - P0[idx]) * t[:, None]).astype(np.float32)

def md(Q, X):
    d = min_abstand(Q, X)
    return np.asarray(d.cpu() if hasattr(d, "cpu") else d)

# Modell
m = trimesh.load(STL, force="mesh"); m.apply_scale(SK)
OBF = m.sample(1_500_000).astype(np.float32)
sel = m.face_adjacency_angles > np.radians(WINKEL)
E = m.vertices[m.face_adjacency_edges[sel]]
lang = np.linalg.norm(E[:, 1] - E[:, 0], axis=1) >= MINK
MK = entlang(E[lang, 0], E[lang, 1])
# Gitter
S = json.load(open(GIT))["segmente"]
G0 = np.array([s[0] for s in S], float); G1 = np.array([s[1] for s in S], float)
gl = np.linalg.norm(G1 - G0, axis=1) >= MINK
GP = entlang(G0[gl], G1[gl])

t0 = time.time()
d_rec = md(GP, OBF)    # Gitterpunkt -> Modelloberflaeche
d_pra = md(MK, GP)     # Modellkante -> Gitter
baender = []
for lo, hi in zip(BAND[:-1], BAND[1:]):
    g = (GP[:, 2] >= lo) & (GP[:, 2] < hi); k = (MK[:, 2] >= lo) & (MK[:, 2] < hi)
    baender.append({"band": f"{lo:g}-{hi:g}", "gitter_pkt": int(g.sum()), "modellkante_pkt": int(k.sum()),
                    "recall": round(float((d_rec[g] < TOL).mean()), 4) if g.sum() else None,
                    "praezision": round(float((d_pra[k] < TOL).mean()), 4) if k.sum() else None,
                    "gitterdichte": round(float(g.sum() / max(k.sum(), 1)), 3)})
gesamt = {"recall": round(float((d_rec < TOL).mean()), 4), "praezision": round(float((d_pra < TOL).mean()), 4)}

# Pruefstand
pb = {}
pf = os.path.join(ODIR, "pruefbericht.json")
if os.path.exists(pf):
    d = json.load(open(pf)); st = [p.get("status", "ok" if p.get("ok") else "fehler") for p in d.get("pruefungen", [])]
    pb = {"bestanden": bool(d.get("bestanden")), "n": len(st), "ok": sum(1 for p in d["pruefungen"] if p.get("ok")),
          "widerspruch": st.count("widerspruch")}
# Bauteil-Sichtpruefung
ts = None
if TS and os.path.exists(TS):
    d = json.load(open(TS)); u = [t.get("urteil") for t in d.get("teile", []) if t.get("typ") != "GANZ"]
    ts = {"datei": TS, "gruen": u.count("GRUEN"), "rot": u.count("ROT"), "ungeprueft": u.count("UNGEPRUEFT"),
          "gate_bewiesen": bool(d.get("gate_bewiesen") or "--ts_gate" in a),
          "rot_teile": sorted(t["typ"] for t in d.get("teile", []) if t.get("urteil") == "ROT")}
# foto_diff
fd = {}
for f in sorted(os.listdir(os.path.join(ODIR, "audit"))):
    if f.startswith("foto_diff_") and f.endswith(".json"):
        d = json.load(open(os.path.join(ODIR, "audit", f)))
        fd[d.get("foto", f[10:-5])] = {"rot": d.get("anteil_modellkanten_ohne_foto"), "gelb": d.get("anteil_fotokanten_ohne_modell")}

# 6. Wolkenbeleg je Bauteil (generischer Fehlerfinder, 9.11.: Staffelgiebel/Erker fielen hier ohne Handarbeit auf):
#    Anteil der Modellflaeche MIT Wolkendaten in < --nah m, die naeher als --beleg m an der Wolke liegt. Rueckseiten ohne Daten zaehlen nicht.
#    Niedriger Wert = Teil steht neben echten Daten, trifft sie aber nicht (falsche Form/Lage). Nur Hinweisliste, bis per Synth + 2. Objekt bewiesen.
teile = None
WOLKE = opt("--wolke"); TDIR = opt("--teile_dir")
if WOLKE and TDIR and os.path.isdir(TDIR):
    Wv = np.load(WOLKE, mmap_mode="r")[:, :3].astype(np.float32)
    zw = float(Wv[:, 2].max())
    NAH = opt("--nah", 1.0, float); BEL = opt("--beleg", 0.15, float)
    # L-KR4 (10.11.): nur Flaeche zaehlen, die zu mindestens --sicht_min Kameras (Zentren C aus --kameras) hin zeigt und < --sicht_max m entfernt ist.
    # Verdeckte Rueckseiten (Normale ins Gebaeude) konnten sonst auf die Wolke geschoben werden und hoben den Beleg ohne Formgewinn.
    KAMF = opt("--kameras"); CC = None
    if KAMF and os.path.exists(KAMF):
        import torch
        _k = json.load(open(KAMF)); _k = _k.get("kameras", _k) if isinstance(_k, dict) else _k
        _vals = _k.values() if isinstance(_k, dict) else _k
        CC = np.array([v["C"] for v in _vals if "C" in v], np.float32)
        DEV = "cuda" if torch.cuda.is_available() else "cpu"; CCt = torch.from_numpy(CC).to(DEV)
        SMIN = opt("--sicht_min", 3, int); SMAX = opt("--sicht_max", 100.0, float)
        # Verdeckung (10.11. nachts, L-KR17): nur Normale-zur-Kamera liess Flaechen IM Nachbarteil zaehlen (Gesimsenden im Helm: Gewinn +0,064 'rein metrisch').
        # Je Kamera Kugel-Tiefenkarte des GANZEN Modells (OBF-Stichprobe, --sicht_grad Winkelraster, Minimum je Zelle, GPU); Punkt sichtbar, wenn
        # sein Abstand <= Tiefe + 0,15 m + 1 % Abstand. --ohne_verdeckung = alte Messart.
        VERD = "--ohne_verdeckung" not in a
        # Verdeckung (10.11. nachts, L-KR17): nur 'Normale zur Kamera' liess Flaechen IM Nachbarteil zaehlen (Gesimsenden im Helm: +0,064 'rein metrisch').
        # Exakter Strahltest Punkt -> Kamera gegen das GANZE Modell (trimesh/Embree). Kugel-Tiefenkarten auf der GPU wurden verworfen:
        # fein = Loecher (Innenwuerfel 42 % sichtbar), mehrstufig = zu konservativ (Satteldach 7 % statt exakt 34 %).
        # Je Punkt Abbruch, sobald --sicht_min Kameras ihn sehen. Beweis: Innen-/Hinterwuerfel 0 %, Wuerfel vor der Fassade sichtbar.
        RAY = m.ray if VERD else None
    def sichtbar(P, N):
        if CC is None: return np.ones(len(P), bool)
        Pt_ = torch.from_numpy(P).to(DEV); Nt_ = torch.from_numpy(N.astype(np.float32)).to(DEV); n = torch.zeros(len(P), dtype=torch.int32, device=DEV)
        if RAY is None:
            for i in range(0, len(CC), 64):
                V = CCt[i:i + 64][None, :, :] - Pt_[:, None, :]                       # Punkt -> Kamera
                ok = ((V * Nt_[:, None, :]).sum(-1) > 0) & (V.norm(dim=-1) < SMAX)
                n += ok.sum(1, dtype=torch.int32)
            return (n >= SMIN).cpu().numpy()
        P64 = P.astype(np.float64); N64 = N.astype(np.float64); nv = np.zeros(len(P), np.int32)
        for c in CC[np.random.default_rng(0).permutation(len(CC))]:
            offen = np.nonzero(nv < SMIN)[0]
            if len(offen) == 0: break
            V = c.astype(np.float64) - P64[offen]; d = np.linalg.norm(V, axis=1)
            ok = ((V * N64[offen]).sum(1) > 0) & (d < SMAX) & (d > 0.2)
            idx = offen[ok]
            if len(idx) == 0: continue
            dv = V[ok] / d[ok, None]; o = P64[idx] + dv * 0.05
            loc, ri, _ = RAY.intersects_location(o, dv, multiple_hits=False)
            frei = np.ones(len(idx), bool)
            if len(ri): frei[ri] = np.linalg.norm(loc - o[ri], axis=1) >= d[ok][ri] - 0.15
            nv[idx[frei]] += 1
        return nv >= SMIN
    # Rangwert fuer die Kreis-Zielwahl (Nutzer 10.11.): nur Flaeche, die die Wolke sieht und die keine Brandwand ist (LoD2-Nachbarn,
    # tools/nachbarn_modellrahmen.py). Die Tor-Groessen (beleg, kanten_*) bleiben unveraendert - nur zusaetzliche Felder rang_*.
    NBF = opt("--nachbarn"); NB = None
    if NBF and os.path.exists(NBF):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from nachbarn_modellrahmen import brandwand as _brandwand
        NB = trimesh.load(NBF, force="mesh")
    # Vorgebaut (10.11., Rumpf-Frontbild): Flaeche, deren Normalenstrahl innerhalb 1,5 m ein ANDERES Teil trifft (Rumpfwand hinter Erker,
    # Balkon, Laube), ist von aussen nie zu sehen - zaehlt im Rangwert nicht (sonst gilt der Rumpf wegen verdeckter Wand als 'schwaechstes Teil').
    _alle = {f: trimesh.load(os.path.join(TDIR, f), force="mesh") for f in sorted(os.listdir(TDIR)) if f.endswith(".stl") and "ausschnitt" not in f}
    for _m in _alle.values(): _m.apply_scale(SK)
    teile = []
    for f in sorted(os.listdir(TDIR)):
        if not f.endswith(".stl") or "ausschnitt" in f:
            continue
        tm = _alle[f]
        Pt, fi = tm.sample(60000, return_index=True); Pt = Pt.astype(np.float32); dt = md(Pt, Wv)
        vis = sichtbar(Pt, tm.face_normals[fi]); nah = (dt < NAH) & vis
        bw = _brandwand(Pt, tm.face_normals[fi], NB) if NB is not None else np.zeros(len(Pt), bool)
        _rest = trimesh.util.concatenate([v for k_, v in _alle.items() if k_ != f]) if len(_alle) > 1 else None
        vg = _brandwand(Pt, tm.face_normals[fi], _rest, weite=1.5, start=-0.02, min_d=0.05) if (_rest is not None and NBF) else np.zeros(len(Pt), bool)
        nf = nah & ~bw & ~vg
        teile.append({"teil": f[:-4], "anteil_mit_daten": round(float(nah.mean()), 3), "anteil_sichtbar": round(float(vis.mean()), 3),
                      "anteil_brandwand": round(float(bw.mean()), 3), "anteil_vorgebaut": round(float(vg.mean()), 3), "rang_beleg": round(float((dt[nf] < BEL).mean()), 3) if nf.sum() >= 50 else None,
                      "beleg": round(float((dt[nah] < BEL).mean()), 3) if nah.any() else None,
                      "median_m": round(float(np.median(dt[nah])), 3) if nah.any() else None,
                      "ueber_wolke_z": round(float((Pt[:, 2] > zw).mean()), 3)})
    # 7. Fotokanten je Bauteil (10.11.: Wolkenbeleg ist bei ~0,6 ausgereizt - Bogen/Dach/Erker/Helm Gewinn ~0; Form steht in den Fotokanten).
    #    Gitterpunkte (Kantengitter aus Fotos) werden dem naechsten Teil zugeordnet (< --nah m).
    #    kanten_recall = Anteil dieser Gitterpunkte, die < --tol an der Teiloberflaeche liegen (Fotokante vom Teil erklaert).
    #    kanten_praez  = Anteil der Formkanten des Teils (> --winkel, kamera-zugewandt), die < --tol an einem Gitterpunkt liegen (Teilkante im Foto belegt).
    if True:
        namen = [t["teil"] for t in teile]; dmin = np.full(len(GP), np.inf, np.float32); wer = np.full(len(GP), -1, np.int32); pr = {}; pr2 = {}
        for i, nm in enumerate(namen):
            tm = trimesh.load(os.path.join(TDIR, nm + ".stl"), force="mesh"); tm.apply_scale(SK)
            d = md(GP, tm.sample(80000).astype(np.float32)); b_ = d < dmin; dmin[b_] = d[b_]; wer[b_] = i
            sl = tm.face_adjacency_angles > np.radians(WINKEL); Et = tm.vertices[tm.face_adjacency_edges[sl]]
            if len(Et):
                fa = tm.face_adjacency[sl]; nm2 = tm.face_normals[fa[:, 0]] + tm.face_normals[fa[:, 1]]
                ln = np.linalg.norm(Et[:, 1] - Et[:, 0], axis=1) >= MINK; Et, nm2 = Et[ln], nm2[ln]
                mid = ((Et[:, 0] + Et[:, 1]) / 2).astype(np.float32); vk = sichtbar(mid, nm2 / np.maximum(1e-9, np.linalg.norm(nm2, axis=1))[:, None])
                Et, nm2 = Et[vk], nm2[vk]
            if len(Et):
                KP = entlang(Et[:, 0], Et[:, 1]); dk = md(KP, GP); pr[nm] = (round(float((dk < TOL).mean()), 3), int(len(KP)))
                # Rang: nur Kantenpunkte mit Wolke in < NAH (die Fotos sehen die Stelle) und nicht auf einer Brandwand
                kw = md(KP.astype(np.float32), Wv) < NAH
                if NB is not None:
                    _n = nm2 / np.maximum(1e-9, np.linalg.norm(nm2, axis=1))[:, None]
                    _L = np.linalg.norm(Et[:, 1] - Et[:, 0], axis=1); _cnt = np.maximum(2, np.ceil(_L / 0.05).astype(int))   # wie entlang()
                    _kn = np.repeat(_n, _cnt, 0)   # Kantenpunkt -> Normale seiner Kante
                    kw &= ~_brandwand(KP, _kn, NB)
                    _rest = trimesh.util.concatenate([v for k_, v in _alle.items() if k_ != nm + ".stl"]) if len(_alle) > 1 else None
                    if _rest is not None: kw &= ~_brandwand(KP, _kn, _rest, weite=1.5, start=-0.02, min_d=0.05)
                pr2[nm] = round(float((dk[kw] < TOL).mean()), 3) if kw.sum() >= 50 else None
            else:
                pr[nm] = (None, 0); pr2[nm] = None
        for i, t in enumerate(teile):
            g = (wer == i) & (dmin < NAH)
            t["kanten_recall"] = round(float((dmin[g] < TOL).mean()), 3) if g.sum() >= 50 else None
            t["gitter_pkt"] = int(g.sum()); t["kanten_praez"], t["kanten_pkt"] = pr[t["teil"]]
            _p, _r = pr2.get(t["teil"]), t["kanten_recall"]; _f = None if _p is None or _r is None else (2 * _p * _r / (_p + _r) if _p + _r > 0 else 0.0)
            _w = [x for x in (t.get("rang_beleg"), _f) if x is not None]
            t["rang_kanten_praez"] = _p; t["rang_guete"] = round(sum(_w) / len(_w), 3) if _w else None   # Zielwahl-Rang (Kreis), nicht Tor
    teile.sort(key=lambda t: (t["beleg"] is None, t["beleg"] if t["beleg"] is not None else 9))

try:
    git = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", os.path.abspath(STL)],
                                capture_output=True, text=True).stdout.strip())
except Exception:
    git, dirty = "?", True
import hashlib
STL_SHA = hashlib.sha256(open(STL, "rb").read()).hexdigest()[:16]
# 8. Fehlkanten (10.11.: fehlende Elemente - Ost-Staffelgiebel, Pfeiler-Daechlein, Dachgitter - wurden nie Ziel des Kreises):
#    Gitterpunkte (Fotokanten) ohne Modellflaeche in < --fehl_ab m, innerhalb der Modellhuelle +1 m, zu 0,5-m-Voxel-Clustern (6er-Nachbarschaft) verbunden, Cluster >= --fehl_min Pkt;
#    je Cluster recall_kasten = Recall aller Gitterpunkte im Kasten +-0,25 m (gleiche Definition wie --regionen, Vorher-Wert fuer den Kreis).
#    Cluster-ID aus dem auf 2 m gerundeten Schwerpunkt (stabil ueber Laeufe). --regionen JSON [{id, lo, hi}]: Recall der Gitterpunkte je Kasten.
from scipy import ndimage
FEHL_AB = opt("--fehl_ab", 0.30, float); lo_m, hi_m = m.bounds[0] - 1.0, m.bounds[1] + 1.0
inn = np.all((GP >= lo_m) & (GP <= hi_m), axis=1) & (GP[:, 2] >= m.bounds[0][2] + 0.3)
# Gitter-Anpassungen, die der Gitterbau selbst als 'abweichend' markiert (Zylinder cx/cy/R/z_fuss/z_kopf), sind keine Fehlteile:
# Kreis 10.11. fk_-8_+10_+6 = Saeulen-Fit R 0,62 (62 % Inlier) frei vor dem Nachbarhaus, Agent pruefte 5 Fotos (L-KR8). Nur hier ausgenommen, Recall unveraendert.
_GJ = json.load(open(GIT)); aus = np.zeros(len(GP), bool)
# ausserdem schwache Zylinder-Fits (Inlier < 0,1 x Median der Liste): 716 und 983 Inlier gegen Median ~22000, beide am Foto als
# Nicht-Saeule belegt (a030944, a032345 r2, a032646 r1: echte Pfeiler 5,6 m weiter vorn); 2497 bleibt drin.
for _k, _v in _GJ.items():
    _zyl = [e for e in (_v if isinstance(_v, list) else []) if isinstance(e, dict) and all(k_ in e for k_ in ("cx", "cy", "R", "z_fuss", "z_kopf"))]
    _med = float(np.median([e["inlier"] for e in _zyl if "inlier" in e])) if any("inlier" in e for e in _zyl) else 0.0
    for _e in _zyl:
        if _e.get("abweichend") or ("inlier" in _e and _e["inlier"] < 0.1 * _med):
            aus |= (np.hypot(GP[:, 0] - _e["cx"], GP[:, 1] - _e["cy"]) <= _e["R"] + 0.15) & (GP[:, 2] >= _e["z_fuss"] - 0.15) & (GP[:, 2] <= _e["z_kopf"] + 0.15)
U = GP[inn & (d_rec >= FEHL_AB) & ~aus]; fehlkanten = []
if len(U):
    VX = opt("--fehl_voxel", 0.5, float); vi = np.floor((U - lo_m) / VX).astype(int); shp = vi.max(0) + 1; occ = np.zeros(shp, bool); occ[tuple(vi.T)] = True
    lab, nl = ndimage.label(occ); li = lab[tuple(vi.T)]   # 6er-Nachbarschaft, 0,5-m-Voxel: trennt benachbarte Elemente (1 m/26er verband Fassade+Dach zu einem Cluster)
    for k in range(1, nl + 1):
        P_ = U[li == k]
        if len(P_) < opt("--fehl_min", 200, int): continue
        c = P_.mean(0); fid = "fk_" + "_".join(f"{v:+.0f}" for v in np.round(c / 2) * 2)
        fehlkanten.append({"id": fid, "zentrum": [round(float(v), 2) for v in c], "lo": [round(float(v), 2) for v in P_.min(0)],
                           "hi": [round(float(v), 2) for v in P_.max(0)], "pkt": int(len(P_))})
    fehlkanten.sort(key=lambda f: -f["pkt"])
def kasten_recall(lo, hi):
    g = np.all((GP >= np.array(lo) - 0.25) & (GP <= np.array(hi) + 0.25), axis=1)
    return {"pkt": int(g.sum()), "recall": round(float((d_rec[g] < TOL).mean()), 4) if g.sum() else None}
for f_ in fehlkanten: f_["recall_kasten"] = kasten_recall(f_["lo"], f_["hi"])["recall"]
regionen = {}
if opt("--regionen") and os.path.exists(opt("--regionen")):
    for r_ in json.load(open(opt("--regionen"))): regionen[r_["id"]] = kasten_recall(r_["lo"], r_["hi"])

zeile = {"zeit": time.strftime("%Y-%m-%d %H:%M"), "git": git + ("+" if dirty else ""), "etikett": ETIKETT, "stl": STL, "stl_sha": STL_SHA, "skala": SK,
         "gitter": GIT, "tol_m": TOL, "min_kante_m": MINK, "kanten": {"gesamt": gesamt, "baender": baender},
         "pruefstand": pb, "teile_sicht": ts, "foto_diff": fd, "wolkenbeleg_teile": teile, "fehlkanten": fehlkanten[:20], "regionen": regionen, "sicht": ("verdeckung_strahl" if (opt("--kameras") and "--ohne_verdeckung" not in a) else "normale"), "rechenzeit_s": round(time.time() - t0, 1)}

# Vergleich mit Vorlauf
KF = os.path.join(ODIR, "konvergenz.jsonl")
vor = None
if os.path.exists(KF):
    z = [l for l in open(KF) if l.strip()]
    vor = json.loads(z[-1]) if z else None
rueck = []
if vor:
    vb = {b["band"]: b for b in vor["kanten"]["baender"]}
    for b in baender:
        v = vb.get(b["band"])
        if not v: continue
        for k, n in (("recall", "gitter_pkt"), ("praezision", "modellkante_pkt")):
            if b[k] is not None and v.get(k) is not None and min(b[n], v[n]) >= 200 and b[k] < v[k] - RAUSCH:
                rueck.append(f"{k} {b['band']} m: {v[k]:.3f} -> {b[k]:.3f}")
    if vor.get("pruefstand", {}).get("bestanden") and not pb.get("bestanden"):
        rueck.append("Pruefstand nicht mehr bestanden")
    vt, nt = vor.get("teile_sicht"), ts
    if vt and nt and vt.get("gate_bewiesen") and nt.get("gate_bewiesen"):
        if nt["gruen"] < vt["gruen"]:
            rueck.append(f"GRUEN-Teile {vt['gruen']} -> {nt['gruen']}")
        neu_rot = sorted(set(nt["rot_teile"]) - set(vt["rot_teile"]))
        if neu_rot:
            rueck.append("neu ROT: " + ", ".join(neu_rot))
zeile["rueckschritt"] = rueck

# Ausgabe
print(f"Konvergenz {OBJ}  git {zeile['git']}  tol {TOL} m  min_kante {MINK} m  ({zeile['rechenzeit_s']} s GPU)")
print(f"{'Band m':>8} {'Gitterpkt':>9} {'Recall':>7} {'Vorlauf':>7} | {'Modellk.':>8} {'Praez.':>7} {'Vorlauf':>7}  Gitterdichte")
vb = {b["band"]: b for b in vor["kanten"]["baender"]} if vor else {}
f3 = lambda x: "-" if x is None else f"{x:.3f}"
for b in baender:
    v = vb.get(b["band"], {})
    print(f"{b['band']:>8} {b['gitter_pkt']:>9} {f3(b['recall']):>7} {f3(v.get('recall')):>7} | {b['modellkante_pkt']:>8} "
          f"{f3(b['praezision']):>7} {f3(v.get('praezision')):>7}  {b['gitterdichte']}")
print(f"{'gesamt':>8} {'':>9} {f3(gesamt['recall']):>7} {f3(vor['kanten']['gesamt']['recall']) if vor else '-':>7} | {'':>8} "
      f"{f3(gesamt['praezision']):>7} {f3(vor['kanten']['gesamt']['praezision']) if vor else '-':>7}")
if pb: print(f"Pruefstand: bestanden={pb['bestanden']}  ok {pb['ok']}/{pb['n']}  widerspruch {pb['widerspruch']}")
if ts: print(f"Teile-Sicht: GRUEN {ts['gruen']}  ROT {ts['rot']}  UNGEPRUEFT {ts['ungeprueft']}  "
             f"({'Gate bewiesen' if ts['gate_bewiesen'] else 'NUR HINWEIS, Gate nicht bewiesen'})")
for k, v in fd.items(): print(f"foto_diff {k}: rot {v['rot']}  gelb {v['gelb']}")
if teile:
    print("Wolkenbeleg je Bauteil (schlechteste zuerst; Hinweis, kein Gate): Teil | Flaeche mit Daten | davon auf Wolke | Median m | ueber Wolken-zmax")
    for t in teile:
        flag = "  <- pruefen" if t["beleg"] is not None and t["beleg"] < 0.3 else ""
        print(f"  {t['teil']:30s} {t['anteil_mit_daten']:.2f}  {t['beleg']}  {t['median_m']}  {t['ueber_wolke_z']}  kanten R {t.get('kanten_recall')} P {t.get('kanten_praez')} ({t.get('gitter_pkt')}/{t.get('kanten_pkt')}){flag}")
if rueck:
    print("RUECKSCHRITT: " + "; ".join(rueck))
if fehlkanten:
    print(f"Fehlkanten (Fotokanten ohne Modellflaeche >= {FEHL_AB} m, Cluster >= {opt('--fehl_min', 200, int)} Pkt): {len(fehlkanten)}")
    for f_ in fehlkanten[:10]: print(f"  {f_['id']:22s} {f_['pkt']:6d} Pkt  Zentrum {f_['zentrum']}  Kasten {f_['lo']} .. {f_['hi']}  Recall im Kasten {f_['recall_kasten']}")
for k_, v_ in regionen.items(): print(f"Region {k_}: {v_}")
if opt("--json_aus"): json.dump(zeile, open(opt("--json_aus"), "w"), ensure_ascii=False)   # Zeile auch im Trockenlauf greifbar (Kreis-Trockentest)
if not TROCKEN:
    with open(KF, "a") as f: f.write(json.dumps(zeile, ensure_ascii=False) + "\n")
    print("angehaengt:", KF)
sys.exit(3 if rueck else 0)
