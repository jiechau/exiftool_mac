#!/usr/bin/env python3
"""What the three camera_latest skills have to agree on.

organize-photo-folders writes the block layout; create-diary and tag-photo read it. When each
script carried its own copy of the layout names and its own copy of the config lookup, the three
agreed only by luck -- a leaf renamed in one was a silently-skipped block in the others. Everything
in here is the shared contract: where the photos are, how exiftool is found, what a block
directory is called, and what is inside one.

The rules themselves are written down in organize-photo-folders.md at the repo root. This file is
the code that enforces them; that file is the spec.

Not a skill: a directory under .claude/skills/ without a SKILL.md is not discovered as one.
Imported by the three scripts with a sys.path insert -- see the header of any of them.
"""
import datetime
import fnmatch
import os
import re
import subprocess
import shutil
import sys


# ---------------------------------------------------------------- the block layout

RAW_SUB = 'RAW'                         # NOTE the case. macOS would forgive 'raw', the NAS
JPG_SUB = 'JPG'                         # (ext4, and rsync over SMB) will not.
LIGHTS = 'lights'
DARKS = 'darks'

ORIGINAL = '_00Original'                # the untouched pool: every frame the block was cut from.
                                        # It lives INSIDE a category, not at the block root --
                                        # <block>/01_Astro/_00Original/lights/{RAW,JPG}.
# Three spellings are read as a pool, one is written. '_00_Original' is the older hand-made
# spelling, still on the drive in 2026_0907 and 2026_0916; '00_Original' is the flat block-root
# pool this skill itself wrote until 2026-09-25. Both are read so a re-run on an un-migrated
# folder finds its photos instead of parking every one of them under _dangling/.
ORIGINAL_ALIASES = (ORIGINAL, '_00_Original', '00_Original')

CATEGORY_DEFAULT = '01_Astro'           # the only category created at init; see the templates
POOL = f'{CATEGORY_DEFAULT}/{ORIGINAL}/{LIGHTS}'    # where organize-photo-folders puts a photo
CAMERA_ALL = '_CameraAll'               # every frame of the block as the camera rendered it

POSTPROC = '_Post-Processing'           # a CATEGORY's collector. NOTE the case, for the RAW_SUB
                                        # reason above: ext4 on the NAS is case-sensitive and
                                        # will not forgive a lower-case one.
POSTPROC_ROOT = '_post-processing_jpg'  # ONE per shoot, at the shoot root, beside _00info/ and
                                        # the diary. From 2026-10-01 create-diary owns it: it is
                                        # deleted and rebuilt on every diary run from the blocks'
                                        # _Post-Processing/ directories, so nothing hand-placed in
                                        # it survives. organize-photo-folders never makes one, and
                                        # no block carries one.
INFO_ROOT = '_00info'                   # per shoot: screenshots, sky charts, planning notes.
                                        # Underscore-less '00info' is the older spelling; it is
                                        # still protected at the root (PROTECTED_ROOT below) so an
                                        # un-migrated folder is never walked into, but the diary
                                        # is built from this one.
DANGLING = '_dangling'
DIARY_GLOB = '*diary'                   # matches both spellings; protected at the shoot root
DIARY_OLD = '_diary'                    # the bare spelling, before diary_dir_name() existed

# The owner's filing categories. Only 01_Astro/ is created at init (see the templates); the other
# two are recognised wherever the owner has made them by hand -- a 02_Landscape/_00Original/ is
# read as a photo source like any other pool.
CATEGORIES = ('01_Astro', '02_Landscape', '03_Portraits')
TESTS = '04_tests'

RAW_EXTS = ('CR2', 'CR3', 'NEF', 'ARW', 'DNG', 'RAF', 'ORF', 'PEF', 'RW2')
JPG_EXTS = ('JPG', 'JPEG')

# What a block is created with. Nothing here is speculative: a directory is in the template only
# because the owner files into it on the night. 02_Landscape/, 03_Portraits/, 04_tests/ and every
# darks/ used to be created empty alongside these and went unused shoot after shoot, so a finished
# folder carried hundreds of empty directories that said nothing about the work in it. They are
# not created any more -- the owner makes one by hand when a shoot actually needs it, and this
# skill still READS any pool found inside one (ORIGINAL_ALIASES above).
#
# _post-processing_jpg/ is NOT among them, from 2026-09-25: there is one per SHOOT, at the shoot
# root, and tag-photo is what creates it when it has something to copy up. A block's exports go in
# its category's _Post-Processing/, so a per-block copy of the shoot's collector was a second name
# for a place that already existed and was empty in every block on the drive.
#
# Nor is a per-block _00info/, from 2026-10-04, for the same reason the categories went: it was
# created in every block and stayed empty in nearly all of them. Notes about a night go in the
# shoot root's _00info/, which is the one the diary reads. A block-level one made by hand is a
# '_' name below the root, so a re-run parks it like any other hand work.
#
# A scattered-group is stray and test frames: somewhere to put the frames and an export.
MIN_TEMPLATE = (
    f'{POOL}/{RAW_SUB}',                        # 01_Astro/_00Original/lights/RAW
    f'{POOL}/{JPG_SUB}',                        # 01_Astro/_00Original/lights/JPG
    f'{CATEGORY_DEFAULT}/{POSTPROC}',           # 01_Astro/_Post-Processing
)

# A set group is what actually gets stacked, so it also gets the three Camera Raw directories that
# a stacking pass writes into.
FULL_TEMPLATE = MIN_TEMPLATE + (
    f'{CATEGORY_DEFAULT}/{CAMERA_ALL}',         # 01_Astro/_CameraAll
    f'{CATEGORY_DEFAULT}/_CameraRaw0',
    f'{CATEGORY_DEFAULT}/_CameraRaw1',
)

# A block directory: 6I-0035-550d-18mm-15s-f3.5-iso1600. Anything else -- a card dump, a
# hand-made tree -- is not a block, so a folder holding none has simply not been organized yet.
BLOCK_RE = re.compile(r'^\d[A-L]-\d{3,}(?:-|$)')
# A *group* carries settings; a scattered-group (6H-0036-6dii, or a bare 6H-0037) does not.
# A hand-added label may follow the ISO -- 6H-0039-6dii-24mm-8s-f1.4-iso200_thor is still a group.
GROUP_RE = re.compile(r'-iso\d+(?:_.*)?$', re.I)

TZ_RE = re.compile(r'[+-]\d{2}:?\d{2}$')     # trailing +08:00 on an exiftool stamp
# A screenshot with no EXIF date still carries its time in its own name: 2026-08-18 16.35.16.png
NAME_DT_RE = re.compile(r'(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})[.:-](\d{2})[.:-](\d{2})')

# OS metadata the filesystem regenerates on its own. It never counts as content, so a directory
# holding nothing else is still "empty". Anything a person made is content and saves it.
JUNK_FILES = {'.DS_Store', 'Thumbs.db', 'desktop.ini', '.localized'}
JUNK_PREFIXES = ('._',)

PROTECTED_PREFIXES = ('.', '_')
# Protected WITHOUT a leading underscore, and only at the top level of a shoot folder. Deeper
# down these mean nothing -- a nested 00info/ is just another directory full of photos.
PROTECTED_ROOT = {INFO_ROOT, '00info'}
PROTECTED_ROOT_GLOBS = (DIARY_GLOB,)


def is_photo(fn):
    return fn.rpartition('.')[2].upper() in RAW_EXTS + JPG_EXTS


def is_jpg(fn):
    return fn.rpartition('.')[2].upper() in JPG_EXTS


def is_junk(fn):
    return fn in JUNK_FILES or fn.startswith(JUNK_PREFIXES) or fn.startswith('.')


def is_pool_name(name):
    """A pool directory -- the untouched frames a block was cut from, under any of the three
    spellings this repo has written. The pool is the ONE thing inside an organized block that is
    read back as a photo source; everything else in the block is the owner's work."""
    return name in ORIGINAL_ALIASES


def under_pool(rel):
    """True once any segment of a block-relative path is a pool directory. Everything below a
    pool is frames -- lights/, darks/, or the flat RAW/ and JPG/ of the older layout -- so the
    walk stops asking questions and just reads."""
    return bool(rel) and any(is_pool_name(s) for s in rel.replace('\\', '/').split('/'))


def has_pool(path):
    """True if path IS a pool directory or holds one at any depth.

    This is what 'already organized' means now that the pool sits inside a category: a block is
    organized when something under it is a pool, and 01_Astro/ has to be walked into rather than
    parked precisely because a pool is beneath it. Walks the subtree, so it is called on
    directories, not in an inner loop over files."""
    if is_pool_name(os.path.basename(os.path.normpath(path))):
        return True
    for _, dirnames, _ in os.walk(path):
        if any(is_pool_name(d) for d in dirnames):
            return True
    return False


def is_protected_root(name):
    """Top-level-only protected names: _00info/ (and the older 00info/) and *diary/."""
    return name in PROTECTED_ROOT or any(
        fnmatch.fnmatch(name, g) for g in PROTECTED_ROOT_GLOBS)


def diary_dir_name(folder):
    """The diary directory for a shoot: _<shoot folder name>_diary.

    Named after the folder rather than a bare _diary/ so the directory still says which shoot it
    belongs to once it has been copied or dragged somewhere else -- a hundred folders all called
    _diary are indistinguishable the moment they leave home. create-diary deletes a bare _diary/
    (DIARY_OLD) and writes this one in its place.
    """
    return f"_{os.path.basename(os.path.abspath(folder))}_diary"


def is_block(name):
    return bool(BLOCK_RE.match(name))


def is_group(name):
    """A block whose name carries settings. Scattered-groups stop at the camera or earlier."""
    return bool(GROUP_RE.search(name))


def block_dirs(folder):
    """Block directories at the root of a shoot folder, in name order.

    Hand-curated root names are never blocks whatever they are called: '_' and '.' names, 00info/
    and the diary."""
    out = []
    for name in sorted(os.listdir(folder)):
        if name.startswith(PROTECTED_PREFIXES) or is_protected_root(name):
            continue
        if is_block(name) and os.path.isdir(os.path.join(folder, name)):
            out.append(name)
    return out


def pool_jpg_dir(block_dir, cat=None):
    """Where a category's untouched JPEGs sit, or None. Four shapes are recognised, newest first:

        <cat>/_00Original/lights/JPG   the current layout
        <cat>/_00Original/JPG          a pool with no lights/darks split
        <cat>/lights/JPG               before the pool directory existed
        <block>/00_Original/JPG        the flat block-root pool

    cat=None means the block's own frames: the categories are tried in order, then the block root.
    Existence only -- a caller that needs the filenames lists it, so an empty pool still resolves
    and the caller can say so."""
    bases = ([os.path.join(block_dir, cat)] if cat
             else [os.path.join(block_dir, c) for c in CATEGORIES] + [block_dir])
    for base in bases:
        for alias in ORIGINAL_ALIASES:
            for tail in ((LIGHTS, JPG_SUB), (JPG_SUB,)):
                d = os.path.join(base, alias, *tail)
                if os.path.isdir(d):
                    return d
        d = os.path.join(base, LIGHTS, JPG_SUB)
        if os.path.isdir(d):
            return d
    return None


def pool_jpg(block_dir, cat=None):
    """(dir, files) for pool_jpg_dir(), or (None, []) when the block has no pool at all."""
    d = pool_jpg_dir(block_dir, cat)
    if d is None:
        return None, []
    return d, sorted(f for f in os.listdir(d)
                     if is_jpg(f) and not is_junk(f) and os.path.isfile(os.path.join(d, f)))


def postproc_dirs(block_dir):
    """Every _Post-Processing/ in a block, as [(dir, category or None)], in path order.

    A block can hold several: one per category (01_Astro/_Post-Processing/, 02_Landscape/...) and
    the block's own at its root, the "main" one. The category is the first path segment when that
    is one of CATEGORIES, so a _Post-Processing/ filed deeper inside a category still belongs to it;
    None means the main one, or one somewhere that is not under a category. The name is matched
    without regard to case, for the older hand-made _post-processing/. Pools, _dangling/ and
    dot-directories are never walked into.
    """
    out = []
    for root, dirs, _ in os.walk(block_dir):
        dirs[:] = sorted(d for d in dirs
                         if not d.startswith('.') and d != DANGLING and not is_pool_name(d))
        for d in dirs:
            if d.lower() == POSTPROC.lower():
                rel = os.path.relpath(os.path.join(root, d), block_dir).replace('\\', '/')
                first = rel.split('/')[0]
                out.append((os.path.join(root, d),
                            first if first in CATEGORIES and '/' in rel else None))
    return out


def has_old_layout(block_dir):
    """A block with no pool in any recognised spelling: a bare lights/jpg/, or an even older jpg/.

    Reported, never read. A folder in that shape wants re-organizing, not a diary built round it."""
    if pool_jpg_dir(block_dir) is not None:
        return False
    return (os.path.isdir(os.path.join(block_dir, LIGHTS, 'jpg'))
            or os.path.isdir(os.path.join(block_dir, 'jpg')))


def make_tree(block_path, kind):
    """Create a block's scaffolding. 'group' gets the full tree, anything else the minimum."""
    for rel in (FULL_TEMPLATE if kind == 'group' else MIN_TEMPLATE):
        os.makedirs(os.path.join(block_path, *rel.split('/')), exist_ok=True)


# ---------------------------------------------------------------- where the photos are

# 這幾個 skill 住在 exiftool_mac repo 裡，照片不在。Mac 上照片在 UltraFit256 的 camera_latest，
# 路徑就是 go.sh 同步時用的 $dest_camera_dir_base，同一份 config，不另外開 key。
# Windows 是另外一台機器、另外一顆碟，路徑本來就不一樣，所以那邊讀 $dest_camera_dir_copy --
# 這不是同一個資料夾開兩個 key，是兩台機器各自的路徑。
CONFIG_VAR_POSIX = 'dest_camera_dir_base'
CONFIG_VAR_WIN = 'dest_camera_dir_copy'
CONFIG_ENV = 'CAMERA_LATEST_DIR'            # 臨時換一顆碟時用，兩個平台都吃
SENTINEL = 'it_exists.txt'                  # 掛載證明，整個 repo 都靠它擋隨身碟沒插的情況

EXIFTOOL_ENV = 'EXIFTOOL'
EXIFTOOL_CANDIDATES = {
    'posix': ('/opt/homebrew/bin/exiftool', '/usr/local/bin/exiftool'),
    'nt': (r'C:\Windows\exiftool.exe',
           r'C:\Program Files\exiftool\exiftool.exe',
           r'C:\Program Files (x86)\exiftool\exiftool.exe',
           r'C:\exiftool\exiftool.exe'),
}


def on_windows():
    return os.name == 'nt'


def config_var():
    return CONFIG_VAR_WIN if on_windows() else CONFIG_VAR_POSIX


def repo_root():
    """<repo>/.claude/skills/_shared/<this file> -> <repo>. Move this file and it breaks."""
    p = os.path.abspath(__file__)
    for _ in range(4):
        p = os.path.dirname(p)
    return p


def camera_base_dir():
    """The camera_latest root for this machine, or None -- the caller says what None means.

    $CAMERA_LATEST_DIR wins on both platforms; otherwise the per-platform key out of
    config/config_vars.txt."""
    env = os.environ.get(CONFIG_ENV)
    if env:
        return os.path.expanduser(env.rstrip('/\\'))
    key = config_var()
    try:
        # 一定要指定 utf-8：config_vars.txt 裡有中文路徑，Windows 的預設編碼是 cp950，會爆。
        with open(os.path.join(repo_root(), 'config', 'config_vars.txt'),
                  encoding='utf-8') as fh:
            for line in fh:
                k, _, val = line.partition('=')
                if k.strip() == key:
                    return os.path.expanduser(val.strip().rstrip('/\\'))
    except OSError:
        pass
    return None


def resolve_folder(arg):
    """A shoot folder is named, not pathed: `2026_0907_camera_daw_bay`.

    An absolute path, or a relative one that exists from the cwd, is taken as given -- so running
    this from inside camera_latest still works. Anything else is a bare shoot-folder name and gets
    looked up under this machine's base."""
    arg = arg.rstrip('/\\')
    if os.path.isabs(arg) or os.path.isdir(arg):
        return arg
    key = config_var()
    base = camera_base_dir()
    if not base:
        sys.exit(f"no {key} in config/config_vars.txt and no ${CONFIG_ENV} set; "
                 f"cannot tell where '{arg}' lives -- pass a full path instead")
    # 隨身碟沒掛載時，掛載點還是解析得出來，只是空的。sentinel 不在就是沒掛載。
    # Windows 那邊碟不會掉，但規則一致比較不會記錯，而且 base 打錯時一樣擋得住。
    if not os.path.isfile(os.path.join(base, SENTINEL)):
        sys.exit(f"{base} has no {SENTINEL}: the drive looks unmounted "
                 f"(or {key} points somewhere else). Refusing to touch '{arg}'")
    return os.path.join(base, arg)


def _runs_ok(exe):
    """A candidate is only real if `exiftool -ver` actually answers."""
    try:
        out = subprocess.run([exe, '-ver'], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return out.stdout.strip()


def find_exiftool(override=None):
    """Rule 0: exiftool has to be there and has to run. Returns (path, version).

    --exiftool, then $EXIFTOOL, then PATH, then the usual install locations for this platform.
    Nothing found is not an error to work around: the skill stops and the agent asks the owner
    where it is, because guessing is how the wrong binary gets used on the wrong machine."""
    # An explicit --exiftool is the answer, not a first guess. Falling back from a path the owner
    # typed would run some other binary than the one they named, which is the whole failure this
    # is here to prevent.
    if override:
        exe = os.path.expanduser(override)
        ver = _runs_ok(exe) if (os.path.isfile(exe) or shutil.which(exe)) else None
        if not ver:
            sys.exit(f"exiftool at '{override}' is not there or will not run. "
                     f"Check the path and try again.")
        return exe, ver

    tried = []
    cands = []
    if os.environ.get(EXIFTOOL_ENV):
        cands.append(os.environ[EXIFTOOL_ENV])
    for name in ('exiftool', 'exiftool.exe'):
        found = shutil.which(name)
        if found:
            cands.append(found)
    cands += EXIFTOOL_CANDIDATES['nt' if on_windows() else 'posix']

    for exe in cands:
        exe = os.path.expanduser(exe)
        if exe in tried:
            continue
        tried.append(exe)
        if not (os.path.isfile(exe) or shutil.which(exe)):
            continue
        ver = _runs_ok(exe)
        if ver:
            return exe, ver

    where = ('exiftool.exe from exiftool.org, unzipped and renamed from exiftool(-k).exe'
             if on_windows() else '`brew install exiftool`')
    sys.exit("exiftool not found. Tried: " + (', '.join(tried) or 'nothing on $PATH') + "\n"
             "ASK THE OWNER where exiftool is installed on this machine, then re-run with "
             "--exiftool <path> (or set $" + EXIFTOOL_ENV + ").\n"
             "If it is not installed: " + where)


# ---------------------------------------------------------------- reading times

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


def read_geo_time(exe, paths):
    """What tag-photo and create-diary mean by "tagged": {path: (DateTimeOriginal, has_gps)}.

    One exiftool call for the whole list. DateTimeOriginal is the photo-taken time and the only
    date that counts -- a stacker's ModifyDate or CreateDate is not when anything was shot. GPS
    counts when both latitude and longitude are there. A path exiftool cannot read at all comes
    back (None, False): untagged, which is the truth as far as anything downstream can tell.
    """
    if not paths:
        return {}
    out = subprocess.run(
        [exe, '-q', '-T', '-directory', '-filename', '-DateTimeOriginal',
         '-GPSLatitude', '-GPSLongitude', '-@', '-'],
        input='\n'.join(paths), capture_output=True, text=True)
    tags = {}
    for line in out.stdout.splitlines():
        f = line.split('\t')
        if len(f) < 5:
            continue
        tags[os.path.normpath(os.path.join(f[0], f[1]))] = f[2:5]
    res = {}
    for p in paths:
        t = tags.get(os.path.normpath(p))
        if not t:
            res[p] = (None, False)
            continue
        res[p] = (parse_stamp(t[0]),
                  all(v.strip() not in ('', '-') for v in t[1:3]))
    return res


def read_dates(exe, paths, fallback=False):
    """One exiftool call for a whole list -- never one call per file.

    Returns ({path: datetime}, [paths with no usable timestamp]). Camera frames are read from EXIF
    alone. With fallback=True -- for _00info/ -- a file with no EXIF date falls back to the time in
    its filename, then to FileModifyDate, so screenshots sit where they belong in a strip instead
    of piling up at its end.
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
