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
import sys, os, json, argparse, numpy as np

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto")
    ap.add_argument("--achse", default="x", help="Modellachse, die im Foto waagerecht liegt (Blick von Ost/West: x = Nord-Sued)")
    ap.add_argument("--hoehe-unten", default="TUERM_SPITZE"); ap.add_argument("--hoehe-oben", default="GZ1+DACHHOEHE", help="Massname, Zahl oder Summe (Generator: RZ1 = GZ1 + DACHHOEHE)")
    ap.add_argument("--pick-oben", nargs=2, type=float, help="u v des Helmscheitels (sonst 'oben' aus dem V-Protokoll)")
    ap.add_argument("--halbfenster", type=int, default=120, help="Suchbreite links/rechts der Achsspalte (px)"); ap.add_argument("--himmel-delta", type=float, default=14, help="Abstand (HSV S und V) vom Himmel-Median, ab dem ein Pixel Koerper ist")
    ap.add_argument("--pruefungen", nargs="*", type=float); ap.add_argument("--toleranz", type=float, default=0.7); ap.add_argument("--dz", type=float, default=0.5)
    a = ap.parse_args(); import cv2
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(od)
    V = json.load(open(os.path.join(od, "messprotokoll", f"V-{a.foto}.json")))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from bauteile import lade_masse
    masse = {k: {"wert": v} for k, v in lade_masse(os.path.join(od, "masse.json")).items()}   # Formeln (GZ1 = ZZ + 10) aufgeloest
    def hoehe(ausdruck):   # Massname, Zahl oder Summe daraus ("37.0+DACHHOEHE")
        return float(sum(float(masse[t]["wert"]) if t in masse else float(t) for t in ausdruck.split("+")))
    z_unten = hoehe(a.hoehe_unten); z_oben = hoehe(a.hoehe_oben)
    repo = os.path.dirname(root); fd = obj.get("fotos_dir", "daten/fotos"); fd = fd if os.path.isabs(fd) else os.path.join(repo, fd)
    datei = [f for f in os.listdir(fd) if f.startswith(a.foto)][0]; im = cv2.imread(os.path.join(fd, datei))
    picks = np.array(list(V["unten"]["picks"].values()), float); v_unten = float(picks[:, 1].mean()); streu = float(picks[:, 1].std())
    u_ach = float(picks[:, 0].mean()); po = a.pick_oben or V["oben"]["pick"]; v_oben = float(po[1])
    ppm = (v_unten - v_oben) / (z_oben - z_unten)                      # px je Meter (senkrecht = waagerecht bei Orthografie)
    ortho = streu / max(v_unten - v_oben, 1)
    print(f"Foto {a.foto}: Zeile unten {v_unten:.1f} ({a.hoehe_unten}={z_unten} m), oben {v_oben:.1f} ({a.hoehe_oben}={z_oben} m) -> {ppm:.2f} px/m; Orthografie-Streuung {ortho:.3f}")
    if ortho > 0.1: sys.exit("Foto zu nah (gleich hohe Punkte streuen > 10 % der Messstrecke)")
    # Himmelmodell aus zwei Fenstern seitlich des Turms in Scheitelhoehe
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(float)
    u0 = int(u_ach); sky = np.r_[hsv[int(v_oben):int(v_oben) + 40, u0 - 3 * a.halbfenster:u0 - 2 * a.halbfenster].reshape(-1, 3), hsv[int(v_oben):int(v_oben) + 40, u0 + 2 * a.halbfenster:u0 + 3 * a.halbfenster].reshape(-1, 3)]
    s_max = np.percentile(sky[:, 1], 50) + a.himmel_delta; v_min = np.percentile(sky[:, 2], 50) - a.himmel_delta   # Median: Fremdkoerper (Kran) im Himmelfenster stoeren nicht; enge Schwelle, sonst zaehlt die sonnenbeschienene Helmflaeche als Himmel
    ist_himmel = (hsv[..., 1] < s_max) & (hsv[..., 2] > v_min)
    nicht = (~ist_himmel).astype(np.uint8); nicht = cv2.morphologyEx(nicht, cv2.MORPH_CLOSE, np.ones((5, 7), np.uint8))   # Glanzlichter/Falze im Helm schliessen
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
        zeilen.append((v, (l - c), (r - c), (r - l + 1) / ppm, z_unten + (v_unten - v) / ppm))
    Z = np.array(zeilen)
    prof = []
    for z in np.arange(np.floor(Z[:, 4].min() / a.dz) * a.dz, Z[:, 4].max(), a.dz):
        k = (Z[:, 4] >= z) & (Z[:, 4] < z + a.dz)
        if k.sum() >= 2: prof.append(dict(z=round(float(z + a.dz / 2), 2), breite_roh=round(float(np.median(Z[k, 3])), 2), zeilen=int(k.sum())))
    # Monotonie: nach oben nie breiter als die Schicht darunter (entfernt Kran/Fahne/Tuermchenueberlappung); von unten nach oben laufendes Minimum
    bmin = np.inf
    for r in prof:
        bmin = min(bmin, r["breite_roh"]); r["breite"] = round(bmin, 2)
    print(f"Silhouette ({len(prof)} Schichten): z | Breite {a.achse} (m) | roh")
    for r in prof: print(f"  {r['z']:5.2f}  {r['breite']:5.2f}  {r['breite_roh']:5.2f}")
    # Kontrollbild
    k0 = im[int(v_oben) - 20:int(v_unten) + 20, u0 - a.halbfenster:u0 + a.halbfenster].copy()
    for v, l, r, _, _ in Z: cv2.line(k0, (int(l + a.halbfenster), int(v - v_oben + 20)), (int(r + a.halbfenster), int(v - v_oben + 20)), (0, 0, 255), 1)
    k0 = cv2.resize(k0, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST); os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    cv2.imwrite(os.path.join(od, "audit", f"silhouette_{a.foto}.png"), k0)
    proto = dict(foto=a.foto, verfahren="Silhouettenbreite je Zeile, fernes Seitenfoto (orthografisch), Massstab aus zwei Bezugszeilen", achse=a.achse,
                 bezug=dict(unten=dict(zeile=v_unten, hoehe=z_unten, mass=a.hoehe_unten, picks=V["unten"]["picks"]), oben=dict(zeile=v_oben, hoehe=z_oben, mass=a.hoehe_oben, pick=list(po))),
                 px_je_m=round(ppm, 3), orthografie_abweichung=round(ortho, 4), himmel=dict(s_max=float(s_max), v_min=float(v_min)), profil=prof, kontrollbild=f"audit/silhouette_{a.foto}.png")
    pp = os.path.join(od, "messprotokoll", f"M-{a.foto}-S1.json"); json.dump(proto, open(pp, "w"), indent=1, ensure_ascii=False); print("Protokoll:", pp)
    if a.pruefungen:
        tp = os.path.join(od, "masstabelle.json"); T = json.load(open(tp)); neu = 0
        for z in a.pruefungen:
            r = min(prof, key=lambda q: abs(q["z"] - z)); name = f"Profil Dach (Foto {a.foto}): Tiefe {a.achse} bei {z:.0f} m (m)"; wert = f"silhouette_{a.foto}_{int(z)}"
            T["messungen"][wert] = {"typ": "ausdehnung_streifen", "z": float(z), "achse": a.achse, "quer_max": 2.0}
            soll = [round(r["breite"] - a.toleranz, 2), round(r["breite"] + a.toleranz, 2)]
            quelle = f"foto_silhouette_profil.py: Foto {a.foto} Silhouette {r['breite']} m bei {r['z']} m ({ppm:.1f} px/m aus {a.hoehe_unten}/{a.hoehe_oben}); Protokoll M-{a.foto}-S1"
            for pr in T["pruefungen"]:
                if pr["name"] == name:
                    if pr["soll"] != soll: pr.setdefault("historie", []).append({"datum": "auto", "alt_soll": pr["soll"], "grund": "foto_silhouette_profil.py neu gerechnet"}); pr["soll"] = soll; pr["quelle"] = quelle
                    break
            else:
                T["pruefungen"].append(dict(name=name, wert=wert, soll=soll, quelle=quelle, quelltyp="foto_verhaeltnis", merkmal="schlankheit", massstab=f"{a.hoehe_unten} + {a.hoehe_oben} (Zeilen)", protokoll=f"M-{a.foto}-S1")); neu += 1
        namen = {f"Profil Dach (Foto {a.foto}): Tiefe {a.achse} bei {z:.0f} m (m)" for z in a.pruefungen}
        alt = [pr for pr in T["pruefungen"] if pr["name"].startswith(f"Profil Dach (Foto {a.foto})") and pr["name"] not in namen]
        T["pruefungen"] = [pr for pr in T["pruefungen"] if pr not in alt]
        for pr in alt: T["messungen"].pop(pr["wert"], None)
        json.dump(T, open(tp, "w"), indent=1, ensure_ascii=False); print(f"Masstabelle: {neu} neue Silhouetten-Pruefungen, {len(alt)} veraltete entfernt")

if __name__ == "__main__":
    main()
