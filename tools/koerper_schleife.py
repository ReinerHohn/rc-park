#!/usr/bin/env python3
"""koerper_schleife.py - KOERPER AUS DEM WOLKENREST FINDEN, BAUEN, NACHMESSEN, ANNEHMEN ODER VERWERFEN (21.11.2026).

Anlass (modelle/ANALYSE_SACKGASSEN_2026-11-21.md Ursache 7): der Mensch im Handlauf BENANNTE ("da ist ein Treppenturm") und PRUEFTE. tools/ebenen_schleife.py ersetzt das Pruefen fuer
Wandebenen; dieser Treiber ersetzt beides fuer ganze Koerper, die auf keiner Wandebene liegen - nach demselben Muster (Kandidat -> bauen -> messen -> nur bei Gewinn behalten).
Je Runde:
  1. REST MESSEN am sauberen Stand (tools/wolke_rest.py): Haufen der dichten Wolke, die nicht am Modell liegen, mit Grobform. Nachbarn/Umgebung/Hohlraeume sind keine Kandidaten.
  2. KANDIDATEN = alle baubaren Haufen (rund, kasten, ring, band, stab), die noch nicht in audit/koerper_auto.json stehen (auch nicht als verworfen) -> dort mit angenommen = null
     und 'am_modell_vorher' = Wolkenpunkte naeher als --nah (0,15 m) an der Modellflaeche im Kasten des Haufens (+ 0,5 m).
  3. BAUEN: Generator aus objekt.json['generator'] (bauteile.wolkenrest_koerper baut alles mit angenommen != false) - alle offenen Kandidaten in EINEM Bau.
  4. NACHMESSEN je Kandidat im selben Kasten: 'am_modell_nachher'. ANNAHMEREGEL: Gewinn = nachher - vorher >= --gewinn (0,3) x Punktzahl des Haufens.
     Begruendung: die Punkte des Haufens SIND die Oberflaeche des fehlenden Koerpers; stimmt der gebaute Koerper, liegen sie danach an seiner Flaeche. Die Grenze 0,15 m (statt der
     Restgrenze 0,35 m) macht die Regel auch fuer kleine Koerper scharf (ein 0,8-m-Klotz irgendwo im Haufen laege sonst immer 'am Modell'). 30 % statt 100 %, weil Deckflaechen,
     Profile und Stufen der Grobform fehlen duerfen. Beide Zahlen sind ANNAHMEN (Schwabentor + synthetische Tests).
     Sonst: angenommen = false mit Grund - bleibt als Protokoll in der Datei, wird beim naechsten Bau weggelassen und nie wieder vorgeschlagen.
  5. Wurde etwas verworfen: neu bauen (ohne die Verworfenen), dann erst neu messen (Schritt 1 nur am sauberen Stand). ENDE: kein neuer Kandidat oder --runden erreicht
     (offene Kandidaten, die nicht mehr gemessen wurden, werden aus der Datei genommen und beim naechsten Lauf wieder gefunden).
Eintraege ohne Messung aus der Zeit vor diesem Treiber (wolke_rest --uebernehmen allein) bleiben als 'Altbestand' angenommen; --neu verwirft die Datei und prueft alles von vorn.
--erst_bauen: vor der ersten Messung einmal bauen (wenn seit dem letzten Bau ein anderes Kettenergebnis dazukam, z. B. audit/dach_profil.json).
Ausgabe: audit/koerper_auto.json (Kandidaten mit Urteil), audit/koerper_schleife.json (Zusammenfassung), audit/koerper_schleife_verlauf.jsonl. Rueckgabe 0 = gelaufen, 2 = Abbruch, 3 = nichts zu tun.
Aufruf: koerper_schleife.py <objekt.json> <wolke.npy> [--runden 4] [--neu] [--erst_bauen] [--bild B.jpg] [--stl S] [--bau "<Befehl>"] [--grundflaechen G.json] [--rest "<Optionen fuer wolke_rest>"]
Danach die volle Abnahme (tools/bauen_abnehmen.sh) laufen lassen - die Schleife baut nur den Generator.
"""
import sys, os, json, argparse, subprocess, time, math, shlex

HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER)
sys.path.insert(0, HIER)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("wolke"); ap.add_argument("--runden", type=int, default=4); ap.add_argument("--gewinn", type=float, default=0.3); ap.add_argument("--neu", action="store_true")
    ap.add_argument("--erst_bauen", action="store_true"); ap.add_argument("--bau", default="", help="Baubefehl statt objekt.json['generator'] (Tests: Bau-Attrappe)"); ap.add_argument("--stl", default=""); ap.add_argument("--bild", default="")
    ap.add_argument("--grundflaechen", default=""); ap.add_argument("--rest", default="", help="weitere Optionen fuer wolke_rest.py, z. B. '--jeder 1'"); a = ap.parse_args()
    import wolke_rest as WR
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); obj = json.load(open(objp)); A = os.path.join(od, "audit"); os.makedirs(A, exist_ok=True); kp = os.path.join(A, "koerper_auto.json"); wr = os.path.join(A, "wolke_rest.json")
    bau = a.bau or obj.get("generator")
    if not bau: print("ABBRUCH: kein Baubefehl (objekt.json 'generator' fehlt)"); return 2
    try: rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    except Exception: rev = "?"
    K = [] if a.neu or not os.path.exists(kp) else json.load(open(kp)).get("haufen", []); zaehler = dict(bau=0, mess=0); t_anf = time.time()
    erst = a.erst_bauen or (a.neu and os.path.exists(kp) and any(k.get("angenommen") is not False for k in json.load(open(kp)).get("haufen", [])))
    for k in list(K):                                                                       # Bestand ohne Urteil
        if k.get("angenommen") in (True, False): continue
        if "am_modell_vorher" in k and k.get("urteil") is None: K.remove(k); erst = True      # offener Kandidat eines abgebrochenen Laufs: Stand unbekannt -> weg, sauber bauen, neu finden
        else: k["angenommen"] = True; k["urteil"] = "Altbestand ohne Messung (vor tools/koerper_schleife.py uebernommen) - mit --neu neu pruefen"

    def speichern(): json.dump(dict(quelle="tools/wolke_rest.py + tools/koerper_schleife.py", haufen=K), open(kp, "w"), indent=1)

    def bauen():
        speichern(); zaehler["bau"] += 1; r = subprocess.run(["bash", "-c", bau], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, KOERPER_AUTO=kp, OBJEKT_JSON=objp))
        return "" if r.returncode == 0 else ((r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ["Bau abgestuerzt"])[-1][:200])

    def messen():
        speichern(); zaehler["mess"] += 1
        r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(HIER, "wolke_rest.py"), objp, a.wolke] + (["--stl", a.stl] if a.stl else []) + (["--bild", a.bild] if a.bild else []) + (["--grundflaechen", a.grundflaechen] if a.grundflaechen else []) + shlex.split(a.rest), capture_output=True, text=True)
        if r.returncode != 0: return None, (r.stderr.strip().splitlines() or ["wolke_rest abgestuerzt"])[-1][:200]
        return json.load(open(wr)), ""

    def kurz(k): return f"{k['id']} ({k['form']}, {k['punkte']} Punkte, x {k['kasten'][0]:.1f}..{k['kasten'][3]:.1f} y {k['kasten'][1]:.1f}..{k['kasten'][4]:.1f} z {k['kasten'][2]:.1f}..{k['kasten'][5]:.1f})"

    vor_bau = None
    if erst:
        B0, err = messen()
        if B0 is not None: vor_bau = B0["an_flaeche_punkte"]
        err = bauen()
        if err: print("ABBRUCH beim ersten Bau:", err); return 2
    B, err = messen()
    if B is None: print("ABBRUCH beim Ausgangsstand:", err); return 2
    ausgang = B["an_flaeche_punkte"] if vor_bau is None else vor_bau; print(f"Ausgang: {ausgang} Wolkenpunkte am Modell" + (f" (vor dem ersten Bau; danach {B['an_flaeche_punkte']})" if vor_bau is not None else "") + f", {len(B['haufen'])} Haufen: "
                                                                             + ", ".join(f"{n} {f}" for f, n in sorted({h['form']: sum(1 for x in B['haufen'] if x['form'] == h['form']) for h in B['haufen']}.items())), flush=True)
    runde = 0; ende = "kein neuer Kandidat"
    while True:
        neu = WR.uebernehmen(B["haufen"], K)                                                # nur am sauberen Stand (alle gebauten Koerper angenommen)
        if not neu: break
        if runde >= a.runden:
            for k in neu: K.remove(k)
            ende = f"Rundengrenze {a.runden} ({len(neu)} Kandidaten ungemessen, beim naechsten Lauf wieder da)"; break
        runde += 1; t0 = time.time(); gesamt_vor = B["an_flaeche_punkte"]; err = bauen(); Bn = None
        if not err: Bn, err = messen()
        for k in neu:
            soll = max(int(math.ceil(a.gewinn * k["punkte"])), 1); k["gewinn_soll"] = soll
            if Bn is None: k["angenommen"] = False; k["urteil"] = "verworfen: Bau/Messung gescheitert: " + err
            else:
                n = Bn.get("kandidaten", {}).get(k["id"]); k["am_modell_nachher"] = n; g = (n if n is not None else -10 ** 9) - int(k.get("am_modell_vorher") or 0); k["gewinn"] = g if n is not None else None
                if n is not None and g >= soll: k["angenommen"] = True; k["urteil"] = f"angenommen: {g} Wolkenpunkte mehr am Modell (Soll >= {soll} = {a.gewinn * 100:.0f} % von {k['punkte']})"
                else: k["angenommen"] = False; k["urteil"] = f"verworfen: nur {g if n is not None else 'keine Messung'} Wolkenpunkte mehr am Modell (Soll >= {soll} = {a.gewinn * 100:.0f} % von {k['punkte']}) - gebauter Koerper trifft die Wolke nicht"
            print(f"Runde {runde}: {kurz(k)}: {k['urteil']}", flush=True)
            with open(os.path.join(A, "koerper_schleife_verlauf.jsonl"), "a") as f_: f_.write(json.dumps(dict(zeit=time.strftime("%Y-%m-%d %H:%M"), git=rev, runde=runde, **{x: k.get(x) for x in ("id", "form", "punkte", "kasten", "am_modell_vorher", "am_modell_nachher", "gewinn", "gewinn_soll", "angenommen", "urteil")}), ensure_ascii=False) + "\n")
        speichern()
        if any(k["angenommen"] is False for k in neu):                                      # sauberer Stand: ohne die Verworfenen bauen und neu messen
            err = bauen(); B2, err2 = messen() if not err else (None, err)
            if B2 is None: print("ABBRUCH beim Rueckbau:", err or err2); ende = "Abbruch beim Rueckbau: " + (err or err2); break
            B = B2
        else: B = Bn
        print(f"   Runde {runde}: gesamt {gesamt_vor} -> {B['an_flaeche_punkte']} Wolkenpunkte am Modell ({time.time() - t0:.0f} s)", flush=True)
    speichern(); an = [k for k in K if k.get("angenommen") is True]; ab = [k for k in K if k.get("angenommen") is False]
    Z = dict(quelle="tools/koerper_schleife.py", zeit=time.strftime("%Y-%m-%d %H:%M"), git=rev, runden=runde, ende=ende, baulaeufe=zaehler["bau"], messlaeufe=zaehler["mess"], wolke_am_modell_vorher=ausgang, wolke_am_modell_nachher=B["an_flaeche_punkte"],
             angenommen=[dict(id=k["id"], form=k["form"], punkte=k["punkte"], urteil=k.get("urteil")) for k in an], verworfen=[dict(id=k["id"], form=k["form"], punkte=k["punkte"], urteil=k.get("urteil")) for k in ab],
             gemeldet=[dict(id=h["id"], form=h["form"], punkte=h["punkte"], kasten=h["kasten"], grund=h.get("grund", "keine baubare Grobform")) for h in B["haufen"] if not h.get("kandidat")], sekunden=round(time.time() - t_anf))
    json.dump(Z, open(os.path.join(A, "koerper_schleife.json"), "w"), indent=1, ensure_ascii=False)
    print(f"KOERPER-SCHLEIFE: {runde} Runden, {zaehler['bau']} Baulaeufe, {len(an)} Koerper angenommen, {len(ab)} verworfen, Ende: {ende}; Wolkenpunkte am Modell {ausgang} -> {B['an_flaeche_punkte']}; "
          f"{len(Z['gemeldet'])} Haufen nur gemeldet ({sum(1 for g in Z['gemeldet'] if g['form'] == 'nachbar')} Nachbarn, {sum(1 for g in Z['gemeldet'] if g['form'] == 'hohl')} Hohlraeume) -> {kp}")
    return 0 if (runde or zaehler["bau"]) else 3


if __name__ == "__main__": sys.exit(main())
