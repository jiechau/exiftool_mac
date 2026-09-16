---
name: tag-photo
description: Stamp each _Post-Processing/ output with the GPS and capture time of the frames it was made from, then copy every one of them up into the shoot folder's root _post-processing_jpg/. A block has up to four - 01_Astro/, 02_Landscape/, 03_Portraits/ and the block's own - and each is dated off its own lights/JPG (the block's own off 00_Original/JPG), never off a sibling category or another block. Files are ordered by filename length, shortest first, and given the reference frame's time +1s, +2s, ... A directory holding work but with no frames to date it against stops the run and asks for a reference photo. A file that is only a copy of an original frame (IMG_0046.JPG, or 6H-0050-..._IMG_0148.JPG) is left alone. Reads the 6I-0010-... block names organize-photo-folders writes. Use when asked to tag a shoot folder such as "tag photo 2026_0907_camera_daw_bay".
---

# Tag photo

A stacked TIF out of Sequator carries no GPS and whatever date the stacker felt like writing. The
frames it was made from carry both. This puts them back.

**The rules are in [`organize-photo-folders.md`](../../../organize-photo-folders.md) at the repo
root — section 6 covers this skill.** This file is how to run it.

## Ask before you run

- **No folder named?** Ask which shoot folder, then stop.

## Run it

```bash
cd ~/life_codes/exiftool_mac
python3 .claude/skills/tag-photo/tag.py 2026_0907_camera_daw_bay
```

Plan only. Read it back, then apply in the same turn:

```bash
python3 .claude/skills/tag-photo/tag.py 2026_0907_camera_daw_bay --apply
```

| flag | what for |
|---|---|
| `--apply` | write the tags and copy up (default is plan only) |
| `--reference 'KEY=PATH'` | date one directory off this frame instead. Repeatable. |
| `--skip-unreferenced` | stamp what can be dated, leave the rest alone |
| `--exiftool PATH` | when exiftool is not on `PATH` |

## What gets dated off what

| directory | reference frames |
|---|---|
| `<block>/01_Astro/_Post-Processing/` | `01_Astro/lights/JPG` |
| `<block>/02_Landscape/_Post-Processing/` | `02_Landscape/lights/JPG` |
| `<block>/03_Portraits/_Post-Processing/` | `03_Portraits/lights/JPG` |
| `<block>/_Post-Processing/` | `00_Original/JPG` |

Always the **last frame by capture time** — the moment that run finished. Products then get
+1 s, +2 s, … in filename-length order, so `..._thor.jpg` comes before
`..._thor_SequatorStacking30.tif`.

## When it asks for a reference frame

A category holding work with an empty `lights/JPG` has nothing to date against, and **nothing is
borrowed** from a sibling category or another block to paper over it. The run prints a
`NEEDS A REFERENCE FRAME` block, refuses to write, and exits non-zero.

That is your cue to **ask the owner which photo it should be dated from**, then re-run with the
line the plan already printed for you:

```bash
python3 .claude/skills/tag-photo/tag.py 2026_0907_camera_daw_bay \
  --reference '6I-0011-6dii-24mm-8s-f1.8-iso3200/02_Landscape=/path/to/IMG_0105.JPG' --apply
```

The key is the directory: `<block>/<category>`, or just `<block>` for the block's own
`_Post-Processing/`. Only reach for `--skip-unreferenced` if the owner says to leave those alone.

## What to say when you read the plan back

- **Which file gets which timestamp**, per directory, and what the reference frame was.
- **`time only (no GPS on this body)`** — the 550d records no GPS, so those products get a time
  and no location. Expected, not a failure.
- **Anything left alone**: copies of original frames, and anything that is not a taggable image
  (video especially — QuickTime dates are UTC and this skill stays out of that entirely).
- **A `CLASH`** in the copy-up list: two blocks export the same filename. Nothing is overwritten;
  one of them has to be renamed by hand.
- **`_dangling/` is not empty** — parked work that belongs to no block and so cannot be tagged.

## Two things it will never do

- **Touch anything outside a `_Post-Processing/`.** Not `00_Original/`, not `lights/`, not
  `darks/`.
- **Rewrite a copy of an original.** `IMG_0046.JPG` sitting in a `_Post-Processing/` already
  carries the camera's own GPS and true timestamp; overwriting them would put a made-up record
  over a real one.

Running it twice is safe: the time is always recomputed from the reference frame, never from the
target's current tags, so the seconds cannot drift.
