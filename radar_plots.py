import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.patheffects as pe

# Theme Colors
BG_COLOR = '#0B0F19'  # Dark Navy
AXES_COLOR = '#0B0F19'
TEXT_COLOR = '#E0E0E0'
GRID_COLOR = '#1F2937'
CYAN = '#00FFFF'
GREEN = '#00FF00'

class BaseRadarPlot(QWidget):
    def __init__(self, parent=None, title="", xlabel="", ylabel=""):
        super().__init__(parent)
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.figure.patch.set_facecolor(BG_COLOR)
        
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        # Style Toolbar
        self.toolbar.setStyleSheet("background-color: #1F2937; color: white;")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        
        self.ax = self.figure.add_subplot(111)
        self.title = title
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.setup_dark_axes()
        
    def setup_dark_axes(self):
        self.ax.clear()
        self.ax.set_facecolor(AXES_COLOR)
        self.ax.set_title(self.title, color=CYAN, pad=10, fontsize=12, fontweight='bold')
        self.ax.set_xlabel(self.xlabel, color=TEXT_COLOR, fontsize=10)
        self.ax.set_ylabel(self.ylabel, color=TEXT_COLOR, fontsize=10)
        
        self.ax.tick_params(colors=TEXT_COLOR, which='both')
        for spine in self.ax.spines.values():
            spine.set_color('#374151')
            
        self.ax.grid(True, color=GRID_COLOR, linestyle='-', linewidth=0.5, alpha=0.8)
        self.figure.tight_layout()

class AScanRadarPlot(BaseRadarPlot):
    def __init__(self, parent=None):
        super().__init__(parent, title="A-Scan Radar Trace", xlabel="Time (ns)", ylabel="Amplitude")
        self.line = None
        
    def plot_data(self, time_array, amplitude_array):
        self.setup_dark_axes()
        if len(time_array) == 0:
            self.canvas.draw()
            return
            
        # Glowing effect plot
        self.line, = self.ax.plot(
            time_array, amplitude_array, 
            color=GREEN, 
            linewidth=1.5,
            path_effects=[pe.withStroke(linewidth=3, foreground='#004400')] # Glow
        )
        
        # Find Peak
        max_idx = np.argmax(np.abs(amplitude_array))
        peak_t = time_array[max_idx]
        peak_a = amplitude_array[max_idx]
        
        # Mark Peak
        self.ax.scatter(peak_t, peak_a, color='red', s=50, zorder=5, 
                        path_effects=[pe.withStroke(linewidth=3, foreground='black')])
        self.ax.annotate(f"Peak (T: {peak_t:.1f}ns)", xy=(peak_t, peak_a), 
                         xytext=(10, 10), textcoords="offset points", color='red', fontsize=8)
        
        # Grid like oscilloscope
        self.ax.grid(True, color='#003300', linestyle='-', linewidth=1.0)
        
        self.ax.set_xlim([0, time_array[-1]])
        max_amp = np.max(np.abs(amplitude_array))
        if max_amp == 0: max_amp = 1.0
        self.ax.set_ylim([-max_amp * 1.5, max_amp * 1.5])
        
        self.figure.tight_layout()
        self.canvas.draw()

class BScanRadarPlot(BaseRadarPlot):
    def __init__(self, parent=None):
        super().__init__(parent, title="Subsurface Radar Profile (B-Scan)", xlabel="Distance (m)", ylabel="Time (ns)")
        self.im = None
        self.colormap = 'magma' # Dark theme friendly default
        
    def plot_data(self, b_scan_data, time_array, cmap=None):
        self.setup_dark_axes()
        if cmap: self.colormap = cmap
        if len(time_array) == 0 or b_scan_data.size == 0:
            self.canvas.draw()
            return
            
        n_traces = b_scan_data.shape[1]
        max_time = time_array[-1]
        
        extent = [-n_traces/2 * 0.05, n_traces/2 * 0.05, max_time, 0]
        vmax = np.max(np.abs(b_scan_data)) if b_scan_data.size > 0 else 1.0
        if vmax == 0: vmax = 1.0
        
        self.im = self.ax.imshow(b_scan_data, aspect='auto', cmap=self.colormap, 
                                 extent=extent, vmin=-vmax, vmax=vmax)
        
        self.ax.set_ylabel("Time (ns) (Depth \u2193)", color=TEXT_COLOR)
        self.figure.tight_layout()
        self.canvas.draw()
        
    def set_colormap(self, cmap):
        self.colormap = cmap
        if self.im:
            self.im.set_cmap(cmap)
            self.canvas.draw()

class CScanRadarPlot(BaseRadarPlot):
    def __init__(self, parent=None):
        super().__init__(parent, title="C-Scan Detection Map", xlabel="X Location", ylabel="Y Location")
        self.im = None
        
    def plot_data(self, c_scan_data, threshold=0.0):
        self.setup_dark_axes()
        if c_scan_data.size == 0:
            self.canvas.draw()
            return
            
        extent = [-1.5, 1.5, -1.5, 1.5]
        
        # Apply threshold visibility
        data = np.copy(c_scan_data)
        max_val = np.max(data)
        if max_val > 0:
            data[data < (threshold/100.0) * max_val] = 0
            
        # Locator crosshairs
        if np.max(data) > 0:
            self.ax.axhline(0, color='red', linestyle='--', alpha=0.5)
            self.ax.axvline(0, color='red', linestyle='--', alpha=0.5)
            self.ax.plot(0, 0, marker='o', markersize=10, markerfacecolor='none', markeredgecolor='red')

        self.im = self.ax.imshow(data, aspect='equal', cmap='inferno', 
                                 extent=extent, origin='lower')
        
        self.figure.tight_layout()
        self.canvas.draw()
