#!/usr/bin/env python3
"""test_flaechen_gegen_netz.py - synthetischer BEWEIS (bekannte Wahrheit) fuer flaechen_gegen_netz.py. Gate vor dem Kaufhaus (Nutzerregel Beweis zuerst).
Szene (Meter): Wand 16 x 9 m, 4 Zonen, 4 Kameras (verschiedene Standorte), 'Foto' = Render der WAHREN Geometrie (glatte Wand + Kasten + Stufen) mit Zonenfarbe + Rauschen.
Getestetes Netz = wahre Geometrie, in Zone A/B Knoten zufaellig verschoben (Beulen 8 cm).
  A  Beulen, Foto einfarbig                   -> >= 70 % der beurteilten Dreiecke markiert   (der Fall der Nutzeridee)
  B  Beulen, Foto stark texturiert            -> <= 10 % markiert (Foto nicht einfarbig: keine Aussage)
  C  glatt, Foto einfarbig (+ echter Kasten)  -> <= 3 % markiert (inkl. Kasten, dessen Foto-Flaechen je einfarbig, Netz eben)
  D  echte Stufen (Geometrie), Foto je Stufe andere Farbe -> <= 5 % markiert
  Abbau: Abstand der freien Knoten in A zur wahren Ebene sinkt auf <= 30 %; Rand/Zone C/D unveraendert (max Verschiebung < 1 mm ausserhalb A)
  Gegenprobe A': gleiches Netz, Foto mit Fenster-Kontrast ueberall (kleine einfarbige Flaechen < a_min) -> A faellt ab (Gate sieht die Abhaengigkeit vom Foto)
  /media/oem/scan/venv-seg/bin/python -I tools/test_flaechen_gegen_netz.py   (Exit 0 = alle bestanden)"""
import sys, os, json, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flaechen_gegen_netz as FG, render_kern as RK

W, H, F_PX = 1600, 1000, 1800.0


def kamera(c, ziel):
    z = np.asarray(ziel, float) - c; z /= np.linalg.norm(z); x = np.cross(z, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(z, x)
    R = np.stack([x, y, z]); return dict(R=R, t=-R @ np.asarray(c, float), f=F_PX, cx=W / 2, cy=H / 2)


def szene(rng, beulen=0.08):
    """Wahre Wand (x -8..8, z 0..9, y = 0, Stufen in Zone D) als Gitter 0,25 m. Rueckgabe wahr, netz (beult), zone[F] (A..D, K=Kasten), farbe[F,3]."""
    xs = np.arange(-8, 8.001, 0.25); zs = np.arange(0, 9.001, 0.25); X, Z = np.meshgrid(xs, zs); nx = len(xs)
    Y = np.where(X >= 5, -0.3 * np.floor(Z / 1.5), 0.0)
    V = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1); idx = np.arange(len(V)).reshape(len(zs), nx)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
    Fc = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)]); Fc = Fc[:, ::-1]                      # Normalen zur Kamera (-y)
    cen = V[Fc].mean(1); zone = np.where(cen[:, 0] < -3, 0, np.where(cen[:, 0] < 0, 1, np.where(cen[:, 0] < 4.75, 2, 3)))
    farbe = np.zeros((len(Fc), 3), np.uint8)
    farbe[zone == 0] = (170, 175, 185); farbe[zone == 1] = (150, 170, 160); farbe[zone == 2] = (200, 190, 180)
    band = (np.floor(cen[:, 2] / 1.5)).astype(int); pal = np.array([(90, 120, 200), (200, 120, 90), (110, 200, 120), (60, 90, 90), (200, 200, 90), (150, 90, 170)], np.uint8)
    farbe[zone == 3] = pal[band[zone == 3] % len(pal)]
    riser = (zone == 3) & (cen[:, 2] - band * 1.5 > 1.25);
    farbe[riser] = np.stack([30 + 25 * band[riser]] * 3, 1).astype(np.uint8); farbe[(zone == 3) & (cen[:, 0] < 5.0)] = (30, 230, 230)                  # Steigung der Stufe = eigene Flaeche (eigene Farbe)
    wand = trimesh.Trimesh(V, Fc, process=False)
    kasten = trimesh.creation.box(extents=(1.5, 0.6, 1.0)); kasten.apply_translation((2.5, -0.3, 4.0))
    wahr = trimesh.util.concatenate([wand, kasten]); nF = len(wand.faces)
    zone = np.concatenate([zone, np.full(len(kasten.faces), 4)]); cols = np.array([(80, 80, 200), (200, 80, 80), (80, 200, 80), (200, 200, 80), (80, 200, 200), (200, 80, 200)], np.uint8)
    farbe = np.concatenate([farbe, cols[np.arange(len(kasten.faces)) // 2 % 6]])
    Vn = np.asarray(wahr.vertices).copy(); vz = np.zeros(len(Vn), int); vz[wand.faces[zone[:nF] <= 1].ravel()] = 1
    nur_wand = np.arange(len(Vn)) < len(V); bump = rng.normal(0, beulen, (len(Vn), 3)); bump[:, 0] *= 0.2; bump[:, 2] *= 0.2
    # nur Knoten, die ausschliesslich zu Zone A/B-Dreiecken gehoeren (Zonenrand zu C bleibt wahr)
    anz = np.bincount(wand.faces.ravel(), minlength=len(Vn)); az = np.bincount(wand.faces[zone[:nF] <= 1].ravel(), minlength=len(Vn)); innen = nur_wand & (anz == az) & (anz > 0)
    Vn[innen] += bump[innen]; netz = trimesh.Trimesh(Vn, wahr.faces, process=False)
    return wahr, netz, zone, farbe, innen


def foto(wahr, zone, farbe, kam, rng, kontrast=False, punkte=True):
    depth, fid, pos = RK.dreiecke_rastern(wahr, kam["R"], kam["t"], kam["f"], kam["cx"], kam["cy"], W, H)
    img = np.full((H, W, 3), 225, np.uint8); ok = fid >= 0; img[ok] = farbe[fid[ok]]
    img = img.astype(np.float32); z = zone[np.clip(fid, 0, None)]
    tex = cv2.resize(rng.normal(0, 30, (H // 4, W // 4, 1)).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)[..., None] if False else np.repeat(cv2.resize(rng.normal(0, 30, (H // 4, W // 4)).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)[..., None], 3, 2)
    m_ = ok & (z == 1); img[m_] += tex[m_]
    if kontrast:                                                                                              # Fensterraster ueberall: Flaechen < a_min
        yy, xx = np.mgrid[0:H, 0:W]; g = ((xx // 18 + yy // 18) % 2).astype(np.float32); img[ok] += (g[ok, None] * 60 - 30)
    if punkte:                                                                                                # schwarze Einzelpunkte/Loecher (1-3 px) mitten in den Flaechen = Rauschen (Nutzer 7.11.)
        n = int(0.004 * W * H); ys, xs = rng.integers(0, H, n), rng.integers(0, W, n)
        for y, x in zip(ys, xs): img[y:y + int(rng.integers(1, 4)), x:x + int(rng.integers(1, 4))] = 10
    img += rng.normal(0, 1.0, img.shape).astype(np.float32); return np.clip(img, 0, 255).astype(np.uint8)


def lauf(rng, kontrast=False, p=None):
    wahr, netz, zone, farbe, innen = szene(rng); p = dict(FG.STANDARD, **(p or {}))
    cams = [kamera((x0, -22.0, 3.0 + dz), (0.0, 0.0, 4.0)) for x0, dz in ((-9, 0), (-3, 1), (3, 0.5), (9, 1.5))]
    erg = [FG.foto_auswerten(netz, k, foto(wahr, zone, farbe, k, rng, kontrast), p, ausgabe=None) for k in cams]
    return wahr, netz, zone, innen, FG.abstimmen(erg, p, len(netz.faces)), erg, p


def main():
    rng = np.random.default_rng(1); ok_all = True; res = {}
    wahr, netz, zone, innen, ab, erg, p = lauf(rng)
    bel = ab["nfoto"] >= p["n_min"]; mk = ab["markiert"]
    def quote(z, alle=False): s = (zone == z) & (True if alle else bel); return float(mk[s].sum() / max(s.sum(), 1)), int(s.sum())   # B/K: Nenner = alle Dreiecke (Foto nicht einfarbig -> unbeurteilt, nie markiert)
    q = {n: quote(z, n in "BK") for n, z in zip("ABCDK", range(5))}; res["zonen"] = {k: dict(markiert=v[0], beurteilt=v[1]) for k, v in q.items()}
    for n, lim, op in (("A", 0.70, ">="), ("B", 0.10, "<="), ("C", 0.03, "<="), ("D", 0.05, "<="), ("K", 0.03, "<=")):
        ok = (q[n][0] >= lim) if op == ">=" else (q[n][0] <= lim); ok_all &= ok and q[n][1] > (5 if n == "K" else 20)
        print(f"Zone {n}: markiert {q[n][0]*100:5.1f} % von {q[n][1]} beurteilten Dreiecken (Soll {op} {lim*100:.0f} %) -> {'ok' if ok and q[n][1] > (5 if n == "K" else 20) else 'FEHLER'}")
    # Abbau
    V, frei = FG.abbauen(netz, ab, 10); Vn = np.asarray(netz.vertices); Vw = np.asarray(wahr.vertices)
    e0 = np.abs(Vn[innen, 1] - Vw[innen, 1]); fa = frei & innen; e1 = np.abs(V[fa, 1] - Vw[fa, 1]); e0f = np.abs(Vn[fa, 1] - Vw[fa, 1])
    rest = np.linalg.norm(V - Vn, axis=1)[~frei].max() if (~frei).any() else 0.0
    r = float(np.sqrt((e1 ** 2).mean()) / max(np.sqrt((e0f ** 2).mean()), 1e-9)) if fa.any() else 9.0
    print(f"Abbau: freie Knoten in A/B {int(fa.sum())} von {int(innen.sum())}; RMS-Abstand zur wahren Ebene vorher {np.sqrt((e0f**2).mean())*100:.2f} cm nachher {np.sqrt((e1**2).mean())*100:.2f} cm (Verhaeltnis {r:.2f}, Soll <= 0.30); Verschiebung nicht freier Knoten max {rest*1000:.3f} mm")
    # Zone B ist nicht markiert -> ihre Knoten sind NICHT frei; Verhaeltnis gilt fuer Zone-A-Knoten
    res["abbau"] = dict(frei=int(fa.sum()), verhaeltnis=r, rest_mm=float(rest * 1000)); ok_all &= (r <= 0.30) and fa.sum() > 100 and rest < 1e-9
    # Gegenprobe: kontrastreiches Foto -> A faellt ab
    wahr, netz, zone, innen, ab2, erg2, p = lauf(np.random.default_rng(1), kontrast=True); bel2 = ab2["nfoto"] >= p["n_min"]; sA = (zone == 0) & bel2
    qa = float(ab2["markiert"][sA].sum() / max(sA.sum(), 1)); print(f"Gegenprobe A' (Foto mit Kontrastraster): Zone A markiert {qa*100:.1f} % (muss < 30 %, ohne Kontrast {q['A'][0]*100:.0f} %)"); ok_all &= qa < 0.30
    res["gegenprobe_A"] = qa
    # Farbstreuung-Gate: ein raues, aber FOTO-GLEICHES Netz ohne Beulen (Zone C-Qualitaet ueberall) darf nirgends markieren
    # Wolkenvariante (3D, Region-Growing nach Farbe+Normale+Ebene): Punktwolke aus der WAHREN Geometrie (Farbe je Dreieck, Zone B zufaellig je Dreieck, 1 % schwarze Ausreisser)
    wahr, netz, zone, farbe, innen = szene(np.random.default_rng(1)); rg = np.random.default_rng(5)
    Pw, fi = trimesh.sample.sample_surface(wahr, 200000, seed=3); Pw = np.asarray(Pw); Cw = farbe[fi].astype(np.float32)
    bz = zone[fi] == 1; Cw[bz] += rg.uniform(-40, 40, (bz.sum(), 3)) * 0 + rg.uniform(-40, 40, (len(np.unique(fi)), 3))[np.searchsorted(np.unique(fi), fi[bz])]
    sch = rg.random(len(Pw)) < 0.01; Cw[sch] = 5; Cw = np.clip(Cw, 0, 255).astype(np.uint8)
    abw = FG.wolke_regionen(netz, Pw, Cw, p); mkw = abw["markiert"]; belw = abw["nfoto"] >= 1
    def qw(z, alle=False): s = (zone == z) & (True if alle else belw); return float(mkw[s].sum() / max(s.sum(), 1)), int(s.sum())
    for n, z, lim, op in (("A", 0, 0.70, ">="), ("B", 1, 0.10, "<="), ("C", 2, 0.03, "<="), ("D", 3, 0.05, "<="), ("K", 4, 0.03, "<=")):
        v, nn_ = qw(z, n in "BK"); ok = (v >= lim) if op == ">=" else (v <= lim); ok_all &= ok and nn_ > 5
        print(f"Wolke Zone {n}: markiert {v*100:5.1f} % von {nn_} (Soll {op} {lim*100:.0f} %) -> {'ok' if ok and nn_ > 5 else 'FEHLER'}"); res.setdefault("wolke", {})[n] = v
    Vw_, frei_w = FG.abbauen(netz, abw, 10); fw_ = frei_w & innen; r_w = float(np.sqrt(((Vw_[fw_, 1] - np.asarray(wahr.vertices)[fw_, 1]) ** 2).mean()) / max(np.sqrt(((np.asarray(netz.vertices)[fw_, 1] - np.asarray(wahr.vertices)[fw_, 1]) ** 2).mean()), 1e-9)) if fw_.any() else 9
    print(f"Wolke Abbau: freie Knoten {int(fw_.sum())}, Restabstand/Anfangsabstand {r_w:.2f} (Soll <= 0.30)"); ok_all &= r_w <= 0.30 and fw_.sum() > 100
    print("ALLE BESTANDEN" if ok_all else "FEHLGESCHLAGEN"); json.dump(res, open(os.path.join(os.environ.get("TEST_AUS", "/tmp"), "test_flaechen_gegen_netz.json"), "w"), indent=1); return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
