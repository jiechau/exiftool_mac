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
├── _00info/
├── _Post-Processing/
│
├── 00_Original/                  <- the ONLY thing this skill fills
│   ├── RAW/                      every .CR2 in the block
│   └── JPG/                      every .JPG in the block
│
├── 01_Astro/
│   ├── _Post-Processing/  _CameraRaw0/  _CameraRaw1/
│   ├── lights/{RAW,JPG}
│   └── darks/{RAW,JPG}
│
├── 02_Landscape/
│   ├── _Post-Processing/
│   ├── lights/{RAW,JPG}
│   └── darks/{RAW,JPG}
│
├── 03_Portraits/
│   ├── _Post-Processing/  _CameraRaw0/
│   └── lights/{RAW,JPG}
│
└── 04_tests/{RAW,JPG}
```

A scattered group gets the **minimum**: `_00info/`, `_Post-Processing/`, `00_Original/{RAW,JPG}`.
Scattered groups are stray and test frames; they get somewhere to put a note and somewhere to put
an export, and nothing else.

Notes that matter:

- **`00_Original/` is the only directory the skill fills.** Everything else is created empty for
  the owner to file into by hand, and is never read back as a photo source.
- Both `00_Original/RAW` and `00_Original/JPG` exist even when a block is JPEG-only. The template
  is uniform so a block looks the same whatever it happened to hold.
- **`RAW` and `JPG` are upper-case.** macOS would forgive `raw`; ext4 on the NAS will not.
- The shape differs per category on purpose: astro stacks in two Camera Raw passes and needs
  darks, landscape needs darks but not the raw passes, portraits needs one raw pass and no darks,
  and `04_tests/` is a dumping ground with no `lights/`.

---

## 5. Traversal, re-organize, and `_dangling/`

Re-running on an organized folder is normal and is the point — that is how a shoot gets renumbered
after frames are added or removed. One walk decides what every directory is, and the same rules
apply in plan mode and under `--apply`, so the plan is what actually happens.

In order:

1. **At the shoot root, every `_` and `.` name is the owner's staging** — `_dangling/`,
   `_post-processing_jpg/`, `_00info/`, `_diary/`, `_tmp/` — and so are `00info/` and `*diary/`.
   Never read, never moved. **The underscore keeps its old meaning at the root: it protects.**
   Below the root it means the opposite (rule 3), because down there it is work inside a block.
2. **A `.` name at any depth** is the filesystem's — `.Trashes`, `.fseventsd`. Skipped, never
   parked.
3. **A `_` name below the root** is hand-curated work sitting inside a block that is about to be
   renumbered — `_CameraRaw0/`, `_Post-Processing/`, `_00info/`. **Parked under
   `_dangling/<its original path>/`.** An underscore-less `post-processing*/` is parked too.
4. **Inside an already-organized block** — one holding a `00_Original/` — photos come out of
   `00_Original/` **only**, and *everything else in that block is parked as well*:
   `01_Astro/lights/`, `02_Landscape/`, `04_tests/`. Filing a frame under `02_Landscape` is a
   decision, and re-pooling it would silently undo that decision.
5. **Anything else** is a card dump, an old hand-made tree, a stray folder: walked into, and its
   photos pooled.

Two things soften rule 3 and 4:

- **An empty directory is not parked, it is removed.** The scaffolding a previous run created is
  empty by design; parking it would fill `_dangling/` with hundreds of empty directories on every
  re-run. "Empty" means no file a person made — OS litter does not count as content.
- **The original path is preserved in `_dangling/`**, because the block's number is about to
  change and the path is the only record of which block the work came from.

A source directory left holding nothing but OS litter (`.DS_Store`, `Thumbs.db`, `desktop.ini`,
`._*`) is deleted. Anything a person made saves it, and it is reported instead. Nothing under a
block this run just wrote is ever swept — its scaffolding is empty on purpose.

**Never** deletes a photo, renames an original, or rewrites an original's EXIF.

---

## 6. What the other two skills read

### create-diary

**Two source directories, and the blocks are not among them:**

| source | what it holds |
|---|---|
| `_00info/` | the night's screenshots, sky charts, planning notes, phone frames |
| `_post-processing_jpg/` | the finished exports `tag-photo` copied up out of the blocks |

Nothing inside a block is read — not `00_Original/`, not a category's `lights/`, not a block's own
`_Post-Processing/`. The strip is what the owner has already chosen to keep, and a frame still
sitting in a block has not been chosen yet. The way into the diary is to export it and let
`tag-photo` collect it, or to drop it in `_00info/`.

Both directories are walked to any depth. **JPEG and PNG only** — `_00info/` is mostly
screenshots; a `.tif` is reported and left out, because a diary is for flicking through and those
run to hundreds of megabytes.

Everything is sorted into **one flat stream by capture time**: EXIF, then the timestamp in the
filename, then `FileModifyDate`, so a screenshot named `2026-09-11 06.01.44.png` sits where it
belongs instead of piling up at the end. Ties break on filename, and anything with no timestamp of
any kind sorts last rather than disappearing.

Each copy is named `d000010_`, `d000020_`, … **in front of the file's own name** — the number is
the diary's ordering and the rest is the file as the owner named it. The gap of 10 is so a frame
can be slipped in by hand between two of them.

The diary is emptied and rebuilt on every run, so it always mirrors its two sources exactly. There
is no undo and none is needed: every entry is a copy of a file still sitting in one of them.

The directory is named **`_<shoot folder name>_diary/`** — `_2026_0911_camera_llm_diary/` — so it
still says which shoot it belongs to once it has been copied or dragged somewhere else; a hundred
folders all called `_diary` are indistinguishable the moment they leave home. A shoot that already
has any `*diary/` keeps the name it has: the run never renames one out from under the owner.

One source missing is a warning and the run continues on the other; both missing stops the run.

### tag-photo

A block has up to four `_Post-Processing/` directories and **each is dated off its own frames**:

| directory | reference frames |
|---|---|
| `<block>/01_Astro/_Post-Processing/` | `01_Astro/lights/JPG` |
| `<block>/02_Landscape/_Post-Processing/` | `02_Landscape/lights/JPG` |
| `<block>/03_Portraits/_Post-Processing/` | `03_Portraits/lights/JPG` |
| `<block>/_Post-Processing/` | `00_Original/JPG` |

The reference is the **last frame by capture time** — the moment that run finished — and the
directory's products are stamped with its GPS and time at +1 s, +2 s, … in **filename-length
order, shortest first**, so the keeper (`..._thor.jpg`) comes before its variants
(`..._thor_SequatorStacking30.tif`).

**Nothing is borrowed.** A category holding work but with an empty `lights/JPG` has no run to date
against, and no sibling category or other block fills the gap: the run **stops and asks the owner
which photo to date it from**, then re-runs with
`--reference '<block>/<category>=<path to a frame>'`. `--skip-unreferenced` leaves those
directories alone instead.

A file that is only a copy of an original frame (`IMG_0046.JPG`, or `6H-0050-..._IMG_0148.JPG`) is
left completely alone — it already carries the camera's own GPS and true timestamp, and
overwriting those would put a made-up record over a real one. A body with no GPS (the 550d) yields
time only.

Scattered groups are skipped and reported: no settings, so no run to date against.

Every stamped directory is then copied up into the shoot root's `_post-processing_jpg/`. That copy is
**additive** — the root folder is hand-curated and nothing in it is ever deleted.

Idempotent by construction: the time is always recomputed from the reference frame, never from the
target's current tags, so the seconds cannot drift across runs.

---

## 7. Working on this

All three are **plan-first**: run with no `--apply`, show the plan, then `--apply` in the same
turn. No skill guesses an argument.

```
python3 .claude/skills/organize-photo-folders/organize.py <folder> <start> [--apply]
python3 .claude/skills/create-diary/diary.py              <folder>         [--apply]
python3 .claude/skills/tag-photo/tag.py                   <folder>         [--apply]
```

All three take `--exiftool PATH`. `organize.py` also takes `--prefix` and `--keep-source`;
`tag.py` takes `--reference` and `--skip-unreferenced`.

To try a change without risking the drive, copy a shoot folder somewhere scratch, `touch
it_exists.txt` beside it, and point `$CAMERA_LATEST_DIR` at that directory.

**The photos are not in this repo.** The skills live here, the shoot folders live on the removable
drive. Don't put documentation back on the drive — it moved here on 2026-09-09 so the drive stays
pure storage.
