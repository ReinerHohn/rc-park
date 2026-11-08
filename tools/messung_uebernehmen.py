#!/usr/bin/env python3
"""messung_uebernehmen.py <objekt> [--anwenden]
Uebernimmt die BESTAETIGTEN Direktmessungen aus <objekt>/messungen_wolke.json (tools/messen_interaktiv.py) in die Parameter von objekt.json.
Standard = PROBELAUF (zeigt Tabelle alt -> neu mit Quelle, schreibt nichts). --anwenden: Sicherung objekt.json.mess_bak, Werte + werte_quellen (Regel 3b) schreiben.
Zuordnung (Definitionen aus tools/baukasten_gen.py):
  spitze_links/rechts, turm_links/rechts_unten -> erker:1 / erker:0: spitze_z, unterkante_z, mitte_u (Mittel aus Spitzen-u und Kasten-u, Warnung bei Differenz > 0,6 m)
  bogen1..4_scheitel -> bogenreihe: u_k = u0 + (n-k+0,5)*pitch (Bogen 1 = links im Foto = groesstes u, Ausgleich nach kleinsten Quadraten), scheitel_z = Mittel z;
     ANNAHME: kaempfer_z/oberkante_z werden mit dem Scheitel mitgefuehrt (gleiche relative Lage zwischen boden_z und scheitel_z), damit boden<kaempfer<scheitel<oberkante gilt
  first_links/rechts -> satteldach: u1/u0, z_first (Mittel), n_first (Mittel);  traufe_links/rechts -> z_traufe_v (Mittel), n_traufe_v (Mittel)
  boden_mitte -> bogenreihe boden_z
Nur Parameter, zu denen mindestens die noetigen Messungen vorliegen. Danach: Modell bauen, Tor (teil_tor.py/Gesamtscore), Overlay ansehen."""
import sys, os, json, argparse, shutil, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--anwenden", action="store_true"); a = ap.parse_args()
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OD = os.path.join(R, "modelle", a.objekt); OJ = os.path.join(OD, "objekt.json")
M = {e["id"]: e for e in json.load(open(os.path.join(OD, "messungen_wolke.json")))}; O = json.load(open(OJ)); B = {b["typ"]: b for b in O["bauteile"]}
neu = {}      # (typ, param) -> (wert, quelle, hinweis)
SCHWACH = {}
def g(i, k):
    """Messwert; None bei schwacher Messung (< 30 Wolkenpunkte oder Box vergroessert) - dann wird sie NICHT uebernommen (Nutzerbefund 8.11.: first_links z 25,7 aus 22 Punkten im Himmel)"""
    if i not in M: return None
    m = M[i]["mess"]
    if m.get("punkte", 99) < 30 or (m.get("box_erweitert") or 1) > 1.0: SCHWACH[i] = "%d Punkte, Box x%s" % (m.get("punkte", 0), m.get("box_erweitert") or 1); return None
    return m[k]
def beleg(ids): ids = [i for i in ids if i not in SCHWACH]; return "messungen_wolke.json " + ",".join(i for i in ids if i in M) + " (Wolke, Gegenproben bestaetigt)"
def setze(typ, p, v, ids, hinweis=""):
    if typ in B and v is not None: neu[(typ, p)] = (round(float(v), 3), beleg(ids), hinweis)

for typ, sp, un in (("erker:1", "spitze_links", "turm_links_unten"), ("erker:0", "spitze_rechts", "turm_rechts_unten")):
    us, uu = g(sp, "u"), g(un, "u"); setze(typ, "spitze_z", g(sp, "z"), [sp]); setze(typ, "unterkante_z", g(un, "z"), [un])
    if us is not None and uu is not None: setze(typ, "mitte_u", (us + uu) / 2, [sp, un], "" if abs(us - uu) <= 0.6 else "WARNUNG: Spitzen-u und Kasten-u weichen %.2f m ab" % abs(us - uu))
    elif us is not None: setze(typ, "mitte_u", us, [sp], "nur Spitzen-u")
br = B.get("bogenreihe:laube")
if br:
    nb = int(br["n_boegen"]); ks = [k for k in range(1, nb + 1) if "bogen%d_scheitel" % k in M]
    if len(ks) >= 2:
        A = np.array([[1.0, nb - k + 0.5] for k in ks]); y = np.array([g("bogen%d_scheitel" % k, "u") for k in ks]); (u0, pitch), *_ = np.linalg.lstsq(A, y, rcond=None); res = float(np.sqrt(np.mean((A @ [u0, pitch] - y) ** 2)))
        ids = ["bogen%d_scheitel" % k for k in ks]; setze("bogenreihe:laube", "u0", u0, ids, "Ausgleich %d Boegen, Rest %.2f m" % (len(ks), res)); setze("bogenreihe:laube", "pitch", pitch, ids)
    if ks:
        zs = float(np.mean([g("bogen%d_scheitel" % k, "z") for k in ks])); ids = ["bogen%d_scheitel" % k for k in ks]; zb = g("boden_mitte", "z") if "boden_mitte" in M else None
        if zb is None: zb = br["boden_z"]
        elif "boden_mitte" in M: setze("bogenreihe:laube", "boden_z", zb, ["boden_mitte"])
        setze("bogenreihe:laube", "scheitel_z", zs, ids); f = (zs - zb) / max(br["scheitel_z"] - br["boden_z"], 0.1)
        setze("bogenreihe:laube", "kaempfer_z", zb + (br["kaempfer_z"] - br["boden_z"]) * f, ids, "ANNAHME: relative Lage zwischen Boden und Scheitel beibehalten")
        setze("bogenreihe:laube", "oberkante_z", zb + (br["oberkante_z"] - br["boden_z"]) * f, ids, "ANNAHME: relative Lage zwischen Boden und Scheitel beibehalten")
da = B.get("satteldach:haupt")
if da:
    fl, fr, tl, tr = (M.get(i) for i in ("first_links", "first_rechts", "traufe_links", "traufe_rechts"))
    if fl: setze("satteldach:haupt", "u1", g("first_links", "u"), ["first_links"], "ANNAHME: Firstende = Dachende in u (kein Walm)")
    if fr: setze("satteldach:haupt", "u0", g("first_rechts", "u"), ["first_rechts"], "ANNAHME: Firstende = Dachende in u (kein Walm)")
    fz = [v for v in (g(i, "z") for i in ("first_links", "first_rechts") if i in M) if v is not None]; fn = [v for v in (g(i, "n") for i in ("first_links", "first_rechts") if i in M) if v is not None]
    tz = [v for v in (g(i, "z") for i in ("traufe_links", "traufe_rechts") if i in M) if v is not None]; tn = [v for v in (g(i, "n") for i in ("traufe_links", "traufe_rechts") if i in M) if v is not None]
    if fz: setze("satteldach:haupt", "z_first", np.mean(fz), ["first_links", "first_rechts"]); setze("satteldach:haupt", "n_first", np.mean(fn), ["first_links", "first_rechts"])
    if tz: setze("satteldach:haupt", "z_traufe_v", np.mean(tz), ["traufe_links", "traufe_rechts"]); setze("satteldach:haupt", "n_traufe_v", np.mean(tn), ["traufe_links", "traufe_rechts"])

# --- an die Arkade gekoppelte Teile (ANNAHME: folgen den Boegen) und Fensterband/Balkon aus eigenen Messungen
if br and ("bogenreihe:laube", "u0") in neu:
    nu0, npi = neu[("bogenreihe:laube", "u0")][0], neu[("bogenreihe:laube", "pitch")][0]; nb_ = int(br["n_boegen"]); ou0, opi = float(br["u0"]), float(br["pitch"]); pbr = float(br["pfeiler_breite"])
    import subprocess
    try: AO = json.loads(subprocess.run(["git", "show", "HEAD:modelle/%s/objekt.json" % a.objekt], cwd=R, capture_output=True, text=True, check=True).stdout); Ab = [x for x in AO["bauteile"] if x["typ"] == "bogenreihe:laube"][0]; AU0, API = float(Ab["u0"]), float(Ab["pitch"])
    except Exception: AU0, API = ou0, opi
    if "quader:laube_rueck" in B: setze("quader:laube_rueck", "u0", nu0 - pbr / 2, [], "ANNAHME: Rueckwand spannt die Arkade (aus Bogenreihe u0/pitch)"); setze("quader:laube_rueck", "u1", nu0 + nb_ * npi + pbr / 2, [], "ANNAHME: Rueckwand spannt die Arkade")
    for t, b in B.items():
        if t.startswith("fensterreihe:eg") and b.get("aktiv", True):
            if b.get("bucht") is not None: i = int(b["bucht"])
            else: i = int(round((float(b["u_mitte"]) - AU0) / API - 0.5)); i = min(max(i, 0), nb_ - 1)     # naechste ALTE Bogenmitte (Arkade vor den Messungen, git HEAD) -> gleiche Bucht
            setze(t, "bucht", i, [], "Bucht von rechts (0 = rechts), einmal aus alter Arkade bestimmt"); setze(t, "u_mitte", nu0 + (i + 0.5) * npi, [], "ANNAHME: Fenster bleibt in Bucht %d (von rechts) der Arkade" % (i + 1))
fo = B.get("fensterreihe:og")
if fo and "fensterband_links_aussen" in M and "fensterband_rechts_aussen" in M:
    uL, uR = g("fensterband_links_aussen", "u"), g("fensterband_rechts_aussen", "u"); nf = int(fo["n_fenster"]); bw = float(fo["breite"]); ids = ["fensterband_links_aussen", "fensterband_rechts_aussen"]
    setze("fensterreihe:og", "u_mitte", uR + bw / 2, ids, "kleinste u = rechtes Fenster im Foto"); setze("fensterreihe:og", "pitch", (uL - uR - bw) / (nf - 1), ids, "Aussenraender -> %d Fenster (Anzahl am Foto gezaehlt)" % nf)
# Fensterreihe OG aus Fenstermitten (Punkte/Rechtecke, fenster_og_1 = links im Foto = groesstes u): u_mitte = rechtes Fenster, pitch per Ausgleich, Mitte z -> Hoehenversatz der Fensterform (Hoehe/Breite bleiben)
ks = [k for k in range(1, 9) if "fenster_og_%d" % k in M and g("fenster_og_%d" % k, "u") is not None]
if fo and len(ks) >= 3:
    ids = ["fenster_og_%d" % k for k in ks]; nf = int(fo["n_fenster"]); us = [g(i, "u") for i in ids]
    if all(v is not None for v in us):
        A = np.array([[1.0, nf - k] for k in ks]); (u0, pitch), *_ = np.linalg.lstsq(A, np.array(us), rcond=None); res = float(np.sqrt(np.mean((A @ [u0, pitch] - us) ** 2)))
        setze("fensterreihe:og", "u_mitte", u0, ids, "Ausgleich %d Fenstermitten, Rest %.2f m (u_mitte = rechtes Fenster)" % (len(ks), res)); setze("fensterreihe:og", "pitch", pitch, ids)
        zm = float(np.mean([g(i, "z") for i in ids])); zc = (float(fo["unterseite_z"]) + float(fo["scheitel_z"])) / 2; dz = zm - zc
        for p_ in ("unterseite_z", "kaempfer_z", "scheitel_z", "riegel_z"): setze("fensterreihe:og", p_, float(fo[p_]) + dz, ids, "ANNAHME: Fensterform unveraendert, Mitte z auf gemessene Mitte %.2f (Punkt in Fenstermitte)" % zm)
        wn = [g(i, "n") for i in ids]; setze("fensterreihe:og", "wand_n", np.mean(wn) - float(fo["tiefe"]) / 2 if False else np.mean(wn), ids, "Wolkenflaeche (Glas/Wand) n")
ba = B.get("balkonband:haupt")
if ba and "balkon_links_ende" in M and "balkon_rechts_ende" in M:
    ids = ["balkon_links_ende", "balkon_rechts_ende"]; setze("balkonband:haupt", "u_bis", g("balkon_links_ende", "u"), ids); setze("balkonband:haupt", "u_von", g("balkon_rechts_ende", "u"), ids)
    bz = [v for v in (g(i, "z") for i in ids) if v is not None]
    if bz: setze("balkonband:haupt", "oberseite_z", np.mean(bz), ids, "Oberkante Bruestung")

# --- statische Helm-Gruppen (stl_teil:helme_*): Spitze -> du, Spitze/Unterkante -> dz, sz (dn bleibt: gemessene Vorderflaeche != Helmachse)
import trimesh
KS = 1000 / 87
for typ, b in B.items():
    if not typ.startswith("stl_teil:helme") or b.get("aktiv") is False: continue
    n_ = np.array(b["achse_n"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
    P = np.vstack([np.asarray(trimesh.load(f, process=False).vertices) for f in b["dateien"]]) / KS; lo, hi = P.min(0), P.max(0); A = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]); d = P - A
    cu = d[:, :2] @ u_ * float(b.get("su", 1.0)) + float(b.get("du", 0.0)); cz = d[:, 2] * float(b.get("sz", 1.0)) + float(b.get("dz", 0.0)); i = int(cz.argmax()); tip_u = (A[:2] + (d[i, :2] @ n_) * 0 )[0] * 0 + (A[:2] @ u_) + cu[i]
    sp = [(abs(g(k, "u") - tip_u), k) for k in ("spitze_links", "spitze_rechts") if k in M]; un = {"spitze_links": "turm_links_unten", "spitze_rechts": "turm_rechts_unten"}
    if not sp: continue
    k = min(sp)[1]; ids = [k] + ([un[k]] if un[k] in M else [])
    setze(typ, "du", float(b.get("du", 0.0)) + g(k, "u") - tip_u, [k], "Helmspitze (u %.2f) auf gemessene Spitze %s" % (tip_u, k))
    zu = g(un[k], "z") if un[k] in M else float(A[2]) + float(b.get("dz", 0.0)); zs = g(k, "z"); h0 = float(hi[2] - lo[2])
    setze(typ, "dz", zu - float(A[2]), ids, "Unterkante auf Messung" if un[k] in M else "Unterkante unveraendert"); setze(typ, "sz", (zs - zu) / h0, ids, "Spitze z %.2f, Unterkante z %.2f" % (zs, zu))

for i, w in SCHWACH.items(): print("SCHWACHE MESSUNG NICHT UEBERNOMMEN:", i, "-", w)
if not neu: sys.exit("keine uebernehmbaren Messungen in messungen_wolke.json")
print("%-18s %-14s %10s %10s  %s" % ("Bauteil", "Parameter", "alt", "neu", "Quelle / Hinweis"))
for (t, p), (v, q, h) in neu.items(): print("%-18s %-14s %10s %10.3f  %s %s" % (t, p, B[t].get(p), v, q.split(" (")[0], ("| " + h) if h else ""))
# Plausibilitaet nach Generator-Regeln (vor dem Schreiben)
fehler = []
for t, b in B.items():
    c = dict(b); c.update({p: v for (tt, p), (v, _, _) in neu.items() if tt == t})
    if t.startswith("erker") and not (c["unterkante_z"] < c["oberkante_z"] < c["spitze_z"]): fehler.append("%s: unterkante %.2f < oberkante %.2f < spitze %.2f verletzt (oberkante_z nicht gemessen)" % (t, c["unterkante_z"], c["oberkante_z"], c["spitze_z"]))
    if t == "bogenreihe:laube" and not (c["boden_z"] < c["kaempfer_z"] < c["scheitel_z"] < c["oberkante_z"]): fehler.append("bogenreihe: z-Reihenfolge verletzt")
    if t == "satteldach:haupt" and not (c["u1"] - c["u0"] > 1 and c["z_traufe_v"] < c["z_first"]): fehler.append("satteldach: u1-u0 oder Traufe<First verletzt")
for f in fehler: print("PLAUSIBILITAET:", f)
warn = [h for (_, _, h) in neu.values() if h.startswith("WARNUNG")]
if not a.anwenden: print("\nPROBELAUF - nichts geschrieben. Mit --anwenden uebernehmen (Sicherung objekt.json.mess_bak)."); sys.exit(0)
if fehler: sys.exit("nicht angewendet: Plausibilitaet verletzt")
shutil.copy(OJ, OJ + ".mess_bak")
for (t, p), (v, q, h) in neu.items(): B[t][p] = v; B[t].setdefault("werte_quellen", {})[p] = q + (" | " + h if h else "")
json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False); print("\nangewendet: %d Parameter (Sicherung objekt.json.mess_bak). Naechster Schritt: bauen, Tor, Overlay." % len(neu))
