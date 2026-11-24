#!/usr/bin/env python3
"""Wissensbaum-Lueckenpruefung, projektunabhaengig: steht jeder Eintrag der Wissensquellen (Register, Erkenntnisse, Logbuecher, Archiv,
Memory-Archiv) als Verweis in einer Zeile des Wissensbaums? NUR LESEND.

Anlass (rc-park 24.11.2026): der Baum behauptete nach einer Stichprobe von Hand "0 fehlend", tatsaechlich fehlten 942 Eintraege
(66 von 125 Registerabschnitten beim Verdichten auf ein Zeilenbudget verloren). Vollstaendigkeit braucht ein Werkzeug, keine Stichprobe.

  python3 ~/.claude/skills/doku-pflege/luecken.py [--wurzel DIR] [--memory DIR|aus] [--voll] [--warnung] [--json AUS]
rc 0 = keine Luecke (oder --warnung), rc 1 = Luecken, rc 2 = Aufruffehler.

Konfig: <repo>/.claude/doku-pflege.json -> "wissen": {"baum": [globs], "luecken": [Quelle, ...]}. Quelle:
  {"name": "REGISTER", "glob": "Doku/REGISTER*.md", "art": "abschnitt", "kopf": "^## (.*)", "id": "^([A-Z]{1,3}[0-9]{0,3}[a-z]?)\\\\b",
   "aliase": ["REGISTER", "Register"], "frei": false}
  art "abschnitt": je Ueberschrift (kopf) ein Eintrag; Schluessel = ID (Regex "id" auf den Ueberschriftstext) oder Textanfang.
  art "zeile":     je Zeile, die "zeile" (Regex, Gruppe 1 = Text) trifft, ein Eintrag; Schluessel = ID aus dem Text oder Textanfang.
  art "datei":     je Datei ein Eintrag; der Baum muss den Pfad ohne .md irgendwo nennen (z. B. archiv/NAME).
Baumverweis: "[<Alias> <ID>]" bzw. "[<Alias> §<Textanfang>]" (Anfang: mind. 4 Buchstaben/Ziffern, klein, nur a-z0-9). "frei": true = die ID
  zaehlt auch ohne Alias in einer Klammer "[ID]"/"(ID)". Doppelte IDs werden als ID#2, ID#3 gezaehlt und gemeldet (Agenten vergeben parallel
  dieselbe "naechste freie" ID). "alias_datei": true = auch der Dateiname (ohne .md) gilt als Alias (Logbuecher). Nicht eingecheckte Dateien (git ls-files --others) sind keine Quelle.
Memory: Dateien, die ~/.claude/projects/<repo>/memory/archiv_index.md oder MEMORY.md verlinkt, muessen als "memory/<name>" im Baum stehen
  ("memory": false in der Konfig = aus).
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

STANDARD = {
    "baum": ["PROJEKT.md", "Doku/projekt/**/*.md"],
    "luecken": [{"name": "archiv", "glob": "Doku/archiv/**/*.md", "art": "datei"}],
    "memory": True,
}


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower()).replace("ß", "ss")
    return "".join(c for c in s if c.isalnum() and ord(c) < 128)


def lies(p):
    try:
        return Path(p).resolve().read_text(encoding="utf-8", errors="replace").split("\n")
    except OSError:
        return []


def konfig(w):
    k = dict(STANDARD)
    try:
        k.update(json.loads((Path(w) / ".claude" / "doku-pflege.json").read_text(encoding="utf-8")).get("wissen", {}))
    except (OSError, ValueError, AttributeError):
        pass
    return k


def ungetrackt(w):
    try:
        r = subprocess.run(["git", "-C", str(w), "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True, timeout=60)
        return {str(Path(w, x).resolve()) for x in r.stdout.split("\n") if x} if r.returncode == 0 else set()
    except OSError:
        return set()


def dateien(w, globs, fremd):
    aus, gesehen = [], set()
    for g in globs if isinstance(globs, list) else [globs]:
        for p in sorted(Path(w).glob(g)):
            r = str(p.resolve())
            if p.is_file() and r not in gesehen and r not in fremd and p.name != "INDEX.md":
                gesehen.add(r)
                aus.append(p)
    return aus


def eintraege(w, q, fremd):
    """[(schluessel, art 'id'|'anfang'|'datei', titel, ort)]"""
    aus = []
    id_rx = re.compile(q["id"]) if q.get("id") else None
    for p in dateien(w, q["glob"], fremd):
        rel = str(p.relative_to(w))
        if q["art"] == "datei":
            aus.append((rel[:-3] if rel.endswith(".md") else rel, "datei", p.stem, rel))
            continue
        rx = re.compile(q.get("kopf", r"^## (.*)") if q["art"] == "abschnitt" else q["zeile"])
        ids = {}
        for i, z in enumerate(lies(p), 1):
            m = rx.match(z)
            if not m:
                continue
            t = (m.group(1) if m.groups() else z).strip()
            mi = id_rx.match(re.sub(r"^[*`]+", "", t)) if id_rx else None
            if mi:
                k = mi.group(1)
                ids[k] = ids.get(k, 0) + 1
                aus.append((k if ids[k] == 1 else f"{k}#{ids[k]}", "id", t, f"{rel}:{i}"))
            elif len(norm(t)) >= 4:
                aus.append((norm(t), "anfang", t, f"{rel}:{i}"))
    return aus


def gedeckt(e, q, baum_roh):
    k, art = e[0], e[1]
    if art == "datei":
        return k in baum_roh or k.split("/", 1)[-1] in baum_roh
    aliase = list(q.get("aliase") or [q["name"]])
    if q.get("alias_datei"):                   # z. B. Logbuecher: der Dateiname ist der Alias ([LOGBUCH_X §17:15])
        aliase.append(Path(e[3].split(":")[0]).stem)
    al = "|".join(re.escape(a) for a in aliase)
    if art == "id":
        # Doppel-ID "L55#2" muss genau so im Baum stehen (gemeldet wird sie trotzdem)
        if re.search(rf"(?:{al})[^\]\n]*?(?<![A-Za-z0-9]){re.escape(k)}(?![A-Za-z0-9])", baum_roh):
            return True
        return bool(q.get("frei")) and re.search(rf"[\[(,/ ]{re.escape(k)}(?![0-9a-z])", baum_roh) is not None
    for m in re.finditer(rf"(?:{al})[^\]\n]*", baum_roh):
        for seg in re.findall(r"§([^;,\]§]+)", m.group(0)):
            n = norm(seg)
            if len(n) >= 4 and (k.startswith(n) or n.startswith(k)):
                return True
    return False


def memory_eintraege(mem):
    d = Path(mem)
    namen = []
    for p in (d / "archiv_index.md", d / "MEMORY.md"):
        for z in lies(p):
            for m in re.finditer(r"\]\(([^)/]+\.md)\)", z):
                if m.group(1) not in namen and m.group(1) not in ("archiv_index.md", "MEMORY.md"):
                    namen.append(m.group(1))
    return [(f"memory/{Path(n).stem}", "datei", n, f"memory/{n}") for n in namen if (d / n).exists()]


def standard_memory(w):
    s = str(Path(w).resolve()).split("/.claude/worktrees/")[0]
    return Path.home() / ".claude" / "projects" / s.replace("/", "-") / "memory"


def standard_wurzel():
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except OSError:
        pass
    return Path.cwd()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wurzel", default=None)
    ap.add_argument("--memory", default=None)
    ap.add_argument("--voll", action="store_true")
    ap.add_argument("--warnung", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    w = Path(a.wurzel) if a.wurzel else standard_wurzel()
    k = konfig(w)
    fremd = ungetrackt(w)
    baum = dateien(w, k["baum"], set())
    if not baum:
        print(f"FEHLER: kein Wissensbaum unter {w} ({k['baum']})", file=sys.stderr)
        return 2
    baum_roh = "\n".join("\n".join(lies(p)) for p in baum)
    print(f"Wissensbaum: {len(baum)} Dateien, {len(baum_roh.splitlines())} Zeilen")
    quellen = [(q, eintraege(w, q, fremd)) for q in k["luecken"]]
    mem = None if a.memory == "aus" or not k.get("memory", True) else Path(a.memory) if a.memory else standard_memory(w)
    if mem is not None and mem.is_dir():
        quellen.append(({"name": "memory", "art": "datei"}, memory_eintraege(mem)))
    fehl_ges, doppelt_ges, aus_json = 0, 0, []
    for q, es in quellen:
        fehl = [e for e in es if not gedeckt(e, q, baum_roh)]
        doppelt = [e for e in es if "#" in e[0]]
        fehl_ges += len(fehl)
        doppelt_ges += len(doppelt)
        zeige = fehl if a.voll else fehl[:30]
        print(f"{q['name']}: {len(es)} Eintraege, {len(es) - len(fehl)} im Baum, {len(fehl)} fehlend"
              + (f", {len(doppelt)} doppelte IDs" if doppelt else "")
              + (": " + " | ".join(f"{e[0] if e[1] != 'anfang' else e[2][:30]} ({e[3]})" for e in zeige) if fehl else "")
              + (" ..." if len(fehl) > len(zeige) else ""))
        aus_json += [{"quelle": q["name"], "schluessel": e[0], "art": e[1], "titel": e[2], "ort": e[3]} for e in fehl]
    if a.json:
        Path(a.json).write_text(json.dumps(aus_json, ensure_ascii=False, indent=1), encoding="utf-8")
    if fehl_ges:
        print(f"{'WARNUNG' if a.warnung else 'FEHLER'}: {fehl_ges} Eintraege fehlen im Wissensbaum (Ast zu lang -> Unterast, nie verdichten)"
              + (f"; {doppelt_ges} doppelt vergebene IDs zuerst eindeutig machen" if doppelt_ges else ""))
        return 0 if a.warnung else 1
    print("OK: 0 Luecken")
    return 0


if __name__ == "__main__":
    sys.exit(main())
