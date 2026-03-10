import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, Circle
import matplotlib.patheffects as pe

# Theme Colors
BG_COLOR = '#080B10'  # Deepest Navy
AXES_COLOR = '#0A0E17'
CYAN = '#00FFFF'
TEXT_COLOR = '#E0E0E0'

# Layer Colors for Dark Theme
LAYER_COLORS = [
    '#1A2B4C', # Very dark blue (Air)
    '#2A2A2A', # Dark Asphalt
    '#3A3E45', # Dark concrete
    '#4A3B22', # Dark dirt/sand
    '#2F4F4F', # Deep Slate Gray
]

class EnvironmentVisualization(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(4, 6), dpi=100)
        self.figure.patch.set_facecolor(BG_COLOR)
        
        self.canvas = FigureCanvas(self.figure)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        
        self.ax = self.figure.add_subplot(111)
        
    def setup_axes(self):
        self.ax.clear()
        self.ax.set_facecolor(AXES_COLOR)
        self.ax.set_title("Subsurface Cross-Section", color=CYAN, pad=15, fontsize=12, fontweight='bold')
        self.ax.set_ylabel("Depth (m)", color=TEXT_COLOR, fontsize=10)
        
        self.ax.tick_params(colors=TEXT_COLOR, which='both')
        self.ax.xaxis.set_visible(False) # Hide x axis ticks, only show depth
        
        for spine in self.ax.spines.values():
            spine.set_color('#374151')
            
        self.ax.invert_yaxis()
        self.figure.tight_layout()
        
    def render_environment(self, layers, buried_object):
        self.setup_axes()
        
        width = 2.0
        x_min = -width / 2
        
        current_depth = 0.0
        
        if not layers:
            # Empty state
            self.ax.set_xlim([-1, 1])
            self.ax.set_ylim([0.1, -0.1])
            self.canvas.draw()
            return
        
        for i, layer in enumerate(layers):
            vis_thickness = 0.5 if layer.thickness == np.inf else layer.thickness
            color = LAYER_COLORS[i % len(LAYER_COLORS)]
            
            # Draw Layer Rectangle
            rect = Rectangle((x_min, current_depth), width, vis_thickness, 
                             facecolor=color, edgecolor=CYAN, linewidth=1, alpha=0.9)
            self.ax.add_patch(rect)
            
            # Layer text
            text_y = current_depth + vis_thickness / 2
            label = f"{layer.name}\nεr={layer.epsilon_r:.1f} | σ={layer.sigma:.2e}"
            self.ax.text(0, text_y, label, ha='center', va='center', 
                         color='white', fontsize=10, fontweight='bold',
                         path_effects=[pe.withStroke(linewidth=2, foreground='black')])
            
            current_depth += vis_thickness
            
        # Draw the target object
        if buried_object and buried_object.layer_index >= 0 and buried_object.layer_index < len(layers):
            obj_depth = 0.0
            for i in range(buried_object.layer_index):
                obj_depth += 0.5 if layers[i].thickness == np.inf else layers[i].thickness
            
            obj_depth += buried_object.depth
            
            # Glowing Red Sphere
            glow = Circle((0, obj_depth), buried_object.radius * 1.5, facecolor='none', edgecolor='red', alpha=0.5, linewidth=3)
            sphere = Circle((0, obj_depth), buried_object.radius, facecolor='#FF3333', edgecolor='#FF0000', zorder=5)
            self.ax.add_patch(glow)
            self.ax.add_patch(sphere)
            
            # Object annotation
            self.ax.annotate(
                f"{buried_object.object_type}",
                xy=(buried_object.radius, obj_depth),
                xytext=(buried_object.radius + 0.1, obj_depth),
                color='#FF3333', fontweight='heavy',
                arrowprops=dict(arrowstyle="-|>", color='#FF3333'),
                path_effects=[pe.withStroke(linewidth=2, foreground='black')]
            )

        if current_depth == 0:
            current_depth = 0.5
            
        self.ax.set_xlim([x_min, width/2])
        self.ax.set_ylim([current_depth + 0.1, -0.1])
        
        self.figure.tight_layout()
        self.canvas.draw()
