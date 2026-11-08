#!/usr/bin/env python3
"""spitze_hoehe.py - Hoehe von Helm-/Nadelspitzen AUTOMATISCH aus der Himmelssilhouette aller kalibrierten Fotos (2026-11-05).

Warum: Kantenvergleich (foto_diff) ist auf der Nadel flach (Erkernadel 9-13 m gleich gut, Versuchslog stufe5), Laser DOM1 blind fuer Nadeln
(Regel 4). Die Spitze steht gegen den Himmel: entlang der senkrechten Achse (x, y fest, z laeuft) wird im Foto gesucht, bis zu welcher Hoehe
ein zusammenhaengender Koerper (Nicht-Himmel) reicht. Die Achse kommt aus dem Generator (Beleg masse.spitzen = [[x, y, z_fuss], ...]) oder
--achse; die Hoehe folgt aus der Buendelkamera (amtliche Anker) - kein Massstab aus dem Modell, nur die Achsenlage (Fehler quer zur Blickrichtung
verschiebt die Spitze seitlich, nicht in der Hoehe; Fehler in Blickrichtung ~ Abstand/Hoehe -> je Foto als Unsicherheit ausgewiesen).
Himmel je Pixel: Farbabstand zum Himmel-Median im Fenster (Himmelsmaske himmelsmaske/<nr>.png als Lernmenge, wenn vorhanden, sonst obere Fensterzeilen).
Ergebnis je Spitze: Median ueber die Fotos, Streuung, alle Einzelwerte; Widerspruch (Streuung > --toleranz) wird gemeldet, nicht gemittelt (Regel 5).

  /media/oem/scan/venv-seg/bin/python -I tools/spitze_hoehe.py <objekt.json> (--elemente <elemente.json> | --achse X Y ZFUSS ...) [--stl <modell.stl>] [--aus DIR]
"""
import os, sys, json, glob, argparse
import numpy as np, cv2
TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
import fehlteile_finden as FF
from fassade_ortho import projizieren, nachbarn_netz
import trimesh


def himmel_fenster(im, hm, x, y0, y1, hb, rand=3.0):
    """Fenster um die projizierte Achse; Rueckgabe Koerpermaske (True = kein Himmel) und Himmel-Median-Farbe (Lab)."""
    H, W = im.shape[:2]; xa, xb = max(0, int(x - rand * hb)), min(W, int(x + rand * hb) + 1); ya, yb = max(0, int(y1)), min(H, int(y0) + 1)
    if xb - xa < 5 or yb - ya < 10: return None
    lab = cv2.cvtColor(im[ya:yb, xa:xb], cv2.COLOR_BGR2LAB).astype(np.float32)
    lern = (hm[ya:yb, xa:xb] > 127) if hm is not None else np.zeros(lab.shape[:2], bool)
    if lern.sum() < 50: lern = np.zeros(lab.shape[:2], bool); lern[: max(3, (yb - ya) // 10)] = True     # ohne Maske: oberste Zeilen = Himmel (Achse reicht weit ueber die Spitze)
    med = np.median(lab[lern], 0); sd = np.median(np.abs(lab[lern] - med), 0) * 1.4826 + 2.0
    dist = np.sqrt((((lab - med) / sd) ** 2).sum(-1))
    return dist > 6.0, (xa, ya)


def _schnitt(O, D, ix):
    A = np.zeros((3, 3)); b = np.zeros(3)
    for i_ in ix: P_ = np.eye(3) - np.outer(D[i_], D[i_]); A += P_; b += P_ @ O[i_]
    return np.linalg.lstsq(A, b, rcond=None)[0]


def _abst(O, D, X_):
    v_ = X_ - O; return np.linalg.norm(v_ - (v_ * D).sum(1)[:, None] * D, axis=1)


def triangulieren(O, D, X, Y, Z0, tol, radius):
    """RANSAC ueber alle Strahlpaare: Punkt mit den meisten Strahlen naeher als tol; nur innerhalb radius um die Achse und ueber Z0. -> (Punkt, Inlier) oder None."""
    best = None
    for i_ in range(len(O)):
        for j_ in range(i_ + 1, len(O)):
            if abs(float(D[i_] @ D[j_])) > 0.995: continue                                            # fast parallel: Schnitt unbestimmt
            X_ = _schnitt(O, D, [i_, j_])
            if np.hypot(X_[0] - X, X_[1] - Y) > radius or X_[2] < Z0: continue
            inl_ = _abst(O, D, X_) < tol
            if best is None or inl_.sum() > best[1].sum(): best = (X_, inl_)
    return best


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--elemente"); ap.add_argument("--achse", nargs=3, type=float, action="append")
    ap.add_argument("--hoehe-max", type=float, default=20.0, help="Suchbereich ueber dem Fuss (m)"); ap.add_argument("--min-ppm", type=float, default=15.0, help="mindestens Pixel je Meter an der Achse")
    ap.add_argument("--luecke-m", type=float, default=0.4, help="groesste Luecke im Koerper entlang der Achse (Nadel duenn, Bildrauschen)")
    ap.add_argument("--fenster-m", type=float, default=1.0, help="halbe Fensterbreite (m) x 3 = Suchbreite quer zur Achse (Achsen-/Kameraversatz bis ~1 m)")
    ap.add_argument("--toleranz", type=float, default=0.8); ap.add_argument("--achse-sigma", type=float, default=0.5, help="Lagefehler der Achse in Blickrichtung (m): Generatorachse vs. Turm, Sichtpruefung 2026-11-05 bis ~1 m quer"); ap.add_argument("--max-unsicherheit", type=float, default=0.5, help="Foto verwerfen, wenn Hoehenunsicherheit groesser (steile Nahsicht)"); ap.add_argument("--stl", help="Modell (STL, mm) fuer die Sichtpruefung: Strahl zur Helmmitte darf nichts treffen (sonst misst die Spur Dach/Giebel davor)"); ap.add_argument("--tri-min", type=int, default=4, help="mindestens so viele Fotos im Konsens (test_spitze_hoehe T2: 3 Fehlspuren treffen sich zufaellig)"); ap.add_argument("--tri-tol", type=float, default=0.3, help="Strahlabstand (m) fuer Inlier der Triangulation"); ap.add_argument("--tri-radius", type=float, default=4.0, help="Spitze hoechstens so weit (m) waagerecht von der Achse"); ap.add_argument("--alle-kameras", action="store_true", help="auch K-Protokolle ohne Buendeltor (Altobjekte wie Martinstor)"); ap.add_argument("--aus"); a = ap.parse_args(argv)
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit", "spitze_hoehe"); os.makedirs(aus, exist_ok=True)
    achsen = [list(x) for x in (a.achse or [])]
    if a.elemente:
        for e in json.load(open(a.elemente)):
            sp = e.get("spitzen")
            if isinstance(sp, str): sp = json.loads(sp.replace("'", '"'))
            achsen += [list(map(float, s[:3])) for s in (sp or [])]
    if not achsen: raise SystemExit("keine Spitzenachsen (--achse oder Beleg masse.spitzen)")
    ray = None
    if a.stl:
        m_ = trimesh.load(a.stl); m_.apply_scale(obj.get("stl_massstab", 87) / 1000.0); nb, _ = nachbarn_netz(obj); sz = trimesh.util.concatenate([m_, nb]) if nb is not None else m_
        RI = trimesh.ray.ray_pyembree.RayMeshIntersector if hasattr(trimesh.ray, "ray_pyembree") else trimesh.ray.ray_triangle.RayMeshIntersector; ray = RI(sz)
    erg = []
    for i, (X, Y, Z0) in enumerate(achsen):
        ZS = np.arange(Z0, Z0 + a.hoehe_max, 0.05); P = np.stack([np.full_like(ZS, X), np.full_like(ZS, Y), ZS], 1); werte = []
        for kp in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
            K = json.load(open(kp)); kk = K.get("kamera", {})
            if not kk.get("rvec"): continue
            if not (kk.get("buendel_tor") or {}).get("ok") and not a.alle_kameras: continue
            nr = os.path.basename(kp)[2:-5]; pf = glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + "_*"))
            if not pf: continue
            im = cv2.imread(pf[0]); H, W = im.shape[:2]; R, t, f, _, _ = FF.kamera_laden(K, obj, nr, ROOT, W, H); tr = np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float)
            px, z = projizieren(P + tr, R, t, f, float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)), float(kk.get("k1") or 0.0))
            dbg = os.environ.get("SH_DEBUG")
            if (z <= 1).any():
                if dbg: print('   dbg', nr, 'hinter Kamera')
                continue
            sel = (px[:, 1] >= 2) & (px[:, 1] < H - 2); zs, px = ZS[sel], px[sel]                     # nur der Achsenteil im Bild (Spitze darf nahe am oberen Rand liegen; oben-Pruefung verlangt Himmel darueber)
            if len(zs) < 40 or zs[0] > Z0 + 0.5: continue
            ppm = abs(px[-1, 1] - px[0, 1]) / max(0.05, zs[-1] - zs[0])
            if dbg: print('   dbg', nr, 'ppm', round(float(ppm), 1), 'px', px[0].round(), px[-1].round(), W, H)
            if ppm < a.min_ppm or not (0 <= px[:, 0].min() and px[:, 0].max() < W and True): continue
            if abs(px[-1, 0] - px[0, 0]) > 0.3 * abs(px[-1, 1] - px[0, 1]): continue                     # Achse stark geneigt (Froschperspektive nah): Fenster quer ungenau
            if ray is not None:                                                                       # Sichtpruefung: Helm (1,5 m ueber Fuss) und Spitzenbereich vom Kamerazentrum frei (Sichtpruefung 2026-11-05: Spur lief sonst auf Kamin/Giebel davor)
                C0 = -np.asarray(R).T @ np.asarray(t, float).ravel() - tr; verdeckt = False
                for zz in (Z0 + 1.5, Z0 + 4.0):
                    Q = np.array([X, Y, zz]); v_ = Q - C0; dd = np.linalg.norm(v_); loc, _, _ = ray.intersects_location(C0[None], (v_ / dd)[None], multiple_hits=False)
                    if len(loc) and np.linalg.norm(loc[0] - C0) < dd - 1.5: verdeckt = True
                if verdeckt:
                    if dbg: print('   dbg', nr, 'verdeckt')
                    continue
            hm_p = os.path.join(od, "himmelsmaske", nr + ".png"); hm = cv2.imread(hm_p, cv2.IMREAD_GRAYSCALE) if os.path.exists(hm_p) else None
            if hm is not None and hm.shape != (H, W): hm = cv2.resize(hm, (W, H), interpolation=cv2.INTER_NEAREST)
            hb = max(6.0, a.fenster_m * ppm); fe = himmel_fenster(im, hm, float(np.median(px[:, 0])), px[0, 1], px[-1, 1], hb)
            if fe is None: continue
            kor, (xa, ya) = fe; xc = float(np.median(px[:, 0])) - xa
            v_von_z = lambda zz: float(np.interp(zz, zs, px[:, 1])) - ya; z_von_v = lambda vv: float(np.interp(-(vv + ya), -px[:, 1], zs))
            # Silhouette zeilenweise nach oben verfolgen: Start = Koerperlauf an der Achse 1-3 m ueber dem Fuss (Helmkoerper, breit), je Zeile die Laeufe,
            # die den vorigen Lauf beruehren; zu breit (> breit_m) = Hintergrund angeschlossen -> unsicher, abbrechen
            r0 = int(round(v_von_z(Z0 + 1.5)))
            if not (0 <= r0 < kor.shape[0]): continue
            row = kor[r0]; lauf = None
            for c in range(int(xc - 0.8 * ppm), int(xc + 0.8 * ppm) + 1):
                if 0 <= c < row.size and row[c]:
                    l_ = c; r_ = c
                    while l_ > 0 and row[l_ - 1]: l_ -= 1
                    while r_ < row.size - 1 and row[r_ + 1]: r_ += 1
                    lauf = (l_, r_); break
            if lauf is None: continue
            top_r, leer, gap, unsicher, breiten = r0, 0, max(2, int(a.luecke_m * ppm)), False, []
            l_, r_ = lauf
            for rr in range(r0 - 1, -1, -1):
                row = kor[rr]; lo, hi = max(0, l_ - 2), min(row.size - 1, r_ + 2)
                if not row[lo:hi + 1].any():
                    leer += 1
                    if leer > gap: break
                    continue
                cs = np.where(row[lo:hi + 1])[0] + lo; nl, nr_ = int(cs.min()), int(cs.max())
                while nl > 0 and row[nl - 1]: nl -= 1
                while nr_ < row.size - 1 and row[nr_ + 1]: nr_ += 1
                if (nr_ - nl + 1) > max(3 * ppm, 2.5 * (r_ - l_ + 1) + 4):                                 # schlagartig breiter: Hintergrund (Dach, Baum) angeschlossen
                    unsicher = True; break
                l_, r_, top_r, leer = nl, nr_, rr, 0; breiten.append((rr, nr_ - nl + 1))
            oben = kor[max(0, top_r - int(1.0 * ppm)): max(0, top_r - 2), max(0, l_ - int(ppm)): r_ + int(ppm)]
            ax_ = lambda rr: float(np.interp(-(rr + ya), -px[:, 1], px[:, 0])) - xa; drift = abs((0.5 * (l_ + r_) - ax_(top_r)) - (0.5 * (lauf[0] + lauf[1]) - ax_(r0))) / ppm                              # Spitze muss ueber dem Helmkoerper stehen (sonst Giebelstufe/Wolke gefolgt, Sichtpruefung 2026-11-05: 032/053/020)
            if dbg: print('   dbg', nr, 'unsicher', unsicher, 'drift', round(drift, 2), 'oben', oben.size and round(float(oben.mean()), 3))
            if unsicher or drift > 4.0 or oben.size == 0 or oben.mean() > 0.05: continue                             # ueber der Spitze kein freier Himmel: nicht messbar
            fest_r = top_r
            for rr_, w_ in reversed(breiten):                                                           # hoechste Zeile mit Koerperbreite >= 0,15 m (Knauf; darueber Stange/Fahne)
                if w_ >= 0.15 * ppm: fest_r = rr_; break
            h = z_von_v(top_r); h_fest = z_von_v(fest_r); top = int(np.argmin(np.abs(px[:, 1] - (top_r + ya))))
            C = -np.asarray(R).T @ np.asarray(t, float).ravel() - tr; dist = float(np.linalg.norm(C[:2] - np.array([X, Y])))
            h = float(zs[top]); el = float(np.degrees(np.arctan2(h - C[2], dist)))
            uns = float(0.5 / ppm + abs(np.tan(np.radians(el))) * a.achse_sigma)                         # Achsenfehler in Blickrichtung (sigma) wirkt ueber tan(Sichtwinkel) auf die Hoehe
            if uns > a.max_unsicherheit:
                print(f"  Spitze {i} Foto {nr}: {h:.2f} m verworfen (Sicht {el:+.0f} Grad, Unsicherheit {uns:.2f} m)", flush=True); continue
            uu, vv = (0.5 * (l_ + r_) + xa - float(kk.get("cx", W / 2))) / f, (top_r + ya - float(kk.get("cy", H / 2))) / f; u0_, v0_ = uu, vv; k1_ = float(kk.get("k1") or 0.0)
            for _ in range(5): r2_ = uu * uu + vv * vv; uu, vv = u0_ / (1 + k1_ * r2_), v0_ / (1 + k1_ * r2_)
            dr = np.array([uu, vv, 1.0]) @ np.asarray(R); dr /= np.linalg.norm(dr)
            werte.append(dict(strahl=[C.tolist(), dr.tolist()], foto=nr, spitze_z=round(h, 2), knauf_z=round(h_fest, 2), ppm=round(float(ppm), 1), abstand_m=round(dist, 1), sicht_grad=round(el, 1),
                              unsicherheit_m=round(uns, 2), px=[round(float(0.5 * (l_ + r_) + xa), 1), round(float(top_r + ya), 1)]))
            b = im[max(0, int(px[-1, 1]) - 20): int(px[0, 1]) + 20, max(0, int(px[0, 0] - 6 * hb)): int(px[0, 0] + 6 * hb)].copy()
            oy, ox = max(0, int(px[-1, 1]) - 20), max(0, int(px[0, 0] - 6 * hb))
            cv2.line(b, (int(px[0, 0]) - ox, int(px[0, 1]) - oy), (int(px[-1, 0]) - ox, int(px[-1, 1]) - oy), (255, 255, 0), 1)
            cv2.circle(b, (int(0.5 * (l_ + r_) + xa) - ox, int(top_r + ya) - oy), 6, (0, 0, 255), 2); cv2.circle(b, (int(0.5 * (l_ + r_) + xa) - ox, int(fest_r + ya) - oy), 6, (0, 255, 0), 2)
            if b.size: cv2.imwrite(os.path.join(aus, f"spitze{i}_{nr}.jpg"), b)
            print(f"  Spitze {i} Foto {nr}: {h:.2f} m, Knauf {h_fest:.2f} m (ppm {ppm:.0f}, Abstand {dist:.0f} m, Sicht {el:+.0f} Grad)", flush=True)
        r = dict(achse=[X, Y, Z0], werte=werte)
        if len(werte) >= 3:                                                                           # Spitzenpunkt TRIANGULIEREN (RANSAC ueber Strahlpaare): falsche Spuren (Giebelstufe, Kamin) treffen sich nicht im selben Punkt
            O = np.array([w["strahl"][0] for w in werte]); Dd = np.array([w["strahl"][1] for w in werte]); best = triangulieren(O, Dd, X, Y, Z0, a.tri_tol, a.tri_radius)
            schnitt = lambda ix: _schnitt(O, Dd, ix); abst = lambda X_: _abst(O, Dd, X_)
            if best is not None and best[1].sum() >= a.tri_min:
                X_ = schnitt(np.where(best[1])[0]); inl_ = abst(X_) < a.tri_tol; X_ = schnitt(np.where(inl_)[0]); d_ = abst(X_)
                for w, ok, dd_ in zip(werte, inl_, d_): w["tri_innen"] = bool(ok); w["tri_abstand_m"] = round(float(dd_), 3)
                r["triangulation"] = dict(punkt=[round(float(c), 3) for c in X_], n=int(inl_.sum()), n_fotos=len(werte), rms_m=round(float(np.sqrt((d_[inl_] ** 2).mean())), 3), fotos=[w["foto"] for w, ok in zip(werte, inl_) if ok])
                print(f"Spitze {i} triangul.: ({X_[0]:.2f}, {X_[1]:.2f}, {X_[2]:.2f}) aus {int(inl_.sum())}/{len(werte)} Fotos, RMS {r['triangulation']['rms_m']:.2f} m: {','.join(r['triangulation']['fotos'])}")
        if werte:
            v = np.array([w["spitze_z"] for w in werte]); md = float(np.median(v)); inl = np.abs(v - md) <= a.toleranz           # Ausreisser (Spur auf Giebelstufe/Wolke, Sichtpruefung 2026-11-05) einzeln ausweisen, nicht mitteln
            for w, ok in zip(werte, inl): w["innen"] = bool(ok)
            wid = bool(inl.sum() < 2 or inl.sum() < 0.5 * len(v))
            if not inl.any(): inl[:] = True
            r.update(median=round(float(np.median(v[inl])), 2), spanne=[round(float(v[inl].min()), 2), round(float(v[inl].max()), 2)], n=int(inl.sum()), n_aus=int((~inl).sum()),
                     widerspruch=wid)
            print(f"Spitze {i} ({X:.1f}, {Y:.1f}): Median {r['median']:.2f} m (Spanne {r['spanne'][0]:.2f}-{r['spanne'][1]:.2f}) aus {r['n']} Fotos, {r['n_aus']} Ausreisser{'  WIDERSPRUCH' if r['widerspruch'] else ''}")
        else: print(f"Spitze {i} ({X:.1f}, {Y:.1f}): kein Foto mit freiem Himmel ueber der Spitze")
        erg.append(r)
    json.dump(dict(spitzen=erg, parameter=vars(a)), open(os.path.join(aus, "spitze_hoehe.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
