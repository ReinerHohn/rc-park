#!/usr/bin/env python3
"""sfm_db_variante.py <quelle.db> <ziel.db> [--kamera-je-clip] [--priors behalten|loeschen|exif --fotos <ordner>] [--bildliste <datei> --nur fotos|video|alle]
Kopie einer COLMAP-Datenbank fuer Mapper-Versuche vorbereiten (19.11.2026, modelle/GLOBALER_MAPPER_STABIL.md). Die Quelle bleibt unangetastet.
  --kamera-je-clip  Videobilder '<clip>__vf_NNN' eines Clips (gleiche Breite/Hoehe) teilen sich EINE Kamera (ANNAHME: Clip zoomt nicht; Pruefung ueber
                    Brennweiten-Streuung in tools/mapper_bewerten.py clip_f_cv). Verwaiste Kameras werden geloescht.
  --priors loeschen alle Kameras auf Schaetzung 1,2 x max(Breite, Hoehe) und source=GUESS (2): der view_graph_calibrator schaetzt dann JEDE Brennweite selbst.
                    Anlass: pycolmap 4.2.1 schrieb fuer 47 Martinstor-Fotos EXIF-Prioren von bis zu 8,7 Mio px (FocalPlaneXResolution-Fehler, Zuschnitt-Diagonale);
                    Kameras mit Prior werden im Kalibrator NICHT optimiert (SetParameterBlockConstant) -> Gift fuer Posen und GPS-Tor.
  --priors exif     Prior nur, wenn er sauber herleitbar ist: Bildbreite = EXIF-Originalbreite (kein Zuschnitt/Verkleinerung) und f_mm x Pixel/mm (FocalPlaneXResolution)
                    oder f35 x Diagonale/43,27 mm ergibt f/Breite in 0,5..5; sonst GUESS. Quelle source=EXIF (3). Mehrdeutige Zuschnitte -> tools/brennweite_waehlen.py (GPS).
  --bildliste       Namensliste fuer --GlobalMapper.image_list_path (fotos = keine Videobilder, video = nur Videobilder).
  --loeschen REGEX  Bilder samt Merkmalen/Paaren aus der Kopie entfernen (z.B. '_360\\.' fuer Mapillary-Panoramen, 'vorschau' fuer 1024-px-Vorschauen).
Alte Datenbanken (pycolmap 4.2.1, Spalte prior_focal_length statt source) werden erkannt.
Modell bleibt SIMPLE_RADIAL (params f, cx, cy, k); nur f und source werden geaendert."""
import sys, os, re, shutil, sqlite3, argparse, collections, math
import numpy as np


def exif_prior(pfad):
    """f_px oder None (nur eindeutige Faelle, siehe Kopf). Liefert (f_px, quelle)."""
    from PIL import Image
    try: im = Image.open(pfad); ex = im.getexif(); sub = ex.get_ifd(0x8769)
    except Exception: return None, "kein EXIF"
    W, H = im.size; rat = lambda v: float(v) if not isinstance(v, tuple) else float(v[0]) / float(v[1])
    f_mm = rat(sub[0x920A]) if 0x920A in sub and sub[0x920A] else None; f35 = float(sub[0xA405]) if 0xA405 in sub and sub[0xA405] else None
    ew = sub.get(0xA002); eh = sub.get(0xA003)
    if not f_mm: return None, "keine Brennweite"
    if ew and int(ew) != W and int(eh or 0) != W: return None, f"Bild {W} px, EXIF-Original {ew} px (Zuschnitt/Verkleinerung mehrdeutig)"
    f = None; q = ""
    if 0xA20E in sub and sub.get(0xA210, 2) in (2, 3, 4) and rat(sub[0xA20E]) > 0:
        f = f_mm * rat(sub[0xA20E]) / {2: 25.4, 3: 10.0, 4: 1.0}[sub.get(0xA210, 2)]; q = "f_mm x Pixel/mm"
        if ew and int(ew) != W: f *= W / int(ew)
    elif f35:
        f = f35 / 43.27 * math.hypot(W, H); q = "f35 x Diagonale"
    if f is None: return None, "weder Pixelgroesse noch f35"
    if not (0.5 <= f / W <= 5): return None, f"f/Breite {f / W:.2f} unplausibel ({q})"
    return f, q


def rig_schema(c):
    """COLMAP 4.x-Datenbank mit rigs/frames/frame_data (jedes Bild = ein Frame in einem Ein-Kamera-Rig)."""
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='frame_data'").fetchone())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("quelle"); ap.add_argument("ziel"); ap.add_argument("--kamera-je-clip", action="store_true")
    ap.add_argument("--priors", choices=["behalten", "loeschen", "exif"], default="behalten"); ap.add_argument("--fotos", default="")
    ap.add_argument("--bildliste", default=""); ap.add_argument("--nur", choices=["fotos", "video", "alle"], default="alle"); ap.add_argument("--loeschen", default="", help="Regex: Bilder samt Merkmalen/Paaren aus der Kopie entfernen")
    a = ap.parse_args()
    if os.path.abspath(a.quelle) == os.path.abspath(a.ziel): sys.exit("Quelle und Ziel gleich - Quelle bleibt unangetastet")
    shutil.copyfile(a.quelle, a.ziel); c = sqlite3.connect(a.ziel)
    bericht = collections.Counter()
    if a.loeschen:   # Bilder samt Merkmalen/Paaren entfernen (z.B. 360-Grad-Panoramen 'mapillary_neu__sv_NN_360': kein Lochkameramodell -> vergiften Kalibrierung und Posen)
        weg = [(iid, n) for iid, n in c.execute("SELECT image_id, name FROM images") if re.search(a.loeschen, n)]
        for iid, n in weg:
            c.execute("DELETE FROM keypoints WHERE image_id=?", (iid,)); c.execute("DELETE FROM descriptors WHERE image_id=?", (iid,))
            for tab in ("matches", "two_view_geometries"):   # pair_id = id1 * 2147483647 + id2 (id1 < id2)
                c.execute(f"DELETE FROM {tab} WHERE pair_id / 2147483647 = ? OR pair_id % 2147483647 = ?", (iid, iid))
            c.execute("DELETE FROM images WHERE image_id=?", (iid,))
            if rig_schema(c):   # COLMAP 4.x: frame_data(data_id=image_id) -> frames -> rigs; pose_priors(corr_data_id=image_id)
                for fid, in c.execute("SELECT frame_id FROM frame_data WHERE data_id=? AND sensor_type=0", (iid,)).fetchall():
                    c.execute("DELETE FROM frame_data WHERE frame_id=?", (fid,)); c.execute("DELETE FROM frames WHERE frame_id=?", (fid,))
                c.execute("DELETE FROM pose_priors WHERE corr_data_id=? AND corr_sensor_type=0", (iid,))
        bericht[f"Bilder geloescht ({a.loeschen})"] = len(weg)
    bilder = c.execute("SELECT image_id, name, camera_id FROM images").fetchall()
    spalten = [r[1] for r in c.execute("PRAGMA table_info(cameras)")]; alt = "source" not in spalten   # alte Datenbanken (pycolmap 4.2.1): prior_focal_length 0/1 statt source
    sq = "CASE WHEN prior_focal_length THEN 3 ELSE 2 END" if alt else "source"
    kam = {r[0]: list(r[1:]) for r in c.execute(f"SELECT camera_id, model, width, height, params, {sq} FROM cameras")}
    def setze(cid, p, s):
        if alt: c.execute("UPDATE cameras SET params=?, prior_focal_length=? WHERE camera_id=?", (p, 1 if s == 3 else 0, cid))
        else: c.execute("UPDATE cameras SET params=?, source=? WHERE camera_id=?", (p, s, cid))
    if a.priors != "behalten":
        pf = {}
        if a.priors == "exif":
            if not a.fotos: sys.exit("--priors exif braucht --fotos")
            import glob; pf = {os.path.basename(x): x for x in glob.glob(os.path.join(a.fotos, "**", "*"), recursive=True)}
        for iid, name, cid in bilder:
            m, w, h, params, src = kam[cid]; p = np.frombuffer(params, dtype=np.float64).copy(); f_neu = 1.2 * max(w, h); s_neu = 2
            if a.priors == "exif" and "__vf_" not in name and name in pf:
                f, q = exif_prior(pf[name])
                if f: f_neu, s_neu = f, 3; bericht["prior aus EXIF"] += 1
                else: bericht["GUESS: " + q.split(" (")[0][:40]] += 1
            if src == 3 and s_neu == 2: bericht["alter EXIF-Prior entfernt"] += 1
            p[0] = f_neu; setze(cid, p.tobytes(), s_neu); kam[cid][3] = p.tobytes(); kam[cid][4] = s_neu
    if a.kamera_je_clip:
        gruppen = collections.defaultdict(list)
        for iid, name, cid in bilder:
            mm = re.match(r"(.+)__vf_(\d+)\.", os.path.basename(name))
            if mm: gruppen[(mm.group(1), kam[cid][1], kam[cid][2])].append((iid, cid))
        rs = rig_schema(c)
        for (clip, w, h), L in gruppen.items():
            ziel_cid = L[0][1]
            if rs: ziel_rig = c.execute("SELECT rig_id FROM rigs WHERE ref_sensor_id=? AND ref_sensor_type=0", (ziel_cid,)).fetchone()
            for iid, cid in L[1:]:
                c.execute("UPDATE images SET camera_id=? WHERE image_id=?", (ziel_cid, iid))
                if rs:   # Lehre 19.11. (Absturz 'Camera 466 from rig 466 not found'): frame_data.sensor_id und frames.rig_id muessen mitziehen
                    c.execute("UPDATE frame_data SET sensor_id=? WHERE data_id=? AND sensor_type=0", (ziel_cid, iid))
                    if ziel_rig: c.execute("UPDATE frames SET rig_id=? WHERE frame_id IN (SELECT frame_id FROM frame_data WHERE data_id=? AND sensor_type=0)", (ziel_rig[0], iid))
            bericht["Clips mit gemeinsamer Kamera"] += 1; bericht["Videobilder umgehaengt"] += len(L) - 1
        n = c.execute("DELETE FROM cameras WHERE camera_id NOT IN (SELECT camera_id FROM images)").rowcount; bericht["verwaiste Kameras geloescht"] += n
        if rs:
            c.execute("DELETE FROM frames WHERE rig_id IN (SELECT rig_id FROM rigs WHERE ref_sensor_type=0 AND ref_sensor_id NOT IN (SELECT camera_id FROM cameras))")
            bericht["verwaiste Rigs geloescht"] += c.execute("DELETE FROM rigs WHERE ref_sensor_type=0 AND ref_sensor_id NOT IN (SELECT camera_id FROM cameras)").rowcount
    c.commit()
    if a.bildliste:
        namen = [n for _, n, _ in bilder if a.nur == "alle" or (("__vf_" in n) == (a.nur == "video"))]
        open(a.bildliste, "w").write("\n".join(sorted(namen)) + "\n"); bericht[f"Bildliste ({a.nur})"] = len(namen)
    print("Bilder:", len(bilder), "Kameras:", c.execute("SELECT COUNT(*) FROM cameras").fetchone()[0], "| source:", dict(collections.Counter(r[0] for r in c.execute(f"SELECT {sq} FROM cameras"))))
    for k, v in sorted(bericht.items()): print(f"  {k}: {v}")
    c.close()


if __name__ == "__main__": main()
