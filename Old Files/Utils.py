import copy as _copy
import queue as _queue
import threading as _threading
from collections import deque as _deque

import Fractal_Logic as fl


def reset_simulation_globals():
    """Clear module-level rule/state accumulators before a fresh run."""
    fl.hard_reset_tiles.clear()
    fl.set_tile_change_hook(None)



def run_simulation_clean(seed_tile, stage, snapshot_cb=None):
    """Run a clean simulation without leaking previous global state."""
    reset_simulation_globals()
    return fl.run_simulation(seed_tile, stage, snapshot_cb=snapshot_cb)



def extract_tile_layout(seed_tile):
    """Traverse the assembly and return render-friendly tile metadata."""
    if seed_tile is None:
        return []

    tiles = []
    stack = _deque([(seed_tile, 0, 0)])
    visited = set()

    while stack:
        tile, x, y = stack.pop()
        if tile is None:
            continue

        ident = id(tile)
        if ident in visited:
            continue
        visited.add(ident)

        tiles.append(
            {
                "tile": tile,
                "x": x,
                "y": y,
                "status": tile.status,
                "copy_direction": tile.copy_direction,
                "pseudo_seed": bool(tile.pseudo_seed),
                "original_seed": bool(tile.original_seed),
                "wall": bool(tile.wall),
                "terminal": bool(tile.terminal),
                "caps": list(tile.caps) if tile.caps is not None else [],
                "next": list(tile.next) if tile.next is not None else [],
                "previous": list(tile.previous) if tile.previous is not None else [],
                "breadcrumbs": {"N": tile.N, "E": tile.E, "W": tile.W, "S": tile.S},
                "key_tiles": {
                    "N": tile.key_tile_N[0] if tile.key_tile_N is not None else None,
                    "E": tile.key_tile_E[0] if tile.key_tile_E is not None else None,
                    "W": tile.key_tile_W[0] if tile.key_tile_W is not None else None,
                    "S": tile.key_tile_S[0] if tile.key_tile_S is not None else None,
                },
            }
        )

        if tile.tile_to_N is not None:
            stack.append((tile.tile_to_N, x, y + 1))
        if tile.tile_to_E is not None:
            stack.append((tile.tile_to_E, x + 1, y))
        if tile.tile_to_W is not None:
            stack.append((tile.tile_to_W, x - 1, y))
        if tile.tile_to_S is not None:
            stack.append((tile.tile_to_S, x, y - 1))

    return tiles



def summarize_layout(layout):
    if not layout:
        return {"tile_count": 0, "bounds": (0, 0, 0, 0), "status_counts": {}}

    xs = [item["x"] for item in layout]
    ys = [item["y"] for item in layout]
    status_counts = {}
    for item in layout:
        key = item["status"] or "None"
        status_counts[key] = status_counts.get(key, 0) + 1

    return {
        "tile_count": len(layout),
        "bounds": (min(xs), max(xs), min(ys), max(ys)),
        "status_counts": status_counts,
    }



def clone_seed(seed_tile):
    return _copy.deepcopy(seed_tile)



def _layout_signature_item(item):
    return (
        item["x"],
        item["y"],
        item["status"],
        item["copy_direction"],
        tuple(item["caps"] or ()),
        tuple(item["next"] or ()),
        tuple(item["previous"] or ()),
        tuple(sorted((item.get("breadcrumbs") or {}).items())),
        tuple(sorted((item.get("key_tiles") or {}).items())),
        item["original_seed"],
        item["pseudo_seed"],
        item["wall"],
        item["terminal"],
    )



def _layout_signature(layout):
    return tuple(sorted(_layout_signature_item(item) for item in layout))


class LayoutSnapshotRecorder:
    def __init__(self, seed_tile):
        self.seed_tile = seed_tile
        self.snapshots = []
        self._last_signature = None
        self._change_count = 0

    def capture(self, title, reason=None):
        layout = extract_tile_layout(self.seed_tile)
        signature = _layout_signature(layout)
        if signature == self._last_signature:
            return None

        self._last_signature = signature
        summary = summarize_layout(layout)
        snapshot = {
            "title": title,
            "layout": layout,
            "summary": summary,
            "reason": reason,
        }
        self.snapshots.append(snapshot)
        return snapshot

    def note_change(self, _tile, attr_name):
        self._change_count += 1
        return self.capture(f"Tile change #{self._change_count}", reason=f"Observed tile update: {attr_name}")


class StepSimulationSession:
    def __init__(self, seed_tile, max_stage):
        self.seed_tile = seed_tile
        self.max_stage = max_stage
        self.recorder = LayoutSnapshotRecorder(seed_tile)
        self.queue = _queue.Queue()
        self._resume_event = _threading.Event()
        self._done_event = _threading.Event()
        self._lock = _threading.Lock()
        self.result = None
        self.error = None
        self._thread = None

    def start(self):
        initial = self.recorder.capture("Initial seed", reason="Initial state")
        if initial is not None:
            self.queue.put({"type": "snapshot", "snapshot": initial})

        self._thread = _threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        return self

    def _emit_snapshot(self, snapshot):
        if snapshot is not None:
            self.queue.put({"type": "snapshot", "snapshot": snapshot})

    def _on_tile_change(self, tile, attr_name):
        snapshot = self.recorder.note_change(tile, attr_name)
        if snapshot is None:
            return

        self._emit_snapshot(snapshot)
        self._resume_event.clear()
        self._resume_event.wait()

    def _worker(self):
        reset_simulation_globals()
        initial = self.recorder.capture("Initial seed", reason="Initial state")
        if initial is not None and not self.recorder.snapshots[:-1]:
            # already queued by start(); no-op guard for unusual reuse
            pass

        fl.set_tile_change_hook(self._on_tile_change)
        fl.instrument_tile_graph(self.seed_tile)
        try:
            self.result = fl.run_simulation(self.seed_tile, self.max_stage, snapshot_cb=None)
            final_snapshot = self.recorder.capture("Final assembly", reason="Simulation completed")
            if final_snapshot is not None:
                self._emit_snapshot(final_snapshot)
            self.queue.put({
                "type": "done",
                "result": self.result,
            })
        except Exception as exc:
            self.error = exc
            self.queue.put({"type": "error", "error": exc})
        finally:
            fl.set_tile_change_hook(None)
            self._done_event.set()
            self._resume_event.set()

    def resume_one_step(self):
        if not self._done_event.is_set():
            self._resume_event.set()

    def get_pending_events(self):
        events = []
        while True:
            try:
                events.append(self.queue.get_nowait())
            except _queue.Empty:
                break
        return events

    @property
    def is_done(self):
        return self._done_event.is_set()


def run_simulation_stepwise(seed_tile, stage):
    """Compatibility helper: run stepwise and collect all snapshots eagerly."""
    session = StepSimulationSession(seed_tile, stage).start()

    while not session.is_done:
        session.resume_one_step()
        session._done_event.wait(0.001)

    raw_snapshots = []
    for event in session.get_pending_events():
        if event["type"] == "snapshot":
            raw_snapshots.append(event["snapshot"])
        elif event["type"] == "error":
            raise event["error"]

    if session.error is not None:
        raise session.error

    return session.result, raw_snapshots


def compute_auto_stage_limit(seed_tile_count, tile_limit=30000):
    stage = 1
    actual_stage = 1
    num_tiles = max(1, seed_tile_count)

    while num_tiles < tile_limit:
        stage += 1
        actual_stage *= 2
        num_tiles *= num_tiles

    return max(1, stage - 1), max(1, actual_stage // 2)
