#!/usr/bin/env python3
"""test_bildwert.py - Beweise S7 (Minimalform 2026-11-06): T1 synthetische Luecke (Kaufhaus), T4 Martinstor Bedarf (Sued groesster, ohne Handwert).
T2/T3 entfallen (Budget). Ausgabe nur unter /media/oem/scan/rc-park_null/test_bildwert/.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_bildwert.py [t1|t4]
"""
import os, sys, json, copy, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bildwert as B
ROOT = B.ROOT; T = "/media/oem/scan/rc-park_null/test_bildwert"; RF = "/media/oem/scan/rc-park_null/s3_phase_a/restfeld_v1"; FK = "/media/oem/scan/rc-park_null/s3_phase_a/lauf_d/fehlerkarte_k0"


def t1():
    objp = os.path.join(ROOT, "modelle/kaufhaus_null5/objekt.json"); obj = json.load(open(objp)); par = B.standard_parameter(); cams, _ = B.kameras_laden(objp, obj)
    stl = json.load(open(RF + "/restfeld.json"))["parameter"]["stl"]; S = B.szene_aus_restfeld(RF, FK, par); V = B.Verdecker(stl, obj["stl_massstab"], obj)
    nk, Vis, namen = B.n_kam_berechnen(S, cams, V, par)
    anteil = {s: float((nk[S.seite == s] >= 3).mean()) for s in B.SEITEN if (S.seite == s).any()}; print("n_kam>=3 je Seite (mit Nachbar-Verdeckern):", {k: round(v, 3) for k, v in anteil.items()})
    # ABWEICHUNG von Spec 6 (ehrlich): im Kaufhaus-Netz stehen ALLE 94 Kameras im Norden (Ost/West/Sued sind echte Luecken), es gibt keine Ostkameras zum Entfernen.
    # Ersatz: echte Luecke Ost (n_kam>=3 = anteil['Ost']); Kandidaten = 8 virtuelle Ostkameras (x 14..22 m, y -8..8 m, z 1,6 m, Blick auf die Mitte; f = 1300 px bei 1600x1200, ANNAHME) + 10 Dubletten.
    luecke = "Ost"; ost = S.seite == luecke; a0 = a1 = anteil[luecke]; rest = cams; nkr, Visr, namr = nk, Vis, namen; kands = []
    for j, (x, y) in enumerate(zip(np.linspace(14, 22, 8), np.linspace(-8, 8, 8))):
        C = np.array([x, y, 1.6]); pz = B.pose_blick(C, np.array([-x, -y]), 1300.0, 1600, 1200, nick_deg=15.0); kands.append(dict(id=f"ost_v{j}", quelle="ostkamera", pose=pz, seite_hint=luecke))
    gedeckt = [n for i, n in enumerate(namr) if Visr[i].sum() > 0 and not (Visr[i] & (nkr < 3) & (S.A > 0)).any()]                    # Dublette nur von Kameras, die ausschliesslich bereits gedeckte Zellen sehen
    front = sorted(gedeckt, key=lambda n: -Visr[namr.index(n)].sum())[:10]; print("gedeckte Kameras fuer Dubletten:", len(gedeckt))
    for n in front:
        c = copy.deepcopy(rest[n]); C = B.zentrum(c); C2 = C + 0.3 * c["R"][0]; kands.append(dict(id="dub_" + n, quelle="frontdublette", pose=dict(R=c["R"], t=-c["R"] @ C2, f=c["f"], cx=c["cx"], cy=c["cy"], W=c["W"], H=c["H"]), seite_hint="gedeckt"))
    k, gew, nk0, nk1 = B.bewerten(S, rest, V, kands, par)
    ow = [x for x in k if x["quelle"] == "ostkamera"]; dw = [x for x in k if x["quelle"] == "frontdublette"]
    kein_dub = not any(x["id"] in gew for x in dw); dub_max = max(x["wert_vorher"] for x in dw); ost_min = min(x["wert_vorher"] for x in ow); sel_ost = [i for i in gew if i.startswith("ost_")]
    a2 = float((nk1[ost] >= 3).mean())
    erg = dict(ostkameras=8, ost_anteil_vorher=a0, ost_anteil_ohne=a1, ost_anteil_nach_auswahl=a2, gewaehlt=gew, dubletten_wert_max=dub_max, ostkamera_wert_min=ost_min,
               bedingungen=dict(vorbedingung_luecke=a0 < 0.5, keine_dublette_gewaehlt=kein_dub, dubletten_unter_min_wert=dub_max < par["min_wert_m2"], ost_vor_dubletten=max(x["wert_vorher"] for x in ow) > dub_max and len(sel_ost) >= 3, luecke_geschlossen=a2 > a1))
    json.dump(erg, open(f"{T}/t1.json", "w"), indent=1); print(json.dumps(erg, indent=1)); return all(erg["bedingungen"].values())


def t4():
    objp = os.path.join(ROOT, "modelle/martinstor/objekt.json"); obj = json.load(open(objp)); par = B.standard_parameter(); cams, info = B.kameras_laden(objp, obj)
    S = B.szene_aus_stl(os.path.join(ROOT, obj["stl"]), obj["stl_massstab"], par); V = B.Verdecker(os.path.join(ROOT, obj["stl"]), obj["stl_massstab"])
    nk, Vis, namen = B.n_kam_berechnen(S, cams, V, par); Tb = B.bedarf_tabelle(S, nk, par); print(f"Martinstor: {len(cams)} Kameras {info}")
    for s in B.SEITEN: print(s, Tb[s]["flaeche_m2"], Tb[s]["anteil_nk_ge3"], Tb[s]["bedarf_m2"])
    gr = max(B.SEITEN, key=lambda s: Tb[s]["bedarf_m2"]); json.dump(dict(tabelle=Tb, groesster=gr, kameras=len(cams)), open(f"{T}/t4.json", "w"), indent=1); print("groesster Bedarf:", gr); return gr == "Sued"


if __name__ == "__main__":
    os.makedirs(T, exist_ok=True); w = sys.argv[1:] or ["t1", "t4"]; ok = {x: globals()[x]() for x in w}; print(ok); sys.exit(0 if all(ok.values()) else 1)
