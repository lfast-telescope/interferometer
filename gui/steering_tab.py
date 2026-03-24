"""
Beam Steering tab — manual jog control for the SMC100 stages.
"""

import io
import sys
import contextlib

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QDoubleSpinBox, QComboBox, QTextEdit,
    QMessageBox, QLineEdit,
)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal


class _SignalStream:
    """File-like object that emits each written line via a callback."""
    def __init__(self, callback):
        self._cb = callback
        self._buf = ""
    def write(self, text):
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line:
                self._cb(line)
    def flush(self):
        if self._buf:
            self._cb(self._buf)
            self._buf = ""


class _JogWorker(QThread):
    """Run a blocking setPositionRel(verbose=True) off the GUI thread."""
    stdout_line = pyqtSignal(str)   # each line printed by the controller
    finished = pyqtSignal()         # move complete
    error = pyqtSignal(str)

    def __init__(self, smc, step, channel, parent=None):
        super().__init__(parent)
        self.smc = smc
        self.step = step
        self.channel = channel

    def run(self):
        stream = _SignalStream(self.stdout_line.emit)
        try:
            old_stdout = sys.stdout
            sys.stdout = stream
            self.smc.setPositionRel(self.step, channel=self.channel, verbose=True)
            sys.stdout = old_stdout
            stream.flush()
        except Exception as exc:
            sys.stdout = old_stdout
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class _GoToWorker(QThread):
    """Run a blocking setPositionAbs(verbose=True) off the GUI thread."""
    stdout_line = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, smc, pos, channel, parent=None):
        super().__init__(parent)
        self.smc = smc
        self.pos = pos
        self.channel = channel

    def run(self):
        stream = _SignalStream(self.stdout_line.emit)
        try:
            old_stdout = sys.stdout
            sys.stdout = stream
            self.smc.setPositionAbs(self.pos, channel=self.channel, verbose=True)
            sys.stdout = old_stdout
            stream.flush()
        except Exception as exc:
            sys.stdout = old_stdout
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class _ResetWorker(QThread):
    """Run a blocking resetController() off the GUI thread."""
    stdout_line = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, smc, channel, parent=None):
        super().__init__(parent)
        self.smc = smc
        self.channel = channel

    def run(self):
        stream = _SignalStream(self.stdout_line.emit)
        try:
            old_stdout = sys.stdout
            sys.stdout = stream
            self.smc.resetController(channel=self.channel)
            sys.stdout = old_stdout
            stream.flush()
        except Exception as exc:
            sys.stdout = old_stdout
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class SteeringTab(QWidget):
    """Manual beam-steering controls using smc100 stages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.smc = None          # smc100 instance (created on connect)
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- Connection group ---
        conn_box = QGroupBox("Stage Connection")
        conn_layout = QHBoxLayout(conn_box)
        conn_layout.addWidget(QLabel("COM port:"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.addItems(["COM3", "COM4", "COM5"])
        conn_layout.addWidget(self.port_combo)
        conn_layout.addWidget(QLabel("Channels:"))
        self.nchannels_spin = QDoubleSpinBox()
        self.nchannels_spin.setDecimals(0)
        self.nchannels_spin.setRange(1, 4)
        self.nchannels_spin.setValue(3)
        conn_layout.addWidget(self.nchannels_spin)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._toggle_connection)
        conn_layout.addWidget(self.connect_btn)
        root.addWidget(conn_box)

        # --- Jog controls ---
        jog_box = QGroupBox("Jog Controls")
        jog_grid = QGridLayout(jog_box)

        jog_grid.addWidget(QLabel("Step size (mm):"), 0, 0)
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setDecimals(4)
        self.step_spin.setRange(0.0001, 5.0)
        self.step_spin.setValue(0.01)
        self.step_spin.setSingleStep(0.005)
        jog_grid.addWidget(self.step_spin, 0, 1)

        labels = ["Ch1 (Tilt)", "Ch2 (Tip)", "Ch3 (Focus)"]
        self.minus_btns = []
        self.plus_btns = []
        self.pos_labels = []
        for row, label in enumerate(labels, start=1):
            jog_grid.addWidget(QLabel(label), row, 0)
            minus = QPushButton("−")
            plus = QPushButton("+")
            pos = QLabel("--")
            pos.setMinimumWidth(160)
            pos.setAlignment(Qt.AlignCenter)
            minus.clicked.connect(lambda _, ch=row: self._jog(ch, -1))
            plus.clicked.connect(lambda _, ch=row: self._jog(ch, +1))
            jog_grid.addWidget(minus, row, 1)
            jog_grid.addWidget(pos, row, 2)
            jog_grid.addWidget(plus, row, 3)
            self.minus_btns.append(minus)
            self.plus_btns.append(plus)
            self.pos_labels.append(pos)

        root.addWidget(jog_box)

        # --- Go To Position ---
        goto_box = QGroupBox("Go To Position")
        goto_grid = QGridLayout(goto_box)
        labels = ["Ch1 (Tilt)", "Ch2 (Tip)", "Ch3 (Focus)"]
        self.goto_edits = []
        self.goto_btns = []
        for row, label in enumerate(labels):
            goto_grid.addWidget(QLabel(label), row, 0)
            edit = QLineEdit()
            edit.setPlaceholderText("position (mm)")
            goto_grid.addWidget(edit, row, 1)
            go_btn = QPushButton("Go")
            go_btn.setEnabled(False)
            go_btn.clicked.connect(lambda _, ch=row + 1: self._go_to(ch))
            goto_grid.addWidget(go_btn, row, 2)
            self.goto_edits.append(edit)
            self.goto_btns.append(go_btn)
        root.addWidget(goto_box)

        # --- Reset controller ---
        reset_box = QGroupBox("Reset Controller")
        reset_layout = QHBoxLayout(reset_box)
        reset_layout.addWidget(QLabel("Channel:"))
        self.reset_ch_spin = QDoubleSpinBox()
        self.reset_ch_spin.setDecimals(0)
        self.reset_ch_spin.setRange(1, 3)
        self.reset_ch_spin.setValue(1)
        reset_layout.addWidget(self.reset_ch_spin)
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset_controller)
        self.reset_btn.setEnabled(False)
        reset_layout.addWidget(self.reset_btn)
        root.addWidget(reset_box)

        # --- Log ---
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        root.addWidget(self.log)

        root.addStretch()
        self._set_jog_enabled(False)

    # -------------------------------------------------------------- actions
    def _toggle_connection(self):
        if self.smc is None:
            self._connect()
        else:
            self._disconnect()

    def _connect(self):
        try:
            from LFASTfiber.libs.libNewport import smc100
        except ImportError:
            QMessageBox.critical(
                self, "Import Error",
                "Could not import smc100 from LFASTfiber.libs.libNewport.\n"
                "Make sure the library is installed.")
            return

        port = self.port_combo.currentText()
        nch = int(self.nchannels_spin.value())
        try:
            # Capture stdout from smc100 constructor (stage ID / state info)
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                self.smc = smc100(port, nchannels=nch)
            output = f.getvalue().strip()
            if output:
                for line in output.splitlines():
                    self._log(line)
            self.connect_btn.setText("Disconnect")
            self._set_jog_enabled(True)
            # Use cached state from constructor instead of re-querying serial
            self._update_positions_from_cache()
        except Exception as exc:
            QMessageBox.critical(self, "Connection Error", str(exc))
            self.smc = None

    def _disconnect(self):
        if self.smc is not None:
            try:
                self.smc.close()
            except Exception:
                pass
            self.smc = None
        self.connect_btn.setText("Connect")
        self._set_jog_enabled(False)
        for lbl in self.pos_labels:
            lbl.setText("--")
        self._log("Disconnected")

    def _jog(self, channel, direction):
        if self.smc is None:
            return
        step = self.step_spin.value() * direction
        self._set_jog_enabled(False)
        self._jog_channel = channel
        self._jog_worker = _JogWorker(self.smc, step, channel)
        self._jog_worker.stdout_line.connect(self._on_jog_stdout)
        self._jog_worker.error.connect(lambda msg: self._log(f"Jog error: {msg}"))
        self._jog_worker.finished.connect(self._on_jog_finished)
        self._log(f"Ch{channel} moving {step:+.4f} mm …")
        self._jog_worker.start()

    def _on_jog_stdout(self, line):
        """Handle each stdout line emitted during a move."""
        self._log(line)
        # Parse "Current position: 1TP22.34664 MOVING" style output
        if "Current position:" in line:
            parts = line.split()
            # parts ~ ['Current', 'position:', '1TP22.34664', 'MOVING']
            if len(parts) >= 4:
                raw_pos = parts[2]
                state = parts[3]
                ch = self._jog_channel
                numeric = self._parse_position(raw_pos)
                lbl = self.pos_labels[ch - 1]
                if numeric is not None:
                    lbl.setText(f"{numeric:.4f}  |  {state}")
                else:
                    lbl.setText(f"{raw_pos}  |  {state}")

    def _on_jog_finished(self):
        """Re-enable controls after move completes."""
        self._jog_worker = None
        self._set_jog_enabled(True)

    def _go_to(self, channel):
        if self.smc is None:
            return
        text = self.goto_edits[channel - 1].text().strip()
        try:
            pos = float(text)
        except ValueError:
            self._log(f"Ch{channel}: invalid position \"{text}\"")
            return
        self._set_jog_enabled(False)
        self._goto_channel = channel
        self._goto_worker = _GoToWorker(self.smc, pos, channel)
        self._goto_worker.stdout_line.connect(self._on_goto_stdout)
        self._goto_worker.error.connect(lambda msg: self._log(f"GoTo error: {msg}"))
        self._goto_worker.finished.connect(self._on_goto_finished)
        self._log(f"Ch{channel} moving to {pos:.4f} mm …")
        self._goto_worker.start()

    def _on_goto_stdout(self, line):
        self._log(line)
        # Update the Jog Controls position label
        if "Current position:" in line:
            parts = line.split()
            if len(parts) >= 4:
                raw_pos = parts[2]
                state = parts[3]
                ch = self._goto_channel
                numeric = self._parse_position(raw_pos)
                lbl = self.pos_labels[ch - 1]
                if numeric is not None:
                    lbl.setText(f"{numeric:.4f}  |  {state}")
                else:
                    lbl.setText(f"{raw_pos}  |  {state}")

    def _on_goto_finished(self):
        self._goto_worker = None
        self._set_jog_enabled(True)

    def _reset_controller(self):
        if self.smc is None:
            return
        ch = int(self.reset_ch_spin.value())
        self._set_jog_enabled(False)
        self._reset_worker = _ResetWorker(self.smc, ch)
        self._reset_worker.stdout_line.connect(self._on_reset_stdout)
        self._reset_worker.error.connect(lambda msg: self._log(f"Reset error: {msg}"))
        self._reset_worker.finished.connect(self._on_reset_finished)
        self._reset_worker.start()

    def _on_reset_stdout(self, line):
        self._log(line)

    def _on_reset_finished(self):
        self._reset_worker = None
        self._update_positions()
        self._set_jog_enabled(True)

    @staticmethod
    def _parse_position(raw_pos):
        """Extract numeric value from raw position string like '1TP22.33664'."""
        try:
            return float(raw_pos.split("TP")[-1])
        except (IndexError, ValueError, TypeError):
            return None

    def _update_positions(self):
        if self.smc is None:
            return
        for i, lbl in enumerate(self.pos_labels, start=1):
            try:
                raw_pos = self.smc.getPosition(channel=i)
                state = self.smc.state[i].get('CURSTATE', '??')
                numeric = self._parse_position(raw_pos)
                if numeric is not None:
                    lbl.setText(f"{numeric:.4f}  |  {state}")
                else:
                    lbl.setText(f"{raw_pos}  |  {state}")
            except Exception:
                lbl.setText("err")

    def _update_positions_from_cache(self):
        """Update labels from already-cached smc100 state (no serial I/O)."""
        if self.smc is None:
            return
        for i, lbl in enumerate(self.pos_labels, start=1):
            try:
                raw_pos = self.smc.state[i].get('PA', '')
                state = self.smc.state[i].get('CURSTATE', '??')
                numeric = self._parse_position(raw_pos)
                if numeric is not None:
                    lbl.setText(f"{numeric:.4f}  |  {state}")
                else:
                    lbl.setText(f"{raw_pos}  |  {state}")
            except Exception:
                lbl.setText("err")

    def _set_jog_enabled(self, enabled):
        for btn in self.minus_btns + self.plus_btns + self.goto_btns:
            btn.setEnabled(enabled)
        self.step_spin.setEnabled(enabled)
        self.reset_btn.setEnabled(enabled)

    def _log(self, msg):
        self.log.append(msg)

    # -------------------------------------------------------------- cleanup
    def cleanup(self):
        """Call on application exit to release hardware."""
        self._disconnect()
