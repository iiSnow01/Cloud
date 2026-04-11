import sys
import os
import contextlib
import subprocess
import logging
import traceback
import faulthandler

# Ensure the project root is in sys.path so our local packages take priority
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from runtime_paths import runtime_path

# On Windows, set selector policy BEFORE any asyncio/Qt imports
if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

GUI_BOOTSTRAP_ENV = "CLOUDGRAM_GUI_BOOTSTRAP"
DEBUG_CONSOLE_ENV = "CLOUDGRAM_DEBUG_CONSOLE"
AUTOSYNC_ENV = "CLOUDGRAM_AUTOSYNC"
_LOG_STREAM = None


def project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


LOG_PATH = runtime_path("cloudgram_launch.log")


def preferred_gui_python() -> str | None:
    venv_python = os.path.join(project_root(), ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python

    current_name = os.path.basename(sys.executable).lower()
    current_dir = os.path.dirname(sys.executable)
    if current_name in {"python.exe", "pythonw.exe"}:
        sibling = os.path.join(current_dir, "python.exe")
        if os.path.exists(sibling):
            return sibling

    return None


def should_bootstrap_gui() -> bool:
    if sys.platform != "win32" or getattr(sys, "frozen", False):
        return False
    if os.environ.get(GUI_BOOTSTRAP_ENV) == "1":
        return False
    if os.environ.get(DEBUG_CONSOLE_ENV) == "1":
        return False

    gui_python = preferred_gui_python()
    if not gui_python:
        return False

    return os.path.abspath(gui_python).lower() != os.path.abspath(sys.executable).lower()


def should_autosync_on_startup() -> bool:
    return os.environ.get(AUTOSYNC_ENV, "1").strip().lower() not in {"0", "false", "no", "off"}


def bootstrap_gui_process() -> bool:
    gui_python = preferred_gui_python()
    if not gui_python:
        return False

    env = os.environ.copy()
    env[GUI_BOOTSTRAP_ENV] = "1"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [gui_python, os.path.abspath(__file__), *sys.argv[1:]],
        cwd=project_root(),
        env=env,
        creationflags=creationflags,
    )
    return True


def setup_runtime_logging():
    global _LOG_STREAM
    if _LOG_STREAM is not None:
        return

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    _LOG_STREAM = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
    _LOG_STREAM.write("\n=== Cloudgram launch ===\n")

    if sys.stdout is None or os.environ.get(GUI_BOOTSTRAP_ENV) == "1":
        sys.stdout = _LOG_STREAM
    if sys.stderr is None or os.environ.get(GUI_BOOTSTRAP_ENV) == "1":
        sys.stderr = _LOG_STREAM

    try:
        faulthandler.enable(_LOG_STREAM, all_threads=True)
    except Exception:
        pass

    def _log_uncaught(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb, file=_LOG_STREAM)
        _LOG_STREAM.flush()

    sys.excepthook = _log_uncaught


if __name__ == "__main__":
    if should_bootstrap_gui() and bootstrap_gui_process():
        raise SystemExit(0)
    setup_runtime_logging()


import asyncio
import qasync
from PyQt6.QtWidgets import QApplication

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def show_window_notice(window, title: str, message: str, *, auto_hide_ms: int = 5000):
    print(f">>> {title}: {message}", flush=True)
    toast = getattr(window, "toast", None)
    if toast is not None:
        toast.show_alert(title, message, False, auto_hide_ms)


async def main():
    # Lazy imports inside the coroutine so any ImportError is caught cleanly.
    print(">>> Stage 1: Initializing DB...", flush=True)
    try:
        from db.local_db import init_db
        init_db()
    except Exception as e:
        print(f"!!! DB Error: {e}", flush=True)

    app = QApplication.instance()
    if not app:
        print("!!! Error: QApplication was not initialized.", flush=True)
        return

    print(">>> Stage 2: Connecting to Telegram...", flush=True)
    from cloud_auth.login import get_client
    
    client = get_client()
    try:
        await asyncio.wait_for(client.connect(), timeout=30)
    except asyncio.TimeoutError:
        print("!!! Telegram connection timed out.", flush=True)
    except Exception as e:
        print(f"!!! Telegram is unavailable: {e}", flush=True)

    if not await client.is_user_authorized():
        print(">>> Stage 3: Login required. Showing screen...", flush=True)
        from ui.login_screen import LoginScreen

        login_screen = LoginScreen(client)
        login_screen.show()
        await login_screen.wait_for_login()

        if not await client.is_user_authorized():
            print("!!! Login cancelled or failed.", flush=True)
            return

    try:
        me = await client.get_me()
        if me:
            import os
            os.environ["CLOUDGRAM_OWNER_ID"] = str(me.id)
            os.environ["CLOUDGRAM_OWNER_PHONE"] = str(getattr(me, 'phone', 'Unknown'))
    except Exception as e:
        print(f"!!! Error getting user profile: {e}", flush=True)

    print(">>> Stage 4: Launching Main Interface...", flush=True)
    from ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    window.load_files()

    if should_autosync_on_startup():
        print(">>> Stage 5: Syncing latest history in background...", flush=True)
        async def do_sync():
            try:
                from core.syncer import sync_from_telegram
                synced = await sync_from_telegram(
                    status_callback=lambda msg: print(f"Sync-Log: {msg}", flush=True)
                )
                print(f">>> Sync finished - {synced} files updated.", flush=True)
                window.load_files()
                show_window_notice(
                    window,
                    "Sync complete",
                    f"Telegram sync refreshed {synced} file(s).",
                    auto_hide_ms=3000,
                )
            except Exception as e:
                print(f"!!! Sync error: {e}", flush=True)
                show_window_notice(
                    window,
                    "Sync error",
                    f"Telegram sync failed: {e}",
                    auto_hide_ms=7000,
                )
        asyncio.create_task(do_sync())
    else:
        print(">>> Startup Telegram sync is disabled. Opening local library only.", flush=True)

    print(">>> Application is fully running.", flush=True)
    try:
        while window.isVisible():
            await asyncio.sleep(0.5)
    finally:
        pass
if __name__ == "__main__":
    print("=== Starting Cloudgram ===", flush=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    print("--- Event Loop Setup ---", flush=True)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    print("--- Starting Application ---", flush=True)
    try:
        with loop:
            loop.run_until_complete(main())
    except Exception as e:
        import traceback

        print(f"!!! Fatal Launch Error: {e}", flush=True)
        traceback.print_exc()
