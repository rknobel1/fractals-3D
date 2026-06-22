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
)


class GeneratorBuilderWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("3D Generator Builder")
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

        self.prev_btn = QPushButton("Previous Layer")
        self.prev_btn.clicked.connect(self.previous_layer)
        sidebar_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next Layer")
        self.next_btn.clicked.connect(self.next_layer)
        sidebar_layout.addWidget(self.next_btn)

        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(self.reset_view)
        sidebar_layout.addWidget(reset_btn)

        self.done_btn = QPushButton("Done")
        self.done_btn.clicked.connect(self.enter_origin_selection_mode)
        sidebar_layout.addWidget(self.done_btn)

        self.done_btn.setEnabled(False)

        sidebar_layout.addStretch()

        # Selecting origin cube
        self.mode = "build"
        self.origin_tile = None

        main_layout.addWidget(sidebar, stretch=1)

        self.setCentralWidget(main_widget)

        self.update_layer_buttons()
        self.setup_scene()

    def set_origin_tile(self, tile):
        self.origin_tile = tile

        self.redraw_scene()

        self.layer_label.setText(
            f"Selected origin: {tile} — press Done to confirm"
        )
        self.done_btn.setText("Done")
        self.done_btn.setEnabled(True)

    def setup_scene(self):
        self.plotter.set_background("white")
        self.plotter.add_axes()

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
        )

        self.draw_active_layer_grid()

        self.plotter.camera_position = "iso"
        self.plotter.reset_camera()
        self.enable_cube_placement()

    def layer_has_tiles(self, z):
        return any(tile_z == z for _x, _y, tile_z in self.generator_tiles)
    
    def has_higher_layer(self):
        return any(tile_z > self.current_layer for _x, _y, tile_z in self.generator_tiles)
    
    def get_layer_label_text(self):
        if self.mode == "select_origin":
            return f"Select origin cube — Layer Z = {self.current_layer}"

        if self.origin_tile is not None:
            return f"Origin selected: {self.origin_tile}"

        return f"Current Layer: Z = {self.current_layer}"

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

    def enable_cube_placement(self):
        self.plotter.iren.add_observer("LeftButtonPressEvent", self.on_left_click)

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

        if tile in self.generator_tiles:
            self.generator_tiles.remove(tile)
            self.remove_cube(tile)
        else:
            self.generator_tiles.add(tile)
            actor = self.add_cube(tile, color="lightblue", opacity=1.0)
            self.tile_actors[tile] = actor

        self.update_done_button()
        self.update_layer_buttons()
        self.plotter.render()

    def redraw_scene(self):
        self.plotter.clear()

        self.plotter.set_background("white")
        self.plotter.add_axes()

        self.draw_bounding_box()
        self.draw_active_layer_grid()
        self.draw_all_cubes()

        self.plotter.render()

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
        self.plotter.camera_position = "iso"
        self.plotter.reset_camera()

    def enter_origin_selection_mode(self):
        if self.mode == "build":
            if not self.generator_tiles:
                return

            self.mode = "select_origin"
            self.done_btn.setText("Confirm Origin")
            self.done_btn.setEnabled(False)
            self.layer_label.setText(
                f"Select origin cube — Layer Z = {self.current_layer}"
            )
            return

        if self.mode == "select_origin":
            if self.origin_tile is None:
                return

            self.mode = "origin_selected"
            self.done_btn.setText("Origin Selected")
            self.done_btn.setEnabled(False)
            self.layer_label.setText(f"Origin selected: {self.origin_tile}")
            return


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorBuilderWindow()
    window.show()
    sys.exit(app.exec())