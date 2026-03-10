import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

class BasePlotWidget(QWidget):
    def __init__(self, parent=None, title="", xlabel="", ylabel=""):
        super().__init__(parent)
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Adjust layout for better fit
        self.figure.tight_layout()
        
        self.ax = self.figure.add_subplot(111)
        self.title = title
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.setup_axes()
        
    def setup_axes(self):
        self.ax.clear()
        self.ax.set_title(self.title, pad=10, fontsize=11, fontweight='bold')
        self.ax.set_xlabel(self.xlabel, fontsize=9)
        self.ax.set_ylabel(self.ylabel, fontsize=9)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.figure.tight_layout()

class AScanWidget(BasePlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent, title="A-Scan (1D Radar Trace)", xlabel="Time (ns)", ylabel="Amplitude")
        self.line = None
        
    def plot_data(self, time_array, amplitude_array):
        self.setup_axes()
        self.line, = self.ax.plot(time_array, amplitude_array, color='#007BFF', linewidth=1.5)
        self.ax.set_xlim([0, time_array[-1] if len(time_array) > 0 else 20])
        
        # dynamic ylim
        max_amp = np.max(np.abs(amplitude_array)) if len(amplitude_array) > 0 else 1.0
        if max_amp == 0:
            max_amp = 1.0
        self.ax.set_ylim([-max_amp * 1.5, max_amp * 1.5])
        self.figure.tight_layout()
        self.canvas.draw()

class BScanWidget(BasePlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent, title="B-Scan (2D Profile)", xlabel="Position (m)", ylabel="Time (ns)")
        self.im = None
        
    def plot_data(self, b_scan_data, time_array):
        self.setup_axes()
        
        # b_scan_data shape is (time_samples, position_traces)
        n_traces = b_scan_data.shape[1]
        max_time = time_array[-1] if len(time_array) > 0 else 20
        
        # Position is arbitrarily -1.25m to +1.25m for 50 traces (0.05m step)
        extent = [-n_traces/2 * 0.05, n_traces/2 * 0.05, max_time, 0]
        
        # Plot radargram (diverging colormap usually preferred for GPR like 'seismic' or 'gray')
        vmax = np.max(np.abs(b_scan_data)) if b_scan_data.size > 0 else 1.0
        if vmax == 0: vmax = 1.0
        
        self.im = self.ax.imshow(b_scan_data, aspect='auto', cmap='seismic', 
                                 extent=extent, vmin=-vmax, vmax=vmax)
        
        self.ax.set_ylabel("Time (ns) (Depth \u2193)")
        self.figure.tight_layout()
        self.canvas.draw()

class CScanWidget(BasePlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent, title="C-Scan (Top-Down Detection Map)", xlabel="X Position (m)", ylabel="Y Position (m)")
        self.im = None
        
    def plot_data(self, c_scan_data):
        self.setup_axes()
        
        # Position arbitrary coordinates
        extent = [-1.25, 1.25, -1.25, 1.25]
        
        self.im = self.ax.imshow(c_scan_data, aspect='equal', cmap='viridis', 
                                 extent=extent, origin='lower')
        
        self.figure.tight_layout()
        self.canvas.draw()

from matplotlib.patches import Rectangle, Circle

class LayerViewWidget(BasePlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent, title="Physical Environment (Cross Section)", xlabel="Distance (m)", ylabel="Depth (m)")
        
    def plot_environment(self, layers, buried_object):
        self.setup_axes()
        
        # Use an inverted Y axis so Depth goes down
        self.ax.invert_yaxis()
        
        # Choose a consistent width for the visualization
        width = 2.0
        x_min = -width / 2
        
        current_depth = 0.0
        colors = ['#E6F3FF', '#808080', '#D3D3D3', '#DAA520', '#A0522D', '#228B22']
        
        for i, layer in enumerate(layers):
            # If thickness is infinite, just give it a visual block size (e.g., 0.5m)
            vis_thickness = 0.5 if layer.thickness == np.inf else layer.thickness
            color = colors[i % len(colors)]
            
            # Draw rectangle
            rect = Rectangle((x_min, current_depth), width, vis_thickness, 
                             facecolor=color, edgecolor='black', alpha=0.7)
            self.ax.add_patch(rect)
            
            # Add text label
            text_y = current_depth + vis_thickness / 2
            label = f"{layer.name}\n(\u03B5r={layer.epsilon_r}, \u03C3={layer.sigma})"
            self.ax.text(0, text_y, label, ha='center', va='center', fontsize=9, fontweight='bold')
            
            current_depth += vis_thickness
            
        # Draw the object if exists
        if buried_object and buried_object.layer_index >= 0 and buried_object.layer_index < len(layers):
            obj_depth = 0.0
            for i in range(buried_object.layer_index):
                obj_depth += 0.5 if layers[i].thickness == np.inf else layers[i].thickness
            
            obj_depth += buried_object.depth
            
            circle = Circle((0, obj_depth), buried_object.radius, facecolor='red', edgecolor='black')
            self.ax.add_patch(circle)
            
            self.ax.text(buried_object.radius + 0.05, obj_depth, f"{buried_object.object_type}", 
                         color='red', fontweight='bold', va='center')
                         
        self.ax.set_xlim([x_min, width/2])
        self.ax.set_ylim([current_depth, -0.1])
        self.figure.tight_layout()
        self.canvas.draw()
