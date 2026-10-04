#!/usr/bin/env python3
"""Make sure every file in a group's _Post-Processing/ directories carries GPS and a taken time.

A stacked TIF out of Sequator carries no EXIF worth having, and a Photoshop export can lose the
GPS on the way out. The frames it was made from carry both. This fills the gap -- and only the
gap: a file that already has DateTimeOriginal AND GPS is not touched.

Run per group, named on the command line:

    tag.py 2026_0907_camera_daw_bay 6I-0011-6dii-24mm-8s-f1.8-iso3200_sagittarius

A group can hold several _Post-Processing/ directories (camera_lib.postproc_dirs()):

  <block>/01_Astro/_Post-Processing/       a category's
  <block>/02_Landscape/_Post-Processing/
  <block>/03_Portraits/_Post-Processing/
  <block>/_Post-Processing/                the block's own, "main"

Every file in each of them except .xmp and .txt is checked. One that is missing either tag is
dated off, in order:

  1. A SIBLING in the same directory with a similar name -- its derivative chain. The owner names
     a variant by hanging a suffix off what it came from (X.tif -> X_LRC.tif -> X_LRC_q6.jpg), so
     a sibling whose stem is a prefix of this one's, ending at a _ - ( or space, or the other way
     round, is the same picture. The longest shared stem wins. A sibling qualifies when it has
     both tags already, or is a copy of an original frame with a real date, or was itself planned
     a moment ago in this run -- so a whole chain lands on one time.
  2. The LAST frame by capture time in the category's own _00Original/lights/JPG.
  3. The last frame in 01_Astro/_00Original/lights/JPG -- for a category with no pool of its own,
     and always for the main _Post-Processing/.
  4. --reference PATH, when the owner has named one. Otherwise the run stops and asks.

A sibling's time is copied exactly. Files dated off a pool frame get its time +1s, +2s, ... in
filename-length order, shortest first -- the keeper (..._thor.tif) before its variants -- so two
roots dated off the same frame do not land on the same second.

What is written is both tags: the reference's GPS (when it has any -- the 550d records none) and
its time as AllDates. A file that is only a copy of an original frame -- IMG_0046.JPG, or
6H-0050-..._IMG_0148.JPG -- is never rewritten, even when it is missing GPS: it carries the
camera's own record, and a made-up one must not go over it.

Nothing outside a _Post-Processing/ is ever written, and nothing is copied anywhere. (Copying up
into the shoot root's _post-processing_jpg/ belongs to create-diary since 2026-10-01.)

Idempotent: a file this run tags has both tags afterwards, so the next run leaves it alone. On a
body with no GPS the same files are re-stamped every run with the same values.

The block layout this reads is written down in organize-photo-folders.md at the repo root.

Plan-only by default; pass --apply to write.
"""
import argparse
import datetime
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_shared'))
from camera_lib import (                                            # noqa: E402
    CATEGORY_DEFAULT, DANGLING, POSTPROC,
    block_dirs, find_exiftool, is_block, is_junk, is_jpg, pool_jpg_dir, postproc_dirs,
    read_dates, read_geo_time, resolve_folder,
)

# Sidecars and notes. Not images, never checked.
IGNORED_EXTS = ('.XMP', '.TXT')
# What exiftool can safely write in place. Anything else missing a tag is reported and left
# alone -- notably video (QuickTime dates are UTC and need -api QuickTimeUTC, a trap this skill
# stays out of) and raw files.
TAGGABLE_EXTS = ('.TIF', '.TIFF', '.JPG', '.JPEG', '.PNG', '.PSD', '.PSB')
# Where a variant's suffix starts: X_q6, X-edit, X(IMG_0091), X copy.
STEM_BREAKS = '_-( '

# Names that are a camera's own, not something a person exported: IMG_0046, _MG_1234,
# DSC01234, and the iPhone's '2026-08-18 22.35.21'. Used only as a fallback -- the real test
# is whether the block still holds a file by that name.
CAMERA_NAME_RE = re.compile(r'^(?:IMG|_MG|DSC|DSCN|PICT|P)_?\d{3,}$', re.I)
STAMP_NAME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[ _T]\d{2}[.:-]\d{2}[.:-]\d{2}')


def ext_of(fn):
    return os.path.splitext(fn)[1].upper()


def block_originals(block_dir):
    """Every filename the block holds OUTSIDE any _Post-Processing/ -- the pool, lights/, darks/,
    04_tests/. A _Post-Processing/ entry matching one of these is a copy of an original frame."""
    names = set()
    for root, dirs, files in os.walk(block_dir):
        dirs[:] = [d for d in dirs if d.lower() != POSTPROC.lower() and d != DANGLING]
        for f in files:
            names.add(f.lower())
    return names


def is_original_copy(fn, block, originals):
    """Is this _Post-Processing/ entry just a copy of one of the block's own frames?

    Either the block still holds a file by that name -- after stripping a '<block>_' prefix (or
    the prefix up to the -iso<n>, since a label may follow it), which is how the owner marks a
    frame they pulled out to work on -- or the bare name is plainly a camera's own (IMG_0148).
    """
    lower = fn.lower()
    if lower in originals:
        return True
    stripped = fn
    for prefix in {block + '_', re.sub(r'(-iso\d+).*$', r'\1', block, flags=re.I) + '_'}:
        if lower.startswith(prefix.lower()):
            stripped = fn[len(prefix):]
            if stripped.lower() in originals:
                return True
    # The owner also puts the category in the name: <block>_01Astro_IMG_0046.JPG.
    stripped = re.sub(r'^\d\d[A-Za-z]+_', '', stripped)
    if stripped.lower() in originals:
        return True
    stem = os.path.splitext(stripped)[0]
    return bool(CAMERA_NAME_RE.match(stem) or STAMP_NAME_RE.match(stem))


def best_sibling(fn, known):
    """The closest relative of fn among `known` (filename -> reference), or None.

    Related means one stem is the other's, or a prefix of it ending at a STEM_BREAKS character.
    Score is the shared length; a tie goes to the ancestor (what this was made FROM), then to the
    shorter name, then to name order, so the pick is the same every run."""
    t = os.path.splitext(fn)[0].lower()
    cands = []
    for k in known:
        if k == fn:
            continue
        s = os.path.splitext(k)[0].lower()
        if s == t:
            score, ancestor = len(s), True
        elif len(s) < len(t) and t.startswith(s) and t[len(s)] in STEM_BREAKS:
            score, ancestor = len(s), True
        elif len(t) < len(s) and s.startswith(t) and s[len(t)] in STEM_BREAKS:
            score, ancestor = len(t), False
        else:
            continue
        cands.append((-score, not ancestor, len(k), k.lower(), k))
    return min(cands)[-1] if cands else None


def last_frame(exe, jpg_dir, cache):
    """(path, time, has_gps, nframes) for the last frame by capture time in jpg_dir, or None when
    there is no such directory or nothing datable in it. Cached: several _Post-Processing/ can
    fall back to the same 01_Astro pool."""
    if jpg_dir is None:
        return None
    if jpg_dir in cache:
        return cache[jpg_dir]
    frames = [os.path.join(jpg_dir, f) for f in sorted(os.listdir(jpg_dir))
              if is_jpg(f) and not is_junk(f)]
    dates, _ = read_dates(exe, frames)
    dated = [p for p in frames if p in dates]
    res = None
    if dated:
        # Last by capture time, name as tiebreak -- the ordering create-diary uses.
        ref = max(dated, key=lambda p: (dates[p], os.path.basename(p)))
        _, gps = read_geo_time(exe, [ref])[ref]
        res = (ref, dates[ref].replace(microsecond=0), gps, len(dated))
    cache[jpg_dir] = res
    return res


def reference_file(exe, path):
    """--reference PATH, validated: (path, time, has_gps, 1)."""
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        sys.exit(f"--reference: no such file: {path}")
    dates, _ = read_dates(exe, [path])
    if path not in dates:
        sys.exit(f"--reference {path} carries no date to copy")
    _, gps = read_geo_time(exe, [path])[path]
    return (path, dates[path].replace(microsecond=0), gps, 1)


def plan_block(exe, folder, block, reference=None):
    """Everything this block needs written. Returns a dict:

      block, dirs: [ {ppdir, rel, ok, writes, originals, other, unresolved, ignored} ]

    `writes` entries are {f, path, t, gps_src, how}; gps_src is the file GPS is copied from, or
    None when the reference has none. `unresolved` is files with no sibling, no pool and no
    --reference -- reported, never guessed at.
    """
    bdir = os.path.join(folder, block)
    originals = block_originals(bdir)
    cache = {}

    listing = []
    for ppdir, cat in postproc_dirs(bdir):
        files = [f for f in sorted(os.listdir(ppdir))
                 if not is_junk(f) and os.path.isfile(os.path.join(ppdir, f))]
        listing.append((ppdir, cat, files))
    tags = read_geo_time(exe, [os.path.join(d, f) for d, _, fs in listing for f in fs
                               if ext_of(f) not in IGNORED_EXTS])

    dirs = []
    for ppdir, cat, files in listing:
        g = dict(ppdir=ppdir, rel=os.path.relpath(ppdir, bdir).replace('\\', '/'), cat=cat,
                 ok=[], writes=[], originals=[], other=[], unresolved=[], refs={},
                 ignored=[f for f in files if ext_of(f) in IGNORED_EXTS])
        known = {}          # filename -> (time, gps_src): what a sibling can be dated off
        missing = []
        for f in files:
            if ext_of(f) in IGNORED_EXTS:
                continue
            p = os.path.join(ppdir, f)
            t, gps = tags.get(p, (None, False))
            orig = is_original_copy(f, block, originals)
            if t and gps:
                g['ok'].append(f)
                known[f] = (t, p)
            elif orig and t:
                known[f] = (t, None)    # a real date, no GPS on this body: still the truth
                g['originals'].append(f)
            elif orig:
                g['originals'].append(f)
            else:
                missing.append(f)

        # Shortest name first: the keeper before its variants, so a variant can find the keeper
        # already planned and share its time.
        missing.sort(key=lambda f: (len(f), f.lower()))
        n = 0
        for f in missing:
            if ext_of(f) not in TAGGABLE_EXTS:
                g['other'].append(f)
                continue
            sib = best_sibling(f, known)
            if sib:
                t, gps_src = known[sib]
                how = f'sibling {sib}'
            else:
                ref, where = None, None
                if cat:
                    ref, where = last_frame(exe, pool_jpg_dir(bdir, cat), cache), cat
                if ref is None:
                    ref = last_frame(exe, pool_jpg_dir(bdir, CATEGORY_DEFAULT), cache)
                    where = CATEGORY_DEFAULT
                if ref is None and reference:
                    ref, where = reference, '--reference'
                if ref is None:
                    g['unresolved'].append(f)
                    continue
                n += 1
                path, ref_t, gps, nframes = ref
                g['refs'][where] = ref
                t = ref_t + datetime.timedelta(seconds=n)
                gps_src = path if gps else None
                how = f'{where} +{n}s'
            p = os.path.join(ppdir, f)
            g['writes'].append(dict(f=f, path=p, t=t, gps_src=gps_src, how=how))
            known[f] = (t, gps_src)
        dirs.append(g)
    return dict(block=block, dirs=dirs)


def unresolved_of(plan):
    return [(g['rel'], f) for g in plan['dirs'] for f in g['unresolved']]


def print_block(plan):
    print(f"{plan['block']}")
    if not plan['dirs']:
        print(f"  no {POSTPROC}/ in this block\n")
        return
    for g in plan['dirs']:
        print(f"  {g['rel']}/   {len(g['ok'])} already tagged")
        for where, (path, t, gps, nframes) in g['refs'].items():
            print(f"    reference {where}: {os.path.basename(path)} "
                  f"(last of {nframes}, {t:%Y-%m-%d %H:%M:%S})"
                  f"{'' if gps else '  -- no GPS on this body, time only'}")
        for w in g['writes']:
            gps = 'GPS+time' if w['gps_src'] else 'time only'
            print(f"    {w['t']:%Y-%m-%d %H:%M:%S}  {gps:<9}  {w['f']}   <- {w['how']}")
        for f in g['originals']:
            if f not in g['ok']:
                print(f"     --   left alone, a copy of an original frame: {f}")
        for f in g['other']:
            print(f"     --   left alone, not a taggable image: {f}")
        for f in g['unresolved']:
            print(f"     ??   NO REFERENCE: {f}")
    print()


def apply_block(exe, plan):
    """exiftool writes in place with -overwrite_original, per repo convention -- no _original
    litter is left beside the products. Returns (written, failed)."""
    written, failed = 0, []
    for g in plan['dirs']:
        for w in g['writes']:
            cmd = [exe, '-overwrite_original', '-q']
            if w['gps_src']:
                cmd += ['-tagsFromFile', w['gps_src'], '-gps:all']
            # Assignments come after the copy so they win. AllDates = DateTimeOriginal +
            # CreateDate + ModifyDate; the subsec is cleared so the whole-second order the
            # plan just laid out is the order anything reading these files sees.
            cmd += [f"-AllDates={w['t']:%Y:%m:%d %H:%M:%S}", '-SubSecTimeOriginal=', w['path']]
            out = subprocess.run(cmd, capture_output=True, text=True)
            if out.returncode != 0:
                failed.append((w['f'], (out.stderr or '').strip().splitlines()[:1]))
            else:
                written += 1
    return written, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('groups', nargs='+', metavar='group',
                    help='block directory name(s), e.g. '
                         '6I-0011-6dii-24mm-8s-f1.8-iso3200_sagittarius')
    ap.add_argument('--reference', metavar='PATH',
                    help='date anything with no sibling and no pool frame off this photo')
    ap.add_argument('--skip-unreferenced', action='store_true',
                    help='tag what can be dated and leave the rest alone (default: refuse)')
    ap.add_argument('--exiftool', help='path to exiftool, when it is not on PATH')
    ap.add_argument('--apply', action='store_true', help='write the tags (default: plan only)')
    args = ap.parse_args()

    exe, _ = find_exiftool(args.exiftool)
    folder = resolve_folder(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"folder not found: {folder}")
    blocks = block_dirs(folder)
    for grp in args.groups:
        if grp not in blocks or not is_block(grp):
            sys.exit(f"no group '{grp}' in {folder}. Groups there:\n  " +
                     ('\n  '.join(blocks) or '(none -- run organize-photo-folders first)'))
    reference = reference_file(exe, args.reference) if args.reference else None

    t0 = time.time()
    plans = [plan_block(exe, folder, grp, reference) for grp in args.groups]
    for p in plans:
        print_block(p)
    unresolved = [(p['block'], rel, f) for p in plans for rel, f in unresolved_of(p)]
    nwrites = sum(len(g['writes']) for p in plans for g in p['dirs'])
    if not nwrites and not unresolved:
        print("nothing to write: every file already carries GPS and a taken time")

    if unresolved:
        print(f"NEEDS A REFERENCE PHOTO — {len(unresolved)} file(s) have no similar sibling and "
              f"no frame in their category's or 01_Astro's _00Original/lights/JPG:")
        for blk, rel, f in unresolved:
            print(f"  {blk}/{rel}/{f}")
        print("  Ask which photo they should be dated from, then re-run with --reference <path>.")
        if not args.skip_unreferenced:
            sys.exit("\nrefusing to write (see above), or pass --skip-unreferenced to leave "
                     "those alone.")
    if args.apply:
        written, failed = 0, []
        for p in plans:
            w, f = apply_block(exe, p)
            written += w
            failed += f
        print(f"\ntagged {written} file(s)")
        for f, err in failed:
            print(f"  FAILED  {f}: {err}", file=sys.stderr)
    elif nwrites:
        print("\n(plan only -- re-run with --apply to write the tags)")
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
