#!/usr/bin/env python3
"""test_koerper_schleife.py - fester Test ohne GPU fuer tools/wolke_rest.py (Grobformen, Nachbar-Abtrennung), bauteile.wolkenrest_koerper und tools/koerper_schleife.py (21.11.2026).

Synthetisch: Turm 8 x 8 x 20 m als Modell; Wolke = Turmflaechen + sechs Dinge, die dem Modell fehlen:
  Kasten  Anbau an der Wand x = 8: y 2..5, 2 m tief, bis z 6            -> 'kasten' (breit 3, tief 2, oben 6, bis zum Boden)
  Ring    Umgang um den Turm z 14..15, Ausladung 0,8 m                  -> 'ring'   (Ausladung 0,8, alle Sektoren)
  Stab    Stange auf dem Dach bei (4, 4), r 0,15 m, z 20..24            -> 'stab'
  Rund    Treppenturm an der Wand y = 0, Achse (4, -0,8), r 1,5, z 0..12 -> 'rund'
  Haus    Nachbarhaus x -10..0, y -2..10, z 0..9 an der Wand x = 0      -> 'nachbar' (mit Grundflaeche: Beleg Grundflaeche; ohne: geometrische Ersatzregel, ANNAHME)
  Gang    Flaeche im Vollkoerper (y = 4, x 1..7, z 1..5)                -> 'hohl'
Teil 1 (im Prozess): Formen, Masse, Kandidaten; Nachbar nie Kandidat (mit und ohne Grundflaechen).
Teil 2 (Treiber mit BAU-ATTRAPPE statt Generator: Turm + bauteile.wolkenrest_koerper, der Kasten absichtlich 3,6 m daneben gebaut): Ring/Stab/Rund angenommen, Kasten verworfen und
  im Endmodell weggelassen, Wolkenpunkte am Modell gestiegen; zweiter Lauf schlaegt den verworfenen Kasten nicht wieder vor (nichts zu tun, kein Bau).
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/test_koerper_schleife.py     (Attrappe intern: ~/.venvs/rcpark/bin/python -I tools/test_koerper_schleife.py --attrappe)
"""
import sys, os, json, argparse, subprocess, tempfile, shutil
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
GEN_PY = os.path.expanduser("~/.venvs/rcpark/bin/python")


def attrappe():
    """Bau-Attrappe = kleinster Generator: Turm + alle nicht verworfenen Koerper aus KOERPER_AUTO; Form in FALSCH_FORM wird 3,6 m entlang der Wand versetzt gebaut (falscher Koerper)."""
    import trimesh
    from manifold3d import Manifold as M
    from bauteile import wolkenrest_koerper
    obj = json.load(open(os.environ["OBJEKT_JSON"])); kp = os.environ["KOERPER_AUTO"]; tmp = kp + ".attrappe.json"; D = json.load(open(kp)) if os.path.exists(kp) else dict(haufen=[])
    for H in D["haufen"]:
        if H.get("form") == os.environ.get("FALSCH_FORM") and H.get("mass"): H["mass"]["u0"] += 3.6; H["mass"]["u1"] += 3.6
    json.dump(D, open(tmp, "w")); k, bel = wolkenrest_koerper(M.cube((8, 8, 20)), tmp); os.remove(tmp); m = k.to_mesh()
    t = trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3] * 1000.0 / 87.0, np.asarray(m.tri_verts), process=False); t.export(obj["stl"])
    json.dump(bel, open(os.path.join(os.path.dirname(kp), "attrappe_belege.json"), "w")); return 0


def wolke(rng, dichte=400, rausch=0.015):
    def flaeche(o, a, b):
        o, a, b = (np.array(v, float) for v in (o, a, b)); n = int(dichte * np.linalg.norm(np.cross(a, b))); return o + rng.random((n, 1)) * a + rng.random((n, 1)) * b
    def quader(x0, y0, z0, x1, y1, z1, seiten):
        T = dict(xm=((x0, y0, z0), (0, y1 - y0, 0), (0, 0, z1 - z0)), xp=((x1, y0, z0), (0, y1 - y0, 0), (0, 0, z1 - z0)), ym=((x0, y0, z0), (x1 - x0, 0, 0), (0, 0, z1 - z0)), yp=((x0, y1, z0), (x1 - x0, 0, 0), (0, 0, z1 - z0)),
                 zm=((x0, y0, z0), (x1 - x0, 0, 0), (0, y1 - y0, 0)), zp=((x0, y0, z1), (x1 - x0, 0, 0), (0, y1 - y0, 0))); return [flaeche(*T[s]) for s in seiten]
    def zyl(cx, cy, r, z0, z1, w0=0.0, w1=2 * np.pi):
        n = int(dichte * r * (w1 - w0) * (z1 - z0)); w = w0 + rng.random(n) * (w1 - w0); return np.c_[cx + r * np.cos(w), cy + r * np.sin(w), z0 + rng.random(n) * (z1 - z0)]
    T = quader(0, 0, 0, 8, 8, 20, ("xm", "xp", "ym", "yp", "zp"))
    T += quader(8, 2, 0, 10, 5, 6, ("xp", "ym", "yp", "zp"))                                                            # Kasten
    T += quader(-0.8, -0.8, 14, 8.8, 8.8, 15, ("xm", "xp", "ym", "yp", "zm", "zp"))                                     # Ring (Deck-/Unterflaeche: Teil ueber dem Turm liegt im Modell -> 'hohl' oder zu nah, stoert nicht)
    T += [zyl(4, 4, 0.15, 20, 24)]                                                                                      # Stab
    T += [zyl(4, -0.8, 1.5, 0, 12, np.pi - 0.5, 2 * np.pi + 0.5)]                                                       # Rund (Bogen vor der Wand y = 0)
    T += quader(-10, -2, 0, 0, 10, 9, ("xm", "ym", "yp", "zp"))                                                         # Nachbarhaus
    T += [flaeche((1, 4, 1), (6, 0, 0), (0, 0, 4))]                                                                     # Gang im Vollkoerper
    W = np.vstack(T); W = W[~((W[:, 2] > 14.001) & (W[:, 2] < 14.999) & (W[:, 0] > 0.3) & (W[:, 0] < 7.7) & (W[:, 1] > 0.3) & (W[:, 1] < 7.7) & (np.abs(W[:, 1] - 4) > 0.01))]
    return (W + rng.normal(0, rausch, W.shape)).astype(np.float32)


def main():
    if "--attrappe" in sys.argv: return attrappe()
    import trimesh, wolke_rest as WR
    rng = np.random.default_rng(7); W = wolke(rng); F = []; ok = lambda b, t: F.append(t) if not b else None
    G = dict(eigen=[[[0, 0], [8, 0], [8, 8], [0, 8]]], fremd=[dict(name="haus", umriss=[[-10, -2], [0, -2], [0, 10], [-10, 10]], hoehe=9.0)])
    # --- Teil 1: Formen im Prozess ---
    m = trimesh.creation.box(extents=(8, 8, 20)); m.apply_translation((4, 4, 10)); S, fi = trimesh.sample.sample_surface(m, 300000, seed=0); S = np.asarray(S, np.float32); N = np.asarray(m.face_normals[fi], np.float32)
    a = argparse.Namespace(fern=0.35, nah=0.15, zelle=0.4, anschluss=0.8, weit=4.0, min_p=150, boden=1.0)
    for mit in (True, False):
        H, kenn, _, _ = WR.messen(S, N, W, a, [np.array(p, float) for p in G["eigen"]] if mit else None, [(f["name"], np.array(f["umriss"], float), f["hoehe"]) for f in G["fremd"]] if mit else None)
        def finde(form, x, y, z): return [h for h in H if h["form"] == form and h["kasten"][0] - 0.5 <= x <= h["kasten"][3] + 0.5 and h["kasten"][1] - 0.5 <= y <= h["kasten"][4] + 0.5 and h["kasten"][2] - 0.5 <= z <= h["kasten"][5] + 0.5]
        t = "mit Grundflaechen" if mit else "ohne Grundflaechen"
        k = finde("kasten", 9, 3.5, 3); ok(len(k) == 1 and k[0]["kandidat"], f"{t}: Kasten nicht als 'kasten' erkannt: {[(h['form'], h['kasten']) for h in H]}")
        if k: q = k[0]["mass"]; ok(abs(q["u1"] - q["u0"] - 3) < 0.15 and abs(q["w1"] - q["w0"] - 2) < 0.15 and abs(q["z1"] - 6) < 0.15 and q["bis_boden"] and q["rest"] < 0.05, f"{t}: Kastenmasse falsch {q}")
        k = finde("ring", 8.6, 4, 14.5); ok(len(k) == 1 and k[0]["kandidat"], f"{t}: Ring nicht als 'ring' erkannt: {[(h['form'], h['kasten'], h['pruef'].get('ring')) for h in H if h['kasten'][2] > 13 and h['kasten'][5] < 16]}")
        if k: q = k[0]["mass"]; ok(abs(q["ausladung"] - 0.8) < 0.15 and abs(q["z0"] - 14) < 0.15 and abs(q["z1"] - 15) < 0.15 and q["abdeckung"] >= 0.95, f"{t}: Ringmasse falsch {q}")
        k = finde("stab", 4, 4, 22); ok(len(k) == 1 and k[0]["kandidat"], f"{t}: Stab nicht als 'stab' erkannt: {[(h['form'], h['kasten'], h['pruef'].get('stab')) for h in H if h['kasten'][2] > 19]}")
        if k: q = k[0]["mass"]; ok(abs(q["r"] - 0.15) < 0.03 and abs(q["x"] - 4) < 0.05 and abs(q["y"] - 4) < 0.05 and abs(q["z1"] - 24) < 0.15 and len(q["profil"]) >= 10, f"{t}: Stabmasse falsch {q}")
        k = finde("rund", 4, -1.5, 6); ok(len(k) == 1 and k[0]["kandidat"] and abs(k[0]["kreis"]["r"] - 1.5) < 0.1 and len(k[0]["profil"]) >= 20, f"{t}: Rundturm nicht als 'rund' erkannt: {[(h['form'], h['kasten'], h['pruef'].get('rund')) for h in H if h['kasten'][4] < 0.5]}")
        k = finde("nachbar", -3, 4, 5); ok(len(k) >= 1 and not any(h["kandidat"] for h in k) and all(h["nachbar"]["quelle"] == ("Grundflaeche" if mit else "ANNAHME geometrisch") for h in k), f"{t}: Nachbarhaus nicht abgetrennt: {[(h['form'], h['kasten'], h.get('nachbar')) for h in H if h['kasten'][0] < -1]}")
        ok(not any(h.get("kandidat") and h["kasten"][0] < -1.0 for h in H), f"{t}: ein Haufen am Nachbarhaus ist Bauteil-Kandidat")
        k = finde("hohl", 4, 4, 3); ok(len(k) == 1 and not k[0]["kandidat"], f"{t}: Flaeche im Vollkoerper nicht als 'hohl' gemeldet")
        ok(sum(1 for h in H if h.get("kandidat")) == 4, f"{t}: {sum(1 for h in H if h.get('kandidat'))} Kandidaten statt 4: {[(h['form'], h['kasten']) for h in H if h.get('kandidat')]}")
    # --- Teil 2: Treiber mit Bau-Attrappe ---
    T = tempfile.mkdtemp(prefix="koerper_schleife_"); A = os.path.join(T, "audit")
    try:
        stl = os.path.join(T, "turm.stl"); json.dump(dict(name="Testturm", stl=stl, stl_massstab=87), open(os.path.join(T, "objekt.json"), "w")); np.save(os.path.join(T, "wolke.npy"), W); json.dump(G, open(os.path.join(T, "g.json"), "w"))
        bau = f"{shlex_quote(GEN_PY)} -I {shlex_quote(os.path.abspath(__file__))} --attrappe"; env = dict(os.environ, OBJEKT_JSON=os.path.join(T, "objekt.json"), KOERPER_AUTO=os.path.join(A, "koerper_auto.json"), FALSCH_FORM="kasten"); os.makedirs(A)
        r = subprocess.run(["bash", "-c", bau], env=env, capture_output=True, text=True); ok(r.returncode == 0 and os.path.exists(stl), "Bau-Attrappe laeuft nicht: " + r.stderr[-300:])
        cmd = [sys.executable, "-W", "ignore", "-I", os.path.join(HIER, "koerper_schleife.py"), os.path.join(T, "objekt.json"), os.path.join(T, "wolke.npy"), "--bau", bau, "--grundflaechen", os.path.join(T, "g.json"), "--rest", "--jeder 1 --proben 300000"]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True); ok(r.returncode == 0, f"Treiber rc {r.returncode}: {(r.stdout + r.stderr)[-400:]}")
        if r.returncode == 0:
            Z = json.load(open(os.path.join(A, "koerper_schleife.json"))); K = {k["form"]: k for k in json.load(open(os.path.join(A, "koerper_auto.json")))["haufen"]}
            ok(sorted(x["form"] for x in Z["angenommen"]) == ["ring", "rund", "stab"], f"angenommen {[(x['form'], x['urteil']) for x in Z['angenommen']]}, verworfen {[(x['form'], x['urteil']) for x in Z['verworfen']]}")
            ok([x["form"] for x in Z["verworfen"]] == ["kasten"] and K.get("kasten", {}).get("angenommen") is False and "verworfen" in K.get("kasten", {}).get("urteil", ""), f"falsch gebauter Kasten nicht verworfen: {Z['verworfen']}")
            ok(Z["wolke_am_modell_nachher"] > Z["wolke_am_modell_vorher"] + 3000, f"Wolkenpunkte am Modell nicht gestiegen: {Z['wolke_am_modell_vorher']} -> {Z['wolke_am_modell_nachher']}")
            ok(all(k.get("gewinn", 0) >= 0.6 * k["punkte"] for f, k in K.items() if f != "kasten"), f"richtige Koerper treffen die Wolke schlecht: {[(f, k.get('gewinn'), k['punkte']) for f, k in K.items()]}")
            bel = json.load(open(os.path.join(A, "attrappe_belege.json"))); ok(len(bel) == 3 and not any("Kasten" in b["element"] for b in bel) and all("ANNAHME" in b.get("hinweis", "") for b in bel), f"Endmodell: Belege {[b['element'][:30] for b in bel]} (verworfener Kasten muss fehlen)")
            ok(Z["baulaeufe"] == 2 and Z["runden"] == 1, f"{Z['baulaeufe']} Baulaeufe / {Z['runden']} Runden statt 2 / 1 (ein Bau mit allen Kandidaten, ein Rueckbau)")
            ok(any(g["form"] == "nachbar" for g in Z["gemeldet"]) and any(g["form"] == "hohl" for g in Z["gemeldet"]), "Nachbar/Hohlraum fehlen in der Meldeliste")
            r = subprocess.run(cmd, env=env, capture_output=True, text=True); Z2 = json.load(open(os.path.join(A, "koerper_schleife.json")))
            ok(r.returncode == 3 and Z2["baulaeufe"] == 0 and len(Z2["verworfen"]) == 1 and len(Z2["angenommen"]) == 3, f"zweiter Lauf: rc {r.returncode}, {Z2['baulaeufe']} Baulaeufe (verworfener Kasten darf nicht wieder vorgeschlagen werden): {r.stdout[-300:]}")
    finally: shutil.rmtree(T, ignore_errors=True)
    for f in F: print("FEHLER", f)
    print(f"test_koerper_schleife: {len(F)} Fehler"); return 1 if F else 0


def shlex_quote(s):
    import shlex; return shlex.quote(s)


if __name__ == "__main__": sys.exit(main())
