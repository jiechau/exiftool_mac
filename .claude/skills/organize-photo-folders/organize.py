#!/usr/bin/env python3
"""Group a shoot folder of astro photos into
<YM>-<nnnn>-<camera>[-<focal>-<shutter>-<aperture>-<iso>]/lights/{jpg,raw}.

Walks the shoot root and every subdirectory under it, at any depth, and re-blocks the whole
thing from scratch. Idempotent by construction: no log, no manifest, no undo -- run it again
and it simply re-reads the folder and rebuilds the layout.

Frames land under lights/ because that is what they are: the calibration frames a stack also
needs -- darks/, flats/, bias/ -- are sorted out by hand afterwards, and this skill knows
nothing about them. It re-blocks whatever it finds, so a hand-made darks/ is pulled back into
lights/ on the next run and has to be moved out again; that is expected, not a malfunction.

A directory whose name starts with `_` is skipped at every depth -- the one exception being a
post-processing tree below the root, `_post-processing*` included, which is parked, path and
all, under _dangling/ before the photo walk starts. The root's own _post-processing/ stays.
"""
import argparse, datetime, fnmatch, os, re, shutil, subprocess, sys, time
from collections import Counter, OrderedDict

RAW_EXTS = ('CR2', 'CR3', 'NEF', 'ARW', 'DNG', 'RAF', 'ORF', 'PEF', 'RW2')
JPG_EXTS = ('JPG', 'JPEG')

# A leading underscore means "hand-curated" AT EVERY DEPTH: _tmp/, _dangling/, _diary/,
# _info/ (the name 00info/ used to carry) at the root, and a _post-processing/ sitting inside
# an already-organized block. None of them is entered, read for photos, or removed.
PROTECTED_PREFIXES = ('.', '_')         # dot-names too: .Trashes, .fseventsd, .DS_Store's kin
# Protected names WITHOUT a leading underscore, recognised ONLY at the top level of the shoot
# folder. Deeper down these mean nothing -- a nested 00info/ is just another directory full of
# photos and gets flattened like the rest.
PROTECTED_ROOT = {'00info'}
PROTECTED_ROOT_GLOBS = ('*diary',)      # diary, my-diary ... (_diary is covered by the '_')

LIGHTS = 'lights'                       # every block's frames are light frames until sorted;
                                        # darks/, flats/, bias/ are the owner's to make by hand
DANGLING = '_dangling'                  # where post-processing* trees are parked
# Matched at any depth, root included. The underscore form counts too: below the root a
# post-processing tree is parked whatever it is called, because the block directory around it
# is about to be renumbered and the tree would end up inside the wrong block. At the root the
# usual underscore rule wins and _post-processing/ is the owner's own, left alone.
POSTPROC_GLOBS = ('post-processing*', '_post-processing*')

# OS metadata the filesystem regenerates on its own. It never counts as content, so a source
# directory holding nothing else is still "emptied" and gets removed along with it. Anything
# a person made -- a .txt, a .tif stack, a stray photo -- is content and saves the directory.
JUNK_FILES = {'.DS_Store', 'Thumbs.db', 'desktop.ini', '.localized'}
JUNK_PREFIXES = ('._',)                 # AppleDouble sidecars

CAMERA_SLUGS = {
    'Canon EOS 6D Mark II': '6dii',
    'Canon EOS 550D': '550d',
    'iPhone 15 Pro': 'iphone15pro',
}

MONTH_CODE = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'F',
              7: 'G', 8: 'H', 9: 'I', 10: 'J', 11: 'K', 12: 'L'}

TOL = 0.5        # seconds: interval jitter still counted as "fixed interval"
MIN_PHOTOS = 3   # a group needs at least this many consecutive fixed-interval photos


# ---------------------------------------------------------------- where the photos are

# 這個 skill 住在 exiftool_mac repo 裡，照片不在。照片在 UltraFit256 上的 camera_latest，
# 路徑就是 go.sh 同步時用的 $dest_camera_dir_base，同一份 config，不另外開一個 key。
CONFIG_VAR = 'dest_camera_dir_base'         # config/config_vars.txt
CONFIG_ENV = 'CAMERA_LATEST_DIR'            # 臨時換一顆碟時用
SENTINEL = 'it_exists.txt'                  # 掛載證明，整個 repo 都靠它擋隨身碟沒插的情況


def camera_latest_dir():
    """$dest_camera_dir_base out of the repo's config/config_vars.txt, or $CAMERA_LATEST_DIR.
    Returns None if neither is set -- the caller says what that means."""
    env = os.environ.get(CONFIG_ENV)
    if env:
        return os.path.expanduser(env.rstrip('/'))
    # <repo>/.claude/skills/<skill>/<this file> -> <repo>
    repo = os.path.abspath(__file__)
    for _ in range(4):
        repo = os.path.dirname(repo)
    try:
        with open(os.path.join(repo, 'config', 'config_vars.txt')) as fh:
            for line in fh:
                key, _, val = line.partition('=')
                if key.strip() == CONFIG_VAR:
                    return os.path.expanduser(val.strip().rstrip('/'))
    except OSError:
        pass
    return None


def resolve_folder(arg):
    """A shoot folder is named, not pathed: `2026_0818_camera_jilong_dwl_parking`.

    An absolute path, or a relative one that exists from the cwd, is taken as given -- so
    running this from inside camera_latest still works. Anything else is a bare shoot-folder
    name and gets looked up under camera_latest."""
    arg = arg.rstrip('/')
    if os.path.isabs(arg) or os.path.isdir(arg):
        return arg
    base = camera_latest_dir()
    if not base:
        sys.exit(f"no {CONFIG_VAR} in config/config_vars.txt and no ${CONFIG_ENV} set; "
                 f"cannot tell where '{arg}' lives -- pass a full path instead")
    # 隨身碟沒掛載時，掛載點還是解析得出來，只是空的。sentinel 不在就是沒掛載。
    if not os.path.isfile(os.path.join(base, SENTINEL)):
        sys.exit(f"{base} has no {SENTINEL}: the UltraFit256 drive looks unmounted "
                 f"(or {CONFIG_VAR} points somewhere else). Refusing to touch '{arg}'")
    return os.path.join(base, arg)


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
    """The shoot folder is named YYYY_MMDD_camera_<place>; that date is the whole shoot's
    date, which is what we want -- a night crossing midnight must not change prefix."""
    m = re.match(r'(\d{4})_(\d{2})(\d{2})', os.path.basename(os.path.abspath(folder)))
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return date_prefix(y, mo) if 1 <= mo <= 12 else None


# ---------------------------------------------------------------- classification

def is_photo(fn):
    return fn.rpartition('.')[2].upper() in RAW_EXTS + JPG_EXTS


def is_junk(name):
    return name in JUNK_FILES or name.startswith(JUNK_PREFIXES)


def is_protected_root(name):
    """Top-level-only protected directory names (the ones without a leading underscore)."""
    return name in PROTECTED_ROOT or any(
        fnmatch.fnmatch(name, g) for g in PROTECTED_ROOT_GLOBS)


def skip_dir(name, at_root):
    """A '_' or '.' name is skipped wherever it sits; 00info/ and *diary/ only at the root."""
    return name.startswith(PROTECTED_PREFIXES) or (at_root and is_protected_root(name))


def is_postproc(name):
    return any(fnmatch.fnmatch(name, g) for g in POSTPROC_GLOBS)


def protected_rel(rel):
    """True for a path the skill must not touch: anything under a top-level protected name,
    a '_' or '.' segment at any depth, or a post-processing* tree (that one is _dangling's
    business)."""
    segs = rel.split(os.sep)
    return (is_protected_root(segs[0])
            or any(s.startswith(PROTECTED_PREFIXES) or is_postproc(s) for s in segs))


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


def find_postproc_dirs(folder):
    """Every post-processing tree under the shoot root, at any depth -- `post-processing*` and
    `_post-processing*` alike. Its own subtree is not descended into: it moves whole.

    The parking test comes BEFORE the protected-name test, which is what lets a
    `_post-processing/` sitting inside a block be parked: the leading underscore keeps a
    directory in place everywhere else, but not here. At the root it still does -- a top-level
    `_post-processing/` is the owner's own, and only the underscore-less `post-processing/` is
    parked from there.
    """
    found = []
    for dirpath, dirnames, _ in os.walk(folder):
        rel = os.path.relpath(dirpath, folder)
        at_root = (rel == '.')
        keep = []
        for d in sorted(dirnames):
            if is_postproc(d) and not (at_root and d.startswith(PROTECTED_PREFIXES)):
                found.append(os.path.normpath(os.path.join('' if at_root else rel, d)))
                continue            # do not descend; it moves as one tree
            if skip_dir(d, at_root):
                continue
            keep.append(d)
        dirnames[:] = keep
    return found


def park_dangling(folder, rels, apply):
    """abc/abc/post-processing -> _dangling/abc/abc/post-processing, path preserved."""
    plan = [(rel, os.path.join(DANGLING, rel)) for rel in rels]
    print(f"{'parking' if apply else 'will park'} {len(plan)} post-processing "
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


# ---------------------------------------------------------------- gathering

def find_photo_dirs(folder):
    """Every subdirectory under the shoot root that holds loose photos, at any depth --
    a card dump (CANON100/, DCIM/100MSDCF/), an older hand-made tree, a block from a
    previous run -- including its lights/, and any darks/ or flats/ sorted out by hand since,
    which is why those come back as light frames and have to be moved out again. Protected
    names -- '_' and '.' at any depth, 00info/ and *diary/ at the root -- are never descended
    into, and neither is a post-processing* tree: that one belongs to _dangling/, planned or
    already parked."""
    found, root_abs = [], os.path.abspath(folder)
    for dirpath, dirnames, filenames in os.walk(folder):
        at_root = os.path.abspath(dirpath) == root_abs
        dirnames[:] = sorted(d for d in dirnames
                             if not skip_dir(d, at_root) and not is_postproc(d))
        if at_root:
            continue
        if any(is_photo(f) for f in filenames):
            found.append(os.path.relpath(dirpath, folder))
    return found


def find_pairs(folder, subdirs=()):
    """Photos at the top level of `folder`, plus any of `subdirs`, paired by basename.
    Returns {base: {ext: path-relative-to-folder}}."""
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


def prune_source_dirs(folder, subdirs=()):
    """Sweep the whole tree bottom-up and remove every directory left holding nothing but OS
    junk -- the dirs this run emptied, and any an earlier run left behind (an `iphone15pro/`
    sitting on a stray .DS_Store). Bottom-up means DCIM/100MSDCF/ takes DCIM/ with it, and an
    old block goes once its jpg/ and raw/ are gone. Anything a person made saves the
    directory. Protected names are never touched."""
    removed, junked, kept, root_abs = [], [], [], os.path.abspath(folder)
    for dirpath, _, _ in os.walk(folder, topdown=False):
        if os.path.abspath(dirpath) == root_abs:
            continue
        rel = os.path.relpath(dirpath, folder)
        if protected_rel(rel):
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

def check_exiftool():
    """Rule 0: exiftool has to be there and has to run."""
    exe = shutil.which('exiftool') or '/opt/homebrew/bin/exiftool'
    if not (os.path.isfile(exe) and os.access(exe, os.X_OK)):
        sys.exit("exiftool not found on PATH (expected /opt/homebrew/bin/exiftool) -- "
                 "install it with `brew install exiftool`, then re-run")
    try:
        out = subprocess.run([exe, '-ver'], capture_output=True, text=True, timeout=30)
    except OSError as e:
        sys.exit(f"exiftool at {exe} is not usable: {e}")
    if out.returncode != 0 or not out.stdout.strip():
        sys.exit(f"exiftool at {exe} is not usable: {(out.stderr or '').strip()}")
    return exe, out.stdout.strip()


def read_exif(exe, folder, pairs):
    """One exiftool call for the whole folder. Reads the JPG of each pair when present."""
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

def split_runs(rows):
    """Consecutive photos at a constant interval -> ('group', slice); the rest -> ('scattered', slice)."""
    n = len(rows)
    if n == 0:
        return []
    deltas = [(rows[i + 1]['t'] - rows[i]['t']).total_seconds() for i in range(n - 1)]
    locked, i = [], 0
    while i < n - 1:
        j = i
        while j + 1 < n - 1 and abs(deltas[j + 1] - deltas[i]) <= TOL:
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


def build_plan(rows, prefix, start):
    """Group per camera body, then number <prefix>-<start>.. by each block's first-photo time."""
    by_cam = OrderedDict()
    for r in rows:
        by_cam.setdefault(r['model'], []).append(r)

    blocks = []
    for model, crows in by_cam.items():
        for run in split_runs(crows):
            blocks.append(dict(kind=run['kind'], iv=run['iv'],
                               rows=crows[run['a']:run['b'] + 1], model=model))
    blocks.sort(key=lambda b: b['rows'][0]['t'])

    plan = []
    for k, b in enumerate(blocks):
        first = b['rows'][0]
        name = f"{prefix}-{start + k:04d}"
        # Naming keys always come from the block's FIRST photo. A scattered-group stops at
        # the camera: its focal length and settings vary, which is why it is scattered.
        leaf = name + '-' + camera_slug(first['model'])
        if b['kind'] == 'group':
            leaf += (f"-{fmt_focal(first['focal'])}-{fmt_shutter(first['exp'])}"
                     f"-{fmt_aperture(first['fnum'])}-iso{first['iso']}")
        settings = Counter((r['exp'], r['fnum'], r['iso']) for r in b['rows'])
        plan.append(dict(name=name, kind=b['kind'], iv=b['iv'], dest=leaf,
                         bases=[r['base'] for r in b['rows']],
                         t0=b['rows'][0]['t'].strftime('%m-%d %H:%M:%S'),
                         t1=b['rows'][-1]['t'].strftime('%m-%d %H:%M:%S'),
                         mixed=(len(settings) > 1),
                         focals=sorted({fmt_focal(r['focal']) for r in b['rows']})))
    return plan


def print_plan(plan, pairs):
    print(f"{'BLOCK':<9} {'TYPE':<9} {'N':>4} {'IVL':>7}  {'SPAN':<28} DEST")
    for p in plan:
        n = len(p['bases'])
        iv = f"{p['iv']:.2f}s" if p['iv'] else '-'
        print(f"{p['name']:<9} {p['kind']:<9} {n:>4} {iv:>7}  "
              f"{p['t0']} -> {p['t1']}  {p['dest']}/{LIGHTS}")
        if p['mixed'] and p['kind'] == 'group':
            print("        !! mixed exposure settings inside a fixed-interval group")
        if len(p['focals']) > 1 and p['kind'] == 'group':
            print(f"        !! mixed focal lengths: {p['focals']} (dir uses the first photo's)")
    print(f"\n{len(plan)} blocks "
          f"({sum(1 for p in plan if p['kind'] == 'group')} groups, "
          f"{sum(1 for p in plan if p['kind'] == 'scattered')} scattered-groups), "
          f"{sum(len(p['bases']) for p in plan)} photos, "
          f"{sum(len(v) for v in pairs.values())} files")


# ---------------------------------------------------------------- apply

def apply_plan(folder, plan, pairs, source_dirs=(), keep_source=False):
    moves, made = 0, []
    for p in plan:
        for base in p['bases']:
            for ext, sub in [(e, 'raw') for e in RAW_EXTS] + [(e, 'jpg') for e in JPG_EXTS]:
                fn = pairs.get(base, {}).get(ext)
                if not fn:
                    continue
                dest_dir = os.path.join(folder, p['dest'], LIGHTS, sub)
                if dest_dir not in made:
                    os.makedirs(dest_dir, exist_ok=True)
                    made.append(dest_dir)
                dst = os.path.join(dest_dir, os.path.basename(fn))
                src = os.path.join(folder, fn)
                if os.path.abspath(src) == os.path.abspath(dst):
                    continue          # re-run: already where the plan wants it
                if os.path.exists(dst):
                    print(f"  skip, destination exists: {dst}", file=sys.stderr)
                    continue
                shutil.move(src, dst)
                moves += 1
    removed, junked, kept = ([], [], list(source_dirs)) if keep_source \
        else prune_source_dirs(folder, source_dirs)
    return moves, removed, junked, kept


def main():
    ap = argparse.ArgumentParser(
        description='Re-block a shoot folder into <YM>-<nnnn>-... directories.')
    ap.add_argument('folder')
    ap.add_argument('start', nargs='?', type=int, default=1,
                    help='first block number, 4-digit padded (default: 1 -> 0001)')
    ap.add_argument('--prefix', help="override the <year-digit><month-letter> prefix, e.g. 6I")
    ap.add_argument('--apply', action='store_true', help='move files (default: plan only)')
    ap.add_argument('--keep-source', action='store_true',
                    help='do not delete an absorbed source directory once it is empty')
    args = ap.parse_args()

    # Rule 0: the folder has to exist, and exiftool has to exist and run.
    folder = resolve_folder(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"folder not found: {folder}")
    exe, ver = check_exiftool()
    if args.start < 0:
        sys.exit(f"start number must not be negative: {args.start}")

    prefix = args.prefix or prefix_from_folder(folder)

    t0 = time.time()
    # Rule 4: park every post-processing* tree under _dangling/ before anything else, so its
    # photos are never pulled into a block.
    pp = find_postproc_dirs(folder)
    if pp:
        park_dangling(folder, pp, args.apply)

    # Rule 3: the root and every subdirectory under it, at any depth, minus protected names.
    source_dirs = find_photo_dirs(folder)
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
    print(f"prefix {prefix}, numbering from {args.start:04d}  (exiftool {ver})\n")
    print_plan(plan, pairs)

    if args.apply:
        moves, removed, junked, kept = apply_plan(
            folder, plan, pairs, source_dirs, args.keep_source)
        # A photo already in the block the plan wants is not "loose", and a block dir still
        # full of its own photos is not a source dir worth reporting as kept.
        leaves = {os.path.abspath(os.path.join(folder, p['dest'], LIGHTS, sub))
                  for p in plan for sub in ('jpg', 'raw')}
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
