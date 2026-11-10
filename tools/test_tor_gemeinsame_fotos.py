"""Test Torluecke 3 (11.11.): Foto-Gewinn nur auf GEMEINSAMEN Fotos (bauteil_kreis.angleichen).
1) synthetisch: Nachher verliert ein schlechtes Foto -> scheinbarer Gewinn muss verschwinden; gleiche Saetze -> unveraendert.
2) Echtfall EG2 a205314 r2 (Pruefer verwarf +0,11 wegen anderem Fotosatz): Gewinn auf gemeinsamen Fotos muss < Tor 0,02 sein,
   sonst haette das Tor den Fall auch kuenftig durchgelassen. Aufruf: python3 tools/test_tor_gemeinsame_fotos.py  (Exit 0 = bestanden)"""
import ast, json, os, sys
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bauteil_kreis.py")
mod = ast.parse(open(SRC).read()); ns = {}
code = [n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name in ("f1_je", "angleichen")]
assert len(code) == 2, "f1_je/angleichen fehlen in bauteil_kreis.py"
exec(compile(ast.Module(body=code, type_ignores=[]), SRC, "exec"), ns); ns["JE"] = JE = {}
fehler = 0
def pruef(name, ok, info=""):
    global fehler; fehler += not ok; print(("OK    " if ok else "FALSCH"), name, info)
e = lambda p, r, m=100, f=100: dict(praez=p, recall=r, mk_px=m, fk_px=f)
# 1a: Nachher laesst das schlechte Foto C weg, A/B unveraendert -> echter Gewinn 0
JE["v"] = {"A": e(.8, .8), "B": e(.7, .7), "C": e(.2, .2)}; JE["n"] = {"A": e(.8, .8), "B": e(.7, .7)}
fv, fn = ns["f1_je"](JE["v"], list(JE["v"])), ns["f1_je"](JE["n"], list(JE["n"]))
va, na = ns["angleichen"]("v", "n", fv, fn, "synth")
pruef("synth Fotosatz kleiner: Scheingewinn weg", na - va < 0.005 and fn - fv > 0.1, f"roh {fv}->{fn}, gemeinsam {va}->{na}")
# 1b: gleiche Saetze -> unveraendert
JE["n2"] = {"A": e(.9, .9), "B": e(.8, .8), "C": e(.3, .3)}
r = ns["angleichen"]("v", "n2", 0.5, 0.6, "synth"); pruef("synth gleiche Fotos: unveraendert", r == (0.5, 0.6), str(r))
# 1c: kein gemeinsames Foto -> nachher None
JE["n3"] = {"D": e(.9, .9)}; r = ns["angleichen"]("v", "n3", 0.5, 0.9, "synth"); pruef("synth kein gemeinsames Foto: nachher None", r[1] is None, str(r))
# 2: Echtfall EG2
L = "/media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261110_205314a205314"; FL = "/media/oem/scan/rc-park_kreis/kaufhaus_grob3/fotoform/463a982812579942_v2_wolkenverdeckung_festbereich.json"
if os.path.exists(os.path.join(L, "fotoform_r2_vorpruef.json")) and os.path.exists(FL):
    t = "fensterreihe__eg2"; fl = json.load(open(FL))["teile"][t]
    nach = {k: v for k, v in json.load(open(os.path.join(L, "fotoform_r2_vorpruef.json")))["teile"][t].items() if k != "_gesamt" and "mk_px" in v}
    fotos = [l.split()[1].rstrip(":") for l in open(os.path.join(L, "fotoform_r2_vorpruef.log")) if l.startswith("Foto ")]   # Fotosatz der Runde (aus dem Messlog)
    JE["ev"] = {f: fl[f] for f in fotos}; JE["en"] = nach
    fv, fn = ns["f1_je"](JE["ev"], fotos), ns["f1_je"](nach, list(nach))
    va, na = ns["angleichen"]("ev", "en", fv, fn, "EG2")
    pruef("Echtfall EG2: roh etwa wie im Log (0,658 -> 0,768; Formliste seither nachgerechnet, Toleranz 0,02)", abs(fv - 0.658) < 0.02 and abs(fn - 0.768) < 0.01, f"{fv} -> {fn}")
    pruef("Echtfall EG2: gemeinsam unter Tor (+0,02)", na is None or na < va + 0.02, f"{va} -> {na}")
else: print("HINWEIS Echtfall-Daten fehlen, nur synthetisch")
print("BESTANDEN" if not fehler else f"{fehler} FEHLER"); sys.exit(1 if fehler else 0)
