# Lehren 8.11. (Sweep, Lot, Foto-Loop) - Nutzerwunsch "Logge alles mit und lerne"
1. **Bildfeedback zuerst.** Wolke (gelb) + Modellkanten (rot) auf kalibriertem Foto (`tools/modell_foto_overlay.py`) hat in 5 Minuten gezeigt, was Zahlen in Stunden nicht zeigten (Modell gekippt, zu schmal, Dach zu niedrig). Immer vor jeder Zahlenjagd ansehen.
2. **Beweistest synthetisch IST nicht der Echtbefund.** Synthetik <1 cm bewies nur, dass die Suche funktioniert, WENN das Teil in der Wolke so existiert. Echtfehler kam aus Modellform/Pose. Beide Tests brauchen: (a) Synthetik, (b) Overlay am echten Foto.
3. **Nur Verschiebung reicht nicht.** Drehung (gier/nick/roll) + Streckung gehoeren in den Sweep (8 DoF); Nutzer hat das Kippen im Bild sofort gesehen.
4. **Schrumpf-Falle (BS143/BS145):** jede Zielfunktion, bei der ein kleineres Modell leichter in die Wolke passt, schrumpft. Rueckrichtung mit FESTER Region + Kappung.
5. **Bezugsrahmen pruefen vor Modell-Fit:** Wolke war gekippt (BS146). Boden/Wand-Ebenen messen (robust: RANSAC; maskierte Baender verfaelschen Neigungen).
6. **Handwerte aus Bildern sind keine Messung (BS148).** Messungen nur per Werkzeug mit Protokoll.
7. **Kamerahoehe 15,8 m im Netzrahmen** (Fotos eher vom Platz): ungeklaert, vor Verwendung der Kamerapositionen pruefen.
8. **Plateau = nicht bestimmt:** Fensterreihen in ebener Wand liefern aus der Wolke nur dn. u/z brauchen Foto-Kanten.
9. **Arbeitsweise:** erst Hypothese aufschreiben, mit einem schnellen Test widerlegen (z.B. 7-Grad-Gier: RANSAC widerlegte in 1 Min), dann bauen.
Offen: Modell zu schmal (links ~200 px), Dach 100 px zu niedrig, Arkadenabstand/Erkerlage, Kamerahoehe, schraeges Punktband in Pfeilerhoehe.
