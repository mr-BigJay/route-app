from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from database.db import DatabaseManager
from ui.route_service import compute_route_for_pair, compute_route_from_pair_row


class RouteComputeWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        db: DatabaseManager,
        origin_id: int,
        destination_id: int,
        *,
        force: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.origin_id = origin_id
        self.destination_id = destination_id
        self.force = force

    def run(self) -> None:
        try:
            result = compute_route_for_pair(
                self.db,
                self.origin_id,
                self.destination_id,
                force=self.force,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)


class RouteBatchWorker(QThread):
    progress = Signal(int, int, str)
    finished_ok = Signal(int, int)
    failed = Signal(str)

    def __init__(
        self,
        db: DatabaseManager,
        pairs: list[dict],
        *,
        force: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.pairs = list(pairs)
        self.force = force
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total = len(self.pairs)
        success_count = 0
        failed_count = 0
        for index, pair in enumerate(self.pairs, start=1):
            if self._cancelled:
                self.finished_ok.emit(success_count, failed_count)
                return
            label = f"{pair.get('origin_title', '')} → {pair.get('destination_title', '')}"
            self.progress.emit(index - 1, total, label)
            try:
                compute_route_from_pair_row(self.db, pair, force=self.force)
                success_count += 1
            except Exception:
                failed_count += 1
            self.progress.emit(index, total, label)
        self.finished_ok.emit(success_count, failed_count)
