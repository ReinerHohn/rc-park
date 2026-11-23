#!/usr/bin/env python3
"""http_holen.py - eine URL laden, bei HTTP 429/503 (Drosselung) mit Wartezeit und Backoff wiederholen (23.11.2026).
Anlass Lauf schwabentor-1122p: commons_harvest lud 60 Bilder in 70 s (jeden Lauf neu, 0,5 s Pause), danach brachen online_ansichten_holen (od_02)
und openverse_holen (upload.wikimedia.org) beim ersten HTTP 429 ab -> keine Fremdbilder fuer die Ostseite.
Regel (Wikimedia-Etikette, Lehre 9.11.: kein Retry-Sturm): Retry-After des Servers wird befolgt, sonst basis_s * 2^k (60, 120, 240 s ...), je Warten hoechstens
max_warte_s; alle Wartezeiten eines Prozesses zusammen hoechstens RCPARK_429_BUDGET_S (Standard 600 s). Danach Gedrosselt (Aufrufer sperrt die Quelle fuer den Lauf).
  import http_holen; daten = http_holen.hole(url, {"User-Agent": ...}, timeout=60)
"""
import os, time, email.utils, urllib.request, urllib.error, urllib.parse

DROSSEL = (429, 503)
_verbraucht = [0.0]      # Wartezeit dieses Prozesses (Budget gilt ueber alle Aufrufe)


class Gedrosselt(Exception):
    """Server drosselt weiter, Wartebudget/Versuche erschoepft."""


def budget_s():
    try: return float(os.environ.get("RCPARK_429_BUDGET_S", "600"))
    except ValueError: return 600.0


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


def hole(url, headers=None, timeout=60, versuche=4, basis_s=60.0, max_warte_s=300.0, schlafen=time.sleep, oeffnen=None, melden=print):
    """Bytes der URL. HTTP 429/503: warten (Retry-After/Backoff) und bis zu <versuche>-mal neu; danach Gedrosselt. Andere Fehler gehen unveraendert durch."""
    oeffnen = oeffnen or (lambda rq, timeout: urllib.request.urlopen(rq, timeout=timeout))
    for v in range(versuche):
        try:
            with oeffnen(urllib.request.Request(url, headers=headers or {}), timeout=timeout) as r: return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in DROSSEL: raise
            w = wartezeit(v, (e.headers or {}).get("Retry-After") if e.headers is not None else None, basis_s, max_warte_s)
            rest = budget_s() - _verbraucht[0]
            if v == versuche - 1 or w > rest:
                raise Gedrosselt(f"HTTP {e.code} {url[:90]}: nach {v + 1} Versuch(en) weiter gedrosselt (gewartet in diesem Prozess {_verbraucht[0]:.0f} s, Budget {budget_s():.0f} s)") from e
            melden(f"HTTP {e.code} von {urllib.parse.urlparse(url).netloc}: warte {w:.0f} s (Versuch {v + 1}/{versuche}, Retry-After {e.headers.get('Retry-After') if e.headers is not None else None})", flush=True)
            schlafen(w); _verbraucht[0] += w
    raise Gedrosselt(f"{url[:90]}: keine Versuche")
