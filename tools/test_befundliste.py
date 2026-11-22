#!/usr/bin/env python3
"""test_befundliste.py - synthetische Pruefung von tools/befundliste.py (22.11.2026, Agenten-Schleife automatisch).

Nachgebaut sind die Sichtbefunde der Nacht 21./22.11. am Schwabentor (audit/neben_eigen__IMG_20261106_113231.jpg, Laeufe 1121m..1122a):
  oben    Putz mit Rundbogenfenster + Gesimsband im Foto, Modell glatt            -> 'fehlt/zu flach'      (Rundbogenfenster flach / fehlen)
  Mitte   geschweiftes Vordach (gekruemmte Traufe) im Foto, Modell Kasten          -> 'Form falsch'         (Vordach flache Platte)
  unten   Quadermauerwerk (Fugen) im Foto, Modell richtungslose Beulen              -> 'zu grob/verrauscht'  (Mauerwerk klumpig)
  dazu    gutes Modell (Geometrie wie Foto) -> keine Flaechenbefunde; falsche Kamera (Foto zeigt Himmel) -> 'Beleg ungueltig';
          Fassade ohne Fotos (seiten_luecken 'ungesehen') -> 'KEINE FOTOS' statt FEHLER; Codefehler im Log; Tor-JSONs (hand_vergleich, fenster_form_tor);
          Ort aus der Kamera (z-Bereich je Zone), Bauteil aus audit/*_auto.json, Ausschnitt-Bilder.
Kein Rechenlauf, < 10 s, < 300 MB. Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/test_befundliste.py
"""
import sys, os, json, tempfile, shutil
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import befundliste as BL

F = 0


def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text)
    if not ok: F += 1


W, H = 600, 800
X0, X1, Y0, Y1 = 150, 450, 100, 700           # Gebaeude im Bild; Kamera 30 m vor der Wand, f 600 -> 0,05 m/px; y 100 = z 30, y 700 = z 0
YO, YU = 340, 460                              # Grenzen oben/Mitte/unten (z 18 / z 12)


def traufe(x):                                 # geschweifte Traufkante des Vordachs (Mitte tief, Enden hoch)
    return 445 - 60 * ((x - 300) / 150.0) ** 2


def foto_bild(rng):
    im = np.full((H, W), 228.0) + rng.normal(0, 1.5, (H, W))
    im[Y0:Y1, X0:X1] = 200 + rng.normal(0, 2, (Y1 - Y0, X1 - X0))
    for cx in (240, 360):                      # zwei Rundbogenfenster in Nischen
        cv2.rectangle(im, (cx - 25, 170), (cx + 25, 260), 150, -1); cv2.circle(im, (cx, 170), 25, 150, -1)
        cv2.rectangle(im, (cx - 12, 185), (cx + 12, 255), 55, -1); cv2.circle(im, (cx, 185), 12, 55, -1)
        cv2.line(im, (cx - 32, 264), (cx + 32, 264), 70, 4)
    cv2.line(im, (X0, 300), (X1, 300), 70, 6)  # Gesimsband
    for x in range(X0, X1):                    # Vordach: Ziegelflaeche bis zur geschweiften Traufe
        y2 = int(traufe(x)); im[355:y2, x] = 85 + 10 * ((np.arange(355, y2) // 8) % 2)
    for r, y in enumerate(range(YU, Y1, 24)):  # Quader 48 x 24 mit Fugen
        for x in range(X0 - (24 if r % 2 else 0), X1, 48):
            a, b = max(x, X0), min(x + 48, X1)
            if b > a: im[y:y + 24, a:b] = rng.uniform(95, 150) + rng.normal(0, 4, (min(24, Y1 - y), b - a))
            im[y:y + 24, max(x, X0):max(x, X0) + 3] = 45
        im[y:y + 3, X0:X1] = 45
    g = np.clip(im, 0, 255).astype(np.uint8)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


def modell_bild(art, rng):
    r = np.full((H, W), 235.0)
    r[Y0:Y1, X0:X1] = 200
    if art == "gut":
        for cx in (240, 360):
            cv2.rectangle(r, (cx - 25, 170), (cx + 25, 260), 170, -1); cv2.circle(r, (cx, 170), 25, 170, -1)
            cv2.rectangle(r, (cx - 12, 185), (cx + 12, 255), 90, -1); cv2.circle(r, (cx, 185), 12, 90, -1)
            cv2.line(r, (cx - 32, 264), (cx + 32, 264), 110, 4)
        cv2.line(r, (X0, 300), (X1, 300), 110, 6)
        for x in range(X0, X1): r[355:int(traufe(x)), x] = 150
        for rr, y in enumerate(range(YU, Y1, 24)):
            for x in range(X0 - (24 if rr % 2 else 0), X1, 48): r[y:y + 24, max(x, X0):max(x, X0) + 3] = 120
            r[y:y + 3, X0:X1] = 120
    else:
        r[370:412, X0 + 10:X1 - 10] = 150; r[412:418, X0 + 10:X1 - 10] = 90          # Kastenvordach: gerade Unterkante, falsche Hoehe
        hf = cv2.GaussianBlur(rng.normal(0, 1, (Y1 - YU, X1 - X0)).astype(np.float32), (0, 0), 3) * 60.0     # Hoehenfeld mit Beulen ohne Richtung,
        gy, gx = np.gradient(hf); nrm = np.dstack([-gx, -gy, np.ones_like(hf)]); nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)  # schattiert wie
        li = np.array([-0.45, -0.75, 1.0]); li /= np.linalg.norm(li); r[YU:Y1, X0:X1] = 60 + 190 * np.clip(nrm @ li, 0, 1)            # modell_neben_foto
    g = np.clip(r, 0, 255).astype(np.uint8)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


def kamera():
    C = np.array([30.0, 0.0, 15.0]); R = np.array([[0, 1.0, 0], [0, 0, -1.0], [-1.0, 0, 0]])     # Blick -x, rechts = +y, unten = -z
    rv = cv2.Rodrigues(R)[0].ravel(); t = -R @ C
    return dict(rvec=rv.tolist(), t=t.tolist(), f_px=600.0, cx=300.0, cy=400.0, k1=0.0, bild=[W, H])


def objekt_anlegen(d, ungesehen=False):
    od = os.path.join(d, "modelle", "synth"); au = os.path.join(od, "audit"); os.makedirs(au); os.makedirs(os.path.join(od, "messprotokoll"))
    json.dump(dict(name="synth", seiten_konvention={"+x": "Nord", "-x": "Sued", "+y": "West", "-y": "Ost"}), open(os.path.join(od, "objekt.json"), "w"))
    da = os.path.join(d, "daten"); os.makedirs(os.path.join(da, "fassade"))
    fa = [dict(id="f00", n=[1.0, 0.0], d=[0.0, 1.0], o=[0.0, 0.0], u=[-10.0, 10.0], z=[0.0, 30.0]),
          dict(id="f01", n=[-1.0, 0.0], d=[0.0, -1.0], o=[-12.0, 0.0], u=[-10.0, 10.0], z=[0.0, 30.0])]
    json.dump(dict(fassaden=fa), open(os.path.join(da, "fassade", "fassaden.json"), "w"))
    json.dump(dict(waende=[dict(nr=0, ungesehen=ungesehen, abdeckung=0.1 if ungesehen else 0.95, fotos=1 if ungesehen else 30),
                           dict(nr=1, ungesehen=True, abdeckung=0.0, fotos=0, ohne_daten_m2=400.0)]), open(os.path.join(au, "seiten_luecken.json"), "w"))
    json.dump(dict(f00=dict(fenster=[dict(u0=-3.5, u1=-1.5, z0=22.0, z1=27.0), dict(u0=1.5, u1=3.5, z0=22.0, z1=27.0)])), open(os.path.join(au, "fenster_auto.json"), "w"))
    json.dump(dict(fassaden=[dict(id="f00", u0=-7.5, u1=7.5, z_t=12.5, z_a=17.0, familie="geschweift")]), open(os.path.join(au, "vordach_profil.json"), "w"))
    json.dump(dict(passt=1, gesamt=2, bauteile=[dict(bauteil="galerie", urteil="PASST"), dict(bauteil="uhr", urteil="FALSCH", masse=dict(mitte_z=dict(soll=31.9, ist=29.0, ok=False)))]),
              open(os.path.join(au, "hand_vergleich.json"), "w"))
    json.dump(dict(fassaden=dict(f00=[dict(kasten=[1.5, 3.5, 22.0, 27.0], fenster=dict(gebaut="gerade", fotos_sagen="rund", urteil="FALSCH", stimmen=dict(rund=9, gerade=1)))])),
              open(os.path.join(au, "fenster_form_tor.json"), "w"))
    json.dump(dict(kamera=kamera()), open(os.path.join(od, "messprotokoll", "K-foto_a.json"), "w"))
    json.dump(dict(kamera=kamera()), open(os.path.join(od, "messprotokoll", "K-foto_b.json"), "w"))
    log = os.path.join(da, "gesamtkette.log")
    open(log, "w").write("=== fassaden\nquader_raster w01_mono.npz: FEHLER UnboundLocalError: cannot access local variable 'oe_f' where it is not associated with a value - Relief unveraendert\n"
                         "/x/scipy/_measurements.py:810: RuntimeWarning: invalid value encountered in divide\n")
    return od, au, da, log


def ueberlapp(b, z0, z1):
    z = (b.get("ort") or {}).get("z")
    return bool(z) and None not in z and min(z[1], z1) - max(z[0], z0) > 0.5


def main():
    rng = np.random.default_rng(7); foto = foto_bild(rng)
    gut = np.hstack([foto, modell_bild("gut", rng)]); schlecht = np.hstack([foto, modell_bild("schlecht", rng)])
    leer = np.full((H, W, 3), 228, np.uint8); leer = (leer.astype(float) + rng.normal(0, 1.5, leer.shape)).clip(0, 255).astype(np.uint8)
    cv2.rectangle(leer, (0, 650), (W, H), (90, 120, 80), -1)                                      # Baeume/Boden unten, oben Himmel
    falsch = np.hstack([leer, modell_bild("schlecht", rng)])

    print("Bildvergleich je Kachel")
    fb, fm = BL.haelften(schlecht); m = BL.modellmaske(fm)
    pruef(abs(m.mean() - (X1 - X0) * (Y1 - Y0) / (W * H)) < 0.02, f"Modellmaske = Gebaeudeflaeche ({m.mean():.3f})")
    q_gut = BL.beleg_quote(foto, m); q_falsch = BL.beleg_quote(leer, m)
    pruef(q_gut is not None and q_gut < BL.BELEG_QUOTE, f"Beleg: Umriss liegt auf Fotokanten (Quote {q_gut:.2f} < {BL.BELEG_QUOTE})")
    pruef(q_falsch is None or q_falsch > BL.BELEG_QUOTE, f"Beleg: Foto ohne Gebaeude -> Quote {q_falsch} > {BL.BELEG_QUOTE}")
    K = kamera(); h = BL.strahl_treffer(K, 300, 100, 1.0, [dict(id="f00", n=[1, 0], d=[0, 1], o=[0, 0], u=[-10, 10], z=[0, 30])])
    pruef(h is not None and h[0] == "f00" and abs(h[1]) < 0.05 and abs(h[2] - 30.0) < 0.05 and abs(h[3] - 30.0) < 0.1, f"Strahl Bildmitte oben -> f00 u 0 z 30 in 30 m ({h})")
    p = BL.projizieren(K, [0.0, 2.5, 15.0], 1.0)
    pruef(p is not None and abs(p[0] - 350) < 0.5 and abs(p[1] - 400) < 0.5, f"Projektion u 2,5 z 15 -> Pixel (350, 400) ({p})")

    d = tempfile.mkdtemp(prefix="befundliste_test_")
    try:
        od, au, da, log = objekt_anlegen(d)
        cv2.imwrite(os.path.join(au, "neben_foto_a.jpg"), schlecht, [cv2.IMWRITE_JPEG_QUALITY, 95])
        cv2.imwrite(os.path.join(au, "neben_foto_b.jpg"), falsch, [cv2.IMWRITE_JPEG_QUALITY, 95])
        E = BL.erstellen(os.path.join(od, "objekt.json"), daten=da, log=log, verdecker=False)
        B = E["befunde"]; bild = [b for b in B if b["art"] in BL.ARTEN.values() and b["beleg"].get("bild", "").endswith("foto_a.jpg") and "kacheln" in (b["beleg"].get("zahl") or {})]
        print("Schlechtes Modell (Schwabentor-Befunde der Nacht)")
        fe = [b for b in bild if b["art"] == "fehlt/zu flach" and ueberlapp(b, 18, 30) and b["stufe"] == "FEHLER"]
        pruef(bool(fe), "oben: 'fehlt/zu flach' (Rundbogenfenster/Gesims) im z-Bereich 18-30 m" + (f" z {fe[0]['ort']['z']}, Bauteil '{fe[0]['ort'].get('bauteil')}'" if fe else f" - gefunden: {[(b['art'], b['ort'].get('z')) for b in bild]}"))
        pruef(any(b["ort"].get("bauteil") == "fenster" for b in fe), "oben: Bauteil 'fenster' aus fenster_auto.json zugeordnet")
        fo = [b for b in bild if b["art"] == "Form falsch" and ueberlapp(b, 12, 18)]
        pruef(bool(fo), "Mitte: 'Form falsch' (Kastenvordach gegen geschweifte Traufe) im z-Bereich 12-18 m" + (f" Bauteil '{fo[0]['ort'].get('bauteil')}'" if fo else f" - gefunden: {[(b['art'], b['ort'].get('z')) for b in bild]}"))
        pruef(any("vordach" in b["ort"].get("bauteil", "") for b in fo), "Mitte: Bauteil 'vordach_profil' -> Vorschlag " + (fo[0]["vorschlag"]["werkzeug"][:40] if fo else "-"))
        kl = [b for b in bild if b["art"] == "zu grob/verrauscht" and ueberlapp(b, 0, 12)]
        pruef(bool(kl) and "quader_raster" in kl[0]["vorschlag"]["werkzeug"], "unten: 'zu grob/verrauscht' (klumpiges Mauerwerk) z 0-12 m -> tools/quader_raster.py")
        cfid = [b["id"] for b in B if b["art"] == "Codefehler"]
        pruef(bool(kl) and kl[0]["beleg"].get("moegliche_ursache") == cfid, f"Klumpen mit Codefehler in quader_raster verknuepft ({kl[0]['beleg'].get('moegliche_ursache') if kl else '-'})")
        pruef(all(b.get("ausschnitt") and os.path.exists(os.path.join(od, b["ausschnitt"])) for b in fe + fo + kl), "Ausschnitt-Bilder Foto|Modell je Bildbefund geschrieben")
        pruef(all(b["ort"].get("seite") == "Nord" for b in fe + fo + kl), "Himmelsseite aus seiten_konvention (f00 -> Nord)")
        bu = [b for b in B if b["art"] == "Beleg ungueltig"]
        pruef(len(bu) == 1 and bu[0]["beleg"]["bild"].endswith("foto_b.jpg") and not [b for b in B if b["art"] in BL.ARTEN.values() and b["beleg"].get("bild", "").endswith("foto_b.jpg")],
              "falsche Kamera (Foto zeigt Himmel): 'Beleg ungueltig', keine Flaechenbefunde aus diesem Bild")
        cf = [b for b in B if b["art"] == "Codefehler"]
        pruef(len(cf) == 1 and cf[0]["vorschlag"]["werkzeug"] == "tools/quader_raster.py", "Codefehler aus dem Log (UnboundLocalError) -> tools/quader_raster.py; RuntimeWarning nicht")
        pruef(any(b["art"] == "Lage/Mass" and b["ort"].get("bauteil") == "uhr" for b in B) and not any(b["ort"].get("bauteil") == "galerie" for b in B), "hand_vergleich: FALSCH -> Befund, PASST -> keiner")
        ff = [b for b in B if b["beleg"].get("tor") == "audit/fenster_form_tor.json"]
        pruef(len(ff) == 1 and ff[0].get("ausschnitt"), "fenster_form_tor FALSCH -> Befund mit Ausschnitt (Fensterkasten in die Kamera projiziert)")
        ko = [b for b in B if b["art"] == "keine Fotos"]
        pruef(len(ko) == 1 and ko[0]["ort"]["fassade"] == "f01" and ko[0]["stufe"] == "KEINE FOTOS" and ko[0]["ort"].get("seite") == "Sued", "Wand ohne Fotos (f01 Sued): 'keine Fotos', kein FEHLER")
        pruef(os.path.exists(os.path.join(au, "befunde.json")) and json.load(open(os.path.join(au, "befunde.json")))["befunde"], "audit/befunde.json geschrieben")
        rf = [b["stufe"] for b in B]; pruef(rf == sorted(rf, key=lambda s: {"FEHLER": 0, "HINWEIS": 1, "KEINE FOTOS": 2}[s]), "Reihenfolge FEHLER vor HINWEIS vor KEINE FOTOS")

        print("Gutes Modell (Geometrie wie im Foto)")
        cv2.imwrite(os.path.join(au, "neben_foto_a.jpg"), gut, [cv2.IMWRITE_JPEG_QUALITY, 95]); os.remove(os.path.join(au, "neben_foto_b.jpg"))
        E2 = BL.erstellen(os.path.join(od, "objekt.json"), daten=da, verdecker=False)
        b2 = [b for b in E2["befunde"] if b["art"] in BL.ARTEN.values() and b["stufe"] == "FEHLER" and "kacheln" in (b["beleg"].get("zahl") or {})]
        pruef(len(b2) == 0, f"keine Flaechen-FEHLER ({[(b['art'], b['ort'].get('z'), b['staerke']) for b in b2]})")
        pruef(not os.path.exists(os.path.join(au, "befunde", "b40.jpg")) and len(os.listdir(os.path.join(au, "befunde"))) == len([b for b in E2["befunde"] if b.get("ausschnitt")]), "alte Ausschnitte des vorigen Laufs entfernt")

        print("Fassade ohne Fotos")
        shutil.rmtree(d); od, au, da, log = objekt_anlegen(d, ungesehen=True)
        cv2.imwrite(os.path.join(au, "neben_foto_a.jpg"), schlecht, [cv2.IMWRITE_JPEG_QUALITY, 95])
        E3 = BL.erstellen(os.path.join(od, "objekt.json"), daten=da, verdecker=False)
        b3 = [b for b in E3["befunde"] if b["art"] in BL.ARTEN.values()]
        pruef(b3 and all(b["stufe"] == "KEINE FOTOS" and b["staerke"] == 0 for b in b3), f"Bildbefunde auf ungesehener f00 -> 'KEINE FOTOS' ({len(b3)})")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print(f"test_befundliste: {F} Fehler")
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
