#!/usr/bin/env python3
"""druck_luft.py <teil.stl> [--schicht_mm 0.08] [--winkel_grad 45] [--min_mm2 2] [--unterfuettern AUS.stl | --stuetzen AUS.stl [--frei_mm 1.2] [--reich_mm 15]] - Luftinseln je Schicht finden (Druck-Vorpruefung, Masse in Druck-mm, z = Druckrichtung).

Anlass 17.11.2026: Uhr als Klipsteil auf dem Bambu wurde Spaghetti. Die Zeiger schwebten im Modell ueber dem Zifferblatt (78 mm2 bei z 2,2 mm, 30 mm2 bei z 2,9 mm ohne Halt);
der Drucker legte sie in die Luft, die Faeden rissen die Ziffern mit ab. Keine Pruefung hatte das gemeldet (druck_vorcheck misst Wanddicke, druck_teilung den Ueberhang
nur als Flaechenanteil der Aussenhaut).
Verfahren: waagerechte Schnitte im Schichtabstand; frei = Schnitt(z) minus Schnitt(z - Schicht) um Schicht x tan(winkel) verbreitert. Eine Flaeche, die mehr als --min_mm2
frei liegt UND an einer Stelle weiter als --bruecke_mm (5) vom tragenden Material entfernt ist (kuerzere Stuecke ueberbrueckt der Drucker), steht in der Liste mit Hoehe, Flaeche und Lage.
rc 3, wenn eine Luftinsel gefunden wurde; rc 0 sonst.
--unterfuettern AUS.stl: jede Luftinsel wird senkrecht bis auf das Material darunter (oder das Bett) verlaengert - fuer Reliefteile, die mit der Schauseite nach oben
liegen (Zeiger, Schilder, Wappen ueber einem Grund). NICHT fuer Teile mit Durchblicken (Boegen, Fenster): dort wuerde die Oeffnung zugegossen.
--stuetzen AUS.stl (Funktion stuetzen, auch von druck_teilung/druck_farbteile benutzt): bis --frei_mm ueber Material/Bett senkrecht auffuellen, sonst nur im INNENRAUM
eine 45-Grad-Konsole von der Wand (bis --reich_mm), Hohlplatten (Spalt <= 3 mm) zu; mit --saeule_mm2 / --gitter_mm kleine bzw. alle uebrigen Aussen-Inseln mit
Abbrech-Saeule bzw. Lamellen-Gitter (Stuetze im Modell, nach dem Druck abbrechen). druck_teilung waegt vorher Schnitt in der Inselunterseite gegen den Gitterbedarf.
Schnitthoehen +0,0137 mm versetzt (nie genau in einer waagerechten Modellflaeche).
"""
import sys, os, argparse, numpy as np, trimesh
from manifold3d import Manifold as M, Mesh, CrossSection as CS, JoinType, OpType, FillRule
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))


def luftinseln(modell, schicht=0.08, winkel=45.0, min_mm2=2.0, bruecke=5.0):
    bb = modell.bounding_box(); zs = np.arange(bb[2] + schicht / 2 + 0.0137, bb[5], schicht); S = [modell.slice(float(z)) for z in zs]; weit = schicht * np.tan(np.radians(winkel)); out = []      # +0,0137 mm: Schnitt nie genau in einer waagerechten Modellflaeche (17.11.2026: dort lieferte slice nur 1-2 Konturen statt 21 - Turmring fehlte); weit = schicht * np.tan(np.radians(winkel)); out = []
    for i in range(1, len(zs)):
        if S[i].is_empty(): continue
        frei = S[i] - S[i - 1].offset(weit, JoinType.Round, 2.0, 12)
        for g in frei.decompose():
            if g.area() < min_mm2: continue
            b_ = g.bounds(); r_ = weit + bruecke + 1.0                                  # Traeger nur im Umkreis der Flaeche verdicken (17.11.2026: der ganze Schnitt um 5,4 mm verdickt = 26 von 33 s Laufzeit am Turmteil; Ergebnis gleich)
            traeger = (S[i - 1] ^ CS.square((b_[2] - b_[0] + 2 * r_, b_[3] - b_[1] + 2 * r_)).translate((b_[0] - r_, b_[1] - r_))).offset(weit + bruecke, JoinType.Round, 2.0, 12)
            if (g - traeger).area() > 0.05:                                             # nur, was weiter als 'bruecke' von tragendem Material liegt (Fensterstuerze/Rippenansaetze ueberbrueckt der Drucker)
                b_ = g.bounds(); out.append(dict(i=i, z=float(zs[i]), flaeche=float(g.area()), mitte=[(b_[0] + b_[2]) / 2, (b_[1] + b_[3]) / 2], cs=g))
    return out, zs, S


def innenraum(cs, schliess=4.0):
    """Gefuellter Umriss eines Schnitts (Aussenkonturen ohne ihre Loecher), Fenster bis 2 x schliess vorher zugeschlossen: Hohlraeume gehoeren dazu, was aussen am
    Gebaeude haengt (Galerie, Vordach) und breite Oeffnungen nicht. (17.11.2026: ohne Zuschliessen war der Hohlraum eines Galeriebodens 'aussen', weil ein Fenster
    in derselben Hoehe den Turmring oeffnete.)"""
    if cs.is_empty(): return CS()
    po = cs.simplify(0.01).offset(schliess, JoinType.Round, 2.0, 8).to_polygons()
    aus = [q for q in po if len(q) >= 3 and 0.5 * float(np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1])) > 0]
    return CS(aus, FillRule.Positive).offset(-schliess, JoinType.Round, 2.0, 8) if aus else CS()


def stuetzen(modell, schicht=0.4, winkel=45.0, min_mm2=2.0, bruecke=5.0, frei_mm=1.2, reich_mm=15.0, runden=4, li=None, zs=None, S=None, saeule_mm2=0.0, hohl_mm=3.0, gitter_mm=0.0, gitter_dicke=0.8, gitter_schaetzen=0.0):
    """Luftinseln im Modell selbst unterbauen (17.11.2026, Turm-Bausatz: 6 von 7 Koerperteilen hatten Luftinseln) -> (Modell mit Stuetzen, Rest-Inseln, Protokoll).
    Zwei generische Arten, je Insel (alles in Druck-mm, z = Druckrichtung):
      FUELLEN  - Abstand zum Material darunter (oder zum Bett) <= frei_mm: senkrecht bis dorthin auffuellen (Unterseite plan; z. B. Boden 0,6 mm ueber dem Bett,
                 Traufbrett knapp ueber dem Schnitt, Platten-Rueckseite). Sichtbar wird hoechstens frei_mm.
      SCHRAEGE - Insel liegt im INNENRAUM des Schnitts (gefuellter Umriss: Hohlraum, hohle Wand, hohle Platte - nicht aussen am Gebaeude): darunter eine Konsole, die von den
                 Waenden mit 45 Grad (winkel) bis unter die Insel waechst; Reichweite = groesster Abstand der Insel von der Wand darunter, hoechstens reich_mm. Unten endet
                 sie an der Wand, am Boden darunter oder am Bett. Weiter als reich_mm von jeder Wand (grosse flache Decke) oder aussen (Galerie, Vordach): bleibt Insel
                 -> Schnitt in der Inselhoehe (druck_teilung) oder Stuetzen im Slicer.
      HOHLPLATTE - Abstand <= hohl_mm und darunter >= 90 % Platte (Spalt zwischen zwei Platten, z. B. ausgehoehlter Galerieboden): ganz fuellen.
                 ANNAHME: ein so schmaler Spalt (3 mm Druck) ist von aussen kaum sichtbar - er schliesst sich (Bild ansehen).
      SAEULE   - nur mit saeule_mm2 > 0: kleine Insel (<= saeule_mm2, z. B. tiefste Ecke eines flach geneigten Pultdachs) aussen bekommt eine senkrechte Saeule ihres
                 Grundrisses bis zum Material darunter oder zum Bett = gezielte Stuetze, nach dem Druck ABBRECHEN (Lage in prot['saeulen']).
      GITTER   - nur mit gitter_mm > 0, fuer alles, was danach noch frei haengt (aussen, z. B. Traufkasten): senkrechte Lamellen (gitter_dicke, Abstand gitter_mm) unter der
                 Insel bis zum Material/Bett = Stuetze im Modell, die druck_luft prueft (Slicer-Stuetzen prueft niemand); nach dem Druck ABBRECHEN (prot['gitter']).
    Rest-Inseln tragen 'hoehe' (Abstand zum Material darunter) - druck_teilung schaetzt daraus, was ein Gitter kosten wuerde.
    Nach jeder Runde werden die Inseln neu gesucht (Schraegen ueber Fensterluecken setzen neu an); hoechstens 'runden' Runden."""
    bb = modell.bounding_box(); weit = schicht * np.tan(np.radians(winkel)); erg = modell; prot = dict(fuellen=0, schraege=0, volumen_mm3=0.0, inseln_vorher=None, saeulen=[], gitter=[])
    def lamellen(x, abstand):
        """GITTER: Lamellen quer zur laengeren Seite der Insel, jede bis zu IHREM Material darunter -> (Koerper, Volumen mm3)."""
        q_ = x["cs"]; b_ = q_.bounds(); quer = (b_[2] - b_[0]) >= (b_[3] - b_[1]); out_ = []; v_ = 0.0; i = x["i"]; z_oben = float(zs[i]) + 0.25 * schicht
        for k_ in q_.decompose():
            kb = k_.bounds(); lo_, hi_ = (kb[0], kb[2]) if quer else (kb[1], kb[3]); pos = list(np.arange(lo_ + abstand / 2, hi_, abstand)) or [(lo_ + hi_) / 2]
            for p_ in pos:
                st_ = CS.square((gitter_dicke, kb[3] - kb[1] + 2)).translate((p_ - gitter_dicke / 2, kb[1] - 1)) if quer else CS.square((kb[2] - kb[0] + 2, gitter_dicke)).translate((kb[0] - 1, p_ - gitter_dicke / 2))
                for la in (k_ ^ st_).decompose():
                    if la.area() < 0.05: continue
                    jl = unterkante(la, i); zu = float(zs[jl]) if jl >= 0 else bb[2]; d_ = 0.01 if jl >= 0 else 0.0
                    out_.append(la.extrude(z_oben - zu + d_).translate((0, 0, zu - d_))); v_ += la.area() * (z_oben - zu)
        return out_, v_
    def unterkante(cs_, i):
        for j in range(i - 1, -1, -1):
            if (S[j] ^ cs_).area() > max(min(min_mm2, 0.3 * cs_.area()), 0.05 * cs_.area()): return j
        return -1
    if li is None: li, zs, S = luftinseln(modell, schicht, winkel, min_mm2, bruecke)
    prot["inseln_vorher"] = len(li); prot["flaeche_vorher_mm2"] = round(sum(x["flaeche"] for x in li), 1)
    versucht = set()
    for _ in range(runden):
        if not li: break
        stuecke = []; innen = {}
        def IN(j):
            if j not in innen: innen[j] = innenraum(S[j])
            return innen[j]
        for x in li:
            i = x["i"]; cs = x["cs"].offset(0.2, JoinType.Round, 2.0, 12); j0 = -1
            for j in range(i - 1, -1, -1):                                              # Material darunter = nennenswerte Ueberdeckung (17.11.2026: 0,5 mm2 Randberuehrung hielt die Konsole unter einer Hohlplatte nach einer Schicht an)
                if (S[j] ^ x["cs"]).area() > max(min_mm2, 0.05 * x["flaeche"]): j0 = j; break
            z_unten = float(zs[j0]) if j0 >= 0 else bb[2]; z_oben = float(zs[i]) + 0.25 * schicht
            if zs[i] - z_unten <= frei_mm + 1e-6 and (j0 < 0 or (S[j0] ^ cs).area() >= 0.5 * cs.area()):      # nur, wo darunter WEITGEHEND Material liegt (17.11.2026: Galerieboden 1,5 mm ueber einzelnen Konsolen wurde ganz aufgefuellt - neue Insel 1,2 mm tiefer)
                stuecke.append(cs.extrude(z_oben - z_unten + (0.01 if j0 >= 0 else 0.0)).translate((0, 0, z_unten - (0.01 if j0 >= 0 else 0.0)))); prot["fuellen"] += 1; continue
            if j0 >= 0 and zs[i] - z_unten <= hohl_mm + 1e-6 and max((S[j] ^ cs).area() for j in range(max(j0 - 2, 0), j0 + 1)) >= 0.9 * cs.area():      # HOHLPLATTE (17.11.2026: Galerieboden mit 2,4 mm Spalt zwischen zwei Platten, vom Generator ausgehoehlt; seitlich nur zu 33 % Wand): Platte darueber und darunter -> ganz fuellen
                stuecke.append(cs.extrude(z_oben - z_unten + 0.01).translate((0, 0, z_unten - 0.01))); prot["fuellen"] += 1; continue
            b_ = cs.bounds(); fen = CS.square((b_[2] - b_[0] + 2 * reich_mm + 2, b_[3] - b_[1] + 2 * reich_mm + 2)).translate((b_[0] - reich_mm - 1, b_[1] - reich_mm - 1))
            unten = S[i - 1] ^ fen; w = None
            for ww in np.arange(1.0, reich_mm + 0.01, 1.0):
                if (cs - unten.offset(ww, JoinType.Round, 2.0, 12)).area() < 0.02 * cs.area(): w = float(ww); break
            lagen_ = []; key = (round(x["mitte"][0]), round(x["mitte"][1]), round(float(zs[i])))
            if key in versucht: w = None                                                 # Schraege hat diese Insel schon nicht geloest (z. B. haengende Rinne ohne Wand im Umkreis) -> Saeule
            versucht.add(key)
            for j in (range(i - 1, j0, -1) if w is not None else []):
                r = w - (zs[i] - zs[j]) + schicht
                if r <= 0: break
                reg = cs ^ (S[j] ^ fen).offset(r, JoinType.Round, 2.0, 12) ^ IN(j)
                if reg.is_empty(): continue
                z1 = z_oben if j == i - 1 else float(zs[j]) + 0.5 * schicht + 0.25 * schicht; z0 = float(zs[j0]) if j == j0 + 1 and j0 >= 0 else max(float(zs[j]) - 0.5 * schicht, bb[2])
                lagen_.append(reg.extrude(z1 - z0).translate((0, 0, z0)))
            if lagen_: stuecke += lagen_; prot["schraege"] += 1
            elif x["flaeche"] <= saeule_mm2:                                            # Grundriss mindestens 3,2 mm rund (ein schmaler Streifen von 8 mm2 und 5 cm Hoehe stuende nicht)
                fuss = x["cs"] + CS.circle(1.6, 24).translate((x["mitte"][0], x["mitte"][1]))
                stuecke.append(fuss.extrude(z_oben - z_unten + (0.01 if j0 >= 0 else 0.0)).translate((0, 0, z_unten - (0.01 if j0 >= 0 else 0.0))))
                prot["saeulen"].append(dict(x_mm=round(x["mitte"][0], 1), y_mm=round(x["mitte"][1], 1), z_mm=round(float(zs[i]), 2), hoehe_mm=round(float(z_oben - z_unten), 1), flaeche_mm2=round(x["flaeche"], 1)))
            elif gitter_mm > 0:
                st_l, v_ = lamellen(x, gitter_mm); stuecke += st_l; nl_ = len(st_l)
                if nl_: prot["gitter"].append(dict(x_mm=round(x["mitte"][0], 1), y_mm=round(x["mitte"][1], 1), z_mm=round(float(zs[i]), 2), flaeche_mm2=round(x["flaeche"], 1), lamellen=nl_, volumen_mm3=round(v_)))
        if not stuecke: break
        neu = M.batch_boolean(stuecke, OpType.Add); v0 = erg.volume(); erg = erg + neu; prot["volumen_mm3"] += erg.volume() - v0
        li, zs, S = luftinseln(erg, schicht, winkel, min_mm2, bruecke)
    for x in li:
        j_ = unterkante(x["cs"], x["i"]); x["hoehe"] = float(zs[x["i"]] - (zs[j_] if j_ >= 0 else bb[2]))
        if gitter_schaetzen > 0: x["gitter_mm3"] = lamellen(x, gitter_schaetzen)[1]      # was ein Gitter hier kosten wuerde (druck_teilung waegt damit Schnitt gegen Stuetze)
    prot["volumen_mm3"] = round(prot["volumen_mm3"], 1); prot["inseln_rest"] = len(li); prot["flaeche_rest_mm2"] = round(sum(x["flaeche"] for x in li), 1)
    return erg, li, prot


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stl"); ap.add_argument("--schicht_mm", type=float, default=0.08); ap.add_argument("--winkel_grad", type=float, default=45.0)
    ap.add_argument("--min_mm2", type=float, default=2.0); ap.add_argument("--bruecke_mm", type=float, default=5.0, help="bis zu diesem Abstand vom Traeger gilt frei Gedrucktes als Bruecke/kurzer Ueberhang"); ap.add_argument("--unterfuettern", default="")
    ap.add_argument("--stuetzen", default="", help="AUS.stl: Inseln generisch unterbauen (Funktion stuetzen: fuellen bis --frei_mm, sonst 45-Grad-Konsole im Innenraum bis --reich_mm)"); ap.add_argument("--frei_mm", type=float, default=1.2); ap.add_argument("--reich_mm", type=float, default=15.0); ap.add_argument("--saeule_mm2", type=float, default=0.0, help="kleine Aussen-Inseln bis zu dieser Flaeche mit Abbrech-Saeule stuetzen (0 = aus)"); ap.add_argument("--gitter_mm", type=float, default=0.0, help="Rest-Inseln mit Lamellen in diesem Abstand stuetzen (0 = aus)"); a = ap.parse_args()
    m = trimesh.load(a.stl, process=True); mo = M(Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
    if mo.is_empty(): print("FEHLER: kein geschlossener Koerper"); return 2
    li, zs, S = luftinseln(mo, a.schicht_mm, a.winkel_grad, a.min_mm2, a.bruecke_mm)
    for x in li[:30]: print(f"  LUFTINSEL z {x['z']:.2f} mm: {x['flaeche']:.1f} mm2 frei bei x {x['mitte'][0]:.1f} / y {x['mitte'][1]:.1f}")
    print(f"{os.path.basename(a.stl)}: {len(li)} Luftinsel(n) (Schicht {a.schicht_mm} mm, {a.winkel_grad:g} Grad, ab {a.min_mm2:g} mm2)" + (" - NICHT ohne Stuetzen druckbar" if li else " - frei haengt nichts"))
    if a.stuetzen:
        erg, rest, prot = stuetzen(mo, a.schicht_mm, a.winkel_grad, a.min_mm2, a.bruecke_mm, a.frei_mm, a.reich_mm, li=li, zs=zs, S=S, saeule_mm2=a.saeule_mm2, gitter_mm=a.gitter_mm)
        from bauteile import stl_schreiben; stl_schreiben(erg, a.stuetzen, b"rcpark stuetzen")
        for x in rest[:30]: print(f"  BLEIBT z {x['z']:.2f} mm: {x['flaeche']:.1f} mm2 bei x {x['mitte'][0]:.1f} / y {x['mitte'][1]:.1f}")
        for q in prot["gitter"]: print(f"  GITTER (nach dem Druck abbrechen) bei x {q['x_mm']} / y {q['y_mm']}, z {q['z_mm']} mm: {q['lamellen']} Lamellen, {q['volumen_mm3']} mm3")
        for q in prot["saeulen"]: print(f"  SAEULE (nach dem Druck abbrechen) bei x {q['x_mm']} / y {q['y_mm']}, z {q['z_mm']} mm, {q['hoehe_mm']} mm hoch")
        print(f"gestuetzt: {prot['fuellen']} gefuellt, {prot['schraege']} Schraegen, {len(prot['saeulen'])} Saeulen, +{prot['volumen_mm3']:.0f} mm3; danach {len(rest)} Luftinsel(n) -> {a.stuetzen}"); return 3 if rest else 0
    if a.unterfuettern:
        if not li: import shutil; shutil.copy(a.stl, a.unterfuettern); print("nichts zu unterfuettern ->", a.unterfuettern); return 0
        bb = mo.bounding_box(); erg = mo; li2 = li; runde = 0
        while li2 and runde < 6:                                                  # 17.11.2026: eine Runde endete an der ersten TEILWEISEN Auflage - Rest hing weiter frei
            runde += 1; stuetz = []
            for x in li2:
                z_oben = x["z"]; z_unten = bb[2]
                for j in range(x["i"] - 1, -1, -1):                               # bis zur ersten Schicht darunter, die unter der Insel Material hat
                    if not (S[j] ^ x["cs"]).is_empty(): z_unten = float(zs[j]); break
                stuetz.append(x["cs"].offset(0.2, JoinType.Round, 2.0, 12).extrude(z_oben - z_unten + 0.02).translate((0, 0, z_unten - 0.01)))
            erg = erg + M.batch_boolean(stuetz, OpType.Add)
            li2, zs, S = luftinseln(erg, a.schicht_mm, a.winkel_grad, a.min_mm2, a.bruecke_mm)
        from bauteile import stl_schreiben; stl_schreiben(erg, a.unterfuettern, b"rcpark unterfuettert")
        print(f"unterfuettert: +{(erg.volume() - mo.volume()):.1f} mm3, danach {len(li2)} Luftinsel(n) -> {a.unterfuettern}"); return 3 if li2 else 0
    return 3 if li else 0


if __name__ == "__main__":
    sys.exit(main())
