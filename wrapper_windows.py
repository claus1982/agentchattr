"""Windows agent injection — uses Win32 WriteConsoleInput to type into the agent CLI.

Called by wrapper.py on Windows. Not imported on other platforms.
"""

import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys
import time

if sys.platform != "win32":
    raise ImportError("wrapper_windows only works on Windows")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

_DEBUG_LOG = Path(__file__).with_name("windows-inject-debug.log")

STD_INPUT_HANDLE = -10
KEY_EVENT = 0x0001
VK_RETURN = 0x0D
VK_MENU = 0x12

# Window message constants used by the wm_setfocus Enter backend.
WM_SETFOCUS = 0x0007
WM_ACTIVATE = 0x0006
WA_ACTIVE = 1
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
SW_RESTORE = 9
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
PM_NOREMOVE = 0x0000


class _CHAR_UNION(ctypes.Union):
    _fields_ = [("UnicodeChar", wintypes.WCHAR), ("AsciiChar", wintypes.CHAR)]


class _KEY_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", wintypes.BOOL),
        ("wRepeatCount", wintypes.WORD),
        ("wVirtualKeyCode", wintypes.WORD),
        ("wVirtualScanCode", wintypes.WORD),
        ("uChar", _CHAR_UNION),
        ("dwControlKeyState", wintypes.DWORD),
    ]


class _EVENT_UNION(ctypes.Union):
    _fields_ = [("KeyEvent", _KEY_EVENT_RECORD)]


class _INPUT_RECORD(ctypes.Structure):
    _fields_ = [("EventType", wintypes.WORD), ("Event", _EVENT_UNION)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", _POINT),
    ]


kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.PeekMessageW.argtypes = [ctypes.POINTER(_MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.PeekMessageW.restype = wintypes.BOOL
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p]
user32.keybd_event.restype = None


def _write_key(handle, char: str, key_down: bool, vk: int = 0, scan: int = 0):
    rec = _INPUT_RECORD()
    rec.EventType = KEY_EVENT
    evt = rec.Event.KeyEvent
    evt.bKeyDown = key_down
    evt.wRepeatCount = 1
    evt.uChar.UnicodeChar = char
    evt.wVirtualKeyCode = vk
    evt.wVirtualScanCode = scan
    written = wintypes.DWORD(0)
    kernel32.WriteConsoleInputW(handle, ctypes.byref(rec), 1, ctypes.byref(written))


def _debug_log(message: str):
    try:
        _DEBUG_LOG.write_text("", encoding="utf-8") if not _DEBUG_LOG.exists() else None
        with _DEBUG_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    except Exception:
        pass


def _ensure_message_queue():
    msg = _MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_NOREMOVE)


def _unlock_foreground_window():
    # Windows foreground lock often blocks SetForegroundWindow from a background
    # helper thread. A synthetic Alt press is the standard local unlock.
    user32.keybd_event(VK_MENU, 0x38, 0, None)
    user32.keybd_event(VK_MENU, 0x38, KEYEVENTF_KEYUP, None)


def _send_wm_setfocus():
    """Tell the console window it just received focus — some Node TUIs
    (GitHub Copilot CLI) gate Enter processing on focus state, so this
    makes them accept injected Enter without an actual focus change."""
    hwnd = kernel32.GetConsoleWindow()
    if not hwnd:
        _debug_log("wm_setfocus: no console hwnd")
        return 0
    user32.SendMessageW(hwnd, WM_SETFOCUS, 0, 0)
    user32.SendMessageW(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    _debug_log(f"wm_setfocus: hwnd=0x{int(hwnd):X}")
    return hwnd


def _send_window_enter(hwnd):
    """Deliver Enter through the window message path used by real keyboard input.

    Copilot's current Windows input layer accepts the typed text injected into
    the console buffer, but can ignore VK_RETURN unless it arrives through the
    focused-window keyboard path.
    """
    if not hwnd:
        return
    scan = 0x1C
    keydown_lparam = 1 | (scan << 16)
    keyup_lparam = 1 | (scan << 16) | (1 << 30) | (1 << 31)
    user32.SendMessageW(hwnd, WM_KEYDOWN, VK_RETURN, keydown_lparam)
    user32.SendMessageW(hwnd, WM_KEYUP, VK_RETURN, keyup_lparam)


def _send_input_enter(hwnd):
    """Send a real keyboard Enter event after briefly foregrounding the console.

    Newer Copilot CLI builds can ignore both console-buffer Enter and synthetic
    window messages unless Enter comes through the regular keyboard path.
    """
    if not hwnd:
        _debug_log("send_input_enter: skipped, no hwnd")
        return

    previous_hwnd = user32.GetForegroundWindow()
    current_tid = kernel32.GetCurrentThreadId()
    _ensure_message_queue()
    target_pid = wintypes.DWORD(0)
    target_tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
    foreground_pid = wintypes.DWORD(0)
    foreground_tid = 0
    if previous_hwnd:
        foreground_tid = user32.GetWindowThreadProcessId(previous_hwnd, ctypes.byref(foreground_pid))

    attached_foreground = False
    attached_target = False
    _debug_log(
        "send_input_enter: "
        f"target=0x{int(hwnd):X} previous=0x{int(previous_hwnd) if previous_hwnd else 0:X} "
        f"current_tid={int(current_tid)} target_tid={int(target_tid)} foreground_tid={int(foreground_tid)}"
    )

    try:
        if foreground_tid and foreground_tid != current_tid:
            attached_foreground = bool(user32.AttachThreadInput(foreground_tid, current_tid, True))
        if target_tid and target_tid != current_tid and target_tid != foreground_tid:
            attached_target = bool(user32.AttachThreadInput(target_tid, current_tid, True))
        attach_error = ctypes.get_last_error()

        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        _unlock_foreground_window()
        set_fg_ok = user32.SetForegroundWindow(hwnd)
        time.sleep(0.1)

        inputs = (_INPUT * 2)()
        inputs[0].type = INPUT_KEYBOARD
        inputs[0].union.ki = _KEYBDINPUT(VK_RETURN, 0x1C, 0, 0, None)
        inputs[1].type = INPUT_KEYBOARD
        inputs[1].union.ki = _KEYBDINPUT(VK_RETURN, 0x1C, KEYEVENTF_KEYUP, 0, None)
        sent = user32.SendInput(2, inputs, ctypes.sizeof(_INPUT))
        send_error = ctypes.get_last_error()
        foreground_after = user32.GetForegroundWindow()
        _debug_log(
            "send_input_enter: "
            f"attach_fg={attached_foreground} attach_target={attached_target} "
            f"attach_error={attach_error} "
            f"set_fg_ok={set_fg_ok} sent={sent} send_error={send_error} "
            f"foreground_after=0x{int(foreground_after) if foreground_after else 0:X}"
        )

        if sent != 2:
            _debug_log("send_input_enter: falling back to WM_KEYDOWN/WM_KEYUP")
            _send_window_enter(hwnd)

        time.sleep(0.1)
        if previous_hwnd and previous_hwnd != hwnd:
            user32.SetForegroundWindow(previous_hwnd)
            _debug_log(f"send_input_enter: restored previous=0x{int(previous_hwnd):X}")
    finally:
        if attached_target:
            user32.AttachThreadInput(target_tid, current_tid, False)
        if attached_foreground:
            user32.AttachThreadInput(foreground_tid, current_tid, False)


def inject(text: str, *, delay: float = 0.3, enter_backend: str = "console_input"):
    """Inject text + Enter into the current console via WriteConsoleInput.

    Uses batch WriteConsoleInputW for the text (all records in one call)
    then a separate Enter keystroke after a scaled delay.

    `enter_backend` controls how the final Enter is delivered:
      - "console_input" (default): standard WriteConsoleInput + VK_RETURN.
        Works for Claude/Codex/Gemini/Kimi/Qwen/Kilo/etc.
      - "wm_setfocus": fake-focus message (WM_SETFOCUS + WM_ACTIVATE) to
        the console window before sending VK_RETURN. Needed for GitHub
        Copilot CLI, whose Ink-based input layer ignores Enter events
        when the console window is unfocused.
    """
    handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)

    # Build all key events at once (key down + key up per character)
    n_events = len(text) * 2
    if n_events > 0:
        records = (_INPUT_RECORD * n_events)()
        idx = 0
        for ch in text:
            for key_down in (True, False):
                rec = records[idx]
                rec.EventType = KEY_EVENT
                evt = rec.Event.KeyEvent
                evt.bKeyDown = key_down
                evt.wRepeatCount = 1
                evt.uChar.UnicodeChar = ch
                evt.wVirtualKeyCode = 0
                evt.wVirtualScanCode = 0
                idx += 1
        written = wintypes.DWORD(0)
        kernel32.WriteConsoleInputW(handle, records, n_events, ctypes.byref(written))

    # Scale delay with text length so longer prompts get more processing time
    scaled_delay = max(delay, len(text) * 0.001)
    time.sleep(scaled_delay)

    if enter_backend == "wm_setfocus":
        hwnd = _send_wm_setfocus()
        # Tiny pause for the window to process the focus message
        time.sleep(0.05)
        _debug_log(f"inject: backend=wm_setfocus len={len(text)}")
        _send_input_enter(hwnd)
        # Codex on Windows can accept the focus event yet still leave the
        # composed prompt pending. Follow up with a console Enter so the
        # already-injected line is actually submitted.
        _write_key(handle, "\r", True, vk=VK_RETURN, scan=0x1C)
        _write_key(handle, "\r", False, vk=VK_RETURN, scan=0x1C)
        return

    _write_key(handle, "\r", True, vk=VK_RETURN, scan=0x1C)
    _write_key(handle, "\r", False, vk=VK_RETURN, scan=0x1C)


# ---------------------------------------------------------------------------
# Activity detection — console screen buffer hashing
# ---------------------------------------------------------------------------

STD_OUTPUT_HANDLE = -11


class _COORD(ctypes.Structure):
    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]


class _SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", wintypes.SHORT),
        ("Top", wintypes.SHORT),
        ("Right", wintypes.SHORT),
        ("Bottom", wintypes.SHORT),
    ]


class _CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", _COORD),
        ("dwCursorPosition", _COORD),
        ("wAttributes", wintypes.WORD),
        ("srWindow", _SMALL_RECT),
        ("dwMaximumWindowSize", _COORD),
    ]


class _CHAR_INFO(ctypes.Structure):
    _fields_ = [("Char", _CHAR_UNION), ("Attributes", wintypes.WORD)]


kernel32.GetConsoleScreenBufferInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(_CONSOLE_SCREEN_BUFFER_INFO),
]
kernel32.GetConsoleScreenBufferInfo.restype = wintypes.BOOL

kernel32.ReadConsoleOutputW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(_CHAR_INFO),
    _COORD,
    _COORD,
    ctypes.POINTER(_SMALL_RECT),
]
kernel32.ReadConsoleOutputW.restype = wintypes.BOOL


def _read_visible_console_char_data(handle) -> bytes | None:
    csbi = _CONSOLE_SCREEN_BUFFER_INFO()
    if not kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(csbi)):
        return None

    rect = csbi.srWindow
    width = rect.Right - rect.Left + 1
    height = rect.Bottom - rect.Top + 1
    if width <= 0 or height <= 0:
        return None

    buffer_size = _COORD(width, height)
    buffer_coord = _COORD(0, 0)
    read_rect = _SMALL_RECT(rect.Left, rect.Top, rect.Right, rect.Bottom)
    char_info_array = (_CHAR_INFO * (width * height))()

    ok = kernel32.ReadConsoleOutputW(
        handle, char_info_array, buffer_size, buffer_coord,
        ctypes.byref(read_rect),
    )
    if not ok:
        return None

    import array as _array

    raw = bytes(char_info_array)
    shorts = _array.array("H")
    shorts.frombytes(raw)
    return shorts[::2].tobytes()


def _console_text_from_char_data(char_data: bytes | None) -> str:
    if not char_data:
        return ""
    text = char_data.decode("utf-16-le", errors="ignore").replace("\x00", " ")
    return " ".join(text.split())


def _should_auto_allow_agentchattr_mcp(console_text: str) -> bool:
    normalized = " ".join(console_text.lower().split())
    return (
        "allow the agentchattr mcp server to run tool" in normalized
        and "always allow" in normalized
        and "cancel" in normalized
    )


def get_activity_checker(pid_holder, agent_name="unknown", trigger_flag=None):
    """Return a callable that detects agent activity by diffing visible characters.

    Counts how many visible characters changed since last poll. Filters out
    invisible buffer noise (ConPTY artifacts, cursor jitter, timer ticks) by
    requiring a minimum number of changed cells. Uses hysteresis: goes active
    immediately on significant change, requires sustained quiet to go idle.

    trigger_flag: shared [bool] list — set to [True] by queue watcher when a
    message is injected. Forces active state immediately (covers thinking phase).
    pid_holder: not used for screen hashing, but kept for signature compatibility.
    """
    last_chars = [None]  # previous poll's character bytes
    handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    MIN_CHANGED_CELLS = 10  # idle noise is 2-5 cells; real work is 50+
    IDLE_COOLDOWN = 5       # need 5 consecutive idle polls (5s) before going idle
    _consecutive_idle = [0]
    _is_active = [False]

    def check():
        # External trigger: queue watcher injected a message → force active
        triggered = False
        if trigger_flag is not None and trigger_flag[0]:
            trigger_flag[0] = False
            triggered = True
            _consecutive_idle[0] = 0
            _is_active[0] = True

        char_data = _read_visible_console_char_data(handle)
        if char_data is None:
            return _is_active[0]

        # Count how many characters actually changed
        prev = last_chars[0]
        n_changed = 0
        if prev is not None and len(prev) == len(char_data):
            if prev != char_data:  # fast path: skip counting if identical
                for i in range(0, len(prev), 2):
                    if prev[i:i+2] != char_data[i:i+2]:
                        n_changed += 1
        significant = n_changed >= MIN_CHANGED_CELLS
        last_chars[0] = char_data

        # Hysteresis: active immediately on significant change or trigger,
        # idle only after IDLE_COOLDOWN consecutive quiet polls
        if significant or triggered:
            _consecutive_idle[0] = 0
            _is_active[0] = True
        else:
            _consecutive_idle[0] += 1
            if _consecutive_idle[0] >= IDLE_COOLDOWN:
                _is_active[0] = False

        return _is_active[0]

    return check


def run_agent(command, extra_args, cwd, env, queue_file, agent, no_restart, start_watcher, strip_env=None, pid_holder=None, session_name=None, inject_env=None, inject_delay: float = 0.3, enter_backend: str = "console_input", auto_allow_agentchattr_mcp: bool = False):
    """Run agent as a direct subprocess, inject via Win32 console."""
    if inject_env:
        env = {**env, **inject_env}
    start_watcher(lambda text: inject(text, delay=inject_delay, enter_backend=enter_backend))

    if auto_allow_agentchattr_mcp and agent == "codex":
        def _auto_allow_loop():
            handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            last_injected_at = 0.0
            while True:
                try:
                    console_text = _console_text_from_char_data(
                        _read_visible_console_char_data(handle)
                    )
                    if _should_auto_allow_agentchattr_mcp(console_text):
                        now = time.time()
                        if now - last_injected_at >= 2.0:
                            _debug_log("auto_allow_mcp: approving agentchattr MCP prompt")
                            inject("3", delay=0.05, enter_backend=enter_backend)
                            last_injected_at = now
                    time.sleep(0.5)
                except Exception:
                    time.sleep(1)

        threading = __import__("threading")
        threading.Thread(target=_auto_allow_loop, daemon=True).start()

    while True:
        try:
            proc = subprocess.Popen([command] + extra_args, cwd=cwd, env=env)
            if pid_holder is not None:
                pid_holder[0] = proc.pid
            proc.wait()
            if pid_holder is not None:
                pid_holder[0] = None

            if no_restart:
                break

            print(f"\n  {agent.capitalize()} exited (code {proc.returncode}).")
            print(f"  Restarting in 3s... (Ctrl+C to quit)")
            time.sleep(3)
        except KeyboardInterrupt:
            break
