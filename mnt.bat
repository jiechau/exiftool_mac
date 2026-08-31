@echo off
rem ============================================================================
rem  mnt.bat  -  mount the nas as a drive letter (T:) for a session that has
rem              none of its own
rem
rem  Drive letters are per-logon-session. An ssh login gets its own session, and
rem  the T: you see in Explorer does not exist inside it - 'dir T:\' there says
rem  "path not found". So after every ssh login, run this first, then go.bat:
rem
rem      mnt.bat
rem      go.bat cw
rem
rem  Sitting at the machine you normally do not need it; Explorer already holds
rem  T:. Running it there is harmless - it checks first and does nothing if the
rem  path is already reachable. It is also the fix when T: has gone stale on the
rem  desktop ('net use' showing Unavailable).
rem
rem  This is the only script on the windows side that touches nas credentials:
rem      user / host / drive letter  <- config\config_win.txt     (gitignored)
rem      password 'pw'               <- config\config_secrets.txt (gitignored)
rem  'pw' is the same DS918 admin password '. go.sh 2' uses on the mac. Do not
rem  make a second copy of it under a new name - two keys for one account mean
rem  two places to change and they will drift apart.
rem
rem  go.bat itself does no connecting; it only checks whether the path is there.
rem
rem  This script never calls 'net use /delete'. That would drop a remembered
rem  mapping for the whole account, not just this session, and break the
rem  desktop's T:. If the drive letter is stuck it authenticates the server
rem  first and retries, which clears a dead entry on its own.
rem ============================================================================

setlocal EnableExtensions

if not "%~1"=="" goto :usage

set "CONF=%~dp0config\config_win.txt"
set "SECR=%~dp0config\config_secrets.txt"
if not exist "%CONF%" goto :noconf
if not exist "%SECR%" goto :nosecr

for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%CONF%") do set "%%A=%%B"
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%SECR%") do set "%%A=%%B"

set "DRIVE=%nas_drive%"
set "UNC=%nas_unc%"
set "USR=%nas_user%"
set "TARGET=%remote_camera_working_dir_base%"
if not defined DRIVE  goto :badconf
if not defined UNC    goto :badconf
if not defined USR    goto :badconf
if not defined TARGET goto :badconf
if not defined pw     goto :nopw

if "%TARGET:~-1%"=="\" set "TARGET=%TARGET:~0,-1%"

rem ---- already there? then do nothing (the desktop case) ----------------------
if exist "%TARGET%\it_exists.txt" goto :already

rem ---- mount -----------------------------------------------------------------
echo [mnt] %DRIVE%  ^<--  %UNC%   (user: %USR%)
net use %DRIVE% "%UNC%" /user:%USR% "%pw%" /persistent:no
if exist "%TARGET%\it_exists.txt" goto :ok

rem  If the letter is still held by a dead mapping, authenticate the server
rem  itself first - that clears the stale entry - then map again. This is the
rem  reason there is no 'net use /delete' anywhere in here.
echo [mnt] retry: authenticate the server first
net use "%UNC%" /user:%USR% "%pw%" /persistent:no >nul 2>&1
net use %DRIVE% "%UNC%" /persistent:no >nul 2>&1
if exist "%TARGET%\it_exists.txt" goto :ok
goto :failed


:already
echo [mnt] %TARGET% is already reachable, nothing to do
exit /b 0

:ok
echo [mnt] ok: %TARGET%
echo [mnt] now run: go.bat cw
exit /b 0

:usage
echo.
echo usage: mnt.bat        (no arguments)
echo.
echo   maps the nas to a drive letter for THIS logon session, then:
echo       go.bat cw
echo.
echo   needed after every ssh login - drive letters do not cross sessions.
echo.
exit /b 1

:noconf
echo [mnt] STOP: no %CONF%
echo [mnt] copy config\config_win_example.txt to config\config_win.txt and edit it
exit /b 1

:nosecr
echo [mnt] STOP: no %SECR%
echo [mnt] copy config\config_secrets_example.txt to config\config_secrets.txt and set pw
exit /b 1

:badconf
echo [mnt] STOP: %CONF% needs nas_drive, nas_unc, nas_user and remote_camera_working_dir_base
exit /b 1

:nopw
echo [mnt] STOP: %SECR% has no pw
echo [mnt] pw is the DS918 admin password, the same one go.sh 2 uses on the mac
exit /b 1

:failed
echo.
echo [mnt] FAILED: %TARGET% is still not reachable
echo [mnt] check that the nas is up, and that pw in config\config_secrets.txt is current.
echo [mnt] if the drive letter is taken by something else, pick another one
echo [mnt] with nas_drive= in config\config_win.txt
echo.
exit /b 1