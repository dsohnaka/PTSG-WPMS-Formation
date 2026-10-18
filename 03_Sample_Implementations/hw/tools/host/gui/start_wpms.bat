@echo off
rem ===========================================================================
rem start_wpms.bat - OUTSIDE WPMS: a stand-in for the Layer 4 controller.
rem One-click start of the host control GUI on Windows: finds Python 3.8+ with
rem Tkinter and quartus_stp, starts wpms_bridge.tcl (or reuses a running one
rem after a PING), then opens wpms_gui.py --connect. Logs: wpms_logs\ beside
rem this BAT (or %LOCALAPPDATA%\WPMS\logs). The Python part follows the
rem marker line below; cmd never reaches it.
rem License: MIT (Layer 3 tooling; not part of the WPMS design).
rem ---------------------------------------------------------------------------
rem REVISION HISTORY(RH)
rem 001 2026-10-18 Tsuneo Ohnaka  Add : Launcher v2 (the architect's).
rem 002 2026-10-18 Claude Code    Fix : socket timeouts also caught as socket.timeout
rem                                     (an OSError, not TimeoutError, before Python 3.10).
rem ===========================================================================
setlocal EnableExtensions DisableDelayedExpansion
rem Save on the Desktop, beside the repository, or in its host\gui folder.
rem Optional first argument: repository root or host\gui folder.
rem Optional environment: WPMS_GUI_DIR, QUARTUS_STP (full EXE path).
set "WPMS_LAUNCHER=%~f0"
set "WPMS_LOCATION=%~1"
set "WPMS_PYTHON="

py -3 -c "import sys, tkinter; assert sys.version_info >= (3, 8)" >nul 2>&1
if not errorlevel 1 set "WPMS_PYTHON=py -3"
if defined WPMS_PYTHON goto run
python -c "import sys, tkinter; assert sys.version_info >= (3, 8)" >nul 2>&1
if not errorlevel 1 set "WPMS_PYTHON=python"
if defined WPMS_PYTHON goto run
python3 -c "import sys, tkinter; assert sys.version_info >= (3, 8)" >nul 2>&1
if not errorlevel 1 set "WPMS_PYTHON=python3"
if defined WPMS_PYTHON goto run

echo [ERROR] No working Python 3.8+ with Tkinter was found.
echo Tried: py -3, python, python3.
echo Check your Python installation and its Tcl/Tk component.
pause
endlocal & exit /b 1

:run
echo [WPMS] Python command: %WPMS_PYTHON%
%WPMS_PYTHON% -c "import os; p=os.environ['WPMS_LAUNCHER']; exec(compile(open(p, encoding='ascii').read().split('#'+'==WPMS_PYTHON==#', 1)[1], p, 'exec'))"
set "WPMS_RC=%errorlevel%"
if not "%WPMS_RC%"=="0" pause
endlocal & exit /b %WPMS_RC%

#==WPMS_PYTHON==#
import os
import errno
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

GUI_RELATIVE = Path("03_Sample_Implementations/hw/tools/host/gui")
REPOSITORY = "PTSG-WPMS-Formation"
HOST, PORT = "127.0.0.1", 50707
CONNECT_TIMEOUT = 5
START_TIMEOUT = 60
LOG_DIR = None


class LaunchError(Exception):
    pass


class Tee:
    def __init__(self, console, log):
        self.console, self.log = console, log

    def write(self, text):
        self.console.write(text)
        self.log.write(text)
        self.log.flush()
        return len(text)

    def flush(self):
        self.console.flush()
        self.log.flush()


def configure_logs():
    global LOG_DIR
    primary = Path(os.environ["WPMS_LAUNCHER"]).resolve().parent / "wpms_logs"
    fallback = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "WPMS" / "logs"
    for folder in (primary, fallback):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            log = (folder / "launcher.log").open("w", encoding="utf-8")
        except OSError:
            continue
        LOG_DIR = folder
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(errors="backslashreplace")
        sys.stdout, sys.stderr = Tee(sys.stdout, log), Tee(sys.stderr, log)
        print("[WPMS] Launcher v2 - " + time.strftime("%Y-%m-%d %H:%M:%S"), flush=True)
        print("[WPMS] Logs: " + str(LOG_DIR), flush=True)
        return
    raise LaunchError("Could not create a log folder beside this BAT or in Local AppData.")


def show_log(path):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    print("[WPMS] Last log lines from: " + str(path), flush=True)
    for line in lines[-20:]:
        print("  " + line, flush=True)


def gui_under(folder):
    folder = Path(folder).expanduser().resolve()
    for candidate in (folder, folder / GUI_RELATIVE):
        if (candidate / "wpms_gui.py").is_file():
            return candidate
    return None


def find_gui():
    explicit = os.environ.get("WPMS_LOCATION") or os.environ.get("WPMS_GUI_DIR")
    if explicit:
        result = gui_under(explicit)
        if result:
            return result
        raise LaunchError("No wpms_gui.py under the specified folder: " + explicit)

    launcher_folder = Path(os.environ["WPMS_LAUNCHER"]).resolve().parent
    folders = [launcher_folder, launcher_folder / REPOSITORY]
    desktops = [Path.home() / "Desktop"]
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                desktop, _ = winreg.QueryValueEx(key, "Desktop")
                desktops.insert(0, Path(os.path.expandvars(desktop)))
        except OSError:
            pass
    for name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.environ.get(name):
            desktops.append(Path(os.environ[name]) / "Desktop")
    folders.extend(desktop / REPOSITORY for desktop in desktops)
    for folder in folders:
        result = gui_under(folder)
        if result:
            return result
    raise LaunchError(
        "Repository not found. Put this BAT in the repository's host\\gui folder, "
        "or pass the repository folder as its first argument."
    )


def validate_files(gui):
    required = [gui / "wpms_bridge.tcl", gui / "wpms_ctl.py",
                gui.parent / "wpms_issp_host.tcl", gui.parent / "wpms_music.py"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise LaunchError("Repository files are missing: " + "; ".join(missing))


def local_port_available():
    # A connect timeout does not tell us whether a bridge is listening.
    # Only start another bridge if the local address is actually available.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            test.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            test.bind((HOST, PORT))
        except OSError as exc:
            if exc.errno in (errno.EADDRINUSE, errno.EACCES) or getattr(exc, "winerror", None) in (10013, 10048):
                return False
            raise LaunchError("Cannot check the local bridge port: " + str(exc)) from exc
        return True


def probe_bridge():
    try:
        connection = socket.create_connection((HOST, PORT), timeout=CONNECT_TIMEOUT)
    except ConnectionRefusedError:
        return "absent", ""
    except (TimeoutError, socket.timeout):
        if local_port_available():
            return "absent", "Connection timed out, but the local port is available."
        return "waiting", "The local port is in use, but the connection timed out."
    except OSError as exc:
        raise LaunchError("Cannot reach the local bridge: " + str(exc)) from exc
    with connection:
        connection.settimeout(10)
        try:
            connection.sendall(b"PING\n")
            with connection.makefile("r", encoding="ascii", errors="replace") as reply:
                line = reply.readline(512).strip()
                if line.startswith("ERR busy"):
                    raise LaunchError(
                        "The bridge is busy. Disconnect or close the existing GUI, "
                        "then run this launcher again."
                    )
                if not re.fullmatch(r"OK WPMS 57504D53 [0-9A-Fa-f]{8}", line):
                    raise LaunchError("Bridge PING failed: " + (line or "empty reply"))
                connection.sendall(b"QUIT\n")
                if reply.readline(512).strip() != "BYE":
                    raise LaunchError("The bridge did not finish the connection check.")
                return "ready", line
        except (TimeoutError, socket.timeout):
            return "waiting", "Connected to the local port, but the bridge reply timed out."
        except OSError as exc:
            raise LaunchError("Bridge communication failed: " + str(exc)) from exc


def find_quartus():
    override = os.environ.get("QUARTUS_STP")
    if override:
        path = Path(override.strip('"')).expanduser()
        if path.is_file():
            return path
        raise LaunchError("QUARTUS_STP does not point to an existing EXE: " + str(path))
    for name in ("quartus_stp.exe", "quartus_stp"):
        found = shutil.which(name)
        if found:
            return Path(found)
    candidates = []
    for name in ("QUARTUS_ROOTDIR", "QUARTUS_ROOTDIR_OVERRIDE"):
        if os.environ.get(name):
            root = Path(os.environ[name].strip('"'))
            candidates.extend(root / sub / "quartus_stp.exe" for sub in ("bin64", "bin"))
    drive = os.environ.get("SystemDrive", "C:") + "\\"
    for name in ("intelFPGA_lite", "intelFPGA", "intelFPGA_pro", "altera_lite", "altera"):
        root = Path(drive) / name
        if root.is_dir():
            versions = sorted(root.iterdir(), key=lambda path: tuple(
                int(part) for part in re.findall(r"\d+", path.name)), reverse=True)
            for version in versions:
                candidates.extend(version / "quartus" / sub / "quartus_stp.exe"
                                  for sub in ("bin64", "bin"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise LaunchError(
        'quartus_stp.exe was not found. Run in the same shell where quartus_stp worked, '
        'or set QUARTUS_STP to its full EXE path.'
    )


def ensure_bridge(gui):
    state, info = probe_bridge()
    if state == "ready":
        print("[WPMS] Reusing bridge: " + info, flush=True)
        return
    if state == "waiting":
        print("[WPMS] " + info, flush=True)
        print("[WPMS] Waiting for the existing listener; a second bridge will not be started.", flush=True)
        deadline = time.monotonic() + 20
        while state == "waiting" and time.monotonic() < deadline:
            time.sleep(0.5)
            state, info = probe_bridge()
        if state == "ready":
            print("[WPMS] Reusing bridge: " + info, flush=True)
            return
        if state == "waiting":
            raise LaunchError(
                "Port 50707 is already in use but is not answering as a WPMS bridge. "
                "Check the previous bridge window and Windows security/network settings. "
                "No second bridge was started."
            )
    if info:
        print("[WPMS] " + info, flush=True)
    quartus = find_quartus()
    print("[WPMS] Starting bridge with: " + str(quartus), flush=True)
    print("[WPMS] Close the In-System Sources and Probes Editor if it is open.", flush=True)
    bridge_log = LOG_DIR / "bridge.log"
    print("[WPMS] Bridge output: " + str(bridge_log), flush=True)
    with bridge_log.open("w", encoding="utf-8") as output:
        bridge = subprocess.Popen(
            [str(quartus), "-t", str(gui / "wpms_bridge.tcl")], cwd=str(gui),
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    deadline = time.monotonic() + START_TIMEOUT
    last_notice = time.monotonic()
    while time.monotonic() < deadline:
        state, info = probe_bridge()
        if state == "ready":
            print("[WPMS] Bridge ready: " + info, flush=True)
            return
        code = bridge.poll()
        if code is not None and code != 0:
            show_log(bridge_log)
            raise LaunchError("Quartus bridge exited with code " + str(code)
                              + ". Check the board, USB/JTAG and any other ISSP session.")
        if time.monotonic() - last_notice >= 10:
            print("[WPMS] Waiting for bridge startup... " + info, flush=True)
            last_notice = time.monotonic()
        time.sleep(0.5)
    show_log(bridge_log)
    raise LaunchError(
        "Bridge was not ready within 60 seconds. See bridge.log. "
        "If the bridge is still starting, wait and run this launcher again."
    )


def main():
    configure_logs()
    if os.name != "nt":
        raise LaunchError("This launcher is for Windows.")
    gui = find_gui()
    validate_files(gui)
    print("[WPMS] GUI folder: " + str(gui), flush=True)
    print("[WPMS] Python: " + sys.executable, flush=True)
    ensure_bridge(gui)
    print("[WPMS] Opening GUI with automatic connection...", flush=True)
    gui_log = LOG_DIR / "gui.log"
    with gui_log.open("w", encoding="utf-8") as output:
        code = subprocess.call([sys.executable, str(gui / "wpms_gui.py"), "--connect"],
                               cwd=str(gui), stdout=output, stderr=subprocess.STDOUT,
                               env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if code:
        show_log(gui_log)
        raise LaunchError("GUI exited with code " + str(code) + ". See gui.log.")
    print("[WPMS] GUI closed. The bridge stays open for the next launch.", flush=True)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (LaunchError, OSError) as exc:
        print("[ERROR] " + str(exc), flush=True)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
