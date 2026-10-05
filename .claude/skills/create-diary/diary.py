#!/usr/bin/env python3
"""Rebuild <folder>/_post-processing_jpg/ and <folder>/_<folder>_diary/ from scratch.

Every run, in this order:

  1. DELETE <folder>/_diary/ (the old spelling), <folder>/_<folder>_diary/ and
     <folder>/_post-processing_jpg/. All three are copies and all three are rebuilt below, so a
     first run and a tenth run end in the same place.
  2. COLLECT from every _Post-Processing/ in every block (camera_lib.postproc_dirs()) the files
     meant for looking at: a camera-style upper-case .JPG, a *_q6.jpg export, or a .png (any
     case). Nothing else -- not .psd/.tif/.xmp/raw, and not the full-size *_q12.jpg.
  3. CHECK those picks carry GPS and DateTimeOriginal. A group holding one that does not is run
     through tag-photo first (tag.plan_block / apply_block), so the copies carry the tags.
  4. COPY them flat into <folder>/_post-processing_jpg/.
  5. SORT everything under _00info/ plus everything in _post-processing_jpg/ into one stream by
     capture time, and number it d000010_, d000020_, ... in front of each file's own name.
  6. WRITE that stream into <folder>/_<folder>_diary/.

Ordering is by capture time: EXIF first, then the timestamp in the filename, then
FileModifyDate, so a screenshot named 2026-09-11 06.01.44.png sits where it belongs. Ties break
on filename; anything with no timestamp at all sorts last. A file tag-photo is about to stamp is
sorted by the time it is about to get, so the plan is what --apply writes.

Nothing in a block is ever changed here except through tag-photo, whose rules are its own.

The layout this reads is written down in organize-photo-folders.md at the repo root.

Plan-only by default; pass --apply to write.
"""
import argparse
import datetime
import fnmatch
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '_shared'))
sys.path.insert(0, os.path.join(HERE, '..', 'tag-photo'))
from camera_lib import (                                            # noqa: E402
    DIARY_GLOB, DIARY_OLD, INFO_ROOT, POSTPROC_ROOT,
    block_dirs, diary_dir_name, find_exiftool, is_junk, postproc_dirs, read_dates,
    read_geo_time, resolve_folder,
)
import tag                                                          # noqa: E402

STEP = 10                                   # gap between diary numbers, a reading convenience
SEP = '_'                                   # d000010_<original filename>


def wanted(fn):
    """A _Post-Processing/ file that belongs in the diary: a camera-style .JPG (the extension
    upper-case, exactly), a quality-6 export, or a .png in either case (a screen grab such as a
    field-of-view diagram). *_q12.jpg is the full-size export and is left out, as is every .psd
    .tif .xmp and raw file."""
    low = fn.lower()
    return fn.endswith('.JPG') or low.endswith('_q6.jpg') or low.endswith('.png')


def walk_files(root):
    """Every non-junk file under root, at any depth, in path order."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith('.'))
        out += [os.path.join(dirpath, f) for f in sorted(filenames) if not is_junk(f)]
    return out


def collect_postproc(folder):
    """(picked, clashes, skipped) from every block's _Post-Processing/ directories.

    `picked` is [(src, block)], one per destination name. `clashes` is two blocks exporting the
    same filename: the first is kept, the second reported -- it goes nowhere until one of them is
    renamed. `skipped` counts what is there but not wanted (tif, psd, q12, ...)."""
    picked, clashes, skipped, seen = [], [], 0, {}
    for block in block_dirs(folder):
        for ppdir, _ in postproc_dirs(os.path.join(folder, block)):
            for src in walk_files(ppdir):
                fn = os.path.basename(src)
                if not wanted(fn):
                    skipped += 1
                    continue
                if fn in seen:
                    clashes.append((fn, seen[fn], block))
                    continue
                seen[fn] = block
                picked.append((src, block))
    return picked, clashes, skipped


def plan_tagging(exe, folder, picked):
    """Run tag-photo's planner on every block holding a picked file that is missing a tag.

    Returns (plans, overrides, still_missing). overrides maps a path to the time tag-photo is
    about to give it; still_missing is the picked files tag-photo will not fix (a copy of an
    original on a body with no GPS, most often)."""
    geo = read_geo_time(exe, [src for src, _ in picked])
    need = sorted({blk for src, blk in picked if not all(geo[src])})
    plans = [tag.plan_block(exe, folder, blk) for blk in need]
    overrides = {os.path.normpath(w['path']): (w['t'], bool(w['gps_src']))
                 for p in plans for g in p['dirs'] for w in g['writes']}
    still = []
    for src, _ in picked:
        t, gps = overrides.get(os.path.normpath(src), geo[src])
        if not (t and gps):
            still.append(src)
    return plans, overrides, still


def build_stream(exe, info_files, picked, overrides):
    """The diary: one flat stream, sorted by capture time, numbered d000010_/d000020_/..."""
    entries = [dict(src=p, name=os.path.basename(p), source=INFO_ROOT) for p in info_files]
    entries += [dict(src=s, name=os.path.basename(s), source=POSTPROC_ROOT) for s, _ in picked]
    # fallback=True: _00info/ screenshots carry no EXIF, only a timestamp in the filename.
    dates, _ = read_dates(exe, [e['src'] for e in entries], fallback=True)
    for e in entries:
        ov = overrides.get(os.path.normpath(e['src']))
        e['t'] = ov[0] if ov else dates.get(e['src'])
    entries.sort(key=lambda e: (e['t'] is None, e['t'] or datetime.datetime.min, e['name']))
    for i, e in enumerate(entries):
        e['final'] = f"d{(i + 1) * STEP:06d}{SEP}{e['name']}"
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--exiftool', help='path to exiftool, when it is not on PATH')
    ap.add_argument('--apply', action='store_true', help='write everything (default: plan only)')
    args = ap.parse_args()

    exe, _ = find_exiftool(args.exiftool)
    folder = resolve_folder(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"folder not found: {folder}")
    t0 = time.time()
    diary_name = diary_dir_name(folder)
    ppjpg = os.path.join(folder, POSTPROC_ROOT)

    # 1. what is deleted
    doomed = [d for d in (DIARY_OLD, diary_name, POSTPROC_ROOT)
              if os.path.isdir(os.path.join(folder, d))]
    others = [n for n in sorted(os.listdir(folder))
              if fnmatch.fnmatch(n, DIARY_GLOB) and n not in (DIARY_OLD, diary_name)
              and os.path.isdir(os.path.join(folder, n))]

    # 2. what is collected
    picked, clashes, skipped = collect_postproc(folder)
    info_dir = os.path.join(folder, INFO_ROOT)
    info_files = walk_files(info_dir) if os.path.isdir(info_dir) else []
    if not picked and not info_files:
        sys.exit(f"nothing for a diary: no {INFO_ROOT}/ content and no .JPG, *_q6.jpg or .png in any "
                 f"block's _Post-Processing/")

    # 3. what tag-photo has to fix first
    plans, overrides, still = plan_tagging(exe, folder, picked)
    unresolved = [(p['block'], rel, f) for p in plans for rel, f in tag.unresolved_of(p)]

    # 5. the stream
    stream = build_stream(exe, info_files, picked, overrides)

    # ---- the plan
    print("DELETE")
    for d in doomed:
        n = len(walk_files(os.path.join(folder, d)))
        print(f"  {d}/   ({n} file(s))")
    if not doomed:
        print("  nothing -- none of them exists yet")
    if os.path.isdir(ppjpg):
        fresh = {os.path.basename(s) for s, _ in picked}
        lost = [os.path.basename(p) for p in walk_files(ppjpg)
                if os.path.basename(p) not in fresh]
        if lost:
            print(f"  !! {len(lost)} file(s) in {POSTPROC_ROOT}/ are not in any block's "
                  f"_Post-Processing/ and will be GONE after this run:")
            for f in lost:
                print(f"       {f}")
    for n in others:
        print(f"  (left alone: {n}/ -- a diary under another name)")

    print(f"\nTAG FIRST — {len(plans)} group(s) hold a pick missing GPS or taken time")
    for p in plans:
        tag.print_block(p)
    for s in still:
        print(f"  note: {os.path.relpath(s, folder)} will still lack GPS or taken time "
              f"(tag-photo leaves copies of originals alone)")

    print(f"\nCOPY into {POSTPROC_ROOT}/ — {len(picked)} file(s) "
          f"({skipped} other file(s) in _Post-Processing/ left out: tif, psd, xmp, q12, raw ...)")
    for s, blk in picked:
        print(f"  {os.path.basename(s)}")
    for fn, a, b in clashes:
        print(f"  CLASH  {fn}: both {a} and {b} export this name -- only {a}'s is copied")

    print(f"\n{diary_name}/ — {len(stream)} file(s): "
          f"{sum(e['source'] == INFO_ROOT for e in stream)} from {INFO_ROOT}/, "
          f"{sum(e['source'] == POSTPROC_ROOT for e in stream)} from {POSTPROC_ROOT}/")
    for e in stream:
        when = f"{e['t']:%Y-%m-%d %H:%M:%S}" if e['t'] else '(no date)'
        print(f"  {e['final']:<60}  {when}")

    if unresolved:
        print(f"\nNEEDS A REFERENCE PHOTO — tag-photo cannot date {len(unresolved)} file(s):")
        for blk, rel, f in unresolved:
            print(f"  {blk}/{rel}/{f}")
        sys.exit("\nrefusing to write. Ask which photo to date them from, run tag-photo on that "
                 "group with --reference <path> --apply, then run create-diary again.")

    if not args.apply:
        print("\n(plan only -- re-run with --apply to tag, delete, copy and rebuild)")
        print(f"elapsed: {time.time() - t0:.1f}s")
        return

    # ---- apply, in the order the docstring gives
    tagged, failed = 0, []
    for p in plans:                                     # 3. tag first, so the copies carry it
        w, f = tag.apply_block(exe, p)
        tagged += w
        failed += f
    for d in doomed:                                    # 1. delete
        shutil.rmtree(os.path.join(folder, d))
    os.makedirs(ppjpg)                                  # 4. copy
    for s, _ in picked:
        shutil.copy2(s, os.path.join(ppjpg, os.path.basename(s)))
    diary = os.path.join(folder, diary_name)            # 6. the diary
    os.makedirs(diary)
    for e in stream:
        src = (os.path.join(ppjpg, e['name']) if e['source'] == POSTPROC_ROOT else e['src'])
        shutil.copy2(src, os.path.join(diary, e['final']))

    print(f"\ntagged {tagged} file(s); deleted {', '.join(d + '/' for d in doomed) or 'nothing'}; "
          f"copied {len(picked)} into {POSTPROC_ROOT}/; wrote {len(stream)} into {diary_name}/")
    for f, err in failed:
        print(f"  FAILED to tag {f}: {err}", file=sys.stderr)
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
