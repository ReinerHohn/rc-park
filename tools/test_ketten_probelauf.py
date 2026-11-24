#!/usr/bin/env python3
"""Test des Ketten-Probelaufs (tools/ketten_probe.py + tools/ketten_probelauf.sh, 24.11.2026; Anlass Kettenlauf 1122za: Abbruch nach 2 min, weil die dichte Wolke
"aelter als das SfM-Netz" war - Schnelltest und Einzeltests hatten es nicht gesehen). Ohne Rechenlast (< 5 s, nur Standardbibliothek):
  1 Auswertung: sauberer Lauf = OK; 1122za-Fall (veralteter Stand + Handanweisung) = FEHLER mit erstem Fehler; Lage-Abbruch = KEIN_URTEIL; Lauf ohne Ende,
    Traceback, roter *_beleg = FEHLER; im Grundstand bekannte rote Stufe = nur Hinweis; rote Tor-Urteile (Daten) sperren nicht.
  2 Marken: Code-Staende in seiten_modelle.json/stand.json/drahtmaske werden verstellt, Daten-Kennungen (RAHMEN id, K-Datei rahmen) und beiseitegelegte
    *.alt_*-Staende nicht; das Netz sparse/0 wird "neu"; --plan schreibt nichts.
  3 Sichern: nur Dateien nach der Marke. 4 Fotowahl: ueber den Blickwinkel verteilt. 5 Skript: Syntax, Planmodus ohne Grundstand = rc 3 und schreibt nichts."""
import os, sys, json, time, tempfile, tarfile, subprocess
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import ketten_probe as KP

F = 0
def pruef(b, t):
    global F
    print(("    ok    " if b else "    FEHLER ") + t); F += (not b)


def bericht(schritte, erg=None, start="2026-11-24 15:23:10"):
    B = dict(schritte=[dict(stufe="LAUF_START", ok=True, zeit="2026-11-24 10:00:00"), dict(stufe="alt_rot", ok=False, fehler="aelter als vorher")]
             + [dict(stufe="LAUF_START", ok=True, zeit=start)] + schritte)
    if erg is not None: B["lauf_ergebnis"] = dict(dict(zeit="2026-11-24 15:40:00", rc=0, abbruch=""), **erg)
    return B


ENDE = ["x", "GESAMTKETTE_ENDE /pfad"]
gut = [dict(stufe="sfm", ok=True, sekunden=300, rc=0), dict(stufe="bauen", ok=True, sekunden=60, rc=0), dict(stufe="seiten", ok=False, fehler="Wand w03 ohne Fotos (Seitenluecke)")]
R = KP.auswerten(bericht(gut, dict(rc=4)), ENDE)
pruef(R["urteil"] == 0 and R["daten"] and R["daten"][0][0] == "seiten" and R["sekunden"] == 360, f"sauberer Lauf mit rotem Daten-Tor = OK ({R['urteil']}, Daten {R['daten'][:1]})")
za = [dict(stufe="sfm_bis_kameras", ok=False, rc=3, sekunden=97, ende=["[OK] sfm: registriert 903 von 1147", "[FEHLER] dicht: aelter als das SfM-Netz: sfm/sparse_dicht/images.bin - neu rechnen mit --neu dicht"]),
      dict(stufe="abbruch", ok=False, fehler="SfM gescheitert (rc 3)")]
R = KP.auswerten(bericht(za, dict(rc=4, abbruch="SfM gescheitert (rc 3) - Wolke/Ausrichtung eines frueheren Laufs werden NICHT weiterverwendet")), ENDE)
pruef(R["urteil"] == 1 and R["erster_fehler"][0] == "sfm_bis_kameras" and "aelter als" in R["erster_fehler"][1], f"Fall 1122za = FEHLER, erster Fehler {R['erster_fehler'] and R['erster_fehler'][0]}")
R = KP.auswerten(bericht([dict(stufe="tor_gps", ok=False, fehler="GPS widerspricht 40 m")], dict(rc=3, abbruch="keine Lage besteht alle Tore - nicht modellieren")), ENDE)
pruef(R["urteil"] == 2 and not R["ablauf"], f"Lage-Abbruch = KEIN_URTEIL ({R['urteil']})")
B_ = bericht(gut); B_["lauf_ergebnis"] = dict(zeit="2026-11-24 12:00:00", rc=0, abbruch="")      # Ergebnis eines FRUEHEREN Laufs
R = KP.auswerten(B_, ["kein Ende"]); pruef(R["urteil"] == 1 and R["ablauf"][-1][0] == "ende", "Lauf ohne GESAMTKETTE_ENDE (Ergebnis vom Vorlauf) = FEHLER")
R = KP.auswerten(bericht(gut, {}), ENDE + ["Traceback (most recent call last):", "KeyError: 'x'"]); pruef(R["urteil"] == 1 and R["ablauf"][0][0] == "traceback", "Traceback im Log = FEHLER")
bel = gut + [dict(stufe="fenster_beleg", ok=False, fehler="fassaden.json nicht in diesem Lauf geschrieben")]
R = KP.auswerten(bericht(bel, {}), ENDE); pruef(R["urteil"] == 1 and R["erster_fehler"][0] == "fenster_beleg", "roter *_beleg (stiller Erfolg) = FEHLER")
B_t = bericht(gut); B_t["teillauf_ergebnis"] = dict(zeit="2026-11-24 15:40:00", rc=0, abbruch="")
R = KP.auswerten(B_t, ["GESAMTKETTE_TEILLAUF_ENDE /x/gesamtkette_bericht.json"]); pruef(R["urteil"] == 0, "Teillauf (--bis anlegen) mit GESAMTKETTE_TEILLAUF_ENDE = OK, kein Absturz (Grundstand 24.11.)")
R = KP.auswerten(B_t); pruef(R["urteil"] == 0, "Teillauf ohne Log: teillauf_ergebnis zaehlt als Ende")
R = KP.auswerten(bericht([dict(stufe="abnahme_x", ok=False, fehler="  -> 0 veraltete Auto-Beobachtung(en) dieses Fotos ersetzt | ABNAHME rc=3")], dict(rc=4)), ENDE); pruef(R["urteil"] == 0 and not R["ablauf"], "Abnahme rot mit Text veraltete Auto-Beobachtung = Daten, kein Ablauffehler (Grundstand 24.11.)")
R = KP.auswerten(bericht(bel, {}), ENDE, bekannt=["fenster_beleg"]); pruef(R["urteil"] == 0, "dieselbe Stufe im Grundstand schon rot (--bekannt) = nur Hinweis")
pruef(R["stufen"] == 4 and all(n != "alt_rot" for n, _ in R["daten"] + R["ablauf"]), "nur der letzte Lauf (ab LAUF_START) zaehlt")

# 2 Marken
import pfade; S = pfade.temp_ordner(prefix="kprobe_test_"); D = os.path.join(S, "daten"); Z = os.path.join(S, "modell")
def js(p, o): os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(o, open(p, "w"))
js(os.path.join(D, "pipe", "sfm", "seiten_modelle.json"), dict(ergebnis=dict(art="vereint"), nachstufe_code="fdf6375caffd+belegt0"))
js(os.path.join(D, "pipe", "sfm", "seiten_modelle", "vereinen_0_1", "stand.json"), dict(stand=[["/a/images.bin", 1, 2], "abcdef012345"]))
js(os.path.join(D, "pipe", "sfm", "dicht", "fused.ply.drahtmaske.json"), dict(detektor="0123456789ab_cv4.12"))
js(os.path.join(D, "pipe", "sfm.alt_20261124", "seiten_modelle.json"), dict(nachstufe_code="fdf6375caffd"))
js(os.path.join(Z, "messprotokoll", "RAHMEN.json"), dict(aktuell=dict(id="aaaaaaaaaaaa")))
js(os.path.join(Z, "messprotokoll", "K-x.json"), dict(kamera=dict(rahmen="bbbbbbbbbbbb")))
sp = os.path.join(D, "pipe", "sfm", "sparse", "0"); os.makedirs(sp); open(os.path.join(sp, "images.bin"), "w").write("x"); os.utime(os.path.join(sp, "images.bin"), (1e9, 1e9))
g, nf = KP.marken(D, Z, plan=True)
pruef(len(g) == 3 and json.load(open(os.path.join(D, "pipe", "sfm", "seiten_modelle.json")))["nachstufe_code"].startswith("fdf6") and os.path.getmtime(os.path.join(sp, "images.bin")) < 2e9,
      f"--plan: 3 Marken gefunden, nichts geschrieben ({[p for p, _ in g]})")
g, nf = KP.marken(D, Z)
sm = json.load(open(os.path.join(D, "pipe", "sfm", "seiten_modelle.json"))); st = json.load(open(os.path.join(D, "pipe", "sfm", "seiten_modelle", "vereinen_0_1", "stand.json")))
pruef(sm["nachstufe_code"] == "000000000000+belegt0" and st["stand"][1] == "000000000000" and st["stand"][0][0] == "/a/images.bin"
      and json.load(open(os.path.join(D, "pipe", "sfm", "dicht", "fused.ply.drahtmaske.json")))["detektor"] == "000000000000_cv4.12", "Code-Staende verstellt (Anhang bleibt)")
pruef(json.load(open(os.path.join(D, "pipe", "sfm.alt_20261124", "seiten_modelle.json")))["nachstufe_code"] == "fdf6375caffd"
      and json.load(open(os.path.join(Z, "messprotokoll", "RAHMEN.json")))["aktuell"]["id"] == "aaaaaaaaaaaa"
      and json.load(open(os.path.join(Z, "messprotokoll", "K-x.json")))["kamera"]["rahmen"] == "bbbbbbbbbbbb", "beiseitegelegte Staende und Daten-Kennungen unberuehrt")
pruef(os.path.getmtime(os.path.join(sp, "images.bin")) > time.time() - 60 and nf == ["images.bin"], "Netz sparse/0 'neu geschrieben' (Zeit jetzt)")

# 3 Sichern
C = os.path.join(S, "code"); os.makedirs(os.path.join(C, "tools")); open(os.path.join(C, "tools", "alt.py"), "w").write("x"); os.utime(os.path.join(C, "tools", "alt.py"), (1e9, 1e9))
mk = os.path.join(C, ".export_marke"); open(mk, "w").close(); os.utime(mk, (time.time() - 5, time.time() - 5))
os.makedirs(os.path.join(C, "modelle", "kprobe_x")); open(os.path.join(C, "modelle", "kprobe_x", "objekt.json"), "w").write("{}")
os.makedirs(os.path.join(C, "daten", "kprobe_x")); os.symlink("/nirgends/fotos", os.path.join(C, "daten", "kprobe_x", "fotos"))
gs_alt = os.path.join(C, "modelle", "kprobe_x", "aus_grundstand.json"); open(gs_alt, "w").write("{}"); os.utime(gs_alt, (1e9, 1e9))   # frueherer Grundstand, nicht neu geschrieben
tp = os.path.join(S, "root.tar"); KP.sichern(C, mk, tp); nm = sorted(tarfile.open(tp).getnames())
pruef("modelle/kprobe_x/objekt.json" in nm and "daten/kprobe_x/fotos" in nm and "tools/alt.py" not in nm and ".export_marke" not in nm, f"sichern: Neues nach der Marke ({nm})")
KP.sichern(C, mk, tp, getrackt={"tools/alt.py"}); nm = sorted(tarfile.open(tp).getnames())
pruef("modelle/kprobe_x/aus_grundstand.json" in nm and "tools/alt.py" not in nm, "sichern mit Repo-Liste: alte Kettenausgabe bleibt, getrackte Datei nicht")

# 4 Fotowahl
import math
K = dict(bilder=[dict(name=f"eigen__b{i}.jpg", C=[10 * math.cos(i * math.pi / 4), 10 * math.sin(i * math.pi / 4), 1]) for i in range(8)])
fo = os.path.join(S, "fotos"); os.makedirs(fo)
for b in K["bilder"]: open(os.path.join(fo, b["name"]), "w").write("jpg")
js(os.path.join(S, "kameras.json"), K)
ok = KP.fotowahl(os.path.join(S, "kameras.json"), fo, os.path.join(S, "wahl"), n=4)
ws = sorted(os.listdir(os.path.join(S, "wahl"))); wk = sorted(int(n_[1]) for n_ in ws)
pruef(len(ok) == 4 and ws[0].startswith("b") and all(wk[i + 1] - wk[i] == 2 for i in range(3)), f"Fotowahl: 4 von 8, je 90 Grad, Praefix eigen__ weg ({ws})")

# 5 Skript
sh = os.path.join(HIER, "ketten_probelauf.sh")
pruef(subprocess.run(["bash", "-n", sh]).returncode == 0, "ketten_probelauf.sh Syntax")
W = os.path.join(S, "probe_wurzel"); r = subprocess.run(["bash", sh, "--plan"], capture_output=True, text=True, env=dict(os.environ, RCPARK_PROBE_WURZEL=W), timeout=60)
pruef(r.returncode == 3 and "kein Grundstand" in r.stdout and "S2 marke" in r.stdout and not os.path.exists(W), f"Planmodus ohne Grundstand: rc {r.returncode}, nichts angelegt")

import shutil; shutil.rmtree(S, ignore_errors=True)
print(f"test_ketten_probelauf: {F} Fehler"); sys.exit(1 if F else 0)
