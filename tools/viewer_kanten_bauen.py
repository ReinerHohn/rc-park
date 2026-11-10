"""3D-Viewer: Wolke (Fotofarben) + Kantenpunkte + Drahtgitter, Ebenen schaltbar, eigener Canvas-Renderer (kein WebGL noetig).
Aufruf: viewer_kanten_bauen.py OUT.html [--seg SEGMENTE.json] [--kp KANTENPUNKTE.npy] [--n 120000] [--koerper KOERPER.stl] [--objekt NAME] [--fotos KAM.json --bilder DIR --n_fotos 90] (passendes Foto je Blickrichtung) (Formkanten > 25 Grad + schattierte Flaeche; Front = Fassade von aussen)"""
import sys, json, base64, numpy as np
if len(sys.argv) < 2 or sys.argv[1].startswith("-"): sys.exit(__doc__)
def opt(n, d, t=str): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"; Wd = "/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2"
P = np.load(Wd + "/j_voll_lot2_crop.npy", mmap_mode="r"); rgb = np.load(Wd + "/j_crop_rgb2.npy", mmap_mode="r"); print("Wolke", P.shape, "RGB", rgb.shape, rgb.dtype, flush=True)
rng = np.random.default_rng(0); N = opt("--n", 120000, int); idx = np.sort(rng.choice(len(P), N, replace=False)); W = np.asarray(P[idx]); C = np.asarray(rgb[idx]); C = (C * 255 if C.dtype != np.uint8 and C.max() <= 1.01 else C).astype(np.uint8)
# L23 (9.11.): die _crop-Wolke endet bei z 26,0 (Giebelspitzen 29 m fehlten). Punkte der vollen Wolke ueber dem Crop-Deckel im Crop-Grundriss
# ergaenzen (ohne Fotofarbe -> grau), damit Giebel/Helme oben nicht leer aussehen.
try:
    PV = np.load(Wd + "/j_voll_lot2.npy", mmap_mode="r"); zc = float(np.asarray(P[:, 2]).max()); lo = np.asarray(P[:, :2]).min(0); hi = np.asarray(P[:, :2]).max(0)
    zv = np.asarray(PV[:, 2]); sel = np.where(zv > zc)[0]; X = np.asarray(PV[sel]); X = X[np.all((X[:, :2] >= lo) & (X[:, :2] <= hi), axis=1)]
    W = np.concatenate([W, X.astype(W.dtype)]); C = np.concatenate([C, np.full((len(X), 3), 150, np.uint8)]); print("ueber Crop-Deckel", round(zc, 2), "ergaenzt:", len(X), flush=True)
except FileNotFoundError:
    pass
KP = np.load(opt("--kp", D + "/tsweep80_konsens.npy")); KP = KP[rng.choice(len(KP), min(len(KP), 60000), replace=False)]
S = json.load(open(opt("--seg", D + "/segmente_karte4.json")))["segmente"]
ctr = np.median(W, axis=0); SC = 400.0
def q(a): return base64.b64encode(np.round((np.asarray(a, np.float32) - ctr) * SC).astype("<i2").tobytes()).decode()
seg = np.array([[*s[0], *s[1]] for s in S], np.float32); sq = np.array([s[2] for s in S], np.uint8)
KB = np.zeros((0, 6), np.float32); SE = np.zeros((0, 6), np.float32); SN = np.zeros((0, 6), np.int8); MP = np.zeros((0, 3), np.float32); MC = np.zeros(0, np.uint8)
if "--koerper" in sys.argv:
    import trimesh; m = trimesh.load(opt("--koerper", "")); e = m.face_adjacency_edges[m.face_adjacency_angles > np.radians(25)]; KB = m.vertices[e].reshape(-1, 6).astype(np.float32); print("Koerper-Formkanten", len(KB), flush=True)
    # Umrisskanten (Nutzer 10.11. "Saeulen vergessen"): gekruemmte Flaechen (runde Pfeiler, Helme) haben keine Knickkante > 25 Grad.
    # Alle Nachbarkanten > 1 Grad mit beiden Flaechennormalen ausliefern; der Viewer zeichnet je Blickrichtung die, deren Normalen
    # zur Blickrichtung verschiedene Vorzeichen haben (Silhouette) - allgemein fuer jede gekruemmte Form.
    sel = m.face_adjacency_angles > np.radians(1); fa = m.face_adjacency[sel]
    SE = m.vertices[m.face_adjacency_edges[sel]].reshape(-1, 6).astype(np.float32)
    SN = np.round(np.concatenate([m.face_normals[fa[:, 0]], m.face_normals[fa[:, 1]]], 1) * 127).astype(np.int8); print("Umriss-Kandidaten", len(SE), flush=True)
    # 10.11. Nutzerbefund "Modell spiegelverkehrt, Saeulen fehlen": Formkanten ohne Verdeckung zeigen die Fassade von hinten wie gespiegelt,
    # runde Pfeiler haben keine Kante > 25 Grad. Deshalb zusaetzlich die Flaeche als schattierte Punkte (z-gepuffert, verdeckt Hinteres).
    MP, fi = trimesh.sample.sample_surface_even(m, opt("--n_flaeche", 400000, int), seed=0) if hasattr(trimesh.sample, "sample_surface_even") else trimesh.sample.sample_surface(m, opt("--n_flaeche", 400000, int))
    nrm = m.face_normals[fi]; L = np.array([0.35, -0.55, 0.76]); L /= np.linalg.norm(L)
    MC = np.clip(70 + 150 * np.abs(nrm @ L), 0, 255).astype(np.uint8); print("Modellflaeche Punkte", len(MP), flush=True)
MRGB = None
if "--modell_farbe" in sys.argv:   # tools/modell_fotofarbe.py: Oberflaechenpunkte mit Fotofarbe (Median ueber bis zu 6 Ansichten); ohne Ansicht -> schattiertes Grau
    Z = np.load(opt("--modell_farbe", "")); MP = Z["P"]; Cf = Z["C"].astype(np.int16); nrm = Z["N"]; L = np.array([0.35, -0.55, 0.76]); L /= np.linalg.norm(L)
    g = np.clip(70 + 150 * np.abs(nrm @ L), 0, 255).astype(np.int16); ohne = Cf[:, 0] < 0
    Cf[ohne] = np.stack([g[ohne]] * 3, 1); MRGB = Cf.clip(0, 255).astype(np.uint8); MC = g.astype(np.uint8)
    print("Modell-Fotofarbe", len(MP), "Punkte, gefaerbt", round(100 * (1 - ohne.mean()), 1), "%", flush=True)
# Front-Ansicht = Hauptfassade VON AUSSEN (Blick entgegen der Fassadennormale achse_n aus objekt.json; --objekt NAME). Ohne Angabe Blick nach +y.
fy = 0.0
if "--objekt" in sys.argv:
    _o = json.load(open(__file__.replace("tools/viewer_kanten_bauen.py", f"modelle/{opt('--objekt', '')}/objekt.json")))
    _n = next((b["achse_n"] for b in _o.get("bauteile", []) if b.get("achse_n") and b.get("aktiv", True)), None)
    if _n: fy = float(np.arctan2(-_n[0], -_n[1])); print("Front-Blick entgegen achse_n", _n, "yaw", round(fy, 3), flush=True)
data = {"se": q(SE.reshape(-1, 3)) if len(SE) else "", "sn": base64.b64encode(SN.tobytes()).decode(), "nse": len(SE), "fy": fy, "m": q(MP) if len(MP) else "", "mc": base64.b64encode(MC.tobytes()).decode(), "nm": len(MP), "kb": q(KB.reshape(-1, 3)) if len(KB) else "", "nkb": len(KB), "ctr": ctr.tolist(), "sc": SC, "w": q(W), "c": base64.b64encode(C.tobytes()).decode(), "k": q(KP), "s": q(seg.reshape(-1, 3)), "sq": base64.b64encode(sq.tobytes()).decode(), "nw": len(W), "nk": len(KP), "ns": len(S)}
# Passendes Foto je Blickrichtung (Nutzer 10.11.): kalibrierte Kameras (gleicher Rahmen wie die Wolke, z. B. sfm/kam_lot2.json), Auswahl
# --n_fotos nach groesster Richtungsvielfalt (Fernpunkt-Auswahl auf Blickrichtung + Standort), Vorschaubilder klein eingebettet.
FT = []
if "--fotos" in sys.argv:
    import cv2, os
    KJ = json.load(open(opt("--fotos", ""))); BD = opt("--bilder", D + "/bilder"); NF = opt("--n_fotos", 90, int)
    nam = [k for k in KJ if os.path.exists(os.path.join(BD, k))]
    dirs = np.array([np.asarray(KJ[k]["Rn"])[2] for k in nam]); Cs = np.array([KJ[k]["C"] for k in nam])
    # Uebersicht bevorzugt (Pruefung 10.11.: reine Richtungswahl lieferte Nahaufnahmen einer Saeule): Gebaeudemitte im Bild (Achse <= 30 Grad
    # zur Mitte) und Abstand >= 10 m; Vielfalt per Fernpunkt-Auswahl erst unter diesen, Rest nur zum Auffuellen.
    zm = ctr - Cs; dist = np.linalg.norm(zm, axis=1); zent = np.einsum("ij,ij->i", dirs, zm / dist[:, None])
    gut = np.where((zent >= np.cos(np.radians(30))) & (dist >= 10))[0]; rest = np.setdiff1d(np.arange(len(nam)), gut)
    mrk = np.concatenate([dirs * 10.0, (Cs - ctr) / 3.0], 1); wahl = []
    for pool in (gut, rest):
        if not len(pool) or len(wahl) >= NF: continue
        dmin = np.full(len(pool), np.inf) if not wahl else np.min(np.linalg.norm(mrk[pool][:, None] - mrk[wahl][None], axis=2), 1)
        if not wahl: wahl.append(int(pool[np.argmax(dist[pool])])); dmin = np.linalg.norm(mrk[pool] - mrk[wahl[0]], axis=1)
        while len(wahl) < min(NF, len(nam)) and dmin.max() > 0:
            j = int(np.argmax(dmin)); wahl.append(int(pool[j])); dmin = np.minimum(dmin, np.linalg.norm(mrk[pool] - mrk[pool[j]], axis=1))
    print("Uebersichtsfotos", len(gut), "von", len(nam), flush=True)
    for j in wahl:
        im = cv2.imread(os.path.join(BD, nam[j]))
        if im is None: continue
        h, w = im.shape[:2]; f_ = 420 / max(h, w); im = cv2.resize(im, (int(w * f_), int(h * f_)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 72])
        FT.append({"n": nam[j], "d": [round(float(x), 4) for x in dirs[j]], "c": [round(float(x), 2) for x in Cs[j] - ctr], "u": int(j in set(gut.tolist())), "j": base64.b64encode(buf.tobytes()).decode()})
    print("Fotos eingebettet", len(FT), "von", len(nam), sum(len(f["j"]) for f in FT) // 1024, "KB", flush=True)
data["ft"] = FT
if MRGB is not None: data["mrgb"] = base64.b64encode(MRGB.tobytes()).decode(); data["m"] = q(MP); data["nm"] = len(MP)
html = open(__file__.replace("viewer_kanten_bauen.py", "viewer_kanten_vorlage.html")).read().replace("/*DATA*/", "const DATA=" + json.dumps(data) + ";")
open(sys.argv[1], "w").write(html); print("geschrieben", sys.argv[1], len(html) // 1024, "KB")
