#!/usr/bin/env python3
"""foto_zaehlung.py - Zaehlprotokoll fuer STRUKTURMERKMALE am Foto (Anzahl Oeffnungen/Fenster/Zinnen je Flaeche ...), Register CB.

Warum: Anzahlen kommen NICHT aus Punktwolken (sfm_bodenanker ist laut Quellen-Matrix blind fuer 'anzahl'/'fassade') und NICHT aus Dateien, die den
Generator speisen (zirkulaer). Eine Anzahl gilt erst, wenn sie am Foto gezaehlt, im Foto markiert und als Protokoll abgelegt ist.
Das Protokoll (messprotokoll/Z-<foto>-<nr>.json + .jpg mit Markierungen) nennt je sichtbarer Flaeche die gezaehlten Punkte; 'ergebnis.je_flaeche'
ist der Wert, den die Pruefung 'Oeffnungen je Flaeche' fordert. Voll sichtbare Flaechen muessen gleich viele Punkte haben, sonst Abbruch (Exit 2).

  tools/foto_zaehlung.py modelle/martinstor/objekt.json 043 --was "Ecktuermchen Arkadenband: Oeffnungen je Achteckflaeche" \
      --punkt F1:voll:368,1079 --punkt F2:voll:438,1085 --punkt F0:teil:318,1095 --punkt F3:teil:476,1109  [--nr 1] [--zeuge "Name"]
Punkt = <flaeche-id>:<voll|teil>:<x>,<y> in ORIGINAL-Pixeln des Fotos; 'teil' = nur angeschnitten sichtbare Flaeche (zaehlt nicht fuer das Ergebnis).
"""
import sys, os, json, glob, time, argparse, cv2, numpy as np

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("--was", required=True)
    ap.add_argument("--punkt", action="append", required=True); ap.add_argument("--nr", type=int); ap.add_argument("--wer", default="Claude (Sichtzaehlung am Foto)")
    ap.add_argument("--hinweis", default=""); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); obj = json.load(open(a.objekt)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.objekt))))
    pts = []
    for s in a.punkt:
        fl, art, xy = s.split(":"); x, y = [float(v) for v in xy.split(",")]; assert art in ("voll", "teil"), art; pts.append(dict(flaeche=fl, art=art, x=x, y=y))
    je = {}
    for p in pts: je.setdefault(p["flaeche"], dict(art=p["art"], n=0))["n"] += 1
    voll = [v["n"] for v in je.values() if v["art"] == "voll"]
    if not voll: sys.exit("keine voll sichtbare Flaeche markiert - Zaehlung ungueltig")
    if len(set(voll)) != 1: sys.exit(f"voll sichtbare Flaechen haben verschieden viele Punkte {je} - Zaehlung widerspruechlich, nichts geschrieben")
    fd = obj.get("fotos_dir", "daten/martinstor/fotos"); fd = fd if os.path.isabs(fd) else os.path.join(root, fd)
    cands = sorted(glob.glob(os.path.join(fd, f"{a.foto}_*.jpg")) + glob.glob(os.path.join(fd, f"{a.foto}_*.png"))); assert cands, f"Foto {a.foto} nicht in {fd}"
    im = cv2.imread(cands[0])
    mp = os.path.join(od, "messprotokoll"); os.makedirs(mp, exist_ok=True)
    nr = a.nr or 1 + max([int(os.path.basename(f).split("-")[2].split(".")[0]) for f in glob.glob(os.path.join(mp, f"Z-{a.foto}-*.json"))] or [0]); pid = f"Z-{a.foto}-{nr:03d}"
    for p in pts:
        c = (int(p["x"]), int(p["y"])); col = (0, 200, 0) if p["art"] == "voll" else (0, 160, 255)
        cv2.circle(im, c, 22, col, 4); cv2.putText(im, f"{p['flaeche']}", (c[0] - 20, c[1] - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, col, 3)
    x0, y0 = int(max(0, min(p["x"] for p in pts) - 250)), int(max(0, min(p["y"] for p in pts) - 250)); x1, y1 = int(max(p["x"] for p in pts) + 250), int(max(p["y"] for p in pts) + 250)
    cv2.imwrite(os.path.join(mp, pid + ".jpg"), im[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 90])
    prot = dict(id=pid, typ="zaehlung", foto=a.foto, datei=os.path.basename(cands[0]), was=a.was, wer=a.wer, datum=time.strftime("%Y-%m-%d"), punkte=pts,
                je_flaeche_gezaehlt=je, ergebnis=dict(je_flaeche=voll[0], voll_sichtbare_flaechen=len(voll)), bild=pid + ".jpg", ausschnitt=[x0, y0, x1, y1],
                regel="Quelle: Foto (Sichtzaehlung, massstabsfrei). NICHT aus Punktwolke/Generatoreingabe ableiten (Register CB).", hinweis=a.hinweis)
    json.dump(prot, open(os.path.join(mp, pid + ".json"), "w"), indent=1, ensure_ascii=False)
    print(f"{pid}: je Flaeche {voll[0]} (voll sichtbar: {len(voll)}), Bild {pid}.jpg"); print(json.dumps(je))

if __name__ == "__main__":
    main()
