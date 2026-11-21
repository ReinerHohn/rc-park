#!/usr/bin/env python3
"""Fester Test: BELASTUNGSPROBE fuer seiten_vereinen.vereinen OHNE echte Daten (Vorbild tools/versuche/vereinen_robust_1121.py, dort an den Martinstor-Wolken:
8 verfaelschte Laeufe enden auf 0,26-0,96 % der Bauhoehe und 0,04-0,49 Grad gleich - modelle/GLOBALER_MAPPER_STABIL.md, 21.11.2026 15:05).
Synthetischer rechtwinkliger Turm 10 x 8 m, Wand 40 m, Walmdach bis 55 m, Helmstange bis 60 m, Nachbarhaus auf EINER Flanke, Boden. Zwei Seitenmodelle mit dichter Wolke:
A sieht die Vorderseite (+x), B die Rueckseite (-x); B liegt in einem eigenen System (Massstab 2,7, beliebig gedreht/verschoben), das A-System ist gegen die Welt gekippt
(Lot nicht entlang z). Die Punktpaare P/Q verbinden wie am echten Bau die AEHNLICHEN Waende (B-Rueckwand auf A-Vorderwand, 15 % Ausreisser).
Die Klappung wird durch Ersetzen von seiten_vereinen.geklappt verfaelscht: Kippung bis 8 Grad, Drehung um das Lot bis +-20 Grad, Verschiebung bis 30 % der Turmhoehe
(fester Zufallskeim + die zwei Eckfaelle). ERWARTUNG je Fall:
  - Urteil 'vereint', Flanke 'gleich' (Nachbarhaus), Blick nachher > 120 Grad;
  - Endlage der B-Wolke gegen die WAHRE Lage (Median ueber die Wolkenpunkte): waagerecht <= 0,3 % der Turmhoehe (= 0,18 m: stange() trifft die Achse laut test_seiten_vereinen.py
    auf 0,15 m; gemessen 0,02 %), Drehung <= 0,5 Grad (Lot aus Wandnormalen <= 0,3 Grad laut demselben Test, Wandrichtung ebenso; gemessen 0,06 Grad), senkrecht <= 1,0 % (harte
    Grenze = groesster am Martinstor gemessener Lagewert 0,96 %; gemessen bis 0,34 %, siehe BEKANNTE SCHWAECHE 1);
  - gemeldete Korrekturen = eingebrachte Verfaelschung: lot_b.kippung_grad = Kippung +-0,5 Grad, dreh_b.verdrehung_grad = -Drehung +-0,5 Grad,
    spitzen.klapp_versatz = aus der Verfaelschung vorhergesagter Versatz der Stange +-1 % der Turmhoehe.
ABLEHNUNG: Massstab der Klappung 10 % falsch (er ist das Einzige, was weiter aus der Klappung kommt) -> Turmhoehen 10 % verschieden -> ok False, Grund 'Turmhoehen'.
BEKANNTE SCHWAECHEN von seiten_vereinen.py, die dieser Turm aufgedeckt hat (21.11.2026; Werkzeug bewusst NICHT geaendert - es war in der Hauptsitzung in Arbeit). Jede steht als
ERWARTETER FEHLSCHLAG im Test: solange die Schwaeche besteht, laeuft der Test durch und nennt sie; ist sie behoben, schlaegt er an -> Schalter unten auf False setzen.
  1. HOEHENLAGE WIRD NICHT NACHGEFUEHRT (BEKANNT_SENKRECHT): die Lot-Berichtigung dreht B um den Median SEINER Wolke, der Spitzenabgleich schiebt nur waagerecht. War die Klappung um einen
     anderen Punkt gekippt (hier: Mitte der Punktpaare), bleibt B senkrecht versetzt, etwa sin(Kippung) x waagerechter Abstand der beiden Drehpunkte: bis 0,34 % der Turmhoehe
     (0,2 m bei 60 m) bei 5,8 Grad; waagerecht dagegen 0,02 %. Soll: <= 0,1 %. Keine Pruefung im Werkzeug bemerkt es ('Turmhoehen' vergleicht Hoehen ueber dem je eigenen Boden).
  2. KLAPPUNG SETZT AEHNLICHES LOT IN BEIDEN MODELLSYSTEMEN VORAUS (BEKANNT_LOT_SYSTEM): geklappt() verwirft in der Zufallssuche jede Abbildung, die das Lot von A um mehr als
     20 Grad dreht ((R @ up) @ up < 0.94); das Lot von B wird nie gemessen. Gemessen an diesem Turm (340 richtige von 400 Paaren, B-System zusaetzlich gedreht, 18 Lagen):
     Lot der wahren Klappung 15-95 Grad neben dem von A -> trotzdem gefunden (nur ueber Zufallstreffer + Nachausgleich, der die Lot-Bedingung NICHT mehr prueft - die Bedingung
     gilt fuer das Ergebnis also gar nicht); B-System 90 Grad um eine waagerechte Achse gekippt oder ab ~120 Grad -> None ODER eine Zufallsabbildung mit 1-6 Treffern
     (einmal Massstab 0): es gibt keine Mindestzahl stimmiger Paare. vereinen() rechnet mit so einer Abbildung weiter und lehnt mit irrefuehrenden Gruenden ab (Achse uneinig /
     keine Klappung / keine hoechsten Bauteile; die Wandsuche auf der zum Punkt geschrumpften Wolke brauchte dabei 9 s) - kein falsches 'vereint', aber die Ursache steht nicht
     im Urteil. Wie oft echte Modellpaare so liegen: ungeprueft (Martinstor passte). Deshalb liegt hier das B-System nur um das Lot gedreht; die zwei Faelle 'B-System gedreht'
     pruefen nur geklappt() selbst.
Aufruf: python -I tools/test_seiten_vereinen_robust.py [--zeigen]   (--zeigen: Zahlen je Fall, auch bei Erfolg)"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import seiten_vereinen as V

BEKANNT_SENKRECHT = True; BEKANNT_LOT_SYSTEM = True                                   # erwartete Fehlschlaege, siehe Kopf
HOEHE = 60.0; AX = np.array([-0.9, -0.2, 0.0])


def rot(achse, grad):
    a = np.asarray(achse, float); a = a / np.linalg.norm(a); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]]); w = np.radians(grad)
    return np.eye(3) + np.sin(w) * K + (1 - np.cos(w)) * K @ K


def seite(rng, vz):
    """Dichte Wolke einer Seite in Weltkoordinaten (z oben), vz = +1 Vorderseite / -1 Rueckseite. Nur die gesehene Haelfte von Wand, Dach und Nachbarhaus."""
    u = lambda a, b, n: rng.uniform(a, b, n); n = 22000; z = u(0, 40, n); T = [np.c_[np.full(n, 5.0), u(-4, 4, n), z]]                # Wand zur Kamera
    for sy in (4.0, -4.0): n = 9000; T.append(np.c_[u(0, 5, n), np.full(n, sy), u(0, 40, n)])                                       # Seitenwaende, kameranahe Haelfte
    n = 9000; f = u(0, 1, n); T.append(np.c_[5 * (1 - f), u(-4, 4, n) * (1 - f), 40 + 15 * f])                                      # Dachflaeche zur Kamera
    for sy in (4.0, -4.0): n = 3500; f = u(0, 1, n); T.append(np.c_[u(0, 5, n) * (1 - f), sy * (1 - f), 40 + 15 * f])               # seitliche Dachflaechen, kameranahe Haelfte
    n = 2500; T.append(np.c_[rng.normal(0, 0.08, n), rng.normal(0, 0.08, n), u(55, 60, n)])                                         # Helmstange
    T = np.vstack(T) * [vz, vz, 1.0]                                                                                                # Rueckseite = halbe Drehung um die Achse
    n = 7000; N = [np.c_[np.full(n, 4.0 * vz), u(8, 18, n), u(0, 15, n)], np.c_[vz * u(4, 12, 4000), np.full(4000, 8.0), u(0, 15, 4000)]]   # Nachbarhaus: IMMER Flanke +y
    n = 8000; B = np.c_[vz * u(5, 35, n), u(-15, 20, n), np.zeros(n)]                                                               # Boden vor der Seite
    return np.vstack([T] + N + [B]) + AX + rng.normal(0, 0.015, (len(T) + 11000 + n, 3))


def kameras(rng, vz, n=40):
    C = np.c_[vz * rng.uniform(30, 50, n), rng.uniform(-15, 15, n), rng.normal(1.6, 0.1, n)] + AX; Vd = AX + [0, 0, 20.0] - C; return C, Vd / np.linalg.norm(Vd, axis=1, keepdims=True)


rng = np.random.default_rng(3)
G = rot([1.0, 2.0, 0.5], 20.0); up = G @ [0.0, 0, 1]                                    # A-System: gegen die Welt gekippt
s0, R0, t0 = 2.7, G.T @ rot(up, 140.0), np.array([30.0, -12.0, 7.0])                    # B-System: Welt = s0 R0 X_B + t0; gegen A nur UM DAS LOT gedreht (Voraussetzung von geklappt, siehe unten)
nachB = lambda Xw: (Xw - t0) @ R0 / s0; nachA = lambda Xw: Xw @ G.T
DAw, DBw = seite(rng, 1), seite(rng, -1); DA, DB = nachA(DAw), nachB(DBw); (CAw, VAw), (CBw, VBw) = kameras(rng, 1), kameras(rng, -1)
CA, VA, CB, VB = nachA(CAw), VAw @ G.T, nachB(CBw), VBw @ R0
XA = DA[rng.choice(len(DA), 4000, replace=False)]; XB = DB[rng.choice(len(DB), 4000, replace=False)]
n = 400; Qw = np.c_[np.full(n, 5.0), rng.uniform(-4, 4, n), rng.uniform(2, 40, n)]; Pw = Qw * [-1, -1, 1] + AX + rng.normal(0, 0.03, (n, 3)); Qw = Qw + AX   # aehnliche Waende: Rueckwand <-> Vorderwand
aus = rng.choice(n, 60, replace=False); Pw[aus] = DBw[rng.choice(len(DBw), 60)]                                                                              # 15 % falsche Paare
P, Q = nachB(Pw), nachA(Qw)
WAHR = np.eye(4); WAHR[:3, :3] = s0 * G @ R0; WAHR[:3, 3] = G @ t0                      # wahre Abbildung B -> A
orig = V.geklappt; ROH = orig(P, Q, up); assert ROH is not None, "unverfaelschte Klappung nicht gefunden"
stange_b = nachB(AX + [0, 0, 58.5]); stange_a = nachA(AX + [0, 0, 58.5]); zeigen = "--zeigen" in sys.argv


def lauf(kipp, dreh, schub, r1, r2, massstab=1.0):
    """Ein Vereinen mit verfaelschter Klappung. r1/r2 = waagerechte Zufallsrichtungen (Kippachse, Schubrichtung). Rueckgabe (Ergebnis, vorhergesagter Versatz der Stange in m)."""
    s, R, t, inl = ROH; c = np.median(Q[inl], 0); q = np.cross(up, r1); sh = np.cross(up, r2); sh = sh / np.linalg.norm(sh) * schub * HOEHE
    dR = rot(up, dreh) @ rot(q, kipp); sf, Rf, tf = s * massstab, dR @ R, massstab * dR @ (t - c) + c + sh
    V.geklappt = lambda *a, **k: (sf, Rf, tf, inl)
    try: erg = V.vereinen(XA, CA, VA, XB, CB, VB, P, Q, up, 0.02, DA, DB)
    finally: V.geklappt = orig
    Bk = sf * DB @ Rf.T + tf; Rk = rot(up, dreh) @ dR.T; c_ = np.median(Bk, 0); y = Rk @ (sf * Rf @ stange_b + tf - c_) + c_ - stange_a   # Stange von B nach idealer Lot-Berichtigung
    return erg, float(np.linalg.norm(y - (y @ up) * up))


def messen(erg):
    """Endlage gegen die wahre Lage: (Median waagerecht, Median senkrecht [mit Vorzeichen], beides in % der Turmhoehe; Drehung in Grad)."""
    M = np.array(erg["B_nach_A"]); d = DB @ M[:3, :3].T + M[:3, 3] - DB @ WAHR[:3, :3].T - WAHR[:3, 3]; h = d @ up
    R1 = M[:3, :3] / np.cbrt(np.linalg.det(M[:3, :3])); return float(np.median(np.linalg.norm(d - np.outer(h, up), axis=1)) / HOEHE * 100), float(np.median(h) / HOEHE * 100), float(np.degrees(np.arccos(np.clip((np.trace(R1 @ (G @ R0).T) - 1) / 2, -1, 1))))


zr = np.random.default_rng(7); FAELLE = [(0.0, 0.0, 0.0)] + [(float(zr.uniform(2, 8)), float(zr.uniform(-20, 20)), float(zr.uniform(0.05, 0.30))) for _ in range(4)] + [(8.0, 20.0, 0.30), (8.0, -20.0, 0.30)]
fehler = []; bekannt = []; schlimm = [0.0, 0.0, 0.0]
for kipp, dreh, schub in FAELLE:
    erg, vorher = lauf(kipp, dreh, schub, zr.normal(size=3), zr.normal(size=3)); name = f"Kippung {kipp:.1f} Grad, Drehung {dreh:+.1f} Grad, Schub {100 * schub:.0f} %"
    if "B_nach_A" not in erg: fehler.append(f"{name}: keine Endlage ({erg.get('urteil')})"); continue
    lage, hoch, dw = messen(erg); pr = erg["pruefung"]; lb, db, sp = erg.get("lot_b") or {}, erg.get("dreh_b") or {}, erg.get("spitzen") or {}; schlimm = [max(schlimm[0], lage), max(schlimm[1], abs(hoch)), max(schlimm[2], dw)]
    if zeigen: print(f"{name}: {erg['urteil'][:70]} | Endlage waagerecht {lage:.2f} % / senkrecht {hoch:+.2f} % / {dw:.2f} Grad | lot_b {lb.get('kippung_grad')} | dreh_b {db.get('verdrehung_grad')} | Versatz {sp.get('klapp_versatz', 0) * sp.get('hoehe_a', 0):.2f} m (vorhergesagt {vorher:.2f}) | Hoehen {100 * sp.get('hoehe_einigkeit', 0):.2f} % | Achse {100 * pr['achse_einigkeit']:.2f} % | Blick {pr['blick_nachher']:.0f} | Flanke {pr['flanke']} | Dach {pr['dach']}")
    pruef = [(erg["ok"] and erg["urteil"] == "vereint", f"Urteil '{erg['urteil']}' statt vereint"), (lage <= 0.3, f"Endlage waagerecht {lage:.2f} % der Turmhoehe neben der wahren Lage (Grenze 0,3)"), (abs(hoch) <= 1.0, f"Endlage senkrecht {hoch:+.2f} % der Turmhoehe (harte Grenze 1,0)"),
             (dw <= 0.5, f"Endlage {dw:.2f} Grad gegen die wahre Lage verdreht (Grenze 0,5)"), (pr["flanke"] == "gleich", f"Flanke '{pr['flanke']}' statt gleich"), (pr["blick_nachher"] > 120, f"Blick nachher {pr['blick_nachher']:.0f} Grad"),
             (lb.get("kippung_grad") is not None and abs(lb["kippung_grad"] - kipp) <= 0.5, f"lot_b meldet {lb.get('kippung_grad')} Grad, eingebracht {kipp:.1f}"),
             (db.get("verdrehung_grad") is not None and abs(db["verdrehung_grad"] + dreh) <= 0.5, f"dreh_b meldet {db.get('verdrehung_grad')} Grad, eingebracht {-dreh:.1f}"),
             (bool(sp) and abs(sp["klapp_versatz"] * sp["hoehe_a"] - vorher) <= 0.01 * HOEHE, f"spitzen meldet {sp.get('klapp_versatz', 0) * sp.get('hoehe_a', 0):.2f} m Versatz, vorhergesagt {vorher:.2f}"),
             (kipp < 0.2 or lb.get("berichtigt"), "Kippung nicht berichtigt"), (abs(dreh) < 0.3 or db.get("berichtigt"), "Drehung nicht berichtigt")]
    fehler += [f"{name}: {text}" for gut, text in pruef if not gut]
erg, _ = lauf(3.0, 10.0, 0.10, zr.normal(size=3), zr.normal(size=3), massstab=1.10)   # ABLEHNUNG: Massstab der Klappung 10 % falsch
if zeigen: print("Massstab 10 % falsch:", erg.get("urteil"), "| Hoehen", (erg.get("spitzen") or {}).get("hoehe_einigkeit"))
if BEKANNT_SENKRECHT and schlimm[1] <= 0.1: fehler.append(f"Schwaeche 1 (Hoehenlage) tritt nicht mehr auf (senkrecht hoechstens {schlimm[1]:.2f} %): BEKANNT_SENKRECHT = False setzen")
elif BEKANNT_SENKRECHT: bekannt.append(f"Hoehenlage nicht nachgefuehrt, senkrecht bis {schlimm[1]:.2f} % der Turmhoehe (Soll 0,1)")
elif schlimm[1] > 0.1: fehler.append(f"Endlage senkrecht bis {schlimm[1]:.2f} % der Turmhoehe (Grenze 0,1)")
for name, T in (("90 Grad gekippt", rot(np.cross(up, [0.3, 1.0, 0.2]), 90.0)), ("140 Grad um eine schiefe Achse gegen die Welt gedreht", rot([0.3, -1.0, 0.6], 140.0).T @ R0)):   # B in einem EIGENEN System; 340 richtige Paare vorhanden
    g = orig(P @ T.T, Q, up); gut = g is not None and int(g[3].sum()) >= 300; was = "None" if g is None else f"{int(g[3].sum())} Treffer, Massstab {g[0]:.3f}"
    if zeigen: print(f"B-System {name}: geklappt -> {was}")
    if BEKANNT_LOT_SYSTEM and gut: fehler.append(f"Schwaeche 2 (Lot beider Systeme) tritt bei '{name}' nicht mehr auf: BEKANNT_LOT_SYSTEM = False setzen")
    elif BEKANNT_LOT_SYSTEM: bekannt.append(f"B-System {name}: geklappt() findet die Klappung nicht ({was})")
    elif not gut: fehler.append(f"B-System {name}: geklappt() findet die Klappung nicht ({was})")
if erg.get("ok") or "Turmhoehen" not in str(erg.get("urteil")): fehler.append(f"Massstab der Klappung 10 % falsch wurde NICHT wegen der Turmhoehen abgelehnt: ok {erg.get('ok')}, Urteil '{erg.get('urteil')}'")
if fehler: print("\n".join(fehler)); sys.exit(f"FEHLER: {len(fehler)} Erwartungen verletzt")
print(f"ok: {len(FAELLE)} Faelle (Kippung bis 8 Grad, Drehung bis +-20 Grad, Schub bis 30 %) vereint, Endlage waagerecht hoechstens {schlimm[0]:.2f} % der Turmhoehe / {schlimm[2]:.2f} Grad neben der wahren Lage; Massstabsfehler 10 % abgelehnt"
      + "".join(f" | BEKANNTE SCHWAECHE (erwarteter Fehlschlag): {b}" for b in bekannt))
