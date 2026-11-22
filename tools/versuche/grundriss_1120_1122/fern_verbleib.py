"""Wo sind die 10 Fernfotos (110741-111237) in 1122 geblieben? Fotoordner, fremd, Gemeinschaft, Seite, Teilmodell, DB-Paare."""
import os, json, sqlite3, shutil
D = "/media/oem/scan/rc-park_daten/schwabentor-1122"; OUT = os.path.dirname(os.path.abspath(__file__))
s = json.load(open(f"{D}/pipe/sfm/seiten.json")); fremd = set(s["fremd"]); gem = s["gemeinschaft"]
seite_von_gruppe = {g: i for i, e in enumerate(s["seiten"]) for g in e["gruppen"]}
fern = [f"eigen__IMG_20261106_{t}" for t in ("110741", "110743", "110749", "110754", "110756", "110801", "110802", "111235", "111235_2", "111237")]
fotos = set(os.listdir(f"{D}/fotos"))
sm = json.load(open(f"{D}/pipe/sfm/seiten_modelle.json"))
teil_listen = {}
for e in sm["teile"]:
    p = f"{D}/pipe/sfm/seiten_modelle/teil{e['teil']}.txt"
    if os.path.exists(p): teil_listen[e["teil"]] = set(open(p).read().split())
print("Gruppengroessen je Gemeinschaft:", s["groessen"][:12])
for f in fern:
    nm = [x for x in fotos if os.path.splitext(x)[0] == f]; n = nm[0] if nm else None; g = gem.get(n) if n else None
    print(f, "Foto:", bool(n), "fremd:", n in fremd, "Gemeinschaft:", g, "Seite:", seite_von_gruppe.get(g), "Teil-Listen:", [k for k, v in teil_listen.items() if n in v])
# Verbindungen der Gemeinschaft dieser Fotos
g0 = {gem.get(x) for x in fotos if os.path.splitext(x)[0] in fern}
print("Gemeinschaften der Fernfotos:", g0)
for v in s["verbindungen"]:
    if v["a"] in g0 or v["b"] in g0: print("  Verbindung", v["a"], v["b"], "paare", v["paare"], "geprueft", v["geprueft"], "p_median", v["p_median"], v["urteil"])
print("Seiten:", [(i, e["gruppen"], e["bilder"]) for i, e in enumerate(s["seiten"])][:10])
print("Meldungen sm:", [m for m in sm.get("meldungen", []) if "Teil" in m][:12])
