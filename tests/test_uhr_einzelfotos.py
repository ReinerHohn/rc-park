#!/usr/bin/env python3
"""test_uhr_einzelfotos.py - fester synthetischer Test fuer den Befund 'Uhr Sued (f01) fehlt' aus Kettenlauf 1122x (24.11.2026), < 30 s, nur CPU.

Befund (modelle/schwabentor-1122/audit/neben_detail_uhr_f01.jpg, uhren_auto.json f01 uhren = []): im feinen Wandbild (Mosaik) laeuft eine Naht quer durch den
Ziffernring (unteres Drittel aus einem anderen Foto, verdreht/versetzt und ausgewaschen) -> 12er-Teilung 1,14 < Tor 1,2, Uhr verworfen. In 1122w kam sie nur durch den Teillauf
(anders zusammengesetztes Mosaik). Teile:
  1 NAHT       Mosaik mit Naht durch den Ring: zifferblatt_beleg im Mosaik faellt durch (Vorbedingung), die Mehrheit der Einzelfotos (4 Fotos, Zeiger je Foto anders,
               Versatz bis 0,2 m, ein Foto mit Oberleitung quer, eines mit altem dunklem Anstrich) belegt die Uhr -> uhren_auto.json hat die Uhr, Mitte/Durchmesser stimmen.
  2 UNABHAENGIG dasselbe mit sauberem Mosaik -> dieselbe Uhr (Urteil haengt nicht davon ab, welche Fotos das Mosaik zusammensetzen = ob ein Teillauf lief).
  3 ROT-PROBE  Heiligenschein (Gold mit 9 Steinen) und Rundfenster ohne Teilung, auch in allen Einzelfotos -> verworfen, Grund nennt die Einzelfotos.
  4 ZU WENIG   nur 2 Einzelfotos zeigen die Scheibe -> verworfen (Mehrheit braucht >= 3 Fotos).
  5 RELIEF     zifferblatt_aus_fotos richtet das Foto mit anderem Anstrich ueber den Kantenbetrag aus (Grauwert-ECC scheitert) -> Relief aus >= 3 Fotos.
Werte sind Testgeometrie, kein Objektmass.
"""
import sys, os, json, shutil, subprocess, numpy as np, cv2
HIER = os.path.dirname(os.path.abspath(__file__)); TOOLS = os.path.join(os.path.dirname(HIER), "tools"); sys.path.insert(0, TOOLS)
from pfade import temp_ordner
import uhren_wandbild as UW

F = 0
def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text); F += 0 if ok else 1

c = 0.01; R = dict(u0=0.0, z1=8.0, nu=1300, nz=800, zelle=c)
uu = R["u0"] + (np.arange(R["nu"]) + 0.5) * c; zz = R["z1"] - (np.arange(R["nz"]) + 0.5) * c; UU, ZZ = np.meshgrid(uu, zz)
UC, ZC, RA, RI = 2.0, 5.0, 1.0, 0.65; HC = 6.5; FC = 10.5
GOLD = (40, 175, 225)


def bild(seed, dx=0.0, dz=0.0, zeiger=0.0, ring=(125, 130, 135), feld=(205, 175, 150), draht=False, uhr=True, rest=True, dreh=0.0):
    rng = np.random.default_rng(seed); B = np.zeros((R["nz"], R["nu"], 3), np.float32); B[:] = (228, 232, 236); B += rng.normal(0, 3, B.shape)
    if uhr:
        u_, z_ = UC + dx, ZC + dz; rr = np.hypot(UU - u_, ZZ - z_); ph = np.arctan2(UU - u_, ZZ - z_)
        B[rr <= RA] = ring; B[rr <= RI] = feld; B[(rr > 0.96 * RA) & (rr <= RA)] = GOLD; B[(rr > RI - 0.02) & (rr <= RI + 0.02)] = GOLD
        for n_ in range(12):
            a_ = np.radians(30 * n_ + dreh); B[(np.abs(np.sin(ph - a_)) * rr < 0.035) & (rr > RI + 0.05) & (rr < RA - 0.06) & (np.cos(ph - a_) > 0)] = GOLD
        for a_, l_, b_ in ((zeiger, 0.92, 0.03), (zeiger * 0.37 + 1.9, 0.6, 0.04)):                  # Zeiger reichen in den Ring (wie Schwabentor: Sonne/Mond)
            B[(np.abs(np.sin(ph - a_)) * rr < b_) & (rr < l_ * RA) & (np.cos(ph - a_) > 0)] = GOLD
        B[np.hypot(UU - u_ - 0.75 * np.sin(zeiger), ZZ - z_ - 0.75 * np.cos(zeiger)) < 0.1] = GOLD     # Sonne am Zeiger
    if rest:
        u_ = HC + dx; rh = np.hypot(UU - u_, ZZ - ZC)                                                   # Heiligenschein: Gold, 9 Steine auf 270 Grad, Gesicht + Koerper
        B[rh <= 0.9] = GOLD; B[(rh > 0.86) & (rh <= 0.9)] = (60, 90, 120)
        for a_ in np.radians(np.linspace(-135, 135, 9)): B[np.hypot(UU - (u_ + 0.72 * np.sin(a_)), ZZ - (ZC + 0.72 * np.cos(a_))) < 0.06] = (40, 40, 40)
        B[np.hypot((UU - u_) / 0.42, (ZZ - ZC + 0.05) / 0.55) < 1] = (120, 140, 170); B[(np.abs(UU - u_) < 0.6) & (ZZ < ZC - 0.45) & (rh < 0.84)] = (90, 60, 50)
        rf = np.hypot(UU - FC - dx, ZZ - ZC); B[rf <= 0.8] = (190, 195, 200); B[rf <= 0.68] = (45, 40, 38)  # Rundfenster: Rahmen + dunkles Glas, keine Teilung
        B[rf <= 0.68] += rng.normal(0, 6, B[rf <= 0.68].shape)
    if draht: B[np.abs((ZZ - ZC) - 0.35 * (UU - UC)) < 0.015] = (30, 30, 30)
    return B.clip(0, 255).astype(np.uint8)


def anlegen(T, naht, n_fotos):
    FF = os.path.join(T, "fassade_fein"); os.makedirs(os.path.join(FF, "ortho_f00_einzeln"), exist_ok=True)
    json.dump(dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], raster=R)]), open(os.path.join(FF, "fassaden.json"), "w"))
    M = bild(1, zeiger=0.4)
    if naht:                                                                       # unteres Drittel der Scheibe aus einem anderen, versetzten und ausgewaschenen Foto
        A = bild(2, zeiger=2.5, dreh=15.0); A = (0.6 * A + 0.4 * 245).astype(np.uint8)   # anderes Foto: Ziffern um eine halbe Teilung verdreht entzerrt, heller
        m_ = (ZZ < ZC - 0.1) & (np.abs(UU - UC) < 1.3); M[m_] = A[m_]
    cv2.imwrite(os.path.join(FF, "ortho_f00_fein.png"), M)
    var = [dict(dx=0.0, zeiger=0.3), dict(dx=0.15, dz=0.05, zeiger=1.4, draht=True), dict(dx=-0.18, dz=-0.04, zeiger=3.6, ring=(45, 40, 40), feld=(70, 60, 40)), dict(dx=0.08, dz=0.1, zeiger=5.0)]
    for i, v in enumerate(var[:n_fotos]): cv2.imwrite(os.path.join(FF, "ortho_f00_einzeln", f"foto_{i}.png"), bild(10 + i, **v))
    K = lambda u0, u1, z0, z1: dict(klasse="uhr", stimmen=5, gesehen=6, u0=u0, u1=u1, z0=z0, z1=z1)
    json.dump(dict(fassaden=dict(f00=dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], elemente=[K(1.0, 3.0, 4.0, 6.0), K(5.6, 7.4, 4.1, 5.9), K(9.7, 11.3, 4.2, 5.8)]))),
              open(os.path.join(T, "elemente.json"), "w"))
    od = os.path.join(T, "obj"); os.makedirs(od, exist_ok=True); json.dump(dict(name="test"), open(os.path.join(od, "objekt.json"), "w"))
    return FF, od, M


def lauf(T, FF, od, zifferblatt=False):
    aus = os.path.join(od, "audit", "uhren_auto.json")
    p = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "uhren_wandbild.py"), os.path.join(od, "objekt.json"), FF, "--elemente", os.path.join(T, "elemente.json"), "--aus", aus],
                       capture_output=True, text=True, env=dict(os.environ, OHNE_ZIFFERBLATT="0" if zifferblatt else "1"))
    return p, (json.load(open(aus))["f00"] if os.path.exists(aus) else None)


W = temp_ordner("test_uhr_einzelfotos_"); erg = {}
for name, naht, n_f in (("naht", True, 4), ("sauber", False, 4), ("zwei", True, 2)):
    T = os.path.join(W, name); os.makedirs(T, exist_ok=True); FF, od, M = anlegen(T, naht, n_f)
    if name == "naht":
        b = UW.zifferblatt_beleg(cv2.cvtColor(M, cv2.COLOR_BGR2GRAY), (UC - R["u0"]) / c, (R["z1"] - ZC) / c, RA / c)
        pruef(not b["ok"], f"1 Vorbedingung: Mosaik mit Naht faellt im Mosaik-Beleg durch ({b['verh']}, k={b['k']})")
    p, J = lauf(T, FF, od, zifferblatt=(name == "naht")); erg[name] = J
    pruef(J is not None, f"{name}: uhren_wandbild lief (rc {p.returncode}) {(p.stdout + p.stderr)[-200:] if J is None else ''}")
    if J is None: continue
    U = J["uhren"]; V = J["verworfen"]
    if name in ("naht", "sauber"):
        pruef(len(U) == 1, f"{name}: genau eine Uhr ({[(x['u'], x['z'], x['d_aussen']) for x in U]})")
        if U: pruef(abs(U[0]["u"] - UC) < 0.08 and abs(U[0]["z"] - ZC) < 0.08 and abs(U[0]["d_aussen"] - 2 * RA) < 0.15, f"{name}: Uhr vermessen u {U[0]['u']} z {U[0]['z']} d {U[0]['d_aussen']}")
        pruef(any(v["kasten"][0] > 5 and v["kasten"][0] < 8 and "kein Zifferblatt" in v["grund"] for v in V), f"3 {name}: Heiligenschein verworfen ({[v['grund'][:60] for v in V]})")
        pruef(any(v["kasten"][0] > 9 and ("kein Zifferblatt" in v["grund"] or "Kreis nur" in v["grund"]) for v in V), f"3 {name}: Rundfenster verworfen")
        if name == "naht":
            pruef(bool(U) and (U[0].get("beleg_einzelfotos") or {}).get("n_ok", 0) >= 3, f"1 naht: Mehrheit der Einzelfotos belegt ({U[0].get('beleg_einzelfotos') if U else None})")
            pruef(any(v["kasten"][0] > 5 and "Einzelfotos" in v["grund"] for v in V), "3 naht: Rot-Probe auch in den Einzelfotos geprueft (Grund nennt sie)")
            pruef(bool(U) and bool(U[0].get("zifferblatt")) and len(U[0].get("zifferblatt_fotos", [])) >= 3,
                  f"5 Relief aus >= 3 Einzelfotos trotz anderem Anstrich ({U[0].get('zifferblatt_fotos') if U else None}, {U[0].get('zifferblatt_fehlt') if U else ''})")
            if U and U[0].get("zifferblatt"): print("  Kontrollbild: " + os.path.join(od, "audit", U[0]["zifferblatt"][:-4] + ".jpg"))
    else:
        pruef(len(U) == 0 and any(v["kasten"][0] < 4 and "Einzelfotos" in v["grund"] for v in V), f"4 zwei Fotos: verworfen ({[v['grund'][-70:] for v in V if v['kasten'][0] < 4]})")
if erg.get("naht") and erg.get("sauber") and erg["naht"]["uhren"] and erg["sauber"]["uhren"]:
    a_, b_ = erg["naht"]["uhren"][0], erg["sauber"]["uhren"][0]
    pruef(abs(a_["u"] - b_["u"]) < 0.05 and abs(a_["z"] - b_["z"]) < 0.05, "2 Uhr gleich mit Naht- und sauberem Mosaik")
print("FEHLER: %d" % F if F else "ALLE BESTANDEN (Uhr trotz Mosaik-Naht aus Mehrheit der Einzelfotos, unabhaengig vom Mosaik, Heiligenschein/Rundfenster verworfen, 2 Fotos zu wenig, Relief ueber Kanten-ECC)")
if not F: shutil.rmtree(W, ignore_errors=True)
sys.exit(1 if F else 0)
