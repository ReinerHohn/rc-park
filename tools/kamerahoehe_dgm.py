#!/usr/bin/env python3
"""kamerahoehe_dgm.py --modell <sparse> --bilder <fotos> --ursprung <lat> <lon> (--m_je_einheit X | --vereinen <vereinen.json> --rahmen rahmen_a)
                     [--lot_modell <sparse>] [--matrix <json> --schluessel B_nach_A] [--aus <bericht.json>]

KAMERAHOEHE GEGEN DAS GELAENDE (DGM1) AN DER GPS-LAGE DER KAMERA (24.11.2026, Kette schwabentor-1122z, Teil 1 = OST-Teil laut seiten_konvention).
BEFUND: die 45 Kameras von Teil 1 (dichte Wolke) standen nach der Wandbindung im Median ~12 m (nach der Hoehenkorrektur +6,5 m ~18 m) ueber dem Boden von Teil 0,
Teil-0-Kameras bei 1,5 m. Frage: echt (erhoehter Standort) oder Fehler (Massstab/Kippung)?
GEMESSEN (nur gelesen):
  - ECHT: zwei Gruppen eigener Fotos 23.11. - Strasse 15:38-15:46 (DGM1 an der GPS-Lage 283-286 m, EXIF-Hoehe 325-340 m ellipsoidisch) und Schlossberg-Hang
    15:48-15:51 (DGM1 303-318 m, EXIF 358-368 m) plus Online-/Commons-Bilder "Blick vom Schlossberg auf das Schwabentor". DGM und EXIF-Hoehe sagen unabhaengig
    20-35 m Hoehenunterschied; die Hang-Kameras blicken im eigenen Rahmen von Teil 1 nach UNTEN (Pitch -4..-14 Grad), die Strassenkameras nach oben (+6..+20 Grad).
  - Im EIGENEN Rahmen von Teil 1 (Lot aus den Bild-Achsen, GPS-Massstab) stimmen die Hoehenunterschiede mit dem DGM (Strasse 7,2 m -> Hang 40,8 m = 33,6 m; DGM 33,4 m).
  - NACH DER WANDBINDUNG (Kippung 10 Grad aus den B-Waenden um den Fusspunkt der B-Wolke, Massstab 0,882) sind sie auf ~2/3 GESTAUCHT (Steigung Modell/DGM ~0,6):
    die 60-85 m entfernten Hang-Kameras sinken durch die Kippung um ~10 m. Hoehe des Turms (z_saeulen) bleibt davon unberuehrt, die Kamerageometrie von Teil 1
    passt aber nicht mehr zum Gelaende -> Kippung bzw. Massstab der Bindung sind fuer die KAMERAS nicht belegt (Teilmodell gebogen oder Wand-Lot von B falsch).
PRUEFUNG (generisch, jedes Teilmodell/jede Bindung): Kameras mit EXIF-GPS -> erwartete Hoehe = DGM1(GPS) + HAND_M; Modellhoehe = (Zentrum . Lot) * m_je_einheit
  (nach --matrix). Verglichen werden nur UNTERSCHIEDE (Versatz frei, Handy-GPS traegt keine Hoehe, das DGM schon): Theil-Sen-Steigung Modell/DGM ueber Paare mit
  >= PAAR_MIN_M DGM-Unterschied, Rest (MAD) nach Versatz. Spanne der DGM-Hoehen < SPANNE_MIN_M -> Steigung 'nicht messbar' (ebenes Umfeld; Rest bleibt Probe).
  ok = Steigung in [STEIG_MIN, STEIG_MAX] und Rest <= REST_MAX_M. Erhoehte Kameras (DGM > ERHOEHT_M ueber dem Objektboden) werden als ECHT erhoeht gemeldet.
rc 0 = stimmig, 3 = Hoehen gestaucht/gestreckt oder Rest zu gross, 2 = zu wenig Kameras mit GPS/DGM. Test: tools/test_kamerahoehe_dgm.py.
Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap; Kern ohne pycolmap testbar).
"""
import os, sys, json, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)

HAND_M = 1.6          # ANNAHME: Kamera in Handhoehe ueber dem DGM (Fenster/Balkon -> Rest)
PAAR_MIN_M = 5.0      # ANNAHME: Steigung nur aus Paaren mit >= 5 m DGM-Unterschied (DGM1 +-0,5 m, GPS-Lage +-5 m am Hang ~ +-2 m)
SPANNE_MIN_M = 8.0    # ANNAHME: darunter ist das Umfeld zu eben fuer eine Steigung
STEIG_MIN, STEIG_MAX = 0.80, 1.25   # ANNAHME: Massstab-/Kippfehler unter 20 % gelten als nicht nachweisbar (GPS-Lage am Hang)
REST_MAX_M = 4.0      # ANNAHME: Median-Abweichung nach Versatz (GPS-Lage +-5 m am 30-%-Hang ~ 1,5 m, Hand/Balkon)
ERHOEHT_M = 5.0       # erwartete Hoehe > 5 m ueber dem Objektboden = erhoehter Standort (Hang, Schlossberg)
MIN_KAMERAS = 5


def vergleich(h_modell, h_erwartet):
    """h_modell, h_erwartet: Meter (Versatz beliebig). -> dict(n, spanne_m, steigung, versatz_m, rest_m, ok, urteil)."""
    hm = np.asarray(h_modell, float); he = np.asarray(h_erwartet, float); g = np.isfinite(hm) & np.isfinite(he); hm, he = hm[g], he[g]; n = len(hm)
    if n < MIN_KAMERAS: return dict(n=n, ok=None, urteil=f"zu wenig Kameras mit GPS + DGM ({n} < {MIN_KAMERAS})")
    sp = float(np.percentile(he, 90) - np.percentile(he, 10)); i, j = np.triu_indices(n, 1); d = he[j] - he[i]; m = np.abs(d) >= PAAR_MIN_M
    st = float(np.median((hm[j] - hm[i])[m] / d[m])) if (sp >= SPANNE_MIN_M and m.sum() >= 3) else None
    vs = float(np.median(hm - he)); rest = float(np.median(np.abs(hm - he - vs)))
    if st is not None:                                                      # Rest gegen die geschaetzte Steigung (sonst misst der Rest nur die Stauchung)
        c = float(np.median(hm - st * he)); rest = float(np.median(np.abs(hm - st * he - c)))
    gr = []
    if st is not None and not (STEIG_MIN <= st <= STEIG_MAX): gr.append(f"Hoehen {'gestaucht' if st < 1 else 'gestreckt'}: Steigung Modell/DGM {st:.2f} (erlaubt {STEIG_MIN}-{STEIG_MAX})")
    if rest > REST_MAX_M: gr.append(f"Rest {rest:.1f} m > {REST_MAX_M} m")
    ok = not gr
    u = (f"stimmig: {n} Kameras, DGM-Spanne {sp:.1f} m, Steigung {'nicht messbar' if st is None else f'{st:.2f}'}, Rest {rest:.1f} m" if ok else "; ".join(gr) + f" ({n} Kameras, DGM-Spanne {sp:.1f} m)")
    return dict(n=n, spanne_m=round(sp, 2), steigung=None if st is None else round(st, 3), versatz_m=round(vs, 2), rest_m=round(rest, 2), ok=ok, urteil=u)


def erwartete_hoehen(ll, ursprung, dgm=None):
    """ll: Liste (lat, lon) -> DGM1-Hoehe + HAND_M ueber dem DGM am Ursprung (Objektboden). dgm(E, N) -> Hoehe; Standard dom1_kachel DGM1."""
    from bauwerk_pipeline import utm32
    if dgm is None:
        from dom1_kachel import dom1_hoehe
        dgm = lambda E, N: dom1_hoehe(E, N, art="dgm1")
    z0 = float(dgm(*utm32(*ursprung)[:2])); return np.array([float(dgm(*utm32(la, lo)[:2])) + HAND_M - z0 for la, lo in ll]), z0


def modell_hoehen(modell, lot_modell=None, matrix=None):
    """-> (Namen, Hoehe in Modelleinheiten entlang des Lots von lot_modell, Pitch Grad). matrix (4x4) bildet --modell in den Rahmen von lot_modell ab."""
    import pycolmap
    from seiten_gps_vereinen import lot_aus_bild_achsen
    r = pycolmap.Reconstruction(modell); ims = [im for im in r.images.values() if im.has_pose]
    C = np.array([im.projection_center() for im in ims]); V = np.array([im.cam_from_world().rotation.matrix()[2] for im in ims])
    if matrix is not None:
        M = np.asarray(matrix, float); C = (M[:3, :3] @ C.T).T + M[:3, 3]; V = (M[:3, :3] @ V.T).T; V /= np.linalg.norm(V, axis=1, keepdims=True)
    if lot_modell and lot_modell != modell:
        rl = pycolmap.Reconstruction(lot_modell); up = lot_aus_bild_achsen([im.cam_from_world().rotation.matrix() for im in rl.images.values() if im.has_pose])
    else:
        up = lot_aus_bild_achsen([im.cam_from_world().rotation.matrix() for im in ims])
        if matrix is not None: up = np.asarray(matrix, float)[:3, :3] @ up; up /= np.linalg.norm(up)
    return [im.name for im in ims], C @ up, np.degrees(np.arcsin(np.clip(V @ up, -1, 1)))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--modell", required=True); ap.add_argument("--bilder", required=True)
    ap.add_argument("--ursprung", nargs=2, type=float, required=True); ap.add_argument("--m_je_einheit", type=float)
    ap.add_argument("--vereinen"); ap.add_argument("--rahmen", default="rahmen_a"); ap.add_argument("--lot_modell")
    ap.add_argument("--matrix"); ap.add_argument("--schluessel", default="B_nach_A"); ap.add_argument("--aus")
    a = ap.parse_args(argv)
    mj = a.m_je_einheit or (json.load(open(a.vereinen))[a.rahmen]["massstab"] if a.vereinen else None)
    if not mj: print("FEHLER: --m_je_einheit oder --vereinen noetig"); return 2
    M = json.load(open(a.matrix))[a.schluessel] if a.matrix else None
    from seiten_gps_vereinen import gps_roh
    namen, h, pitch = modell_hoehen(a.modell, a.lot_modell, M); roh = gps_roh(a.bilder, namen)
    k = [i for i, n in enumerate(namen) if n in roh]
    if len(k) < MIN_KAMERAS: print(f"zu wenig Kameras mit GPS ({len(k)})"); return 2
    he, z0 = erwartete_hoehen([roh[namen[i]] for i in k], a.ursprung); hm = h[k] * mj
    e = vergleich(hm, he); e.update(dgm_ursprung_m=round(z0, 2), erhoeht_echt=int((he > ERHOEHT_M).sum()),
                                    pitch_erhoeht_grad=round(float(np.median(pitch[k][he > ERHOEHT_M])), 1) if (he > ERHOEHT_M).any() else None,
                                    pitch_strasse_grad=round(float(np.median(pitch[k][he <= ERHOEHT_M])), 1) if (he <= ERHOEHT_M).any() else None,
                                    kameras=[dict(name=namen[i], dgm_m=round(float(he[j]), 1), modell_m=round(float(hm[j]), 1), pitch=round(float(pitch[i]), 1)) for j, i in enumerate(k)])
    print(("KAMERAHOEHE STIMMIG: " if e["ok"] else "KAMERAHOEHE NICHT STIMMIG: ") + e["urteil"] +
          f"; erhoeht (DGM > {ERHOEHT_M:.0f} m): {e['erhoeht_echt']} Kameras, Pitch erhoeht {e['pitch_erhoeht_grad']} / Strasse {e['pitch_strasse_grad']} Grad")
    if a.aus: json.dump(e, open(a.aus, "w"), indent=1, ensure_ascii=False)
    return 0 if e["ok"] else (2 if e["ok"] is None else 3)


if __name__ == "__main__":
    sys.exit(main())
