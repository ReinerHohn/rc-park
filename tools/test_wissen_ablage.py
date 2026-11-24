#!/usr/bin/env python3
"""Synthetischer Test fuer tools/werkzeug_aehnlich.py, tools/wissen_ablage_pruefen.py und die Wortschatz-Gruppe in tools/wissen_suchen.py
(Anlass 24.11.2026: formsitz neu erdacht neben flaechen_mass + nie eingecheckter Spec; L55 5x vergeben; Martinstor-Hoehe-Rueckfall).
Verwandt: tools/test_wissensbaum_luecken.py (Lueckenpruefung + Wortsuche)."""
import io
import subprocess
import os
import sys
os.environ.setdefault("WISSEN_BEDEUTUNG", "aus")  # synthetische Wortsuche-Tests: ohne Embedding-Unterprozess (24.11.2026)
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import werkzeug_aehnlich as wa  # noqa: E402
import wissen_ablage_pruefen as wap  # noqa: E402
import wissen_suchen as ws  # noqa: E402

SYN = str(Path(__file__).resolve().parent / "wissen_synonyme.json")


def schreibe(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def lauf(fn, argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(argv)
    return rc, buf.getvalue()


def git(w, *a):
    subprocess.run(["git", "-C", str(w), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True)


def main():
    with tempfile.TemporaryDirectory() as t:
        w = Path(t)
        td = w / "tools"
        # ---- werkzeug_aehnlich: Wortschatz statt gleiches Wort, Komposita
        schreibe(td / "flaechen_mass.py", '"""flaechen_mass.py - Formvergleich ueber FLAECHEN statt Kanten: Modellflaechen gegen SAM-Masken je Foto,\n'
                 'Silhouette gegen den Himmel, IoU flaechengewichtet."""\n')
        schreibe(td / "dicht_bildwahl.py", '"""dicht_bildwahl.py - Bildwahl fuer die dichte Wolke: Fernansichten und fast gleiche Videobilder weglassen."""\n')
        schreibe(td / "fenster_tor.py", '"""fenster_tor.py - Fensterrahmen zaehlen und Laibungstiefe pruefen."""\n')
        schreibe(td / "helm_fit.py", "# Helm-Kegel an Kantengitter anpassen (RANSAC)\n")
        schreibe(td / "test_flaechen_mass.py", '"""Test Formvergleich Flaechen Silhouette Himmel"""\n')
        tr = wa.aehnliche("trennscharfes Formmass: Modellflaechen gegen Foto, Silhouette am Himmel, IoU", td)
        assert tr and tr[0][1] == "flaechen_mass.py", tr
        assert all(n != "test_flaechen_mass.py" for _, n, _ in tr), tr          # Tests spiegeln ihr Werkzeug -> nie Doppelgaenger
        tr = wa.aehnliche("Bildauswahl fuer die dichte Wolke", td)
        assert tr and tr[0][1] == "dicht_bildwahl.py", tr                       # "Bildauswahl" ~ "Bildwahl" ueber 4-Gramme
        assert wa.aehnliche("Druckerduese reinigen", td) == [], wa.aehnliche("Druckerduese reinigen", td)
        pp = wa.paare(td, 0.0)
        assert all("test_" not in a + b for _, a, b in pp), pp
        # Kopfpruefung: Werkzeuge ausserhalb der Basis brauchen "Verwandt:"/"Vorlaeufer:"
        schreibe(td / "werkzeug_basis.json", '{"werkzeuge": ["flaechen_mass.py", "dicht_bildwahl.py", "fenster_tor.py"]}')
        rc, aus = lauf(wa.main, ["--tools", str(td), "--kopf-pruefen"])
        assert rc == 1 and "tools/helm_fit.py" in aus and "flaechen_mass" not in aus, aus
        rc, aus = lauf(wa.main, ["--tools", str(td), "--kopf-pruefen", "--warnung"])
        assert rc == 0 and "WARNUNG" in aus, aus
        schreibe(td / "helm_fit.py", "# Helm-Kegel an Kantengitter anpassen (RANSAC)\n# Verwandt/Vorlaeufer: keine (wissen_suchen 'Helm' ohne Werkzeug)\n")
        rc, aus = lauf(wa.main, ["--tools", str(td), "--kopf-pruefen"])
        assert rc == 0 and "OK" in aus, aus
        rc, aus = lauf(wa.main, ["--tools", str(td), "--wie", str(td / "flaechen_mass.py")])
        assert "flaechen_mass.py" not in aus.split("\n")[0], aus                # sich selbst nie

        # ---- wissen_ablage_pruefen: ungetrackt, tote Verweise, Doppel-IDs (Sperrklinke), Widerspruchsliste
        m = w / "modelle"
        schreibe(w / "PROJEKT.md", "# Wurzel\n- Spec siehe modelle/archiv/SPEC_X.md\n")
        schreibe(m / "VERSUCHSREGISTER_TEST.md", "# R\n## BM - Teilmenge (02.11.)\nx\n## BN - Sweet Spot\ny\n")
        schreibe(m / "REZEPT_GEBAEUDE_AUS_FOTOS.md", "# Rezept\n- L54 eins\n- L55 zwei\n")
        schreibe(m / "WIDERSPRUECHE.md", "# W\n- Regelzeile ohne Trennpunkt\n- Turm: Hoehe · Werte: 54,8 m (Laser), 60 m (Text) · Status: geklaert · gilt: 54,8 m · 31.10.\n")
        git(w, "init", "-q")
        git(w, "add", "-A")
        git(w, "commit", "-qm", "basis")
        schreibe(m / "archiv" / "SPEC_X.md", "# nie eingecheckt\n")
        rc, aus = lauf(wap.main, ["--wurzel", str(w), "--basis", str(w / "b.json")])
        assert "modelle/archiv/SPEC_X.md" in aus and "1 ungetrackt: 1" in aus, aus          # ungetrackt = Warnung
        assert rc == 1 and "2 tote_verweise: 1" in aus, aus                                 # Verweis auf nicht eingecheckte Spec
        rc, aus = lauf(wap.main, ["--wurzel", str(w), "--basis", str(w / "b.json"), "--basis-schreiben"])
        rc, aus = lauf(wap.main, ["--wurzel", str(w), "--basis", str(w / "b.json")])
        assert rc == 0 and "WISSEN-ABLAGE OK" in aus, aus                                    # Sperrklinke: alter Stand geht durch
        # neue Doppel-ID (paralleler Agent vergibt dieselbe "naechste freie" ID) -> rot
        schreibe(m / "REZEPT_GEBAEUDE_AUS_FOTOS.md", "# Rezept\n- L54 eins\n- L55 zwei\n- L55 drei (anderer Agent)\n")
        rc, aus = lauf(wap.main, ["--wurzel", str(w), "--basis", str(w / "b.json")])
        assert rc == 1 and "REZEPT_GEBAEUDE_AUS_FOTOS.md L55 (2x)" in aus, aus
        schreibe(m / "VERSUCHSREGISTER_TEST.md", "# R\n## BM - Teilmenge (02.11.)\nx\n## BN - Sweet Spot\ny\n## BN - noch ein BN\nz\n")
        rc, aus = lauf(wap.main, ["--wurzel", str(w), "--basis", str(w / "b.json"), "--basis-schreiben"])
        rc, aus = lauf(wap.main, ["--wurzel", str(w), "--basis", str(w / "b.json")])
        assert rc == 0, aus                                                                   # in der Basis -> nur gemeldet
        schreibe(m / "VERSUCHSREGISTER_TEST.md", "# R\n## BM - x\n## BN - a\n## BN - b\n## BN - c\n")
        rc, aus = lauf(wap.main, ["--wurzel", str(w), "--basis", str(w / "b.json")])
        assert rc == 1 and "BN (3x)" in aus, aus                                             # dritte Vergabe ueber der Basis -> rot
        schreibe(m / "VERSUCHSREGISTER_TEST.md", "# R\n## BM - x\n## BN - a\n## BN - b\n")
        # Widerspruchszeile ohne Status / geklaert ohne gilt
        schreibe(m / "WIDERSPRUECHE.md", "# W\n- Turm: Hoehe · Werte: 54,8 m, 60 m · 31.10.\n- Bogen · Werte: 5 m, 6,55 m · Status: geklaert · 31.10.\n")
        rc, aus = lauf(wap.main, ["--wurzel", str(w), "--basis", str(w / "b.json")])
        assert rc == 1 and "WIDERSPRUECHE.md:2: ohne" in aus and "WIDERSPRUECHE.md:3: geklaert ohne" in aus, aus

        # ---- wissen_suchen: Wortschatz-Gruppe + genaue Gruppe zuerst
        schreibe(m / "NOTIZ.md", "# Notiz\nDrahtgitter aus Kanten\n")
        rc, aus = lauf(ws.main, ["Formmass", "--wurzel", str(w), "--memory", "aus", "--ohne-git", "--synonyme", SYN, "--max", "0"])
        assert "tools/flaechen_mass.py" in aus, aus                                          # ueber Synonym/Wortschatz gefunden
        rc, aus = lauf(ws.main, ["Silhouette Himmel Modellflaechen", "--wurzel", str(w), "--memory", "aus", "--ohne-git", "--ohne-synonyme"])
        assert "== Aehnliche Werkzeuge" in aus or "tools/flaechen_mass.py" in aus, aus
        e = ws.erweitern("Drahtgitter", ws.lade_synonyme(SYN))
        assert "Oberleitung" not in e and "Kante" in e, e                                    # Homonym "Draht" zieht nicht mehr mit
        assert "Oberleitung" in ws.erweitern("Draht", ws.lade_synonyme(SYN))
    # Projektkopien == Vorschlag fuer claude-mds (bis zur Uebernahme muessen beide gleich bleiben, sonst misst der Nachweis die falsche Fassung)
    hier = Path(__file__).resolve().parent
    v = hier / "claude_mds_vorschlag" / "claude" / "skills" / "doku-pflege"
    for a, b in (("wissen_suchen.py", "wissen_suchen.py"), ("werkzeug_aehnlich.py", "werkzeug_aehnlich.py"), ("wissen_wiederfinden.py", "wiederfinden.py")):
        if (v / b).exists():
            assert (hier / a).read_bytes() == (v / b).read_bytes(), f"tools/{a} weicht vom Vorschlag {v / b} ab - beide gleich halten (cp)"
    # ---- 24.11.2026 Vokabelluecke: Alltagsfragen (doc2query), Kompositazerlegung, Rangfusion, weicher Rueckfall ohne Embedding
    with tempfile.TemporaryDirectory() as t2:
        w2 = Path(t2)
        schreibe(w2 / "PROJEKT.md", "# Projekt\n")
        zeile = "- 07.11. · fTetWild auf mvs_fix → ✗ · 1506 Komponenten, offener Boden"
        schreibe(w2 / "Doku" / "projekt" / "netz.md", "# Netz\n## Versucht\n" + zeile + "\n- 08.11. · anderes Thema Dachziegel\n")
        schreibe(w2 / "Doku" / "projekt" / ".fragen" / "Doku__projekt__netz.md.jsonl",
                 '{"hash": "%s", "fragen": ["Die Huelle hat Loecher, wie wird sie dicht?"]}\n' % ws.zeilen_hash(zeile))
        t = ws.suchen(w2, ["Huelle", "Loecher"], [], None, False)
        assert t["Wissensbaum"] and "netz.md:3:" in t["Wissensbaum"][0][1], t          # Treffer nur ueber die Frage, gezeigt: Originalzeile
        assert "fTetWild" in t["Wissensbaum"][0][1]
        assert ws.teilwoerter("Gewoelberippen-Buendel", {"gewoelbe", "rippen", "buendel"})[:1] == ["gewoelberippen"]
        assert "speicher" in ws.teilwoerter("Arbeitsspeicher", {"arbeit", "speicher"})
        assert ws.bedeutung_verfuegbar({"bedeutung": {"python": "/gibt/es/nicht"}})[0] is None          # kein Absturz, nur Wortsuche
        f = ws.fusionieren({"Wissensbaum": [(5.0, "a.md:1: x"), (4.0, "a.md:2: y")], "Werkzeuge (Kopf)": []},
                           [{"name": "a.md", "nr": 2, "gruppe": "Wissensbaum", "wert": 0.9, "text": "y"},
                            {"name": "b.md", "nr": 7, "gruppe": "Wissensbaum", "wert": 0.8, "text": "z"}])
        assert [s for _, s in f["Wissensbaum"]][:1] == ["a.md:2: y"] and any(s.startswith("b.md:7:") for _, s in f["Wissensbaum"]), f
    print("OK test_wissen_ablage")


if __name__ == "__main__":
    main()
