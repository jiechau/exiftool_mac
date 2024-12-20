#/bin/bash

# alias date=gdate

# ARG
# . ./changedate_mp4_batch.sh 2023-01-03 18:30:00

# 目前整個目錄下的檔案都會改變。要小心。

# # 有這些可以改
# touch -t 202303022105.13 aaa.mp4
# setfile -d "03/02/2023 21:05:13" aaa.mp4
# # 最後決定使用
# # what really matter is 用 QuickTime:CreateDate，不是 QuickTime:MediaCreateDate
# exiftool -overwrite_original -api QuickTimeUTC -ee "-QuickTime:CreateDate='2023:03:13 06:17:17+08:00'" aaa.mp4

# # view info
# exiftool -G -api QuickTimeUTC -ee aaa.mp4 | grep -i date
# mediainfo aaa.mp4
# stat -x aaa.mp4


# ARG
# . ./changedate_mp4_batch.sh 2023-01-03 18:30:00
# echo $(date +"%Y-%m-%d %H:%M:%S") 'start'
if [ "$#" -eq 2 ]; then
  ee=$1
  tt=$2
  dy=$(date --date="${ee} ${tt} 0 hour ago" +'%Y')
  dm=$(date --date="${ee} ${tt} 0 hour ago" +'%m')
  dd=$(date --date="${ee} ${tt} 0 hour ago" +'%d')
  hh=$(date --date="${ee} ${tt} 0 hour ago" +'%H')
  hm=$(date --date="${ee} ${tt} 0 hour ago" +'%M')
  hs=$(date --date="${ee} ${tt} 0 hour ago" +'%S')
else
  echo '# for mac: alias date=gdate'
  echo ". ./changedate_mp4_batch.sh "$(date +"%Y-%m-%d %H:%M:%S")
  return
  exit
fi

current_dir=$(pwd)
echo "Current directory: $current_dir"
echo "${dy}-${dm}-${dd} ${hh}:${hm}:${hs}"

# stop here
read -n 1 -s -r -p "Press any key to continue..."
echo # move to a new line after key press

# Loop through all .mp4 files in current directory
for video in *.mp4; do
    # Check if files exist (prevent error if no .mp4 files found)
    if [ -f "$video" ]; then
        echo "Found video file: $video"
        # You can add your commands here to process each video file
        # For example:
        # ffplay "$video"  # If you want to play it with ffmpeg
        # vlc "$video"     # If you want to play it with vlc

        # change date
        touch -t ${dy}${dm}${dd}${hh}${hm}.${hs} $video
        setfile -d "${dm}/${dd}/${dy} ${hh}:${hm}:${hs}" $video
        exiftool -overwrite_original -api QuickTimeUTC -ee \
         "-QuickTime:CreateDate='${dy}:${dm}:${dd} ${hh}:${hm}:${hs}+08:00'" $video
        exiftool -overwrite_original -api QuickTimeUTC -ee \
         "-QuickTime:MediaCreateDate='${dy}:${dm}:${dd} ${hh}:${hm}:${hs}+08:00'" $video

    fi
done

# echo done
echo 'done'


