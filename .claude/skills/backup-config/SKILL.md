---
name: backup-config
description: Back up this repo's config files and .claude/ to the jsave backup repo and push. Use when the user asks to "backup config", "sync to jsave", or wants config_vars.txt / config_secrets.txt / config_win.txt / .claude saved off to gitlab jsave.
---

# backup-config

`config/` 裡的東西大半是 gitignored（`config_secrets.txt`、`config_win.txt`），
在這個 repo 裡沒有備份。這個 skill 把它們（連同 `.claude/`）複製到另一個 repo
`jsave` 再 push 出去——**那才是這些檔案唯一的備份**。

Source project root: `~/life_codes/exiftool_mac`
Backup repo: `~/life_codes/jsave` (origin must be `https://gitlab.com/jiechau/jsave.git`)
Backup target dir: `~/life_codes/jsave/exiftool_mac/`

Backed up (force-overwrite into the target dir, **flat** — no `config/` level,
matching what is already there):

- `config/config_secrets.txt`
- `config/config_secrets_example.txt`
- `config/config_sourcedir.txt`
- `config/config_vars.txt`
- `config/config_win.txt` — **optional**, gitignored and per-Windows-box, so it
  does not exist on the Mac. Missing is normal; skip it, don't fail.
- `.claude/` (whole directory, mirrored)

## Steps

1. **Validate the backup repo first, before copying anything.** `~/life_codes/jsave`
   must exist, be a git repo, and have `origin` pointing at `jsave.git`. If not —
   **stop and warn the user**. Do not create it, do not guess another location.

2. **`git pull` in `jsave`.** Still before the copy: pulling on top of freshly
   copied files is how a conflict eats a just-made backup. If the pull fails,
   stop and report.

3. **Copy**, force-overwriting into `~/life_codes/jsave/exiftool_mac/`.
   `.claude/` is mirrored (target removed first), so a deleted skill also
   disappears from the backup.

4. **Commit and push** from `~/life_codes/jsave`: `git add -A`, and if there is
   nothing staged say "no changes to back up" and stop; otherwise commit as
   `backup exiftool_mac config <YYYY-MM-DD HH:MM>` and `git push`.

5. Report what was copied (and whether `config_win.txt` was there) and confirm
   the push.

## One-shot command

All of the above lives in `backup.sh` next to this file. Run it as one fixed
command with no arguments, so it can be allowlisted once in settings instead of
prompting per step:

```bash
bash ~/life_codes/exiftool_mac/.claude/skills/backup-config/backup.sh
```

It is **executed, not sourced** — unlike `go.sh` it has no aliases and no
`return`, so the repo's usual sourcing rule does not apply here.

Edit `backup.sh` to change what gets backed up; keep this file's list in sync.
Note `jsave` pushes to three remotes (gitlab / github / bitbucket) off one
`origin`, so a single `git push` can partly fail — read its output.
