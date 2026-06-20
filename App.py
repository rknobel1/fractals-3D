import sys
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

        # 3D viewport
        self.plotter = QtInteractor(main_widget)
        main_layout.addWidget(self.plotter, stretch=4)

        # Sidebar
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)

        self.layer_label = QLabel(f"Current Layer: Z = {self.current_layer}")
        sidebar_layout.addWidget(self.layer_label)

        next_btn = QPushButton("Next Layer")
        next_btn.clicked.connect(self.next_layer)
        sidebar_layout.addWidget(next_btn)

        prev_btn = QPushButton("Previous Layer")
        prev_btn.clicked.connect(self.previous_layer)
        sidebar_layout.addWidget(prev_btn)

        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(self.reset_view)
        sidebar_layout.addWidget(reset_btn)

        sidebar_layout.addStretch()

        main_layout.addWidget(sidebar, stretch=1)

        self.setCentralWidget(main_widget)

        self.setup_scene()

    def setup_scene(self):
        self.plotter.set_background("white")
        self.plotter.add_axes()

        bounds_cube = pv.Cube(
            center=(0, 0, 0),
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

    def next_layer(self):
        self.current_layer += 1
        self.layer_label.setText(f"Current Layer: Z = {self.current_layer}")

    def previous_layer(self):
        self.current_layer -= 1
        self.layer_label.setText(f"Current Layer: Z = {self.current_layer}")

    def reset_view(self):
        self.plotter.camera_position = "iso"
        self.plotter.reset_camera()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorBuilderWindow()
    window.show()
    sys.exit(app.exec())