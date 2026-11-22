#!/usr/bin/env python3
"""dach_aus_fotos.py <objekt.json> [--teil N] [--voxel 0.15] [--rand 3.5] [--schreiben] [--neu] - DACH AUS DEN FOTOS: Hoehe und Umriss des Dachs aus der Himmelskante vieler Fotos.

Anlass 17.11.2026 (Kettenturm schwab_auto): das Dach kam nur aus DOM1/LoD2 (tools/dach_vermessen.py: Ebenenfit auf 1-m-Laserraster + Nadel "sqrt Pixel"). Das Umriss-Tor
meldete aus mehreren Fotos +5 m. KERNMETHODE: Form aus den Fotos mit den Messkameras, DOM1/LoD2 nur Gegenprobe.

Verfahren (Sichtkegel-Schnitt, allgemein fuer jedes Kettenobjekt mit dach.json und Messkameras messprotokoll/K-*.json):
  1. Kameras: alle K-*.json mit Foto; ohne sfm_guete 'schlecht', ohne 'tiefe_unsicher', nur plausible (kamera_plausibel). Verzeichnung k1 wird mitgerechnet.
  2. Je Foto Himmelsmaske (foto_pick.himmel, Cache audit/himmel_cache - derselbe wie beim Umriss-Tor). Fotos ohne plausible Maske fallen weg.
  3. Raumgitter (--voxel m) ueber Grundriss + --rand, von --unten m unter der LoD2-Wandoberkante bis ueber die erwartete Hoehe. Je Zelle und Foto: faellt die Zelle auf Himmel?
     Eine Zelle ist LUFT, wenn mindestens --min_fotos Fotos aus mindestens 2 Richtungen (20-Grad-Sektoren um das Gebaeude) dort Himmel sehen. Verdecker (Baum, Nachbar,
     Draht) machen in einzelnen Fotos nur 'kein Himmel' - sie koennen nichts wegschneiden und werden von den anderen Fotos ueberstimmt. Eine einzelne falsche Kamera
     kann allein nichts wegschneiden (Mehrheit). Uebrig bleibt die Sichthuelle; davon der Koerper ueber dem Grundriss.
  4. Hoehenprofil: je Hoehenschicht das Rechteck der Huelle in den Grundrissachsen (dach.json mitte_uv/achse_a) -> Stuetzstellen [z, a0, a1, b0, b1] (Douglas-Peucker).
     Daraus benannt: Traufe (breiteste Schicht), Knicke, First (Ende der Dachflaeche), Aufsatz (Laterne/Dachreiter/Nadel darueber). Die Profilform deckt Zelt, Walm,
     Sattel, Mansarde/Knick und Aufsaetze ab; Gauben, Giebelstufen und nicht rechteckige Daecher NICHT (-> 'belegt' false, wenn die Huelle kein Rechteck fuellt).
  5. Gegenprobe am Foto: Profilkoerper in jede Kamera rastern und gegen die Himmelskante vergleichen (wie umriss_tor) -> Median je Foto; 'belegt' nur, wenn genug Fotos
     aus genug Richtungen passen. DOM1/LoD2-Werte stehen daneben; Widerspruch wird GEMELDET (rc 3), nicht gemittelt.
Ausgabe: audit/dach_foto.json, audit/dach_foto.jpg (Profil + Fotos mit Kante - ANSEHEN); --schreiben traegt den Block 'foto' in dach.json des Teils ein (tools/dach_bauen.py
baut dann das Fotodach, wenn 'belegt'). rc 0 belegt und ohne Widerspruch, 2 nicht belegt (zu wenige Fotos/Richtungen, Huelle unbrauchbar), 3 belegt, aber Widerspruch zu DOM1/LoD2.
23.11.2026 (Kette 1122o): Fotos nur von zwei Seiten -> hinter dem Dach 'Sichtschatten' bis an den Gitterrand und ueber den First (First +4,4 m, Ueberstand 3,83 m,
Kerbe). Seitdem: Ausdehnung je Achse aus dem Schnitt durch die Grundrissmitte, Seite am Gitterrand = OFFEN (kein Beleg, Ersatz aus Gegenseite/anderer Achse),
Schichten ohne Mittelschnitt am Gitterrand = Schatten (kein Dach), Dachflaeche ohne Aufsatz nach oben nie breiter, Traufe = oberste gleich breite Schicht,
Gegenprobe ohne Kameras ueber der Traufe, abweichende Kameragruppe nach Form/Ausrichtung getrennt (gruppe_ursache: Meterfehler waechst mit der Entfernung?).
Grenzen: Sichthuelle >= wahrer Koerper (Einbuchtungen unsichtbar; mit wenigen Richtungen zu dick an den Ecken). Kameras nur vom Boden: die Dachflaeche selbst sieht nur,
wer seitlich an ihr entlang schaut. Massstab und Hoehenbezug kommen aus den Kameras - ist deren Ausrichtung falsch skaliert, ist es das Fotodach auch (deshalb die Meldung
gegen DOM1/LoD2 und tools/lage_gps_pruefen.py lesen).
"""
import sys, os, json, glob, argparse, time
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kamera_plausibel as KP

SEKTOR = 20.0                                  # Grad je Richtungssektor


def kameras_laden(od, fd, mitte3, log=print):
    """-> Liste dict(name, R, t, f, cx, cy, k1, W0, H0, C, foto, sektor). Nur brauchbare Messkameras mit Foto."""
    aus = []; weg = dict(schlecht=0, tiefe=0, unplausibel=0, ohne_foto=0)
    for kp in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        try: k = json.load(open(kp)).get("kamera")
        except Exception: continue
        if not isinstance(k, dict) or "rvec" not in k: continue
        if (k.get("sfm_guete") or {}).get("klasse") == "schlecht": weg["schlecht"] += 1; continue
        if k.get("tiefe_unsicher"): weg["tiefe"] += 1; continue
        if not KP.datei_pruefen(kp)[0]: weg["unplausibel"] += 1; continue
        nm = os.path.basename(kp)[2:-5]; pf = [p for p in glob.glob(os.path.join(fd, glob.escape(nm) + ".*")) if p.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png")]
        if not pf: weg["ohne_foto"] += 1; continue
        R = cv2.Rodrigues(np.array(k["rvec"], float))[0]; t = np.array(k["t"], float); C = -R.T @ t
        wh = k.get("bild") or [2 * k["cx"], 2 * k["cy"]]
        az = float(np.degrees(np.arctan2(C[1] - mitte3[1], C[0] - mitte3[0])) % 360.0)
        aus.append(dict(name=nm, R=R, t=t, f=float(k["f_px"]), cx=float(k["cx"]), cy=float(k["cy"]), k1=float(k.get("k1") or 0.0), W0=int(wh[0]), H0=int(wh[1]), C=C, foto=pf[0],
                        az=az, sektor=int(az // SEKTOR), abstand=float(np.hypot(C[0] - mitte3[0], C[1] - mitte3[1])), guete=(k.get("sfm_guete") or {}).get("klasse")))
    log(f"Kameras: {len(aus)} brauchbar (weg: {weg})")
    return aus


def himmel_laden(kam, cache_dir, nur_cache=False):
    """Himmelsmaske (bool, True = Himmel) in der Arbeitsgroesse (laengste Seite 1600 px) + Massstab s. None, wenn das Foto keine plausible Maske gibt.
    Cache wie umriss_tor (umriss_<foto>.png); Fehlschlag wird als <foto>.kein gemerkt (sonst jedes Mal 1,3 s je Foto)."""
    s = min(1.0, 1600.0 / max(kam["H0"], kam["W0"])); W, H = int(kam["W0"] * s), int(kam["H0"] * s)
    pc = os.path.join(cache_dir, f"umriss_{kam['name']}.png"); pk = os.path.join(cache_dir, f"{kam['name']}.kein")
    if os.path.exists(pk) and os.path.getmtime(pk) >= os.path.getmtime(kam["foto"]): return None, s
    if os.path.exists(pc) and os.path.getmtime(pc) >= os.path.getmtime(kam["foto"]):
        m = cv2.imread(pc, cv2.IMREAD_GRAYSCALE)
        if m is not None and m.shape == (H, W): return m > 127, s
    if nur_cache: return None, s
    import foto_pick as FP
    im = cv2.imread(kam["foto"])
    if im is None or im.shape[0] != kam["H0"] or im.shape[1] != kam["W0"]:
        if im is None: return None, s
        kam["skal_bild"] = (im.shape[1] / kam["W0"], im.shape[0] / kam["H0"])      # Foto in anderer Groesse als die Kamera: Maske in Kameragroesse rechnen
    ims = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA); os.makedirs(cache_dir, exist_ok=True)
    try: sk = FP.himmel(ims)
    except (Exception, SystemExit):
        open(pk, "w").write("keine plausible Himmelsmaske\n"); return None, s
    cv2.imwrite(pc, (sk * 255).astype(np.uint8)); return sk, s


def projizieren(P, kam, s, xp=np):
    """P (n,3) -> (u, v, z) in der Arbeitsgroesse, mit Verzeichnung k1 (x_v = x (1 + k1 r^2)). xp = numpy oder torch."""
    R = kam["R"] if xp is np else xp.as_tensor(kam["R"], dtype=P.dtype, device=P.device); t = kam["t"] if xp is np else xp.as_tensor(kam["t"], dtype=P.dtype, device=P.device)
    Xc = P @ R.T + t; z = Xc[:, 2]; zz = xp.where(z > 1e-6, z, xp.ones_like(z)); xn = Xc[:, 0] / zz; yn = Xc[:, 1] / zz; d = 1 + kam["k1"] * (xn * xn + yn * yn)
    return (kam["f"] * xn * d + kam["cx"]) * s, (kam["f"] * yn * d + kam["cy"]) * s, z


def huelle_schneiden(kams, gitter, cache_dir, min_fotos=2, kern_anteil=0.05, kern_tief=0.6, foto_fehler=0.01, log=print):
    """Sichtkegel-Schnitt auf dem Raumgitter. gitter = (us, vs, zs) Zellmitten. -> (koerper bool [nu, nv, nz], n_himmel, n_gesehen, benutzte Kameras, verworfene).
    Zwei Durchgaenge (Mehrheit ueber Fotos): 1. alle Fotos stimmen ab; KERN = Zellen, die fast kein Foto (< kern_anteil) als Himmel sieht, um kern_tief m nach innen
    geschrumpft. 2. Ein Foto, das im Kern Himmel sieht (> foto_fehler seiner Kernzellen), widerspricht der Mehrheit - falsche Kamera oder Himmelsmaske auf heller Wand
    (17.11.2026 Kettenturm: weisser Putz bei bedecktem Himmel) - und stimmt nicht mit. Danach ist eine Zelle LUFT, wenn min_fotos der uebrigen Fotos dort Himmel sehen."""
    import torch
    from scipy import ndimage as ndi
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    us, vs, zs = gitter; nu, nv, nz = len(us), len(vs), len(zs); dv = float(us[1] - us[0])
    G = torch.stack(torch.meshgrid(torch.as_tensor(us, dtype=torch.float32), torch.as_tensor(vs, dtype=torch.float32), torch.as_tensor(zs, dtype=torch.float32), indexing="ij"), -1).reshape(-1, 3).to(dev)
    ecken = np.array([[u, v, z] for u in (us[0], us[-1]) for v in (vs[0], vs[-1]) for z in (zs[0], zs[-1])]); bilder = []; t0 = time.time(); n_ohne = 0
    for kam in kams:
        s = min(1.0, 1600.0 / max(kam["H0"], kam["W0"])); W, H = int(kam["W0"] * s), int(kam["H0"] * s)
        u, v, z = projizieren(ecken, kam, s)
        if (z < 0.5).any() or u.max() < 0 or u.min() > W or v.max() < 0 or v.min() > H: continue           # Gitter nicht (ganz vor der Kamera) im Bild
        sk, s = himmel_laden(kam, cache_dir)
        if sk is None: n_ohne += 1; continue
        bilder.append((kam, s, cv2.morphologyEx(sk.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))))   # Himmelsfetzen in Fenstern/hellen Flaechen weg

    def stimme(kam, s, sk):
        H, W = sk.shape; skt = torch.as_tensor(sk, device=dev).bool(); u, v, z = projizieren(G, kam, s, torch); ui = u.round().long(); vi = v.round().long()
        im_bild = (z > 0.5) & (ui >= 2) & (ui < W - 2) & (vi >= 2) & (vi < H - 2)
        hi = torch.zeros(len(G), dtype=torch.bool, device=dev); hi[im_bild] = skt[vi[im_bild], ui[im_bild]]
        return im_bild, hi

    n_h = torch.zeros(len(G), dtype=torch.int16, device=dev); n_s = torch.zeros(len(G), dtype=torch.int16, device=dev); bl = []
    for kam, s, sk in bilder:
        im_bild, hi = stimme(kam, s, sk)
        if int(im_bild.sum()) < 0.02 * len(G): continue
        n_s += im_bild.to(torch.int16); n_h += hi.to(torch.int16); bl.append((kam, s, sk))
    f3 = lambda x: x.reshape(nu, nv, nz).cpu().numpy()
    kern = f3((n_s >= max(5, min_fotos + 2)) & (n_h.float() < kern_anteil * n_s.float()))
    kern = ndi.binary_erosion(kern, iterations=max(1, int(round(kern_tief / dv))))
    kt = torch.as_tensor(kern.reshape(-1), device=dev); benutzt = []; verworfen = []
    n_h.zero_(); n_s.zero_()
    for kam, s, sk in bl:
        im_bild, hi = stimme(kam, s, sk); nk = int((im_bild & kt).sum()); fe = float((hi & kt).sum()) / max(nk, 1)
        kam["kern_fehler"] = round(fe, 4)
        if kern.any() and nk > 50 and fe > foto_fehler: verworfen.append(kam); continue
        n_s += im_bild.to(torch.int16); n_h += hi.to(torch.int16); benutzt.append(kam)
    luft = n_h >= min_fotos
    log(f"Sichtkegel: {len(benutzt)} Fotos stimmen ab, {len(verworfen)} widersprechen der Mehrheit (Himmel im Kern), {n_ohne} ohne plausible Himmelsmaske; "
        f"{len(G)} Zellen, Kern {int(kern.sum())}, {time.time() - t0:.0f} s; Luft {float(luft.float().mean()) * 100:.0f} %")
    return ~f3(luft), f3(n_h), f3(n_s), benutzt, verworfen


def kante_im_foto(P, kam, s, sk, punkt_m):
    """Punktmenge P (Oberflaeche eines Koerpers, Punktabstand punkt_m) in die Kamera, Oberkante je Bildspalte gegen die Himmelskante des Fotos (wie umriss_tor).
    -> dict(n Spalten, med = Median der Abweichung in m mit Vorzeichen (+ = Foto hoeher), mad = Median |Abweichung|, ym, yf, gueltig) oder None."""
    H, W = sk.shape; u, v, z = projizieren(P, kam, s); ok = (z > 0.5) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
    if ok.sum() < 50: return None
    m = np.zeros((H, W), np.uint8); m[v[ok].astype(int), u[ok].astype(int)] = 1; zm = float(np.median(z[ok])); r = int(np.clip(np.ceil(1.5 * punkt_m * kam["f"] * s / zm), 1, 25))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))).astype(bool)
    sk = cv2.morphologyEx(sk.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))               # Fahrdraehte/duenne Stangen (< 9 px) sind keine Dachkante (17.11.2026: Draht ueber dem Turm gab +2,4 m)
    hat = m.any(0); ym = np.where(hat, m.argmax(0), -1); frei = np.cumprod(sk, axis=0).astype(bool); yf = frei.sum(0)
    g = hat & (yf > 3) & (ym > 3) & (yf < H - 2)
    if g.sum() < 20: return None
    dm = (ym - yf) * zm / (kam["f"] * s)
    return dict(n=int(g.sum()), med=float(np.median(dm[g])), mad=float(np.median(np.abs(dm[g]))), ym=ym, yf=yf, gueltig=g, dm=dm)


def _ausdehnung(X, m, dv):
    """Ausdehnung [lo, hi] der Zellen m entlang X (Einzelzellen = Rauschen zaehlen nicht: je Bin >= 3 Zellen). -> (lo, hi) oder None."""
    if m.sum() < 4: return None
    h, kanten = np.histogram(X[m], bins=np.arange(X.min() - dv, X.max() + 2 * dv, dv)); gut = np.where(h >= 3)[0]
    return (float(kanten[gut[0]]), float(kanten[gut[-1] + 1])) if len(gut) else None


def profil_aus_huelle(K, gitter, c, ea, ha, hb, band_zellen=3, rand_zellen=2):
    """Je Hoehenschicht das Rechteck der Huelle in den Grundrissachsen.
    -> (ext [nz, 4] = a0, a1, b0, b1 (m, relativ zur Mitte; nan = leer), flaeche [nz], Koerpermaske, offen [nz, 4] bool, info dict).

    23.11.2026 (Kette 1122o, Befund First +4,4 m / Kerbe Achse b): Fotos gab es nur von zwei Seiten (Nord fern, West nah). Hinter dem Turm (von den Kameras aus)
    sieht KEIN Foto Himmel - die Huelle laeuft dort als 'Sichtschatten' bis an den Gitterrand (b+ 9,71 = Gitterrand 9,88, 'Ueberstand' 3,83 m) und ragt hinter
    dem Dach bis 49,9 m auf; die obersten Schichten (47-49,9 m) lagen ganz NEBEN der Turmachse (b 1..9,7). Darum:
      - Ausdehnung je Achse nur im SCHNITT durch die Grundrissmitte (Band +-band_zellen um die andere Achse): Schattenzellen weit hinter dem Dach
        verbreitern die Querachse nicht mehr (Schatten in Hoehe z ist so breit wie das Dach tiefer unten).
      - Seite, deren Huelle an den Gitterrand stoesst = OFFEN (nicht gemessen, kein Foto begrenzt sie) -> offen[k, s].
      - Schicht, deren Schnitt durch die Mitte leer ist: nur dann (als Aufsatz neben der Mitte) behalten, wenn sie nirgends an den Gitterrand stoesst - sonst ist
        sie Sichtschatten, kein Dach; darueber wird nichts mehr gezaehlt."""
    from scipy import ndimage as ndi
    us, vs, zs = gitter; dv = float(us[1] - us[0]); eb = np.array([-ea[1], ea[0]])
    UU, VV = np.meshgrid(us, vs, indexing="ij"); A = (UU - c[0]) * ea[0] + (VV - c[1]) * ea[1]; B = (UU - c[0]) * eb[0] + (VV - c[1]) * eb[1]
    nu, nv = UU.shape; rand = np.zeros((nu, nv), bool); r_ = max(1, int(rand_zellen))
    rand[:r_] = rand[-r_:] = True; rand[:, :r_] = rand[:, -r_:] = True
    lab, n = ndi.label(K, np.ones((3, 3, 3)))                               # auch ueber Ecken verbunden (duenne Aufsaetze haengen sonst nicht am Dach)
    if n == 0: return None, None, None, None, None
    innen = (np.abs(A) < ha) & (np.abs(B) < hb); ix = np.arange(1, n + 1); zahl = ndi.sum(np.broadcast_to(innen[:, :, None], K.shape), lab, index=ix); gr = ndi.sum(K, lab, index=ix)
    behalten = 1 + np.where((ix == 1 + int(np.argmax(zahl))) | ((gr >= 100) & (zahl >= 0.9 * gr)))[0]      # Hauptkoerper + frei schwebende Stuecke ganz ueber dem Grundriss (offene Laterne: Himmel scheint zwischen den Stuetzen durch, der Helm darueber haengt in der Huelle nicht am Dach)
    K = np.isin(lab, behalten)
    ext = np.full((len(zs), 4), np.nan); fl = np.zeros(len(zs)); offen = np.zeros((len(zs), 4), bool)
    band = max(1, int(band_zellen)) * dv + 0.5 * dv; schnitt_a = np.abs(B) <= band; schnitt_b = np.abs(A) <= band
    seite_n = np.stack([-A, A, -B, B], -1)                                  # Richtung jeder Zelle nach a-, a+, b-, b+
    info = dict(schatten_ab_z=None, neben_mitte=[], offen_schichten=0)
    for k in range(len(zs)):
        m = K[:, :, k]
        if m.sum() < 4: continue
        am_rand = m & rand
        if am_rand.any():                                                   # Seite(n), auf der die Huelle den Gitterrand erreicht: dort begrenzt kein Foto den Koerper
            s_ = np.argmax(seite_n[am_rand], 1); offen[k, np.unique(s_)] = True
        ea_ = _ausdehnung(A, m & schnitt_a, dv); eb_ = _ausdehnung(B, m & schnitt_b, dv)
        if ea_ is None or eb_ is None:                                      # Schnitt durch die Mitte leer
            if am_rand.any():
                if info["schatten_ab_z"] is None: info["schatten_ab_z"] = round(float(zs[k]), 2)
                offen[k] = True; continue                                   # Sichtschatten hinter dem Dach - kein Koerper
            ea_ = ea_ or _ausdehnung(A, m, dv); eb_ = eb_ or _ausdehnung(B, m, dv)
            if ea_ is None or eb_ is None: continue
            info["neben_mitte"].append(round(float(zs[k]), 2))
        if info["schatten_ab_z"] is not None and zs[k] > info["schatten_ab_z"]: offen[k] = True; continue      # ueber dem Schatten haengt nichts mehr am Dach
        ext[k] = [ea_[0], ea_[1], eb_[0], eb_[1]]
        w = [(ea_[1] - ea_[0]) if not offen[k, 0:2].any() else 2 * min(abs(ea_[j]) for j in (0, 1) if not offen[k, j]) if not offen[k, 0:2].all() else np.nan,
             (eb_[1] - eb_[0]) if not offen[k, 2:4].any() else 2 * min(abs(eb_[j]) for j in (0, 1) if not offen[k, 2 + j]) if not offen[k, 2:4].all() else np.nan]
        fl[k] = w[0] * w[1] if np.isfinite(w).all() else 0.0             # Flaeche ohne offene Seite (dort die Gegenseite) - eine offene Seite macht keine Schicht 'breiteste'
    info["offen_schichten"] = int(offen.any(1).sum())
    return ext, fl, K, offen, info


def seiten_belege(ext, zs, kams, cache_dir, c, ea, dv, log=print):
    """Je Schicht und Seite (a-, a+, b-, b+): wie viele Fotos sehen dicht ausserhalb der Huelle Himmel UND schauen dabei an dieser Seite ENTLANG (quer zur Seitennormalen,
    +-30 Grad)? Nur solche Fotos legen die Lage der Seite fest. Fotos, die auf die Seite zu schauen, begrenzen sie nur schraeg von oben/unten (Huelle dort zu dick:
    17.11.2026 Laterne des Kettenturms in Nord-Sued-Richtung 7 m statt 1,8 m, weil kein Foto von Ost/West sie sieht)."""
    eb = np.array([-ea[1], ea[0]]); nz = len(zs); P = []; idx = []
    for k in range(nz):
        if not np.isfinite(ext[k]).all(): continue
        a0, a1, b0, b1 = ext[k]
        for s_, (fest, achse) in enumerate(((a0 - 2 * dv, 0), (a1 + 2 * dv, 0), (b0 - 2 * dv, 1), (b1 + 2 * dv, 1))):
            lauf = np.linspace(b0, b1, 7) if achse == 0 else np.linspace(a0, a1, 7)
            for q in lauf:
                a_, b_ = (fest, q) if achse == 0 else (q, fest); P.append([c[0] + a_ * ea[0] + b_ * eb[0], c[1] + a_ * ea[1] + b_ * eb[1], zs[k]]); idx.append((k, s_))
    bel = np.zeros((nz, 4), int)
    if not P: return bel
    P = np.array(P); idx = np.array(idx)
    for kam in kams:
        sk, s = himmel_laden(kam, cache_dir, nur_cache=True)
        if sk is None: continue
        H, W = sk.shape; u, v, z = projizieren(P, kam, s); ok = (z > 0.5) & (u >= 2) & (u < W - 2) & (v >= 2) & (v < H - 2); hi = np.zeros(len(P), bool); hi[ok] = sk[v[ok].astype(int), u[ok].astype(int)]
        d = c - kam["C"][:2]; d = d / max(np.linalg.norm(d), 1e-9); entlang = [abs(d @ ea) <= 0.5, abs(d @ ea) <= 0.5, abs(d @ eb) <= 0.5, abs(d @ eb) <= 0.5]
        tr = np.zeros((nz, 4), int); np.add.at(tr, (idx[:, 0], idx[:, 1]), hi.astype(int))
        bel += (tr >= 3) & np.array(entlang)[None, :]
    return bel


def _dp(z, Y, tol):
    """Douglas-Peucker ueber mehrere Kanaele Y [n, m] entlang z: Indizes der Stuetzstellen."""
    halten = {0, len(z) - 1}; stapel = [(0, len(z) - 1)]
    while stapel:
        i, j = stapel.pop()
        if j - i < 2: continue
        t = ((z[i + 1:j] - z[i]) / (z[j] - z[i]))[:, None]; ab = np.abs(Y[i + 1:j] - (Y[i] + t * (Y[j] - Y[i]))).max(1); k = int(np.argmax(ab))
        if ab[k] > tol: halten.add(i + 1 + k); stapel += [(i, i + 1 + k), (i + 1 + k, j)]
    return sorted(halten)


def dach_aus_profil(ext, fl, bel, zs, teil, dv, traufe_dicke=0.3, tol=0.12, luecke_max=3.0, einpassen=None, offen=None, log=print):
    """Huellprofil -> Dachparameter + Stuetzstellen. Regeln (jede nicht gemessene Groesse steht in 'annahmen'):
      Traufe   = breiteste Schicht der Huelle im Suchband um die LoD2-Wandoberkante (-3 .. +6 m; LoD2 hier nur Suchhilfe).
      Seiten   = Huellkante, wo >= 2 Fotos an der Seite entlang Himmel sehen; sonst gespiegelt von der Gegenseite, sonst im Verhaeltnis der anderen Achse - nie weiter als die Huelle.
      Dachflaeche zwischen Traufe und Aufsatzfuss = gerade Verbindung, wo die Huelle nicht schmaler ist (vom Boden sieht man die Dachflaeche nicht; die Huelle ist dort nur Obergrenze).
      Aufsatzfuss = unterste Hoehe, ab der die Breite <= 30 % der Traufbreite bleibt; Aufsatz, wenn der Koerper mehr als 1 m ueber die verlaengerte Dachflaeche hinausragt.
    -> dict oder (None, grund)."""
    zw = float(teil.get("wand_oberkante_lod2") or zs[0] + 8); ha, hb = float(teil["halb_a"]), float(teil["halb_b"]); nz = len(zs)
    band = np.where((zs >= zw - 3) & (zs <= zw + 6) & np.isfinite(ext).all(1))[0]
    if len(band) < 5: return None, "Huelle im Traufband leer"
    km = int(band[np.argmax(fl[band])]); toleranz = 2.0 * dv * 2.0 * np.sqrt(max(fl[km], 0.0))       # je Seite eine Zelle Rasterung (2 dv je Achse, Flaeche ~ 2 dv (wa + wb), wa + wb ~ 2 sqrt(F)): gleich breite Schichten -> die OBERSTE ist die Traufe (die Huelle laeuft unter dem Ueberstand schraeg aus)
    ke = km
    while ke + 1 <= band[-1] and fl[ke + 1] >= fl[km] - toleranz: ke += 1
    if ke == band[0]: return None, f"Huelle wird nach unten immer breiter (keine Traufe im Band {zw - 3:.1f}..{zw + 6:.1f} m gefunden) - Nachbarn/Verdecker oder zu wenige Fotos"
    voll = np.where(np.isfinite(ext).all(1))[0]; kt = ke; ann = []; dv_ = float(zs[1] - zs[0])
    for k in voll[voll > ke]:
        if (k - kt) * dv_ > luecke_max: break                               # groessere Luecke: darueber haengt nichts mehr am Koerper
        if k - kt > 3: ann.append(f"ANNAHME: zwischen {zs[kt]:.1f} und {zs[k]:.1f} m scheint der Himmel durch (offene Laterne/Stuetzen?) - als geschlossener Koerper gebaut, Breite zwischen den Schichten darunter und darueber gerade verbunden")
        kt = int(k)
    if kt - ke < 4: return None, "ueber der Traufe kein Koerper (Flachdach oder Dach nicht gegen den Himmel gesehen)"
    ks = np.arange(ke, kt + 1); z = zs[ks]; E = ext[ks].copy(); B = bel[ks] >= 2; da = np.isfinite(E).all(1)
    for j in range(4): E[:, j] = np.interp(z, z[da], E[da, j])
    B[~da] = False
    roh = E.copy(); verh = ha / hb; O = (offen[ks] if offen is not None else np.zeros_like(B)) & ~B
    # Seiten ohne Beleg: Gegenseite spiegeln, sonst andere Achse im Verhaeltnis des Grundrisses, nie ueber die Huelle hinaus.
    # OFFENE Seite (Huelle am Gitterrand, 1122o b+ 'Ueberstand' 3,83 m): die Huelle ist dort keine Grenze -> ohne Beleg Gegenseite bzw. andere Achse aus der
    # (nicht offenen) Huelle; bleibt nichts, wird zwischen den Nachbarschichten gerade verbunden - nie der Gitterrand.
    ersatz = np.zeros(4, int); unbestimmt = np.zeros_like(B)
    for k in range(len(ks)):
        for s_ in range(4):
            if B[k, s_]: continue
            geg = s_ ^ 1; vz = -1.0 if s_ % 2 == 0 else 1.0; andere_j = (2, 3) if s_ < 2 else (0, 1); fv = verh if s_ < 2 else 1.0 / verh
            if B[k, geg]: wert = abs(roh[k, geg])
            elif any(B[k, j] for j in andere_j): wert = float(np.mean([abs(roh[k, j]) for j in andere_j if B[k, j]])) * fv
            elif O[k, s_] and not O[k, geg]: wert = abs(roh[k, geg])
            elif O[k, s_] and any(not O[k, j] for j in andere_j): wert = float(np.mean([abs(roh[k, j]) for j in andere_j if not O[k, j]])) * fv
            elif O[k, s_]: unbestimmt[k, s_] = True; continue
            else: continue
            if O[k, s_]: E[k, s_] = vz * wert; ersatz[s_] += 1; continue          # offene Seite: Huelle ist keine Obergrenze
            wert = min(wert, abs(roh[k, s_]) if roh[k, s_] * vz > 0.3 else max(abs(roh[k, s_]), abs(roh[k, geg])))      # nie ueber die Huelle hinaus; liegt die Huellschicht ganz auf der anderen Seite der Mitte (duenne schiefe Schicht), gilt ihre weitere Seite
            if abs(wert - abs(roh[k, s_])) > 1e-6 or roh[k, s_] * vz < 0: E[k, s_] = vz * wert; ersatz[s_] += 1
    for s_ in range(4):                                                      # offen ohne jeden Ersatz: zwischen bestimmten Schichten gerade verbinden
        u_ = unbestimmt[:, s_]
        if u_.any():
            if u_.all(): return None, f"Seite {('a-', 'a+', 'b-', 'b+')[s_]} in allen Dachschichten offen (kein Foto begrenzt sie, keine Gegenseite) - Dach nicht bestimmbar"
            E[u_, s_] = np.interp(z[u_], z[~u_], E[~u_, s_]); ersatz[s_] += int(u_.sum())
    ohne = ~B.any(1)
    if ohne.mean() > 0.5: return None, f"{ohne.mean() * 100:.0f} % der Dachschichten hat an keiner Seite ein Foto, das an ihr entlang Himmel sieht"
    ant = B.mean(0); achse_bel = [max(ant[0], ant[1]) >= 0.5, max(ant[2], ant[3]) >= 0.5]
    for s_, nm in enumerate(("a-", "a+", "b-", "b+")):
        if ersatz[s_]: ann.append(f"ANNAHME: Seite {nm} in {ersatz[s_]} von {len(ks)} Schichten ({ersatz[s_] * dv:.1f} m Hoehe) ohne Foto, das an ihr entlang schaut - Lage von der Gegenseite gespiegelt bzw. aus der anderen Achse im Grundrissverhaeltnis, begrenzt durch die Sichthuelle")
    # Aufsatzfuss je Achse, Dachflaeche als Gerade
    br = np.c_[E[:, 1] - E[:, 0], E[:, 3] - E[:, 2]]; kf = []
    for j in (0, 1):
        klein = br[:, j] <= 0.3 * br[0, j]; k_ = len(ks) - 1
        while k_ > 0 and klein[k_]: k_ -= 1
        kf.append(min(k_ + 1, len(ks) - 1) if klein[-1] else len(ks) - 1)
    dick = 0.0
    for j in (0, 1):
        if kf[j] < 2: continue
        t = ((z[:kf[j] + 1] - z[0]) / (z[kf[j]] - z[0]))
        for s_ in (2 * j, 2 * j + 1):
            ger = E[0, s_] + t * (E[kf[j], s_] - E[0, s_]); alt = E[:kf[j] + 1, s_].copy()
            E[:kf[j] + 1, s_] = np.where(np.abs(ger) < np.abs(alt), ger, alt); dick = max(dick, float(np.max(np.abs(alt) - np.abs(E[:kf[j] + 1, s_]))))
    if dick > tol: ann.append(f"ANNAHME: Dachflaeche zwischen Traufe und Aufsatzfuss/First GERADE (vom Boden nicht einsehbar; die Sichthuelle ist dort bis {dick:.1f} m dicker und nur Obergrenze) - Knick/Schweifung nur, wo die Huelle schmaler ist als die Gerade")
    br = np.c_[E[:, 1] - E[:, 0], E[:, 3] - E[:, 2]]; jb = int(np.argmax([ant[0] + ant[1], ant[2] + ant[3]]))          # besser belegte Achse fuer die benannten Groessen
    kff = kf[jb]; einzug = None
    if einpassen is not None and kff >= 8:
        achsen = [j for j in (0, 1) if kf[j] == kff or abs(kf[j] - kff) <= 3]                                         # nur Achsen, in denen das Dach bis zum Aufsatzfuss zulaeuft (ein Sattel-First bleibt lang)
        einzug, text = einpassen(z, E, kff, achsen)
        if einzug is not None:
            for j in achsen: E[:kff + 1, 2 * j] += einzug; E[:kff + 1, 2 * j + 1] -= einzug
            ann = [x for x in ann if "GERADE" not in x] + [text]; br = np.c_[E[:, 1] - E[:, 0], E[:, 3] - E[:, 2]]
    kff = kf[jb]; steig = (z[kff] - z[0]) / max(0.5 * (br[0, jb] - br[kff, jb]), 1e-3); z_spitz = z[kff] + steig * 0.5 * br[kff, jb]
    aufsatz = bool(z[-1] > z_spitz + 1.0 and kff < len(ks) - 1); z_first = float(z[kff]) if aufsatz else float(z[-1])
    if aufsatz and kff < 3: return None, "Koerper ueber der Traufe ist nur ein schmaler Aufsatz (keine Dachflaeche gefunden)"
    # Dachflaeche ohne Aufsatz wird nach oben nie breiter (23.11.2026, 1122o: Zacken/Kerbe an der Spitze aus Huellrauschen + Ersatzseiten); mit Aufsatz nur bis zum
    # Aufsatzfuss - darueber darf er auskragen (Laternenkrempe, Zwiebel)
    bis = len(ks) if not aufsatz else kff + 1; vz4 = np.array([-1.0, 1.0, -1.0, 1.0])
    for s_ in range(4):
        w_ = np.maximum(vz4[s_] * E[:bis, s_], 0.0); E[:bis, s_] = vz4[s_] * np.minimum.accumulate(w_)
    # Stuetzstellen
    ix = _dp(z, E, tol); kn = [[round(float(z[0] - traufe_dicke), 2)] + [round(float(x), 2) for x in E[0]]] + [[round(float(z[i]), 2)] + [round(float(x), 2) for x in E[i]] for i in ix]
    kn[-1][0] = round(float(z[-1] + 0.5 * dv), 2)
    for q in kn:                                                             # entartete Ringe vermeiden
        if q[2] - q[1] < 0.1: m_ = 0.5 * (q[1] + q[2]); q[1], q[2] = round(m_ - 0.05, 2), round(m_ + 0.05, 2)
        if q[4] - q[3] < 0.1: m_ = 0.5 * (q[3] + q[4]); q[3], q[4] = round(m_ - 0.05, 2), round(m_ + 0.05, 2)
    ann.append(f"ANNAHME: Traufstaerke {traufe_dicke:.1f} m (Unterseite des Dachueberstands nicht messbar: die Huelle laeuft unter der Traufe schraeg aus)")
    ann.append("ANNAHME: Querschnitt je Hoehe ein Rechteck in den Grundrissachsen (Laterne/runde Aufsaetze, Gauben, Grate werden zum Rechteck)")
    knick = [round(float(z[i]), 2) for i in ix if 0 < i < kff and (einzug is not None or abs((E[i] - roh[i])).max() < 1e-6)]
    return dict(traufe_z=round(float(z[0]), 2), traufe_breite_a=round(float(br[0, 0]), 2), traufe_breite_b=round(float(br[0, 1]), 2),
                ueberstand_m=dict(zip(("a-", "a+", "b-", "b+"), [round(float(x), 2) for x in (-E[0, 0] - ha, E[0, 1] - ha, -E[0, 2] - hb, E[0, 3] - hb)])),
                first_z=round(z_first, 2), neigung_grad=[round(float(np.degrees(np.arctan2(z[kf[j]] - z[0], max(0.5 * (br[0, j] - br[kf[j], j]), 1e-3)))), 1) for j in (0, 1)],
                knicke_z=knick, aufsatz=(dict(fuss_z=round(float(z[kff]), 2), oben_z=round(float(z[-1] + 0.5 * dv), 2), breite_a=round(float(np.median(br[kff:, 0])), 2), breite_b=round(float(np.median(br[kff:, 1])), 2)) if aufsatz else None),
                hoechster_punkt_z=round(float(z[-1] + 0.5 * dv), 2), seiten_belegt_anteil=dict(zip(("a-", "a+", "b-", "b+"), [round(float(x), 2) for x in ant])), achse_belegt=dict(a=bool(achse_bel[0]), b=bool(achse_bel[1])),
                profil=kn, annahmen=ann), None


def einpasser(kams, cache_dir, c, ea, max_fotos=40, stufen=np.arange(0.0, 2.41, 0.15), log=print):
    """-> Funktion einpassen(z, E, kff, achsen): Dachflaeche zwischen Traufe und Aufsatzfuss an die Himmelskante der Fotos anpassen (Schweifung/Knick).
    Die Sichthuelle taugt dafuer nicht (Kameras am Boden schneiden ueber der Traufe nur schraeg). Darum Vergleich im Bild: Einzug der Dachflaeche nach innen an 4 Hoehen
    (20/40/60/80 % der Dachhoehe, dazwischen gerade, an Traufe und Aufsatzfuss 0), je Hoehe der Wert mit der kleinsten mittleren Abweichung Dachkante - Himmelskante
    ueber die Fotos (zwei Durchgaenge). Benutzt werden die Fotos mit der groessten Entfernung (nur sie sehen die Dachflaeche), hoechstens max_fotos.
    Uebernommen wird das Ergebnis nur, wenn es die Abweichung um mehr als 10 % und 3 cm senkt; sonst bleibt die Gerade (ANNAHME)."""
    def einpassen(z, E, kff, achsen):
        def profil(d4):
            F = E.copy(); t = (z[:kff + 1] - z[0]) / (z[kff] - z[0]); d = np.interp(t, [0, 0.2, 0.4, 0.6, 0.8, 1.0], [0] + list(d4) + [0])
            for j in achsen:
                gr = 0.5 * ((E[:kff + 1, 2 * j + 1] - E[:kff + 1, 2 * j]) - (E[kff, 2 * j + 1] - E[kff, 2 * j])); dd = np.minimum(d, np.maximum(gr, 0.0)); F[:kff + 1, 2 * j] += dd; F[:kff + 1, 2 * j + 1] -= dd
            return [[z[i]] + list(F[i]) for i in range(0, len(z), 2)] + [[z[-1]] + list(F[-1])], d
        bilder = []
        P0 = profil_punkte(profil([0, 0, 0, 0])[0], c, ea, 0.2)
        for kam in sorted(kams, key=lambda k: -k["abstand"]):
            if float(kam["C"][2]) >= z[0]: continue                          # Kamera ueber der Traufe: Dach vor Stadt/Hang, nicht vor dem Himmel
            sk, s = himmel_laden(kam, cache_dir, nur_cache=True)
            if sk is None: continue
            sk = cv2.morphologyEx(sk.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool); r = kante_im_foto(P0, kam, s, sk, 0.2)
            if r is None or r["n"] < 150 or r["mad"] > 1.5: continue
            bilder.append((kam, s, sk))
            if len(bilder) >= max_fotos: break
        if len(bilder) < 3: return None, None
        def fehler(d4, je_foto=False):
            P = profil_punkte(profil(d4)[0], c, ea, 0.2); w = []
            for kam, s, sk in bilder:
                r = kante_im_foto(P, kam, s, sk, 0.2); w.append(float(np.mean(np.minimum(np.abs(r["dm"][r["gueltig"]]), 2.0))) if r is not None else 2.0)
            return np.array(w) if je_foto else float(np.median(w))           # Median ueber die Fotos: die Mehrheit entscheidet, eine Gruppe falsch stehender Kameras zieht nicht mit
        def suchen(d4):
            fb = fehler(d4)
            for i in range(4):
                for v in stufen:
                    if v == d4[i]: continue
                    q = list(d4); q[i] = float(v); f = fehler(q)
                    if f < fb - 1e-4: fb, d4 = f, q
            return d4
        d4 = suchen([0.0, 0.0, 0.0, 0.0]); w = fehler(d4, True); gut = w <= max(0.5, 2.0 * float(np.median(w))); n_alle = len(bilder)
        if gut.sum() >= 3: bilder = [b_ for b_, g_ in zip(bilder, gut) if g_]   # Fotos, die auch zum eingepassten Dach nicht passen (andere Kameragruppe, Verdecker), entscheiden die Feinform nicht
        f0 = fehler([0.0, 0.0, 0.0, 0.0]); d4 = suchen(d4); fb = fehler(d4)
        sekt = sorted({k["sektor"] for k, _, _ in bilder})
        log(f"Dachflaeche einpassen: {len(bilder)} von {n_alle} Fotos (Sektoren {sekt}), mittlere Abweichung gerade {f0:.2f} m -> eingepasst {fb:.2f} m, Einzug bei 20/40/60/80 % der Dachhoehe {d4} m")
        if fb > 0.9 * f0 or f0 - fb < 0.03: return None, None
        quer = {0: "b", 1: "a"}
        text = (f"Dachflaeche geschweift/geknickt AUS FOTOS: Einzug {d4} m bei 20/40/60/80 % der Dachhoehe (mittlere Abweichung zur Himmelskante {f0:.2f} -> {fb:.2f} m, {len(bilder)} Fotos, Sektoren {sekt}); "
                "ANNAHME: in beiden Achsen gleich (die Fotos zeigen nur das Profil quer zur Blickrichtung)")
        return profil(d4)[1], text
    return einpassen


def profil_punkte(profil, c, ea, schritt=0.12):
    """Oberflaechenpunkte des Profilkoerpers (Ringe zwischen den Stuetzstellen) im Rahmen - fuer die Gegenprobe am Foto."""
    eb = np.array([-ea[1], ea[0]]); P = []; q = np.array(profil, float)
    for i in range(len(q) - 1):
        n = max(2, int(np.ceil((q[i + 1, 0] - q[i, 0]) / schritt)) + 1)
        for t in np.linspace(0, 1, n):
            z, a0, a1, b0, b1 = q[i] + t * (q[i + 1] - q[i]); na = max(2, int((a1 - a0) / schritt) + 1); nb = max(2, int((b1 - b0) / schritt) + 1)
            aa = np.r_[np.linspace(a0, a1, na), np.linspace(a0, a1, na), np.full(nb, a0), np.full(nb, a1)]; bb = np.r_[np.full(na, b0), np.full(na, b1), np.linspace(b0, b1, nb), np.linspace(b0, b1, nb)]
            P.append(np.c_[c[0] + aa * ea[0] + bb * eb[0], c[1] + aa * ea[1] + bb * eb[1], np.full(len(aa), z)])
    z, a0, a1, b0, b1 = q[-1]; aa, bb = np.meshgrid(np.arange(a0, a1 + schritt, schritt), np.arange(b0, b1 + schritt, schritt)); aa, bb = aa.ravel(), bb.ravel()
    P.append(np.c_[c[0] + aa * ea[0] + bb * eb[0], c[1] + aa * ea[1] + bb * eb[1], np.full(len(aa), z)])
    return np.vstack(P)


def gegenprobe(P, kams, cache_dir, punkt_m, grenze=0.5, min_spalten=40, z_kamera_max=None):
    """Profilkoerper gegen die Himmelskante jedes Fotos. -> Liste dict(foto, n, med, mad, sektor, abstand, passt).
    z_kamera_max (Traufhoehe): Kameras darueber (Schlossberg, Nachbarturm) sehen das Dach VON OBEN vor Stadt/Hang, nicht vor dem Himmel - ihre Himmelskante ist
    nicht die Dachkante (1122o: 15 Fotos aus 323 m, Kamerahoehe 61 m, 'Abweichung' +20..+98 m) -> nicht beurteilbar, zaehlen nicht."""
    aus = []
    for kam in kams:
        if z_kamera_max is not None and float(kam["C"][2]) >= z_kamera_max: continue
        sk, s = himmel_laden(kam, cache_dir, nur_cache=True)
        if sk is None: continue
        sk = cv2.morphologyEx(sk.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool); r = kante_im_foto(P, kam, s, sk, punkt_m)
        if r is None or r["n"] < min_spalten: continue
        aus.append(dict(foto=kam["name"], n=r["n"], med=round(r["med"], 2), mad=round(r["mad"], 2), sektor=kam["sektor"], abstand=round(kam["abstand"], 1), passt=bool(r["mad"] <= grenze)))
    return aus


def gruppe_ursache(meds, abstaende, min_fotos=3, min_verhaeltnis=2.0):
    """Abweichende Kameragruppe: Form oder Ausrichtung? Eine falsch stehende/gedrehte Kamera hat einen WINKELfehler -> die Abweichung in Metern waechst mit der
    Entfernung (proportional). Ein Formfehler des Dachs ist in Metern fuer nahe und ferne Fotos gleich. Die Gruppe wird am Median der Entfernung geteilt; liegt das
    Verhaeltnis der Abweichungen (fern/nah) naeher an 1 als am Entfernungsverhaeltnis (geometrische Mitte sqrt(r)), ist es Form, sonst Ausrichtung.
    Unterscheidbar erst, wenn die fernen Fotos >= min_verhaeltnis mal so weit weg sind wie die nahen (sonst 'offen').
    1122o: 48 Fotos 300-360 Grad, -1,40 m von 34 bis 139 m Entfernung gleich -> Form (Sichtschatten hinter dem Turm), nicht Teil-/Seitenverwechslung.
    -> dict(urteil 'form'|'ausrichtung'|'offen', verhaeltnis_abstand, verhaeltnis_abweichung, text) oder None (zu wenige Fotos)."""
    m = np.abs(np.asarray(meds, float)); a = np.asarray(abstaende, float)
    if len(m) < 2 * min_fotos: return None
    nah = a <= np.median(a); fern = ~nah
    if nah.sum() < min_fotos or fern.sum() < min_fotos: return None
    an, af = float(np.median(a[nah])), float(np.median(a[fern])); mn, mf = float(np.median(m[nah])), float(np.median(m[fern]))
    rd = af / max(an, 1e-6); re = mf / max(mn, 1e-6)
    urteil = "offen" if rd < min_verhaeltnis else ("form" if re <= np.sqrt(rd) else "ausrichtung")
    return dict(urteil=urteil, verhaeltnis_abstand=round(rd, 2), verhaeltnis_abweichung=round(re, 2),
                text=f"nah {mn:.2f} m bei {an:.0f} m, fern {mf:.2f} m bei {af:.0f} m Entfernung")


def bild_schreiben(pfad, erg, ext, zs, teil, kams, cache_dir, P, c, ea):
    """Kontrollbild: links Profil (Huelle roh, Fotodach, DOM1-Dach) je Achse, rechts bis zu 3 Fotos verschiedener Richtung mit Dachkante (gruen) und Himmelskante (rot)."""
    hoehe = 900; z0, z1 = erg["profil"][0][0] - 3, erg["hoechster_punkt_z"] + 1.5; ms = hoehe / (z1 - z0); bw = int(18 * ms); teile = []
    q = np.array(erg["profil"]); b = teil.get("beste") or {}
    for j, nm in ((0, "Achse a"), (1, "Achse b")):
        im = np.full((hoehe, bw, 3), 255, np.uint8); X = lambda a_: int(bw / 2 + a_ * ms); Y = lambda z_: int((z1 - z_) * ms)
        for zz in np.arange(np.ceil(z0), z1, 1.0): cv2.line(im, (0, Y(zz)), (bw, Y(zz)), (225, 225, 225), 1); cv2.putText(im, f"{zz:.0f}", (2, Y(zz) - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 120, 120), 1)
        for k in range(len(zs)):
            if np.isfinite(ext[k]).all() and z0 < zs[k] < z1: cv2.line(im, (X(ext[k, 2 * j]), Y(zs[k])), (X(ext[k, 2 * j + 1]), Y(zs[k])), (200, 200, 200), 1)
        pts = np.array([[X(r[1 + 2 * j]), Y(r[0])] for r in q] + [[X(r[2 + 2 * j]), Y(r[0])] for r in q[::-1]], np.int32); cv2.polylines(im, [pts], True, (40, 160, 40), 2)
        if b.get("first") is not None and b.get("steigung"):
            h_ = float(teil["halb_a"] if j == 0 else teil["halb_b"]); zf = float(b["first"]); k_ = float(b["steigung"]); fh = float(b.get("first_halblaenge") or 0.0) if j == 0 else 0.0
            cv2.polylines(im, [np.array([[X(-h_), Y(zf - k_ * (h_ - fh))], [X(-fh), Y(zf)], [X(fh), Y(zf)], [X(h_), Y(zf - k_ * (h_ - fh))]], np.int32)], False, (200, 80, 40), 1)
        if teil.get("wand_oberkante_lod2"): cv2.line(im, (X(-8), Y(teil["wand_oberkante_lod2"])), (X(8), Y(teil["wand_oberkante_lod2"])), (200, 80, 40), 1)
        cv2.putText(im, nm + ": grau Sichthuelle, gruen Fotodach, blau DOM1/LoD2", (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1); teile.append(im)
    gp = sorted([g for g in erg.get("gegenprobe", []) if g["n"] >= 80], key=lambda g: (not g["passt"], -g["n"])); wahl = []; sekt = set()
    for g in gp:
        if g["sektor"] // 3 not in sekt: wahl.append(g); sekt.add(g["sektor"] // 3)
        if len(wahl) == 3: break
    for g in wahl:
        kam = next(k for k in kams if k["name"] == g["foto"]); sk, s = himmel_laden(kam, cache_dir, nur_cache=True); sko = cv2.morphologyEx(sk.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
        r = kante_im_foto(P, kam, s, sko, 0.12); im = cv2.resize(cv2.imread(kam["foto"]), sk.shape[::-1]); cs = np.where(r["gueltig"])[0]
        for cc in cs: cv2.circle(im, (int(cc), int(r["ym"][cc])), 2, (60, 220, 60), -1); cv2.circle(im, (int(cc), int(r["yf"][cc])), 1, (40, 40, 240), -1)
        x0, x1 = max(0, cs.min() - 150), min(im.shape[1], cs.max() + 150); y0, y1 = max(0, int(min(r["ym"][cs].min(), r["yf"][cs].min())) - 80), min(im.shape[0], int(r["ym"][cs].max()) + 200)
        aus = im[y0:y1, x0:x1]; aus = cv2.resize(aus, (max(1, int(aus.shape[1] * hoehe / aus.shape[0])), hoehe)); aus = aus[:, :900]
        cv2.putText(aus, f"{g['foto'][-28:]}  Median {g['med']:+.2f} m, |.| {g['mad']:.2f} m", (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2); teile.append(aus)
    cv2.imwrite(pfad, np.hstack(teile), [cv2.IMWRITE_JPEG_QUALITY, 85])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("objekt"); ap.add_argument("--teil", type=int, default=None, help="Teil aus dach.json (Standard: groesste Grundflaeche)"); ap.add_argument("--voxel", type=float, default=0.15)
    ap.add_argument("--rand", type=float, default=3.5, help="m um den Grundriss (Dachueberstand)"); ap.add_argument("--unten", type=float, default=8.0, help="m unter der LoD2-Wandoberkante beginnen")
    ap.add_argument("--min_fotos", type=int, default=2); ap.add_argument("--grenze", type=float, default=0.5, help="m: Foto 'passt', wenn Median |Dachkante - Himmelskante| darunter")
    ap.add_argument("--schreiben", action="store_true", help="Block 'foto' in dach.json eintragen (nur wenn belegt; sonst wird ein vorhandener Block entfernt)")
    a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"])
    au = os.path.join(root, obj.get("audit", os.path.join(od, "audit"))); os.makedirs(au, exist_ok=True); cache = os.path.join(au, "himmel_cache"); dp = os.path.join(od, "dach.json")
    if not os.path.exists(dp) or not json.load(open(dp)).get("teile"): print("KEIN dach.json mit Teilen (erst tools/dach_vermessen.py) - nichts gerechnet"); return 2
    dj = json.load(open(dp)); t = next((x for x in dj["teile"] if x["teil"] == a.teil), None) if a.teil is not None else max(dj["teile"], key=lambda x: x["flaeche_m2"])
    if t is None: print(f"Teil {a.teil} nicht in dach.json"); return 2
    g = np.array(t["grundriss_uv"], float); c = np.array(t["mitte_uv"], float); ea = np.array(t["achse_a"], float); ea /= np.linalg.norm(ea); zw = float(t.get("wand_oberkante_lod2") or t["dom1_p95"])
    zo = max(float(obj.get("hoehe_m") or 0), float(t["dom1_max"]), float((t.get("beste") or {}).get("first") or 0)) * 1.2 + 3.0
    gitter = (np.arange(g[:, 0].min() - a.rand, g[:, 0].max() + a.rand, a.voxel), np.arange(g[:, 1].min() - a.rand, g[:, 1].max() + a.rand, a.voxel), np.arange(max(zw - a.unten, 0.5), zo, a.voxel))
    erg = dict(werkzeug="dach_aus_fotos.py", quelle="foto", datum=time.strftime("%Y-%m-%d %H:%M"), teil=t["teil"], belegt=False, voxel_m=a.voxel)
    def ende(rc, grund=None):
        if grund: erg["grund"] = grund; print("NICHT BELEGT:", grund)
        json.dump(erg, open(os.path.join(au, "dach_foto.json"), "w"), indent=1, ensure_ascii=False)
        if a.schreiben:
            alt = t.pop("foto", None)
            if erg["belegt"]: t["foto"] = {k: v for k, v in erg.items() if k != "gegenprobe"}
            if erg["belegt"] or alt is not None:
                __import__("json_sicher").schreiben(dp, dj); print("dach.json: Block 'foto' " + ("eingetragen" if erg["belegt"] else "ENTFERNT (nicht mehr belegt)") + f" (Teil {t['teil']})")
        return rc
    kams = kameras_laden(od, fd, [c[0], c[1], zw])
    if len(kams) < 5: return ende(2, f"nur {len(kams)} brauchbare Messkameras")
    K, n_h, n_s, ben, verw = huelle_schneiden(kams, gitter, cache, a.min_fotos)
    erg.update(fotos_abgestimmt=len(ben), fotos_widerspruch=len(verw), sektoren=sorted({k["sektor"] for k in ben}))
    if len(ben) < 5 or len(erg["sektoren"]) < 2: return ende(2, f"{len(ben)} Fotos aus {len(erg['sektoren'])} Richtungssektoren sehen das Dach gegen den Himmel - zu wenig fuer einen Sichtkegel-Schnitt")
    ext, fl, Kk, offen, hinfo = profil_aus_huelle(K, gitter, c, ea, float(t["halb_a"]), float(t["halb_b"]))
    if ext is None: return ende(2, "Sichthuelle leer")
    for j in range(4): ext[:, j] = __import__("scipy.ndimage", fromlist=["x"]).median_filter(np.where(np.isfinite(ext[:, j]), ext[:, j], 0.0), 5, mode="nearest") + np.where(np.isfinite(ext[:, j]), 0.0, np.nan)
    bel = seiten_belege(ext, gitter[2], ben, cache, c, ea, a.voxel)
    bel[offen] = 0                                                           # Seite am Gitterrand: Himmel jenseits des Gitters ist kein Beleg fuer die Lage der Seite
    erg["huelle_offen"] = dict(zip(("a-", "a+", "b-", "b+"), [round(float(x), 2) for x in offen.mean(0)])); erg["huelle_schatten_ab_z"] = hinfo["schatten_ab_z"]
    if hinfo["schatten_ab_z"] is not None or offen.any():
        print(f"Sichthuelle OFFEN (an den Gitterrand, kein Foto begrenzt sie) je Seite Anteil der Schichten {erg['huelle_offen']}; Sichtschatten ohne Schnitt durch die Mitte ab z {hinfo['schatten_ab_z']} m (nicht als Dach gezaehlt)")
    d, grund = dach_aus_profil(ext, fl, bel, gitter[2], t, a.voxel, einpassen=einpasser(ben, cache, c, ea), offen=offen)
    if d is None: return ende(2, grund)
    erg.update(d); erg.update(mitte_uv=t["mitte_uv"], achse_a=t["achse_a"])
    P = profil_punkte(d["profil"], c, ea); gp = gegenprobe(P, ben, cache, 0.12, a.grenze, z_kamera_max=d["traufe_z"]); erg["gegenprobe"] = gp
    passt = [x for x in gp if x["passt"]]; sp = sorted({x["sektor"] for x in passt}); mads = [x["mad"] for x in gp]
    erg["gegenprobe_kurz"] = dict(fotos=len(gp), passt=len(passt), sektoren_passt=sp, median_abweichung_m=(round(float(np.median(mads)), 2) if mads else None), grenze_m=a.grenze)
    # Vergleich mit DOM1/LoD2: melden, nicht mitteln
    b = t.get("beste") or {}; wid = []; vgl = dict(lod2_wandoberkante=round(zw, 2), dom1_first=(round(float(b["first"]), 2) if b.get("first") is not None else None), dom1_max=round(float(t["dom1_max"]), 2), dom1_form=b.get("form"), objekt_hoehe_m=obj.get("hoehe_m"))
    if abs(d["traufe_z"] - zw) > 1.0: wid.append(f"Traufe Foto {d['traufe_z']:.2f} m gegen LoD2-Wandoberkante {zw:.2f} m ({d['traufe_z'] - zw:+.2f} m, Faktor {d['traufe_z'] / zw:.3f})")
    if b.get("first") is not None and abs(d["first_z"] - float(b["first"])) > 1.0: wid.append(f"First/Dachende Foto {d['first_z']:.2f} m gegen DOM1-Ebenenfit {float(b['first']):.2f} m ({d['first_z'] - float(b['first']):+.2f} m, Faktor {d['first_z'] / float(b['first']):.3f})")
    if d["hoechster_punkt_z"] < float(t["dom1_max"]) - 1.0: wid.append(f"hoechster Punkt Foto {d['hoechster_punkt_z']:.2f} m UNTER DOM1-Maximum {float(t['dom1_max']):.2f} m (Laser sieht etwas, das die Fotos nicht gegen den Himmel zeigen)")
    if d["hoechster_punkt_z"] > float(t["dom1_max"]) + 1.0: vgl["hinweis_spitze"] = f"hoechster Punkt Foto {d['hoechster_punkt_z']:.2f} m ueber DOM1-Maximum {float(t['dom1_max']):.2f} m (+{d['hoechster_punkt_z'] - float(t['dom1_max']):.2f} m) - DOM1 ist blind fuer Nadeln/Knaeufe, fuer sich kein Widerspruch"
    if len([w for w in wid if "Faktor 1." in w]) >= 2: wid.append("Traufe UND First liegen in den Fotos hoeher als im Laser: das spricht fuer einen Massstabs-/Hoehenfehler der Kamera-Ausrichtung (tools/lage_gps_pruefen.py, LoD2-Sockelumring als Wandebene?), nicht nur fuer eine andere Dachform")
    erg["vergleich_dom1_lod2"] = vgl; erg["widerspruch"] = wid
    breit = [x for x in gp if x["n"] >= 150]                                 # Fotos, die viel Dachkante zeigen (schmale Ausschnitte/Fernfotos mit Vordergrund entscheiden nicht)
    erg["gegenprobe_kurz"].update(fotos_breit=len(breit), passt_breit=sum(x["passt"] for x in breit))
    erg["belegt"] = bool(len(passt) >= 3 and len(sp) >= 2 and len(breit) >= 3 and sum(x["passt"] for x in breit) > 0.5 * len(breit))      # Mehrheit der Fotos mit viel Dachkante
    gruppen = {}                                                             # Fotos, die NICHT passen, nach Blickrichtung: eine einige Gruppe = Kameras dieser Richtung stehen anders als die Mehrheit
    for x in breit:
        if not x["passt"] and abs(x["med"]) < 5.0: gruppen.setdefault(x["sektor"] // 3, []).append((x["med"], x["abstand"]))
    erg["kameragruppen_abweichend"] = []
    for q, v in sorted(gruppen.items()):
        me = [m_ for m_, _ in v]
        if len(v) < 3 or (np.sign(me) == np.sign(np.median(me))).mean() < 0.8: continue
        ur = gruppe_ursache(me, [a_ for _, a_ in v])
        erg["kameragruppen_abweichend"].append(dict(richtung_grad=[q * 60, q * 60 + 60], fotos=len(v), median_m=round(float(np.median(me)), 2), ursache=ur))
    for q in erg["kameragruppen_abweichend"]:
        ur = q["ursache"] or {}
        if ur.get("urteil") == "form":
            wid.append(f"Kameras aus Richtung {q['richtung_grad'][0]}-{q['richtung_grad'][1]} Grad ({q['fotos']} Fotos) sehen die Dachkante im Median {q['median_m']:+.2f} m anders - die Abweichung "
                       f"waechst NICHT mit der Entfernung ({ur['text']}): FORMFEHLER des Fotodachs auf der von ihnen gesehenen Seite, keine falsch stehende Kameragruppe")
        else:
            wid.append(f"Kameras aus Richtung {q['richtung_grad'][0]}-{q['richtung_grad'][1]} Grad ({q['fotos']} Fotos) sehen die Dachkante im Median {q['median_m']:+.2f} m anders als die Mehrheit"
                       + (f" ({ur['text']})" if ur.get("text") else "")
                       + (" - Fehler waechst mit der Entfernung: Ausrichtung dieser Kameras pruefen (nicht gemittelt)" if ur.get("urteil") == "ausrichtung" else
                          " - Form oder Ausrichtung NICHT trennbar (Entfernungen zu aehnlich oder zu wenige Fotos); Kontrollbild ansehen (Fahrdraht/Laterne in der Himmelskante?)"))
    print(f"Fotodach Teil {t['teil']}: Traufe {d['traufe_z']:.2f} m ({d['traufe_breite_a']:.2f} x {d['traufe_breite_b']:.2f} m), First/Dachende {d['first_z']:.2f} m, Neigung a/b {d['neigung_grad'][0]:.0f}/{d['neigung_grad'][1]:.0f} Grad, "
          + (f"Aufsatz {d['aufsatz']['fuss_z']:.2f}..{d['aufsatz']['oben_z']:.2f} m ({d['aufsatz']['breite_a']:.1f} x {d['aufsatz']['breite_b']:.1f} m)" if d["aufsatz"] else "kein Aufsatz") + f", hoechster Punkt {d['hoechster_punkt_z']:.2f} m, {len(d['profil'])} Stuetzstellen")
    print(f"Seiten belegt (Anteil der Schichten): {d['seiten_belegt_anteil']}")
    print(f"Gegenprobe: {len(passt)} von {len(gp)} Fotos passen (<= {a.grenze} m) aus Sektoren {sp}; Median der Abweichung {erg['gegenprobe_kurz']['median_abweichung_m']} m; mit >= 150 Spalten Dachkante: {erg['gegenprobe_kurz']['passt_breit']} von {len(breit)}")
    print(f"DOM1/LoD2 daneben: {vgl}")
    for x in d["annahmen"]: print("  " + x)
    for x in wid: print("  WIDERSPRUCH: " + x)
    try: bild_schreiben(os.path.join(au, "dach_foto.jpg"), erg, ext, gitter[2], t, ben, cache, P, c, ea); print("->", os.path.join(au, "dach_foto.jpg"), "(ANSEHEN)")
    except Exception as e: print("Kontrollbild nicht geschrieben:", repr(e)[:200])
    if not erg["belegt"]: return ende(2, f"Gegenprobe: nur {len(passt)} von {len(gp)} Fotos aus {len(sp)} Sektoren passen ({erg['gegenprobe_kurz']['passt_breit']} von {len(breit)} mit >= 150 Spalten Dachkante; verlangt >= 3 Fotos, >= 2 Sektoren, Mehrheit) - Fotodach wird NICHT benutzt")
    return ende(3 if wid else 0)


if __name__ == "__main__":
    sys.exit(main())
