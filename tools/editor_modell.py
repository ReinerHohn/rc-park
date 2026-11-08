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
def ortho(s0, z0, neig, vor, hinter, px=0.025):
    k = (round(s0, 3), round(z0, 3), round(neig, 2), round(vor, 2), round(hinter, 2), px)
    if k not in ORC: ORC[k] = ortho_(s0, z0, neig, vor, hinter, px); ORD[k] = ORD["last"]
    ORD["last"] = ORD[k]; return ORC[k]

def ortho_(s0, z0, neig, vor, hinter, px=0.025):
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
    S = np.vstack(segs); meth = np.array([m[0] for m in mid]); fam = np.array([m[1] for m in mid]); ln = np.hypot(S[:, 2] - S[:, 0], S[:, 3] - S[:, 1]); o2 = np.argsort(-ln); S, meth, fam, ln = S[o2], meth[o2], fam[o2], ln[o2]
    d = (S[:, 2:] - S[:, :2]) / ln[:, None]; ang = np.arctan2(d[:, 1], d[:, 0]) % np.pi; used = np.zeros(len(S), bool); out = []
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
    ORD["last"] = dict(dep=dep, mk=(bm >= 0.02), px=px, vor=vor, hinter=hinter, gray=cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY), d8=d0)
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
            f = lambda k, d: float(q.get(k, [d])[0]); self._send(200, "application/json", json.dumps(ortho(f("s0", 12.6), f("z0", 9.5), f("neig", 0), f("vor", 2.0), f("hinter", 0.4), f("px", 0.025))).encode())
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
