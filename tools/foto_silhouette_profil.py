#!/usr/bin/env python3
"""foto_silhouette_profil.py - GENERISCH: Breitenprofil eines Dachhelms/Turmkopfs aus einem FERNEN Seitenfoto (nahezu orthografisch).

Wozu: einseitige Fotowolken driften in der Tiefe, der Laser (DOM1, 1-m-Zellmaxima) ist auf steilen Helmflaechen blind
(wenige Rueckkehrer -> Zellen fallen unter die Schwelle, Schnitt und Flaeche zu klein). Ein Foto von der SEITE aus ~1 km
zeigt die Ausdehnung des Helms senkrecht zur Blickrichtung je Hoehe direkt als Silhouette gegen den Himmel.

Massstab: zwei Bildzeilen mit bekannter Hoehe aus dem V-Protokoll (modelle/<objekt>/messprotokoll/V-<foto>.json):
  'unten' = gleich hohe Punkte (Tuermchenspitzen, Hoehe aus masse[hoehe_unten]) und 'oben' = Pick am Helmscheitel
  (Hoehe aus masse[hoehe_oben]). Orthografie -> gleicher Massstab waagerecht wie senkrecht (Abweichung = Streuung der
  gleich hohen Punkte, wird wie in foto_verhaeltnis.py geprueft).
Silhouette: je Zeile zwischen den beiden Bezugszeilen die zusammenhaengende Nicht-Himmel-Strecke um die Achsspalte
  (Himmel = hell und wenig gesaettigt; Schwellen aus dem Himmel-Fenster neben dem Turm geschaetzt). Zeilen, in denen
  Fremdkoerper (Kran, Fahne) die Strecke verbreitern, fallen durch einen Monotonie-Filter (Helm wird nach oben nicht breiter).

  foto_silhouette_profil.py modelle/<objekt>/objekt.json 061 --achse x --hoehe-unten TUERM_SPITZE --hoehe-oben RZ1 \
      --pick-oben 2387 303 --pruefungen 46 49 52
Schreibt messprotokoll/M-<foto>-S1.json (Protokoll mit Massstab und Zeilen), audit/silhouette_<foto>.png (Kontrollbild)
und mit --pruefungen Pruefzeilen 'Profil Dach (Foto <nr>): Tiefe <achse> bei <z> m' in die Masstabelle (Messung
ausdehnung_streifen, quelltyp foto_verhaeltnis, Soll = Fotowert +- Toleranz).
"""
import sys, os, json, math, argparse, numpy as np

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto")
    ap.add_argument("--achse", default="x", help="Modellachse, die im Foto waagerecht liegt (Blick von Ost/West: x = Nord-Sued)")
    ap.add_argument("--rand-unten", type=float, default=1.0, help="Hoehe ueber den Tuermchen-Bezugspicks, ab der die Silhouette gilt (Knaeufe ragen ~0,5 m ueber die Spitzen)"); ap.add_argument("--bezug", nargs="*", help="Namen der Bezugspicks (K-<foto>.json, Hoehen aus anker3d.json); leer = alle Picks mit Anker")
    ap.add_argument("--halbfenster", type=int, default=120, help="Suchbreite links/rechts der Achsspalte (px)"); ap.add_argument("--himmel-delta", type=float, default=14, help="Abstand (HSV S und V) vom Himmel-Median, ab dem ein Pixel Koerper ist")
    ap.add_argument("--pruefungen", nargs="*", type=float); ap.add_argument("--toleranz", type=float, default=0.7); ap.add_argument("--dz", type=float, default=0.5)
    a = ap.parse_args(); import cv2
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(od)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from bauteile import lade_masse
    masse = lade_masse(os.path.join(od, "masse.json"))
    # Bezug: Picks aus K-<foto>.json mit Ankerhoehen aus anker3d.json (sigma) -> Ausgleich v = v0 - ppm * z ueber ALLE Bezugspicks,
    # Residuen je Pick in m zeigen, welche Bezugshoehe nicht passt (statt zwei von Hand gewaehlter Zeilen). Orthografie: Streuung gleich hoher Picks.
    K = json.load(open(os.path.join(od, "messprotokoll", f"K-{a.foto}.json"))); AN = json.load(open(os.path.join(od, "anker3d.json")))["anker"]
    bez = [(n, float(uv[0]), float(uv[1]), float(AN[n]["xyz"][2]), float(AN[n].get("sigma", 1.0)), np.array(AN[n]["xyz"], float)) for n, uv in K["punkte"].items() if n in AN and (not a.bezug or n in a.bezug)]
    if len(bez) < 3: sys.exit("weniger als 3 Bezugspicks mit Anker")
    # Schwache Perspektive (fernes Foto): u = u0 + ppm * (x sin(th) - y cos(th)) [Bildrechts], v = v0 - ppm * z. Unbekannt: ppm, th (Azimut), u0, v0.
    # So gehen auch WAAGERECHTE Bekanntgroessen ein (Abstand der Tuermchen N-S aus Wolke/DOM1), der Massstab ist ueberbestimmt und ein
    # falscher Hoehenanker (z. B. SfM-Nadelende) faellt als Residuum auf, statt den Massstab zu verbiegen. Robust: Picks > 3 sigma raus, neu loesen.
    from scipy.optimize import least_squares
    def modell(p, X):
        ppm_, th, u0_, v0_ = p; return np.c_[u0_ + ppm_ * (X[:, 0] * np.sin(th) - X[:, 1] * np.cos(th)), v0_ - ppm_ * X[:, 2]]
    def loese(B):
        X = np.array([b[5] for b in B]); UV = np.array([[b[1], b[2]] for b in B]); W = 1.0 / np.array([max(b[4], 0.2) for b in B])
        best = None
        for th0 in np.radians(range(0, 360, 30)):
            for ppm0 in (5.0, 10.0, 20.0):
                sol = least_squares(lambda p: ((modell(p, X) - UV) * W[:, None]).ravel(), [ppm0, th0, UV[:, 0].mean(), UV[:, 1].mean() + ppm0 * X[:, 2].mean()], method="trf")
                if best is None or sol.cost < best.cost: best = sol
        return best
    B = list(bez); verworfen = []
    for _ in range(len(bez)):
        sol = loese(B); X = np.array([b[5] for b in B]); UV = np.array([[b[1], b[2]] for b in B]); ppm, th, u0, v0 = sol.x
        res_m = (UV - modell(sol.x, X)) / ppm; r2 = np.hypot(res_m[:, 0], res_m[:, 1]); sig = np.array([max(b[4], 0.3) for b in B])
        if len(B) > 3 and (r2 / sig).max() > 3.0:
            i = int(np.argmax(r2 / sig)); verworfen.append((B[i], res_m[i])); B.pop(i); continue
        break
    print(f"Foto {a.foto}: schwache Perspektive aus {len(B)} Bezugspicks -> {ppm:.2f} px/m, Azimut {np.degrees(th):.1f} Grad, Nullzeile {v0:.1f} (z=0)")
    for b, r in zip(B, res_m): print(f"   {b[0]:14s} (u {b[1]:.0f}, v {b[2]:.0f})  Anker {b[5].round(2).tolist()} sigma {b[4]}  Residuum du {r[0]:+.2f} m, dv {r[1]:+.2f} m")
    for b, r in verworfen:
        z_impl = (v0 - b[2]) / ppm; print(f"   VERWORFEN {b[0]:14s} Residuum du {r[0]:+.2f} dv {r[1]:+.2f} m -> aus dem Foto folgt Hoehe {z_impl:.1f} m statt Anker {b[3]} m")
    ortho = 0.0
    # gleich hohe Picks: groesste Gruppe gleicher Ankerhoehe (statt Namensmuster) - ihre Zeilenstreuung misst die Orthografie
    grp = {}
    for b in B: grp.setdefault(round(b[3], 1), []).append(b)
    gleich = max(grp.values(), key=len) if grp else []
    spanne_px = max(float(uv[1]) for uv in K["punkte"].values()) - min(float(uv[1]) for uv in K["punkte"].values())   # Messstrecke = alle Picks
    if len(gleich) >= 2: ortho = float(np.std([b[2] for b in gleich]) / max(spanne_px, 1.0))
    u_ach = float(u0); v_unten = max(b[2] for b in B); v_oben = min(b[2] for b in B)
    res = [tuple(r) for r in res_m]; bez = B
    def z_von_v(v): return (v0 - v) / ppm
    # Picks mit Anker, die NICHT als Bezug dienen: ihre aus dem Foto folgende Hoehe gegen den Anker (unabhaengige Probe)
    for n, uv in K["punkte"].items():
        if n in AN and a.bezug and n not in a.bezug: print(f"   PROBE {n:14s} Zeile {float(uv[1]):.0f} -> Hoehe aus Foto {(v0 - float(uv[1])) / ppm:.1f} m (Anker {AN[n]['xyz'][2]} m, Differenz {(v0 - float(uv[1])) / ppm - AN[n]['xyz'][2]:+.1f})")
    print(f"   Orthografie-Streuung (gleich hohe Picks) {ortho:.3f}; Achsspalte u {u_ach:.0f}")
    if ortho > 0.1: sys.exit("Foto zu nah (gleich hohe Punkte streuen > 10 % der Messstrecke)")
    v_oben = min(min(b[2] for b in bez), min((b[2] for b, _ in verworfen), default=1e9))   # Messbereich bis zum hoechsten Pick (auch verworfene: Nadelende)
    fd = obj.get("fotos_dir", "daten/fotos"); fd = fd if os.path.isabs(fd) else os.path.join(os.path.dirname(root), fd)
    datei = [f for f in os.listdir(fd) if f.startswith(a.foto)][0]; im = cv2.imread(os.path.join(fd, datei))
    # Himmelmodell aus zwei Fenstern seitlich des Turms in Scheitelhoehe
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(float)
    u0 = int(u_ach); sky = np.r_[hsv[int(v_oben):int(v_oben) + 40, u0 - 3 * a.halbfenster:u0 - 2 * a.halbfenster].reshape(-1, 3), hsv[int(v_oben):int(v_oben) + 40, u0 + 2 * a.halbfenster:u0 + 3 * a.halbfenster].reshape(-1, 3)]
    s_max = np.percentile(sky[:, 1], 50) + a.himmel_delta; v_min = np.percentile(sky[:, 2], 50) - a.himmel_delta   # Median: Fremdkoerper (Kran) im Himmelfenster stoeren nicht; enge Schwelle, sonst zaehlt die sonnenbeschienene Helmflaeche als Himmel
    ist_himmel = (hsv[..., 1] < s_max) & (hsv[..., 2] > v_min)
    nicht = (~ist_himmel).astype(np.uint8); nicht = cv2.morphologyEx(nicht, cv2.MORPH_CLOSE, np.ones((5, 7), np.uint8))   # Glanzlichter/Falze im Helm schliessen
    aufl_m = 7 / ppm                                                                            # AUFLOESUNGSGRENZE: der Schliessungskern (7 px) macht alles mindestens so breit
    print(f"   Aufloesungsgrenze der Silhouette: {aufl_m:.2f} m (Schliessungskern 7 px); Breiten < {1.5 * aufl_m:.2f} m sind nur Obergrenzen")
    zeilen = []
    for v in range(int(v_oben) + 2, int(v_unten) - 1):
        row = nicht[v, u0 - a.halbfenster:u0 + a.halbfenster] > 0
        idx = np.flatnonzero(row)
        if len(idx) == 0: continue
        c = a.halbfenster; j = idx[np.argmin(np.abs(idx - c))]
        if abs(j - c) > 25: continue                                      # kein Koerper nahe der Achse -> Zeile ueberspringen
        l = j
        while l - 1 >= 0 and row[l - 1]: l -= 1
        r = j
        while r + 1 < len(row) and row[r + 1]: r += 1
        zeilen.append((v, (l - c), (r - c), (r - l + 1) / ppm, z_von_v(v)))
    Z = np.array(zeilen)
    seitlich = [b for b in bez if math.hypot(b[5][0], b[5][1]) > 1.5]                            # Picks abseits der Achse (Ecktuermchen o. ae.) stecken darunter in der Silhouettenstrecke
    z_frei = max([b[3] for b in seitlich], default=-1e9) + a.rand_unten
    Z = Z[Z[:, 4] >= z_frei]
    prof = []
    for z in np.arange(np.floor(Z[:, 4].min() / a.dz) * a.dz, Z[:, 4].max(), a.dz):
        k = (Z[:, 4] >= z) & (Z[:, 4] < z + a.dz)
        if k.sum() >= 2: prof.append(dict(z=round(float(z + a.dz / 2), 2), breite_roh=round(float(np.median(Z[k, 3])), 2), zeilen=int(k.sum())))
    # Monotonie: nach oben nie breiter als die Schicht darunter (entfernt Kran/Fahne/Tuermchenueberlappung); von unten nach oben laufendes Minimum
    bmin = np.inf
    for r in prof:
        bmin = min(bmin, r["breite_roh"]); r["breite"] = round(bmin, 2); r["nur_obergrenze"] = bool(r["breite"] < 1.5 * aufl_m)   # unter 1,5 x Kernbreite: nur Obergrenze
    print(f"Silhouette ({len(prof)} Schichten): z | Breite {a.achse} (m) | roh")
    for r in prof: print(f"  {r['z']:5.2f}  {r['breite']:5.2f}  {r['breite_roh']:5.2f}")
    # Kontrollbild
    k0 = im[int(v_oben) - 20:int(v_unten) + 20, u0 - a.halbfenster:u0 + a.halbfenster].copy()
    for v, l, r, _, _ in Z: cv2.line(k0, (int(l + a.halbfenster), int(v - v_oben + 20)), (int(r + a.halbfenster), int(v - v_oben + 20)), (0, 0, 255), 1)
    k0 = cv2.resize(k0, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST); os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    cv2.imwrite(os.path.join(od, "audit", f"silhouette_{a.foto}.png"), k0)
    proto = dict(foto=a.foto, verfahren="Silhouettenbreite je Zeile, fernes Seitenfoto (orthografisch), Massstab = Ausgleich ueber Bezugspicks (K-Protokoll) mit Ankerhoehen (anker3d)", achse=a.achse,
                 bezug=[dict(name=b[0], u=b[1], zeile=b[2], hoehe=b[3], sigma=b[4], residuum_m=[round(float(r[0]), 2), round(float(r[1]), 2)]) for b, r in zip(bez, res)], verworfen=[dict(name=b[0], residuum_m=[round(float(r[0]), 2), round(float(r[1]), 2)], hoehe_aus_foto=round(float((v0 - b[2]) / ppm), 2), anker_hoehe=b[3]) for b, r in verworfen], azimut_grad=round(float(np.degrees(th)), 1), nullzeile=round(float(v0), 1),
                 px_je_m=round(ppm, 3), aufloesung_m=round(aufl_m, 2), orthografie_abweichung=round(ortho, 4), himmel=dict(s_max=float(s_max), v_min=float(v_min)), profil=prof, kontrollbild=f"audit/silhouette_{a.foto}.png")
    pp = os.path.join(od, "messprotokoll", f"M-{a.foto}-S1.json"); json.dump(proto, open(pp, "w"), indent=1, ensure_ascii=False); print("Protokoll:", pp)
    if a.pruefungen:
        tp = os.path.join(od, "masstabelle.json"); from masstabelle_io import sperren, schreiben; _L = sperren(tp); T = json.load(open(tp)); neu = 0
        for z in a.pruefungen:
            r = min(prof, key=lambda q: abs(q["z"] - z))
            if r.get("nur_obergrenze"): print(f"   Pruefung bei {z} m ausgelassen: Breite {r['breite']} m liegt unter 1,5 x Aufloesungsgrenze ({1.5 * aufl_m:.2f} m)"); continue
            name = f"Profil Dach (Foto {a.foto}): Tiefe {a.achse} bei {z:.0f} m (m)"; wert = f"silhouette_{a.foto}_{int(z)}"
            T["messungen"][wert] = {"typ": "ausdehnung_streifen", "z": float(z), "achse": a.achse, "quer_max": 2.0}
            soll = [round(r["breite"] - a.toleranz, 2), round(r["breite"] + a.toleranz, 2)]
            quelle = f"foto_silhouette_profil.py: Foto {a.foto} Silhouette {r['breite']} m bei {r['z']} m ({ppm:.1f} px/m, Ausgleich ueber {len(bez)} Bezugspicks: {', '.join(b[0] for b in bez)}); Protokoll M-{a.foto}-S1"
            for pr in T["pruefungen"]:
                if pr["name"] == name:
                    if pr["soll"] != soll: pr.setdefault("historie", []).append({"datum": "auto", "alt_soll": pr["soll"], "grund": "foto_silhouette_profil.py neu gerechnet"}); pr["soll"] = soll; pr["quelle"] = quelle
                    break
            else:
                T["pruefungen"].append(dict(name=name, wert=wert, soll=soll, quelle=quelle, quelltyp="foto_verhaeltnis", merkmal="schlankheit", massstab="Bezugspicks K-Protokoll + anker3d (Ausgleich)", protokoll=f"M-{a.foto}-S1")); neu += 1
        namen = {f"Profil Dach (Foto {a.foto}): Tiefe {a.achse} bei {z:.0f} m (m)" for z in a.pruefungen if not min(prof, key=lambda q: abs(q["z"] - z)).get("nur_obergrenze")}
        alt = [pr for pr in T["pruefungen"] if pr["name"].startswith(f"Profil Dach (Foto {a.foto})") and pr["name"] not in namen]
        T["pruefungen"] = [pr for pr in T["pruefungen"] if pr not in alt]
        for pr in alt: T["messungen"].pop(pr["wert"], None)
        schreiben(tp, T, _L); print(f"Masstabelle: {neu} neue Silhouetten-Pruefungen, {len(alt)} veraltete entfernt")

if __name__ == "__main__":
    main()
