#!/usr/bin/env python3
"""kamera_gelaende.py (bis 16.11.2026 kamera_plausibel.py; der Name traegt jetzt die Grobregel Standort/Brennweite) <objekt.json> <SFM-AUSRICHTUNG.json> [--unter 1.5] [--gruppe 4] [--fusion <pipe>/dicht/stereo/fusion.cfg] - Kameras unter dem Gelaende finden (falsch verortete Bildgruppen).

Lehre Schwabentor 15.11.2026: eine Geisterwand in der dichten Wolke (27 852 Punkte auf der Strasse) kam zu 92 % aus 6 Bildern EINES Videoclips,
deren Kameras 0,3-4,5 m UNTER dem Gelaende standen (70 m entfernt). Das Grundriss-Tor sah nur den Haufen, nicht die Ursache.
Pruefung: Kamerahoehe im Modellrahmen (z = 0 am Gelaende des Objekts, ANNAHME: Umgebung etwa eben; Hang -> --unter groesser waehlen) < -unter.
Je Quelle (Namensteil vor '__vf_' bzw. vor '__', sonst 'eigen') gezaehlt; >= --gruppe Kameras einer Quelle unter Gelaende = rc 3 + Liste
audit/kamera_plausibel.json ('ausschliessen': Bildnamen fuer die dichte Wolke/Fusion). Einzelne Ausreisser = nur Hinweis.

24.11.2026 DAUERHAFT ROT (schwabentor-1122, 7 Laeufe seit 23.11.): das Tor zaehlte die Kameras des SfM-Modells, nicht die der DICHTEN WOLKE. Lauf 1122z 12:29: 28 Kameras
unter Gelaende, davon 25 NIE in der dichten Wolke (nicht in fusion.cfg.alle: Commons-Altfotos, Staatsarchiv 1901, 7wvSPHS1gDA - der Mapper setzt sie bis 40 km tief, dicht_modell
nimmt sie gar nicht); die 3 uebrigen (eigene Fotos 23.11., Teil 1, -1,5..-1,6 m) nahm wolke_neu_fusionieren heraus - danach 0 Kameras unter Gelaende in der Wolke, das Tor
'_ohne_tiefe_kameras' blieb trotzdem rc 3 (gleiche Ausrichtung, gleiche Zaehlung) und wurde nur als Bericht durchgewunken. Der Ost-Teil-Versatz war NICHT die Ursache
(nur diese 3 Kameras gehoeren zu Teil 1; die Gruppen commons_orig2 12 und netz_commons_geo 7 liegen in Teil 0).
Mit --fusion (aktive Bildliste der Fusion): rc 3 nur, solange eine schlechte Gruppe besteht UND mindestens eine Kamera unter Gelaende noch in der Fusion steht - also genau,
solange das Neufusionieren noch etwas zu tun hat (Ausloeser in gesamtkette unveraendert). Die Ausschlussliste bleibt vollstaendig (alle Kameras unter Gelaende), die Grenzen
(--unter, --gruppe) sind unveraendert. Ohne --fusion bzw. ohne Datei: alte Zaehlung ueber alle Kameras. Test: tools/test_kamera_gelaende.py.
"""
import sys, os, json, collections


def stamm(n):
    n = os.path.basename(str(n).strip()); b, e = os.path.splitext(n)
    return b if e.lower() in (".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff") else n


def fusion_bilder(pfad):
    """Aktive Bildliste der Fusion (fusion.cfg: Bildname je Zeile, ggf. mit Zusatzspalten) -> Menge der Namensstaemme oder None (Datei fehlt/leer)."""
    if not pfad or not os.path.isfile(pfad): return None
    s = {stamm(l.split()[0]) for l in open(pfad) if l.strip() and not l.lstrip().startswith("#")}
    return s or None


def urteil(K, unter=1.5, gruppe=4, fusion=None):
    """K = {bild: {'standort': [x, y, z]}} -> dict(tief, je_quelle, alle, schlecht, in_wolke, rc)."""
    quelle = lambda n: n.split("__vf_")[0] if "__vf_" in n else (n.split("__")[0] if "__" in n else "eigen")
    tief = {n: k["standort"][2] for n, k in K.items() if k["standort"][2] < -unter}; je = collections.Counter(quelle(n) for n in tief); alle = collections.Counter(quelle(n) for n in K)
    schlecht = {q: c for q, c in je.items() if c >= gruppe}
    in_wolke = None if fusion is None else sorted(n for n in tief if stamm(n) in fusion)
    rc = 3 if schlecht and (in_wolke is None or in_wolke) else 0
    return dict(tief=tief, je_quelle=je, alle=alle, schlecht=schlecht, in_wolke=in_wolke, rc=rc, quelle=quelle)


def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    opt = lambda n, d: float(a[a.index(n) + 1]) if n in a else d
    unter, gruppe = opt("--unter", 1.5), int(opt("--gruppe", 4)); od = os.path.dirname(os.path.abspath(a[0])); K = json.load(open(a[1]))["kameras"]
    fpfad = a[a.index("--fusion") + 1] if "--fusion" in a else None; fusion = fusion_bilder(fpfad)
    u = urteil(K, unter, gruppe, fusion); tief, je, alle, schlecht, quelle = u["tief"], u["je_quelle"], u["alle"], u["schlecht"], u["quelle"]
    aus = sorted(tief)   # JEDE Kamera unter Gelaende ist fuer die dichte Wolke unbrauchbar (v2: Commons-Einzelbilder bis km tief = Ausreisser des globalen Mappers)
    print(f"{len(tief)} von {len(K)} Kameras tiefer als {unter} m unter dem Gelaende")
    for q, c in je.most_common(8): print(f"  {q[:50]:50s} {c:3d} von {alle[q]:3d}  (tiefste {min(tief[n] for n in tief if quelle(n) == q):.1f} m){'  <-- GRUPPE' if q in schlecht else ''}")
    if fpfad and fusion is None: print(f"HINWEIS: Bildliste der Fusion {fpfad} fehlt/leer - Urteil ueber alle Kameras des Modells")
    elif fusion is not None: print(f"DICHTE WOLKE: {len(u['in_wolke'])} der {len(tief)} Kameras unter Gelaende stehen in der Fusion ({fpfad}, {len(fusion)} Bilder)"
                                   + (f": {', '.join(n[:40] for n in u['in_wolke'][:6])}" if u["in_wolke"] else " - die dichte Wolke ist frei davon"))
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(dict(werkzeug="kamera_gelaende.py", ausrichtung=a[1], unter_m=unter, n=len(K), tief=tief, gruppen=schlecht, ausschliessen=aus, fusion=fpfad,
                   in_wolke=u["in_wolke"], rc=u["rc"]), open(os.path.join(od, "audit", "kamera_plausibel.json"), "w"), indent=1)
    if u["rc"] == 3: print(f"WARNUNG: {len(schlecht)} Quelle(n) mit >= {gruppe} Kameras unter Gelaende - Bildgruppe falsch verortet? {len(aus)} Bilder aus der dichten Wolke nehmen (audit/kamera_plausibel.json)"); return 3
    if schlecht: print(f"BESTANDEN fuer die dichte Wolke: {len(schlecht)} Quelle(n) mit >= {gruppe} Kameras unter Gelaende im SfM-Modell, aber keine davon in der Fusion (Hinweis: Lage dieser Bilder im Modell unbrauchbar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
