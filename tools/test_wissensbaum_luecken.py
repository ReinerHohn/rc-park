#!/usr/bin/env python3
"""Synthetischer Test fuer tools/wissensbaum_luecken.py und tools/wissen_suchen.py (Anlass 24.11.: Register BM/BN fehlten im Baum)."""
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wissensbaum_luecken as wl  # noqa: E402
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


def main():
    with tempfile.TemporaryDirectory() as t:
        w = Path(t)
        m = w / "modelle"
        schreibe(w / "tools" / "bildwert.py", '"""bildwert.py - Bildwert messen: nur Bilder, die Luecken schliessen."""\n')
        schreibe(w / "tools" / "sweetspot.py", "# Sweet Spot der Aufloesung\n")
        schreibe(w / "tools" / "foto_wichtigkeit.py", '"""Wichtigkeit je Foto."""\n')
        schreibe(m / "VERSUCHSREGISTER_TEST.md", "# Register\n\n## A. Datenquellen\nText\n\n## BM - Teilmenge verliert Schichten (2026-11-02)\n"
                 "tools/foto_wichtigkeit.py zeigt: Tuermchen fehlen\n\n## BN - Sweet Spot = Aufloesung (2026-11-02)\nsweetspot.py 1000-1200 px\n"
                 "## CQ - Bildwert\nbildwert.py\n## CQ - S8 Kanten\nx\n## Poisson-Netz v3 (2026-11-03): Sued\ny\n")
        schreibe(m / "NICHTS_GEBRACHT.md", "# Sackgassen\n| Versuch | Ergebnis |\n|---|---|\n| Foto-Teilmenge fuer SfM | Tuermchen verloren |\n"
                 "- BS9 (7.11.) Bogenkontur: zerschmiert\n- NUTZERFREIGABE 7.11.: alles erlaubt\n## 2026-11-12: Kanten-NCC-Tiefenscan\n")
        schreibe(m / "REZEPT_GEBAEUDE_AUS_FOTOS.md", "## Lehren\n- **L1 (9.11.)**: eins\n- **L2**: zwei\n- **L2 (spaeter)**: doppelt\n- **L-EBENE1 (21.11.):** Ebenen\n")
        schreibe(m / "LOGBUCH_PROBE_2026-11-19.md", "# Logbuch\n## 09:20-09:35 Ausrichtung Martinstor\nx\n## Sackgassen / Zeitfresser\ny\n")
        schreibe(m / "archiv" / "INDEX.md", "# Archiv\n")
        schreibe(m / "archiv" / "STAND_2026-11-05.md", "# Stand 5.11.\nBildauswahl per Greedy\n")
        mem = w / "mem"
        schreibe(mem / "MEMORY.md", "- [Gpu](gpu-pc.md) - x\n- [Repo](../../git/x.md) - kein Memory\n")
        schreibe(mem / "archiv_index.md", "- [Alt](alt-notiz.md) - y\n")
        schreibe(mem / "gpu-pc.md", "---\ndescription: RTX 4060\n---\n")
        schreibe(mem / "alt-notiz.md", "---\ndescription: alt\n---\nSweetspot Stadtlauf\n")
        # Baum: nur ein Teil gedeckt
        schreibe(w / "PROJEKT.md", "# Wurzel\n")
        schreibe(w / "Doku" / "projekt" / "foto-sfm.md", "# Ast\n## Versucht\n- 02.11. · Teilmenge → ✗ [VERSUCHSREGISTER_TEST BM] `tools/foto_wichtigkeit.py`\n"
                 "- [NICHTS_GEBRACHT BS9] und [REZEPT L1]\n- [LOGBUCH_PROBE_2026-11-19 09:20] [archiv/STAND_2026-11-05]\n")
        rc, aus = lauf(wl.main, ["--wurzel", str(w), "--memory", str(mem), "--voll"])
        assert rc == 1, aus
        assert "VERSUCHSREGISTER_TEST.md: 6 Eintraege, 1 im Baum, 5 fehlend" in aus, aus
        assert "[VERSUCHSREGISTER_TEST CQ#2]" in aus and "[VERSUCHSREGISTER_TEST BN]" in aus, aus
        assert "REZEPT_GEBAEUDE_AUS_FOTOS.md: 4 Eintraege, 1 im Baum, 3 fehlend" in aus, aus
        assert "[REZEPT L2#2]" in aus, aus
        assert "NICHTS_GEBRACHT.md: 4 Eintraege, 1 im Baum, 3 fehlend" in aus, aus   # Tabellenkopf ist kein Eintrag
        assert "LOGBUCH_PROBE_2026-11-19.md: 2 Eintraege, 1 im Baum, 1 fehlend" in aus, aus
        assert "archiv/: 1 Eintraege, 1 im Baum, 0 fehlend" in aus, aus
        assert "memory (archiv_index): 2 Eintraege, 0 im Baum, 2 fehlend" in aus, aus     # ../-Verweis ins Repo zaehlt nicht
        assert "sweetspot.py" in aus and "bildwert.py" in aus and "foto_wichtigkeit.py (" not in aus, aus
        rc, _ = lauf(wl.main, ["--wurzel", str(w), "--memory", str(mem), "--warnung"])
        assert rc == 0
        # alles nachtragen (Unterast, wie im echten Baum) -> 0 Luecken
        schreibe(w / "Doku" / "projekt" / "foto-sfm" / "fotoauswahl.md",
                 "- [VERSUCHSREGISTER_TEST A] [VERSUCHSREGISTER_TEST BN] `tools/sweetspot.py`; [VERSUCHSREGISTER_TEST CQ, CQ#2] `tools/bildwert.py`\n"
                 "- [VERSUCHSREGISTER_TEST §Poisson-Netz v3 (2026-11-03)] [NICHTS_GEBRACHT §Foto-Teilmenge fuer SfM]\n"
                 "- [NICHTS_GEBRACHT §NUTZERFREIGABE 7.11.] [NICHTS_GEBRACHT §2026-11-12: Kanten-NCC]\n"
                 "- [REZEPT L2] [REZEPT L2#2] (L-EBENE1) [LOGBUCH_PROBE_2026-11-19 §Sackgassen / Zeitfresser]\n"
                 "- [memory/gpu-pc] [memory/alt-notiz]\n")
        rc, aus = lauf(wl.main, ["--wurzel", str(w), "--memory", str(mem)])
        assert rc == 0 and "OK: 0 Luecken" in aus, aus
        # Symlink-Quelle wird aufgeloest und nicht doppelt gezaehlt
        os.symlink(m / "VERSUCHSREGISTER_TEST.md", m / "VERSUCHSREGISTER_ZWEIT.md")
        rc, aus = lauf(wl.main, ["--wurzel", str(w), "--memory", str(mem)])
        assert rc == 0 and "ZWEIT" not in aus, aus

        # ---- wissen_suchen: Synonym findet Register, Archiv, Werkzeug, Memory; Baum zuerst
        rc, aus = lauf(ws.main, ["Bildauswahl", "--wurzel", str(w), "--memory", str(mem), "--ohne-git", "--max", "0", "--synonyme", SYN])
        assert rc == 0, aus
        assert aus.index("== Wissensbaum") < aus.index("== Register") < aus.index("== Archiv") < aus.index("== Memory"), aus
        assert "modelle/VERSUCHSREGISTER_TEST.md:7:" in aus, aus          # "Sweet Spot" ueber Synonym
        assert "modelle/archiv/STAND_2026-11-05.md:2:" in aus, aus
        assert "tools/bildwert.py:1:" in aus and "tools/foto_wichtigkeit.py" in aus, aus
        assert "memory/alt-notiz.md:4:" in aus, aus
        rc, aus = lauf(ws.main, ["Bildauswahl", "--wurzel", str(w), "--memory", "aus", "--ohne-git", "--ohne-synonyme"])
        assert "VERSUCHSREGISTER_TEST" not in aus, aus                     # ohne Synonyme nur das Wort
        rc, aus = lauf(ws.main, ["Lot", "--wurzel", str(w), "--memory", "aus", "--ohne-git", "--ohne-synonyme"])
        assert rc == 1, aus                                               # kurzes Wort nur ganz ("Pilot" o. ae. trifft nicht)
        rc, aus = lauf(ws.main, ["Tuermchen", "Teilmenge", "--und", "--wurzel", str(w), "--memory", "aus", "--ohne-git", "--synonyme", SYN])
        assert "NICHTS_GEBRACHT.md:4:" in aus and "foto-sfm.md" not in aus, aus
    print("OK test_wissensbaum_luecken")


if __name__ == "__main__":
    main()
