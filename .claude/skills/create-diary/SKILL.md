---
name: create-diary
description: Rebuild the shoot folder's *diary/ directory (_diary/ by default) from scratch — every photo in 00info/, the first, middle and last JPEG of each group, every JPEG of each scattered-group, named <source>_<filename> and numbered d000010_, d000020_, ... in capture order, with each group's three frames kept together. Frames are read from each block's lights/jpg/ only; darks/, flats/ and bias/ never reach the strip. The diary is emptied first, so it always mirrors 00info/ and the blocks exactly. Reads the 6I-0001-... block names organize-photo-folders writes. Use when asked to create or rebuild the diary for a shoot folder such as "create diary for 2026_0821_camera_ccd_roof".
---

# Create diary

Puts the night's screenshots and charts beside its frames — everything in `00info/`, three frames
to stand for each intervalometer run, every test frame — so a whole night reads as a single ordered
strip in the diary directory.

Run this **after** `organize-photo-folders`. It reads `00info/` and the block directories that skill
produces, and does nothing without them.

**Frames come from `<block>/lights/jpg/`** — the light frames, the ones worth looking at. A block's
`darks/`, `flats/` and `bias/` are calibration the owner sorted out by hand after organizing, and
the strip has no use for them: they are never read. Nor is `raw/`, in `lights/` or anywhere else.

**The diary directory** is whatever `*diary/` directory sits at the root of the shoot folder —
`_diary/` is what gets created if there is none. `*diary/` is a protected name for
`organize-photo-folders`, so the two skills agree on it without either having to be told.

## Rule 0 — where the photos are

This skill lives in the `exiftool_mac` repo; the photos do not. They sit in `camera_latest/` on
the removable `UltraFit256` drive, at the path `config/config_vars.txt` calls
**`$dest_camera_dir_base`** — the same variable `go.sh` syncs that library from. The script reads
that file itself, so a shoot folder is named, never pathed:

```
create diary for 2026_0821_camera_ccd_roof
```

An absolute path, or a relative one that exists from the current directory, is still taken as
given — running the script from inside `camera_latest/` works unchanged. `$CAMERA_LATEST_DIR`
overrides the config var for a one-off run against another drive. A bare name is resolved only
after `camera_latest/it_exists.txt` is confirmed, so an unmounted drive stops the run instead of
presenting an empty directory as a shoot folder. `organize-photo-folders` resolves folders the
same way.

## Rule 1 — a folder argument is required

The skill needs one folder, e.g. "create diary for `2026_0821_camera_ccd_roof`".

**If no folder is named, stop and ask the user which folder to use.** Do not guess, do not scan for
candidates, do not pick the newest directory. Ask, then stop.

## Rule 2 — the folder must exist, hold `00info/`, be organized, and `exiftool` must run

Check all four before doing anything else. If the folder does not exist, stop and say so — do not
create it and do not look for a similarly-named folder.

**`exiftool` must exist and answer `exiftool -ver`** (`/opt/homebrew/bin/exiftool` is the fallback
if it is not on PATH). Everything here is sorted by capture time, so without it there is no diary.
Stop and say so.

**`00info/` must exist.** The diary is built from `00info/` and the blocks together, so a shoot folder
without one is not ready. Stop and say so — do not create `00info/`.

Stop as well if the folder holds no block directory with a `lights/jpg/` subdirectory: it has not
been organized yet. Say so, and stop — do not organize it on your own initiative.

**A block directory** is one whose name starts with `<prefix>-<nnnn>-` and holds `lights/jpg/`, the
shape `organize-photo-folders` writes: `6I-0035-550d-18mm-15s-f3.5-iso1600/lights/jpg`.

Nothing else counts. A card dump or a hand-made tree is not a block, so a shoot folder holding
none of these has simply not been organized yet — that is the case Rule 2 stops on. Names starting
with `_` or `.` are never blocks, at any depth, and neither are `00info/` and `*diary/` at the root.

A block holding a bare `jpg/` and no `lights/` is the **old layout**, from before `lights/` existed.
It is skipped with a warning rather than read: re-run `organize-photo-folders` on the folder to move
those frames under `lights/`, then build the diary. Say this to the user — do not run the organize
skill yourself to fix it, and do not move the files by hand.

## Rule 3 — the diary is rebuilt from scratch, every run

The diary is **emptied and filled again** on each run. It is not patched, and nothing in it
survives on its own merits: after a run it holds exactly what `00info/` and the current blocks call
for, and nothing else. This matters more than it used to: `organize-photo-folders` renumbers a whole
folder from whatever start number it is given, so block names change between runs and a diary frame
naming an old block is stale by definition. Rebuilding leaves none of them behind.

Because the diary is disposable, **`00info/` is where a photo belongs if it must appear in the strip.**
Dropping a frame straight into the diary no longer keeps it there — put it in `00info/` instead.

**There is no undo, and none is needed.** Every frame in the diary is a copy of a file still
sitting in `00info/` or a block, so the next run writes it straight back. That is also why emptying
the diary is safe to do outright: it holds no original, only copies, and a file in it that no source
accounts for is a leftover of an older run — a stale name from before a renumber — not something to
keep.

If a photo must be in the strip, **put it in `00info/`.** That is the only place that makes it
permanent; a frame dropped straight into the diary is gone on the next run.

## What it does

### 1. The diary directory

The `*diary/` directory at the top level of the shoot folder, or a new `_diary/` if there is
none. It is never itself treated as a block, and it sits with the other hand-curated `_` names —
`00info/`, `_tmp/`, `_dangling/`, `_post-processing/` — rather than pretending to be block zero.

### 2. Pick the frames

`00info/` is read at its top level; every block directory is read from its `lights/jpg/`
subdirectory only. **`raw/` is never touched, and neither is `darks/`, `flats/` or `bias/`**, and
nothing is ever moved or renamed inside `00info/` or a block — the diary is built from **copies**.

| Source | Told apart by | What is copied |
|---|---|---|
| `00info/` | the name `00info` | **every** photo in it |
| group, e.g. `6I-0002-6dii-24mm-8s-f11-iso100` | name carries `-iso<n>` | the **first, middle and last** frame, by capture time |
| scattered-group, e.g. `6I-0001-6dii` | no settings in the name | **every** frame |

A group is a fixed-interval run, so three frames show how it went: where it started, where it sat,
and what it had drifted to by the end — cloud rolling in, the target sliding out of frame, dew on
the glass. A scattered-group is the test and framing shots, which all differ — so all of them are
kept. `00info/` holds the night's story — screenshots, planning notes, weather and sky charts, phone
frames — so all of it is kept too.

A group of fewer than three frames contributes what it has: the three picks are de-duplicated, so a
two-frame group gives two and a one-frame group gives one. A block name may carry a hand-added
label after the ISO — `6H-0039-6dii-24mm-8s-f1.4-iso200_thor` — and is still a group.

Only `.JPG`/`.JPEG`/`.PNG` are taken from `00info/` (`DIARY_EXTS`); anything else there is reported
and left where it is. Blocks contribute `SOURCE_EXTS` only.

Each copy is named `<source>_<original filename>` — joined with an **underscore**, the source being
`00info` or the block directory:

```
00info/2026-08-18 21.15.04.png                            ->  00info_2026-08-18 21.15.04.png
6I-0002-6dii-24mm-8s-f11-iso100/lights/jpg/IMG_0013.JPG  ->  6I-0002-6dii-24mm-8s-f11-iso100_IMG_0013.JPG
6I-0001-6dii/lights/jpg/IMG_0001.JPG                     ->  6I-0001-6dii_IMG_0001.JPG
```

The `lights/jpg/` level does not appear in the name: the source is the **block**, and the frames
are lights because lights are the only thing the diary reads.

The underscore is what separates the source from the original filename; the dashes inside the name
all belong to the block.

The original filename is preserved inside the new name, so every diary frame still points back at
the exact file it came from.

### 3. Order the diary, then number it

The strip is ordered in **units**. Every photo from `00info/` and every frame of a scattered-group
is a unit of its own, placed at its own capture time. **A group is a single unit of three frames**,
inserted where its *first* pick falls — and the three then sit together.

That is the point of the unit: a group's first and last frame can be an hour apart, so sorting
every frame flat would strew the run's middle and end through everything shot alongside it. Placing
the three at the run's start keeps them readable as one run.

The ordered strip is then given a sequence prefix, starting at **`d000010_`** and **stepping by
10** — the number is joined to the rest with an **underscore** as well:

```
d000010_00info_2026-08-18 21.15.04.png
d000020_6I-0001-6dii_IMG_0001.JPG
d000030_6I-0002-6dii-24mm-8s-f11-iso100_IMG_0013.JPG
d000040_6I-0002-6dii-24mm-8s-f11-iso100_IMG_0027.JPG
d000050_6I-0002-6dii-24mm-8s-f11-iso100_IMG_0041.JPG
```

The gap of 10 is a reading convenience, not an insertion point any more — a run renumbers the strip
from `d000010` regardless, so a frame is added by putting it in `00info/`, not by squeezing a number
in between two others.

**The time a photo is sorted by.** Camera frames in a block are read from EXIF alone —
`SubSecDateTimeOriginal`, then `DateTimeOriginal`, then `CreateDate` — and a block frame with none
of those is ignored. For `00info/` the chain continues: a screenshot with no EXIF date falls back to
the `YYYY-MM-DD HH.MM.SS` time in **its own filename**, and then to `FileModifyDate`. Many
screenshots carry no EXIF date at all, and mtime is wrong in any folder that has been copied, so the
filename is tried first. Only a photo with no time by any of those routes sorts to the end, by name,
and is reported.

Because the diary is rebuilt whole, a run is idempotent: running it twice in a row leaves exactly
the same set of names, and running it after `00info/` or a block changed reflects that change.

## How to run it

Run from the repo checkout (`~/life_codes/exiftool_mac`). `<folder>` is a bare shoot-folder
name, resolved under `$dest_camera_dir_base` per Rule 0:

```bash
python3 .claude/skills/create-diary/diary.py <folder>            # plan only
python3 .claude/skills/create-diary/diary.py <folder> --apply    # rebuild the diary
```

Run the plan first and show the user the table. Then apply, in the same turn — being asked to create the diary is the request to write
it. Nothing else is written: the run leaves no state file behind, only the diary itself.

`--apply` empties the diary and fills it again — say so plainly before running it. Originals inside
`00info/` and the block folders are never touched, so a rebuild costs nothing but the copying, and
running it again is the way back from any run.

## Reporting back

After applying, report:

- the per-source table: source, type, frames available, which frames were picked
- the resulting diary in order, with its `dNNNNNN-` numbers
- how many frames were written, and how many the run removed from the diary first
- verification that `00info/` contributed every photo, groups three frames each (fewer only when
  the group holds fewer) kept together in the strip, and scattered-groups all of theirs
- anything worth revisiting — non-photo files left in `00info/`, blocks skipped for unreadable
  timestamps, blocks skipped for holding a bare `jpg/` and no `lights/` (the old layout — say the
  folder wants re-organizing), photos placed by filename or mtime rather than EXIF, or a
  scattered-group large enough to swamp the strip. Flag these; do not silently drop them.
