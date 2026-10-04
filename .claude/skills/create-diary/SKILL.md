---
name: create-diary
description: Rebuild a shoot folder's _post-processing_jpg/ and _<folder name>_diary/ from scratch. Deletes _diary/, _<folder>_diary/ and _post-processing_jpg/ first; collects every upper-case .JPG and *_q6.jpg from every block's _Post-Processing/ (no .psd .tif .xmp raw or *_q12.jpg); runs tag-photo on any group whose picks lack GPS or taken time; copies the picks into _post-processing_jpg/; then sorts everything in _00info/ plus _post-processing_jpg/ into one capture-time stream numbered d000010_, d000020_, ... in front of each file's own name. Use when asked to create or rebuild the diary for a shoot folder such as "create diary for 2026_0907_camera_daw_bay".
---

# Create diary

A contact sheet for a night: everything in `_00info/`, plus the exports out of every block's
`_Post-Processing/`, in the order they were shot.

**The rules are in [`organize-photo-folders.md`](../../../organize-photo-folders.md) at the repo
root — section 6 covers this skill.** This file is how to run it.

## Ask before you run

- **No folder named?** Ask which shoot folder, then stop.

## Run it

```bash
cd ~/life_codes/exiftool_mac
python3 .claude/skills/create-diary/diary.py 2026_0907_camera_daw_bay
```

The name is looked up under `$dest_camera_dir_copy` on Windows and `$dest_camera_dir_base` on macOS.
Plan only. Read it back, then apply in the same turn:

```bash
python3 .claude/skills/create-diary/diary.py 2026_0907_camera_daw_bay --apply
```

`--exiftool PATH` when exiftool is not on `PATH`; if it is not found the script stops and you
**ask the owner where it is** rather than guessing.

## What a run does

1. **Deletes** `_diary/`, `_<folder>_diary/` and `_post-processing_jpg/` at the shoot root.
2. **Picks** every `.JPG` (upper-case extension) and `*_q6.jpg` in every block's
   `_Post-Processing/`.
3. **Tags first**: any group with a pick missing GPS or taken time goes through `tag-photo`'s
   planner, and its plan is printed under `TAG FIRST`.
4. **Copies** the picks flat into `_post-processing_jpg/`.
5. **Sorts** `_00info/` (every file, any depth) plus `_post-processing_jpg/` by capture time and
   numbers them `d000010_…`.
6. **Writes** them into `_<folder>_diary/`.

## What to say when you read the plan back

- **The `!!` list under DELETE** — files in `_post-processing_jpg/` that no block's
  `_Post-Processing/` holds. **They are deleted by `--apply` and not rebuilt.** Say so plainly
  and ask before applying if the list is not empty; the owner may want to move them into a block
  or `_00info/` first.
- **What `TAG FIRST` will write**, as for tag-photo: which files, which time, from what.
- **Any `note: … will still lack GPS`** — a copy of an original from a body with no GPS. Expected.
- **Any `CLASH`** — two blocks export the same filename; only the first is copied.
- **How many files the diary will hold**, split between `_00info/` and `_post-processing_jpg/`.

If it prints `NEEDS A REFERENCE PHOTO` it refuses to write: ask which photo to use, run
`tag-photo <folder> <group> --reference <path> --apply` for that group, then run this again.
