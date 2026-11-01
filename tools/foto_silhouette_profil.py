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
    bez = [(n, float(uv[0]), float(uv[1]), float(AN[n]["xyz"][2]), float(AN[n].get("sigma", 1.0))) for n, uv in K["punkte"].items() if n in AN and (not a.bezug or n in a.bezug)]
    if len(bez) < 2: sys.exit("weniger als 2 Bezugspicks mit Anker")
    zz = np.array([b[3] for b in bez]); vv = np.array([b[2] for b in bez]); ww = 1.0 / np.array([max(b[4], 0.2) for b in bez])
    Aa = np.c_[np.ones(len(zz)), -zz] * ww[:, None]; v0, ppm = np.linalg.lstsq(Aa, vv * ww, rcond=None)[0]
    res = (vv - (v0 - ppm * zz)) / ppm                                                     # Residuum in m (positiv = Pick liegt tiefer im Bild = niedriger)
    print(f"Foto {a.foto}: Ausgleich ueber {len(bez)} Bezugspicks -> {ppm:.2f} px/m, Nullzeile {v0:.1f} (z=0)")
    for b, r in zip(bez, res): print(f"   {b[0]:14s} Zeile {b[2]:6.1f}  Hoehe {b[3]:5.2f} m (sigma {b[4]})  Residuum {r:+.2f} m")
    schlecht = [b[0] for b, r in zip(bez, res) if abs(r) > 2 * max(b[4], 0.3)]
    if schlecht: print("   ! Bezugspicks ausserhalb 2 sigma:", schlecht)
    def z_von_v(v): return (v0 - v) / ppm
    gleich = [b for b in bez if b[0].startswith("tuermchen")]; ortho = (np.std([b[2] for b in gleich]) / (vv.max() - vv.min())) if len(gleich) >= 2 else 0.0
    u_ach = float(np.mean([b[1] for b in bez])); v_unten = max(b[2] for b in bez); v_oben = min(b[2] for b in bez); z_unten = z_von_v(v_unten)
    print(f"   Orthografie-Streuung (gleich hohe Picks) {ortho:.3f}; Achsspalte u {u_ach:.0f}; Messbereich Zeilen {v_oben:.0f}..{v_unten:.0f} = z {z_von_v(v_unten):.1f}..{z_von_v(v_oben):.1f} m")
    if ortho > 0.1: sys.exit("Foto zu nah (gleich hohe Punkte streuen > 10 % der Messstrecke)")
    fd = obj.get("fotos_dir", "daten/fotos"); fd = fd if os.path.isabs(fd) else os.path.join(os.path.dirname(root), fd)
    datei = [f for f in os.listdir(fd) if f.startswith(a.foto)][0]; im = cv2.imread(os.path.join(fd, datei))
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
        zeilen.append((v, (l - c), (r - c), (r - l + 1) / ppm, z_von_v(v)))
    Z = np.array(zeilen)
    z_frei = max([b[3] for b in bez if b[0].startswith("tuermchen")], default=-1e9) + a.rand_unten   # ueber den Tuermchenknaeufen erst ist die Strecke das Dach allein
    Z = Z[Z[:, 4] >= z_frei]
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
    proto = dict(foto=a.foto, verfahren="Silhouettenbreite je Zeile, fernes Seitenfoto (orthografisch), Massstab = Ausgleich ueber Bezugspicks (K-Protokoll) mit Ankerhoehen (anker3d)", achse=a.achse,
                 bezug=[dict(name=b[0], u=b[1], zeile=b[2], hoehe=b[3], sigma=b[4], residuum_m=round(float(r), 2)) for b, r in zip(bez, res)], nullzeile=round(float(v0), 1),
                 px_je_m=round(ppm, 3), orthografie_abweichung=round(ortho, 4), himmel=dict(s_max=float(s_max), v_min=float(v_min)), profil=prof, kontrollbild=f"audit/silhouette_{a.foto}.png")
    pp = os.path.join(od, "messprotokoll", f"M-{a.foto}-S1.json"); json.dump(proto, open(pp, "w"), indent=1, ensure_ascii=False); print("Protokoll:", pp)
    if a.pruefungen:
        tp = os.path.join(od, "masstabelle.json"); T = json.load(open(tp)); neu = 0
        for z in a.pruefungen:
            r = min(prof, key=lambda q: abs(q["z"] - z)); name = f"Profil Dach (Foto {a.foto}): Tiefe {a.achse} bei {z:.0f} m (m)"; wert = f"silhouette_{a.foto}_{int(z)}"
            T["messungen"][wert] = {"typ": "ausdehnung_streifen", "z": float(z), "achse": a.achse, "quer_max": 2.0}
            soll = [round(r["breite"] - a.toleranz, 2), round(r["breite"] + a.toleranz, 2)]
            quelle = f"foto_silhouette_profil.py: Foto {a.foto} Silhouette {r['breite']} m bei {r['z']} m ({ppm:.1f} px/m, Ausgleich ueber {len(bez)} Bezugspicks: {', '.join(b[0] for b in bez)}); Protokoll M-{a.foto}-S1"
            for pr in T["pruefungen"]:
                if pr["name"] == name:
                    if pr["soll"] != soll: pr.setdefault("historie", []).append({"datum": "auto", "alt_soll": pr["soll"], "grund": "foto_silhouette_profil.py neu gerechnet"}); pr["soll"] = soll; pr["quelle"] = quelle
                    break
            else:
                T["pruefungen"].append(dict(name=name, wert=wert, soll=soll, quelle=quelle, quelltyp="foto_verhaeltnis", merkmal="schlankheit", massstab="Bezugspicks K-Protokoll + anker3d (Ausgleich)", protokoll=f"M-{a.foto}-S1")); neu += 1
        namen = {f"Profil Dach (Foto {a.foto}): Tiefe {a.achse} bei {z:.0f} m (m)" for z in a.pruefungen}
        alt = [pr for pr in T["pruefungen"] if pr["name"].startswith(f"Profil Dach (Foto {a.foto})") and pr["name"] not in namen]
        T["pruefungen"] = [pr for pr in T["pruefungen"] if pr not in alt]
        for pr in alt: T["messungen"].pop(pr["wert"], None)
        json.dump(T, open(tp, "w"), indent=1, ensure_ascii=False); print(f"Masstabelle: {neu} neue Silhouetten-Pruefungen, {len(alt)} veraltete entfernt")

if __name__ == "__main__":
    main()
