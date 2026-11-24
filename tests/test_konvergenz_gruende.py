#!/usr/bin/env python3
"""test_konvergenz_gruende.py - Rote Probe zu tools/konvergenz.py: None NUR mit benanntem Grund, Messfehler = Exit 4 "KONVERGENZ NICHT GEMESSEN".

Anlass Kette 1122zb (24.11.2026): konvergenz.jsonl hatte EINE Zeile, alle 20 Fotos und 24 Bauteile None, Stufe rc 3 = "kein Beleg (Datendecke -> Fotoauftrag)",
die Kette wertete das als in Ordnung. Ursache: Werkzeugfehler (foto_diff_batch 20/20 CUDA-OOM, teil_fotoform Pfad statt Name) - siehe tests/test_konvergenz_messfehler.py.
Geprueft (synthetisch, --lesen/--fein-json, kein Rechenlauf, < 10 s):
  1. ROT: alle Fotos mit OOM-Fehler in batch_ergebnis.json + teil_fotoform gescheitert -> Exit 4, Text "KONVERGENZ NICHT GEMESSEN", jede Seite fotos_grund
     mit MESSFEHLER, gemessen=False (vorher: rc 3, Status Datendecke, Gruende fehlten).
  2. Datendecke (Foto nicht beurteilbar, Kamera nicht belastbar) -> Exit 3, Grund DATENDECKE, kein Messfehler.
  3. Werte vorhanden -> Exit 0, fotos_grund leer; Wiederholung derselben Lauf-ID ersetzt die Zeile (Kette wiederholt die Stufe nach Speichermangel).
  4. Fotosatz bleibt ueber Laeufe gleich (kein Bruch); Messart grob wechselt -> Bruch aller Seiten mit bruch_grund; erster Lauf bruch_grund 'Reihe neu angelegt'.
  5. gruende_fein: belastbar/leer/teil_fotoform-Fehler/zu wenig Pixel.
Aufruf: CUDA_VISIBLE_DEVICES= /media/oem/scan/venv-seg/bin/python -I tests/test_konvergenz_gruende.py
Verwandt/Vorlaeufer: tools/test_konvergenz.py (Grundtest, gleiche Kamera-Nachbildung), tests/test_konvergenz_messfehler.py (Ursachen-Fix).
"""
import sys, os, json, io, contextlib, math
import numpy as np, cv2
T = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"); sys.path.insert(0, T)
from pfade import temp_ordner
import konvergenz as KV

F = []


def ok(b, t):
    print(("    ok    " if b else "    FEHLER ") + t)
    if not b: F.append(t)


def kam(C, ziel, f=1200.0, W=1500, H=1000):
    C = np.asarray(C, float); fw = np.asarray(ziel, float) - C; fw /= np.linalg.norm(fw)
    rt = np.cross(fw, [0, 0, 1.0]); rt /= np.linalg.norm(rt); dn = np.cross(fw, rt); R = np.vstack([rt, dn, fw]); t = -R @ C
    return dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=t.tolist(), f_px=f, cx=W / 2, cy=H / 2, bild=[W, H], rms_px=1.0, standort_xyz=C.tolist(), sfm_guete=dict(klasse="gut"))


R0 = temp_ordner("test_konvg_"); OD = os.path.join(R0, "modelle", "probe"); MP = os.path.join(OD, "messprotokoll"); AU = os.path.join(OD, "audit")
FD = os.path.join(R0, "daten", "probe", "fotos"); DA = os.path.join(R0, "daten_kette"); EIN = os.path.join(R0, "ein")
for d in (MP, AU, FD, os.path.join(DA, "fassade"), EIN): os.makedirs(d, exist_ok=True)
obj = dict(name="probe", stl="modelle/stl/fehlt.stl", stl_massstab=87, audit="modelle/probe/audit", fotos_dir="daten/probe/fotos",
           seiten_konvention={"+x": "Nord", "-x": "Sued", "+y": "West", "-y": "Ost"}, rahmen_wand=dict(u0=-5, u1=5, v0=-4, v1=4), hoehe_m=10.0)
OJ = os.path.join(OD, "objekt.json"); json.dump(obj, open(OJ, "w"))
rng = np.random.default_rng(0); MITTE = {"+x": [5, 0, 5], "-x": [-5, 0, 5], "+y": [0, 4, 5], "-y": [0, -4, 5]}; NORM = {"+x": [1, 0], "-x": [-1, 0], "+y": [0, 1], "-y": [0, -1]}
FOTOS = []
for ax in MITTE:
    m = np.array(MITTE[ax], float); n = np.array(NORM[ax] + [0], float); q = np.array([-n[1], n[0], 0.0])
    for nm, C in {"a": m + 30 * n, "b": m + 30 * n + 8 * q}.items():
        nr = f"{'p' if ax[0] == '+' else 'm'}{ax[1]}_{nm}"
        json.dump(dict(foto=nr, kamera=kam(C, m)), open(os.path.join(MP, f"K-{nr}.json"), "w"))
        cv2.imwrite(os.path.join(FD, nr + ".jpg"), (rng.random((150, 200)) * 255).astype(np.uint8)); FOTOS.append(nr)
json.dump(dict(fassaden=[dict(id="f00", o=[5, -4, 0], d=[0, 1, 0], n=[1, 0, 0])]), open(os.path.join(DA, "fassade", "fassaden.json"), "w"))
json.dump(dict(bauteile=[dict(name="uhr_f00", art="fassade", fassade="f00", u=[3, 5], z=[6, 8], ansichten=[dict(modus="front", foto="px_a", abstand_m=12.0)]),
                         dict(name="tor_f00", art="fassade", fassade="f00", u=[2, 6], z=[0, 4], ansichten=[dict(modus="front", foto="px_b", abstand_m=60.0)])]),
          open(os.path.join(AU, "neben_details.json"), "w"))


def eingabe(werte=None, oom=False, nicht_beurteilbar=()):
    for p in os.listdir(EIN): os.remove(os.path.join(EIN, p))
    if oom:
        json.dump(dict(ergebnisse={f"m|{nr}": dict(fehler="OutOfMemoryError: CUDA out of memory. Tried to allocate 32.00 MiB.") for nr in FOTOS}), open(os.path.join(EIN, "batch_ergebnis.json"), "w"))
        return
    for nr in FOTOS:
        v = (werte or {}).get(nr, 0.6)
        json.dump(dict(foto=nr, anteil_modellkanten_ohne_foto=round(1 - v, 4), anteil_fotokanten_ohne_modell=round(1 - v, 4), beurteilbar=nr not in nicht_beurteilbar,
                       modellkanten_px=0 if nr in nicht_beurteilbar else 900), open(os.path.join(EIN, f"foto_diff_{nr}.json"), "w"))


def lauf(lid, fein=None, extra=()):
    arg = [OJ, "--lauf", lid, "--lesen", EIN, "--daten", DA, "--ohne-wolke", "--ohne-formsitz", "--ohne-hoehe"] + list(extra)
    if fein is not None:
        p = os.path.join(R0, "tf.json")
        if fein == "fehlt":
            if os.path.exists(p): os.remove(p)
        else: json.dump(fein, open(p, "w"))
        arg += ["--fein-json", p]
    out = io.StringIO()
    with contextlib.redirect_stdout(out): rc = KV.main(arg)
    zl = open(os.path.join(AU, "konvergenz.jsonl")).read().splitlines()
    return rc, out.getvalue(), json.loads(zl[-1]), zl


TF_OK = {"teile": {"uhr_f00": {"px_a": {"f1_f": 0.5, "mkf_px": 900, "fkf_px": 900}}}}

print("1. ROT: Messfehler (1122zb nachgestellt) -> Exit 4, nie still 'Datendecke'")
eingabe(oom=True)
rc, txt, z, zl = lauf("L1", fein="fehlt")
ok(rc == 4, f"Exit 4 (war 1122zb: rc 3 = in Ordnung) - rc {rc}")
ok("KONVERGENZ NICHT GEMESSEN" in txt and "NICHT IN ORDNUNG" in txt, "Text meldet KONVERGENZ NICHT GEMESSEN - NICHT IN ORDNUNG")
ok(z["gemessen"] is False and z["messfehler"]["grob"] == len(FOTOS), f"Zeile: gemessen False, messfehler grob {z['messfehler']['grob']}/{len(FOTOS)}")
ok(all(e["status"] == KV.MESSFEHLER for g, e in z["seiten"].items() if g != "rund"), "jede Seite Status MESSFEHLER (nicht KEIN/Datendecke)")
ok(all(e["fotos_grund"] and all(q.startswith(KV.MF) and "OutOfMemory" in q for q in e["fotos_grund"].values()) for e in z["seiten"].values()),
   "jedes None-Foto hat einen Grund 'MESSFEHLER foto_diff: OutOfMemoryError ...'")
ok(all(e["bruch"] and e["bruch_grund"] == "Reihe neu angelegt" for e in z["seiten"].values()), "erster Lauf: Bruch mit Grund 'Reihe neu angelegt' (nicht stumm)")
ok(z["modus_grob"] == "raster", "Messart in der Zeile")
fn = (z["seiten"]["+x"].get("bauteile_fein_grund") or {})
ok(fn.get("uhr_f00", "").startswith(KV.MF) and fn.get("tor_f00", "").startswith(KV.DD), f"fein: fehlender Bericht = MESSFEHLER, ferne Kamera = DATENDECKE ({fn})")

print("2. Datendecke -> Exit 3, Grund DATENDECKE")
eingabe(nicht_beurteilbar=FOTOS)
rc, txt, z, zl = lauf("L2", fein={"teile": {}})
ok(rc == 3, f"Exit 3 (kein Beleg, kein Messfehler) - rc {rc}")
ok(z["gemessen"] is True and all(e["status"] == KV.KEIN for e in z["seiten"].values()), "Status 'kein Beleg (Datendecke)'")
ok(all(q.startswith(KV.DD) and "nicht beurteilbar" in q for e in z["seiten"].values() for q in e["fotos_grund"].values()), "Grund 'DATENDECKE nicht beurteilbar'")
ok(len(zl) == 2 and not any(e["bruch"] for e in z["seiten"].values()), "zweite Zeile, Fotosatz unveraendert (kein Bruch)")

print("3. Werte + Wiederholung derselben Lauf-ID")
eingabe({nr: 0.7 for nr in FOTOS})
rc, txt, z, zl = lauf("L3", fein=TF_OK)
ok(rc == 0 and all(e["f1"] is not None and not e["fotos_grund"] for e in z["seiten"].values()), f"Exit 0, Werte je Seite, fotos_grund leer (rc {rc})")
ok(z["seiten"]["+x"]["bauteile_fein"].get("uhr_f00") == 0.5 and "uhr_f00" not in z["seiten"]["+x"]["bauteile_fein_grund"], "fein: Wert ohne Grund")
rc, txt, z, zl = lauf("L3", fein=TF_OK)
ok(len(zl) == 3 and sum(1 for ln in zl if json.loads(ln)["lauf"] == "L3") == 1, f"Wiederholung L3 ersetzt ihre Zeile ({len(zl)} Zeilen)")

print("4. Messart-Wechsel = Bruch")
rc, txt, z, zl = lauf("L4", fein=TF_OK, extra=["--modus-grob", "punkt"])
ok(all(e["bruch"] and "Messart" in (e["bruch_grund"] or "") for e in z["seiten"].values()) and "MESSART GROB raster -> punkt" in txt, "raster -> punkt: Bruch aller Seiten, gemeldet")
ok(json.load(open(os.path.join(AU, "konvergenz_fotosatz.json")))["messart_grob"] == "punkt", "Messart im Fotosatz festgeschrieben")
rc, txt, z, zl = lauf("L5", fein=TF_OK)
ok(not any(e["bruch"] for e in z["seiten"].values()) and z["modus_grob"] == "punkt", "naechster Lauf ohne Angabe: Messart aus dem Fotosatz, kein Bruch")

print("5. gruende_fein")
bt = {"a": dict(kameras=[dict(foto="x", belastbar=True, aufloesung_m=0.03)]), "b": dict(kameras=[dict(foto="y", belastbar=False, aufloesung_m=0.12)]),
      "c": dict(kameras=[]), "d": dict(kameras=[dict(foto="x", belastbar=True, aufloesung_m=0.03)])}
tf = {"teile": {"a": {"x": {"f1_f": 0.4, "mkf_px": 900, "fkf_px": 900}}, "d": {"x": {"f1_f": 0.4, "mkf_px": 20, "fkf_px": 900}}}}
g = KV.gruende_fein(tf, bt, None, {"a", "b", "c", "d"})
ok("a" not in g and g["b"].startswith(KV.DD) and "12 cm" in g["b"] and g["c"].startswith(KV.DD) and "20/900" in g["d"], f"belastbar ohne Grund; fern / ohne Kamera / zu wenig Pixel benannt ({g})")
g = KV.gruende_fein(None, bt, "rc 1: FileNotFoundError", {"a", "b", "d"})
ok(g["a"].startswith(KV.MF) and "FileNotFoundError" in g["a"] and g["b"].startswith(KV.DD), "teil_fotoform-Fehler -> MESSFEHLER nur bei belastbaren Teilen")
g = KV.gruende_fein(tf, bt, None, {"b"})
ok("leer" in g["a"], "Teil im STL leer -> benannt")
print("ALLE OK" if not F else f"FEHLER: {len(F)}: {F}")
sys.exit(1 if F else 0)
