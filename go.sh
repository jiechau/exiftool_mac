#!/bin/bash
# 
# . ./go.sh
# . ./go.sh 1 # write NAS
#

echo $(date +"%Y-%m-%d %H:%M:%S") 'start_go.sh'
export PATH=/usr/local/bin:$PATH
cd /Users/jiechau/life_codes/exiftool_mac
echo "$PWD"

# ARG
is_nas=0
if [ "$#" -eq 1 ]; then
  is_nas=$1 # it should be '1'
fi
echo "NAS=${is_nas}"
#return
#exit 0

# config/config_vars.txt
. config/config_vars.txt
echo $program_dir_base
echo $working_dir_base
echo $moved_dir_base
echo $problem_dir_base
echo $dest_photo_dir_base
echo $dest_video_dir_base
echo ""

# config/config_sourcedir.txt
filename_sourcedir="config/config_sourcedir.txt"
IFS=$'\r\n' GLOBIGNORE='*' command eval  'sourcedir=($(<$filename_sourcedir))'
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


         # the sit part/start


         # create/move to tmp folder
         mkdir -p ${TMPDIR}
         mv "${DPDIR}"/*.jpg "${TMPDIR}" 2>/dev/null
         mv "${DPDIR}"/*.png "${TMPDIR}" 2>/dev/null
         mv "${DPDIR}"/*.mov "${TMPDIR}" 2>/dev/null
         mv "${DPDIR}"/*.mp4 "${TMPDIR}" 2>/dev/null

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
            exiftool -api QuickTimeUTC -ee -ext mov -ext mp4 -r -if "\$MediaCreateDate" -d "${dest_video_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<MediaCreateDate" "${TMPDIR}"
            echo "    ====v2"
            exiftool -api QuickTimeUTC -ee -ext mov -ext mp4 -r -if "not \$MediaCreateDate" -d "${dest_video_dir_base}/%Y_%m%d_/%Y-%m-%d %H.%M.%S%%-c.%%e" "-filename<CreateDate" "${TMPDIR}"

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

# if sync to NAS
if [ "$is_nas" -ne 1 ]; then
  return
  exit 0
fi

# rsync UltraFit256 to 162
echo ""
CHECKFILE="${remote_918_photo_dir_base}/it_exists.txt"
if [ -f "$CHECKFILE" ]; then
   echo "918 photo exists"
   rsync -a --delete "${dest_photo_dir_base}/" "${remote_918_photo_dir_base}"
fi
CHECKFILE="${remote_213_photo_dir_base}/it_exists.txt"
if [ -f "$CHECKFILE" ]; then
   echo "213 photo exists"
   rsync -a --delete "${dest_photo_dir_base}/" "${remote_213_photo_dir_base}"
fi
CHECKFILE="${remote_918_video_dir_base}/it_exists.txt"
if [ -f "$CHECKFILE" ]; then
   echo "918 video exists"
   rsync -a --delete "${dest_video_dir_base}/" "${remote_918_video_dir_base}"
fi
CHECKFILE="${remote_213_video_dir_base}/it_exists.txt"
if [ -f "$CHECKFILE" ]; then
   echo "213 video exists"
   rsync -a --delete "${dest_video_dir_base}/" "${remote_213_video_dir_base}"
fi


# end
echo "ddone"
echo $(date +"%Y-%m-%d %H:%M:%S") 'end_go.sh'
echo ""




