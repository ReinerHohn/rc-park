#!/usr/bin/env python3
"""pipeline_objekt.py <objekt> <fotos_ordner> <daten_ordner> - Foto-Pipeline in FESTER Reihenfolge, jede Stufe geprueft.

Reihenfolge (Regel: Fotos zuerst, LOD2 nur als Abgleich):
  1 fotos      tools/fotos_pruefen.py: defekte Bilder -> quarantaene/ (nichts loeschen)
  2 sfm        tools/iphone_sfm.py: duenne Wolke (COLMAP, GPU); Pruefung: >= 50 % der Fotos registriert
  3 dicht      COLMAP undistort -> patch_match (GPU) -> stereo_fusion -> fused.ply; Pruefung: Datei > 0 Byte
  4 kandidaten tools/lod2_kandidaten.py: Gebaeude um die Koordinate (nur Liste, nichts uebernehmen)
  5 abgleich   tools/sfm_lod2_ausrichten.py --radius 30 --schreiben: Guete berichten, Entscheidung NICHT automatisch
  6 abnahme    tools/bauen_abnehmen.sh <objekt>: Generator + Pruefstand + Sichtblatt (nur wenn Generator existiert)
Ergebnis: <daten_ordner>/pipeline_bericht.json mit Status je Stufe. Eine Stufe, die ausfaellt, stoppt die Kette
und wird im Bericht mit der Ursache festgehalten. Fehlt ein Eingang (z. B. Koordinate), wird die Stufe als OFFEN markiert.
Aufruf (ueber GPU-Steuerung): JOB_GPU_MB=6000 tools/job_start.sh pipe_<objekt> <log> /media/oem/scan/venv-seg/bin/python -I tools/pipeline_objekt.py <objekt> <fotos> <daten>
        [--stufe grob|schnell|fein] [--sfm-von DIR] [--neu sfm|dicht] [--ohne-abnahme]

17.11.2026 (Durchsicht) - Zwischenstaende galten allein deshalb als gueltig, weil sie EXISTIEREN:
  - Bildbestand: nach der SfM wird der Fotoordner mit der SfM-Datenbank verglichen. Bilder, die die SfM nie gesehen hat (neu gesammelt) oder die es nicht mehr gibt, stehen als
    Zeile 'ACHTUNG Bildbestand' in Ausgabe und Bericht. Das Netz wird NICHT von selbst neu gerechnet (Stunden; nachregistrierte Fotos der Stufe 'seiten' liegen absichtlich im
    Ordner, ohne im Netz zu sein - schwab_v3: 352). Neu rechnen: `--neu sfm` oder Umgebungsvariable RCPARK_PIPE_NEU=sfm (fuer Kettenlaeufe): sfm/, kameras.json und dicht/ werden
    BEISEITEGELEGT (<name>.alt_<zeit>, nichts wird geloescht - Platz danach selbst freigeben), dann alles neu. `--neu dicht`: nur dicht/ und sfm/sparse_dicht.
  - Abgeleitete Staende: kameras.json aelter als das Netz -> neu exportiert. Bildwahl/Tiefenkarten/fused.ply aelter als das Netz (jemand hat sfm/ entfernt und neu gerechnet):
    FEHLER rc 3 statt stiller Mischung aus neuem Netz und alter Wolke (die Tiefenkarten galten allein ueber ihre ANZAHL als fertig) - mit `--neu dicht` neu rechnen.
  - dichte Wolke: Pruefung an der Punktzahl im PLY-Kopf (vorher Datei > 0 Byte: eine fused.ply mit 0 Punkten hat 300 Byte Kopf und galt als OK).
  - Abgleich gescheitert -> rc 5 und KEINE Abnahme (vorher rc 0; an martinstor_gk/kaufhaus_gk lief die Abnahme nach gescheitertem Abgleich).
  - Abnahme: Objekte der Gesamtkette (objekt.json 'gesamtkette') werden hier NICHT gebaut - die Kette baut in ihrer Stufe 'bauen' NACH den Lage-Toren und dem Dach
    (vorher lief bauen_abnehmen.sh schon in der Kettenstufe 'sfm', vor jedem Tor). Auch mit --ohne-abnahme.
Umgebung: venv-seg (Steuerung); pycolmap-Schritte ruft das Werkzeug selbst mit venv-colmap. Weitere Optionen: --mapper <art>, RCPARK_PIPE_NEU=sfm|dicht.
Exit: 0 = alle Stufen ok, 1 = keine gueltigen Fotos, 2 = SfM registriert < 50 %, 3 = abgeleitete Staende aelter als das Netz / dichte Wolke fehlt,
      4 = Fotoordner fehlt, 5 = Abgleich (sfm_lod2_ausrichten) gescheitert.
"""
import sys, os, json, glob, subprocess, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY_SEG = "/media/oem/scan/venv-seg/bin/python"
PY_COL = "/media/oem/scan/venv-colmap/bin/python"  # pycolmap (SfM, Kamera-Export)
PY_SEG = "/media/oem/scan/venv-seg/bin/python"    # torch auf der GPU (Ausrichtung, Luecken)

def fremd_anzahl(seiten_json):
    """Anzahl fremder Bilder aus seiten.json - 'fremd' ist eine Liste der Bildnamen (aeltere Staende: Zahl)."""
    fr = (seiten_json or {}).get("fremd") or 0
    return len(fr) if isinstance(fr, (list, tuple, dict)) else int(fr)

def run(cmd, log=None, env=None):
    print("+", " ".join(cmd), flush=True)
    # 18.11.2026 (Kaufhaus gk2e: Fusion 1 h ohne jede Zeile im Log): Ausgabe zeilenweise ins Log statt erst am Ende - Fortschritt (z. B. 'Fusing image [n/N]') sichtbar
    p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1); zeilen = []
    f = open(log, "a") if log else None
    for z in p.stdout:
        zeilen.append(z)
        if f: f.write(z); f.flush()
    p.wait()
    if f: f.close()
    return p.returncode, "".join(zeilen)

def stufe(bericht, name, status, detail):
    bericht["stufen"].append({"name": name, "status": status, "detail": detail})
    print(f"[{status}] {name}: {detail}", flush=True)

BILD_ENDUNGEN = (".jpg", ".jpeg", ".png")


def db_bilder(db):
    """Namen aller Bilder, die die SfM gesehen hat (COLMAP-Datenbank, nur lesend); None, wenn es keine lesbare Datenbank gibt."""
    if not os.path.exists(db): return None
    try:
        import sqlite3
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True); n = {r[0] for r in c.execute("SELECT name FROM images")}; c.close(); return n
    except Exception: return None


def seiten_dicht_uebernehmen(daten, sparse_dir):
    """21.11.2026 SEITENMODELLE (tools/sfm_seiten_modelle.py, von iphone_sfm.py bei mehreren Bildteilen gerechnet): die dichten Wolken je Seite sind dort schon entstanden (das Vereinen
    braucht sie) und liegen vereint im System von sparse/0 unter sfm/seiten_modelle/. Damit die Stufe 'dicht' sie NICHT ein zweites Mal rechnet, wird dicht/ eine Verknuepfung auf den
    fertigen COLMAP-Arbeitsordner ('ergebnis.dicht' in sfm/seiten_modelle.json: images, sparse, stereo, fused.ply). Nur wenn es dicht/ noch nicht gibt, die Wolke Punkte hat und nicht
    aelter ist als das Netz sparse/0 (sonst rechnet die Stufe wie bisher auf sparse/0 - beim vereinten Modell ueber alle Seiten). `--neu dicht` legt die Verknuepfung beiseite und
    rechnet neu. Rueckgabe True = uebernommen."""
    smj = os.path.join(daten, "sfm", "seiten_modelle.json"); ziel = os.path.join(daten, "dicht")
    try: e = (json.load(open(smj)).get("ergebnis") or {}) if os.path.isfile(smj) else {}
    except Exception as ex: print(f"HINWEIS {smj} nicht lesbar ({ex}) - dichte Wolke wird wie bisher gerechnet", flush=True); return False
    q = e.get("dicht"); ib = os.path.join(sparse_dir, "images.bin")
    if e and os.path.islink(ziel) and (not q or os.path.realpath(ziel) != os.path.realpath(q)) and os.path.realpath(ziel).startswith(os.path.realpath(os.path.join(daten, "sfm", "seiten_modelle")) + os.sep):
        z = f"{ziel}.alt_{time.strftime('%Y%m%d_%H%M%S')}"; os.rename(ziel, z)   # 22.11.2026: eigene Verknuepfung auf eine FRUEHERE Seitenwolke (z. B. teil0/dicht, jetzt vereint) -> beiseite
        print(f"Seitenmodelle: dicht/ zeigte auf eine fruehere Seitenwolke - Verknuepfung beiseitegelegt ({z})" + (f", neu auf {q}" if q else " - Stufe 'dicht' rechnet auf sparse/0"), flush=True)
    if not q or os.path.lexists(ziel) or not os.path.isfile(ib): return False
    qf = os.path.join(q, "fused.ply"); n = ply_punkte(qf)
    if n == 0 or os.path.getmtime(qf) < os.path.getmtime(ib) - 2:
        print(f"HINWEIS Seitenmodelle: dichte Wolke {qf} leer oder aelter als das Netz - NICHT uebernommen, Stufe 'dicht' rechnet auf sparse/0", flush=True); return False
    os.symlink(os.path.abspath(q), ziel)
    print(f"dichte Wolke aus den Seitenmodellen uebernommen ({e.get('art')}, {n} Punkte): {ziel} -> {q} - keine zweite Rechnung", flush=True); return True


def seiten_nachstufe_veraltet(daten):
    """22.11.2026 (Nulllauf kette-schwabentor-null-1122c: Stufe 'sfm' nahm sparse/0 + seiten_modelle.json von 02:39, der GPS-Rueckfall von 05:40 lief nie): kam sparse/0 aus den
    Seitenmodellen (sfm/seiten_modelle.json mit 'ergebnis') und passt dessen 'nachstufe_code' nicht zum aktuellen Code der Nachstufe (sfm_seiten_modelle.NACHSTUFE, tools/code_stand.py)
    -> Grund (Text), sonst None. Dann rechnet iphone_sfm.py mit RCPARK_SFM_NUR_NACHSTUFE=1 nur Vereinen/Tore/Einsetzen neu (Merkmale, Mapper je Teil, Wolken je Teil aus dem Stand).
    RCPARK_SEITEN_NACHSTUFE=0 = Stand davor (vorhandenes sparse/0 gilt)."""
    smj = os.path.join(daten, "sfm", "seiten_modelle.json")
    if os.environ.get("RCPARK_SEITEN_NACHSTUFE", "1") == "0" or not os.path.isfile(smj): return None
    try: d = json.load(open(smj))
    except Exception as ex: return f"{smj} nicht lesbar ({ex})"
    if not d.get("ergebnis"): return None                                 # Seitenweg nicht bis zum Ergebnis gelaufen (Mapperwahl wie bisher) - nichts nachzuholen
    import sfm_seiten_modelle as SM
    alt, neu = d.get("nachstufe_code"), SM.nachstufe_code()
    return None if alt == neu else f"Code der Nachstufe geaendert ({alt or 'ohne Code-Stand'} -> {neu}; {', '.join(SM.NACHSTUFE)})"


def stand_pruefen(daten, fotos):
    """Passen die Zwischenstaende unter `daten` zum Fotoordner und zueinander? Nur lesen. Rueckgabe dict:
    neu/fehlend = Bilder im Ordner, die die SfM nie sah / die die SfM sah und die es nicht mehr gibt (None = keine Datenbank);
    kameras_alt = kameras.json aelter als das Netz; dicht_alt = Liste der dichten Zwischenstaende, die aelter sind als das Netz."""
    mt = lambda q: os.path.getmtime(q) if os.path.exists(q) else None
    im_ordner = {f for f in os.listdir(fotos) if f.lower().endswith(BILD_ENDUNGEN) and os.path.isfile(os.path.join(fotos, f))} if os.path.isdir(fotos) else set()
    n_db = db_bilder(os.path.join(daten, "sfm", "db.db")); netz = mt(os.path.join(daten, "sfm", "sparse", "0", "images.bin"))
    erg = dict(bilder_ordner=len(im_ordner), bilder_sfm=None if n_db is None else len(n_db), neu=None if n_db is None else sorted(im_ordner - n_db), fehlend=None if n_db is None else sorted(n_db - im_ordner), kameras_alt=False, dicht_alt=[])
    if netz is not None:
        k = mt(os.path.join(daten, "kameras.json")); erg["kameras_alt"] = k is not None and k < netz - 2
        erg["dicht_alt"] = [q for q in (os.path.join("sfm", "sparse_dicht", "images.bin"), os.path.join("dicht", "sparse", "images.bin"), os.path.join("dicht", "fused.ply")) if mt(os.path.join(daten, q)) is not None and mt(os.path.join(daten, q)) < netz - 2]
    return erg


def beiseite(pfade, marke):
    """Zwischenstaende umbenennen statt loeschen (<pfad>.alt_<marke>); Verknuepfungen (--sfm-von) werden als Verknuepfung umbenannt. Rueckgabe: neue Namen."""
    weg = []
    for q in pfade:
        if os.path.lexists(q): z = f"{q.rstrip('/')}.alt_{marke}"; os.rename(q.rstrip("/"), z); weg.append(z)
    return weg


def ply_punkte(p):
    """Punktzahl aus dem PLY-Kopf; 0, wenn die Datei fehlt, leer ist oder keinen Kopf hat."""
    try:
        with open(p, "rb") as f:
            for _ in range(60):
                l = f.readline()
                if l.startswith(b"element vertex"): return int(l.split()[-1])
                if not l or l.startswith(b"end_header"): break
    except (OSError, ValueError): pass
    return 0


def main():
    obj, fotos, daten = sys.argv[1], sys.argv[2], sys.argv[3]
    stufe_wahl = sys.argv[sys.argv.index("--stufe") + 1] if "--stufe" in sys.argv else "schnell"   # grob: Vorschau 800 px; schnell (Standard seit 15.11.2026, Nutzer "Ja"): 1600 px nur fotometrisch + Filter, Fusion min_num_pixels 8 (Schwabentor: 2 cm Median zur geometrischen Wolke, ~50 statt ~125 min, aber 4,0 statt 2,2 % Strassenpunkte); fein: mit geometrischem Durchgang - nur wenn ein Tor zweifelt
    os.makedirs(daten, exist_ok=True)
    bericht = {"objekt": obj, "start": time.strftime("%Y-%m-%d %H:%M:%S"), "stufen": []}
    spath = os.path.join(daten, "pipeline_bericht.json")
    def sichern(): __import__("json_sicher").schreiben(spath, bericht)      # 17.11.2026: erst vollstaendig wandeln, dann ersetzen
    neu_wahl = sys.argv[sys.argv.index("--neu") + 1] if "--neu" in sys.argv and sys.argv.index("--neu") + 1 < len(sys.argv) else os.environ.get("RCPARK_PIPE_NEU", "")
    if neu_wahl not in ("", "sfm", "dicht"): print(f"FEHLER: --neu/RCPARK_PIPE_NEU kennt nur 'sfm' oder 'dicht', nicht {neu_wahl!r}", flush=True); return 4
    log = os.path.join(daten, "pipeline.log")

    # 0 Eingangscheck (Lehre Schwabentor 13.11.: Platzhalter-Objekt und fehlender Fotopfad fielen erst spaet auf)
    oj = os.path.join(ROOT, "modelle", obj, "objekt.json")
    cfg = json.load(open(oj)) if os.path.exists(oj) else {}
    probleme = []
    if not os.path.isdir(fotos): probleme.append(f"Fotoordner fehlt: {fotos}")
    if not cfg: probleme.append(f"objekt.json fehlt: {oj}")
    if cfg and "koordinate_utm" not in cfg: probleme.append("koordinate_utm fehlt (fuer Kandidatenliste)")
    if cfg and "rahmen_wand" not in cfg: probleme.append("rahmen_wand fehlt (fuer Foto-Luecken)")
    stufe(bericht, "eingang", "OK" if not probleme else "OFFEN", "; ".join(probleme) if probleme else "Fotos, Objekt, Koordinate, Rahmen vorhanden")
    if not os.path.isdir(fotos): sichern(); return 4
    sichern()

    # 1 Fotos
    rc, out = run([PY_SEG, "-I", "tools/fotos_pruefen.py", fotos], log)
    n_gueltig = len([f for f in os.listdir(fotos) if os.path.isfile(os.path.join(fotos, f))])
    stufe(bericht, "fotos", "OK" if rc in (0, 1) and n_gueltig > 0 else "FEHLER", f"{n_gueltig} Dateien im Ordner nach Pruefung; rc={rc}")
    if n_gueltig == 0: sichern(); return 1
    sichern()

    if neu_wahl:                                                          # ausdruecklich neu rechnen: alte Staende beiseitelegen (nie loeschen)
        weg = beiseite([os.path.join(daten, "sfm"), os.path.join(daten, "kameras.json"), os.path.join(daten, "dicht")] if neu_wahl == "sfm" else [os.path.join(daten, "dicht"), os.path.join(daten, "sfm", "sparse_dicht")], time.strftime("%Y%m%d_%H%M%S"))
        stufe(bericht, "neu", "OK", f"--neu {neu_wahl}: beiseitegelegt (NICHT geloescht, Platz selbst freigeben): " + (", ".join(os.path.relpath(q, daten) for q in weg) or "nichts vorhanden")); sichern()

    # 2 SfM (duenne Wolke)
    # --sfm-von DIR: Fotowolke aus einem frueheren Lauf mit denselben Fotos wiederverwenden (identisches Ergebnis, spart die Stunde nicht, aber Minuten)
    if "--sfm-von" in sys.argv:
        quelle = os.path.join(sys.argv[sys.argv.index("--sfm-von") + 1], "sfm")
        ziel = os.path.join(daten, "sfm")
        if os.path.isdir(os.path.join(quelle, "sparse", "0")) and not os.path.exists(ziel):
            os.symlink(os.path.abspath(quelle), ziel)
            print(f"Fotowolke wiederverwendet aus {quelle}", flush=True)
    sparse_dir = os.path.join(daten, "sfm", "sparse", "0")
    nach_grund = seiten_nachstufe_veraltet(daten) if os.path.isdir(sparse_dir) else None
    if nach_grund:                                                        # 22.11.2026: billige Nachstufe mit aktuellem Code, teure Teile aus dem Zwischenstand (iphone_sfm.py NUR NACHSTUFE)
        print(f"SEITENMODELLE NACHSTUFE NEU: {nach_grund} - iphone_sfm.py rechnet Vereinen/Tore/Einsetzen neu (Merkmale, Mapper je Teil, dichte Wolken je Teil aus dem Zwischenstand)", flush=True)
        rc_n, out_n = run([PY_COL, "-I", "tools/iphone_sfm.py", fotos, os.path.join(daten, "sfm")], log, env=dict(os.environ, RCPARK_SFM_NUR_NACHSTUFE="1", RCPARK_SEITEN_OBJEKT=oj))
        if rc_n != 0 or seiten_nachstufe_veraltet(daten):
            stufe(bericht, "sfm", "FEHLER", f"Nachstufe der Seitenmodelle mit neuem Code gescheitert (rc {rc_n}): {(out_n.strip().splitlines() or [''])[-1][:200]} - sparse/0 gehoert zu altem Code; bewusst neu: --neu sfm"); sichern(); return 2
        stufe(bericht, "seiten_nachstufe", "OK", nach_grund + " -> Vereinen/Einsetzen neu gerechnet"); sichern()
    if not os.path.isdir(sparse_dir):
        mapper_wahl = sys.argv[sys.argv.index("--mapper") + 1] if "--mapper" in sys.argv and sys.argv.index("--mapper") + 1 < len(sys.argv) else ""   # 19.11.2026: auto (Standard von iphone_sfm) | global | inkrementell | konsens (modelle/GLOBALER_MAPPER_STABIL.md); leer = nichts durchreichen
        rc, out = run([PY_COL, "-I", "tools/iphone_sfm.py", fotos, os.path.join(daten, "sfm")] + (["--mapper", mapper_wahl] if mapper_wahl else []), log, env=dict(os.environ, RCPARK_SEITEN_OBJEKT=oj))   # 22.11.2026: objekt.json fuer die Stufe LoD2 je Teil (sfm_seiten_modelle.lod2_stufe)
    rc_ok = os.path.isdir(sparse_dir)
    reg = None
    if rc_ok:
        rc2, o2 = run([PY_COL, "-I", "-c", f"import pycolmap;r=pycolmap.Reconstruction({sparse_dir!r});print('REG',r.num_reg_images())"])
        m = re.findall(r"REG (\d+)", o2)
        reg = int(m[-1]) if m else None
        # 19.11.2026 (Nutzer): Kamera-Abdeckung SOFORT nach dem Mapper melden - vorher erst in den Lage-Toren, nach ~40 min Tiefenkarten. Winkel im MODELLSYSTEM (noch nicht eingenordet):
        # die Meldung sagt, WIE VIEL des Kranzes fehlt, die Himmelsrichtung liefert erst tor_kamera nach der Ausrichtung. Die Kette rechnet weiter (kein Abbruch).
        try:
            rc3, o3 = run([PY_SEG, "-I", "tools/kamera_abdeckung.py", sparse_dir]); sk = re.search(r"Sektor: (\{[^}]*\})", o3); lu = re.search(r"groesste Luecke: (\d+) Grad", o3)
            sek = __import__("ast").literal_eval(sk.group(1)) if sk else {}; duenn = [k for k, v in sek.items() if v < 5]; luecke = int(lu.group(1)) if lu else None
            det = f"{len(sek) - len(duenn)} von {len(sek)} Sektoren (30 Grad) mit >= 5 Kameras, groesste Luecke {luecke} Grad, staerkster Sektor {max(sek.values()) if sek else 0} von {sum(sek.values())} Kameras"
            if duenn or rc3 != 0:
                print(f"ACHTUNG ABDECKUNG (frueh, vor der dichten Wolke): {det} -> von {len(duenn)} Sektoren fehlen Fotos; Fotobedarf tools/foto_auftrag.py / tools/seiten_luecken.py (Himmelsrichtung nach der Ausrichtung: tor_kamera)", flush=True)
            stufe(bericht, "abdeckung", "OFFEN" if duenn or rc3 != 0 else "OK", det)
        except Exception as e_: print("HINWEIS Abdeckung frueh nicht pruefbar:", e_, flush=True)
    ziel = 0.5 * n_gueltig
    # 21.11.2026 (Martinstor-Kettenlauf 1121a brach ab: 574 von 2107 registriert, Ziel 1053 - aber die Seitenerkennung hatte 1362 Bilder als FREMD erkannt, d. h. ohne
    # echte Verbindung zum Objekt; von den 745 Objektbildern waren 574 im Modell). Grundmenge = Objektbilder, wenn die Seitenerkennung gelaufen ist.
    try:
        sj_ = json.load(open(os.path.join(daten, "sfm", "seiten.json"))); n_fremd = fremd_anzahl(sj_)   # 21.11.2026: seiten.json schreibt die LISTE der fremden Bilder - int(list) warf, except schluckte, Ziel blieb 1053 (Martinstor 1121b)
        if 0 < n_fremd < n_gueltig: ziel = 0.5 * (n_gueltig - n_fremd); print(f"SfM-Ziel: {n_fremd} fremde Bilder (Seitenerkennung) zaehlen nicht -> Ziel >= {int(ziel)} von {n_gueltig - n_fremd} Objektbildern", flush=True)
    except Exception: pass
    status = "OK" if rc_ok and reg is not None and reg >= ziel else "FEHLER"
    stufe(bericht, "sfm", status, f"registriert {reg} von {n_gueltig} (Ziel >= {int(ziel)})")
    if status != "OK": sichern(); return 2
    sichern()

    # Bildbestand und abgeleitete Staende (17.11.2026): passt das vorhandene Netz noch zum Fotoordner, passen Kameras/Bildwahl/Tiefenkarten/Wolke zum Netz?
    seiten_dicht_uebernehmen(daten, sparse_dir)                           # 22.11.2026: vor stand_pruefen - eine fruehere Seitenwolke wird erst umgehaengt, dann geprueft
    st = stand_pruefen(daten, fotos)
    if st["neu"] or st["fehlend"]:
        txt = (f"{len(st['neu'])} Bilder im Fotoordner sind NICHT im SfM-Netz (nie gesehen; z. B. {', '.join(st['neu'][:3])})" if st["neu"] else "") + (" und " if st["neu"] and st["fehlend"] else "") + \
              (f"{len(st['fehlend'])} Bilder des Netzes gibt es im Fotoordner nicht mehr (z. B. {', '.join(st['fehlend'][:3])})" if st["fehlend"] else "")
        print(f"ACHTUNG Bildbestand: {txt} - das Netz ({st['bilder_sfm']} Bilder) wurde NICHT neu gerechnet. Neue Bilder ins Netz: --neu sfm bzw. RCPARK_PIPE_NEU=sfm (nachregistrierte Fotos der Stufe 'seiten' sind hier zu erwarten)", flush=True)
        stufe(bericht, "bildbestand", "ACHTUNG", txt + " - Netz nicht neu gerechnet (--neu sfm)"); sichern()
    if st["dicht_alt"]:
        stufe(bericht, "dicht", "FEHLER", "aelter als das SfM-Netz: " + ", ".join(st["dicht_alt"]) + " - Bildwahl/Tiefenkarten/Wolke gehoeren zu einem FRUEHEREN Netz; neu rechnen mit --neu dicht bzw. RCPARK_PIPE_NEU=dicht (legt dicht/ und sfm/sparse_dicht beiseite)")
        sichern(); return 3

    # Kameras als JSON fuer die GPU-Umgebung (Ausrichtung und Luecken brauchen kein pycolmap mehr)
    kam_json = os.path.join(daten, "kameras.json")
    if not os.path.exists(kam_json) or st["kameras_alt"]:                 # 17.11.2026: 'existiert' reichte - nach neu gerechneter SfM blieben die Kameras des alten Netzes
        if st["kameras_alt"]: print("kameras.json ist aelter als das SfM-Netz - wird neu exportiert", flush=True)
        run([PY_COL, "-I", "tools/kamera_export.py", sparse_dir, kam_json], log)
        ib = os.path.join(sparse_dir, "images.bin")
        if not os.path.exists(kam_json) or (os.path.exists(ib) and os.path.getmtime(kam_json) < os.path.getmtime(ib) - 2):
            stufe(bericht, "kameras", "FEHLER", f"tools/kamera_export.py schrieb {kam_json} nicht (neu) - siehe {log}"); sichern(); return 2

    # Parallel: Kandidatenliste (CPU, LOD2-Text) laeuft waehrend der dichten Stufe (GPU). Keine gemeinsame Ressource.
    koord = cfg.get("koordinate_utm")
    gml = (cfg.get("lod2") or {}).get("gml")
    kand_proc = None
    if koord and gml:
        kand_log = open(os.path.join(daten, "kandidaten.log"), "w")
        kand_proc = subprocess.Popen([PY_SEG, "-W", "ignore", "-I", "tools/lod2_kandidaten.py", "--gml", gml, "--e", str(koord[0]), "--n", str(koord[1]), "--radius", "45"], cwd=ROOT, stdout=kand_log, stderr=subprocess.STDOUT)
        # 3 dichte Wolke
    fused = os.path.join(daten, "dicht", "fused.ply")
    seiten_dicht_uebernehmen(daten, sparse_dir)
    if ply_punkte(fused) == 0:                                            # 17.11.2026: vorher 'Datei > 0 Byte' - eine fused.ply mit 0 Punkten (nur Kopf) galt als fertig
        # Bildwahl fuer Tiefenkarten (Lehre 14.11.: Fernansichten/gleiche Videobilder kosten voll, bringen am Objekt wenig) -> tools/dicht_bildwahl.py
        sparse_wahl = os.path.join(daten, "sfm", "sparse_dicht")
        if stufe_wahl != "grob" and not os.path.isdir(sparse_wahl):
            uns_ = os.path.join(daten, "sfm", "konsens_arbeit", "unstabil.txt"); mwj_ = os.path.join(daten, "sfm", "mapper_wahl.json")      # 19.11.2026: Konsens-Mapper -> nur Rueckgrat-Kameras in die dichte Wolke
            kons_ = os.path.isfile(uns_) and os.path.isfile(mwj_) and json.load(open(mwj_)).get("gewaehlt") == "konsens"
            # 21.11.2026: Sperrliste fuers Messen = unstabile Kameras des Konsens-Mappers VEREINIGT mit den Kameras, deren Brennweite das Modell nicht festlegt (tools/brennweite_schaerfe.py:
            # 'unbestimmt' wandert zwischen zwei Mapper-Laeufen zu 67-100 %, 'scharf' zu 1-14 %) -> sfm/sperrliste_messen.txt. unstabil.txt selbst bleibt unveraendert.
            # GUARD (ANNAHME 50 %, nicht gemessen; Martinstor Nord 14 %, Sued 21 %): sperrt die Schaerfe-Liste mehr als die Haelfte der Bilder (kleiner Fotosatz, jedes Foto eigene Kamera),
            # gilt nur die Konsens-Liste wie bisher - sonst bliebe keine dichte Wolke. RCPARK_SCHAERFE_SPERRE=0 = Stand vor dem 21.11.
            ohne_ = uns_ if kons_ else ""; sperr_ = os.path.join(daten, "sfm", "sperrliste_messen.txt")
            if os.environ.get("RCPARK_SCHAERFE_SPERRE", "1") != "0":
                rc_b, out_b = run([PY_COL, "-I", "tools/brennweite_schaerfe.py", sparse_dir, "--aus", os.path.join(daten, "sfm", "brennweite_schaerfe.json"), "--liste", os.path.join(daten, "sfm", "unbestimmt.txt"),
                                   "--sperrliste", sperr_] + (["--vereinen", uns_] if kons_ else []), log); print(out_b.strip()[-400:], flush=True)
                n_sperr = len([z for z in open(sperr_) if z.strip()]) if rc_b == 0 and os.path.isfile(sperr_) else 0
                if rc_b != 0: print(f"ACHTUNG brennweite_schaerfe.py gescheitert (rc {rc_b}) - dichte Wolke OHNE Schaerfe-Sperrliste", flush=True)
                elif reg and n_sperr > 0.5 * reg: print(f"ACHTUNG Sperrliste {n_sperr} von {reg} Bildern (> 50 %) - NICHT angewandt (zu wenige scharf bestimmte Kameras; mehr Fotos/Video noetig), nur Konsens-Liste", flush=True)
                elif n_sperr: ohne_ = sperr_
            rc_w, out_w = run([PY_COL, "-I", "tools/dicht_bildwahl.py", sparse_dir, sparse_wahl] + (["--ohne", ohne_] if ohne_ else []), log); print(out_w.strip()[-400:], flush=True)
            if rc_w != 0: sparse_wahl = sparse_dir
        sparse_dicht = sparse_wahl if os.path.isdir(sparse_wahl) else sparse_dir
        script = os.path.join(daten, "dicht_kette.py")
        open(script, "w").write(f'''import pycolmap, os, time, sys
sys.path.insert(0, {os.path.dirname(os.path.abspath(__file__))!r}); import gpu_buchung as GB
bilder = {fotos!r}; sparse = {sparse_dicht!r}; out = {os.path.join(daten, "dicht")!r}
os.makedirs(out, exist_ok=True)
STUFE = {stufe_wahl!r}
uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = 1600
import glob as _g
_n = pycolmap.Reconstruction(sparse).num_reg_images()   # nur eingehaengte Bilder bekommen Tiefenkarten
_dm = os.path.join(out, "stereo", "depth_maps")
# 18.11.2026 (Kaufhaus gk2: Platte voll -> 272 leere Tiefenkarten, Fusion brach mit 'width_ > 0' ab, 0 Punkte): kaputte Karten (< 2 KB) loeschen, damit sie neu gerechnet werden
for _k in _g.glob(os.path.join(out, "stereo", "*_maps", "*.bin")):
    if os.path.getsize(_k) < 2048: os.remove(_k); print("kaputte Karte geloescht:", os.path.basename(_k), flush=True)
_fertig = os.path.isdir(_dm) and len(_g.glob(os.path.join(_dm, "*.photometric.bin"))) >= _n and (STUFE != "fein" or len(_g.glob(os.path.join(_dm, "*.geometric.bin"))) >= _n)
# 19.11.2026 FALLE: COLMAP rechnet fuer geom_consistency zuerst UNGEFILTERTE fotometrische Karten - sind schon (gefilterte) Karten der Stufe grob/schnell da,
# ueberspringt es sie und die Feinstufe laeuft still auf den falschen Karten. -> abbrechen, ausser RCPARK_FEIN_KARTEN_NEU=1 (dann gefilterte Karten loeschen, neu rechnen).
_pm = _g.glob(os.path.join(_dm, "*.photometric.bin")); _gm = _g.glob(os.path.join(_dm, "*.geometric.bin"))
if STUFE == "fein" and not _fertig and _pm and not _gm:
    if os.environ.get("RCPARK_FEIN_KARTEN_NEU") != "1":
        print("ABBRUCH FEIN: " + str(len(_pm)) + " gefilterte fotometrische Karten (Stufe grob/schnell) liegen in " + _dm + " - die geometrische Pruefung braucht ungefilterte. Neu rechnen mit RCPARK_FEIN_KARTEN_NEU=1 (loescht sie) oder anderer Ordner.", flush=True); sys.exit(5)
    for _k in _pm + _g.glob(os.path.join(out, "stereo", "normal_maps", "*.photometric.bin")): os.remove(_k)
    print("FEIN: gefilterte fotometrische Karten geloescht (RCPARK_FEIN_KARTEN_NEU=1), werden ungefiltert neu gerechnet", flush=True)
if _fertig:
    print("Tiefenkarten aus Cache (" + str(_n) + " Bilder, Modus " + STUFE + ")", flush=True)
else:
    pycolmap.undistort_images(out, sparse, bilder, output_type="COLMAP", undistort_options=uo)
GROB = STUFE == "grob"
po = pycolmap.PatchMatchOptions(); po.max_image_size = 800 if GROB else 1600; po.gpu_index = "0"
FEIN = STUFE == "fein"; po.geom_consistency = FEIN; po.filter = True
if STUFE == "schnell": po.window_step = 2   # Messung 15.11.2026 (Schwabentor, 40 Referenzbilder): 196 statt 485 s, 11 % weniger Punkte, Abstand zur Standardwolke Median 1,3 cm, p90 4,4 cm, 0,4 % > 30 cm   # grob/schnell: nur fotometrisch (gefiltert); fein: mit geometrischer Konsistenz
if not _fertig:
    pycolmap.patch_match_stereo(out, options=po)
fo = pycolmap.StereoFusionOptions(); fo.max_image_size = 800 if GROB else 1600
# 18.11.2026 (Kaufhaus gk2d, 595 Bilder: OOM-Kill nach 90 s, 11 GB RAM + 6 GB Swap): COLMAP-Vorgabe cache_size 32 GB > 15 GB RAM -> use_cache=True (sonst laedt COLMAP alle Karten, cache_size wirkungslos) + nach freiem RAM begrenzen (40 %)
try:
    _frei_gb = int([l for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0].split()[1]) / 1048576
except Exception: _frei_gb = 8.0
_nf = len([l for l in open(os.path.join(out, "stereo", "fusion.cfg")) if l.strip()]); _bedarf = _nf * (0.045 if not GROB else 0.012)   # GB (Messung 18.11.: 100 Bilder 1600 px = 4,1 GB)
# 18.11.2026: use_cache (1 Thread, Nachladen) lief am Kaufhaus 4 h ohne Ende (1,56 TB gelesen) -> passt es nicht in 60 % des freien RAM: TEILFUSION in voller Aufloesung (tools/teilfusion.py), sonst normal mit allen Kernen
print("Fusion:", _nf, "Bilder, Bedarf ~%.1f GB, frei %.1f GB" % (_bedarf, _frei_gb), "-> TEILFUSION" if _bedarf > 0.6 * _frei_gb else "-> am Stueck", flush=True)
if STUFE == "schnell": fo.min_num_pixels = 3   # 19.11.2026 gemessen (Martinstor): 8 (Annahme vom 15.11.) warf Putz und Sockel weg; 3 = 5-fache Punktzahl, Anteil falscher Punkte gleich (1,3 %), Wanddicke 4 -> 5 cm
GB.frei()   # Fusion hat keinen GPU-Code (Minuten auf der CPU)
if _bedarf > 0.6 * _frei_gb:
    import subprocess as _sp
    _rc = _sp.call([sys.executable, "-I", os.path.join({os.path.dirname(os.path.abspath(__file__))!r}, "teilfusion.py"), out, os.path.join(out, "fused.ply"), "--max_image_size", str(fo.max_image_size), "--min_num_pixels", str(fo.min_num_pixels), "--input_type", "geometric" if FEIN else "photometric"])
    if _rc: sys.exit(_rc)
else:
    pycolmap.stereo_fusion(os.path.join(out, "fused.ply"), out, options=fo, input_type="geometric" if FEIN else "photometric", output_type="ply")
GB.belegen()
print("FERTIG", flush=True)
''')
        rc, out = run([PY_COL, "-I", script], log)
    n_pkt = ply_punkte(fused); ok = n_pkt > 0
    stufe(bericht, "dicht", "OK" if ok else "FEHLER", f"fused.ply {n_pkt} Punkte, {os.path.getsize(fused) if os.path.exists(fused) else 0} Byte" + ("" if ok else " - dichte Wolke LEER oder nicht geschrieben"))
    if not ok: sichern(); return 3
    sichern()

    # 4 Kandidaten (laufen parallel zur dichten Stufe, hier nur einsammeln)
    if kand_proc is not None:
        rc = kand_proc.wait(); out = open(os.path.join(daten, "kandidaten.log")).read()
        kand = [l for l in out.splitlines() if re.match(r"\s*\d+\.\d+\s+\S+\s+\S+", l)]
        stufe(bericht, "kandidaten", "OK" if rc == 0 else "FEHLER", f"{len(kand)} Gebaeude im Umkreis (Liste siehe Log)")
    else:
        stufe(bericht, "kandidaten", "OFFEN", "keine koordinate_utm/lod2.gml in objekt.json")
    sichern()

    # 5 Abgleich (Ausrichtung, Entscheidung beim Nutzer)
    if os.path.exists(oj) and sparse_dir:
        rc, out = run([PY_SEG, "-u", "-I", "tools/sfm_lod2_ausrichten.py", oj, "--kameras", kam_json, "--dicht", fused, "--name", obj, "--radius", "30", "--schreiben", "--fotos", fotos], log)   # --fotos: GPS-Startmassstab aus den Bildern dieses Laufs (15.11.)
        g = re.findall(r"Guete[^\n]*", out)
        stufe(bericht, "abgleich", "OK" if rc == 0 else "FEHLER", (g[-1] if g else "ohne Guete-Zeile") + " | Entscheidung beim Nutzer" + ("" if rc == 0 else f" | rc {rc}: {out.strip().splitlines()[-1][:160] if out.strip() else 'keine Ausgabe'}"))
        if rc != 0: sichern(); print("BERICHT", spath, flush=True); return 5      # 17.11.2026: lief mit rc 0 weiter bis zur Abnahme - Wolke/Ausrichtung im Objekt sind dann die eines frueheren Laufs
    else:
        stufe(bericht, "abgleich", "OFFEN", "kein objekt.json")
    sichern()

    # 5b Foto-Luecken (was noch fotografiert werden muss)
    if os.path.exists(oj) and "rahmen_wand" in cfg and os.path.isdir(sparse_dir):
        rc, out = run([PY_SEG, "-W", "ignore", "-I", "tools/foto_luecken_plan.py", oj, "--kameras", kam_json, "--schritt", "3"], log)
        n = len(re.findall(r"^\s+- ", out, re.M))   # Luecken-Zeilen beginnen mit "  - "
        stufe(bericht, "foto_luecken", "OK" if rc == 0 else "FEHLER", f"{n} Luecken; Liste in modelle/{obj}/foto_luecken.json")
    sichern()

    # 6 Abnahme
    if "--ohne-abnahme" in sys.argv or "gesamtkette" in cfg:              # 17.11.2026: in Kettenlaeufen lief der Bau schon HIER (Kettenstufe 'sfm'), vor Lage-Toren und Dach; die Kette baut selbst in 'bauen'
        stufe(bericht, "abnahme", "UEBERSPRUNGEN", "Objekt der Gesamtkette: gebaut und abgenommen wird in der Kettenstufe 'bauen' nach den Lage-Toren" if "gesamtkette" in cfg else "--ohne-abnahme")
    elif os.path.exists(os.path.join(ROOT, "modelle", f"{obj}_gen.py")) or os.path.exists(os.path.join(ROOT, "modelle", obj, "objekt.json")):
        rc, out = run(["bash", "tools/bauen_abnehmen.sh", obj], log)
        stufe(bericht, "abnahme", "OK" if rc == 0 else f"ROT rc={rc}", "bauen_abnehmen.sh; Sichtblatt audit/seiten.jpg ansehen")
    sichern()
    print("BERICHT", spath, flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
