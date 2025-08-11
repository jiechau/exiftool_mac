#/bin/bash

# alias date=gdate

# ARG
# . ./changedate_mov.sh 2023-01-03 18:30:00

# copy changedate_mov.sh to working dir 
#   (e.g. /Volumes/data/jiechau/_tmp_exiftool_mac/_ds_clips or ~/Downloads/ready) 
# the file must be named aaa.mov

# # 有這些可以改
# touch -t 202303022105.13 aaa.mov
# setfile -d "03/02/2023 21:05:13" aaa.mov
# # 最後決定使用
# # what really matter is 用 QuickTime:CreateDate，不是 QuickTime:MediaCreateDate
# exiftool -overwrite_original -api QuickTimeUTC -ee "-QuickTime:CreateDate='2023:03:13 06:17:17+08:00'" aaa.mov

# # view info
# exiftool -G -api QuickTimeUTC -ee aaa.mov | grep -i date
# mediainfo aaa.mov
# stat -x aaa.mov


# ARG
# . ./changedate_mov.sh 2023-01-03 18:30:00
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
  echo '# filename must be "aaa.mov"'
  echo '# for mac: alias date=gdate'
  echo ". ./changedate_mov.sh "$(date +"%Y-%m-%d %H:%M:%S")
  return
  exit
fi

echo "${dy}-${dm}-${dd} ${hh}:${hm}:${hs}"

# stop here
read -n 1 -s -r -p "Press any key to continue..."
echo # move to a new line after key press


# datalog
touch -t ${dy}${dm}${dd}${hh}${hm}.${hs} aaa.mov
setfile -d "${dm}/${dd}/${dy} ${hh}:${hm}:${hs}" aaa.mov
exiftool -overwrite_original -api QuickTimeUTC -ee \
 "-QuickTime:CreateDate='${dy}:${dm}:${dd} ${hh}:${hm}:${hs}+08:00'" aaa.mov
exiftool -overwrite_original -api QuickTimeUTC -ee \
 "-QuickTime:MediaCreateDate='${dy}:${dm}:${dd} ${hh}:${hm}:${hs}+08:00'" aaa.mov


# echo done
echo 'done'


