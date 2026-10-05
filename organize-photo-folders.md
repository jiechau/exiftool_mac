# organize-photo-folders — the rules

The specification for the three `camera_latest` skills. `organize-photo-folders` writes the
layout described here; `create-diary` and `tag-photo` read it. Where a `SKILL.md` and this file
disagree, this file is right.

The code that enforces it: `.claude/skills/_shared/camera_lib.py` (the shared contract),
`.claude/skills/organize-photo-folders/organize.py`, `create-diary/diary.py`, `tag-photo/tag.py`.

`organize-photo-folders` is the **first step** on a card dump. Everything after it — filing frames
into categories, stacking, exporting — is hand work, and the skill's job is to hand that work a
known shape to start from.

---

## 1. Preconditions

Checked in this order. Any one failing stops the run.

**exiftool.** Looked for as `--exiftool PATH`, then `$EXIFTOOL`, then on `PATH`, then the usual
install locations for the platform (macOS: `/opt/homebrew/bin`, `/usr/local/bin`; Windows:
`C:\Windows`, `C:\Program Files\exiftool`, `C:\exiftool`). A candidate only counts if
`exiftool -ver` actually answers. **If none is found the run stops and the agent asks the owner
where it is**, then re-runs with `--exiftool <path>`. It is never guessed at or installed.

**The base directory.** `$CAMERA_LATEST_DIR` if set, on either platform. Otherwise, out of
`config/config_vars.txt`:

| platform | key |
|---|---|
| macOS (and anything not Windows) | `dest_camera_dir_base` |
| Windows 11 (`os.name == 'nt'`) | `dest_camera_dir_copy` |

These are two different machines' paths to two different drives, which is why there are two keys.
It is not the "two keys naming one folder" that `CLAUDE.md` warns about.

**The sentinel.** `it_exists.txt` must be a file at the base, **on both platforms**. On the Mac it
is the repo's usual proof that `UltraFit256` is actually mounted — an unmounted mount point still
resolves as an empty directory, and these scripts move and delete files. On Windows the drive does
not go away, but the rule is kept identical so there is one rule to remember, and it still catches
a mistyped base.

**The folder.** A shoot folder is **named, not pathed**: `2026_0907_camera_daw_bay`. An absolute
path, or a relative one that exists from the current directory, is taken as given.

**The arguments.** Both are required and neither is ever guessed: the folder name, and the
starting block number. Missing either means ask, then stop.

```
organize 2026_0907_camera_daw_bay 10
```

---

## 2. Grouping

Every photo under the shoot folder, from every source directory at any depth, is pooled and
sorted into **one** capture-time stream. There is no per-camera pass: two bodies shooting the same
night interleave in real time, and the block numbers follow the night, not the equipment.

A `.CR2` and a `.JPG` sharing a basename are **one photo**. EXIF is read from the `.JPG` — same
shooting data, far faster — in **one** batched `exiftool` call, never one call per file. The time
is `SubSecDateTimeOriginal`, falling back to `DateTimeOriginal`; the sub-second part is what makes
a fixed interval detectable at all, since 8–30 s exposures are only seconds apart on the clock.

The stream is then cut into two kinds of block:

**Set group** — at least **3** consecutive frames that share the whole shooting signature
(`camera + focal + shutter + aperture + ISO`) **and** sit at a constant interval, within 0.5 s.
Both tests matter. The signature is what makes the directory name true of every frame inside it;
the interval is what says an intervalometer was running rather than someone firing by hand at the
same settings. Every delta is compared against the run's **first** delta, not its predecessor, so
a slow drift cannot creep a run along one jittery frame at a time.

**Scattered group** — every stretch between two set groups, and before the first and after the
last. One scattered group per stretch. It may mix bodies and settings; that is what makes it
scattered.

---

## 3. Names

```
6I-0010-6dii-24mm-8s-f1.8-iso3200
││ └──── block number: the second argument, +1 per block in time order, zero-padded to 4
│└────── month letter:  1 A  2 B  3 C  4 D  5 E  6 F  7 G  8 H  9 I  10 J  11 K  12 L
└─────── last digit of the year: 2026 -> 6
```

The date prefix comes from the **shoot folder's own name** (`YYYY_MMDD_...`), never from a photo,
because a night crossing midnight must keep one prefix. A folder whose name carries no date falls
back to the first photo's date, with a warning.

**Set group:** `<prefix>-<nnnn>-<camera>-<focal>-<shutter>-<aperture>-<iso>`. Every frame shares
these by construction, so the first frame's values are the group's.

**Scattered group:** `<prefix>-<nnnn>`, then `-<camera>` **only if every frame is the same body**,
then `-<focal>` **only if every frame is also the same focal length**, stopping at the first field
that differs. Settings never appear: a scattered group has none to speak of.

| what it holds | name |
|---|---|
| one body, one focal | `6I-0012-6dii-24mm` |
| one body, mixed focal | `6I-0014-550d` |
| two bodies | `6I-0015` |

Formats: focal `24mm`; shutter `8s`, or `1_200s` for `1/200`; aperture `f1.8`, `f11`; ISO
`iso3200`. Camera: `Canon EOS 6D Mark II` → `6dii`, `Canon EOS 550D` → `550d`, anything else joins
on underscores (`Canon_EOS_700D`). A body that shoots here often enough to be talked about by name
belongs in `CAMERA_SLUGS`.

**A hand-added suffix is valid**: `6I-0013-6dii-24mm-8s-f1.8-iso6400_thor` is still a group, and
every skill recognises it. It is **not** carried across a re-organize — blocks are renumbered and
names re-derived from EXIF, so re-add it by hand afterwards.

---

## 4. The tree a block gets

A set group gets the full working tree:

```
6I-0017-6dii-24mm-8s-f1.8-iso6400/
└── 01_Astro/
    ├── _00Original/
    │   └── lights/               <- the ONLY thing this skill fills
    │       ├── RAW/              every .CR2 in the block
    │       └── JPG/              every .JPG in the block
    ├── _CameraAll/
    ├── _CameraRaw0/
    ├── _CameraRaw1/
    └── _Post-Processing/
```

A scattered group gets the **minimum**: the same tree without `_CameraAll/`, `_CameraRaw0/` and
`_CameraRaw1/`. Scattered groups are stray and test frames — they get somewhere to put the frames
and an export, but they are not what gets stacked, so they get no stacking directories.

**No block gets an `_00info/`** (dropped 2026-10-04) — it was created in every block and stayed
empty in nearly all of them. Notes about the night go in the shoot root's `_00info/`, which is the
one `create-diary` reads. A block-level `_00info/` made by hand is a `_` name below the root, so a
re-run parks it under `_dangling/` like any other hand work.

Notes that matter:

- **The pool is the only directory the skill fills**, and it sits *inside a category*:
  `01_Astro/_00Original/lights/{RAW,JPG}`, not at the block root.
- **Nothing is created speculatively.** `02_Landscape/`, `03_Portraits/`, `04_tests/` and every
  `darks/` used to be scaffolded empty alongside these, and went unused shoot after shoot — a
  finished folder carried hundreds of empty directories that said nothing about the work in it.
  They are **not created any more**. Make one by hand when a shoot actually needs it; a
  `_00Original/` inside it is read like any other pool (rule 3 below).
- Both `lights/RAW` and `lights/JPG` exist even when a block is JPEG-only. The template is uniform
  so a block looks the same whatever it happened to hold.
- **`RAW` and `JPG` are upper-case.** macOS would forgive `raw`; ext4 on the NAS will not.
- **`_00Original` is the spelling written.** Two older ones are still *read* so an un-migrated
  folder converts on its first re-run rather than having every photo parked: `_00_Original` (the
  hand-made spelling in `2026_0907` and `2026_0916`) and the flat block-root `00_Original` this
  skill itself wrote until 2026-09-25. See `camera_lib.ORIGINAL_ALIASES`.
- **There is no `_post-processing_jpg/` in a block.** There is one per *shoot*, at the shoot root,
  and `create-diary` rebuilds it from the blocks on every run. A block's exports go in its
  category's `_Post-Processing/`, so a per-block copy of the shoot's collector was a second name
  for a place that already existed — and it was empty in every block on the drive. Dropped from
  the template on 2026-09-25.

---

## 5. Traversal, re-organize, and `_dangling/`

Re-running on an organized folder is normal and is the point — that is how a shoot gets renumbered
after frames are added or removed. One walk decides what every directory is, and the same rules
apply in plan mode and under `--apply`, so the plan is what actually happens.

In order:

1. **At the shoot root, every `_` and `.` name is the owner's staging** — `_dangling/`,
   `_post-processing_jpg/`, `_00info/`, `_diary/`, `_tmp/` — and so are `00info/` and `*diary/`.
   Never read, never moved. **The underscore keeps its old meaning at the root: it protects.**
   Below the root it means the opposite (rule 4), because down there it is work inside a block.
2. **A `.` name at any depth** is the filesystem's — `.Trashes`, `.fseventsd`. Skipped, never
   parked.
3. **A pool, and the path down to one, is read.** A pool is a directory named `_00Original`,
   `_00_Original` or `00_Original`, at any depth. This exemption is what makes the layout work:
   `_00Original` is itself a `_` name and would otherwise fall to rule 4, and `01_Astro/` would
   fall to rule 5. Everything below a pool is frames — `lights/`, `darks/`, and the flat `RAW/`
   and `JPG/` of the older layout. **This is the only thing re-read out of an organized block.**
4. **A `_` name below the root** is hand-curated work sitting inside a block that is about to be
   renumbered — `_CameraRaw0/`, `_CameraAll/`, `_Post-Processing/`, `_00info/`. **Parked under
   `_dangling/<its original path>/`.** An underscore-less `post-processing*/` is parked too.
5. **Inside an already-organized block** — one with a pool under it anywhere — everything that
   does not lead to a pool is parked as well, whatever it is called: a `02_Landscape/` holding a
   filed `_Post-Processing/`, an `04_tests/` full of frames. Filing a frame under `02_Landscape`
   is a decision, and re-pooling it would silently undo that decision.
6. **Anything else** is a card dump, an old hand-made tree, a stray folder: walked into, and its
   photos pooled.

Rule 5 is deliberately **not** applied at the shoot root. At the root a pool exists as soon as one
block has been organized, and rule 5 would then park every un-organized card dump sitting beside
it — exactly the thing that is there to be absorbed.

Two things soften rules 4 and 5:

- **An empty directory is not parked, it is removed.** The scaffolding a previous run created is
  empty by design; parking it would fill `_dangling/` with hundreds of empty directories on every
  re-run. "Empty" means no file a person made — OS litter does not count as content. **This
  overrides rule 3 as well**: an empty pool is not a photo source, it is last run's scaffolding.
  Without that, the emptied `00_Original/` of a block just converted to the new layout would
  match the alias forever and sit there through every future run.
- **The original path is preserved in `_dangling/`**, because the block's number is about to
  change and the path is the only record of which block the work came from.

**`darks/` is pooled with the lights.** A dark frame sits under the pool, so rule 3 reads it, and
it carries the same timestamp and settings as the lights around it — so it is re-blocked by time
like any other frame and comes out filed as a light. The lights/darks split is therefore *not*
preserved across a re-run: re-running a block whose darks matter means filing them again
afterwards. Decided this way on 2026-09-25, over the alternative of carrying `darks/` through
untouched, because the pool is meant to be one undifferentiated stream of what the camera shot.

A source directory left holding nothing but OS litter (`.DS_Store`, `Thumbs.db`, `desktop.ini`,
`._*`) is deleted. Anything a person made saves it, and it is reported instead.

Inside a block this run just wrote, the sweep removes **only a directory the photos came out of**
— a source directory, or a parent of one. The block's own scaffolding is empty on purpose and is
never touched, and scaffolding is never a source, so the two cannot be confused.

That distinction is needed because **a block name can be both old and new in the same run**. A
scattered-group's name carries no settings, so `6I-0098-6dii-14mm` one run is
`6I-0098-6dii-14mm` the next with different frames in it; a renumber then lands a new block on an
old block's name, and the old block's emptied pool sits *inside* a directory the run just wrote.
Guarding the whole block by name would leave that pool there permanently — which is how
`2026_0925_camera_neihu_ccd_roof` ended up with an empty `6I-0098-6dii-14mm/00_Original/` on
2026-09-25.

**Never** deletes a photo, renames an original, or rewrites an original's EXIF.

---

## 6. What the other two skills read

### create-diary

Takes a shoot folder name, resolved under this machine's base (`$dest_camera_dir_copy` on Windows,
`$dest_camera_dir_base` on macOS). Every run is a **rebuild from scratch**, first or tenth alike:

1. **Delete** `_diary/` (the old spelling), `_<folder>_diary/` and `_post-processing_jpg/` at the
   shoot root. All three are copies and all three are written again below. Anything hand-placed
   in `_post-processing_jpg/` that is not also in a block's `_Post-Processing/` is **gone** — the
   plan lists each such file under `!!` so it can be moved into a block first.
2. **Collect** from every `_Post-Processing/` in every block the files meant for looking at: an
   upper-case **`.JPG`** (a camera frame the owner pulled out), a **`*_q6.jpg`** export, or a
   **`.png`** in either case (a screen grab, e.g. a field-of-view diagram; added 2026-10-06). The
   directory keeps its `_jpg` name all the same. Not `.psd`, `.tif`, `.xmp`, raw, and not the full-size `*_q12.jpg`.
3. **Check** each of those carries GPS and `DateTimeOriginal`. A group holding one that does not is
   run through **`tag-photo` first** — the whole group, by its rules below — so the copies carry the
   tags. If tag-photo would need a reference photo, the diary stops and says which group.
4. **Copy** them flat into `_post-processing_jpg/`. Two blocks exporting the same filename is a
   `CLASH`: the first is kept, the second reported.
5. **Sort** everything under `_00info/` (any file, any depth) plus everything in
   `_post-processing_jpg/` into one flat stream by capture time — EXIF, then the timestamp in the
   filename, then `FileModifyDate` — ties on filename, undated last. Number it `d000010_`,
   `d000020_`, … **in front of the file's own name**; the gap of 10 lets a frame be slipped in by
   hand.
6. **Write** that stream into **`_<shoot folder name>_diary/`** — `_2026_0907_camera_daw_bay_diary/`
   — named after the shoot so it still says where it came from once copied elsewhere.

A `*diary/` under any other name is left alone and reported.

### tag-photo

Takes a shoot folder **and one or more group names** —
`tag.py 2026_0907_camera_daw_bay 6I-0011-6dii-24mm-8s-f1.8-iso3200_sagittarius`. A group can hold
several `_Post-Processing/` directories (`camera_lib.postproc_dirs()`): one per category
(`01_Astro/`, `02_Landscape/`, `03_Portraits/`) and the block's own at its root, the *main* one.

**Every file in each of them except `.xmp` and `.txt` must carry GPS and `DateTimeOriginal`.** One
that already has both is not touched. One missing either is given both, dated off the first of:

| | category `_Post-Processing/` | main `_Post-Processing/` |
|---|---|---|
| 1 | a **sibling** with a similar name | a **sibling** with a similar name |
| 2 | the last JPG in the category's `_00Original/lights/JPG` | the last JPG in `01_Astro/_00Original/lights/JPG` |
| 3 | the last JPG in `01_Astro/_00Original/lights/JPG` | `--reference PATH` |
| 4 | `--reference PATH` | stop and ask |

**A sibling** is the derivative chain in the same directory: a variant is named by hanging a suffix
off what it came from (`X.tif` → `X_LRC.tif` → `X_LRC_q6.jpg`), so a file whose stem is a prefix of
this one's ending at `_` `-` `(` or a space — or the other way round — is the same picture. Longest
shared stem wins, ancestor over descendant on a tie. A loose common prefix is deliberately not
enough: every file in a block shares `6I-0011-…_01Astro_`. A sibling qualifies when it has both tags
already, is a copy of an original with a real date, or was planned a moment earlier in the same run
— files are planned shortest name first, so a whole chain lands on one time.

A sibling's time is copied exactly. **A pool frame is the last by capture time**, and files dated
off it get its time **+1 s, +2 s, …** in filename-length order, so two unrelated stacks do not share
a second. `--reference` is only reached when there is no frame at all; without it the run stops,
lists the files, and asks which photo to use (`--skip-unreferenced` leaves them alone instead).

A file that is only a **copy of an original frame** (`IMG_0046.JPG`, `6H-0050-..._IMG_0148.JPG`,
`<block>_01Astro_IMG_0046.JPG`) is never rewritten, even missing GPS — it carries the camera's own
record. A body with no GPS (the 550d) yields time only, and those files are re-stamped with the same
values on every run. Video and raw are reported, never written.

**Nothing is copied anywhere** — collecting into `_post-processing_jpg/` is create-diary's job
since 2026-10-01. Idempotent: a file tagged once has both tags and is left alone the next time.

---

## 7. Working on this

All three are **plan-first**: run with no `--apply`, show the plan, then `--apply` in the same
turn. No skill guesses an argument.

```
python3 .claude/skills/organize-photo-folders/organize.py <folder> <start> [--apply]
python3 .claude/skills/create-diary/diary.py              <folder>         [--apply]
python3 .claude/skills/tag-photo/tag.py                   <folder> <group>... [--apply]
```

All three take `--exiftool PATH`. `organize.py` also takes `--prefix` and `--keep-source`;
`tag.py` takes `--reference PATH` and `--skip-unreferenced`.

To try a change without risking the drive, copy a shoot folder somewhere scratch, `touch
it_exists.txt` beside it, and point `$CAMERA_LATEST_DIR` at that directory.

**The photos are not in this repo.** The skills live here, the shoot folders live on the removable
drive. Don't put documentation back on the drive — it moved here on 2026-09-09 so the drive stays
pure storage.
