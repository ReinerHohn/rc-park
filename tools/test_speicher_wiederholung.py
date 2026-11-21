#!/usr/bin/env python3
"""Stufe, die am Speicher scheitert, wird im Lauf wiederholt (Nutzer 21.11.2026; Lauf 1121p: w03 Signal 6 nach Kernel-OOM blieb weg)."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gesamtkette as GK
f = 0
def ok(b, t):
    global f
    print(("    ok " if b else "    FEHLER ") + t); f += (not b)
ok(GK.speichermangel(-9, ""), "Signal 9 = Speichermangel")
ok(GK.speichermangel(-6, ""), "Signal 6 = Speichermangel")
ok(GK.speichermangel(3, "    FEHLER (Werkzeug abgestuerzt): tiefe_lokal.py: vom System beendet (Signal 6)"), "Teilwerkzeug vom System beendet")
ok(GK.speichermangel(1, "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate"), "CUDA-OOM")
ok(not GK.speichermangel(3, "keine Stufe im Profil"), "normales 'geht nicht' wird NICHT wiederholt")
ok(not GK.speichermangel(0, "out of memory"), "rc 0 nie wiederholen")
ok(GK.speichermangel(2, "", kernel_oom=True), "Kernel-OOM waehrend der Stufe")
d = tempfile.mkdtemp(); zaehler = os.path.join(d, "n"); B = {"schritte": [], "_pfad": os.path.join(d, "b.json")}
skript = f"import os,signal\np={zaehler!r}\nn=int(open(p).read()) if os.path.exists(p) else 0\nopen(p,'w').write(str(n+1))\nprint('versuch',n+1,flush=True)\nos.kill(os.getpid(), signal.SIGKILL) if n==0 else print('fertig')"
os.environ["RCPARK_SPEICHER_WIEDERHOL"] = "2"; GK._speicher_abwarten = lambda *a, **k: None
rc, out = GK.lauf(B, "test_oom", [sys.executable, "-I", "-c", skript], os.path.join(d, "log"))
ok(rc == 0 and open(zaehler).read() == "2", f"Stufe nach Signal 9 einmal wiederholt und dann ok (rc {rc}, Versuche {open(zaehler).read()})")
ok(B["schritte"][0].get("speicher_wiederholung") == 1 and len(B["schritte"]) == 2, "Bericht vermerkt die Wiederholung")
os.remove(zaehler); B["schritte"] = []
rc, out = GK.lauf(B, "test_normal", [sys.executable, "-I", "-c", "import sys;print('kein Ergebnis');sys.exit(3)"], os.path.join(d, "log"))
ok(rc == 3 and len(B["schritte"]) == 1, "rc 3 ohne Speichermangel -> keine Wiederholung")
print(f"{'FEHLER' if f else 'OK'} speicher_wiederholung ({f} Fehler)"); sys.exit(1 if f else 0)
