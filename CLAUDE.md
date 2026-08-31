# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal media-pipeline of Bash scripts wrapping `exiftool` and `rsync`. Three jobs: reorganize phone photo dumps into a date-named local library, replicate that library to two Synology NAS boxes, and repair EXIF datetime/GPS tags by hand. One scratch folder (`camera_working`) is pulled back down from the DS918 — the only sync that writes to the Mac. There is no build, no test suite, no linter, no dependency manifest — every file is a standalone script. Almost all of them are Bash on macOS; the two `.bat` files are the Windows end of `camera_working` and are the exception to every rule below. `README.md` is the user-facing narrative; read it for the *why* behind the pipeline.

## Scripts must be sourced, not executed

`go.sh` and the `changedate_*.sh` scripts use `return` for early exit and rely on shell aliases (`date`→`gdate`, `rsync`→homebrew `rsync`). They break when run as `./go.sh`. Always:

```shell
cd ~/life_codes/exiftool_mac
. go.sh 2
```

macOS ships BSD `date` and a broken `rsync`; `go.sh` prepends `/opt/homebrew/bin` to `PATH` and aliases both. Never "simplify" those aliases or the `export PATH` line away.

## Architecture: a config × mode matrix

There is no application logic to speak of — `go.sh` is one big `if [ "$is_nas" -eq N ]` dispatch over four modes, and the interesting structure is a matrix:

- **Three libraries**, each a `dest_*_dir_base` var: photo, video, camera. Plus `camera_working`, a scratch folder that travels the other way.
- **Four numeric modes**: `0` = collect from Dropbox into the libraries (local only); `1` = mirror over `/Volumes/` SMB mounts (DS918 only); `2` = mirror over rsync daemon port 873 on the LAN (DS918 + DS1525); `3` = mirror to DS918 over the internet.
- **One string mode**: `camera_working` (short form `cw`), the NAS→Mac pull — see below.

`is_nas=$1` feeds `[ "$is_nas" -eq N ]`, a *numeric* test, so a string arg would throw `integer expression expected` four times and fall through silently. The string mode is therefore normalized up front: it sets `is_camera_working=1` and rewrites `is_nas=9` so no numeric block matches, and a `case` guard rejects anything else non-numeric with a message. **Any new string mode has to go through that same normalization.**

Every path is a variable in `config/config_vars.txt`, sourced at startup. Nothing is hardcoded in `go.sh` except host IPs, usernames, and the mode structure itself. **Adding a library** therefore means: one `dest_*` var, one `remote_<host>_*` var per NAS, and one rsync block per mode — the camera library added in the most recent commit is the worked example to copy.

Remote paths are rsync **daemon module** paths (`host::module/subdir`), not filesystem paths. The first component is the Synology shared-folder name as exported by the rsync service. List what a box actually exports before assuming a path works:

```shell
sshpass -p "$pw" rsync --port=873 --protocol=29 admin@192.168.123.163::
```

### Two tracks into the library

`go.sh 0` populates `photo_latest/` and `video_latest/` only. **`camera_latest/` is organized by hand** (SD-card imports, `YYYY_MMDD_camera_event/<body>-<lens>/`, JPG alongside CR2 RAW) and only joins the pipeline at the sync stage. Don't add camera handling to mode `0`.

### `camera_working` runs backwards, and `--delete` points at the Mac

`. go.sh cw` is a single `rsync -a --delete` **from** DS918 **to** the local folder — the reverse of every other mode. The Photoshop work happens on a Windows machine that syncs itself against the NAS folder; the Mac only collects results. No `-u`: a locally-newer file is overwritten, because the goal is an exact copy of the NAS.

This inverts the repo's usual hazard. Elsewhere a missing local drive endangers the remote; here **an unreachable NAS endangers the local folder**. The remote `it_exists.txt` probe is therefore load-bearing, not a convenience — if it fails the block must skip entirely, or the Mac folder gets emptied. The local sentinel is still checked as well, to avoid dumping gigabytes onto the internal disk when UltraFit256 is unmounted.

Excluded: `@eaDir` (Synology-generated), `.DS_Store`, `.Trashes`, and `Thumbs.db` / `desktop.ini` (from the Windows box that owns the folder's content). Note rsync protects excluded files on the *receiver* from `--delete`, so adding an exclude never removes copies already pulled down — they go permanently stale and must be deleted by hand once.

It was a two-way sync until 2026-08-31. If you are tempted to restore the push pass, note that a two-way rsync cannot use `--delete` at all — the two passes destroy each other's files.

## The Windows end: `go.bat` and `mnt.bat`

Two `.bat` files, the other half of `cw`. They invert most of this file's assumptions, so read this before editing either.

- **Executed, not sourced.** `go.bat cw`, never `. go.bat cw` — the opposite of `go.sh`'s contract. Nothing here uses `return` and there are no aliases to preserve.
- **`go.bat` takes `cw` and nothing else** — one argument, exactly `cw`. Modes `0`/`1`/`2`/`3` stay Mac-only and print usage. Extra arguments are rejected, mirroring `go.sh`'s `$# -ne 1`.
- **`robocopy /MIR` is `rsync -a --delete`.** Direction is Windows → NAS, and Windows holds the master copy. There is no `/XO`: an exact mirror is the point, so a NAS-newer file is overwritten too. Do not add it — that was the old two-way design and it is gone.
- **`/FFT` is mandatory**, for the same class of reason `--protocol=29` is. NTFS keeps 100ns timestamps, the Synology over SMB only second-level; without a 2-second tolerance every file looks newer on every run and the whole folder re-transfers. It is rsync's `--modify-window`.
- **Robocopy exit codes are not Unix.** 0–7 all mean success (1 = copied, 2 = extras in destination, 4 = mismatch); only `>= 8` is failure. The guard is `if %RC% GEQ 8` — `if errorlevel 1` would report every successful sync as an error. `rc=2` is routine here: it is `@eaDir` being counted as an extra.
- **Excluded items are not purged on the destination**, exactly as in rsync. That is what keeps `/XD @eaDir` from deleting Synology's thumbnails on every run.

### The danger cascades

`/MIR` deletes on the **NAS** side, and `. go.sh cw` then mirrors the NAS onto the Mac. An empty or mistyped local Windows folder therefore empties the NAS folder, and the next Mac pull empties the Mac folder. **One bad run takes out all three copies.** Both `it_exists.txt` sentinels are checked before robocopy is invoked for precisely this reason, and here the *source* one is the load-bearing check. `set "GO_DRY=1"` switches to `robocopy /L` — quoted, because `set GO_DRY=1 & ...` stores the trailing space and a later bare `set GO_DRY=` then fails to clear it, silently pinning the script in dry-run.

### Drive letters are per-logon-session

The one that wastes an afternoon. A `T:` connected in Explorer does **not** exist inside an SSH login, a scheduled task, or an elevated shell — each gets its own logon session. `dir T:\` there reports "path not found", while `net use` may still *list* the mapping as Unavailable, because listing and connecting are different things. Key-based SSH compounds it: the token carries no password, so even the UNC path fails until something authenticates the server.

`mnt.bat` is the fix, and the only Windows script that touches credentials (`nas_drive` / `nas_unc` / `nas_user` from `config_win.txt`, `$pw` from `config_secrets.txt`). It is idempotent, and it **must not call `net use /delete`** — that drops a remembered mapping account-wide, not just for the session. It authenticates the server and retries instead, which clears a dead drive letter on its own.

`go.bat` deliberately knows none of this: it takes a path and checks whether it is there.

### Windows config

`config/config_win.txt` is **gitignored** — every Windows box keeps its own, which is why its paths are not committed the way `config_vars.txt`'s are. `config/config_win_example.txt` is the template and must be updated alongside any new key. Both files are read with `for /f "eol=# tokens=1,* delims=="`, so leading whitespace or spaces around `=` will break them, and a value containing `%` or `^` will not survive expansion.

`.gitattributes` pins `*.bat` to CRLF and `*.sh` to LF. cmd.exe misparses LF-only batch files around multi-line blocks and labels, so that rule is not cosmetic.

## Danger surface

Every sync is `rsync -a --delete`, and the local library lives on a **removable drive** (`UltraFit256`). If that drive is unmounted the source path still resolves as an empty directory, and a `--delete` sync from it would erase the remote copy.

That is what the empty `it_exists.txt` files guard. They sit at the top of each library, propagate to the remotes via `rsync -a`, and are checked as a proof-of-liveness: mode `0` writes only into a destination that has one, mode `1` checks the mounted share, modes `2`/`3` use the remote one as a reachability probe. **Preserve these checks when editing sync blocks.** A sync that silently does nothing is almost always a missing sentinel.

When changing any rsync invocation, verify with `--dry-run --stats` first and read the created/deleted counts before running it live.

Other landmines:

- **`--protocol=29` is required** on mode-2 transfers. The newer protocol stopped working against these Synology daemons on 2024/09/21. Removing it breaks the sync.
- Mode `2` probes only the **video** module, then syncs photo and camera off that one result — a per-library probe would deadlock, since a fresh remote folder has no `it_exists.txt` until the first sync puts it there.
- **The probe's `$?` must be read immediately.** Each reachability probe is a bare `--dry-run` rsync followed by `if [ $? -eq 0 ]`. Putting anything between them — an `echo`, a comment is fine, a command is not — makes `$?` that command's status and the guard silently stops guarding. This was a live bug in the DS918 mode-2 block (fixed 2026-08-22); the trace `echo` now goes *before* the probe.
- `changedate_*.sh` and `gps_*.sh` all use `-overwrite_original` and mutate media in place. `changedate_mp4_batch.sh` rewrites *every* `.mp4` in the working directory with the same timestamp.
- Timestamps are hardcoded to `+08:00` (Taiwan) throughout.
- `-api QuickTimeUTC -ee` is mandatory on every video exiftool call; QuickTime stores dates in UTC and omitting it shifts everything by the offset.

## Conventions

- **Comments are bilingual.** Explanatory notes are frequently in Traditional Chinese, often recording *why* a workaround exists (e.g. the `--protocol=29` note). Match the surrounding language when editing a block.
- **The `.bat` files are the exception: ASCII English only.** `go.bat` and `mnt.bat` get read through a console (`type mnt.bat` over SSH), and a Windows console's codepage is not something the repo can control — at cp950 the UTF-8 Chinese comes out as mojibake. Everything else in the repo is read in an editor, so it stays bilingual. Do not "restore" Chinese comments to the `.bat` files; put the Chinese explanation in `readme.txt` or `README.md` instead.
- **Retired config is commented, not deleted.** DS212 (`192.168.123.162`, the `remote_213_*` vars) was a third NAS target; its blocks survive commented out in both `go.sh` and `config/config_vars.txt`. Leave them.
- The `changedate_mp4.sh` / `changedate_mov.sh` scripts require their target to be renamed to literally `aaa.mp4` / `aaa.mov`.
- `gps_*.sh` hardcode absolute paths to their reference clips in `gps_sample/`. Those checked-in media files are not test fixtures — each *is* a saved GPS coordinate, copied onto target files via `-tagsFromFile`. Do not remove them.

## Secrets

`config/config_secrets.txt` is gitignored and sourced by `go.sh`. Modes `2` and `3` read exactly five vars from it — `$pw` (DS918 LAN), `$pw_1525` (DS1525 LAN), and `$pi_public` / `$pp_public` / `$pw_public` (DS918 over the internet); modes `0` and `1` need none. `config/config_secrets_example.txt` mirrors that set and should be updated alongside any new credential.

`mnt.bat` on Windows parses the same file for `$pw` — the same DS918 `admin` password mode `2` uses, deliberately not a second copy under a new name. If you add a Windows credential, reuse an existing key before inventing one; two keys for one account drift apart. Note the file is *parsed* there, not sourced, so it must stay plain `KEY=VALUE` — no shell quoting, no `export`, or the batch parser takes the quotes literally.

LAN hosts and usernames (`admin@192.168.123.163`, `jie@192.168.123.164`) are hardcoded in `go.sh`, not in the secrets file — only the public endpoint is configurable.

## Off-limits

`readme.txt` opens with an explicit instruction from the repo owner: it is an engineer's private memo, not to be referenced or modified unless they say so. Don't read it into docs, and don't edit it.
