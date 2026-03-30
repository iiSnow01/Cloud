import sys
import os
# Ensure the project root is in sys.path so our local packages take priority
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
import qasync
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.login_screen import LoginScreen
from db.local_db import init_db
from cloud_auth.login import get_client
from core.syncer import sync_from_telegram

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

async def main():
    print(">>> Stage 1: Initializing App Tasks...", flush=True)
    try:
        init_db()
    except Exception as e:
        print(f"!!! DB Error: {e}", flush=True)

    # Get the existing app instance
    app = QApplication.instance()
    if not app:
         print("!!! Error: QApplication was not initialized by __main__ block.", flush=True)
         return

    print(">>> Stage 2: Connecting to Telegram (checking session)...", flush=True)
    client = get_client()
    try:
        # 30 second timeout for network issues
        await asyncio.wait_for(client.connect(), timeout=30)
    except asyncio.TimeoutError:
        print("!!! Error: Connection to Telegram timed out. Check your internet.", flush=True)
        return
    except Exception as e:
        print(f"!!! Connection failure: {e}", flush=True)
        return

    # 3. Authorization check
    if not await client.is_user_authorized():
        print(">>> Stage 3: Login required. Showing screen...", flush=True)
        login_screen = LoginScreen(client)
        login_screen.show()
        await login_screen.wait_for_login()
    
    print(">>> Stage 4: Launching Main Interface...", flush=True)
    window = MainWindow()
    window.show()
    # Immediate initial load of existing files
    window.load_files()

    # Background sync task
    print(">>> Stage 5: Syncing latest history in background...", flush=True)
    async def run_sync():
        try:
            synced = await sync_from_telegram(
                status_callback=lambda msg: print(f"Sync-Log: {msg}", flush=True)
            )
            print(f">>> Sync finished - {synced} files updated.", flush=True)
            window.load_files() # Refresh again
        except Exception as e:
            print(f"!!! Sync Error: {e}", flush=True)

    asyncio.create_task(run_sync())

    print(">>> Application is fully running.", flush=True)
    # Correct qasync pattern: wait for the window to close
    while window.isVisible():
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    print("=== Starting Cloudgram ===", flush=True)
    
    # On Windows, SelectorEventLoop is sometimes preferred by Telethon + qasync
    if sys.platform == 'win32':
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    print("--- Event Loop Setup ---", flush=True)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    print("--- Starting Application Thread ---", flush=True)
    try:
        with loop:
            loop.run_until_complete(main())
    except Exception as e:
        print(f"!!! Fatal Launch Error: {e}", flush=True)
