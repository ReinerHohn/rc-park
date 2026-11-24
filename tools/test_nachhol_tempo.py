#!/usr/bin/env python3
"""test_nachhol_tempo.py - Tempo des Nachholens (Kette 1122q: merkmale 20 min, paare 50 min, Downloads 13,5 min davon 12 min HTTP-429-Warten), 23.11.2026.
Nur CPU, vorgespielte Daten (kein torch/pycolmap, kein Netz):
 (1) Zwischenspeicher Grob-LightGlue + ALIKED (tools/lg_zwischenspeicher.py, zusatzfotos_lightglue.grob_runde): Folgelauf mit gleichen Bildern rechnet 0 Paare neu
     und liefert dieselben Werte/dieselbe Auswahl; geaenderter Bildinhalt -> nur dessen Paare neu; andere Parameter-Kennung -> alles neu; Merkmale bitgleich;
     aufraeumen haelt den Speicher auf einen Lauf.
 (2) Schalter RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT: Standard AUS; SIFT-Paarliste ist Obermenge der LightGlue-Auswahl; einlesen matcht nur bei 'aufgeschoben';
     seiten_luecken schreibt den Schalter in den Befehl (Schritt-Kette).
 (3) Messskript tools/versuche/nachhol_sift_gewaehlt_messen.py: Befehle aus dem Skript, Pfad-Umlenkung, DB-Beschneiden, Posenvergleich + Urteil.
 (4) Drossel-Marke (tools/http_holen.py): gedrosselt + Vorrat -> kein erneutes Warten; ohne Vorrat / abgelaufen -> wie bisher; Erfolg loescht die Marke.
"""
import sys, os, json, sqlite3, io, email.message, urllib.error, collections
import numpy as np
TD = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, TD); sys.path.insert(0, os.path.join(TD, "versuche"))
import pfade
T = pfade.temp_ordner("test_nachhol_tempo_")
os.environ["RCPARK_DROSSEL_DATEI"] = os.path.join(T, "drossel_marken.json")
for k_ in ("RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT", "RCPARK_NACHHOL_SIFT_MARGE", "RCPARK_NACHHOL_SIFT_MIN", "RCPARK_LG_CACHE", "RCPARK_DROSSEL_MARKE_H"): os.environ.pop(k_, None)
fehler_ = []
def pruef(b, t):
    print(("ok   " if b else "FEHLER ") + t)
    if not b: fehler_.append(t)

import lg_zwischenspeicher as LZ, zusatzfotos_lightglue as ZL, zusatzfotos_registrieren as ZR
still = lambda *a, **k: None

# ---------- (1) Zwischenspeicher ----------
bd = os.path.join(T, "bilder"); os.makedirs(bd)
rng = np.random.default_rng(0); namen = [f"b{i:02d}.jpg" for i in range(12)]; neu = namen[:5]
for n in namen: open(os.path.join(bd, n), "wb").write(rng.bytes(3000))
h = {n: LZ.inhalt_hash(os.path.join(bd, n)) for n in namen}
kand = [(x, y) for x in neu for y in namen if y != x and (y not in neu or x < y)]
wert = lambda x, y, h_: (int(h_[x][:6], 16) * 7 + int(h_[y][:6], 16)) % 50      # "Grob-Matches" haengen nur am Bildinhalt (Reihenfolge x=image0)
aufrufe = []
def rechner(h_):
    def r(x, y): aufrufe.append((x, y)); return wert(x, y, h_)
    return r
sc0, st0 = ZL.grob_runde(kand, h, rechner(h), None, melden=still)                       # ohne Speicher = alter Weg
ref_sel = set()
for x in neu:                                                                              # Referenz: Auswahlregel wie vor dem Umbau (Kopie der alten Schleife)
    for y, k in sorted(sc0[x].items(), key=lambda t: -t[1])[:3]:
        if k >= 8: ref_sel.add(tuple(sorted((x, y))))
pruef(ZL.auswahl(sc0, neu, 3) == ref_sel and st0["gerechnet"] == len(kand), f"auswahl() = alte Auswahlregel ({len(ref_sel)} Paare), ohne Speicher alle {len(kand)} gerechnet")
SO = os.path.join(T, "zs"); mk = LZ.kennung(art="aliked", max_kp=4096); gk = LZ.kennung(art="grob", grob=512)
sp = LZ.Speicher(SO, mk, gk); aufrufe.clear(); sc1, st1 = ZL.grob_runde(kand, h, rechner(h), sp, melden=still, alle=7); sp.schliessen()
pruef(len(aufrufe) == len(kand) and st1 == dict(gespeichert=0, gerechnet=len(kand)) and sc1 == sc0, f"Lauf 1 mit leerem Speicher: alles gerechnet, Werte wie ohne Speicher ({st1})")
sp = LZ.Speicher(SO, mk, gk); aufrufe.clear(); sc2, st2 = ZL.grob_runde(kand, h, rechner(h), sp, melden=still); sp.schliessen()
pruef(aufrufe == [] and st2["gerechnet"] == 0 and sc2 == sc0 and ZL.auswahl(sc2, neu, 3) == ref_sel, f"Lauf 2, gleiche Bilder: 0 Paare gerechnet, gleiche Werte und Auswahl ({st2})")
open(os.path.join(bd, "b07.jpg"), "wb").write(rng.bytes(3000)); h2 = dict(h, **{"b07.jpg": LZ.inhalt_hash(os.path.join(bd, "b07.jpg"))})
sp = LZ.Speicher(SO, mk, gk); aufrufe.clear(); sc3, st3 = ZL.grob_runde(kand, h2, rechner(h2), sp, melden=still); sp.schliessen()
pruef(sorted(aufrufe) == sorted(p for p in kand if "b07.jpg" in p) and all(sc3[x][y] == wert(x, y, h2) for x, y in kand),
      f"Bild b07 neu (anderer Inhalt, gleicher Name): nur seine {len(aufrufe)} Paare gerechnet, Werte richtig")
sp = LZ.Speicher(SO, mk, LZ.kennung(art="grob", grob=256)); aufrufe.clear(); ZL.grob_runde(kand, h2, rechner(h2), sp, melden=still); sp.schliessen()
pruef(len(aufrufe) == len(kand), "andere Parameter (grob 256) -> andere Kennung -> alles neu gerechnet")
# Merkmale bitgleich
sp = LZ.Speicher(SO, mk, gk); F = dict(keypoints=rng.random((1, 50, 2), dtype=np.float32), descriptors=rng.random((1, 50, 128), dtype=np.float32),
                                       keypoint_scores=rng.random((1, 50), dtype=np.float32), image_size=np.array([[2000., 1500.]], np.float32))
pruef(sp.merkmale_holen(h["b00.jpg"]) is None, "Merkmale: unbekanntes Bild -> None (rechnen)")
sp.merkmale_ablegen(h["b00.jpg"], F); sp.merkmale_ablegen(h["b01.jpg"], F); G = sp.merkmale_holen(h["b00.jpg"])
pruef(G is not None and all(np.array_equal(G[k], F[k]) and G[k].dtype == F[k].dtype and G[k].shape == F[k].shape for k in F), "Merkmale aus dem Speicher bitgleich (Wert, dtype, Form)")
open(os.path.join(sp.md, h["b01.jpg"] + ".npz"), "wb").write(b"kaputt"); pruef(sp.merkmale_holen(h["b01.jpg"]) is None, "beschaedigte Merkmal-Datei -> None (neu rechnen statt Absturz)")
alt_ordner = os.path.join(SO, "aliked_altkennung"); os.makedirs(alt_ordner); open(os.path.join(alt_ordner, "x.npz"), "wb").write(b"0")
au = sp.aufraeumen({h2[n] for n in namen if n != "b01.jpg"}); n_grob = sp.con.execute("select count(*) from grob").fetchone()[0]; sp.schliessen()
pruef(not os.path.exists(alt_ordner) and os.path.exists(os.path.join(SO, "aliked_" + mk, h["b00.jpg"] + ".npz")) and not os.path.exists(os.path.join(SO, "aliked_" + mk, h["b01.jpg"] + ".npz"))
      and n_grob == sum(1 for x, y in kand if "b01.jpg" not in (x, y)), f"aufraeumen: alte Kennung + Bilder ausserhalb des Laufs weg, {n_grob} Grob-Werte des Laufs bleiben ({au})")
os.environ["RCPARK_LG_CACHE"] = "0"; pruef(ZL.speicher_ordner("/d/Z") is None, "RCPARK_LG_CACHE=0 schaltet den Speicher ab"); os.environ.pop("RCPARK_LG_CACHE")
pruef(ZL.speicher_ordner("/d/Z") == "/d/Z/zwischenspeicher_lg", "Standardort unter dem Datenordner, NICHT in lg/ (wird am Skriptende geloescht)")
src = open(os.path.join(TD, "zusatzfotos_lightglue.py")).read()
pruef("grob_runde(kand, h, rechne, sp)" in src and "sp.merkmale_holen(h[n])" in src and "LZ.modellstand()" in src, "paare nutzt den Zwischenspeicher (Quelltext) mit Modellstand in der Kennung")
pruef(set(LZ.modellstand()) >= {"lightglue", "torch"}, f"Modellstand-Felder vorhanden ({LZ.modellstand()})")

# ---------- (2) Schalter SIFT nur gewaehlt ----------
pruef(not ZR.sift_nur_gewaehlt(), "RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT Standard AUS")
os.environ["RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT"] = "1"; pruef(ZR.sift_nur_gewaehlt(), "Schalter =1 an")
import seiten_luecken as SL
pruef(SL.sift_schalter() == "RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT=1 ", "seiten_luecken schreibt den Schalter in den merkmale-Befehl (Befehls-Hash der Schritt-Kette aendert sich)")
os.environ.pop("RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT"); pruef(SL.sift_schalter() == "", "ohne Schalter Befehl unveraendert (keine unnoetige Neuberechnung)")
ss = ZL.sift_auswahl(sc0, neu, 3); pruef(ss >= ZL.auswahl(sc0, neu, 3) and len(ss) > len(ZL.auswahl(sc0, neu, 3)), f"SIFT-Paarliste Obermenge der LG-Auswahl ({len(ss)} >= {len(ZL.auswahl(sc0, neu, 3))})")
os.environ["RCPARK_NACHHOL_SIFT_MARGE"] = "100"; os.environ["RCPARK_NACHHOL_SIFT_MIN"] = "0"
pruef(ZL.sift_auswahl(sc0, neu, 3) == {tuple(sorted(p)) for p in kand}, "Marge 100, Min 0 -> alle Kandidaten (Grenzfall = Standardweg)")
os.environ.pop("RCPARK_NACHHOL_SIFT_MARGE"); os.environ.pop("RCPARK_NACHHOL_SIFT_MIN")
Zd = os.path.join(T, "Z"); os.makedirs(os.path.join(Zd, "lg")); json.dump(dict(sift_matching="alle", paare=99), open(os.path.join(Zd, "merkmale.json"), "w"))
gerufen = []
def matchen(db, pf, saat=False): gerufen.append((db, open(pf).read(), saat)); return 17
pruef(ZL.sift_nachholen(Zd, matchen) is None and not gerufen, "merkmale hat alle Paare gematcht -> einlesen matcht nichts nach")
json.dump(dict(sift_matching="aufgeschoben", paare=0), open(os.path.join(Zd, "merkmale.json"), "w"))
try: ZL.sift_nachholen(Zd, matchen); pruef(False, "aufgeschoben ohne sift_paare.txt muss abbrechen")
except SystemExit as e: pruef("sift_paare.txt" in str(e), "aufgeschoben, aber Paarliste fehlt -> klarer Abbruch")
open(os.path.join(Zd, "lg", "sift_paare.txt"), "w").write("a.jpg r1.jpg\na.jpg b.jpg\n")
n_ = ZL.sift_nachholen(Zd, matchen); M = json.load(open(os.path.join(Zd, "merkmale.json")))
pruef(n_ == 2 and gerufen and gerufen[0][0] == os.path.join(Zd, "db.db") and gerufen[0][2] and M["sift_matching"] == "nur_gewaehlt" and M["verifizierte_paare_gesamt"] == 17,
      f"aufgeschoben -> nur die 2 Paare der Liste in Z/db.db gematcht (Saat gesetzt), merkmale.json nachgetragen ({M})")
rs = open(os.path.join(TD, "zusatzfotos_registrieren.py")).read()
pruef("aufgeschoben = sift_nur_gewaehlt()" in rs and "else: ver = sift_paare_matchen_gespeichert(db, pf, pycolmap)" in rs, "merkmale: Standardweg matcht weiter alle Kandidatenpaare (Quelltext)")

# ---------- (3) Messskript ----------
import nachhol_sift_gewaehlt_messen as MS
Zp = "/daten/obj/seiten_nachholen"; sh = os.path.join(T, "holen.sh")
open(sh, "w").write("\n".join([f"  RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT=1 /py tools/zusatzfotos_registrieren.py merkmale --ref-db /r/db.db --sparse /r/0 --aus {Zp}",
                               f"  /py tools/zusatzfotos_lightglue.py refnamen --ziel {Zp} --ref-sparse /r/0", f"  /py tools/zusatzfotos_lightglue.py paare --ziel {Zp} --ref-sparse /r/0 --ref-bilder /f",
                               f"  /py tools/zusatzfotos_lightglue.py einlesen --ziel {Zp} --ref-sparse /r/0", f"  /py tools/zusatzfotos_registrieren.py registrieren --sparse {Zp}/lg/ref_tri --aus {Zp}/lg --je-bild --kalibrieren   # Kommentar"]) + "\n")
B = MS.befehle_aus_skript(sh, Zp)
pruef(set(B) == {"merkmale", "refnamen", "paare", "einlesen", "registrieren"} and "#" not in B["registrieren"] and "RCPARK_NACHHOL" not in B["merkmale"], "Messskript liest die 5 Befehle aus dem Nachhol-Skript (ohne Kommentar, ohne Schalter)")
u = MS.umlenken(B["registrieren"], Zp, "/m/A")
pruef(u.endswith("--sparse /m/A/lg/ref_tri --aus /m/A/lg --je-bild --kalibrieren") and MS.umlenken(f"x {Zp}_alt {Zp}", Zp, "/m/A") == f"x {Zp}_alt /m/A", f"Pfad-Umlenkung nur ganzer Pfadstuecke ({u[-60:]})")
db = os.path.join(T, "mess.db"); con = sqlite3.connect(db)
con.execute("create table images (image_id integer, name text)"); con.execute("create table matches (pair_id integer, rows integer, cols integer, data blob)"); con.execute("create table two_view_geometries (pair_id integer, rows integer)")
ims = {"r1.jpg": 1, "r2.jpg": 2, "a.jpg": 3, "b.jpg": 4}
for n, i in ims.items(): con.execute("insert into images values (?,?)", (i, n))
alle_p = [("r1.jpg", "r2.jpg"), ("a.jpg", "r1.jpg"), ("a.jpg", "r2.jpg"), ("b.jpg", "r1.jpg"), ("a.jpg", "b.jpg")]
for x, y in alle_p: pid = ZL.paar_id(ims[x], ims[y]); con.execute("insert into matches values (?,?,?,?)", (pid, 1, 2, b"")); con.execute("insert into two_view_geometries values (?,?)", (pid, 1))
con.commit(); con.close()
g, b_ = MS.db_beschneiden(db, {("a.jpg", "r1.jpg"), ("a.jpg", "b.jpg")}, {"a.jpg", "b.jpg"})
con = sqlite3.connect(db); rest = {r[0] for r in con.execute("select pair_id from matches")}; rest2 = {r[0] for r in con.execute("select pair_id from two_view_geometries")}; con.close()
soll = {ZL.paar_id(ims[x], ims[y]) for x, y in [("r1.jpg", "r2.jpg"), ("a.jpg", "r1.jpg"), ("a.jpg", "b.jpg")]}
pruef(g == 2 and rest == soll and rest2 == soll, "DB-Beschneiden: Referenzpaar bleibt, gewaehlte Paare bleiben, nur nicht gewaehlte Paare mit neuem Bild weg")
I = np.eye(3); Rz = lambda d: np.array([[np.cos(np.radians(d)), -np.sin(np.radians(d)), 0], [np.sin(np.radians(d)), np.cos(np.radians(d)), 0], [0, 0, 1]])
PA = {"a": (np.zeros(3), I), "b": (np.ones(3), I), "c": (np.zeros(3), I)}; PB = {"a": (np.array([0.01, 0, 0]), Rz(0.2)), "b": (np.ones(3), I), "d": (np.zeros(3), I)}
v = MS.gegenueber(PA, PB)
pruef(v["verloren"] == ["c"] and v["gewonnen"] == ["d"] and abs(v["zentrum_m"]["max"] - 0.01) < 1e-9 and abs(v["winkel_grad"]["max"] - 0.2) < 1e-6, "Posenvergleich: verloren/gewonnen, Zentrum (m), Winkel (Grad)")
pruef(not MS.urteil(v, None)["kein_verlust"] and MS.urteil(MS.gegenueber(PA, dict(PA)), None)["kein_verlust"], "Urteil: verlorenes Bild -> Verlust; identische Posen -> kein Verlust")
pruef(MS.sc_aus_rang({"a": [["r1", 9], ["r2", 3]]}) == {"a": {"r1": 9, "r2": 3}}, "Rangliste -> Paarwerte")

# ---------- (4) Drossel-Marke ----------
import http_holen as HH
class Antwort(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
def f429(): m_ = email.message.Message(); m_["Retry-After"] = "120"; return urllib.error.HTTPError("https://upload.wikimedia.org/x.jpg", 429, "Too many", m_, None)
def oeffner(folge):
    def o(rq, timeout):
        x = folge.pop(0)
        if isinstance(x, Exception): raise x
        return Antwort(x)
    return o
U = "https://upload.wikimedia.org/a.jpg"; host = "upload.wikimedia.org"
HH._verbraucht[0] = 0.0; schl = []; HH.vorrat_melden(0)
try: HH.hole(U, oeffnen=oeffner([f429()] * 4), schlafen=schl.append, melden=still); pruef(False, "Gedrosselt erwartet")
except HH.Gedrosselt: pass
mk_ = HH.marken_lesen().get(host)
pruef(schl == [120.0, 120.0, 120.0] and mk_ and mk_["code"] == 429, f"Lauf 1 (wie 1122q): 3 x 120 s gewartet, dann Gedrosselt + Marke geschrieben ({mk_ and mk_['datum']})")
HH._verbraucht[0] = 0.0; schl = []; HH.vorrat_melden(27)      # zweiter Prozess (openverse, 27 Bilder schon da)
try: HH.hole(U, oeffnen=oeffner([f429()] * 4), schlafen=schl.append, melden=still); pruef(False, "Gedrosselt erwartet")
except HH.Gedrosselt as e: pruef(schl == [] and "kein erneutes Warten" in str(e), f"Marke frisch + Vorrat -> sofort Gedrosselt, 0 s gewartet statt 360 s ({str(e)[:90]})")
HH._verbraucht[0] = 0.0; schl = []; HH.vorrat_melden(0)
try: HH.hole(U, oeffnen=oeffner([f429()] * 4), schlafen=schl.append, melden=still)
except HH.Gedrosselt: pass
pruef(schl == [120.0, 120.0, 120.0], "Marke frisch, aber KEIN Vorrat -> wartet wie bisher (sonst gaebe es nie ein erstes Bild)")
m_ = HH.marken_lesen(); m_[host]["zeit"] -= 25 * 3600; HH._marken_schreiben(m_); HH._verbraucht[0] = 0.0; schl = []; HH.vorrat_melden(5)
try: HH.hole(U, oeffnen=oeffner([f429()] * 4), schlafen=schl.append, melden=still)
except HH.Gedrosselt: pass
pruef(schl == [120.0, 120.0, 120.0], "Marke aelter als 24 h -> wartet wieder (Quelle neu versuchen)")
HH._verbraucht[0] = 0.0; d = HH.hole(U, oeffnen=oeffner([b"JPEG"]), schlafen=still, melden=still, vorrat=True)
pruef(d == b"JPEG" and host not in HH.marken_lesen(), "Host liefert wieder -> Marke geloescht")
HH.marke_setzen(host, 429); d = HH.hole(U, oeffnen=oeffner([b"JPEG"]), schlafen=still, melden=still, vorrat=True)
pruef(d == b"JPEG", "frische Marke verhindert keinen Versuch: erster Abruf wird immer gemacht (ein Versuch je Lauf)")
os.environ["RCPARK_DROSSEL_DATEI"] = "0"; pruef(HH.marken_datei() is None and HH.marke_alter_s(host) is None, "RCPARK_DROSSEL_DATEI=0 schaltet die Marken ab")
os.environ["RCPARK_DROSSEL_DATEI"] = os.path.join(T, "drossel_marken.json")
for t_, m_ in (("online_ansichten_holen.py", "http_holen.vorrat_melden("), ("openverse_holen.py", "http_holen.vorrat_melden("), ("commons_harvest.py", "http_holen.vorrat_melden(")):
    pruef(m_ in open(os.path.join(TD, t_)).read(), f"{t_} meldet seinen Vorrat (Drossel-Marke greift)")

print("test_nachhol_tempo:", "BESTANDEN" if not fehler_ else f"{len(fehler_)} FEHLER")
sys.exit(1 if fehler_ else 0)
