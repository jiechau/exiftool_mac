---
name: organize-photo-folders
description: Sort a shoot folder of astro photos into <YM>-<nnnn>-<camera>-<focal>-<shutter>-<aperture>-<iso>/lights/{jpg,raw} by reading EXIF and detecting fixed-interval (intervalometer) sequences. Walks the shoot root and every subdirectory under it at any depth - card dumps (CANON100/, DCIM/100MSDCF/), older hand-made trees, already-organized blocks, hand-sorted darks/ and flats/ - flattens them, and deletes each source directory once it is empty. Any directory whose name starts with _ is skipped at every depth, except a post-processing tree below the root - post-processing* and _post-processing* alike are parked under _dangling/ first, path preserved, since the block around them is about to be renumbered. Takes the folder and a starting block number. Use when asked to organize, sort, or group a shoot folder such as "organize 2026_0818_camera_jilong_dwl_parking 35".
---

# Organize photo folders

Turns a night's shooting — however it currently sits on disk — into the per-block tree used
across this project. It re-reads the whole folder every time, so running it twice or three
times over the same folder is normal and expected.

Every frame it places lands in `<block>/lights/`. Calibration frames — `darks/`, `flats/`,
`bias/` — are the owner's to sort out by hand afterwards, and this skill knows nothing about
them: see Rule 5.

## Rule 0 — where the photos are

This skill lives in the `exiftool_mac` repo; the photos do not. They sit in `camera_latest/` on
the removable `UltraFit256` drive, at the path `config/config_vars.txt` calls
**`$dest_camera_dir_base`** — the same variable `go.sh` syncs that library from. The script reads
that file itself, so a shoot folder is named, never pathed:

```
organize 2026_0818_camera_jilong_dwl_parking 35
```

An absolute path, or a relative one that exists from the current directory, is still taken as
given — running the script from inside `camera_latest/` works unchanged. `$CAMERA_LATEST_DIR`
overrides the config var for a one-off run against another drive.

Because the library is on a removable drive, the script checks `camera_latest/it_exists.txt`
before resolving a bare name — the repo's usual proof-of-liveness. An unmounted drive leaves an
empty directory behind that would otherwise look like a shoot folder that lost its photos, so a
missing sentinel stops the run.

## Rule 0.5 — the arguments and the tool must check out

Two things are verified before anything is read or moved, and either one failing stops the run:

1. **The folder argument exists.** It is required — "please organize the folder
   `2026_0818_camera_jilong_dwl_parking`". If no folder is named, stop and ask which one. Do
   not guess, do not scan for candidates, do not pick the newest directory. If the named
   folder does not exist under `camera_latest/`, stop and say so — do not create it and do not
   look for a similarly-named one.
2. **`exiftool` exists and runs.** `exiftool -ver` has to answer (`/opt/homebrew/bin/exiftool`
   is the fallback if it is not on PATH). If it is missing or will not run, stop and say so.

Also stop if the folder holds no photos outside the protected names: it is either the wrong
folder or there is nothing left to sort. Say which, and stop.

### The second argument: where the numbering starts

The skill takes a **starting block number** as its second argument:

```
organize 2026_0818_camera_jilong_dwl_parking 35     ->  first block is 0035, then 0036, 0037, ...
```

It defaults to `1` when omitted. Numbers are zero-padded to four digits.

## Rule 1 — no log, no undo

Nothing is recorded and nothing is restorable. There is no manifest, no `--undo`. The skill is
safe to re-run because it rebuilds the layout from EXIF each time, not because it can walk
itself back. Run the plan first, look at it, then apply.

## Rule 2 — protected names: `_` anywhere, `00info/` and `*diary/` at the root

A protected directory is never entered, never read for photos, never removed. There are two
kinds.

**A leading `_` protects a directory at every depth**, wherever it sits:

```
_tmp/  _dangling/  _diary/  _post-processing/
_info/                                       # the name 00info/ used to carry
6I-0011-6dii-24mm-8s-f1.8-iso3200/_lights_v2/           # inside a block, still protected
_weird/post-processing/                      # a protected parent is never entered at all,
                                             # so what is inside it is out of reach too
```

This is the rule that lets the owner park anything anywhere and have it survive a re-run: a
`_notes/` beside the card dump, a `_reject/` full of frames that must not come back, a
`_lights_v2/` inside an already-organized block. Name it with a `_` and the skill walks past
it. A leading dot does the same, at every depth.

**The one exception is a post-processing tree below the root** — `_post-processing/` included.
The underscore does not save it there, because it gets parked under `_dangling/` instead of
being left in place: see Rule 4 for why. Everywhere the walk does not reach at all — inside a
`_weird/`, say — nothing is parked either, protection of the parent settling it.

**Two names are protected only at the top level** of the shoot folder, because they carry no
underscore:

```
00info/     *diary/          # *diary is a glob: diary/, my-diary/, _diary/ all match
```

**These two mean nothing below the root.** A nested `00info/` two levels down is just another
directory full of photos and gets flattened like the rest. And nothing else is protected at
all: card dumps, hand-made subfolders, existing block directories and their `lights/`,
`darks/` and `flats/` are ordinary directories whose photos get re-sorted.

## Rule 3 — walk everything, flatten it, re-block it

The skill takes **the whole shoot folder**: the root, and every subdirectory under it at any
depth. Photos are gathered from all of them into one pool, sorted by time, and re-blocked from
scratch into flat directories directly under the shoot folder. Each emptied source directory is
then **removed**, walking upward, so `DCIM/100MSDCF/` takes `DCIM/` with it and an old
`550d-18mm/8s-f11-iso100/jpg/` takes its two parents.

That includes a folder the owner has already sorted by hand: a block's `lights/` comes back as
lights, and its `darks/` and `flats/` come back as ordinary photos to be re-blocked. Rule 5
says what to do about that — nothing, on this skill's part.

This is what makes the skill re-runnable: a card dump (`CANON100/`, `100CANON/`,
`DCIM/100MSDCF/`), an older hand-made `<camera>-<focal>/` tree, and a set of blocks from
a previous run are all just directories full of photos, and all end up in the same flat layout.
A folder that is already correct comes out unchanged — nothing moves.

Guardrails, none of which are negotiable:

- A source directory goes once nothing but **OS junk** is left in it — `.DS_Store`, `Thumbs.db`,
  `desktop.ini`, `._*` — and that junk is deleted with it. This is what makes `iphone15pro/`
  disappear instead of surviving on a stray `.DS_Store`.
- Anything a person made saves the directory: a `.txt`, a `.tif` stack, a photo the skill could
  not read. The directory stays, with a note on stderr saying what is still inside.
- If the same filename appears in two directories (a camera counter reset), the skill **refuses
  and stops** rather than guessing which one to keep.
- A photo already sitting in the directory the plan wants is left alone, not moved onto itself.

Pass `--keep-source` to organize the photos but leave the emptied directories in place.

## Rule 4 — a post-processing tree goes to `_dangling/`, path and all

Before the photo walk starts, every directory named `post-processing*` **or
`_post-processing*`** found anywhere under the shoot folder is moved to `_dangling/`,
**keeping its path**:

```
abc/abc/post-processing/                            ->  _dangling/abc/abc/post-processing/
abc/abc/_post-processing/                           ->  _dangling/abc/abc/_post-processing/
6I-0011-6dii-24mm-8s-f1.8-iso3200/_post-processing/ ->  _dangling/6I-0011-6dii-24mm-8s-f1.8-iso3200/_post-processing/
```

Its photos are never pulled into a block, and its emptied parents (`abc/abc/`, `abc/`) are
pruned behind it. If the same path is already sitting in `_dangling/` from an earlier run the
two are merged; a file that would overwrite an existing one is left where it is and reported.

**The underscore does not keep a post-processing tree in place below the root**, which is the
one place Rule 2 gives way. The reason is the path: this skill renumbers every block from
whatever start number it is given, so `6I-0011-...` may well be `6I-0014-...` by the time the
run ends. A `_post-processing/` left sitting inside it would then be filed under a block it was
never made from — silently wrong, and hard to notice later. Parking it records the name the
block had when the processing was done, which is exactly what `_dangling/` is for.

**At the root the underscore still wins.** A top-level `_post-processing/` is the owner's own
finished work, filed where they put it, with no block name around it to go stale. It is never
touched. Only the underscore-less `post-processing/` is parked from the root.

## Rule 5 — every frame lands in `lights/`, and calibration is not this skill's business

A block's photos go into `<block>/lights/jpg` and `<block>/lights/raw`. Everything this skill
places is a light frame, because a light frame is all it can recognise: `darks/`, `flats/` and
`bias/` are shot under the same settings as the run they calibrate and are told apart by what
the owner was doing at the time, not by EXIF.

So the calibration frames are **sorted out by hand, after this skill has run**, straight out of
`lights/` and into a sibling directory:

```
6I-0011-6dii-24mm-8s-f1.8-iso3200/
  lights/jpg  lights/raw          <- what the skill writes
  darks/jpg   darks/raw           <- what the owner moves across afterwards
  _post-processing/               <- protected by its underscore (Rule 2)
```

**Re-running the skill undoes that hand-sorting, and that is expected.** `darks/` is an
ordinary directory (Rule 3): its frames are pooled with the rest, re-blocked, and land back
under `lights/` — usually as a block of their own, since a dark-frame run is itself a
fixed-interval sequence. Nothing is lost, the frames just have to be moved across again. Say
this plainly when reporting on a folder that had calibration directories in it, so the owner
knows the hand-sorting is waiting to be redone.

Never create, guess at, or move anything into `darks/`, `flats/` or `bias/` on your own
initiative. If a block looks like a set of dark frames, say so in the report and leave it in
`lights/`.

## What counts as a photo

Any photo file under the shoot folder, outside the protected names. Each photo is one basename,
which may exist as a RAW
(`.CR2`, `.CR3`, `.NEF`, `.ARW`, `.DNG`, `.RAF`, `.ORF`, `.PEF`, `.RW2`) and/or a JPEG
(`.JPG`, `.JPEG`). `IMG_0723.CR2` + `IMG_0723.JPG` is **one** photo. EXIF is read from the JPEG
when both exist — one file per pair, which is what keeps this fast.

Everything that is not a photo file stays where it is — a `.tif` stack, a screenshot, a note —
and the directory holding it survives the prune.

## Grouping

1. Read `SubSecDateTimeOriginal` (falling back to `DateTimeOriginal`) for every photo and sort by it.
2. Partition by camera body first, so two bodies shooting the same night do not interleave.
3. **Group**: three or more consecutive photos separated by a constant interval (±0.5 s tolerance —
   the camera clock jitters by ~0.01 s). This is an intervalometer run.
4. **Scattered-group**: every photo falling between groups, collected into one block. Test shots,
   framing shots, and ISO-ramp shots land here.
5. Number all blocks from the starting number, ordered by each block's **first photo's** datetime.

## Naming

A block directory name starts with a **date prefix** and a **four-digit number**:

```
6I-0001
││ └──── the block number, from the second argument, zero-padded to 4 digits
│└────── month letter:  1 A  2 B  3 C  4 D  5 E  6 F  7 G  8 H  9 I  10 J  11 K  12 L
└─────── last digit of the year: 2026 -> 6
```

So September 2026 is `6I`, August 2026 is `6H`. The prefix comes from the **shoot folder's own
name** (`2026_0818_...` -> `6H`), never from individual photos — a night crosses midnight and
the whole shoot must carry one prefix. If the folder name has no leading `YYYY_MMDD`, the
prefix falls back to the first photo's date and the run says so.

The rest of the name comes from the block's **first photo**:

| Field | EXIF | Becomes |
|---|---|---|
| camera | `Canon EOS 6D Mark II` | `6dii` |
| camera | `Canon EOS 550D` | `550d` |
| camera | `iPhone 15 Pro` | `iphone15pro` |
| camera | anything else | model with `_` for spaces, e.g. `Canon_EOS_700D` |
| focal | `18.0 mm` | `18mm` |
| shutter | `15` | `15s` (a fraction `1/200` becomes `1_200s`) |
| aperture | `3.5` / `11.0` | `f3.5` / `f11` (trailing `.0` dropped, real decimals kept) |
| iso | `1600` | `iso1600` |

```
<folder>/6I-0001-550d-18mm-15s-f3.5-iso1600/lights/jpg    # a group: the full name
<folder>/6I-0001-550d-18mm-15s-f3.5-iso1600/lights/raw
<folder>/6I-0002-550d/lights/jpg                          # a scattered-group: stops at the camera
<folder>/6I-0002-550d/lights/raw
```

A scattered-group's name **stops at the camera** — no focal length, no shutter, aperture or
ISO. Those photos vary in all of it, which is exactly why they are scattered.

Every block is **one flat directory** directly under the shoot folder — there is no
`<camera>-<focal>` parent level. Inside it, `lights/` is the one level the skill writes
(Rule 5), and only the subdirectories a block actually has are created: a JPEG-only shoot gets
no empty `lights/raw/`.

## How to run it

Run from the repo checkout (`~/life_codes/exiftool_mac`). `<folder>` is a bare shoot-folder
name, resolved under `$dest_camera_dir_base` per Rule 0:

```bash
python3 .claude/skills/organize-photo-folders/organize.py <folder> <start>            # plan only
python3 .claude/skills/organize-photo-folders/organize.py <folder> <start> --apply    # move the files
python3 .claude/skills/organize-photo-folders/organize.py <folder> <start> --apply --keep-source
python3 .claude/skills/organize-photo-folders/organize.py <folder> --prefix 6I        # override the prefix
```

Run the plan first and show the user the table. Then apply, in the same turn — being asked to
organize the folder is the request to move the files.

## Reporting back

After applying, report:

- the block table: name, type, photo count, interval, time span, destination (`<block>/lights`)
- **total wall-clock time** and **total photo count**, where a `.CR2` + `.JPG` sharing a basename
  counts as **one** photo (state the file count separately)
- verification that no photos were left outside a block and that jpg/raw counts pair up
- which post-processing trees were parked under `_dangling/`, `_post-processing/` ones included,
  and any merge collisions there. If one came out of a block, say which block — that path is the
  only record of which block it was processed from, and the block may have been renumbered since
- which directories were absorbed and removed, and any OS junk files deleted along with them
- if a directory was **kept** because it still had real content in it, say what is still inside
- if the folder had been organized before, say plainly which blocks changed name or number, and
  that the diary now names blocks that are gone — `create-diary` rebuilds it from scratch, so
  re-running it is the fix
- if any `darks/`, `flats/` or `bias/` directory was absorbed, say so plainly and name the
  blocks its frames landed in: that hand-sorting is now undone and has to be redone (Rule 5)
- anything the user may want to revisit — a group whose exposure settings are not uniform, mixed
  focal lengths inside one block, or photos with unreadable timestamps. Flag these; do not
  silently split or drop them.
