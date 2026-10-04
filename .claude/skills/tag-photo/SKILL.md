---
name: tag-photo
description: For one or more named groups in a shoot folder, make sure every file in each _Post-Processing/ (01_Astro/, 02_Landscape/, 03_Portraits/ and the block's own main one) - except .xmp and .txt - carries GPS and a taken time (DateTimeOriginal). A file that already has both is not touched. One missing either is dated off a similarly-named sibling in the same directory (its derivative chain, X.tif -> X_q6.jpg), else the last JPG in its category's _00Original/lights/JPG, else 01_Astro's; frames from a pool give +1s, +2s, ... A file with nothing to date against stops the run and asks for a reference photo. A copy of an original frame (IMG_0046.JPG, 6H-0050-..._IMG_0148.JPG) is never rewritten. Copies nothing anywhere. Use when asked to tag a group such as "tag photo 2026_0907_camera_daw_bay 6I-0011-6dii-24mm-8s-f1.8-iso3200_sagittarius".
---

# Tag photo

A stacked TIF out of Sequator carries no GPS and whatever date the stacker felt like writing, and a
Photoshop export can drop the GPS. The frames it was made from carry both. This fills the gap.

**The rules are in [`organize-photo-folders.md`](../../../organize-photo-folders.md) at the repo
root — section 6 covers this skill.** This file is how to run it.

## Ask before you run

- **No folder named?** Ask which shoot folder, then stop.
- **No group named?** Ask which group (list the block directories in the folder if that helps),
  then stop. Do not tag every group on your own initiative.

## Run it

```bash
cd ~/life_codes/exiftool_mac
python3 .claude/skills/tag-photo/tag.py 2026_0907_camera_daw_bay 6I-0011-6dii-24mm-8s-f1.8-iso3200_sagittarius
```

Several groups can follow the folder. Plan only. Read it back, then apply in the same turn:

```bash
python3 .claude/skills/tag-photo/tag.py 2026_0907_camera_daw_bay 6I-0011-6dii-24mm-8s-f1.8-iso3200_sagittarius --apply
```

| flag | what for |
|---|---|
| `--apply` | write the tags (default is plan only) |
| `--reference PATH` | date anything with no sibling and no pool frame off this photo |
| `--skip-unreferenced` | tag what can be dated, leave the rest alone |
| `--exiftool PATH` | when exiftool is not on `PATH` |

## What gets dated off what

| | category `_Post-Processing/` | main `<block>/_Post-Processing/` |
|---|---|---|
| 1 | a similarly-named **sibling** | a similarly-named **sibling** |
| 2 | last JPG in `<category>/_00Original/lights/JPG` | last JPG in `01_Astro/_00Original/lights/JPG` |
| 3 | last JPG in `01_Astro/_00Original/lights/JPG` | `--reference`, else stop and ask |
| 4 | `--reference`, else stop and ask | |

A sibling's time is copied exactly, so `X.tif`, `X_q6.jpg` and `X_q12.jpg` land on one second. Files
dated off a pool frame get +1 s, +2 s, … in filename-length order.

## When it asks for a reference photo

The run prints `NEEDS A REFERENCE PHOTO`, refuses to write, and exits non-zero. **Ask the owner
which photo those files should be dated from**, then re-run with `--reference <path> --apply`. Only
reach for `--skip-unreferenced` if the owner says to leave them alone.

## What to say when you read the plan back

- **How many files per `_Post-Processing/` are already tagged**, and which ones get written, with
  the time and where it came from (`sibling …` or `01_Astro +2s`).
- **`time only`**: the 550d records no GPS, so those files get a time and no location. Expected,
  and they will show up again on the next run.
- **Anything left alone**: copies of original frames, and anything that is not a taggable image
  (video and raw especially).

## Two things it will never do

- **Touch anything outside a `_Post-Processing/`**, or copy anything anywhere. Collecting into the
  shoot root's `_post-processing_jpg/` is `create-diary`'s job.
- **Rewrite a copy of an original**, even one missing GPS. It carries the camera's own record.
