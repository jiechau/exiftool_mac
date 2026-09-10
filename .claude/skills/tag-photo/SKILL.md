---
name: tag-photo
description: Stamp each group's _post-processing/ output with that group's own GPS and capture time, read from the last light frame of the run, then copy every group's _post-processing/ up into the shoot folder's root _post-processing/. Files are ordered by filename length, shortest first, and given the reference frame's time +1s, +2s, ... A file that is only a copy of an original frame (IMG_0046.JPG, or 6H-0050-..._IMG_0148.JPG) is left alone. Reads the 6I-0001-... block names organize-photo-folders writes. Use when asked to tag a shoot folder such as "tag photo 2026_0818_camera_jilong_dwl_parking".
---

# Tag photo

A stacked TIF out of Sequator carries no EXIF worth having: no GPS, and whatever date the
stacker felt like writing. The frames it was made from carry both. This skill puts the place
and the time back onto the products, taking them from the run that produced them, so a night's
finished work sorts and maps alongside the frames it came from.

Run this **after** `organize-photo-folders`. It reads the block directories that skill
produces, and stops if there are none.

## Rule 0 — where the photos are

This skill lives in the `exiftool_mac` repo; the photos do not. They sit in `camera_latest/` on
the removable `UltraFit256` drive, at the path `config/config_vars.txt` calls
**`$dest_camera_dir_base`** — the same variable `go.sh` syncs that library from. The script reads
that file itself, so a shoot folder is named, never pathed:

```
tag photo 2026_0818_camera_jilong_dwl_parking
```

An absolute path, or a relative one that exists from the current directory, is still taken as
given. `$CAMERA_LATEST_DIR` overrides the config var for a one-off run against another drive. A
bare name is resolved only after `camera_latest/it_exists.txt` is confirmed, so an unmounted
drive stops the run instead of presenting an empty directory as a shoot folder.
`organize-photo-folders` and `create-diary` resolve folders the same way.

## Rule 1 — a folder argument is required

The skill needs one folder, e.g. "tag photo `2026_0818_camera_jilong_dwl_parking`".

**If no folder is named, stop and ask the user which folder to use.** Do not guess, do not scan
for candidates, do not pick the newest directory. Ask, then stop.

## Rule 2 — the folder must exist, be organized, and `exiftool` must run

Check all three before doing anything else. If the folder does not exist, stop and say so — do
not create it and do not look for a similarly-named folder.

**`exiftool` must exist and answer `exiftool -ver`** (`/opt/homebrew/bin/exiftool` is the
fallback if it is not on PATH). Every tag written and every tag read goes through it.

**The folder must be organized.** That is judged exactly one way: it holds at least one
directory whose name matches a block, `<prefix>-<nnnn>-` — `6H-0038-…`, `6I-0011-…`. A card dump
or a hand-made tree is not a block, so a folder holding none has not been organized yet. Say so
and stop — **do not organize it on your own initiative.**

A folder that is organized but holds only scattered-groups stops too, with a different message:
there is nothing to tag.

## Rule 3 — only groups, and only their `_post-processing/`

**Groups only.** A group carries its settings in its name and so is a real run with an end:
`6H-0050-6dii-24mm-8s-f2.8-iso800`. A scattered-group stops at the camera (`6H-0036-6dii`) —
the night's test and framing shots, no run and no run's end to date anything against. It is
reported and skipped, the same call `create-diary` makes.

The only files this skill ever modifies are the ones inside a **group's own
`_post-processing/`**. Not `lights/`, not `darks/`, `flats/` or `bias/`, not `00info/`, not the
diary, not `_dangling/`. Those are read for their tags at most, and never written.

## Rule 4 — a copy of an original is not post-processing output

A `_post-processing/` folder usually holds one frame the owner pulled out of the run to work
on. It is already a photograph, with the camera's own GPS and its own true timestamp, and
overwriting those would replace a real record with a made-up one. **It is left completely
alone.**

It is recognised two ways, and either is enough:

- **The block still holds a file by that name.** The entry name is matched against every
  filename in the block outside `_post-processing/` — `lights/` and the hand-made `darks/`,
  `flats/`, `bias/` — first as-is, then with a `<block>_` prefix stripped, which is how the
  owner labels a frame they pulled out. `6H-0050-…_IMG_0148.JPG` strips to `IMG_0148.JPG`,
  which is sitting in that block's `lights/jpg/`. That settles it.
- **The bare name is plainly a camera's own**: `IMG_0046`, `_MG_1234`, `DSC01234`, or the
  iPhone's `2026-08-18 22.35.21`. This is the fallback for when the original is no longer in
  the block.

Both forms occur in the archive — `2026_0818` uses the prefixed form, `2026_0907` the bare one.

**Only `.TIF`/`.TIFF`/`.JPG`/`.JPEG`/`.PNG` are ever written.** Anything else in
`_post-processing/` is reported and left alone. Video is deliberately out of scope: QuickTime
stores dates in UTC and needs `-api QuickTimeUTC`, and this skill stays out of that rather than
getting it subtly wrong.

## What it does

### 1. The reference frame

For each group, the **last light frame of the run** — the newest `lights/jpg/` frame by capture
time, with the filename breaking a tie, the same ordering `create-diary` uses. That frame is the
moment the run finished, which is where its products belong.

Its `SubSecDateTimeOriginal` / `DateTimeOriginal` / `CreateDate` gives the time, truncated to
the whole second, and its GPS gives the place.

**A body that records no GPS gives no GPS.** The 550d does not; the 6dii and the iPhone do. When
the reference frame has none, the products get the time only, and the run says so per block.
Nothing is borrowed from another block or another night to fill the gap — an invented location
is worse than none.

### 2. Order by filename length, then hand out the seconds

The products are sorted by **length of filename, shortest first**, ties broken by name so a
`.jpg` and its equally-named `.tif` always land in the same order.

That is not arbitrary. The finished piece gets the plain name and every variant hangs a suffix
off it, so shortest-first puts the keeper in front of its own variants:

```
6H-0040-…-iso200_thor.jpg                    +1s
6H-0040-…-iso200_thor.tif                    +2s
6H-0040-…-iso200_thor_milkyway.png           +3s
6H-0040-…-iso200_thor_milkyway_star.png      +4s
6H-0040-…-iso200_thor_SequatorStacking30.tif +5s
```

Each file is then written with `-AllDates` (`DateTimeOriginal`, `CreateDate`, `ModifyDate`) at
the reference time **plus one second per file** — first `+1s`, second `+2s`, and so on, so the
products sit in that order right after the run they came from. `SubSecTimeOriginal` is cleared,
so the whole-second order the plan lays out is the order anything reading the files sees. GPS is
copied straight across with `-tagsFromFile … -gps:all`.

`-overwrite_original` is used, per repo convention: no `_original` litter is left beside the
products.

**This is idempotent by construction.** The time is always recomputed as *last light frame + N*,
read fresh from `lights/` on every run, never from the target's current tags. Run it twice and
the second run writes exactly what the first did — the seconds cannot drift, however many times
it is re-run.

### 3. Copy up to the root

Every file in each group's `_post-processing/` — the stamped products **and** the original-copies
that were left alone — is then copied into the shoot folder's root `_post-processing/`, which is
created if it is not there.

**The copy is additive. Nothing in the root is ever deleted.** That folder is hand-curated —
CLAUDE.md calls it "never touched" — so a file in it that no block accounts for stays exactly
where it is. This is the opposite of `create-diary`, which empties its directory first, and the
difference is deliberate: the diary holds only copies it can rebuild, the root
`_post-processing/` may hold the owner's own work.

A product this run stamped is **always** re-copied, because its bytes just changed. A file the
run left untouched is copied only if the root lacks it or holds something different.

Two blocks exporting the **same name** with different content is a clash: it is reported and
**not** copied, so neither silently overwrites the other. Rename one and re-run. Bare names like
`IMG_0046.JPG` are what make this possible, which is a reason to prefer the `<block>_…` form.

## How to run it

Run from the repo checkout (`~/life_codes/exiftool_mac`). `<folder>` is a bare shoot-folder
name, resolved under `$dest_camera_dir_base` per Rule 0:

```bash
python3 .claude/skills/tag-photo/tag.py <folder>            # plan only
python3 .claude/skills/tag-photo/tag.py <folder> --apply    # write the tags, copy up
```

Run the plan first and show the user the table. Then apply, in the same turn — being asked to
tag the folder is the request to write it. The run leaves no state file behind.

**Say plainly before applying that `--apply` rewrites EXIF in place and there is no undo.** The
products are derived files the owner can re-export, and nothing in `lights/` is touched, so the
cost of a wrong run is a re-export rather than a lost photograph — but it is still a rewrite.
A large TIF is rewritten whole by exiftool, so a multi-gigabyte stack needs its own size free on
the drive while it is written.

## Reporting back

After applying, report:

- per group: the reference frame, its time, whether it carried GPS, and each product with the
  offset and final timestamp it was given
- the files left alone, with the reason — a copy of an original frame, or not a taggable image
- the scattered-groups skipped, by name — they are skipped by design, so say so rather than
  letting them go unmentioned
- any group whose reference frame carried **no GPS**, naming the body, so the owner knows the
  location is missing rather than wrong
- what the copy-up did: how many files landed in the root `_post-processing/`, and how many were
  already there unchanged
- any name clash between two blocks, which is the one case a file is not copied up
- anything worth revisiting — a group with a `_post-processing/` but no `lights/jpg/` to date it
  against, a group whose frames have no readable timestamp, or a `_dangling/` directory holding
  post-processing work that `organize-photo-folders` parked and nobody has moved back into a
  block yet. Flag these; do not silently drop them.
