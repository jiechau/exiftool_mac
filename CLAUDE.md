# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal media-pipeline of Bash scripts wrapping `exiftool` and `rsync`. Three jobs: reorganize phone photo dumps into a date-named local library, replicate that library to two Synology NAS boxes, and repair EXIF datetime/GPS tags by hand. There is no build, no test suite, no linter, no dependency manifest — every file is a standalone shell script. `README.md` is the user-facing narrative; read it for the *why* behind the pipeline.

## Scripts must be sourced, not executed

`go.sh` and the `changedate_*.sh` scripts use `return` for early exit and rely on shell aliases (`date`→`gdate`, `rsync`→homebrew `rsync`). They break when run as `./go.sh`. Always:

```shell
cd ~/life_codes/exiftool_mac
. go.sh 2
```

macOS ships BSD `date` and a broken `rsync`; `go.sh` prepends `/opt/homebrew/bin` to `PATH` and aliases both. Never "simplify" those aliases or the `export PATH` line away.

## Architecture: a config × mode matrix

There is no application logic to speak of — `go.sh` is one big `if [ "$is_nas" -eq N ]` dispatch over four modes, and the interesting structure is a matrix:

- **Three libraries**, each a `dest_*_dir_base` var: photo, video, camera.
- **Four modes**: `0` = collect from Dropbox into the libraries (local only); `1` = mirror over `/Volumes/` SMB mounts (DS918 only); `2` = mirror over rsync daemon port 873 on the LAN (DS918 + DS1525); `3` = mirror to DS918 over the internet.

Every path is a variable in `config/config_vars.txt`, sourced at startup. Nothing is hardcoded in `go.sh` except host IPs, usernames, and the mode structure itself. **Adding a library** therefore means: one `dest_*` var, one `remote_<host>_*` var per NAS, and one rsync block per mode — the camera library added in the most recent commit is the worked example to copy.

Remote paths are rsync **daemon module** paths (`host::module/subdir`), not filesystem paths. The first component is the Synology shared-folder name as exported by the rsync service. List what a box actually exports before assuming a path works:

```shell
sshpass -p "$pw" rsync --port=873 --protocol=29 admin@192.168.123.163::
```

### Two tracks into the library

`go.sh 0` populates `photo_latest/` and `video_latest/` only. **`camera_latest/` is organized by hand** (SD-card imports, `YYYY_MMDD_camera_event/<body>-<lens>/`, JPG alongside CR2 RAW) and only joins the pipeline at the sync stage. Don't add camera handling to mode `0`.

## Danger surface

Every sync is `rsync -a --delete`, and the local library lives on a **removable drive** (`UltraFit256`). If that drive is unmounted the source path still resolves as an empty directory, and a `--delete` sync from it would erase the remote copy.

That is what the empty `it_exists.txt` files guard. They sit at the top of each library, propagate to the remotes via `rsync -a`, and are checked as a proof-of-liveness: mode `0` writes only into a destination that has one, mode `1` checks the mounted share, modes `2`/`3` use the remote one as a reachability probe. **Preserve these checks when editing sync blocks.** A sync that silently does nothing is almost always a missing sentinel.

When changing any rsync invocation, verify with `--dry-run --stats` first and read the created/deleted counts before running it live.

Other landmines:

- **`--protocol=29` is required** on mode-2 transfers. The newer protocol stopped working against these Synology daemons on 2024/09/21. Removing it breaks the sync.
- Mode `2` probes only the **video** module, then syncs photo and camera off that one result — a per-library probe would deadlock, since a fresh remote folder has no `it_exists.txt` until the first sync puts it there.
- `changedate_*.sh` and `gps_*.sh` all use `-overwrite_original` and mutate media in place. `changedate_mp4_batch.sh` rewrites *every* `.mp4` in the working directory with the same timestamp.
- Timestamps are hardcoded to `+08:00` (Taiwan) throughout.
- `-api QuickTimeUTC -ee` is mandatory on every video exiftool call; QuickTime stores dates in UTC and omitting it shifts everything by the offset.

## Conventions

- **Comments are bilingual.** Explanatory notes are frequently in Traditional Chinese, often recording *why* a workaround exists (e.g. the `--protocol=29` note). Match the surrounding language when editing a block.
- **Retired config is commented, not deleted.** DS212 (`192.168.123.162`, the `remote_213_*` vars) was a third NAS target; its blocks survive commented out in both `go.sh` and `config/config_vars.txt`. Leave them.
- The `changedate_mp4.sh` / `changedate_mov.sh` scripts require their target to be renamed to literally `aaa.mp4` / `aaa.mov`.
- `gps_*.sh` hardcode absolute paths to their reference clips in `gps_sample/`. Those checked-in media files are not test fixtures — each *is* a saved GPS coordinate, copied onto target files via `-tagsFromFile`. Do not remove them.

## Secrets

`config/config_secrets.txt` is gitignored and sourced by `go.sh`. Modes `2` and `3` read exactly five vars from it — `$pw` (DS918 LAN), `$pw_1525` (DS1525 LAN), and `$pi_public` / `$pp_public` / `$pw_public` (DS918 over the internet); modes `0` and `1` need none. `config/config_secrets_example.txt` mirrors that set and should be updated alongside any new credential.

LAN hosts and usernames (`admin@192.168.123.163`, `jie@192.168.123.164`) are hardcoded in `go.sh`, not in the secrets file — only the public endpoint is configurable.

## Off-limits

`readme.txt` opens with an explicit instruction from the repo owner: it is an engineer's private memo, not to be referenced or modified unless they say so. Don't read it into docs, and don't edit it.
