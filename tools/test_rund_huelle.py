#!/usr/bin/env python3
"""test_rund_huelle.py - Rundkoerper mit Dach aus EINSEITIGEN Silhouetten (tools/rund_aus_huelle.py, tools/drehkoerper_aus_fotos.py), 23.11.2026.

Anlass: Kette 1122s, Treppentuermchen am Schwabentor = hoher Zylinder ohne Dach (rund_aus_umriss: Umriss-Stuetze bis zum Suchende 13,75 m, keine Traufe, Dach ab
13,75 gesucht -> ungueltig). Der Koerper steht vor dem Hauptturm: frei vor Himmel ist meist nur eine Seite und das Dach.
Vorgespielte Silhouetten (Vorwaertsabbildung eines Drehkoerpers: Schaft r 1,6 bis z 12,4, Traufe r 1,75, GESCHWEIFTES Dach bis 14,5) in Kameras rund um die Achse,
bei der Haelfte eine Seite vor dem Hauptturm (+-inf), unten (z < 6) Nachbarhaeuser auf beiden Seiten (keine Schranke), Rauschen 1 cm; ein Foto mit falscher Maske
(Silhouette 0,5 m zu schmal) und ein Foto mit weitem Fremdkoerper (Laterne) neben einer Seite:
 A) Huelle: Traufe +-0,25 m, Schaft r +-0,06, Spitze +-0,25, Familie 'geschweift', gueltig, falsches Foto aussortiert, Fremdkoerper stoert nicht.
 B) ROT-PROBE: dieselben Fotos BEIDSEITIG gelesen (alte Laternen-Silhouette: aeussere Ausdehnung, Hauptturm zaehlt zum Koerper) -> Huelle im Schaft viel zu weit.
 C) einseitig_halb: Kante vor Himmel, Draht hinter der Kante bricht nicht ab, Seite vor Wand -> inf, Himmel an der Achse -> NaN.
 D) himmelsfarbe: Maske auf Fassade -> None; echter Himmel -> Farbe + Schwelle >= MIN_KONTRAST.
 E) zonen: unten weite Huelle (wenige Fotos sehen Himmel neben dem Fuss) -> Traufe trotzdem am Dachfuss (nicht 'groesster Radius').
 F) Generator: Block 'dach' -> bauteile.kegeldach_teile baut Traufbrett + Stuempfe bis zur Spitze; drehkoerper_aus_wolkenrest endet an der Traufe."""
import sys, os, math, json, tempfile, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drehkoerper_aus_fotos as DK, rund_aus_huelle as RH

fehler = []
def pruef(ok, text):
    print(("    ok   " if ok else "FEHLER  ") + text)
    if not ok: fehler.append(text)

rng = np.random.default_rng(5)
A = np.array([0.0, 0.0]); ZS = np.round(np.arange(1.0, 18.0, 0.1), 2)
Z_T, R_S, R_T, Z_S = 12.4, 1.6, 1.75, 14.5


def wahr(z):
    z = np.asarray(z, float); r = np.zeros_like(z); r[z < Z_T] = R_S; h = (z >= Z_T) & (z <= Z_T + 0.1); r[h] = R_T
    h = (z > Z_T + 0.1) & (z <= Z_S); t = (z[h] - Z_T - 0.1) / (Z_S - Z_T - 0.1); r[h] = R_T * (1 - t) ** 1.8      # geschweift: unten flach ausgestellt, oben steil
    return r


def fotos(beidseitig=False):
    zf = np.arange(0.5, Z_S + 0.001, 0.01); rf = wahr(zf); quer = DK.querschnitt_einheit(); out = []
    azs = [-150, -120, -90, -60, -30, 0, 20, 45, 70, 100, 130, 160, 185]
    for i, az in enumerate(azs):
        d = 14.0 + 3 * (i % 4); u = np.array([math.cos(math.radians(az)), math.sin(math.radians(az))]); C = np.r_[A + d * u, 1.6]
        B = dict(C=[float(v) for v in C], az=float(az), A0=A.copy(), zg=ZS.copy(), nr=f"syn{i}")
        l, r = DK.silhouette_vorhersage(B, A, zf, rf, quer, dz=0.01); l = l + rng.normal(0, 0.01, len(ZS)); r = r + rng.normal(0, 0.01, len(ZS))
        turm = i % 2 == 0                                                        # Hauptturm hinter einer Seite (bis 30 m hoch)
        if turm:
            if beidseitig: r = np.where(np.isfinite(r), 6.0, r)                 # alte Silhouette: aeussere Ausdehnung = Turmkante
            else: r = np.where(np.isnan(r) & (ZS < 30), np.inf, r); r = np.where(np.isfinite(r), np.inf, r)
        unten = ZS < 6.0                                                          # Nachbarhaeuser neben dem Fuss
        if beidseitig: l = np.where(unten, -8.0, l); r = np.where(unten, 8.0, r)
        else: l = np.where(unten, -np.inf, l); r = np.where(unten, np.inf, r)
        if i == 3: l = np.where(np.isfinite(l) & (ZS > 6), l + 0.5, l)          # falsche Maske: Koerper links 0,5 m zu schmal
        if i == 5: l = np.where((ZS > 8) & (ZS < 10), l - 1.5, l)                # Fremdkoerper (Laterne) links vor Himmel
        B.update(l=l, r=r); out.append(B)
    return out


print("A) Huelle aus einseitigen Silhouetten")
E = RH.huelle_messen(fotos(), A, ZS, 1.7, log=lambda *a: None)
print("   ", {k: E.get(k) for k in ("z_traufe", "r_traufe", "r_schaft", "z_spitze", "familie", "gueltig", "grund")}, "raus", list(E.get("weg", {})))
pruef(E.get("gueltig") is True, f"gueltig ({E.get('grund')})")
pruef(E.get("z_traufe") is not None and abs(E["z_traufe"] - Z_T) <= 0.25, f"Traufe {E.get('z_traufe')} (wahr {Z_T})")
pruef(E.get("r_schaft") is not None and abs(E["r_schaft"] - R_S) <= 0.06, f"Schaft r {E.get('r_schaft')} (wahr {R_S})")
zf_ = np.arange(Z_T, Z_S, 0.01); z_sp = float(zf_[wahr(zf_) >= 0.05].max())                                          # Spitze duenner als 5 cm ist nicht aufloesbar
pruef(E.get("z_spitze") is not None and abs(E["z_spitze"] - z_sp) <= 0.2, f"Spitze {E.get('z_spitze')} (wahr {z_sp:.2f} = Hoehe mit r >= 5 cm; Nadel {Z_S})")
pruef(E.get("familie") == "geschweift", f"Familie {E.get('familie')} (wahr geschweift)")
pruef("syn3" in E.get("weg", {}), f"Foto mit falscher Maske aussortiert ({list(E.get('weg', {}))})")
pruef("syn5" not in E.get("weg", {}), "Foto mit Fremdkoerper bleibt (weiter = kein Widerspruch)")
zm = (E["z_traufe"] + E["z_spitze"]) / 2 if E.get("z_spitze") else 13.4; rp = np.interp(zm, [p[0] for p in E["dach_profil"]], [p[1] for p in E["dach_profil"]]) if E.get("dach_profil") else -1
pruef(abs(rp - wahr([zm])[0]) <= 0.15, f"Dachradius auf halber Hoehe {rp:.2f} (wahr {wahr([zm])[0]:.2f})")

print("B) ROT-PROBE: Huelle ohne 'einseitig' (Hoehen ohne einschraenkendes Foto) erfindet den Suchrand")
FB = fotos(); sm_ = RH.S_MAX_R * 1.7; r_a, _, _ = DK.drehprofil(FB, A, ZS, s_max=sm_); r_e, _, _ = DK.drehprofil(FB, A, ZS, s_max=sm_, einseitig=True); u_ = (ZS >= 1.5) & (ZS < 4.0)   # (Fusszeile: Koerper beginnt bei 0,5 m; (ab ~4,5 m reichen Ringe am Suchrand perspektivisch in die Zeilen ueber 6 m)
pruef(np.allclose(r_a[u_], sm_, atol=0.01) and np.isnan(r_e[u_]).all(), f"z < 4 (Nachbarhaeuser beidseits): ohne einseitig r {np.median(r_a[u_]):.2f} = Suchrand, einseitig NaN (nicht gemessen)")
r_b, _, _ = DK.drehprofil(fotos(beidseitig=True), A, ZS, s_max=sm_, einseitig=True); sch = (ZS > 8) & (ZS < 11)
pruef(abs(float(np.median(r_b[sch])) - R_S) < 0.06, f"beidseitige (zu weite) Silhouette schadet der Huelle nicht: Schaft {np.median(r_b[sch]):.2f}")

print("C) einseitig_halb")
xs = np.arange(-4, 4, 0.01); d = np.zeros_like(xs); d[np.abs(xs) < 1.6] = 1.0; d[xs > 1.6] = 1.0; d[(xs < -1.75) & (xs > -1.77)] = 1.0   # Draht 2 cm hinter der linken Kante
l, r = DK.einseitig_halb(d, xs)
pruef(abs(l + 1.6) < 0.02 and r == np.inf, f"Kante links {l:.3f} (wahr -1,6), rechts vor Wand {r}")
l, r = DK.einseitig_halb(np.zeros_like(xs), xs); pruef(np.isnan(l) and np.isnan(r), "Himmel an der Achse -> NaN")
hm = np.ones_like(xs, bool); hm[xs < -1.6] = False; d2 = np.where(np.abs(xs) < 1.6, 1.0, 0.0)
l, r = DK.einseitig_halb(d2, xs, hm); pruef(l == -np.inf and abs(r - 1.6) < 0.02, f"links Maske kein Himmel -> -inf ({l}), rechts {r:.3f}")

print("D) himmelsfarbe")
px = np.r_[np.tile([200, 180, 150], (300, 1)), rng.uniform(0, 255, (300, 3))]; m = np.r_[np.zeros(300, bool), np.ones(300, bool)]
pruef(DK.himmelsfarbe(px, m) is None, "Maske auf bunter Fassade -> nicht plausibel")
sky = np.tile([235, 220, 200], (400, 1)) + rng.normal(0, 2, (400, 3)); hf = DK.himmelsfarbe(sky, np.ones(400, bool))
pruef(hf is not None and np.linalg.norm(hf[0] - [235, 220, 200]) < 3 and hf[1] >= DK.MIN_KONTRAST, f"Himmel -> Farbe {None if hf is None else hf[0].round()} Schwelle {None if hf is None else round(hf[1], 1)}")

print("E) zonen mit weiter Huelle unten")
zz = np.round(np.arange(3.0, 16.0, 0.1), 2); rr = wahr(zz); rr = np.where(zz < 8.5, 2.2 + (8.5 - zz) * 0.5, rr); rr[zz > Z_S + 0.05] = 0.0
Zo, g = RH.zonen(zz, rr, 1.7)
pruef(Zo is not None and abs(Zo["z_traufe"] - Z_T) <= 0.25 and abs(Zo["r_schaft"] - R_S) <= 0.05, f"Traufe {None if Zo is None else Zo['z_traufe']}, Schaft {None if Zo is None else Zo['r_schaft']} ({g})")

print("F) Generator")
try:
    import bauteile as BT
    from manifold3d import Manifold as M
    E["dach_profil"] = E.get("dach_profil") or [[Z_T, R_T], [Z_S, 0.0]]
    KD = RH.dach_block(E); P = [[z, R_S, 0] for z in np.arange(1.25, E["z_traufe"], 0.5)]
    kd, bel = BT.kegeldach_teile(KD, 0.0, 0.0, P)
    pruef(kd is not None, f"kegeldach_teile baut das Huellendach ({bel[0]['element'][:120] if bel else ''})")
    if kd:
        top = max(t.bounding_box()[5] for t in kd[1]); pruef(abs(top - E["z_spitze"]) < 0.3, f"Dach bis z {top:.2f} (Spitze {E['z_spitze']})")
    with tempfile.TemporaryDirectory() as td:
        kp = os.path.join(td, "k.json"); json.dump(dict(haufen=[dict(id="r", form="rund", kreis=dict(x=0.0, y=0.0, r=R_S), profil=P, dach=KD, kasten=[-2, -2, 1, 2, 2, 11], mass_quelle="foto_umriss")]), open(kp, "w"))
        k2, bel2 = BT.drehkoerper_aus_wolkenrest(M.cube((1, 1, 1)).translate((-20, -20, 0)), kp)
        pruef(abs(k2.bounding_box()[5] - E["z_spitze"]) < 0.3 and any("Kegeldach" in b["element"] for b in bel2), f"Rundkoerper + Dach bis z {k2.bounding_box()[5]:.2f}")
except ImportError as e_:
    pruef(False, f"Generator nicht pruefbar: {e_}")

print("FEHLER:", len(fehler)) if fehler else print("alle Pruefungen bestanden")
sys.exit(1 if fehler else 0)
