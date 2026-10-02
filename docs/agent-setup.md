# Setup playbook for an AI coding agent

This is written so that an AI coding agent (or a careful human) can follow it top to bottom and set up claude-accounts on a new machine without ever touching an existing login. How each part works is in [how-it-works.md](how-it-works.md).

Follow these steps in order. The golden rule: **never do anything that changes
or removes an existing login.** Logins are Keychain items (macOS) or
`.credentials.json` files (Linux). They are keyed on exact config-directory
strings.

## Step 0: inspect the machine (read-only)

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

## Step 1: decide the profile names

- The stock login becomes plain `claude`.
- Each other account gets a name `claude-<name>` (lowercase letters, digits,
  `-`), backed by `~/.claude-<name>`.
- **If a logged-in directory already exists** (for example `~/.claude-foo`),
  reuse its name (`foo`) so the path string, and therefore the login, stays the
  same. Renaming a directory changes the hash, which means a fresh login.
- Directories that don't follow the `~/.claude-<name>` pattern
  (e.g. `~/claude-configs/work`): either leave them alone and re-login under a
  new profile, or, if the user agrees to one re-login, adopt a `~/.claude-<name>` dir.

## Step 2: remove old wrappers that would conflict

Look for existing aliases, functions or scripts named `claude`, `claude-*`, or
`claudech` in the shell rc files and on `PATH` (other than
`~/.local/bin/claude` itself). **Move them into a backup folder; do not delete
them.** Never replace `~/.local/bin/claude`: it belongs to Claude Code's updater.

## Step 3: install

```bash
curl -fsSL https://raw.githubusercontent.com/maxim-golubev/claude-accounts/main/install.sh | bash -s -- <name1> <name2> ...
```

Or from a clone of this repository, without the network: `./install.sh <name1> <name2> ...`
(it uses the `claude-accounts` script next to it).

The installer:

- copies the script;
- creates `profiles.conf` (only the stock `claude` line) if it doesn't exist;
- adds the PATH block to the end of `~/.zshrc` (or `~/.bashrc` for bash) once;
- adds each named profile;
- runs `repair`, which creates the launchers and merges and links history.

## Step 4: log in the new profiles

This step is interactive (it opens a browser). The **user** must do it, in a
new terminal:

```bash
claude-<name> auth login
```

Profiles that already had a login (reused directories) need nothing.

## Step 5: verify

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

## Rules for agents

- Never set `CLAUDE_CONFIG_DIR` to `~/.claude` for the stock profile. It must be *unset*.
- Never add a trailing slash to, or resolve symlinks in, a config path.
- Never run `auth logout`, and never delete, rename or edit `Claude Code-credentials*` Keychain items or `.credentials.json` files.
- Never copy credentials between profiles. OAuth refresh tokens rotate, so two
  copies of one login will log each other out. Log each profile in separately.
- Never delete history. Merges move files, and conflicts are kept in dated backup folders.
- Don't move or rename `~/.claude.json` or `<profile>/.claude.json`.
