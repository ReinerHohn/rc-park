#!/usr/bin/env python3
"""uhren_wandbild.py - Turmuhren aus dem Wandbild finden und vermessen (21.11.2026, Kettenstufe 'bauplan').

Anlass (Kettenluecke 9, modelle/KETTE_LUECKEN_2026-11-20.md): die Uhr gab es nur im Hand-Generator (schwab_v3_gen Z.141-146, martinstor_v4), der Erkenner kannte keine Klasse dafuer.
Ablauf je Fassade:
  1. ZONE = Erkennerkasten der Klasse 'uhr' (tools/fassade_parsing.py, OWLv2 "a clock"/"a clock face") mit >= --stimmen Stimmen und >= 40 % der Fotos, die die Stelle sehen.
     Der Kasten ist nur Suchfenster (KERNMETHODE: Erkennen = Zone, Gestalt aus dem Wandbild).
  2. MASS = Kreis im feinen Wandbild (fassade_fein, 1 cm): Kantenbild, Kreis-Hough in der Zone (Radius 0,35-0,65 x Kastengroesse); Aussenkreis = Kreis mit der
     staerksten Kantenstuetze; Innenkreis (Ziffernring innen) = staerkster konzentrischer Kreis mit 0,45-0,85 x Aussenradius (Mitte < 6 % R daneben), sonst keiner.
     Stuetze = Anteil der Kreispunkte mit Kante in 2 cm; Tor >= --min_stuetze, sonst verworfen (Name der Ursache im JSON).
  3. BELEG (23.11.2026, 1122p: Heiligenschein im Wandgemaelde als Uhr gebaut) = 12er-Teilung (Ziffern/Striche) im Ring 0,55-0,97 R, zifferblatt_beleg();
     ohne Beleg verworfen. Konzentrische Kreise derselben Stelle (Aussenrand + Ziffernring) -> eine Uhr (dubletten_zusammenfassen).
Aufruf:  uhren_wandbild.py <objekt.json> <fassade_fein-ordner> --elemente <fassade/elemente.json> [--aus audit/uhren_auto.json]
Ausgabe: {fid: {o, d, n, uhren: [{u, z, d_aussen, d_innen, stuetze_aussen, stuetze_innen, kasten, quelle}], verworfen: [...]}} + Bild <aus>.jpg
rc 0 = mindestens eine Uhr, rc 3 = keine.
"""
import sys, os, json, argparse, numpy as np, cv2


def stuetze(kanten, cx, cy, r, tol=2):
    t = np.linspace(0, 2 * np.pi, max(60, int(2 * np.pi * r / 2)), endpoint=False); x = np.round(cx + r * np.cos(t)).astype(int); y = np.round(cy + r * np.sin(t)).astype(int)
    H, W = kanten.shape; ok = (x >= tol) & (x < W - tol) & (y >= tol) & (y < H - tol)
    if ok.mean() < 0.8: return 0.0
    k = cv2.dilate(kanten, np.ones((2 * tol + 1, 2 * tol + 1), np.uint8)); return float((k[y[ok], x[ok]] > 0).mean())


def zifferblatt_beleg(g, cx, cy, r, f0=0.55, f1=0.97, min_r=25, min_verh=1.2):
    """ZIFFERBLATT-BELEG (23.11.2026, 1122p: goldener Heiligenschein im Wandgemaelde f01 als Uhr gebaut). Ein beliebiger Kreis ist keine Uhr:
    Ziffern/Stundenstriche sitzen in 12er-Teilung im Ring f0..f1 x r. Winkelprofil (mittlere Helligkeit je Winkel im Ring, 720 Winkel) ohne langsamen
    Verlauf (gleitendes Mittel ueber 45 Grad weg: Schlagschatten ueber der halben Scheibe), Fourier-Betrag je Periodenzahl k = 6..60.
    Beleg = staerkste Periode ist ein Vielfaches von 12 (12 Stunden, 60 Minutenstriche) und >= min_verh x staerkste Nicht-12er-Periode.
    Schwabentor 1122p (feines Wandbild): Uhr f00 2,87, Uhr f01 (halb im Schatten) 1,63; Heiligenschein 0,64 (staerkste k=2-11), Innenring-Dublette 0,25.
    g = Grauwertbild, cx/cy/r in Pixeln. Rueckgabe dict(ok, k, verh, grund)."""
    if r < min_r: return dict(ok=False, k=None, verh=0.0, grund=f"Scheibe nur {r:.0f} px Radius im Wandbild (< {min_r}), 12er-Teilung nicht pruefbar")
    na, nr = 720, 24; t = np.linspace(0, 2 * np.pi, na, endpoint=False); rr = np.linspace(f0, f1, nr) * r
    X = (cx + np.outer(rr, np.cos(t))).astype(np.float32); Y = (cy - np.outer(rr, np.sin(t))).astype(np.float32)
    q = cv2.remap(g.astype(np.float32), X, Y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).mean(0)
    w = na // 8; q = q - np.convolve(np.r_[q[-w:], q, q[:w]], np.ones(w) / w, "same")[w:-w]
    A = np.abs(np.fft.rfft(q)); ks = np.arange(6, 61); a_ = A[ks]; zw = ks % 12 == 0
    k_max = int(ks[np.argmax(a_)]); verh = float(a_[zw].max() / max(a_[~zw].max(), 1e-9))
    ok = k_max % 12 == 0 and verh >= min_verh
    return dict(ok=bool(ok), k=k_max, verh=round(verh, 2), grund="" if ok else f"kein Zifferblatt: 12er-Teilung im Ring nur {verh:.2f} x staerkste Fremdperiode (staerkste Periode k={k_max}, Tor >= {min_verh} und k=12/24/../60)")


def dubletten_zusammenfassen(uhren, tol=0.25):
    """Konzentrische Kreise derselben Uhr (Aussenrand + Ziffernring als zwei Erkennerkaesten, 1122p f01: d 5,05 und 3,33 m, Mitten 3 cm auseinander) -> eine Uhr.
    Gleiche Stelle = Mittenabstand < tol x Radius der groesseren. Die groessere bleibt; passt die kleinere als Innenring (0,45-0,85 x) und fehlt d_innen, wird sie das.
    Rueckgabe (bleibt, weg) - weg mit Grund."""
    bleibt, weg = [], []
    for U in sorted(uhren, key=lambda U: -U["d_aussen"]):
        gross = next((V for V in bleibt if np.hypot(U["u"] - V["u"], U["z"] - V["z"]) < tol * 0.5 * V["d_aussen"]), None)
        if gross is None: bleibt.append(U); continue
        f_ = U["d_aussen"] / gross["d_aussen"]
        if not gross.get("d_innen") and 0.45 <= f_ <= 0.85: gross["d_innen"] = U["d_aussen"]; gross["d_innen_quelle"] = "konzentrische Dublette (zweiter Erkennerkasten)"
        weg.append(dict(kasten=U.get("kasten"), grund=f"Dublette: konzentrisch zur Uhr u {gross['u']:.2f} z {gross['z']:.2f} (Abstand {np.hypot(U['u'] - gross['u'], U['z'] - gross['z']):.2f} m, d {U['d_aussen']:.2f} von {gross['d_aussen']:.2f} m)"))
    return [U for U in uhren if any(U is V for V in bleibt)], weg                  # Reihenfolge wie Eingabe


def gold_maske(bgr):
    """Vergoldete Teile (Ziffern, Randwulst, Zeiger): Farbton gelb/ocker, gesaettigt, hell (HSV, OpenCV-Skala). Schwabentor f00: 8-13 % der Scheibe."""
    h, s, v = [x.astype(int) for x in cv2.split(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV))]
    return (h >= 12) & (h <= 35) & (s >= 70) & (v >= 90)


def druckbar(maske, px, d_min=0.8 * 87 / 1000.0):
    """Mindestmass im Druck: Striche duenner als d_min (m, Standard 0,8 mm bei 1:87 = 7 cm) auf d_min verbreitern (Oeffnung mit d_min trennt duenn/dick,
    duenne Teile um d_min/2 je Seite aufgeweitet), Flecken < d_min^2 weg. Keine Form erfunden: nur vorhandene Striche werden dicker."""
    n0, lab0, st0, _ = cv2.connectedComponentsWithStats(maske.astype(np.uint8), connectivity=8)      # Einzelflecken (Glanzpunkte) vor dem Aufweiten weg
    maske = maske & ~np.isin(lab0, np.flatnonzero(st0[1:, cv2.CC_STAT_AREA] * px * px < 0.25 * d_min * d_min) + 1)
    k = max(3, int(np.ceil(d_min / px)) | 1); E = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)); m8 = maske.astype(np.uint8)
    dick = cv2.morphologyEx(m8, cv2.MORPH_OPEN, E).astype(bool); duenn = maske & ~dick
    r = max(1, int(round(0.5 * d_min / px))); E2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    m = dick | cv2.dilate(duenn.astype(np.uint8), E2).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    weg = np.flatnonzero(st[1:, cv2.CC_STAT_AREA] * px * px < d_min * d_min) + 1
    return m & ~np.isin(lab, weg)


def zifferblatt_aus_fotos(fein, fid, raster, U, aus, px=0.02, rand=1.0, min_fotos=3, mehrheit=0.5, w_ring=0.10, w_feld=0.06, hoch=0.07, zeiger=True):
    """ZIFFERBLATT-RELIEF AUS DEM WANDBILD (21.11.2026, Nutzerbild: Uhr nur flacher Kreis; Katalog-Ziffern sind verboten - kein Baukasten).
    Je entzerrtem Einzelfoto (fein/ortho_<fid>_einzeln) die Scheibe suchen (Kreis-Hough, Radius = gemessener Aussenradius +- 12 %, Suchfenster +- rand m: die Einzelbilder
    liegen bis 0,85 m gegeneinander versetzt), auf die Scheibe normieren (Mitte, Radius) und die Goldteile ausschneiden.
    Feste Teile (Ziffernring, Randwulst: r >= Innenradius) = Mehrheit von >= min_fotos Fotos (Kabel/Spiegelung fallen heraus).
    Zeiger (r < Innenradius) bewegen sich zwischen den Fotos -> aus dem SCHAERFSTEN Foto (zeiger=True; Uhrzeit dieses Fotos).
    Hoehen ueber der Wandflaeche: Innenfeld w_feld, Ziffernring w_ring, Gold + hoch (ANNAHME 6 / 10 / +7 cm = 0,7 / 1,15 / +0,8 mm im Druck).
    Schreibt aus (.npz wie relief_einsatz: rel, a, t, n, u0, z0, px + scheibe d_aussen) und aus.jpg; Rueckgabe dict oder None."""
    import glob
    c = float(raster["zelle"]); u0r, z1r = float(raster["u0"]), float(raster["z1"]); ra = 0.5 * float(U["d_aussen"]); ri = 0.5 * float(U["d_innen"]) if U.get("d_innen") else 0.66 * ra
    cx0 = (float(U["u"]) - u0r) / c; cy0 = (z1r - float(U["z"])) / c; R0 = ra / c; m_ = int((ra + rand) / c)
    S = ra + 0.06; N = int(np.ceil(2 * S / px)); g_ = (np.arange(N) + 0.5) * px - S; X, Y = np.meshgrid(g_, -g_); rr = np.hypot(X, Y); inn = rr <= ra
    K = []
    for f in sorted(glob.glob(os.path.join(fein, f"ortho_{fid}_einzeln", "*.png"))):
        im = cv2.imread(f)
        if im is None: continue
        x0, y0 = max(0, int(cx0) - m_), max(0, int(cy0) - m_); A = im[y0:int(cy0) + m_, x0:int(cx0) + m_]
        if A.size == 0: continue
        g = cv2.cvtColor(A, cv2.COLOR_BGR2GRAY); s = min(1.0, 500.0 / max(A.shape[:2])); gs = cv2.GaussianBlur(cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), (5, 5), 1.2)
        C = cv2.HoughCircles(gs, cv2.HOUGH_GRADIENT, dp=1, minDist=3, param1=110, param2=15, minRadius=int(0.88 * R0 * s), maxRadius=int(1.12 * R0 * s) + 1)
        if C is None: continue
        kan = cv2.Canny(gs, 40, 110); st, cx, cy, r = max(((stuetze(kan, a_, b_, r_), a_, b_, r_) for a_, b_, r_ in C[0][:40]), key=lambda t: t[0])
        if st < 0.7: continue
        cx, cy, r = x0 + cx / s, y0 + cy / s, r / s; k_ = r / R0                                   # Scheibe dieses Fotos -> Normraster (Mitte, Radius gleich)
        B = cv2.remap(im, (cx + X / c * k_).astype(np.float32), (cy - Y / c * k_).astype(np.float32), cv2.INTER_LINEAR, borderValue=(0, 0, 0))
        if (B.sum(2) > 0)[inn].mean() < 0.97: continue
        sch = float(cv2.Laplacian(cv2.cvtColor(B, cv2.COLOR_BGR2GRAY).astype(np.float32), cv2.CV_32F)[inn].var())
        K.append(dict(foto=os.path.basename(f)[:-4], schaerfe=sch, stuetze=st, gold=gold_maske(B), bild=B))
    if len(K) < min_fotos: return None
    K.sort(key=lambda k: -k["schaerfe"]); ref = cv2.GaussianBlur(cv2.cvtColor(K[0]["bild"], cv2.COLOR_BGR2GRAY), (0, 0), 1.0).astype(np.float32); mk = inn.astype(np.uint8)
    for k in K[1:]:                                                       # Feinausrichtung auf das schaerfste Foto (ECC affin): die Einzelbilder sind leicht verschert/verdreht entzerrt
        try:
            M = np.eye(2, 3, dtype=np.float32); _, M = cv2.findTransformECC(ref, cv2.GaussianBlur(cv2.cvtColor(k["bild"], cv2.COLOR_BGR2GRAY), (0, 0), 1.0).astype(np.float32), M, cv2.MOTION_AFFINE,
                                                                             (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-5), mk, 5)
            k["bild"] = cv2.warpAffine(k["bild"], M, (N, N), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP); k["gold"] = gold_maske(k["bild"]); k["ecc"] = True
        except cv2.error: k["ecc"] = False
    K = [K[0]] + [k for k in K[1:] if k.get("ecc")]
    if len(K) < min_fotos: return None
    stimme = np.mean([k["gold"] for k in K], 0)
    fest = (stimme >= mehrheit) & (rr >= ri - 2 * px) & inn
    zg = (K[0]["gold"] & (rr < ri - 2 * px)) if zeiger else np.zeros_like(fest)
    gold = druckbar(fest | zg, px) & inn
    rel = np.where(rr > ri, w_ring, w_feld) + hoch * gold; rel[~inn] = 0.0
    erg = dict(rel=rel.astype(np.float32), px=px, d_aussen=2 * ra, d_innen=2 * ri, gold_anteil=float(gold[inn].mean()), fotos=[k["foto"] for k in K], zeiger_foto=K[0]["foto"] if zeiger else "")
    vis = K[0]["bild"].copy(); vis[gold] = (0, 215, 255); vis[~inn] = (60, 60, 60)
    cv2.imwrite(aus[:-4] + ".jpg", np.hstack([K[0]["bild"], vis, cv2.cvtColor((np.clip(stimme, 0, 1) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)]))
    return erg


def zifferblaetter(od, fein, uhren, px=0.02):
    """Fuer jede Uhr in uhren (dict wie audit/uhren_auto.json) das Zifferblatt-Relief rechnen -> audit/uhr_<fid>_<k>.npz, Eintrag U['zifferblatt'] (relativ zu audit/)."""
    FF = {f["id"]: f for f in json.load(open(os.path.join(fein, "fassaden.json")))["fassaden"]}; n = 0
    for fid, F in uhren.items():
        R_ = (FF.get(fid) or {}).get("raster")
        for k, U in enumerate(F.get("uhren", [])):
            if not R_: continue
            aus = os.path.join(od, "audit", f"uhr_{fid}_{k}.npz"); E = zifferblatt_aus_fotos(fein, fid, R_, U, aus, px=px)
            if E is None: U["zifferblatt_fehlt"] = "weniger als 3 Einzelfotos zeigen die ganze Scheibe"; print(f"{fid}: Uhr {k}: kein Zifferblatt ({U['zifferblatt_fehlt']})"); continue
            S = 0.5 * E["rel"].shape[0] * px
            np.savez_compressed(aus, rel=E["rel"], a=np.asarray(F["o"], float), t=np.asarray(F["d"], float), n=np.asarray(F["n"], float), u0=float(U["u"]) - S, z0=float(U["z"]) - S, px=px,
                                d_aussen=E["d_aussen"], d_innen=E["d_innen"], gold_anteil=E["gold_anteil"])
            U["zifferblatt"] = os.path.basename(aus); U["zifferblatt_fotos"] = E["fotos"]; U["zeiger_foto"] = E["zeiger_foto"]; U["gold_anteil"] = round(E["gold_anteil"], 3); n += 1
            print(f"{fid}: Uhr {k}: Zifferblatt aus {len(E['fotos'])} Einzelfotos (Gold {E['gold_anteil'] * 100:.0f} % der Scheibe, Zeiger aus {E['zeiger_foto']}) -> {aus}")
    return n


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--nur_zifferblatt":          # vorhandene audit/uhren_auto.json um die Zifferblaetter ergaenzen (ohne neue Erkennung)
        ap = argparse.ArgumentParser(); ap.add_argument("uhren_json"); ap.add_argument("fein"); a = ap.parse_args(sys.argv[2:])
        J = json.load(open(a.uhren_json)); n = zifferblaetter(os.path.dirname(os.path.dirname(os.path.abspath(a.uhren_json))), a.fein, J); json.dump(J, open(a.uhren_json, "w"), indent=1); return 0 if n else 3
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fein"); ap.add_argument("--elemente", required=True); ap.add_argument("--aus")
    ap.add_argument("--stimmen", type=int, default=3); ap.add_argument("--min_stuetze", type=float, default=0.85, help="21.11.: echte Uhr 98-100 %%, Scheinkreis im Erkerbild 77 %%"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit", "uhren_auto.json")
    E = json.load(open(a.elemente))["fassaden"]; FF = {f["id"]: f for f in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}; erg = {}; bilder = []; n_uhr = 0
    for fid, F in E.items():
        kand = [e for e in F.get("elemente", []) if e.get("klasse") == "uhr" and e.get("stimmen", 0) >= a.stimmen and e.get("stimmen", 0) >= 0.4 * max(1, e.get("gesehen", 1))]
        if not kand or fid not in FF: continue
        im = cv2.imread(os.path.join(a.fein, f"ortho_{fid}_fein.png"), cv2.IMREAD_GRAYSCALE); R_ = FF[fid].get("raster")
        if im is None or not R_: continue
        gr = cv2.imread(os.path.join(a.fein, f"ortho_{fid}.png"), cv2.IMREAD_GRAYSCALE)      # wie oeffnungen_wandbild: wo das feine Bild leer ist, das grobe auf demselben Raster einsetzen
        if gr is not None: gr = cv2.resize(gr, (im.shape[1], im.shape[0]), interpolation=cv2.INTER_CUBIC); im = np.where(im > 0, im, gr)
        c = float(R_["zelle"]); u0r, z1r = float(R_["u0"]), float(R_["z1"]); px = lambda u, z: ((u - u0r) / c, (z1r - z) / c)
        e_ = dict(o=F["o"], d=F["d"], n=F["n"], uhren=[], verworfen=[]); vis_ = {}
        for k in kand:
            g = max(k["u1"] - k["u0"], k["z1"] - k["z0"]); x0, y0 = px(k["u0"] - 0.3 * g, k["z1"] + 0.3 * g); x1, y1 = px(k["u1"] + 0.3 * g, k["z0"] - 0.3 * g)
            x0, y0 = max(0, int(x0)), max(0, int(y0)); x1, y1 = min(im.shape[1], int(x1)), min(im.shape[0], int(y1)); A = im[y0:y1, x0:x1]
            ka, kb = px(k["u0"], k["z1"]), px(k["u1"], k["z0"]); Kz = im[max(0, int(ka[1])):int(kb[1]), max(0, int(ka[0])):int(kb[0])]      # Fuellgrad nur im Kasten selbst (Rand darf ueber die Fassade hinausragen)
            if A.size == 0 or Kz.size == 0 or (Kz > 0).mean() < 0.6: e_["verworfen"].append(dict(kasten=[k["u0"], k["u1"], k["z0"], k["z1"]], grund="Wandbild in der Zone leer")); continue
            s = min(1.0, 400.0 / max(A.shape)); As = cv2.resize(A, None, fx=s, fy=s, interpolation=cv2.INTER_AREA); As = cv2.GaussianBlur(As, (5, 5), 1.2)
            kan = cv2.Canny(As, 40, 110); rg = 0.5 * g / c * s
            C = cv2.HoughCircles(As, cv2.HOUGH_GRADIENT, dp=1, minDist=3, param1=110, param2=15, minRadius=int(0.7 * rg), maxRadius=int(1.3 * rg) + 1)
            if C is None: e_["verworfen"].append(dict(kasten=[k["u0"], k["u1"], k["z0"], k["z1"]], grund="kein Kreis im Wandbild")); continue
            best = max(((stuetze(kan, cx, cy, r), cx, cy, r) for cx, cy, r in C[0][:40]), key=lambda t: t[0])
            if best[0] < a.min_stuetze: e_["verworfen"].append(dict(kasten=[k["u0"], k["u1"], k["z0"], k["z1"]], grund=f"Kreis nur zu {best[0] * 100:.0f} % von Kanten gestuetzt")); continue
            sa, cx, cy, r = best
            zb_ = zifferblatt_beleg(im, x0 + cx / s, cy / s + y0, r / s)        # 23.11.2026: Kreis allein ist keine Uhr (Heiligenschein) - 12er-Teilung im Ring
            if not zb_["ok"]: e_["verworfen"].append(dict(kasten=[k["u0"], k["u1"], k["z0"], k["z1"]], grund=zb_["grund"], beleg_12=zb_["verh"])); continue
            innen = None
            for f_ in np.arange(0.45, 0.86, 0.01):
                for dx in (-0.04, 0, 0.04):
                    for dy in (-0.04, 0, 0.04):
                        si = stuetze(kan, cx + dx * r, cy + dy * r, f_ * r)
                        if innen is None or si > innen[0]: innen = (si, f_ * r)
            cx, cy, r = float(cx), float(cy), float(r); uc = u0r + (x0 + cx / s) * c; zc = z1r - (y0 + cy / s) * c; da = 2 * r / s * c; di = 2 * innen[1] / s * c if innen and innen[0] >= a.min_stuetze else None
            e_["uhren"].append(dict(u=round(uc, 3), z=round(zc, 3), d_aussen=round(da, 3), d_innen=round(di, 3) if di else None, stuetze_aussen=round(sa, 2), stuetze_innen=round(innen[0], 2) if innen else None,
                                    kasten=[round(k["u0"], 2), round(k["u1"], 2), round(k["z0"], 2), round(k["z1"], 2)], stimmen=k.get("stimmen"), beleg_12=zb_["verh"],
                                    quelle="Zone OWLv2 'uhr' (fassade_parsing) -> Kreis-Hough + Kantenstuetze + 12er-Teilung im feinen Wandbild (1 cm)"))
            print(f"{fid}: UHR Mitte u {uc:.2f} z {zc:.2f}, Durchmesser {da:.2f} m" + (f", innen {di:.2f} m" if di else ", Innenkreis nicht belegt") + f" (Kantenstuetze {sa * 100:.0f} %, 12er-Teilung {zb_['verh']:.2f})")
            vis = cv2.cvtColor(As, cv2.COLOR_GRAY2BGR); cv2.circle(vis, (int(cx), int(cy)), int(r), (0, 255, 0), 2)
            if di: cv2.circle(vis, (int(cx), int(cy)), int(innen[1]), (0, 200, 255), 2)
            vis_[id(e_["uhren"][-1])] = vis
        e_["uhren"], weg_ = dubletten_zusammenfassen(e_["uhren"]); e_["verworfen"] += weg_; n_uhr += len(e_["uhren"]); bilder += [vis_[id(U)] for U in e_["uhren"]]
        for v in e_["verworfen"]: print(f"{fid}: verworfen {v['kasten']}: {v['grund']}")
        erg[fid] = e_
    os.makedirs(os.path.dirname(aus), exist_ok=True)
    if n_uhr and os.environ.get("OHNE_ZIFFERBLATT") != "1": zifferblaetter(os.path.dirname(os.path.dirname(os.path.abspath(aus))), a.fein, erg)   # 21.11.2026: Zifferblatt-Relief aus den Einzelfotos
    json.dump(erg, open(aus, "w"), indent=1)
    if bilder:
        h = max(b.shape[0] for b in bilder); cv2.imwrite(aus[:-5] + ".jpg", np.hstack([np.pad(b, ((0, h - b.shape[0]), (0, 6), (0, 0))) for b in bilder]))
    print(f"-> {aus}: {n_uhr} Uhren"); return 0 if n_uhr else 3


if __name__ == "__main__": sys.exit(main())
