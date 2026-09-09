#!/usr/bin/env python3
"""Build <folder>/_diary/: everything in 00info/, three JPEGs per group, every JPEG of a
scattered-group.

Frames come from each block's lights/jpg/ -- the light frames, which are the ones worth
looking at. A block's darks/, flats/ and bias/ are calibration, sorted out by hand after
organize-photo-folders ran, and the strip has no use for them: they never reach the diary.

The diary is REBUILT from scratch on every run: it is emptied first, then filled again from
00info/ and the block directories, so it always mirrors them exactly and never carries a stale
frame from an older layout. Copies (never moves) out of 00info/ and the blocks, names each copy
<source>_<filename>, then numbers the strip d000010_/d000020_/... in capture order.

A group contributes its first, middle and last frame, and the three travel together: 00info/ and
the scattered frames are placed individually by capture time, and each group is inserted whole at
the time of its first pick, so a run reads as one block rather than three frames scattered through
everything shot alongside it.

There is no undo and none is needed: every frame in the diary is a copy of a file that is still
sitting in 00info/ or a block, so a rebuild puts it straight back. Nothing else is kept -- the diary
holds copies only, so anything in it that the sources do not account for is a leftover of an older
run and goes. A photo that must appear in the strip belongs in 00info/, not in the diary.

Plan-only by default; pass --apply to write.
"""
import argparse, datetime, fnmatch, os, re, shutil, subprocess, sys, time

# Blocks hold camera JPEGs; 00info/ and the diary also hold screenshots and hand-added frames.
SOURCE_EXTS = ('.JPG', '.JPEG')
DIARY_EXTS = ('.JPG', '.JPEG', '.PNG')
LIGHTS = 'lights'                           # a block's light frames: <block>/lights/jpg/
DIARY = '_diary'                            # default; an existing *diary/ at the root wins
DIARY_GLOB = '*diary'                       # how organize-photo-folders protects it
INFO = '00info'                              # hand-curated: read from, never written to
# A block directory: 6I-0035-550d-18mm-15s-f3.5-iso1600. Anything else -- a card dump, a
# hand-made tree -- is not a block, so a folder holding none has simply not been organized yet.
BLOCK_RE = re.compile(r'^\d[A-L]-\d{3,}-')
# Hand-curated names at the root of a shoot folder. None of them is ever a block: '_' and '.'
# names wherever they sit (_tmp/, _dangling/, _diary/, _info/), 00info/ by name.
PROTECTED_PREFIXES = ('.', '_')
PROTECTED_ROOT = {'00info'}
# A group carries settings; a scattered-group does not. A hand-added label may follow the ISO
# (6H-0039-6dii-24mm-8s-f1.4-iso200_thor) -- that is still a group.
GROUP_RE = re.compile(r'-iso\d+(?:_.*)?$', re.I)
TZ_RE = re.compile(r'[+-]\d{2}:?\d{2}$')    # trailing +08:00 on an exiftool stamp
# A screenshot with no EXIF date still carries its time in its own name: 2026-08-18 16.35.16.png
NAME_DT_RE = re.compile(r'(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})[.:-](\d{2})[.:-](\d{2})')
STEP = 10                                   # gap between diary numbers, a reading convenience
SEP = '_'                                   # d000010_<source>_<original filename>


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


def check_exiftool():
    """Same precondition as organize-photo-folders: exiftool has to be there and has to run."""
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
    return exe


def find_diary(folder):
    """The shoot folder's diary directory. organize-photo-folders protects `*diary/` at the
    root, so whichever one is already there is the diary; _diary is what we create."""
    hits = [n for n in sorted(os.listdir(folder))
            if fnmatch.fnmatch(n, DIARY_GLOB) and os.path.isdir(os.path.join(folder, n))]
    return hits[0] if hits else DIARY


def is_source(fn):
    return fn.upper().endswith(SOURCE_EXTS)


def is_diary_photo(fn):
    return fn.upper().endswith(DIARY_EXTS)


def parse_stamp(s):
    """'2026:08:18 16:36:04+08:00' -> datetime, or None."""
    if not s or s == '-':
        return None
    s = TZ_RE.sub('', s.strip()).strip()
    fmt = '%Y:%m:%d %H:%M:%S.%f' if '.' in s else '%Y:%m:%d %H:%M:%S'
    try:
        return datetime.datetime.strptime(s, fmt)
    except ValueError:
        return None


def date_from_name(fn):
    """The time a screenshot carries in its filename, when it carries no EXIF date."""
    m = NAME_DT_RE.search(fn)
    if not m:
        return None
    try:
        return datetime.datetime(*(int(g) for g in m.groups()))
    except ValueError:
        return None


def read_dates(exe, paths, fallback=False):
    """One exiftool call. Returns ({path: datetime}, [paths with no usable timestamp]).

    Camera frames are read from EXIF alone. With fallback=True — for 00info/ — a file with no EXIF
    date falls back to the time in its filename, then to FileModifyDate, so screenshots sit in the
    strip where they belong instead of piling up at its end.
    """
    if not paths:
        return {}, []
    out = subprocess.run(
        [exe, '-q', '-T', '-directory', '-filename', '-SubSecDateTimeOriginal',
         '-DateTimeOriginal', '-CreateDate', '-FileModifyDate', '-@', '-'],
        input='\n'.join(paths), capture_output=True, text=True)
    # Keyed by directory+filename: two bodies on one night both produce IMG_0001.JPG.
    tags = {}
    for line in out.stdout.splitlines():
        f = line.rstrip('\n').split('\t')
        if len(f) < 6:
            continue
        tags[os.path.normpath(os.path.join(f[0], f[1]))] = f[2:6]

    dates, unreadable = {}, []
    for p in paths:
        t = tags.get(os.path.normpath(p), [])
        stamp = next((parse_stamp(v) for v in t[:3] if parse_stamp(v)), None)
        if stamp is None and fallback:
            stamp = date_from_name(os.path.basename(p)) or (parse_stamp(t[3]) if t else None)
        if stamp is None:
            unreadable.append(p)
        else:
            dates[p] = stamp
    return dates, unreadable


def find_blocks(folder):
    """Block directories that hold a lights/jpg/ subdirectory, in block-number order.

    Returns (blocks, stale): `stale` is the blocks carrying a bare jpg/ and no lights/ -- the
    layout organize-photo-folders wrote before lights/ existed. They are reported rather than
    read, because a folder in that shape wants re-organizing, not a diary built around it.

    The diary and the other hand-curated root names are never blocks, whatever they are called.
    """
    blocks, stale = [], []
    for name in sorted(os.listdir(folder)):
        if (name.startswith(PROTECTED_PREFIXES) or name in PROTECTED_ROOT
                or fnmatch.fnmatch(name, DIARY_GLOB)):
            continue
        if not BLOCK_RE.match(name):
            continue
        jpgdir = os.path.join(folder, name, LIGHTS, 'jpg')
        if not os.path.isdir(jpgdir):
            if os.path.isdir(os.path.join(folder, name, 'jpg')):
                stale.append(name)
            continue
        files = sorted(f for f in os.listdir(jpgdir)
                       if is_source(f) and os.path.isfile(os.path.join(jpgdir, f)))
        if files:
            blocks.append((name, jpgdir, files))
    return blocks, stale


def find00info(folder):
    """(dir, photos, other) in 00info/. Photos go in the diary; other files are only reported."""
    d = os.path.join(folder, INFO)
    names = [f for f in sorted(os.listdir(d)) if not f.startswith('.')]
    photos = [f for f in names if is_diary_photo(f) and os.path.isfile(os.path.join(d, f))]
    return d, photos, [f for f in names if f not in photos]


def build_plan(exe, folder, blocks, infodir, infofiles):
    """The diary the sources call for: all of 00info/, three frames per group, all of a
    scattered-group.

    This is the whole diary, not a delta — the run rebuilds it from exactly this list.

    The strip is ordered in *units*. A photo from 00info/ and a frame of a scattered-group is a
    unit of its own, placed at its own capture time. A group is a single unit of three frames —
    first, middle, last — inserted where its *first* pick falls, so the three stay together
    instead of the middle and last drifting off among whatever else was shot during the run.
    """
    all_jpgs = [os.path.join(d, f) for _, d, fs in blocks for f in fs]
    dates, unreadable = read_dates(exe, all_jpgs)
    if unreadable:
        print(f"  warning: no usable DateTimeOriginal, ignored: "
              f"{[os.path.basename(p) for p in unreadable[:5]]}"
              f"{' ...' if len(unreadable) > 5 else ''}", file=sys.stderr)

    units = []                                  # each unit is a list of entries placed together

    def entry(source, kind, n, src, t):
        return dict(source=source, kind=kind, n=n, src=src,
                    stem=f"{source}{SEP}{os.path.basename(src)}", t=t)

    # 00info/ first: the night's screenshots, charts and phone frames, every one of them.
    info_paths = [os.path.join(infodir, f) for f in infofiles]
    idates, iunreadable = read_dates(exe, info_paths, fallback=True)
    for p in iunreadable:
        print(f"  warning: {INFO}/{os.path.basename(p)} has no timestamp of any kind "
              f"(EXIF, filename or mtime), sorted last", file=sys.stderr)
    for p in info_paths:
        units.append([entry(INFO, 'info', len(info_paths), p, idates.get(p))])

    for name, jpgdir, files in blocks:
        kind = 'group' if GROUP_RE.search(name) else 'scattered'
        ordered = sorted((p for p in (os.path.join(jpgdir, f) for f in files) if p in dates),
                         key=lambda p: (dates[p], os.path.basename(p)))
        if not ordered:
            print(f"  warning: {name}: no frame with a readable timestamp, skipped", file=sys.stderr)
            continue
        if kind == 'group':
            # First, middle, last -- de-duplicated, so a one- or two-frame group contributes
            # one or two frames rather than the same file twice.
            idx = sorted({0, len(ordered) // 2, len(ordered) - 1})
            units.append([entry(name, kind, len(ordered), ordered[i], dates[ordered[i]])
                          for i in idx])
        else:
            units.extend([entry(name, kind, len(ordered), src, dates[src])] for src in ordered)

    # A unit is placed by its first frame. Undated ones sort last, by name, rather than
    # disappearing from the sequence.
    units.sort(key=lambda u: (u[0]['t'] is None, u[0]['t'] or datetime.datetime.min, u[0]['stem']))
    plan = [e for u in units for e in u]
    for i, e in enumerate(plan):
        e['final'] = f"d{(i + 1) * STEP:06d}{SEP}{e['stem']}"
    return plan


def current_diary(folder):
    """What the diary holds right now — all of which the run is about to remove and write again.

    Every one of these is a copy: its original is in 00info/ or a block, and the rebuild puts it
    back. Dot-files and subdirectories are left alone.
    """
    diary = os.path.join(folder, DIARY)
    if not os.path.isdir(diary):
        return []
    return [fn for fn in sorted(os.listdir(diary))
            if not fn.startswith('.') and os.path.isfile(os.path.join(diary, fn))]


def print_plan(plan, existing, info_other):
    # One row per source, in the order the sources reach the strip -- a group picks three frames
    # and would otherwise take three rows.
    rows = {}
    for p in plan:
        r = rows.setdefault(p['source'], dict(kind=p['kind'], n=p['n'], picks=[]))
        r['picks'].append(os.path.basename(p['src']))

    w = max([len('SOURCE')] + [len(s) for s in rows])              # block names are long now
    print(f"{'SOURCE':<{w}} {'TYPE':<9} {'N':>4}  PICKED")
    for source, r in rows.items():
        if r['kind'] == 'group':
            pick = f"first+middle+last: {', '.join(r['picks'])}"
        else:
            pick = f"all {len(r['picks'])}: {', '.join(r['picks'][:3])}"
            if len(r['picks']) > 3:
                pick += ' ...'
        print(f"{source:<{w}} {r['kind']:<9} {r['n']:>4}  {pick}")
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
    ap.add_argument('--apply', action='store_true', help='write the diary (default: plan only)')
    args = ap.parse_args()

    global DIARY
    folder = resolve_folder(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"folder not found: {folder}")
    exe = check_exiftool()
    DIARY = find_diary(folder)

    t0 = time.time()
    if not os.path.isdir(os.path.join(folder, INFO)):
        sys.exit(f"no {INFO}/ in {folder}; the diary is built from {INFO}/ and the block "
                 f"directories together, so {INFO}/ must exist")
    blocks, stale = find_blocks(folder)
    if stale:
        print(f"  warning: {len(stale)} block(s) hold a bare jpg/ and no {LIGHTS}/ -- the old "
              f"layout, skipped: {', '.join(stale[:5])}{' ...' if len(stale) > 5 else ''}\n"
              f"  re-run organize-photo-folders on {folder} to move them under {LIGHTS}/",
              file=sys.stderr)
    if not blocks:
        sys.exit(f"no block directories with a {LIGHTS}/jpg/ subdirectory in {folder} -- "
                 f"expected names like 6I-0035-550d-18mm-15s-f3.5-iso1600/{LIGHTS}/jpg "
                 f"(organize the folder first)")
    infodir, infofiles, info_other = find00info(folder)
    plan = build_plan(exe, folder, blocks, infodir, infofiles)
    if not plan:
        sys.exit("nothing to do: no frames with readable timestamps")
    existing = current_diary(folder)
    print_plan(plan, existing, info_other)

    if args.apply:
        written = apply_plan(folder, plan, existing)
        print(f"\nrebuilt {DIARY}/ from scratch: {len(written)} frames written, "
              f"{len(existing)} removed first")
    else:
        print("\n(plan only -- re-run with --apply to rebuild the diary)")
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
