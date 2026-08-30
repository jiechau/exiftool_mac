@echo off
rem ============================================================================
rem  go.bat cw   -   windows 這一端的 camera_working 同步
rem
rem  方向: 本機 windows camera_working  ==>  nas camera_working   (單向)
rem
rem  這是整條鏈的起點。camera_working/ 的正本在 windows (photoshop 的重活在這裡
rem  做)，跑完之後 nas 會變成和本機一模一樣，mac 那邊再用 '. go.sh cw' 從 nas
rem  抓回去:
rem
rem      windows (正本) --go.bat cw--> nas --. go.sh cw--> mac
rem
rem  用 /MIR，所以本機沒有的檔案在 nas 上會被刪掉。這是刻意的 (要求「一模一樣」)。
rem  但也就是說: 本機資料夾如果是空的或是路徑打錯，nas 會被清空，而且下一次 mac
rem  跑 '. go.sh cw' 的時候，mac 那一份也會跟著被清空。一路砍到底。
rem  所以下面兩個 it_exists.txt 的檢查不是方便性質的，是防護。
rem
rem  這支 script 不碰任何 nas 連線/掛載/帳號密碼的事。T: 由外面掛好，
rem  掛不上 (mapping 還在但連不上時 T:\camera_working 是不存在的) 就直接離開。
rem
rem  用法:
rem      go.bat cw                     實際執行
rem      set GO_DRY=1 ^& go.bat cw      只列出會做什麼，不真的動 (robocopy /L)
rem
rem  注意: 這支是「執行」的，和 go.sh 必須 source 剛好相反。
rem        寫 go.bat cw，不要寫 . go.bat cw
rem ============================================================================

setlocal EnableExtensions

echo %DATE% %TIME% start_go.bat

rem ---- ARG -------------------------------------------------------------------
rem  只吃 'cw' 一個參數，其他一律不做事。
if "%~1"==""        goto :usage
if not "%~2"==""    goto :usage
if /i not "%~1"=="cw" goto :usage

rem ---- config ----------------------------------------------------------------
rem  config\config_win.txt 被 .gitignore 忽略，每一台 windows 自己設定。
rem  格式和 mac 的 config_vars.txt 一樣: KEY=VALUE，# 開頭是註解。
rem  行首不要有空白，= 兩邊也不要有空白，否則會變成變數名稱的一部分。
set "CONF=%~dp0config\config_win.txt"
if not exist "%CONF%" goto :noconf

for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%CONF%") do set "%%A=%%B"

set "SRC=%local_camera_working_dir_base%"
set "DST=%remote_camera_working_dir_base%"
if not defined SRC goto :badconf
if not defined DST goto :badconf

rem  robocopy 的路徑結尾不能有反斜線。"C:\foo\" 裡面的 \" 會被當成跳脫字元，
rem  整個參數就爛掉了。這裡先砍掉結尾的反斜線。
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
if "%DST:~-1%"=="\" set "DST=%DST:~0,-1%"

rem ---- 防護 ------------------------------------------------------------------
rem  來源端 it_exists.txt: 確認本機那個資料夾是真的那一個，不是空殼、不是路徑
rem  打錯。這關沒過就 /MIR 上去的話，nas 會被清空。
if not exist "%SRC%\it_exists.txt" goto :nosrc

rem  目的端 it_exists.txt: 確認 T: 真的掛上了。mapping 還在但是連不上的時候，
rem  T:\camera_working 根本不存在，這裡就會擋下來。
if not exist "%DST%\it_exists.txt" goto :nodst

rem ---- rsync -a --delete 的 robocopy 版本 -------------------------------------
rem  /MIR        = /E + /PURGE，完全鏡像，含刪除。等於 rsync -a --delete
rem  /FFT        = 時間戳用 2 秒的容差。NTFS 是 100ns，nas 那邊透過 SMB 只有秒級，
rem                不加這個的話檔案會每次都看起來「比較新」，每跑一次就重傳一次。
rem                等於 rsync 的 --modify-window
rem  /COPY:DAT   = 只複製 資料/屬性/時間戳。不要碰 ACL (/SEC)，SMB 對 nas 會噴錯
rem  /R:2 /W:5   = 重試 2 次、間隔 5 秒。robocopy 預設是重試一百萬次 x 30 秒，
rem                有一個檔案被鎖住就等到天荒地老
rem  /NP         = 不要印每個檔案的百分比進度
rem  不列 /NFL /NDL: /MIR 會刪東西，刪掉什麼要看得到
set "DRY="
if defined GO_DRY set "DRY=/L"

set "RC_OPTS=/MIR /FFT /COPY:DAT /DCOPY:DAT /R:2 /W:5 /NP"
rem  @eaDir 是 Synology 自己產生的縮圖目錄，不要刪它也不要抓它。
rem  Thumbs.db / desktop.ini 是 windows 自己產生的，不要送上去。
rem  .DS_Store / .Trashes 是 mac 的。
rem  注意 robocopy 和 rsync 一樣，被排除的東西在目的端不會被 /MIR 刪掉。
set "RC_XD=/XD @eaDir .Trashes"
set "RC_XF=/XF .DS_Store Thumbs.db desktop.ini"

echo.
echo [go.bat] from : %SRC%
echo [go.bat] to   : %DST%
echo [go.bat]        (/MIR deletes on this side)
if defined DRY echo [go.bat] GO_DRY is set - listing only, nothing will be changed
echo.

robocopy "%SRC%" "%DST%" %RC_OPTS% %RC_XD% %RC_XF% %DRY%
set "RC=%ERRORLEVEL%"

rem  robocopy 的 exit code 不是 unix 那一套:
rem    0 = 沒事可做   1 = 有複製   2 = 目的端有多的(已刪)   4 = 有 mismatch
rem    8 以上 = 真的失敗
rem  所以 0-7 都算成功。這裡用 GEQ 8，不要寫成 'if errorlevel 1'。
if %RC% GEQ 8 goto :rcfail

echo.
echo [go.bat] robocopy rc=%RC% (0-7 = ok)
echo [go.bat] cw done
echo %DATE% %TIME% end_go.bat
exit /b 0


rem ---- 錯誤出口 --------------------------------------------------------------

:usage
echo.
echo usage: go.bat cw
echo.
echo   cw    mirror local camera_working  --^>  nas camera_working  (one way)
echo.
echo   modes 0 / 1 / 2 / 3 are mac-only, see go.sh
echo   set GO_DRY=1 to list only ^(robocopy /L^)
echo.
exit /b 1

:noconf
echo.
echo [go.bat] STOP: no config file
echo [go.bat]   %CONF%
echo [go.bat] copy config\config_win_example.txt to config\config_win.txt and edit it
echo.
exit /b 1

:badconf
echo.
echo [go.bat] STOP: %CONF% is missing local_camera_working_dir_base or remote_camera_working_dir_base
echo.
exit /b 1

:nosrc
echo.
echo [go.bat] STOP: no "%SRC%\it_exists.txt"
echo [go.bat] the local camera_working folder is missing, empty or the path is wrong.
echo [go.bat] refusing to run - /MIR would wipe the nas copy, and the mac copy after that.
echo.
exit /b 1

:nodst
echo.
echo [go.bat] STOP: no "%DST%\it_exists.txt"
echo [go.bat] the nas folder is not mounted. check T: in explorer, then run again.
echo.
exit /b 1

:rcfail
echo.
echo [go.bat] FAILED: robocopy rc=%RC% (8 or more = error)
echo.
exit /b 1
