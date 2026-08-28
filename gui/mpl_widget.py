"""
Reusable Matplotlib canvas widget for embedding plots in PyQt5.
"""

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QVBoxLayout, QWidget


class _LargerCoordsToolbar(NavigationToolbar2QT):
    """NavigationToolbar with 30% larger coordinate readout font."""

    def __init__(self, canvas, parent):
        super().__init__(canvas, parent)
        # locLabel is the QLabel that shows cursor coordinates
        if hasattr(self, 'locLabel'):
            font = self.locLabel.font()
            font.setPointSizeF(font.pointSizeF() * 1.3)
            self.locLabel.setFont(font)


class MplCanvas(FigureCanvasQTAgg):
    """A thin wrapper around FigureCanvasQTAgg that creates its own Figure."""

    def __init__(self, parent=None, width=8, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi,
                          constrained_layout=True)
        self.fig.set_constrained_layout_pads(
            w_pad=0.02, h_pad=0.02, wspace=0.02, hspace=0.02)
        super().__init__(self.fig)
        self.setParent(parent)

    def clear(self):
        self.fig.clear()
        self.draw()


class MplWidget(QWidget):
    """Widget containing a MplCanvas and a NavigationToolbar."""

    def __init__(self, parent=None, width=8, height=5):
        super().__init__(parent)
        self.canvas = MplCanvas(self, width=width, height=height)
        self.toolbar = _LargerCoordsToolbar(self.canvas, self)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    @property
    def fig(self):
        return self.canvas.fig

    def clear(self):
        self.canvas.clear()

    def draw(self):
        self.canvas.draw()
