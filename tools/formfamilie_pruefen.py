#!/usr/bin/env python3
"""formfamilie_pruefen.py - FORMFAMILIEN-SICHTPRUEFUNG JE BAUTEIL (Spec modelle/SPEC_FORMFAMILIE_SICHTPRUEFUNG.md, Nutzerauftrag 11.11.).

Warum: Die Kantenmessung (Foto-F1) misst Kantendichte, keine Formfamilie (Lehren L46/L47): Saegezahn statt Treppe, spitz statt rund, Rechteck statt Bogen,
zu niedriger Sockel, fehlende Aufsaetze/Gelaender blieben im Kreis unbemerkt. Hier tut das Werkzeug, was der Nutzer tut: Foto und Modell-Render
nebeneinander ansehen und NUR die Formfamilie vergleichen.

Ablauf je Teil:
  1. 3-4 Fotos mit grosser sichtbarer Teilflaeche (sicht_px der Formliste), verschiedene Blickrichtungen (>= 25 Grad), moeglichst ein schraeges.
  2. Bildpaar je Foto: links Fotoausschnitt (entzerrt, Teilbox + 30 % Rand), rechts normalen-schattierter Render des GANZEN Modells aus derselben Kamera,
     gleicher Ausschnitt, Zielteil orange, Rest grau, Kanten an Flaechen-/Tiefensprung dunkel.
  3. Bildpruefer `claude -p --model opus` liest die Paare (Read-Werkzeug) und liefert JSON. Fehler/kein JSON = "ungeprueft", nie "passt".
Ausgabe: <arbeit>/formfamilie.json, <arbeit>/bilder/. Schreibt NICHT in masstabelle.json, haengt nichts in den Kreis ein.

Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/formfamilie_pruefen.py <objekt> --teile_dir D --formliste F.json [--teile a,b] [--arbeit A] [--nur_bilder]
Der Prompt kennt KEINE Sollbefunde (Selbstbezug-Verbot); er nennt nur die Formfamilien-Kategorien und den Teilnamen.
"""
import sys, os, json, glob, re, argparse, time, math, subprocess, threading, numpy as np, cv2, trimesh
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_diff as FD, fehlteile_finden as FF, render_kern as RK, teil_fotoform as TF

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARBEIT_STD = "/media/oem/scan/rc-park_tmp/formfamilie"
PANEL = 880           # lange Seite je Bildhaelfte (Paar <= ~1800 px breit)
RAND = 0.30           # Rand um die projizierte Teilbox
MIN_WINKEL = 25.0     # Grad Unterschied der Blickrichtungen
MIN_SICHT = 2500      # sichtbare Teilpixel, darunter kein Kandidat

PROMPT = """Du bist Bildpruefer fuer ein 3D-Modell (H0 1:87, 3D-Druck) des Gebaeudes "{objekt}". Pruefe das Bauteil "{teil}".
Jede der folgenden Bilddateien ist ein Paar: LINKS ein Foto (Ausschnitt um das Bauteil), RECHTS ein schattierter Render des Modells aus DERSELBEN Kamera mit
demselben Ausschnitt. Im Render ist das zu pruefende Bauteil ORANGE, alle anderen Bauteile grau; dunkle Linien = Kanten/Sprunge. Nur das orange Bauteil beurteilen.
Oben im Bild steht das Foto-Kuerzel. Sieh dir jede Datei mit dem Read-Werkzeug an (Bilder werden angezeigt):
{pfade}

Vorgehen: Beschreibe ERST die Form des Bauteils im Foto, DANN die Form im Modell (Mehrzahl der Bilder beachten, ein Foto allein kann verdeckt oder schief sein).
Gehe dafuer bei jedem Bauteil einen Pflicht-Rundgang durch und vergleiche je Station Foto gegen Modell (auch wenn alles gleich aussieht, notiere kurz in "form_*"):
 (1) Fuss/Sockel/Auflager: Grundrissform (rund, achteckig ...), Hoehe im Verhaeltnis zur Schaftdicke bzw. Elementbreite - schaetze das Verhaeltnis in Foto und Modell als Zahl;
 (2) Schaft/Koerper: Querschnitt, Gliederung (glatt, gerillt, gedreht, Rippen), Proportion Hoehe zu Breite als Zahl;
 (3) Oeffnungen (Bogen, Fenster, Tor, Durchgang, auch an den Enden/Seitenflaechen des Bauteils): Umriss jeder Oeffnung - Halbkreis, Spitzbogen, Segmentbogen oder Rechteck;
 (4) Obere Kontur/Abschluss: bei Treppen/Zacken/Daechern fuer jede Stufe die Oberseite (waagerecht oder schraeg) und die Vorderkante (senkrecht oder schraeg), Abdeckungen, Aufsaetze, Bekroenungen;
 (5) Enden und Seiten: ist das Bauteil an den Enden offen, zugemauert, mit Seitenteilen/Gelaender abgeschlossen oder stumpf abgeschnitten;
 (6) Anzahl und Anordnung gleicher Elemente: zaehle in Foto und Modell.
Nenne dann NUR Abweichungen der FORMFAMILIE, naemlich:
- Bogenart (rund, spitz, gerade/Rechteck, Segmentbogen, Kleeblatt ...)
- Stufen: Treppe (waagerechte Stufen) oder Zacke/Saegezahn oder Dach/Schraege
- Anzahl gleicher Elemente (Bogen, Fenster, Saeulen, Stufen ...)
- fehlende oder erfundene Elemente (Sockel, Aufsatz, Gelaender, Stirn/Seitenteil, Rippen, Masswerk, Pfosten ...)
- Proportion: wenn deine geschaetzten Verhaeltniszahlen aus dem Rundgang (Foto gegen Modell) um mehr als etwa 15 % abweichen, melde sie (bei 15-30 % hoechstens "mittel", darueber "hoch", wenn in 2 Bildern gleich)
NICHT melden: Farbe, Textur, Feinlage (wenige cm), Schmutz, Verdeckungen im Foto (Baeume, Personen, Schilder, Geruest, Nachbarhaeuser),
Teile, die im Foto gar nicht zu sehen sind, Details unter ca. 0,3 m Modellgroesse. Gib "sicher" nur mit "hoch", wenn die Abweichung in mindestens 2 Bildern
klar zu sehen ist; ein einziges Bild oder unklare Sicht = hoechstens "mittel"; Vermutung = "niedrig". Wenn Foto und Modell in der Formfamilie passen,
ist die Liste der Abweichungen LEER - erfinde nichts. Wenn das Bauteil im Foto nicht erkennbar ist, melde das in "form_foto" und lasse die Liste leer.

Letzte Zeile deiner Antwort GENAU (eine Zeile, gueltiges JSON, deutsche Texte):
ERGEBNIS {{"teil": "{teil}", "fotos": [{fotos}], "form_foto": "...", "form_modell": "...", "abweichungen": [{{"merkmal": "...", "foto": "...", "modell": "...", "fotos_belegt": ["..."], "sicher": "hoch|mittel|niedrig"}}]}}
"""


def winkel_diff(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def fotowahl(teil, je_foto, kam, mesh_w, n=4, nur_fotos=None):
    """je_foto: {foto: {sicht_px,...}} aus der Formliste; kam: {foto: (Zentrum xyz im Modellrahmen)}; mesh_w: Teilnetz im Modellrahmen.
    Greedy: bestes sicht_px, dann jeweils das beste mit >= MIN_WINKEL Abstand zu allen gewaehlten; ein schraeges Foto wird bevorzugt eingetauscht, falls keins gewaehlt."""
    kand = [(v["sicht_px"], f) for f, v in je_foto.items() if isinstance(v, dict) and v.get("sicht_px", 0) >= MIN_SICHT and f in kam and (not nur_fotos or f in nur_fotos)]
    kand.sort(reverse=True)
    if not kand: return []
    ctr = mesh_w.bounds.mean(0)
    v = mesh_w.vertices[:, :2] - mesh_w.vertices[:, :2].mean(0); w, V = np.linalg.eigh(np.cov(v.T) + 1e-9 * np.eye(2))
    ax = V[:, 1]; nrm = np.array([-ax[1], ax[0]]); naz = math.degrees(math.atan2(nrm[1], nrm[0]))   # Teilflaechennormale (waagerecht), Vorzeichen egal
    az = {f: math.degrees(math.atan2(kam[f][1] - ctr[1], kam[f][0] - ctr[0])) for _, f in kand}
    def schraeg(f):
        d = min(winkel_diff(az[f], naz), winkel_diff(az[f], naz + 180)); return 25.0 <= d <= 75.0
    kand = kand[:14]; wahl = []
    for s, f in kand:
        if all(winkel_diff(az[f], az[g]) >= MIN_WINKEL for g in wahl): wahl.append(f)
        if len(wahl) == n: break
    if not any(schraeg(f) for f in wahl):
        for s, f in kand:
            if f not in wahl and schraeg(f) and all(winkel_diff(az[f], az[g]) >= MIN_WINKEL for g in wahl[:-1]):
                wahl = wahl[:-1] + [f] if len(wahl) >= n else wahl + [f]; break
    return wahl


def schattieren(Mw, fid, dv, R, hell=None):
    """Graustufen-Schattierung (Float 0..1) aus Dreiecksnormalen: Scheinwerfer + Seitenlicht; dunkle Linien an Dreiecks-Gruppen-/Tiefensprung."""
    Nc = np.asarray(Mw.face_normals) @ R.T                        # Normalen im Kamerarahmen (z = Blickrichtung, y nach unten)
    ok = fid >= 0; n = np.zeros(fid.shape + (3,), np.float32); n[ok] = Nc[fid[ok]]
    flip = n[..., 2] > 0; n[flip] *= -1                          # zur Kamera drehen
    kopf = np.clip(-n[..., 2], 0, 1)
    L = np.array([-0.45, -0.65, -0.62]); L /= np.linalg.norm(L); seite = np.clip(n @ (-L), 0, 1)
    g = 0.18 + 0.42 * kopf + 0.40 * seite
    img = np.where(ok, g, 0.93).astype(np.float32)
    # Kanten: Normalensprung (> ~25 Grad) und Tiefensprung (> 4 %)
    nn = n.copy(); dx = np.linalg.norm(nn[:, 1:] - nn[:, :-1], axis=2); dy = np.linalg.norm(nn[1:] - nn[:-1], axis=2)
    kante = np.zeros(fid.shape, bool); kante[:, 1:] |= dx > 0.42; kante[1:] |= dy > 0.42
    dd = np.where(np.isfinite(dv), dv, 0.0)
    rx = np.abs(dd[:, 1:] - dd[:, :-1]) > 0.04 * np.maximum(dd[:, 1:], 0.5); ry = np.abs(dd[1:] - dd[:-1]) > 0.04 * np.maximum(dd[1:], 0.5)
    kante[:, 1:] |= rx; kante[1:] |= ry
    return img, kante


def box_aus_maske(m, W, H):
    ys, xs = np.where(m)
    if len(xs) == 0: return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    bw, bh = x1 - x0 + 1, y1 - y0 + 1; s = max(bw, bh)
    bw2, bh2 = max(bw, 0.25 * s) * (1 + 2 * RAND), max(bh, 0.25 * s) * (1 + 2 * RAND)
    cx_, cy_ = (x0 + x1) / 2, (y0 + y1) / 2
    return (int(max(0, cx_ - bw2 / 2)), int(max(0, cy_ - bh2 / 2)), int(min(W, cx_ + bw2 / 2)), int(min(H, cy_ + bh2 / 2)))


def beschriften(im, text):
    cv2.rectangle(im, (0, 0), (im.shape[1], 26), (0, 0, 0), -1)
    cv2.putText(im, text, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA); return im


def bildpaar(foto_bgr, render_gr, kante, ziel, box, titel, pfad):
    x0, y0, x1, y1 = box
    f = foto_bgr[y0:y1, x0:x1].copy()
    g = (np.clip(render_gr, 0, 1) * 255).astype(np.uint8)
    rgb = np.stack([g, g, g], 2).astype(np.float32)
    tint = np.array([40, 140, 255], np.float32)                  # BGR orange
    rgb[ziel] = rgb[ziel] * 0.35 + (0.65 * tint) * (0.35 + 0.9 * g[ziel, None].astype(np.float32) / 255.0)
    rgb[kante] = rgb[kante] * 0.25
    r = np.clip(rgb, 0, 255).astype(np.uint8)[y0:y1, x0:x1]
    s = PANEL / max(f.shape[:2]); sz = (max(2, int(f.shape[1] * s)), max(2, int(f.shape[0] * s)))
    f = cv2.resize(f, sz, interpolation=cv2.INTER_AREA); r = cv2.resize(r, sz, interpolation=cv2.INTER_NEAREST if s > 1 else cv2.INTER_AREA)
    paar = np.hstack([beschriften(f, f"FOTO {titel}"), np.full((f.shape[0], 6, 3), 255, np.uint8), beschriften(r, f"MODELL (Teil orange) {titel}")])
    cv2.imwrite(pfad, paar, [cv2.IMWRITE_JPEG_QUALITY, 90]); return pfad


def bilder_erzeugen(a, obj, objp, teile_pfade, wahl, formliste_teile, bilder_dir):
    """wahl: {teil: [fotos]}. Rastert je Foto das ganze Modell einmal, dann je Teil. Rueckgabe {teil: {foto: pfad}}."""
    stl = a.stl or os.path.join(R0, obj["stl"]); sk = obj.get("stl_massstab", 87) / 1000.0
    ganz = trimesh.load(stl, force="mesh"); ganz.apply_scale(sk)
    TM = {}
    def teilnetz(t):
        if t not in TM:
            m = trimesh.load(teile_pfade[t], force="mesh"); m.apply_scale(sk); TM[t] = m
        return TM[t]
    je_foto = {}
    for t, fl in wahl.items():
        for f in fl: je_foto.setdefault(f, []).append(t)
    out = {t: {} for t in wahl}
    for nr, ts in je_foto.items():
        vorh = {tn: os.path.join(bilder_dir, f"{tn}_{nr}.jpg") for tn in ts}
        if not a.bilder_neu and all(os.path.exists(v) for v in vorh.values()):   # Bilder dieses Fotos schon da (Wiederaufnahme)
            for tn, v in vorh.items(): out[tn][nr] = v
            continue
        kp = FF.k_datei(objp, obj, R0, nr); K = json.load(open(kp))
        bild = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))
        if not bild: continue
        im0 = cv2.imread(bild[0]); im0, K = FD.foto_skalieren(im0, K); kk = K["kamera"]
        im0, _ = FF.foto_entzerren(im0, kk); H, W = im0.shape[:2]
        R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
        tr = TF.rahmen(stl, obj, kk)
        Mw = ganz.copy(); Mw.apply_translation(tr)
        dv, fid, _ = RK.dreiecke_rastern(Mw, R, t, f, cx, cy, W, H)
        img, kante = schattieren(Mw, fid, dv, R)
        for tn in ts:
            m = teilnetz(tn).copy(); m.apply_translation(tr)
            dp, _, _ = RK.dreiecke_rastern(m, R, t, f, cx, cy, W, H)
            ziel = np.isfinite(dp) & (dp <= dv * 1.003 + 0.03)
            if ziel.sum() < 200: continue
            box = box_aus_maske(ziel, W, H)
            pf = os.path.join(bilder_dir, f"{tn}_{nr}.jpg")
            out[tn][nr] = bildpaar(im0, img, kante, ziel, box, nr, pf)
        print(f"Foto {nr}: {len(ts)} Teile gerendert", flush=True)
    return out


OBJ_NAME = "Gebaeude"   # aus objekt.json["name"] (main), kein Objektname im Code


def pruefer(teil, paare, arbeit, modell, timeout):
    """Ein claude-Aufruf je Teil. Rueckgabe dict mit 'status' ok|ungeprueft."""
    pf = "\n".join(f"- {p}" for p in paare.values()); fotos = ", ".join(f'"{k}"' for k in paare)
    p = PROMPT.format(teil=teil, pfade=pf, fotos=fotos, objekt=OBJ_NAME)
    logp = os.path.join(arbeit, "pruefer", f"{teil}.log"); os.makedirs(os.path.dirname(logp), exist_ok=True)
    t0 = time.time()
    try:
        r = subprocess.run(["claude", "-p", p, "--model", modell, "--permission-mode", "plan"], cwd=arbeit, capture_output=True, text=True, timeout=timeout)
        out = r.stdout + ("\n[stderr]\n" + r.stderr if r.stderr else "")
    except subprocess.TimeoutExpired:
        open(logp, "w").write("ZEITLIMIT"); return {"teil": teil, "status": "ungeprueft", "grund": "Zeitlimit"}
    open(logp, "w").write(out)
    erg = None
    for m in re.finditer(r"ERGEBNIS\s*(\{)", out):
        try: erg = json.JSONDecoder().raw_decode(out[m.start(1):])[0]
        except Exception: pass
    if not isinstance(erg, dict) or "abweichungen" not in erg:
        return {"teil": teil, "status": "ungeprueft", "grund": "kein lesbares JSON (rc %s)" % r.returncode, "log": logp}
    erg["status"] = "ok"; erg["sek"] = round(time.time() - t0); erg["log"] = logp; erg["paare"] = paare
    return erg


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--teile_dir", required=True); ap.add_argument("--formliste", required=True)
    ap.add_argument("--teile", help="Komma; ohne Angabe alle Teile der Formliste"); ap.add_argument("--arbeit", default=ARBEIT_STD)
    ap.add_argument("--stl"); ap.add_argument("--fotos_je_teil", type=int, default=4); ap.add_argument("--nur_bilder", action="store_true")
    ap.add_argument("--modell", default="opus"); ap.add_argument("--parallel", type=int, default=11); ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--neu", action="store_true", help="Pruefer-Ergebnisse im Arbeitsordner nicht wiederverwenden")
    ap.add_argument("--bilder_neu", action="store_true", help="vorhandene Bildpaare neu rendern")
    ap.add_argument("--fotos", help="Foto-Kuerzel erzwingen/einschraenken (Komma)")
    a = ap.parse_args(argv)
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp)); global OBJ_NAME; OBJ_NAME = str(obj.get("name") or a.objekt).split(" - ")[0]
    FL = json.load(open(a.formliste))
    stl = a.stl or os.path.join(R0, obj["stl"]); sk = obj.get("stl_massstab", 87) / 1000.0
    import hashlib
    sha = hashlib.sha256(open(stl, "rb").read()).hexdigest()[:16]
    if FL.get("stl_sha") != sha: print(f"WARNUNG: Formliste stl_sha {FL.get('stl_sha')} != {sha} (aktuelles Modell)", flush=True)
    os.makedirs(os.path.join(a.arbeit, "bilder"), exist_ok=True); bilder_dir = os.path.join(a.arbeit, "bilder")
    teile_pfade = {os.path.basename(p)[:-4]: p for p in glob.glob(os.path.join(a.teile_dir, "*.stl"))}
    namen = a.teile.split(",") if a.teile else sorted(FL["teile"])
    namen = [n for n in namen if n in teile_pfade and n in FL["teile"]]
    # Kamerazentren im Modellrahmen: C = -R^T t - Rahmenverschiebung (Teilnetze liegen ohne Verschiebung vor)
    kam = {}
    for nr in FL["fotos"]:
        try:
            kp = FF.k_datei(objp, obj, R0, nr); K = json.load(open(kp)); kk = K["kamera"]
            R, _ = cv2.Rodrigues(np.array(kk["rvec"])); C = -R.T @ np.array(kk["t"], float)
            kam[nr] = C - TF.rahmen(stl, obj, kk)
        except Exception: continue
    wahl = {}
    for n in namen:
        m = trimesh.load(teile_pfade[n], force="mesh"); m.apply_scale(sk)
        wahl[n] = fotowahl(n, FL["teile"][n], kam, m, a.fotos_je_teil, a.fotos.split(",") if a.fotos else None)
        print(f"{n}: Fotos {wahl[n]}", flush=True)
    t0 = time.time()
    import gpu_slot; gpu_slot.belegen("formfamilie_pruefen")
    paare = bilder_erzeugen(a, obj, objp, teile_pfade, {n: w for n, w in wahl.items() if w}, FL["teile"], bilder_dir)
    t_bild = time.time() - t0
    erg = {"objekt": a.objekt, "stl_sha": sha, "formliste": a.formliste, "teile": {}, "sek_bilder": round(t_bild)}
    for n in namen: erg["teile"][n] = {"status": "ungeprueft", "grund": "keine Bilder"} if not paare.get(n) else {"status": "offen", "paare": paare[n]}
    if not a.nur_bilder:
        pdir = os.path.join(a.arbeit, "pruefer"); os.makedirs(pdir, exist_ok=True)
        def lauf(n):
            cache = os.path.join(pdir, n + ".json")
            if os.path.exists(cache) and not a.neu:
                try:
                    c = json.load(open(cache))
                    if c.get("paare") == paare[n] and c.get("status") == "ok" and c.get("stl_sha") == sha: return n, c, 0
                except Exception: pass
            r = pruefer(n, paare[n], a.arbeit, a.modell, a.timeout); r["stl_sha"] = sha
            if r.get("status") == "ok": json.dump(r, open(cache, "w"), ensure_ascii=False, indent=1)
            return n, r, 1
        todo = [n for n in namen if paare.get(n)]
        aufrufe = 0
        with ThreadPoolExecutor(a.parallel) as ex:
            for n, r, k in ex.map(lauf, todo):
                erg["teile"][n] = r; aufrufe += k
                print(f"{n}: {r['status']}, {len(r.get('abweichungen', []))} Abweichungen", flush=True)
        erg["claude_aufrufe"] = aufrufe
    erg["sek_gesamt"] = round(time.time() - t0)
    json.dump(erg, open(os.path.join(a.arbeit, "formfamilie.json"), "w"), ensure_ascii=False, indent=1)
    return erg


if __name__ == "__main__":
    main()
