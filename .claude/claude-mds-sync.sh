#!/usr/bin/env bash
# claude-mds-sync.sh — STUB für jedes Projekt: liegt dort als .claude/claude-mds-sync.sh und wird per SessionStart-Hook
# (.claude/settings.json des Projekts) bei jedem Claude-Sitzungsstart ausgeführt. Kopiervorlage = diese Datei in claude-mds.
#   - fehlt ~/git/claude-mds: klonen;  sonst höchstens alle 6 h `git pull --ff-only`
#   - dann claude-mds/bootstrap.sh (verlinkt Skills/Regeln/Hooks, trägt globalen Hook ein)
# Nie blockierend: jeder Fehler → sichtbare Meldung (stdout = Claude-Kontext), Exit 0.
D="${CLAUDE_MDS_DIR:-$HOME/git/claude-mds}"
URL="${CLAUDE_MDS_URL:-git@github.com:ReinerHohn/claude-mds.git}"
STAMP="${CLAUDE_HOME:-$HOME/.claude}/.claude-mds-last-sync"
mkdir -p "$(dirname "$STAMP")"
if [ ! -d "$D/.git" ]; then
  mkdir -p "$(dirname "$D")"
  if ! timeout 60 git clone -q "$URL" "$D" 2>/tmp/claude-mds-clone.err; then
    echo "⚠ claude-mds konnte nicht geklont werden ($URL → $D): $(tail -1 /tmp/claude-mds-clone.err)."
    echo "  Globale Regeln/Skills fehlen auf diesem Rechner. Ursache meist SSH-Zugang zu GitHub; Nutzer informieren."
    exit 0
  fi
elif [ -z "$(find "$STAMP" -mmin -360 2>/dev/null)" ]; then
  timeout 20 git -C "$D" pull -q --ff-only 2>/dev/null \
    || echo "⚠ claude-mds: git pull in $D ging nicht (offline oder lokale Änderungen) — es gilt der vorhandene Stand."
fi
touch "$STAMP"
if [ -x "$D/bootstrap.sh" ]; then "$D/bootstrap.sh"; else echo "⚠ claude-mds: $D/bootstrap.sh fehlt (alter Stand?) — globale Regeln/Skills nicht eingerichtet."; fi
exit 0
