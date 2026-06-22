import math
import tkinter as tk
import tkinter.messagebox
from collections import deque

import Fractal_Logic as fl
import Utils as sim


# Tile size used for seed creation
TILE_SIZE = 30

# Tile size used in the result viewer
VIEW_TILE_SIZE = 64

# Max number of tiles allowed for simulation
MAX_SIM_SIZE = 30000


# ----------------------------
# Seed helpers
# ----------------------------
def check_valid_seed(tile_positions):
    valid, error = True, []

    if len(tile_positions) < 1:
        valid = False
        error = "Left click to place tiles"
    else:
        for cord in tile_positions:
            [x, y] = cord.split(',')
            x, y = int(x), int(y)

            if (
                get_tag(x, y - TILE_SIZE * 2) not in tile_positions
                and get_tag(x + TILE_SIZE * 2, y) not in tile_positions
                and get_tag(x - TILE_SIZE * 2, y) not in tile_positions
                and get_tag(x, y + TILE_SIZE * 2) not in tile_positions
            ):
                valid = False
                error = "Fractal must be connected"
                break

    if not valid:
        return [valid, error]

    min_x, max_x, min_y, max_y = math.inf, -1, math.inf, -1
    for cord in tile_positions:
        [x, y] = cord.split(',')
        x, y = int(x), int(y)

        if x < min_x:
            min_x = x
        if x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y

    n, e, w, s = False, False, False, False
    for cord in tile_positions:
        [x, y] = cord.split(',')
        x, y = int(x), int(y)

        if (x == min_x and get_tag(max_x, y) in tile_positions) or (
            x == max_x and get_tag(min_x, y) in tile_positions
        ):
            e, w = True, True
        if (y == min_y and get_tag(x, max_y) in tile_positions) or (
            y == max_y and get_tag(x, min_y) in tile_positions
        ):
            n, s = True, True

    if not (n and s):
        return [False, "Not feasible generator (north/south)"]
    if not (e and w):
        return [False, "Not feasible generator (east/west)"]

    return [True, error]



def get_tag(x, y):
    return str(x) + ',' + str(y)



def get_xy(x, y):
    step = TILE_SIZE * 2
    return [step * round(x / step), step * round(y / step)]



def create_seed(tile_positions, origin_tile_cords):
    tile_positions = dict(tile_positions)
    new_tiles = dict([])
    stack = deque()
    stack.append([origin_tile_cords[0], origin_tile_cords[1], None])
    seed_tile = None

    visited = []

    min_x, max_x, min_y, max_y = math.inf, -1, math.inf, -1
    for cord in tile_positions:
        [x, y] = cord.split(',')
        x, y = int(x), int(y)

        if x < min_x:
            min_x = x
        if x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y

    while len(stack) > 0:
        [x, y, prev] = stack.popleft()
        next_dirs = []

        if [x, y] not in visited:
            visited.append([x, y])

        if get_tag(x, y - TILE_SIZE * 2) in tile_positions and get_tag(x, y - TILE_SIZE * 2) not in visited:
            stack.append([x, y - TILE_SIZE * 2, 'S'])
            visited.append(get_tag(x, y - TILE_SIZE * 2))
            next_dirs.append('N')
        if get_tag(x + TILE_SIZE * 2, y) in tile_positions and get_tag(x + TILE_SIZE * 2, y) not in visited:
            stack.append([x + TILE_SIZE * 2, y, 'W'])
            visited.append(get_tag(x + TILE_SIZE * 2, y))
            next_dirs.append('E')
        if get_tag(x - TILE_SIZE * 2, y) in tile_positions and get_tag(x - TILE_SIZE * 2, y) not in visited:
            stack.append([x - TILE_SIZE * 2, y, 'E'])
            visited.append(get_tag(x - TILE_SIZE * 2, y))
            next_dirs.append('W')
        if get_tag(x, y + TILE_SIZE * 2) in tile_positions and get_tag(x, y + TILE_SIZE * 2) not in visited:
            stack.append([x, y + TILE_SIZE * 2, 'N'])
            visited.append(get_tag(x, y + TILE_SIZE * 2))
            next_dirs.append('S')

        if get_tag(x, y) in tile_positions:
            del tile_positions[get_tag(x, y)]

        if len(next_dirs) == 0:
            next_dirs = None

        if prev is None:
            tile = fl.Tile(prev, next_dirs)
        else:
            tile = fl.Tile([prev], next_dirs)

        if prev is None or next_dirs is None:
            tile.terminal = True
        new_tiles[get_tag(x, y)] = tile

        if prev == 'N':
            tile.tile_to_N = new_tiles[get_tag(x, y - TILE_SIZE * 2)]
            new_tiles[get_tag(x, y - TILE_SIZE * 2)].tile_to_S = tile
            tile.N = 'N'
        if prev == 'E':
            tile.tile_to_E = new_tiles[get_tag(x + TILE_SIZE * 2, y)]
            new_tiles[get_tag(x + TILE_SIZE * 2, y)].tile_to_W = tile
            tile.E = 'N'
        if prev == 'W':
            tile.tile_to_W = new_tiles[get_tag(x - TILE_SIZE * 2, y)]
            new_tiles[get_tag(x - TILE_SIZE * 2, y)].tile_to_E = tile
            tile.W = 'N'
        if prev == 'S':
            tile.tile_to_S = new_tiles[get_tag(x, y + TILE_SIZE * 2)]
            new_tiles[get_tag(x, y + TILE_SIZE * 2)].tile_to_N = tile
            tile.S = 'N'

        if next_dirs is not None:
            for d in next_dirs:
                if d == 'N':
                    tile.N = 'N'
                if d == 'E':
                    tile.E = 'N'
                if d == 'W':
                    tile.W = 'N'
                if d == 'S':
                    tile.S = 'N'

        if [x, y] == origin_tile_cords:
            seed_tile = tile
            tile.original_seed = True
            if tile.next is not None and len(tile.next) > 1:
                tile.terminal = False

    ktn, kte, ktw, kts = None, None, None, None

    for cord in new_tiles:
        [x, y] = cord.split(',')
        x, y = int(x), int(y)

        if (x == min_x and get_tag(max_x, y) in new_tiles) or (x == max_x and get_tag(min_x, y) in new_tiles):
            if [x, y] == origin_tile_cords:
                ktw, kte = new_tiles[get_tag(min_x, y)], new_tiles[get_tag(max_x, y)]
            elif ktw is None and kte is None:
                ktw, kte = new_tiles[get_tag(min_x, y)], new_tiles[get_tag(max_x, y)]
        if (y == min_y and get_tag(x, max_y) in new_tiles) or (y == max_y and get_tag(x, min_y) in new_tiles):
            if [x, y] == origin_tile_cords:
                ktn, kts = new_tiles[get_tag(x, min_y)], new_tiles[get_tag(x, max_y)]
            elif ktn is None and kts is None:
                ktn, kts = new_tiles[get_tag(x, min_y)], new_tiles[get_tag(x, max_y)]

    ktn.key_tile_N = None
    kte.key_tile_E = None
    ktw.key_tile_W = None
    kts.key_tile_S = None

    visited_tiles = []
    stack = deque([ktn])
    while stack:
        cur_tile = stack.pop()
        visited_tiles.append(cur_tile)
        if cur_tile.next is not None:
            for n in cur_tile.next:
                adj_tile = fl.retrieve_tile(cur_tile, n)
                if adj_tile not in visited_tiles:
                    adj_tile.key_tile_N = [fl.opp(n)]
                    stack.append(adj_tile)
        if cur_tile.previous is not None:
            for n in cur_tile.previous:
                adj_tile = fl.retrieve_tile(cur_tile, n)
                if adj_tile not in visited_tiles:
                    adj_tile.key_tile_N = [fl.opp(n)]
                    stack.append(adj_tile)

    visited_tiles = []
    stack = deque([kte])
    while stack:
        cur_tile = stack.pop()
        visited_tiles.append(cur_tile)
        if cur_tile.next is not None:
            for n in cur_tile.next:
                adj_tile = fl.retrieve_tile(cur_tile, n)
                if adj_tile not in visited_tiles:
                    adj_tile.key_tile_E = [fl.opp(n)]
                    stack.append(adj_tile)
        if cur_tile.previous is not None:
            for n in cur_tile.previous:
                adj_tile = fl.retrieve_tile(cur_tile, n)
                if adj_tile not in visited_tiles:
                    adj_tile.key_tile_E = [fl.opp(n)]
                    stack.append(adj_tile)

    visited_tiles = []
    stack = deque([ktw])
    while stack:
        cur_tile = stack.pop()
        visited_tiles.append(cur_tile)
        if cur_tile.next is not None:
            for n in cur_tile.next:
                adj_tile = fl.retrieve_tile(cur_tile, n)
                if adj_tile not in visited_tiles:
                    adj_tile.key_tile_W = [fl.opp(n)]
                    stack.append(adj_tile)
        if cur_tile.previous is not None:
            for n in cur_tile.previous:
                adj_tile = fl.retrieve_tile(cur_tile, n)
                if adj_tile not in visited_tiles:
                    adj_tile.key_tile_W = [fl.opp(n)]
                    stack.append(adj_tile)

    visited_tiles = []
    stack = deque([kts])
    while stack:
        cur_tile = stack.pop()
        visited_tiles.append(cur_tile)
        if cur_tile.next is not None:
            for n in cur_tile.next:
                adj_tile = fl.retrieve_tile(cur_tile, n)
                if adj_tile not in visited_tiles:
                    adj_tile.key_tile_S = [fl.opp(n)]
                    stack.append(adj_tile)
        if cur_tile.previous is not None:
            for n in cur_tile.previous:
                adj_tile = fl.retrieve_tile(cur_tile, n)
                if adj_tile not in visited_tiles:
                    adj_tile.key_tile_S = [fl.opp(n)]
                    stack.append(adj_tile)

    return seed_tile


# ----------------------------
# Snapshot helpers
# ----------------------------
def _layout_signature_item(item):
    return (
        item["x"],
        item["y"],
        item["status"],
        item["copy_direction"],
        tuple(item["caps"] or ()),
        tuple(item["next"] or ()),
        tuple(item["previous"] or ()),
        tuple(item["breadcrumbs"].items()) if isinstance(item.get("breadcrumbs"), dict) else item.get("breadcrumbs"),
        tuple(item["key_tiles"].items()) if isinstance(item.get("key_tiles"), dict) else item.get("key_tiles"),
        item["original_seed"],
        item["pseudo_seed"],
        item["wall"],
        item["terminal"],
    )


def _annotate_layout_diff(prev_layout, curr_layout):
    prev_map = {(item["x"], item["y"]): item for item in (prev_layout or [])}
    curr_map = {(item["x"], item["y"]): item for item in (curr_layout or [])}

    annotated = []
    added = 0
    changed = 0
    unchanged = 0

    for pos, item in curr_map.items():
        prev_item = prev_map.get(pos)
        item = dict(item)

        if prev_item is None:
            item["change_type"] = "added"
            added += 1
        elif _layout_signature_item(prev_item) != _layout_signature_item(item):
            item["change_type"] = "changed"
            changed += 1
        else:
            item["change_type"] = "unchanged"
            unchanged += 1

        annotated.append(item)

    diff = {
        "added": added,
        "changed": changed,
        "removed": len(set(prev_map) - set(curr_map)),
        "unchanged": unchanged,
    }
    return annotated, diff


# ----------------------------
# Result viewer
# ----------------------------

class TileViewer(tk.Toplevel):
    def __init__(self, master, title, snapshots, mode_name, step_session=None):
        super().__init__(master)
        self.title(title)
        self.geometry("1600x950")
        self.minsize(1250, 760)
        self.configure(bg="#f4f6fb")

        self.snapshots = snapshots
        self.snapshot_index = 0
        self.mode_name = mode_name
        self.step_session = step_session
        self.stream_done = step_session is None
        self._stream_poll_job = None
        self.canvas_items = {}
        self.item_to_rect = {}
        self.label_items = []
        self.selected_rect = None

        self.base_tile_size = VIEW_TILE_SIZE
        self.min_zoom = 0.08
        self.max_zoom = 4.0
        self.zoom = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.view_padding = 48
        self.current_layout_bounds = None
        self.last_fit_size = None
        self._suspend_fit_on_resize = False
        self.dragging = False
        self.drag_start = None
        self.drag_origin = None

        self.world_origin_x = 0.0
        self.world_origin_y = 0.0
        self.current_tile_px = self.base_tile_size
        self.label_visibility_threshold = 18
        self._labels_visible = True
        self._current_snapshot_id = None

        self.is_playing = False
        self._play_job = None
        self.play_speed_var = tk.DoubleVar(value=2.0) 

        self._build_ui()
        self._render_current_snapshot(reset_view=True)
        if self.step_session is not None:
            self._stream_poll_job = self.after(40, self._poll_step_session)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#ffffff", bd=1, relief="solid")
        header.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=12, pady=(12, 8))
        header.columnconfigure(0, weight=1)

        left_info = tk.Frame(header, bg="#ffffff")
        left_info.grid(row=0, column=0, padx=14, pady=12, sticky="w")

        self.title_label = tk.Label(
            left_info,
            text="Simulation Viewer",
            font=("Segoe UI", 16, "bold"),
            bg="#ffffff",
            anchor="w",
        )
        self.title_label.pack(side="left")

        self.summary_label = tk.Label(
            left_info,
            text="",
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#334155",
            anchor="w",
            justify="left",
        )
        self.summary_label.pack(side="left", padx=(24, 0), pady=(2, 0))

        controls = tk.Frame(header, bg="#ffffff")
        controls.grid(row=0, column=2, padx=12, pady=8, sticky="e")

        self.prev_btn = tk.Button(controls, text="◀ Prev", command=self.prev_snapshot, width=10)
        self.prev_btn.grid(row=0, column=0, padx=4)

        self.next_btn = tk.Button(controls, text="Next ▶", command=self.next_snapshot, width=10)
        self.next_btn.grid(row=0, column=1, padx=4)

        fit_btn = tk.Button(controls, text="Fit View", command=self.fit_view, width=10)
        fit_btn.grid(row=0, column=2, padx=4)

        self.play_btn = tk.Button(
            controls,
            text="▶ Play",
            command=self.toggle_playback,
            width=10,
            state=("normal" if self.step_session is not None else "disabled"),
        )
        self.play_btn.grid(row=0, column=3, padx=4)

        tk.Label(
            controls,
            text="Speed",
            bg="#ffffff",
            font=("Segoe UI", 9),
        ).grid(row=0, column=4, padx=(10, 4))

        self.speed_spin = tk.Spinbox(
            controls,
            from_=0.25,
            to=25.0,
            increment=0.25,
            textvariable=self.play_speed_var,
            width=6,
            format="%.2f",
        )
        self.speed_spin.grid(row=0, column=5, padx=4)
        self.speed_spin.configure(state=("normal" if self.step_session is not None else "disabled"))

        viewport_frame = tk.Frame(self, bg="#f4f6fb")
        viewport_frame.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        viewport_frame.rowconfigure(0, weight=1)
        viewport_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            viewport_frame,
            bg="#edf2f7",
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self.canvas.bind("<Button-4>", lambda event: self._zoom_at(event.x, event.y, 1.1))
        self.canvas.bind("<Button-5>", lambda event: self._zoom_at(event.x, event.y, 1 / 1.1))
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.focus_set()

        self.bind("<KeyPress>", self._on_keypress)
        self.bind("<Left>", self._on_keypress)
        self.bind("<Right>", self._on_keypress)
        self.bind("<Up>", self._on_keypress)
        self.bind("<Down>", self._on_keypress)
        self.bind("<w>", self._on_keypress)
        self.bind("<a>", self._on_keypress)
        self.bind("<s>", self._on_keypress)
        self.bind("<d>", self._on_keypress)
        self.bind("<W>", self._on_keypress)
        self.bind("<A>", self._on_keypress)
        self.bind("<S>", self._on_keypress)
        self.bind("<D>", self._on_keypress)

        sidebar = tk.Frame(self, bg="#ffffff", bd=1, relief="solid", width=340)
        sidebar.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        sidebar.grid_propagate(False)
        sidebar.rowconfigure(1, weight=1)
        sidebar.columnconfigure(0, weight=1)

        mode_chip = tk.Label(
            sidebar,
            text=f"Mode: {self.mode_name}",
            bg="#e2e8f0",
            fg="#0f172a",
            font=("Segoe UI", 10, "bold"),
            padx=0,
            pady=0,
        )
        mode_chip.grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        detail_frame = tk.Frame(sidebar, bg="#ffffff")
        detail_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        detail_frame.rowconfigure(0, weight=1)
        detail_frame.columnconfigure(0, weight=1)

        self.detail_text = tk.Text(
            detail_frame,
            wrap="word",
            font=("Consolas", 10),
            bg="#ffffff",
            fg="#0f172a",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=8,
        )
        self.detail_text.grid(row=0, column=0, sticky="nsew")

        detail_scroll = tk.Scrollbar(detail_frame, orient="vertical", command=self.detail_text.yview)
        detail_scroll.grid(row=0, column=1, sticky="ns")
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        self.detail_text.insert(
            "1.0",
            "Click a tile to inspect it.\n\n"
            "Controls\n"
            "• Mouse wheel: zoom in/out\n"
            "• Click + drag: pan the view\n"
            "• WASD / Arrow keys: pan the view\n"
            "• Fit View button: center and resize to fit\n",
        )
        self.detail_text.config(state="disabled")

        legend = tk.Label(
            sidebar,
            justify="left",
            anchor="nw",
            bg="#ffffff",
            fg="#475569",
            font=("Segoe UI", 9),
            text=(
                "Legend\n"
                "Seeds:\n"
                "• Black = original seed\n"
                "• Dark gray = pseudo seed\n\n"
                "Tiles:\n"
                "• Dark red = terminal\n"
                "• Light gray = neutral tile\n\n"
                "Statuses:\n"
                "• Yellow = transmitting signal\n"
                "• Red = producing\n"
                "• Green = produced\n\n"
            ),
        )
        legend.grid(row=2, column=0, sticky="ew", padx=8, pady=8)

    def _yellow_check_for_tile(self, item):
        if item.get("status") in {"M", "W"}:
            return True

        breadcrumbs = item.get("breadcrumbs")

        if isinstance(breadcrumbs, dict):
            for v in breadcrumbs.values():
                if v in {"M", "W"}:
                    return True

        return False

    def _color_for_tile(self, item):
        status = item.get("status")

        if self._yellow_check_for_tile(item):
            return "#facc15"

        if item.get("original_seed"):
            return "#000000"  
        if item.get("pseudo_seed"):
            return "#374151"      
        
        if status == "P":
            return "#ef4444"  
        if status == "F":
            return "#22c55e"  

        if item.get("terminal"):
            return "#7f1d1d"  

        return "#94a3b8"

    def _layout_dimensions(self):
        if not self.current_layout_bounds:
            return (0, 0)
        min_x, max_x, min_y, max_y = self.current_layout_bounds
        width_cells = max_x - min_x + 1
        height_cells = max_y - min_y + 1
        return width_cells, height_cells

    def _set_view_from_state(self):
        if not self.current_layout_bounds:
            return
        min_x, _max_x, _min_y, max_y = self.current_layout_bounds
        tile_px = self.base_tile_size * self.zoom
        self.current_tile_px = tile_px
        self.world_origin_x = self.offset_x + self.view_padding - min_x * tile_px
        self.world_origin_y = self.offset_y + self.view_padding + max_y * tile_px

    def _world_rect_for_item(self, item):
        tile_px = self.current_tile_px
        x0 = self.world_origin_x + item["x"] * tile_px
        y0 = self.world_origin_y - item["y"] * tile_px
        inset = min(max(tile_px * 0.16, 2), 10)
        x1 = x0 + tile_px - inset
        y1 = y0 + tile_px - inset
        return x0, y0, x1, y1, tile_px

    def _refresh_header_and_details(self, snapshot):
        summary = snapshot["summary"]
        title_text = snapshot["title"]
        self.title_label.config(text=title_text)
        self.summary_label.config(
            text=(
                f"Tiles: {summary['tile_count']}"
            )
        )
        self._set_detail(snapshot["explanation"])

    def _render_current_snapshot(self, reset_view=False):
        snapshot = self.snapshots[self.snapshot_index]
        layout = snapshot["layout"]

        self.canvas.delete("all")
        self.canvas_items.clear()
        self.item_to_rect.clear()
        self.label_items.clear()
        self.selected_rect = None
        self._current_snapshot_id = id(snapshot)

        if not layout:
            self.current_layout_bounds = None
            self._refresh_header_and_details(snapshot)
            self._update_nav_state()
            return

        xs = [item["x"] for item in layout]
        ys = [item["y"] for item in layout]
        self.current_layout_bounds = (min(xs), max(xs), min(ys), max(ys))

        self._refresh_header_and_details(snapshot)

        if reset_view:
            self.fit_view(redraw=False)
        else:
            self._set_view_from_state()

        for item in layout:
            x0, y0, x1, y1, tile_px = self._world_rect_for_item(item)
            color = self._color_for_tile(item)
            outline = "#1e293b"
            width = 1
            if item.get("change_type") == "added":
                outline = "#1d4ed8"
                width = 3
            elif item.get("change_type") == "changed":
                outline = "#7e22ce"
                width = 3

            rect = self.canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=color,
                outline=outline,
                width=width,
                tags=("tile", f"tile_{id(item['tile'])}"),
            )
            self.canvas_items[rect] = item
            self.item_to_rect[id(item["tile"])] = rect

            label = item["copy_direction"] or item["status"] or ""
            text_color = "#ffffff" if color in {"#111827", "#ef4444"} else "#0f172a"
            font_size = max(8, min(16, int(tile_px * 0.22)))
            text_id = self.canvas.create_text(
                (x0 + x1) / 2,
                (y0 + y1) / 2,
                text=label,
                fill=text_color,
                font=("Segoe UI", font_size, "bold"),
                tags=("tile_label",),
            )
            self.label_items.append(text_id)

        self._update_label_visibility()
        self._update_nav_state()

    def _pretty_value(self, value, indent="  "):
        if isinstance(value, dict):
            if not value:
                return "{}"
            parts = []
            for k, v in value.items():
                parts.append(f"{indent}{k}: {self._pretty_value(v, indent + '  ')}")
            return "\n".join(parts)
        if isinstance(value, (list, tuple, set)):
            seq = list(value)
            if not seq:
                return "[]"
            return "\n".join(f"{indent}- {item}" for item in seq)
        if value is None:
            return "None"
        return str(value)

    def _set_detail(self, text):
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.config(state="disabled")

    def _tile_at_event(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        items = self.canvas.find_overlapping(x, y, x, y)
        for item_id in reversed(items):
            if item_id in self.canvas_items:
                return item_id
        return None

    def _update_label_visibility(self):
        visible = self.current_tile_px >= self.label_visibility_threshold
        if visible != self._labels_visible:
            self._labels_visible = visible
        state = "normal" if visible else "hidden"
        for label_id in self.label_items:
            self.canvas.itemconfigure(label_id, state=state)

    def _pan_canvas(self, dx, dy):
        if dx == 0 and dy == 0:
            return
        self.offset_x += dx
        self.offset_y += dy
        self.world_origin_x += dx
        self.world_origin_y += dy
        self.canvas.move("all", dx, dy)

    def _scale_canvas(self, canvas_x, canvas_y, factor):
        self.canvas.scale("all", canvas_x, canvas_y, factor, factor)
        self.zoom *= factor
        self.offset_x = canvas_x - (canvas_x - self.offset_x) * factor
        self.offset_y = canvas_y - (canvas_y - self.offset_y) * factor
        self.world_origin_x = canvas_x - (canvas_x - self.world_origin_x) * factor
        self.world_origin_y = canvas_y - (canvas_y - self.world_origin_y) * factor
        self.current_tile_px *= factor
        self._update_label_visibility()

    def _on_canvas_press(self, event):
        self.canvas.focus_set()
        self.dragging = False
        self.drag_start = (event.x, event.y)

    def _on_canvas_drag(self, event):
        if self.drag_start is None:
            return
        dx = event.x - self.drag_start[0]
        dy = event.y - self.drag_start[1]
        if abs(dx) > 2 or abs(dy) > 2:
            self.dragging = True
        self._pan_canvas(dx, dy)
        self.drag_start = (event.x, event.y)

    def _on_canvas_release(self, event):
        if self.drag_start is None:
            return
        was_dragging = self.dragging
        self.drag_start = None
        self.dragging = False
        if not was_dragging:
            self._on_canvas_click(event)

    def _on_canvas_click(self, event):
        item_id = self._tile_at_event(event)
        if item_id is None:
            return

        tile_info = self.canvas_items[item_id]
        if self.selected_rect is not None:
            self.canvas.itemconfig(self.selected_rect, width=1)
        self.selected_rect = item_id
        self.canvas.itemconfig(item_id, width=4)

        details = [
            f"Grid position: ({tile_info['x']}, {tile_info['y']})",
            f"Change type: {tile_info.get('change_type', 'n/a')}",
            f"Status: {tile_info['status']}",
            f"Copy direction: {tile_info['copy_direction']}",
            f"Original seed: {tile_info['original_seed']}",
            f"Pseudo seed: {tile_info['pseudo_seed']}",
            f"Wall: {tile_info['wall']}",
            f"Terminal: {tile_info['terminal']}",
            "",
            "Caps:",
            self._pretty_value(tile_info['caps']),
            "",
            "Next:",
            self._pretty_value(tile_info['next']),
            "",
            "Previous:",
            self._pretty_value(tile_info['previous']),
            "",
            "Breadcrumbs:",
            self._pretty_value(tile_info['breadcrumbs']),
            "",
            "Key tiles:",
            self._pretty_value(tile_info['key_tiles']),
        ]
        self._set_detail("\n".join(details))

    def _zoom_at(self, canvas_x, canvas_y, factor):
        if not self.current_layout_bounds:
            return
        new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        factor = new_zoom / self.zoom
        if abs(factor - 1.0) < 1e-9:
            return
        self._scale_canvas(canvas_x, canvas_y, factor)

    def _on_mousewheel(self, event):
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        self._zoom_at(event.x, event.y, factor)

    def _on_shift_mousewheel(self, event):
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        self._zoom_at(event.x, event.y, factor)

    def _on_keypress(self, event):
        key = event.keysym.lower()
        step = 30
        if key in {"left", "a"}:
            self._pan_canvas(step, 0)
        elif key in {"right", "d"}:
            self._pan_canvas(-step, 0)
        elif key in {"up", "w"}:
            self._pan_canvas(0, step)
        elif key in {"down", "s"}:
            self._pan_canvas(0, -step)
        else:
            return

    def _on_canvas_configure(self, event):
        size = (event.width, event.height)
        if self.last_fit_size is None or self.last_fit_size == size:
            return
        if self._suspend_fit_on_resize:
            self.last_fit_size = size
            return
        self.fit_view()

    def fit_view(self, redraw=True):
        if not self.current_layout_bounds:
            return
        self.update_idletasks()
        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())
        width_cells, height_cells = self._layout_dimensions()
        usable_w = max(1, canvas_w - self.view_padding * 2)
        usable_h = max(1, canvas_h - self.view_padding * 2)
        fit_x = usable_w / max(1, width_cells * self.base_tile_size)
        fit_y = usable_h / max(1, height_cells * self.base_tile_size)
        self.zoom = max(self.min_zoom, min(self.max_zoom, min(fit_x, fit_y)))

        content_w = width_cells * self.base_tile_size * self.zoom
        content_h = height_cells * self.base_tile_size * self.zoom
        self.offset_x = (canvas_w - content_w) / 2 - self.view_padding
        self.offset_y = (canvas_h - content_h) / 2 - self.view_padding
        self.last_fit_size = (canvas_w, canvas_h)
        self._set_view_from_state()
        if redraw:
            self._render_current_snapshot(reset_view=False)

    def _append_stream_snapshot(self, snapshot):
        prev_layout = self.snapshots[-1]["raw_layout"] if self.snapshots else None
        annotated_layout, diff = _annotate_layout_diff(prev_layout, snapshot["layout"])
        summary = snapshot["summary"]
        reason = snapshot.get("reason") or "Tile state changed"
        idx = len(self.snapshots) + 1
        self.snapshots.append(
            {
                "title": f"Step {idx}",
                "layout": annotated_layout,
                "raw_layout": snapshot["layout"],
                "summary": summary,
                "diff": diff,
                "explanation": (
                    f"{snapshot['title']}\n"
                    f"{reason}\n"
                    f"Current tiles: {summary['tile_count']}\n"
                    f"Added this step: {diff['added']}\n"
                    f"Changed this step: {diff['changed']}\n"
                    f"Removed this step: {diff['removed']}"
                ),
            }
        )

    def _poll_step_session(self):
        if self.step_session is None:
            return

        advanced = False
        for event in self.step_session.get_pending_events():
            etype = event.get("type")
            if etype == "snapshot":
                self._append_stream_snapshot(event["snapshot"])
                advanced = True
            elif etype == "done":
                self.stream_done = True
                if self.is_playing and self.snapshot_index >= len(self.snapshots) - 1:
                    self.stop_playback()
            elif etype == "error":
                self.stream_done = True
                self.stop_playback()
                tk.messagebox.showerror("Simulation error", str(event["error"]))

        if advanced and self.snapshot_index >= len(self.snapshots) - 2:
            self.snapshot_index = len(self.snapshots) - 1
            self._render_current_snapshot(reset_view=False)
        else:
            self._update_nav_buttons()

        if not self.stream_done:
            self._stream_poll_job = self.after(40, self._poll_step_session)

    def prev_snapshot(self):
        if self.is_playing:
            self.stop_playback()

        if self.snapshot_index > 0:
            self.snapshot_index -= 1
            self._render_current_snapshot(reset_view=False)

    def toggle_playback(self):
        if self.step_session is None:
            return

        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()


    def start_playback(self):
        if self.step_session is None or self.is_playing:
            return

        self.is_playing = True
        self.play_btn.config(text="⏸ Pause")
        self._schedule_next_play_step()


    def stop_playback(self):
        self.is_playing = False
        if hasattr(self, "play_btn"):
            self.play_btn.config(text="▶ Play")
        if self._play_job is not None:
            self.after_cancel(self._play_job)
            self._play_job = None


    def _schedule_next_play_step(self):
        if not self.is_playing:
            return

        try:
            speed = float(self.play_speed_var.get())
        except (tk.TclError, ValueError):
            speed = 2.0

        speed = max(0.25, min(25.0, speed))
        delay_ms = max(1, int(1000 / speed))

        self._play_job = self.after(delay_ms, self._playback_tick)


    def _playback_tick(self):
        self._play_job = None

        if not self.is_playing:
            return

        if self.snapshot_index < len(self.snapshots) - 1:
            self.snapshot_index += 1
            self._render_current_snapshot(reset_view=False)
            self._schedule_next_play_step()
            return

        if self.step_session is not None and not self.stream_done:
            self.step_session.resume_one_step()
            self._schedule_next_play_step()
            return

        self.stop_playback()

    def next_snapshot(self):
        if self.is_playing:
            self.stop_playback()

        if self.snapshot_index < len(self.snapshots) - 1:
            self.snapshot_index += 1
            self._render_current_snapshot(reset_view=False)
            return

        if self.step_session is not None and not self.stream_done:
            self.step_session.resume_one_step()
            self._update_nav_buttons()

    def _update_nav_buttons(self):
        if len(self.snapshots) <= 1:
            self.prev_btn.config(state="disabled")
            self.next_btn.config(state="disabled")
            return

        self.prev_btn.config(state=("normal" if self.snapshot_index > 0 else "disabled"))

        if self.step_session is not None and not self.stream_done:
            can_go_forward = True
        else:
            can_go_forward = self.snapshot_index < len(self.snapshots) - 1
        self.next_btn.config(state=("normal" if can_go_forward else "disabled"))

    def _update_nav_state(self):
        self._update_nav_buttons()

    def _on_close(self):
        self.stop_playback()

        if self._stream_poll_job is not None:
            try:
                self.after_cancel(self._stream_poll_job)
            except Exception:
                pass
            self._stream_poll_job = None

        self.destroy()


# ----------------------------
# App frames
# ----------------------------
class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.tile_positions = {}
        self.origin_tile = None
        self.stages = 1
        self.run_mode = tk.StringVar(value="pure")

        self.title('Fractals in Seeded TA')
        self.geometry('1100x700')
        self.configure(bg="#f4f6fb")

        container = tk.Frame(self, bg="#f4f6fb")
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for frame_cls in (DrawSeedFrame, ChooseOriginFrame, SelectStagesFrame):
            frame = frame_cls(container, self)
            self.frames[frame_cls] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(DrawSeedFrame)

    def show_frame(self, frame_cls):
        frame = self.frames[frame_cls]
        frame.tkraise()
        frame.refresh()

    def finish(self):
        if self.origin_tile is None:
            return

        base_seed = create_seed(self.tile_positions, self.origin_tile)

        try:
            if self.run_mode.get() == "pure":
                seed_for_run = sim.clone_seed(base_seed)
                result = sim.run_simulation_clean(seed_for_run, self.stages)
                seed_tile = result[0] if isinstance(result, (list, tuple)) else result
                layout = sim.extract_tile_layout(seed_tile)
                summary = sim.summarize_layout(layout)
                snapshots = [
                    {
                        "title": f"Pure simulation result (stages={self.stages})",
                        "layout": layout,
                        "summary": summary,
                        "explanation": (
                            f"Simulation completed to stage {self.stages}.\n"
                            f"This is the final assembly view."
                        ),
                    }
                ]
                TileViewer(self, "Simulation Result", snapshots, mode_name="Pure")
            else:
                seed_for_run = sim.clone_seed(base_seed)
                max_stage, actual_stage = sim.compute_auto_stage_limit(len(self.tile_positions))
                session = sim.StepSimulationSession(seed_for_run, max_stage).start()
                initial_snapshots = []
                for event in session.get_pending_events():
                    if event["type"] == "snapshot":
                        initial_snapshots.append(event["snapshot"])
                    elif event["type"] == "error":
                        raise event["error"]

                if not initial_snapshots:
                    layout = sim.extract_tile_layout(seed_for_run)
                    initial_snapshots.append(
                        {
                            "title": "Initial seed",
                            "layout": layout,
                            "summary": sim.summarize_layout(layout),
                            "reason": f"Initial state. Auto-running up to stage {max_stage} (actual stage value {actual_stage}).",
                        }
                    )

                viewer_snapshots = []
                for snap in initial_snapshots:
                    annotated_layout, diff = _annotate_layout_diff(viewer_snapshots[-1]["raw_layout"] if viewer_snapshots else None, snap["layout"])
                    viewer_snapshots.append(
                        {
                            "title": f"Step {len(viewer_snapshots) + 1}",
                            "layout": annotated_layout,
                            "raw_layout": snap["layout"],
                            "summary": snap["summary"],
                            "diff": diff,
                            "explanation": (
                                f"{snap['title']}\n"
                                f"{snap.get('reason') or 'Tile state changed'}\n"
                                f"Auto-running up to stage {max_stage} (actual stage value {actual_stage}).\n"
                                f"Current tiles: {snap['summary']['tile_count']}\n"
                                            f"Added this step: {diff['added']}\n"
                                f"Changed this step: {diff['changed']}\n"
                                f"Removed this step: {diff['removed']}"
                            ),
                        }
                    )

                TileViewer(
                    self,
                    f"Step Viewer (auto max stage {max_stage})",
                    viewer_snapshots,
                    mode_name="Step",
                    step_session=session,
                )
        except Exception as exc:
            tk.messagebox.showerror("Simulation error", str(exc))


class DrawSeedFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f4f6fb")
        self.controller = controller

        self.header = tk.Frame(self, bg="#ffffff", bd=1, relief="solid")
        self.header.pack(fill="x", padx=16, pady=(16, 10))

        tk.Label(
            self.header,
            text="Draw your seed",
            font=("Segoe UI", 18, "bold"),
            bg="#ffffff",
        ).pack(anchor="w", padx=14, pady=(12, 2))

        tk.Label(
            self.header,
            text="Left click to place tiles. Right click on a tile to remove it.",
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#475569",
        ).pack(anchor="w", padx=14, pady=(0, 12))

        body = tk.Frame(self, bg="#f4f6fb")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)
        body.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(body, bg="#e2e8f0", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self.add_tile)
        self.canvas.bind("<Button-3>", self.remove_tile)

        side = tk.Frame(body, bg="#ffffff", bd=1, relief="solid", width=260)
        side.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        side.grid_propagate(False)

        tk.Label(side, text="Seed settings", font=("Segoe UI", 13, "bold"), bg="#ffffff").pack(anchor="w", padx=14, pady=(14, 8))

        tk.Label(side, text="Run mode", font=("Segoe UI", 10, "bold"), bg="#ffffff").pack(anchor="w", padx=14, pady=(6, 4))
        tk.Radiobutton(side, text="Pure simulation", variable=self.controller.run_mode, value="pure", bg="#ffffff").pack(anchor="w", padx=18)
        tk.Radiobutton(side, text="Step mode", variable=self.controller.run_mode, value="step", bg="#ffffff").pack(anchor="w", padx=18)

        self.seed_count_label = tk.Label(side, text="Tiles: 0", font=("Segoe UI", 10), bg="#ffffff", fg="#334155")
        self.seed_count_label.pack(anchor="w", padx=14, pady=(16, 8))

        tk.Button(side, text="Done", command=self.go_to_origin, width=18).pack(anchor="w", padx=14, pady=(6, 14))

    def refresh(self):
        self.redraw_seed()

    def redraw_seed(self):
        self.canvas.delete("all")
        for cord, (_, x, y, is_origin) in self.controller.tile_positions.items():
            fill = "#111827" if is_origin else "#ffffff"
            self.canvas.create_rectangle(x - TILE_SIZE, y - TILE_SIZE, x + TILE_SIZE, y + TILE_SIZE, fill=fill, outline="#334155")
        self.seed_count_label.config(text=f"Tiles: {len(self.controller.tile_positions)}")

    def add_tile(self, event):
        x, y = get_xy(event.x, event.y)
        tag = get_tag(x, y)
        if tag not in self.controller.tile_positions:
            self.controller.tile_positions[tag] = (None, x, y, 0)
            self.redraw_seed()

    def remove_tile(self, event):
        x, y = get_xy(event.x, event.y)
        tag = get_tag(x, y)
        if tag in self.controller.tile_positions:
            if self.controller.origin_tile == [x, y]:
                self.controller.origin_tile = None
            del self.controller.tile_positions[tag]
            self.redraw_seed()

    def go_to_origin(self):
        valid, error = check_valid_seed(self.controller.tile_positions)
        if valid:
            self.controller.show_frame(ChooseOriginFrame)
        else:
            tk.messagebox.showinfo("Invalid seed", error)


class ChooseOriginFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f4f6fb")
        self.controller = controller

        header = tk.Frame(self, bg="#ffffff", bd=1, relief="solid")
        header.pack(fill="x", padx=16, pady=(16, 10))
        tk.Label(header, text="Choose the origin tile", font=("Segoe UI", 18, "bold"), bg="#ffffff").pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(header, text="Left click one tile to mark it as the origin.", font=("Segoe UI", 10), bg="#ffffff", fg="#475569").pack(anchor="w", padx=14, pady=(0, 12))

        self.canvas = tk.Canvas(self, bg="#e2e8f0", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.canvas.bind("<Button-1>", self.choose_origin)

        bottom = tk.Frame(self, bg="#f4f6fb")
        bottom.pack(fill="x", padx=16, pady=(0, 16))
        tk.Button(bottom, text="Back", command=self.go_back, width=12).pack(side="left")
        tk.Button(bottom, text="Done", command=self.go_to_stages, width=12).pack(side="right")

    def refresh(self):
        self.canvas.delete("all")
        for cord, (_, x, y, is_origin) in self.controller.tile_positions.items():
            fill = "#111827" if is_origin else "#ffffff"
            self.canvas.create_rectangle(x - TILE_SIZE, y - TILE_SIZE, x + TILE_SIZE, y + TILE_SIZE, fill=fill, outline="#334155")

    def choose_origin(self, event):
        x, y = get_xy(event.x, event.y)
        tag = get_tag(x, y)
        if tag not in self.controller.tile_positions:
            return

        updated = {}
        for cord, (_, tx, ty, _) in self.controller.tile_positions.items():
            updated[cord] = (None, tx, ty, 1 if cord == tag else 0)
        self.controller.tile_positions = updated
        self.controller.origin_tile = [x, y]
        self.refresh()

    def go_to_stages(self):
        if self.controller.origin_tile is not None:
            self.controller.show_frame(SelectStagesFrame)

    def go_back(self):
        updated = {}
        for cord, (_, x, y, _) in self.controller.tile_positions.items():
            updated[cord] = (None, x, y, 0)

        self.controller.tile_positions = updated
        self.controller.origin_tile = None
        self.controller.show_frame(DrawSeedFrame)


class SelectStagesFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f4f6fb")
        self.controller = controller
        self.stage_var = tk.StringVar(value="1")

        card = tk.Frame(self, bg="#ffffff", bd=1, relief="solid")
        card.pack(fill="both", expand=True, padx=16, pady=16)

        self.title_label = tk.Label(card, text="Choose the simulation depth", font=("Segoe UI", 18, "bold"), bg="#ffffff")
        self.title_label.pack(anchor="w", padx=18, pady=(18, 4))

        self.subtitle_label = tk.Label(
            card,
            text="Select up to what stage to grow the fractal.",
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#475569",
            justify="left",
            wraplength=760,
        )
        self.subtitle_label.pack(anchor="w", padx=18, pady=(0, 18))

        self.dropdown_holder = tk.Frame(card, bg="#ffffff")
        self.dropdown_holder.pack(anchor="w", padx=18, pady=(0, 16), fill="x")

        controls = tk.Frame(card, bg="#ffffff")
        controls.pack(fill="x", padx=18, pady=(0, 18))
        tk.Button(controls, text="Back", command=lambda: self.controller.show_frame(ChooseOriginFrame), width=12).pack(side="left")
        tk.Button(controls, text="Run", command=self.run, width=12).pack(side="right")

    def refresh(self):
        for child in self.dropdown_holder.winfo_children():
            child.destroy()

        if self.controller.run_mode.get() == "step":
            self.title_label.config(text="Step mode")
            self.subtitle_label.config(
                text=(
                    "Step mode no longer uses a user-selected stage count. "
                    "It begins from the initial seed and keeps advancing until the next tile-state change, "
                    "using an automatically computed safety limit behind the scenes."
                )
            )
            tk.Label(
                self.dropdown_holder,
                text=(
                    "No stage selection is needed here. Press Run to open the step viewer and stream snapshots on demand."
                ),
                font=("Segoe UI", 10),
                bg="#ffffff",
                fg="#334155",
                justify="left",
                wraplength=760,
            ).pack(anchor="w")
            self.stage_var.set("1")
            return

        self.title_label.config(text="Choose the simulation depth")
        self.subtitle_label.config(
            text="Higher stages can grow very quickly."
        )

        options = []
        num_tiles = max(1, len(self.controller.tile_positions))
        stage = 1
        actual_stage = 1

        while num_tiles < MAX_SIM_SIZE:
            options.append(f"{stage} - (stage: {actual_stage})")
            num_tiles *= num_tiles
            stage += 1
            actual_stage *= 2

        if not options:
            options = ["1 - (stage: 1)"]

        self.stage_var.set(options[0])
        tk.OptionMenu(self.dropdown_holder, self.stage_var, *options).pack(anchor="w")

    def run(self):
        if self.controller.run_mode.get() == "pure":
            self.controller.stages = int(self.stage_var.get().split(' ')[0])
        else:
            self.controller.stages = 1
        self.controller.finish()


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
