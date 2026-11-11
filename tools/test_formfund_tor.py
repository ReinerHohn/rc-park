#!/usr/bin/env python3
"""test_formfund_tor.py - BEWEIS des Formfund-Pruefers (Spec modelle/SPEC_FORMFUND_TOR.md): positive Faelle muessen bestehen, negative durchfallen.

Faelle (Teile-Ordner aus den Laufordnern des Kreises): Kennung -> (Lauf, vorher, nachher, Befund, Soll).
  positiv: Pruefer muss "besteht" (verbessert, nicht erfunden, sicher >= mittel) liefern.
  negativ: "besteht" waere Fehler (erfunden / nicht_verbessert / unsicher / ungeprueft sind ok).
  offen:   nur Auswertung.
Der synthetische Fall erzeugt "nachher" = Nachher-Stand + erfundener Kasten auf einer Stufe des Giebels (Spitze im Code allgemein: groesste Stufenflaeche).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_formfund_tor.py [--faelle a,b] [--nur_bilder] [--objekt kaufhaus_grob3]
"""
import sys, os, json, argparse, time, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formfund_pruefen as FFP

KREIS = "/media/oem/scan/rc-park_kreis/%s"
ARBEIT = FFP.ARBEIT_STD

# Kennung: (Laufordner, vorher, nachher, Befund, Soll, Hinweis)
FAELLE = {
    "a125135": ("20261111_125136a125135", "teile_r1_vorher_form", "teile_r1_nachher",
                "Staffelgiebel (Westgiebel) sind Treppen mit waagerechten Stufen, keine Saegezacken", "positiv", "Westgiebel Treppe"),
    "a095328": ("20261111_095328a095328", "teile_r1_vorher", "teile_r1_nachher",
                "Gewoelbeansatz: die Rippen des Kreuzgewoelbes in der Laube stimmen nicht", "positiv", "Gewoelbe Rippen"),
    "a104922": ("20261111_104922a104922", "teile_r1_vorher", "teile_r1_nachher",
                "Gewoelbeansatz: die Rippen des Kreuzgewoelbes in der Laube stimmen nicht", "positiv", "Gewoelbe Rippen (Alternativlauf)"),
    "a091923": ("20261111_091923a091923", "teile_r2_vorher", "teile_r2_nachher",
                "Das Tor ist rund statt spitz", "negativ", "Befund alt/falsch: Foto zeigt Spitzbogen"),
    "a102727": ("20261111_102727a102727", "teile_r1_vorher", "teile_r1_nachher",
                "Rinne/Traufe", "negativ", "Rinne zu hoch; generischer Befund"),
    "synth": (None, None, None, "Staffelgiebel Stufen am Westgiebel", "negativ", "Nachher-Stand plus erfundener Kasten 0,5 m auf einer Stufe"),
    "a105629": ("20261111_105629a105629", "teile_r2_vorher", "teile_r2_nachher",
                "Balkon: Seitengelaender / Stirnen der Bruestung", "offen", "Balkon-Stirnen, Baluster-Zahl angenommen"),
    "a123234": ("20261111_123235a123234", "teile_r1_vorher_form", "teile_r1_nachher",
                "Balkon: Seitengelaender / Stirnen der Bruestung", "offen", "Balkon-Stirnen (Alternativlauf)"),
}


def synth_nachher(basis_dir, aus_dir, teil="staffelgiebel__west", hoehe_m=0.5, breite_m=1.0, sk=0.087):
    """Kopiert (Symlinks) den Teile-Ordner und haengt an `teil` einen Kasten (hoehe_m hoch, breite_m entlang der Hauptachse, ganze Giebeldicke) auf die
    Stufe, die in der zweiten Staffelhaelfte (u>0) die breiteste Flaeche hat: erfundener Zusatzkoerper. Einheit der STL = H0-mm, sk = m je STL-Einheit."""
    os.makedirs(aus_dir, exist_ok=True)
    for n in os.listdir(basis_dir):
        d = os.path.join(aus_dir, n)
        if os.path.lexists(d): os.remove(d)
        os.symlink(os.path.join(basis_dir, n), d)
    m = trimesh.load(os.path.join(basis_dir, teil + ".stl"), force="mesh")
    c2 = m.vertices[:, :2].mean(0); v = m.vertices[:, :2] - c2; ax = np.linalg.eigh(np.cov(v.T) + 1e-9 * np.eye(2))[1][:, 1]; nrm = np.array([-ax[1], ax[0]])
    u = v @ ax; w = v @ nrm
    # zweite Stufe von der Spitze: Oberkante der Stufe bei u ~ 0.5 * u.max (Stufe mit Oberflaeche); Hoehe aus dem Netz
    u0 = 0.35 * u.max(); sel = np.abs(u - u0) < 0.03 * (u.max() - u.min()); z_top = float(m.vertices[sel, 2].max())
    dicke = float(w.max() - w.min()); wmitte = float((w.max() + w.min()) / 2)
    b = trimesh.creation.box(extents=[breite_m / sk, dicke, hoehe_m / sk])
    T = np.eye(4); T[:3, 0] = [ax[0], ax[1], 0]; T[:3, 1] = [nrm[0], nrm[1], 0]; T[:3, 2] = [0, 0, 1]
    T[:3, 3] = [c2[0] + ax[0] * u0 + nrm[0] * wmitte, c2[1] + ax[1] * u0 + nrm[1] * wmitte, z_top + hoehe_m / sk / 2 - 0.1 / sk]
    b.apply_transform(T)
    k = trimesh.util.concatenate([m, b]); os.remove(os.path.join(aus_dir, teil + ".stl")); k.export(os.path.join(aus_dir, teil + ".stl"))
    print(f"synth: Kasten bei u={u0:.1f}, z_top={z_top:.1f}, Dicke {dicke:.1f}", flush=True); return aus_dir


def lauf_fall(objekt, kennung, nur_bilder=False, modell="opus", arbeit_wurzel=ARBEIT, n_fotos=3):
    lauf, vo, na, befund, soll, hinweis = FAELLE[kennung]
    if kennung == "synth":
        L = KREIS % objekt + "/" + FAELLE["a125135"][0]
        vorher = L + "/teile_r1_nachher"; nachher = synth_nachher(vorher, os.path.join(arbeit_wurzel, "synth_nachher"))
        teile = ["staffelgiebel__west"]
    else:
        L = KREIS % objekt + "/" + lauf; vorher, nachher = L + "/" + vo, L + "/" + na; teile = None
    arbeit = os.path.join(arbeit_wurzel, kennung); os.makedirs(arbeit, exist_ok=True)
    return FFP.pruefen(objekt, vorher, nachher, befund, teile, os.path.join(arbeit, "erg.json"), None, arbeit, None, n_fotos, nur_bilder, modell)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--objekt", default="kaufhaus_grob3"); ap.add_argument("--faelle", default=",".join(FAELLE))
    ap.add_argument("--nur_bilder", action="store_true"); ap.add_argument("--modell", default="opus")
    a = ap.parse_args(); t0 = time.time(); tab = []; aufrufe = 0
    for k in a.faelle.split(","):
        e = lauf_fall(a.objekt, k, a.nur_bilder, a.modell); soll = FAELLE[k][4]; aufrufe += e.get("claude_aufrufe", 0) or 0
        u = e.get("urteil")
        ok = None if soll == "offen" or a.nur_bilder else ((u == "besteht") if soll == "positiv" else (u != "besteht" and u != "ungeprueft"))
        tab.append((k, soll, u, ok, e.get("sicher"), (e.get("begruendung") or e.get("grund") or "")[:300]))
        print(f"== {k}: soll {soll}, urteil {u}, ok {ok}", flush=True)
    print("\nFall | Soll | Urteil | ok | sicher | Begruendung")
    for r in tab: print(" | ".join(str(x) for x in r))
    print(f"claude-Aufrufe {aufrufe}, Laufzeit {time.time() - t0:.0f} s")
    json.dump({"tab": tab, "aufrufe": aufrufe}, open(os.path.join(ARBEIT, "test_ergebnis.json"), "w"), ensure_ascii=False, indent=1)
    gepr = [r for r in tab if r[1] in ("positiv", "negativ")]
    sys.exit(0 if a.nur_bilder or all(r[3] for r in gepr) else 1)


if __name__ == "__main__":
    main()
