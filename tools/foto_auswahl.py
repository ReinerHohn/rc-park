#!/usr/bin/env python3
"""foto_auswahl.py - Automatische Bildauswahl: Kennzahlen je Foto VOR dem Netz + Pruefung, welche davon die Registrierung wirklich vorhersagen (Register BK).

Je Foto aus objekt.json (fotos_dir/<nr>_*): Groesse, Schaerfe (Laplace-Varianz auf 640 px), EXIF-35mm-Brennweite, Seite laut objekt.json.
Wenn das Foto in sfm/db_<seite>.db liegt: Merkmalszahl, Grad im Match-Graphen (Paare mit >= MIN_INL Inliern), Summe der Inlier, staerkste Verbindung.
Wenn ein Netz (sfm/sparse_<seite>/0) vorliegt: registriert ja/nein, Zahl der 3D-Punkte, mittlerer Reprojektionsfehler.
Pruefung (Beweis statt Behauptung): je Kennzahl AUC (Mann-Whitney, registriert vs nicht) mit exaktem Permutationstest-p ueber alle Netze einzeln;
nur Kennzahlen, die VOR der Rekonstruktion bekannt sind, taugen als Filter (Grad/Inlier kommen aus dem billigen Match-Schritt, nicht aus dem Netz).
  /media/oem/scan/venv-colmap/bin/python -I tools/foto_auswahl.py modelle/<objekt>/objekt.json [--ziel-sfm sfm] [--json audit/foto_auswahl.json]
Ergebnis aendert KEINE Eingabedatei. Auswahl-Vorschlag erst, wenn eine Kennzahl nachweislich traegt (Bericht am Ende).
"""
import sys, os, json, glob, sqlite3, argparse, itertools
import numpy as np, cv2
from PIL import Image, ExifTags

MIN_INL = 15
T = {v: k for k, v in ExifTags.TAGS.items()}

def kennzahlen_bild(fp):
    r = {}
    try:
        im = Image.open(fp); r["breite"], r["hoehe"] = im.size; ex = im.getexif().get_ifd(0x8769); f35 = ex.get(T["FocalLengthIn35mmFilm"]); r["f35"] = float(f35) if f35 else None
    except Exception: r["breite"] = r["hoehe"] = r["f35"] = None
    g = cv2.imread(fp, cv2.IMREAD_GRAYSCALE)
    if g is not None: s = 640 / max(g.shape); r["schaerfe"] = float(cv2.Laplacian(cv2.resize(g, None, fx=s, fy=s), cv2.CV_64F).var())
    else: r["schaerfe"] = None
    return r

def graph(dbp):
    """name(nr) -> {kp, grad, inlier_summe, staerkste}"""
    c = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True); ids = {i: n[:3] for i, n in c.execute("select image_id,name from images")}
    kp = dict(c.execute("select image_id, rows from keypoints")); G = {i: dict(kp=kp.get(i, 0), grad=0, inlier=0, staerkste=0) for i in ids}
    for pid, rows in c.execute("select pair_id, rows from two_view_geometries"):
        if rows < MIN_INL: continue
        i2 = pid % 2147483647; i1 = (pid - i2) // 2147483647
        for i in (i1, i2):
            if i in G: G[i]["grad"] += 1; G[i]["inlier"] += rows; G[i]["staerkste"] = max(G[i]["staerkste"], rows)
    return {ids[i]: v for i, v in G.items()}

def netz(sd, seite):
    import pycolmap
    for p in (os.path.join(sd, f"sparse_{seite}", "0"), os.path.join(sd, f"sparse_modell_{seite}")):
        if os.path.isdir(p):
            r = pycolmap.Reconstruction(p); out = {}
            for im in r.images.values():
                pts = [pt for pt in im.points2D if pt.has_point3D()]; out[im.name[:3]] = dict(punkte3d=len(pts))
            return out
    return None


def beitrag(sd, seite, H=65.0):
    """Beitrag je REGISTRIERTES Foto, rein analytisch aus dem Netz (kein Neuberechnen): was geht verloren, wenn das Foto fehlt?
    verlorene_punkte = 3D-Punkte, deren Spur genau 2 Beobachtungen hat und dieses Foto enthaelt (ohne es nicht mehr triangulierbar);
    verloren_oben = davon Punkte ueber 0,5 H; sektor_einzel = Foto ist eine von <= 2 Kameras im 45-Grad-Sektor; Kosten ~ PatchMatch-Zeit je Foto (gleichmaessig)."""
    import pycolmap
    p = os.path.join(sd, f"sparse_modell_{seite}")
    if not os.path.isdir(p): return None
    r = pycolmap.Reconstruction(p); nm = {i: im.name[:3] for i, im in r.images.items()}; V = {n: dict(verlorene_punkte=0, verloren_oben=0, punkte3d=0) for n in nm.values()}
    gesamt = 0; oben = 0
    for pt in r.points3D.values():
        el = [e.image_id for e in pt.track.elements]; gesamt += 1; o = pt.xyz[2] > 0.5 * H; oben += o
        for i in set(el):
            if i in nm: V[nm[i]]["punkte3d"] += 1
        if len(el) == 2:
            for i in el:
                if i in nm: V[nm[i]]["verlorene_punkte"] += 1; V[nm[i]]["verloren_oben"] += int(o)
    pos = {nm[i]: np.array(im.projection_center()) for i, im in r.images.items() if im.has_pose}; az = {n: np.degrees(np.arctan2(c[1], c[0])) % 360 for n, c in pos.items()}
    sek = {n: int(a // 45) for n, a in az.items()}; zaehl = {k: sum(1 for v in sek.values() if v == k) for k in set(sek.values())}
    for n, v in V.items():
        v["sektor"] = sek.get(n); v["sektor_einzel"] = bool(n in sek and zaehl[sek[n]] <= 2); v["anteil_verloren"] = round(v["verlorene_punkte"] / max(gesamt, 1), 4); v["anteil_verloren_oben"] = round(v["verloren_oben"] / max(oben, 1), 4)
    return dict(punkte=gesamt, punkte_oben=oben, fotos=V)

def waehle(sd, seite, n, H=65.0, w_oben=5.0, schicht=False):
    """Stufe grob: waehle n Fotos, die moeglichst viele 3D-Punkte weiterhin triangulierbar halten (greedy, Punkt zaehlt, wenn >= 2 gewaehlte Fotos ihn sehen;
    Punkte ueber 0,5 H zaehlen w_oben-fach). Rein aus dem Netz, deterministisch."""
    import pycolmap
    r = pycolmap.Reconstruction(os.path.join(sd, f"sparse_modell_{seite}")); nm = {i: im.name[:3] for i, im in r.images.items() if im.has_pose}
    sp = []   # (gewicht, set der Foto-Nummern)
    for pt in r.points3D.values():
        f = {nm[e.image_id] for e in pt.track.elements if e.image_id in nm}
        if len(f) >= 2: sp.append((w_oben if pt.xyz[2] > 0.5 * H else 1.0, f, pt.xyz[2]))
    if schicht:                                                                              # Schichtgleich: jede 5-m-Hoehenschicht traegt gleich viel Gewicht (die duenne obere Haelfte zaehlt wie die dichte untere)
        zb = lambda z: int(np.floor(z / 5.0)); cnt = {}
        for _, _, z in sp: cnt[zb(z)] = cnt.get(zb(z), 0) + 1
        sp = [(1.0 / cnt[zb(z)], f, z) for _, f, z in sp]
    sp = [(w, f) for w, f, _ in sp]
    gew = sum(w for w, _ in sp); gewaehlt = []; zaehl = [0] * len(sp); erg = []
    for _ in range(min(n, len(nm))):
        best, bw = None, -1.0
        for nr in nm.values():
            if nr in gewaehlt: continue
            g = sum(w for k, (w, f) in enumerate(sp) if nr in f and zaehl[k] == 1)          # Punkt wird mit diesem Foto triangulierbar
            g += 0.01 * sum(w for k, (w, f) in enumerate(sp) if nr in f and zaehl[k] == 0)   # Vorbereitung (zweites Foto folgt)
            if g > bw + 1e-12 or (abs(g - bw) <= 1e-12 and best is not None and nr < best): best, bw = nr, g
        gewaehlt.append(best)
        for k, (w, f) in enumerate(sp):
            if best in f: zaehl[k] += 1
        erg.append((best, round(sum(w for k, (w, f) in enumerate(sp) if zaehl[k] >= 2) / gew, 4)))
    return erg

def auc_p(x, y, n_perm=4000, seed=1):
    """AUC = P(x > y) (Mann-Whitney) + Permutations-p (zweiseitig). x registriert, y nicht."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or len(y) < 3: return None, None
    def auc(a, b): return float(((a[:, None] > b[None, :]).sum() + 0.5 * (a[:, None] == b[None, :]).sum()) / (len(a) * len(b)))
    a0 = auc(x, y); z = np.concatenate([x, y]); rng = np.random.default_rng(seed); k = 0
    for _ in range(n_perm):
        rng.shuffle(z); k += abs(auc(z[:len(x)], z[len(x):]) - 0.5) >= abs(a0 - 0.5) - 1e-12
    return a0, (k + 1) / (n_perm + 1)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--sfm", default="sfm"); ap.add_argument("--json", default="audit/foto_auswahl.json"); ap.add_argument("--schicht", action="store_true", help="mit --waehle: jede 5-m-Hoehenschicht gleich gewichten (statt Obergewicht 5)"); ap.add_argument("--waehle", type=int, help="Stufe grob: n Fotos je Netz per Abdeckung waehlen (greedy) und ausgeben"); ap.add_argument("--beitrag", action="store_true", help="nur den Beitrag je Foto (analytisch) ausgeben und Rangliste")
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); sd = os.path.join(od, a.sfm)
    if a.waehle:
        for sname in ("nord", "sued"):
            if not os.path.isdir(os.path.join(sd, f"sparse_modell_{sname}")): continue
            W = waehle(sd, sname, a.waehle, schicht=a.schicht); print(f"Netz {sname}: {a.waehle} Fotos (gewichtete Abdeckung triangulierbarer Punkte):"); print("  " + " ".join(f"{n}({100 * c:.0f}%)" for n, c in W)); print("  --fotos " + ",".join(n for n, _ in W))
        return
    if a.beitrag:
        B = {}
        for sname in ("nord", "sued"):
            b = beitrag(sd, sname)
            if not b: continue
            B[sname] = b; rang = sorted(b["fotos"].items(), key=lambda kv: -(kv[1]["verlorene_punkte"] + 5 * kv[1]["verloren_oben"] + (10000 if kv[1]["sektor_einzel"] else 0)))
            print(f"\nNetz {sname}: {b['punkte']} Punkte, {b['punkte_oben']} ueber 0,5 H. Rangliste nach Beitrag (hoch = unersetzlich):")
            for n, v in rang: print(f"  {n}  3D-Punkte {v['punkte3d']:6d}  verloren ohne Foto {v['verlorene_punkte']:5d} ({100 * v['anteil_verloren']:.1f} %)  davon oben {v['verloren_oben']:4d}  Sektor {v['sektor']}{' EINZEL' if v['sektor_einzel'] else ''}")
        o = os.path.join(od, "audit/foto_beitrag.json"); json.dump(B, open(o, "w"), indent=1, ensure_ascii=False, default=float); print("\ngeschrieben:", o); return
    fd = os.path.join(root, obj["fotos_dir"]); F = {}
    for nr, v in obj["fotos"].items():
        fs = glob.glob(os.path.join(fd, nr + "_*"))
        if fs: F[nr] = dict(seite=v.get("seite"), **kennzahlen_bild(fs[0]))
    print(f"{len(F)} Fotos mit Datei von {len(obj['fotos'])} in objekt.json")
    seiten = [s[len("db_"):-3] for s in sorted(os.listdir(sd)) if s.startswith("db_") and s.endswith(".db") and s[3:-3] in ("nord", "sued")]
    bericht = {}
    for s in seiten:
        G = graph(os.path.join(sd, f"db_{s}.db")); N = netz(sd, s)
        for nr, g in G.items():
            if nr in F: F[nr].update({f"{k}_{s}": v for k, v in g.items()}); F[nr][f"im_netz_{s}"] = True
            if nr in F and N is not None: F[nr][f"registriert_{s}"] = nr in N; F[nr][f"punkte3d_{s}"] = N.get(nr, {}).get("punkte3d", 0)
        if N is None: print(f"Netz {s}: kein Netz zum Vergleich"); continue
        reg = [nr for nr in G if nr in F and nr in N]; unreg = [nr for nr in G if nr in F and nr not in N]
        print(f"\nNetz {s}: {len(G)} Fotos in der DB, {len(reg)} registriert, {len(unreg)} nicht")
        bericht[s] = dict(in_db=len(G), registriert=len(reg), nicht=len(unreg), kennzahlen={})
        for k in ("schaerfe", "breite", "f35", f"kp_{s}", f"grad_{s}", f"inlier_{s}", f"staerkste_{s}"):
            x = [F[n][k] for n in reg if F[n].get(k) is not None]; y = [F[n][k] for n in unreg if F[n].get(k) is not None]
            A, P = auc_p(x, y)
            bericht[s]["kennzahlen"][k] = dict(auc=A, p=P, median_reg=float(np.median(x)) if x else None, median_nicht=float(np.median(y)) if y else None, n_reg=len(x), n_nicht=len(y))
            print(f"  {k:16} AUC {A if A is None else round(A, 2)}  p {P if P is None else round(P, 3)}   Median registriert {np.median(x) if x else None}  nicht {np.median(y) if y else None}  (n {len(x)}/{len(y)})")
    nutz = [f"{s}:{k}" for s, b in bericht.items() for k, v in b["kennzahlen"].items() if v["p"] is not None and v["p"] < 0.05 and v["auc"] is not None and abs(v["auc"] - 0.5) >= 0.2]
    print("\nKennzahlen mit AUC-Abstand >= 0,2 und p < 0,05:", nutz if nutz else "KEINE - kein Filter belegt")
    o = os.path.join(od, a.json); os.makedirs(os.path.dirname(o), exist_ok=True); json.dump(dict(fotos=F, pruefung=bericht, belegt=nutz), open(o, "w"), indent=1, ensure_ascii=False, default=float); print("geschrieben:", o)

if __name__ == "__main__":
    main()
