#/bin/bash

# exiftool −overwrite_original_in_place -r -tagsFromFile SOURCE.JPG -gps:all .
# exiftool -api QuickTimeUTC -ee -G -overwrite_original -tagsFromFile gps_hby.mov -QuickTime:GPSCoordinates aaa.mp4 
exiftool -api QuickTimeUTC -ee -G -overwrite_original -tagsFromFile /Users/jiechau/life_codes/exiftool_mac/gps_sample/gps_468.mp4 -QuickTime:GPSCoordinates aaa.mp4 

# view info
# exiftool -api QuickTimeUTC -ee -G aaa.mp4  | grep -i gps

