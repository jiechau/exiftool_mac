---
name: create-diary
description: Rebuild the shoot folder's *diary/ directory (_diary/ by default) from scratch - every photo in 00info/ and the first, middle and last JPEG of each group, named <block>_<filename> and numbered d000010_, d000020_, ... in capture order, with each group's three frames kept together. Frames come from the categories the owner has filed into (01_Astro/lights/JPG, 02_Landscape/lights/JPG, 03_Portraits/lights/JPG) merged into one capture-time stream, falling back to 00_Original/JPG for a block nothing has been filed into yet. darks/ and RAW/ never reach the strip. Scattered-groups are reported and left out. The diary is emptied first, so it always mirrors 00info/ and the blocks exactly. Reads the 6I-0010-... block names organize-photo-folders writes. Use when asked to create or rebuild the diary for a shoot folder such as "create diary for 2026_0907_camera_daw_bay".
---

# Create diary

A contact sheet for a night: everything the owner put in `00info/`, plus three frames from each
group, in the order they were shot.

**The rules are in [`organize-photo-folders.md`](../../../organize-photo-folders.md) at the repo
root — section 6 covers this skill.** This file is how to run it.

## Ask before you run

- **No folder named?** Ask which shoot folder, then stop.

## Run it

```bash
cd ~/life_codes/exiftool_mac
python3 .claude/skills/create-diary/diary.py 2026_0907_camera_daw_bay
```

Plan only. Read it back, then apply in the same turn:

```bash
python3 .claude/skills/create-diary/diary.py 2026_0907_camera_daw_bay --apply
```

`--exiftool PATH` when exiftool is not on `PATH`; if it is not found the script stops and you
**ask the owner where it is** rather than guessing.

## Where the frames come from

Per block, in this order:

1. `01_Astro/lights/JPG`, `02_Landscape/lights/JPG`, `03_Portraits/lights/JPG` — whichever the
   owner has filed into, **merged and re-sorted by capture time**, so a block worked across two
   categories still reads as one block. The plan's `FROM` column names them.
2. `00_Original/JPG` — the fall-back, used when nothing has been filed yet. That is every block
   the moment `organize-photo-folders` finishes, so a freshly-organized folder still gets a diary.
   The plan says which blocks fell back; mention it, because filing frames will change the strip.

`darks/` never reaches the strip, and neither does `RAW/`, anywhere. A block still in the
pre-`00_Original` layout is reported and skipped — it wants re-organizing first.

## What to say when you read the plan back

- **How many frames** the diary will hold, and how many are being removed first. The diary is
  emptied and rebuilt every run; all of it is copies, so nothing is at risk.
- **Which blocks fell back to `00_Original/JPG`** — see above.
- **The scattered-groups left out**, by name and frame count. They are excluded by design, not by
  accident, and saying so is the whole point of the line.
- **Anything in `00info/` that is not a photo.** It stays where it is and is only reported.

## Two things that catch people out

- **A frame dropped straight into the diary is gone on the next run.** The diary holds copies
  only. A photo that must be in the strip belongs in `00info/`.
- **A test frame worth keeping belongs in `00info/` too.** Scattered-groups are not copied
  anywhere, so a good framing shot sitting in one will never appear.
