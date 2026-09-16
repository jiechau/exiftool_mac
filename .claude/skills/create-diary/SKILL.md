---
name: create-diary
description: Rebuild the shoot folder's *diary/ directory (_<folder name>_diary/ by default) from scratch - every JPEG and PNG in _00info/ and _post-processing_jpg/, sorted into one capture-time stream and numbered d000010_, d000020_, ... in front of each file's own name. Those two directories are the only sources; the block directories are not read at all. The diary is emptied first, so it always mirrors the two sources exactly. Use when asked to create or rebuild the diary for a shoot folder such as "create diary for 2026_0911_camera_llm".
---

# Create diary

A contact sheet for a night: the screenshots and notes in `_00info/`, plus the finished exports
`tag-photo` collected in `_post-processing_jpg/`, in the order they were shot.

**The rules are in [`organize-photo-folders.md`](../../../organize-photo-folders.md) at the repo
root — section 6 covers this skill.** This file is how to run it.

## Ask before you run

- **No folder named?** Ask which shoot folder, then stop.

## Run it

```bash
cd ~/life_codes/exiftool_mac
python3 .claude/skills/create-diary/diary.py 2026_0911_camera_llm
```

Plan only. Read it back, then apply in the same turn:

```bash
python3 .claude/skills/create-diary/diary.py 2026_0911_camera_llm --apply
```

`--exiftool PATH` when exiftool is not on `PATH`; if it is not found the script stops and you
**ask the owner where it is** rather than guessing.

## Where the frames come from

Two directories at the shoot root, and nothing else:

| source | what it holds |
|---|---|
| `_00info/` | the night's screenshots, sky charts, planning notes, phone frames |
| `_post-processing_jpg/` | the finished exports `tag-photo` copied up out of the blocks |

**The blocks are not read.** Not `00_Original/`, not the categories' `lights/`, not a block's own
`_Post-Processing/`. A frame still sitting in a block has not been chosen for the strip yet; the
way to put it there is to export it, let `tag-photo` collect it, or drop it in `_00info/`.

Both folders are walked to any depth. Photos are **JPEG and PNG** — `_00info/` is mostly
screenshots. A `.tif` is reported and left out; they run to hundreds of megabytes and a diary is
for flicking through.

Order is one flat stream by capture time — EXIF first, then the timestamp in the filename, then
the file's mtime, so a screenshot named `2026-09-11 06.01.44.png` sits where it belongs. Each copy
is `d000010_` … in front of **the file's own name**, nothing else added.

## What to say when you read the plan back

- **How many frames** the diary will hold, split by source, and how many are being removed first.
  The diary is emptied and rebuilt every run; all of it is copies, so nothing is at risk.
- **Anything with no timestamp**, which is placed last rather than dropped.
- **Anything that is not a JPEG or PNG** — a `.tif` export in particular. It stays where it is and
  is only reported, so the owner knows it is not in the strip.
- **A source directory that is not there.** One missing is a warning and the run continues on the
  other; both missing stops the run.

## Two things that catch people out

- **A frame dropped straight into the diary is gone on the next run.** The diary holds copies
  only. A photo that must be in the strip belongs in `_00info/` or `_post-processing_jpg/`.
- **Organizing or re-numbering blocks does not change the diary.** The blocks are not a source any
  more, so a re-organize is invisible here — what changes the strip is what lands in those two
  directories.
