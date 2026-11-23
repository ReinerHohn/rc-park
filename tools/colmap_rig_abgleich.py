#!/usr/bin/env python3
"""colmap_rig_abgleich.py  pruefen|angleichen|probe  --db <db.db> --sparse <SfM-Ordner> [--arbeit <ordner>]  -  Kamera/Rig/Frame einer COLMAP-Datenbank an eine Rekonstruktion angleichen.

WARUM (22.11.2026, Kette schwabentor-1120, Laeufe 1122c und 1122d): die Stufe seiten_luecken brach JEDES Mal nach ~44 min in
tools/zusatzfotos_lightglue.py einlesen -> pycolmap.triangulate_points ab:  "ValueError: [reconstruction.cc:327] Check failed: existing_frame.RigId() == frame.RigId()".
Ursache: das Referenzmodell (pipe/sfm/sparse/0, 623 Bilder) hat nur 328 Kameras - Videobilder teilen sich eine Kamera (Rig-ID = Kamera-ID), die Datenbank
(pipe/sfm/db.db, 798 Bilder) fuehrt dagegen je Bild eine eigene Kamera + einen eigenen trivialen Rig. 297 Bilder hingen im Modell an Kamera/Rig X, in der Datenbank an Y.
pycolmap 4.x (Reconstruction::Load beim Triangulieren) verlangt, dass jeder Frame im Modell denselben Rig hat wie in der Datenbank -> Absturz, sobald die Datenbank geladen ist
(0,03 min nach Beginn des Schritts, aber erst NACH ~44 min Merkmale/LightGlue). Ein Fehler der Zuordnung, nicht der neuen Fotos.
LOESUNG: angleichen(db, rec) schreibt die Zuordnung des MODELLS in die (Kopie der) Datenbank: images.camera_id, frames.rig_id, frame_data.sensor_id; fehlende Kamera-/Rig-Zeilen
werden aus dem Modell angelegt. Nur die Zuordnung, keine Merkmale/Matches (Indizes bleiben gleich). Nur auf KOPIEN anwenden - die Referenzdatenbank bleibt unberuehrt.
probe(db, sparse): SCHNELL SCHEITERN - Mini-Datenbank nur mit den Zuordnungstabellen (Kameras, Rigs, Frames, Bilder; keine Merkmale), angleichen, dann derselbe Aufruf
pycolmap.triangulate_points wie in einlesen -> derselbe Lade-Check in Sekunden statt nach 44 min. Exit: 0 = in Ordnung, 4 = Konflikt (pruefen) bzw. Probe gescheitert.
Umgebung: venv-colmap (`/media/oem/scan/venv-colmap/bin/python -I tools/colmap_rig_abgleich.py ...`); pruefen/angleichen brauchen pycolmap nur zum Lesen des Modells."""
import os, sys, sqlite3, argparse, shutil, tempfile
import numpy as np

ZUORDNUNG = ("cameras", "rigs", "rig_sensors", "frames", "frame_data", "images")


def _enum_int(x):
    return int(getattr(x, "value", x))


def _modell(rec):
    """image_id -> (name, camera_id, frame_id, rig_id) aus der Rekonstruktion."""
    out = {}
    for iid, im in rec.images.items():
        fid = int(im.frame_id); rig = int(rec.frames[fid].rig_id) if fid in rec.frames else None
        out[int(iid)] = (im.name, int(im.camera_id), fid, rig)
    return out


def fremde_kameras(con, rec, M=None):
    """Kamera-IDs, die im Modell UND in der Datenbank stehen, dort aber eine ANDERE Kamera bezeichnen -> {id: (modell_werte, db_werte, rest_bilder)}.
    WARUM (23.11.2026, Kette 1122r): das aus Seitenmodellen vereinte sparse/0 (tools/sfm_seiten_modelle.py modelle_zusammen) gibt einer Kamera, die in beiden Teilen
    getrennt ausgeglichen wurde, fuer den zweiten Teil die ID max(Modell)+1 = 822..824 - in der Datenbank sind 822..824 aber die Kameras der Videobilder vf_007..vf_009
    (822: 1920x1080, im Modell 1280x720). angleichen haengte die Modellbilder auf DB-Kamera 822 um -> triangulate_points: "[reconstruction.cc:303] Check failed:
    existing_camera.width == camera.width (1280 vs. 1920)"; bei 823/824 (gleiche Groesse) haetten die Videobilder still die Intrinsik der fremden Kamera bekommen.
    Fremd = Modell/Breite/Hoehe verschieden ODER die DB-Kamera traegt Bilder, die nicht im Modell sind, und keines der Modellbilder dieser Kamera sitzt in der DB auf ihr
    (geteilte Videokamera mit unregistrierten Frames ist dagegen dieselbe Kamera und bleibt). rest_bilder = DB-Bilder auf dieser ID, die nicht im Modell stehen."""
    M = M or _modell(rec)
    dbk = {c: (int(m), int(w), int(h)) for c, m, w, h in con.execute("select camera_id, model, width, height from cameras")}
    db_cam = dict(con.execute("select image_id, camera_id from images"))
    auf = {}
    for i, c in db_cam.items(): auf.setdefault(c, set()).add(i)
    modell_auf = {}
    for iid, (_, cam, _, _) in M.items(): modell_auf.setdefault(cam, set()).add(iid)
    out = {}
    for cam, ims in modell_auf.items():
        if cam not in dbk: continue
        c = rec.cameras[cam]; mw = (_enum_int(c.model), int(c.width), int(c.height)); rest = sorted(auf.get(cam, set()) - set(M))
        if mw != dbk[cam] or (rest and not (auf.get(cam, set()) & ims)): out[cam] = (mw, dbk[cam], rest)
    return out


def konflikte(dbp, rec):
    """Bilder, deren Name/Kamera/Frame/Rig in der Datenbank anders ist als im Modell, und Kamera-IDs, die in der DB eine fremde Kamera sind
    -> Liste von dict(name, art, modell, db)."""
    con = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    try:
        bild = {i: (n, c) for i, n, c in con.execute("select image_id, name, camera_id from images")}
        frame_von = {d: f for f, d in con.execute("select frame_id, data_id from frame_data where sensor_type=0")}
        rig_von = dict(con.execute("select frame_id, rig_id from frames"))
        fremd = fremde_kameras(con, rec)
    finally: con.close()
    out = [dict(name=f"Kamera {c}", art="Kamera-ID fremd belegt", modell=mw, db=dict(werte=dw, bilder_ausserhalb=len(r))) for c, (mw, dw, r) in sorted(fremd.items())]
    for iid, (name, cam, fid, rig) in _modell(rec).items():
        if iid not in bild: out.append(dict(name=name, art="Bild fehlt in der Datenbank", modell=iid, db=None)); continue
        if bild[iid][0] != name: out.append(dict(name=name, art="Name anders", modell=name, db=bild[iid][0])); continue
        if bild[iid][1] != cam: out.append(dict(name=name, art="Kamera anders", modell=cam, db=bild[iid][1]))
        f_db = frame_von.get(iid)
        if f_db != fid: out.append(dict(name=name, art="Frame anders", modell=fid, db=f_db))
        elif rig_von.get(f_db) != rig: out.append(dict(name=name, art="Rig anders", modell=rig, db=rig_von.get(f_db)))
    return out


def angleichen(dbp, rec):
    """Zuordnung des Modells in die Datenbank schreiben (nur Kopien!). -> Anzahl umgehaengter Bilder. Bild fehlt / Name anders -> ValueError (nicht reparierbar)."""
    k = konflikte(dbp, rec); hart = [x for x in k if x["art"] in ("Bild fehlt in der Datenbank", "Name anders", "Frame anders")]
    if hart: raise ValueError(f"{len(hart)} Bilder nicht angleichbar (z. B. {hart[0]}) - Datenbank gehoert nicht zu diesem Modell")
    if not k: return 0
    M = _modell(rec); con = sqlite3.connect(dbp)
    try:
        cams = {c for (c,) in con.execute("select camera_id from cameras")}; rigs = {r for (r,) in con.execute("select rig_id from rigs")}
        spalten = [r[1] for r in con.execute("pragma table_info(cameras)")]
        namen = {x["name"] for x in k}; n = 0
        for cam, (_, _, rest) in sorted(fremde_kameras(con, rec, M).items()):      # 23.11.2026: fremd belegte Kamera-ID (vereintes Seitenmodell) - DB-Bilder ausserhalb des Modells
            if rest:                                                                  # behalten IHRE Kamera unter neuer ID (Zeile kopiert, eigener trivialer Rig), dann bekommt die ID die Werte des Modells
                if con.execute("select count(*) from rig_sensors where sensor_id=? and sensor_type=0", (cam,)).fetchone()[0]:
                    raise ValueError(f"Kamera {cam} ist in der Datenbank Teil eines Mehrsensor-Rigs - fremde Belegung nicht automatisch loesbar")
                neu_c = max(cams | set(rec.cameras)) + 1; neu_r = max(rigs | set(rec.rigs)) + 1
                con.execute(f"insert into cameras ({','.join(spalten)}) select {','.join('?' if s == 'camera_id' else s for s in spalten)} from cameras where camera_id=?", (neu_c, cam)); cams.add(neu_c)
                con.execute("insert into rigs (rig_id, ref_sensor_id, ref_sensor_type) values (?,?,0)", (neu_r, neu_c)); rigs.add(neu_r)
                for iid in rest:
                    con.execute("update images set camera_id=? where image_id=?", (neu_c, iid))
                    for (fid,) in con.execute("select frame_id from frame_data where data_id=? and sensor_type=0", (iid,)).fetchall():
                        con.execute("update frames set rig_id=? where frame_id=?", (neu_r, fid))
                        con.execute("update frame_data set sensor_id=? where frame_id=? and data_id=? and sensor_type=0", (neu_c, fid, iid))
            c = rec.cameras[cam]
            con.execute("update cameras set model=?, width=?, height=?, params=? where camera_id=?", (_enum_int(c.model), int(c.width), int(c.height), np.asarray(c.params, dtype="<f8").tobytes(), cam))
            n += len(rest)
        for iid, (name, cam, fid, rig) in M.items():
            if name not in namen: continue
            if cam not in cams:
                c = rec.cameras[cam]; w = dict(camera_id=cam, model=_enum_int(c.model), width=int(c.width), height=int(c.height),
                                               params=np.asarray(c.params, dtype="<f8").tobytes(), prior_focal_length=int(bool(c.has_prior_focal_length)))
                sp = [s for s in spalten if s in w]; con.execute(f"insert into cameras ({','.join(sp)}) values ({','.join('?' * len(sp))})", [w[s] for s in sp]); cams.add(cam)
            if rig not in rigs:
                ref = rec.rigs[rig].ref_sensor_id; con.execute("insert into rigs (rig_id, ref_sensor_id, ref_sensor_type) values (?,?,?)", (rig, int(ref.id), _enum_int(ref.type))); rigs.add(rig)
            con.execute("update images set camera_id=? where image_id=?", (cam, iid))
            con.execute("update frames set rig_id=? where frame_id=?", (rig, fid))
            con.execute("update frame_data set sensor_id=? where frame_id=? and data_id=? and sensor_type=0", (cam, fid, iid)); n += 1
        con.commit()
    finally: con.close()
    rest = konflikte(dbp, rec)
    if rest: raise ValueError(f"nach dem Angleichen noch {len(rest)} Konflikte, z. B. {rest[0]}")
    return n


def mini_db(quelle, ziel):
    """Neue Datenbank (Schema der laufenden pycolmap-Version) nur mit den Zuordnungstabellen aus <quelle> (Spalten-Schnittmenge; Merkmale/Matches bleiben leer)."""
    import pycolmap
    if os.path.exists(ziel): os.remove(ziel)
    db = pycolmap.Database.open(ziel) if hasattr(pycolmap.Database, "open") else pycolmap.Database(ziel); db.close()
    con = sqlite3.connect(ziel, uri=True); con.execute("attach database ? as q", (f"file:{os.path.abspath(quelle)}?mode=ro",))      # Quelle nur lesend
    try:
        for t in ZUORDNUNG:
            if not con.execute("select 1 from q.sqlite_master where type='table' and name=?", (t,)).fetchone(): continue
            a = [(r[1], r[3]) for r in con.execute(f"pragma main.table_info({t})")]; b = {r[1] for r in con.execute(f"pragma q.table_info({t})")}
            sp = [s for s, nn in a if s in b or nn]; wert = [s if s in b else "0" for s, nn in a if s in b or nn]      # Pflichtspalte fehlt in der Quelle (neueres Schema, z. B. 'source' statt prior_focal_length) -> 0
            con.execute(f"insert into main.{t} ({','.join(sp)}) select {','.join(wert)} from q.{t}")
        con.commit()
    finally: con.close()


def probe(db_quelle, sparse, arbeit=None):
    """Lade-Check von pycolmap.triangulate_points auf einer Mini-Datenbank (nach angleichen) -> (ok, text). Sekunden; liest Quelle und Modell nur."""
    import pycolmap
    eigen = arbeit is None; arbeit = arbeit or tempfile.mkdtemp(prefix="rig_probe_")
    try:
        os.makedirs(arbeit, exist_ok=True); mdb = os.path.join(arbeit, "mini.db"); mini_db(db_quelle, mdb)
        rec = pycolmap.Reconstruction(sparse); vorher = konflikte(mdb, rec)
        try: n = angleichen(mdb, rec)
        except ValueError as e: return False, f"Angleichen unmoeglich: {e}"
        td = os.path.join(arbeit, "tri"); shutil.rmtree(td, ignore_errors=True); os.makedirs(td); bd = os.path.join(arbeit, "bilder"); os.makedirs(bd, exist_ok=True)
        try: pycolmap.triangulate_points(rec, mdb, bd, td, clear_points=True)
        except Exception as e: return False, f"triangulate_points scheitert trotz Angleichen ({type(e).__name__}: {str(e)[:200]})"
        return True, f"{len(vorher)} Zuordnungskonflikte Modell/Datenbank" + (f" (z. B. {vorher[0]['name']}: {vorher[0]['art']} Modell {vorher[0]['modell']} / DB {vorher[0]['db']}), {n} Bilder angeglichen" if vorher else "") + "; Lade-Check von triangulate_points bestanden"
    finally:
        if eigen: shutil.rmtree(arbeit, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("pruefen", "angleichen", "probe")); ap.add_argument("--db", required=True); ap.add_argument("--sparse", required=True); ap.add_argument("--arbeit")
    a = ap.parse_args(argv)
    if a.cmd == "probe":
        ok, t = probe(a.db, a.sparse, a.arbeit); print(("VORPRUEFUNG OK: " if ok else "VORPRUEFUNG GESCHEITERT: ") + t, flush=True); return 0 if ok else 4
    import pycolmap
    rec = pycolmap.Reconstruction(a.sparse)
    if a.cmd == "pruefen":
        k = konflikte(a.db, rec); print(f"{len(k)} Zuordnungskonflikte" + (f", z. B. {k[:3]}" if k else "")); return 4 if k else 0
    print(f"angeglichen: {angleichen(a.db, rec)} Bilder"); return 0


if __name__ == "__main__":
    sys.exit(main())
