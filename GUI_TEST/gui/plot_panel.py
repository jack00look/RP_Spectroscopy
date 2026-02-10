import pyqtgraph as pg
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QLabel
from PySide6.QtCore import Qt, Slot


class BasePlotHandler(QWidget):
    """
    Abstract base class for mode-specific plot handlers.
    Subclass this and implement update() to add a new FSM visualization mode.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def update(self, packet: dict):
        raise NotImplementedError("Subclasses must implement update()")


class SweepPlotHandler(BasePlotHandler):
    """
    Handles the SWEEP mode visualization.
    Shows two vertically-stacked plots sharing the same x-axis:
      - Top:    error_signal   (blue)
      - Bottom: monitor_signal (orange)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # --- Top plot: Error Signal ---
        self.plot_error = pg.PlotWidget(title="Error Signal")
        self.plot_error.setBackground('k')
        self.plot_error.showGrid(x=True, y=True, alpha=0.3)
        self.plot_error.getPlotItem().setLabel('left', 'Error Signal')
        self.plot_error.getPlotItem().getAxis('bottom').enableAutoSIPrefix(False)
        self.plot_error.getPlotItem().getAxis('left').enableAutoSIPrefix(False)
        self.curve_error = self.plot_error.plot(pen=pg.mkPen('c', width=1.5))

        # --- Bottom plot: Monitor Signal ---
        self.plot_monitor = pg.PlotWidget(title="Monitor Signal")
        self.plot_monitor.setBackground('k')
        self.plot_monitor.showGrid(x=True, y=True, alpha=0.3)
        self.plot_monitor.getPlotItem().setLabel('left', 'Monitor Signal')
        self.plot_monitor.getPlotItem().setLabel('bottom', 'Voltage', units='V')
        self.plot_monitor.getPlotItem().getAxis('bottom').enableAutoSIPrefix(False)
        self.plot_monitor.getPlotItem().getAxis('left').enableAutoSIPrefix(False)
        self.curve_monitor = self.plot_monitor.plot(pen=pg.mkPen(color=(255, 165, 0), width=1.5))

        # Link x-axes so zooming/panning is synchronised
        self.plot_monitor.setXLink(self.plot_error)

        # Hide the x-axis label on the top plot (shared axis)
        self.plot_error.getPlotItem().setLabel('bottom', '')

        layout.addWidget(self.plot_error)
        layout.addWidget(self.plot_monitor)

    def update(self, packet: dict):
        x = packet.get("x")
        error = packet.get("error_signal")
        monitor = packet.get("monitor_signal")

        if x is None:
            return

        # Convert to numpy arrays if they aren't already
        x = np.asarray(x)
        if error is not None:
            self.curve_error.setData(x, np.asarray(error))
        if monitor is not None:
            self.curve_monitor.setData(x, np.asarray(monitor))


class PlotPanel(QWidget):
    """
    Mode-aware plot container.
    Routes incoming data packets to the correct handler based on packet['mode'].

    Usage:
        panel = PlotPanel()
        panel.register_handler("SWEEP", SweepPlotHandler())
        panel.update_plot({"mode": "SWEEP", "x": ..., "error_signal": ..., "monitor_signal": ...})

    To add a new mode, create a BasePlotHandler subclass and register it.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._handlers: dict[str, BasePlotHandler] = {}

        # Placeholder shown before first data arrives
        self._placeholder = QLabel("Waiting for data...")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("color: #888; font-size: 16px;")
        self._stack.addWidget(self._placeholder)

        # Register default handlers
        self.register_handler("SWEEP", SweepPlotHandler())

    def register_handler(self, mode: str, handler: BasePlotHandler):
        """Register a plot handler for a given FSM mode."""
        self._handlers[mode] = handler
        self._stack.addWidget(handler)

    @Slot(dict)
    def update_plot(self, packet: dict):
        """Route a data packet to the appropriate handler."""
        mode = packet.get("mode")
        handler = self._handlers.get(mode)
        if handler:
            self._stack.setCurrentWidget(handler)
            handler.update(packet)
