#!/usr/bin/env python3
"""test_hoehensitz.py - synthetische Pruefung von tools/hoehensitz.py (hoehensensitives Formmass, 24.11.2026) und seines Einbaus in tools/konvergenz.py.

Nachgebaut: Turm 10 x 8 x 20 m, zwei umlaufende Gesimse (z 6 und 13, je 0,4 m hoch, 0,4 m Ausladung, aus vier Balken je Seite), Traufplatte bei 20 m
(0,3 m dick, 0,6 m Ueberstand) mit Dachaufsatz, Sohlbaenke (0,15 m) an +x bei z 3; seiten_konvention absichtlich ungewoehnlich (+x = Sued, -y = West).
Wolke = Abtastung der WAHREN Form (2 cm Rauschen) + Bodenschicht + Fremdhaufen.
  E  Modell = Wahrheit                         -> trennt, hoehensitz hoch, med|dz| klein, alle vier Seiten
  NULLPROBE (--probe): Modell +-0,3 / 1 / 2 m in z -> deutlich schlechter (der Formsitz sah davon <= 0,005)
  ROT (--rot): je Seite die staerkste Linie 0,5 m angehoben -> erkannt auf DIESER Seite, Linie 'Modell zu hoch' gemeldet
  R  echtes STL, nur das +x-Gesims bei 13 m sitzt bei 13,5 m -> Sued faellt, die anderen kaum; Fehlerliste Sued: z ~13,5, dz ~ -0,5 'Modell zu hoch'
  X  Wolke mit 0,6 m Rauschen -> "nicht trennbar", NIE ein Urteil
  dazu: Linienfinder auf Kunstprofilen (Sprung -> Linie an richtiger Hoehe/Vorzeichen; gleichmaessige Dachneigung -> keine Linie),
  Einbau konvergenz.py (--lesen hoehensitz.json: Felder + status_hoehe; faellt die Hoehe, faellt die Seite).
Nur CPU, ~1 min. Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_hoehensitz.py
"""
import sys, os, json, io, contextlib, shutil
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfade import temp_ordner
import hoehensitz as HS

F = 0


def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text)
    if not ok: F += 1


W, H, FPX = 1200, 900, 1000.0


def kam(C, ziel):
    C = np.asarray(C, float); fw = np.asarray(ziel, float) - C; fw /= np.linalg.norm(fw)
    rt = np.cross(fw, [0, 0, 1.0]); rt /= np.linalg.norm(rt); dn = np.cross(fw, rt); R = np.vstack([rt, dn, fw]); t = -R @ C
    return dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=t.tolist(), f_px=FPX, cx=W / 2, cy=H / 2, bild=[W, H], rms_px=1.0, k1=0.0,
                standort_xyz=C.tolist(), rahmen_verschiebung=[0.0, 0.0, 0.0], sfm_guete=dict(klasse="gut"))


def box(ext, mitte):
    b = trimesh.creation.box(extents=ext); b.apply_translation(mitte); return b


def turm(gesims_px_z13=13.0):
    """Wahre Form; gesims_px_z13 = Hoehe (Unterkante) des +x-Balkens des oberen Gesimses (Rot: 13,5)."""
    teile = [box([10, 8, 20], [0, 0, 10]), box([11.2, 9.2, 0.3], [0, 0, 20.15]), box([6, 5, 4], [0, 0, 22.3])]
    for zu in (6.0, 13.0):
        teile += [box([0.4, 8.8, 0.4], [5.2, 0, (gesims_px_z13 if zu == 13.0 else zu) + 0.2]), box([0.4, 8.8, 0.4], [-5.2, 0, zu + 0.2]),
                  box([10.0, 0.4, 0.4], [0, 4.2, zu + 0.2]), box([10.0, 0.4, 0.4], [0, -4.2, zu + 0.2])]
    teile += [box([0.15, 1.5, 0.12], [5.075, y, 3.06]) for y in (-2.0, 2.0)]
    return trimesh.util.concatenate(teile)


def stl(m, pfad):
    mm = m.copy(); mm.apply_scale(1000.0 / 87); mm.export(pfad)


def main():
    print("test_hoehensitz:")
    # --- 1. Regeln / Linienfinder ohne Objekt
    pruef(abs(HS.guete(0.75, 0.5) - 0.5) < 1e-9 and HS.guete(0.5, None) is None, "guete = (S - S_null) / (1 - S_null)")
    nv = HS.null_varianten()
    pruef(len(nv) == 4 and all(d[0] == 0 and d[1] == 0 for d in nv) and sorted(abs(d[2]) for d in nv) == [1.3, 1.3, 2.1, 2.1], "Nullvarianten: Modell 1,3 / 2,1 m in +-z")
    nz = 400; zz = np.arange(nz) * HS.DZ_M
    r = np.zeros((3, nz), np.float32); r[0, zz >= 7.0] = 0.4; r[0, zz >= 7.4] = 0.0                       # Gesims 7,0..7,4 m (0,4 m Ausladung)
    r[1] = -0.6 * np.clip(zz - 5.0, 0, None)                                                               # gleichmaessig geneigt ab 5 m (Dach)
    r[2, zz >= 12.0] = -0.3                                                                                 # Ruecksprung bei 12 m
    L = HS.linien(r, np.ones_like(r, bool)); zl = lambda s, sg: [round(q[1] * HS.DZ_M, 2) for q in L if q[0] == s and q[2] == sg]
    pruef(any(abs(z - 7.0) <= 0.06 for z in zl(0, 1)) and any(abs(z - 7.4) <= 0.06 for z in zl(0, -1)) and len([q for q in L if q[0] == 0]) == 2,
          f"Linienfinder: Gesims-Unterkante 7,0 (+) und -Oberkante 7,4 (-) ({zl(0, 1)}, {zl(0, -1)})")
    pruef(len([q for q in L if q[0] == 1 and abs(q[1] * HS.DZ_M - 5.0) > 0.6]) == 0, f"gleichmaessige Neigung -> keine Linie ausser am Knick 5 m ({[q[1] * HS.DZ_M for q in L if q[0] == 1]})")
    pruef(any(abs(z - 12.0) <= 0.06 for z in zl(2, -1)), f"Ruecksprung 12 m -> Linie mit Vorzeichen - ({zl(2, -1)})")

    # --- 2. Synthetisches Objekt
    R0 = temp_ordner("test_hoehensitz_"); OD = os.path.join(R0, "modelle", "probe"); MP = os.path.join(OD, "messprotokoll")
    for d in (MP, os.path.join(OD, "sfm"), os.path.join(R0, "modelle", "stl"), os.path.join(R0, "daten", "probe", "fotos")): os.makedirs(d, exist_ok=True)
    SK = {"+x": "Sued", "-x": "Nord", "+y": "Ost", "-y": "West", "quelle": "Test"}
    obj = dict(name="probe", stl="modelle/stl/probe.stl", stl_massstab=87, stl_einheit_mm=True, zentrierung="achse", audit="modelle/probe/audit",
               fotos_dir="daten/probe/fotos", seiten_konvention=SK, rahmen_wand=dict(u0=-5, u1=5, v0=-4, v1=4), hoehe_m=24.3)
    OJ = os.path.join(OD, "objekt.json"); json.dump(obj, open(OJ, "w"))
    wahr = turm(); rot = turm(13.5)
    stl_w = os.path.join(R0, "modelle", "stl", "probe.stl"); stl_r = os.path.join(R0, "modelle", "stl", "probe_rot.stl"); stl(wahr, stl_w); stl(rot, stl_r)
    S = dict(k=1, seiten={}, ersetzungen=[])
    for ax, C in {"+x": [30.0, 0, 8], "-x": [-30.0, 0, 8], "+y": [0, 30.0, 8], "-y": [0, -30.0, 8]}.items():
        nr = f"k{ax[1]}{'p' if ax[0] == '+' else 'm'}"; json.dump(dict(foto=nr, kamera=kam(C, [0, 0, 8.0])), open(os.path.join(MP, f"K-{nr}.json"), "w"))
        S["seiten"][ax] = dict(name=SK[ax], fotos=[nr])
    sp = os.path.join(R0, "fotosatz.json"); json.dump(S, open(sp, "w"))
    Pw = np.asarray(trimesh.sample.sample_surface(wahr, 2000000, seed=5)[0]) + np.random.default_rng(6).normal(0, 0.02, (2000000, 3))
    boden = np.c_[np.random.default_rng(7).uniform(-15, 15, (200000, 2)), np.random.default_rng(8).normal(0, 0.02, 200000)]
    fremd = np.random.default_rng(9).uniform([40, 40, 0], [50, 50, 10], (50000, 3))
    np.save(os.path.join(OD, "sfm", "punkte_modell_probe.npy"), np.vstack([Pw, boden, fremd]).astype(np.float32))
    wp_x = os.path.join(R0, "wolke_rauschen.npy"); np.save(wp_x, (Pw + np.random.default_rng(11).normal(0, 0.6, Pw.shape)).astype(np.float32))

    def lauf(name, extra):
        jp = os.path.join(R0, name + ".json"); buf = io.StringIO()
        with contextlib.redirect_stdout(buf): rc = HS.main([OJ, "--fotosatz", sp, "--json", jp, "--n-modell", "2000000", "--n-wolke", "2000000"] + extra)
        e = json.load(open(jp)) if rc == 0 and os.path.exists(jp) else {}
        for ax, s in (e.get("seiten") or {}).items():
            print(f"      {name} {s['name']}: hoehensitz {s['hoehensitz']} Zufall {s['hoehensitz_null']} Trennschaerfe {s['trennschaerfe']} a10 {s['a10']} med|dz| {s['med_dz']} -> {s['status']}")
        if rc != 0: print(buf.getvalue()[-2500:])
        return e

    E = lauf("E_wahr", ["--probe", "--rot", "--bild", os.path.join(R0, "hoehensitz.png")])
    s = E.get("seiten") or {}
    pruef(sorted(s) == sorted(["+x", "-x", "+y", "-y"]) and all(s[ax]["name"] == SK[ax] for ax in s), "alle vier Seiten, Namen aus seiten_konvention")
    for ax in ("+x", "-x", "+y", "-y"):
        e = s.get(ax) or {}
        pruef(e.get("trennt") and (e.get("hoehensitz") or 0) >= 0.8 and (e.get("guete") or 0) >= 0.6 and (e.get("med_dz") or 9) < 0.06,
              f"E {SK[ax]}: Modell = Wahrheit -> trennt, hoehensitz {e.get('hoehensitz')} (Zufall {e.get('hoehensitz_null')}), guete {e.get('guete')}, med|dz| {e.get('med_dz')}")
        pr = (E.get("probe") or {}).get(ax) or {}; pm = {k: v for k, v in pr.items() if not k.startswith("decke")}; pd = {k: v for k, v in pr.items() if k.startswith("decke")}
        pruef(len(pm) == 6 and min(pm.values()) >= 0.3, f"NULLPROBE {SK[ax]}: Modell +-0,3/1/2 m in z -> Abfall >= 0,3 ({pm})")
        pruef(len(pd) == 6 and all(v is not None and v >= 0.2 for v in pd.values()), f"NULLPROBE Decke {SK[ax]}: Wolkenhaelfte +-0,3/1/2 m in z -> Abfall >= 0,2 (min {min(pd.values()) if pd else None})")
        for wer, rt in (("Modell", (E.get("rot") or {}).get(ax) or {}), ("Wolkenhaelfte", (E.get("rot_decke") or {}).get(ax) or {})):
            pruef(rt.get("erkannt") and (rt.get("eigene") or 0) >= HS.ROT_MARGE and rt.get("linien_gemeldet", 0) >= 1,
                  f"ROT ({wer}) {SK[ax]}: Linie z0 {rt.get('z0')} um 0,5 m gehoben erkannt (Abfall {rt.get('eigene')}, andere max {rt.get('andere_max')}, gemeldet {rt.get('linien_gemeldet')})")
    pruef(os.path.exists(os.path.join(R0, "hoehensitz.png")), "Kontrollbild geschrieben")
    pruef(E.get("sek", 999) < 300, f"Laufzeit {E.get('sek')} s")

    Rr = lauf("R_gesims_hoch", ["--stl", stl_r]); sr = Rr.get("seiten") or {}
    d = {ax: (s[ax]["hoehensitz"] or 0) - (sr.get(ax, {}).get("hoehensitz") or 0) for ax in s}
    pruef(d["+x"] >= 0.05 and all(d["+x"] > 2 * max(0.0, d[ax]) for ax in ("-x", "+y", "-y")), f"R: Sued-Gesims 0,5 m zu hoch -> Sued faellt {d['+x']:.3f}, andere {[round(d[a], 3) for a in ('-x', '+y', '-y')]}")
    fl = (sr.get("+x") or {}).get("fehler") or []
    tr = [f for f in fl if f.get("dz") is not None and 13.3 <= f["z"] <= 14.2 and -0.62 <= f["dz"] <= -0.38 and f["art"] == "Modell zu hoch"]
    pruef(len(tr) >= 2, f"R: Fehlerliste Sued nennt das Gesims (z 13,5..13,9, dz ~ -0,5, 'Modell zu hoch'): {[(f['z'], f['dz']) for f in fl[:4]]}")

    X = lauf("X_wolke_unbrauchbar", ["--wolke", wp_x]); sx = X.get("seiten") or {}
    pruef(len(sx) == 4 and all(not e.get("trennt") for e in sx.values()), f"X: Wolke 0,6 m Rauschen -> nicht trennbar ({[(e.get('trennschaerfe'), e.get('status')) for e in sx.values()]})")

    # --- 3. Einbau konvergenz.py (--lesen: hoehensitz.json; grob-F1/Formsitz fehlen bewusst -> Urteil nur aus der Hoehe)
    import konvergenz as KV
    les = os.path.join(R0, "lesen"); os.makedirs(les); kv_aus = os.path.join(R0, "kv"); os.makedirs(kv_aus)
    shutil.copy(sp, os.path.join(kv_aus, "konvergenz_fotosatz.json"))

    def kv(lid, hoehe):
        json.dump(hoehe, open(os.path.join(les, "hoehensitz.json"), "w")); buf = io.StringIO()
        with open(stl_w, "r+b") as fh: fh.write(lid.encode().ljust(8, b" "))
        with contextlib.redirect_stdout(buf): rc = KV.main([OJ, "--lauf", lid, "--lesen", les, "--aus", kv_aus, "--ohne-fein", "--ohne-wolke", "--ohne-formsitz"])
        z = json.loads(open(os.path.join(kv_aus, "konvergenz.jsonl")).read().splitlines()[-1])
        return rc, z, buf.getvalue()

    def hoehe_mit(werte, trennt=True):
        f = json.loads(json.dumps(E))
        for ax, v in werte.items(): f["seiten"][ax].update(hoehensitz=v, trennt=trennt)
        return f
    for i, v in enumerate((0.60, 0.70, 0.80)): rc, z, txt = kv(f"L{i}", hoehe_mit({"+x": v, "-y": 0.9 - 0.1 * i}))
    e = z["seiten"]["+x"]; w = z["seiten"]["-y"]
    pruef(e.get("hoehensitz") == 0.8 and e.get("hoehensitz_trennt") is True and "hoehe_a10" in e and "hoehe_fehler" in e, "konvergenz.jsonl traegt hoehensitz/hoehensitz_trennt/hoehe_a10/hoehe_fehler je Seite")
    pruef(e.get("status_hoehe") == KV.STEIGT and e["status"] == KV.STEIGT and w.get("status_hoehe") == KV.FAELLT and w["status"] == KV.FAELLT,
          f"Hoehe trennt: Sued +10 pp -> steigt ({e['status']}), West -10 pp -> faellt ({w['status']})")
    rc, z, txt = kv("L3", hoehe_mit({"+x": 0.6, "-y": 0.95}, trennt=False))
    pruef(z["seiten"]["+x"].get("status_hoehe") == KV.TRENNT_NICHT and z["seiten"]["+x"]["status"] != KV.FAELLT, f"Hoehe trennt nicht -> kein Urteil aus der Hoehe ({z['seiten']['+x']['status']})")
    pruef("Hoehensitz" in txt, "Textausgabe nennt den Hoehensitz")
    pruef(KV.status_mit_hoehe(KV.PLATEAU, KV.STEIGT) == KV.STEIGT and KV.status_mit_hoehe(KV.STEIGT, KV.FAELLT) == KV.FAELLT
          and KV.status_mit_hoehe(KV.PLATEAU, KV.TRENNT_NICHT) == KV.PLATEAU and KV.status_mit_hoehe(KV.PLATEAU, KV.KURZ) == KV.PLATEAU,
          "status_mit_hoehe: Hoehe steigt -> kein PLATEAU, Hoehe faellt -> faellt, ohne Beleg unveraendert")
    print(f"test_hoehensitz: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
