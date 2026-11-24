#!/usr/bin/env python3
"""kameras_nachtragen.py <objekt.json> <sparse-neu> [--bilder ORDNER] [--ueberschreiben] - nachregistrierte Fotos als Messkameras K-<foto>.json in den MODELLRAHMEN bringen.

Teil der Stufe `seiten` (16.11.2026): tools/seiten_luecken.py laedt/registriert Fotos fuer ungesehene Waende (zusatzfotos_registrieren.py registrieren --je-bild).
Deren Posen liegen im SfM-Rahmen. Bruecke ohne eigene Ausrichtungsdatei: die Rekonstruktion <sparse-neu> enthaelt auch die alten Referenzbilder, fuer die es schon
K-Dateien im Modellrahmen gibt -> Aehnlichkeitsabbildung (Massstab, Drehung, Verschiebung; Umeyama) aus den Kamerastandorten der gemeinsamen Bilder,
angewandt auf die neuen Kameras. Pixelmassstab: SfM-Bild (verkleinert) -> Originalfoto (f, cx, cy x Breite_orig / Breite_sfm).
Neue Fotos, die nicht im fotos_dir liegen (Downloads), werden dorthin verlinkt (Name wie im SfM), damit alle Werkzeuge sie finden.
Ausgabe: messprotokoll/K-<foto>.json mit kamera {rvec, t, f_px, cx, cy, k1, quelle, inlier}, Bericht audit/kameras_nachtragen.json (Restfehler der Abbildung,
je vorhandener K-Datei eines neuen Fotos der Standortunterschied = Gegenprobe). Vorhandene Kameras bleiben (ausser --ueberschreiben).
ACHTUNG 'gegenprobe' (23.11.2026, Kette 1122q: 327 neu, gegenprobe 0): sie vergleicht NUR Fotos, die schon eine K-Datei hatten - 0 heisst "keine Doppelbestimmung
widerspricht", NICHT "die neuen Kameras sind geprueft". Die neuen Posen prueft erst tools/kameras_nachtragen_tor.py (plausibel + am Modell nachgezogen, sonst gesperrt).
  /media/oem/scan/venv-colmap/bin/python -I tools/kameras_nachtragen.py modelle/<objekt>/objekt.json <ziel>/lg/sparse_handy/0 --bilder <ziel>/roh
"""
import sys, os, json, glob, argparse, numpy as np, cv2


def umeyama(A, B):
    ma, mb = A.mean(0), B.mean(0); a, b = A - ma, B - mb; U, S, Vt = np.linalg.svd(b.T @ a / len(A)); d = np.sign(np.linalg.det(U @ Vt)); D = np.diag([1, 1, d]); R = U @ D @ Vt; s = (S * np.diag(D)).sum() / (a ** 2).sum(1).mean()
    return s, R, mb - s * R @ ma


# 24.11.2026 (Kette 1122zb, schwabentor-1122): EINE Altkamera lag im SfM ~60 000 Einheiten (~600 km) weg - die Mittelwert-Abbildung (Umeyama auf ALLEN) kippte auf
# Massstab 0,0017 statt ~10,1, Restfehler Median 20 m; die 3 Ausreisser-Runden konnten das nicht mehr retten. Alle 173 neuen Kameras landeten auf dem Turmmittelpunkt
# [1,4 14,0 2,1], 21 davon bestanden danach sogar das Tor ('vertrauen') und sahen KEINE Wand -> 29,6 min Nachholen ohne Nutzen. Darum: Start auf dem KERN (je Rahmen
# Abstand zum koordinatenweisen Median <= Median der Abstaende: die innere Haelfte, Ausreisser jeder Groesse ohne Einfluss), dann Inlier-Runden auf allen;
# danach GUELTIGKEITS-TOR: K-Dateien der Referenzbilder sind aus DEMSELBEN SfM abgeleitet (kameras_aus_buendel) -> Rest ~0 (gemessen 0,00 m in 6 Laeufen);
# Median > ABB_MAX_REST_M oder < ABB_MIN_ANTEIL der gemeinsamen Kameras im Konsens = Abbildung unbrauchbar -> nichts schreiben, rc 4 (Skript bricht ab, Fehlschlag-Marke).
ABB_MAX_REST_M = 0.5      # ANNAHME: Lagefehler Modell/LoD2 (~0,5 m, seiten_luecken.NACHBAR_VOR_M); weit ueber dem gemessenen Rest 0,00 m, weit unter dem Fehlfall 20 m
ABB_MIN_ANTEIL = 0.5      # Mehrheit der gemeinsamen Kameras muss die Abbildung tragen (sonst passen zwei Rahmen nicht zusammen)


def abbildung_robust(A, B, runden=4):
    """Aehnlichkeit A (SfM) -> B (Modell) robust gegen einzelne weit entfernte Ausreisser. -> (s, R, t, gut, rest)."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    da = np.linalg.norm(A - np.median(A, 0), axis=1); db = np.linalg.norm(B - np.median(B, 0), axis=1)
    gut = (da <= np.median(da)) & (db <= np.median(db))
    if gut.sum() < 3: gut = da <= np.median(da)
    for _ in range(runden):
        s, R, t = umeyama(A[gut], B[gut]); rest = np.linalg.norm((s * (R @ A.T).T + t) - B, axis=1)
        neu = rest < max(3 * np.median(rest[gut]), 0.3)
        if neu.sum() < 3 or (neu == gut).all(): break
        gut = neu
    s, R, t = umeyama(A[gut], B[gut]); rest = np.linalg.norm((s * (R @ A.T).T + t) - B, axis=1)
    return s, R, t, gut, rest


def abbildung_tor(gut, rest, max_rest=ABB_MAX_REST_M, min_anteil=ABB_MIN_ANTEIL):
    """-> (ok, grund). Gueltigkeits-Tor der Abbildung SfM -> Modell (siehe oben)."""
    med = float(np.median(rest[gut])) if gut.any() else float("inf"); ant = float(gut.mean()) if len(gut) else 0.0
    if med > max_rest: return False, f"Restfehler Median {med:.2f} m > {max_rest} m"
    if ant < min_anteil: return False, f"nur {gut.sum()} von {len(gut)} gemeinsamen Kameras ({ant:.0%}) im Konsens < {min_anteil:.0%}"
    return True, ""


def main():
    import pycolmap
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("sparse"); ap.add_argument("--bilder", help="Ordner mit den Originalen der neuen Fotos (z. B. <ziel>/roh)"); ap.add_argument("--ueberschreiben", action="store_true"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"]); mp = os.path.join(od, "messprotokoll"); rec = pycolmap.Reconstruction(a.sparse)
    def kdatei(n): return os.path.join(mp, "K-" + os.path.splitext(n)[0] + ".json")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kamera_rahmen as KR; ST = KR.aktuell(mp)
    def kam(n):                                                           # 23.11.2026: Anker nur im gueltigen Rahmen (kamera_rahmen.py; 1122q-Kameras im alten Rahmen verzogen die Abbildung)
        if not os.path.exists(kdatei(n)): return None
        k = json.load(open(kdatei(n))).get("kamera"); return k if isinstance(k, dict) and "rvec" in k and not KR.veraltet(k, mp, kdatei(n), ST) else None
    alt_s, alt_m, neu = [], [], []
    for im in rec.images.values():
        if not im.has_pose: continue
        cw = im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world; R = np.array(cw.rotation.matrix()); t = np.array(cw.translation); C = -R.T @ t; k = kam(im.name)
        if k is not None: Rk = cv2.Rodrigues(np.array(k["rvec"]))[0]; alt_s.append(C); alt_m.append(-Rk.T @ np.array(k["t"]))
        neu.append((im, R, C, k))
    alt_s, alt_m = np.array(alt_s), np.array(alt_m)
    if len(alt_s) < 10: print("zu wenige gemeinsame Bilder mit K-Datei"); return 2
    s, Ra, ta, gut, rest = abbildung_robust(alt_s, alt_m)               # Ausreisser (falsch registrierte / weit entfernte Altkameras) ohne Einfluss, siehe abbildung_robust
    print(f"Abbildung SfM -> Modell aus {gut.sum()} von {len(gut)} gemeinsamen Kameras: Massstab {s:.4f}, Restfehler Median {np.median(rest[gut]):.2f} m, p90 {np.percentile(rest[gut], 90):.2f} m")
    bericht = dict(gemeinsam=int(gut.sum()), massstab=float(s), rest_median_m=float(np.median(rest[gut])), neu=[], gegenprobe=[])
    ok_a, grund_a = abbildung_tor(gut, rest)
    au = os.path.join(root, obj.get("audit", os.path.join(od, "audit"))); bericht["abbildung_ok"] = ok_a
    if not ok_a:                                                          # nichts schreiben: jede neue Kamera laege falsch (1122zb: alle auf einem Punkt im Turm)
        bericht["abbildung_fehler"] = grund_a; json.dump(bericht, open(os.path.join(au, "kameras_nachtragen.json"), "w"), indent=1)
        print(f"FEHLER: ABBILDUNG SfM -> Modell UNBRAUCHBAR ({grund_a}) - KEINE K-Datei geschrieben, {sum(1 for x in neu if x[3] is None)} neue Kameras NICHT nachgetragen "
              f"(nicht gerechnet: kamera_verfeinern, kameras_tor, Wiederholung). Ursache suchen: Ankerkameras im falschen Rahmen? messprotokoll/RAHMEN.json", flush=True)
        return 4
    for im, R, C, k in neu:
        Cm = s * Ra @ C + ta; Rm = R @ Ra.T; stem = os.path.splitext(im.name)[0]
        if k is not None and not a.ueberschreiben:                         # vorhandene Kamera bleibt IMMER (16.11.2026: der Gesamtlauf ueberschrieb die am Modell nachgezogene Kamera von ov_0005 mit der schlechteren SfM-Pose)
            Rk = cv2.Rodrigues(np.array(k["rvec"]))[0]; dC = float(np.linalg.norm(Cm - (-Rk.T @ np.array(k["t"]))))
            if dC > 1.0 and not any(np.allclose(C, q) for q in alt_s[gut]): bericht["gegenprobe"].append(dict(foto=stem, standort_unterschied_m=round(dC, 2)))
            continue
        cam = rec.cameras[im.camera_id]; orig = (glob.glob(os.path.join(fd, stem + ".*")) or (glob.glob(os.path.join(a.bilder, stem + ".*")) if a.bilder else []))
        if not orig: continue
        if not orig[0].startswith(fd): ziel = os.path.join(fd, os.path.basename(orig[0])); os.path.lexists(ziel) or os.symlink(os.path.realpath(orig[0]), ziel); orig = [ziel]
        b = cv2.imread(orig[0])
        if b is None: continue
        f = b.shape[1] / cam.width; p = list(cam.params); K = dict(rvec=cv2.Rodrigues(Rm)[0].ravel().tolist(), t=(-Rm @ Cm).tolist(), f_px=p[0] * f, cx=p[1] * f, cy=p[2] * f, k1=float(p[3]) if len(p) > 3 else 0.0,
                                                                 standort=Cm.tolist(), standort_xyz=[round(float(x), 3) for x in Cm], quelle=f"nachregistriert ({os.path.basename(os.path.dirname(os.path.abspath(a.sparse)))}), Abbildung aus {int(gut.sum())} gemeinsamen Kameras, Rest {np.median(rest[gut]):.2f} m", punkte3d=int(im.num_points3D), rahmen=(ST or {}).get("id"))
        d = json.load(open(kdatei(im.name))) if os.path.exists(kdatei(im.name)) else dict(foto=stem, seite="unbekannt", punkte={}, linien={})
        if isinstance(d.get("kamera"), dict) and "rvec" in d["kamera"] and not KR.veraltet(d["kamera"], mp, kdatei(im.name), ST): d["kamera_vorher"] = d["kamera"]
        elif isinstance(d.get("kamera"), dict): d.pop("kamera_vorher", None)          # alter Rahmen: nicht als Rueckfall aufheben (kameras_nachtragen_tor.sperren stellte kamera_vorher wieder her)
        d["kamera"] = K; json.dump(d, open(kdatei(im.name), "w"), indent=1); bericht["neu"].append(dict(foto=stem, standort=[round(float(v), 1) for v in Cm], f_px=round(K["f_px"]), punkte3d=int(im.num_points3D)))
    au = os.path.join(root, obj.get("audit", os.path.join(od, "audit"))); json.dump(bericht, open(os.path.join(au, "kameras_nachtragen.json"), "w"), indent=1)
    print(f"{len(bericht['neu'])} neue Messkameras geschrieben; Gegenprobe (vorhandene Kamera weicht > 1 m ab): {bericht['gegenprobe'][:6]}")
    for e in bericht["neu"]: print("  ", e["foto"][-28:], e["standort"], "f", e["f_px"], "Punkte", e["punkte3d"])


if __name__ == "__main__":
    sys.exit(main())
