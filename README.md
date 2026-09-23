# claude-accounts

Run several Claude Code accounts side by side on one machine, each with its own
login, while every account shares **one conversation history**. A thread you
started on one account can be resumed (`--resume` / `--continue`) on any other,
for example when one account hits its usage limit.

```text
$ claude-accounts list
PROFILE            ACCOUNT                            CONFIG                   FLAGS
claude             you@example.com                    ~/.claude
claude-work        you@work.example                   ~/.claude-work           --model opus
claude-personal    you@personal.example               ~/.claude-personal

$ claude-work                 # Claude Code, logged into the work account
$ claude-personal --resume    # pick up any thread, including ones started on work
$ claudech                    # interactive picker
```

This file is written so that an AI coding agent can read it top to bottom and
reproduce the setup on a new machine. Humans can use it the same way. The
complete source is embedded at the end, so the file works even offline.

> Unofficial. Not affiliated with Anthropic. It relies on how Claude Code
> stores logins and history today (verified on Claude Code 2.1.x, macOS 15),
> which could change. Make sure your use of multiple accounts follows the terms
> of your plan(s).

---

## Quick start

Requirements: Claude Code installed (`claude --version` works), macOS (or
Linux), `bash`, `curl`.

```bash
# Install, creating two extra profiles: claude-work and claude-personal
curl -fsSL https://raw.githubusercontent.com/maxim-golubev/claude-accounts/main/install.sh | bash -s -- work personal

# Open a NEW terminal, then log each new profile in once
claude-work auth login
claude-personal auth login

# Verify
claude-accounts doctor
```

Plain `claude` keeps using the login you already have. Nothing is logged out.

---

## Commands

| Command | What it does |
| --- | --- |
| `claude …` | Claude Code on the **stock** profile (`~/.claude`, `~/.claude.json`), with its own login. |
| `claude-<name> …` | Claude Code on the isolated profile `~/.claude-<name>`, with its own login. All normal arguments work (`--resume`, `-p`, `mcp`, `auth status`, …). |
| `claudech [args]` | Asks which account to use, then launches it with `args`. |
| `claude-accounts list` | Profiles, the account each is logged into, and their flags. |
| `claude-accounts doctor` | Checks PATH, launchers, logins and history links, and says how to fix anything wrong. |
| `claude-accounts add <name> [flags…]` | Creates profile `claude-<name>`. Then run `claude-<name> auth login`. |
| `claude-accounts repair` | Recreates launchers and relinks shared history. Idempotent. |

Log a profile in or out with Claude Code's own commands: `claude-<name> auth login`,
`claude-<name> auth logout`, `claude-<name> auth status`, or `/login` inside a session.

---

## How it works

### 1. One login per config directory

Claude Code reads the environment variable `CLAUDE_CONFIG_DIR`:

| | Settings and history | Account metadata | Login (macOS Keychain service) |
| --- | --- | --- | --- |
| unset (stock) | `~/.claude/` | `~/.claude.json` | `Claude Code-credentials` |
| `CLAUDE_CONFIG_DIR=/Users/me/.claude-work` | `~/.claude-work/` | `~/.claude-work/.claude.json` | `Claude Code-credentials-` + first 8 hex characters of `sha256("/Users/me/.claude-work")` |

On Linux the login is a file, `<config dir>/.credentials.json`, instead of a
Keychain item.

Because the Keychain name is a hash of the **exact path string**, each config
directory is a completely separate login. The same string also means:

- `/Users/me/.claude-work` and `/Users/me/.claude-work/` are *different* logins.
- `CLAUDE_CONFIG_DIR=~/.claude` is *not* the stock login. The stock login needs
  the variable **unset**.

You can check which Keychain item belongs to a directory:

```bash
dir="$HOME/.claude-work"
svc="Claude Code-credentials-$(printf '%s' "$dir" | shasum -a 256 | cut -c1-8)"
security find-generic-password -s "$svc" >/dev/null && echo "logged in: $svc"
```

### 2. One script, many launcher names

Everything lives in `~/.claude-wrappers/`:

```text
~/.claude-wrappers/
├── profiles.conf               which profiles exist + extra launch flags
└── bin/                        first entry on PATH
    ├── claude-accounts         the only real file
    ├── claude          -> claude-accounts
    ├── claude-work     -> claude-accounts
    ├── claude-personal -> claude-accounts
    └── claudech        -> claude-accounts
```

The script looks at the name it was called by (`$0`):

- `claude`: unset `CLAUDE_CONFIG_DIR`, so the stock profile is used.
- `claude-<name>`: `export CLAUDE_CONFIG_DIR="$HOME/.claude-<name>"`.
- `claudech`: show the picker.
- `claude-accounts`: management commands.

Before it launches Claude Code, it also unsets `ANTHROPIC_API_KEY`,
`ANTHROPIC_AUTH_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN`, so a stray API key in your
environment can never override the subscription login. Then it `exec`s the real
binary with the profile's flags followed by your arguments.

### 3. Finding the real binary

`~/.local/bin/claude` stays exactly as Claude Code's native installer made it: a
symlink that the auto-updater moves to each new version. The launcher resolves
the real binary on every start, in this order:

1. `$CLAUDE_ACCOUNTS_REAL_BIN`, if set.
2. `~/.local/bin/claude` (native install; follows the updater automatically).
3. The newest build in `~/.local/share/claude/versions/`.
4. Any other `claude` on `PATH` (npm or Homebrew installs), skipping the launchers.

So updates need no action, and `claude update` works as usual.

### 4. PATH order: the one thing that breaks

`~/.claude-wrappers/bin` must come **before** `~/.local/bin` on `PATH`,
otherwise `claude` runs the stock binary directly. Many installers append a line
like `export PATH="$HOME/.local/bin:$PATH"` to `~/.zshrc`, which pushes it back
in front. That is why the installer puts this block at the **very end** of the
rc file. If something later appends below it, move the block back to the bottom.

```zsh
# >>> claude-accounts >>>
typeset -U path PATH
path=("$HOME/.claude-wrappers/bin" $path)
# <<< claude-accounts <<<
```

(For bash: `export PATH="$HOME/.claude-wrappers/bin:$PATH"` at the end of
`~/.bashrc`.) `claude-accounts doctor` detects this problem.

### 5. Shared history

Every profile's history items are symlinks into `~/.claude-shared-history/`:

| Item | Why it is shared |
| --- | --- |
| `projects/` | Conversation transcripts, which is what `--resume` / `--continue` read (grouped by working directory). |
| `file-history/` | Checkpoints for rewinding file edits. |
| `tasks/`, `session-env/`, `shell-snapshots/` | Per-session state referenced when a session is resumed. |
| `plans/` | Plan-mode files referenced from transcripts. |
| `paste-cache/` | Large pastes referenced from prompt history. |
| `history.jsonl` | Up-arrow prompt history. |

Everything else stays **per profile**: login, `.claude.json` (account and
onboarding state), `settings.json`, MCP servers, plugins, skills, agents,
`CLAUDE.md`, caches. So each account can have its own model, theme and tools.
If you want the same user-level `CLAUDE.md` or skills everywhere, symlink them
yourself.

When `repair` (or `add`) links a profile that already has local history, it
never discards anything:

1. It moves the local item into `<profile>/local-history-before-shared-<timestamp>/`.
2. It merges that into the shared store: files the shared store lacks are moved
   in, identical duplicates are dropped, and dangling symlinks in the shared
   store are replaced by the real file. Prompt-history lines are deduplicated
   and re-sorted by timestamp.
3. It replaces the item with a symlink to the shared copy.
4. Only genuine conflicts (same path, different content) stay in the dated
   backup folder, and it prints where that folder is.

Different accounts can run at the same time. Transcripts do not depend on the
account, so a resumed thread just continues on whatever account launched it.

---

## Setup playbook for an agent

Follow these steps in order. The golden rule: **never do anything that changes
or removes an existing login.** Logins are Keychain items (macOS) or
`.credentials.json` files (Linux). They are keyed on exact config-directory
strings.

### Step 0: inspect the machine (read-only)

```bash
claude --version                       # Claude Code must be installed
command -v -a claude                   # where claude currently resolves
echo "${CLAUDE_CONFIG_DIR-<unset>}"     # should be unset in a normal terminal
ls -d ~/.claude ~/.claude-* 2>/dev/null
grep -n -i claude ~/.zshrc ~/.zprofile ~/.bashrc ~/.bash_profile 2>/dev/null
security dump-keychain 2>/dev/null | grep -o '"Claude Code-credentials[^"]*"' | sort -u   # macOS
```

For each existing directory, find out whether it is logged in and to which
account. `auth status` only reads state:

```bash
env -u CLAUDE_CONFIG_DIR claude auth status          # stock profile (not through the launcher yet)
CLAUDE_CONFIG_DIR="$HOME/.claude-foo" claude auth status
```

Write this baseline down. You will compare against it at the end.

### Step 1: decide the profile names

- The stock login becomes plain `claude`.
- Each other account gets a name `claude-<name>` (lowercase letters, digits,
  `-`), backed by `~/.claude-<name>`.
- **If a logged-in directory already exists** (for example `~/.claude-foo`),
  reuse its name (`foo`) so the path string, and therefore the login, stays the
  same. Renaming a directory changes the hash, which means a fresh login.
- Directories that don't follow the `~/.claude-<name>` pattern
  (e.g. `~/claude-configs/work`): either leave them alone and re-login under a
  new profile, or, if the user agrees to one re-login, adopt a `~/.claude-<name>` dir.

### Step 2: remove old wrappers that would conflict

Look for existing aliases, functions or scripts named `claude`, `claude-*`, or
`claudech` in the shell rc files and on `PATH` (other than
`~/.local/bin/claude` itself). **Move them into a backup folder; do not delete
them.** Never replace `~/.local/bin/claude`: it belongs to Claude Code's updater.

### Step 3: install

```bash
curl -fsSL https://raw.githubusercontent.com/maxim-golubev/claude-accounts/main/install.sh | bash -s -- <name1> <name2> ...
```

Or offline: save the script from the end of this file as
`~/.claude-wrappers/bin/claude-accounts` (`chmod 755`), create
`~/.claude-wrappers/profiles.conf` (format below), add the PATH block from
"How it works §4" at the end of the rc file, then run
`~/.claude-wrappers/bin/claude-accounts repair`.

The installer:

- copies the script;
- creates `profiles.conf` (only the stock `claude` line) if it doesn't exist;
- adds the PATH block to the end of `~/.zshrc` (or `~/.bashrc` for bash) once;
- adds each named profile;
- runs `repair`, which creates the launchers and merges and links history.

### Step 4: log in the new profiles

This step is interactive (it opens a browser). The **user** must do it, in a
new terminal:

```bash
claude-<name> auth login
```

Profiles that already had a login (reused directories) need nothing.

### Step 5: verify

In a **new** terminal:

```bash
command -v claude                  # -> ~/.claude-wrappers/bin/claude
claude-accounts doctor             # every line "ok", ends with "All good."
claude-accounts list               # right account next to each profile
claude-<name> auth status          # loggedIn: true, expected email
```

Compare with the Step 0 baseline: every account that was logged in before must
still be logged in. To test resume, start `claude-<a>` in some directory, say
something, quit, then run `claude-<b> --continue` in the same directory.

### Rules for agents

- Never set `CLAUDE_CONFIG_DIR` to `~/.claude` for the stock profile. It must be *unset*.
- Never add a trailing slash to, or resolve symlinks in, a config path.
- Never run `auth logout`, and never delete, rename or edit `Claude Code-credentials*` Keychain items or `.credentials.json` files.
- Never copy credentials between profiles. OAuth refresh tokens rotate, so two
  copies of one login will log each other out. Log each profile in separately.
- Never delete history. Merges move files, and conflicts are kept in dated backup folders.
- Don't move or rename `~/.claude.json` or `<profile>/.claude.json`.

---

## Configuration: `profiles.conf`

```text
# <command>        [flags added to every launch]
claude
claude-work        --model opus
claude-personal    --dangerously-skip-permissions
claude-research    --effort high --model sonnet
```

- Order matters only for `claudech`: the first line is the default.
- Flags are split on spaces and inserted before your own arguments. Claude Code
  accepts global flags before subcommands, so `claude-work mcp list` still works.
- `--dangerously-skip-permissions` turns off permission prompts. Only use it if
  you understand the risk.
- After editing by hand, run `claude-accounts repair` to create any new launchers.

Environment overrides (rarely needed): `CLAUDE_ACCOUNTS_HOME` (default
`~/.claude-wrappers`), `CLAUDE_SHARED_HISTORY` (default
`~/.claude-shared-history`), `CLAUDE_ACCOUNTS_REAL_BIN` (path of the real
Claude Code binary).

---

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `claude` ignores the profile / `command -v claude` shows `~/.local/bin/claude` | PATH order. Move the `claude-accounts` block to the end of `~/.zshrc`, open a new terminal. In an old terminal, run `hash -r`. |
| A profile suddenly asks you to log in | Its config path string changed (renamed dir, trailing slash, `~/.claude` set explicitly), or its login was copied elsewhere and rotated. Run `claude-<name> auth login`. |
| `--resume` doesn't show a thread | Transcripts are grouped by working directory, so run it from the directory the conversation started in. Also check `claude-accounts doctor` for unlinked items. |
| `cannot find the Claude Code binary` | Install Claude Code, or set `CLAUDE_ACCOUNTS_REAL_BIN=/path/to/claude`. |
| `local-history-before-shared-*` folders | Conflicts kept during a merge. Inspect them, then delete them when you are satisfied. |
| An IDE extension or desktop app uses the wrong account | They usually start Claude Code without these launchers, so they use the stock profile. Log that into the account you want them to use. |

---

## Uninstall

```bash
rm -rf ~/.claude-wrappers        # launchers + profiles.conf
# delete the "# >>> claude-accounts >>>" block from ~/.zshrc (or ~/.bashrc)
```

Logins, settings and history are untouched. To give a profile private history
again, replace each symlink with a copy, e.g.
`rm ~/.claude-work/projects && cp -R ~/.claude-shared-history/projects ~/.claude-work/projects`.

---

## Full source

The complete launcher, identical to [`claude-accounts`](claude-accounts) in this
repository. Save it as `~/.claude-wrappers/bin/claude-accounts` and `chmod 755` it.

<details>
<summary><code>claude-accounts</code></summary>

```bash
#!/bin/bash
# claude-accounts: run several Claude Code accounts side by side, with one
# shared conversation history so any thread can be resumed from any account.
#
# One script, many names. Every launcher in this directory is a symlink to
# this file, and the name it is invoked as decides what happens:
#
#   claude            stock profile   (~/.claude + ~/.claude.json)
#   claude-<name>     isolated profile (~/.claude-<name>)
#   claudech          interactive account picker
#   claude-accounts   management: list, doctor, add, repair
#
# Claude Code stores each login in the macOS Keychain under a service name
# derived from the exact CLAUDE_CONFIG_DIR string: "Claude Code-credentials"
# when it is unset, otherwise "Claude Code-credentials-" plus the first 8 hex
# digits of sha256(path). Never add a trailing slash to, or resolve symlinks
# in, a profile path: a different string is a different, empty login.

set -euo pipefail

ROOT="${CLAUDE_ACCOUNTS_HOME:-$HOME/.claude-wrappers}"
BIN_DIR="$ROOT/bin"
PROFILES_FILE="$ROOT/profiles.conf"
SHARED="${CLAUDE_SHARED_HISTORY:-$HOME/.claude-shared-history}"
SELF="$BIN_DIR/claude-accounts"

# Everything --resume, rewind and prompt history need, shared by all profiles.
SHARED_ITEMS="projects file-history tasks session-env shell-snapshots paste-cache plans history.jsonl"

die() {
  printf 'claude-accounts: %s\n' "$*" >&2
  exit 1
}

# --- profiles ----------------------------------------------------------------

# Launcher commands in profiles.conf order.
profiles() {
  [ -f "$PROFILES_FILE" ] || die "missing $PROFILES_FILE"
  awk '!/^[[:space:]]*(#|$)/ { print $1 }' "$PROFILES_FILE"
}

# Extra launch flags for a profile; fails if the profile is not configured.
profile_flags() {
  [ -f "$PROFILES_FILE" ] || die "missing $PROFILES_FILE"
  awk -v cmd="$1" '
    $1 == cmd { found = 1; $1 = ""; sub(/^[[:space:]]+/, ""); print; exit }
    END { exit !found }
  ' "$PROFILES_FILE"
}

# CLAUDE_CONFIG_DIR for a profile; empty means "leave it unset" (stock).
config_dir() {
  case "$1" in
    claude) printf '' ;;
    claude-*) printf '%s/.%s' "$HOME" "$1" ;;
    *) die "profile commands must be 'claude' or 'claude-<name>', got '$1'" ;;
  esac
}

# Directory holding a profile's settings and history.
profile_home() {
  local dir
  dir="$(config_dir "$1")"
  printf '%s' "${dir:-$HOME/.claude}"
}

# File holding a profile's account metadata (.claude.json).
profile_state_file() {
  local dir
  dir="$(config_dir "$1")"
  printf '%s/.claude.json' "${dir:-$HOME}"
}

keychain_service() {
  local dir
  dir="$(config_dir "$1")"
  if [ -z "$dir" ]; then
    printf 'Claude Code-credentials'
  else
    printf 'Claude Code-credentials-%s' "$(printf '%s' "$dir" | shasum -a 256 | cut -c1-8)"
  fi
}

account_email() {
  local file
  file="$(profile_state_file "$1")"
  [ -f "$file" ] || return 0
  grep -o '"emailAddress": *"[^"]*"' "$file" | head -n 1 | sed 's/.*"\([^"]*\)"$/\1/' || true
}

has_login() {
  if command -v security >/dev/null 2>&1; then
    security find-generic-password -s "$(keychain_service "$1")" >/dev/null 2>&1
  else
    # Linux and other platforms keep the login in a file instead.
    [ -f "$(profile_home "$1")/.credentials.json" ]
  fi
}

# --- locating the real Claude Code binary ------------------------------------

# Follow a symlink chain to the final file.
resolve_path() {
  local path="$1" target
  while [ -L "$path" ]; do
    target="$(readlink "$path")"
    case "$target" in
      /*) path="$target" ;;
      *) path="$(dirname "$path")/$target" ;;
    esac
  done
  if [ -e "$path" ]; then
    path="$(cd "$(dirname "$path")" && pwd -P)/$(basename "$path")"
  fi
  printf '%s' "$path"
}

is_real_claude() {
  local path
  path="$(resolve_path "$1")"
  [ -f "$path" ] && [ -x "$path" ] && [ "$path" != "$SELF" ]
}

# The native installer's updater keeps ~/.local/bin/claude pointed at the
# newest build, so these launchers never need touching after an update.
real_claude() {
  local candidate versions dir
  if [ -n "${CLAUDE_ACCOUNTS_REAL_BIN:-}" ]; then
    printf '%s' "$CLAUDE_ACCOUNTS_REAL_BIN"
    return
  fi

  candidate="$HOME/.local/bin/claude"
  if is_real_claude "$candidate"; then
    resolve_path "$candidate"
    return
  fi

  versions="$HOME/.local/share/claude/versions"
  if [ -d "$versions" ]; then
    # Entries are plain version numbers such as 2.1.280.
    # shellcheck disable=SC2012
    for candidate in $(ls "$versions" | sort -r -V); do
      if is_real_claude "$versions/$candidate"; then
        printf '%s' "$versions/$candidate"
        return
      fi
    done
  fi

  # npm or Homebrew installs: any other claude on PATH.
  local IFS=:
  for dir in $PATH; do
    [ "$dir" = "$BIN_DIR" ] && continue
    if is_real_claude "$dir/claude"; then
      resolve_path "$dir/claude"
      return
    fi
  done
  return 1
}

# --- launching ---------------------------------------------------------------

launch() {
  local cmd="$1" flags dir real
  shift
  flags="$(profile_flags "$cmd")" || die "no profile '$cmd' in $PROFILES_FILE"
  dir="$(config_dir "$cmd")"
  real="$(real_claude)" || die "cannot find the Claude Code binary; install it or set CLAUDE_ACCOUNTS_REAL_BIN"

  # A subscription login must not be overridden by API credentials that
  # happen to be in the environment.
  unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN
  if [ -z "$dir" ]; then
    unset CLAUDE_CONFIG_DIR
  else
    export CLAUDE_CONFIG_DIR="$dir"
  fi

  set -f # flags are split on whitespace but never globbed
  # shellcheck disable=SC2086
  exec "$real" $flags "$@"
}

pick() {
  local cmds cmd i=0 choice email
  cmds="$(profiles)"
  [ -n "$cmds" ] || die "no profiles in $PROFILES_FILE"

  printf '\nWhich Claude account?\n'
  for cmd in $cmds; do
    i=$((i + 1))
    email="$(account_email "$cmd")"
    printf '  %d) %-18s %s\n' "$i" "$cmd" "${email:-(not logged in)}"
  done
  printf '\nSelect [1-%d, Enter = 1]: ' "$i"
  { read -r choice </dev/tty; } 2>/dev/null || choice=1
  choice="${choice:-1}"
  case "$choice" in
    '' | *[!0-9]*) die "not a number: $choice" ;;
  esac
  [ "$choice" -ge 1 ] && [ "$choice" -le "$i" ] || die "no option $choice"

  cmd="$(printf '%s\n' "$cmds" | sed -n "${choice}p")"
  printf 'Launching %s...\n\n' "$cmd"
  launch "$cmd" "$@"
}

# --- shared history ----------------------------------------------------------

# Move everything from $1 into $2 that $2 does not already have, dropping
# exact duplicates. Whatever is left in $1 afterwards is a genuine conflict
# and is kept for inspection.
merge_tree() {
  local src="$1" dst="$2" entry name
  for entry in "$src"/* "$src"/.[!.]* "$src"/..?*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    name="$(basename "$entry")"
    if [ ! -e "$dst/$name" ] && [ ! -L "$dst/$name" ]; then
      mv "$entry" "$dst/$name"
    elif [ -L "$dst/$name" ] && [ ! -e "$dst/$name" ]; then
      # A dangling link (typically one that pointed back into the profile
      # being merged) is replaced by the real file.
      rm "$dst/$name"
      mv "$entry" "$dst/$name"
    elif [ -d "$entry" ] && [ ! -L "$entry" ] && [ -d "$dst/$name" ]; then
      merge_tree "$entry" "$dst/$name"
    elif [ -f "$entry" ] && cmp -s "$entry" "$dst/$name"; then
      rm "$entry"
    fi
  done
}

# Fold prompt-history lines from $1 into the shared history, oldest first.
merge_history() {
  local old="$1" index="$SHARED/history.jsonl" tmp
  if [ ! -s "$index" ]; then
    mv "$old" "$index"
    return
  fi
  if ! awk 'NR == FNR { seen[$0] = 1; next } !($0 in seen) { exit 1 }' "$index" "$old"; then
    tmp="$index.merge.$$"
    cat "$index" "$old" |
      awk '!seen[$0]++' |
      awk '{ ts = 0; if (match($0, /"timestamp":[0-9]+/)) ts = substr($0, RSTART + 12, RLENGTH - 12); print ts "\t" $0 }' |
      sort -s -n -k1,1 | cut -f2- >"$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$index"
  fi
  rm "$old"
}

mkdir_private() {
  [ -d "$1" ] || mkdir -m 700 "$1"
}

ensure_shared() {
  local item
  mkdir_private "$SHARED"
  for item in $SHARED_ITEMS; do
    case "$item" in
      *.jsonl) [ -e "$SHARED/$item" ] || install -m 600 /dev/null "$SHARED/$item" ;;
      *) mkdir_private "$SHARED/$item" ;;
    esac
  done
}

# Point a profile's history at the shared store. Existing local history is
# merged in first, so nothing is lost; conflicts stay in a dated backup.
link_profile() {
  local cmd="$1" home item path target backup=""
  home="$(profile_home "$cmd")"
  mkdir_private "$home"
  ensure_shared

  for item in $SHARED_ITEMS; do
    path="$home/$item"
    target="$SHARED/$item"
    if [ -L "$path" ]; then
      [ "$(readlink "$path")" = "$target" ] ||
        printf 'WARN %s: %s points to %s, leaving it alone\n' "$cmd" "$path" "$(readlink "$path")" >&2
      continue
    fi
    if [ -e "$path" ]; then
      if [ -z "$backup" ]; then
        backup="$home/local-history-before-shared-$(date +%Y%m%d-%H%M%S)"
        mkdir -m 700 "$backup"
      fi
      mv "$path" "$backup/$item"
      if [ -d "$backup/$item" ]; then
        merge_tree "$backup/$item" "$target"
      else
        merge_history "$backup/$item"
      fi
      printf 'Merged %s %s into %s\n' "$cmd" "$item" "$target"
    fi
    ln -s "$target" "$path"
  done

  if [ -n "$backup" ]; then
    find "$backup" -depth -type d -empty -delete
    if [ -d "$backup" ]; then
      printf 'Kept conflicting files from %s in %s\n' "$cmd" "$backup"
    fi
  fi
}

# --- management commands -----------------------------------------------------

cmd_list() {
  local cmd email
  printf '%-18s %-34s %-24s %s\n' PROFILE ACCOUNT CONFIG FLAGS
  for cmd in $(profiles); do
    email="$(account_email "$cmd")"
    has_login "$cmd" || email="(not logged in)"
    printf '%-18s %-34s %-24s %s\n' "$cmd" "${email:-?}" \
      "$(profile_home "$cmd" | sed "s|^$HOME|~|")" "$(profile_flags "$cmd")"
  done
}

cmd_doctor() {
  local failures=0 cmd real item path
  ok() { printf 'ok    %s\n' "$*"; }
  bad() {
    printf 'FAIL  %s\n' "$*"
    failures=$((failures + 1))
  }

  if real="$(real_claude)"; then
    ok "Claude Code binary: $real ($("$real" --version 2>/dev/null || echo 'version unknown'))"
  else
    bad "Claude Code binary not found"
  fi

  path="$(command -v claude || true)"
  if [ "$path" = "$BIN_DIR/claude" ]; then
    ok "'claude' on PATH resolves to the launcher"
  else
    bad "'claude' on PATH is ${path:-missing}; put $BIN_DIR first in PATH (last lines of ~/.zshrc)"
  fi

  for cmd in $(profiles) claudech; do
    if [ "$(readlink "$BIN_DIR/$cmd" 2>/dev/null)" = claude-accounts ]; then
      ok "launcher $cmd"
    else
      bad "launcher $cmd missing; run: claude-accounts repair"
    fi
  done

  for cmd in $(profiles); do
    if has_login "$cmd"; then
      ok "$cmd logged in as $(account_email "$cmd") [$(keychain_service "$cmd")]"
    else
      bad "$cmd not logged in; run: $cmd auth login"
    fi
    for item in $SHARED_ITEMS; do
      path="$(profile_home "$cmd")/$item"
      if [ "$(readlink "$path" 2>/dev/null)" != "$SHARED/$item" ]; then
        bad "$cmd: $path is not linked to shared history; run: claude-accounts repair"
      fi
    done
  done

  if [ "$failures" -eq 0 ]; then
    printf '\nAll good.\n'
  else
    printf '\n%d problem(s) found.\n' "$failures"
    return 1
  fi
}

cmd_add() {
  local name="${1:-}" cmd
  [ -n "$name" ] || die "usage: claude-accounts add <name> [launch flags...]"
  shift
  case "$name" in
    *[![:lower:][:digit:]-]* | -* | '') die "profile names use only a-z, 0-9 and '-'" ;;
  esac
  cmd="claude-$name"
  if profile_flags "$cmd" >/dev/null 2>&1; then
    die "$cmd already exists"
  fi
  printf '%-18s %s\n' "$cmd" "$*" >>"$PROFILES_FILE"
  cmd_repair
  printf '\nNext: %s auth login\n' "$cmd"
}

cmd_repair() {
  local cmd
  mkdir -p "$BIN_DIR"
  for cmd in $(profiles) claudech; do
    ln -sfn claude-accounts "$BIN_DIR/$cmd"
  done
  for cmd in $(profiles); do
    link_profile "$cmd"
  done
  printf 'Launchers and shared history are in place.\n'
}

usage() {
  cat <<EOF
Usage: claude-accounts <command>

  list                    show profiles and the account each is logged into
  doctor                  check PATH, launchers, logins and history links
  add <name> [flags...]   create profile claude-<name> (then log it in)
  repair                  recreate launchers and relink shared history

Profiles live in $PROFILES_FILE.
Log a profile in or out with: <profile> auth login | <profile> auth logout
EOF
}

manage() {
  case "${1:-help}" in
    list | ls) cmd_list ;;
    doctor) cmd_doctor ;;
    add) shift && cmd_add "$@" ;;
    repair) cmd_repair ;;
    help | -h | --help) usage ;;
    *) usage >&2 && exit 1 ;;
  esac
}

case "$(basename "$0")" in
  claude-accounts) manage "$@" ;;
  claudech) pick "$@" ;;
  *) launch "$(basename "$0")" "$@" ;;
esac
```

</details>

<details>
<summary><code>install.sh</code></summary>

```bash
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
```

</details>

---

MIT License.
