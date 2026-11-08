#!/usr/bin/env python3
"""video_netz.py - objektunabhaengige Pfadaufloesung der Video-Stufe (Register CR).
Netzname: objekt.json video_stufe.netz, sonst sfm.netz, sonst "alle" wenn sfm/sparse_alle existiert, sonst "nord" (Martinstor: unveraendert sparse_nord/0, db_nord.db, SFM-AUSRICHTUNG-nord.json, dicht_nord_*).
Buendel: video_stufe.buendel (true/false), sonst automatisch, wenn sfm/sparse_buendel/0 UND messprotokoll/SFM-AUSRICHTUNG-buendel.json existieren (Netz ist dann schon im Modellsystem, s=1).
  /media/oem/scan/venv-colmap/bin/python -I tools/video_netz.py modelle/<objekt>/objekt.json     (zeigt die aufgeloesten Pfade)
"""
import os, sys, json

def netz_info(objekt):
    op = os.path.abspath(objekt); od = os.path.dirname(op); obj = json.load(open(op)); vz = obj.get("video_stufe") or {}; sf = obj.get("sfm") or {}; sd = os.path.join(od, "sfm")
    netz = vz.get("netz") or (sf.get("netz") if isinstance(sf.get("netz"), str) else None) or ("alle" if os.path.isdir(os.path.join(sd, "sparse_alle")) else "nord")
    bu = vz.get("buendel")
    if bu is None: bu = os.path.exists(os.path.join(sd, "sparse_buendel", "0")) and os.path.exists(os.path.join(od, "messprotokoll", "SFM-AUSRICHTUNG-buendel.json")) and netz != "nord"
    an = "buendel" if bu else netz
    ent = os.path.join(sd, f"dicht_{netz}_entzerrt.npy"); basis = ent if os.path.exists(ent) else os.path.join(sd, f"dicht_{netz}_modell.npy")
    return dict(od=od, netz=netz, buendel=bool(bu), sd=sd, sparse=os.path.join(sd, "sparse_buendel" if bu else f"sparse_{netz}", "0"), db=os.path.join(sd, f"db_{netz}.db"),
                ausr=os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{an}.json"), basis_npy=basis, basis_farben=os.path.join(sd, f"dicht_{netz}_farben.npy"),
                basis_fused=os.path.join(sd, f"dicht_{netz}"), video_dir=os.path.join(sd, f"dicht_{netz}_video"), cfg=vz, obj=obj)

def video_modell(vdir, wert):
    """--modell auto: das Teilmodell mit den meisten registrierten Bildern aus video_sfm ergebnis.json (sonst '0')."""
    if str(wert) != "auto": return str(wert)
    try: return str(json.load(open(os.path.join(vdir, "ergebnis.json")))["modelle"][0]["modell"])
    except Exception: return "0"

if __name__ == "__main__":
    i = netz_info(sys.argv[1]); i.pop("obj")
    for k, v in i.items(): print(f"{k:12s} {v if k == 'cfg' and len(str(v)) < 200 else (str(v)[:160])}" + ("" if k in ("cfg", "netz", "buendel") or os.path.exists(str(v)) else "   (FEHLT)"))
