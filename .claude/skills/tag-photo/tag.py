#!/usr/bin/env python3
"""Stamp each _post-processing/ output with the place and time of the frames it was made from.

A stacked TIF that came out of Sequator carries no EXIF worth having: no GPS, and whatever date
the stacker felt like writing. The frames it was made from carry both.

A block has up to four _post-processing/ directories and each is dated off ITS OWN frames:

  <block>/01_Astro/_post-processing/       <- 01_Astro/lights/JPG
  <block>/02_Landscape/_post-processing/   <- 02_Landscape/lights/JPG
  <block>/03_Portraits/_post-processing/   <- 03_Portraits/lights/JPG
  <block>/_post-processing/                <- 00_Original/JPG

The reference is the LAST frame by capture time -- the moment that run finished -- and every
product then sits at +1s, +2s, ... A category with a _post-processing/ but nothing in its
lights/JPG has no run to date against, and nothing is borrowed from a sibling category or another
block to fill the gap: the run stops and asks for a reference frame, which is then passed back in
with --reference '<block>/<category>=<path>'.

The order the seconds are handed out in is BY FILENAME LENGTH, shortest first. That is not
arbitrary: the finished piece gets the plain name (..._thor.jpg), and every variant hangs a
suffix off it (..._thor_milkyway.png, ..._thor_SequatorStacking30.tif). Sorting by length
therefore puts the keeper first and its variants behind it, which is the order they want to
be read in.

A file in a _post-processing/ that is just a copy of an original frame -- IMG_0046.JPG, or
6H-0050-..._IMG_0148.JPG -- is NOT post-processing output and is left completely alone. It
already carries the camera's own GPS and timestamp, and overwriting those would be a lie.

Nothing outside a _post-processing/ is ever written -- not 00_Original/, not lights/, not darks/.

Idempotent by construction: the time is always recomputed as <last reference frame> + N, read
fresh every run, never from the target's current tags. Run it twice and the second run writes
exactly what the first one did -- the seconds cannot drift.

Finally every one of those directories is copied up into the shoot folder's root
_post-processing/. That copy is ADDITIVE: the root folder is hand-curated and nothing in it
is ever deleted or overwritten with different content.

The block layout this reads is written down in organize-photo-folders.md at the repo root.

Plan-only by default; pass --apply to write.
"""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_shared'))
from camera_lib import (                                            # noqa: E402
    CATEGORIES, DANGLING, JPG_SUB, LIGHTS, ORIGINAL, POSTPROC, POSTPROC_ROOT,
    block_dirs, find_exiftool, is_group, is_junk, is_jpg, read_dates, resolve_folder,
)

# What a post-processing product can be. Anything else in _post-processing/ is reported and
# left alone -- notably video: QuickTime stores dates in UTC and needs -api QuickTimeUTC, a
# trap this skill stays out of entirely rather than getting subtly wrong.
TAGGABLE_EXTS = ('.TIF', '.TIFF', '.JPG', '.JPEG', '.PNG')

# Names that are a camera's own, not something a person exported: IMG_0046, _MG_1234,
# DSC01234, and the iPhone's '2026-08-18 22.35.21'. Used only as a fallback -- the real test
# is whether the block still holds a file by that name.
CAMERA_NAME_RE = re.compile(r'^(?:IMG|_MG|DSC|DSCN|PICT|P)_?\d{3,}$', re.I)
STAMP_NAME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[ _T]\d{2}[.:-]\d{2}[.:-]\d{2}')


def has_gps(exe, path):
    """Whether the reference frame carries GPS at all. The 550d does not; the 6dii does."""
    out = subprocess.run([exe, '-q', '-T', '-GPSLatitude', '-GPSLongitude', path],
                         capture_output=True, text=True)
    f = out.stdout.strip().split('\t')
    return len(f) >= 2 and all(v not in ('', '-') for v in f[:2])


def block_originals(block_dir):
    """Every filename the block holds OUTSIDE any _post-processing/ -- 00_Original/, the
    categories' lights/ and darks/, 04_tests/. A _post-processing/ entry matching one of these is
    a copy of an original frame, not something that was exported."""
    names = set()
    for root, dirs, files in os.walk(block_dir):
        dirs[:] = [d for d in dirs if d != POSTPROC]
        for f in files:
            names.add(f.lower())
    return names


def is_original_copy(fn, block, originals):
    """Is this _post-processing/ entry just a copy of one of the block's own frames?

    Two ways it can be. Either the block still holds a file by that name -- after stripping a
    '<block>_' prefix, which is how the owner labels a frame they pulled out to work on --
    or the bare name is plainly a camera's own (IMG_0148) rather than anything exported.
    """
    lower = fn.lower()
    if lower in originals:
        return True
    stripped = fn
    prefix = block + '_'
    if fn.lower().startswith(prefix.lower()):
        stripped = fn[len(prefix):]
        if stripped.lower() in originals:
            return True
    stem = os.path.splitext(stripped)[0]
    return bool(CAMERA_NAME_RE.match(stem) or STAMP_NAME_RE.match(stem))


def find_groups(folder):
    """(groups, scattered, unorganized) -- group dirs carrying settings, in block order."""
    groups, scattered = [], []
    names = block_dirs(folder)
    for name in names:
        (groups if is_group(name) else scattered).append(name)
    return groups, scattered, not names


def targets_for(folder, block):
    """Every _post-processing/ in a block, paired with the frames that date it.

    Returns [(key, ppdir, refdir, label)]. `key` is what --reference addresses: the bare block
    name for the block's own collector, '<block>/<category>' for a category's.
    """
    bdir = os.path.join(folder, block)
    out = []
    pp = os.path.join(bdir, POSTPROC)
    if os.path.isdir(pp):
        # The block's own collector has no sibling lights/ -- the pool it was cut from is the
        # closest thing it has to a run, and it is always there.
        out.append((block, pp, os.path.join(bdir, ORIGINAL, JPG_SUB),
                    f'{ORIGINAL}/{JPG_SUB}'))
    for cat in CATEGORIES:
        pp = os.path.join(bdir, cat, POSTPROC)
        if os.path.isdir(pp):
            out.append((f'{block}/{cat}', pp, os.path.join(bdir, cat, LIGHTS, JPG_SUB),
                        f'{cat}/{LIGHTS}/{JPG_SUB}'))
    return out


def parse_references(specs):
    """--reference '<block>/<category>=<path>' -> {key: path}, validated up front."""
    refs = {}
    for spec in specs or ():
        key, sep, path = spec.partition('=')
        if not sep or not key.strip() or not path.strip():
            sys.exit(f"--reference wants '<block>[/<category>]=<path>', got: {spec}")
        path = os.path.expanduser(path.strip())
        if not os.path.isfile(path):
            sys.exit(f"--reference {key.strip()}: no such file: {path}")
        refs[key.strip().rstrip('/')] = path
    return refs


def build_plan(exe, folder, groups, refs):
    """One entry per _post-processing/ that has something in it to stamp.

    Returns (plan, notes, unresolved). `unresolved` is the targets with nothing to date them
    against -- reported, never guessed at.
    """
    plan, notes, unresolved = [], [], []
    for block in groups:
        originals = block_originals(os.path.join(folder, block))
        for key, ppdir, refdir, label in targets_for(folder, block):
            entries = [f for f in sorted(os.listdir(ppdir))
                       if not is_junk(f) and os.path.isfile(os.path.join(ppdir, f))]
            if not entries:
                continue                      # empty scaffolding, nothing to date or copy

            if key in refs:
                ref, reflabel, nframes = refs[key], '--reference', 1
            else:
                frames = ([os.path.join(refdir, f) for f in sorted(os.listdir(refdir))
                           if is_jpg(f) and not is_junk(f)]
                          if os.path.isdir(refdir) else [])
                dates, _ = read_dates(exe, frames)
                dated = [p for p in frames if p in dates]
                if not dated:
                    unresolved.append((key, label, len(entries)))
                    continue
                # Last by capture time, name as tiebreak -- the ordering create-diary uses.
                ref = max(dated, key=lambda p: (dates[p], os.path.basename(p)))
                reflabel, nframes = label, len(dated)
            rdates, _ = read_dates(exe, [ref])
            if ref not in rdates:
                unresolved.append((key, f'{reflabel} (unreadable date)', len(entries)))
                continue
            ref_t = rdates[ref].replace(microsecond=0)

            products, skipped, other = [], [], []
            for f in entries:
                if is_original_copy(f, block, originals):
                    skipped.append(f)
                elif f.upper().endswith(TAGGABLE_EXTS):
                    products.append(f)
                else:
                    other.append(f)
            # Shortest name first: the keeper, then its variants. Name breaks a tie, so a .jpg
            # and its equally-named .tif always land in the same order.
            products.sort(key=lambda f: (len(f), f.lower()))
            gps = has_gps(exe, ref)
            if not gps:
                notes.append(f"{key}: {os.path.basename(ref)} carries no GPS "
                             f"(this body does not record it) -- time only, no location written")
            plan.append(dict(key=key, block=block, ppdir=ppdir, ref=ref, reflabel=reflabel,
                             ref_t=ref_t, gps=gps, nframes=nframes, skipped=skipped, other=other,
                             products=[(f, ref_t + datetime.timedelta(seconds=i + 1))
                                       for i, f in enumerate(products)]))
    return plan, notes, unresolved


def plan_root_copies(folder, plan):
    """Every block _post-processing/ file, mapped into the root _post-processing/.

    Additive: the root folder is hand-curated and nothing in it is ever deleted. A name
    already there with DIFFERENT content, exported by a second block, is a genuine clash and
    is reported rather than overwritten -- that is the one case a file does not get copied.

    A product this run is about to stamp is ALWAYS copied. Its bytes change under exiftool a
    moment from now, so comparing it against the root copy here -- before the stamp -- would
    match on the pre-stamp file and skip the very files the run exists to refresh. Only the
    files this run leaves untouched (copies of originals, and anything untaggable) are worth
    testing for freshness, and for those the test is valid because nothing rewrites them.
    """
    root = os.path.join(folder, POSTPROC_ROOT)
    copies, clashes, claimed = [], [], {}
    for g in plan:
        products = {f for f, _ in g['products']}
        for f in sorted(os.listdir(g['ppdir'])):
            src = os.path.join(g['ppdir'], f)
            if is_junk(f) or not os.path.isfile(src):
                continue
            if os.path.abspath(os.path.dirname(src)) == os.path.abspath(root):
                continue                              # the root collector is not its own source
            dst = os.path.join(root, f)
            owner = claimed.get(f)
            if owner is not None:                     # two blocks, one name
                clashes.append((f, owner, g['key']))
                continue
            claimed[f] = g['key']
            if f in products:
                copies.append((src, dst, g['key'], 'stamped'))
            elif not os.path.isfile(dst):
                copies.append((src, dst, g['key'], 'new'))
            else:
                s, d = os.stat(src), os.stat(dst)
                if s.st_size == d.st_size and int(s.st_mtime) == int(d.st_mtime):
                    continue                          # already there, unchanged
                copies.append((src, dst, g['key'], 'replace'))
    return root, copies, clashes


def print_plan(plan, notes, scattered, unresolved, root, copies, clashes):
    print(f"STAMP — each {POSTPROC}/ gets the place and time of its own frames\n")
    for g in plan:
        gps = 'GPS+time' if g['gps'] else 'time only (no GPS on this body)'
        print(f"{g['key']}")
        print(f"  reference: {g['reflabel']}/{os.path.basename(g['ref'])} "
              f"(last of {g['nframes']} frames, {g['ref_t']:%Y-%m-%d %H:%M:%S})  ->  {gps}")
        for f, t in g['products']:
            print(f"    +{(t - g['ref_t']).seconds}s  {t:%H:%M:%S}  {f}")
        for f in g['skipped']:
            print(f"     --   left alone, a copy of an original frame: {f}")
        for f in g['other']:
            print(f"     --   left alone, not a taggable image: {f}")
        print()

    if not any(g['products'] for g in plan):
        print("nothing to stamp: no post-processing product found\n")

    if unresolved:
        print(f"NEEDS A REFERENCE FRAME — {len(unresolved)} directory(s) hold work but have no "
              f"frames to date it against:")
        for key, label, n in unresolved:
            print(f"  {key}   ({n} file(s) waiting; {label} is empty)")
        print("  Nothing is borrowed from another category or block to fill this in. Ask which "
              "photo each should be dated from, then re-run adding:")
        for key, _, _ in unresolved:
            print(f"    --reference '{key}=<path to a frame>'")
        print()

    if scattered:
        print(f"scattered-groups, no settings and so no run to date against — skipped: "
              f"{', '.join(scattered)}\n")
    for n in notes:
        print(f"  note: {n}")
    if notes:
        print()

    print(f"COPY UP — into {POSTPROC_ROOT}/ at the shoot root ({len(copies)} files)")
    if not os.path.isdir(root):
        print(f"  {POSTPROC_ROOT}/ does not exist yet and will be created")
    for _, dst, key, how in copies:
        print(f"  {how:<7} {os.path.basename(dst)}   <- {key}")
    if not copies:
        print("  nothing to copy (everything is already there, unchanged)")
    for f, a, b in clashes:
        print(f"  CLASH   {f}: both {a} and {b} export this name — NOT copied, rename one")


def apply_plan(exe, plan, copies):
    """Stamp, then copy up. exiftool writes in place with -overwrite_original, per repo
    convention -- no _original litter is left beside the products."""
    stamped, failed = 0, []
    for g in plan:
        for f, t in g['products']:
            path = os.path.join(g['ppdir'], f)
            cmd = [exe, '-overwrite_original', '-q']
            if g['gps']:
                cmd += ['-tagsFromFile', g['ref'], '-gps:all']
            # Assignments come after the copy so they win. AllDates = DateTimeOriginal +
            # CreateDate + ModifyDate; the subsec is cleared so the whole-second order the
            # plan just laid out is the order anything reading these files sees.
            cmd += [f"-AllDates={t:%Y:%m:%d %H:%M:%S}", '-SubSecTimeOriginal=', path]
            out = subprocess.run(cmd, capture_output=True, text=True)
            if out.returncode != 0:
                failed.append((f, (out.stderr or '').strip().splitlines()[:1]))
            else:
                stamped += 1

    copied = 0
    for src, dst, _, _ in copies:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return stamped, failed, copied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--reference', action='append', metavar='KEY=PATH',
                    help="date one directory off this frame instead: "
                         "'<block>/<category>=<path>', or '<block>=<path>' for the block's own "
                         "_post-processing/. Repeatable.")
    ap.add_argument('--skip-unreferenced', action='store_true',
                    help='stamp what can be dated and leave the rest alone (default: refuse)')
    ap.add_argument('--exiftool', help='path to exiftool, when it is not on PATH')
    ap.add_argument('--apply', action='store_true',
                    help='write the tags and copy up (default: plan only)')
    args = ap.parse_args()

    exe, _ = find_exiftool(args.exiftool)
    folder = resolve_folder(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"folder not found: {folder}")
    refs = parse_references(args.reference)

    t0 = time.time()
    groups, scattered, unorganized = find_groups(folder)
    if unorganized:
        sys.exit(f"{folder} holds no block directory (expected names like "
                 f"6H-0050-6dii-24mm-8s-f2.8-iso800) -- it has not been organized yet. "
                 f"Run organize-photo-folders on it first.")
    if not groups:
        sys.exit(f"{folder} is organized but holds no *group* (a name carrying -iso<n>); "
                 f"only scattered-groups: {', '.join(scattered)}. Nothing to tag.")

    plan, notes, unresolved = build_plan(exe, folder, groups, refs)
    # Post-processing work organize-photo-folders parked out of the way when it renumbered the
    # folder. It is not in a block, so nothing here can date it -- but it is exactly the kind of
    # thing that gets forgotten, so say it is sitting there.
    dangling = os.path.join(folder, DANGLING)
    if os.path.isdir(dangling) and os.listdir(dangling):
        notes.append(f"{DANGLING}/ is not empty -- organize-photo-folders parked work there. "
                     f"Nothing in it belongs to a block, so it is not tagged; move it back into "
                     f"the right block's {POSTPROC}/ and re-run to pick it up")
    if not plan and not unresolved:
        sys.exit(f"no group in {folder} has anything in a {POSTPROC}/ -- nothing to do")
    root, copies, clashes = plan_root_copies(folder, plan)
    print_plan(plan, notes, scattered, unresolved, root, copies, clashes)

    if unresolved and not args.skip_unreferenced:
        sys.exit(f"\nrefusing to write: {len(unresolved)} directory(s) need a reference frame "
                 f"(see above). Ask which photo to use and re-run with --reference, or pass "
                 f"--skip-unreferenced to leave them alone.")
    if args.apply:
        stamped, failed, copied = apply_plan(exe, plan, copies)
        print(f"\nstamped {stamped} file(s); copied {copied} file(s) up into {POSTPROC_ROOT}/")
        for f, err in failed:
            print(f"  FAILED  {f}: {err}", file=sys.stderr)
    else:
        print("\n(plan only -- re-run with --apply to write the tags and copy up)")
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
