#!/usr/bin/env python3
"""test_konvergenz.py - synthetische Pruefung von tools/konvergenz.py (24.11.2026, Nutzer: "Augenmass ist doof").

Nachgebaut: Objekt 10 x 8 m, 10 m hoch, seiten_konvention absichtlich UNGEWOEHNLICH (+x = Sued ...) -> Namen muessen aus objekt.json kommen, nicht aus
einer Kompassrechnung. Je Seite 3 senkrechte Kameras (eine davon Dublette: 1 m daneben, gleicher Blick) + 1 Eckblick 45 Grad (fuer beide Waende zu schraeg, darf nicht gewaehlt werden).
Geprueft: Fotosatz fest (zweiter Lauf gleich, kein Bruch), Ersetzen bei verschwundener K-Datei (nur diese Seite Bruch, gemeldet), F1 = 2PR/(P+R),
"kein Beleg" statt 0, Status steigt / PLATEAU (mit Restfehler-Ort) / faellt / Reihe zu kurz, gepaarter Gewinn (fehlendes Foto taeuscht keinen Gewinn vor),
feines F1 je Bauteil (eingefroren, ferne Kamera nicht belastbar, PLATEAU nur wenn grob UND fein flach), Kurvenbild, das Wort "konvergiert" kommt nicht vor.
Kein Rechenlauf (--lesen/--fein-json), < 10 s. Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/test_konvergenz.py
"""
import sys, os, json, io, contextlib, math
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfade import temp_ordner
import konvergenz as KV

F = 0


def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text)
    if not ok: F += 1


def kam(C, ziel, f=1200.0, W=1500, H=1000):
    C = np.asarray(C, float); fw = np.asarray(ziel, float) - C; fw /= np.linalg.norm(fw)
    rt = np.cross(fw, [0, 0, 1.0]); rt /= np.linalg.norm(rt); dn = np.cross(fw, rt); R = np.vstack([rt, dn, fw]); t = -R @ C
    return dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=t.tolist(), f_px=f, cx=W / 2, cy=H / 2, bild=[W, H], rms_px=1.0, standort_xyz=C.tolist(),
                sfm_guete=dict(klasse="gut"))


R0 = temp_ordner("test_konv_"); OD = os.path.join(R0, "modelle", "probe"); MP = os.path.join(OD, "messprotokoll"); AU = os.path.join(OD, "audit")
FD = os.path.join(R0, "daten", "probe", "fotos"); DA = os.path.join(R0, "daten_kette"); EIN = os.path.join(R0, "ein")
for d in (MP, AU, FD, os.path.join(DA, "fassade"), EIN): os.makedirs(d, exist_ok=True)
SK = {"+x": "Sued", "-x": "Nord", "+y": "Ost", "-y": "West", "quelle": "Test: absichtlich nicht Kompass"}
obj = dict(name="probe", stl="modelle/stl/fehlt.stl", stl_massstab=87, masstabelle="modelle/probe/masstabelle.json", audit="modelle/probe/audit",
           fotos_dir="daten/probe/fotos", seiten_konvention=SK, rahmen_wand=dict(u0=-5, u1=5, v0=-4, v1=4), hoehe_m=10.0)
OJ = os.path.join(OD, "objekt.json"); json.dump(obj, open(OJ, "w"))
rng = np.random.default_rng(0); MITTE = {"+x": [5, 0, 5], "-x": [-5, 0, 5], "+y": [0, 4, 5], "-y": [0, -4, 5]}; NORM = {"+x": [1, 0], "-x": [-1, 0], "+y": [0, 1], "-y": [0, -1]}
FOTOS = {}
for ax in MITTE:
    m = np.array(MITTE[ax], float); n = np.array(NORM[ax] + [0], float); q = np.array([-n[1], n[0], 0.0])
    lage = {"a": m + 30 * n, "b": m + 30 * n + 8 * q, "c": m + 30 * n - 8 * q, "dub": m + 30 * n + 1.0 * q,
            "schraeg": m + 30 * (math.cos(math.radians(45)) * n + math.sin(math.radians(45)) * q)}
    for nm, C in lage.items():
        nr = f"{ax[0] == '+' and 'p' or 'm'}{ax[1]}_{nm}"; ziel = m + (1.0 * q if nm == "dub" else 0)
        json.dump(dict(foto=nr, kamera=kam(C, ziel)), open(os.path.join(MP, f"K-{nr}.json"), "w"))
        sch = 255 if nm != "c" else 60                          # 'c' unschaerfer (Kontrast klein)
        cv2.imwrite(os.path.join(FD, nr + ".jpg"), (rng.random((150, 200)) * sch).astype(np.uint8)); FOTOS.setdefault(ax, []).append(nr)


def fd(nr, rot, gelb, ok=True, treffer=()):
    json.dump(dict(foto=nr, anteil_modellkanten_ohne_foto=rot, anteil_fotokanten_ohne_modell=gelb, beurteilbar=ok, treffer=list(treffer)), open(os.path.join(EIN, f"foto_diff_{nr}.json"), "w"))


def lauf(lid, werte, fein=None, kein=()):
    """werte {achse: F1-Ziel}: rot = gelb = 1 - F1 (dann F1 = Ziel); kein = Achsen ohne beurteilbares Foto."""
    for ax, fl in FOTOS.items():
        for nr in fl:
            v = werte.get(ax, 0.5); fd(nr, round(1 - v, 4), round(1 - v, 4), ok=ax not in kein,
                                        treffer=[dict(art="FEHLT (Fotokante ohne Modellkante)", laenge_m=50.0, xyz=[5.0, 0.0, 8.0]),
                                                 dict(art="FALSCH/ERFUNDEN (Modellkante ohne Fotokante)", laenge_m=10.0, xyz=[5.0, 3.5, 2.0])])
    arg = [OJ, "--lauf", lid, "--lesen", EIN, "--daten", DA]
    if fein is not None: json.dump(fein, open(os.path.join(EIN, "tf.json"), "w")); arg += ["--fein-json", os.path.join(EIN, "tf.json")]
    out = io.StringIO()
    with contextlib.redirect_stdout(out): rc = KV.main(arg)
    return rc, out.getvalue(), json.loads(open(os.path.join(AU, "konvergenz.jsonl")).read().splitlines()[-1])


print("1. Seiten und Fotosatz")
W_ = KV.waende(obj)
pruef([W_[a]["name"] for a in ("+x", "-x", "+y", "-y")] == ["Sued", "Nord", "Ost", "West"], "Seitennamen aus seiten_konvention (+x = Sued), keine Kompassrechnung")
# Bauteile fuer das Feinmass: Fassade f00 mit Normale +x (-> Sued), Kamera px_a nah (belastbar), mx_a fern (60 m x 1 px x 2 / 1200 = 10 cm -> nicht belastbar)
json.dump(dict(fassaden=[dict(id="f00", o=[5, -4, 0], d=[0, 1, 0], n=[1, 0, 0])]), open(os.path.join(DA, "fassade", "fassaden.json"), "w"))
json.dump(dict(bauteile=[dict(name="uhr_f00", art="fassade", fassade="f00", u=[3, 5], z=[6, 8], w=[-0.3, 0.3], ansichten=[dict(modus="front", foto="px_a", abstand_m=12.0)]),
                         dict(name="tor_f00", art="fassade", fassade="f00", u=[2, 6], z=[0, 4], w=[-0.3, 0.3], ansichten=[dict(modus="front", foto="px_b", abstand_m=60.0)])]),
          open(os.path.join(AU, "neben_details.json"), "w"))
TF = lambda v: {"teile": {"uhr_f00": {"px_a": {"f1_f": v, "mkf_px": 900, "fkf_px": 900, "gelb": []}}, "tor_f00": {"px_b": {"f1_f": 0.9, "mkf_px": 900, "fkf_px": 900}}}}
rc, txt, z1 = lauf("L1", {"+x": 0.50, "-x": 0.50, "+y": 0.60, "-y": 0.60}, fein=TF(0.40))
S1 = json.load(open(os.path.join(AU, "konvergenz_fotosatz.json")))
pruef(rc == 0, f"rc 0 (rc {rc})")
for ax, s in S1["seiten"].items():
    pruef(len(s["fotos"]) == 3 and not any("schraeg" in f for f in s["fotos"]), f"{s['name']}: 3 Fotos, kein Eckblick 45 Grad ({s['fotos']})")
    pruef(sum(1 for f in s["fotos"] if f.endswith("_a") or f.endswith("_dub")) == 1, f"{s['name']}: Dublette (1 m daneben, gleicher Blick) nicht doppelt")
bt = S1.get("bauteile") or {}
pruef(bt.get("uhr_f00", {}).get("seite") == "Sued" and bt["uhr_f00"]["kameras"][0]["belastbar"], "Bauteil an Fassade mit Normale +x -> Seite 'Sued', nahe Kamera belastbar")
pruef(bt.get("tor_f00", {}).get("kameras") and not bt["tor_f00"]["kameras"][0]["belastbar"], f"ferne Kamera (2 x 1 px x 60 m / 1200 = 10 cm > 5 cm) NICHT belastbar ({bt.get('tor_f00')})")
pruef(abs(z1["seiten"]["+x"]["f1"] - 0.5) < 1e-6 and z1["seiten"]["+x"]["n"] == 3, "F1 = Median je Seite, n = 3")
pruef(z1["seiten"]["+x"]["f1_fein"] == 0.4 and z1["seiten"]["+x"]["bauteile_fein"].get("tor_f00") is None, "fein: nur belastbare Kamera zaehlt (tor_f00 ohne Wert, nicht 0,9)")
pruef(all(e["status"] == KV.KURZ for e in z1["seiten"].values()) and all(e["bruch"] for e in z1["seiten"].values()), "Lauf 1: Reihe zu kurz, Reihenanfang als Bruch")

print("2. F1-Rechnung und kein Beleg")
pruef(abs(KV.f1_foto(dict(anteil_modellkanten_ohne_foto=0.2, anteil_fotokanten_ohne_modell=0.4)) - 2 * 0.8 * 0.6 / 1.4) < 1e-9, "F1 = 2PR/(P+R) mit P = 1-rot, R = 1-gelb")
pruef(KV.f1_foto(dict(anteil_modellkanten_ohne_foto=0.2, anteil_fotokanten_ohne_modell=0.4, beurteilbar=False)) is None, "nicht beurteilbar -> None")
rc, txt, z2 = lauf("L2", {"+x": 0.60, "-x": 0.60, "+y": 0.61, "-y": 0.60}, fein=TF(0.55), kein=("-y",))
S2 = json.load(open(os.path.join(AU, "konvergenz_fotosatz.json")))
pruef({a: s["fotos"] for a, s in S2["seiten"].items()} == {a: s["fotos"] for a, s in S1["seiten"].items()} and not S2["ersetzungen"], "Lauf 2: Fotosatz unveraendert, keine Ersetzung")
pruef(z2["seiten"]["-y"]["f1"] is None and z2["seiten"]["-y"]["status"] == KV.KEIN, f"Seite ohne beurteilbares Foto: f1 None + '{KV.KEIN}' (nicht 0)")
pruef(not any(e["bruch"] for e in z2["seiten"].values()), "Lauf 2: kein Bruch")

print("3. Status steigt / PLATEAU / faellt")
rc, txt, z3 = lauf("L3", {"+x": 0.61, "-x": 0.70, "+y": 0.50, "-y": 0.60}, fein=TF(0.555))
e = z3["seiten"]
pruef(e["-x"]["status"] == KV.STEIGT, f"Nord 0,50 -> 0,60 -> 0,70: steigt ({e['-x']['status']})")
pruef(e["+y"]["status"] == KV.FAELLT, f"Ost 0,60 -> 0,61 -> 0,50: faellt ({e['+y']['status']})")
pruef(e["+x"]["status_grob"] == KV.STEIGT, "Sued grob 0,50 -> 0,60 -> 0,61: erster Gewinn 10 pp -> noch steigt")
rc, txt, z4 = lauf("L4", {"+x": 0.615, "-x": 0.75, "+y": 0.50, "-y": 0.60}, fein=TF(0.56))
e = z4["seiten"]["+x"]
pruef(e["status"] == KV.PLATEAU, f"Sued grob +1/+0,5 pp und fein +0,5/+0,5 pp: {KV.PLATEAU} ({e['status']})")
rf = e.get("restfehler") or {}
pruef(rf.get("grob") and rf["grob"][0]["ort"] == "uhr_f00" and rf["grob"][0]["art"] == "FEHLT", f"PLATEAU nennt den Restfehler-Ort: groesster FEHLT-Treffer im Bauteil uhr_f00 ({rf.get('grob')})")
pruef(rf.get("fein") and rf["fein"][0]["bauteil"] == "uhr_f00" and "tor_f00" in rf.get("fein_nicht_belastbar", []), "PLATEAU: Fein-Defizit je Bauteil + nicht belastbare Bauteile (Fotoauftrag)")
pruef("konvergiert" not in txt.lower() and "konvergiert" not in json.dumps(z4).lower(), "das Wort 'konvergiert' kommt in Text und Zeile nicht vor")
# grob flach, fein steigt -> nicht PLATEAU
pruef(KV.status_seite(KV.PLATEAU, KV.STEIGT) == KV.STEIGT and KV.status_seite(KV.PLATEAU, KV.KEIN) == KV.PLATEAU, "PLATEAU nur, wenn grob UND fein flach (fein ohne Beleg zaehlt nicht dagegen)")

print("4. Gepaarter Gewinn")
a = (0.60, {"p": 0.40, "q": 0.60, "r": 0.80}); b = (0.70, {"p": 0.40, "q": 0.60, "r": None})
pruef(abs(KV.gewinn(a, b)) < 1e-9, "Foto r faellt aus: Median springt 0,60 -> 0,50, gepaarter Gewinn bleibt 0")
pruef(abs(KV.gewinn(0.5, 0.6) - 0.1) < 1e-9, "ohne Einzelwerte: Differenz der Mediane")

print("5. Ersetzen + Bruch")
weg = S2["seiten"]["+x"]["fotos"][0]; os.remove(os.path.join(MP, f"K-{weg}.json"))
rc, txt, z5 = lauf("L5", {"+x": 0.62, "-x": 0.76, "+y": 0.50, "-y": 0.60}, fein=TF(0.56))
S5 = json.load(open(os.path.join(AU, "konvergenz_fotosatz.json")))
pruef(weg not in S5["seiten"]["+x"]["fotos"] and len(S5["seiten"]["+x"]["fotos"]) == 3 and S5["ersetzungen"] and "FOTOSATZ ERSETZT" in txt, f"verschwundene K-Datei {weg}: ersetzt und gemeldet")
pruef(z5["seiten"]["+x"]["bruch"] and not z5["seiten"]["-x"]["bruch"], "nur die betroffene Seite ist Bruch")
pruef(z5["seiten"]["+x"]["status_grob"] == KV.KURZ, "nach dem Bruch beginnt die Reihe neu (Reihe zu kurz)")
pruef({a: s["fotos"] for a, s in S5["seiten"].items() if a != "+x"} == {a: s["fotos"] for a, s in S1["seiten"].items() if a != "+x"}, "andere Seiten unveraendert")

print("6. Streuung gleicher Stand + Bild")
Zs = [dict(stl_sha="A", seiten={"s": dict(f1=0.50, fotos={"p": 0.50})}), dict(stl_sha="A", seiten={"s": dict(f1=0.53, fotos={"p": 0.53})})]
pruef(abs(KV.streuung(Zs, "s") - 0.03) < 1e-9, "gleicher STL zweimal gemessen -> Streuung 3 pp (Schwelle wird max(2 pp, 6 pp))")
pruef(os.path.getsize(os.path.join(AU, "konvergenz.png")) > 1000, "audit/konvergenz.png geschrieben")

print("7. Bauteil-STL aus dem End-STL ausschneiden")
def dreieck(p): return [p, [p[0], p[1] + 0.2, p[2]], [p[0], p[1], p[2] + 0.2]]
Tm = np.array([dreieck([5.0, 0.5, 7.0]), dreieck([5.0, 0.6, 7.2]), dreieck([5.0, -3.0, 2.0])]) / 0.087   # zwei in der Uhr (u 4,5 / z 7), eins weit weg; STL in mm H0
A = np.zeros(len(Tm), dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])); A["v"] = Tm
stlp = os.path.join(R0, "ende.stl"); open(stlp, "wb").write(b"\0" * 80 + np.uint32(len(Tm)).tobytes() + A.tobytes())
td = os.path.join(R0, "teile"); os.makedirs(td)
n = KV.teile_schreiben(stlp, obj, {"uhr_f00": bt["uhr_f00"]}, td)
import neben_details as ND
Tt = ND.stl_laden(os.path.join(td, "uhr_f00.stl"), 1.0) if n else np.zeros((0, 3, 3))
pruef(n == 1 and len(Tt) == 2 and np.allclose(Tt[0], Tm[0], atol=1e-3), f"Bauteil-STL: genau die 2 Dreiecke im eingefrorenen Kasten, STL-Einheit erhalten ({len(Tt)})")

print(f"{F} Fehler")
sys.exit(1 if F else 0)
