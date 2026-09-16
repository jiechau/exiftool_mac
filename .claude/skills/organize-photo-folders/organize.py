#!/usr/bin/env python3
"""Re-block a shoot folder into <YM>-<nnnn>-<camera>-<focal>-<shutter>-<aperture>-<iso>/.

The first step on a card dump. Every photo under the shoot folder, at any depth, is pooled into
one capture-time stream and cut into blocks:

  set group        >= 3 consecutive frames sharing camera + focal + shutter + aperture + ISO,
                   shot at a fixed interval (an intervalometer run). Its name carries all five.
  scattered group  everything between two set groups. Its name carries only what every frame in
                   it agrees on -- the camera, then the focal length -- and stops at the first
                   field that differs.

Each block gets a working tree (see camera_lib.FULL_TEMPLATE), and every one of its photos lands
in 00_Original/{RAW,JPG}. That pool is the only thing this skill fills; 01_Astro/, 02_Landscape/,
03_Portraits/ and 04_tests/ are created empty for the owner to file into by hand, and are never
read back as a photo source.

Re-running is safe and is the point: a block already organized is recognised by its 00_Original/,
its photos come back out of there, and it is renumbered from scratch. Anything ELSE in an old
block -- a filed 01_Astro/lights/, a _CameraRaw0/, a _post-processing/ -- is parked under
_dangling/ with its original path intact first, because the block around it is about to be
renumbered and the path is the only record of where the work came from. Empty scaffolding from
the previous run is simply removed.

Never deletes a photo, never renames an original, never touches an original's EXIF.

The rules in full are in organize-photo-folders.md at the repo root.

Plan-only by default; pass --apply to move files.
"""
import argparse
import datetime
import fnmatch
import os
import re
import shutil
import subprocess
import sys
import time
from collections import OrderedDict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_shared'))
from camera_lib import (                                            # noqa: E402
    ORIGINAL, RAW_SUB, JPG_SUB, POSTPROC, DANGLING,
    RAW_EXTS, JPG_EXTS, PROTECTED_PREFIXES,
    FULL_TEMPLATE, MIN_TEMPLATE,
    find_exiftool, is_junk, is_photo, is_protected_root, make_tree, resolve_folder,
)

# Matched at any depth, and against a lower-cased name: the block collector is '_Post-Processing'
# and the shoot root's is '_post-processing_jpg', and older folders still carry the all-lower-case
# spelling -- one lower-cased compare covers the three. The underscore forms are already covered by
# the '_' rule; the underscore-LESS spelling is the one that would otherwise be walked into and
# have its photos absorbed.
POSTPROC_GLOBS = ('post-processing*', '_post-processing*')

CAMERA_SLUGS = {
    'Canon EOS 6D Mark II': '6dii',
    'Canon EOS 550D': '550d',
    'iPhone 15 Pro': 'iphone15pro',
}

MONTH_CODE = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'F',
              7: 'G', 8: 'H', 9: 'I', 10: 'J', 11: 'K', 12: 'L'}

TOL = 0.5        # seconds: interval jitter still counted as "fixed interval"
MIN_PHOTOS = 3   # a set group needs at least this many consecutive frames


# ---------------------------------------------------------------- naming helpers

def camera_slug(model):
    """'Canon EOS 6D Mark II' -> '6dii'; unknown models -> 'Canon_EOS_700D'.
    A body that shoots here often enough to be talked about by name belongs in the table."""
    if model in CAMERA_SLUGS:
        return CAMERA_SLUGS[model]
    return '_'.join(model.split()) or 'unknown'


def trim0(x):
    return x[:-2] if x.endswith('.0') else x


def fmt_focal(x):
    return trim0(x.replace(' mm', '').strip()) + 'mm' if x else 'unknownmm'


def fmt_shutter(x):
    # '8' -> '8s', '1/200' -> '1_200s'
    return (x.replace('/', '_') if '/' in x else trim0(x)) + 's'


def fmt_aperture(x):
    return 'f' + trim0(x)


def date_prefix(year, month):
    """2026-09 -> '6I': last digit of the year, then the month letter A..L."""
    return f"{year % 10}{MONTH_CODE[month]}"


def prefix_from_folder(folder):
    """The shoot folder is named YYYY_MMDD_camera_<place>; that date is the whole shoot's date,
    which is what we want -- a night crossing midnight must not change prefix."""
    m = re.match(r'(\d{4})_(\d{2})(\d{2})', os.path.basename(os.path.abspath(folder)))
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return date_prefix(y, mo) if 1 <= mo <= 12 else None


# ---------------------------------------------------------------- classification

def is_postproc(name):
    # fnmatch() alone would be case-INsensitive on Windows and case-sensitive on macOS, so
    # '_Post-Processing' would match on one platform and not the other. Lower-case it here.
    return any(fnmatch.fnmatchcase(name.lower(), g) for g in POSTPROC_GLOBS)


def protected_rel(rel):
    """True for a path the skill must not delete: anything under a top-level protected name, a
    '_' or '.' segment at any depth, or a post-processing* tree."""
    segs = rel.split(os.sep)
    return (is_protected_root(segs[0])
            or any(s.startswith(PROTECTED_PREFIXES) or is_postproc(s) for s in segs))


def tree_is_empty(path):
    """No file a person made, anywhere under path. OS litter does not count as content, so the
    empty scaffolding a previous run created is empty even with a .DS_Store sitting in it."""
    for _, _, files in os.walk(path):
        if any(not is_junk(f) for f in files):
            return False
    return True


# ---------------------------------------------------------------- one walk, one set of rules

def scan(folder):
    """Walk the shoot folder once and decide, for every directory in it, which of four it is.

    Returns (park, drop, sources) as folder-relative paths:
      park     holds something, and must not be walked into -> _dangling/<its own path>/
      drop     empty scaffolding from an earlier run -> removed
      sources  holds loose photos -> pooled and re-blocked

    The order of the tests below IS the rule set, and it is the same in plan mode and under
    --apply, so the plan is what actually happens:

      1. AT THE ROOT, every '_' and '.' name is the owner's staging -- _dangling/,
         _post-processing/, _00info/, _diary/, _tmp/ -- and so are 00info/ and *diary/. Never
         read, never moved. The underscore keeps its old meaning here: it protects. Below the
         root it means the opposite (rule 3), because down there it is work inside a block.
      2. a '.' name anywhere is the filesystem's -- .Trashes, .fseventsd. Skipped, never parked.
      3. a '_' name BELOW THE ROOT is hand-curated work sitting inside a block that is about to
         be renumbered: _CameraRaw0/, _post-processing/, _00info/. Parked, path preserved.
      4. inside an already-organized block -- one holding a 00_Original/ -- everything except
         00_Original/ is parked too. 01_Astro/lights/ is the owner's filing of a block whose
         number is about to change, and re-pooling it would silently undo that filing.
      5. anything else is a card dump, an old hand-made tree, a stray folder: walked into.
    """
    park, drop, sources = [], [], []
    root_abs = os.path.abspath(folder)
    for dirpath, dirnames, filenames in os.walk(folder):
        at_root = os.path.abspath(dirpath) == root_abs
        rel = '' if at_root else os.path.relpath(dirpath, folder)
        organized = os.path.isdir(os.path.join(dirpath, ORIGINAL))
        keep = []
        for d in sorted(dirnames):
            child = os.path.join(rel, d) if rel else d
            if at_root and (d.startswith(PROTECTED_PREFIXES) or is_protected_root(d)):
                continue                                                        # 1
            if d.startswith('.'):
                continue                                                        # 2
            if d.startswith('_') or is_postproc(d):                             # 3
                pass
            elif organized and d != ORIGINAL:                                   # 4
                pass
            else:
                keep.append(d)                                                  # 5
                continue
            (drop if tree_is_empty(os.path.join(dirpath, d)) else park).append(child)
        dirnames[:] = keep
        if not at_root and any(is_photo(f) for f in filenames):
            sources.append(rel)
    return park, drop, sources


# ---------------------------------------------------------------- _dangling

def merge_move(src, dst):
    """Move src onto dst. If dst already exists (a re-run parking the same tree again),
    merge into it file by file and report anything that could not be moved."""
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
        shutil.move(src, dst)
        return []
    clashes = []
    for name in sorted(os.listdir(src)):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isdir(s) and os.path.isdir(d):
            clashes += merge_move(s, d)
        elif os.path.exists(d):
            clashes.append(d)
        else:
            shutil.move(s, d)
    if not os.listdir(src):
        os.rmdir(src)
    return clashes


def prune_up(folder, rel):
    """Remove now-empty parents of a moved-away directory, stopping at the shoot root."""
    root = os.path.abspath(folder)
    d = os.path.dirname(os.path.abspath(os.path.join(folder, rel)))
    while d != root and d.startswith(root + os.sep):
        if os.path.isdir(d) and all(is_junk(f) for f in os.listdir(d)):
            for f in os.listdir(d):
                os.remove(os.path.join(d, f))
            os.rmdir(d)
        else:
            break
        d = os.path.dirname(d)


def park_dangling(folder, park, drop, apply):
    """<block>/01_Astro/lights -> _dangling/<block>/01_Astro/lights, path preserved.

    The path is the record of which block the work came from, and the block's number is about to
    change, so it is the only thing that survives the renumbering."""
    if park:
        plan = [(rel, os.path.join(DANGLING, rel)) for rel in park]
        print(f"{'parking' if apply else 'will park'} {len(plan)} "
              f"{'tree' if len(plan) == 1 else 'trees'} under {DANGLING}/:")
        for src, dst in plan:
            print(f"  {src}  ->  {dst}")
        sys.stdout.flush()
        clashes = []
        if apply:
            for rel, dst_rel in plan:
                clashes += merge_move(os.path.join(folder, rel), os.path.join(folder, dst_rel))
                prune_up(folder, rel)
        for c in clashes:
            print(f"  !! already in {DANGLING}/, left where it is: "
                  f"{os.path.relpath(c, folder)}", file=sys.stderr)
        print()

    if drop:
        # Empty scaffolding this skill created on an earlier run. Parking it would fill
        # _dangling/ with hundreds of empty directories on every re-run.
        print(f"{'removing' if apply else 'will remove'} {len(drop)} empty "
              f"{'directory' if len(drop) == 1 else 'directories'} "
              f"(scaffolding from an earlier run): "
              f"{', '.join(drop[:6])}{' ...' if len(drop) > 6 else ''}")
        if apply:
            for rel in drop:
                shutil.rmtree(os.path.join(folder, rel), ignore_errors=True)
                prune_up(folder, rel)
        print()


# ---------------------------------------------------------------- gathering

def find_pairs(folder, subdirs=()):
    """Photos at the top level of `folder`, plus any of `subdirs`, paired by basename.
    A .CR2 and a .JPG sharing a basename are one photo. Returns {base: {ext: relpath}}."""
    pairs = OrderedDict()
    for rel in ('.',) + tuple(subdirs):
        d = os.path.join(folder, rel)
        for fn in sorted(os.listdir(d)):
            if not os.path.isfile(os.path.join(d, fn)):
                continue
            base, _, ext = fn.rpartition('.')
            ext = ext.upper()
            if not base or not is_photo(fn):
                continue
            slot = pairs.setdefault(base, {})
            if ext in slot:   # same photo name in two source dirs -- never guess which wins
                sys.exit(f"same photo name in two places: {slot[ext]} and "
                         f"{os.path.normpath(os.path.join(rel, fn))} -- resolve by hand")
            slot[ext] = os.path.normpath(os.path.join(rel, fn))
    return pairs


def prune_source_dirs(folder, subdirs=(), keep_roots=()):
    """Sweep the whole tree bottom-up and remove every directory left holding nothing but OS junk
    -- the dirs this run emptied, and any an earlier run left behind. Bottom-up means
    DCIM/100MSDCF/ takes DCIM/ with it, and an old block goes once its 00_Original/ is gone.

    keep_roots are the block directories this run just wrote. Their scaffolding is empty ON
    PURPOSE -- 01_Astro/lights/RAW/ is there for the owner to file into -- so nothing under them
    is ever swept, or the run would delete the tree it just created."""
    removed, junked, kept, root_abs = [], [], [], os.path.abspath(folder)
    for dirpath, _, _ in os.walk(folder, topdown=False):
        if os.path.abspath(dirpath) == root_abs:
            continue
        rel = os.path.relpath(dirpath, folder)
        if protected_rel(rel) or rel.split(os.sep)[0] in keep_roots:
            continue
        entries = os.listdir(dirpath)
        if any(not is_junk(f) for f in entries):
            if rel in subdirs:      # only worth a note if we took photos out of it
                kept.append(rel)
            continue
        for f in entries:           # .DS_Store and friends, regenerable
            os.remove(os.path.join(dirpath, f))
            junked.append(os.path.join(rel, f))
        os.rmdir(dirpath)
        removed.append(rel)
    return removed, junked, kept


# ---------------------------------------------------------------- EXIF

def read_exif(exe, folder, pairs):
    """One exiftool call for the whole folder -- never one call per file. Reads the JPG of each
    pair when there is one: same shooting data as the raw, far faster to parse."""
    targets, base_of = [], {}
    for base, exts in pairs.items():
        pick = next((exts[e] for e in JPG_EXTS if e in exts), None) \
            or next((exts[e] for e in RAW_EXTS if e in exts), None)
        targets.append(pick)
        # exiftool -filename reports the bare name; find_pairs has already ruled out
        # the same name appearing in two source dirs, so this stays unambiguous.
        base_of[os.path.basename(pick)] = base
    if not targets:
        return []
    out = subprocess.run(
        [exe, '-q', '-T', '-filename', '-SubSecDateTimeOriginal', '-DateTimeOriginal',
         '-Model', '-FocalLength', '-ExposureTime', '-FNumber', '-ISO', '-@', '-'],
        input='\n'.join(os.path.join(folder, t) for t in targets),
        capture_output=True, text=True)
    rows, unreadable = [], []
    for line in out.stdout.splitlines():
        f = line.rstrip('\n').split('\t')
        if len(f) < 8:
            continue
        fn, subsec, dto, model, focal, exp, fnum, iso = f[:8]
        # SubSecDateTimeOriginal is what makes a fixed interval detectable at all: these are
        # 8-30s exposures, so consecutive frames are seconds apart on the clock alone.
        stamp = subsec if subsec != '-' else dto
        try:
            fmt = '%Y:%m:%d %H:%M:%S.%f' if '.' in stamp else '%Y:%m:%d %H:%M:%S'
            t = datetime.datetime.strptime(stamp.split('+')[0].strip(), fmt)
        except ValueError:
            unreadable.append(fn)
            continue
        rows.append(dict(base=base_of[fn], t=t, model=('' if model == '-' else model),
                         focal=('' if focal == '-' else focal), exp=exp, fnum=fnum, iso=iso))
    if unreadable:
        print(f"  warning: no usable DateTimeOriginal, skipped: {unreadable[:5]}"
              f"{' ...' if len(unreadable) > 5 else ''}", file=sys.stderr)
    rows.sort(key=lambda r: r['t'])
    return rows


# ---------------------------------------------------------------- grouping

def sig(r):
    """What a set group holds constant: the whole shooting signature, not just the body."""
    return (r['model'], r['focal'], r['exp'], r['fnum'], r['iso'])


def split_runs(rows):
    """Cut the time-sorted stream into set groups and the scattered stretches between them.

    A set group is >= MIN_PHOTOS consecutive frames that share a signature AND sit at a constant
    interval. Both tests matter: the signature is what makes the directory name true of every
    frame in it, and the interval is what says an intervalometer was running rather than someone
    firing by hand at the same settings.

    Every delta in a run is compared against the run's FIRST delta, not its predecessor, so a
    slow drift cannot creep a run along one jittery frame at a time.
    """
    n = len(rows)
    if n == 0:
        return []
    deltas = [(rows[i + 1]['t'] - rows[i]['t']).total_seconds() for i in range(n - 1)]
    sigs = [sig(r) for r in rows]
    locked, i = [], 0
    while i < n - 1:
        if sigs[i + 1] != sigs[i]:      # deltas[i] spans two frames; both must match
            i += 1
            continue
        j = i
        # extending to deltas[j+1] pulls in rows[j+2], so that frame has to match too
        while (j + 1 < n - 1 and sigs[j + 2] == sigs[i]
               and abs(deltas[j + 1] - deltas[i]) <= TOL):
            j += 1
        if (j + 1 - i + 1) >= MIN_PHOTOS:
            locked.append((i, j + 1, deltas[i]))
            i = j + 2          # photo j+1 closed the run; the next block starts after it
        else:
            i = j + 1
    runs, cur = [], 0
    for a, b, iv in locked:
        if a > cur:
            runs.append(dict(kind='scattered', a=cur, b=a - 1, iv=None))
        runs.append(dict(kind='group', a=a, b=b, iv=iv))
        cur = b + 1
    if cur < n:
        runs.append(dict(kind='scattered', a=cur, b=n - 1, iv=None))
    return runs


def scattered_leaf(name, rows):
    """A scattered group's name carries only what EVERY frame in it agrees on.

    Camera first, then focal length, stopping at the first field that differs -- so a stretch shot
    entirely on the 550d at mixed focal lengths is `6I-0014-550d`, and one that spans two bodies
    is a bare `6I-0015`. Settings are never in the name: a scattered group has none to speak of,
    which is why it is scattered."""
    if len({r['model'] for r in rows}) != 1:
        return name
    leaf = f"{name}-{camera_slug(rows[0]['model'])}"
    if len({r['focal'] for r in rows}) != 1:
        return leaf
    return f"{leaf}-{fmt_focal(rows[0]['focal'])}"


def build_plan(rows, prefix, start):
    """Cut one time-ordered stream into blocks and number them <prefix>-<start>.., in that order.

    There is no per-camera pass: two bodies shooting the same night interleave in real time, and
    the block numbers follow the night, not the equipment. A body of its own still ends up in its
    own blocks, because the model is part of the signature a set group holds constant."""
    plan = []
    for k, run in enumerate(split_runs(rows)):
        brows = rows[run['a']:run['b'] + 1]
        first = brows[0]
        name = f"{prefix}-{start + k:04d}"
        if run['kind'] == 'group':
            # Every frame shares these by construction, so the first photo's are the group's.
            leaf = (f"{name}-{camera_slug(first['model'])}-{fmt_focal(first['focal'])}"
                    f"-{fmt_shutter(first['exp'])}-{fmt_aperture(first['fnum'])}"
                    f"-iso{first['iso']}")
        else:
            leaf = scattered_leaf(name, brows)
        plan.append(dict(name=name, kind=run['kind'], iv=run['iv'], dest=leaf,
                         bases=[r['base'] for r in brows],
                         t0=brows[0]['t'].strftime('%m-%d %H:%M:%S'),
                         t1=brows[-1]['t'].strftime('%m-%d %H:%M:%S'),
                         models=sorted({camera_slug(r['model']) for r in brows}),
                         focals=sorted({fmt_focal(r['focal']) for r in brows})))
    return plan


def print_plan(plan, pairs):
    print(f"{'BLOCK':<9} {'TYPE':<9} {'N':>4} {'IVL':>7}  {'SPAN':<28} DEST")
    for p in plan:
        n = len(p['bases'])
        iv = f"{p['iv']:.2f}s" if p['iv'] else '-'
        print(f"{p['name']:<9} {p['kind']:<9} {n:>4} {iv:>7}  "
              f"{p['t0']} -> {p['t1']}  {p['dest']}/{ORIGINAL}")
        # A set group cannot be mixed -- the signature is a grouping key. A scattered one can be,
        # and the name says so by leaving the field out; spell out what it left out.
        if p['kind'] == 'scattered' and len(p['models']) > 1:
            print(f"        -- spans {len(p['models'])} bodies {p['models']}, "
                  f"so the name carries no camera")
        elif p['kind'] == 'scattered' and len(p['focals']) > 1:
            print(f"        -- mixed focal lengths {p['focals']}, "
                  f"so the name stops at the camera")
    groups = sum(1 for p in plan if p['kind'] == 'group')
    print(f"\n{len(plan)} blocks ({groups} groups, {len(plan) - groups} scattered-groups), "
          f"{sum(len(p['bases']) for p in plan)} photos, "
          f"{sum(len(v) for v in pairs.values())} files")
    print(f"每個 block 都會建好工作目錄：group 給完整的 {len(FULL_TEMPLATE)} 層，"
          f"scattered 給最小的 {len(MIN_TEMPLATE)} 層；照片一律進 {ORIGINAL}/{{{RAW_SUB},{JPG_SUB}}}。")


# ---------------------------------------------------------------- apply

def apply_plan(folder, plan, pairs, source_dirs=(), keep_source=False):
    moves = 0
    for p in plan:
        # The scaffolding comes first and in full, so a block looks the same whether or not it
        # happened to hold a raw file: 00_Original/RAW/ exists even for a JPEG-only group.
        make_tree(os.path.join(folder, p['dest']), p['kind'])
        for base in p['bases']:
            for ext, sub in ([(e, RAW_SUB) for e in RAW_EXTS]
                             + [(e, JPG_SUB) for e in JPG_EXTS]):
                fn = pairs.get(base, {}).get(ext)
                if not fn:
                    continue
                dst = os.path.join(folder, p['dest'], ORIGINAL, sub, os.path.basename(fn))
                src = os.path.join(folder, fn)
                if os.path.abspath(src) == os.path.abspath(dst):
                    continue          # re-run: already where the plan wants it
                if os.path.exists(dst):
                    print(f"  skip, destination exists: {dst}", file=sys.stderr)
                    continue
                shutil.move(src, dst)
                moves += 1
    keep_roots = {p['dest'] for p in plan}
    removed, junked, kept = ([], [], list(source_dirs)) if keep_source \
        else prune_source_dirs(folder, source_dirs, keep_roots)
    return moves, removed, junked, kept


def main():
    ap = argparse.ArgumentParser(
        description='Re-block a shoot folder into <YM>-<nnnn>-... directories.')
    ap.add_argument('folder')
    ap.add_argument('start', nargs='?', type=int, default=1,
                    help='first block number, 4-digit padded (default: 1 -> 0001)')
    ap.add_argument('--prefix', help="override the <year-digit><month-letter> prefix, e.g. 6I")
    ap.add_argument('--exiftool', help='path to exiftool, when it is not on PATH')
    ap.add_argument('--apply', action='store_true', help='move files (default: plan only)')
    ap.add_argument('--keep-source', action='store_true',
                    help='do not delete an absorbed source directory once it is empty')
    args = ap.parse_args()

    # Rule 0: exiftool has to exist and run, and the folder has to exist.
    exe, ver = find_exiftool(args.exiftool)
    folder = resolve_folder(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"folder not found: {folder}")
    if args.start < 0:
        sys.exit(f"start number must not be negative: {args.start}")

    prefix = args.prefix or prefix_from_folder(folder)

    t0 = time.time()
    # One walk decides everything: what gets parked, what gets dropped, where the photos are.
    park, drop, source_dirs = scan(folder)
    if park or drop:
        park_dangling(folder, park, drop, args.apply)

    pairs = find_pairs(folder, source_dirs)
    if source_dirs:
        print(f"absorbing {len(source_dirs)} "
              f"{'subdirectory' if len(source_dirs) == 1 else 'subdirectories'}: "
              f"{', '.join(source_dirs[:8])}{' ...' if len(source_dirs) > 8 else ''}"
              f"{'' if args.keep_source else '  (emptied ones removed)'}\n")
    if not pairs:
        sys.exit(f"no photos in {folder} outside the protected names "
                 f"(wrong folder, or nothing left to sort)")
    rows = read_exif(exe, folder, pairs)
    if not rows:
        sys.exit("no photos with a readable DateTimeOriginal")

    if not prefix:      # folder name did not carry YYYY_MMDD -- fall back to the first photo
        prefix = date_prefix(rows[0]['t'].year, rows[0]['t'].month)
        print(f"note: '{os.path.basename(os.path.abspath(folder))}' has no YYYY_MMDD date; "
              f"prefix {prefix} taken from the first photo ({rows[0]['t'].date()})\n",
              file=sys.stderr)

    plan = build_plan(rows, prefix, args.start)
    print(f"prefix {prefix}, numbering from {args.start:04d}  (exiftool {ver} at {exe})\n")
    print_plan(plan, pairs)

    if args.apply:
        moves, removed, junked, kept = apply_plan(
            folder, plan, pairs, source_dirs, args.keep_source)
        # A photo already in the block the plan wants is not "loose", and a block dir still
        # full of its own photos is not a source dir worth reporting as kept.
        leaves = {os.path.abspath(os.path.join(folder, p['dest'], ORIGINAL, sub))
                  for p in plan for sub in (RAW_SUB, JPG_SUB)}
        kept = [k for k in kept if os.path.abspath(os.path.join(folder, k)) not in leaves]
        left = 0
        for rel in ['.'] + source_dirs:
            d = os.path.join(folder, rel)
            if not os.path.isdir(d) or os.path.abspath(d) in leaves:
                continue
            left += sum(1 for f in os.listdir(d)
                        if os.path.isfile(os.path.join(d, f)) and is_photo(f))
        print(f"\nmoved {moves} files; {left} photo files left outside a block")
        if removed:
            print(f"removed emptied source {'dir' if len(removed) == 1 else 'dirs'}: "
                  f"{', '.join(removed)}")
        if junked:
            print(f"deleted {len(junked)} OS junk "
                  f"{'file' if len(junked) == 1 else 'files'} with them: "
                  f"{', '.join(junked[:5])}{' ...' if len(junked) > 5 else ''}")
        for rel in kept:
            if not args.keep_source:
                print(f"  kept {rel}/: not empty after the move -- left untouched",
                      file=sys.stderr)
    else:
        print("\n(plan only -- re-run with --apply to move files)")
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
