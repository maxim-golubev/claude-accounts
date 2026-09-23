#!/bin/bash
# Installs claude-accounts. Safe to re-run: it never touches logins, and any
# existing history is merged into the shared store rather than replaced.
#
#   ./install.sh [profile names...]
#   curl -fsSL https://raw.githubusercontent.com/maxim-golubev/claude-accounts/main/install.sh | bash -s -- work personal

set -euo pipefail

RAW_URL="https://raw.githubusercontent.com/maxim-golubev/claude-accounts/main/claude-accounts"
ROOT="${CLAUDE_ACCOUNTS_HOME:-$HOME/.claude-wrappers}"
BIN_DIR="$ROOT/bin"

mkdir -p "$BIN_DIR"

# Use the copy next to this installer when there is one, else download it.
here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$here" ] && [ -f "$here/claude-accounts" ]; then
  install -m 755 "$here/claude-accounts" "$BIN_DIR/claude-accounts"
else
  curl -fsSL "$RAW_URL" -o "$BIN_DIR/claude-accounts.tmp"
  chmod 755 "$BIN_DIR/claude-accounts.tmp"
  mv "$BIN_DIR/claude-accounts.tmp" "$BIN_DIR/claude-accounts"
fi

if [ ! -f "$ROOT/profiles.conf" ]; then
  cat >"$ROOT/profiles.conf" <<'EOF'
# Claude Code account profiles, one per line:
#
#   <command>  [flags added to every launch]
#
# "claude" is the stock profile (~/.claude, ~/.claude.json). Any
# "claude-<name>" gets its own isolated profile in ~/.claude-<name>.
# The first line is the default in `claudech`. After editing, run:
#   claude-accounts repair
claude
EOF
fi

# The launchers must come before ~/.local/bin, where Claude Code's updater
# keeps the stock binary, so the PATH line goes at the very end of the rc file.
add_path_block() {
  local rc="$1" line="$2"
  [ -f "$rc" ] || touch "$rc"
  grep -q '>>> claude-accounts >>>' "$rc" && return 0
  cat >>"$rc" <<EOF

# >>> claude-accounts >>>
# Keep this block LAST: installers that prepend ~/.local/bin (where Claude
# Code's updater keeps the stock binary) would otherwise shadow the launchers.
$line
# <<< claude-accounts <<<
EOF
  printf 'Added PATH block to %s\n' "$rc"
}

# The rc lines are written literally; $HOME and $PATH expand when the rc runs.
# shellcheck disable=SC2016
case "${SHELL:-}" in
  */bash) add_path_block "$HOME/.bashrc" 'export PATH="$HOME/.claude-wrappers/bin:$PATH"' ;;
  *) add_path_block "$HOME/.zshrc" 'typeset -U path PATH
path=("$HOME/.claude-wrappers/bin" $path)' ;;
esac

for name in "$@"; do
  if awk -v cmd="claude-$name" '$1 == cmd { found = 1 } END { exit !found }' "$ROOT/profiles.conf"; then
    printf 'Profile claude-%s already exists\n' "$name"
  else
    "$BIN_DIR/claude-accounts" add "$name"
  fi
done

"$BIN_DIR/claude-accounts" repair
printf '\n'
"$BIN_DIR/claude-accounts" list
printf '\nOpen a new terminal, log in each profile once (e.g. claude-work auth login),\nthen run: claude-accounts doctor\n'
