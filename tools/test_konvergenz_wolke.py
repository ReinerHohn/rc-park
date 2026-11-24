#!/usr/bin/env python3
"""test_konvergenz_wolke.py - synthetische Pruefung von tools/konvergenz_wolke.py (Verlust "dichte Wolke -> Modell" je Seite, 24.11.2026).

Nachgebaut: Haus 10 x 8 x 10 m mit Vorbau (1,5 x 4 x 6 m) an der +x-Seite; seiten_konvention absichtlich ungewoehnlich (+x = Sued). 3 Kameras vor +x.
"Fotos" = Render der WAHREN Form (Schattierung je Ebene + Rauschen). Wolke = Abtastung der wahren Form (1 cm Rauschen) + Bodenschicht + ferner Fremdhaufen
(beide muessen der Zuschnitt entfernen), Kamerarahmen wie die K-Dateien.
  A Modell OHNE Vorbau, Wolke wahr           -> verlust >= MARGE, "Modellierung verliert"
  B Modell wahr, Wolke wahr                   -> |verlust| < MARGE, "gleich"
  C Modell wahr, Wolke nur unterste 3 m       -> Abdeckung < 0,5, "Daten fehlen"
  dazu: Statusregeln an den Schwellen, gepaarter Verlust (fehlendes Foto verschiebt nichts), Zuschnitt/Boden/Unterstichprobe, Standardpfad der Wolke,
  Einbau in konvergenz.py (--lesen: Felder f1_wolke/verlust/status_wolke in der jsonl-Zeile, Kurvenbild geschrieben).
Nur CPU (foto_diff Punktmodus). Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_konvergenz_wolke.py
"""
import sys, os, json, io, contextlib
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfade import temp_ordner
import konvergenz_wolke as KW
import render_kern as RK

F = 0


def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text)
    if not ok: F += 1


W, H, FPX = 1200, 800, 960.0


def kam(C, ziel):
    C = np.asarray(C, float); fw = np.asarray(ziel, float) - C; fw /= np.linalg.norm(fw)
    rt = np.cross(fw, [0, 0, 1.0]); rt /= np.linalg.norm(rt); dn = np.cross(fw, rt); R = np.vstack([rt, dn, fw]); t = -R @ C
    return R, t, dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=t.tolist(), f_px=FPX, cx=W / 2, cy=H / 2, bild=[W, H], rms_px=1.0, k1=0.0,
                      standort_xyz=C.tolist(), rahmen_verschiebung=[0.0, 0.0, 0.0], sfm_guete=dict(klasse="gut"))


def foto(m, R, t, rng):
    P, fi = trimesh.sample.sample_surface(m, 2500000, seed=1); P = np.asarray(P)
    d, idx = RK.tiefenbild(P, R, t, FPX, W / 2, H / 2, W, H)
    Nf = m.face_normals; df = np.einsum("ij,ij->i", Nf, m.triangles_center)
    img = np.full((H, W), 200.0); img[int(H * 0.75):] = 120.0; tr = idx >= 0; ft = fi[idx[tr]]; n = Nf[ft]
    l1 = np.array([0.4, -0.5, 0.75]); l2 = np.array([-0.7, 0.3, 0.2]); l1 /= np.linalg.norm(l1); l2 /= np.linalg.norm(l2)
    img[tr] = 40 + 80 * np.abs(n @ l1) + 50 * np.abs(n @ l2) + 35 * np.cos(2.3 * df[ft])
    img = cv2.morphologyEx(img.astype(np.float32), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)) + rng.normal(0, 3, (H, W))
    return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


def stl(m, pfad):
    mm = m.copy(); mm.apply_scale(1000.0 / 87); mm.export(pfad)


def main():
    print("test_konvergenz_wolke:")
    # --- 1. Regeln ohne Rechnung
    M = KW.MARGE
    pruef(KW.wolke_status(0.7, M + 0.001, 0.9, 3) == KW.VERLIERT, "verlust >= MARGE -> Modellierung verliert")
    pruef(KW.wolke_status(0.3, M + 0.01, 0.2, 3) == KW.VERLIERT, "Wolke deutlich besser schlaegt auch schwache Daten (Modell verschenkt trotzdem)")
    pruef(KW.wolke_status(KW.F1_DATEN - 0.01, 0.0, 0.9, 5) == KW.DATEN, "F1_wolke unter F1_DATEN -> Daten fehlen")
    pruef(KW.wolke_status(0.7, 0.0, KW.ABD_DATEN - 0.01, 5) == KW.DATEN, "Abdeckung unter ABD_DATEN -> Daten fehlen")
    pruef(KW.wolke_status(0.7, -M - 0.01, 0.9, 5) == KW.BESSER, "verlust <= -MARGE -> Modell besser als Wolke")
    pruef(KW.wolke_status(0.7, M - 0.01, 0.9, 5) == KW.GLEICH, "knapp unter MARGE -> gleich")
    pruef(KW.wolke_status(0.7, 0.2, 0.9, 2) == KW.WENIG and KW.wolke_status(None, None, None, 0) == KW.WENIG, "< 3 gepaarte Fotos -> zu wenig Fotos (nie 0)")
    pruef(KW.wolke_status(0.8, 0.2, 0.9, 5, verlust_zufall=0.0, guete_w=0.4) == KW.GLEICH, "roher Verlust ohne Verlust ueber Zufall (Kantenteppich) -> nicht 'verliert'")
    pruef(KW.wolke_status(0.6, 0.0, 0.9, 5, verlust_zufall=0.0, guete_w=-0.01) == KW.DATEN, "Wolke nicht besser als Zufall -> Daten fehlen")
    pruef(KW.wolke_status(0.75, 0.3, 0.9, 5, verlust_zufall=0.05, guete_w=0.06, guete_m=0.01) == KW.TRENNT_NICHT,
          "beide kaum ueber Zufall -> nicht trennbar (kein Urteil ueber Modell oder Daten)")
    pruef(KW.wolke_status(0.7, -0.2, 0.9, 5, verlust_zufall=0.0, guete_w=0.3, guete_m=0.3) == KW.GLEICH, "Modell besser nur, wenn auch ueber Zufall (symmetrisch zu 'verliert')")
    pruef(abs(KW.guete(0.75, 0.5) - 0.5) < 1e-9 and KW.guete(0.5, None) is None, "guete = (F1 - F1_null) / (1 - F1_null)")
    S0 = dict(seiten={"+x": dict(name="Sued", fotos=["a", "b", "c", "d"])})
    je0 = dict(a=dict(w=0.8, m=0.7, abd=0.9), b=dict(w=0.6, m=0.5, abd=0.9), c=dict(w=0.4, m=0.3, abd=0.9), d=dict(w=0.9, m=None, abd=0.9))
    e0 = KW.seiten_auswerten(S0, je0)["+x"]
    pruef(abs(e0["verlust"] - 0.1) < 1e-9 and e0["n"] == 3, f"gepaart: Foto ohne Modellwert verschiebt den Verlust nicht (0,1 erwartet, {e0['verlust']})")
    pruef(e0["name"] == "Sued", "Seitenname aus dem Fotosatz (seiten_konvention), keine eigene Kompassrechnung")

    # --- 2. Synthetisches Objekt
    R0 = temp_ordner("test_konv_wolke_"); OD = os.path.join(R0, "modelle", "probe"); MP = os.path.join(OD, "messprotokoll"); FOT = os.path.join(R0, "daten", "probe", "fotos")
    for d in (MP, FOT, os.path.join(OD, "sfm"), os.path.join(R0, "modelle", "stl")): os.makedirs(d, exist_ok=True)
    SK = {"+x": "Sued", "-x": "Nord", "+y": "Ost", "-y": "West", "quelle": "Test"}
    obj = dict(name="probe", stl="modelle/stl/probe.stl", stl_massstab=87, stl_einheit_mm=True, zentrierung="achse", masstabelle="modelle/probe/masstabelle.json",
               audit="modelle/probe/audit", fotos_dir="daten/probe/fotos", seiten_konvention=SK, rahmen_wand=dict(u0=-5, u1=5, v0=-4, v1=4), hoehe_m=10.0)
    OJ = os.path.join(OD, "objekt.json"); json.dump(obj, open(OJ, "w")); json.dump({}, open(os.path.join(OD, "masstabelle.json"), "w"))
    haus = trimesh.creation.box(extents=[10, 8, 10]); haus.apply_translation([0, 0, 5])
    vorbau = trimesh.creation.box(extents=[1.5, 4, 6]); vorbau.apply_translation([5.75, 0, 3])
    wahr = trimesh.util.concatenate([haus, vorbau])                       # Rueckwand des Vorbaus liegt in der Hauswand (verdeckt, keine Kante)
    stl_ohne = os.path.join(R0, "modelle", "stl", "probe.stl"); stl_wahr = os.path.join(R0, "modelle", "stl", "probe_wahr.stl"); stl(haus, stl_ohne); stl(wahr, stl_wahr)
    rng = np.random.default_rng(0); fotos = []
    for i, y in enumerate((-6.0, 5.0, 8.0)):                                 # alle seitlich (> 4 m): Hausecke liegt im Bild -> Modell ohne Vorbau hat Innenkanten (frontal: keine = nicht beurteilbar)
        nr = f"k{i}"; R, t, k = kam([28.0, y, 6.0], [0.0, 0.0, 4.5]); json.dump(dict(foto=nr, kamera=k), open(os.path.join(MP, f"K-{nr}.json"), "w"))
        cv2.imwrite(os.path.join(FOT, nr + ".jpg"), foto(wahr, R, t, rng), [cv2.IMWRITE_JPEG_QUALITY, 95]); fotos.append(nr)
    sp = os.path.join(R0, "fotosatz.json"); json.dump(dict(k=3, seiten={"+x": dict(name="Sued", fotos=fotos)}), open(sp, "w"))
    Pw = np.asarray(trimesh.sample.sample_surface(wahr, 600000, seed=5)[0]) + np.random.default_rng(6).normal(0, 0.01, (600000, 3))
    boden = np.c_[np.random.default_rng(7).uniform(-12, 12, (200000, 2)), np.random.default_rng(8).normal(0, 0.02, 200000)]
    fremd = np.random.default_rng(9).uniform([40, 40, 0], [50, 50, 10], (50000, 3))
    Wv = np.vstack([Pw, boden, fremd]).astype(np.float32); wp = os.path.join(OD, "sfm", "punkte_modell_probe.npy"); np.save(wp, Wv)
    unten = Pw[Pw[:, 2] < 3.0]; wp_u = os.path.join(R0, "wolke_unten.npy"); np.save(wp_u, np.vstack([unten, boden]).astype(np.float32))
    pruef(KW.wolke_pfad(obj, OD) == wp, "Standardwolke = <objektordner>/sfm/punkte_modell_<ordnername>.npy")
    box = (np.array([-6.0, -5.0, -1.0]), np.array([7.5, 5.0, 11.0]))
    P_, info = KW.wolke_laden(wp, box, n_max=10 ** 9)
    pruef(P_[:, 2].min() >= -1.0 + KW.BODEN_M and not np.any(P_[:, 0] > 30), f"Zuschnitt: Bodenschicht und Fremdhaufen weg (z min {P_[:, 2].min():.2f}, n {len(P_)})")
    pruef(info["n_box"] < len(Wv) and len(P_) > 0.95 * len(Pw), "Haus bleibt (> 95 % der Hauspunkte), Rest weg")
    P2, info2 = KW.wolke_laden(wp, box, n_max=100000); pruef(len(P2) == 100000 and info2["n_genutzt"] == 100000, "Unterstichprobe auf n_max (RAM)")
    N_ = KW.normalen_pca(P2[:20000]); wand = np.abs(P2[:20000, 0] - 6.5) < 0.02
    pruef(wand.sum() > 50 and np.median(np.abs(N_[wand, 0])) > 0.95, "PCA-Normale an der Vorbau-Stirnwand ~ +-x")

    # --- 3. Faelle A/B/C (foto_diff Punktmodus, CPU)
    def lauf(name, extra):
        aus = os.path.join(R0, name); buf = io.StringIO()
        with contextlib.redirect_stdout(buf): rc = KW.main([OJ, "--aus", aus, "--fotosatz", sp, "--n-max", "400000"] + extra)
        e = json.load(open(os.path.join(aus, "konvergenz_wolke.json")))["seiten"]["+x"] if rc == 0 else {}
        print(f"      {name}: rc {rc}, wolke {e.get('f1_wolke')} modell {e.get('f1_modell_gleich')} verlust {e.get('verlust')} abd {e.get('abdeckung')} -> {e.get('status')}")
        if rc != 0 or e.get("n", 0) < 3: print(buf.getvalue()[-2500:])
        return aus, e
    ausA, A = lauf("A_ohne_vorbau", [])
    pruef(A.get("status") == KW.VERLIERT and (A.get("verlust") or 0) >= KW.MARGE, "A: Modell ohne Vorbau, Wolke mit -> Modellierung verliert")
    pruef(A.get("abdeckung") is not None and A["abdeckung"] > 0.8, "A: Wolke deckt den Modellbereich (Splat schliesst die Punktluecken)")
    _, B = lauf("B_wahr", ["--stl", stl_wahr])
    pruef(B.get("status") == KW.GLEICH and abs(B.get("verlust") if B.get("verlust") is not None else 9) < KW.MARGE, "B: Modell = Wolke = Wahrheit -> gleich")
    pruef((A.get("f1_modell_gleich") or 1) < (B.get("f1_modell_gleich") or 0), "Modell ohne Vorbau schlechter als wahres Modell (Fotos tragen)")
    _, C = lauf("C_wolke_unten", ["--stl", stl_wahr, "--wolke", wp_u])
    pruef(C.get("status") == KW.DATEN and (C.get("abdeckung") or 1) < KW.ABD_DATEN, "C: Wolke nur unten -> Daten fehlen (Luecken zaehlen, nicht schoenen)")
    # D (Gegenprobe 1122: Kantenteppich aus Wolkenrauschen): Wolke = Wahrheit + 15 cm Rauschen, Modell wahr -> darf NICHT "Modellierung verliert" heissen
    wp_r = os.path.join(R0, "wolke_rausch.npy"); np.save(wp_r, (Pw + np.random.default_rng(11).normal(0, 0.15, Pw.shape)).astype(np.float32))
    _, D = lauf("D_wolke_rauschen", ["--stl", stl_wahr, "--wolke", wp_r])
    pruef(D.get("status") not in (KW.VERLIERT, KW.WENIG) and (D.get("verlust_zufall") is not None and D["verlust_zufall"] < KW.MARGE),
          f"D: verrauschte Wolke schlaegt das wahre Modell nicht (Zufallsniveau; verlust_zufall {D.get('verlust_zufall')}, {D.get('status')})")
    pruef(A.get("verlust_zufall") is not None and A["verlust_zufall"] >= KW.MARGE and A.get("guete_wolke", 0) > A.get("guete_modell", 1),
          "A: Verlust auch ueber dem Zufallsniveau")

    # --- 4. Einbau in konvergenz.py (--lesen: foto_diff_*.json + konvergenz_wolke.json aus Fall A)
    import konvergenz as KV
    import shutil
    kv_aus = os.path.join(R0, "kv"); les = os.path.join(R0, "lesen"); os.makedirs(les); buf = io.StringIO()   # grob = Modell-foto_diff (nicht die Wolkenlaeufe)
    for nr in fotos: shutil.copy(os.path.join(ausA, "modell", nr, f"foto_diff_{nr}.json"), les)
    shutil.copy(os.path.join(ausA, "konvergenz_wolke.json"), les)
    with contextlib.redirect_stdout(buf): rc = KV.main([OJ, "--lauf", "L1", "--lesen", les, "--aus", kv_aus, "--ohne-fein"])
    z = json.loads(open(os.path.join(kv_aus, "konvergenz.jsonl")).read().splitlines()[-1]) if os.path.exists(os.path.join(kv_aus, "konvergenz.jsonl")) else {}
    e = (z.get("seiten") or {}).get("+x") or {}
    pruef(rc == 0 and e.get("status_wolke") == KW.VERLIERT and e.get("verlust") == A.get("verlust") and e.get("f1_wolke") == A.get("f1_wolke"),
          f"konvergenz.jsonl traegt f1_wolke/verlust/status_wolke (rc {rc}, {e.get('status_wolke')})")
    pruef("Wolke F1" in buf.getvalue() and os.path.exists(os.path.join(kv_aus, "konvergenz.png")), "Textausgabe + Kurvenbild mit Wolke")
    pruef(e.get("f1") is not None and abs(e["f1"] - A["f1_modell_gleich"]) < 0.02 and e["f1"] < e["f1_wolke"], "grob-F1 (Modell) und f1_wolke getrennt in derselben Zeile")
    with contextlib.redirect_stdout(io.StringIO()): KV.main([OJ, "--lauf", "L2", "--lesen", les, "--aus", kv_aus, "--ohne-fein", "--ohne-wolke", "--trocken"])
    print(f"test_konvergenz_wolke: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
