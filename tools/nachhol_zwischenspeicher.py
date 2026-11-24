#!/usr/bin/env python3
"""nachhol_zwischenspeicher.py - Ergebnis-Zwischenspeicher nach EINGABE-HASH fuer das Nachholen (tools/seiten_luecken.py), 24.11.2026.

Anlass (Kette schwabentor-null-1122w, Stufe seiten_luecken 48 min): SIFT-Merkmale + Abgleich fuer 388 Bilder 18 min - das Nachhol-Skript loescht am Ende
db.db (Platz auf /media/oem/scan, 17.11.2026: 3,2 GB), also rechnete JEDER Lauf dieselbe Datenbank neu; kamera_verfeinern fuer 267 Kameras ~17 min ebenso.
Regel: gleiche Eingaben (Schluessel = Hash von Bildinhalt, Einstellung, Paarliste, Quelltext ...) -> gespeichertes Ergebnis, BITGLEICH kopiert. Andere Eingabe ->
anderer Schluessel -> neu gerechnet. Der Aufrufer bildet den Schluessel (zusatzfotos_registrieren.merkmale_schluessel, kamera_verfeinern.kv_schluessel).
Ablage NIE auf Root: RCPARK_NACHHOL_CACHE (Ordner; "0" = aus), sonst /media/oem/rcdaten/rc-park_zwischenspeicher (gross), sonst
/media/oem/scan/rc-park_daten/zwischenspeicher; fehlen beide Platten -> aus (kein Ablegen, kein Holen).
  <wurzel>/<art>/<schluessel>/{dateien..., meta.json}. Je Art bleiben die RCPARK_NACHHOL_CACHE_N (Standard 3) zuletzt benutzten Eintraege (gross: db.db ~1,5-2 GB);
  kleine Arten (kamera_verfeinern: JSON je Kamera) mit behalten=None unbegrenzt.
  ablegen() nur bei genug Platz (Dateigroesse + 10 GB frei), atomar (Temp-Ordner -> rename); holen() kopiert nach <ziel>.tmp und benennt um, prueft Groesse gegen meta.json.
Test: tests/test_nachhol_zwischenspeicher.py (Schnelltest)."""
import os, json, time, shutil, hashlib

RESERVE_B = 10 * 2 ** 30


def wurzel():
    """Ablageordner oder None (aus). Nie Root: nur Datenplatten oder ausdruecklich RCPARK_NACHHOL_CACHE."""
    p = os.environ.get("RCPARK_NACHHOL_CACHE")
    if p: return None if p == "0" else p
    if os.path.isdir("/media/oem/rcdaten") and os.access("/media/oem/rcdaten", os.W_OK): return "/media/oem/rcdaten/rc-park_zwischenspeicher"
    if os.path.isdir("/media/oem/scan/rc-park_daten"): return "/media/oem/scan/rc-park_daten/zwischenspeicher"
    return None


def an(): return wurzel() is not None


def text_hash(*teile):
    """sha1 (40 Hex) ueber JSON-Darstellung der Teile (sortierte Schluessel)."""
    return hashlib.sha1(json.dumps(teile, sort_keys=True, default=str).encode()).hexdigest()


def _ordner(art, schl):
    w = wurzel(); return None if w is None else os.path.join(w, art, schl)


def holen(art, schl, ziele, melden=print):
    """ziele {name: zielpfad}. True = alle Dateien aus dem Speicher kopiert (bitgleich), False = kein (vollstaendiger) Eintrag - nichts veraendert."""
    d = _ordner(art, schl)
    if d is None or not os.path.isfile(os.path.join(d, "meta.json")): return False
    try: meta = json.load(open(os.path.join(d, "meta.json")))
    except (OSError, ValueError): return False
    gr = meta.get("groessen", {})
    if any(n not in gr or not os.path.isfile(os.path.join(d, n)) or os.path.getsize(os.path.join(d, n)) != gr[n] for n in ziele): return False
    for n, z in ziele.items():
        os.makedirs(os.path.dirname(os.path.abspath(z)), exist_ok=True); shutil.copyfile(os.path.join(d, n), z + ".tmp"); os.replace(z + ".tmp", z)
    try: os.utime(d)      # zuletzt benutzt (Aufraeumen behaelt die juengsten)
    except OSError: pass
    if melden: melden(f"ZWISCHENSPEICHER {art}: Eintrag {schl[:16]} uebernommen ({', '.join(ziele)}; gerechnet {meta.get('zeit')}) - gleiche Eingaben, gleiches Ergebnis", flush=True)
    return True


def ablegen(art, schl, quellen, behalten="std", melden=print, extra=None, gruppe=None):
    """quellen {name: pfad}. Legt eine Kopie unter <wurzel>/<art>/<schl>/ ab. Rueckgabe True/False (aus, zu wenig Platz, Fehler - nie Ausnahme).
    gruppe (Standard: Ordner der ersten Quelle = je Objekt): 'behalten' gilt JE GRUPPE (24.11.2026, nach Kette 1122zb: der 1,4-GB-Eintrag des Schwabentors war nach
    zwei 33-MB-Probelaeufen eines anderen Objekts der aelteste von 3 - der naechste fremde Eintrag haette ihn verdraengt, der Turm haette 17 min neu gerechnet).
    Standard statt Aufruferangabe, weil der Quelltext von zusatzfotos_registrieren.merkmale im Schluessel steht (eine Aenderung dort verwirft den vorhandenen Eintrag)."""
    d = _ordner(art, schl)
    if d is None: return False
    if gruppe is None and quellen: gruppe = os.path.dirname(os.path.abspath(next(iter(quellen.values()))))      # Standard: Ordner der ersten Quelle (Nachholen: <daten>/<objekt>/seiten_nachholen)
    try:
        groesse = sum(os.path.getsize(p) for p in quellen.values()); os.makedirs(os.path.dirname(d), exist_ok=True)
        frei = shutil.disk_usage(os.path.dirname(d)).free
        if groesse > 2 ** 24 and frei < groesse + RESERVE_B:
            if melden: melden(f"ZWISCHENSPEICHER {art}: NICHT abgelegt - {frei / 2 ** 30:.1f} GB frei, noetig {(groesse + RESERVE_B) / 2 ** 30:.1f} GB", flush=True)
            return False
        tmp = d + f".tmp{os.getpid()}"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
        for n, p in quellen.items(): shutil.copyfile(p, os.path.join(tmp, n))
        json.dump(dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), groessen={n: os.path.getsize(os.path.join(tmp, n)) for n in quellen}, **({"gruppe": str(gruppe)} if gruppe is not None else {}), **(extra or {})), open(os.path.join(tmp, "meta.json"), "w"), indent=1)
        shutil.rmtree(d, ignore_errors=True); os.rename(tmp, d)
    except OSError as e:
        if melden: melden(f"ZWISCHENSPEICHER {art}: Ablegen fehlgeschlagen ({type(e).__name__} {e}) - Ergebnis bleibt gueltig, naechster Lauf rechnet neu", flush=True)
        return False
    if behalten == "std":
        try: behalten = int(os.environ.get("RCPARK_NACHHOL_CACHE_N", "3"))
        except ValueError: behalten = 3
    if behalten: aufraeumen(art, behalten, gruppe=gruppe)
    if melden and groesse > 2 ** 24: melden(f"ZWISCHENSPEICHER {art}: Eintrag {schl[:16]} abgelegt ({groesse / 2 ** 30:.2f} GB unter {os.path.dirname(d)})", flush=True)
    return True


def _gruppe(p):
    try: return json.load(open(os.path.join(p, "meta.json"))).get("gruppe")
    except (OSError, ValueError): return None


def aufraeumen(art, behalten, gruppe=None):
    """Nur die <behalten> zuletzt benutzten Eintraege der Art bleiben (Temp-Reste aelter als 1 h weg) - mit <gruppe> nur unter den Eintraegen DIESER Gruppe
    (fremde Gruppen bleiben unberuehrt; Eintraege ohne Gruppe zaehlen als eigene Gruppe None)."""
    w = wurzel()
    if w is None or not os.path.isdir(os.path.join(w, art)): return
    eintr = []
    for n in os.listdir(os.path.join(w, art)):
        p = os.path.join(w, art, n)
        if ".tmp" in n:
            if time.time() - os.path.getmtime(p) > 3600: shutil.rmtree(p, ignore_errors=True)
            continue
        if os.path.isdir(p) and _gruppe(p) == (None if gruppe is None else str(gruppe)): eintr.append((os.path.getmtime(p), p))
    for _, p in sorted(eintr, reverse=True)[behalten:]: shutil.rmtree(p, ignore_errors=True)


# ---------- kleine Eintraege (JSON) ----------
def json_holen(art, schl):
    d = _ordner(art, schl[:2])
    if d is None: return None
    try: return json.load(open(os.path.join(d, schl + ".json")))
    except (OSError, ValueError): return None


def json_ablegen(art, schl, wert):
    d = _ordner(art, schl[:2])
    if d is None: return False
    try:
        os.makedirs(d, exist_ok=True); t = os.path.join(d, f"{schl}.json.{os.getpid()}.tmp"); json.dump(wert, open(t, "w")); os.replace(t, os.path.join(d, schl + ".json")); return True
    except OSError: return False
