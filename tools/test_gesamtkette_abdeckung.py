#!/usr/bin/env python3
"""Mini-Test (< 2 s) Stufe 'abdeckung_zusatz' in tools/gesamtkette.py (Abdeckungsmeldung nach der Registrierung von Zusatzfotos, 26.11.2026).
lauf() ist ersetzt (kein Rechnen): er prueft den Aufruf von tools/abdeckung_meldung.py und schreibt eine kleine Meldung.
  1 ohne objekt.json 'zusatzfotos'     -> uebersprungen (gruen, Grund), abdeckung_meldung NICHT gestartet
  2 Zusatzordner (registriert, lg/)    -> Aufruf mit --registrierung/--sparse/--ausrichtung/--bilder, Ausgabe <obj>/audit; Zone 'nicht belegt' -> ROT mit Grund + Fotoauftrag
  3 alle Zonen belegt                  -> gruen (Gegenprobe zu 2)
  4 Werkzeug schreibt nichts (rc 1)    -> rot 'nicht geschrieben', KEIN Abbruch (Funktion kehrt zurueck)
  5 Ordner ohne Registrierung          -> rot mit Grund; ohne Zonenliste -> Standardzonen (Waende+Dach) + Hinweis
  6 Kette ruft abdeckung_zusatz in der Stufe seiten auf
  7 (27.11., Review 4) ohne objekt.json 'zusatzfotos', aber messprotokoll/*/einpassung.json mit 'ref' -> Zusatzordner automatisch gefunden und gemeldet;
    Gegenprobe: 'ref' zeigt ins Leere -> uebersprungen. Teile einer Sonderstelle mit Lagedatei offen -> foto_auftrag_lage.py fuer diese Stelle
Python: /media/oem/scan/venv-seg/bin/python -I tools/test_gesamtkette_abdeckung.py"""
import os, sys, json, re, tempfile
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T); os.environ["RCPARK_PLATZ_TOR"] = "test_ersetzt"
import gesamtkette as G

fehler = []
def pruef(b, t):
    if not b: fehler.append(t); print("FEHLER:", t)

from pfade import temp_ordner
tmp = temp_ordner("test_gk_abdeckung_"); Z = os.path.join(tmp, "modelle", "obj"); os.makedirs(Z)
AU = os.path.join(Z, "SFM-AUSRICHTUNG-obj.json"); open(AU, "w").write("{}")
zo = os.path.join(tmp, "zusatz"); lg = os.path.join(zo, "lg"); os.makedirs(os.path.join(lg, "sparse_handy", "0")); os.makedirs(os.path.join(lg, "bilder"))
open(os.path.join(lg, "registrierung.json"), "w").write("{}"); open(os.path.join(lg, "sparse_handy", "0", "images.bin"), "wb").write(b"x")
json.dump(dict(waende="auto", sonderstellen=[]), open(os.path.join(Z, "abdeckung_zonen.json"), "w"))
AUFRUFE = []; MODUS = ["rot"]


def fake_lauf(B, name, cmd, log, ok=(0,), timeout=None, platz=()):
    AUFRUFE.append(cmd); B["schritte"].append(dict(stufe=name, rc=0, ok=True))
    if MODUS[0] == "nichts": return 1, ""
    aus = cmd[cmd.index("--aus") + 1]; os.makedirs(aus, exist_ok=True)
    if "tools/abdeckung_meldung.py" not in cmd: return 0, ""
    z = [dict(name="Nord", status="belegt", fehlt=[]), dict(name="Treppe", status="nicht belegt" if MODUS[0] == "rot" else "belegt",
                                                             fehlt=["Lage im Netz unbekannt"] if MODUS[0] == "rot" else [])]
    if MODUS[0] == "steg": z.append(dict(name="Bruecke Dach", gruppe="Bruecke", status="nicht belegt", fehlt=["0 Fotos"]))
    json.dump(dict(fotos=10, eingeordnet=6, gruende={"keine Korrespondenz": 4}, zonen=z, fotoauftrag=[dict(stelle="Treppe")] if MODUS[0] == "rot" else []),
              open(os.path.join(aus, "abdeckung_meldung.json"), "w"))
    return 0, ""


G.lauf = fake_lauf
neu = lambda: dict(schritte=[], _pfad=os.path.join(tmp, "bericht.json"))
schritt = lambda B: [s for s in B["schritte"] if s["stufe"] == "abdeckung_zusatz"]
# 1
B = neu(); G.abdeckung_zusatz(B, "modelle/obj/objekt.json", Z, AU, os.path.join(tmp, "log"), {})
pruef(not AUFRUFE and len(schritt(B)) == 1 and schritt(B)[0]["ok"] and "keine Zusatzfotos" in schritt(B)[0].get("uebersprungen", ""), "1: ohne Zusatzfotos nicht sauber uebersprungen")
# 2
B = neu(); G.abdeckung_zusatz(B, "modelle/obj/objekt.json", Z, AU, os.path.join(tmp, "log"), dict(zusatzfotos=zo)); c = AUFRUFE[-1] if AUFRUFE else []
pruef("tools/abdeckung_meldung.py" in c and c[c.index("--registrierung") + 1] == os.path.join(lg, "registrierung.json") and c[c.index("--sparse") + 1] == os.path.join(lg, "sparse_handy", "0")
      and c[c.index("--ausrichtung") + 1] == AU and c[c.index("--aus") + 1] == os.path.join(Z, "audit") and "--bilder" in c and c[c.index("--zonen") + 1] == os.path.join(Z, "abdeckung_zonen.json"),
      f"2: Aufruf falsch: {c}")
s = schritt(B); pruef(len(s) == 1 and s[0]["ok"] is False and any("Treppe" in x for x in s[0]["nicht_belegt"]) and s[0]["fotoauftrag"] == ["Treppe"] and s[0]["bild"].endswith("audit/abdeckung_meldung.png"),
                      f"2: nicht belegte Zone nicht rot mit Grund gemeldet: {s}")
# 3
MODUS[0] = "gruen"; B = neu(); G.abdeckung_zusatz(B, "modelle/obj/objekt.json", Z, AU, os.path.join(tmp, "log"), dict(zusatzfotos=[zo]))
pruef(len(schritt(B)) == 1 and schritt(B)[0]["ok"] is True and not schritt(B)[0]["nicht_belegt"], f"3: alle belegt muss gruen sein: {schritt(B)}")
# 4
MODUS[0] = "nichts"; os.remove(os.path.join(Z, "audit", "abdeckung_meldung.json")); B = neu()
try: G.abdeckung_zusatz(B, "modelle/obj/objekt.json", Z, AU, os.path.join(tmp, "log"), dict(zusatzfotos=[zo])); abbruch = False
except SystemExit: abbruch = True
pruef(not abbruch and schritt(B) and schritt(B)[-1]["ok"] is False and "nicht geschrieben" in schritt(B)[-1]["fehler"], f"4: fehlende Meldung nicht rot / Abbruch: {schritt(B)}")
# 5
MODUS[0] = "rot"; os.remove(os.path.join(Z, "abdeckung_zonen.json")); leer = os.path.join(tmp, "leer"); os.makedirs(leer); B = neu(); n0 = len(AUFRUFE)
G.abdeckung_zusatz(B, "modelle/obj/objekt.json", Z, AU, os.path.join(tmp, "log"), dict(zusatzfotos=[leer, zo])); s = schritt(B)
pruef(any(x["ok"] is False and "ohne registrierung.json" in x.get("fehler", "") for x in s), "5: Ordner ohne Registrierung nicht rot gemeldet")
pruef(len(AUFRUFE) == n0 + 1 and AUFRUFE[-1][AUFRUFE[-1].index("--zonen") + 1].endswith("abdeckung_zonen_standard.json") and any("abdeckung_zonen.json fehlt" in x.get("hinweis", "") for x in s),
      "5: ohne Zonenliste keine Standardzonen + Hinweis")
# 6
q = open(os.path.join(T, "gesamtkette.py")).read()
pruef(re.search(r'if dran\("seiten"\)[^\n]*\n\s+abdeckung_zusatz\(B, ZR, Z, AU, log', q) is not None, "6: gesamtkette ruft abdeckung_zusatz nicht in der Stufe seiten auf")
# 7
mp = os.path.join(Z, "messprotokoll", "bruecke_lage"); os.makedirs(mp); json.dump(dict(ref=os.path.join(lg, "sparse_handy", "0")), open(os.path.join(mp, "einpassung.json"), "w"))
MODUS[0] = "steg"; B = neu(); n0 = len(AUFRUFE); G.abdeckung_zusatz(B, "modelle/obj/objekt.json", Z, AU, os.path.join(tmp, "log"), {}); neu_ = AUFRUFE[n0:]
pruef(any("tools/abdeckung_meldung.py" in c and c[c.index("--registrierung") + 1] == os.path.join(lg, "registrierung.json") for c in neu_),
      f"7: Zusatzordner aus einpassung.json nicht automatisch gefunden: {neu_}")
fa = [c for c in neu_ if "tools/foto_auftrag_lage.py" in c]
pruef(len(fa) == 1 and fa[0][fa[0].index("--stelle") + 1] == "Bruecke", f"7: offener Stegteil ohne foto_auftrag_lage-Aufruf: {fa}")
json.dump(dict(ref="/gibt/es/nicht/sparse_handy/0"), open(os.path.join(mp, "einpassung.json"), "w")); B = neu(); n0 = len(AUFRUFE)
G.abdeckung_zusatz(B, "modelle/obj/objekt.json", Z, AU, os.path.join(tmp, "log"), {})
pruef(len(AUFRUFE) == n0 and schritt(B) and schritt(B)[0]["ok"] and "uebersprungen" in schritt(B)[0], "7 Gegenprobe: einpassung.json ins Leere darf nichts starten")
__import__("shutil").rmtree(tmp, ignore_errors=True)
if fehler: print(f"ROT: {len(fehler)} Fehler"); sys.exit(1)
print("ok test_gesamtkette_abdeckung")
