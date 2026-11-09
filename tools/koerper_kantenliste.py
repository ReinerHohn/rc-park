#!/usr/bin/env python3
"""koerper_kantenliste.py - Koerper (v11) als Kantenliste mit Kopplungsgruppen fuer das kantenneutrale Tor (tools/kanten_tor.py) und Rueckweg der Korrekturen.

  export      KOERPER_v11.json FE_v9.json KONSOLEN_v11.json OUT.json
              -> {"segmente": [{id, p0, p1, gruppe_id, instanz, spiegel_partner, parameter: {datei, pfad, achse}}], "gruppen": {gruppe_id: {kopplung, parameter, n}}}
              Gruppen = Wiederholung (gleiche Unterposition der Musterzelle ueber alle Instanzen) + Spiegelpartner (Licht i <-> nl-1-i, linke <-> rechte Kante).
              Teilungsparameter je Unterposition: Fenster je Licht-Klasse (Spiegelklasse min(i, nl-1-i)), Konsolen je Seite.
  zuruecklesen TOR.json AUSDIR
              TOR.json: {"korrekturen": [{"parameter": {"datei": "fenster_erker_v9.json", "pfad": "fenster.je_licht[1].z_kaempfer"}, "wert": 12.28,
                                          "quelle": "foto", "begruendung": "..."}]}  (Pfad wie im Export; 'datei' relativ zu AUSDIR)
              schreibt die Werte in die Eingabe-JSONs (alter Wert + Quelle + Begruendung in 'tor_historie'); danach koerper_v11.py bauen neu.
Nichts Objektspezifisches: alle Lagen aus den JSONs der Kette."""
import sys, os, json, re
import numpy as np


def W(u, n, of, al, z, off=0.0):
    return (al * np.asarray(u) + (of + off) * np.asarray(n) + np.array([0, 0, z])).tolist()


def export(k11, fe, kons, out):
    K = json.load(open(k11)); FE = json.load(open(fe)); KO = json.load(open(kons)) if os.path.exists(kons) else {"konsolen": []}
    u, n, of = K["u"], K["n"], K["off_front"]; F = FE["fenster"]; fe_n = os.path.basename(fe); ko_n = os.path.basename(kons)
    segs = []; gruppen = {}

    def add(p0, p1, gid, inst, par, kopplung, partner_key=None):
        sid = len(segs); segs.append({"id": sid, "p0": p0, "p1": p1, "gruppe_id": gid, "instanz": inst, "spiegel_partner": partner_key, "parameter": par})
        g = gruppen.setdefault(gid, {"kopplung": kopplung, "parameter": par, "n": 0}); g["n"] += 1; return sid

    # --- Fenster: je Gruppe (Instanz), je Licht; Teilungsparameter je Licht-Klasse (Spiegelklasse), je_licht falls vorhanden
    nl = F["n_licht"]; wl = F["w_licht"]; jl = F.get("je_licht"); kl = lambda i: min(i, nl - 1 - i); kn = lambda c: "mitte" if 2 * c == nl - 1 else f"seite{c}"
    wert = lambda key, i: (jl[i][key] if jl and key in jl[i] else F[key])
    pfad = lambda key, i: (f"fenster.je_licht[{i}].{key}" if jl else f"fenster.{key}")
    gr = [g for g in F["gruppen"] if g.get("belegt", True)]
    for gi, g in enumerate(F["gruppen"]):
        if not g.get("belegt", True): continue
        ids = {}
        for i in range(nl):
            x0 = g["mitte"] + (i - nl / 2) * wl; x1 = x0 + wl
            for key, gname in (("z_kaempfer", "kaempfer"), ("z_sohl", "sohlbank"), ("z_scheitel", "scheitel")):
                z = wert(key, i) if key != "z_scheitel" or jl else F["z_scheitel"]
                if key == "z_scheitel": xa, xb = 0.5 * (x0 + x1) - 0.15, 0.5 * (x0 + x1) + 0.15
                else: xa, xb = x0 + 0.05, x1 - 0.05
                ids[(gname, i)] = add(W(u, n, of, xa, z), W(u, n, of, xb, z), f"fenster.{gname}.{kn(kl(i))}", gi, {"datei": fe_n, "pfad": pfad(key, i), "achse": "z"}, "wiederholung+spiegel")
        for i in range(nl + 1):
            x = g["mitte"] + (i - nl / 2) * wl; c = min(i, nl - i)
            ids[("pfosten", i)] = add(W(u, n, of, x, wert("z_sohl", min(i, nl - 1))), W(u, n, of, x, F["z_schulter"]), f"fenster.pfosten.{'mitte' if 2 * c == nl else f'aussen{c}'}", gi,
                                      {"datei": fe_n, "pfad": f"fenster.gruppen[{gi}].mitte|fenster.w_licht", "achse": "along"}, "wiederholung+spiegel")
        for (gname, i), sid in ids.items():   # Spiegelpartner: Licht i <-> nl-1-i, Pfosten i <-> nl-i
            j = (nl - i) if gname == "pfosten" else (nl - 1 - i)
            if j != i and (gname, j) in ids: segs[sid]["spiegel_partner"] = ids[(gname, j)]
    # --- Konsolen: Vorderumriss je Konsole (Seiten links/rechts gespiegelt, Unterkante), Form aus konsolen_v11.json (zelle) oder ANNAHME Trapez
    pl = K["balkon"]["platte"]; zp0 = pl["z0"]; Z = KO.get("zelle", {}); prof = Z.get("profil_ausladung")
    for j, kz in enumerate(KO.get("konsolen", [])):
        w = kz.get("breite", 0.45); d_t = max(p[1] for p in prof) if prof else pl["tiefe"] - 0.15; d_b = prof[0][1] if prof else 0.15
        x = kz["along"]; zb = kz["z0"]
        l = add(W(u, n, of, x - w / 2, zp0, d_t), W(u, n, of, x - w / 2, zb, d_b), "konsole.seite", j, {"datei": ko_n, "pfad": f"konsolen[{j}].along|zelle.breite", "achse": "along"}, "wiederholung+spiegel")
        r = add(W(u, n, of, x + w / 2, zp0, d_t), W(u, n, of, x + w / 2, zb, d_b), "konsole.seite", j, {"datei": ko_n, "pfad": f"konsolen[{j}].along|zelle.breite", "achse": "along"}, "wiederholung+spiegel")
        segs[l]["spiegel_partner"] = r; segs[r]["spiegel_partner"] = l
        add(W(u, n, of, x - w / 2, zb, d_b), W(u, n, of, x + w / 2, zb, d_b), "konsole.unten", j, {"datei": ko_n, "pfad": f"konsolen[{j}].z0", "achse": "z"}, "wiederholung")
    # --- Balkon (Platte, Handlauf): Einzelkanten, keine Kopplung
    a0, a1 = pl["along"]
    add(W(u, n, of, a0, zp0, pl["tiefe"]), W(u, n, of, a1, zp0, pl["tiefe"]), "balkon.platte_unten", 0, {"datei": "rohkoerper/koerper_v10.json", "pfad": "balkon.platte.z0", "achse": "z"}, "einzeln")
    res = {"quelle": {"koerper": k11, "fenster_erker": fe, "konsolen": kons}, "rahmen": {"u": u, "n": n, "off_front": of}, "segmente": segs, "gruppen": gruppen,
           "hinweis": "Pfeiler/Boegen/Baluster/Giebel noch nicht exportiert (offen); Konsolenform ANNAHME, solange 'zelle' fehlt"}
    json.dump(res, open(out, "w"), indent=1); print(f"-> {out}: {len(segs)} Segmente, {len(gruppen)} Gruppen: " + ", ".join(f"{k} ({v['n']})" for k, v in gruppen.items()))


def setze(obj, pfad, wert):
    teile = re.findall(r"[^.\[\]]+|\[\d+\]", pfad); cur = obj
    for i, t in enumerate(teile):
        last = i == len(teile) - 1; key = int(t[1:-1]) if t.startswith("[") else t
        if last: alt = cur[key] if (isinstance(cur, list) and key < len(cur)) or (isinstance(cur, dict) and key in cur) else None; cur[key] = wert; return alt
        cur = cur[key]


def zuruecklesen(tor, ausdir):
    T = json.load(open(tor)); dateien = {}; n_ok = 0
    for k in T.get("korrekturen", []):
        par = k["parameter"]; pf = par["pfad"]
        if "|" in pf: print(f"UEBERSPRUNGEN (zusammengesetzter Parameter, Tor muss Einzelpfad liefern): {pf}"); continue
        d = os.path.join(ausdir, par["datei"]); J = dateien.setdefault(d, json.load(open(d)))
        if pf.startswith("fenster.je_licht") and "je_licht" not in J["fenster"]:   # je-Licht-Parameter anlegen (Formfamilie: je Licht eigener Riegel)
            F = J["fenster"]; F["je_licht"] = [{"z_kaempfer": F["z_kaempfer"], "z_sohl": F["z_sohl"], "z_scheitel": F["z_scheitel"]} for _ in range(F["n_licht"])]
        alt = setze(J, pf, k["wert"]); J.setdefault("tor_historie", []).append({"pfad": pf, "alt": alt, "neu": k["wert"], "quelle": k.get("quelle"), "begruendung": k.get("begruendung"), "tor": tor})
        print(f"  {par['datei']}:{pf}: {alt} -> {k['wert']} ({k.get('quelle')})"); n_ok += 1
    for d, J in dateien.items(): json.dump(J, open(d, "w"), indent=1)
    print(f"{n_ok} Korrekturen uebernommen; jetzt koerper_v11.py bauen")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "export": export(*a[1:5])
    elif a and a[0] == "zuruecklesen": zuruecklesen(a[1], a[2])
    else: print(__doc__); sys.exit(1)
