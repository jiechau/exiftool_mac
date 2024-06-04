RUN
===

mac
need /usr/local/bin/exiftool (e.g. $ brew install exiftool)
need ~/exif_working_dir

cd ~
cd life_codes/exiftool_mac
. go.sh 0 # copy from Dropbox / delete Dropbox (to )
# 整理 ~/exif_working_dir/UltraFit256/photo_latest, video_latest
. go.sh 1 # 需要 mac 連結網路裝置 to DS212 and DS918 (1 和 2 相同，但是 2 比較簡單) 
. go.sh 2 # rsync 在家裡的時候 to DS212 and DS918
. go.sh 3 # rsync 在外面的時候 to DS918 only


problems
========

cron operation not permitted
https://apple.stackexchange.com/questions/378553/crontab-operation-not-permitted
add /usr/sbin/cron to full access disk

exiftool not found:
add export PATH=/usr/local/bin:$PATH to go.sh


README
======

exif tools macos:
https://exiftool.org/
(download dmg)

xnview
https://www.xnview.com/en/nconvert/
(download dmg)

ImageMagick
https://imagemagick.org/script/download.php#macosx
(brew install imagemagick)

# auto rotate
# not sure if we need to do this
#mogrify -auto-orient ${TMPDIR}/*.jpg
#mogrify -auto-orient ${TMPDIR}/*.png

exiftool extractembedded
exiftool -ee 

photo
# exiftool -ee -j aaa.jpb | grep -i date
exiftool -ext jpg -ext png -r -if "\$EXIF:DateTimeOriginal"     -d "${dest_photo_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<EXIF:DateTimeOriginal" "${TMPDIR}"
exiftool -ext jpg -ext png -r -if "not \$EXIF:DateTimeOriginal" -d "${dest_photo_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<File:FileModifyDate" "${TMPDIR}"

video
# fix timezone problem. if no 再用其他的
# https://stackoverflow.com/questions/58936674/i-want-to-change-the-file-name-with-exiftool-to-result-of-adding-time-zone-9
# exiftool -api QuickTimeUTC -ee aaa.mp4
# exiftool -globaltimeshift 8 -ee  aaa.mp4
exiftool -api QuickTimeUTC -ee -ext mov -ext mp4 -r -if "\$MediaCreateDate" -d "${dest_video_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<MediaCreateDate" "${TMPDIR}"
exiftool -api QuickTimeUTC -ee -ext mov -ext mp4 -r -if "not \$MediaCreateDate" -d "${dest_video_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<CreateDate" "${TMPDIR}"

# change date for nas mp4
touch -t 202303022105.08 aaa.mp4
setfile -d "03/02/2023 21:05:07" aaa.mp4
exiftool -api QuickTimeUTC -ee "-MediaCreateDate='2023:03:02 21:05:09+08:00'" ccc.mp4 
exiftool -api QuickTimeUTC -ee "-CreateDate='2023:03:02 21:05:09+08:00'" ccc.mp4 
exiftool -api QuickTimeUTC -ee ccc.mp4

# change gps for nas mp4
exiftool -api QuickTimeUTC -ee -G -overwrite_original -tagsFromFile /Users/jiechau_huang/life_codes/exiftool_mac/gps_sample/gps_hby.mp4 -QuickTime:GPSCoordinates aaa.mp4

# 711
# under same folder
magick mogrify -path ./ -resize 50% -quality 50 *



cd ~
cd life_codes/exiftool_mac
. go.sh 0 # copy from Dropbox / delete Dropbox (to )
# 整理 ~/exif_working_dir/UltraFit256/photo_latest, video_latest
. go.sh 1 # 需要 mac 連結網路裝置 to DS212 and DS918 (1 和 2 相同，但是 2 比較簡單) 
. go.sh 2 # rsync 在家裡的時候 to DS212 and DS918
. go.sh 3 # rsync 在外面的時候 to DS918 only


