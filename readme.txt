This file is an engineer's memo only. 
Do not reference or modify this file until you are explicitly told to do so.



RUN
===

mac
need /usr/local/bin/exiftool or /opt/homebrew/bin/exiftool (e.g. $ brew install exiftool)
need ~/exif_working_dir
need sshpass (go.sh 2 / 3 才會用到)
需要
alias date=/opt/homebrew/bin/gdate # 因為 mac 的 date 參數和 gnu 不一樣 (brew install coreutils)
alias rsync=/opt/homebrew/bin/rsync # 因為 mac 的 rsync 版本一直有問題

cd ~
cd life_codes/exiftool_mac
. go.sh 0  # copy from Dropbox / delete Dropbox (to )
# 整理 ~/exif_working_dir/UltraFit256/photo_latest, video_latest
. go.sh 1  # 需要 mac 連結網路裝置 to DS918 (1 和 2 相同，但是 2 比較簡單)
. go.sh 2  # rsync 在家裡的時候 to DS918 and DS1525
. go.sh 3  # rsync 在外面的時候 to DS918 only
. go.sh cw # camera_working 從 nas 抓回本機 (= . go.sh camera_working)

# 注意 0/1/2/3 都是 本機 -> nas
# 只有 cw 是 nas -> 本機，方向相反


三個 library + 一個工作區
========================

photo_latest   go.sh 0 從 Dropbox 收進來，自動改檔名
video_latest   同上
camera_latest  相機 SD 卡，自己手動整理 (YYYY_MMDD_camera_event/機身-鏡頭/)，go.sh 0 不管它
camera_working windows 那台做 photoshop 的地方，windows 自己和 nas 同步 (go.bat)，
               mac 只負責用 . go.sh cw 把結果抓回來。--delete 砍的是本機，
               本機不要放任何只有本機有的東西。

DS212 (192.168.123.162) 已經退休了，go.sh 和 config_vars.txt 裡面是註解掉不是刪掉。


problems and solutions
======================

cron operation not permitted
https://apple.stackexchange.com/questions/378553/crontab-operation-not-permitted
add /usr/sbin/cron to full access disk

exiftool not found:
add export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH to go.sh

rsync 跑完什麼事都沒發生:
先看 it_exists.txt。每個 library 最上面都要有這個空檔案，這是 UltraFit256 有沒有
掛上的證明。沒掛上的話路徑還是會通 (變成空目錄)，--delete 就會把遠端清光。

go.sh 2 突然不能用 (2024/09/21):
rsync 加 --protocol=29。新的 protocol 對這幾台 Synology 的 daemon 不通了。

遠端路徑找不到:
host::module/subdir 的第一段是 Synology 分享資料夾的名字，不是檔案系統路徑。
列出某台實際 export 了什麼:
sshpass -p "$pw" rsync --port=873 --protocol=29 admin@192.168.123.163::


scripts
=======

go.sh                   0/1/2/3/cw，見上面
showinfo.sh             . showinfo.sh aaa.mp4  看 exiftool / mediainfo / stat 三種日期
changedate_step.sh      . changedate_step.sh 2023-01-03 18:30:00
                        目錄下所有照片，時間每張 +1 秒
changedate_mp4.sh       單一檔案，檔名必須叫 aaa.mp4
changedate_mov.sh       單一檔案，檔名必須叫 aaa.mov
changedate_mp4_batch.sh 目前整個目錄下的 .mp4 都會改成同一個時間。要小心。
gps_468.sh              把 gps_sample/ 裡面存好的座標蓋到 aaa.mp4
gps_ccd.sh              gps_sample/ 那幾個檔案本身就是座標，不要刪
gps_hby.sh
gps_hess.sh

# 這些都是 -overwrite_original，直接改原檔


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
# 現在 go.sh 裡面跑的是這兩行 (QuickTime:CreateDate 優先，沒有才用 MediaCreateDate)
exiftool -api QuickTimeUTC -ee -ext mov -ext mp4 -r -if "\$QuickTime:CreateDate"     -d "${dest_video_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<QuickTime:CreateDate" "${TMPDIR}"
exiftool -api QuickTimeUTC -ee -ext mov -ext mp4 -r -if "not \$QuickTime:CreateDate" -d "${dest_video_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<QuickTime:MediaCreateDate" "${TMPDIR}"
# 以前寫的版本，順序是反的，留著參考
# exiftool -api QuickTimeUTC -ee -ext mov -ext mp4 -r -if "\$MediaCreateDate"     -d "..." "-filename<MediaCreateDate" "${TMPDIR}"
# exiftool -api QuickTimeUTC -ee -ext mov -ext mp4 -r -if "not \$MediaCreateDate" -d "..." "-filename<CreateDate" "${TMPDIR}"

# change date for nas mp4
touch -t 202303022105.08 aaa.mp4
setfile -d "03/02/2023 21:05:07" aaa.mp4
exiftool -api QuickTimeUTC -ee "-MediaCreateDate='2023:03:02 21:05:09+08:00'" ccc.mp4 
exiftool -api QuickTimeUTC -ee "-CreateDate='2023:03:02 21:05:09+08:00'" ccc.mp4 
exiftool -api QuickTimeUTC -ee ccc.mp4

# change gps for nas mp4
exiftool -api QuickTimeUTC -ee -G -overwrite_original -tagsFromFile /Users/jiechau/life_codes/exiftool_mac/gps_sample/gps_hby.mp4 -QuickTime:GPSCoordinates aaa.mp4

# 711
# under same folder
magick mogrify -path ./ -resize 50% -quality 50 *

# extract .mp3 from .mp4
for file in *.mp4; do ffmpeg -i "$file" -q:a 0 -map a "${file%.mp4}.mp3"; done
