#!/usr/bin/env python3
"""http_holen.py - eine URL laden, bei HTTP 429/503 (Drosselung) mit Wartezeit und Backoff wiederholen (23.11.2026).
Anlass Lauf schwabentor-1122p: commons_harvest lud 60 Bilder in 70 s (jeden Lauf neu, 0,5 s Pause), danach brachen online_ansichten_holen (od_02)
und openverse_holen (upload.wikimedia.org) beim ersten HTTP 429 ab -> keine Fremdbilder fuer die Ostseite.
Regel (Wikimedia-Etikette, Lehre 9.11.: kein Retry-Sturm): Retry-After des Servers wird befolgt, sonst basis_s * 2^k (60, 120, 240 s ...), je Warten hoechstens
max_warte_s; alle Wartezeiten eines Prozesses zusammen hoechstens RCPARK_429_BUDGET_S (Standard 600 s). Danach Gedrosselt (Aufrufer sperrt die Quelle fuer den Lauf).
  import http_holen; daten = http_holen.hole(url, {"User-Agent": ...}, timeout=60)
DROSSEL-MARKE (23.11.2026, Lauf 1122q: 13,5 min Downloads, davon 12 min Warten auf upload.wikimedia.org - online_ansichten_holen und openverse_holen warteten
JE 360 s, Ergebnis 2/40 Bilder): endet das Warten mit Gedrosselt, schreibt hole() eine Marke {host: zeit, code} in RCPARK_DROSSEL_DATEI (Standard
/media/oem/scan/rc-park_daten/drossel_marken.json, prozess- und laufuebergreifend; "0" = aus). Ist die Marke juenger als RCPARK_DROSSEL_MARKE_H (Standard 24 h)
UND hat der Aufrufer schon Bilder dieser Quelle (vorrat_melden(n) bzw. hole(..., vorrat=True)), dann wird beim naechsten 429 dieses Hosts NICHT gewartet:
sofort Gedrosselt (ein einziger Versuch je Lauf, kein Retry-Sturm). Ohne Vorrat wird wie bisher gewartet. Ein Erfolg vom Host loescht seine Marke.
"""
import os, json, time, email.utils, urllib.request, urllib.error, urllib.parse

DROSSEL = (429, 503)
_verbraucht = [0.0]      # Wartezeit dieses Prozesses (Budget gilt ueber alle Aufrufe)
_vorrat = [False]        # Aufrufer hat schon Bilder (vorrat_melden): bei frischer Drossel-Marke nicht warten


class Gedrosselt(Exception):
    """Server drosselt weiter, Wartebudget/Versuche erschoepft."""


def budget_s():
    try: return float(os.environ.get("RCPARK_429_BUDGET_S", "600"))
    except ValueError: return 600.0


def marken_datei():
    """Pfad der Drossel-Marken (None = abgeschaltet)."""
    p = os.environ.get("RCPARK_DROSSEL_DATEI")
    if p: return None if p == "0" else p
    d = "/media/oem/scan/rc-park_daten"
    return os.path.join(d, "drossel_marken.json") if os.path.isdir(d) else os.path.join(os.path.expanduser("~/.cache/rcpark"), "drossel_marken.json")


def marke_h():
    try: return float(os.environ.get("RCPARK_DROSSEL_MARKE_H", "24"))
    except ValueError: return 24.0


def marken_lesen():
    p = marken_datei()
    try: return json.load(open(p)) if p and os.path.exists(p) else {}
    except (OSError, ValueError): return {}


def _marken_schreiben(m):
    p = marken_datei()
    if not p: return
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True); t = f"{p}.{os.getpid()}.tmp"; json.dump(m, open(t, "w"), indent=1); os.replace(t, p)
    except OSError: pass      # Marke ist nur eine Abkuerzung - ein Schreibfehler darf keinen Download abbrechen


def marke_alter_s(host, jetzt=None):
    """Alter der Drossel-Marke des Hosts in s, None = keine oder abgelaufen (> RCPARK_DROSSEL_MARKE_H)."""
    e = marken_lesen().get(host)
    if not isinstance(e, dict) or "zeit" not in e: return None
    alt = (time.time() if jetzt is None else jetzt) - float(e["zeit"])
    return alt if 0 <= alt <= marke_h() * 3600 else None


def marke_setzen(host, code, grund="", jetzt=None):
    m = marken_lesen(); m[host] = dict(zeit=time.time() if jetzt is None else jetzt, code=int(code), grund=str(grund)[:160], datum=time.strftime("%Y-%m-%d %H:%M:%S")); _marken_schreiben(m)


def marke_loeschen(host):
    m = marken_lesen()
    if host in m: m.pop(host); _marken_schreiben(m)


def vorrat_melden(n):
    """Aufrufer meldet, wie viele Bilder dieser Quelle er schon hat (> 0: bei frischer Drossel-Marke nicht mehr warten)."""
    _vorrat[0] = bool(n and n > 0)


def retry_after_s(wert, jetzt=None):
    """Retry-After-Kopf -> Sekunden (Zahl oder HTTP-Datum); None = nicht lesbar."""
    if not wert: return None
    wert = str(wert).strip()
    if wert.isdigit(): return float(wert)
    try:
        t = email.utils.parsedate_to_datetime(wert).timestamp(); return max(0.0, t - (time.time() if jetzt is None else jetzt))
    except (TypeError, ValueError, IndexError, OverflowError): return None


def wartezeit(versuch, kopf, basis_s=60.0, max_warte_s=300.0):
    """Wartezeit vor dem naechsten Versuch: Retry-After, sonst basis_s * 2^versuch; gedeckelt auf max_warte_s."""
    ra = retry_after_s(kopf)
    return min(max_warte_s, ra if ra is not None else basis_s * (2 ** versuch))


def hole(url, headers=None, timeout=60, versuche=4, basis_s=60.0, max_warte_s=300.0, schlafen=time.sleep, oeffnen=None, melden=print, vorrat=None):
    """Bytes der URL. HTTP 429/503: warten (Retry-After/Backoff) und bis zu <versuche>-mal neu; danach Gedrosselt (+ Drossel-Marke). Andere Fehler gehen unveraendert durch.
    vorrat (None = vorrat_melden-Stand): Aufrufer hat schon Bilder -> bei frischer Drossel-Marke des Hosts sofort Gedrosselt statt warten."""
    oeffnen = oeffnen or (lambda rq, timeout: urllib.request.urlopen(rq, timeout=timeout))
    host = urllib.parse.urlparse(url).netloc; vorrat = _vorrat[0] if vorrat is None else bool(vorrat)
    for v in range(versuche):
        try:
            with oeffnen(urllib.request.Request(url, headers=headers or {}), timeout=timeout) as r: daten = r.read()
            if v or host in marken_lesen(): marke_loeschen(host)      # Host liefert wieder: Marke weg
            return daten
        except urllib.error.HTTPError as e:
            if e.code not in DROSSEL: raise
            alt = marke_alter_s(host) if vorrat else None
            if alt is not None:
                marke_setzen(host, e.code, f"weiter gedrosselt {url[:90]}")
                raise Gedrosselt(f"HTTP {e.code} {url[:90]}: Quelle {host} war schon vor {alt / 3600:.1f} h gedrosselt (Marke {marken_datei()}) und es liegen schon Bilder vor - "
                                 f"kein erneutes Warten (RCPARK_DROSSEL_MARKE_H={marke_h():g})") from e
            w = wartezeit(v, (e.headers or {}).get("Retry-After") if e.headers is not None else None, basis_s, max_warte_s)
            rest = budget_s() - _verbraucht[0]
            if v == versuche - 1 or w > rest:
                marke_setzen(host, e.code, url[:90])
                raise Gedrosselt(f"HTTP {e.code} {url[:90]}: nach {v + 1} Versuch(en) weiter gedrosselt (gewartet in diesem Prozess {_verbraucht[0]:.0f} s, Budget {budget_s():.0f} s)") from e
            melden(f"HTTP {e.code} von {urllib.parse.urlparse(url).netloc}: warte {w:.0f} s (Versuch {v + 1}/{versuche}, Retry-After {e.headers.get('Retry-After') if e.headers is not None else None})", flush=True)
            schlafen(w); _verbraucht[0] += w
    raise Gedrosselt(f"{url[:90]}: keine Versuche")
