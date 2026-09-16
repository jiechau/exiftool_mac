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

ORIGINAL = '00_Original'                # the untouched pool: every frame the block was cut from
RAW_SUB = 'RAW'                         # NOTE the case. macOS would forgive 'raw', the NAS
JPG_SUB = 'JPG'                         # (ext4, and rsync over SMB) will not.
LIGHTS = 'lights'
DARKS = 'darks'
POSTPROC = '_Post-Processing'           # a block's and a category's collector. NOTE the case,
                                        # for the RAW_SUB reason above: ext4 on the NAS is
                                        # case-sensitive and will not forgive a lower-case one.
POSTPROC_ROOT = '_post-processing_jpg'  # the shoot root's collector, beside _00info/ and _diary/.
                                        # Deliberately NOT the block spelling: it sits one level
                                        # up among the shoot's own directories, so it reads as one
                                        # of those rather than as a block that lost its prefix.
INFO_BLOCK = '_00info'                  # per block: notes about that block
INFO_ROOT = '_00info'                   # per shoot: screenshots, sky charts, planning notes.
                                        # Underscore-less '00info' is the older spelling; it is
                                        # still protected at the root (PROTECTED_ROOT below) so an
                                        # un-migrated folder is never walked into, but the diary
                                        # is built from this one.
DANGLING = '_dangling'
DIARY_GLOB = '*diary'                   # matches both spellings; protected at the shoot root

# The owner's filing categories. organize-photo-folders creates them empty and never reads them
# back as a photo source; create-diary and tag-photo work off their lights/JPG.
CATEGORIES = ('01_Astro', '02_Landscape', '03_Portraits')
TESTS = '04_tests'

RAW_EXTS = ('CR2', 'CR3', 'NEF', 'ARW', 'DNG', 'RAF', 'ORF', 'PEF', 'RW2')
JPG_EXTS = ('JPG', 'JPEG')

# Every block gets this much. A scattered-group is stray and test frames -- it gets somewhere to
# put a note and somewhere to put an export, and nothing else.
MIN_TEMPLATE = (
    INFO_BLOCK,
    POSTPROC,
    f'{ORIGINAL}/{RAW_SUB}',
    f'{ORIGINAL}/{JPG_SUB}',
)

# A set group gets the full working tree. The shape differs per category on purpose: astro stacks
# in two Camera Raw passes and needs darks, landscape needs darks but not the raw passes,
# portraits needs one raw pass and no darks, and 04_tests/ is a dumping ground with no lights.
FULL_TEMPLATE = MIN_TEMPLATE + (
    f'01_Astro/{POSTPROC}',
    '01_Astro/_CameraRaw0',
    '01_Astro/_CameraRaw1',
    f'01_Astro/{LIGHTS}/{RAW_SUB}',
    f'01_Astro/{LIGHTS}/{JPG_SUB}',
    f'01_Astro/{DARKS}/{RAW_SUB}',
    f'01_Astro/{DARKS}/{JPG_SUB}',
    f'02_Landscape/{POSTPROC}',
    f'02_Landscape/{LIGHTS}/{RAW_SUB}',
    f'02_Landscape/{LIGHTS}/{JPG_SUB}',
    f'02_Landscape/{DARKS}/{RAW_SUB}',
    f'02_Landscape/{DARKS}/{JPG_SUB}',
    f'03_Portraits/{POSTPROC}',
    '03_Portraits/_CameraRaw0',
    f'03_Portraits/{LIGHTS}/{RAW_SUB}',
    f'03_Portraits/{LIGHTS}/{JPG_SUB}',
    f'{TESTS}/{RAW_SUB}',
    f'{TESTS}/{JPG_SUB}',
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


def is_protected_root(name):
    """Top-level-only protected names: _00info/ (and the older 00info/) and *diary/."""
    return name in PROTECTED_ROOT or any(
        fnmatch.fnmatch(name, g) for g in PROTECTED_ROOT_GLOBS)


def diary_dir_name(folder):
    """The diary directory for a shoot: _<shoot folder name>_diary.

    Named after the folder rather than a bare _diary/ so the directory still says which shoot it
    belongs to once it has been copied or dragged somewhere else -- a hundred folders all called
    _diary are indistinguishable the moment they leave home. A shoot that already has any *diary/
    keeps the name it has; this is what a new one is called.
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


def category_lights_jpg(block_dir):
    """Every <category>/lights/JPG under a block that actually holds JPEGs, in category order.

    Empty right after organize-photo-folders runs -- everything is still in 00_Original/ until the
    owner files it. Callers fall back to original_jpg() when this comes back empty."""
    out = []
    for cat in CATEGORIES:
        d = os.path.join(block_dir, cat, LIGHTS, JPG_SUB)
        if not os.path.isdir(d):
            continue
        files = sorted(f for f in os.listdir(d)
                       if is_jpg(f) and not is_junk(f) and os.path.isfile(os.path.join(d, f)))
        if files:
            out.append((cat, d, files))
    return out


def original_jpg(block_dir):
    """(dir, files) for a block's 00_Original/JPG, or (dir, []) -- the fall-back frame source."""
    d = os.path.join(block_dir, ORIGINAL, JPG_SUB)
    if not os.path.isdir(d):
        return d, []
    return d, sorted(f for f in os.listdir(d)
                     if is_jpg(f) and not is_junk(f) and os.path.isfile(os.path.join(d, f)))


def has_old_layout(block_dir):
    """The pre-00_Original layout: a bare lights/jpg/ (or an even older jpg/) and no 00_Original/.

    Reported, never read. A folder in that shape wants re-organizing, not a diary built round it."""
    if os.path.isdir(os.path.join(block_dir, ORIGINAL)):
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
