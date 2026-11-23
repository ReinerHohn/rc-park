#!/usr/bin/env python3
"""kamera_verfeinern.py <objekt.json> <fassaden.json> <FOTO> [--gegen FOTO,FOTO,...] [--n 6] [--schreiben] - Kamera eines (nach)registrierten Fotos am MODELL nachziehen.

Warum (16.11.2026, Stufe `seiten`): ein automatisch geladenes Webfoto (Flickr ov_0005, zeigt die sonst ungesehene Ostseite) wurde vom SfM registriert, aber seine
SfM-Punkte liegen fast alle auf EINER Wand (Sued) -> Brennweite und Abstand sind schlecht bestimmt, auf der Ostwand lag die Projektion ~0,9 m daneben.
Automatik ohne Handpicks:
  1. Referenzfotos mit guter Kamera: --gegen oder die --n Kameras mit dem aehnlichsten Standort/Blick (K-Dateien).
  2. ALIKED + LightGlue zwischen dem Foto und jeder Referenz (GPU).
  3. Jeden Treffer der Referenz in 3D heben: Tiefenbild des MODELLS (STL) aus der Referenzkamera rendern (GPU), Tiefe am Treffer lesen (nicht an Tiefenkanten).
     So entstehen 2D-3D-Paare auf ALLEN Flaechen, die beide Fotos zeigen - auch auf der vom SfM ungesehenen Wand. (Erste Fassung schnitt mit den LoD2-Fassadenebenen:
     die liegen bis 0,75 m neben der echten Wand -> Ostpunkte fielen alle als Ausreisser heraus.)
  4. PnP mit RANSAC ueber mehrere Brennweiten, dann Feinausgleich (Drehung, Lage, Brennweite frei). Bericht: Inlier je Wand, Restfehler in px und m.
  --schreiben: K-<FOTO>.json 'kamera' ersetzen (alte bleibt als 'kamera_vorher'). Ohne Schalter nur Bericht.
Grenzen: so gut wie Modell und Referenzkamera; mindestens 2 Flaechenrichtungen mit je >= 15 Inliern,
sonst gilt die Kamera weiter als unsicher (rc 3).
STAPEL (--liste, 23.11.2026, Kette 1122q: 327 Einzelprozesse = 75 von 165 min der Stufe seiten_luecken, je Prozess ~5 s nur Importe + STL-Laden, dazu je Foto
die Merkmale und Tiefenbilder von ~6 Referenzen neu - 1962 Referenzaufrufe auf nur 259 verschiedene Referenzen): EIN Prozess, Fotos in der Reihenfolge der Liste,
K-Dateien werden je Foto frisch gelesen (ein im Stapel geschriebenes Foto ist fuer die folgenden Referenz wie beim Einzelaufruf). Ergebnis = Folge der Einzelaufrufe:
Tiefenbild-Zwischenspeicher je (Foto, rvec, t, f_px, cx, cy) - ein frueher nachgezogenes Referenzfoto bekommt ein NEUES Tiefenbild (der alte Schluessel nur nach Name
haette das veraltete benutzt); Speicher begrenzt (LRU: RCPARK_KV_TIEFE_MB Tiefenbilder im RAM, Standard 768; RCPARK_KV_MERKMALE Merkmalssaetze auf der GPU, Standard 96).
Test: tools/test_kamera_verfeinern_stapel.py (Stapel == Einzelaufrufe, bitgleiche K-Dateien).
"""
import sys, os, json, glob, argparse, numpy as np, cv2, torch, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collections
import render_kern as rk
from scipy.optimize import least_squares
GERAET = "cuda"      # Test (tools/test_kamera_verfeinern_stapel.py) setzt "cpu" mit Ersatz-Merkmalen/-Renderer


class LRU(collections.OrderedDict):
    """Zwischenspeicher mit Obergrenze (Anzahl oder Summe von groesse(wert)); verdraengt das am laengsten nicht benutzte. Verdraengen aendert kein Ergebnis
    (Merkmale/Tiefenbild werden dann neu gerechnet wie beim Einzelaufruf), nur die Laufzeit."""
    def __init__(self, grenze, groesse=lambda v: 1):
        super().__init__(); self.grenze = grenze; self.groesse = groesse; self.summe = 0
    def holen(self, k):
        if k not in self: return None
        self.move_to_end(k); return self[k]
    def ablegen(self, k, v):
        if k in self: self.summe -= self.groesse(self.pop(k))
        self[k] = v; self.summe += self.groesse(v)
        while len(self) > 1 and self.summe > self.grenze: _, alt = self.popitem(last=False); self.summe -= self.groesse(alt)


def tiefen_schluessel(n, k):
    """Schluessel des Tiefenbild-Zwischenspeichers: Foto UND Kamera (das Tiefenbild haengt an rvec/t/f_px/cx/cy). Nur der Name waere im Stapel falsch,
    sobald die Referenz selbst vorher im Stapel nachgezogen wurde."""
    return (n,) + tuple(json.dumps(k.get(x)) for x in ("rvec", "t", "f_px", "cx", "cy"))


def exif_f_px(pfad_, W, H):
    """Brennweite in Pixeln aus EXIF (35-mm-Aequivalent), None wenn nicht vorhanden oder das Bild offensichtlich beschnitten/verkleinert ohne Angabe ist."""
    try:
        from PIL import Image
        ex = Image.open(pfad_).getexif(); f35 = ex.get_ifd(0x8769).get(0xA405)
        return float(f35) / 36.0 * max(W, H) if f35 and 10 <= float(f35) <= 1200 else None
    except Exception: return None


def main(argv=None):
    from lightglue import LightGlue, ALIKED
    from lightglue.utils import load_image, rbd
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fassaden"); ap.add_argument("foto"); ap.add_argument("--liste", help="Datei mit Fotonamen (einer je Zeile) - alle in einem Lauf, Referenzen werden nur einmal gerechnet; Argument FOTO dann beliebig"); ap.add_argument("--gegen"); ap.add_argument("--n", type=int, default=6); ap.add_argument("--schreiben", action="store_true"); ap.add_argument("--min_tiefe", type=float, default=0.06, help="kleinste Tiefenspanne der Inlier relativ zum Abstand, ab der die Brennweite frei geschaetzt werden darf"); ap.add_argument("--stl", help="weitere STL (Nachbarobjekte im selben Rahmen), Komma-Liste"); a = ap.parse_args(argv)
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"]); mp = os.path.join(od, "messprotokoll")
    ms = [trimesh.load(q_) for q_ in ([os.path.join(root, obj["stl"])] + (a.stl.split(",") if a.stl else []))]; mm = trimesh.util.concatenate(ms) if len(ms) > 1 else ms[0]; mm.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0)
    def kam(n):
        p = os.path.join(mp, "K-" + n + ".json")
        if not os.path.exists(p): return None
        k = json.load(open(p)).get("kamera"); return k if isinstance(k, dict) and "rvec" in k else None
    def pfad(n): g = glob.glob(os.path.join(fd, n + ".*")); return g[0] if g else None
    dev = GERAET; ex = ALIKED(max_num_keypoints=4096).eval().to(dev); mt = LightGlue(features="aliked").eval().to(dev)
    MK = LRU(int(os.environ.get("RCPARK_KV_MERKMALE", "96")))                                                         # Merkmale der Referenzen (GPU, ~2 MB je Satz)
    TK = LRU(float(os.environ.get("RCPARK_KV_TIEFE_MB", "768")) * 2 ** 20, lambda v: v[0].nbytes + v[1].nbytes)      # Tiefenbild + Dreiecksnummer je (Referenz, Kamera), RAM
    fotos = [z_.strip() for z_ in open(a.liste) if z_.strip()] if a.liste else [a.foto]; rcs = []
    def eins():
        K0 = kam(a.foto)
        if K0 is not None: R0 = cv2.Rodrigues(np.array(K0["rvec"]))[0]; C0 = -R0.T @ np.array(K0["t"]); blick0 = R0[2]
        if a.gegen: refs = a.gegen.split(",")
        elif K0 is None:                                                      # 16.11.2026: Foto OHNE Kamera (vom SfM nicht registriert): gegen einen Kranz guter Fotos rund ums Gebaeude -
            refs = []                                                         # je Fassade die 3 mit den meisten Zellen im Fassadenbild + alle schon nachgezogenen Fremdfotos (erhoehte Standorte)
            for F in json.load(open(a.fassaden))["fassaden"]:
                if F.get("flaeche_m2", 0) >= 40: refs += sorted(F.get("fotos", {}), key=lambda k_: -F["fotos"][k_].get("zellen", 0))[:3]
            refs += [os.path.basename(p_)[2:-5] for p_ in glob.glob(os.path.join(mp, "K-*.json")) if (kam(os.path.basename(p_)[2:-5]) or {}).get("vertrauen") and not (kam(os.path.basename(p_)[2:-5]) or {}).get("tiefe_unsicher")]
            refs = [n for n in dict.fromkeys(refs) if n != a.foto and kam(n) and pfad(n) and not n.startswith("video")][:24]
            K0 = dict(f_px=float("nan")); C0 = np.full(3, np.nan)
        else:
            kand = []
            for p in glob.glob(os.path.join(mp, "K-*.json")):
                n = os.path.basename(p)[2:-5]; k = kam(n)
                if n == a.foto or k is None or not pfad(n): continue
                if k.get("tiefe_unsicher") or (n.startswith(("dl_", "neu__", "video")) and not k.get("vertrauen")): continue     # 16.11.2026: nur vertrauenswuerdige Referenzen (Buendelkameras eigener/Commons-Fotos oder schon nachgezogene) -
                                                                                                   # sonst bestaetigt sich eine falsche Pose am eigenen Duplikat / an falsch verorteten Videobildern (ov_0005: 27 m vor dem Turm in der Luft)
                R = cv2.Rodrigues(np.array(k["rvec"]))[0]; C = -R.T @ np.array(k["t"]); kand.append((np.linalg.norm(C - C0) * (2.0 - float(R[2] @ blick0)), n))
            refs = [n for _, n in sorted(kand)[:a.n]]
        def merk(n):
            f = MK.holen(n)
            if f is not None: return f, 1.0
            im = load_image(pfad(n)); h, w = im.shape[1:]; s = min(1.0, 1600.0 / max(h, w)); f = ex.extract(im.to(dev), resize=int(max(h, w) * s))
            if n != a.foto: MK.ablegen(n, f)
            return f, 1.0
        fA, _ = merk(a.foto); P2, P3, WN, RF = [], [], [], []
        for n in refs:
            k = kam(n)
            if k is None or not pfad(n): continue
            fB, _ = merk(n)
            with torch.no_grad(): m = rbd(mt({"image0": fA, "image1": fB}))["matches"].cpu().numpy()
            if len(m) < 20: print(f"  {n[-26:]}: {len(m)} Treffer"); continue
            xa = rbd(fA)["keypoints"].cpu().numpy()[m[:, 0]]; xb = rbd(fB)["keypoints"].cpu().numpy()[m[:, 1]]
            R = cv2.Rodrigues(np.array(k["rvec"]))[0]; C = -R.T @ np.array(k["t"]); x = (xb[:, 0] - k["cx"]) / k["f_px"]; y = (xb[:, 1] - k["cy"]) / k["f_px"]; k1 = float(k.get("k1") or 0); xu, yu = x.copy(), y.copy()
            for _ in range(4): q = 1 + k1 * (xu * xu + yu * yu); xu, yu = x / q, y / q
            D = np.stack([xu, yu, np.ones_like(xu)], 1) @ R                     # Weltstrahl je Treffer, Kamera-z-Anteil = 1
            hb, wb = int(round(2 * k["cy"])), int(round(2 * k["cx"])); sk = min(1.0, 1800.0 / max(hb, wb)); Wr, Hr = int(wb * sk), int(hb * sk)
            tk_ = tiefen_schluessel(n, k); tf_ = TK.holen(tk_)
            if tf_ is None:                                                    # Tiefenbild des MODELLS aus der Referenzkamera (GPU), je (Referenz, Kamera) einmal
                d_, i_ = [np.asarray(v_) for v_ in rk.dreiecke_rastern(mm, R, np.array(k["t"]), k["f_px"] * sk, k["cx"] * sk, k["cy"] * sk, Wr, Hr)[:2]]
                tf_ = (d_, i_.astype(np.int32) if len(mm.faces) < 2 ** 31 else i_); TK.ablegen(tk_, tf_)      # Dreiecksnummer int32 (verlustfrei): 8 statt 12 Byte je Pixel
            tiefe, fid = tf_
            ui = np.clip((xb[:, 0] * sk).astype(int), 0, Wr - 1); vi = np.clip((xb[:, 1] * sk).astype(int), 0, Hr - 1); best = tiefe[vi, ui].astype(np.float64); f_ = fid[vi, ui]; tr = f_ >= 0
            for du, dv in ((-2, 0), (2, 0), (0, -2), (0, 2)):                  # nicht an Tiefenkanten heben (Nachbarpixel muessen dieselbe Tiefe haben)
                tr &= np.abs(tiefe[np.clip(vi + dv, 0, Hr - 1), np.clip(ui + du, 0, Wr - 1)] - best) < 0.15
            nrm = mm.face_normals[np.where(tr, f_, 0)]; az = (np.round(np.degrees(np.arctan2(nrm[:, 1], nrm[:, 0])) / 90.0).astype(int) % 4); wand = np.where(tr, np.where(nrm[:, 2] > 0.5, 4, az), -1)   # Flaechenklasse: 4 Himmelsrichtungen, 4 = Dach
            ok = wand >= 0; X = C + best[ok, None] * D[ok]; P2.append(xa[ok]); P3.append(X); WN.append(wand[ok]); RF += [n] * int(ok.sum()); print(f"  {n[-26:]}: {len(m)} Treffer, {int(ok.sum())} auf dem Modell")
        if not P2: print("keine Paare"); return 2
        P2 = np.vstack(P2).astype(np.float64); P3 = np.vstack(P3).astype(np.float64); WN = np.concatenate(WN); im = cv2.imread(pfad(a.foto)); H, W = im.shape[:2]; cx, cy = W / 2, H / 2; best = None
        for f in np.geomspace(0.4 * max(W, H), 12 * max(W, H), 30):
            Km = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]]); ok, r, t, inl = cv2.solvePnPRansac(P3, P2, Km, None, reprojectionError=max(4.0, 0.004 * max(W, H)), iterationsCount=400, flags=cv2.SOLVEPNP_EPNP)
            if ok and inl is not None and (best is None or len(inl) > len(best[3])): best = (f, r, t, inl.ravel())
        if best is None or len(best[3]) < 30: print("PnP ohne tragfaehige Loesung"); return 3
        f, r, t, inl = best
        def res(p): pr, _ = cv2.projectPoints(P3[inl], p[:3], p[3:6], np.array([[p[6], 0, cx], [0, p[6], cy], [0, 0, 1.0]]), None); return (pr.reshape(-1, 2) - P2[inl]).ravel()
        s = least_squares(res, np.r_[r.ravel(), t.ravel(), f], loss="soft_l1", f_scale=3.0); p = s.x; err = np.sqrt((res(p) ** 2).reshape(-1, 2).sum(1)); R = cv2.Rodrigues(p[:3])[0]; C = -R.T @ p[3:6]; dist = float(np.median(np.linalg.norm(P3[inl] - C, axis=1)))
        je_wand = {int(w): int((WN[inl] == w).sum()) for w in np.unique(WN[inl])}; tragend = sum(1 for v in je_wand.values() if v >= 15)
        print(f"{a.foto}: {len(inl)} Inlier von {len(P2)}, je Wand {je_wand}, Rest Median {np.median(err):.1f} px = {np.median(err) * dist / p[6] * 100:.0f} cm an der Wand; f {K0['f_px']:.0f} -> {p[6]:.0f} px, Standort {np.round(C0, 1).tolist()} -> {np.round(C, 1).tolist()} ({np.linalg.norm(C - C0):.1f} m verschoben)")
        # 16.11.2026 nachts (Kameras "am Mond"): Brennweite und Abstand sind nur trennbar, wenn die Punkte in der TIEFE verteilt sind. Mass: Tiefenspanne (p5-p95 entlang der Blickachse) / Abstand.
        zc_ = (P3[inl] @ R.T + p[3:6])[:, 2]; tiefe_rel = float((np.percentile(zc_, 95) - np.percentile(zc_, 5)) / max(np.median(zc_), 1e-6)); f_exif = exif_f_px(pfad(a.foto), W, H)
        if f_exif and (tiefe_rel < a.min_tiefe or abs(np.log(p[6] / f_exif)) > np.log(1.25)):      # bekannte Linse (EXIF): festhalten, wenn die Geometrie die Brennweite nicht traegt oder ihr um > 25 % widerspricht
            def res_f(q): pr, _ = cv2.projectPoints(P3[inl], q[:3], q[3:6], np.array([[f_exif, 0, cx], [0, f_exif, cy], [0, 0, 1.0]]), None); return (pr.reshape(-1, 2) - P2[inl]).ravel()
            ok_, r_, t_ = cv2.solvePnP(P3[inl], P2[inl], np.array([[f_exif, 0, cx], [0, f_exif, cy], [0, 0, 1.0]]), None, flags=cv2.SOLVEPNP_EPNP); q = least_squares(res_f, np.r_[r_.ravel(), t_.ravel()], loss="soft_l1", f_scale=3.0).x
            e2 = np.sqrt((res_f(q) ** 2).reshape(-1, 2).sum(1))
            if np.median(e2) < max(3 * np.median(err), 6.0): print(f"  Brennweite aus EXIF festgehalten ({f_exif:.0f} px statt {p[6]:.0f}; Tiefenspanne {tiefe_rel * 100:.0f} %), Rest {np.median(e2):.1f} px"); p = np.r_[q, f_exif]; err = e2; R = cv2.Rodrigues(p[:3])[0]; C = -R.T @ p[3:6]; dist = float(np.median(np.linalg.norm(P3[inl] - C, axis=1)))
            else: print(f"{a.foto}: EXIF-Brennweite {f_exif:.0f} px passt nicht zu den Punkten (Rest {np.median(e2):.0f} px) - falsche Zuordnung, nicht geschrieben"); return 3
        elif tiefe_rel < a.min_tiefe: print(f"{a.foto}: Punkte liegen fast in einer Ebene (Tiefenspanne {tiefe_rel * 100:.1f} % des Abstands < {a.min_tiefe * 100:.0f} %) und keine EXIF-Brennweite - Abstand/Zoom nicht trennbar, nicht geschrieben"); return 3
        if tragend < 2: print("nur eine Wand mit >= 15 Inliern - Kamera bleibt unsicher, nicht geschrieben"); return 3
        if not np.isfinite(C).all() or dist > 600 or p[6] > 10 * max(W, H) or p[6] < 0.4 * max(W, H): print(f"{a.foto}: Loesung unplausibel (Abstand {dist:.0f} m, f {p[6]:.0f} px bei {max(W, H)} px Bildbreite) - entartete Tele-Loesung, nicht geschrieben"); return 3      # 16.11.2026: PnP mit freier Brennweite lief bei fast ebenen Punkten ins Unendliche (Kamera 350 000 km entfernt, trotzdem 2 Flaechen >= 15 Inlier)
        if a.schreiben:
            kp = os.path.join(mp, "K-" + a.foto + ".json"); d = json.load(open(kp)) if os.path.exists(kp) else dict(foto=a.foto, seite="unbekannt", punkte={}, linien={})
            if d.get("kamera"): d["kamera_vorher"] = d["kamera"]
            d["kamera"] = dict(rvec=p[:3].tolist(), t=p[3:6].tolist(), f_px=float(p[6]), cx=cx, cy=cy, k1=0.0, standort=C.tolist(), quelle=f"kamera_verfeinern.py: {len(inl)} Inlier auf {tragend} Waenden gegen {sorted(set(RF))[:6]}, Rest {np.median(err):.1f} px", tiefenspanne=round(tiefe_rel, 3), vertrauen=True, rest_px_median=float(np.median(err)), inlier_je_wand=je_wand)
            __import__("json_sicher").schreiben(kp, d); print("geschrieben:", kp)
        return 0
    for f_ in fotos:
        a.foto = f_
        try: rcs.append(eins())
        except Exception as e_:
            print(f"{f_}: Fehler {str(e_)[:120]}"); rcs.append(9)
            if dev == "cuda": torch.cuda.empty_cache()      # Stapel: ein GPU-Speicherfehler bei einem Foto soll die folgenden nicht mitreissen (Einzelaufruf: neuer Prozess)
        if len(fotos) > 1: print(f"FOTO {len(rcs)}/{len(fotos)} {f_}: rc {rcs[-1]}", flush=True)
    print(f"FERTIG: {sum(1 for r_ in rcs if r_ == 0)} von {len(rcs)} Kameras bestimmt"); return 0 if any(r_ == 0 for r_ in rcs) else 3


if __name__ == "__main__":
    sys.exit(main())
