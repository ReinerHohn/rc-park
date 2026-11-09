#!/usr/bin/env python3
"""editor_modell.py <objekt> --kameras k.json --bilder dir [--foto ip_IMG_6161.jpg] [--port 8766]
Browser-Editor (Nutzerwunsch 8.11.): Modellkanten je Bauteil ueber das Foto, Teil anklicken, mit der Maus VERSCHIEBEN (u = entlang Fassade, z = Hoehe),
'Kanten-Snap' sucht automatisch die beste Lage an den Fotokanten (Canny + Distanztransformation, +-0,8 m), 'Speichern' schreibt die Verschiebung in die Parameter
von objekt.json (Sicherung objekt.json.edit_bak, werte_quellen Regel 3b). Eigener Server (127.0.0.1), unabhaengig vom Messserver.
Grenzen (MVP): nur Verschiebung (kein Skalieren); Teile werden einzeln vom Generator gebaut (Bau schlaegt bei manchen fehl -> in der Liste markiert);
nach dem Speichern ist das Gesamt-STL NICHT neu gebaut (tools/baukasten_gen.py), nur die Kanten des gespeicherten Teils werden neu geladen."""
import sys, os, json, argparse, subprocess, shutil, datetime, threading, urllib.parse
import numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I entfernt das Skriptverzeichnis; kontur_mittel.py liegt neben diesem Skript
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--kameras", required=True); ap.add_argument("--bilder", required=True)
ap.add_argument("--wolke", default="/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2/j_voll_lot2_crop.npy"); ap.add_argument("--foto", default="ip_IMG_6161.jpg"); ap.add_argument("--port", type=int, default=8766); a = ap.parse_args()
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OJ = os.path.join(R0, "modelle", a.objekt, "objekt.json"); KAM = json.load(open(a.kameras)); SW = 1613
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "editor_modell.html"); LOCK = threading.Lock(); CACHE = {}; DT = {}; PIV = {}; MESH = {}
def obj(): return json.load(open(OJ))
def uax():
    n = np.array(obj()["fassade_n"]["wert"], float); n /= np.linalg.norm(n); return np.array([n[1], -n[0]])

def kanten(b, mt):
    """3D-Kanten (m) eines Bauteils: Generator mit NUR_BAUTEIL, scharfe Kanten (> 0,6 rad), max. 4000 Segmente. Cache je Typ + objekt.json-Zeit."""
    k = (b["typ"], mt)
    if k in CACHE: return CACHE[k]
    nm = "_ed_%d.stl" % abs(hash(b["typ"])); env = dict(os.environ, NUR_BAUTEIL=b["typ"], OBJ_DIR=a.objekt, STL_NAME=nm, SCALE="87", ELEMENTE_AUS="/dev/null")
    subprocess.run([os.path.expanduser("~/.venvs/rcpark/bin/python"), os.path.join(R0, "tools", "baukasten_gen.py"), a.objekt], env=env, capture_output=True, text=True)
    p = os.path.join(R0, "modelle", "stl", nm)
    if not os.path.exists(p): CACHE[k] = None; return None
    m = trimesh.load(p, process=False); os.remove(p); m.apply_scale(87 / 1000); m.merge_vertices(); V = np.asarray(m.vertices); e = m.face_adjacency_edges[m.face_adjacency_angles > 0.6]
    if len(e) > 4000: e = e[np.random.default_rng(0).choice(len(e), 4000, replace=False)]
    MESH[b["typ"]] = np.asarray(m.triangles, np.float32).tobytes()
    lo, hi = m.bounds; PIV[b["typ"]] = [float((lo[0] + hi[0]) / 2), float((lo[1] + hi[1]) / 2), float(lo[2])]   # Drehpunkt/Skalenanker = Huellmitte (x,y), Unterkante (z) des AKTUELLEN Teils
    CACHE[k] = np.hstack([V[e[:, 0]], V[e[:, 1]]]).round(3).tolist(); return CACHE[k]

def dt_foto(foto):
    if foto not in DT:
        g = cv2.imread(os.path.join(a.bilder, foto), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION); g = cv2.resize(g, (SW, int(g.shape[0] * SW / g.shape[1])), interpolation=cv2.INTER_AREA)
        ed = cv2.Canny(cv2.GaussianBlur(g, (3, 3), 0), 60, 140); DT[foto] = cv2.distanceTransform(255 - ed, cv2.DIST_L2, 3)
    return DT[foto]

WOLKE = {}
def wolke_abstand(n=200000):
    """Wolkenpunkte (Teilmenge) + Abstand zur Modelloberflaeche (alle Bauteile, Oberflaechenproben, KD-Baum): float32 [x,y,z,d]. Neu bei geaenderter objekt.json."""
    from scipy.spatial import cKDTree
    mt = os.path.getmtime(OJ)
    if WOLKE.get("mt") == mt: return WOLKE["b"]
    if "Pf" not in WOLKE: WOLKE["Pf"] = np.load(a.wolke)[:, :3].astype(np.float32)
    S = []
    for b in obj()["bauteile"]:
        if b.get("aktiv", True) is False: continue
        with LOCK: E = kanten(b, mt)
        if not E or b["typ"] not in MESH: continue
        T = np.frombuffer(MESH[b["typ"]], np.float32).reshape(-1, 3, 3).astype(np.float64); ar = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
        if ar.sum() < 1e-6: continue
        k = int(min(60000, max(500, ar.sum() * 400))); i = np.random.default_rng(1).choice(len(T), k, p=ar / ar.sum()); r1, r2 = np.random.default_rng(2).random((2, k)); f = r1 + r2 > 1; r1[f], r2[f] = 1 - r1[f], 1 - r2[f]
        S.append(T[i, 0] + (T[i, 1] - T[i, 0]) * r1[:, None] + (T[i, 2] - T[i, 0]) * r2[:, None])
    S = np.vstack(S); lo, hi = S.min(0) - 1.5, S.max(0) + 1.5; Pf = WOLKE["Pf"]; Pf = Pf[np.all((Pf >= lo) & (Pf <= hi), 1)]       # nur Wolke im Umkreis (1,5 m) um das Modell, nicht Nachbarhaeuser/Boden
    P = Pf[np.random.default_rng(0).choice(len(Pf), min(n, len(Pf)), replace=False)]; d = cKDTree(S).query(P)[0].astype(np.float32); WOLKE.update(mt=mt, b=np.hstack([P, d[:, None]]).astype(np.float32).tobytes()); return WOLKE["b"]

def ebenen():
    """Ebenen-Vorschlaege aus der Wolke (GPU-RANSAC): Ebenen, die nur um die Fassadenrichtung u geneigt sind (Linie im (s,z)-Schnitt), je zusammenhaengende Flaeche
    ein Vorschlag mit Umrisspolygon (u,v) in Freiform-Koordinaten. Nur Wolke (Regel: Wolke legt Lage fest; Form/Name bestimmt der Nutzer)."""
    import torch, scipy.ndimage as ndi
    if "E" in WOLKE: return WOLKE["E"]
    wolke_abstand()                                    # fuellt MESH + Wolke
    T = np.vstack([np.frombuffer(m, np.float32).reshape(-1, 3) for m in MESH.values()]); lo, hi = T.min(0) - 0.7, T.max(0) + 0.7
    Pf = WOLKE["Pf"]; Pf = Pf[np.all((Pf >= lo) & (Pf <= hi), 1)].astype(np.float64)
    U_ = uax(); n_ = np.array(obj()["fassade_n"]["wert"], float); n_ /= np.linalg.norm(n_)
    q = np.c_[Pf[:, :2] @ U_, Pf[:, :2] @ n_, Pf[:, 2]]; dev = "cuda" if torch.cuda.is_available() else "cpu"
    rem = np.ones(len(q), bool); minN = max(800, int(0.003 * len(q))); out = []; rng = np.random.default_rng(5); tol = 0.06
    for it in range(40):
        idx = np.nonzero(rem)[0]
        if len(idx) < minN: break
        sub = idx[rng.choice(len(idx), min(len(idx), 250000), replace=False)]; R = torch.tensor(q[sub][:, 1:], dtype=torch.float32, device=dev); M = len(sub)
        best = (-1, None)
        for ch in range(12):
            i1 = torch.randint(0, M, (250,), device=dev); i2 = torch.randint(0, M, (250,), device=dev); p1, p2 = R[i1], R[i2]; d = p2 - p1; L = d.norm(dim=1); ok = L > 0.5
            nn = torch.stack([-d[:, 1], d[:, 0]], 1) / L.clamp(min=1e-6)[:, None]; dist = ((R[None, :, :] - p1[:, None, :]) * nn[:, None, :]).sum(2).abs(); cnt = (dist < tol).sum(1); cnt[~ok] = 0
            j = int(cnt.argmax())
            if int(cnt[j]) > best[0]: best = (int(cnt[j]), (nn[j].cpu().numpy().astype(np.float64), float((nn[j] * p1[j]).sum())))
        if best[0] * len(idx) / M < minN: break
        nrm, dd = best[1]
        for _ in range(2):                                   # Verfeinern: Ausgleich ueber alle Inlier
            dist = np.abs(q[idx][:, 1:] @ nrm - dd); inl = idx[dist < tol]
            if len(inl) < 10: break
            c = q[inl][:, 1:].mean(0); w, V = np.linalg.eigh(np.cov((q[inl][:, 1:] - c).T)); nrm = V[:, 0]; dd = float(nrm @ c)
        dist = np.abs(q[idx][:, 1:] @ nrm - dd); inl = idx[dist < tol]; rem[inl] = False
        if len(inl) < minN: continue
        a_, b_ = nrm; ds, dz = -b_, a_
        if dz < 0: ds, dz = -ds, -dz
        al = np.arctan2(ds, dz); sn, cn = np.sin(al), np.cos(al); c = q[inl][:, 1:].mean(0); s0, z0 = float(c[0]), float(c[1])
        qi = q[inl]; v = (qi[:, 1] - s0) * sn + (qi[:, 2] - z0) * cn; uu = qi[:, 0]; cell = 0.25
        g = np.zeros((int((uu.max() - uu.min()) / cell) + 3, int((v.max() - v.min()) / cell) + 3), int); gi = ((uu - uu.min()) / cell).astype(int) + 1; gj = ((v - v.min()) / cell).astype(int) + 1; np.add.at(g, (gi, gj), 1)
        lab, nl = ndi.label(g >= 2, structure=np.ones((3, 3)))
        for l in range(1, nl + 1):
            sel = lab[gi, gj] == l
            if sel.sum() < minN: continue
            fi = 0.08; u_l, v_l = uu[sel], v[sel]; u0, v0 = u_l.min(), v_l.min(); H = np.zeros((int((v_l.max() - v0) / fi) + 5, int((u_l.max() - u0) / fi) + 5), np.uint8)
            H[((v_l - v0) / fi).astype(int) + 2, ((u_l - u0) / fi).astype(int) + 2] = 255; H = cv2.morphologyEx(H, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
            cs, _ = cv2.findContours(H, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cs: continue
            cc = max(cs, key=cv2.contourArea); ap = cv2.approxPolyDP(cc, 0.12 / fi, True)[:, 0, :].astype(float)
            if len(ap) < 3: continue
            poly = np.c_[ap[:, 0] * fi + u0 - 2 * fi, ap[:, 1] * fi + v0 - 2 * fi].round(3).tolist()
            rms = float(np.sqrt(np.mean((qi[sel][:, 1:] @ nrm - dd) ** 2)))
            out.append(dict(id=len(out), npts=int(sel.sum()), neig=round(float(np.degrees(al)), 2), s0=round(s0, 3), z0=round(z0, 3), poly=poly, rms=round(rms, 3), flaeche=round(float(cv2.contourArea(cc) * fi * fi), 1)))
    out.sort(key=lambda e: -e["npts"]); 
    for i, e in enumerate(out): e["id"] = i
    WOLKE["E"] = out; WOLKE["Emt"] = os.path.getmtime(OJ); return out

ORC = {}; ORD = {}
ORC_LAST = {}
def ortho(s0, z0, neig, vor, hinter, px=0.025, schnell=False):
    k = (round(s0, 3), round(z0, 3), round(neig, 2), round(vor, 2), round(hinter, 2), px, bool(schnell))
    if k not in ORC: ORC[k] = ortho_(s0, z0, neig, vor, hinter, px, schnell); ORD[k] = ORD["last"]; ORD[k]["meth"] = ORD["meth"]; ORD[k]["lin"] = ORC[k]["linien"]
    ORD["last"] = ORD[k]; ORD["meth"] = ORD[k]["meth"]; ORC_LAST["bild"] = ORC[k]["bild"]; return ORC[k]

def ortho_(s0, z0, neig, vor, hinter, px=0.025, schnell=False):
    """Ortho-Ansicht der Wolke auf einer Ebene (Linie im (s,z)-Schnitt, Neigung um u): Blick von aussen, +u links. Farbbild + erkannte Kanten
    (Farbkanten 'f' und Tiefenkanten 't', LSD) in (u,v). Nur Wolke; Kantenlisten sind Vorschlaege, der Nutzer waehlt (Regel: Wolke legt Lage fest, Nutzer benennt)."""
    import base64
    if not MESH: wolke_abstand()
    T = np.vstack([np.frombuffer(m, np.float32).reshape(-1, 3) for m in MESH.values()]); lo, hi = T.min(0) - 0.7, T.max(0) + 0.7
    if "Pf" not in WOLKE: WOLKE["Pf"] = np.load(a.wolke)[:, :3].astype(np.float32)
    if "RGB" not in WOLKE: WOLKE["RGB"] = np.load(os.path.join(os.path.dirname(a.wolke), "j_crop_rgb2.npy"))
    m0 = np.all((WOLKE["Pf"] >= lo) & (WOLKE["Pf"] <= hi), 1); Pf = WOLKE["Pf"][m0].astype(np.float64); C = WOLKE["RGB"][m0]
    U_ = uax(); n_ = np.array(obj()["fassade_n"]["wert"], float); n_ /= np.linalg.norm(n_)
    u = Pf[:, :2] @ U_; sS = Pf[:, :2] @ n_; z = Pf[:, 2]; al = np.radians(neig); sn, cn = np.sin(al), np.cos(al)
    t = (sS - s0) * cn - (z - z0) * sn; v = (sS - s0) * sn + (z - z0) * cn; k = (t >= -hinter) & (t <= vor)
    if k.sum() < 1000: return dict(fehler="zu wenige Punkte in dieser Ebene (%d)" % int(k.sum()))
    u, v, t, C = u[k], v[k], t[k], C[k]; um, vm = u.max(), v.max(); W = int((um - u.min()) / px) + 2; Hh = int((vm - v.min()) / px) + 2
    o = np.argsort(t); xi = ((um - u[o]) / px).astype(int); yi = ((vm - v[o]) / px).astype(int)
    img = np.zeros((Hh, W, 3), np.uint8); dep = np.full((Hh, W), np.nan, np.float32); img[yi, xi] = C[o][:, ::-1]; dep[yi, xi] = t[o]
    mk = (~np.isnan(dep)).astype(np.float32); bl = cv2.GaussianBlur(img.astype(np.float32), (0, 0), 2.0); bm = cv2.GaussianBlur(mk, (0, 0), 2.0)
    fill = (bl / np.maximum(bm[:, :, None], 1e-3)).astype(np.uint8); img2 = np.where(mk[:, :, None] > 0, img, fill); img2[bm < 0.02] = 0
    d0 = np.where(np.isnan(dep), -hinter, dep); d0 = cv2.medianBlur(((d0 + hinter) / (vor + hinter) * 255).clip(0, 255).astype(np.uint8), 3)
    if schnell:                                               # nur Geometrie (fuer SAM/Foto-Entzerrung): keine CPU-Kantensuche auf der Wolken-Ortho
        jpg = cv2.imencode(".jpg", img2, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes()
        ORD["last"] = dict(dep=dep, mk=(bm >= 0.02), px=px, vor=vor, hinter=hinter, u0=float(um), v0=float(vm), s0=s0, z0=z0, neig=neig, gray=cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY), d8=d0); ORD["meth"] = (np.zeros((0, 4)), np.array([]), np.array([]))
        return dict(bild="data:image/jpeg;base64," + base64.b64encode(jpg).decode(), w=W, h=Hh, u0=float(um), v0=float(vm), px=px, linien=[], s0=s0, z0=z0, neig=neig, punkte=int(k.sum()))
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD); hsv = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV); lab = cv2.cvtColor(img2, cv2.COLOR_BGR2LAB)
    kan = {"grau": cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY), "R": img2[:, :, 2], "G": img2[:, :, 1], "B": img2[:, :, 0], "Farbton": hsv[:, :, 0] * 1, "Saettigung": hsv[:, :, 1], "Lab-a": lab[:, :, 1], "Lab-b": lab[:, :, 2], "Tiefe": d0}
    segs = []; mid = []; minl = 0.3 / px
    for name, g in kan.items():                                   # Kanal x Kontraststufe durchsweepen, jede Kombination ist ein eigenes Verfahren
        gf = g.astype(np.float32); lo_, hi_ = np.percentile(g, 2), np.percentile(g, 98); stretch = np.clip((gf - lo_) / max(hi_ - lo_, 1) * 255, 0, 255).astype(np.uint8)
        varianten = [("n", g, 1.0), ("clahe", cv2.createCLAHE(3.0, (8, 8)).apply(g), 1.0), ("fein", cv2.GaussianBlur(g, (0, 0), 1.5), 1.0), ("gamma-dunkel", (255 * (gf / 255) ** 0.6).astype(np.uint8), 1.0), ("gamma-hell", (255 * (gf / 255) ** 1.7).astype(np.uint8), 1.0),
                     ("kontrast", stretch, 1.0), ("bilateral", cv2.bilateralFilter(g, 7, 40, 5), 1.0), ("halbskala", cv2.resize(g, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA), 0.5)]
        for var, gg, sk in varianten:
            Ls = lsd.detect(gg)[0]
            if Ls is None: continue
            Ls = np.asarray(Ls).reshape(-1, 4) / sk; Ls = Ls[np.hypot(Ls[:, 2] - Ls[:, 0], Ls[:, 3] - Ls[:, 1]) > minl]; Ls = Ls[np.argsort(-np.hypot(Ls[:, 2] - Ls[:, 0], Ls[:, 3] - Ls[:, 1]))][:700]
            segs.append(Ls); mid += [(name + "/" + var, name)] * len(Ls)
    try:                                                   # Phasenkongruenz (helligkeits-/kontrastunabhaengig, Kovesi): PC-Karte -> LSD; eigene Verfahren fuer Bewertung
        from phasepack import phasecong
        for name in ("grau", "Lab-a", "Lab-b", "Tiefe"):
            pc = phasecong(kan[name].astype(np.float64), nscale=4, norient=6)[0]; pc8 = (np.clip(pc / max(np.percentile(pc, 99.5), 1e-6), 0, 1) * 255).astype(np.uint8)
            for var, gg in (("pc", pc8), ("pc-fein", cv2.GaussianBlur(pc8, (0, 0), 1.2))):
                Ls = lsd.detect(gg)[0]
                if Ls is None: continue
                Ls = np.asarray(Ls).reshape(-1, 4); Ls = Ls[np.hypot(Ls[:, 2] - Ls[:, 0], Ls[:, 3] - Ls[:, 1]) > minl]; Ls = Ls[np.argsort(-np.hypot(Ls[:, 2] - Ls[:, 0], Ls[:, 3] - Ls[:, 1]))][:700]
                segs.append(Ls); mid += [(name + "/" + var, "PC-" + name)] * len(Ls)
    except Exception as e_: print("Phasenkongruenz uebersprungen:", e_)
    S = np.vstack(segs); meth = np.array([m[0] for m in mid]); fam = np.array([m[1] for m in mid]); ln = np.hypot(S[:, 2] - S[:, 0], S[:, 3] - S[:, 1]); o2 = np.argsort(-ln); S, meth, fam, ln = S[o2], meth[o2], fam[o2], ln[o2]
    ORD["meth"] = (S.copy(), meth.copy(), fam.copy()); d = (S[:, 2:] - S[:, :2]) / ln[:, None]; ang = np.arctan2(d[:, 1], d[:, 0]) % np.pi; used = np.zeros(len(S), bool); out = []
    for i in range(len(S)):
        if used[i]: continue
        di = d[i]; nrm = np.array([-di[1], di[0]]); p0 = S[i, :2]
        da = np.abs(((ang - ang[i] + np.pi / 2) % np.pi) - np.pi / 2); pd = np.maximum(np.abs((S[:, :2] - p0) @ nrm), np.abs((S[:, 2:] - p0) @ nrm))
        a1_ = (S[:, :2] - p0) @ di; a2_ = (S[:, 2:] - p0) @ di; lo_, hi_ = np.minimum(a1_, a2_), np.maximum(a1_, a2_)
        g_ = (~used) & (da < np.radians(4)) & (pd < 5) & (hi_ > -0.2 / px) & (lo_ < ln[i] + 0.2 / px); g_[i] = True
        used |= g_; ex = np.r_[lo_[g_], hi_[g_]]; t0, t1 = ex.min(), ex.max(); votes = len(set(meth[g_])); fam_n = len(set(fam[g_]))
        if t1 - t0 < minl: continue
        q0 = p0 + di * t0; q1 = p0 + di * t1; out.append([round(float(q0[0]), 1), round(float(q0[1]), 1), round(float(q1[0]), 1), round(float(q1[1]), 1), votes, fam_n, "t" if "Tiefe" in set(fam[g_]) else "f"])
    out.sort(key=lambda l: -(l[4]))
    jpg = cv2.imencode(".jpg", img2, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes()
    ORD["last"] = dict(dep=dep, mk=(bm >= 0.02), px=px, vor=vor, hinter=hinter, u0=float(um), v0=float(vm), s0=s0, z0=z0, neig=neig, gray=cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY), d8=d0)
    return dict(bild="data:image/jpeg;base64," + base64.b64encode(jpg).decode(), w=W, h=Hh, u0=float(um), v0=float(vm), px=px, linien=out, s0=s0, z0=z0, neig=neig, punkte=int(k.sum()))

def regionen(linien, minfl=0.05, luecke=12):
    """Geschlossene Flaechen zwischen den (vom Nutzer gesichteten) Kanten der letzten Ortho-Ansicht: Kanten + Luecken ohne Wolke sind Wand, Rest zerfaellt in Zellen (Zusammenhangskomponenten).
    Rueckgabe je Zelle Umriss (Bildpixel), Flaeche m2, mittlere Tiefe (m vor der Ebene), Rechteckigkeit."""
    d = ORD["last"]; dep, mk, px = d["dep"], d["mk"], d["px"]; H, W = dep.shape; wand = np.zeros((H, W), np.uint8)
    for l in linien: cv2.line(wand, (int(round(l[0])), int(round(l[1]))), (int(round(l[2])), int(round(l[3]))), 255, 2)
    if luecke > 0:                                          # Linienenden in Verlaengerungsrichtung bis zur naechsten Kante verlaengern (Luecken schliessen, max. 'luecke' Pixel)
        w1 = wand.copy()
        for l in linien:
            x1, y1, x2, y2 = l[:4]; L = np.hypot(x2 - x1, y2 - y1)
            if L < 3: continue
            dx, dy = (x2 - x1) / L, (y2 - y1) / L
            for (px_, py_, sg) in ((x2, y2, 1), (x1, y1, -1)):
                for t in range(4, luecke + 1):
                    qx, qy = int(round(px_ + sg * dx * t)), int(round(py_ + sg * dy * t))
                    if not (0 <= qx < W and 0 <= qy < H): break
                    if wand[qy, qx]: cv2.line(w1, (int(round(px_)), int(round(py_))), (qx, qy), 255, 2); break
        wand = w1
    wand[~mk] = 255; frei = (wand == 0).astype(np.uint8); n, lab, st, cen = cv2.connectedComponentsWithStats(frei, connectivity=4); gesamt = int(mk.sum()); out = []
    for i in range(1, n):
        ar = st[i, cv2.CC_STAT_AREA]; m2 = ar * px * px
        if m2 < minfl or ar > 0.4 * gesamt: continue
        reg = (lab[st[i, 1]:st[i, 1] + st[i, 3], st[i, 0]:st[i, 0] + st[i, 2]] == i).astype(np.uint8)
        cs, _ = cv2.findContours(np.pad(reg, 1), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cs: continue
        c = max(cs, key=cv2.contourArea); ap = cv2.approxPolyDP(c, 4.5, True)[:, 0, :].astype(float)
        if len(ap) < 3: continue
        ap = ap - 1 + [st[i, 0], st[i, 1]]; tt = dep[st[i, 1]:st[i, 1] + st[i, 3], st[i, 0]:st[i, 0] + st[i, 2]][reg > 0]; tt = tt[~np.isnan(tt)]
        rr = cv2.minAreaRect(c.astype(np.float32)); rect = float(cv2.contourArea(c) / max(rr[1][0] * rr[1][1], 1e-6))
        out.append(dict(poly=ap.round(1).tolist(), m2=round(float(m2), 2), t=round(float(np.median(tt)), 2) if len(tt) else None, rect=round(rect, 2)))
    out.sort(key=lambda e: -e["m2"]); ORD["regs"] = out[:500]; return out[:500]

def gleiche(poly, thr=0.5, eigene_skala=False):
    """Gleiche Elemente zu einem Beispiel-Polygon (Bildpixel) finden (Template-Matching auf Grau + Tiefe der Ortho-Ansicht, normierte Kreuzkorrelation), je Treffer die passende
    automatische Zelle (falls vorhanden) als Instanz nehmen, alle Instanzen ausrichten und zu EINER Form mitteln (tools/kontur_mittel.py). Zaehlung/Anzahl bleibt Sache des Nutzers (Foto, Regel 9):
    die Treffer sind nur Vorschlaege."""
    import kontur_mittel as KM
    d = ORD["last"]; P = np.array(poly, float); x0, y0 = np.floor(P.min(0)).astype(int) - 3; x1, y1 = np.ceil(P.max(0)).astype(int) + 3; H, W = d["gray"].shape
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H); mask = np.zeros((y1 - y0, x1 - x0), np.uint8); cv2.fillPoly(mask, [np.round(P - [x0, y0]).astype(np.int32)], 255)
    res = 0
    for k in ("gray",):                                    # Suche nur im Helligkeitsbild: Tiefenbild ist rauschig, ganzes Fenster als Vorlage liefert gleiche Fenster mit r ~ 0,5-0,6 (gemessen)
        im = d[k]; tpl = im[y0:y1, x0:x1]; r = cv2.matchTemplate(im, tpl, cv2.TM_CCOEFF_NORMED, mask=mask); r = np.nan_to_num(r, nan=-1, posinf=-1, neginf=-1).clip(-1, 1); res = res + r
    kk = max(3, int(0.6 * min(x1 - x0, y1 - y0))) | 1; mx = cv2.dilate(res, np.ones((kk, kk), np.uint8)); pk = np.argwhere((res >= mx - 1e-6) & (res >= thr)); pk = pk[np.argsort(-res[pk[:, 0], pk[:, 1]])][:60]
    treffer = [(int(x), int(y), float(res[y, x])) for y, x in pk]; cen0 = P.mean(0); ar0 = abs(KM.flaeche(KM.ccw(P))); zellen = ORD.get("regs", []); inst = []; src = []
    for (x, y, sc) in treffer:
        dx, dy = x - x0, y - y0; c = cen0 + [dx, dy]; best = None
        for z in zellen:
            Z = np.array(z["poly"], float); zc = Z.mean(0); ar = abs(KM.flaeche(KM.ccw(Z)))
            if np.hypot(*(zc - c)) < 0.35 * max(x1 - x0, y1 - y0) and 0.6 < ar / ar0 < 1.6 and (best is None or np.hypot(*(zc - c)) < best[0]): best = (np.hypot(*(zc - c)), Z)
        inst.append(best[1] if best is not None else P + [dx, dy]); src.append("Zelle" if best is not None else "Kopie")
    if len(inst) < 2: return dict(instanzen=[], fehler="keine weiteren Treffer (Schwelle senken?)", treffer=treffer)
    ed = cv2.Canny(cv2.GaussianBlur(d["gray"], (3, 3), 0), 40, 110) | cv2.Canny(d["d8"], 30, 90); dt = np.minimum(cv2.distanceTransform(255 - ed, cv2.DIST_L2, 3), 10.0)     # Abstand zur naechsten Farb-/Tiefenkante
    def passung(Pq):
        Q = np.asarray(Pq, float); Q2 = np.vstack([Q, Q[:1]]); seg = np.hypot(*np.diff(Q2, axis=0).T); n = np.maximum((seg / 2).astype(int), 1); pts = np.vstack([Q2[i] + (Q2[i + 1] - Q2[i]) * (np.arange(n[i]) / n[i])[:, None] for i in range(len(Q))])
        return pts
    def verfeinern(Pq):                                      # Lage (+-6 px) und Groesse (+-4 %) je Instanz an den Kanten nachziehen
        Pq = np.asarray(Pq, float); c = Pq.mean(0); best = (1e9, Pq)
        for sc_ in (0.96, 0.98, 1.0, 1.02, 1.04):
            for dy in range(-6, 7):
                for dx in range(-6, 7):
                    Q = (Pq - c) * sc_ + c + [dx, dy]; pts = passung(Q); xi = np.clip(pts[:, 0].round().astype(int), 0, W - 1); yi = np.clip(pts[:, 1].round().astype(int), 0, H - 1); cst = float(dt[yi, xi].mean())
                    if cst < best[0]: best = (cst, Q)
        return best[1], best[0]
    inst2 = []; pas = []
    for I in inst:
        Q, cst = verfeinern(I); inst2.append(Q); pas.append(cst)
    inst = inst2; m = KM.mittelform(inst); out = []
    for i, (I, sr, sc) in enumerate(zip(inst, src, treffer)):
        Mf = KM.vereinfachen(KM.platzieren(m, i, eigene_skala), 2.0); out.append(dict(roh=np.asarray(I).round(1).tolist(), mittel=Mf.round(1).tolist(), quelle=sr, score=round(sc[2], 2), abw_px=round(m["abweichung"][i], 1), passung_px=round(pas[i], 1)))
    return dict(instanzen=out, skala_px=round(m["skala"], 1), px=d["px"])

def boegen(linien, px, rmin_m=0.5, rmax_m=4.0):
    import kontur_mittel as KM
    pts, dirs = [], []
    for l in linien:
        L = np.hypot(l[2] - l[0], l[3] - l[1]); n = int(L / 2) + 2; t = np.linspace(0, 1, n); pts.append(np.c_[l[0] + t * (l[2] - l[0]), l[1] + t * (l[3] - l[1])]); dirs.append(np.tile([(l[2] - l[0]) / max(L, 1e-6), (l[3] - l[1]) / max(L, 1e-6)], (n, 1)))
    if not pts: return []
    B = KM.boegen_finden(np.vstack(pts), rmin_m / px, rmax_m / px, D=np.vstack(dirs), tol=2.5); out = []
    for b in B:
        w = 2 * b["r"] * np.sin(min(np.radians(b["spann_grad"]), np.pi) / 2); st = b["r"] * (1 - np.cos(np.radians(b["spann_grad"]) / 2)) if b["spann_grad"] < 180 else b["r"]
        out.append(dict(poly=KM.bogenlinie(b).round(1).tolist(), r_m=round(b["r"] * px, 2), spann=round(b["spann_grad"]), breite_m=round(w * px, 2), stich_m=round(st * px, 2), n=b["n"]))
    return out

def maske_zu_flaechen(w, h, daten, eps=3.0, schliessen=5):
    """Nutzermaske (Spraydose/Zauberstab, 0/1 je Bildpixel) -> bereinigte Umrisse: Schliessen (Luecken), Oeffnen (Sprenkel), aeussere Konturen, Vereinfachen. Rueckgabe Liste dict(poly, m2) absteigend nach Flaeche."""
    m = (np.frombuffer(daten, np.uint8).reshape(h, w) > 0).astype(np.uint8) * 255; px = ORD["last"]["px"]
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((schliessen, schliessen), np.uint8)); m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); out = []
    for c in cs:
        ar = cv2.contourArea(c)
        if ar < 30: continue
        ap = cv2.approxPolyDP(c, eps, True)[:, 0, :].astype(float)
        if len(ap) >= 3: out.append(dict(poly=ap.round(1).tolist(), m2=round(float(ar * px * px), 2), rect=0))
    out.sort(key=lambda e: -e["m2"]); return out[:20]

def pfad(wp, eps=1.2):
    """Kante nachzeichnen: Wegpunkte (Bildpixel, grob vom Nutzer gezogen) -> kuerzester Weg durch die Kantenkarte (Farb- und Tiefenkanten) von Punkt zu Punkt ('intelligente Schere'),
    dadurch rastet die gezeichnete Linie auf der echten Kante ein. Rueckgabe vereinfachter Linienzug."""
    from skimage.graph import route_through_array
    d = ORD["last"]
    if "cost" not in d:
        ed = cv2.Canny(cv2.GaussianBlur(d["gray"], (3, 3), 0), 40, 110) | cv2.Canny(d["d8"], 30, 90); d["cost"] = 1.0 + 3.0 * np.minimum(cv2.distanceTransform(255 - ed, cv2.DIST_L2, 3), 8.0)
    C = d["cost"]; H, W = C.shape; out = []
    for a, b in zip(wp[:-1], wp[1:]):
        x0, y0 = int(round(a[0])), int(round(a[1])); x1, y1 = int(round(b[0])), int(round(b[1])); m = 30
        X0, Y0, X1, Y1 = max(min(x0, x1) - m, 0), max(min(y0, y1) - m, 0), min(max(x0, x1) + m, W - 1), min(max(y0, y1) + m, H - 1)
        if not (0 <= x0 < W and 0 <= y0 < H and 0 <= x1 < W and 0 <= y1 < H): continue
        pth, _ = route_through_array(C[Y0:Y1 + 1, X0:X1 + 1], (y0 - Y0, x0 - X0), (y1 - Y0, x1 - X0), fully_connected=True, geometric=True)
        out += [(px_ + X0, py_ + Y0) for py_, px_ in (pth if not out else pth[1:])]
    if len(out) < 2: return []
    ap = cv2.approxPolyDP(np.array(out, np.float32).reshape(-1, 1, 2), eps, False)[:, 0, :]; return ap.round(1).tolist()

def gruppen(thr=0.12, minfl=0.15):
    """Aufbau-Vorschlag: die automatischen Zellen (letzte /api/regionen) nach Form, Groesse und Tiefe zu Gruppen gleicher Elemente zusammenfassen (z. B. 5 gleiche Fenster, 4 Boegen);
    je Gruppe Mittelform (tools/kontur_mittel.py) und die Tiefe relativ zur Wandflaeche (Median-Tiefe der groessten Zelle) AUS DER WOLKE, damit die Tiefe der Bauteile gemessen statt angenommen ist."""
    import kontur_mittel as KM
    zellen = [z for z in ORD.get("regs", []) if z["m2"] >= minfl and z["t"] is not None]
    if not zellen: return dict(gruppen=[], fehler="erst Flaechen vorschlagen")
    wand_t = zellen[0]["t"]; px = ORD["last"]["px"]; desc = []
    for z in zellen:
        P = KM.ccw(np.array(z["poly"], float)); U = KM.umtasten(P, 32); a = np.sqrt(abs(KM.flaeche(P))); desc.append(((U - U.mean(0)) / a, a))
    def dist(A, B):
        return min(float(np.mean(np.hypot(*(np.roll(A, k, axis=0) - B).T))) for k in range(32))
    gr = []
    for i, z in enumerate(zellen):
        for g in gr:
            j = g["idx"][0]
            if 0.8 < z["m2"] / zellen[j]["m2"] < 1.25 and abs(z["t"] - zellen[j]["t"]) < 0.06 and dist(desc[i][0], desc[j][0]) < thr: g["idx"].append(i); break
        else: gr.append(dict(idx=[i]))
    out = []
    for g in gr:
        ix = g["idx"]
        if len(ix) < 2 and zellen[ix[0]]["m2"] < 0.3: continue
        polys = [zellen[i]["poly"] for i in ix]; m = KM.mittelform(polys) if len(ix) >= 2 else None
        mittel = [KM.vereinfachen(KM.platzieren(m, k, False), 2.0).round(1).tolist() for k in range(len(ix))] if m else polys
        dt = float(np.mean([zellen[i]["t"] for i in ix]) - wand_t)
        out.append(dict(n=len(ix), m2=round(float(np.mean([zellen[i]["m2"] for i in ix])), 2), dt=round(dt, 3), rect=round(float(np.mean([zellen[i].get("rect", 0) for i in ix])), 2), roh=polys, mittel=mittel,
                        abw_cm=round(float(np.mean(m["abweichung"])) * px * 100, 1) if m else None))
    out.sort(key=lambda e: (-e["n"], -e["m2"])); return dict(gruppen=out[:60], wand_t=round(float(wand_t), 3))

WFILE = os.path.join(os.path.dirname(OJ), "kanten_wahrheit.jsonl")
def wahrheit_speichern(d):
    """vom Nutzer bestaetigte Kanten (nachgezeichnet/gezogen/Umriss erzeugter Bauteile) mit Ortho-Parametern ablegen, damit Kantenverfahren daran gemessen werden koennen"""
    with open(WFILE, "a") as f: f.write(json.dumps(dict(zeit=datetime.datetime.now().isoformat(timespec="seconds"), art=d.get("art", ""), plane=d["plane"], linien=d["linien"])) + "\n")
    return sum(1 for _ in open(WFILE))

def kanten_bewerten(tol=3.0):
    """Trefferquote (Recall) je Verfahren und fuer die Stimmen-Zusammenfuehrung gegen die bestaetigten Kanten der aktuellen Ortho-Ebene: Anteil der Wahrheits-Linienlaenge, der innerhalb tol Pixel
    einer erkannten Linie liegt. Zusaetzlich Dichte (erkannte Linienlaenge je Bildflaeche), weil Recall allein ein 'alles zeichnen' belohnt."""
    d = ORD["last"]; px = d["px"]; H, W = d["gray"].shape; u0, v0 = d["u0"], d["v0"]; T = []
    if not os.path.exists(WFILE): return dict(fehler="noch keine bestaetigten Kanten (nachzeichnen oder Bauteile erzeugen)")
    for z in open(WFILE):
        r = json.loads(z); pl = r["plane"]
        if abs(pl["s0"] - d["s0"]) < 0.02 and abs(pl["z0"] - d["z0"]) < 0.02 and abs(pl["neig"] - d["neig"]) < 0.2:
            for l in r["linien"]: T.append([(pl["u0"] - l[0] * pl["px"] - 0) , 0, 0, 0] if False else [(u0 - (pl["u0"] - l[0] * pl["px"])) / px, (v0 - (pl["v0"] - l[1] * pl["px"])) / px, (u0 - (pl["u0"] - l[2] * pl["px"])) / px, (v0 - (pl["v0"] - l[3] * pl["px"])) / px])
    if not T: return dict(fehler="keine bestaetigten Kanten fuer diese Ebene")
    T = np.array(T, float); Ls = np.hypot(T[:, 2] - T[:, 0], T[:, 3] - T[:, 1]); tot = float(Ls.sum()); S, meth, fam = d["meth"]; out = []
    P = np.vstack([np.c_[np.linspace(t[0], t[2], max(int(l / 2), 2)), np.linspace(t[1], t[3], max(int(l / 2), 2))] for t, l in zip(T, Ls)])
    def recall(segs):
        if len(segs) == 0: return 0.0
        m = np.zeros((H, W), np.uint8)
        for q in segs: cv2.line(m, (int(round(q[0])), int(round(q[1]))), (int(round(q[2])), int(round(q[3]))), 255, 1)
        dt = cv2.distanceTransform(255 - m, cv2.DIST_L2, 3); xi = P[:, 0].round().astype(int).clip(0, W - 1); yi = P[:, 1].round().astype(int).clip(0, H - 1); return float((dt[yi, xi] <= tol).mean())
    def dichte(segs): return float(np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1]).sum() * px / (H * W * px * px)) if len(segs) else 0.0
    for name in sorted(set(meth)):
        sg = S[meth == name]; out.append(dict(verfahren=name, recall=round(recall(sg), 3), segmente=int(len(sg)), dichte=round(dichte(sg), 3)))
    L = np.array([l[:4] for l in d["lin"]], float)
    for k in (1, 3, 6, 12, 20):
        sg = np.array([l[:4] for l in d["lin"] if l[4] >= k], float).reshape(-1, 4); out.append(dict(verfahren="FUSION >= %d Stimmen" % k, recall=round(recall(sg), 3), segmente=int(len(sg)), dichte=round(dichte(sg), 3)))
    out.sort(key=lambda e: -e["recall"]); return dict(tabelle=out, wahrheit_laenge_m=round(tot * px, 1), n_linien=int(len(T)))

def modellkanten_px(d, winkel=25.0, minlaenge_px=40, kamera=None, slab=None):
    """Kanten des Modells (Knickkanten der Teilnetze, Winkel > winkel) in die Pixel der Ortho-Ansicht d projizieren; nur Kanten in der Ortho-Scheibe. Unabhaengig von den Kantenverfahren (Modell stammt aus Wolke+Fotos+Nutzer)."""
    U_ = uax(); n_ = np.array(obj()["fassade_n"]["wert"], float); n_ /= np.linalg.norm(n_); al = np.radians(d["neig"]); sn, cn = np.sin(al), np.cos(al); px = d["px"]; out = []
    for typ, b in MESH.items():
        T = np.frombuffer(b, np.float32).reshape(-1, 3).astype(np.float64)
        try: m = trimesh.Trimesh(T, np.arange(len(T)).reshape(-1, 3), process=True); m.merge_vertices()
        except Exception: continue
        if len(m.faces) < 2: continue
        adj = m.face_adjacency; ang = np.degrees(m.face_adjacency_angles); e = m.face_adjacency_edges[ang > winkel]
        # Randkanten (nur eine Flaeche) ebenfalls
        if len(e) == 0: continue
        P = m.vertices[e]                                          # (n,2,3)
        u = P[..., :2] @ U_; sS = P[..., :2] @ n_; z = P[..., 2]; t = (sS - d["s0"]) * cn - (z - d["z0"]) * sn; v = (sS - d["s0"]) * sn + (z - d["z0"]) * cn
        ok = np.all((t >= -(slab or d["hinter"])) & (t <= (slab or d["vor"])), 1)
        if kamera is not None:                                    # Kante durch die Kamera auf die Ebene (t=0) abbilden: so sieht sie das entzerrte Foto (Parallaxe!)
            C_ = np.array(kamera["C"], float); nrm_ = np.array([n_[0] * cn, n_[1] * cn, -sn]); p0_ = np.r_[d["s0"] * n_, d["z0"]]
            for i in np.where(ok)[0]:
                Q = []
                for X in P[i]:
                    dv = X - C_; den = float(dv @ nrm_)
                    if abs(den) < 1e-6: Q = None; break
                    lam = float((p0_ - C_) @ nrm_) / den; Y = C_ + lam * dv; ux = Y[:2] @ U_; sS_ = Y[:2] @ n_; v_ = (sS_ - d["s0"]) * sn + (Y[2] - d["z0"]) * cn; Q.append(((d["u0"] - ux) / px, (d["v0"] - v_) / px))
                if Q: out.append([Q[0][0], Q[0][1], Q[1][0], Q[1][1]])
            continue
        for i in np.where(ok)[0]: out.append([(d["u0"] - u[i, 0]) / px, (d["v0"] - v[i, 0]) / px, (d["u0"] - u[i, 1]) / px, (d["v0"] - v[i, 1]) / px])
    out = np.array(out, float).reshape(-1, 4)
    return out[np.hypot(out[:, 2] - out[:, 0], out[:, 3] - out[:, 1]) >= minlaenge_px]

def verfahren_vs_modell(tol=6.0):
    """Trefferquote (Modellkante von Verfahren erkannt) UND Praezision (erkannte Linie liegt an Modellkante) je Verfahren auf der aktuellen Ebene. F = harmonisches Mittel."""
    d = ORD["last"]; M = modellkanten_px(d)
    if len(M) < 5: return dict(fehler="zu wenige Modellkanten in der Scheibe")
    H, W = d["gray"].shape; S, meth, fam = d["meth"]
    def raster(segs):
        m = np.zeros((H, W), np.uint8)
        for q in segs: cv2.line(m, (int(round(q[0])), int(round(q[1]))), (int(round(q[2])), int(round(q[3]))), 255, 1)
        return m
    def samp(segs):
        return np.vstack([np.c_[np.linspace(q[0], q[2], max(int(np.hypot(q[2] - q[0], q[3] - q[1]) / 2), 2)), np.linspace(q[1], q[3], max(int(np.hypot(q[2] - q[0], q[3] - q[1]) / 2), 2))] for q in segs])
    def hit(P, m):
        dt = cv2.distanceTransform(255 - m, cv2.DIST_L2, 3); xi = P[:, 0].round().astype(int).clip(0, W - 1); yi = P[:, 1].round().astype(int).clip(0, H - 1); return float((dt[yi, xi] <= tol).mean())
    PM = samp(M); mM = raster(M); res = []
    def bewerte(name, sg):
        if len(sg) == 0: return
        F_ = lambda r_, p_: 2 * r_ * p_ / max(r_ + p_, 1e-9); rec = hit(PM, raster(sg)); pre = hit(samp(sg), mM); sh = sg + np.array([41.0, 27.0, 41.0, 27.0]); rec0 = hit(PM, raster(sh)); pre0 = hit(samp(sh), mM)   # Zufallsbasis: Linien um (41,27) px versetzt
        res.append(dict(verfahren=name, recall=round(rec, 3), praez=round(pre, 3), F=round(F_(rec, pre), 3), F_zufall=round(F_(rec0, pre0), 3), gewinn=round(F_(rec, pre) - F_(rec0, pre0), 3), seg=int(len(sg))))
    for name in sorted(set(meth)): bewerte(name, S[meth == name])
    for nm in sorted(set(fam)): bewerte("FAMILIE " + nm, S[fam == nm])
    for k in (1, 3, 6, 12, 20, 30): bewerte("FUSION >= %d" % k, np.array([l[:4] for l in d["lin"] if l[4] >= k], float).reshape(-1, 4))
    res.sort(key=lambda e: -e["gewinn"]); return dict(tabelle=res, modellkanten=int(len(M)), tol_px=tol)

def foto_stuetzung(d, anz=12, tol=2.5):
    """Unabhaengige Pruefung der Kantenverfahren an den FOTOS: jeder Linienpunkt (u,v, Tiefe t aus der Wolke) wird in die besten Fotos projiziert (Blick auf die Ebene, cos>0,5);
    Stuetzung = Anteil der Fotos, in denen dort eine Canny-Kante liegt (<= tol px bei 1613 px Breite). Zufallsbasis: dieselben Linien um (41,27) px versetzt. Misst Praezision (Linie ist im Foto sichtbare Kante), nicht Vollstaendigkeit."""
    U_ = uax(); n_ = np.array(obj()["fassade_n"]["wert"], float); n_ = n_[:2] / np.linalg.norm(n_[:2]); al = np.radians(d["neig"]); sn, cn = np.sin(al), np.cos(al); px = d["px"]; H, W = d["gray"].shape
    nrm = np.array([n_[0] * cn, n_[1] * cn, -sn])                  # Ebenennormale (zeigt von Fassade weg, +t)
    mid = np.array([d["u0"] - W / 2 * px, d["v0"] - H / 2 * px]); sS = d["s0"]; c0 = np.r_[(mid[0] * U_ + sS * n_), d["z0"] + mid[1] * cn]     # grobe Ebenenmitte
    sc = []
    for f, K in KAM.items():
        if not os.path.exists(os.path.join(a.bilder, f)): continue
        C = np.array(K["C"], float); v = C - c0; dist = np.linalg.norm(v); cs = float(v @ nrm) / dist
        if cs > 0.5 and 3 < dist < 60: sc.append((dist * (2 - cs), f))
    fotos = [f for _, f in sorted(sc)[:anz]]
    if len(fotos) < 3: return dict(fehler="zu wenige Fotos sehen die Ebene (%d)" % len(fotos))
    dep = d["d8"].astype(np.float32) / 255 * (d["vor"] + d["hinter"]) - d["hinter"]
    S, meth, fam = d["meth"]
    def welt(P):
        x = np.clip(P[:, 0].round().astype(int), 0, W - 1); y = np.clip(P[:, 1].round().astype(int), 0, H - 1); t = dep[y, x]; u = d["u0"] - P[:, 0] * px; v = d["v0"] - P[:, 1] * px
        sS_ = d["s0"] + t * cn + v * sn; z = d["z0"] - t * sn + v * cn; return np.c_[np.outer(u, U_) + np.outer(sS_, n_), z]
    DTs = [dt_foto(f) for f in fotos]
    def stuetz(P):
        X = welt(P); acc = np.zeros(len(X)); cnt = np.zeros(len(X))
        for f, D in zip(fotos, DTs):
            uv, z = proj(KAM[f], X); ok = (z > 1) & (uv[:, 0] >= 0) & (uv[:, 0] < D.shape[1] - 1) & (uv[:, 1] >= 0) & (uv[:, 1] < D.shape[0] - 1)
            x = uv[:, 0].clip(0, D.shape[1] - 1).round().astype(int); y = uv[:, 1].clip(0, D.shape[0] - 1).round().astype(int); acc += ok * (D[y, x] <= tol); cnt += ok
        return acc, cnt
    def samp(sg, off=(0, 0)):
        L = np.hypot(sg[:, 2] - sg[:, 0], sg[:, 3] - sg[:, 1]); n = np.maximum((L / 4).astype(int), 2); P = np.vstack([np.c_[np.linspace(q[0], q[2], k), np.linspace(q[1], q[3], k)] for q, k in zip(sg, n)]) + np.array(off, float)
        idx = np.repeat(np.arange(len(sg)), n); return P, idx
    def bewerte(name, sg):
        if len(sg) < 3: return None
        P, idx = samp(sg); a_, c_ = stuetz(P); ok = c_ >= 3; P0, idx0 = samp(sg, (41, 27)); a0, c0_ = stuetz(P0); ok0 = c0_ >= 3
        if ok.sum() < 10 or ok0.sum() < 10: return None
        pr = float((a_[ok] / c_[ok]).mean()); pz = float((a0[ok0] / c0_[ok0]).mean())
        L = np.hypot(sg[:, 2] - sg[:, 0], sg[:, 3] - sg[:, 1]); li = np.bincount(idx[ok], weights=(a_[ok] / c_[ok]), minlength=len(sg)) / np.maximum(np.bincount(idx[ok], minlength=len(sg)), 1)
        best_m = float((L * (li > 0.5)).sum() * px)                # Laenge der Linien, die in > 50 % der Fotos auf einer Kante liegen
        return dict(verfahren=name, praez=round(pr, 3), zufall=round(pz, 3), gewinn=round(pr - pz, 3), bestaetigt_m=round(best_m, 1), seg=int(len(sg)))
    res = [r for r in (bewerte(nm, S[meth == nm]) for nm in sorted(set(meth))) if r]
    res += [r for r in (bewerte("FAMILIE " + nm, S[fam == nm]) for nm in sorted(set(fam))) if r]
    res += [r for r in (bewerte("FUSION >= %d" % k, np.array([l[:4] for l in d["lin"] if l[4] >= k], float).reshape(-1, 4)) for k in (1, 3, 6, 8, 12, 20, 30)) if r]
    res += [r for r in (bewerte("FUSION Familien >= %d" % k, np.array([l[:4] for l in d["lin"] if l[5] >= k], float).reshape(-1, 4)) for k in (2, 3, 4, 5, 6)) if r]
    res += [r for r in (bewerte("FUSION Lab-b-Stimmen", np.array([l[:4] for l in d["lin"] if l[4] >= 8 and l[5] >= 3], float).reshape(-1, 4)),) if r]
    return dict(tabelle=res, fotos=fotos)

def foto_ortho(d, foto, mitTiefe=False):
    """Ortho-Ansicht der Ebene direkt aus dem FOTO (Homographie, volle Aufloesung) statt aus eingefaerbten Wolkenpunkten: scharfe, gerade Kanten. Rueckgabe BGR-Bild in Ortho-Pixeln (gleiches Raster wie die Wolken-Ortho), Maske gueltig."""
    U_ = uax(); n_ = np.array(obj()["fassade_n"]["wert"], float); n_ = n_[:2] / np.linalg.norm(n_[:2]); al = np.radians(d["neig"]); sn, cn = np.sin(al), np.cos(al); px = d["px"]; H, W = d["gray"].shape
    im = cv2.imread(os.path.join(a.bilder, foto), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); K = KAM[foto]; sc = im.shape[1] / K["W"]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64); u = d["u0"] - xx * px; v = d["v0"] - yy * px
    t = (d["d8"].astype(np.float64) / 255 * (d["vor"] + d["hinter"]) - d["hinter"]) if mitTiefe else np.zeros_like(u)
    sS = d["s0"] + t * cn + v * sn; z = d["z0"] - t * sn + v * cn
    X = np.stack([u * U_[0] + sS * n_[0], u * U_[1] + sS * n_[1], z], -1).reshape(-1, 3)
    Xc = X @ np.array(K["Rn"]).T + np.array(K["tn"]); zc = Xc[:, 2]; uv = (K["f"] * Xc[:, :2] / np.where(zc > 0.5, zc, 0.5)[:, None] + [K["cx"], K["cy"]]) * sc
    mx = uv[:, 0].reshape(H, W).astype(np.float32); my = uv[:, 1].reshape(H, W).astype(np.float32)
    out = cv2.remap(im, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)); ok = (zc.reshape(H, W) > 1) & (mx >= 0) & (mx < im.shape[1]) & (my >= 0) & (my < im.shape[0])
    return out, ok

def beste_fotos(d, anz=6):
    U_ = uax(); n_ = np.array(obj()["fassade_n"]["wert"], float); n_ = n_[:2] / np.linalg.norm(n_[:2]); al = np.radians(d["neig"]); sn, cn = np.sin(al), np.cos(al); px = d["px"]; H, W = d["gray"].shape
    nrm = np.array([n_[0] * cn, n_[1] * cn, -sn]); c0 = np.r_[((d["u0"] - W / 2 * px) * U_ + d["s0"] * n_), d["z0"] + (d["v0"] - H / 2 * px) * cn]; sc = []
    for f, K in KAM.items():
        if not os.path.exists(os.path.join(a.bilder, f)): continue
        v = np.array(K["C"], float) - c0; dist = np.linalg.norm(v); cs = float(v @ nrm) / dist
        if cs > 0.6 and 3 < dist < 60: sc.append((-cs - 0.02 / dist * 0, f))
    return [f for _, f in sorted(sc)[:anz]]

def fotokanten(d, anz=8, tiefe=True, minl_m=0.25, winkel=2.5, abst=2.5):
    """Kanten aus FOTOS: je Foto Ortho (Homographie, scharf) -> Linienfinder auf grau/R/G/B/Lab-b -> Linien ueber die Fotos stapeln; behalten, wenn die Mehrheit der Fotos, die die Stelle sehen,
    die Kante hat; Lage/Ausdehnung = Median ueber die Fotos (Nutzerwunsch 9.11.)."""
    H, W = d["gray"].shape; px = d["px"]; fl = beste_fotos(d, anz); segs = []; masks = []; lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    for fi, f in enumerate(fl):
        im, ok = foto_ortho(d, f, tiefe); ok = cv2.erode(ok.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0; masks.append(ok); lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
        for g in (cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), im[:, :, 2], im[:, :, 1], im[:, :, 0], lab[:, :, 2]):
            g = cv2.GaussianBlur(g, (0, 0), 1.0); L = lsd.detect(g)[0]
            if L is None: continue
            L = np.asarray(L).reshape(-1, 4); ln = np.hypot(L[:, 2] - L[:, 0], L[:, 3] - L[:, 1]); L = L[ln > minl_m / px]
            mx = ((L[:, 0] + L[:, 2]) / 2).astype(int).clip(0, W - 1); my = ((L[:, 1] + L[:, 3]) / 2).astype(int).clip(0, H - 1); L = L[ok[my, mx]]
            segs.append(np.c_[L, np.full(len(L), fi)])
    if not segs: return []
    S = np.vstack(segs); ln = np.hypot(S[:, 2] - S[:, 0], S[:, 3] - S[:, 1]); S = S[np.argsort(-ln)]; ln = np.sort(ln)[::-1]
    th = np.arctan2(S[:, 3] - S[:, 1], S[:, 2] - S[:, 0]) % np.pi; used = np.zeros(len(S), bool); out = []; M = np.array([m for m in masks])
    for i in range(len(S)):
        if used[i]: continue
        c = np.array([np.cos(th[i]), np.sin(th[i])]); nvec = np.array([-c[1], c[0]]); p0 = S[i, :2]
        dth = np.abs((th - th[i] + np.pi / 2) % np.pi - np.pi / 2); rho = (S[:, :2] - p0) @ nvec; rho2 = (S[:, 2:4] - p0) @ nvec
        g = (~used) & (dth < np.radians(winkel)) & (np.abs(rho) < abst) & (np.abs(rho2) < abst)
        if not g[i]: continue
        a1 = (S[:, :2] - p0) @ c; a2 = (S[:, 2:4] - p0) @ c; lo = np.minimum(a1, a2); hi = np.maximum(a1, a2); s0_, s1_ = lo[i], hi[i]; g &= (hi > s0_ - 3) & (lo < s1_ + 3)
        idx = np.where(g)[0]; used[idx] = True; fot = S[idx, 4].astype(int)
        # Fotos, die die Mitte sehen
        mid = p0 + c * (s0_ + s1_) / 2; mx, my = int(np.clip(mid[0], 0, W - 1)), int(np.clip(mid[1], 0, H - 1)); sehen = int(M[:, my, mx].sum())
        nf = len(set(fot.tolist()))
        if sehen < 2 or nf < max(2, int(np.ceil(0.5 * sehen))): continue
        w = ln[idx]; off = float(np.median(rho[idx] * 0.5 + rho2[idx] * 0.5)); ex = []
        for f_ in sorted(set(fot.tolist())): k = idx[fot == f_]; ex.append((lo[k].min(), hi[k].max()))
        e0 = float(np.median([e[0] for e in ex])); e1 = float(np.median([e[1] for e in ex]))
        if (e1 - e0) < minl_m / px: continue
        A = p0 + c * e0 + nvec * off; Bp = p0 + c * e1 + nvec * off; out.append([float(A[0]), float(A[1]), float(Bp[0]), float(Bp[1]), nf, round(nf / sehen, 2), "p"])
    return out

def fotokanten_voll(d, cmin=0.9, maxn=80, tiefe=False, anteil=0.3, minl_m=0.25):
    """Kantenkarte wie eine Tiefenkarte aus ALLEN Fotos, die die Ebene sehen (GPU): je Foto Entzerrung (grid_sample, volle Aufloesung, Tiefe aus Wolke), Kantenmaske auf grau/Gelb-Blau/Gruen,
    Summe ueber Fotos / Zahl der Fotos, die den Pixel sehen = Kantenanteil F. Median-/Mehrheitsregel: F >= anteil. Linien per LSD auf F."""
    import torch, torch.nn.functional as Fn
    dev = "cuda"; U_ = uax(); n_ = np.array(obj()["fassade_n"]["wert"], float); n_ = n_[:2] / np.linalg.norm(n_[:2]); al = np.radians(d["neig"]); sn, cn = np.sin(al), np.cos(al); px = d["px"]; H, W = d["gray"].shape
    nrm = np.array([n_[0] * cn, n_[1] * cn, -sn]); c0 = np.r_[((d["u0"] - W / 2 * px) * U_ + d["s0"] * n_), d["z0"] + (d["v0"] - H / 2 * px) * cn]
    cand = []
    for f, K in KAM.items():
        if not os.path.exists(os.path.join(a.bilder, f)): continue
        v = np.array(K["C"], float) - c0; dist = np.linalg.norm(v); cs = float(v @ nrm) / dist
        if cs > cmin and 3 < dist < 70: cand.append((-cs, f))
    fl = [f for _, f in sorted(cand)[:maxn]]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64); u = d["u0"] - xx * px; v = d["v0"] - yy * px
    t = (d["d8"].astype(np.float64) / 255 * (d["vor"] + d["hinter"]) - d["hinter"]) if tiefe else np.zeros_like(u)
    sS = d["s0"] + t * cn + v * sn; z = d["z0"] - t * sn + v * cn; X = np.stack([u * U_[0] + sS * n_[0], u * U_[1] + sS * n_[1], z], -1).reshape(-1, 3)
    E = torch.zeros(H, W, device=dev); V = torch.zeros(H, W, device=dev); kern = torch.ones(1, 1, 3, 3, device=dev)
    sob = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32, device=dev)[None, None]
    for f in fl:
        K = KAM[f]; im = cv2.imread(os.path.join(a.bilder, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
        if im is None: continue
        sc = im.shape[1] / K["W"]; Xc = X @ np.array(K["Rn"]).T + np.array(K["tn"]); zc = Xc[:, 2]; uv = (K["f"] * Xc[:, :2] / np.where(zc > 0.5, zc, 0.5)[:, None] + [K["cx"], K["cy"]]) * sc
        gx = torch.tensor(uv[:, 0].reshape(H, W) / (im.shape[1] - 1) * 2 - 1, dtype=torch.float32, device=dev); gy = torch.tensor(uv[:, 1].reshape(H, W) / (im.shape[0] - 1) * 2 - 1, dtype=torch.float32, device=dev)
        ok = torch.tensor(zc.reshape(H, W) > 1, device=dev) & (gx.abs() < 0.995) & (gy.abs() < 0.995)
        T = torch.tensor(im[:, :, ::-1].copy(), device=dev).permute(2, 0, 1)[None].float(); R = Fn.grid_sample(T, torch.stack([gx, gy], -1)[None], mode="bicubic", padding_mode="zeros", align_corners=True)[0]; del T
        ch = torch.stack([R.mean(0), R[1], (R[0] + R[1]) / 2 - R[2]])[:, None]                # grau, Gruen, Gelb-Blau (Lab-b-aehnlich)
        ch = Fn.avg_pool2d(ch, 3, 1, 1); gxs = Fn.conv2d(ch, sob, padding=1); gys = Fn.conv2d(ch, sob.transpose(2, 3), padding=1); mag = torch.sqrt(gxs ** 2 + gys ** 2)[:, 0]
        okm = ok & (Fn.max_pool2d((~ok)[None, None].float(), 7, 1, 3)[0, 0] == 0)           # Rand der Sichtbarkeit abziehen
        e = torch.zeros(H, W, device=dev, dtype=torch.bool)
        for c in range(3):
            m = mag[c]; vals = m[okm]
            if vals.numel() < 1000: continue
            thr = torch.quantile(vals[::max(1, vals.numel() // 200000)], 0.90); loc = Fn.max_pool2d(m[None, None], 5, 1, 2)[0, 0]; e |= (m >= thr) & (m >= loc * 0.999)      # starke lokale Maxima (duenne Kante)
        e = Fn.conv2d(e[None, None].float(), kern, padding=1)[0, 0] > 0                    # 1 px Toleranz fuer Restversatz
        E += (e & okm).float(); V += okm.float(); del R, ch, gxs, gys, mag
    torch.cuda.empty_cache()
    if len(fl) < 3 or float((V >= 3).sum()) < 1000: d["F"] = np.zeros((H, W), np.uint8); d["V"] = np.zeros((H, W), np.float32); return dict(linien=[], fotos=len(fl), score=0.0, cmin=cmin, tiefe=bool(tiefe))
    F = torch.where(V >= 3, E / V.clamp(min=1), torch.zeros_like(E)); Fn_ = F.cpu().numpy(); Vn = V.cpu().numpy()
    f8 = (np.clip(Fn_, 0, 1) * 255).astype(np.uint8); d["F"] = f8; d["V"] = Vn
    G_ = cv2.GaussianBlur(np.clip(Fn_ / max(float(np.percentile(Fn_[Vn >= 3], 99.5)), 0.4), 0, 1).astype(np.float32), (0, 0), 1.2); bin_ = (G_ * 255).astype(np.uint8)
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD); L = lsd.detect(bin_)[0]; out = []
    if L is not None:
        for q in np.asarray(L).reshape(-1, 4):
            if np.hypot(q[2] - q[0], q[3] - q[1]) < minl_m / px: continue
            n = max(int(np.hypot(q[2] - q[0], q[3] - q[1])), 2); xs = np.linspace(q[0], q[2], n).round().astype(int).clip(0, W - 1); ys = np.linspace(q[1], q[3], n).round().astype(int).clip(0, H - 1)
            out.append([float(q[0]), float(q[1]), float(q[2]), float(q[3]), int(np.median(Vn[ys, xs])), round(float(np.median(Fn_[ys, xs])), 2), "p"])
    ok_ = Vn >= 8; sc_ = 0.0
    if ok_.sum() > 5000:                                       # Selbstpruefung ohne Wahrheit: wie einig sind die Fotos an ihren staerksten Kanten? (scharf ausgerichtet = hoher Anteil)
        v_ = Fn_[ok_]; top = v_ >= np.percentile(v_, 97); sc_ = float(v_[top].mean())
    return dict(linien=out, fotos=len(fl), score=round(sc_, 3), cmin=cmin, tiefe=bool(tiefe))

def fotokanten_auto(d, kandidaten=((0.8, False), (0.9, False), (0.95, False), (0.8, True), (0.9, True)), minfotos=6):
    """Sweet Spot je Ebene automatisch: Blickwinkel-Schwelle x Tiefe aus der Wolke durchprobieren, die Einstellung mit der groessten Foto-Einigkeit (score) nehmen; mindestens minfotos Fotos."""
    best = None; prot = []
    for cm, tf in kandidaten:
        r = fotokanten_voll(d, cm, 80, tf)
        prot.append(dict(cmin=cm, tiefe=tf, fotos=r["fotos"], score=r["score"], linien=len(r["linien"])))
        if r["fotos"] >= minfotos and (best is None or r["score"] > best[0]["score"]): best = (r, d["F"].copy(), d["V"].copy())
    if best is None: return dict(fehler="zu wenige frontale Fotos", protokoll=prot)
    d["F"], d["V"] = best[1], best[2]; r = best[0]; r["protokoll"] = prot; return r

DEXI = {}
def dexined_linien(bgr, dicht=0.88, minp=0.6, minlen=10):
    """Trainierte Kantenkarte (DexiNed/BIPED via kornia, Gewichte in /media/oem/scan/tools_src/torch_cache), Sigmoid -> Skelett -> LSD; Rueckgabe Linien (x1,y1,x2,y2,p_mittel). Lizenz Gewichte: BIPED/DexiNed - vor Verkauf pruefen."""
    import torch
    from skimage.morphology import skeletonize
    os.environ.setdefault("TORCH_HOME", "/media/oem/scan/tools_src/torch_cache")
    if "m" not in DEXI:
        from kornia.models.dexined import DexiNed
        DEXI["m"] = DexiNed(pretrained=True).cuda().eval()
    x = torch.tensor(bgr[:, :, ::-1].copy()).permute(2, 0, 1)[None].float().cuda()
    with torch.no_grad(): ys = DEXI["m"](x)
    y = ys[-1] if isinstance(ys, (list, tuple)) else ys; pm = torch.sigmoid(y)[0, 0].cpu().numpy(); del x, ys, y; torch.cuda.empty_cache()
    th = max(float(np.percentile(pm, dicht * 100)), 0.3); sk = skeletonize(pm > th).astype(np.uint8) * 255
    L = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(cv2.GaussianBlur(sk, (0, 0), 1.0))[0]; out = []
    if L is None: return pm, out
    for q in np.asarray(L).reshape(-1, 4):
        ln = np.hypot(q[2] - q[0], q[3] - q[1])
        if ln < minlen: continue
        n = max(int(ln), 2); xs = np.linspace(q[0], q[2], n).round().astype(int).clip(0, pm.shape[1] - 1); ys_ = np.linspace(q[1], q[3], n).round().astype(int).clip(0, pm.shape[0] - 1); pp = float(pm[ys_, xs].mean())
        if pp >= minp: out.append([float(q[0]), float(q[1]), float(q[2]), float(q[3]), pp])
    return pm, out

def linien_verbinden(L, px, winkel=1.5, abst=1.5, luecke_m=0.5):
    """Kollineare Stuecke zu durchgehenden Linien verbinden (Winkel < winkel Grad, Querabstand < abst px, Luecke < luecke_m). Lage = laengengewichtete Ausgleichsgerade, Ausdehnung = Vereinigung. Wiederholen bis stabil."""
    if len(L) < 2: return L
    A = np.array([l[:4] for l in L], float); ex = [l[4:] for l in L]; gap = luecke_m / px
    for _ in range(6):
        ln = np.hypot(A[:, 2] - A[:, 0], A[:, 3] - A[:, 1]); o = np.argsort(-ln); A = A[o]; ex = [ex[i] for i in o]; ln = ln[o]; used = np.zeros(len(A), bool); newA = []; newex = []
        th = np.arctan2(A[:, 3] - A[:, 1], A[:, 2] - A[:, 0]) % np.pi; changed = False
        for i in range(len(A)):
            if used[i]: continue
            c = np.array([np.cos(th[i]), np.sin(th[i])]); nv = np.array([-c[1], c[0]]); p0 = A[i, :2]
            dth = np.abs((th - th[i] + np.pi / 2) % np.pi - np.pi / 2); r1 = (A[:, :2] - p0) @ nv; r2 = (A[:, 2:] - p0) @ nv
            a1 = (A[:, :2] - p0) @ c; a2 = (A[:, 2:] - p0) @ c; lo = np.minimum(a1, a2); hi = np.maximum(a1, a2)
            g = (~used) & (dth < np.radians(winkel)) & (np.abs(r1) < abst) & (np.abs(r2) < abst); g[i] = True
            idx = np.where(g)[0]; idx = idx[np.argsort(lo[idx])]; grp = [i]; cur_hi = hi[i]; cur_lo = lo[i]               # von Seed nach beiden Seiten ketten
            for _r in range(2):
                for j in idx:
                    if j in grp: continue
                    if lo[j] <= cur_hi + gap and hi[j] >= cur_lo - gap: grp.append(j); cur_hi = max(cur_hi, hi[j]); cur_lo = min(cur_lo, lo[j])
            for j in grp: used[j] = True
            if len(grp) > 1: changed = True
            w = ln[grp]; P = np.vstack([A[grp][:, :2], A[grp][:, 2:]]); W2 = np.r_[w, w]; m = (P * W2[:, None]).sum(0) / W2.sum(); C = ((P - m).T * W2) @ (P - m); ev, evec = np.linalg.eigh(C); d_ = evec[:, 1]
            t = (P - m) @ d_; e0 = t.min(); e1 = t.max(); newA.append(np.r_[m + d_ * e0, m + d_ * e1]); newex.append(ex[i][:1] + [max(ex[j][1] for j in grp)] if False else ex[i])
        A = np.array(newA); ex = newex
        if not changed: break
    return [[float(a[0]), float(a[1]), float(a[2]), float(a[3])] + list(e) for a, e in zip(A, ex)]

def fotokanten_ref(d, stuetz=0.25, minl_m=0.15, nref=1):
    """Allgemeine Methode (wie ein Mensch): Geometrie aus dem SCHAERFSTEN frontalen Foto (Entzerrung, LSD auf grau/gelb-blau/gruen), die uebrigen Fotos stimmen ab (Kantenanteil F aus allen Fotos, 1 px Toleranz,
    entlang der Linie im Mittel >= stuetz). Keine Handwerte je Objekt: Referenz = hoechster cos * Laplace-Schaerfe der Ortho."""
    H, W = d["gray"].shape; px = d["px"]; fl = beste_fotos(d, 30)
    if len(fl) < 3: return dict(fehler="zu wenige frontale Fotos")
    sh = []
    for f in fl[:12]:
        im, ok = foto_ortho(d, f, False); g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); okk = cv2.erode(ok.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        sh.append((float(cv2.Laplacian(g, cv2.CV_32F)[okk].var()) * okk.mean() if okk.sum() > 5000 else 0.0, f))
    sh.sort(reverse=True); ref = [f for _, f in sh[:nref]]
    Fm = fotokanten_voll(d, 0.8, 80, False)                                  # F-Karte aller Fotos (Abstimmung) in d["F"]
    F = d["F"].astype(np.float32) / 255; F = cv2.dilate(F, np.ones((3, 3), np.uint8)); V = d["V"]; lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD); out = []
    for f in ref:
        im, ok = foto_ortho(d, f, False); lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB); okk = cv2.erode(ok.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0; cand = []
        for g in (cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), lab[:, :, 2], im[:, :, 1]):
            gb = cv2.GaussianBlur(g, (0, 0), 0.8); mg = np.hypot(cv2.Sobel(gb.astype(np.float32), cv2.CV_32F, 1, 0), cv2.Sobel(gb.astype(np.float32), cv2.CV_32F, 0, 1)); L = lsd.detect(gb)[0]
            if L is None: continue
            for q in np.asarray(L).reshape(-1, 4):
                ln = np.hypot(q[2] - q[0], q[3] - q[1])
                if ln < minl_m / px: continue
                n = max(int(ln), 2); xs = np.linspace(q[0], q[2], n).round().astype(int).clip(0, W - 1); ys = np.linspace(q[1], q[3], n).round().astype(int).clip(0, H - 1)
                if not okk[ys, xs].all(): continue
                cand.append((q, float(mg[ys, xs].mean() / max(np.percentile(mg[okk], 99), 1e-3)), float(F[ys, xs].mean()), int(np.median(V[ys, xs]))))   # (Segment, Kontrast rel., Foto-Abstimmung, Zahl Fotos)
        if not cand: continue
        kt = np.array([c[1] for c in cand]); thr_k = max(float(np.percentile(kt, 60)), 0.12)      # starker Kontrast im scharfen Foto zaehlt auch ohne Abstimmung (Relief steht vor der Ebene -> Parallaxe)
        for q, kon, sup, nv in cand:
            if (sup >= stuetz and nv >= 3) or kon >= thr_k: out.append([float(q[0]), float(q[1]), float(q[2]), float(q[3]), nv, round(max(sup, kon), 2), "p"])
    try:                                                       # trainierte Kantenkarte als zusaetzliche Quelle (Relief, Saeulen, Fensterteilung)
        im_r, ok_r = foto_ortho(d, ref[0], False); _, DL = dexined_linien(im_r); okr = cv2.erode(ok_r.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        for q in DL:
            mx_, my_ = int(np.clip((q[0] + q[2]) / 2, 0, W - 1)), int(np.clip((q[1] + q[3]) / 2, 0, H - 1))
            if okr[my_, mx_]: out.append([q[0], q[1], q[2], q[3], int(V[my_, mx_]), round(q[4], 2), "p"])
    except Exception as e_: print("DexiNed uebersprungen:", e_)
    # doppelte Linien (gleicher Ort aus mehreren Kanaelen) entfernen: laengste zuerst, Rasterbelegung
    out.sort(key=lambda l: -np.hypot(l[2] - l[0], l[3] - l[1])); occ = np.zeros((H, W), np.uint8); keep = []
    for l in out:
        m = np.zeros((H, W), np.uint8); cv2.line(m, (int(l[0]), int(l[1])), (int(l[2]), int(l[3])), 1, 1); tot = m.sum()
        if tot == 0: continue
        if (cv2.dilate(occ, np.ones((5, 5), np.uint8)) & m).sum() / tot > 0.7: continue
        occ |= m; keep.append(l)
    keep = linien_verbinden(keep, px)
    for l in keep:                                              # Einrasten auf die Hauptrichtungen der entzerrten Ebene (waagerecht/senkrecht), nur innerhalb 2 Grad (Recherche: Fluchtpunkt-/Manhattan-Regel)
        dx, dy = l[2] - l[0], l[3] - l[1]; ang = np.degrees(np.arctan2(dy, dx)) % 180; mx_, my_ = (l[0] + l[2]) / 2, (l[1] + l[3]) / 2; h = np.hypot(dx, dy) / 2
        for ziel in (0, 90, 180):
            if abs(ang - ziel) < 2.0:
                r_ = np.radians(ziel); l[0], l[1], l[2], l[3] = mx_ - h * np.cos(r_), my_ - h * np.sin(r_), mx_ + h * np.cos(r_), my_ + h * np.sin(r_); break
    keep = [l for l in keep if np.hypot(l[2] - l[0], l[3] - l[1]) >= 0.3 / px]
    try:                                                       # Bogenraender: Kreisbogen-RANSAC auf den nicht waagerechten/senkrechten Linien, Bogenstuecke durch die Kurve ersetzen
        sch = [l for l in keep if min(abs(np.degrees(np.arctan2(l[3] - l[1], l[2] - l[0])) % 90), 90 - abs(np.degrees(np.arctan2(l[3] - l[1], l[2] - l[0])) % 90)) > 3]
        B_ = boegen(sch, px) if len(sch) > 5 else []; bl = []
        if B_:
            occ_ = np.zeros((H, W), np.uint8)
            for b in B_: cv2.polylines(occ_, [np.array(b["poly"], np.float32).round().astype(np.int32)], False, 1, 1)
            near = cv2.dilate(occ_, np.ones((7, 7), np.uint8)); rest = []
            for l in keep:
                n = max(int(np.hypot(l[2] - l[0], l[3] - l[1])), 2); xs = np.linspace(l[0], l[2], n).round().astype(int).clip(0, W - 1); ys = np.linspace(l[1], l[3], n).round().astype(int).clip(0, H - 1)
                if l in sch and near[ys, xs].mean() > 0.8: continue
                rest.append(l)
            for b in B_:
                P_ = np.array(b["poly"], float); bl += [[float(P_[i, 0]), float(P_[i, 1]), float(P_[i + 1, 0]), float(P_[i + 1, 1]), 99, 9, "b"] for i in range(len(P_) - 1)]
            keep = rest + bl; d["boegen"] = B_
    except Exception as e_: print("Bogenfit uebersprungen:", e_)
    d["ref"] = keep; d["roh"] = [l for l in out]
    return dict(linien=keep, fotos=len(fl), referenz=ref, methode="ref")

def vergleich_heldout(d, mengen, anz=14, tol=2.5):
    """Fairer Vergleich von Linienmengen (Name -> Liste [x1,y1,x2,y2,..] in Ortho-Pixeln) an Fotos, die NICHT in Referenz/Abstimmung (cos >= 0,8) vorkamen (0,5 <= cos < 0,8).
    Praezision = Anteil der Linienpunkte (3D auf der Ebene, Tiefe 0) mit Canny-Kante <= tol px im Foto; Zufallsbasis = Linien um (41,27) px versetzt; Recall = Anteil der Canny-Pixel im Ortho-Bereich, die
    <= tol px an einer projizierten Linie liegen; F = harmonisches Mittel; Gewinn = F - F(Zufall). Gleiche Fotos und Region fuer alle Mengen."""
    U_ = uax(); n_ = np.array(obj()["fassade_n"]["wert"], float); n_ = n_[:2] / np.linalg.norm(n_[:2]); al = np.radians(d["neig"]); sn, cn = np.sin(al), np.cos(al); px = d["px"]; H, W = d["gray"].shape
    nrm = np.array([n_[0] * cn, n_[1] * cn, -sn]); c0 = np.r_[((d["u0"] - W / 2 * px) * U_ + d["s0"] * n_), d["z0"] + (d["v0"] - H / 2 * px) * cn]; cand = []
    for f, K in KAM.items():
        if not os.path.exists(os.path.join(a.bilder, f)): continue
        v = np.array(K["C"], float) - c0; dist = np.linalg.norm(v); cs = float(v @ nrm) / dist
        if 0.5 <= cs < 0.8 and 3 < dist < 60: cand.append((dist, f))
    fl = [f for _, f in sorted(cand)[:anz]]
    if len(fl) < 3: return dict(fehler="zu wenige Held-out-Fotos (%d)" % len(fl))
    def welt(P):
        u = d["u0"] - P[:, 0] * px; v = d["v0"] - P[:, 1] * px; sS = d["s0"] + v * sn; z = d["z0"] + v * cn; return np.c_[np.outer(u, U_) + np.outer(sS, n_), z]
    gy, gx = np.mgrid[0:H:6, 0:W:6]; reg = np.c_[gx.ravel(), gy.ravel()].astype(float); reg = reg[d["gray"][gy.ravel(), gx.ravel()] > 0]
    def samp(sg, off=(0, 0)):
        sg = np.asarray(sg, float).reshape(-1, 4)[:, :4]; L = np.hypot(sg[:, 2] - sg[:, 0], sg[:, 3] - sg[:, 1]); n = np.maximum((L / 3).astype(int), 2)
        return np.vstack([np.c_[np.linspace(q[0], q[2], k), np.linspace(q[1], q[3], k)] for q, k in zip(sg, n)]) + np.array(off, float)
    acc = {k: dict(p=[], p0=[], r=[], r0=[]) for k in mengen}; PS = {k: (samp(v), samp(v, (41, 27))) for k, v in mengen.items()}; RW = welt(reg)
    for f in fl:
        g = cv2.imread(os.path.join(a.bilder, f), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION); g = cv2.resize(g, (SW, int(g.shape[0] * SW / g.shape[1])), interpolation=cv2.INTER_AREA)
        ed = cv2.Canny(cv2.GaussianBlur(g, (3, 3), 0), 60, 140); Dd = dt_foto(f); K = KAM[f]; Hh, Ww = ed.shape
        uvr, zr = proj(K, RW); okr = (zr > 1) & (uvr[:, 0] >= 0) & (uvr[:, 0] < Ww) & (uvr[:, 1] >= 0) & (uvr[:, 1] < Hh); region = np.zeros((Hh, Ww), np.uint8)
        for x_, y_ in uvr[okr].astype(int): region[y_, x_] = 255
        region = cv2.dilate(region, np.ones((25, 25), np.uint8)) > 0; E = (ed > 0) & region
        if E.sum() < 500: continue
        for k, (P, P0) in PS.items():
            for nm, PP in (("", P), ("0", P0)):
                uv, z = proj(K, welt(PP)); ok = (z > 1) & (uv[:, 0] >= 0) & (uv[:, 0] < Ww - 1) & (uv[:, 1] >= 0) & (uv[:, 1] < Hh - 1)
                if ok.sum() < 30: continue
                x = uv[ok, 0].round().astype(int); y = uv[ok, 1].round().astype(int); pr = float((Dd[y, x] <= tol).mean()); m = np.zeros((Hh, Ww), np.uint8); m[y, x] = 255
                dm = cv2.distanceTransform(255 - cv2.dilate(m, np.ones((3, 3), np.uint8)), cv2.DIST_L2, 3); rc = float((dm[E] <= tol).mean())
                acc[k]["p" + nm].append(pr); acc[k]["r" + ("0" if nm else "")].append(rc)
    res = []
    for k, v in acc.items():
        if not v["p"]: continue
        F_ = lambda p_, r_: 2 * p_ * r_ / max(p_ + r_, 1e-9); p, r, p0, r0 = [float(np.mean(v[q])) for q in ("p", "r", "p0", "r0")]
        res.append(dict(methode=k, linien=len(mengen[k]), praez=round(p, 3), recall=round(r, 3), F=round(F_(p, r), 3), F_zufall=round(F_(p0, r0), 3), gewinn=round(F_(p, r) - F_(p0, r0), 3)))
    res.sort(key=lambda e: -e["gewinn"]); return dict(tabelle=res, fotos=fl)

def synth_pruefstand(d, anz=14, pos_cm=3.0, rot_grad=0.15, breite=1500, seed=5, tol=2.5):
    """Synthetischer Rundlauf mit EXAKTER Wahrheit: Modell (MESH) mit den echten Kamerapositionen der frontalen Fotos rendern (Flaechenschattierung je Normale + Helligkeit je Bauteil, Unschaerfe, Rauschen),
    Posen fuer die Auswertung um pos_cm/rot_grad stoeren, dann die Fotokanten-Methoden laufen lassen und mit den Modellkanten (Knickkanten, in der Ebene) vergleichen. Gleiche Ebene wie ORD['last']."""
    import tempfile
    rng = np.random.RandomState(seed); U_ = uax(); n_ = np.array(obj()["fassade_n"]["wert"], float); n_ = n_[:2] / np.linalg.norm(n_[:2]); al = np.radians(d["neig"]); sn, cn = np.sin(al), np.cos(al); px = d["px"]; H, W = d["gray"].shape
    fl = beste_fotos(d, anz)
    if len(fl) < 4: return dict(fehler="zu wenige Fotos")
    tri = []; hel = []
    for typ, b in MESH.items():
        T = np.frombuffer(b, np.float32).reshape(-1, 3, 3).astype(np.float64); tri.append(T); hel.append(np.full(len(T), rng.uniform(0.35, 0.9)))
    T = np.vstack(tri); hb = np.concatenate(hel); N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9); Lg = np.array([0.4, -0.5, 0.75]); Lg /= np.linalg.norm(Lg)
    tmp = tempfile.mkdtemp(prefix="synth_", dir="/media/oem/scan/rc-park_null"); KS = {}; K0 = {}
    for i, f in enumerate(fl):
        K = KAM[f]; sc = breite / K["W"]; Wi = breite; Hi = int(K["H"] * sc); Xc = T.reshape(-1, 3) @ np.array(K["Rn"]).T + np.array(K["tn"]); zc = Xc[:, 2].reshape(-1, 3)
        uv = ((K["f"] * Xc[:, :2] / np.where(Xc[:, 2] > 0.3, Xc[:, 2], 0.3)[:, None] + [K["cx"], K["cy"]]) * sc).reshape(-1, 3, 2); fl_ = np.abs(N @ np.array(K["Rn"]).T[:, 2]) ; vis = (zc > 0.5).all(1)
        sh = 0.45 + 0.55 * np.abs(N @ Lg); col = np.clip(sh * hb, 0, 1); order = np.argsort(-zc.mean(1)); img = np.full((Hi, Wi), 0.2, np.float32)
        for k in order:
            if not vis[k]: continue
            q = uv[k]
            if q[:, 0].max() < -50 or q[:, 0].min() > Wi + 50 or q[:, 1].max() < -50 or q[:, 1].min() > Hi + 50: continue
            cv2.fillConvexPoly(img, q.round().astype(np.int32), float(col[k]), lineType=cv2.LINE_8)
        g = cv2.GaussianBlur(img, (0, 0), 1.0) + rng.normal(0, 0.012, img.shape).astype(np.float32); g8 = (np.clip(g, 0, 1) * 255).astype(np.uint8); nm = "syn_%d.jpg" % i
        cv2.imwrite(os.path.join(tmp, nm), cv2.merge([g8, g8, g8])); Kp = json.loads(json.dumps(K)); Kp["W"] = K["W"]; C = np.array(K["C"], float) + rng.normal(0, pos_cm / 100, 3)
        ax = rng.normal(0, 1, 3); ax /= np.linalg.norm(ax); th = np.radians(rot_grad) * rng.normal(0, 1); Kr, _ = cv2.Rodrigues(ax * th); Rn = Kr @ np.array(K["Rn"]); Kp["Rn"] = Rn.tolist(); Kp["C"] = C.tolist(); Kp["tn"] = (-Rn @ C).tolist()
        KS[nm] = Kp
    alt = (a.bilder, dict(KAM), dict(DT)); a.bilder = tmp; KAM.clear(); KAM.update(KS); DT.clear()
    try:
        # Wahrheit: Modellkanten in der Ebene (lange, Knickkanten), ausserdem Silhouette
        r = fotokanten_ref(d); ref = r.get("linien", []); roh = d.get("roh", []); K_ref = alt[1][fl[int(r["referenz"][0].split("_")[1].split(".")[0])]]; M = modellkanten_px(d, 25.0, 40, kamera=K_ref, slab=1.2)
        Fm = fotokanten_voll(d, 0.7, 80, False); stap = Fm["linien"]; Fm2 = fotokanten_voll(d, 0.7, 80, True); stap_t = Fm2["linien"]
    finally:
        a.bilder = alt[0]; KAM.clear(); KAM.update(alt[1]); DT.clear(); DT.update(alt[2]); shutil.rmtree(tmp, ignore_errors=True)
    if len(M) < 5: return dict(fehler="zu wenige Wahrheitskanten")
    def raster(sg):
        m = np.zeros((H, W), np.uint8)
        for q in np.asarray(sg, float).reshape(-1, 7 if False else (len(sg[0]) if len(sg) else 4))[:, :4]: cv2.line(m, (int(round(q[0])), int(round(q[1]))), (int(round(q[2])), int(round(q[3]))), 255, 1)
        return m
    def samp(sg):
        sg = np.asarray([l[:4] for l in sg], float).reshape(-1, 4); L = np.hypot(sg[:, 2] - sg[:, 0], sg[:, 3] - sg[:, 1]); n = np.maximum((L / 2).astype(int), 2); return np.vstack([np.c_[np.linspace(q[0], q[2], k), np.linspace(q[1], q[3], k)] for q, k in zip(sg, n)])
    def hit(P, m):
        dt = cv2.distanceTransform(255 - m, cv2.DIST_L2, 3); xi = P[:, 0].round().astype(int).clip(0, W - 1); yi = P[:, 1].round().astype(int).clip(0, H - 1); return float((dt[yi, xi] <= tol).mean())
    PM = samp(M.tolist()); mM = raster([list(q) for q in M]); res = []
    for nm, sg in (("Foto-Ref (verbunden, Bogen)", ref), ("Foto: LSD Referenzfoto roh", roh), ("Abstimmung alle Fotos flach", stap), ("Abstimmung alle Fotos mit Wolkentiefe", stap_t)):
        if not len(sg): continue
        mm = raster([list(q[:4]) for q in sg]); rec = hit(PM, mm); pre = hit(samp(sg), mM); res.append(dict(methode=nm, linien=len(sg), praez=round(pre, 3), recall=round(rec, 3), F=round(2 * rec * pre / max(rec + pre, 1e-9), 3)))
    return dict(tabelle=res, fotos=len(fl), pos_cm=pos_cm, rot_grad=rot_grad, wahrheit=int(len(M)))

SAMP = {}
def sam_flaechen(d, minfl=0.02, maxanteil=0.6, eps=1.3, fein=False):
    """Objekte statt Kontrastlinien: SAM (facebook/sam-vit-base via transformers, Gewichte /media/oem/scan/tools_src/hf_cache) auf der scharfen Ortho des Referenzfotos -> Masken -> Polygone im Format von regionen().
    Wie ein Mensch: Fensterscheiben, Gelaenderband, Statuen, Konsolen, Bogenoeffnungen als eigene Flaechen. Lizenz: SAM Apache-2.0 (Gewichte, Meta)."""
    import torch
    from PIL import Image
    ck = ("sam", round(d["s0"], 3), round(d["z0"], 3), round(d["neig"], 2), round(d["px"], 4), d["gray"].shape, round(minfl, 4), round(maxanteil, 2), eps, bool(fein))      # Ergebnis je Ebene merken (2 min Rechenzeit)
    cp = os.path.join(os.path.dirname(OJ), "sam_cache_%s.json" % abs(hash(ck[1:]) % 10**8))
    if os.path.exists(cp):
        r0 = json.load(open(cp)); ORD["regs"] = r0["flaechen"][:500]; return r0
    os.environ.setdefault("HF_HOME", "/media/oem/scan/tools_src/hf_cache")
    if "g" not in SAMP:
        from transformers import pipeline
        SAMP["g"] = pipeline("mask-generation", model="facebook/sam-vit-large", device=0)
    fl = beste_fotos(d, 30); sh = []
    for f in fl[:8]:
        im, ok = foto_ortho(d, f, False); g_ = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); okk = cv2.erode(ok.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        sh.append((float(cv2.Laplacian(g_, cv2.CV_32F)[okk].var()) * okk.mean() if okk.sum() > 5000 else 0.0, f))
    sh.sort(reverse=True); im, ok = foto_ortho(d, sh[0][1], False); H, W = im.shape[:2]
    okE = cv2.erode(ok.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0; M = []
    if not fein:                                                           # GROB (Nutzer 9.11.: bester Stand): Ganzbild + grosse Kacheln -> Balkon, Statuen, Fenster, Boegen als Ganzes
        sk = 1200.0 / W if W > 1500 else 1.0; im_s = cv2.resize(im, None, fx=sk, fy=sk, interpolation=cv2.INTER_AREA) if sk < 1 else im
        r = SAMP["g"](Image.fromarray(im_s[:, :, ::-1]), points_per_batch=32, pred_iou_thresh=0.88, stability_score_thresh=0.92)
        for m_ in r["masks"]:
            mm_ = np.asarray(m_.cpu() if hasattr(m_, "cpu") else m_).astype(np.uint8); yy_, xx_ = np.where(mm_)
            if len(yy_) < 30: continue
            bx0, bx1, by0, by1 = int(xx_.min() / sk), int(xx_.max() / sk) + 2, int(yy_.min() / sk), int(yy_.max() / sk) + 2; bx1, by1 = min(bx1, W), min(by1, H)
            if sk < 1: cr = cv2.resize(mm_, (W2 := int(round(mm_.shape[1] / sk)), H2 := int(round(mm_.shape[0] / sk))), interpolation=cv2.INTER_NEAREST)[by0:by1, bx0:bx1] if False else cv2.resize(mm_[int(by0 * sk):int(by1 * sk) + 1, int(bx0 * sk):int(bx1 * sk) + 1], (bx1 - bx0, by1 - by0), interpolation=cv2.INTER_NEAREST)
            else: cr = mm_[by0:by1, bx0:bx1]
            cr = cr.astype(bool) & okE[by0:by1, bx0:bx1]
            if cr.sum() > 30 and (W <= 1500 or cr.sum() > 0.03 * H * W): M.append((bx0, by0, cr))
        torch.cuda.empty_cache(); tw, th_ = (int(min(W, W * 0.6)), int(min(H, H * 0.6))) if W <= 1500 else (700, 520); sx_, sy_ = max(int(tw * 0.7), 1), max(int(th_ * 0.7), 1)      # feine Ortho (>1500 px): SAM-Kacheln in 1:1 statt Verkleinerung
    else: tw, th_ = int(min(W, 620)), int(min(H, 470)); sx_, sy_ = max(int(tw * 0.65), 1), max(int(th_ * 0.65), 1)     # Kacheln: SAM sieht jedes Objekt in ~2x Aufloesung
    xs_t = list(range(0, max(W - tw, 0) + 1, sx_)); ys_t = list(range(0, max(H - th_, 0) + 1, sy_))
    if xs_t[-1] != max(W - tw, 0): xs_t.append(max(W - tw, 0))
    if ys_t[-1] != max(H - th_, 0): ys_t.append(max(H - th_, 0))
    for y0 in ys_t:
        for x0 in xs_t:
            tile = im[y0:y0 + th_, x0:x0 + tw]
            if (tile.sum(2) > 0).mean() < 0.3: continue
            r = SAMP["g"](Image.fromarray(tile[:, :, ::-1]), points_per_batch=64, pred_iou_thresh=0.88, stability_score_thresh=0.92)
            for m_ in r["masks"]:
                mm = np.asarray(m_.cpu() if hasattr(m_, "cpu") else m_).astype(bool); ys2, xs2 = np.where(mm)
                if len(ys2) < 30: continue
                if (x0 > 0 and xs2.min() <= 1) or (y0 > 0 and ys2.min() <= 1) or (x0 + tw < W and xs2.max() >= tw - 2) or (y0 + th_ < H and ys2.max() >= th_ - 2): continue     # am Kachelrand abgeschnitten -> verwerfen
                bx0, bx1, by0, by1 = xs2.min(), xs2.max() + 1, ys2.min(), ys2.max() + 1; M.append((x0 + bx0, y0 + by0, mm[by0:by1, bx0:bx1] & okE[y0 + by0:y0 + by1, x0 + bx0:x0 + bx1]))
            torch.cuda.empty_cache()
    M = [(x_, y_, c_) for x_, y_, c_ in M if c_.any()]; M.sort(key=lambda t: -int(t[2].sum())); keep = []; out = []; dep = d["d8"].astype(np.float32) / 255 * (d["vor"] + d["hinter"]) - d["hinter"]; px = d["px"]
    def iou_(A, B):
        ax, ay, am = A; bx, by, bm = B; x0_, y0_ = max(ax, bx), max(ay, by); x1_, y1_ = min(ax + am.shape[1], bx + bm.shape[1]), min(ay + am.shape[0], by + bm.shape[0])
        if x1_ <= x0_ or y1_ <= y0_: return 0.0
        i_ = int((am[y0_ - ay:y1_ - ay, x0_ - ax:x1_ - ax] & bm[y0_ - by:y1_ - by, x0_ - bx:x1_ - bx]).sum()); return i_ / max(int(am.sum()) + int(bm.sum()) - i_, 1)
    for mt in M:
        ar = int(mt[2].sum()); m2 = ar * px * px
        if m2 < minfl or ar > maxanteil * H * W: continue
        if any(iou_(mt, k) > 0.8 for k in keep): continue
        m = np.zeros((H, W), bool); m[mt[1]:mt[1] + mt[2].shape[0], mt[0]:mt[0] + mt[2].shape[1]] = mt[2]       # Vollbild nur fuer behaltene Masken
        keep.append(mt); cs, hi = cv2.findContours(m.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)          # mit Loechern (Ringe: Bogenraender, Rahmen)
        if not cs: continue
        hi = hi[0]; top = [i for i in range(len(cs)) if hi[i][3] < 0]
        if not top: continue
        i0 = max(top, key=lambda i: cv2.contourArea(cs[i])); c = cs[i0]; ap = cv2.approxPolyDP(c, eps, True)[:, 0, :].astype(float)
        if len(ap) < 3: continue
        loecher = [cv2.approxPolyDP(cs[j], eps, True)[:, 0, :].astype(float).round(1).tolist() for j in range(len(cs)) if hi[j][3] == i0 and cv2.contourArea(cs[j]) > 30]; loecher = [l for l in loecher if len(l) >= 3]
        rr = cv2.minAreaRect(c.astype(np.float32)); rect = float(cv2.contourArea(c) / max(rr[1][0] * rr[1][1], 1e-6)); tt = dep[m]
        if rect > 0.9 and not loecher:                                          # voll rechteckig und achsparallel -> exaktes Rechteck (nur ohne Loch)
            ang = rr[2] % 90; ang = min(ang, 90 - ang)
            if ang < 3.0:
                ys_, xs_ = np.where(m); x0_, x1_ = float(np.percentile(xs_, 0.5)), float(np.percentile(xs_, 99.5)); y0_, y1_ = float(np.percentile(ys_, 0.5)), float(np.percentile(ys_, 99.5)); ap = np.array([[x0_, y0_], [x1_, y0_], [x1_, y1_], [x0_, y1_]], float); rect = 1.0
        out.append(dict(poly=ap.round(1).tolist(), loecher=loecher, m2=round(float(m2), 2), t=round(float(np.median(tt)), 2), rect=round(rect, 2)))
    out.sort(key=lambda e: -e["m2"]); ORD["regs"] = out[:500]; res_ = dict(flaechen=out[:500], referenz=sh[0][1]); json.dump(res_, open(cp, "w")); return res_

def kantenpunkte(foto, pts, r):
    """naechster Fotokantenpunkt (Canny, 1613 px) je Eingabepunkt innerhalb r px; sonst unveraendert. Rueckgabe Liste [x,y,bewegt]"""
    g = cv2.imread(os.path.join(a.bilder, foto), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION); g = cv2.resize(g, (SW, int(g.shape[0] * SW / g.shape[1])), interpolation=cv2.INTER_AREA)
    ed = cv2.Canny(cv2.GaussianBlur(g, (3, 3), 0), 60, 140); ys, xs = np.where(ed > 0)
    if len(xs) == 0: return [[x, y, False] for x, y in pts]
    dst, lab = cv2.distanceTransformWithLabels(255 - ed, cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL); out = []
    for x, y in pts:
        xi, yi = int(round(min(max(x, 0), ed.shape[1] - 1))), int(round(min(max(y, 0), ed.shape[0] - 1))); d = float(dst[yi, xi]); l = int(lab[yi, xi]) - 1
        out.append([float(xs[l]), float(ys[l]), True] if d <= r and 0 <= l < len(xs) else [x, y, False])
    return out

def proj(K, X):
    Xc = X @ np.array(K["Rn"]).T + np.array(K["tn"]); z = Xc[:, 2]; s = SW / K["W"]
    return (K["f"] * Xc[:, :2] / np.where(z > 0.5, z, 0.5)[:, None] + [K["cx"], K["cy"]]) * s, z

def snap(foto, E, du, dz, rad=0.8, st=0.04):
    """beste Zusatzverschiebung (u,z) in +-rad: mittlerer Abstand der projizierten Kantenpunkte (5 je Kante) zur naechsten Fotokante minimal. Rueckgabe (du,dz,vorher,nachher)"""
    K = KAM[foto]; D = dt_foto(foto); E = np.asarray(E, float); t = np.linspace(0, 1, 5)[None, :, None]; Q = (E[:, None, :3] * (1 - t) + E[:, None, 3:] * t).reshape(-1, 3); u_ = uax()
    def sc(a_, b_):
        X = Q.copy(); X[:, :2] += np.outer(np.full(len(X), a_), u_); X[:, 2] += b_; uv, z = proj(K, X); x = np.clip(uv[:, 0].round().astype(int), 0, D.shape[1] - 1); y = np.clip(uv[:, 1].round().astype(int), 0, D.shape[0] - 1)
        ok = (z > 1) & (uv[:, 0] >= 0) & (uv[:, 0] < D.shape[1]) & (uv[:, 1] >= 0) & (uv[:, 1] < D.shape[0]); return float(np.minimum(D[y[ok], x[ok]], 12).mean()) if ok.sum() > 20 else 99.0
    s0 = sc(du, dz); best = (s0, du, dz)
    for a_ in np.arange(du - rad, du + rad + 1e-9, st):
        for b_ in np.arange(dz - rad, dz + rad + 1e-9, st):
            s = sc(a_, b_)
            if s < best[0] - 1e-9: best = (s, a_, b_)
    return best[1], best[2], s0, best[0]

ZP = {"fensterreihe": ["unterseite_z", "kaempfer_z", "scheitel_z", "riegel_z"], "bogenreihe": ["kaempfer_z", "scheitel_z", "oberkante_z"], "erker": ["spitze_z", "unterkante_z", "oberkante_z"],
      "satteldach": ["z_first", "z_traufe_v", "z_traufe_h", "z_unten"], "balkonband": ["oberseite_z"], "gaubenreihe": [], "quader": ["z0", "z1"]}
UP = {"fensterreihe": ["u_mitte"], "bogenreihe": ["u0"], "erker": ["mitte_u"], "satteldach": ["u0", "u1"], "balkonband": ["u_von", "u_bis"], "gaubenreihe": ["u_mitte"], "quader": ["u0", "u1"]}
SKAL = {"satteldach", "fensterreihe", "bogenreihe", "balkonband"}     # parametrische Familien, bei denen Breite/Hoehe ziehen auf Parameter abbildbar ist
SKALBR = {"fensterreihe": ["pitch", "breite"], "bogenreihe": ["pitch", "oeffnung_breite", "pfeiler_breite"]}
def speichern(ed):
    O = obj(); shutil.copy(OJ, OJ + ".edit_bak"); out = []
    for b in O["bauteile"]:
        e = ed.get(b["typ"])
        if not e: continue
        du, dz = float(e["du"]), float(e["dz"]); fam = b["typ"].split(":")[0]; q = b.setdefault("werte_quellen", {}); txt = "editor_modell.py: vom Nutzer im Foto %s verschoben (du %.3f m, dz %.3f m), Kanten-Snap %s" % (a.foto, du, dz, "ja" if e.get("snap") else "nein")
        fu, fz, rl, gi = (float(e.get(k, v)) for k, v in (("fu", 1.0), ("fz", 1.0), ("roll", 0.0), ("gier", 0.0)))
        if fam == "stl_teil":
            if (abs(fu - 1) > 1e-4 or abs(fz - 1) > 1e-4 or abs(rl) > 1e-3 or abs(gi) > 1e-3):
                import trimesh as _t
                n_ = np.array(O["fassade_n"]["wert"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]]); piv = np.array(e["pivot"], float)
                if b.get("anker_m"): A = np.array(b["anker_m"], float)
                else:
                    Pm = np.vstack([np.asarray(_t.load(f if os.path.isabs(f) else os.path.join(os.path.dirname(OJ), f), process=False).vertices) for f in b["dateien"]]) / (1000 / 87); lo, hi = Pm.min(0), Pm.max(0); A = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
                pn, pu, pz = (piv[:2] - A[:2]) @ n_, (piv[:2] - A[:2]) @ u_, piv[2] - A[2]     # Pivot im Ankerrahmen (n,u,z)
                su0, sz0, du0, dz0 = (float(b.get(k, v)) for k, v in (("su", 1.0), ("sz", 1.0), ("du", 0.0), ("dz", 0.0)))
                b["su"], b["sz"] = round(su0 * fu, 4), round(sz0 * fz, 4); b["du"], b["dz"] = round(du0 * fu + pu * (1 - fu) + du, 3), round(dz0 * fz + pz * (1 - fz) + dz, 3)
                if abs(rl) > 1e-3 or abs(gi) > 1e-3:
                    if abs(float(b.get("roll_grad", 0))) > 1e-3 or abs(float(b.get("gier_grad", 0))) > 1e-3: out.append("%s: Teil war schon gedreht - Drehung NICHT uebernommen (erst zuruecksetzen)" % b["typ"])
                    else: b["roll_grad"], b["gier_grad"], b["rot_pivot"] = round(rl, 3), round(gi, 3), [round(pn, 3), round(pu + du, 3), round(pz + dz, 3)]; q["roll_grad"] = q["gier_grad"] = txt
                for k in ("su", "sz", "du", "dz"): q[k] = txt + " (Skalierung fu %.3f fz %.3f)" % (fu, fz)
            else:
                for k, d in (("du", du), ("dz", dz)): b[k] = round(float(b.get(k, 0.0)) + d, 3); q[k] = txt
        else:
            if fam not in SKAL: fu = fz = 1.0
            piv = np.array(e.get("pivot") or [0, 0, 0], float); u_ = uax(); pu, pz = float(piv[:2] @ u_), float(piv[2])    # Skalierung um die Huellmitte (u) bzw. Unterkante (z) des Teils
            for k in UP.get(fam, []):
                if b.get(k) is not None: b[k] = round(pu + (float(b[k]) - pu) * fu + du, 3); q[k] = txt + (" (Breite x%.3f)" % fu if fu != 1 else "")
            for k in ZP.get(fam, []):
                if b.get(k) is not None: b[k] = round(pz + (float(b[k]) - pz) * fz + dz, 3); q[k] = txt + (" (Hoehe x%.3f)" % fz if fz != 1 else "")
            if fu != 1:
                for k in SKALBR.get(fam, []):
                    if b.get(k) is not None: b[k] = round(float(b[k]) * fu, 4); q[k] = txt + " (Breite x%.3f)" % fu
            if fam == "gaubenreihe" and abs(dz) > 1e-6: out.append("%s: dz nicht uebernommen (Gauben haengen am Dach)" % b["typ"])
        out.append("%s: du %.3f dz %.3f" % (b["typ"], du, dz))
    json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False); return out

def rdp(P, e):
    P = np.asarray(P, float)
    if len(P) < 3: return P
    a, b = P[0], P[-1]; v = b - a; d = np.abs(v[0] * (P[:, 1] - a[1]) - v[1] * (P[:, 0] - a[0])) / (np.linalg.norm(v) + 1e-9); i = int(np.argmax(d))
    if d[i] > e: return np.vstack([rdp(P[:i + 1], e)[:-1], rdp(P[i:], e)])
    return np.vstack([a, b])

def kontur_info(typ):
    """Fensterkontur eines fensterreihe-Bauteils: gespeicherte 'kontur' oder die Standardform (Rechteck + Kielbogen wie baukasten_gen.fensterreihe), Fenstermitten u, Bezug z0, Wandebene s"""
    b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]
    if typ.split(":")[0] == "freiform": return dict(kontur=b["kontur"], mitten=[0.0], z0=float(b["ebene_z"]), s=float(b["ebene_s"]), neig=float(b["neigung_grad"]), eigen=True)
    if typ.split(":")[0] != "fensterreihe": return None
    nf, u0, pitch, bw = int(b["n_fenster"]), float(b["u_mitte"]), float(b["pitch"]), float(b["breite"]); z0, zk, zs = float(b["unterseite_z"]), float(b["kaempfer_z"]), float(b["scheitel_z"]); kiel = float(b.get("kiel", 0.4))
    if b.get("kontur"): K = [[float(x), float(z)] for x, z in b["kontur"]]; eigen = True
    else:
        t = np.linspace(0, 1, 16); zz = zk + (zs - zk) * (t - kiel * np.sin(2 * np.pi * t) / (2 * np.pi)); right = [(bw / 2 * (1 - tt), z_ - z0) for tt, z_ in zip(t, zz)]; left = [(-bw / 2 * (1 - tt), z_ - z0) for tt, z_ in zip(t[::-1], zz[::-1])]
        K = [[-bw / 2, 0.0], [bw / 2, 0.0]] + [list(map(float, p_)) for p_ in right] + [list(map(float, p_)) for p_ in left[1:]]; eigen = False; K = rdp(K, 0.025).tolist()    # Standardform auf wenige Punkte vereinfachen (leichter zu ziehen)
    return dict(kontur=[[round(x, 3), round(z, 3)] for x, z in K], mitten=[round(u0 + i * pitch, 3) for i in range(nf)], z0=z0, s=float(b["wand_n"]) + float(b.get("tiefe", 0.3)), eigen=eigen, neig=0.0)

def griffe_von(b):
    """Ziehbare Parameter-Griffe je Familie: (id, Beschriftung, u, s (n-Ebene), z). Ziehen -> griff_anwenden schreibt die betroffenen Parameter."""
    fam = b["typ"].split(":")[0]; G = []
    if fam == "bogenreihe":
        nb, u0, pt, ow, sn = int(b["n_boegen"]), float(b["u0"]), float(b["pitch"]), float(b["oeffnung_breite"]), float(b["pfeiler_n"])
        for i in range(nb):
            uc = u0 + (i + 0.5) * pt
            G += [("scheitel_%d" % i, "Scheitel", uc, sn, float(b["scheitel_z"])), ("kaempfer_%d" % i, "Kaempfer rechts", uc + ow / 2, sn, float(b["kaempfer_z"])), ("fuss_%d" % i, "Fuss rechts", uc + ow / 2, sn, float(b["boden_z"])), ("ober_%d" % i, "Oberkante", uc, sn, float(b["oberkante_z"]))]
    elif fam == "satteldach":
        u0, u1 = float(b["u0"]), float(b["u1"])
        G = [("first_l", "First links", u1, float(b["n_first"]), float(b["z_first"])), ("first_r", "First rechts", u0, float(b["n_first"]), float(b["z_first"])),
             ("traufe_l", "Traufe links", u1, float(b["n_traufe_v"]), float(b["z_traufe_v"])), ("traufe_r", "Traufe rechts", u0, float(b["n_traufe_v"]), float(b["z_traufe_v"]))]
    elif fam == "fensterreihe":
        u0, pt, bw, sn = float(b["u_mitte"]), float(b["pitch"]), float(b["breite"]), float(b["wand_n"]) + float(b.get("tiefe", 0.3))
        G = [("scheitel", "Scheitel", u0, sn, float(b["scheitel_z"])), ("kaempfer", "Kaempfer", u0 + bw / 2, sn, float(b["kaempfer_z"])), ("unten", "Unterkante rechts", u0 + bw / 2, sn, float(b["unterseite_z"])),
             ("pitch", "Abstand (naechstes Fenster)", u0 + pt, sn, float(b["kaempfer_z"])), ("lage", "Reihe verschieben", u0, sn, float(b["unterseite_z"]))]
    return [dict(id=i, label=l, u=round(u, 3), s=round(sv, 3), z=round(z, 3)) for i, l, u, sv, z in G]

def griff_anwenden(typ, gid, u, z):
    O = obj(); b = [x for x in O["bauteile"] if x["typ"] == typ][0]; fam = typ.split(":")[0]; q = b.setdefault("werte_quellen", {}); txt = "editor_modell.py: Griff '%s' im Foto %s gezogen" % (gid, a.foto); n = dict(b)   # n = neue Werte
    if fam == "bogenreihe":
        k, i = gid.rsplit("_", 1); i = int(i); uc = float(b["u0"]) + (i + 0.5) * float(b["pitch"])
        if k == "scheitel": n["scheitel_z"] = z; n["oberkante_z"] = float(b["oberkante_z"]) + (z - float(b["scheitel_z"])); n["u0"] = float(b["u0"]) + (u - uc)     # Oberkante (Abstand zum Scheitel) folgt
        elif k == "kaempfer": n["kaempfer_z"] = z; n["oeffnung_breite"] = 2 * (u - uc)
        elif k == "fuss": n["boden_z"] = z; n["oeffnung_breite"] = 2 * (u - uc)
        elif k == "ober": n["oberkante_z"] = z
        if not (n["boden_z"] < n["kaempfer_z"] < n["scheitel_z"] < n["oberkante_z"]) or n["oeffnung_breite"] < 0.5: return "Unplausibel: Reihenfolge boden < kaempfer < scheitel < oberkante bzw. Oeffnung >= 0,5 m verletzt"
    elif fam == "satteldach":
        if gid.endswith("_l"): n["u1"] = u
        else: n["u0"] = u
        if gid.startswith("first"): n["z_first"] = z
        else: n["z_traufe_v"] = z
        if not (n["z_traufe_v"] < n["z_first"]) or n["u1"] - n["u0"] < 1: return "Unplausibel: Traufe muss unter dem First liegen, Dach >= 1 m breit"
    elif fam == "fensterreihe":
        u0 = float(b["u_mitte"])
        if gid == "scheitel": n["scheitel_z"] = z
        elif gid == "kaempfer": n["kaempfer_z"] = z; n["breite"] = 2 * (u - u0)
        elif gid == "unten": n["unterseite_z"] = z; n["breite"] = 2 * (u - u0)
        elif gid == "pitch": n["pitch"] = u - u0
        elif gid == "lage": n["u_mitte"] = u; dz = z - float(b["unterseite_z"]); [n.__setitem__(k_, float(b[k_]) + dz) for k_ in ("unterseite_z", "kaempfer_z", "scheitel_z", "riegel_z")]
        if not (n["unterseite_z"] < n["kaempfer_z"] < n["scheitel_z"]) or n["breite"] >= n["pitch"] or n["breite"] < 0.3: return "Unplausibel: unten < kaempfer < scheitel, Breite 0,3 m bis kleiner als Abstand"
    else: return "Dieses Teil hat keine Griffe"
    shutil.copy(OJ, OJ + ".edit_bak")
    for k, v in n.items():
        if k != "werte_quellen" and v != b.get(k) and isinstance(v, (int, float)): b[k] = round(float(v), 3); q[k] = txt
    json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False); return None

def freiform_anlegen(d):
    """neues Bauteil freiform:<name> (oder ersetzen) mit der im Foto gezeichneten Kontur; Quelle = Nutzerzeichnung (Regel 3b)"""
    O = obj(); shutil.copy(OJ, OJ + ".edit_bak"); ref = [b for b in O["bauteile"] if b.get("achse_n")][0]; typ = "freiform:" + d["name"]
    b = dict(typ=typ, gruppe="Freiform vom Nutzer gezeichnet: " + d["name"], kontur=[[round(float(x), 3), round(float(z), 3)] for x, z in d["kontur"]], ebene_s=round(float(d["s0"]), 3), ebene_z=round(float(d["z0"]), 3), neigung_grad=round(float(d["neig"]), 2),
             tiefe=round(float(d["tiefe"]), 3), modus=d.get("modus", "anbau"), achse_n=ref["achse_n"], achse_quelle=ref.get("achse_quelle", ""),
             quelle="editor_modell.py: Kontur vom Nutzer im Foto %s gezeichnet (%s), auf Ebene s=%.2f z=%.2f Neigung %.1f Grad projiziert; Tiefe %.2f m ist ANNAHME (Foto sieht keine Tiefe)" % (d.get("foto", a.foto), datetime.date.today().isoformat(), float(d["s0"]), float(d["z0"]), float(d["neig"]), float(d["tiefe"])))
    O["bauteile"] = [x for x in O["bauteile"] if x["typ"] != typ] + [b]; json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False)

def kontur_speichern(typ, K):
    O = obj(); shutil.copy(OJ, OJ + ".edit_bak")
    for b in O["bauteile"]:
        if b["typ"] == typ: b["kontur"] = [[round(float(x), 3), round(float(z), 3)] for x, z in K]; b.setdefault("werte_quellen", {})["kontur"] = "editor_modell.py: Fensterkontur vom Nutzer im Foto %s gezeichnet/verschoben (%d Punkte, relativ zur Fenstermitte und unterseite_z)" % (a.foto, len(K))
    json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False)

class H(BaseHTTPRequestHandler):
    def log_message(self, *x): pass
    def _send(self, code, ctype, body): self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            h = open(HTML, encoding="utf-8").read()
            if "test" in q: h += '<img src="/api/warte" width=1 height=1><script>setTimeout(async()=>{try{sel=%r;zeichne();if(%s){LIN=[[700,400,800,400],[800,400,800,500],[800,500,700,500],[700,500,700,400]];SELK=new Set([0,1,2,3]);zeichne();const P=kantenPolygon();FM={neu:true,kontur:[],mitten:[0],z0:0,s:13.5,neig:0};msg("POLY "+JSON.stringify(P)+" -> "+JSON.stringify(P.map(q=>{const w=unproj(q[0],q[1]);return[+w.u.toFixed(2),+w.v.toFixed(2)]})));FM=null;return}if(%s){await formUm();if(%s&&0){document.getElementById("kz").checked=true;await kzUm();await formSnap();return}const q0=FM.kontur[5],pp=fmPt(0,q0),w=unproj(pp[0],pp[1]);msg("ROUNDTRIP "+q0+" -> "+[(w.u-FM.mitten[0]).toFixed(3),(w.z-FM.z0).toFixed(3)]+" Punkte "+FM.kontur.length);return}const b=c.getBoundingClientRect(),k=b.width/c.width,h=griffe(BB).find(x=>x.hx==%s&&x.hy==%s),E=(t,x,y)=>c.dispatchEvent(new MouseEvent(t,{clientX:b.left+x*k,clientY:b.top+y*k,bubbles:true}));E("mousedown",h.x,h.y);E("mousemove",h.x+(%s),h.y+(%s));window.onmouseup();msg("SIM "+JSON.stringify(off[sel])+" dx="+(h.x)+" BB="+JSON.stringify(BB))}catch(e){msg("SIMFEHLER "+e+e.stack)}},20000)</script>' % (q.get("typ", ["stl_teil:fassade"])[0], "true" if "kmtest" in q else "false", "true" if "form" in q else "false", "true" if "snap" in q else "false", q.get("hx", ["1"])[0], q.get("hy", ["0"])[0], q.get("dx", ["120"])[0], q.get("dy", ["0"])[0])   # Testhilfe: Ladeereignis verzoegern, damit ein Headless-Screenshot das fertige Bild zeigt
            self._send(200, "text/html; charset=utf-8", h.encode())
        elif u.path == "/api/warte": import time; time.sleep(25); self._send(200, "image/gif", b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        elif u.path == "/api/start": self._send(200, "application/json", json.dumps(dict(fotos=sorted(KAM), foto=a.foto, teile=[b["typ"] for b in obj()["bauteile"] if b.get("aktiv", True) is not False], u=uax().tolist())).encode())
        elif u.path == "/api/bild":
            f = q.get("foto", [a.foto])[0]; g = cv2.imread(os.path.join(a.bilder, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); g = cv2.resize(g, (SW, int(g.shape[0] * SW / g.shape[1])), interpolation=cv2.INTER_AREA)
            self._send(200, "image/jpeg", cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes())
        elif u.path == "/api/kamera": K = KAM[q.get("foto", [a.foto])[0]]; self._send(200, "application/json", json.dumps(dict(K={k: K[k] for k in ("Rn", "tn", "f", "cx", "cy", "W", "H") if k in K}, s=SW / K["W"])).encode())
        elif u.path == "/ortho": self._send(200, "text/html; charset=utf-8", (open(os.path.join(os.path.dirname(HTML), "editor_ortho.html"), encoding="utf-8").read() + ('<img src="/api/warte" width=1 height=1><script>' + open(q["js"][0]).read() + '</script>' if "js" in q else "")).encode())
        elif u.path == "/api/ortho":
            f = lambda k, d: float(q.get(k, [d])[0]); self._send(200, "application/json", json.dumps(ortho(f("s0", 12.6), f("z0", 9.5), f("neig", 0), f("vor", 2.0), f("hinter", 0.4), f("px", 0.025), bool(int(q.get("schnell", ["0"])[0])))).encode())
        elif u.path == "/api/ebenen":
            E = ebenen()
            self._send(200, "application/json", json.dumps(dict(ebenen=E, u=uax().tolist())).encode())
        elif u.path == "/api/wolke_farbe":
            if "FB" not in WOLKE:
                if "Pf" not in WOLKE: WOLKE["Pf"] = np.load(a.wolke)[:, :3].astype(np.float32)
                rgb = np.load(os.path.join(os.path.dirname(a.wolke), "j_crop_rgb2.npy")).astype(np.uint8); assert len(rgb) == len(WOLKE["Pf"])
                WOLKE["FB"] = WOLKE["Pf"].tobytes() + rgb.tobytes()
            self._send(200, "application/octet-stream", WOLKE["FB"])
        elif u.path == "/api/wolke": self._send(200, "application/octet-stream", wolke_abstand())
        elif u.path == "/api/linien":
            f = q.get("foto", [a.foto])[0]; g = cv2.imread(os.path.join(a.bilder, f), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION); g = cv2.resize(g, (SW, int(g.shape[0] * SW / g.shape[1])), interpolation=cv2.INTER_AREA)
            L = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(g)[0]; L = np.zeros((0, 4)) if L is None else np.asarray(L).reshape(-1, 4); L = L[np.hypot(L[:, 2] - L[:, 0], L[:, 3] - L[:, 1]) > 18]
            self._send(200, "application/json", json.dumps(dict(l=np.round(L, 1).tolist())).encode())
        elif u.path == "/api/kontur": self._send(200, "application/json", json.dumps(kontur_info(q["typ"][0]) or {}).encode())
        elif u.path == "/3d_test":     # nur Test: 3D-Seite + Testskript aus Datei (Argument ?js=Pfad), ohne Wirkung im Normalbetrieb
            self._send(200, "text/html; charset=utf-8", (open(os.path.join(os.path.dirname(HTML), "editor_3d.html"), encoding="utf-8").read() + '<img src="/api/warte" width=1 height=1><script>' + open(q["js"][0]).read() + '</script>').encode())
        elif u.path == "/3d": self._send(200, "text/html; charset=utf-8", (open(os.path.join(os.path.dirname(HTML), "editor_3d.html"), encoding="utf-8").read() + ('<img src="/api/warte" width=1 height=1><script>setTimeout(async()=>{try{document.getElementById("wk").checked=true;await wolkeUm();R.render(sc,cam);const c2=document.createElement("canvas");c2.width=cv.width;c2.height=cv.height;c2.style.cssText="position:fixed;left:286px;top:0;width:"+cv.width+"px;height:"+cv.height+"px;z-index:5;background:#111";c2.getContext("2d").drawImage(cv,0,0);document.body.appendChild(c2)}catch(e){msg("FEHLER "+e)}},12000)</script>' if "test" in q else "")).encode())
        elif u.path.startswith("/vendor/"): self._send(200, "application/javascript", open(os.path.join(os.path.dirname(HTML), "vendor", os.path.basename(u.path)), "rb").read())
        elif u.path == "/api/mesh":
            typ = q["typ"][0]; b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]
            with LOCK: E = kanten(b, os.path.getmtime(OJ))
            self._send(200, "application/octet-stream", MESH.get(typ, b"") if E else b"")
        elif u.path == "/api/griffe": typ = q["typ"][0]; b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]; self._send(200, "application/json", json.dumps(dict(g=griffe_von(b))).encode())
        elif u.path == "/api/kanten":
            typ = q["typ"][0]; b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]
            with LOCK: E = kanten(b, os.path.getmtime(OJ))
            self._send(200, "application/json", json.dumps(dict(typ=typ, kanten=E, pivot=PIV.get(typ), n=(np.array(obj()["fassade_n"]["wert"], float) / np.linalg.norm(obj()["fassade_n"]["wert"])).tolist(), stl=typ.startswith("stl_teil"), skal=typ.startswith("stl_teil") or typ.split(":")[0] in SKAL)).encode())
        else: self._send(404, "text/plain", b"nein")
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/snap":
            typ = d["typ"]; b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]
            with LOCK: E = kanten(b, os.path.getmtime(OJ))
            if not E: return self._send(200, "application/json", json.dumps(dict(fehler="Teil nicht baubar")).encode())
            du, dz, s0, s1 = snap(d.get("foto", a.foto), E, float(d["du"]), float(d["dz"])); self._send(200, "application/json", json.dumps(dict(du=round(du, 3), dz=round(dz, 3), vorher=round(s0, 2), nachher=round(s1, 2))).encode())
        elif self.path == "/api/snappunkte": self._send(200, "application/json", json.dumps(dict(pts=kantenpunkte(d.get("foto", a.foto), d["pts"], float(d.get("r", 14))))).encode())
        elif self.path == "/api/bauen":
            with LOCK:
                env = dict(os.environ, SCALE="87", OBJ_DIR=os.path.join(R0, "modelle", a.objekt)); t0 = datetime.datetime.now()
                r = subprocess.run([os.path.expanduser("~/.venvs/rcpark/bin/python"), os.path.join(R0, "tools", "baukasten_gen.py"), a.objekt], env=env, capture_output=True, text=True, cwd=os.path.join(R0, "modelle", a.objekt))
            self._send(200, "application/json", json.dumps(dict(ok=r.returncode == 0, sek=round((datetime.datetime.now() - t0).total_seconds(), 1), log=(r.stdout + r.stderr)[-400:])).encode())
        elif self.path == "/api/griff":
            with LOCK: err = griff_anwenden(d["typ"], d["id"], float(d["u"]), float(d["z"]))
            self._send(200, "application/json", json.dumps(dict(ok=err is None, fehler=err)).encode())
        elif self.path == "/api/wahrheit":
            self._send(200, "application/json", json.dumps(dict(n=wahrheit_speichern(d))).encode())
        elif self.path == "/api/synth":
            self._send(200, "application/json", json.dumps(synth_pruefstand(ORD["last"], int(d.get("anz", 14)), float(d.get("pos_cm", 3.0)), float(d.get("rot_grad", 0.15)))).encode())
        elif self.path == "/api/heldout":
            dd = ORD["last"]; M = {"Wolken-Ortho Fusion >=8": [l[:4] for l in dd["lin"] if l[4] >= 8], "Wolken-Ortho Fusion >=20": [l[:4] for l in dd["lin"] if l[4] >= 20],
                 "Foto: LSD je Foto ohne Verbinden (ref roh)": [l[:4] for l in dd.get("roh", [])], "Foto-Ref (verbunden+eingerastet)": [l[:4] for l in dd.get("ref", [])]}
            M = {k: v for k, v in M.items() if v}; self._send(200, "application/json", json.dumps(vergleich_heldout(dd, M, int(d.get("anz", 14)), float(d.get("tol", 2.5)))).encode())
        elif self.path == "/api/fotokanten":
            r_ = fotokanten_ref(ORD["last"], float(d.get("stuetz", 0.25))) if d.get("ref", True) else fotokanten_auto(ORD["last"]) if d.get("auto", True) else fotokanten_voll(ORD["last"], float(d.get("cmin", 0.9)), int(d.get("anz", 80)), bool(d.get("tiefe", False)), float(d.get("anteil", 0.3)))
            if "fehler" in r_: self._send(200, "application/json", json.dumps(r_).encode()); return
            im_ = cv2.imencode(".png", ORD["last"]["F"])[1].tobytes(); r_["F"] = "data:image/png;base64," + __import__("base64").b64encode(im_).decode()
            self._send(200, "application/json", json.dumps(r_).encode())
        elif self.path == "/api/fotoortho":
            fl = beste_fotos(ORD["last"], int(d.get("anz", 3))); outs = []
            for i, f in enumerate(fl):
                im, ok = foto_ortho(ORD["last"], f, bool(d.get("tiefe", False))); im[~ok] = 0; pth = d["pfad"] + "_%d.png" % i; cv2.imwrite(pth, im); outs.append([f, pth])
            cv2.imwrite(d["pfad"] + "_wolke.png", cv2.imdecode(np.frombuffer(__import__("base64").b64decode(ORC_LAST["bild"].split(",")[1]), np.uint8), 1))
            self._send(200, "application/json", json.dumps(dict(fotos=outs)).encode())
        elif self.path == "/api/vsfoto":
            self._send(200, "application/json", json.dumps(foto_stuetzung(ORD["last"], int(d.get("anz", 12)), float(d.get("tol", 2.5)))).encode())
        elif self.path == "/api/vsmodell":
            self._send(200, "application/json", json.dumps(verfahren_vs_modell(float(d.get("tol", 6.0)))).encode())
        elif self.path == "/api/bewerten":
            self._send(200, "application/json", json.dumps(kanten_bewerten(float(d.get("tol", 3.0)))).encode())
        elif self.path == "/api/gruppen":
            self._send(200, "application/json", json.dumps(gruppen(float(d.get("thr", 0.12)), float(d.get("minfl", 0.15)))).encode())
        elif self.path == "/api/pfad":
            self._send(200, "application/json", json.dumps(dict(pfad=pfad(d["wp"]))).encode())
        elif self.path == "/api/maske":
            import base64
            self._send(200, "application/json", json.dumps(dict(flaechen=maske_zu_flaechen(int(d["w"]), int(d["h"]), base64.b64decode(d["daten"]), float(d.get("eps", 3.0))))).encode())
        elif self.path == "/api/gleiche":
            self._send(200, "application/json", json.dumps(gleiche(d["poly"], float(d.get("thr", 0.5)), bool(d.get("eigene_skala", False)))).encode())
        elif self.path == "/api/boegen":
            self._send(200, "application/json", json.dumps(dict(boegen=boegen(d["linien"], ORD["last"]["px"]))).encode())
        elif self.path == "/api/sam_flaechen":
            self._send(200, "application/json", json.dumps(sam_flaechen(ORD["last"], float(d.get("minfl", 0.03)), fein=bool(d.get("fein", False)))).encode())
        elif self.path == "/api/regionen":
            self._send(200, "application/json", json.dumps(dict(regionen=regionen(d["linien"], float(d.get("minfl", 0.05)), int(d.get("luecke", 12))))).encode())
        elif self.path == "/api/freiform":
            with LOCK: freiform_anlegen(d)
            self._send(200, "application/json", json.dumps(dict(ok=True)).encode())
        elif self.path == "/api/kontur":
            with LOCK: kontur_speichern(d["typ"], d["kontur"])
            self._send(200, "application/json", json.dumps(dict(ok=True)).encode())
        elif self.path == "/api/speichern":
            with LOCK: r = speichern(d["teile"])
            self._send(200, "application/json", json.dumps(dict(ok=True, log=r, hinweis="objekt.json geschrieben (Sicherung .edit_bak). Gesamt-STL neu bauen: tools/baukasten_gen.py")).encode())
        else: self._send(404, "text/plain", b"nein")
print("Editor: http://127.0.0.1:%d/  Objekt %s" % (a.port, a.objekt), flush=True); ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
