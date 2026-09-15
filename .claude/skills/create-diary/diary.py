#!/usr/bin/env python3
"""Build <folder>/_diary/: everything in 00info/ and three JPEGs per group.

Scattered-groups -- the blocks whose name stops at the camera, holding the night's test and
framing shots -- are NOT in the strip. They are counted and reported, never copied.

Frames come from the categories the owner has filed a block into: 01_Astro/lights/JPG,
02_Landscape/lights/JPG and 03_Portraits/lights/JPG, merged and re-sorted into one stream, so a
block worked across two categories still reads as one block. A block nobody has filed yet -- which
is every block the moment organize-photo-folders finishes -- falls back to its 00_Original/JPG, so
the diary works on a folder that has only just been organized.

darks/ is calibration and never reaches the strip, and neither does RAW/, anywhere.

The diary is REBUILT from scratch on every run: it is emptied first, then filled again from
00info/ and the block directories, so it always mirrors them exactly and never carries a stale
frame from an older layout. Copies (never moves) out of 00info/ and the blocks, names each copy
<source>_<filename>, then numbers the strip d000010_/d000020_/... in capture order.

A group contributes its first, middle and last frame, and the three travel together: 00info/
photos are placed individually by capture time, and each group is inserted whole at the time of
its first pick, so a run reads as one block rather than three frames scattered through everything
shot alongside it.

There is no undo and none is needed: every frame in the diary is a copy of a file that is still
sitting in 00info/ or a block, so a rebuild puts it straight back. Nothing else is kept -- the diary
holds copies only, so anything in it that the sources do not account for is a leftover of an older
run and goes. A photo that must appear in the strip belongs in 00info/, not in the diary.

The block layout this reads is written down in organize-photo-folders.md at the repo root.

Plan-only by default; pass --apply to write.
"""
import argparse
import datetime
import fnmatch
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_shared'))
from camera_lib import (                                            # noqa: E402
    DIARY, DIARY_GLOB, JPG_SUB, LIGHTS, ORIGINAL,
    block_dirs, category_lights_jpg, find_exiftool, has_old_layout, is_group, is_junk,
    original_jpg, read_dates, resolve_folder,
)
from camera_lib import INFO_ROOT as INFO                            # noqa: E402

# Blocks hold camera JPEGs; 00info/ and the diary also hold screenshots and hand-added frames.
SOURCE_EXTS = ('.JPG', '.JPEG')
DIARY_EXTS = ('.JPG', '.JPEG', '.PNG')
STEP = 10                                   # gap between diary numbers, a reading convenience
SEP = '_'                                   # d000010_<source>_<original filename>


def find_diary(folder):
    """The shoot folder's diary directory. organize-photo-folders protects `*diary/` at the
    root, so whichever one is already there is the diary; _diary is what we create."""
    hits = [n for n in sorted(os.listdir(folder))
            if fnmatch.fnmatch(n, DIARY_GLOB) and os.path.isdir(os.path.join(folder, n))]
    return hits[0] if hits else DIARY


def is_diary_photo(fn):
    return fn.upper().endswith(DIARY_EXTS)


def find_blocks(folder):
    """Every block directory and the frames its diary entry is built from.

    Returns (blocks, stale). Each block is (name, where-the-frames-came-from, [full paths]).
    `stale` is the blocks still in the pre-00_Original layout -- a bare lights/jpg/ or an even
    older jpg/. They are reported rather than read, because a folder in that shape wants
    re-organizing, not a diary built around it.
    """
    blocks, stale = [], []
    for name in block_dirs(folder):
        bdir = os.path.join(folder, name)
        if has_old_layout(bdir):
            stale.append(name)
            continue
        # What the owner has filed comes first; 00_Original/ is the fall-back, not the preference,
        # because a filed block says which frames were worth keeping and the pool does not.
        cats = category_lights_jpg(bdir)
        if cats:
            label = '+'.join(c for c, _, _ in cats) + f'/{LIGHTS}/{JPG_SUB}'
            paths = [os.path.join(d, f) for _, d, fs in cats for f in fs]
        else:
            d, files = original_jpg(bdir)
            label = f'{ORIGINAL}/{JPG_SUB}'
            paths = [os.path.join(d, f) for f in files]
        if paths:
            blocks.append((name, label, paths))
    return blocks, stale


def find00info(folder):
    """(dir, photos, other) in 00info/. Photos go in the diary; other files are only reported."""
    d = os.path.join(folder, INFO)
    names = [f for f in sorted(os.listdir(d)) if not f.startswith('.')]
    photos = [f for f in names if is_diary_photo(f) and os.path.isfile(os.path.join(d, f))]
    return d, photos, [f for f in names if f not in photos]


def build_plan(exe, folder, blocks, infodir, infofiles):
    """The diary the sources call for: all of 00info/ and three frames per group.

    Returns (plan, skipped) — `skipped` is the scattered-groups, reported so they are visibly
    left out rather than silently missing.

    This is the whole diary, not a delta — the run rebuilds it from exactly this list.

    The strip is ordered in *units*. A photo from 00info/ is a unit of its own, placed at its own
    capture time. A group is a single unit of three frames — first, middle, last — inserted where
    its *first* pick falls, so the three stay together instead of the middle and last drifting off
    among whatever else was shot during the run.
    """
    # Scattered-groups are the test and framing shots. They are not part of the night's story,
    # so nothing of them reaches the strip -- not even their timestamps get read.
    groups = [b for b in blocks if is_group(b[0])]
    skipped = [(name, len(ps)) for name, _, ps in blocks if not is_group(name)]
    if not groups:
        print(f"  warning: no group directories (a name carrying -iso<n>) in this folder; "
              f"the diary is {INFO}/ only", file=sys.stderr)
    all_jpgs = [p for _, _, ps in groups for p in ps]
    dates, unreadable = read_dates(exe, all_jpgs)
    if unreadable:
        print(f"  warning: no usable DateTimeOriginal, ignored: "
              f"{[os.path.basename(p) for p in unreadable[:5]]}"
              f"{' ...' if len(unreadable) > 5 else ''}", file=sys.stderr)

    units = []                                  # each unit is a list of entries placed together

    def entry(source, kind, n, src, t, label=''):
        return dict(source=source, kind=kind, n=n, src=src, label=label,
                    stem=f"{source}{SEP}{os.path.basename(src)}", t=t)

    # 00info/ first: the night's screenshots, charts and phone frames, every one of them.
    info_paths = [os.path.join(infodir, f) for f in infofiles]
    idates, iunreadable = read_dates(exe, info_paths, fallback=True)
    for p in iunreadable:
        print(f"  warning: {INFO}/{os.path.basename(p)} has no timestamp of any kind "
              f"(EXIF, filename or mtime), sorted last", file=sys.stderr)
    for p in info_paths:
        units.append([entry(INFO, 'info', len(info_paths), p, idates.get(p), label='(all)')])

    for name, label, paths in groups:
        # Re-sorted by capture time, not by the category they were filed into: a block worked
        # across two categories is still one run and reads as one.
        ordered = sorted((p for p in paths if p in dates),
                         key=lambda p: (dates[p], os.path.basename(p)))
        if not ordered:
            print(f"  warning: {name}: no frame with a readable timestamp, skipped",
                  file=sys.stderr)
            continue
        # First, middle, last -- de-duplicated, so a one- or two-frame group contributes
        # one or two frames rather than the same file twice.
        idx = sorted({0, len(ordered) // 2, len(ordered) - 1})
        units.append([entry(name, 'group', len(ordered), ordered[i], dates[ordered[i]], label)
                      for i in idx])

    # A unit is placed by its first frame. Undated ones sort last, by name, rather than
    # disappearing from the sequence.
    units.sort(key=lambda u: (u[0]['t'] is None, u[0]['t'] or datetime.datetime.min, u[0]['stem']))
    plan = [e for u in units for e in u]
    for i, e in enumerate(plan):
        e['final'] = f"d{(i + 1) * STEP:06d}{SEP}{e['stem']}"
    return plan, skipped


def current_diary(folder):
    """What the diary holds right now — all of which the run is about to remove and write again.

    Every one of these is a copy: its original is in 00info/ or a block, and the rebuild puts it
    back. Dot-files and subdirectories are left alone.
    """
    diary = os.path.join(folder, DIARY)
    if not os.path.isdir(diary):
        return []
    return [fn for fn in sorted(os.listdir(diary))
            if not is_junk(fn) and os.path.isfile(os.path.join(diary, fn))]


def print_plan(plan, existing, info_other, skipped):
    # One row per source, in the order the sources reach the strip -- a group picks three frames
    # and would otherwise take three rows.
    rows = {}
    for p in plan:
        r = rows.setdefault(p['source'],
                            dict(kind=p['kind'], n=p['n'], label=p['label'], picks=[]))
        r['picks'].append(os.path.basename(p['src']))

    w = max([len('SOURCE')] + [len(s) for s in rows])              # block names are long now
    lw = max([len('FROM')] + [len(r['label']) for r in rows.values()])
    print(f"{'SOURCE':<{w}} {'TYPE':<9} {'N':>4}  {'FROM':<{lw}}  PICKED")
    for source, r in rows.items():
        if r['kind'] == 'group':
            pick = f"first+middle+last: {', '.join(r['picks'])}"
        else:                                                      # 00info/: all of it
            pick = f"all {len(r['picks'])}: {', '.join(r['picks'][:3])}"
            if len(r['picks']) > 3:
                pick += ' ...'
        print(f"{source:<{w}} {r['kind']:<9} {r['n']:>4}  {r['label']:<{lw}}  {pick}")
    fallbacks = [s for s, r in rows.items()
                 if r['kind'] == 'group' and r['label'].startswith(ORIGINAL)]
    if fallbacks:
        print(f"\n{len(fallbacks)} group(s) have nothing filed under "
              f"{'/'.join(('<category>', LIGHTS, JPG_SUB))} yet, so the strip is built from "
              f"{ORIGINAL}/{JPG_SUB}: {', '.join(fallbacks[:5])}"
              f"{' ...' if len(fallbacks) > 5 else ''}")
    if skipped:
        print(f"\nscattered-groups, left out of the diary by design — {len(skipped)} block(s), "
              f"{sum(c for _, c in skipped)} frames: "
              + ', '.join(f"{n} ({c})" for n, c in skipped))
    if info_other:
        print(f"\nnot photos, left in {INFO}/: {', '.join(info_other[:8])}"
              f"{' ...' if len(info_other) > 8 else ''}")

    if existing:
        print(f"\n{DIARY}/ is emptied first: {len(existing)} files, all of them copies "
              f"this run writes again from {INFO}/ and the blocks")

    print(f"\ndiary after this run — {len(plan)} frames:")
    for e in plan:
        print(f"  {e['final']}")


def apply_plan(folder, plan, existing):
    diary = os.path.join(folder, DIARY)
    os.makedirs(diary, exist_ok=True)

    # 1. Empty the diary. Everything in it is a copy of a file still in 00info/ or a block, so
    #    there is nothing here to preserve -- step 2 writes the strip again from the sources.
    for fn in existing:
        os.remove(os.path.join(diary, fn))

    # 2. Rebuild it.
    written = []
    for e in plan:
        shutil.copy2(e['src'], os.path.join(diary, e['final']))  # sources are never modified
        written.append(e['final'])
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--exiftool', help='path to exiftool, when it is not on PATH')
    ap.add_argument('--apply', action='store_true', help='write the diary (default: plan only)')
    args = ap.parse_args()

    global DIARY
    exe, _ = find_exiftool(args.exiftool)
    folder = resolve_folder(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"folder not found: {folder}")
    DIARY = find_diary(folder)

    t0 = time.time()
    if not os.path.isdir(os.path.join(folder, INFO)):
        sys.exit(f"no {INFO}/ in {folder}; the diary is built from {INFO}/ and the block "
                 f"directories together, so {INFO}/ must exist")
    blocks, stale = find_blocks(folder)
    if stale:
        print(f"  warning: {len(stale)} block(s) are still in the old layout (a bare "
              f"{LIGHTS}/jpg/ and no {ORIGINAL}/), skipped: "
              f"{', '.join(stale[:5])}{' ...' if len(stale) > 5 else ''}\n"
              f"  re-run organize-photo-folders on {folder} to move them into {ORIGINAL}/",
              file=sys.stderr)
    if not blocks:
        sys.exit(f"no block directories with frames in {folder} -- expected names like "
                 f"6I-0035-550d-18mm-15s-f3.5-iso1600 holding "
                 f"01_Astro/{LIGHTS}/{JPG_SUB}/ or {ORIGINAL}/{JPG_SUB}/ "
                 f"(organize the folder first)")
    infodir, infofiles, info_other = find00info(folder)
    plan, skipped = build_plan(exe, folder, blocks, infodir, infofiles)
    if not plan:
        sys.exit("nothing to do: no frames with readable timestamps")
    existing = current_diary(folder)
    print_plan(plan, existing, info_other, skipped)

    if args.apply:
        written = apply_plan(folder, plan, existing)
        print(f"\nrebuilt {DIARY}/ from scratch: {len(written)} frames written, "
              f"{len(existing)} removed first")
    else:
        print("\n(plan only -- re-run with --apply to rebuild the diary)")
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
