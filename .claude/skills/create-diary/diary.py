#!/usr/bin/env python3
"""Build <folder>/_<folder>_diary/: every photo in _00info/ and _post-processing_jpg/, by time.

Two source directories and nothing else. The blocks are not read -- not their 00_Original/, not
their categories, not their own _Post-Processing/. What belongs in the strip is what the owner has
already chosen to keep: the night's screenshots and notes in _00info/, and the finished exports
that tag-photo collected at the shoot root in _post-processing_jpg/. A frame still sitting in a
block has not been chosen yet, and a frame that should appear belongs in one of those two folders.

That is the whole rule, and it is why this script no longer knows what a group is, which category
a frame was filed into, or which three frames of a run to pick.

Both folders are walked to any depth, so a _00info/ that grows subfolders still works. Photos are
JPEG and PNG -- _00info/ is mostly screenshots; a .tif export is reported and left out, because a
diary is for flicking through and those run to hundreds of megabytes.

Ordering is one flat stream by capture time: EXIF first, then the timestamp in the filename, then
FileModifyDate, so a screenshot named 2026-09-11 06.01.44.png sits where it belongs instead of
piling up at the end. Ties break on filename. Each copy is named d000010_/d000020_/... in front of
its original filename, nothing else added -- the number is the diary's own ordering and the rest is
the file as the owner named it.

The diary is REBUILT from scratch on every run: emptied first, then filled again from the two
sources, so it always mirrors them exactly and never carries a frame from an older layout. There
is no undo and none is needed -- every entry is a copy of a file still sitting in _00info/ or
_post-processing_jpg/, so a rebuild puts it straight back.

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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_shared'))
from camera_lib import (                                            # noqa: E402
    DIARY_GLOB, INFO_ROOT, POSTPROC_ROOT,
    diary_dir_name, find_exiftool, is_junk, read_dates, resolve_folder,
)

SOURCES = (INFO_ROOT, POSTPROC_ROOT)        # the only two directories the diary is built from
DIARY_EXTS = ('.JPG', '.JPEG', '.PNG')      # _00info/ is mostly screenshots, hence PNG
STEP = 10                                   # gap between diary numbers, a reading convenience
SEP = '_'                                   # d000010_<original filename>


def find_diary(folder):
    """The shoot folder's diary directory.

    organize-photo-folders protects `*diary/` at the root, so whichever one is already there is
    the diary and keeps the name it has -- a shoot is not renamed out from under the owner. A
    shoot with none gets `_<folder name>_diary`, which is what the older shoots here are called.
    """
    hits = [n for n in sorted(os.listdir(folder))
            if fnmatch.fnmatch(n, DIARY_GLOB) and os.path.isdir(os.path.join(folder, n))]
    return hits[0] if hits else diary_dir_name(folder)


def is_diary_photo(fn):
    return fn.upper().endswith(DIARY_EXTS)


def collect(folder, diary):
    """(photos, other, missing) across the two source directories.

    `photos` is every JPEG/PNG under them at any depth, `other` the files left behind and only
    reported, `missing` the source directories that are not there at all. The diary itself is
    skipped if it happens to sit inside a source -- it holds copies, and re-reading them would
    double the strip on every run.
    """
    photos, other, missing = [], [], []
    for src in SOURCES:
        root = os.path.join(folder, src)
        if not os.path.isdir(root):
            missing.append(src)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames
                                 if not d.startswith('.')
                                 and os.path.abspath(os.path.join(dirpath, d)) != diary)
            for fn in sorted(filenames):
                if is_junk(fn):
                    continue
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, folder)
                (photos if is_diary_photo(fn) else other).append((p, rel, src))
    return photos, other, missing


def build_plan(exe, photos):
    """One flat stream, sorted by capture time, numbered d000010_/d000020_/...

    This is the whole diary, not a delta -- the run rebuilds it from exactly this list.
    """
    paths = [p for p, _, _ in photos]
    # fallback=True: _00info/ screenshots carry no EXIF, only a timestamp in the filename.
    dates, undated = read_dates(exe, paths, fallback=True)
    for p in undated:
        print(f"  warning: {os.path.basename(p)} has no timestamp of any kind "
              f"(EXIF, filename or mtime), sorted last", file=sys.stderr)

    plan = [dict(src=p, rel=rel, source=src, t=dates.get(p), name=os.path.basename(p))
            for p, rel, src in photos]
    # Undated entries sort last, by name, rather than disappearing from the sequence.
    plan.sort(key=lambda e: (e['t'] is None, e['t'] or datetime.datetime.min, e['name']))
    for i, e in enumerate(plan):
        e['final'] = f"d{(i + 1) * STEP:06d}{SEP}{e['name']}"
    return plan


def current_diary(diary):
    """What the diary holds right now -- all of which the run removes and writes again.

    Every one of these is a copy: its original is in one of the two sources, and the rebuild puts
    it back. Dot-files and subdirectories are left alone.
    """
    if not os.path.isdir(diary):
        return []
    return [fn for fn in sorted(os.listdir(diary))
            if not is_junk(fn) and os.path.isfile(os.path.join(diary, fn))]


def print_plan(plan, other, missing, existing, diary_name):
    counts = {}
    for e in plan:
        counts[e['source']] = counts.get(e['source'], 0) + 1
    print(f"{'SOURCE':<24} {'PHOTOS':>7}")
    for src in SOURCES:
        if src in missing:
            print(f"{src:<24} {'--':>7}   not present")
        else:
            print(f"{src:<24} {counts.get(src, 0):>7}")

    undated = [e for e in plan if e['t'] is None]
    if undated:
        print(f"\n{len(undated)} file(s) with no timestamp, placed last: "
              f"{', '.join(e['name'] for e in undated[:5])}"
              f"{' ...' if len(undated) > 5 else ''}")
    if other:
        print(f"\nnot a JPEG/PNG, left where they are ({len(other)}): "
              f"{', '.join(rel for _, rel, _ in other[:8])}"
              f"{' ...' if len(other) > 8 else ''}")
    if existing:
        print(f"\n{diary_name}/ is emptied first: {len(existing)} file(s), all of them copies "
              f"this run writes again from {' and '.join(SOURCES)}")

    print(f"\ndiary after this run — {len(plan)} frames:")
    for e in plan:
        when = f"{e['t']:%Y-%m-%d %H:%M:%S}" if e['t'] else '(no date)'
        print(f"  {e['final']:<52}  {when}  <- {e['source']}")


def apply_plan(diary, plan, existing):
    os.makedirs(diary, exist_ok=True)

    # 1. Empty the diary. Everything in it is a copy of a file still sitting in one of the two
    #    sources, so there is nothing here to preserve -- step 2 writes the strip again.
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

    exe, _ = find_exiftool(args.exiftool)
    folder = resolve_folder(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"folder not found: {folder}")

    t0 = time.time()
    diary_name = find_diary(folder)
    diary = os.path.join(folder, diary_name)

    photos, other, missing = collect(folder, os.path.abspath(diary))
    if len(missing) == len(SOURCES):
        sys.exit(f"neither {' nor '.join(SOURCES)} is in {folder}; the diary is built from those "
                 f"two directories, so at least one must exist")
    if not photos:
        sys.exit(f"no JPEG or PNG in {' or '.join(s for s in SOURCES if s not in missing)} "
                 f"-- nothing to build a diary from")

    plan = build_plan(exe, photos)
    existing = current_diary(diary)
    print_plan(plan, other, missing, existing, diary_name)

    if args.apply:
        written = apply_plan(diary, plan, existing)
        print(f"\nrebuilt {diary_name}/ from scratch: {len(written)} frames written, "
              f"{len(existing)} removed first")
    else:
        print("\n(plan only -- re-run with --apply to rebuild the diary)")
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
