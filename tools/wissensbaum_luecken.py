#!/usr/bin/env python3
"""Wissensbaum-Lueckenpruefung: steht jeder Register-/Archiv-/Logbuch-/Memory-Eintrag als Zeile im lebenden Wissensbaum?

Anlass 24.11.2026: der Baum Doku/projekt/ (Commit ff7c30b77 "Verlustpruefung 0 fehlend") enthielt nur 59 von 125
Abschnitten des VERSUCHSREGISTER_MARTINSTOR; Vorarbeit Bildwert/Sweet Spot/Fotoauswahl/Teilmenge (BM/BN) wurde nicht
gefunden, ein Agent doppelt beauftragt. Das alte "0 fehlend" war eine Stichprobe von Hand, kein Werkzeug.

Quellen (je Eintrag ein Schluessel) und wie der Baum ihn nennen muss (Verweis in einer Baumzeile):
  VERSUCHSREGISTER_*.md   je "## <ID>." Abschnitt        [VERSUCHSREGISTER_MARTINSTOR J] (auch "VERSUCHSREGISTER J", "Register J")
  NICHTS_GEBRACHT.md      je "- <ID> (" Zeile             [NICHTS_GEBRACHT BS9]
                          je "##"-Abschnitt/Tabellenzeile [NICHTS_GEBRACHT §<Anfang der Ueberschrift/ersten Zelle>]
  REZEPT_GEBAEUDE_...     je Lehre L<n>/L-<X><n>          [REZEPT L47] (doppelte IDs: L55, L55#2, ...)
  LERNJOURNAL_MARTINSTOR  je "## Eintrag <n>"             [LERNJOURNAL 9]
  ERKENNTNISSE.md         je "- <Datum> · ..." Zeile      [ERKENNTNISSE §<Anfang des Textes nach Datum/Art>]
  LOGBUCH_*.md (modelle/) je "##"-Abschnitt               [LOGBUCH_<NAME> §<Anfang der Ueberschrift>] (Uhrzeit allein reicht, z. B. 17:15)
  archiv/*.md             je Datei                        archiv/<NAME> irgendwo in einer Baumzeile
  Memory (archiv_index)   je verlinkte Datei              memory/<name> irgendwo in einer Baumzeile
"§<Anfang>" trifft, wenn der normalisierte Text (klein, nur Buchstaben/Ziffern) ein Anfang der normalisierten
Ueberschrift ist (mind. 4 Zeichen). Symlinks werden aufgeloest, modelle/inhalt/ (Inhaltsverzeichnisse) ist keine Quelle.

Werkzeug-Abgleich: jedes tools/<x>.py, das in einem Register-Eintrag (VR, NG, REZEPT, LERNJOURNAL, ERKENNTNISSE)
genannt ist, muss irgendwo im Baum (Doku/projekt/**, PROJEKT.md) vorkommen.

Aufruf: python3 -I tools/wissensbaum_luecken.py [--wurzel DIR] [--memory DIR] [--json AUS.json] [--warnung] [--voll]
rc 0 = keine Luecke, rc 1 = Luecken (mit --warnung immer rc 0), rc 2 = Aufruffehler.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = s.replace("ß", "ss")
    return "".join(c for c in s if c.isalnum() and ord(c) < 128)


def lies(p):
    try:
        return Path(p).resolve().read_text(encoding="utf-8", errors="replace").split("\n")
    except OSError:
        return []


class Eintrag:
    def __init__(self, quelle, art, schluessel, datei, von, bis, titel, text=""):
        self.quelle, self.art, self.schluessel = quelle, art, schluessel
        self.datei, self.von, self.bis, self.titel, self.text = datei, von, bis, titel, text

    def verweis(self):
        if self.art == "datei":
            return self.schluessel
        if self.art == "anfang":
            t = re.split(r"[\[\],;]|" + QUELL_WORT.pattern, self.titel)[0][:40].strip()
            return f"[{self.quelle} §{t}]"
        return f"[{self.quelle} {self.schluessel}]"

    def als_dict(self, wurzel, tools_dir=None):
        try:
            d = str(Path(self.datei).relative_to(wurzel))
        except ValueError:
            d = str(self.datei)
        return {"quelle": self.quelle, "schluessel": self.schluessel, "datei": d, "von": self.von,
                "bis": self.bis, "titel": self.titel[:160], "verweis": self.verweis(),
                "werkzeuge": [f"tools/{t}.py" for t in werkzeuge_in(self.text, tools_dir)] if tools_dir else []}


def _abschnitte(zeilen, kopf_re):
    """[(zeilennr 1-basiert, match, ende)] fuer Ueberschriften, ende = Zeile vor der naechsten gleichrangigen."""
    treffer = [(i + 1, m) for i, z in enumerate(zeilen) if (m := kopf_re.match(z))]
    aus = []
    for k, (n, m) in enumerate(treffer):
        ende = treffer[k + 1][0] - 1 if k + 1 < len(treffer) else len(zeilen)
        aus.append((n, m, ende))
    return aus


def _text(zeilen, von, bis):
    return "\n".join(zeilen[von - 1:bis])


ID_RE = re.compile(r"^(?:Register\s+)?([A-Z]{1,3}[0-9]{0,3}[a-z]?(?:-[A-Z][A-Za-z]+)?)(?=[\s.:)(\-\u2013,]|$)")


def _eindeutig(k, ids):
    if k in ids:
        j = 2
        while f"{k}#{j}" in ids:
            j += 1
        k = f"{k}#{j}"
    ids.add(k)
    return k


def quelle_versuchsregister(p):
    z = lies(p)
    name = Path(p).stem
    aus, ids = [], set()
    for n, m, e in _abschnitte(z, re.compile(r"^## (.*)")):
        t = m.group(1).strip()
        mi = ID_RE.match(t)
        if mi:
            aus.append(Eintrag(name, "id", _eindeutig(mi.group(1), ids), p, n, e, t, _text(z, n, e)))
        else:
            aus.append(Eintrag(name, "anfang", norm(t), p, n, e, t, _text(z, n, e)))
    return aus


def quelle_nichts_gebracht(p):
    z = lies(p)
    aus, ids = [], set()
    trenn = lambda x: x.startswith("|") and x.strip("| ") and set(x.replace("|", "").strip()) <= set("-: ")
    for i, zeile in enumerate(z, 1):
        if zeile.startswith("- "):
            t = re.sub(r"^[*`]+", "", zeile[2:].strip())
            mi = ID_RE.match(t)
            tok = mi.group(1) if mi else ""
            if mi and (any(c.isdigit() for c in tok) or "-" in tok):
                aus.append(Eintrag("NICHTS_GEBRACHT", "id", _eindeutig(tok, ids), p, i, i, t, zeile))
            elif norm(t):
                aus.append(Eintrag("NICHTS_GEBRACHT", "anfang", norm(t), p, i, i, t, zeile))
        elif zeile.startswith("## "):
            aus.append(Eintrag("NICHTS_GEBRACHT", "anfang", norm(zeile[3:]), p, i, i, zeile[3:].strip(), zeile))
        elif zeile.startswith("|") and not trenn(zeile) and not (i < len(z) and trenn(z[i])):
            erste = re.sub(r"[`*]", "", zeile.strip().strip("|").split("|")[0]).strip()
            if norm(erste):
                aus.append(Eintrag("NICHTS_GEBRACHT", "anfang", norm(erste), p, i, i, erste, zeile))
    return aus


def quelle_rezept(p):
    z = lies(p)
    aus, ids = [], {}
    l_re = re.compile(r"^\s*[-|]\s*\**(L(?:-[A-Z]+)?[0-9]+[a-z]?)\b")
    for i, zeile in enumerate(z, 1):
        m = l_re.match(zeile)
        if not m:
            continue
        k = m.group(1)
        ids[k] = ids.get(k, 0) + 1
        if ids[k] > 1:
            k = f"{k}#{ids[k]}"
        aus.append(Eintrag("REZEPT", "id", k, p, i, i, zeile.strip()[:200], zeile))
    return aus


def quelle_lernjournal(p):
    z = lies(p)
    aus = []
    for n, m, e in _abschnitte(z, re.compile(r"^## (.*)")):
        t = m.group(1)
        mm = re.match(r"Eintrag (\d+[a-z]?)", t)
        if mm:
            aus.append(Eintrag("LERNJOURNAL", "id", mm.group(1), p, n, e, t, _text(z, n, e)))
        else:
            aus.append(Eintrag("LERNJOURNAL", "anfang", norm(t), p, n, e, t, _text(z, n, e)))
    return aus


def quelle_erkenntnisse(p):
    z = lies(p)
    aus = []
    for i, zeile in enumerate(z, 1):
        m = re.match(r"^- \d{1,2}\.\d{1,2}\.(?:\d{2,4})?\s*·\s*([^·]+?)\s*·\s*(.*)", zeile)
        if m:
            t = m.group(2)
            aus.append(Eintrag("ERKENNTNISSE", "anfang", norm(t), p, i, i, t, zeile))
    return aus


def quelle_logbuch(p):
    z = lies(p)
    name = Path(p).stem
    aus = []
    for n, m, e in _abschnitte(z, re.compile(r"^## (.*)")):
        t = m.group(1).strip()
        aus.append(Eintrag(name, "anfang", norm(t), p, n, e, t, _text(z, n, e)))
    return aus


def quelle_archiv(d):
    aus = []
    for p in sorted(Path(d).glob("*.md")):
        if p.name == "INDEX.md":
            continue
        z = lies(p)
        titel = next((x.lstrip("# ").strip() for x in z if x.startswith("#")), p.stem)
        aus.append(Eintrag("archiv", "datei", f"archiv/{p.stem}", p, 1, len(z), titel))
    return aus


def quelle_memory(d):
    d = Path(d)
    idx = d / "archiv_index.md"
    namen = []
    for p in (idx, d / "MEMORY.md"):
        for zeile in lies(p):
            for m in re.finditer(r"\]\(([^)]+\.md)\)", zeile):
                ziel = m.group(1)
                if "/" in ziel:          # Verweise ins Repo (../../git/...) sind keine Memory-Dateien
                    continue
                if ziel not in namen and ziel not in ("archiv_index.md", "MEMORY.md"):
                    namen.append(ziel)
    aus = []
    for n in namen:
        p = d / n
        z = lies(p)
        titel = next((x.split(":", 1)[1].strip() for x in z if x.startswith("description:")), n)
        aus.append(Eintrag("memory", "datei", f"memory/{Path(n).stem}", p, 1, len(z), titel))
    return aus


# ---------------- Baum lesen und Verweise auswerten ----------------
QUELL_WORT = re.compile(
    r"(VERSUCHSREGISTER(?:_[A-Z]+)?|Versuchsregister|Register|NICHTS_GEBRACHT|REZEPT(?:_GEBAEUDE_AUS_FOTOS)?|Rezept|"
    r"LERNJOURNAL(?:_MARTINSTOR)?|ERKENNTNISSE|LOGBUCH_[A-Za-z0-9_\-]+)")


def baum_dateien(wurzel):
    w = Path(wurzel)
    aus = sorted((w / "Doku" / "projekt").rglob("*.md"))
    if (w / "PROJEKT.md").exists():
        aus.append(w / "PROJEKT.md")
    return aus


def _quelle_von_wort(wort):
    if wort.upper().startswith("VERSUCHSREGISTER") or wort in ("Register",):
        return "VR:" + (wort.upper() if "_" in wort else "")
    if wort.startswith("NICHTS"):
        return "NG"
    if wort.upper().startswith("REZEPT"):
        return "RZ"
    if wort.startswith("LERNJOURNAL"):
        return "LJ"
    if wort.startswith("ERKENNTNISSE"):
        return "ER"
    return "LB:" + wort.removesuffix(".md")


def verweise(baumtext):
    """Liefert {quelle: [(segment_roh, segment_norm)]} und IDs je Quelle aus allen [..]-Klammern und Quellwort-Folgen."""
    seg = {}
    for zeile in baumtext.split("\n"):
        # jede Stelle eines Quellworts bis zum Klammerende/Zeilenende als Segment
        for m in QUELL_WORT.finditer(zeile):
            q = _quelle_von_wort(m.group(1))
            rest = zeile[m.end():]
            # Ende: schliessende ] oder naechstes Quellwort
            ende = len(rest)
            for zeichen in ("]", "】"):
                k = rest.find(zeichen)
                if k >= 0:
                    ende = min(ende, k)
            n2 = QUELL_WORT.search(rest)
            if n2:
                ende = min(ende, n2.start())
            stueck = rest[:ende]
            seg.setdefault(q, []).append(stueck)
    return seg


def _ids(stuecke):
    ids = set()
    for s in stuecke:
        s2 = s.replace("§", " §")
        for t in re.split(r"[\s,;/+()]+", s2):
            t = t.strip(".:`*")
            if t and not t.startswith("§"):
                ids.add(t)
        # Bereiche wie "BS20b-e" nicht aufloesen (bewusst streng)
    return ids


def _anfaenge(stuecke):
    aus = []
    for s in stuecke:
        for teil in re.split(r"[;,]", s):
            t = teil.strip().lstrip("§").strip()
            n = norm(t)
            if len(n) >= 4:
                aus.append((t, n))
            # Uhrzeiten einzeln (17:15, 09:20-09:35)
            for u in re.findall(r"\d{1,2}:\d{2}", teil):
                aus.append((u, "UHR:" + u))
    return aus


def gedeckt(eintrag, seg, baum_norm, baum_roh):
    if eintrag.art == "datei":
        stem = eintrag.schluessel                    # archiv/NAME oder memory/name
        return stem in baum_roh or stem.replace("memory/", "Memory ") in baum_roh
    q = eintrag.quelle
    if q.startswith("VERSUCHSREGISTER"):
        stuecke = seg.get("VR:" + q.upper(), []) + seg.get("VR:", [])
    elif q == "NICHTS_GEBRACHT":
        stuecke = seg.get("NG", [])
    elif q == "REZEPT":
        stuecke = seg.get("RZ", [])
    elif q == "LERNJOURNAL":
        stuecke = seg.get("LJ", [])
    elif q == "ERKENNTNISSE":
        stuecke = seg.get("ER", [])
    else:
        stuecke = seg.get("LB:" + q, [])
    if eintrag.art == "id":
        ids = _ids(stuecke)
        if eintrag.schluessel in ids:
            return True
        # Rezept-Lehren duerfen auch ohne Quellwort in einer Klammer stehen ("[L47]", "(L-EBENE3)")
        if q == "REZEPT" and "#" not in eintrag.schluessel:
            return re.search(r"[\[(,/ ]" + re.escape(eintrag.schluessel) + r"(?![0-9a-z])", baum_roh) is not None
        return False
    kopf = eintrag.schluessel
    for roh, n in _anfaenge(stuecke):
        if n.startswith("UHR:"):
            if n[4:] in eintrag.titel[:30]:
                return True
        elif kopf.startswith(n) or (len(kopf) >= 4 and n.startswith(kopf)):
            return True
    return False


def werkzeuge_in(text, tools_dir):
    namen = set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\.py\b", text))
    return sorted(n for n in namen if (Path(tools_dir) / f"{n}.py").exists())


def standard_memory(wurzel):
    w = str(Path(wurzel).resolve())
    if "/.claude/worktrees/" in w:
        w = w.split("/.claude/worktrees/")[0]
    return Path.home() / ".claude" / "projects" / w.replace("/", "-") / "memory"


def sammeln(wurzel, memory):
    m = Path(wurzel) / "modelle"
    quellen = []   # (anzeige, [Eintrag], register?)
    gesehen = set()

    def neu(p):
        r = Path(p).resolve()
        if r in gesehen or not r.exists():
            return False
        gesehen.add(r)
        return True
    for p in sorted(m.glob("VERSUCHSREGISTER_*.md")):
        if neu(p):
            quellen.append((p.name, quelle_versuchsregister(p), True))
    for name, fn in (("NICHTS_GEBRACHT.md", quelle_nichts_gebracht), ("REZEPT_GEBAEUDE_AUS_FOTOS.md", quelle_rezept),
                     ("LERNJOURNAL_MARTINSTOR.md", quelle_lernjournal), ("ERKENNTNISSE.md", quelle_erkenntnisse)):
        if neu(m / name):
            quellen.append((name, fn(m / name), True))
    for p in sorted(m.glob("LOGBUCH_*.md")):
        if neu(p):
            quellen.append((p.name, quelle_logbuch(p), False))
    if (m / "archiv").is_dir():
        quellen.append(("archiv/", quelle_archiv(m / "archiv"), False))
    if memory and Path(memory).is_dir():
        quellen.append(("memory (archiv_index)", quelle_memory(memory), False))
    return quellen


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wurzel", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--memory", default=None, help="Memory-Ordner (Standard: ~/.claude/projects/<repo>/memory; 'aus' = ohne)")
    ap.add_argument("--json", default=None, help="fehlende Eintraege als JSON schreiben")
    ap.add_argument("--warnung", action="store_true", help="Luecken nur melden, rc 0")
    ap.add_argument("--voll", action="store_true", help="alle fehlenden Schluessel ausgeben (sonst max. 40 je Quelle)")
    a = ap.parse_args(argv)
    w = Path(a.wurzel)
    if not (w / "modelle").is_dir():
        print(f"FEHLER: {w}/modelle fehlt", file=sys.stderr)
        return 2
    mem = None if a.memory == "aus" else Path(a.memory) if a.memory else standard_memory(w)
    if mem is not None and not mem.is_dir():
        print(f"Hinweis: Memory-Ordner {mem} fehlt - Memory-Abgleich uebersprungen")
        mem = None
    baum = baum_dateien(w)
    baum_roh = "\n".join("\n".join(lies(p)) for p in baum)
    seg = verweise(baum_roh)
    baum_norm = norm(baum_roh)
    tools_dir = w / "tools"
    fehl_json, gesamt_fehl = [], 0
    werkzeug_fehl = {}
    print(f"Wissensbaum: {len(baum)} Dateien, {len(baum_roh.splitlines())} Zeilen")
    for anzeige, eintraege, register in sammeln(w, mem):
        fehl = [e for e in eintraege if not gedeckt(e, seg, baum_norm, baum_roh)]
        gesamt_fehl += len(fehl)
        zeige = fehl if a.voll else fehl[:40]
        print(f"{anzeige}: {len(eintraege)} Eintraege, {len(eintraege) - len(fehl)} im Baum, {len(fehl)} fehlend"
              + (": " + " | ".join(e.verweis() if e.art != "anfang" else e.titel[:30] for e in zeige) if fehl else "")
              + (" ..." if len(fehl) > len(zeige) else ""))
        fehl_json += [e.als_dict(w, tools_dir) for e in fehl]
        if register:
            for e in eintraege:
                for t in werkzeuge_in(e.text, tools_dir):
                    if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(t) + r"\.py\b", baum_roh):
                        werkzeug_fehl.setdefault(t, []).append(e.verweis())
    print(f"Werkzeuge aus Registern ohne Baumzeile: {len(werkzeug_fehl)}"
          + (": " + ", ".join(f"{t}.py ({v[0]})" for t, v in sorted(werkzeug_fehl.items())[: (10**6 if a.voll else 60)]) if werkzeug_fehl else ""))
    if a.json:
        Path(a.json).write_text(json.dumps({"eintraege": fehl_json,
                                            "werkzeuge": {f"{t}.py": v for t, v in sorted(werkzeug_fehl.items())}},
                                           ensure_ascii=False, indent=1), encoding="utf-8")
    luecken = gesamt_fehl + len(werkzeug_fehl)
    if luecken:
        print(f"{'WARNUNG' if a.warnung else 'FEHLER'}: {gesamt_fehl} Eintraege + {len(werkzeug_fehl)} Werkzeuge fehlen im Wissensbaum")
        return 0 if a.warnung else 1
    print("OK: 0 Luecken")
    return 0


if __name__ == "__main__":
    sys.exit(main())
