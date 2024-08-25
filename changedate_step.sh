#/bin/bash

# alias date=gdate

# ARG
# 在那個需要工作的目錄下 改變目錄下所有照片日期 步進1秒
# . /Users/jiechau_huang/life_codes/exiftool_mac/changedate_step.sh 2023-01-03 18:30:00

# # view info
# exiftool -G aaa.jpg | grep -i date
# stat -x aaa.jpg

# echo $(date +"%Y-%m-%d %H:%M:%S") 'start'
if [ "$#" -eq 2 ]; then
  ee=$1
  tt=$2
  orig_dt="${ee} ${tt}"
else
  echo '# for mac: alias date=gdate'
  echo '# run'
  echo ". ./changedate_step.sh "$(date +"%Y-%m-%d %H:%M:%S")
  echo "# run under the dir you like to work"
  echo "# put all pics in that dir"
  echo ". /Users/jiechau_huang/life_codes/exiftool_mac/changedate_step.sh "$(date +"%Y-%m-%d %H:%M:%S")
  return
  exit
fi

# find out NUM
#NUM_pics=1
#echo $PWD
#NUM_pics=$(find . -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.png' \) | wc -l)
#echo $NUM_pics


ii=0
for filename_this in *.{jpg,JPG,jpeg,JPEG,png,PNG}
do
  # Check if file exists due to the glob pattern possibly not finding a match
  if [ -e "$filename_this" ]
  then
    # orig
    echo $filename_this
    # new date time
    # /opt/homebrew/bin/gdate -d "2023-01-03 18:30:00 GMT+08:00 + 100 seconds" "+%Y-%m-%d %H:%M:%S"
    dt_file_file=$(gdate -d "$orig_dt GMT+08:00 + $ii seconds" "+%Y-%m-%d %H:%M:%S")
    echo $dt_file_file # 2023-01-05 00:00:07
    dy=$(date --date="$dt_file_file GMT+08:00" +'%Y')
    dm=$(date --date="$dt_file_file GMT+08:00" +'%m')
    dd=$(date --date="$dt_file_file GMT+08:00" +'%d')
    hh=$(date --date="$dt_file_file GMT+08:00" +'%H')
    hm=$(date --date="$dt_file_file GMT+08:00" +'%M')
    hs=$(date --date="$dt_file_file GMT+08:00" +'%S')
    echo "${dy}-${dm}-${dd} ${hh}:${hm}:${hs}" # 2023-01-05 00:00:07
    # set
    touch -t ${dy}${dm}${dd}${hh}${hm}.${hs} "$filename_this"
    setfile -d "${dm}/${dd}/${dy} ${hh}:${hm}:${hs}" "$filename_this"
    exiftool "-DateTimeOriginal=${dy}-${dm}-${dd} ${hh}:${hm}:${hs}" "-CreateDate=${dy}-${dm}-${dd} ${hh}:${hm}:${hs}" -overwrite_original "$filename_this"
    #exiftool -overwrite_original -api QuickTimeUTC -ee \
    # "-QuickTime:CreateDate='${dy}:${dm}:${dd} ${hh}:${hm}:${hs}+08:00'" aaa.mp4
    # +1
    ii=$((ii + 1))
  fi
done






