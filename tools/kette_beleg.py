#!/usr/bin/env python3
"""kette_beleg.py - gemeinsamer BELEG-Helfer der Gesamtkette gegen 'stille Erfolge' (Audit 23.11.2026, modelle/AUDIT_STILLE_ERFOLGE_2026-11-23.md).

Fehlermuster: eine Stufe meldet rc 0 / 'in Ordnung', die FOLGESTUFE liest aber eine Ausgabe, die gar nicht aus diesem Lauf stammt (Werkzeug endete frueh ohne zu
schreiben, z. B. fassade_tiefe rc 2 'nur 2 Fotos'), oder eine Ausgabe ohne Inhalt. Belegt im Lauf 1122t: bauplan_sweep_f01 rc 2 schrieb nichts,
vorbauten_bauplan las vorbauten_f01.json des Laufs von 12:25 (Fassadennummern koennen sich zwischen Laeufen verschieben -> Vorbau eines alten Rahmens).

Regel (keine erfundenen Schwellen): eine erwartete Ausgabe ist BELEGT, wenn sie (1) existiert, (2) seit dem Stufenstart geschrieben wurde (mtime >= seit - 2 s,
wie gesamtkette.frisch) und (3) den Mindestinhalt hat, der sich aus der Sache ergibt (Menge > 0 bzw. alle Eingaben verarbeitet) - nur wenn die Stufe ihn angibt.
Altstaende werden NICHT geloescht, sondern beiseitegelegt (<datei>.veraltet_<marke>), damit kein Verbraucher sie als frisch liest.
  pruefen(pfade, seit, inhalt)  -> Liste der Verstoesse (leer = belegt)
  beiseite(pfade, seit, marke)  -> Liste der beiseitegelegten Altdateien (nur die, die NICHT seit 'seit' geschrieben wurden)
  db_fehlende_bilder(db, namen) -> Bilder ohne Eintrag/ohne Schluesselpunkte in einer COLMAP-Datenbank (SIFT laesst sie bei GPU-Speichermangel still weg)
  stl_pruefen(pfad, seit)       -> Bau belegt: STL frisch und > 0 Dreiecke (1122u: 84-Byte-STL bei rc 0); CLI 'kette_beleg.py stl <pfad> <seit>' fuer bauen_abnehmen.sh
  bearbeitet_urteil(...)        -> Listenstufe ohne ein bearbeitetes Element (mono: 0 Waende) ist NICHT in Ordnung
"""
import os, json, time, sqlite3


def frisch(pfad, seit):
    """True, wenn `pfad` existiert und seit `seit` (time.time() vor dem Stufenstart) geschrieben wurde. seit=None: nur Existenz (Einstieg ohne die Erzeugerstufe)."""
    if not os.path.exists(pfad): return False
    return seit is None or os.path.getmtime(pfad) >= seit - 2.0


def json_menge(pfad, schluessel=None):
    """Anzahl Eintraege: len(j[schluessel]) bzw. len(j) (Liste/dict). Unlesbar -> -1."""
    try: j = json.load(open(pfad))
    except Exception: return -1
    v = j.get(schluessel) if (schluessel and isinstance(j, dict)) else j
    return len(v) if isinstance(v, (list, dict)) else (-1 if v is None else 1)


def pruefen(pfade, seit=None, inhalt=None):
    """Verstoesse als Textliste. inhalt: dict pfad -> Funktion(pfad) -> (ok, text) fuer den sachlichen Mindestinhalt."""
    f = []
    for p in pfade:
        if not os.path.exists(p): f.append(f"{os.path.basename(p)} fehlt"); continue
        if not frisch(p, seit): f.append(f"{os.path.basename(p)} stammt aus einem FRUEHEREN Lauf ({time.strftime('%d.%m. %H:%M', time.localtime(os.path.getmtime(p)))}, Stufenstart {time.strftime('%d.%m. %H:%M', time.localtime(seit))})"); continue
        if inhalt and p in inhalt:
            try: ok_, txt = inhalt[p](p)
            except Exception as e_: ok_, txt = False, f"nicht lesbar: {type(e_).__name__} {e_}"
            if not ok_: f.append(f"{os.path.basename(p)}: {txt}")
    return f


def mindestens_eins(schluessel=None):
    """Inhaltspruefung 'Menge > 0' (aus der Sache: eine Liste ohne Eintrag belegt nichts)."""
    def _p(p):
        n = json_menge(p, schluessel); return n > 0, f"{'[' + schluessel + '] ' if schluessel else ''}leer ({n} Eintraege)"
    return _p


def beiseite(pfade, seit, marke=None):
    """Altdateien (existieren, aber NICHT seit `seit` geschrieben) -> <pfad>.veraltet_<marke>. Nichts wird geloescht. Rueckgabe: beiseitegelegte Pfade (neuer Name)."""
    marke = marke or time.strftime("%Y%m%d_%H%M%S"); weg = []
    for p in pfade:
        if os.path.exists(p) and seit is not None and not frisch(p, seit):
            z = f"{p}.veraltet_{marke}"; os.replace(p, z); weg.append(z)
    return weg


def stl_dreiecke(pfad):
    """Dreiecke eines STL (binaer: Kopfzahl, nur wenn die Dateigroesse dazu passt; ASCII: 'facet'-Zeilen). Unlesbar/kaputt -> -1. Ohne numpy/trimesh (System-Python)."""
    try:
        g = os.path.getsize(pfad)
        with open(pfad, "rb") as f: kopf = f.read(84)
        if len(kopf) == 84:
            n = int.from_bytes(kopf[80:84], "little")
            if g == 84 + 50 * n: return n
        if kopf[:5].lower() == b"solid":
            with open(pfad, "rb") as f: return sum(1 for z in f if z.lstrip().lower().startswith(b"facet"))
        return -1
    except OSError: return -1


def stl_pruefen(pfad, seit=None):
    """24.11.2026 (Kettenlauf 1122u): der Generator schrieb ein LEERES STL (84 Byte, 0 Dreiecke), bauen_abnehmen.sh meldete im Modus RCPARK_NUR_BAUEN=1 rc 0, alle
    Folgestufen stuerzten mit KeyError 'world'. Ein Bau ist nur belegt, wenn das STL existiert, seit dem Stufenstart geschrieben wurde und > 0 Dreiecke hat."""
    f_ = pruefen([pfad], seit)
    if f_: return f_
    n = stl_dreiecke(pfad)
    return [] if n > 0 else [f"{os.path.basename(pfad)}: {'unlesbar/kaputt' if n < 0 else '0 Dreiecke (leeres Modell)'} ({os.path.getsize(pfad)} Byte)"]


def bearbeitet_urteil(bearbeitet, versucht=None, uebersprungen=None, was="Waende"):
    """24.11.2026 (Audit Punkt 9, Stufe mono): eine Stufe, die ueber eine Liste laeuft und KEIN Element bearbeitet hat, hat nichts belegt - auch wenn jedes Einzelwerkzeug
    sein Urteil (rc 4) sauber meldete. Rueckgabe (ok, fehler): ok = mindestens ein Element bearbeitet; fehler nennt Versuche (rc je Element) und Uebersprungene."""
    if bearbeitet: return True, ""
    v_ = ", ".join(f"{k} rc {r}" for k, r in (versucht or {}).items()) or "keiner"
    return False, f"0 {was} bearbeitet (versucht: {v_}; uebersprungen: {', '.join(map(str, uebersprungen or [])) or 'keine'})"


def db_fehlende_bilder(db, namen):
    """Namen aus `namen`, die in der COLMAP-Datenbank fehlen oder 0 Schluesselpunkte haben. COLMAP/SiftGPU schreibt bei 'out of memory' nur 'Failed to process the image'
    und laesst das Bild WEG - extract_features endet trotzdem normal (Fall zusatzfotos_registrieren 23.11.2026). Datenbank ohne Tabellen -> alle fehlen."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try: ids = {n: i for i, n in con.execute("select image_id,name from images")}; kp = dict(con.execute("select image_id,rows from keypoints").fetchall())
        finally: con.close()
    except sqlite3.Error: return list(namen)
    return [n for n in namen if not kp.get(ids.get(n), 0)]


if __name__ == "__main__":      # 24.11.2026: Aufruf aus tools/bauen_abnehmen.sh:  python3 -I tools/kette_beleg.py stl <pfad> <seit (Unix-Zeit)>  -> rc 0 belegt, rc 4 Verstoss
    import sys
    if len(sys.argv) != 4 or sys.argv[1] != "stl": sys.exit("Aufruf: kette_beleg.py stl <pfad.stl> <seit>")
    f_ = stl_pruefen(sys.argv[2], float(sys.argv[3]))
    print("STL-BELEG: " + ("; ".join(f_) if f_ else f"{sys.argv[2]} frisch, {stl_dreiecke(sys.argv[2])} Dreiecke")); sys.exit(4 if f_ else 0)
