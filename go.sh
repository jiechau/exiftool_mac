#!/bin/bash
# 
# . ./go.sh 0 # sync Dropbox to local
# . ./go.sh 1 # write NAS (need mac local mount: /Volumes/)
# . ./go.sh 2 # write NAS, using intranet rsync 873
# . ./go.sh 3 # write NAS, using internet, only ds918, no ds212
#
# 另外注意 UltraFit256/photo_,video_ 下面要有 it_exists.txt
#

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
echo "args number = $#, OK"
echo "is_nas=${is_nas} (should be 0,1,2,3)"
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
echo ""

# 這些是 dropbox 的實際目錄
# config/config_sourcedir.txt
filename_sourcedir="config/config_sourcedir.txt"
IFS=$'\r\n' GLOBIGNORE='*' command eval  'sourcedir=($(<$filename_sourcedir))'

echo $filename_sourcedir
echo ${remote_918_video_dir_base}
echo ${remote_918_photo_dir_base}
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


# . go.sh 1 才會 # if sync to NAS
#
# if sync to NAS
if [ "$is_nas" -eq 1 ]; then

   # rsync UltraFit256 to 162
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

   CHECKFILE="/Volumes/${remote_213_video_dir_base}/it_exists.txt"
   if [ -f "$CHECKFILE" ]; then
      echo "213 video exists: $CHECKFILE"
      rsync -a --delete "${dest_video_dir_base}/" "/Volumes/${remote_213_video_dir_base}"
   fi

   CHECKFILE="/Volumes/${remote_213_photo_dir_base}/it_exists.txt"
   if [ -f "$CHECKFILE" ]; then
      echo "213 photo exists: $CHECKFILE"
      rsync -a --delete "${dest_photo_dir_base}/" "/Volumes/${remote_213_photo_dir_base}"
   fi

   echo "is_nas=${is_nas} done"
fi


# . go.sh 2 才會 # write NAS, using rsync 873
#
# if sync to NAS
if [ "$is_nas" -eq 2 ]; then
   # 918, strangly it's format is 192.168.123.163::video/video_latest
   echo "--dry-run admin@192.168.123.163::${remote_918_video_dir_base}/it_exists.txt"
   sshpass -p $pw rsync --port=873 -e "ssh -p 22" --dry-run --timeout=10 admin@192.168.123.163::${remote_918_video_dir_base}/it_exists.txt
   if [ $? -eq 0 ]; then
      sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a --delete "${dest_video_dir_base}/" admin@192.168.123.163::${remote_918_video_dir_base}
      echo "163::video" $?
      sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a --delete "${dest_photo_dir_base}/" admin@192.168.123.163::${remote_918_photo_dir_base} 
      echo "163::photo" $?
   else
      echo "rsync 163 fail:" $?
   fi
   # 213, strangly it's format is 192.168.123.162:/volume1/video/video_latest
   echo "--dry-run admin@192.168.123.162:/volume1/${remote_213_video_dir_base}/it_exists.txt"
   sshpass -p $pw rsync --port=873 -e "ssh -p 22" --dry-run --timeout=10 admin@192.168.123.162:/volume1/${remote_213_video_dir_base}/it_exists.txt 
   if [ $? -eq 0 ]; then
      sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a --delete "${dest_video_dir_base}/" admin@192.168.123.162:/volume1/${remote_213_video_dir_base} 
      echo "162:/../video" $?
      sshpass -p $pw rsync --port=873 -e "ssh -p 22" -a --delete "${dest_photo_dir_base}/" admin@192.168.123.162:/volume1/${remote_213_photo_dir_base}
      echo "162:/../photo" $?
   else
      echo "rsync 162 fail:" $?   
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
   echo "--dry-run admin@$pi::${remote_918_video_dir_base}/it_exists.txt"
   sshpass -p $pw rsync --port=$pp -e "ssh -p $pp" --dry-run --timeout=10 admin@$pi::${remote_918_video_dir_base}/it_exists.txt
   if [ $? -eq 0 ]; then
      sshpass -p $pw rsync --port=$pp -e "ssh -p $pp" -a --delete "${dest_video_dir_base}/" admin@$pi::${remote_918_video_dir_base} 
      echo "$pi::video" $?
      sshpass -p $pw rsync --port=$pp -e "ssh -p $pp" -a --delete "${dest_photo_dir_base}/" admin@$pi::${remote_918_photo_dir_base} 
      echo "$pi::photo" $?
   else
      echo "rsync $pi fail:" $?   
   fi
   echo
   echo "is_nas=${is_nas} done"
fi


# end
echo "ddone"
echo $(date +"%Y-%m-%d %H:%M:%S") 'end_go.sh'
echo ""




