# How claude-accounts works

The details behind the [README](../README.md): how Claude Code keeps logins apart, how one script serves every account, and how history is shared without losing anything.

## 1. One login per config directory

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

## 2. One script, many launcher names

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

## 3. Finding the real binary

`~/.local/bin/claude` stays exactly as Claude Code's native installer made it: a
symlink that the auto-updater moves to each new version. The launcher resolves
the real binary on every start, in this order:

1. `$CLAUDE_ACCOUNTS_REAL_BIN`, if set.
2. `~/.local/bin/claude` (native install; follows the updater automatically).
3. The newest build in `~/.local/share/claude/versions/`.
4. Any other `claude` on `PATH` (npm or Homebrew installs), skipping the launchers.

So updates need no action, and `claude update` works as usual.

## 4. PATH order: the one thing that breaks

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

## 5. Shared history

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

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `claude` ignores the profile / `command -v claude` shows `~/.local/bin/claude` | PATH order. Move the `claude-accounts` block to the end of `~/.zshrc`, open a new terminal. In an old terminal, run `hash -r`. |
| A profile suddenly asks you to log in | Its config path string changed (renamed dir, trailing slash, `~/.claude` set explicitly), or its login was copied elsewhere and rotated. Run `claude-<name> auth login`. |
| `--resume` doesn't show a thread | Transcripts are grouped by working directory, so run it from the directory the conversation started in. Also check `claude-accounts doctor` for unlinked items. |
| `cannot find the Claude Code binary` | Install Claude Code, or set `CLAUDE_ACCOUNTS_REAL_BIN=/path/to/claude`. |
| `local-history-before-shared-*` folders | Conflicts kept during a merge. Inspect them, then delete them when you are satisfied. |
| An IDE extension or desktop app uses the wrong account | They usually start Claude Code without these launchers, so they use the stock profile. Log that into the account you want them to use. |
