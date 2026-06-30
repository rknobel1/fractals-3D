import sys
import math
import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QRadioButton,
    QButtonGroup,
)
from PySide6.QtCore import Qt, QThread, QObject, Signal, QEvent
from PySide6.QtGui import QShortcut, QKeySequence
from collections import deque
from Simulation import *

MAX_SIM_SIZE = 1_000_000

class PyVistaKeyFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            blocked = {
                Qt.Key_Q,
                Qt.Key_V,
                Qt.Key_W,
                Qt.Key_S,
                Qt.Key_F,
                Qt.Key_Plus,
                Qt.Key_Equal,
                Qt.Key_Minus,
            }

            if event.key() in blocked:
                return True

            if event.key() == Qt.Key_C and event.modifiers() & Qt.ShiftModifier:
                return True

        return super().eventFilter(obj, event)

class SimulationWorker(QObject):
    finished = Signal(object)
    error = Signal(str)
    cancelled_signal = Signal()

    def __init__(self, seed_tile, stages):
        super().__init__()
        self.seed_tile = seed_tile
        self.stages = stages
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            seed_tile, _ = run_simulation(
                self.seed_tile,
                self.stages,
                cancel_callback=lambda: self.cancelled
            )

            if self.cancelled:
                self.cancelled_signal.emit()
            else:
                self.finished.emit(seed_tile)

        except SimulationCancelled:
            self.cancelled_signal.emit()

        except Exception as e:
            if self.cancelled:
                self.cancelled_signal.emit()
            else:
                self.error.emit(str(e))


class StepSimulationWorker(QObject):
    finished = Signal(object)
    error = Signal(str)
    cancelled_signal = Signal()

    def __init__(self, seed_tile, stages):
        super().__init__()
        self.seed_tile = seed_tile
        self.stages = stages
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            # For now, step mode uses the same regular simulation code.
            seed_tile, _ = run_simulation(
                self.seed_tile,
                self.stages,
                cancel_callback=lambda: self.cancelled
            )

            if self.cancelled:
                self.cancelled_signal.emit()
            else:
                self.finished.emit(seed_tile)

        except SimulationCancelled:
            self.cancelled_signal.emit()

        except Exception as e:
            if self.cancelled:
                self.cancelled_signal.emit()
            else:
                self.error.emit(str(e))


class GeneratorBuilderWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Fractals in 3D Seeded TA")
        self.resize(1400, 900)

        self.current_layer = 0
        self.generator_size = 10

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        # Tile Generation
        self.generator_tiles = set()
        self.tile_actors = {}
        self.grid_actors = []

        # 3D viewport
        self.plotter = QtInteractor(main_widget)
        main_layout.addWidget(self.plotter, stretch=4)

        # Sidebar
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)

        self.layer_label = QLabel(f"Current Layer: Z = {self.current_layer}")
        sidebar_layout.addWidget(self.layer_label)

        # Back button
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setEnabled(False)
        sidebar_layout.addWidget(self.back_btn) 

        # Previous layer button with shortcut
        self.prev_btn = QPushButton("Previous Layer")
        self.prev_btn.clicked.connect(self.previous_layer)
        sidebar_layout.addWidget(self.prev_btn)

        self.prev_shortcut = QShortcut(QKeySequence("B"), self)
        self.prev_shortcut.activated.connect(self.previous_layer)

        # Next layer button with shortcut
        self.next_btn = QPushButton("Next Layer")
        self.next_btn.clicked.connect(self.next_layer)
        sidebar_layout.addWidget(self.next_btn)

        self.next_shortcut = QShortcut(QKeySequence("N"), self)
        self.next_shortcut.activated.connect(self.next_layer)

        # Reset camera view to default
        self.reset_btn = QPushButton("Reset Camera")
        self.reset_btn.clicked.connect(self.reset_view)
        sidebar_layout.addWidget(self.reset_btn)

        # Reset all tiles to default
        self.reset_all_btn = QPushButton("Reset All")
        self.reset_all_btn.clicked.connect(self.reset_all)
        sidebar_layout.addWidget(self.reset_all_btn)

        # Done button with shortcut
        self.done_btn = QPushButton("Done")
        self.done_btn.clicked.connect(self.change_current_mode)
        sidebar_layout.addWidget(self.done_btn)

        self.done_shortcut = QShortcut(QKeySequence("Enter"), self)
        self.done_shortcut.activated.connect(self.change_current_mode)

        # Selecting simulation stage
        self.stage_label = QLabel("Simulation Stage")
        sidebar_layout.addWidget(self.stage_label)
        self.stage_label.hide()

        self.stage_combo = QComboBox()
        sidebar_layout.addWidget(self.stage_combo)
        self.stage_combo.hide()

        # Simulation mode radio buttons
        self.sim_mode_label = QLabel("Simulation Mode")
        sidebar_layout.addWidget(self.sim_mode_label)
        self.sim_mode_label.hide()

        self.sim_mode_group = QButtonGroup(self)

        self.regular_sim_radio = QRadioButton("Regular")
        self.regular_sim_radio.setChecked(True)
        self.sim_mode_group.addButton(self.regular_sim_radio)
        sidebar_layout.addWidget(self.regular_sim_radio)
        self.regular_sim_radio.hide()

        self.step_sim_radio = QRadioButton("Step Mode")
        self.sim_mode_group.addButton(self.step_sim_radio)
        sidebar_layout.addWidget(self.step_sim_radio)
        self.step_sim_radio.hide()

        # Run button
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self.run_simulation)
        sidebar_layout.addWidget(self.run_btn)
        self.run_btn.hide()

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_simulation)
        self.cancel_btn.hide()
        self.cancel_btn.setEnabled(False)
        sidebar_layout.addWidget(self.cancel_btn)

        # Warning label
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("""
        QLabel {
            color: #b35c00;
            font-size: 11px;
        }
        """)
        self.warning_label.hide()
        sidebar_layout.addWidget(self.warning_label)

        self.stages = 1

        self.done_btn.setEnabled(False)

        sidebar_layout.addStretch()

        self.shortcuts_label = QLabel("""
            <b>Shortcuts</b><br>
            N - Next Layer<br>
            B - Previous Layer<br>
            Enter - Confirm<br><br>
            LMB - Place Tile<br>
            RMB - Remove Tile<br><br>
            R - Fit Objects in View
            """)
        
        self.shortcuts_label.setStyleSheet("""
        QLabel {
            color: #666;
            font-size: 11px;
            padding: 6px;
            border-top: 1px solid #ccc;
        }
    """)

        self.shortcuts_label.setAlignment(
            Qt.AlignLeft | Qt.AlignBottom
        )

        sidebar_layout.addWidget(self.shortcuts_label)

        self.mode = "build"
        self.origin_tile = None

        main_layout.addWidget(sidebar, stretch=1)

        self.setCentralWidget(main_widget)

        self.update_layer_buttons()
        self.update_back_button()
        self.setup_scene()
        self.clear_pyvista_controls()

    def clear_pyvista_controls(self):
        self.pyvista_key_filter = PyVistaKeyFilter(self)
        self.plotter.installEventFilter(self.pyvista_key_filter)
        self.plotter.interactor.installEventFilter(self.pyvista_key_filter)

    # VISUALS
    def draw_active_layer_grid(self):
        half = self.generator_size // 2
        z = self.current_layer

        for i in range(-half, half + 1):
            horizontal_line = np.array([
                [-half, i, z],
                [half, i, z],
            ])

            vertical_line = np.array([
                [i, -half, z],
                [i, half, z],
            ])

            self.plotter.add_lines(
                horizontal_line,
                color="lightgray",
                width=1,
            )

            self.plotter.add_lines(
                vertical_line,
                color="lightgray",
                width=1,
            )

    def draw_bounding_box(self):
        bounds_cube = pv.Cube(
            center=(0, 0, self.generator_size / 2),
            x_length=self.generator_size,
            y_length=self.generator_size,
            z_length=self.generator_size,
        )

        self.plotter.add_mesh(
            bounds_cube,
            style="wireframe",
            color="black",
            line_width=2,
            pickable=False,
        )

    def draw_all_cubes(self):
        self.tile_actors.clear()

        for tile in self.generator_tiles:
            _x, _y, z = tile

            if tile == self.origin_tile:
                color = "black"
                opacity = 1.0 if z == self.current_layer else 0.25
            else:
                color = "lightblue" if z == self.current_layer else "gray"
                opacity = 1.0 if z == self.current_layer else 0.25

            actor = self.add_cube(tile, color=color, opacity=opacity)
            self.tile_actors[tile] = actor

    def get_layer_label_text(self):
        if self.mode == "select_origin":
            return f"Select origin cube — Layer Z = {self.current_layer}"

        if self.origin_tile is not None:
            return f"Origin selected: {self.origin_tile}"

        return f"Current Layer: Z = {self.current_layer}"

    def setup_scene(self):
        self.plotter.set_background("white")
        self.plotter.add_axes()

        self.draw_bounding_box()
        self.draw_active_layer_grid()

        # Camera position (south of model), focal point, up direction
        self.plotter.camera_position = [
            (0, -25, 20),  
            (0, 0, 5),     
            (0, 0, 1),     
        ]
        self.plotter.reset_camera()
        self.enable_cube_placement()

    def redraw_scene(self):
        self.plotter.clear()

        self.plotter.set_background("white")
        self.plotter.add_axes()

        self.draw_bounding_box()
        self.draw_active_layer_grid()
        self.draw_all_cubes()

        self.plotter.render()

    # UTILS
    def set_origin_tile(self, tile):
        self.origin_tile = tile

        self.redraw_scene()

        self.layer_label.setText(
            f"Selected origin: {tile} — press Done to confirm"
        )
        self.done_btn.setText("Done")
        self.done_btn.setEnabled(True)

    def set_running_state(self, running: bool):
        self.back_btn.setEnabled(not running)
        self.prev_btn.setEnabled(not running)
        self.next_btn.setEnabled(not running)
        self.done_btn.setEnabled(not running)
        self.reset_btn.setEnabled(not running)
        self.reset_all_btn.setEnabled(not running)
        self.stage_combo.setEnabled(not running)
        self.regular_sim_radio.setEnabled(not running)
        self.step_sim_radio.setEnabled(not running)
        self.run_btn.setEnabled(not running)

        self.cancel_btn.setVisible(running)
        self.cancel_btn.setEnabled(running)

        if running:
            self.run_btn.setText("Running...")
        else:
            self.run_btn.setText("Run")
            self.cancel_btn.setText("Cancel")
            self.update_back_button()
            self.update_layer_buttons()

            if self.mode == "build":
                self.update_done_button()
            elif self.mode == "select_origin":
                self.done_btn.setEnabled(self.origin_tile is not None)

    def layer_has_tiles(self, z):
        return any(tile_z == z for _x, _y, tile_z in self.generator_tiles)
    
    def has_higher_layer(self):
        return any(tile_z > self.current_layer for _x, _y, tile_z in self.generator_tiles)

    def change_current_mode(self):
        if self.mode == "build":
            valid, error = self.check_valid_seed_3d()

            if not valid:
                self.layer_label.setText(error)
                return

            self.mode = "select_origin"
            self.update_back_button()
            self.done_btn.setText("Confirm Origin")
            self.done_btn.setEnabled(False)
            self.current_layer = 0
            self.update_layer_buttons()
            self.redraw_scene()
            self.layer_label.setText(
                f"Select origin cube — Layer Z = {self.current_layer}"
            )
            return

        if self.mode == "select_origin":
            if self.origin_tile is None:
                return

            self.show_stage_selection()
            return

    # BUTTONS AND FUNCTIONALITY
    def update_layer_buttons(self):
        self.prev_btn.setEnabled(self.current_layer > 0)

        can_go_next = (
            self.current_layer < self.generator_size - 1
            and (
                self.layer_has_tiles(self.current_layer)
                or self.has_higher_layer()
            )
        )

        self.next_btn.setEnabled(can_go_next)

    def update_done_button(self):
        self.done_btn.setEnabled(len(self.generator_tiles) > 0)

    def update_back_button(self):
        self.back_btn.setEnabled(self.mode in ("select_origin", "select_stages", "display_result"))

    def enable_cube_placement(self):
        self.plotter.iren.add_observer("LeftButtonPressEvent", self.on_left_click)
        self.plotter.iren.add_observer("RightButtonPressEvent", self.on_right_click)

    def on_left_click(self, obj, event):
        click_pos = self.plotter.iren.get_event_position()

        picker = self.plotter.iren.interactor.GetPicker()
        picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)

        world_pos = picker.GetPickPosition()
        camera_pos = self.plotter.camera.position

        point = self.intersect_camera_ray_with_layer(camera_pos, world_pos)

        if point is not None:
            self.on_grid_click(point)

        return
    
    def on_right_click(self, obj, event):
        if self.mode != "build":
            return

        click_pos = self.plotter.iren.get_event_position()

        picker = self.plotter.iren.interactor.GetPicker()
        picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)

        world_pos = picker.GetPickPosition()
        camera_pos = self.plotter.camera.position

        point = self.intersect_camera_ray_with_layer(camera_pos, world_pos)

        if point is None:
            return

        half = self.generator_size / 2

        x = math.floor(point[0] + half)
        y = math.floor(point[1] + half)
        z = self.current_layer

        tile = (x, y, z)

        if tile in self.generator_tiles:
            self.generator_tiles.remove(tile)
            self.remove_cube(tile)

            if self.origin_tile == tile:
                self.origin_tile = None

            self.update_done_button()
            self.update_layer_buttons()
            self.plotter.render()

    def intersect_camera_ray_with_layer(self, camera_pos, picked_pos):
        z = self.current_layer

        cx, cy, cz = camera_pos
        px, py, pz = picked_pos

        dz = pz - cz

        if abs(dz) < 1e-8:
            return None

        t = (z - cz) / dz

        if t < 0:
            return None

        x = cx + t * (px - cx)
        y = cy + t * (py - cy)

        return (x, y, z)

    def on_grid_click(self, point):
        if point is None:
            return

        # Only allow tile placement in build mode,
        # but still allow selecting an existing origin tile in select_origin mode.
        if self.mode not in ("build", "select_origin"):
            return

        half = self.generator_size / 2

        x = math.floor(point[0] + half)
        y = math.floor(point[1] + half)
        z = self.current_layer

        if x < 0 or x >= self.generator_size:
            return
        if y < 0 or y >= self.generator_size:
            return
        if z < 0 or z >= self.generator_size:
            return

        tile = (x, y, z)

        if self.mode == "select_origin":
            if tile not in self.generator_tiles:
                return

            self.set_origin_tile(tile)
            return

        if tile not in self.generator_tiles:
            self.generator_tiles.add(tile)
            actor = self.add_cube(tile, color="lightblue", opacity=1.0)
            self.tile_actors[tile] = actor

        self.update_done_button()
        self.update_layer_buttons()
        self.plotter.render()

    def add_cube(self, tile, color="lightblue", opacity=1.0):
        x, y, z = tile
        half = self.generator_size / 2

        cube = pv.Cube(
            center=(
                x - half + 0.5,
                y - half + 0.5,
                z + 0.5,
            ),
            x_length=1,
            y_length=1,
            z_length=1,
        )

        actor = self.plotter.add_mesh(
            cube,
            color=color,
            opacity=opacity,
            show_edges=True,
            pickable=False,
        )

        return actor

    def remove_cube(self, tile):
        actor = self.tile_actors.pop(tile, None)

        if actor is not None:
            self.plotter.remove_actor(actor)

    def next_layer(self):
        if not self.next_btn.isEnabled():
            return

        self.current_layer += 1
        self.layer_label.setText(self.get_layer_label_text())

        self.update_layer_buttons()
        self.redraw_scene()


    def previous_layer(self):
        if not self.prev_btn.isEnabled():
            return

        self.current_layer -= 1
        self.layer_label.setText(self.get_layer_label_text())

        self.update_layer_buttons()
        self.redraw_scene()

    def reset_view(self):
        self.plotter.camera_position = [
            (0, -25, 20),  # camera position (south of model)
            (0, 0, 5),     # focal point
            (0, 0, 1),     # up direction
        ]
        self.plotter.reset_camera()

    def go_back(self):
        if self.mode == "select_stages":
            self.mode = "select_origin"

            self.stage_label.hide()
            self.stage_combo.hide()
            self.run_btn.hide()
            self.warning_label.hide()

            self.done_btn.show()
            self.done_btn.setText("Confirm Origin")
            self.done_btn.setEnabled(self.origin_tile is not None)

            self.layer_label.setText(
                f"Selected origin: {self.origin_tile} — press Done to confirm"
                if self.origin_tile is not None
                else f"Select origin cube — Layer Z = {self.current_layer}"
            )

            self.redraw_scene()

        elif self.mode == "select_origin":
            self.mode = "build"
            self.origin_tile = None

            self.done_btn.show()
            self.done_btn.setText("Done")
            self.update_done_button()

            self.layer_label.setText(f"Current Layer: Z = {self.current_layer}")

            self.redraw_scene()

        elif self.mode == "display_result":
            self.restore_stage_selection_after_simulation()
            self.redraw_scene()

        self.update_back_button()
        self.update_layer_buttons()

    def reset_all(self):
        self.current_layer = 0
        self.generator_tiles.clear()
        self.tile_actors.clear()
        self.grid_actors.clear()

        self.mode = "build"
        self.update_back_button()
        self.origin_tile = None

        self.stage_label.hide()
        self.stage_combo.hide()
        self.run_btn.hide()
        self.cancel_btn.hide()
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel")
        self.done_btn.show()
        self.stages = 1

        self.done_btn.setText("Done")
        self.done_btn.setEnabled(False)
        self.layer_label.setText(f"Current Layer: Z = {self.current_layer}")

        self.update_layer_buttons()
        self.warning_label.hide()
        self.redraw_scene()
        self.reset_view()

    def cancel_simulation(self):
        if hasattr(self, "sim_worker"):
            self.sim_worker.cancel()

        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")
        self.layer_label.setText("Cancelling...")

    def update_simulation_warning(self):
        if self.stage_combo.count() == 0:
            self.warning_label.hide()
            return

        _, _, tile_count = self.stage_combo.currentData()

        if tile_count > 300_000:
            self.warning_label.setText(
                f"⚠ This simulation will generate "
                f"{tile_count:,} tiles and may take a couple minutes."
            )
            self.warning_label.show()
        else:
            self.warning_label.hide()

    # LOGIC
    def check_valid_seed_3d(self):
        if len(self.generator_tiles) < 1:
            return False, "Left click to place tiles"

        # Connectivity check
        start = next(iter(self.generator_tiles))
        visited = set()
        queue = deque([start])

        directions = [
            (1, 0, 0),
            (-1, 0, 0),
            (0, 1, 0),
            (0, -1, 0),
            (0, 0, 1),
            (0, 0, -1),
        ]

        while queue:
            tile = queue.popleft()

            if tile in visited:
                continue

            visited.add(tile)

            x, y, z = tile
            for dx, dy, dz in directions:
                neighbor = (x + dx, y + dy, z + dz)

                if neighbor in self.generator_tiles and neighbor not in visited:
                    queue.append(neighbor)

        if len(visited) != len(self.generator_tiles):
            return False, "Fractal must be connected"

        xs = [x for x, _y, _z in self.generator_tiles]
        ys = [y for _x, y, _z in self.generator_tiles]
        zs = [z for _x, _y, z in self.generator_tiles]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        min_z, max_z = min(zs), max(zs)

        has_east_west = False
        has_north_south = False
        has_top_bottom = False

        for x, y, z in self.generator_tiles:
            if (
                (x == min_x and (max_x, y, z) in self.generator_tiles)
                or (x == max_x and (min_x, y, z) in self.generator_tiles)
            ):
                has_east_west = True

            if (
                (y == min_y and (x, max_y, z) in self.generator_tiles)
                or (y == max_y and (x, min_y, z) in self.generator_tiles)
            ):
                has_north_south = True

            if (
                (z == min_z and (x, y, max_z) in self.generator_tiles)
                or (z == max_z and (x, y, min_z) in self.generator_tiles)
            ):
                has_top_bottom = True

        if not has_north_south:
            return False, "Not feasible generator (north/south)"

        if not has_east_west:
            return False, "Not feasible generator (east/west)"

        if not has_top_bottom:
            return False, "Not feasible generator (top/bottom)"

        return True, ""

    @staticmethod
    def create_seed(tile_positions, origin_tile_cords):
        tile_positions = dict(tile_positions)
        new_tiles = dict([])
        stack = deque()
        stack.append([origin_tile_cords[0], origin_tile_cords[1], origin_tile_cords[2], None])
        seed_tile = None

        visited = []

        min_x, max_x, min_y, max_y, min_z, max_z = math.inf, -1, math.inf, -1, math.inf, -1
        for cord in tile_positions:
            [x, y, z] = cord.split(',')
            x, y, z = int(x), int(y), int(z)

            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
            if z < min_z:
                min_z = z
            if z > max_z:
                max_z = z

        while len(stack) > 0:
            [x, y, z, prev] = stack.popleft()
            next_dirs = []

            if [x, y, z] not in visited:
                visited.append([x, y, z])

            if get_tag(x, y + 1, z) in tile_positions and get_tag(x, y + 1, z) not in visited:
                stack.append([x, y + 1, z, 'S'])
                visited.append(get_tag(x, y + 1, z))
                next_dirs.append('N')
            if get_tag(x + 1, y, z) in tile_positions and get_tag(x + 1, y, z) not in visited:
                stack.append([x + 1, y, z, 'W'])
                visited.append(get_tag(x + 1, y, z))
                next_dirs.append('E')
            if get_tag(x - 1, y, z) in tile_positions and get_tag(x - 1, y, z) not in visited:
                stack.append([x - 1, y, z, 'E'])
                visited.append(get_tag(x - 1, y, z))
                next_dirs.append('W')
            if get_tag(x, y - 1, z) in tile_positions and get_tag(x, y - 1, z) not in visited:
                stack.append([x, y - 1, z, 'N'])
                visited.append(get_tag(x, y - 1, z))
                next_dirs.append('S')
            if get_tag(x, y, z + 1) in tile_positions and get_tag(x, y, z + 1) not in visited:
                stack.append([x, y, z + 1, 'D'])
                visited.append(get_tag(x, y, z + 1))
                next_dirs.append('U')
            if get_tag(x, y, z - 1) in tile_positions and get_tag(x, y, z - 1) not in visited:
                stack.append([x, y, z - 1, 'U'])
                visited.append(get_tag(x, y, z - 1))
                next_dirs.append('D')

            if get_tag(x, y, z) in tile_positions:
                del tile_positions[get_tag(x, y, z)]

            if len(next_dirs) == 0:
                next_dirs = None

            if prev is None:
                tile = Tile(prev, next_dirs)
            else:
                tile = Tile([prev], next_dirs)

            if prev is None or next_dirs is None:
                tile.terminal = True
            new_tiles[get_tag(x, y, z)] = tile

            if prev == 'N':
                tile.tile_to_N = new_tiles[get_tag(x, y + 1, z)]
                new_tiles[get_tag(x, y + 1, z)].tile_to_S = tile
                tile.N = 'N'
            if prev == 'E':
                tile.tile_to_E = new_tiles[get_tag(x + 1, y, z)]
                new_tiles[get_tag(x + 1, y, z)].tile_to_W = tile
                tile.E = 'N'
            if prev == 'W':
                tile.tile_to_W = new_tiles[get_tag(x - 1, y, z)]
                new_tiles[get_tag(x - 1, y, z)].tile_to_E = tile
                tile.W = 'N'
            if prev == 'S':
                tile.tile_to_S = new_tiles[get_tag(x, y - 1, z)]
                new_tiles[get_tag(x, y - 1, z)].tile_to_N = tile
                tile.S = 'N'
            if prev == 'U':
                tile.tile_to_U = new_tiles[get_tag(x, y, z + 1)]
                new_tiles[get_tag(x, y, z + 1)].tile_to_D = tile
                tile.U = 'N'
            if prev == 'D':
                tile.tile_to_D = new_tiles[get_tag(x, y, z - 1)]
                new_tiles[get_tag(x, y, z - 1)].tile_to_U = tile
                tile.D = 'N'

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
                    if d == 'U':
                        tile.U = 'N'
                    if d == 'D':
                        tile.D = 'N'

            if [x, y, z] == origin_tile_cords:
                seed_tile = tile
                tile.original_seed = True
                if tile.next is not None and len(tile.next) > 1:
                    tile.terminal = False

        ktn, kte, ktw, kts, ktu, ktd = None, None, None, None, None, None

        for cord in new_tiles:
            [x, y, z] = cord.split(',')
            x, y, z = int(x), int(y), int(z)

            if (x == min_x and get_tag(max_x, y, z) in new_tiles) or (x == max_x and get_tag(min_x, y, z) in new_tiles):
                if [x, y, z] == origin_tile_cords:
                    ktw, kte = new_tiles[get_tag(min_x, y, z)], new_tiles[get_tag(max_x, y, z)]
                elif ktw is None and kte is None:
                    ktw, kte = new_tiles[get_tag(min_x, y, z)], new_tiles[get_tag(max_x, y, z)]
            if (y == min_y and get_tag(x, max_y, z) in new_tiles) or (y == max_y and get_tag(x, min_y, z) in new_tiles):
                if [x, y, z] == origin_tile_cords:
                    ktn, kts = new_tiles[get_tag(x, max_y, z)], new_tiles[get_tag(x, min_y, z)]
                elif ktn is None and kts is None:
                    ktn, kts = new_tiles[get_tag(x, max_y, z)], new_tiles[get_tag(x, min_y, z)]
            if (z == min_z and get_tag(x, y, max_z) in new_tiles) or (z == max_z and get_tag(x, y, min_z) in new_tiles):
                if [x, y, z] == origin_tile_cords:
                    ktu, ktd = new_tiles[get_tag(x, y, max_z)], new_tiles[get_tag(x, y, min_z)]
                elif ktu is None and ktd is None:
                    ktu, ktd = new_tiles[get_tag(x, y, max_z)], new_tiles[get_tag(x, y, min_z)]

        ktn.key_tile_N = None
        kte.key_tile_E = None
        ktw.key_tile_W = None
        kts.key_tile_S = None
        ktu.key_tile_U = None
        ktd.key_tile_D = None

        visited_tiles = []
        stack = deque([ktn])
        while stack:
            cur_tile = stack.pop()
            visited_tiles.append(cur_tile)
            if cur_tile.next is not None:
                for n in cur_tile.next:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_N = [opp(n)]
                        stack.append(adj_tile)
            if cur_tile.previous is not None:
                for n in cur_tile.previous:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_N = [opp(n)]
                        stack.append(adj_tile)

        visited_tiles = []
        stack = deque([kte])
        while stack:
            cur_tile = stack.pop()
            visited_tiles.append(cur_tile)
            if cur_tile.next is not None:
                for n in cur_tile.next:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_E = [opp(n)]
                        stack.append(adj_tile)
            if cur_tile.previous is not None:
                for n in cur_tile.previous:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_E = [opp(n)]
                        stack.append(adj_tile)

        visited_tiles = []
        stack = deque([ktw])
        while stack:
            cur_tile = stack.pop()
            visited_tiles.append(cur_tile)
            if cur_tile.next is not None:
                for n in cur_tile.next:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_W = [opp(n)]
                        stack.append(adj_tile)
            if cur_tile.previous is not None:
                for n in cur_tile.previous:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_W = [opp(n)]
                        stack.append(adj_tile)

        visited_tiles = []
        stack = deque([kts])
        while stack:
            cur_tile = stack.pop()
            visited_tiles.append(cur_tile)
            if cur_tile.next is not None:
                for n in cur_tile.next:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_S = [opp(n)]
                        stack.append(adj_tile)
            if cur_tile.previous is not None:
                for n in cur_tile.previous:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_S = [opp(n)]
                        stack.append(adj_tile)

        visited_tiles = []
        stack = deque([ktu])
        while stack:
            cur_tile = stack.pop()
            visited_tiles.append(cur_tile)
            if cur_tile.next is not None:
                for n in cur_tile.next:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_U = [opp(n)]
                        stack.append(adj_tile)
            if cur_tile.previous is not None:
                for n in cur_tile.previous:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_U = [opp(n)]
                        stack.append(adj_tile)

        visited_tiles = []
        stack = deque([ktd])
        while stack:
            cur_tile = stack.pop()
            visited_tiles.append(cur_tile)
            if cur_tile.next is not None:
                for n in cur_tile.next:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_D = [opp(n)]
                        stack.append(adj_tile)
            if cur_tile.previous is not None:
                for n in cur_tile.previous:
                    adj_tile = retrieve_tile(cur_tile, n)
                    if adj_tile not in visited_tiles:
                        adj_tile.key_tile_D = [opp(n)]
                        stack.append(adj_tile)

        # for k, t in new_tiles.items():
        #     debug_print(t)
        #     print()

        return seed_tile
    
    def show_stage_selection(self):
        self.mode = "select_stages"

        self.update_back_button()
        self.done_btn.hide()
        self.stage_label.show()
        self.stage_combo.show()
        self.sim_mode_label.show()
        self.regular_sim_radio.show()
        self.step_sim_radio.show()
        self.run_btn.show()

        self.stage_combo.clear()

        options = []
        num_tiles = max(1, len(self.generator_tiles))
        stage = 1
        actual_stage = 1

        while num_tiles < MAX_SIM_SIZE:
            options.append((stage, actual_stage, num_tiles))
            num_tiles *= num_tiles
            stage += 1
            actual_stage *= 2

        if not options:
            options = [(1, 1)]

        for stage, actual_stage, num_tiles in options:
            self.stage_combo.addItem(
                f"{stage} - (stage: {actual_stage})",
                (stage, actual_stage, num_tiles),
            )

        if not hasattr(self, "_stage_warning_connected"):
            self.stage_combo.currentIndexChanged.connect(
                self.update_simulation_warning
            )
            self._stage_warning_connected = True

        self.update_simulation_warning()

        self.layer_label.setText(
            f"Origin selected: {self.origin_tile}. Choose simulation depth."
        )

    @staticmethod
    def extract_3d_layout(seed_tile):
        coords = {}
        visited = set()

        queue = deque()
        queue.append((seed_tile, (0, 0, 0)))

        while queue:
            tile, pos = queue.popleft()

            if id(tile) in visited:
                continue

            visited.add(id(tile))
            coords[tile] = pos

            x, y, z = pos

            neighbors = [
                (tile.tile_to_N, (x, y + 1, z)),
                (tile.tile_to_S, (x, y - 1, z)),
                (tile.tile_to_E, (x + 1, y, z)),
                (tile.tile_to_W, (x - 1, y, z)),
                (tile.tile_to_U, (x, y, z + 1)),
                (tile.tile_to_D, (x, y, z - 1)),
            ]

            for neighbor, npos in neighbors:
                if neighbor is not None:
                    queue.append((neighbor, npos))

        return coords
    
    @staticmethod
    def build_voxel_surface_mesh(coords_by_tile):
        positions = list(coords_by_tile.values())
        pos_set = set(positions)

        points = []
        faces = []
        colors = []

        face_defs = [
            ((1, 0, 0), [(1,0,0), (1,1,0), (1,1,1), (1,0,1)]),
            ((-1, 0, 0), [(0,0,0), (0,0,1), (0,1,1), (0,1,0)]),
            ((0, 1, 0), [(0,1,0), (0,1,1), (1,1,1), (1,1,0)]),
            ((0, -1, 0), [(0,0,0), (1,0,0), (1,0,1), (0,0,1)]),
            ((0, 0, 1), [(0,0,1), (1,0,1), (1,1,1), (0,1,1)]),
            ((0, 0, -1), [(0,0,0), (0,1,0), (1,1,0), (1,0,0)]),
        ]

        color_lookup = {
            "original": [0, 0, 0],
            "pseudo": [80, 80, 80],
            "terminal": [255, 0, 0],
            "normal": [173, 216, 230],
        }

        for tile, (x, y, z) in coords_by_tile.items():
            if tile.original_seed:
                c = color_lookup["original"]
            elif tile.pseudo_seed:
                c = color_lookup["pseudo"]
            elif tile.terminal:
                c = color_lookup["terminal"]
            else:
                c = color_lookup["normal"]

            for (dx, dy, dz), corners in face_defs:
                if (x + dx, y + dy, z + dz) in pos_set:
                    continue

                start = len(points)
                for ox, oy, oz in corners:
                    points.append((x + ox, y + oy, z + oz))

                faces.extend([4, start, start + 1, start + 2, start + 3])
                colors.append(c)

        mesh = pv.PolyData(
            np.asarray(points, dtype=np.float32),
            np.asarray(faces, dtype=np.int64)
        )
        mesh.cell_data["colors"] = np.array(colors, dtype=np.uint8)
        
        return mesh

    def display_simulation_result(self, seed_tile):
        coords = GeneratorBuilderWindow.extract_3d_layout(seed_tile)

        self.plotter.clear()
        self.plotter.set_background("white")
        self.plotter.add_axes()

        mesh = self.build_voxel_surface_mesh(coords)

        self.plotter.add_mesh(
            mesh,
            scalars="colors",
            rgb=True,
            show_edges=True,
            pickable=False,
        )

        self.plotter.camera_position = [
            (0, -25, 20),
            (0, 0, 5),
            (0, 0, 1),
        ]

        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)

        self.plotter.reset_camera()
        self.plotter.render()

        self.layer_label.setText(
            f"Simulation complete — displayed {len(coords)} tiles"
        )

    def restore_stage_selection_after_simulation(self, message=None):
        self.mode = "select_stages"
        self.stage_label.show()
        self.stage_combo.show()
        self.sim_mode_label.show()
        self.regular_sim_radio.show()
        self.step_sim_radio.show()
        self.run_btn.show()
        self.done_btn.hide()

        self.set_running_state(False)
        self.update_back_button()
        self.update_simulation_warning()

        if message is None:
            message = f"Origin selected: {self.origin_tile}. Choose simulation depth."

        self.layer_label.setText(message)

    def run_simulation(self):
        self.stages, _, _ = self.stage_combo.currentData()

        if self.origin_tile is None:
            return

        self.set_running_state(True)
        QApplication.processEvents()

        seed_tile = GeneratorBuilderWindow.create_seed(
            {
                f"{x},{y},{z}": None
                for x, y, z in self.generator_tiles
            },
            list(self.origin_tile),
        )

        self.sim_thread = QThread()

        if self.step_sim_radio.isChecked():
            self.sim_worker = StepSimulationWorker(seed_tile, self.stages)
        else:
            self.sim_worker = SimulationWorker(seed_tile, self.stages)

        self.sim_worker.moveToThread(self.sim_thread)

        self.sim_thread.started.connect(self.sim_worker.run)

        self.sim_worker.finished.connect(self.on_simulation_finished)
        self.sim_worker.error.connect(self.on_simulation_error)
        self.sim_worker.cancelled_signal.connect(self.on_simulation_cancelled)

        self.sim_worker.finished.connect(self.sim_thread.quit)
        self.sim_worker.error.connect(self.sim_thread.quit)
        self.sim_worker.cancelled_signal.connect(self.sim_thread.quit)

        self.sim_worker.finished.connect(self.sim_worker.deleteLater)
        self.sim_worker.error.connect(self.sim_worker.deleteLater)
        self.sim_worker.cancelled_signal.connect(self.sim_worker.deleteLater)

        self.sim_thread.finished.connect(self.sim_thread.deleteLater)

        self.sim_thread.start()

    def on_simulation_finished(self, seed_tile):
        self.mode = "display_result"
        self.update_back_button()
        self.set_running_state(False)
        self.display_simulation_result(seed_tile)

    def on_simulation_error(self, error_message):
        self.restore_stage_selection_after_simulation(
            f"Simulation failed: {error_message}"
        )

    def on_simulation_cancelled(self):
        self.restore_stage_selection_after_simulation(
            f"Simulation Cancelled."
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorBuilderWindow()
    window.show()
    sys.exit(app.exec())