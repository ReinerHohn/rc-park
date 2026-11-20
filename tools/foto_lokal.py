#!/usr/bin/env python3
"""foto_lokal.py - LOKALES FOTO-TOR (modelle/archiv/SPEC_LOKALES_FOTOTOR.md): F1 eines Teils im AENDERUNGSBEREICH, vorher vs. nachher, plus F1 ganz (Festbereich).

Fuer ein Teil (oder alle geaenderten) zwei Teile-Ordner (vorher/nachher) und Fotos. Je Foto:
  Aenderungsmaske = Silhouette-XOR | Tiefe >0,05 m | Normale >20 Grad (Teil vorher gegen nachher), um schwelle x Kappe (0,14 m) erweitert.
  Praezision/Recall/F1 in (Maske UND sichtbarer Teilbereich), vorher und nachher in DERSELBEN Maske; Verdeckung wie teil_fotoform (ganzes Modell + Fotowolke).
  Ganz-F1 = wie teil_fotoform --bereich_von (Vereinigungsbereich vorher/nachher), jeder Stand gegen sein eigenes Modell.
Modell-STL je Stand: --stl_vorher/--stl_nachher, sonst aus den Teilen zusammengesetzt (anbau-Vereinigung minus ausschnitt, manifold3d; ohne Vereinfachung/Konsolen).
Nutzt teil_fotoform/foto_diff/render_kern nur lesend (Kopie der Messlogik, teil_fotoform.py wird anderweitig umgebaut).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_lokal.py <objekt> --vorher D --nachher D --fotos a,b,c [--nur teil] --aus x.json [--bilder DIR]
"""
import sys, os, json, glob, argparse, tempfile, subprocess, hashlib, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_diff as FD, fehlteile_finden as FF, render_kern as RK
from teil_fotoform import rahmen, METRIK   # nur lesend

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = "/media/oem/scan/rc-park_tmp/foto_lokal"
MIN_LOKAL_PX = 150; MIN_LOKAL_FOTOS = 3

_SYN = r'''
import sys, json, numpy as np, trimesh, manifold3d as M
d, aus = sys.argv[1], sys.argv[2]
l = json.load(open(d + "/liste.json")); A, C = [], []
for k, v in l.items():
    m = trimesh.load(d + "/" + v["datei"], force="mesh")
    mf = M.Manifold(M.Mesh(np.asarray(m.vertices, np.float32), np.asarray(m.faces, np.uint32)))
    (A if v["modus"] == "anbau" else C).append(mf)
u = M.Manifold.batch_boolean(A, M.OpType.Add)
if C: u = u - M.Manifold.batch_boolean(C, M.OpType.Add)
o = u.to_mesh(); trimesh.Trimesh(np.asarray(o.vert_properties)[:, :3], np.asarray(o.tri_verts), process=False).export(aus)
'''
def stl_aus_teilen(d):
    h = hashlib.sha256(b"".join(open(p, "rb").read() for p in sorted(glob.glob(os.path.join(d, "*.stl"))))).hexdigest()[:16]
    os.makedirs(TMP, exist_ok=True); out = os.path.join(TMP, f"modell_{h}.stl")
    if not os.path.exists(out):
        s = os.path.join(TMP, "syn.py"); open(s, "w").write(_SYN)
        subprocess.run([os.path.expanduser("~/.venvs/rcpark/bin/python"), s, d, out], check=True)
    return out

def f1_von(p, r): return 2 * p * r / (p + r) if p + r else 0.0

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--vorher", required=True); ap.add_argument("--nachher", required=True)
    ap.add_argument("--fotos", required=True); ap.add_argument("--nur"); ap.add_argument("--stl_vorher"); ap.add_argument("--stl_nachher")
    ap.add_argument("--schwelle", type=float, default=0.4); ap.add_argument("--min_px", type=int, default=150)
    ap.add_argument("--tiefe_m", type=float, default=0.05); ap.add_argument("--normale_grad", type=float, default=20.0)
    ap.add_argument("--wolke"); ap.add_argument("--wolke_abs", type=float, default=0.5); ap.add_argument("--wolke_rel", type=float, default=0.05)
    ap.add_argument("--wolke_schliess", type=int, default=10); ap.add_argument("--aus"); ap.add_argument("--bilder", help="Ordner fuer Bildpaare mit Aenderungsmaske")
    a = ap.parse_args(argv)
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp))
    D = {"v": a.vorher, "n": a.nachher}
    STL = {"v": a.stl_vorher or stl_aus_teilen(a.vorher), "n": a.stl_nachher or stl_aus_teilen(a.nachher)}
    names = sorted({os.path.basename(p)[:-4] for d in D.values() for p in glob.glob(os.path.join(d, "*.stl"))})
    if a.nur: names = a.nur.split(",")
    else:
        def sh(d, n):
            p = os.path.join(d, n + ".stl"); return hashlib.md5(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None
        names = [n for n in names if sh(D["v"], n) != sh(D["n"], n)]
    import wolke_verdeckung as WV
    wp = a.wolke or obj.get("kreis", {}).get("wolke") or "/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2/j_voll_lot2.npy"
    VERD = WV.Verdecker(np.load(wp, mmap_mode="r"))
    sc = obj.get("stl_massstab", 87) / 1000.0
    TM = {}
    def teil(s, n):
        k = (s, n)
        if k not in TM:
            p = os.path.join(D[s], n + ".stl"); m = trimesh.load(p, force="mesh") if os.path.exists(p) else None
            if isinstance(m, trimesh.Trimesh) and len(m.faces): m.apply_scale(sc); TM[k] = m
            else: TM[k] = None
        return TM[k]
    tmp = tempfile.mkdtemp(prefix="fl_", dir=TMP); import atexit, shutil; atexit.register(shutil.rmtree, tmp, True)
    erg = {"objekt": a.objekt, "vorher": a.vorher, "nachher": a.nachher, "teile": {n: {} for n in names}, "stl": STL, "schwelle_m": round(a.schwelle * 0.35, 3)}
    bild = None
    def foto(nr):
        kp = FF.k_datei(objp, obj, R0, nr)
        if not kp: return
        K = json.load(open(kp)); kk = K["kamera"]; bf = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))
        if not bf: return
        im0, K = FD.foto_skalieren(cv2.imread(bf[0]), K); kk = K["kamera"]; H, W = im0.shape[:2]
        voll = os.path.join(tmp, f"voll_{W}x{H}.png")
        if not os.path.exists(voll): cv2.imwrite(voll, np.full((H, W), 255, np.uint8))
        R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
        S = {}
        for s in "vn":
            FD._RUECK = {"nur_kosten": False}
            try: FD.main([objp, nr, "--stl", STL[s], "--bewertung-maske", voll, "--kostenkarte", os.path.join(tmp, f"k_{nr}{s}.npz"), "--aus", tmp])
            except BaseException as ex:
                if "out of memory" in str(ex).lower(): raise
                S = None; break
            finally: rueck, FD._RUECK = FD._RUECK, None
            if not rueck or "kosten" not in rueck: S = None; break
            S[s] = dict(Z=rueck["kosten"], dv=rueck["depth"], tr=rahmen(STL[s], obj, kk))
        if not S: erg.setdefault("fotos_fehler", []).append(nr); return
        ZL = max(2, int(round(12 * float(os.environ.get("RCPARK_FOTO_SKALA") or 1.0)))); zc = VERD.zkarte(R, t, f, cx, cy, W, H, zelle=ZL)
        for s in "vn":
            Z = S[s]["Z"]; mkp, fkp = Z["mkp"], Z["fkp"]; dF16 = Z["dF"]
            _dtF = cv2.distanceTransform((~fkp).astype(np.uint8), cv2.DIST_L2, 5); _dF = dF16.astype(np.float32); _s = (_dF > 0.05) & (_dF < 0.95) & mkp
            S[s]["kap"] = float(np.median(_dtF[_s] / _dF[_s])) if _s.sum() > 20 else 30.0
        tr = S["v"]["tr"]   # Teile liegen im Rahmen des Modells; vorher/nachher-Rahmen identisch angenommen (zentrierung huelle koennte abweichen -> je Stand)
        for n in names:
            RN = {}
            for s in "vn":
                m = teil(s, n)
                if m is None: RN[s] = None; continue
                mm = m.copy(); mm.apply_translation(S[s]["tr"])
                dp, fid, _ = RK.dreiecke_rastern(mm, R, t, f, cx, cy, W, H); RN[s] = dict(dp=dp, fid=fid, nrm=mm.face_normals)
            if RN["v"] is None and RN["n"] is None: continue
            INF = np.full((H, W), np.inf, np.float32)
            dpv = RN["v"]["dp"] if RN["v"] else INF; dpn = RN["n"]["dp"] if RN["n"] else INF
            fv, fn = np.isfinite(dpv), np.isfinite(dpn)
            # Aenderungsmaske
            ch = fv ^ fn; both = fv & fn
            ch |= both & (np.abs(dpv - dpn) > a.tiefe_m)
            if RN["v"] and RN["n"]:
                nv = RN["v"]["nrm"][np.clip(RN["v"]["fid"], 0, None)]; nn = RN["n"]["nrm"][np.clip(RN["n"]["fid"], 0, None)]
                cosw = np.clip((nv * nn).sum(-1), -1, 1); ch |= both & (np.degrees(np.arccos(cosw)) > a.normale_grad)
            if ch.sum() == 0: continue
            kap = 0.5 * (S["v"]["kap"] + S["n"]["kap"]); rr = max(1, int(round(a.schwelle * kap)))
            chd = cv2.dilate(ch.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rr + 1, 2 * rr + 1))) > 0
            wert = {}
            for s in "vn":
                o = "n" if s == "v" else "v"; dv = S[s]["dv"]
                def sicht(dp):
                    fin = np.isfinite(dp); vis = fin & (dp <= dv * 1.003 + 0.03)
                    vd = VERD.verdeckt(zc, dp, ZL, a.wolke_abs, a.wolke_rel, a.wolke_schliess) & vis
                    return vis & ~vd
                vis = sicht(dpv if s == "v" else dpn); vis_o = sicht(dpn if s == "v" else dpv)   # Festbereich: Vereinigung, Verdeckung gegen das Modell des gemessenen Stands
                vis_u = vis | vis_o
                if vis_u.sum() < 200: continue
                Z = S[s]["Z"]; mkp, fkp, dF, dM = Z["mkp"], Z["fkp"], Z["dF"].astype(np.float32), Z["dM"].astype(np.float32)
                ms = cv2.dilate(vis_u.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
                r = {}
                for art, reg in (("ganz", ms), ("lokal", ms & chd)):
                    mk_t, fk_t = mkp & reg, fkp & reg
                    if art == "ganz" and fk_t.sum() < a.min_px: continue
                    if art == "lokal" and mk_t.sum() + fk_t.sum() < MIN_LOKAL_PX: continue
                    ok_m, ok_f = dF[mk_t] < a.schwelle, dM[fk_t] < a.schwelle
                    r[art] = dict(praez=round(float(ok_m.mean()), 3) if ok_m.size else 0.0, recall=round(float(ok_f.mean()), 3) if ok_f.size else 0.0, mk_px=int(mk_t.sum()), fk_px=int(fk_t.sum()))
                if r: wert[s] = r
                if a.bilder and s in ("n", "v"):
                    ym, xm = np.where(ms | chd)
                    if len(ym):
                        y0, y1, x0, x1 = max(0, ym.min() - 30), min(H, ym.max() + 30), max(0, xm.min() - 30), min(W, xm.max() + 30)
                        reg = ms & chd; mk_t, fk_t = mkp & reg, fkp & reg
                        ov = (im0 // 2).copy(); ov[reg] = (ov[reg] * 1.5).clip(0, 255).astype(np.uint8)
                        ov[mk_t & (dF < a.schwelle)] = (0, 200, 0); ov[mk_t & (dF >= a.schwelle)] = (0, 0, 255)
                        ov[fk_t & (dM >= a.schwelle) & ~mk_t] = (0, 255, 255); ov[fk_t & (dM < a.schwelle) & ~mk_t] = (200, 120, 0)
                        cnt, _ = cv2.findContours(chd.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); cv2.drawContours(ov, cnt, -1, (255, 0, 255), 2)
                        os.makedirs(a.bilder, exist_ok=True); cv2.imwrite(os.path.join(a.bilder, f"{n}_{nr}_{'vorher' if s == 'v' else 'nachher'}.jpg"), ov[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 85])
            if "v" in wert and "n" in wert: erg["teile"][n][nr] = wert
        print("Foto", nr, "fertig", flush=True)
    import torch, time
    for nr in a.fotos.split(","):
        for versuch in range(12):   # GPU-Speicher voll (Kreis + andere Jobs): warten und Foto wiederholen (wie teil_fotoform)
            try:
                foto(nr); break
            except (torch.OutOfMemoryError, RuntimeError) as ex:
                if "out of memory" not in str(ex).lower(): raise
                for je_ in erg["teile"].values(): je_.pop(nr, None)
                torch.cuda.empty_cache(); print(f"Foto {nr}: GPU-Speicher voll, Versuch {versuch + 1}, warte 60 s", flush=True); time.sleep(60)
        else: erg.setdefault("fotos_fehler", []).append(nr)
    for n, je in erg["teile"].items():
        def agg(stand, art, fotos):
            mk = sum(je[x][stand][art]["mk_px"] for x in fotos); fk = sum(je[x][stand][art]["fk_px"] for x in fotos)
            if not mk or not fk: return None
            p = sum(je[x][stand][art]["praez"] * je[x][stand][art]["mk_px"] for x in fotos) / mk
            r = sum(je[x][stand][art]["recall"] * je[x][stand][art]["fk_px"] for x in fotos) / fk
            return round(f1_von(p, r), 3)
        fg = [x for x in je if "ganz" in je[x]["v"] and "ganz" in je[x]["n"]]
        fl = [x for x in je if "lokal" in je[x]["v"] and "lokal" in je[x]["n"]]
        g = {"ganz_fotos": len(fg), "lokal_fotos": len(fl)}
        if fg: g.update(f1_ganz_vor=agg("v", "ganz", fg), f1_ganz_nach=agg("n", "ganz", fg))
        if len(fl) >= MIN_LOKAL_FOTOS: g.update(f1_lokal_vor=agg("v", "lokal", fl), f1_lokal_nach=agg("n", "lokal", fl))
        else: g["lokal_nicht_messbar"] = True
        je["_gesamt"] = g
    if a.aus: json.dump(erg, open(a.aus, "w"), ensure_ascii=False, indent=1)
    for n, je in erg["teile"].items(): print(n, je.get("_gesamt"))
    return erg

if __name__ == "__main__":
    import gpu_slot; gpu_slot.belegen("foto_lokal")
    main()
