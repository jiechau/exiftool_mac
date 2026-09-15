---
name: organize-photo-folders
description: Sort a shoot folder of astro photos into <YM>-<nnnn>-<camera>-<focal>-<shutter>-<aperture>-<iso>/00_Original/{RAW,JPG} by reading EXIF and detecting fixed-interval (intervalometer) runs, and scaffold each block with 01_Astro/ 02_Landscape/ 03_Portraits/ 04_tests/ for the hand work that follows. Walks the shoot root and every subdirectory at any depth - card dumps (100CANON/, DCIM/100MSDCF/), older hand-made trees, already-organized blocks - pools every photo into one capture-time stream, and deletes each source directory once it is empty. An already-organized block is re-read from its 00_Original/ only; everything else in it, and every directory whose name starts with _, is parked under _dangling/ with its path preserved, since the block around it is about to be renumbered. Runs on macOS and Windows 11. Takes the folder and a starting block number. Use when asked to organize, sort, or group a shoot folder such as "organize 2026_0907_camera_daw_bay 10".
---

# Organize photo folders

Turns a night's shooting — however it currently sits on disk — into the per-block tree the rest
of this project reads. It re-reads the whole folder every time, so running it twice or three times
over the same folder is normal and expected.

**The rules are in [`organize-photo-folders.md`](../../../organize-photo-folders.md) at the repo
root — read it before changing behaviour.** This file is how to run the thing.

## Ask before you run

Neither argument is ever guessed.

- **No folder named?** Ask which shoot folder, then stop.
- **No start number?** Ask what the first block number should be, then stop. It is usually
  "one past the last block number already used this month" — but that is the owner's call, not a
  thing to infer.

## Run it

```bash
cd ~/life_codes/exiftool_mac
python3 .claude/skills/organize-photo-folders/organize.py 2026_0907_camera_daw_bay 10
```

The folder is **named, not pathed** — the script reads `config/config_vars.txt` itself
(`dest_camera_dir_base` on macOS, `dest_camera_dir_copy` on Windows 11). An absolute path still
works if you have one.

**Plan first, always.** The command above only prints what it would do. Read the plan out to the
owner, then apply in the same turn:

```bash
python3 .claude/skills/organize-photo-folders/organize.py 2026_0907_camera_daw_bay 10 --apply
```

| flag | what for |
|---|---|
| `--apply` | actually move files (default is plan only) |
| `--exiftool PATH` | when exiftool is not on `PATH` — see below |
| `--prefix 6I` | override the date prefix, when the folder name carries no `YYYY_MMDD` |
| `--keep-source` | leave absorbed source directories behind even when empty |

## If exiftool is not found

The script stops with a list of what it tried. **Ask the owner where exiftool is on this machine**
and re-run with `--exiftool <path>`. Do not install it, and do not guess a path.

## Reading the plan back

Say these things, because they are what the owner is deciding on:

- **How many blocks, and the numbering range.** `4 blocks (2 groups, 2 scattered-groups)`, first
  `6I-0010`, last `6I-0013`.
- **Anything going into `_dangling/`.** This is work being moved out of a block that is about to
  be renumbered. Name the paths. Nothing is lost, but the owner has to move it back afterwards.
- **Anything being removed.** Emptied source directories and empty scaffolding from an earlier
  run. Both are routine; say so rather than listing all of it.
- **A scattered group that spans two bodies or two focal lengths.** The plan prints why its name
  is short. Repeat it — a bare `6I-0015` looks like a bug otherwise.

## Afterwards

Every photo is in `<block>/00_Original/{RAW,JPG}` and every other directory in the block is empty
and waiting. The owner files frames into `01_Astro/lights/`, `02_Landscape/lights/` and so on by
hand; nothing here does that, and nothing here ever reads those back as a photo source.

`create-diary` and `tag-photo` both work on the result. Until frames are filed into a category,
`create-diary` builds the strip from `00_Original/JPG`.

## Testing a change

Never against the drive. Copy a shoot folder somewhere scratch, `touch it_exists.txt` beside it,
and point the script at it:

```bash
cp -R "$dest_camera_dir_base/2026_0907_camera_daw_bay" /tmp/lab/
touch /tmp/lab/it_exists.txt
CAMERA_LATEST_DIR=/tmp/lab python3 .claude/skills/organize-photo-folders/organize.py \
    2026_0907_camera_daw_bay 10
```

Then check the two things that break first: run it twice and confirm the second run moves 0 files
and produces identical block names, and put a file into a block's `01_Astro/lights/JPG` and
confirm it lands in `_dangling/` with its path intact rather than being re-pooled.
