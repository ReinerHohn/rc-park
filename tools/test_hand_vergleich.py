#!/usr/bin/env python3
"""test_hand_vergleich.py - fester synthetischer Test fuer tools/hand_vergleich.py (21.11.2026): Treppenturm aus koerper_auto.json (form rund),
Ueberstand und Laterne aus dach_profil.json werden gemessen und gegen referenz_hand.json geurteilt. < 1 s, keine Bibliotheken."""
import os, sys, json, tempfile, subprocess

H = os.path.dirname(os.path.abspath(__file__))
with tempfile.TemporaryDirectory() as T:
    os.makedirs(os.path.join(T, "audit")); oj = os.path.join(T, "objekt.json"); json.dump({}, open(oj, "w"))
    json.dump(dict(quelle="test", bauteile=[
        dict(bauteil="treppenturm", masse=dict(radius=1.5, traufe=11.5), toleranz_m=0.4),
        dict(bauteil="zeltdach_ueberstand", masse=dict(ueberstand=1.0), toleranz_m=0.3),
        dict(bauteil="laterne", masse=dict(spitze_z=50.25, krempe_z=48.0), toleranz_m=0.6),
        # Tor: lichte Masse gegen lichte, Aussen-Scheitel gegen aussenmass; Kaempfer als Handannahme (angezeigt, nicht geurteilt)
        dict(bauteil="tor", masse=dict(breite=4.4, scheitel=6.3, scheitel_aussen=6.7, kaempfer=4.0), toleranz_m=0.4, hand_annahme=dict(kaempfer="test"))]), open(os.path.join(T, "referenz_hand.json"), "w"))
    json.dump(dict(f00=dict(oeffnungen=[dict(gebaut=True, breite=4.5, scheitel=6.22, kaempfer=2.99, aussenmass=dict(scheitel=6.6, breite=5.26))])), open(os.path.join(T, "audit", "oeffnungen_auto.json"), "w"))
    json.dump(dict(haufen=[dict(punkte=100, form="rund", kreis=dict(x=0, y=0, r=1.6), kasten=[0, 0, 1, 1, 1, 11.7]),
                           dict(punkte=50, form="kasten", kasten=[0, 0, 0, 1, 1, 30])]), open(os.path.join(T, "audit", "koerper_auto.json"), "w"))
    sch = []
    for i in range(28):                       # Wand halb 5 m; Traufe ueber 2 m mit 1 m Ueberstand, Pyramide, Hals 0,5 m bei z 47, Laternenkopf 1 m ab z 48
        z = 37.0 + 0.5 * i
        w = 6.0 if z < 39 else (max(0.5, 6.0 - (z - 39) * 0.7) if z < 48 else 1.0)
        sch.append([z, -w, w, -w, w, 100])
    json.dump(dict(scheiben=sch, wand_halb=[5.0, 5.0], schritt=0.5), open(os.path.join(T, "audit", "dach_profil.json"), "w"))
    r = subprocess.run([sys.executable, os.path.join(H, "hand_vergleich.py"), oj], capture_output=True, text=True)
    erg = {b["bauteil"]: b for b in json.load(open(os.path.join(T, "audit", "hand_vergleich.json")))["bauteile"]}
    fehler = [b for b in ("treppenturm", "zeltdach_ueberstand", "laterne", "tor") if erg[b]["urteil"] != "PASST"]
    if erg["tor"]["masse"]["scheitel_aussen"]["ist"] != 6.6 or not erg["tor"]["masse"]["kaempfer"].get("hand_annahme"): fehler.append("tor: aussen/annahme")
    R_ = json.load(open(os.path.join(T, "referenz_hand.json"))); R_["bauteile"][3].pop("hand_annahme"); json.dump(R_, open(os.path.join(T, "referenz_hand.json"), "w"))
    subprocess.run([sys.executable, os.path.join(H, "hand_vergleich.py"), oj], capture_output=True, text=True)      # ohne Annahme-Vermerk muss der Kaempfer wieder urteilen
    if {b["bauteil"]: b for b in json.load(open(os.path.join(T, "audit", "hand_vergleich.json")))["bauteile"]}["tor"]["urteil"] != "FALSCH": fehler.append("tor: Kaempfer ohne Annahme nicht geurteilt")
    if fehler or r.returncode != 0:
        print("FEHLER hand_vergleich:", fehler, r.stdout[-400:], r.stderr[-400:]); sys.exit(1)
    print("OK hand_vergleich: Treppenturm, Ueberstand, Laterne aus Wolkenstufen erkannt; Tor licht/aussen getrennt, Handannahme nicht geurteilt")
