#/bin/bash

# ARG
# . ./showinfo.sh aaa.mp4


# exiftool -G -api QuickTimeUTC -ee aaa.mp4 | grep -i date
# mediainfo aaa.mp4 | grep -i date
# stat -x aaa.mp4


# ARG
fname=aaa.mp4
if [ "$#" -eq 1 ]; then
  fname=$1
fi

exiftool -G -api QuickTimeUTC -ee $fname | grep -i date
mediainfo $fname | grep -i date
stat -x $fname



