#!/usr/bin/env python3
"""prusa_print.py - Prusa MK4S ueber PrusaLink im LAN steuern: Zugang ablegen / Status / Upload + Druckstart (ohne Cloud).

  python3 tools/prusa_print.py zugang <benutzer> <passwort>     # einmalig; ODER: zugang --api-key <schluessel>
  python3 tools/prusa_print.py status
  python3 tools/prusa_print.py print <datei.gcode|.bgcode> [name_auf_dem_drucker]

Anlass 17.11.2026: der Nutzer erwartet, dass Drucke aus der Sitzung gestartet werden; die PrusaLink-Anmeldung war nirgends abgelegt (Repo, Memory, ~/.config) -
das Gegenstueck tools/p1s_print.py (Bambu) hat seine Daten im Skript. Hier liegen sie AUSSERHALB des Repos: ~/.config/rcpark/prusalink.json (nur fuer den Nutzer lesbar).
Drucker: prusa-mk4.local / 192.168.178.55 (PrusaLink, Digest-Login oder X-Api-Key). Schnittstelle PrusaLink v1: GET /api/v1/status, PUT /api/v1/files/usb/<name>
mit 'Print-After-Upload: ?1'. Vor dem Start wird geprueft: Drucker IDLE/READY/FINISHED, G-Code enthaelt die Duesenpruefung M862.1 (falsche Duese -> Drucker bricht selbst ab).
Grenze: ob das Blech leer ist, sieht dieses Werkzeug nicht - Status FINISHED heisst, das letzte Teil liegt vermutlich noch darauf (dann wird NICHT gestartet, ausser --trotzdem).
"""
import sys, os, json, urllib.request, urllib.error
CFG = os.path.expanduser("~/.config/rcpark/prusalink.json"); HOST = "192.168.178.55"


def zugang():
    if not os.path.exists(CFG): sys.exit(f"kein Zugang abgelegt ({CFG}) - einmalig: python3 tools/prusa_print.py zugang <benutzer> <passwort>   (am Drucker: Einstellungen > Netzwerk > PrusaLink)")
    return json.load(open(CFG))


def anfrage(methode, pfad, daten=None, kopf=None, timeout=600):
    z = zugang(); url = f"http://{z.get('host', HOST)}{pfad}"; kopf = dict(kopf or {})
    if z.get("api_key"): kopf["X-Api-Key"] = z["api_key"]; op = urllib.request.build_opener()
    else:
        pm = urllib.request.HTTPPasswordMgrWithDefaultRealm(); pm.add_password(None, url, z["benutzer"], z["passwort"]); op = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(pm))
    try:
        with op.open(urllib.request.Request(url, data=daten, method=methode, headers=kopf), timeout=timeout) as r: t = r.read(); return r.status, (json.loads(t) if t[:1] in (b"{", b"[") else t.decode(errors="replace"))
    except urllib.error.HTTPError as e: return e.code, e.read().decode(errors="replace")[:300]


def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == "zugang":
        os.makedirs(os.path.dirname(CFG), exist_ok=True); d = dict(host=HOST, api_key=a[2]) if a[1] == "--api-key" else dict(host=HOST, benutzer=a[1], passwort=a[2])
        fd = os.open(CFG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600); os.write(fd, json.dumps(d).encode()); os.close(fd); c, r = anfrage("GET", "/api/v1/status", timeout=15)
        print("Zugang abgelegt:", CFG, "| Anmeldung", "funktioniert" if c == 200 else f"SCHEITERT (HTTP {c})"); return 0 if c == 200 else 3
    c, st = anfrage("GET", "/api/v1/status", timeout=15)
    if c != 200: print(f"Status nicht lesbar: HTTP {c} {str(st)[:120]}" + (" - Anmeldung falsch?" if c in (401, 403) else "")); return 3
    p = st.get("printer", {}); zustand = p.get("state"); print(f"Zustand {zustand}, Duese {p.get('temp_nozzle')} C, Bett {p.get('temp_bed')} C" + (f", Auftrag {st['job'].get('progress')} % (noch {st['job'].get('time_remaining')} s)" if st.get("job") else ""))
    if a[0] == "status": return 0
    if a[0] == "print":
        f = a[1]; name = (a[2] if len(a) > 2 and not a[2].startswith("--") else os.path.basename(f)).replace(" ", "_"); kopf = open(f, "rb").read(400000)
        if f.endswith(".gcode") and b"M862.1" not in kopf: print("ABBRUCH: G-Code ohne Duesenpruefung M862.1 (mit tools/prusa_slice.py slicen)"); return 2
        if zustand not in ("IDLE", "READY", "FINISHED", "STOPPED") or (zustand == "FINISHED" and "--trotzdem" not in a): print(f"ABBRUCH: Drucker ist {zustand}" + (" - das letzte Teil liegt vermutlich noch auf dem Blech (leeren, dann --trotzdem)" if zustand == "FINISHED" else "")); return 4
        c, r = anfrage("PUT", "/api/v1/files/usb/" + urllib.request.quote(name), daten=open(f, "rb").read(), kopf={"Content-Type": "application/octet-stream", "Print-After-Upload": "?1", "Overwrite": "?1"})
        print(f"Upload {name}: HTTP {c} {str(r)[:160]}")
        if c not in (200, 201, 204): return 3
        import time; time.sleep(8); c, st = anfrage("GET", "/api/v1/status", timeout=15); print("nach dem Start:", st.get("printer", {}).get("state") if c == 200 else f"HTTP {c}"); return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
