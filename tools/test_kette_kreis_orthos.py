#!/usr/bin/env python3
"""test_kette_kreis_orthos.py - fester Test (CPU, < 20 s, ohne Daten) fuer den KREISFALL der Kette (22.11.2026, Kettenlauf schwabentor 1121v).

Befund: die Einzelfoto-Orthos (fassade_ortho --einzeln) werden zu Beginn jedes Kettenlaufs auf das STL des VORIGEN Laufs projiziert. Hat das die gesuchte Kante schon
gebaut (Fensterkasten, lichte Toroeffnung als Loch), springt dort die Projektionsflaeche: die Kante klebt in jedem Ortho an der Naht, ihre Parallaxe ist weg.
Folge im echten Lauf: Laibung f00 'unplausibel T 4,68 m' (Probe 0,82/0,85 m), Tor 5,23 statt 4,32 (Verlauf hand_vergleich PASST/FALSCH im Wechsel je Lauf).
Fix: laibung_aus_fotos und oeffnungen_aus_kanten.laibungskanten tasten die Fotos selbst auf einer Ebene ab (foto_feld / _foto_flach) - unabhaengig vom Vorergebnis.

 A  laibung_aus_fotos (CLI): synthetische Lochkamera-Fotos (Fenster 0,60 m, Laden 0,80 m hinter der Wand) + 'Kreis-Orthos' (Kasten des vorigen Baus: Inhalt an der
    Naht festgeklebt, schwarzer Verdeckungsstreifen, Relief -0,54). Soll: mit Fotos T = 0,80 +-0,05 (Quelle 'foto'); nur Orthos (--ohne_foto) NICHT 0,80 (Kreis belegt).
 B  oeffnungen_aus_kanten.laibungskanten: Tor mit Fase 0,25 m, Innenkante 0,30 m tief; Kreis-Orthos mit festgeklebter Innenkante und Loch im Relief.
    Soll: mit Fotos Innenkante u -1,25 +-0,03 und Tiefe 0,30 +-0,10 (Ruecksprung gegen die Aussenkante belegt); ohne Fotos Tiefe nicht 0,30 (Kreis belegt).
 C  fenster_form_tor.urteil: 7:6 (korb:rund, echter Stand 1121v rechte Nische) ist kein FALSCH, 3:0 und 4:1 schon.
 D  hand_vergleich.form_ist mit dem echten Form-Tor-Stand 1121v (f00, gekuerzt): Fenster rund PASST, Nische korb 7 / rund 6 -> Form 'rund' ok mit Hinweis, nicht FALSCH.
rc 0 = bestanden.
"""
import sys, os, json, tempfile, shutil, subprocess, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
F_ = 0


def pruef(ok, t):
    global F_
    print(("  ok     " if ok else "  FEHLER ") + t); F_ += not ok


def kamera(C, ziel, f=1500.0, W=1000, Hh=800):
    """K-Datei-Kamera (rvec, t, f_px, cx, cy) mit Zentrum C (Welt xyz), Blick auf ziel, z oben."""
    import cv2
    fw = np.asarray(ziel, float) - C; fw /= np.linalg.norm(fw); re = np.cross(fw, [0, 0, 1.0]); re /= np.linalg.norm(re); un = np.cross(fw, re)
    R = np.array([re, un, fw]); return dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=(-R @ C).tolist(), f_px=f, cx=W / 2, cy=Hh / 2, k1=0.0, bild=[W, Hh]), R


def strahlen(kk, R, C, W=1000, Hh=800):
    """Je Pixel Strahl in Fassadenkoordinaten (u, w, z) fuer Fassade o = 0, d = (1, 0), n = (0, -1) (Welt x = u, y = -w)."""
    jj, ii = np.meshgrid(np.arange(W) + 0.5, np.arange(Hh) + 0.5); xn = (jj - kk["cx"]) / kk["f_px"]; yn = (ii - kk["cy"]) / kk["f_px"]
    D = np.stack([xn, yn, np.ones_like(xn)], -1) @ R                                                     # Welt = R^T * Kamera
    return (C[0], -C[1], C[2]), (D[..., 0], -D[..., 1], D[..., 2])


def foto_fenster(kk, R, C, b0, b1, z0, z1, T):
    """Foto: Wand w = 0 hell 200 (+ Rauschen), Fensteroeffnung b0..b1 x z0..z1, Laibung hell 235 bis zum Laden (w = -T, dunkel 60)."""
    (cu, cw, cz), (du, dw, dz) = strahlen(kk, R, C); t0 = -cw / dw; u0 = cu + t0 * du; zz0 = cz + t0 * dz
    g = np.full(du.shape, 200.0); im = (u0 > b0) & (u0 < b1) & (zz0 > z0) & (zz0 < z1)
    tT = (-T - cw) / dw; uT = cu + tT * du; zT = cz + tT * dz; laden = im & (uT > b0) & (uT < b1) & (zT > z0) & (zT < z1)
    g[im] = 235.0; g[laden] = 60.0
    return np.clip(g + np.random.default_rng(int(abs(C[0] * 7 + C[1]))).normal(0, 2, g.shape), 1, 255).astype(np.uint8)


def foto_tor(kk, R, C, a0, a1, fase, L):
    """Foto: Wand w = 0 (150), Toroeffnung a0..a1 (ganze Hoehe) mit Fase links/rechts (dunkel 70, schraeg von w 0 an a0 bis w -L an a0 + fase), dahinter hell 210."""
    (cu, cw, cz), (du, dw, dz) = strahlen(kk, R, C); t0 = -cw / dw; u0 = cu + t0 * du
    g = np.full(du.shape, 150.0); im = (u0 > a0) & (u0 < a1); g[im] = 210.0
    for ua, ub in ((a0, a0 + fase), (a1, a1 - fase)):                                                    # Fase als Ebene durch (ua, 0) und (ub, -L): Schnitt des Strahls
        eu, ew = ub - ua, -L; nu_, nw_ = -ew, eu; den = du * nu_ + dw * nw_
        with np.errstate(divide="ignore", invalid="ignore"):
            t = ((ua - cu) * nu_ + (0 - cw) * nw_) / den; s = ((cu + t * du - ua) * eu + (cw + t * dw) * ew) / (eu * eu + ew * ew)
        g[im & (t > 0) & (s >= 0) & (s <= 1)] = 70.0
    return np.clip(g + np.random.default_rng(int(abs(C[0] * 7 + C[1]))).normal(0, 2, g.shape), 1, 255).astype(np.uint8)


def teil_a(d):
    import cv2
    U0, U1, Z0, Z1, c = -3.0, 3.0, 9.0, 13.0, 0.01; b0, b1, z0, z1, T = -0.3, 0.3, 10.0, 11.8, 0.80
    ob = os.path.join(d, "modelle", "x"); mp = os.path.join(ob, "messprotokoll"); ff = os.path.join(d, "fassade_fein"); ez = os.path.join(ff, "ortho_f00_einzeln"); fo = os.path.join(d, "fotos"); au = os.path.join(d, "audit")
    for x in (mp, ez, fo, au): os.makedirs(x, exist_ok=True)
    json.dump(dict(fotos_dir="fotos"), open(os.path.join(ob, "objekt.json"), "w"))
    nu, nz = int((U1 - U0) / c), int((Z1 - Z0) / c); uu = U0 + c * (np.arange(nu) + 0.5)
    rel = np.full((nz, nu), 10000, np.uint16); box = (uu >= b0) & (uu <= b1); zz = Z1 - c * (np.arange(nz) + 0.5); zb = (zz >= z0) & (zz <= z1)
    rel[np.ix_(zb, box)] = 9460                                                                              # Kasten des vorigen Baus: Relief -0,54
    for k, (Cu, Cw) in enumerate(((-9.0, 14.0), (-6.0, 10.0), (-4.0, 7.0), (-2.5, 9.0), (2.5, 9.0), (4.0, 7.0), (6.0, 10.0), (9.0, 14.0))):
        C = np.array([Cu, -Cw, 1.6]); kk, R = kamera(C, (0.0, 0.0, 10.9)); n_ = f"k{k}"
        cv2.imwrite(os.path.join(fo, n_ + ".png"), foto_fenster(kk, R, C, b0, b1, z0, z1, T)); json.dump(dict(kamera=kk), open(os.path.join(mp, f"K-{n_}.json"), "w"))
        g = np.full((nz, nu), 200, np.uint8); g[np.ix_(zb, box)] = 60                                        # Kreis-Ortho: Kasten dunkel bis an die Naht, Verdeckungsstreifen auf der Nahseite
        j = np.flatnonzero(box); st = j[:6] if Cu < 0 else j[-6:]; g[np.ix_(zb, st)] = 0
        cv2.imwrite(os.path.join(ez, n_ + ".png"), g)
    cv2.imwrite(os.path.join(ff, "relief_f00.png"), rel)
    json.dump(dict(fassaden=[dict(id="f00", o=[0, 0], d=[1, 0], n=[0, -1], raster=dict(u0=U0, z1=Z1, zelle=c))]), open(os.path.join(ff, "fassaden.json"), "w"))
    fe = [dict(u0=b0, u1=b1, z0=z0, z1=z1, bogen=dict(form="rund", kaempfer=11.5, scheitel=11.8), tiefe=0.12, tiefe_quelle="ANNAHME")]
    erg = {}
    for tag, extra in (("foto", []), ("ortho", ["--ohne_foto"])):
        fa = os.path.join(au, f"fenster_{tag}.json"); json.dump(dict(f00=dict(o=[0, 0], d=[1, 0], n=[0, -1], fenster=fe)), open(fa, "w"))
        r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(H, "laibung_aus_fotos.py"), fa, ff, os.path.join(ob, "objekt.json")] + extra, capture_output=True, text=True)
        B = json.load(open(os.path.join(au, "laibung_aus_fotos.json")))["f00"][0]; erg[tag] = (r, B)
    r, B = erg["foto"]; qu = {p.get("quelle") for p in B.get("punkte", [])}
    pruef(r.returncode == 0 and abs(B.get("tiefe_ab_wand", -9) - T) <= 0.05 and qu == {"foto"},
          f"A mit Fotos: T {B.get('tiefe_ab_wand')} (soll {T}), {B.get('fotos')} Fotos, Quelle {qu}, rc {r.returncode} {r.stderr[-200:]}")
    r, B = erg["ortho"]
    pruef("fehler" in B or abs(B.get("tiefe_ab_wand", -9) - T) > 0.05, f"A nur Kreis-Orthos: {B.get('fehler') or B.get('tiefe_ab_wand')} (darf nicht {T} treffen - sonst belegt der Test den Kreis nicht)")


def teil_b(d):
    import cv2, oeffnungen_aus_kanten as O
    U0, Z1, c, nu, nz = -3.0, 4.0, 0.01, 600, 400; a0, a1, fase, L = -1.5, 1.5, 0.25, 0.30
    F = dict(id="t00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], raster=dict(u0=U0, z1=Z1, zelle=c, nu=nu, nz=nz)); E_ = dict(id="t00_wand", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0])
    uu = U0 + c * (np.arange(nu) + 0.5); fo = os.path.join(d, "fotos_b"); os.makedirs(fo, exist_ok=True)
    rel = np.full((nz, nu), -0.03, np.float32); band = ((uu >= a0) & (uu < a0 + fase)) | ((uu <= a1) & (uu > a1 - fase)); rel[:, band] = -0.15; loch = (uu >= a0 + fase) & (uu <= a1 - fase); rel[:, loch] = 0.0
    einz = []; fotos = {}
    for k, (Cu, Cw) in enumerate(((-6.0, 10.0), (-3.5, 9.0), (-1.0, 11.0), (1.0, 11.0), (3.5, 9.0), (6.0, 10.0))):
        C = np.array([Cu, -Cw, 2.0]); kk, R = kamera(C, (-1.25, 0.0, 2.0)); n_ = f"t{k}"; p = os.path.join(fo, n_ + ".png")
        cv2.imwrite(p, foto_tor(kk, R, C, a0, a1, fase, L)); fotos[n_] = (p, kk)
        g = np.full((nz, nu), 150, np.uint8); g[:, (uu > a0) & (uu < a1)] = 210; g[:, band] = 70                 # Kreis-Ortho: Innenkante klebt an der Naht (keine Parallaxe)
        g = np.clip(g + np.random.default_rng(k).normal(0, 2, g.shape), 1, 255).astype(np.uint8); einz.append((n_, g, C))
    W = O.wandbild_aus(F, np.full((nz, nu), 150, np.float32), E_, einz, quelle="synthetisch", relief=rel)
    W["fotos"] = fotos; W["foto_cache"] = {}; W["relief_da"] = np.ones((nz, nu), bool) & ~loch[None, :]
    def innen(K): return min(K, key=lambda k: abs(k["u"] - (a0 + fase))) if K else None
    K, _ = O.laibungskanten(W, a0 - 0.2, a0 + 0.6, 1.0, 3.0); ki = innen(K); ka = min(K, key=lambda k: abs(k["u"] - a0)) if K else None
    pruef(ki is not None and abs(ki["u"] - (a0 + fase)) <= 0.03 and ki["tiefe"] is not None and abs(ki["tiefe"] - L) <= 0.10 and ka is not None and ka["tiefe"] is not None and ka["tiefe"] < ki["tiefe"] - 0.07,
          f"B mit Fotos: Innenkante {ki and (round(ki['u'], 3), ki['tiefe'] and round(ki['tiefe'], 3), ki['fotos'])} (soll {a0 + fase}, {L}), Aussenkante {ka and (round(ka['u'], 3), ka['tiefe'] and round(ka['tiefe'], 3))}")
    W.pop("fotos"); K2, _ = O.laibungskanten(W, a0 - 0.2, a0 + 0.6, 1.0, 3.0); k2 = innen(K2)
    pruef(k2 is None or k2["tiefe"] is None or abs(k2["tiefe"] - L) > 0.10, f"B nur Kreis-Orthos: Innenkante {k2 and (round(k2['u'], 3), k2['tiefe'])} (darf die Tiefe {L} nicht treffen)")


def teil_c():
    import fenster_form_tor as FT
    for st, soll in (({"korb": 7, "stich": 1, "rund": 6}, "UNBESTIMMT"), ({"korb": 3}, "FALSCH"), ({"korb": 4, "rund": 1}, "FALSCH"), ({"rund": 10, "korb": 5, "stich": 1}, "PASST"), ({"korb": 8, "rund": 5}, "UNBESTIMMT")):
        u, _ = FT.urteil("rund", st); pruef(u == soll, f"C urteil gebaut rund, Stimmen {st}: {u} (soll {soll})")


def teil_d():
    import hand_vergleich as HV
    tor = {"fassaden": {"f00": [                                                                                # echter Stand audit/fenster_form_tor.json, Lauf 1121v (gekuerzt)
        {"kasten": [1.839, 2.529, 23.14, 24.94], "fenster": {"gebaut": "rund", "stimmen": {"rund": 10, "korb": 5, "stich": 1}, "urteil": "PASST"},
         "nische": {"gebaut": "rund", "stimmen": {"korb": 7, "stich": 1, "rund": 6}, "urteil": "UNBESTIMMT"}, "urteil": "UNBESTIMMT"},
        {"kasten": [-2.381, -1.681, 23.05, 24.89], "fenster": {"gebaut": "rund", "stimmen": {"rund": 16, "korb": 5}, "urteil": "PASST"},
         "nische": {"gebaut": "rund", "stimmen": {"rund": 12, "korb": 3, "stich": 4, "gerade": 1}, "urteil": "PASST"}, "urteil": "PASST"}]}}
    fz = [dict(u0=1.839, u1=2.529, z0=23.14, z1=24.94, bogen=dict(form="rund")), dict(u0=-2.381, u1=-1.681, z0=23.05, z1=24.89, bogen=dict(form="rund"))]
    e = HV.form_ist(fz, tor, "f00")
    pruef(e["ist"] == "rund" and not e.get("tor_falsch") and not e.get("unsicher") and "Nische" in e.get("hinweis", ""), f"D form_ist 1121v: {e}")
    tor["fassaden"]["f00"][0]["nische"]["urteil"] = "FALSCH"; e = HV.form_ist(fz, tor, "f00")
    pruef(e.get("tor_falsch"), f"D Nische belegt FALSCH bleibt FALSCH: {e.get('tor', e)}")


def main():
    d = temp_ordner("test_kreis_")
    try:
        teil_a(d); teil_b(d); teil_c(); teil_d()
    finally: shutil.rmtree(d, ignore_errors=True)
    print(f"test_kette_kreis_orthos: {F_} Fehler"); return 1 if F_ else 0


if __name__ == "__main__": sys.exit(main())
