#!/usr/bin/env python3
"""formfund_pruefen.py - FORMFUND-PRUEFER (Spec modelle/archiv/SPEC_FORMFUND_TOR.md, Nutzerentscheid 11.11.).

Warum: Bei Formfunden des Nutzers (Treppe statt Saegezahn, Balkon-Stirnen) ist die Kantenmessung blind (Foto-F1 -0,002 / +0,004).
Gebraucht wird, was der Nutzer tut: Foto, Modell VORHER und Modell NACHHER nebeneinander ansehen.

Je geaendertem Teil 3-4 Fotos (Wahl wie formfamilie_pruefen.fotowahl: meiste Sichtflaeche, verschiedene Richtungen, schraeg/Stirn) plus eine
[Kontur]-Kachel (frontal entzerrt, orthografisch). Je Foto ein DREIERBILD: Fotoausschnitt | Render vorher | Render nachher (gleicher Ausschnitt,
ganzes Modell schattiert, das Teil orange). Ein Bildpruefer (`claude -p --model opus`, ein Aufruf je Runde mit allen Bildern) urteilt:
  {verbessert, erfunden, sicher: hoch|mittel|niedrig, begruendung, fotos}.
Der Befundtext kommt als FRAGE, nicht als Tatsache. Fehler/kein JSON = "ungeprueft", nie "passt".
Das Tor-Urteil steht in `urteil` ("besteht" nur bei verbessert und nicht erfunden und sicher >= mittel).

Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/formfund_pruefen.py <objekt> --vorher D --nachher D [--teile a,b] --befund "Text" --aus x.json
        [--formliste F.json] [--arbeit A] [--fotos nr,nr] [--nur_bilder]
Ohne --teile: alle Teile, deren STL zwischen vorher und nachher verschieden ist (Dateivergleich). Schreibt nichts in main, haengt nichts ein.
"""
import sys, os, json, glob, re, argparse, time, math, subprocess, hashlib, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_diff as FD, fehlteile_finden as FF, render_kern as RK, teil_fotoform as TF
import formfamilie_pruefen as FP
import foto_lokal as FL

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARBEIT_STD = "/media/oem/scan/rc-park_tmp/formfund"
PANEL = 620            # lange Seite je Bildteil (Dreierbild <= ~1900 px breit)
MIN_SICHT = FP.MIN_SICHT

PROMPT = """Du bist Bildpruefer fuer ein 3D-Modell (H0 1:87, 3D-Druck) des Gebaeudes "{objekt}". Eine Generatoraenderung hat das Bauteil/die Bauteile {teile} veraendert.
Jede der folgenden Bilddateien ist ein DREIERBILD: LINKS ein Foto (Ausschnitt), MITTE ein schattierter Render des Modells VORHER, RECHTS derselbe Render NACHHER,
alle drei aus DERSELBEN Kamera mit demselben Ausschnitt. Im Render ist das geaenderte Bauteil ORANGE, alles andere grau; dunkle Linien = Kanten/Spruenge.
Dateien mit [Kontur] sind FRONTAL-PARALLELE Ansichten ohne Perspektive: links das Foto per Homographie auf die Frontebene des Teils entzerrt (nur Dinge in der Teilebene
stimmen, Tiefenversatz verzerrt), Mitte/rechts das Modell orthografisch vorher/nachher; bei Stufen, Zacken, Bogenarten ist sie zur Entscheidung gut geeignet.
Sieh dir jede Datei mit dem Read-Werkzeug an (Bilder werden angezeigt):
{pfade}

{befundblock}
Vorgehen, in dieser Reihenfolge:
1. Beschreibe die Form im FOTO am betroffenen Merkmal (Mehrzahl der Bilder beachten; ein Foto allein kann verdeckt oder schief sein).
2. Beschreibe die Form VORHER am selben Merkmal.
3. Beschreibe die Form NACHHER am selben Merkmal.
4. Frage `verbessert`: Ist NACHHER naeher am Foto als VORHER, und zwar an diesem Merkmal (Formfamilie: Bogenart, Treppe/Saegezahn, Zahl der Elemente, Aufsatz/Gelaender/Stirn)? true/false.
5. Frage `erfunden`: Hat NACHHER etwas, das im Foto NICHT da ist (erfundene Form, falsche Bogenart, zu viele oder zu wenige Elemente, zusaetzlicher Koerper, der nirgends im Foto auftaucht)? Auch kleine Zusatzkoerper melden. true/false.
Bei NEUEN oder verschobenen Teilen pruefe zusaetzlich die LAGE gegen Nachbarelemente im Foto (sitzt das Teil auf gleicher Hoehe/Stelle wie im Foto, z. B. an der Dachkante/Traufe/Gesimskante, nicht sichtbar darueber oder darunter?). Sitzt es NACHHER sichtbar falsch (grob ueber ca. 0,3 m, in mindestens 2 Bildern erkennbar), ist `verbessert` false und die Lage steht in der Begruendung.
Nicht melden: Farbe, Textur, Feinlage von wenigen cm, Verdeckungen im Foto (Baeume, Personen, Gerueste, Nachbarhaeuser), Details unter ca. 0,3 m.
`sicher`: hoch nur, wenn dein Urteil in mindestens 2 Bildern klar zu sehen ist; ein einziges Bild oder unklare Sicht = hoechstens mittel; Vermutung = niedrig.
Wenn das Merkmal im Foto nicht erkennbar ist: verbessert=false, sicher=niedrig, das in der Begruendung sagen.

Letzte Zeile deiner Antwort GENAU (eine Zeile, gueltiges JSON, deutsche Texte):
ERGEBNIS {{"verbessert": true|false, "erfunden": true|false, "sicher": "hoch|mittel|niedrig", "begruendung": "...", "fotos": [{fotos}]}}
"""


BEFUND_MIT = """Eine Meldung (kein Beweis) lautet: "{befund}"
Behandle sie als FRAGE, nicht als Tatsache: pruefe am Foto, ob das stimmt und ob NACHHER besser ist als VORHER.
"""
# Grauzonen-Tor (SPEC_GRAUZONE_TOR.md): KEIN Befund, KEINE Absicht - nur Teilname und Bilder.
BEFUND_OHNE = """Es gibt keine Meldung und keine Absichtserklaerung. Frage: Was hat sich zwischen VORHER und NACHHER geaendert?
Ist NACHHER naeher am Foto als VORHER? Ist in NACHHER etwas erfunden? Bestimme das betroffene Merkmal selbst aus dem Unterschied der beiden Renders.
"""


def beschriften(im, text):
    return FP.beschriften(im, text)


def panel_render(img, kante, ziel, box, titel):
    """Ein Render-Teilbild (BGR) im Ausschnitt box, Teil orange."""
    x0, y0, x1, y1 = box
    g = (np.clip(img, 0, 1) * 255).astype(np.uint8); rgb = np.stack([g, g, g], 2).astype(np.float32)
    tint = np.array([40, 140, 255], np.float32)
    rgb[ziel] = rgb[ziel] * 0.35 + (0.65 * tint) * (0.35 + 0.9 * g[ziel, None].astype(np.float32) / 255.0)
    rgb[kante] = rgb[kante] * 0.25
    return np.clip(rgb, 0, 255).astype(np.uint8)[y0:y1, x0:x1]


def dreier(foto, rv, rn, titel, pfad, panel=PANEL):
    s = panel / max(foto.shape[:2]); sz = (max(2, int(foto.shape[1] * s)), max(2, int(foto.shape[0] * s)))
    f = cv2.resize(foto, sz, interpolation=cv2.INTER_AREA)
    mode = cv2.INTER_NEAREST if s > 1 else cv2.INTER_AREA
    v = cv2.resize(rv, sz, interpolation=mode); n = cv2.resize(rn, sz, interpolation=mode)
    sp = np.full((f.shape[0], 6, 3), 255, np.uint8)
    bild = np.hstack([beschriften(f, f"FOTO {titel}"), sp, beschriften(v, "VORHER (Teil orange)"), sp, beschriften(n, "NACHHER (Teil orange)")])
    cv2.imwrite(pfad, bild, [cv2.IMWRITE_JPEG_QUALITY, 90]); return pfad


def zustand_stl(d):
    return FL.stl_aus_teilen(d)


def kontur_dreier(tn, mv, mn, ctx, nr, pfad):
    """[Kontur]-Dreierbild: Foto auf Frontebene entzerrt | Ortho vorher | Ortho nachher (gleiche Ausdehnung = Vereinigung beider Staende)."""
    im0, R, t, f, cx, cy, W, H = ctx
    mu = trimesh.util.concatenate([mv, mn])
    v2 = mu.vertices[:, :2] - mu.vertices[:, :2].mean(0); ax = np.linalg.eigh(np.cov(v2.T) + 1e-9 * np.eye(2))[1][:, 1]
    nrm = np.array([-ax[1], ax[0]]); b = mu.bounds; mitte = (b[0] + b[1]) / 2
    uv = (mu.vertices[:, :2] - mitte[:2]) @ ax; ue = (float(uv.min()), float(uv.max())); ze = (float(b[0, 2]), float(b[1, 2]))
    C = -np.asarray(R, float).T @ np.asarray(t, float).ravel(); n3 = np.array([nrm[0], nrm[1], 0.0])
    seite = 1.0 if float((C - mitte) @ n3) >= 0 else -1.0
    ov, proj, (Wm, Hm) = FP.ortho_kontur(mv, ax, nrm, seite, mitte, ue, ze)
    on, proj2, _ = FP.ortho_kontur(mn, ax, nrm, seite, mitte, ue, ze)
    h_, w_ = ov.shape[:2]
    uc, zc = (ue[0] + ue[1]) / 2, (ze[0] + ze[1]) / 2; ue2 = (uc - Wm / 2, uc + Wm / 2); ze2 = (zc - Hm / 2, zc + Hm / 2)
    gs = np.linspace(0, 1, 7); G = [(u, z) for u in ue2[0] + gs * (ue2[1] - ue2[0]) for z in ze2[0] + gs * (ze2[1] - ze2[0])]
    P3 = [mitte + np.array([ax[0], ax[1], 0.0]) * u + np.array([0, 0, 1.0]) * (z - mitte[2]) for u, z in G]
    Xc = [np.asarray(R, float) @ P + np.asarray(t, float).ravel() for P in P3]
    sel = [i for i, x in enumerate(Xc) if x[2] > 1 and -0.1 * W <= f * x[0] / x[2] + cx < 1.1 * W and -0.1 * H <= f * x[1] / x[2] + cy < 1.1 * H]
    if len(sel) < 8: print(f"  Kontur {nr} {tn}: nur {len(sel)} Ebenenpunkte im Bild", flush=True); return None
    src = np.float32([[f * Xc[i][0] / Xc[i][2] + cx, f * Xc[i][1] / Xc[i][2] + cy] for i in sel]); dst = np.float32([proj(P3[i]) for i in sel])
    Hm_, _ = cv2.findHomography(src, dst, 0)
    if Hm_ is None: return None
    foto = cv2.warpPerspective(im0, Hm_, (w_, h_), flags=cv2.INTER_LINEAR, borderValue=(40, 40, 40))
    return dreier(foto, ov, on, f"{nr} [Kontur] frontal entzerrt", pfad)


class Kontext:
    """Je Foto: Bild, Kamera, Raster des GANZEN Modells vorher/nachher (gecacht, klein gehalten)."""
    def __init__(s, obj, objp, stl_real, stls, ganz):
        s.obj, s.objp, s.stl_real, s.stls, s.ganz, s.c = obj, objp, stl_real, stls, ganz, {}
    def get(s, nr, voll=True):
        if nr in s.c: return s.c[nr]
        kp = FF.k_datei(s.objp, s.obj, R0, nr); K = json.load(open(kp)); bild = glob.glob(os.path.join(R0, s.obj["fotos_dir"], nr + "_*"))
        if not bild: return None
        im0 = cv2.imread(bild[0]); im0, K = FD.foto_skalieren(im0, K); kk = K["kamera"]; im0, _ = FF.foto_entzerren(im0, kk); H, W = im0.shape[:2]
        R, t, f, _, _ = FF.kamera_laden(K, s.obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
        c = {"im0": im0, "R": R, "t": t, "f": f, "cx": cx, "cy": cy, "W": W, "H": H, "tr": TF.rahmen(s.stl_real, s.obj, kk)}
        if voll:
            for z in ("v", "n"):
                Mw = s.ganz[z].copy(); Mw.apply_translation(c["tr"]); dv, fid, _ = RK.dreiecke_rastern(Mw, R, t, f, cx, cy, W, H)
                c["dv_" + z] = dv; c["img_" + z], c["kante_" + z] = FP.schattieren(Mw, fid, dv, R)
        if len(s.c) > 4: s.c.pop(next(iter(s.c)))
        s.c[nr] = c; return c


def ersatz_sicht(mn, kam, objp, obj, nmax=12):
    """Ersatz fuer die Formliste bei Teilen ohne Eintrag: Fotos, deren Blickachse (<= 22 Grad) das Teilzentrum trifft, Wert ~ 1e8/Abstand^2 (keine Verdeckungspruefung;
    Bilder ohne sichtbares Teil fallen spaeter beim Rastern weg)."""
    ctr = mn.bounds.mean(0); ext = float(np.linalg.norm(mn.extents)); out = []
    for nr, C in kam.items():
        try:
            kk = json.load(open(FF.k_datei(objp, obj, R0, nr)))["kamera"]; Rm, _ = cv2.Rodrigues(np.array(kk["rvec"])); fw = Rm[2]
        except Exception: continue
        d = ctr - C; dist = float(np.linalg.norm(d)); cosw = float(d @ fw) / (dist + 1e-9)
        if cosw < math.cos(math.radians(22)): continue
        out.append((1e8 / dist ** 2, nr))
    return {nr: {"sicht_px": max(MIN_SICHT, v)} for v, nr in sorted(out, reverse=True)[:nmax]}


def bilder_erzeugen(tn, mv, mn, wahl, kam, fl_teil, kx, bilder_dir, kontur=True):
    """Dreierbilder je gewaehltem Foto (+ eine Kontur). Rueckgabe {etikett: pfad}."""
    out = {}
    for nr in wahl:
        c = kx.get(nr)
        if not c: continue
        m1 = mv.copy(); m1.apply_translation(c["tr"]); m2 = mn.copy(); m2.apply_translation(c["tr"])
        W, H = c["W"], c["H"]; ss = {}
        for z, m in (("v", m1), ("n", m2)):
            dp, _, _ = RK.dreiecke_rastern(m, c["R"], c["t"], c["f"], c["cx"], c["cy"], W, H)
            ss[z] = np.isfinite(dp) & (dp <= c["dv_" + z] * 1.003 + 0.03)
        uni = ss["v"] | ss["n"]
        if uni.sum() < 200: print(f"  {tn} {nr}: Teil kaum sichtbar", flush=True); continue
        # Aenderungsmaske (Silhouette-XOR): Ausschnitt nicht kleiner als das Teil, damit Kontext bleibt
        box = FP.box_aus_maske(uni, W, H)
        pf = os.path.join(bilder_dir, f"{tn}_{nr}.jpg")
        foto = c["im0"][box[1]:box[3], box[0]:box[2]].copy()
        rv = panel_render(c["img_v"], c["kante_v"], ss["v"], box, "v"); rn = panel_render(c["img_n"], c["kante_n"], ss["n"], box, "n")
        out[nr] = dreier(foto, rv, rn, nr, pf)
    if kontur:
        m0 = mn; v2 = m0.vertices[:, :2] - m0.vertices[:, :2].mean(0); ax = np.linalg.eigh(np.cov(v2.T) + 1e-9 * np.eye(2))[1][:, 1]
        nrm = np.array([-ax[1], ax[0]]); ctr = m0.bounds.mean(0); fr = []
        smax = max([v.get("sicht_px", 0) for v in fl_teil.values() if isinstance(v, dict)] + [1])
        for nr, v in fl_teil.items():
            if not isinstance(v, dict) or v.get("sicht_px", 0) < max(MIN_SICHT, 0.08 * smax) or nr not in kam: continue
            d = kam[nr][:2] - ctr[:2]; ang = math.degrees(math.acos(min(1.0, abs(float(d @ nrm)) / (np.linalg.norm(d) + 1e-9)))); fr.append((ang, nr))
        for ang, nr in sorted(fr)[:8]:
            c = kx.get(nr, voll=False)
            if not c: continue
            m1 = mv.copy(); m1.apply_translation(c["tr"]); m2 = mn.copy(); m2.apply_translation(c["tr"])
            r_ = kontur_dreier(tn, m1, m2, (c["im0"], c["R"], c["t"], c["f"], c["cx"], c["cy"], c["W"], c["H"]), nr, os.path.join(bilder_dir, f"{tn}_Kontur_{nr}.jpg"))
            if r_: out["Kontur " + nr] = r_; print(f"{tn}: Kontur Foto {nr} (Winkel zur Frontnormale {ang:.0f} Grad)", flush=True); break
    return out


def pruefer(objekt, teile, befund, paare, arbeit, modell, timeout, ohne_befund=False, logname="pruefer_formfund.log"):
    pf = "\n".join(f"- {p}" for p in paare.values()); fotos = ", ".join(f'"{k}"' for k in paare)
    p = PROMPT.format(objekt=objekt, teile=", ".join(teile), pfade=pf, befundblock=(BEFUND_OHNE if ohne_befund else BEFUND_MIT.format(befund=befund.replace('"', "'"))), fotos=fotos)
    logp = os.path.join(arbeit, logname); t0 = time.time()
    try:
        r = subprocess.run(["claude", "-p", p, "--model", modell, "--permission-mode", "plan"], cwd=arbeit, capture_output=True, text=True, timeout=timeout)
        out = r.stdout + ("\n[stderr]\n" + r.stderr if r.stderr else "")
    except subprocess.TimeoutExpired:
        open(logp, "w").write("ZEITLIMIT"); return {"status": "ungeprueft", "grund": "Zeitlimit"}
    open(logp, "w").write(out); erg = None
    for m in re.finditer(r"ERGEBNIS\s*(\{)", out):
        try: erg = json.JSONDecoder().raw_decode(out[m.start(1):])[0]
        except Exception: pass
    if not isinstance(erg, dict) or "verbessert" not in erg or "erfunden" not in erg:
        return {"status": "ungeprueft", "grund": "kein lesbares JSON (rc %s)" % r.returncode, "log": logp}
    erg["status"] = "ok"; erg["sek"] = round(time.time() - t0); erg["log"] = logp; return erg


def urteil_von(erg):
    """besteht = verbessert und nicht erfunden und sicher >= mittel; ungeprueft zaehlt NIE als bestanden."""
    if erg.get("status") != "ok": return "ungeprueft"
    if erg.get("erfunden") is True: return "erfunden"
    if erg.get("verbessert") is True and erg.get("sicher") in ("hoch", "mittel"): return "besteht"
    if erg.get("verbessert") is True: return "unsicher"
    return "nicht_verbessert"


def pruefen(objekt, vorher, nachher, befund, teile=None, aus=None, formliste=None, arbeit=ARBEIT_STD, fotos=None, n_fotos=3,
            nur_bilder=False, modell="opus", timeout=900, ohne_befund=False):
    objp = os.path.join(R0, "modelle", objekt, "objekt.json"); obj = json.load(open(objp)); name = str(obj.get("name") or objekt).split(" - ")[0]
    stl_real = os.path.join(R0, obj["stl"]); sk = obj.get("stl_massstab", 87) / 1000.0
    if teile is None:
        def sh(d, n):
            p = os.path.join(d, n + ".stl"); return hashlib.md5(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None
        alle = sorted({os.path.basename(p)[:-4] for d in (vorher, nachher) for p in glob.glob(os.path.join(d, "*.stl"))})
        teile = [n for n in alle if sh(vorher, n) != sh(nachher, n)]
    if not formliste:
        cand = sorted(glob.glob("/media/oem/scan/rc-park_kreis/%s/fotoform/*_v2_wolkenverdeckung_festbereich.json" % objekt), key=os.path.getmtime)
        cand = [c for c in cand if len(json.load(open(c)).get("teile", {})) >= 35] or cand
        formliste = cand[-1]
    FLd = json.load(open(formliste))
    os.makedirs(arbeit, exist_ok=True); bilder_dir = os.path.join(arbeit, "bilder"); os.makedirs(bilder_dir, exist_ok=True)
    print(f"geaenderte Teile: {teile}; Formliste {os.path.basename(formliste)}", flush=True)
    kam = {}
    for nr in FLd["fotos"]:
        try:
            kp = FF.k_datei(objp, obj, R0, nr); kk = json.load(open(kp))["kamera"]
            Rm, _ = cv2.Rodrigues(np.array(kk["rvec"])); kam[nr] = -Rm.T @ np.array(kk["t"], float) - TF.rahmen(stl_real, obj, kk)
        except Exception: continue
    stls = {"v": zustand_stl(vorher), "n": zustand_stl(nachher)}
    ganz = {}
    for z in ("v", "n"):
        g = trimesh.load(stls[z], force="mesh"); g.apply_scale(sk); ganz[z] = g
    kx = Kontext(obj, objp, stl_real, stls, ganz)
    paare = {}; neu = []; t0 = time.time()
    import gpu_slot; gpu_slot.belegen("formfund_pruefen")
    for tn in teile:
        pv, pn = os.path.join(vorher, tn + ".stl"), os.path.join(nachher, tn + ".stl")
        if not os.path.exists(pn): print(f"{tn}: fehlt im Nachher-Stand -> uebersprungen", flush=True); continue
        mn = trimesh.load(pn, force="mesh"); mn.apply_scale(sk)
        if os.path.exists(pv): mv = trimesh.load(pv, force="mesh"); mv.apply_scale(sk)
        else:   # NEUES Teil: im Vorher-Stand nur ein 1-mm-Platzhalter an der Ecke der Teilbox (nichts zu sehen), Hinweis an den Pruefer
            mv = trimesh.creation.box(extents=[0.01] * 3); mv.apply_translation(mn.bounds[0]); neu.append(tn); print(f"{tn}: NEUES Teil (im Vorher-Stand nicht vorhanden)", flush=True)
        fl_teil = FLd["teile"].get(tn) or ersatz_sicht(mn, kam, objp, obj)   # Teil nicht in der Formliste (z. B. neu): Naeherung aus Kamerageometrie
        wahl = FP.fotowahl(tn, fl_teil, kam, mn, n_fotos, fotos)
        print(f"{tn}: Fotos {wahl}", flush=True)
        for e, p in bilder_erzeugen(tn, mv, mn, wahl, kam, fl_teil, kx, bilder_dir).items(): paare[f"{tn} {e}"] = p
    erg = {"objekt": objekt, "teile": teile, "vorher": vorher, "nachher": nachher, "befund": befund, "formliste": formliste, "paare": paare, "sek_bilder": round(time.time() - t0)}
    if not paare: erg.update({"status": "ungeprueft", "grund": "keine Bilder"})
    elif not nur_bilder:
        bf = befund + (" [Hinweis: Bauteil %s ist im VORHER-Stand NICHT vorhanden (mittleres Bild zeigt es nicht); NACHHER fuegt es neu hinzu - pruefe, ob es im Foto wirklich existiert und so aussieht]" % ", ".join(neu) if neu else "")
        erg.update(pruefer(name, teile, bf, paare, arbeit, modell, timeout, ohne_befund)); erg["claude_aufrufe"] = 1
    else: erg["status"] = "nur_bilder"
    erg["urteil"] = urteil_von(erg); erg["sek_gesamt"] = round(time.time() - t0)
    if aus: json.dump(erg, open(aus, "w"), ensure_ascii=False, indent=1)
    return erg


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--vorher", required=True); ap.add_argument("--nachher", required=True)
    ap.add_argument("--teile", help="Komma; ohne Angabe per Dateivergleich"); ap.add_argument("--befund", default=""); ap.add_argument("--aus")
    ap.add_argument("--formliste"); ap.add_argument("--arbeit", default=ARBEIT_STD); ap.add_argument("--fotos", help="Foto-Kuerzel einschraenken (Komma)")
    ap.add_argument("--n_fotos", type=int, default=3); ap.add_argument("--nur_bilder", action="store_true"); ap.add_argument("--modell", default="opus"); ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--ohne_befund", action="store_true", help="Grauzonen-Tor: Prompt ohne Befundtext/Absicht")
    a = ap.parse_args(argv)
    e = pruefen(a.objekt, a.vorher, a.nachher, a.befund, a.teile.split(",") if a.teile else None, a.aus, a.formliste, a.arbeit,
                a.fotos.split(",") if a.fotos else None, a.n_fotos, a.nur_bilder, a.modell, a.timeout, a.ohne_befund)
    print(json.dumps({k: e.get(k) for k in ("urteil", "verbessert", "erfunden", "sicher", "begruendung", "claude_aufrufe", "sek_gesamt")}, ensure_ascii=False, indent=1))
    return e


if __name__ == "__main__":
    main()
