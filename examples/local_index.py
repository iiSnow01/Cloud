"""Capture Cloudgram's real search UI with an isolated, synthetic file index."""

import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from db import local_db
from ui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="PNG file to save")
    args = parser.parse_args()

    app = QApplication([])
    app.setStyle("Fusion")
    with TemporaryDirectory() as directory, patch.object(
        local_db, "DB_PATH", str(Path(directory) / "cloudgram-demo.db")
    ), patch.dict(os.environ, {"CLOUDGRAM_OWNER_ID": "0", "CLOUDGRAM_OWNER_PHONE": "Offline demo"}):
        local_db.init_db()
        local_db.upsert_file(1, "report-q1.pdf", 1_800_000, "document", "2026-04-03 14:00:00")
        local_db.upsert_file(2, "report-q2.pdf", 2_400_000, "document", "2026-04-04 09:00:00")
        local_db.upsert_file(3, "meeting-notes.txt", 3_000, "document", "2026-04-05 15:00:00")

        window = MainWindow()
        window.hero_subtitle.setText("Temporary SQLite index with sample documents.")
        window.sync_btn.setEnabled(False)
        window.upload_btn.setEnabled(False)
        window.show()
        window.search_box.setText("report")
        app.processEvents()
        if window.count_label.text() != "2 items" or window.index_label.text() != "Local index: 3 files":
            raise RuntimeError("The search did not return the expected sample results.")
        if not window.grab().save(str(args.output), "PNG"):
            raise OSError(f"Could not save {args.output}")
        window.close()


if __name__ == "__main__":
    main()
