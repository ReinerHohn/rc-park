"""Fernsicht-Regel auf den ECHTEN 1122-Gruppen (seiten.json, EXIF-GPS) - nur lesen; Gegenprobe Martinstor, falls vorhanden."""
import os, sys, json, collections
sys.path.insert(0, "/home/oem/git/rc-park/.claude/worktrees/agent-a5d004d794431467c/tools")
from seiten_erkennen import fernsicht_gruppen, fernsicht_behalten, richtung
from paarvorwahl import gps_aus_exif
from netz_fotos_holen import geo
for obj, w in (("schwabentor-1122", "/media/oem/scan/rc-park_daten/schwabentor-1122/pipe/sfm"),) + tuple((o, f"/media/oem/scan/rc-park_daten/{o}/pipe/sfm") for o in sys.argv[1:]):
    sj = f"{w}/seiten.json"
    if not os.path.isfile(sj): print(obj, "keine seiten.json"); continue
    s = json.load(open(sj)); mitte = geo(json.load(open(f"/home/oem/git/rc-park/modelle/{obj}/objekt.json"))); fd = f"/media/oem/scan/rc-park_daten/{obj}/fotos"
    gq = collections.defaultdict(list)
    for n, k in s["gemeinschaft"].items():
        q = gps_aus_exif(os.path.join(fd, n))
        if q is not None: gq[k].append(q)
    fern = fernsicht_gruppen(gq, mitte); verb = [dict(v) for v in s["verbindungen"]]; beh = fernsicht_behalten(verb, fern)
    print(obj, "Fernsicht-Gruppen:", sorted(fern), "behalten:", sorted(beh), "| Gruppen mit GPS:", len(gq))
    for k in sorted(fern): print("   Gruppe", k, "Bilder", s["groessen"][k], "GPS-Abstaende", sorted(round(richtung(mitte, q)[1]) for q in gq[k]))
