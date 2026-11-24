#!/usr/bin/env python3
"""sift_paar_speicher.py - SIFT-Abgleich JE PAAR wiederverwenden (Nachholen, Stufe merkmale in tools/zusatzfotos_registrieren.py), 24.11.2026.

Anlass (Kette schwabentor-null-1122zb, Stufe seiten_luecken 1777 s, gemessen an den Zeitstempeln im gesamtkette.log):
  merkmale 17:20:47-17:37:32 = 1005 s (57 %; SIFT-Matching 347 353 Paare = 326 Kandidaten x 903 Referenz + Kandidat x Kandidat),
  refnamen/paare (LightGlue, Zwischenspeicher-Treffer 326 815/347 353) 278 s, einlesen 87 s, registrieren ~190 s, nachtragen/verfeinern/Tor ~200 s.
  Der Eintrags-Zwischenspeicher 'merkmale' (tools/nachhol_zwischenspeicher.py) greift nur bei GLEICHER Kandidatenliste und GLEICHER Referenz-DB - jeder
  Kettenlauf von null rechnet aber ein neues SfM: registriert sind je Lauf etwas andere Bilder (Kandidaten 553 / 542 / 307 / 307 / 244 in
  seiten_nachholen/versucht_*.txt), also ist die Paarliste jedes Mal anders und der ganze Abgleich lief neu, obwohl fast alle PAARE dieselben sind.
Regel: COLMAP matcht jedes Paar fuer sich (Ergebnis haengt nur an Schluesselpunkten/Beschreibern beider Bilder, ihren Kameras und den Optionen; nicht an den
  anderen Paaren der Liste) und UEBERSPRINGT Paare, die schon Matches + Zwei-Bild-Geometrie in der Datenbank haben (gemessen: tests/test_sift_paar_speicher.py,
  CPU-Abgleich, Teil-/Umkehr-Listen bitgleich, vorhandenes Paar unberuehrt). Darum: vor dem Abgleich die gespeicherten Zeilen der bekannten Paare in die DB
  schreiben, COLMAP rechnet nur den Rest; danach die neu gerechneten Paare ablegen. Tabellen matches/two_view_geometries haben pair_id als INTEGER PRIMARY KEY
  (= rowid): Lesereihenfolge ist unabhaengig von der Einfuegereihenfolge -> Datenbankinhalt wie ohne Speicher.
Schluessel je Paar: sha1(Basis, Fingerabdruck Bild x, Fingerabdruck Bild y, Reihenfolge der Bild-IDs, gleicher Frame). Fingerabdruck = Schluesselpunkte +
  Beschreiber (rows, cols, data) + Kamerazeile (Modell, Groesse, Parameter, Brennweiten-Prior). Basis = pycolmap-Version, Geraet (GPU/CPU), Optionen,
  Spalten der Tabellen, Quelltext der Rechenfunktion des Aufrufers.
GUARD (Stichprobe): ein Teil der Treffer (deterministisch, >= 16, ~0,5 %) wird NICHT eingesetzt, sondern von COLMAP neu gerechnet und mit dem Speicher
  verglichen. Weichen mehr als max(2, 2 %) ab (systematisch: falscher Schluessel, andere Bibliothek ...) -> WARNUNG, eingesetzte Zeilen wieder geloescht,
  alles neu gerechnet (Ergebnis wie ohne Speicher), Speicherdatei verworfen.
  GEMESSEN 24.11.2026 (pycolmap 4.2.1, CPU-Abgleich, 9 Bilder/36 Paare): COLMAP selbst ist MEHRFAEDIG NICHT wiederholbar - 3 von 30 gleichen Laeufen hatten
  2 Paare mit anderen Matches (z. B. 210 statt 467); mit num_threads=1 40/40 gleich. Ein Einzelausreisser der Stichprobe ist darum Rauschen der Rechnung
  selbst, kein Speicherfehler; "bitgleich" heisst hier: dieselbe Zeile, die dieselbe Rechnung frueher geliefert hat. GPU-Abgleich (Kette) nicht gemessen.
Greift die Abkuerzung nicht (kein Treffer): nichts eingesetzt, derselbe Aufruf wie bisher - nur danach lesend abgelegt.
Verwandt/Vorlaeufer: tools/nachhol_zwischenspeicher.py (Eintrag je ganzer Stufe, bleibt die erste Stufe), tools/lg_zwischenspeicher.py (LightGlue je Bildinhalt/Paar),
  tools/zusatzfotos_registrieren.py (Aufrufer, Stufe merkmale), tools/zusatzfotos_lightglue.py (Schalter RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT - anderer, NICHT bitgleicher Weg).
Ablage: <nachhol_zwischenspeicher.wurzel()>/sift_paare/<objekt>_<h6>/paare_<h8>.sqlite (nie Root); Groesse RCPARK_SIFT_PAARSPEICHER_GB (Standard 3, aelteste
  Haelfte raus); Schalter RCPARK_SIFT_PAARSPEICHER=0 (aus). Ablegen nur bei >= 10 GB frei.
"""
import os, sqlite3, hashlib, json, time

RESERVE_B = 10 * 2 ** 30


def paar_id(a, b):
    a, b = (int(a), int(b)) if a < b else (int(b), int(a))
    return a * 2147483647 + b


def _sha(*teile):
    h = hashlib.sha1()
    for t in teile:
        b = t if isinstance(t, (bytes, bytearray, memoryview)) else json.dumps(t, sort_keys=True, default=str).encode()
        h.update(len(b).to_bytes(8, "little")); h.update(b)
    return h.hexdigest()


def spalten(con, tab):
    return [r[1] for r in con.execute(f"pragma table_info({tab})")]


def an():
    if os.environ.get("RCPARK_SIFT_PAARSPEICHER", "1") == "0": return False
    import nachhol_zwischenspeicher as NZ
    return NZ.an()


def basis(pycolmap, quelle="", db=None):
    """Teil des Schluessels, der fuer alle Paare gilt (Werkzeug, Geraet, Optionen, Tabellenschema, Quelltext des Aufrufers)."""
    mo = getattr(pycolmap, "FeatureMatchingOptions", lambda: None)(); vo = getattr(pycolmap, "TwoViewGeometryOptions", lambda: None)()
    if vo is not None: vo.ransac.random_seed = 0
    def d_(o):
        try: return o.todict()
        except Exception: return str(o.summary()) if hasattr(o, "summary") else repr(o)
    gpu = bool(getattr(pycolmap, "has_cuda", False)) and os.environ.get("CUDA_VISIBLE_DEVICES", None) != ""
    sch = None
    if db:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True); sch = {t: spalten(con, t) for t in ("matches", "two_view_geometries", "cameras", "keypoints", "descriptors")}; con.close()
    return _sha("sift-paar-1", getattr(pycolmap, "__version__", "?"), gpu, d_(mo), d_(vo), sch, quelle)


def fingerabdruecke(con, namen):
    """{name: (image_id, fingerabdruck, frame_id|None)} fuer die genannten Bilder (Schluesselpunkte, Beschreiber, Kamerazeile)."""
    cs = spalten(con, "cameras"); cams = {r[0]: r[1:] for r in con.execute(f"select {', '.join(cs)} from cameras")}
    frame = {}
    if "frame_data" in {r[0] for r in con.execute("select name from sqlite_master where type='table'")}:
        try: frame = {int(d): int(f) for f, d, st in con.execute("select frame_id, data_id, sensor_type from frame_data") if int(st) == 0}
        except sqlite3.Error: frame = {}
    ds = [c for c in spalten(con, "descriptors") if c != "image_id"]; out = {}; nm = set(namen)
    for iid, name, cid in con.execute("select image_id, name, camera_id from images"):
        if name not in nm: continue
        kp = con.execute("select rows, cols, data from keypoints where image_id=?", (iid,)).fetchone()
        de = con.execute(f"select {', '.join(ds)} from descriptors where image_id=?", (iid,)).fetchone()
        out[name] = (int(iid), _sha(kp[0] if kp else None, kp[1] if kp else None, bytes(kp[2]) if kp and kp[2] is not None else b"",
                                    [bytes(v) if isinstance(v, (bytes, memoryview)) else v for v in (de or ())], cams.get(cid)), frame.get(int(iid)))
    return out


def ablage(db):
    """Speicherdatei fuer die DB <db> (Gruppe = Ordner der DB, Name nach dem Objektordner) oder None (aus)."""
    if not an(): return None
    import nachhol_zwischenspeicher as NZ
    d = os.path.dirname(os.path.abspath(db)); obj = os.path.basename(os.path.dirname(d)) or "x"
    return os.path.join(NZ.wurzel(), "sift_paare", f"{obj}_{hashlib.sha1(d.encode()).hexdigest()[:6]}")


def _speicher_oeffnen(ordner, b, mcols, gcols):
    os.makedirs(ordner, exist_ok=True); p = os.path.join(ordner, f"paare_{b[:8]}.sqlite"); S = sqlite3.connect(p)
    S.execute("create table if not exists m (k text primary key, zeit real, " + ", ".join(f'"m_{c}"' for c in mcols) + ", " + ", ".join(f'"g_{c}"' for c in gcols) + ")")
    return S, p


def _lesen(con, pids, mcols, gcols):
    """{pair_id: (matches-Werte, geometrie-Werte)} nur fuer Paare mit BEIDEN Zeilen."""
    out = {}; pl = list(pids)
    for i in range(0, len(pl), 900):
        ch = pl[i:i + 900]; q = ",".join("?" * len(ch))
        M = {r[0]: tuple(r[1:]) for r in con.execute(f"select pair_id, {', '.join(mcols)} from matches where pair_id in ({q})", ch)}
        G = {r[0]: tuple(r[1:]) for r in con.execute(f"select pair_id, {', '.join(gcols)} from two_view_geometries where pair_id in ({q})", ch)}
        for k in M:
            if k in G: out[k] = (M[k], G[k])
    return out


def _gleich(a, b):
    norm = lambda t: tuple(bytes(v) if isinstance(v, memoryview) else v for v in t)
    return norm(a[0]) == norm(b[0]) and norm(a[1]) == norm(b[1])


def matchen(db, paare_txt, rechnen, b, ordner, melden=print, stichprobe_min=16, stichprobe_anteil=0.005, abw_min=2, abw_anteil=0.02):
    """SIFT-Abgleich der Paare in <paare_txt> in <db> mit Paarspeicher. rechnen(db, paare_txt) -> verifizierte Paare (der bisherige Aufruf).
    <b> basis(), <ordner> ablage(db) oder None (dann nur rechnen). -> (verifiziert, statistik)."""
    if not ordner: return rechnen(db, paare_txt), dict(aus=True)
    con = None
    try:      # Vorbereitung + Einsetzen in EINER Transaktion; jeder Fehler hier -> Rueckrollen, bisheriger Weg (Stub-/Alt-Schema, fremde DB)
        t0 = time.time(); paare = [z.split() for z in open(paare_txt) if z.strip()]
        con = sqlite3.connect(db); mcols = [c for c in spalten(con, "matches") if c != "pair_id"]; gcols = [c for c in spalten(con, "two_view_geometries") if c != "pair_id"]
        fp = fingerabdruecke(con, {n for p in paare for n in p})
        vorh = {r[0] for r in con.execute("select pair_id from matches")} & {r[0] for r in con.execute("select pair_id from two_view_geometries")}
        offen = {}
        for x, y in paare:
            if x not in fp or y not in fp: continue
            (ix, hx, fx), (iy, hy, fy) = fp[x], fp[y]; pid = paar_id(ix, iy)
            if pid in vorh or pid in offen: continue
            offen[pid] = _sha(b, hx, hy, ix < iy, fx is not None and fx == fy)
        S, sp = _speicher_oeffnen(ordner, b, mcols, gcols); k2p = {k: p for p, k in offen.items()}; treffer = {}
        kl = list(k2p)
        for i in range(0, len(kl), 900):
            ch = kl[i:i + 900]
            for r in S.execute(f"select k, " + ", ".join(f'"m_{c}"' for c in mcols) + ", " + ", ".join(f'"g_{c}"' for c in gcols) + f" from m where k in ({','.join('?' * len(ch))})", ch):
                treffer[k2p[r[0]]] = (tuple(r[1:1 + len(mcols)]), tuple(r[1 + len(mcols):]))
        n_probe = min(len(treffer), max(stichprobe_min, int(len(treffer) * stichprobe_anteil)))
        probe = set(sorted(treffer, key=lambda p: hashlib.sha1(offen[p].encode()).hexdigest())[:n_probe])
        einsetzen = [p for p in treffer if p not in probe]
        if einsetzen:
            con.executemany(f"insert into matches (pair_id, {', '.join(mcols)}) values ({','.join('?' * (1 + len(mcols)))})", [(p,) + treffer[p][0] for p in einsetzen])
            con.executemany(f"insert into two_view_geometries (pair_id, {', '.join(gcols)}) values ({','.join('?' * (1 + len(gcols)))})", [(p,) + treffer[p][1] for p in einsetzen])
    except (sqlite3.Error, OSError, KeyError, ValueError, TypeError, AttributeError) as e_:
        if con is not None:
            try: con.rollback(); con.close()
            except sqlite3.Error: pass
        melden(f"SIFT-Paarspeicher: AUS fuer diesen Lauf ({type(e_).__name__}: {str(e_)[:120]}) - bisheriger Weg ohne Speicher", flush=True)
        return rechnen(db, paare_txt), dict(aus=True, grund=type(e_).__name__)
    con.commit(); con.close(); t_vor = time.time() - t0
    melden(f"SIFT-Paarspeicher: {len(paare)} Paare, {len(vorh & set(paar_id(fp[x][0], fp[y][0]) for x, y in paare if x in fp and y in fp))} schon in der Referenz-DB, "
           f"{len(offen)} zu matchen, davon {len(treffer)} aus dem Speicher ({len(einsetzen)} eingesetzt, Stichprobe {len(probe)} neu gerechnet) - {t_vor:.0f} s", flush=True)
    ver = rechnen(db, paare_txt); con = sqlite3.connect(db); st = dict(paare=len(paare), offen=len(offen), treffer=len(treffer), eingesetzt=len(einsetzen), stichprobe=len(probe), verworfen=False)
    if probe:
        neu = _lesen(con, probe, mcols, gcols); abw = [p for p in probe if p not in neu or not _gleich(neu[p], treffer[p])]
        st["abweichend"] = len(abw)
        if abw and len(abw) <= max(abw_min, abw_anteil * len(probe)):
            melden(f"SIFT-Paarspeicher: Stichprobe {len(abw)}/{len(probe)} Paare anders als gespeichert - im Rahmen des Rauschens von COLMAP selbst (mehrfaedig nicht wiederholbar, s. Kopf), Speicher bleibt", flush=True)
        elif abw:
            melden(f"WARNUNG SIFT-Paarspeicher: Stichprobe {len(abw)}/{len(probe)} Paare weichen vom Speicher ab - eingesetzte Zeilen verworfen, ALLE neu gerechnet, Speicher {sp} geloescht", flush=True)
            for i in range(0, len(einsetzen), 900):
                ch = einsetzen[i:i + 900]; q = ",".join("?" * len(ch))
                con.execute(f"delete from matches where pair_id in ({q})", ch); con.execute(f"delete from two_view_geometries where pair_id in ({q})", ch)
            con.commit(); con.close(); S.close(); os.remove(sp); ver = rechnen(db, paare_txt); con = sqlite3.connect(db)
            S, sp = _speicher_oeffnen(ordner, b, mcols, gcols); einsetzen = []; treffer = {}; st.update(verworfen=True)
    gerechnet = [p for p in offen if p not in set(einsetzen)]
    try:
        import shutil
        if shutil.disk_usage(ordner).free >= RESERVE_B:
            neu = _lesen(con, gerechnet, mcols, gcols); jetzt = time.time()
            S.executemany(f"insert or replace into m values ({','.join('?' * (2 + len(mcols) + len(gcols)))})", [(offen[p], jetzt) + neu[p][0] + neu[p][1] for p in neu])
            if einsetzen: S.executemany("update m set zeit=? where k=?", [(jetzt, offen[p]) for p in einsetzen])
            S.commit(); st["abgelegt"] = len(neu)
            gb = float(os.environ.get("RCPARK_SIFT_PAARSPEICHER_GB", "3"))
            if os.path.getsize(sp) > gb * 2 ** 30:      # aelteste Haelfte raus
                n = S.execute("select count(*) from m").fetchone()[0]; S.execute("delete from m where k in (select k from m order by zeit limit ?)", (n // 2,)); S.commit(); S.execute("vacuum")
        else: melden(f"SIFT-Paarspeicher: NICHT abgelegt (unter {RESERVE_B / 2 ** 30:.0f} GB frei unter {ordner})", flush=True)
    except (OSError, sqlite3.Error) as e: melden(f"SIFT-Paarspeicher: Ablegen fehlgeschlagen ({type(e).__name__} {e}) - Ergebnis bleibt gueltig", flush=True)
    con.close(); S.close(); st["sekunden"] = round(time.time() - t0, 1)
    return ver, st
