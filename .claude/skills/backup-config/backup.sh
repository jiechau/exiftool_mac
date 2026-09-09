#!/usr/bin/env bash
# Back up exiftool_mac's config files + .claude/ into the jsave repo and push.
# 這些檔案大半是 gitignored，jsave 是它們唯一的備份。
# Invoked by the backup-config skill. Kept as a fixed file so it can be
# allowlisted as a single exact command (no dynamic args) in settings.
set -e
SRC="$HOME/life_codes/exiftool_mac"
DST="$HOME/life_codes/jsave"
TGT="$DST/exiftool_mac"

# 1 validate the backup repo — before copying anything
[ -d "$DST/.git" ] || { echo "ERROR: $DST is not a git repo — stopping."; exit 1; }
git -C "$DST" remote get-url origin | grep -q 'jsave.git' \
  || { echo "ERROR: $DST origin is not jsave.git — stopping."; exit 1; }

# 2 pull before the copy: pulling afterwards risks a conflict eating a fresh backup
git -C "$DST" pull

# 3 copy (force overwrite, flat — no config/ level)
mkdir -p "$TGT"
cp -f "$SRC/config/config_secrets.txt" \
      "$SRC/config/config_secrets_example.txt" \
      "$SRC/config/config_sourcedir.txt" \
      "$SRC/config/config_vars.txt" \
      "$TGT/"
# config_win.txt 是每台 windows 自己的，Mac 上通常沒有 — 沒有就跳過，不算錯
if [ -f "$SRC/config/config_win.txt" ]; then
  cp -f "$SRC/config/config_win.txt" "$TGT/"
  echo "copied config_win.txt"
else
  echo "config_win.txt not present — skipped (normal on the Mac)."
fi
# .claude/ 用鏡像的方式，刪掉的 skill 備份端也要跟著消失。
# 先確認來源在，才敢刪目標。
[ -d "$SRC/.claude" ] || { echo "ERROR: $SRC/.claude missing — stopping."; exit 1; }
rm -rf "$TGT/.claude"
cp -a "$SRC/.claude" "$TGT/.claude"

# 4 commit + push
git -C "$DST" add -A
if git -C "$DST" diff --cached --quiet; then
  echo "No changes to back up."
else
  git -C "$DST" commit -m "backup exiftool_mac config $(date '+%Y-%m-%d %H:%M')"
  git -C "$DST" push
fi
