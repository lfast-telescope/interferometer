"""
Main window — assembles tabs and wires signals.
"""

import sys
import os

from PyQt5.QtWidgets import QMainWindow, QTabWidget, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from .steering_tab import SteeringTab
from .measurement_tab import MeasurementTab
from .results_tab import ResultsTab
from .analysis_tab import AnalysisTab
from .long_exposure_tab import LongExposureTab


class MainWindow(QMainWindow):
    """Top-level window for the Interferometer GUI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LFAST Interferometer Control")
        self.resize(1200, 800)

        # --- Central tab widget ---
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.steering_tab = SteeringTab()
        self.measurement_tab = MeasurementTab()
        self.results_tab = ResultsTab()
        self.analysis_tab = AnalysisTab()
        self.long_exposure_tab = LongExposureTab()

        self.tabs.addTab(self.steering_tab, "Beam Steering")
        self.tabs.addTab(self.measurement_tab, "Measurement")
        self.tabs.addTab(self.results_tab, "Results / Compare")
        self.tabs.addTab(self.analysis_tab, "Analysis")
        self.tabs.addTab(self.long_exposure_tab, "Long Exposure")

        # Wire measurement → results
        self.measurement_tab.on_surface_ready = self._on_surface_ready
        # Wire measurement → long exposure mirror number
        self.measurement_tab.on_take_new_done = self.long_exposure_tab.mirror_spin.setValue

        #Set custom icon
        self.setWindowIcon(QIcon(r"C:\Users\lfast-admin\Pictures\Untitled.ico"))

    def _on_surface_ready(self, result_dict, slot_index):
        """Forward from measurement tab to results tab and switch view."""
        self.results_tab.set_surface(result_dict, slot_index)
        self.tabs.setCurrentWidget(self.results_tab)

    def closeEvent(self, event):
        self.steering_tab.cleanup()
        self.long_exposure_tab.cleanup()
        super().closeEvent(event)


def run_gui():
    """Entry-point function — create the QApplication and show the window."""
    # Use non-interactive Agg-compatible backend for embedded matplotlib
    import matplotlib
    matplotlib.use('Qt5Agg')

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
