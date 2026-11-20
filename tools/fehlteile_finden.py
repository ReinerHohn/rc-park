#!/usr/bin/env python3
"""fehlteile_finden.py - AUTOMATISCH finden, wo das Foto Struktur zeigt, die das Modell nicht hat (und umgekehrt).

Mit der kalibrierten Kamera eines Fotos (K-<foto>.json "kamera", aus amtlichen Ankern; ersatzweise Silhouettenkamera aus kameras.json) wird das
Modell gerendert: Tiefe + Normalen -> Modellkanten. Das Foto wird auf ~0,15 m geglaettet (Steinfugen weg) -> Fotokanten. Je Zelle (~1 x 1 m auf
dem Modell) Kantendichte Foto vs Modell. Score > 0: Foto hat Struktur, Modell nicht (FEHLT). Score < 0: Modell hat Struktur ohne Fotobeleg (ERFUNDEN?).
Jede auffaellige Zelle bekommt ihre 3D-Lage (Modelloberflaeche) und landet als Beobachtung in der Masstabelle (einmal, mit Foto/Zelle).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/fehlteile_finden.py modelle/<objekt>/objekt.json <foto> [--schwelle 0.35] [--top 12]
Ausgabe: modelle/<objekt>/audit/fehlteile_<foto>.jpg (Heatmap ueber dem Foto, nummerierte Treffer), fehlteile_<foto>.json.
Grenzen: nur Kanten (keine Farbe), Verdeckungen (Baeume, Leitungen) erzeugen Scheintreffer -> jeder Treffer wird angesehen, bevor er in den Generator geht.

GPU (2026-11-10): Flaechenstichprobe, Z-Puffer, Min-/Max-Filter (erode/dilate/close), Gauss der Tiefe, Sobel (float64), nanmedian und Zellsummen laufen in PyTorch
(CUDA; ohne CUDA oder mit RENDER_CPU=1 derselbe Code auf der CPU). Die Zufallszahlen werden wie in trimesh.sample_surface(seed=0) mit numpy gezogen (gleiche Punkte),
Suche/Gewichtung/Gather laufen auf der GPU. Bewusst CPU (cv2): imread, GaussianBlur(uint8), Canny (Hysterese, bit-genau noetig), imwrite, addWeighted.
Zellschleifen sind vektorisiert (reshape-Summen); das Overlay wird je Zelle gebaut statt als 12-MP-float64-Heatmap. Normalen wurden nie weiterverwendet (nur render() fuer Fremdaufrufer).
Zeiten je Abschnitt und VRAM: FEHLTEILE_PROF=1. VRAM-Spitze (12-MP-Foto, Messung 2026-11-10): torch.max_memory_allocated ~800 MiB, reserviert ~0,9-1,0 GiB, nvidia-smi je Prozess ~1000 MiB inkl. CUDA-Kontext (Ziel < 1500 MiB).
Umgebung: torch/cv2/trimesh -> venv-seg (s.o.) oder `tools/py tools/fehlteile_finden.py ...`. RENDER_CPU=1 erzwingt CPU.
Exit 0 = gelaufen (Treffer sind Hinweise, kein Urteil); keine Kamera fuer das Foto -> Abbruch mit Text.
"""
import sys, os, json, glob, math, time, numpy as np, cv2, trimesh
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
SIL_F0 = 5.4 / 4.29   # Brennweitenfaktor der Silhouettenkamera (foto_silhouette_gpu); je Objekt in objekt.json ueberschreibbar
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_PROF = bool(os.environ.get("FEHLTEILE_PROF")); _t0 = [time.perf_counter()]; _tab = []
def _dev():
    import torch
    return torch.device("cuda" if torch.cuda.is_available() and not os.environ.get("RENDER_CPU") else "cpu")
def _zeit(name):
    """Abschnittszeit (mit GPU-Synchronisation), nur wenn FEHLTEILE_PROF gesetzt."""
    if not _PROF: return
    import torch
    if torch.cuda.is_available(): torch.cuda.synchronize()
    now = time.perf_counter()
    if _t0[0] is not None: _tab.append((name, now - _t0[0]))
    _t0[0] = now

def stichprobe(m, n, dev, seed=0, block=1 << 19):
    """Wie trimesh.sample.sample_surface(m, n, seed=seed): dieselben Zufallszahlen (numpy-Generator, gleiche Reihenfolge) -> dieselben Punkte;
    kumulierte Flaechen auf der CPU (24k Werte), Suche/Gather/Arithmetik float64 auf `dev`. Rueckgabe (P (n,3) float64, Flaechennummer (n,)) als Tensoren."""
    import torch
    rng = np.random.default_rng(seed); cum = np.cumsum(m.area_faces); pick = rng.random(n) * cum[-1]; rl = rng.random((n, 2, 1))
    fi = torch.searchsorted(torch.as_tensor(cum, device=dev), torch.as_tensor(pick, device=dev)); del pick      # linksseitig wie np.searchsorted (gleiche float64-Werte)
    V = np.asarray(m.vertices); F = np.asarray(m.faces); org = V[F[:, 0]]; vec = V[F[:, 1:]] - np.tile(org, (1, 2)).reshape((-1, 2, 3))
    org = torch.as_tensor(org, device=dev); vec = torch.as_tensor(vec, device=dev); P = torch.empty((n, 3), dtype=torch.float64, device=dev)
    for s in range(0, n, block):
        e = min(n, s + block); r = torch.as_tensor(rl[s:e], device=dev); test = r.sum(dim=1).reshape(-1) > 1.0
        r[test] -= 1.0; r = r.abs(); f_ = fi[s:e]
        P[s:e] = (vec[f_] * r).sum(dim=1) + org[f_]
    return P, fi

def tiefe_gpu(P, R, t, f, cx, cy, W, H, dev):
    """Z-Puffer wie render_kern.tiefenbild (gleiche Rundung/float32-Tiefe/isclose; bei Gleichstand gewinnt der spaeteste Punkt), alles auf `dev`.
    Rueckgabe depth (H,W float32, inf leer), idx (H,W int32 Punktnummer, -1 leer) als Tensoren."""
    import torch
    Rg = torch.as_tensor(np.asarray(R, np.float64), device=dev); tg = torch.as_tensor(np.asarray(t, np.float64).ravel(), device=dev)
    d = torch.full((H * W,), float("inf"), dtype=torch.float32, device=dev); idx = torch.full((H * W,), -1, dtype=torch.int64, device=dev); n = len(P); B = 1 << 20; teile = []
    for s in range(0, n, B):
        Xc = P[s:s + B] @ Rg.T + tg; z = Xc[:, 2]
        u = torch.round(f * Xc[:, 0] / z + cx).long(); v = torch.round(f * Xc[:, 1] / z + cy).long()
        ok = (z > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H); flat = v[ok] * W + u[ok]; zz = z[ok].float(); wo = torch.nonzero(ok, as_tuple=True)[0] + s
        d.scatter_reduce_(0, flat, zz, reduce="amin"); teile.append((flat, zz, wo))
    for flat, zz, wo in teile:
        w = torch.isclose(d[flat], zz); idx.scatter_reduce_(0, flat[w], wo[w], reduce="amax")
    out = idx.to(torch.int32).reshape(H, W); del idx, teile
    return d.reshape(H, W), out

def _pool(x, kh, kw, hoechst=True):
    """Rechteckiges Max-/Min-Filter (= cv2.dilate/erode mit Rechteckkern, Rand neutral) als zwei 1-D-Pools. x: (H,W) Tensor (float32/half)."""
    import torch, torch.nn.functional as Fn
    y = x[None, None] if hoechst else -x[None, None]
    if kw > 1: y = Fn.max_pool2d(y, (1, kw), stride=1, padding=(0, kw // 2))
    if kh > 1: y = Fn.max_pool2d(y, (kh, 1), stride=1, padding=(kh // 2, 0))
    return (y if hoechst else -y)[0, 0]

def _gauss(x, sigma, ksize):
    """cv2.GaussianBlur fuer float32 (Kern aus cv2.getGaussianKernel, Rand reflect-101), getrennt, auf dem Geraet von x."""
    import torch, torch.nn.functional as Fn
    k = cv2.getGaussianKernel(ksize, sigma, cv2.CV_32F).ravel(); r = ksize // 2; H, W = x.shape
    y = Fn.pad(x[None, None], (r, r, 0, 0), mode="reflect")[0, 0]; a = torch.zeros_like(x)
    for i in range(ksize): a += float(k[i]) * y[:, i:i + W]
    y = Fn.pad(a[None, None], (0, 0, r, r), mode="reflect")[0, 0]; b = torch.zeros_like(x)
    for i in range(ksize): b += float(k[i]) * y[i:i + H]
    return b

def _sobel(x, dx, dy):
    """cv2.Sobel(x, CV_64F, dx, dy, ksize=3) (ohne Skalierung, Rand reflect-101), x float64-Tensor."""
    import torch.nn.functional as Fn
    H, W = x.shape; y = Fn.pad(x[None, None], (1, 1, 1, 1), mode="reflect")[0, 0]
    if dx:   # Ableitung in x, Glaettung [1 2 1] in y
        c = y[:, 2:] - y[:, :-2]; return c[:-2] + 2 * c[1:-1] + c[2:]
    c = y[2:] - y[:-2]; return c[:, :-2] + 2 * c[:, 1:-1] + c[:, 2:]

def k_datei(objp, obj, root, nr):
    """EINE Stelle fuer die K-Datei eines Fotos (2026-11-04): zuerst der Objektordner (dort schreiben kameras_aus_buendel/kamera_bruecke/beweis_anker),
    dann der Ordner der Masstabelle (Handkalibrierung alter Objekte). Vorher lasen foto_diff/fehlteile nur den Masstabellenordner, test_foto_diff den Objektordner:
    bei martinstor_lod2 (Masstabelle -> martinstor_null) verglich foto_diff gegen die alte Handkamera (RMS 92 px, f 4059 statt 3858) -> Beweis T1 55 %."""
    for d in (os.path.dirname(os.path.abspath(objp)), os.path.join(root, os.path.dirname(obj["masstabelle"]))):
        kp = os.path.join(d, "messprotokoll", f"K-{nr}.json")
        if os.path.exists(kp) and "kamera" in json.load(open(kp)): return kp
    kp = os.path.join(root, os.path.dirname(obj["masstabelle"]), "messprotokoll", f"K-{nr}.json"); return kp

def kmatrix(kk, W, H):
    return np.array([[float(kk["f_px"]), 0, float(kk.get("cx", W / 2))], [0, float(kk["f_px"]), float(kk.get("cy", H / 2))], [0, 0, 1.0]])

def foto_entzerren(im, kk):
    """Radiale Verzeichnung (COLMAP SIMPLE_RADIAL k1 = OpenCV k1, normierte Koordinaten) aus dem Foto nehmen, damit es zur Lochkamera der Renderer passt (2026-11-04).
    Vorher renderten foto_diff/fehlteile ohne k1: Kanten an der Bildecke im Median 44-71 px versetzt (Kaufhaus/Martinstor), tol 16-40 px. Rueckgabe (Bild, k1)."""
    k1 = float(kk.get("k1") or 0.0) if kk else 0.0
    if not k1 or "f_px" not in kk: return im, 0.0
    H, W = im.shape[:2]; Km = kmatrix(kk, W, H)
    return cv2.undistort(im, Km, np.array([k1, 0, 0, 0], float), None, Km), k1

def foto_verzerren(im, kk):
    """Umkehrung fuer Pruefbilder (test_foto_diff): Lochkamera-Render -> Bild wie aus der echten Kamera mit k1."""
    k1 = float(kk.get("k1") or 0.0) if kk else 0.0
    if not k1: return im
    H, W = im.shape[:2]; Km = kmatrix(kk, W, H); u, v = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    p = cv2.undistortPoints(np.stack([u.ravel(), v.ravel()], 1).reshape(-1, 1, 2), Km, np.array([k1, 0, 0, 0], float), P=Km).reshape(H, W, 2)   # verzerrtes Pixel -> Lochkamera-Pixel
    return cv2.remap(im, p[..., 0].astype(np.float32), p[..., 1].astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

def kamera_laden(K, obj, nr, root, W, H):
    if "kamera" in K:
        k = K["kamera"]
        import messung_pruefen as MP                              # Treffer nur dort, wo die Anker tragen (sonst Extrapolation)
        lo, hi = MP.kamera_zone(k)
        R, _ = cv2.Rodrigues(np.array(k["rvec"]))
        return R, np.array(k["t"]), k["f_px"], "K-%s (amtliche Anker)" % nr, (lo, hi)
    for kp in glob.glob(os.path.join(root, "modelle", "foto_silhouette", "*kameras.json")):      # Silhouettenkamera (foto_dach_gemeinsam)
        kam = json.load(open(kp))
        if nr in kam:
            d, az, el, tz, ro, fs, sx, sy = kam[nr]["th"]; k = W / 400.0
            tgt = np.array([0, 0, tz]); cam = tgt + d * np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
            fw = tgt - cam; fw /= np.linalg.norm(fw); x = np.cross(fw, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(fw, x)
            cr, sr = math.cos(ro), math.sin(ro); x2 = cr * x + sr * y; y2 = -sr * x + cr * y; R = np.vstack([x2, y2, fw]); t = -R @ cam
            f = SIL_F0 * 400 * k * fs; return R, t, f, "Silhouettenkamera %s (sx/sy %.0f/%.0f px vernachlaessigt)" % (os.path.basename(kp), sx * k, sy * k), (None, None)
    raise SystemExit("keine Kamera fuer Foto " + nr)

def render(m, R, t, f, W, H, cx, cy, n=2500000):
    """Tiefe, Normalen und 3D-Lage je Pixel ueber den gemeinsamen Renderkern (GPU, wenn vorhanden). Fuer Fremdaufrufer (numpy-Rueckgabe);
    die Stichprobe ist seit 2026-11-10 GPU-gestuetzt, liefert aber dieselben Punkte wie trimesh.sample_surface(seed=0)."""
    import render_kern as RK
    Pt, fit = stichprobe(m, n, _dev()); P = Pt.cpu().numpy(); fi = fit.cpu().numpy(); del Pt, fit; N = m.face_normals[fi]
    depth, idx = RK.tiefenbild(P, R, t, f, cx, cy, W, H)
    if hasattr(depth, "cpu"): depth = depth.cpu().numpy(); idx = idx.cpu().numpy()
    nrm = np.zeros((H, W, 3)); pos = np.zeros((H, W, 3)); tr = idx >= 0
    nrm[tr] = N[idx[tr]]; pos[tr] = P[idx[tr]]
    return depth, nrm, pos

def versatz_test(a, objp, nr, px, schwelle):
    """M3 (Plan): Erklaert ein Versatz der Bildmitte (Kamerafehler) die Rot/Blau-Muster? Raster 5 x 5 mit Schritt px (+-2 Schritte), je Punkt dasselbe Werkzeug mit --dx/--dy --nur-metrik
    (Subprozess, schreibt nichts). Kennzahl = Summe |Heat| (Rot + Blau). Faellt sie bei einer Verschiebung um mehr als `schwelle` (ANNAHME 10 %) unter den Ausgangswert,
    erklaert Kamerafehler einen Teil der Treffer; sonst nicht. GRENZE: nur Bildhauptpunkt-Verschiebung, keine Rotation/Brennweite/Skalierung."""
    import subprocess
    basis = [x for i, x in enumerate(a) if x not in ("--versatz-test", "--nur-versatz-test", "--nur-metrik") and not (i > 0 and a[i - 1] in ("--versatz-test", "--dx", "--dy", "--versatz-schwelle")) and x not in ("--dx", "--dy", "--versatz-schwelle")]
    me = os.path.abspath(__file__); rows = []
    for ix in range(-2, 3):
        for iy in range(-2, 3):
            r = subprocess.run([sys.executable, "-W", "ignore", "-I", me] + basis + ["--dx", str(ix * px), "--dy", str(iy * px), "--nur-metrik"], capture_output=True, text=True, env=os.environ)
            m = [l for l in r.stdout.splitlines() if l.startswith("METRIK")]
            if not m: raise SystemExit("Versatztest: Teilaufruf ohne Kennzahl: " + (r.stderr or r.stdout)[-300:])
            rot, blau, n = m[-1].split()[1:]; rows.append(dict(dx=ix * px, dy=iy * px, rot=float(rot), blau=float(blau), summe=float(rot) + float(blau), treffer=int(n)))
    s0 = [r for r in rows if r["dx"] == 0 and r["dy"] == 0][0]["summe"]; smin = min(r["summe"] for r in rows); smax = max(r["summe"] for r in rows)
    gewinn = (s0 - smin) / s0 if s0 else 0.0
    urteil = (f"Kamerafehler (Bildmitte +-{2 * px:.0f} px) erklaert die Treffer TEILWEISE: Summe faellt um {100 * gewinn:.1f} % (> {100 * schwelle:.0f} %)" if gewinn > schwelle
              else f"Bildversatz erklaert die Treffer NICHT: Summe {smin:.1f}..{smax:.1f} (Ausgang {s0:.1f}, groesster Rueckgang {100 * gewinn:.1f} % <= {100 * schwelle:.0f} %)")
    return dict(schritt_px=px, schwelle=schwelle, summe_ausgang=s0, summe_min=smin, summe_max=smax, rueckgang_anteil=round(gewinn, 4), urteil=urteil, raster=rows,
                grenze="nur Verschiebung der Bildmitte; Rotation, Brennweite und Skalierung nicht getestet (ANNAHME Schwelle 10 %)")

def main():
    _zeit("import"); a = sys.argv[1:]; objp, nr = a[0], a[1]; dx = float(a[a.index("--dx") + 1]) if "--dx" in a else 0.0; dy = float(a[a.index("--dy") + 1]) if "--dy" in a else 0.0; sch = float(a[a.index("--schwelle") + 1]) if "--schwelle" in a else 0.35; top = int(a[a.index("--top") + 1]) if "--top" in a else 12
    obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp)))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    kp = k_datei(objp, obj, root, nr); K = json.load(open(kp)) if os.path.exists(kp) else {}
    _zeit("json"); im = cv2.imread((glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*")) or glob.glob(os.path.join(root, obj["fotos_dir"], nr + ".*")))[0]); H, W = im.shape[:2]; _zeit("imread"); kk = K.get("kamera", {}); cx, cy = float(kk.get("cx", W / 2)) + dx, float(kk.get("cy", H / 2)) + dy   # Hauptpunkt aus K (Buendelkameras), sonst Bildmitte
    R, t, f, quelle, (zlo, zhi) = kamera_laden(K, obj, nr, root, W, H)
    vt = None
    if "--versatz-test" in a or "--nur-versatz-test" in a:
        px = float(a[a.index("--versatz-test") + 1]) if "--versatz-test" in a and a.index("--versatz-test") + 1 < len(a) and not a[a.index("--versatz-test") + 1].startswith("--") else 30.0
        vt = versatz_test(a, objp, nr, px, float(a[a.index("--versatz-schwelle") + 1]) if "--versatz-schwelle" in a else 0.10)
        if "--nur-versatz-test" in a:
            out_ = os.path.join(root, obj.get("audit", os.path.dirname(obj["masstabelle"]) + "/audit")); os.makedirs(out_, exist_ok=True); json.dump(dict(foto=nr, versatz_test=vt), open(os.path.join(out_, f"versatz_test_{nr}.json"), "w"), indent=1, ensure_ascii=False)
            print(f"Versatztest {nr}: {vt['urteil']} -> {out_}/versatz_test_{nr}.json"); return
    stl = a[a.index("--stl") + 1] if "--stl" in a else os.path.join(root, obj["stl"])
    m = trimesh.load(stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    m.apply_translation(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]])   # wie foto_diff._netz: Buendel-/Brueckenkamera traegt ihren Rahmen (Runde 5: ohne das lag das Netz 1,45 m zu tief)
    _zeit("stl"); import torch
    dev = _dev(); _zeit("torch-import"); torch.backends.cudnn.allow_tf32 = False
    if dev.type == "cuda": torch.cuda.reset_peak_memory_stats()
    Pt, _fi = stichprobe(m, 2500000, dev); del _fi; _zeit("stichprobe")
    depth, idx = tiefe_gpu(Pt, R, t, f, cx, cy, W, H, dev); _zeit("zpuffer")
    sil = torch.isfinite(depth); sil_f = _pool(_pool(sil.half(), 7, 7, True), 7, 7, False)                       # close 7x7 = dilate, dann erode
    # Punktrender hat Loecher: Tiefe per Minimum-Filter (naechster Punkt gewinnt) fuellen, dann glaetten
    dfill = torch.where(sil, depth, torch.full_like(depth, 1e6)); del depth
    dfill = _pool(dfill, 5, 5, False); dfill[sil_f == 0] = float("nan")
    ok_ = dfill[~torch.isnan(dfill)]; n_ = ok_.numel(); k1 = ok_.kthvalue((n_ - 1) // 2 + 1).values; k2 = ok_.kthvalue(n_ // 2 + 1).values   # numpy-nanmedian: Mittel der beiden mittleren Werte
    dmed32 = ((k1 + k2) / 2).item(); del ok_; dmed = float(np.float32(dmed32)); ppm0 = f / dmed; _zeit("fuellen+median")
    dsm = _gauss(torch.nan_to_num(dfill, nan=0.0), 3.0, 25).double(); del dfill                                 # cv2: ksize = round(4*3*2+1)|1 = 25 fuer float32
    gx = _sobel(dsm, 1, 0) / 8.0; gy = _sobel(dsm, 0, 1) / 8.0; del dsm                                          # m je Pixel
    mk = torch.hypot(gx, gy) > 0.2
    # Normalenwechsel: Winkel zwischen Nachbar-Gradienten (zweite Ableitung der Tiefe, in m/px je px)
    kr = _sobel(gx, 1, 0).abs_() / 8.0; kr += _sobel(gy, 0, 1).abs_() / 8.0; kr += _sobel(gx, 0, 1).abs_() / 8.0; del gx, gy
    mk |= (kr * ppm0) > 1.0; del kr; mk &= sil_f > 0; _zeit("gradienten")                                       # Tiefensprung > 0,25 m/px oder deutliche Kante
    # Fotokanten: Glaettung auf ~0,15 m (Steinfugen weg), Canny, nur innerhalb der Modellsilhouette (erodiert, damit der Rand nicht zaehlt)
    ppm = f / dmed; sigma = max(1.0, 0.07 * ppm)                                                                 # ~7 cm: Steinfugen weg, Bauteile bleiben
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), sigma); _zeit("foto_grau+blur(cv2)")
    fk = torch.from_numpy(cv2.Canny(g, 20, 60) > 0).to(dev); _zeit("canny(cv2)")
    kin = int(0.6 * ppm) | 1; inner = _pool(sil_f, kin, kin, False) > 0; del sil_f; fk &= inner; mk &= inner
    kt = int(0.3 * ppm) | 1                                                                                      # Toleranz 0,3 m: Kante zaehlt, wenn im Umkreis eine liegt
    fk = _pool(fk.half(), kt, kt, True) > 0; mk = _pool(mk.half(), kt, kt, True) > 0; _zeit("erode/dilate")      # (faengt ~0,5 m Kamerafehler ab)
    # Zellen ~1 m: Summen je Zelle per reshape, Rest auf wenigen hundert Zahlen (CPU, float64 wie vorher)
    cs = max(8, int(round(1.0 * ppm))); gh, gw = H // cs, W // cs; treffer = []
    def zsum(x): return x[:gh * cs, :gw * cs].reshape(gh, cs, gw, cs).sum(dim=(1, 3), dtype=torch.int64).cpu().numpy()
    n_in = zsum(inner); s_fk = zsum(fk); s_mk = zsum(mk); gueltig = n_in >= 0.5 * cs * cs; del fk, mk
    if not gueltig.any():   # Modell bedeckt im Foto keine ganze 1-m-Zelle (Nahaufnahme/anderer Bildausschnitt) - frueher IndexError, von der Abnahme verschluckt (10.11.)
        od = os.path.join(root, obj.get("audit", os.path.dirname(obj["masstabelle"]) + "/audit")); os.makedirs(od, exist_ok=True); tg = ("_" + os.path.basename(stl)[:-4]) if "--stl" in a else ""
        json.dump(dict(foto=nr, stl=stl, kamera=quelle, zelle_px=cs, treffer=[], hinweis="keine gueltige Zelle: Modellflaeche im Foto < 1 Zelle - nicht bewertbar"), open(os.path.join(od, f"fehlteile_{nr}{tg}.json"), "w"), indent=1, ensure_ascii=False)
        print(f"Fehlteile {nr}: keine gueltige 1-m-Zelle (Zelle {cs} px, Raster {gh}x{gw}, Modell deckt keine Zelle zur Haelfte; Modell-Median-Abstand {dmed:.1f} m, Silhouette innen {float(n_in.sum()) / (gh * gw * cs * cs):.3f} des Bildes, max Zellanteil {float(n_in.max()) / (cs * cs):.2f}) - nicht bewertbar, uebersprungen"); return
    def dichte(s_): return max(1e-6, float(np.quantile(s_[gueltig] / np.maximum(1, n_in[gueltig]), 0.9)))
    qf, qm = dichte(s_fk), dichte(s_mk); print(f"  Kantendichte 90%-Quantil Foto {qf:.3f}, Modell {qm:.3f}")
    with np.errstate(all="ignore"):
        heat = np.where(gueltig, np.minimum(1.0, s_fk / n_in / qf) - np.minimum(1.0, s_mk / n_in / qm), 0.0)       # beide auf ihr 90-%-Quantil normiert
    _zeit("zellen")
    for i, j in np.argwhere(gueltig & (np.abs(heat) >= sch)):                                                    # Reihenfolge wie die alte Doppelschleife (Zeile, Spalte)
        s = heat[i, j]; sl = (slice(i * cs, (i + 1) * cs), slice(j * cs, (j + 1) * cs))
        ix = idx[sl][inner[sl] & (idx[sl] >= 0)].long(); P3 = Pt[ix].mean(0).cpu().numpy() if len(ix) else [np.nan] * 3
        treffer.append(dict(zelle=[int(j) * cs, int(i) * cs, cs], score=round(float(s), 3), art="FEHLT im Modell" if s > 0 else "ERFUNDEN? (Modell ohne Fotobeleg)", xyz=[round(float(x), 2) for x in P3]))
    _zeit("treffer_xyz")
    if _PROF and dev.type == "cuda": print("  PROF VRAM-Spitze torch.max_memory_allocated %.0f MiB, reserviert %.0f MiB" % (torch.cuda.max_memory_allocated() / 2**20, torch.cuda.max_memory_reserved() / 2**20))
    del Pt, idx, inner
    def nachbar_ok(tr):
        x, y, s_ = tr["zelle"]; j, i = x // cs, y // cs; nb = [heat[ii, jj] for ii in (i - 1, i, i + 1) for jj in (j - 1, j, j + 1) if 0 <= ii < gh and 0 <= jj < gw and (ii, jj) != (i, j)]
        return sum(1 for v in nb if np.sign(v) == np.sign(tr["score"]) and abs(v) >= sch / 2) >= 2
    treffer = [tr for tr in treffer if nachbar_ok(tr)]                                                           # mindestens 2 gleichsinnige Nachbarzellen
    if zlo is not None:                                                                                          # nur Hoehen, die die Anker tragen (sonst extrapoliert die Kamera)
        n0 = len(treffer); treffer = [tr for tr in treffer if np.isfinite(tr["xyz"][2]) and zlo <= tr["xyz"][2] <= zhi]
        if n0 != len(treffer):
            print(f"  Ankerzone {zlo:.1f}..{zhi:.1f} m: {n0 - len(treffer)} Treffer ausserhalb verworfen "
                  f"(2026-11-01: K-060 meldete so sechs 'erfundene Teile' bei 33-39 m, obwohl ihre Anker erst bei 41 m beginnen).")
    treffer.sort(key=lambda t: -abs(t["score"])); treffer = treffer[:top]
    if "--nur-metrik" in a:       # interner Aufruf des Versatztests: nur Kennzahl, nichts schreiben
        print("METRIK %.4f %.4f %d" % (heat[heat > 0].sum(), -heat[heat < 0].sum(), len(treffer))); return
    # Overlay auf dem Geraet in Zeilenbloecken: Farbe je Zelle konstant (kein 12-MP-float64-Bild); Mischung wie cv2.addWeighted (0,65 / 0,35, gerundet; +-1 Grauwert moeglich)
    cr = torch.as_tensor((np.clip(heat / 0.6, 0, 1) * 255).astype(np.uint8), device=dev); cb = torch.as_tensor((np.clip(-heat / 0.6, 0, 1) * 255).astype(np.uint8), device=dev)
    og = torch.from_numpy(im).to(dev); o = np.empty_like(im)
    for y0 in range(0, H, 512):
        y1 = min(H, y0 + 512); blk = og[y0:y1].float() * 0.65; ys = torch.arange(y0, y1, device=dev) // cs; zeile = ys < gh
        for ch, cz in ((2, cr), (0, cb)):
            c = torch.zeros((y1 - y0, W), device=dev); ysz = ys.clamp(max=gh - 1)
            c[:, :gw * cs] = cz[ysz].repeat_interleave(cs, dim=1) * zeile[:, None]; blk[..., ch] += c * 0.35
        o[y0:y1] = blk.round().clamp(0, 255).to(torch.uint8).cpu().numpy()
    del og; _zeit("overlay")
    for k, tr in enumerate(treffer, 1):
        x, y, s = tr["zelle"]; cv2.rectangle(o, (x, y), (x + s, y + s), (0, 255, 255), 3); cv2.putText(o, str(k), (x + 4, y + s - 6), 0, 1.0, (0, 255, 255), 3)
    out = os.path.join(root, obj.get("audit", os.path.dirname(obj["masstabelle"]) + "/audit")); os.makedirs(out, exist_ok=True)
    tag = ("_" + os.path.basename(stl)[:-4]) if "--stl" in a else ""
    cv2.imwrite(os.path.join(out, f"fehlteile_{nr}{tag}.jpg"), o); json.dump(dict(foto=nr, stl=stl, kamera=quelle, zelle_px=cs, schwelle=sch, treffer=treffer, versatz_test=vt), open(os.path.join(out, f"fehlteile_{nr}{tag}.json"), "w"), indent=1, ensure_ascii=False); _zeit("jpg+json")
    print(f"Fehlteile {nr} ({quelle}; Zelle {cs} px = 1 m; rot = fehlt im Modell, blau = Modell ohne Fotobeleg) -> {out}/fehlteile_{nr}{tag}.jpg")
    for k, tr in enumerate(treffer, 1): print(f"  {k:2d}. {tr['art']:36s} score {tr['score']:+.2f}  bei x={tr['xyz'][0]} y={tr['xyz'][1]} z={tr['xyz'][2]} m")
    # Beobachtungen automatisch eintragen (einmal je Foto/Zelle)
    tp = os.path.join(root, obj["masstabelle"])
    def _eintragen(tab):
        if "--stl" not in a: ersetzt = auto_ersetzen(tab, f"fehlteile-{nr}-"); print(f"  -> {ersetzt} veraltete Auto-Beobachtung(en) dieses Fotos ersetzt")
        vorhanden = {b.get("auto_id") for b in tab.get("beobachtungen_offen", []) if isinstance(b, dict)}; neu = 0
        for k, tr in enumerate(treffer, 1):
            if "--stl" in a: break                                                       # Testlaeufe an fremden STL erzeugen keine Beobachtungen
            if tr["art"].startswith("FEHLT") and tr["score"] >= sch:
                aid = f"fehlteile-{nr}-{tr['zelle'][0]}-{tr['zelle'][1]}"
                if aid in vorhanden: continue
                tab.setdefault("beobachtungen_offen", []).append(dict(datum="auto", wer=f"fehlteile_finden (Foto {nr}, Treffer {k})", auto_id=aid,
                    art="fehlteil", foto=nr, z_von=tr["xyz"][2], z_bis=tr["xyz"][2], xyz=tr["xyz"], abweichung=tr["score"],
                    text=f"Foto zeigt Struktur ohne Modellgegenstueck bei z={tr['xyz'][2]} m, y={tr['xyz'][1]} m (Zelle {tr['zelle']}, Score {tr['score']:+.2f})",
                    naechster_schritt=f"audit/fehlteile_{nr}.jpg Treffer {k} ansehen, Element benennen, Zeile + beleg()")); neu += 1
        return neu
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from masstabelle_io import aendern, auto_ersetzen
    _zeit("vor-masstabelle"); neu = aendern(tp, _eintragen); print(f"  -> {neu} neue Beobachtung(en) in der Masstabelle"); _zeit("masstabelle")
    # Fuer Treffer AUF einer Fassade einen fertigen Eintrag fuer fassade.json vorschlagen - seit die Elemente Daten sind,
    # ist der Weg von "hier fehlt etwas" zu "dieses Element einfuegen" ein Textbaustein statt einer Codeaenderung.
    fp = os.path.join(root, os.path.dirname(obj["masstabelle"]), "fassade.json")
    if os.path.exists(fp):
        vor = []
        for k, tr in enumerate(treffer, 1):
            if not tr["art"].startswith("FEHLT"): continue
            x, y, z = tr["xyz"]
            if np.isnan(x): continue
            seite, u = ("+x" if x > 0 else "-x", y) if abs(x) > abs(y) else ("+y" if y > 0 else "-y", x)
            if abs(u) > 4.5 or z > 32 or z < 7: continue                       # Kanten und Dachbereich sind keine Fassadenoeffnungen
            vor.append({"treffer": k, "seite": seite,
                        "vorschlag": {"typ": "fenster", "u": round(float(u), 2), "z": round(float(z), 2), "breite": 0.6, "hoehe": 0.85,
                                      "was": f"VORSCHLAG aus fehlteile_finden Foto {nr} Treffer {k} - vor dem Einbau am Vollbild pruefen"}})
        if vor:
            print(f"  Vorschlaege fuer {os.path.relpath(fp, root)} (NICHT automatisch eingebaut):")
            for v in vor: print(f"    Seite {v['seite']}: " + json.dumps(v["vorschlag"], ensure_ascii=False))
            json.dump(vor, open(os.path.join(out, f"fassade_vorschlaege_{nr}.json"), "w"), indent=1, ensure_ascii=False)
    _zeit("fassade")
    if _PROF: print("  PROF " + "  ".join(f"{k} {v:.2f}" for k, v in _tab) + f"  | Summe {sum(v for _, v in _tab):.2f} s")

if __name__ == "__main__":
    import gpu_slot; gpu_slot.belegen("fehlteile_finden")   # gemeinsame GPU-Schlange (10.11.: >2-3 gleichzeitige GPU-Pruefungen = Einbruch)
    main()
