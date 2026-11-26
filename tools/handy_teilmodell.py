#!/usr/bin/env python3
"""handy_teilmodell.py <db> <bilder> <vorbereitet.json> <aus-ordner> [--threads 12]

Teilmodell NUR aus den neuen Zusatzfotos (z. B. Handyfotos 26.11.2026) per inkrementellem COLMAP-Mapper, wenn sich viele Bilder nicht ins Hauptnetz einordnen
(PnP braucht bekannte 3D-Punkte; Brücke/Unterdurchgang/Treppe hatte das Netz nicht: 144 von 241 Bildern blieben draussen).
Der Mapper nutzt nur die Paare NEU x NEU aus der Zusatz-Datenbank (zusatzfotos_registrieren.py merkmale). <aus>/<n>/ = Modelle (cameras/images/points3D .bin).
Ausrichten ins Hauptmodell: tools/teilmodell_ausrichten.py (gemeinsame, schon eingeordnete Bilder -> Aehnlichkeitsabbildung).
Verwandt: modelle/METHODE_SEITEN_SFM.md (aufwendigere Seiten-Methode), tools/zusatzfotos_registrieren.py, tools/kameras_nachtragen.py.
Vorlaeufer: keiner fuer 'nur neue Bilder'; seiten_luecken/zusatzfotos_registrieren ordnen nur gegen bekannte Punkte ein.
"""
import os, sys, json, argparse


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("db"); ap.add_argument("bilder"); ap.add_argument("vorb"); ap.add_argument("aus")
    ap.add_argument("--threads", type=int, default=12); ap.add_argument("--min_model_size", type=int, default=8)
    a = ap.parse_args(); import pycolmap
    names = sorted(json.load(open(a.vorb))["bilder"]); os.makedirs(a.aus, exist_ok=True)
    o = pycolmap.IncrementalPipelineOptions(); o.image_names = names; o.num_threads = a.threads; o.min_model_size = a.min_model_size
    print(f"Mapper auf {len(names)} Bildern", flush=True)
    r = pycolmap.incremental_mapping(a.db, a.bilder, a.aus, o)
    for k, m in sorted(r.items()):
        print(f"Modell {k}: {m.num_reg_images()} Bilder, {m.num_points3D()} Punkte, Reproj {m.compute_mean_reprojection_error():.2f} px", flush=True)
    print(f"FERTIG {len(r)} Modelle", flush=True); return 0 if r else 3


if __name__ == "__main__":
    sys.exit(main())
