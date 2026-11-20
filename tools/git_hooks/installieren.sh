#!/bin/bash
# Installiert die Geheimnis-/Groessen-Sperre als lokale Git-Hooks (pre-commit + pre-push). Die alte Pruefstand-Sperre (tools/git_hooks/pre-commit)
# bleibt aus; wer sie zusaetzlich will: RCPARK_PRUEFSTAND_HOOK=1 bash tools/git_hooks/installieren.sh
cd "$(git rev-parse --show-toplevel)" || exit 1; H=$(git rev-parse --git-path hooks); mkdir -p "$H"
cat > "$H/pre-commit" <<'X'
#!/bin/bash
cd "$(git rev-parse --show-toplevel)" || exit 1
python3 tools/git_hooks/geheim_pruefen.py --staged || exit 1
[ "${RCPARK_PRUEFSTAND_HOOK:-0}" = "1" ] && exec bash tools/git_hooks/pre-commit
exit 0
X
cp tools/git_hooks/pre-push "$H/pre-push"; chmod +x "$H/pre-commit" "$H/pre-push"; echo "Hooks installiert in $H (pre-commit, pre-push)"
