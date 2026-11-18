#!/usr/bin/env python3
"""colmap_db_schema.py <db.db>  -  KOPIE einer COLMAP-Datenbank auf das Schema von pycolmap 4.2.1 (venv-colmap) zurueckfuehren.
18.11.2026 (Kaufhaus gk2h, Stufe seiten_luecken: "No registered database factory succeeded" / SQLite "SQL logic error"): der globale Mapper der Kette
(eigener Bau /media/oem/scan/colmap-build, Stand ce2b5ab 30.10.2026) schreibt die Kameratabelle neu: Spalte 'source' (CameraSource UNKNOWN 0, USER 1, GUESS 2,
EXIF 3, SINGLE_VIEW 4) und PRIMARY KEY(camera_id, source) statt 'prior_focal_length'. pycolmap 4.2.1 kann solche Datenbanken nicht oeffnen.
Rueckwandlung (wie COLMAP selbst alte Kameras liest, database_sqlite.cc: has_prior ? EXIF : GUESS): je camera_id die Zeile mit der hoechsten Quelle,
prior_focal_length = 1 bei USER/EXIF/SINGLE_VIEW, sonst 0. NUR auf Kopien anwenden - das Original braucht der neue Mapper weiter.
Rueckgabe: True, wenn umgewandelt wurde; False, wenn das Schema schon alt war."""
import sqlite3, sys

ALT = ("CREATE TABLE cameras   (camera_id            INTEGER  PRIMARY KEY AUTOINCREMENT  NOT NULL,    model                INTEGER                             NOT NULL,"
       "    width                INTEGER                             NOT NULL,    height               INTEGER                             NOT NULL,    params               BLOB,"
       "    prior_focal_length   INTEGER                             NOT NULL)")


def kameras_alt(db):
    c = sqlite3.connect(db); sp = [r[1] for r in c.execute("PRAGMA table_info(cameras)")]
    if "source" not in sp: c.close(); return False
    rows = c.execute("SELECT camera_id, model, width, height, params, source FROM cameras ORDER BY camera_id, source").fetchall(); beste = {}
    for cid, m, w, h, p, s in rows:
        if cid not in beste or s > beste[cid][5]: beste[cid] = (cid, m, w, h, p, s)
    with c:
        c.execute("ALTER TABLE cameras RENAME TO cameras_neu_schema"); c.execute(ALT)
        c.executemany("INSERT INTO cameras (camera_id, model, width, height, params, prior_focal_length) VALUES (?, ?, ?, ?, ?, ?)",
                      [(cid, m, w, h, p, 1 if s in (1, 3, 4) else 0) for cid, m, w, h, p, s in beste.values()])
        c.execute("DROP TABLE cameras_neu_schema")
    c.close(); return True


if __name__ == "__main__":
    print("umgewandelt" if kameras_alt(sys.argv[1]) else "Schema schon alt - nichts getan")
