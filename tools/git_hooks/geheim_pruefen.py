#!/usr/bin/env python3
"""geheim_pruefen.py - verhindert Commits/Pushes, die GitHub ablehnt oder Zugangsdaten veroeffentlichen (Nutzer 20.11.2026 nach blockiertem Push).
  python3 tools/git_hooks/geheim_pruefen.py --staged            pre-commit: gestagte Aenderungen pruefen
  python3 tools/git_hooks/geheim_pruefen.py --bereich A..B      pre-push: alle Commits A..B (neue Blobs) pruefen
  python3 tools/git_hooks/geheim_pruefen.py --test              Selbsttest (synthetisch)
Sperrt (rc 1): Datei > 95 MB (GitHub-Grenze 100 MB); bekannte Zugangsdaten aus ~/.config/rcpark/*.json (Werte der Schluessel code/sn/passwort/
token/key/... ); typische Schluessel (privater SSH/PEM-Schluessel, GitHub-, AWS-, OpenAI/Anthropic-, Slack-, Google-Token);
Zuweisungen wie  password = "..." / CODE = "..."  mit >= 8 Zeichen. Warnt: Datei > 50 MB.
Fehlalarm: Zeile mit "geheim-ok" markieren oder RCPARK_GEHEIM_OK=1 setzen (nur bewusst!). Ausgabe nennt nie das Geheimnis selbst. Nur Standardbibliothek."""
import os, re, subprocess, sys, json, glob

GRENZE, WARN = 95_000_000, 50_000_000
MUSTER = [("privater Schluessel", r"-----BEGIN (RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY"),
          ("GitHub-Token", r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{40,}"),
          ("AWS-Schluessel", r"\bAKIA[0-9A-Z]{16}\b"),
          ("API-Schluessel sk-", r"\bsk-(ant-)?[A-Za-z0-9_\-]{24,}"),
          ("Slack-Token", r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
          ("Google-API-Schluessel", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
          ("Zugangsdaten-Zuweisung", r"(?i)\b(pass(wort|word)?|pwd|token|secret|api[_-]?key|access[_-]?code|zugangscode|CODE)\b\s*[:=]\s*[\"'][A-Za-z0-9+/_\-]{8,}[\"']")]
SCHLUESSEL = re.compile(r"(?i)(code|sn|serial|pass|token|key|secret|zugang)")


def bekannte_geheimnisse():
    w = set()
    for f in glob.glob(os.path.expanduser("~/.config/rcpark/*.json")):
        try: z = json.load(open(f))
        except Exception: continue
        for k, v in (z.items() if isinstance(z, dict) else []):
            if isinstance(v, str) and len(v) >= 6 and SCHLUESSEL.search(k): w.add(v)
    return w


def git(*a, binaer=False):
    r = subprocess.run(["git", *a], capture_output=True); return r.stdout if binaer else r.stdout.decode("utf-8", "replace")


def pruefe_text(name, text, geheim, funde):
    for nr, z in enumerate(text.splitlines(), 1):
        if "geheim-ok" in z: continue
        for g in geheim:
            if g in z: funde.append(f"{name}:{nr}: bekannte Zugangsdaten aus ~/.config/rcpark")
        for art, m in MUSTER:
            if re.search(m, z): funde.append(f"{name}:{nr}: {art}")


def staged(geheim):
    funde, warn = [], []
    for z in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0"):
        if not z: continue
        g = int(git("cat-file", "-s", f":{z}").strip() or 0)
        if g > GRENZE: funde.append(f"{z}: {g / 1e6:.0f} MB > 95 MB (GitHub lehnt ab) - in .gitignore eintragen")
        elif g > WARN: warn.append(f"{z}: {g / 1e6:.0f} MB (GitHub warnt ab 50 MB)")
    diff = git("diff", "--cached", "-U0", "--no-color", "--diff-filter=ACMR")
    datei = "?"; zeilen = {}
    for l in diff.splitlines():
        if l.startswith("+++ "): datei = l[6:] if l.startswith("+++ b/") else l[4:]
        elif l.startswith("+") and not l.startswith("+++"): zeilen.setdefault(datei, []).append(l[1:])
    for d, zz in zeilen.items(): pruefe_text(d, "\n".join(zz), geheim, funde)
    return funde, warn


def bereich(spanne, geheim):
    funde, warn = [], []
    objs = git("rev-list", "--objects", *spanne.split()).splitlines()
    pfad = {o.split(" ", 1)[0]: (o.split(" ", 1)[1] if " " in o else "") for o in objs}
    info = subprocess.run(["git", "cat-file", "--batch-check=%(objecttype) %(objectname) %(objectsize)"], input="\n".join(pfad).encode(), capture_output=True).stdout.decode().split("\n")
    lesen = []
    for l in info:
        t = l.split()
        if len(t) != 3 or t[0] != "blob": continue
        g = int(t[2]); p = pfad.get(t[1], "")
        if g > GRENZE: funde.append(f"{p}: {g / 1e6:.0f} MB > 95 MB in der Historie (GitHub lehnt den Push ab)")
        elif g < 2_000_000 and p.endswith((".py", ".sh", ".json", ".md", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".env")): lesen.append((t[1], p))
    # Stapel: ein einziger cat-file --batch statt eines Prozesses je Datei (1160 Commits: sonst > 10 min)
    if lesen:
        roh = subprocess.run(["git", "cat-file", "--batch"], input="\n".join(h for h, _ in lesen).encode() + b"\n", capture_output=True).stdout; i = 0
        for h, p in lesen:
            kopf_ende = roh.index(b"\n", i); n = int(roh[i:kopf_ende].split()[2]); inhalt = roh[kopf_ende + 1:kopf_ende + 1 + n]; i = kopf_ende + 1 + n + 1
            pruefe_text(p, inhalt.decode("utf-8", "replace"), geheim, funde)
    return funde, warn


def selbsttest():
    f = []; pruefe_text("x.py", 'CODE = "abc12345"\nok = 1\npassword = "kurz"', set(), f); assert len(f) == 1, f  # geheim-ok (Selbsttest)
    f = []; pruefe_text("x.py", 'k = "ghp_' + "a" * 36 + '"', set(), f); assert f and "GitHub" in f[0]
    f = []; pruefe_text("x.py", 'IP, CODE, SN = z["ip"], z["code"], z["sn"]', set(), f); assert not f, f
    f = []; pruefe_text("x.md", "Seriennummer 01ABCDEF99", {"01ABCDEF99"}, f); assert f and "bekannte" in f[0]
    f = []; pruefe_text("x.py", 'CODE = "abc12345"  # geheim-ok', set(), f); assert not f  # geheim-ok (Selbsttest)
    print("geheim_pruefen Selbsttest ok"); return 0


def main():
    if "--test" in sys.argv: return selbsttest()
    if os.environ.get("RCPARK_GEHEIM_OK") == "1": print("geheim_pruefen: uebersprungen (RCPARK_GEHEIM_OK=1)"); return 0
    geheim = bekannte_geheimnisse()
    if "--bereich" in sys.argv: funde, warn = bereich(sys.argv[sys.argv.index("--bereich") + 1], geheim)
    else: funde, warn = staged(geheim)
    for w in warn: print("WARNUNG", w)
    if funde:
        print("GESPERRT - Zugangsdaten oder zu grosse Dateien:"); [print("  " + x) for x in sorted(set(funde))[:30]]
        print("Abhilfe: Geheimnis nach ~/.config/rcpark/<name>.json auslagern bzw. Datei in .gitignore; Fehlalarm: Zeile mit 'geheim-ok' markieren.")
        return 1
    return 0


if __name__ == "__main__": sys.exit(main())
