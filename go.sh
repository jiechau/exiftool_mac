#!/bin/bash
# 
# . ./go.sh 0 # sync Dropbox to local
# . ./go.sh 1 # write NAS (need mac local mount: /Volumes/)
# . ./go.sh 2 # write NAS, using intranet rsync 873
# . ./go.sh 3 # write NAS, using internet, only ds918, no ds212
# . ./go.sh camera_working # camera_working 雙向同步 (only ds918, 家裡 LAN)
# . ./go.sh cw             # 同上，camera_working 的縮寫
#
# 另外注意 UltraFit256/photo_,video_ 下面要有 it_exists.txt
#
# 2024/09/21 ./go.sh 2 突然不能用，後來 rsync 加 --protocol=29

alias date=/opt/homebrew/bin/gdate # 因為 mac 的 date 參數和 gnu 不一樣
alias rsync=/opt/homebrew/bin/rsync # 因為 mac 的 rsync 版本一直有問題

echo $(date +"%Y-%m-%d %H:%M:%S") 'start_go.sh'
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
#cd /Users/jiechau/life_codes/exiftool_mac # home mac
cd /Users/jiechau/life_codes/exiftool_mac # friDay mac
echo "$PWD"

# ARG
is_nas=4
if [ "$#" -ne 1 ]; then
   echo "no arg!!!!!!!!!!!!!!!!!!!!!!!!"
   return
   #exit 0
else
   is_nas=$1 # it should be '1'
fi

# 'camera_working' (縮寫 'cw') 是雙向同步 camera_working，和 0/1/2/3 的單向備份不一樣。
# 這裡換成 is_nas=9，讓下面 -eq 0/1/2/3 的區塊都不會進去。
is_camera_working=0
if [ "$is_nas" = "camera_working" ] || [ "$is_nas" = "cw" ]; then
   is_camera_working=1
   is_nas=9
fi
# 下面的區塊都是用 -eq 比數字，非數字會噴 "integer expression expected"
case "$is_nas" in
   ''|*[!0-9]*)
      echo "bad arg: '$1' (should be 0,1,2,3 or camera_working/cw)"
      return
      #exit 0
      ;;
esac

echo "args number = $#, OK"
echo "is_nas=${is_nas} (should be 0,1,2,3 or camera_working/cw)"
echo ""


# config/config_vars.txt
. config/config_vars.txt
# config/config_secrets.txt
. config/config_secrets.txt

echo "config/config_vars.txt"
echo $program_dir_base
echo $working_dir_base
echo $moved_dir_base
echo $problem_dir_base
echo $dest_video_dir_base # UltraFit256
echo $dest_photo_dir_base # UltraFit256
echo $dest_camera_dir_base # UltraFit256
echo $dest_camera_working_dir_base # UltraFit256
echo ""

# 這些是 dropbox 的實際目錄
# config/config_sourcedir.txt
filename_sourcedir="config/config_sourcedir.txt"
IFS=$'\r\n' GLOBIGNORE='*' command eval  'sourcedir=($(<$filename_sourcedir))'

echo $filename_sourcedir
echo ${remote_918_video_dir_base}
echo ${remote_918_photo_dir_base}
echo ${remote_918_camera_dir_base}
echo ${remote_918_camera_working_dir_base}
echo ${remote_1525_camera_dir_base}
echo ${remote_213_video_dir_base}
echo ${remote_213_photo_dir_base}
echo ""

# . go.sh 0 
#
# sync from dropbox to UltraFit256
if [ "$is_nas" -eq 0 ]; then

   tmp_idx=0
   for i in "${sourcedir[@]}"
   do
      # do whatever on "$i" here
      # echo $i
      if [[ $i != "#"* ]]; then
         #echo "yes #"
         DPDIR=$i
         echo "$DPDIR"
         if [ -d "$DPDIR" ]; then
            
            ((tmp_idx=tmp_idx+1))
            TMPDIR=${moved_dir_base}/${tmp_idx}
            echo $tmp_idx $TMPDIR

            # create/move to tmp folder
            mkdir -p ${TMPDIR}
            mv "${DPDIR}"/*.jpg "${TMPDIR}" 2>/dev/null
            mv "${DPDIR}"/*.png "${TMPDIR}" 2>/dev/null
            mv "${DPDIR}"/*.mov "${TMPDIR}" 2>/dev/null
            mv "${DPDIR}"/*.mp4 "${TMPDIR}" 2>/dev/null
            mv "${DPDIR}"/*.JPG "${TMPDIR}" 2>/dev/null
            mv "${DPDIR}"/*.PNG "${TMPDIR}" 2>/dev/null
            mv "${DPDIR}"/*.MOV "${TMPDIR}" 2>/dev/null
            mv "${DPDIR}"/*.MP4 "${TMPDIR}" 2>/dev/null


            # Directory to process
            DIR="${TMPDIR}"
            # Find all files with uppercase extensions and rename them
            find "$DIR" -type f | while IFS= read -r file; do
                # Get the file extension in uppercase
                ext=$(echo "${file##*.}" | tr '[:lower:]' '[:upper:]')
                # Get the file path without the extension
                base="${file%.*}"
                
                # Check if the extension is uppercase
                if [[ "$file" =~ \.[A-Z]+$ ]]; then
                    # Convert the extension to lowercase
                    newfile="${base}.$(echo "$ext" | tr '[:upper:]' '[:lower:]')"
                    # Rename the file
                    mv "$file" "$newfile"
                    echo "Renamed: $file -> $newfile"
                fi
            done

            # auto rotate
            # not sure if we need to do this
            #mogrify -auto-orient ${TMPDIR}/*.jpg
            #mogrify -auto-orient ${TMPDIR}/*.png

            # rename
            # move to UltraFit256
            CHECKFILE="${dest_photo_dir_base}/it_exists.txt"
            if [ -f "$CHECKFILE" ]; then
               echo "    USB photo exists"
               echo "    ====p1"
               exiftool -ext jpg -ext png -r -if "\$EXIF:DateTimeOriginal"     -d "${dest_photo_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<EXIF:DateTimeOriginal" "${TMPDIR}"
               echo "    ====p2"
               exiftool -ext jpg -ext png -r -if "not \$EXIF:DateTimeOriginal" -d "${dest_photo_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<File:FileModifyDate" "${TMPDIR}"
            fi
            CHECKFILE="${dest_video_dir_base}/it_exists.txt"
            if [ -f "$CHECKFILE" ]; then
               echo "    USB video exists"
               # fix timezone problem. if no 再用其他的
               # https://stackoverflow.com/questions/58936674/i-want-to-change-the-file-name-with-exiftool-to-result-of-adding-time-zone-9
               # -api QuickTimeUTC -ee
               # -globaltimeshift 8 -ee  
               echo "    ====v1"
               exiftool -api QuickTimeUTC -ee -ext mov -ext mp4 -r -if "\$QuickTime:CreateDate" -d "${dest_video_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<QuickTime:CreateDate" "${TMPDIR}"
               echo "    ====v2"
               exiftool -api QuickTimeUTC -ee -ext mov -ext mp4 -r -if "not \$QuickTime:CreateDate" -d "${dest_video_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<QuickTime:MediaCreateDate" "${TMPDIR}"

            # the sit part/end


            fi


         else
            #echo "no DIR"
            :
         fi


      else
         #echo "no #"
         :
      fi

   done
   echo "is_nas=${is_nas} done"

fi

# ??
# . go.sh 1 才會 # if sync to NAS
#
# if sync to NAS
if [ "$is_nas" -eq 1 ]; then

   # rsync UltraFit256 to 918, 1525
   echo ""

   CHECKFILE="/Volumes/${remote_918_video_dir_base}/it_exists.txt"
   if [ -f "$CHECKFILE" ]; then
      echo "918 video exists: ${CHECKFILE}"
      rsync -a --delete "${dest_video_dir_base}/" "/Volumes/${remote_918_video_dir_base}"
   fi

   CHECKFILE="/Volumes/${remote_918_photo_dir_base}/it_exists.txt"
   if [ -f "$CHECKFILE" ]; then
      echo "918 photo exists: $CHECKFILE"
      rsync -a --delete "${dest_photo_dir_base}/" "/Volumes/${remote_918_photo_dir_base}"
   fi

   # camera: 來源端也要檢查 (UltraFit256 沒掛上就不要 --delete 遠端)
   CHECKFILE="/Volumes/${remote_918_camera_dir_base}"
   if [ -d "$CHECKFILE" ] && [ -f "${dest_camera_dir_base}/it_exists.txt" ]; then
      echo "918 camera exists: $CHECKFILE"
      rsync -a --delete "${dest_camera_dir_base}/" "/Volumes/${remote_918_camera_dir_base}"
   else
      echo "918 camera skipped: $CHECKFILE / ${dest_camera_dir_base}/it_exists.txt"
   fi

   # CHECKFILE="/Volumes/${remote_213_video_dir_base}/it_exists.txt"
   # if [ -f "$CHECKFILE" ]; then
   #    echo "213 video exists: $CHECKFILE"
   #    rsync -a --delete "${dest_video_dir_base}/" "/Volumes/${remote_213_video_dir_base}"
   # fi
   # 
   # CHECKFILE="/Volumes/${remote_213_photo_dir_base}/it_exists.txt"
   # if [ -f "$CHECKFILE" ]; then
   #    echo "213 photo exists: $CHECKFILE"
   #    rsync -a --delete "${dest_photo_dir_base}/" "/Volumes/${remote_213_photo_dir_base}"
   # fi

   echo "is_nas=${is_nas} done"
fi


# . go.sh 2 才會 # write NAS, using rsync 873
#
# if sync to NAS
if [ "$is_nas" -eq 2 ]; then
   # 918, strangly it's format is 192.168.123.163::video/video_latest
   # --protocol=29
   echo "--dry-run admin@192.168.123.163::${remote_918_video_dir_base}/it_exists.txt"
   echo "sshpass -p $pw rsync --port=873 -e \"ssh -p 22\" --protocol=29 --dry-run --timeout=10 admin@192.168.123.163::${remote_918_video_dir_base}/it_exists.txt"
   # 這個 echo 要放在 sshpass 前面。放後面的話 $? 會變成 echo 的結果 (永遠 0)，
   # 下面的 if 就等於沒有檢查，--delete 會照跑。1525 那段本來就是這樣寫的。
   sshpass -p $pw rsync --port=873 -e "ssh -p 22" --protocol=29 --dry-run --timeout=10 admin@192.168.123.163::${remote_918_video_dir_base}/it_exists.txt
   if [ $? -eq 0 ]; then
      sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a --delete --protocol=29 "${dest_video_dir_base}/" admin@192.168.123.163::${remote_918_video_dir_base}
      echo "163::video" $?
      sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a --delete --protocol=29 "${dest_photo_dir_base}/" admin@192.168.123.163::${remote_918_photo_dir_base} 
      echo "163::photo" $?
      # camera: 本機來源要有 it_exists.txt (UltraFit256 沒掛上就不要 --delete 遠端)
      if [ -f "${dest_camera_dir_base}/it_exists.txt" ]; then
         sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a --delete --protocol=29 "${dest_camera_dir_base}/" admin@192.168.123.163::${remote_918_camera_dir_base}
         echo "163::camera" $?
      else
         echo "163::camera skipped, no ${dest_camera_dir_base}/it_exists.txt"
      fi
   else
      echo "rsync 163 fail:" $?
   fi

   
   # # 213, strangly it's format is 192.168.123.162:/volume1/video/video_latest
   # echo "--dry-run admin@192.168.123.162:/volume1/${remote_213_video_dir_base}/it_exists.txt"
   # echo "sshpass -p $pw rsync --port=873 -e \"ssh -p 22\" --protocol=29 --dry-run --timeout=10 admin@192.168.123.162:/volume1/${remote_213_video_dir_base}/it_exists.txt" 
   # sshpass -p $pw rsync --port=873 -e "ssh -p 22" --protocol=29 --dry-run --timeout=10 admin@192.168.123.162:/volume1/${remote_213_video_dir_base}/it_exists.txt 
   # if [ $? -eq 0 ]; then
   #    sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a --delete --protocol=29 "${dest_video_dir_base}/" admin@192.168.123.162:/volume1/${remote_213_video_dir_base} 
   #    echo "162:/../video" $?
   #    sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a --delete --protocol=29 "${dest_photo_dir_base}/" admin@192.168.123.162:/volume1/${remote_213_photo_dir_base}
   #    echo "162:/../photo" $?
   # else
   #    echo "rsync 162 fail:" $?   
   # fi
   

   # 1525, strangly it's format is 192.168.123.164::video/video_latest
   echo "--dry-run jie@192.168.123.164::${remote_1525_video_dir_base}/it_exists.txt"
   echo "sshpass -p $pw_1525 rsync --port=873 -e \"ssh -p 22\" --protocol=29 --dry-run --timeout=10 jie@192.168.123.164::${remote_1525_video_dir_base}/it_exists.txt" 
   sshpass -p $pw_1525 rsync --port=873 -e "ssh -p 22" --protocol=29 --dry-run --timeout=10 jie@192.168.123.164::${remote_1525_video_dir_base}/it_exists.txt 
   if [ $? -eq 0 ]; then
      sshpass -p $pw_1525 rsync --port=873 -e "ssh -p 22" -a --delete --protocol=29 "${dest_video_dir_base}/" jie@192.168.123.164::${remote_1525_video_dir_base} 
      echo "164::DSfile/_home/_jie/video/video_latest" $?
      sshpass -p $pw_1525 rsync --port=873 -e "ssh -p 22" -a --delete --protocol=29 "${dest_photo_dir_base}/" jie@192.168.123.164::${remote_1525_photo_dir_base}
      echo "164::DSfile/_home/_jie/video/photo_latest" $?
      # camera: 本機來源要有 it_exists.txt (UltraFit256 沒掛上就不要 --delete 遠端)
      if [ -f "${dest_camera_dir_base}/it_exists.txt" ]; then
         sshpass -p $pw_1525 rsync --port=873 -e "ssh -p 22" -a --delete --protocol=29 "${dest_camera_dir_base}/" jie@192.168.123.164::${remote_1525_camera_dir_base}
         echo "164::${remote_1525_camera_dir_base}" $?
      else
         echo "164::camera skipped, no ${dest_camera_dir_base}/it_exists.txt"
      fi
   else
      echo "rsync 164 fail:" $?   
   fi



   # test
   #sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a --delete /Users/jiechau/tmp/DS918file/file_ttt/ admin@192.168.123.163::DS918file/file_ttt
   echo
   echo "is_nas=${is_nas} done"
fi


# . go.sh 3 # write NAS, using public, only ds918, no ds212
#
# if sync to NAS
if [ "$is_nas" -eq 3 ]; then
   # 918
   # 918
   echo "--dry-run admin@$pi_public::${remote_918_video_dir_base}/it_exists.txt"
   sshpass -p $pw_public rsync --port=$pp_public -e "ssh -p $pp_public" --dry-run --timeout=10 admin@$pi_public::${remote_918_video_dir_base}/it_exists.txt
   if [ $? -eq 0 ]; then
      sshpass -p $pw_public rsync --port=$pp_public -e "ssh -p $pp_public" -a --delete "${dest_video_dir_base}/" admin@$pi_public::${remote_918_video_dir_base} 
      echo "$pi_public::video" $?
      sshpass -p $pw_public rsync --port=$pp_public -e "ssh -p $pp_public" -a --delete "${dest_photo_dir_base}/" admin@$pi_public::${remote_918_photo_dir_base} 
      echo "$pi_public::photo" $?
      # camera: 本機來源要有 it_exists.txt (UltraFit256 沒掛上就不要 --delete 遠端)
      if [ -f "${dest_camera_dir_base}/it_exists.txt" ]; then
         sshpass -p $pw_public rsync --port=$pp_public -e "ssh -p $pp_public" -a --delete "${dest_camera_dir_base}/" admin@$pi_public::${remote_918_camera_dir_base}
         echo "$pi_public::camera" $?
      else
         echo "$pi_public::camera skipped, no ${dest_camera_dir_base}/it_exists.txt"
      fi
   else
      echo "rsync $pi_public fail:" $?   
   fi
   echo
   echo "is_nas=${is_nas} done"
fi


# . go.sh camera_working  ( . go.sh cw )
#
# camera_working 雙向同步，只有 ds918，只走家裡 LAN 的 rsync 873。
# 和 0/1/2/3 不一樣的地方：
#   1. 兩個方向都跑一次 (先拉下來，再推上去)
#   2. 不能用 --delete。雙向同步分不出「這邊刪掉了」和「那邊新增了」，
#      加了 --delete 會互相砍檔。所以刪除不會傳到另一邊，要自己兩邊各刪一次。
#   3. -u = --update，只有比較新的檔案才會蓋過去。兩邊都改到同一個檔的話，
#      mtime 比較新的贏，舊的那份會被蓋掉。
if [ "$is_camera_working" -eq 1 ]; then

   CHECKFILE="${dest_camera_working_dir_base}/it_exists.txt"
   if [ ! -f "$CHECKFILE" ]; then
      echo "no ${CHECKFILE} (UltraFit256 沒掛上?), stop"
   else
      echo "local  : ${dest_camera_working_dir_base}"
      echo "remote : admin@192.168.123.163::${remote_918_camera_working_dir_base}"
      echo "--dry-run admin@192.168.123.163::${remote_918_camera_working_dir_base}/it_exists.txt"
      sshpass -p $pw rsync --port=873 -e "ssh -p 22" --protocol=29 --dry-run --timeout=10 admin@192.168.123.163::${remote_918_camera_working_dir_base}/it_exists.txt
      if [ $? -eq 0 ]; then
         # @eaDir 是 Synology 自己產生的縮圖目錄，不要拉到 mac 上
         echo "    ==== pull  163 -> local"
         sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a -u -v --protocol=29 \
          --exclude '@eaDir' --exclude '.DS_Store' --exclude '.Trashes' \
          admin@192.168.123.163::${remote_918_camera_working_dir_base}/ "${dest_camera_working_dir_base}/"
         echo "    pull" $?
         echo "    ==== push  local -> 163"
         sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a -u -v --protocol=29 \
          --exclude '@eaDir' --exclude '.DS_Store' --exclude '.Trashes' \
          "${dest_camera_working_dir_base}/" admin@192.168.123.163::${remote_918_camera_working_dir_base}
         echo "    push" $?
      else
         echo "rsync 163 fail:" $?
      fi
   fi

   echo
   echo "is_nas=camera_working done"
fi


# end
echo "ddone"
echo $(date +"%Y-%m-%d %H:%M:%S") 'end_go.sh'
echo ""




