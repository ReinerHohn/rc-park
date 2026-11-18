# Recherche 18.11.2026: runde Elemente (Tuermchen, Erker, Rundtuerme, Pfeiler) - Wandbild/Bauplan

Auftrag Nutzer: "recherchiere tief, wie wir es bei runden Elementen machen (Schloesser, Erker am Kaufhaus)". Stand: Recherche, KEIN Code, nichts gemessen.

## Stand im Repo (gelesen)
- `fassade_ortho.py`: (u,z)-Raster je EBENE Wand (koplanare LoD2-Stuecke); Zelle -> Foto per Lochkamera, Sichtbarkeit per Strahl gegen STL, gewichteter Median.
  Keine Zylinder-/Kegel-Abwicklung. Bei runden Flaechen passt die Ebene nicht (nur ein Streifen je Foto nutzbar).
- Kaufhaus-Erker = n-ECK (`bauteile.erker_polygon`, Teil-Achteck: Front + 2 Schraegflaechen) mit Unterbau-Trichter + Netzgewoelbe-Rippen
  -> die Flaechen sind EBEN: je Flaeche ein eigenes Wandbild moeglich (noch nicht gebaut; Erker bisher Katalog/Hand, L3). Foto-F1 Erker-Unterbau Basis 0,596 -> 0,629 (Achse 11,9 + Bogenrippen, LOGBUCH_ERKER_UNTERBAU_R1).
- Martinstor-Tuermchen: Kegelprofil aus Wolke + Silhouette (`wolke_tuerm_baender.py`, `foto_silhouette_profil.py`: Breite je Hoehe gegen den Himmel aus fernem Foto), 4 Stueck.
- Wirklich runde Teile (Laubenpfeiler, Treppenturm, Rundtuerme): nur Katalog / Rotationsprofil.

## Literatur (Web, nur Zusammenfassungen der Suchtreffer gelesen, keine Volltexte geprueft)
1. Zylinder-Orthophoto (ISPRS 2001, Burgtuerme): auf den NAECHSTEN Zylinder projizieren, Pixel fuer Pixel entzerren; normale Ortho-Software (Zentral- -> Orthoprojektion) passt nicht.
2. CIPA 2013: Photo-Plan fuer Zylinder/Kegel aus Einzelfoto; nur EINE Linie unverzerrt.
3. Zhang/Liang/Ma ICCV 2011: "generalized cylinders" (c(s,t)=t*p+h(s)) aus EINEM Foto, Textur low-rank (regelmaessig: Fenster/Fugenraster), robust gegen Verdeckung - Zusatz zu TILT.
4. Rotationsflaechen (Wong/Mendonca/Cipolla): Achse + Profil aus Silhouette; Rest-Mehrdeutigkeit Massstab/Achsneigung, mit Horizont oder mehreren Ansichten aufloesbar (passt zu foto_silhouette_profil).
5. Deveau et al. (CIPA): Achse + Profil aus Laser, Profil-RMS minimieren.
6. Primitive-Fit (Remondino 2012: Zylinder, Pyramiden aus Dense Matching), Werner/Zisserman 2002: Ebene + Abweichung.

## Vorschlag (nicht umgesetzt)
A. Erst unterscheiden: polygonal (Erker, Achtecktuerme) -> JEDE Flaeche als eigene Ebene ins Wandbild (billig, trifft die Kaufhaus-Erker);
   rund (Zylinder) -> `zylinder_ortho.py`: Achse + Radius aus Silhouetten/Sweep, Raster (Winkel*R, z), Sichtbarkeit cos-Winkel zur Flaechennormalen, > 70 Grad faellt weg (wie Ebene);
   Kegel/Helm -> Rotationsprofil + Abwicklung (Abwicklungswinkel).
B. Tiefe: Radialabweichung je Zelle statt Ebenenabweichung (Analog tiefe_lokal).
C. Form nie aus Katalog: Profil aus Silhouetten mehrerer Ansichten (Regel Kernmethode).
D. Test: synthetischer Zylinder (Schnelltest, Rueckprojektion) vor echtem Objekt; dann Kaufhaus-Erker (Ebenen), dann Rundteil.
Risiken: kamera_abdeckung rundum noetig (Luecke > 90 Grad = Seite ungesehen); Achse/Radius-Fehler verschmiert das Wandbild; Verdecker (Baeume, Staende).
