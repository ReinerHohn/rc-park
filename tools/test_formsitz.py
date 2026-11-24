#!/usr/bin/env python3
"""test_formsitz.py - synthetische Pruefung von tools/formsitz.py (trennscharfes Formmass, 24.11.2026) und seines Einbaus in tools/konvergenz.py.

Nachgebaut: Turm 10 x 8 x 14 m mit Vorsprung (1 x 4 x 6 m) an +x; seiten_konvention absichtlich ungewoehnlich (+x = Sued, -y = West).
Je Seite +x und -y drei Kameras (frontal und schraeg, 24-30 m). Wolke = Abtastung der WAHREN Form (2 cm Rauschen) + Bodenschicht + Fremdhaufen.
  E  Modell = Wahrheit                      -> trennt, guete hoch, med|dz| klein
  NULLPROBE (--probe): Modell 0,3 m entlang der Seitennormale, 1/2 m in jeder Richtung, 5 Grad gedreht -> deutlich schlechter
  ROT  (--rot): Fassade der Seite 0,35 m nach aussen -> erkannt (Abfall >= ROT_MARGE) auf DIESER Seite
  R  echtes STL mit Wand +x 0,35 m zu weit aussen -> formsitz Sued faellt >= 0,05, West kaum
  X  Wolke mit 0,6 m Rauschen (unbrauchbar) -> Trennschaerfe klein -> "nicht trennbar", NIE ein Urteil
  dazu: Regeln seiten_auswerten (n < 3, Trennschaerfe), Einbau konvergenz.py (--lesen formsitz.json: Felder + PLATEAU nur, wenn es trennt).
Nur CPU, ~1 min. Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_formsitz.py
"""
import sys, os, json, io, contextlib, shutil
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfade import temp_ordner
import formsitz as FS

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


def stl(m, pfad):
    mm = m.copy(); mm.apply_scale(1000.0 / 87); mm.export(pfad)


def main():
    print("test_formsitz:")
    # --- 1. Regeln ohne Rechnung
    pruef(abs(FS.guete(0.75, 0.5) - 0.5) < 1e-9 and FS.guete(0.5, None) is None, "guete = (S - S_null) / (1 - S_null)")
    nv = FS.null_varianten()
    pruef(len(nv) == 4 and all(abs(np.linalg.norm(d) - w) < 1e-6 for d, w in zip(nv, (1.3, 1.3, 2.1, 2.1))), "Nullvarianten 1,3 m +-x und 2,1 m +-y")
    S0 = dict(seiten={"+x": dict(name="Sued", fotos=["a", "b", "c", "d"]), "-y": dict(name="West", fotos=["e", "f"])})
    q = lambda s, s0, t: dict(formsitz=s, formsitz_null=s0, guete=FS.guete(s, s0), tiefe=s, deckung=0.9, trennschaerfe=t, decke=t + 0.1, decke_null=0.1, relativ=(s - s0) / t)
    je0 = dict(a=q(0.7, 0.1, 0.6), b=q(0.6, 0.1, 0.5), c=q(0.8, 0.2, 0.7), d=dict(fehler="x"), e=q(0.9, 0.1, 0.8), f=q(0.9, 0.1, 0.8))
    e0 = FS.seiten_auswerten(S0, je0)
    pruef(e0["+x"]["trennt"] and e0["+x"]["n"] == 3 and abs(e0["+x"]["formsitz"] - 0.7) < 1e-9 and e0["+x"]["name"] == "Sued",
          "Seite: Median ueber Fotos, Foto mit Fehler zaehlt nicht, Name aus dem Fotosatz (seiten_konvention)")
    pruef(not e0["-y"]["trennt"] and e0["-y"]["status"] == "zu wenig Fotos", "< 3 Fotos -> zu wenig Fotos, trennt nicht")
    je1 = {k: dict(v, trennschaerfe=0.05) for k, v in je0.items() if "fehler" not in v}
    pruef(FS.seiten_auswerten(S0, je1)["+x"]["status"] == FS.TRENNT_NICHT, "Trennschaerfe < TRENN_MIN -> nicht trennbar (auch bei hohem formsitz)")

    # --- 2. Synthetisches Objekt
    R0 = temp_ordner("test_formsitz_"); OD = os.path.join(R0, "modelle", "probe"); MP = os.path.join(OD, "messprotokoll")
    for d in (MP, os.path.join(OD, "sfm"), os.path.join(R0, "modelle", "stl"), os.path.join(R0, "daten", "probe", "fotos")): os.makedirs(d, exist_ok=True)
    SK = {"+x": "Sued", "-x": "Nord", "+y": "Ost", "-y": "West", "quelle": "Test"}
    obj = dict(name="probe", stl="modelle/stl/probe.stl", stl_massstab=87, stl_einheit_mm=True, zentrierung="achse", audit="modelle/probe/audit",
               fotos_dir="daten/probe/fotos", seiten_konvention=SK, rahmen_wand=dict(u0=-5, u1=5, v0=-4, v1=4), hoehe_m=14.0)
    OJ = os.path.join(OD, "objekt.json"); json.dump(obj, open(OJ, "w"))
    turm = trimesh.creation.box(extents=[10, 8, 14]); turm.apply_translation([0, 0, 7])
    vor = trimesh.creation.box(extents=[1.0, 4, 6]); vor.apply_translation([5.5, 0, 6])
    wahr = trimesh.util.concatenate([turm, vor])
    turm_r = trimesh.creation.box(extents=[10.35, 8, 14]); turm_r.apply_translation([0.175, 0, 7])                 # Wand +x 0,35 m zu weit aussen
    vor_r = vor.copy(); vor_r.apply_translation([0.35, 0, 0]); rot = trimesh.util.concatenate([turm_r, vor_r])
    stl_w = os.path.join(R0, "modelle", "stl", "probe.stl"); stl_r = os.path.join(R0, "modelle", "stl", "probe_rot.stl"); stl(wahr, stl_w); stl(rot, stl_r)
    seiten = {"+x": [([26.0, 0.0, 6.0]), ([24.0, -9.0, 7.0]), ([25.0, 8.0, 5.0])], "-y": [([0.0, -27.0, 6.0]), ([-9.0, -25.0, 7.0]), ([8.0, -24.0, 5.0])]}
    S = dict(k=3, seiten={}, ersetzungen=[])
    for ax, Cs in seiten.items():
        S["seiten"][ax] = dict(name=SK[ax], fotos=[])
        for i, C in enumerate(Cs):
            nr = f"{ax[1]}{'p' if ax[0] == '+' else 'm'}{i}"; json.dump(dict(foto=nr, kamera=kam(C, [0, 0, 6.0])), open(os.path.join(MP, f"K-{nr}.json"), "w"))
            S["seiten"][ax]["fotos"].append(nr)
    sp = os.path.join(R0, "fotosatz.json"); json.dump(S, open(sp, "w"))
    Pw = np.asarray(trimesh.sample.sample_surface(wahr, 1500000, seed=5)[0]) + np.random.default_rng(6).normal(0, 0.02, (1500000, 3))
    boden = np.c_[np.random.default_rng(7).uniform(-15, 15, (200000, 2)), np.random.default_rng(8).normal(0, 0.02, 200000)]
    fremd = np.random.default_rng(9).uniform([40, 40, 0], [50, 50, 10], (50000, 3))
    np.save(os.path.join(OD, "sfm", "punkte_modell_probe.npy"), np.vstack([Pw, boden, fremd]).astype(np.float32))
    wp_x = os.path.join(R0, "wolke_rauschen.npy"); np.save(wp_x, (Pw + np.random.default_rng(11).normal(0, 0.6, Pw.shape)).astype(np.float32))

    def lauf(name, extra):
        jp = os.path.join(R0, name + ".json"); buf = io.StringIO()
        with contextlib.redirect_stdout(buf): rc = FS.main([OJ, "--fotosatz", sp, "--json", jp, "--n-modell", "1500000", "--n-wolke", "1500000"] + extra)
        e = json.load(open(jp)) if rc == 0 and os.path.exists(jp) else {}
        for ax, s in (e.get("seiten") or {}).items():
            print(f"      {name} {s['name']}: formsitz {s['formsitz']} Zufall {s['formsitz_null']} Trennschaerfe {s['trennschaerfe']} med|dz| {s['med_dz']} -> {s['status']}")
        if rc != 0: print(buf.getvalue()[-2500:])
        return e

    E = lauf("E_wahr", ["--probe", "--rot", "--bild", os.path.join(R0, "formsitz.jpg")])
    s = E.get("seiten") or {}
    for ax in ("+x", "-y"):
        e = s.get(ax) or {}
        pruef(e.get("trennt") and (e.get("formsitz") or 0) >= 0.8 and (e.get("guete") or 0) >= 0.7 and (e.get("med_dz") or 9) < 0.05,
              f"E {SK[ax]}: Modell = Wahrheit -> trennt, formsitz {e.get('formsitz')}, guete {e.get('guete')}, med|dz| {e.get('med_dz')}")
        pruef((e.get("trennschaerfe") or 0) >= FS.TRENN_MIN and 0.5 <= (e.get("relativ") or 0) <= 1.3, f"E {SK[ax]}: Trennschaerfe {e.get('trennschaerfe')}, relativ {e.get('relativ')} (~1)")
        pr = (E.get("probe") or {}).get(ax) or {}
        nach = "x" if ax[1] == "x" else "y"
        pruef(min(pr.get(f"+{nach} 0.3 m", 0), pr.get(f"-{nach} 0.3 m", 0)) >= 0.3, f"NULLPROBE {SK[ax]}: 0,3 m entlang der Normale -> Abfall >= 0,3 ({pr.get(f'+{nach} 0.3 m')}, {pr.get(f'-{nach} 0.3 m')})")
        gross = {k: v for k, v in pr.items() if k.endswith(" 1 m") or k.endswith(" 2 m") or "5 Grad" in k}
        pruef(len(gross) == 14 and min(gross.values()) >= 0.05, f"NULLPROBE {SK[ax]}: 1/2 m jede Richtung + 5 Grad -> Abfall >= 0,05 (min {min(gross.values()) if gross else None})")
        rt = (E.get("rot") or {}).get(ax) or {}
        pruef(rt.get("erkannt") and rt.get("eigene", 0) >= FS.ROT_MARGE, f"ROT {SK[ax]}: Fassade 0,35 m aussen erkannt (Abfall {rt.get('eigene')})")
    pruef(os.path.exists(os.path.join(R0, "formsitz.jpg")), "Kontrollbild geschrieben")
    pruef(E.get("sek", 999) < 300, f"Laufzeit {E.get('sek')} s")

    Rr = lauf("R_wand_aussen", ["--stl", stl_r]); sr = Rr.get("seiten") or {}
    d_sued = (s["+x"]["formsitz"] or 0) - (sr.get("+x", {}).get("formsitz") or 0); d_west = (s["-y"]["formsitz"] or 0) - (sr.get("-y", {}).get("formsitz") or 0)
    pruef(d_sued >= 0.05 and d_sued > 2 * d_west, f"R: echte Wand 0,35 m aussen -> Sued faellt {d_sued:.3f}, West {d_west:.3f}")
    pruef(abs((sr.get("+x", {}).get("med_dz") or 0) - 0.35) < 0.1, f"R: med|dz| Sued ~ 0,35 m ({sr.get('+x', {}).get('med_dz')})")

    X = lauf("X_wolke_unbrauchbar", ["--wolke", wp_x]); sx = X.get("seiten") or {}
    pruef(all(not e.get("trennt") and e.get("status") == FS.TRENNT_NICHT for e in sx.values()) and len(sx) == 2,
          f"X: Wolke 0,6 m Rauschen -> nicht trennbar ({[(e.get('trennschaerfe'), e.get('status')) for e in sx.values()]})")

    # --- 3. Einbau konvergenz.py (--lesen: formsitz.json; grob-F1 fehlt bewusst -> Urteil nur aus Formsitz)
    import konvergenz as KV
    les = os.path.join(R0, "lesen"); os.makedirs(les); kv_aus = os.path.join(R0, "kv")
    os.makedirs(kv_aus);shutil.copy(sp, os.path.join(kv_aus, "konvergenz_fotosatz.json"))

    def kv(lid, form):
        json.dump(form, open(os.path.join(les, "formsitz.json"), "w")); buf = io.StringIO()
        with open(stl_w, "r+b") as fh: fh.write(lid.encode().ljust(8, b" "))   # anderer STL-Stand je Lauf (gleicher Stand = Streuungsmessung in konvergenz)
        with contextlib.redirect_stdout(buf): rc = KV.main([OJ, "--lauf", lid, "--lesen", les, "--aus", kv_aus, "--ohne-fein", "--ohne-wolke"])
        z = json.loads(open(os.path.join(kv_aus, "konvergenz.jsonl")).read().splitlines()[-1])
        return rc, z, buf.getvalue()

    def form_mit(werte, trennt=True):
        f = json.loads(json.dumps(E))
        for ax, v in werte.items():
            f["seiten"][ax].update(formsitz=v, trennt=trennt, fotos={nr: v for nr in f["seiten"][ax]["fotos"]})
        return f
    for i, v in enumerate((0.70, 0.705, 0.708)): rc, z, txt = kv(f"L{i}", form_mit({"+x": v, "-y": 0.5 + 0.1 * i}))
    e = z["seiten"]["+x"]; w = z["seiten"]["-y"]
    pruef(e.get("formsitz") == 0.708 and e.get("formsitz_trennt") is True and "med_dz" in e and e.get("fotos_formsitz"), "konvergenz.jsonl traegt formsitz/formsitz_trennt/med_dz je Seite")
    pruef(e["status"] == KV.PLATEAU and w["status"] == KV.STEIGT, f"Formsitz trennt: Sued flach -> PLATEAU ({e['status']}), West +10 pp -> steigt ({w['status']})")
    rc, z, txt = kv("L3", form_mit({"+x": 0.708, "-y": 0.8}, trennt=False))
    pruef(z["seiten"]["+x"]["status"] == KV.TRENNT_NICHT and z["seiten"]["-y"]["status"] == KV.TRENNT_NICHT,
          f"Formsitz trennt nicht -> kein PLATEAU/steigt, 'nicht trennbar' ({z['seiten']['+x']['status']})")
    pruef("Formsitz" in txt, "Textausgabe nennt den Formsitz")
    pruef(KV.status_mit_formsitz(KV.PLATEAU, KV.FAELLT, False) == KV.FAELLT and KV.status_mit_formsitz(KV.PLATEAU, KV.KEIN, True) == KV.PLATEAU,
          "ohne Trennung bleibt nur ein belegtes feines steigt/faellt; mit Trennung wie bisher")
    print(f"test_formsitz: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
