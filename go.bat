@echo off
rem ============================================================================
rem  go.bat cw  -  the windows end of the camera_working sync
rem
rem  Direction: local windows camera_working  ==>  nas camera_working  (one way)
rem
rem  This is the head of the chain. The master copy of camera_working lives on
rem  windows, because the heavy photoshop work happens here. After this runs the
rem  nas matches this machine exactly, and the mac then pulls it down with
rem  '. go.sh cw':
rem
rem      windows (master) --go.bat cw--> nas --. go.sh cw--> mac
rem
rem  It uses /MIR, so a file that is not here gets deleted on the nas. That is
rem  deliberate - "exactly the same" is the point. But it also means: if the
rem  local folder is empty or the path is wrong, the nas folder gets emptied,
rem  and the next '. go.sh cw' on the mac then empties the mac folder too.
rem  One bad run takes out all three copies. That is why the two it_exists.txt
rem  checks below are guards, not conveniences.
rem
rem  This script does no mounting and needs no nas credentials. T: is mounted
rem  by something else (Explorer, or mnt.bat over ssh). If it is not there -
rem  a mapping can exist but be Unavailable, in which case T:\camera_working
rem  does not exist - this script just stops.
rem
rem  Usage:
rem      go.bat cw                      run it
rem      set "GO_DRY=1" ^& go.bat cw     list only, change nothing (robocopy /L)
rem      set "GO_DRY=" ^& go.bat cw      back to normal. Keep the quotes: written
rem                                     bare, the space before the ^& becomes the
rem                                     value and you stay stuck in dry run.
rem
rem  Note this one is EXECUTED, not sourced - the opposite of go.sh.
rem  Write 'go.bat cw', never '. go.bat cw'.
rem ============================================================================

setlocal EnableExtensions

echo %DATE% %TIME% start_go.bat

rem ---- ARG -------------------------------------------------------------------
rem  Takes 'cw' and nothing else. Anything else does nothing at all.
if "%~1"==""        goto :usage
if not "%~2"==""    goto :usage
if /i not "%~1"=="cw" goto :usage

rem ---- config ----------------------------------------------------------------
rem  config\config_win.txt is gitignored - every windows box keeps its own.
rem  Same KEY=VALUE format as the mac's config_vars.txt, # starts a comment.
rem  No leading whitespace, and no spaces around the =, or they end up as part
rem  of the variable name or the value.
set "CONF=%~dp0config\config_win.txt"
if not exist "%CONF%" goto :noconf

for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%CONF%") do set "%%A=%%B"

set "SRC=%local_camera_working_dir_base%"
set "DST=%remote_camera_working_dir_base%"
if not defined SRC goto :badconf
if not defined DST goto :badconf

rem  A robocopy path must not end in a backslash. In "C:\foo\" the \" is read
rem  as an escaped quote and the whole argument falls apart. Trim it here.
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
if "%DST:~-1%"=="\" set "DST=%DST:~0,-1%"

rem ---- guards ----------------------------------------------------------------
rem  Source sentinel: proof that the local folder really is the working folder,
rem  not an empty shell and not a mistyped path. If this check does not hold and
rem  we /MIR anyway, the nas folder gets emptied.
if not exist "%SRC%\it_exists.txt" goto :nosrc

rem  Destination sentinel: proof that T: is actually mounted. When the mapping
rem  is remembered but disconnected, T:\camera_working does not exist and this
rem  is what catches it.
if not exist "%DST%\it_exists.txt" goto :nodst

rem ---- robocopy: the 'rsync -a --delete' of windows ---------------------------
rem  /MIR        = /E + /PURGE, a full mirror including deletes. No /XO: an
rem                exact copy is the point, so a nas-newer file is overwritten
rem  /FFT        = 2-second tolerance on timestamps. NTFS keeps 100ns, the nas
rem                over SMB only second-level; without this every file looks
rem                newer on every run and the whole folder re-transfers each
rem                time. This is rsync's --modify-window
rem  /COPY:DAT   = data, attributes, timestamps only. Do not add /SEC - NTFS
rem                ACLs over SMB to the nas just throw errors
rem  /R:2 /W:5   = retry twice, 5s apart. The default is one million retries
rem                30s apart, so one file locked by photoshop hangs forever
rem  /NP         = no per-file percentage
rem  No /NFL or /NDL on purpose: /MIR deletes things, and you want to see what
set "DRY="
if defined GO_DRY set "DRY=/L"

set "RC_OPTS=/MIR /FFT /COPY:DAT /DCOPY:DAT /R:2 /W:5 /NP"
rem  @eaDir is Synology's own thumbnail directory - do not copy it and do not
rem  delete it. Thumbs.db / desktop.ini are made by windows, keep them here.
rem  .DS_Store / .Trashes belong to the mac.
rem  Like rsync, robocopy will not purge an excluded item on the destination,
rem  so @eaDir survives on the nas.
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

rem  Robocopy exit codes are not the unix ones:
rem    0 = nothing to do   1 = files copied   2 = extras in dest   4 = mismatch
rem    8 and up = real failure
rem  So 0-7 all mean success. Use GEQ 8 here, never 'if errorlevel 1'.
rem  rc=2 is routine: that is @eaDir being counted as an extra.
if %RC% GEQ 8 goto :rcfail

echo.
echo [go.bat] robocopy rc=%RC% (0-7 = ok)
echo [go.bat] cw done
echo %DATE% %TIME% end_go.bat
exit /b 0


rem ---- error exits -----------------------------------------------------------

:usage
echo.
echo usage: go.bat cw
echo.
echo   cw    mirror local camera_working  --^>  nas camera_working  (one way)
echo.
echo   modes 0 / 1 / 2 / 3 are mac-only, see go.sh
echo   set "GO_DRY=1" to list only ^(robocopy /L^), set "GO_DRY=" to clear
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
echo [go.bat] the nas folder is not mounted. run mnt.bat, or check T: in explorer.
echo.
exit /b 1

:rcfail
echo.
echo [go.bat] FAILED: robocopy rc=%RC% (8 or more = error)
echo.
exit /b 1