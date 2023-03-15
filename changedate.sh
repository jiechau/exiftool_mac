#/bin/bash

# ARG
# . ./changedate.sh 2023-01-03 18:30:00

# copy changedate.sh to working dir 
#   (e.g. /Volumes/data/jiechau/_tmp_exiftool_mac/_ds_clips or ~/Downloads/ready) 
# the file must be named aaa.mp4

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
# . ./changedate.sh 2023-01-03 18:30:00
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
  echo '# filename must be "aaa.mp4"'
  echo '# for mac: alias date=gdate'
  echo '. ./changedate.sh 2023-01-03 18:30:00'
  return
  exit
fi

echo "${dy}-${dm}-${dd} ${hh}:${hm}:${hs}"

# datalog
touch -t ${dy}${dm}${dd}${hh}${hm}.${hs} aaa.mp4
setfile -d "${dm}/${dd}/${dy} ${hh}:${hm}:${hs}" aaa.mp4
exiftool -overwrite_original -api QuickTimeUTC -ee \
 "-QuickTime:CreateDate='${dy}:${dm}:${dd} ${hh}:${hm}:${hs}+08:00'" aaa.mp4



