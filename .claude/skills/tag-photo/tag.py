#!/usr/bin/env python3
"""Stamp each group's _post-processing/ output with the group's own place and time.

A stacked TIF that came out of Sequator carries no EXIF worth having: no GPS, and whatever
date the stacker felt like writing. The frames it was made from carry both. So each group's
_post-processing/ files are given the GPS and the capture time of the LAST light frame in
that group -- the moment the run finished -- plus one second per file, so the night's
products land at the end of their own run instead of at some arbitrary point.

The order the seconds are handed out in is BY FILENAME LENGTH, shortest first. That is not
arbitrary: the finished piece gets the plain name (..._thor.jpg), and every variant hangs a
suffix off it (..._thor_milkyway.png, ..._thor_SequatorStacking30.tif). Sorting by length
therefore puts the keeper first and its variants behind it, which is the order they want to
be read in.

A file in _post-processing/ that is just a copy of an original frame -- IMG_0046.JPG, or
6H-0050-..._IMG_0148.JPG -- is NOT post-processing output and is left completely alone. It
already carries the camera's own GPS and timestamp, and overwriting those would be a lie.

Nothing in lights/ is ever read for anything but its tags, and never written. The only files
this script modifies are the ones inside a group's _post-processing/.

Idempotent by construction: the time is always recomputed as <last light frame> + N, read
fresh from lights/ every run, never from the target's current tags. Run it twice and the
second run writes exactly what the first one did -- the seconds cannot drift.

Finally every group's _post-processing/ is copied up into the shoot folder's root
_post-processing/. That copy is ADDITIVE: the root folder is hand-curated and nothing in it
is ever deleted or overwritten with different content.

Plan-only by default; pass --apply to write.
"""
import argparse, datetime, os, re, shutil, subprocess, sys, time

# What a post-processing product can be. Anything else in _post-processing/ is reported and
# left alone -- notably video: QuickTime stores dates in UTC and needs -api QuickTimeUTC, a
# trap this skill stays out of entirely rather than getting subtly wrong.
TAGGABLE_EXTS = ('.TIF', '.TIFF', '.JPG', '.JPEG', '.PNG')
POSTPROC = '_post-processing'                # both the source dirs and the root collector
LIGHTS = 'lights'                            # <block>/lights/jpg holds the reference frames
DANGLING = '_dangling'                       # where organize-photo-folders parks stray trees

# A block directory, as organize-photo-folders writes it: 6H-0050-6dii-24mm-8s-f2.8-iso800.
BLOCK_RE = re.compile(r'^\d[A-L]-\d{3,}-')
# A *group* carries settings; a scattered-group (6H-0036-6dii) does not and has no run to
# date its products against. A hand-added label may follow the ISO (..._thor) -- still a group.
GROUP_RE = re.compile(r'-iso\d+(?:_.*)?$', re.I)
TZ_RE = re.compile(r'[+-]\d{2}:?\d{2}$')     # trailing +08:00 on an exiftool stamp

# Names that are a camera's own, not something a person exported: IMG_0046, _MG_1234,
# DSC01234, and the iPhone's '2026-08-18 22.35.21'. Used only as a fallback -- the real test
# is whether the block still holds a file by that name.
CAMERA_NAME_RE = re.compile(r'^(?:IMG|_MG|DSC|DSCN|PICT|P)_?\d{3,}$', re.I)
STAMP_NAME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[ _T]\d{2}[.:-]\d{2}[.:-]\d{2}')

# OS litter: never tagged, never copied to the root.
JUNK_FILES = {'.DS_Store', 'Thumbs.db', 'desktop.ini', '.localized'}
JUNK_PREFIXES = ('._',)


# ---------------------------------------------------------------- where the photos are

# 這個 skill 住在 exiftool_mac repo 裡，照片不在。照片在 UltraFit256 上的 camera_latest，
# 路徑就是 go.sh 同步時用的 $dest_camera_dir_base，同一份 config，不另外開一個 key。
CONFIG_VAR = 'dest_camera_dir_base'          # config/config_vars.txt
CONFIG_ENV = 'CAMERA_LATEST_DIR'             # 臨時換一顆碟時用
SENTINEL = 'it_exists.txt'                   # 掛載證明，整個 repo 都靠它擋隨身碟沒插的情況


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
    """Same precondition as the other two skills: exiftool has to be there and has to run."""
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


# ---------------------------------------------------------------- reading the frames

def parse_stamp(s):
    """'2026:08:18 23:32:34+08:00' -> datetime, or None."""
    if not s or s == '-':
        return None
    s = TZ_RE.sub('', s.strip()).strip()
    fmt = '%Y:%m:%d %H:%M:%S.%f' if '.' in s else '%Y:%m:%d %H:%M:%S'
    try:
        return datetime.datetime.strptime(s, fmt)
    except ValueError:
        return None


def read_dates(exe, paths):
    """One exiftool call for a whole folder -- never one call per file. {path: datetime}."""
    if not paths:
        return {}
    out = subprocess.run(
        [exe, '-q', '-T', '-directory', '-filename', '-SubSecDateTimeOriginal',
         '-DateTimeOriginal', '-CreateDate', '-@', '-'],
        input='\n'.join(paths), capture_output=True, text=True)
    # Keyed by directory+filename: two bodies on one night both produce IMG_0001.JPG.
    tags = {}
    for line in out.stdout.splitlines():
        f = line.rstrip('\n').split('\t')
        if len(f) < 5:
            continue
        tags[os.path.normpath(os.path.join(f[0], f[1]))] = f[2:5]
    dates = {}
    for p in paths:
        t = tags.get(os.path.normpath(p), [])
        stamp = next((parse_stamp(v) for v in t if parse_stamp(v)), None)
        if stamp is not None:
            dates[p] = stamp
    return dates


def has_gps(exe, path):
    """Whether the reference frame carries GPS at all. The 550d does not; the 6dii does."""
    out = subprocess.run([exe, '-q', '-T', '-GPSLatitude', '-GPSLongitude', path],
                         capture_output=True, text=True)
    f = out.stdout.strip().split('\t')
    return len(f) >= 2 and all(v not in ('', '-') for v in f[:2])


def is_junk(fn):
    return fn in JUNK_FILES or fn.startswith(JUNK_PREFIXES) or fn.startswith('.')


def block_originals(block_dir):
    """Every filename the block holds OUTSIDE _post-processing/ -- lights/, and the darks/,
    flats/ and bias/ the owner sorted out by hand. A _post-processing/ entry matching one of
    these is a copy of an original frame, not something that was exported."""
    names = set()
    for root, dirs, files in os.walk(block_dir):
        dirs[:] = [d for d in dirs if d != POSTPROC]
        for f in files:
            names.add(f.lower())
    return names


def is_original_copy(fn, block, originals):
    """Is this _post-processing/ entry just a copy of one of the group's own frames?

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
    organized = False
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if name.startswith(('.', '_')) or not os.path.isdir(path):
            continue
        if not BLOCK_RE.match(name):
            continue
        organized = True
        (groups if GROUP_RE.search(name) else scattered).append(name)
    return groups, scattered, not organized


# ---------------------------------------------------------------- the plan

def build_plan(exe, folder, groups):
    """One entry per group that has a _post-processing/ to stamp.

    The reference frame is the LAST light frame by capture time -- the end of the run. Every
    product then sits at +1s, +2s, ... in filename-length order, shortest first.
    """
    plan, notes = [], []
    for block in groups:
        bdir = os.path.join(folder, block)
        ppdir = os.path.join(bdir, POSTPROC)
        if not os.path.isdir(ppdir):
            continue
        jpgdir = os.path.join(bdir, LIGHTS, 'jpg')
        if not os.path.isdir(jpgdir):
            notes.append(f"{block}: has {POSTPROC}/ but no {LIGHTS}/jpg/ to date it against, "
                         f"skipped (re-run organize-photo-folders?)")
            continue
        frames = [os.path.join(jpgdir, f) for f in sorted(os.listdir(jpgdir))
                  if not is_junk(f) and f.upper().endswith(('.JPG', '.JPEG'))]
        dates = read_dates(exe, frames)
        dated = [p for p in frames if p in dates]
        if not dated:
            notes.append(f"{block}: no light frame with a readable timestamp, skipped")
            continue
        # Last by capture time, name as tiebreak -- the same ordering create-diary uses.
        ref = max(dated, key=lambda p: (dates[p], os.path.basename(p)))
        ref_t = dates[ref].replace(microsecond=0)

        entries = [f for f in sorted(os.listdir(ppdir))
                   if not is_junk(f) and os.path.isfile(os.path.join(ppdir, f))]
        originals = block_originals(bdir)
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
            notes.append(f"{block}: {os.path.basename(ref)} carries no GPS "
                         f"(this body does not record it) -- time only, no location written")
        plan.append(dict(block=block, ppdir=ppdir, ref=ref, ref_t=ref_t, gps=gps,
                         nframes=len(dated), skipped=skipped, other=other,
                         products=[(f, ref_t + datetime.timedelta(seconds=i + 1))
                                   for i, f in enumerate(products)]))
    return plan, notes


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
    root = os.path.join(folder, POSTPROC)
    copies, clashes, claimed = [], [], {}
    for g in plan:
        products = {f for f, _ in g['products']}
        for f in sorted(os.listdir(g['ppdir'])):
            src = os.path.join(g['ppdir'], f)
            if is_junk(f) or not os.path.isfile(src):
                continue
            dst = os.path.join(root, f)
            owner = claimed.get(f)
            if owner is not None:                    # two blocks, one name
                clashes.append((f, owner, g['block']))
                continue
            claimed[f] = g['block']
            if f in products:
                copies.append((src, dst, g['block'], 'stamped'))
            elif not os.path.isfile(dst):
                copies.append((src, dst, g['block'], 'new'))
            else:
                s, d = os.stat(src), os.stat(dst)
                if s.st_size == d.st_size and int(s.st_mtime) == int(d.st_mtime):
                    continue                          # already there, unchanged
                copies.append((src, dst, g['block'], 'replace'))
    return root, copies, clashes


def print_plan(plan, notes, scattered, root, copies, clashes):
    print("STAMP — each group's _post-processing/ gets that group's place and time\n")
    for g in plan:
        gps = 'GPS+time' if g['gps'] else 'time only (no GPS on this body)'
        print(f"{g['block']}")
        print(f"  reference: {LIGHTS}/jpg/{os.path.basename(g['ref'])} "
              f"(last of {g['nframes']} frames, {g['ref_t']:%Y-%m-%d %H:%M:%S})  ->  {gps}")
        for f, t in g['products']:
            print(f"    +{(t - g['ref_t']).seconds}s  {t:%H:%M:%S}  {f}")
        for f in g['skipped']:
            print(f"     --   left alone, a copy of an original frame: {f}")
        for f in g['other']:
            print(f"     --   left alone, not a taggable image: {f}")
        print()

    if not any(g['products'] for g in plan):
        print("nothing to stamp: no group holds a post-processing product\n")

    if scattered:
        print(f"scattered-groups, no settings and so no run to date against — skipped: "
              f"{', '.join(scattered)}\n")
    for n in notes:
        print(f"  note: {n}")
    if notes:
        print()

    print(f"COPY UP — into {POSTPROC}/ at the shoot root ({len(copies)} files)")
    if not os.path.isdir(root):
        print(f"  {POSTPROC}/ does not exist yet and will be created")
    for _, dst, block, how in copies:
        print(f"  {how:<7} {os.path.basename(dst)}   <- {block}")
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
    ap.add_argument('--apply', action='store_true',
                    help='write the tags and copy up (default: plan only)')
    args = ap.parse_args()

    folder = resolve_folder(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"folder not found: {folder}")
    exe = check_exiftool()

    t0 = time.time()
    groups, scattered, unorganized = find_groups(folder)
    if unorganized:
        sys.exit(f"{folder} holds no block directory (expected names like "
                 f"6H-0050-6dii-24mm-8s-f2.8-iso800) -- it has not been organized yet. "
                 f"Run organize-photo-folders on it first.")
    if not groups:
        sys.exit(f"{folder} is organized but holds no *group* (a name carrying -iso<n>); "
                 f"only scattered-groups: {', '.join(scattered)}. Nothing to tag.")

    plan, notes = build_plan(exe, folder, groups)
    # Post-processing work organize-photo-folders parked out of the way when it renumbered the
    # folder. It is not in a block, so nothing here can date it -- but it is exactly the kind of
    # thing that gets forgotten, so say it is sitting there.
    dangling = os.path.join(folder, DANGLING)
    if os.path.isdir(dangling) and os.listdir(dangling):
        notes.append(f"{DANGLING}/ is not empty -- organize-photo-folders parked post-processing "
                     f"work there. Nothing in it belongs to a block, so it is not tagged; move it "
                     f"back into the right block's {POSTPROC}/ and re-run to pick it up")
    if not plan:
        sys.exit(f"no group in {folder} has a {POSTPROC}/ subdirectory -- nothing to do")
    root, copies, clashes = plan_root_copies(folder, plan)
    print_plan(plan, notes, scattered, root, copies, clashes)

    if args.apply:
        stamped, failed, copied = apply_plan(exe, plan, copies)
        print(f"\nstamped {stamped} file(s); copied {copied} file(s) up into {POSTPROC}/")
        for f, err in failed:
            print(f"  FAILED  {f}: {err}", file=sys.stderr)
    else:
        print("\n(plan only -- re-run with --apply to write the tags and copy up)")
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
