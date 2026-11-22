#!/usr/bin/env python3
"""haufen_klaeren.py - Strassenhaufen des Grundriss-Tors (tools/wolke_grundriss_pruefen.py, Test A) AUTOMATISCH klaeren: Doppelwand oder Umgebung?

Anlass 22.11.2026 (Kettenlauf schwabentor-1122k, Nutzer: "Keine Handangriffe, nur Automatik", "Der Grundrisscheck ist wichtig"): die richtige Lage
fiel nur durch Tor A, weil derselbe Platz-Haufen vor der Ostseite (44 330 Punkte; 1120: 44 105) wieder auftauchte, den am 20.11. ein Handeintrag
(objekt.json grundriss_haufen_geklaert) als Laterne/Schildermast/Oberleitung/Erker/Sichtstrahl-Faecher geklaert hatte. Handbefund damals:
"Ostwand im Schnitt einfach bei x 3-4 m, keine zweite parallele Wand". Diese Pruefung macht den Handbefund messbar.

MERKMAL "WANDBLATT": eine versetzte Wand (falsche Lage, falsch gesetztes Teilnetz) ist im Haufen ein senkrechtes ebenes Blatt, das das ganze
Wandband (z 1,5-9 m) ueber viele Meter LUECKENLOS fuellt - wie die echten Waende derselben Wolke. Umgebung fuellt es nicht: Masten sind schmal,
Oberleitung/Erker haengen oben (unten leer), Sichtstrahl-Faecher und Flugpunkte sind duenne schraege Streifen mit Hoehenbaendern.
  Suche: Hough (Richtung 1 Grad x Abstand 0,25 m, Band +-0,3 m) auf hoechstens 250 000 Proben, Auswertung je Blatt auf ALLEN Punkten:
  Raster laengs 0,5 m x Hoehe 0,5 m (15 Zeilen), Zelle belegt ab 2 Punkten, Spalte "voll" ab 70 % belegter Zeilen; Blattlaenge = laengster
  Lauf voller Spalten (eine Spalte Luecke erlaubt).
GRENZE: Blatt >= GRENZE_M = 3,0 m = 2 x laengstes Umgebungsblatt der Belege (1,5 m); liegt zwischen Umgebung (<= 1,5 m) und versetzten
  Waenden (>= 5,5 m), geometrische Mitte 2,9 m. (Erster Entwurf Grenze = L_eich/3 verworfen: L_eich schwankt 9,5-17 m je nach Wolke, bei 17 m
  lag die Grenze 5,7 m UEBER dem 5,5-m-Blatt der falschen Lage +8 Grad x1,089 -> haette sie durchgewunken.)
EICHUNG an derselben Wolke: dieselbe Suche auf den eigenen Wandpunkten (nicht Strasse, <= 1 m von einer LoD2-Kante des Zielgebaeudes) ->
  L_eich = laengstes eigenes Wandblatt. URTEILSFAEHIG nur bei L_eich >= 2 x GRENZE_M (6 m): sonst fuellt die Wolke schon ihre eigenen Waende
  nicht lueckenlos, eine duenne versetzte Wand fiele unter die Grenze -> "nicht geklaert" (streng, Tor bleibt rot).
URTEIL: geklaert (echte Umgebung) <=> urteilsfaehig UND laengstes Haufenblatt < GRENZE_M. Sonst NICHT geklaert (rot).
BELEGE 22.11.2026 (echtes Tor auf Kopien, /media/oem/rcdaten/tmp/haufen_auto, objekt.json OHNE Handeintrag; laengstes Haufenblatt / L_eich):
  richtig  schwabentor-1120  Platz-Haufen 44 105 P.: 0,5 m / 9,5 m  -> geklaert, rc 0
  richtig  schwabentor-1122k Platz-Haufen 44 330 P.: 1,5 m / 16,0 m -> geklaert, rc 0 (das 1,5-m-Blatt ist der auskragende Bilderker bei x 5,8)
  falsch   gu_probe2 (Teil 1 per GPS, Doppelwand West, 17,6 %): 18,5 m -> rot
  falsch   1122k nachgestellt +8 Grad x0,92 (wie Lauf 1122: Haufen 362 973 statt 348 813): 5,5 m -> rot; -8 Grad x0,92: 17,0 m; weitere im Bericht
           (Nachstellung = Drehung um den Rahmenursprung + Massstab, Versatz neu an die LoD2-Waende gelegt; KEINE echten Kettenloesungen).
GRENZEN / UNGEPRUEFT: Waende unter 1,5 m Abstand zur LoD2-Kante zaehlen in Tor A gar nicht (dort greift Test C); versetzte Teile ausserhalb
  z 1,5-9 m (nur Dach) sieht das Merkmal nicht; fehlt das Zielgebaeude im LoD2, gibt es keine Eichung -> nicht geklaert.
Abschalten: RCPARK_HAUFEN_AUTO=0 (dann nur noch der alte Handeintrag).
"""
import os
import numpy as np

AN = os.environ.get("RCPARK_HAUFEN_AUTO", "1") != "0"
UMGEBUNG_MAX_M = 1.5          # laengstes Wandblatt echter Umgebung in den Belegfaellen (1120: 0,5 m, 1122k: 1,5 m Bilderker)
GRENZE_M = 2 * UMGEBUNG_MAX_M  # 3,0 m: zwischen Umgebung (<= 1,5 m) und versetzten Waenden (>= 5,5 m), geometrische Mitte 2,9 m
EICH_FAKTOR = 2.0             # urteilsfaehig nur, wenn die eigenen Waende derselben Wolke >= 2 x GRENZE_M lueckenlos fuellen


def blatt_suche(P, zlo=1.5, zhi=9.0, dz=0.5, da=0.5, breite=0.3, k_min=2, f_voll=0.7, n_max=250000, spitzen=6, seed=0):
    """Senkrechte ebene Blaetter in P (x, y, z). Rueckgabe: Liste je Blatt (Richtung der Normalen, Abstand, Punkte, laenge_voll_m, fuell_median, mitte)."""
    P = np.asarray(P, float); P = P[(P[:, 2] >= zlo) & (P[:, 2] < zhi)]
    if len(P) < 50: return []
    S = P if len(P) <= n_max else P[np.random.default_rng(seed).choice(len(P), n_max, replace=False)]
    nz = int(round((zhi - zlo) / dz)); out = []
    th = np.radians(np.arange(180)); N = np.c_[np.cos(th), np.sin(th)]
    D = S[:, :2] @ N.T
    lo = np.floor(D.min() / 0.25) - 1; nb = int(np.ceil(D.max() / 0.25) - lo) + 2
    H = np.zeros((180, nb), np.int64)
    for w in range(180): H[w] = np.bincount((np.floor(D[:, w] / 0.25) - lo).astype(int), minlength=nb)[:nb]
    Hs = H + np.roll(H, 1, 1) + np.roll(H, -1, 1)
    genommen = []
    for f in np.argsort(Hs.ravel())[::-1]:
        w, b = divmod(int(f), nb)
        if any(min(abs(w - w2), 180 - abs(w - w2)) < 5 and abs(b - b2) < 6 for w2, b2 in genommen): continue
        genommen.append((w, b))
        d0 = (b + lo + 0.5) * 0.25; sel = np.abs(P[:, :2] @ N[w] - d0) < breite          # Auswertung auf ALLEN Punkten (Dichte wie in der Eichung)
        if sel.sum() < 30: break
        t = np.array([-N[w, 1], N[w, 0]]); a = P[sel, :2] @ t; z = P[sel, 2]
        ia = (np.floor(a / da) - np.floor(a.min() / da)).astype(int); iz = np.clip(((z - zlo) / dz).astype(int), 0, nz - 1)
        G = np.zeros((ia.max() + 1, nz), int); np.add.at(G, (ia, iz), 1)
        frac = (G >= k_min).mean(1); best = cur = luecke = 0
        for v in frac >= f_voll:
            if v: cur += 1 + luecke; luecke = 0
            elif cur and luecke == 0: luecke = 1
            else: cur = luecke = 0
            best = max(best, cur)
        out.append(dict(richtung_grad=int(w), abstand_m=round(float(d0), 2), punkte=int(sel.sum()), laenge_voll_m=round(best * da, 1),
                        ausdehnung_m=round(float(np.ptp(a)), 1), fuell_median=round(float(np.median(frac)), 2),
                        mitte=[round(float(v), 2) for v in (N[w] * d0 + t * np.median(a))]))
        if len(genommen) >= spitzen: break
    return sorted(out, key=lambda b: -b["laenge_voll_m"])


def hoehenprofil(P, zlo=1.5, zhi=9.0, dz=0.5):
    """Anteil der Punkte je 0,5-m-Hoehenzeile (nur Bericht: Wand = gleichmaessig, Umgebung = Baender)."""
    h = np.histogram(np.asarray(P)[:, 2], bins=np.arange(zlo, zhi + 1e-6, dz))[0]
    return [round(float(v), 3) for v in h / max(1, h.sum())]


def klaeren(H, eigen):
    """H = Haufenpunkte (x, y, z im Wandband), eigen = eigene Wandpunkte des Zielgebaeudes (Eichung). -> dict mit geklaert (bool), urteilsfaehig, befund, Merkmalen."""
    bl_e = blatt_suche(eigen) if eigen is not None and len(eigen) else []
    L_eich = bl_e[0]["laenge_voll_m"] if bl_e else 0.0; grenze = GRENZE_M
    bl_h = blatt_suche(H); L_h = bl_h[0]["laenge_voll_m"] if bl_h else 0.0
    m = dict(regel="Wandblatt (haufen_klaeren.py)", laengstes_haufenblatt_m=L_h, haufenblatt=(bl_h[0] if bl_h else None), eich_wandblatt_m=L_eich,
             eich_blatt=(bl_e[0] if bl_e else None), grenze_m=grenze, eich_mindest_m=EICH_FAKTOR * grenze, punkte=int(len(H)), hoehenprofil=hoehenprofil(H) if len(H) else [])
    if L_eich < EICH_FAKTOR * grenze:
        m.update(geklaert=False, urteilsfaehig=False, befund=f"nicht geklaert: eigene Waende fuellen das Wandband nur {L_eich:.1f} m lang (< {EICH_FAKTOR * grenze:.1f} m) - Wolke zu duenn fuer ein Urteil")
    elif L_h >= grenze:
        b = bl_h[0]
        m.update(geklaert=False, urteilsfaehig=True, befund=f"NICHT geklaert: senkrechtes Wandblatt im Haufen {L_h:.1f} m lang (Grenze {grenze:.1f} m; eigene Wand {L_eich:.1f} m) bei {b['mitte']}, Normale {b['richtung_grad']} Grad - versetzte Wand / falsche Lage")
    else:
        m.update(geklaert=True, urteilsfaehig=True, befund=f"automatisch geklaert: kein Wandblatt im Haufen (laengstes {L_h:.1f} m < Grenze {grenze:.1f} m; eigene Wand {L_eich:.1f} m) - echte Umgebung / Sichtstrahl-Faecher, keine Doppelwand")
    return m
