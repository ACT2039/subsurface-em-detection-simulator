import sys
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QFormLayout, QLineEdit, QComboBox, 
                             QPushButton, QLabel, QGroupBox, QScrollArea, QFrame,
                             QSizePolicy, QSplitter)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QDoubleValidator, QFont

from simulation_engine import SimulationEngine, RadarConfig, Layer, BuriedObject
from radar_plots import AScanRadarPlot, BScanRadarPlot, CScanRadarPlot
from environment_visualization import EnvironmentVisualization

DARK_THEME_CSS = """
QWidget {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    color: #00FFFF;
    background-color: #080B10;
}
QMainWindow, QSplitter::handle {
    background-color: #05080A;
}
QPushButton {
    background-color: #1A2B4C;
    color: #00FFFF;
    border: 1px solid #00FFFF;
    border-radius: 4px;
    padding: 8px 12px;
    font-weight: bold;
    text-transform: uppercase;
}
QPushButton:hover {
    background-color: #00FFFF;
    color: #080B10;
}
QPushButton:pressed {
    background-color: #00CCCC;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #1F2937;
    border-radius: 4px;
    margin-top: 25px;
    padding-top: 15px;
    background-color: #0B0E14;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    left: 10px;
    top: -15px;
    background-color: transparent;
    color: #00FF00;
}
QLineEdit, QComboBox {
    padding: 6px;
    border: 1px solid #1F2937;
    border-radius: 3px;
    background-color: #05080A;
    color: #E0E0E0;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #00FFFF;
    background-color: #0B0E14;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:vertical {
    border: none;
    background-color: #05080A; /* Very dim track */
    width: 12px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background-color: #1F2937; /* Brighter handle */
    min-height: 30px;
    border-radius: 6px;
}
QScrollBar::handle:vertical:hover {
    background-color: #00FFFF; /* Cyan on hover */
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px; /* Hide arrows for a clean modern look */
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
#primary_btn {
    background-color: #004400;
    color: #00FF00;
    border: 1px solid #00FF00;
}
#primary_btn:hover {
    background-color: #00FF00;
    color: #000000;
}
#warning_btn {
    background-color: #442200;
    color: #FFBF00;
    border: 1px solid #FFBF00;
}
#warning_btn:hover {
    background-color: #FFBF00;
    color: #000000;
}
#metric_card {
    background-color: #0B0E14;
    border: 1px solid #1F2937;
    border-radius: 6px;
}
#metric_title {
    color: #8892B0;
    font-size: 11px;
    font-weight: bold;
    border: none;
}
#metric_value {
    color: #00FFFF;
    font-size: 16px;
    font-weight: bold;
    border: none;
}
#layer_card {
    background-color: #05080A;
    border: 1px solid #1F2937;
    border-left: 3px solid #00FFFF;
    border-radius: 2px;
}
"""

class MissionControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MISSION CONTROL: Subsurface EM Detection Simulator")
        self.resize(1400, 900)
        
        self.layer_widgets = []
        self.current_results = None
        self.validator = QDoubleValidator()
        self.validator.setNotation(QDoubleValidator.Notation.ScientificNotation)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Upper Splitter (Left: Controls, Center: Plots, Right: Env)
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.setup_panel_1_controls()
        self.setup_panel_2_displays()
        self.setup_panel_3_environment()
        
        # Bottom Panel (Analytics)
        self.v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.v_splitter.addWidget(self.h_splitter)
        
        analytics_panel = self.setup_panel_4_analytics()
        self.v_splitter.addWidget(analytics_panel)
        
        main_layout.addWidget(self.v_splitter)
        
        # Default Weights
        self.h_splitter.setSizes([350, 700, 350])
        self.v_splitter.setSizes([750, 150])
        
        # Disable cb_presets triggering early before UI finishes loading
        self.cb_presets.blockSignals(True)
        self.cb_presets.setCurrentIndex(1) # Start with Road Infrastructure
        self.cb_presets.blockSignals(False)
        self.load_preset()

    # =========================================================================
    # PANEL 1: RADAR CONTROLS
    # =========================================================================
    def setup_panel_1_controls(self):
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,5,0)
        
        controls_group = QGroupBox("System Uplink Parameters")
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        
        # Presets
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Scenario Target:"))
        self.cb_presets = QComboBox()
        self.cb_presets.blockSignals(True) # Block during setup
        self.cb_presets.addItems(["Custom Override", "Road Infrastructure", "Utility Detection", "Landmine Sweeper"])
        self.cb_presets.currentIndexChanged.connect(self.load_preset)
        self.cb_presets.blockSignals(False)
        preset_layout.addWidget(self.cb_presets)
        self.scroll_layout.addLayout(preset_layout)
        
        # Radar Config
        rc_group = QGroupBox("Transceiver Settings")
        rc_layout = QFormLayout()
        
        self.cb_radar_type = QComboBox()
        self.cb_radar_type.addItems(["Ground Penetrating Impulse", "FMCW Core", "UWB Synthetic Aperture"])
        
        self.le_frequency = QLineEdit("1e9")
        self.le_bandwidth = QLineEdit("5e8")
        self.le_pulse_width = QLineEdit("1e-9")
        self.le_transmit_power = QLineEdit("1.0")
        self.le_antenna_gain = QLineEdit("1.0")
        self.le_sampling_freq = QLineEdit("10e9")
        
        for le in [self.le_frequency, self.le_bandwidth, self.le_pulse_width, 
                   self.le_transmit_power, self.le_antenna_gain, self.le_sampling_freq]:
            le.setValidator(self.validator)
            
        rc_layout.addRow("Arch Type:", self.cb_radar_type)
        rc_layout.addRow("Center Freq (Hz):", self.le_frequency)
        rc_layout.addRow("Bandwidth (Hz):", self.le_bandwidth)
        rc_layout.addRow("Pulse Width (s):", self.le_pulse_width)
        rc_layout.addRow("Tx Power (W):", self.le_transmit_power)
        rc_layout.addRow("Antenna Gain:", self.le_antenna_gain)
        rc_layout.addRow("Sampling Rate (Hz):", self.le_sampling_freq)
        rc_group.setLayout(rc_layout)
        self.scroll_layout.addWidget(rc_group)
        
        # Layers
        self.layer_group = QGroupBox("Subsurface Map (Strata)")
        self.layer_main_layout = QVBoxLayout()
        self.layer_main_layout.setContentsMargins(5, 15, 5, 5) # add space for title
        self.layers_container = QWidget()
        self.layers_container_layout = QVBoxLayout(self.layers_container)
        self.layers_container_layout.setSpacing(10)
        self.layer_main_layout.addWidget(self.layers_container)
        
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("+ Add Strata")
        btn_rem = QPushButton("- Drop Strata")
        btn_add.clicked.connect(lambda: self.add_layer_widget("New Stratum", "1.0", "1", "1", "0"))
        btn_rem.clicked.connect(self.remove_layer)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_rem)
        self.layer_main_layout.addLayout(btn_layout)
        self.layer_group.setLayout(self.layer_main_layout)
        self.scroll_layout.addWidget(self.layer_group)
        
        # Object
        obj_group = QGroupBox("Anomalous Target Config")
        obj_layout = QFormLayout()
        self.cb_obj_type = QComboBox()
        self.cb_obj_type.addItems(["Metal Sphere", "Metal Cylinder", "Void", "Dielectric Inclusion"])
        self.cb_obj_layer = QComboBox()
        
        self.le_obj_radius = QLineEdit("0.05")
        self.le_obj_depth = QLineEdit("0.25")
        self.le_obj_sig = QLineEdit("1e7")
        self.le_obj_eps = QLineEdit("1.0")
        
        for le in [self.le_obj_radius, self.le_obj_depth, self.le_obj_sig, self.le_obj_eps]:
            le.setValidator(self.validator)
            
        obj_layout.addRow("Target Type:", self.cb_obj_type)
        obj_layout.addRow("Host Strata:", self.cb_obj_layer)
        obj_layout.addRow("Radius (m):", self.le_obj_radius)
        obj_layout.addRow("Strata Depth (m):", self.le_obj_depth)
        obj_layout.addRow("Target \u03C3 (S/m):", self.le_obj_sig)
        obj_layout.addRow("Target \u03B5r:", self.le_obj_eps)
        obj_group.setLayout(obj_layout)
        self.scroll_layout.addWidget(obj_group)
        
        # Action Buttons
        act_layout = QVBoxLayout()
        act_layout.setSpacing(15)
        
        self.run_btn = QPushButton("INITIATE RADAR SCAN")
        self.run_btn.setObjectName("primary_btn")
        self.run_btn.setFixedHeight(50)
        self.run_btn.clicked.connect(self.run_simulation)
        
        self.export_btn = QPushButton("EXPORT TELEMETRY")
        self.export_btn.setObjectName("warning_btn")
        self.export_btn.clicked.connect(self.export_results)
        
        act_layout.addWidget(self.run_btn)
        act_layout.addWidget(self.export_btn)
        
        self.scroll_layout.addLayout(act_layout)
        self.scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_content)
        controls_layout = QVBoxLayout()
        controls_layout.addWidget(scroll_area)
        controls_group.setLayout(controls_layout)
        left_layout.addWidget(controls_group)
        self.h_splitter.addWidget(left_panel)

    def add_layer_widget(self, name, thick, eps, mu, sig):
        container = QFrame()
        container.setObjectName("layer_card")
        layout = QFormLayout(container)
        layout.setContentsMargins(5,5,5,5)
        
        le_name = QLineEdit(name)
        le_thick = QLineEdit(thick)
        le_eps = QLineEdit(eps)
        le_sig = QLineEdit(sig)
        le_eps.setValidator(self.validator)
        le_sig.setValidator(self.validator)
        
        idx = len(self.layer_widgets)
        
        title = QLabel(f"\u25B6 STRATA {idx+1}")
        title.setStyleSheet("color: #00FF00; font-weight: bold; border:none;")
        layout.addRow(title)
        layout.addRow("Label:", le_name)
        layout.addRow("Depth (m):", le_thick)
        layout.addRow("\u03B5r:", le_eps)
        layout.addRow("\u03C3:", le_sig)
        
        self.layers_container_layout.addWidget(container)
        self.layer_widgets.append({
            'container': container, 'name': le_name, 'thick': le_thick,
            'eps': le_eps, 'sig': le_sig, 'mu': QLineEdit("1.0") # Fixed mu
        })
        self.update_object_layer_combo()

    def remove_layer(self):
        if len(self.layer_widgets) > 1:
            w = self.layer_widgets.pop()
            # Properly delete the widget from the layout system
            w['container'].setParent(None)
            w['container'].deleteLater()
            self.update_object_layer_combo()

    def update_object_layer_combo(self):
        curr = self.cb_obj_layer.currentIndex()
        self.cb_obj_layer.clear()
        for i, lw in enumerate(self.layer_widgets):
            self.cb_obj_layer.addItem(f"Strata {i+1}: {lw['name'].text()}", i)
        if 0 <= curr < len(self.layer_widgets):
            self.cb_obj_layer.setCurrentIndex(curr)

    # =========================================================================
    # PANEL 2: RADAR DISPLAYS
    # =========================================================================
    def setup_panel_2_displays(self):
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(5,0,5,0)
        
        plots_scroll = QScrollArea()
        plots_scroll.setWidgetResizable(True)
        plots_content = QWidget()
        plots_layout = QVBoxLayout(plots_content)
        
        self.a_scan = AScanRadarPlot()
        self.b_scan = BScanRadarPlot()
        self.c_scan = CScanRadarPlot()
        
        self.a_scan.setMinimumHeight(250)
        self.b_scan.setMinimumHeight(350)
        self.c_scan.setMinimumHeight(350)
        
        plots_layout.addWidget(self.a_scan)
        plots_layout.addWidget(self.b_scan)
        plots_layout.addWidget(self.c_scan)
        plots_layout.addStretch()
        
        plots_scroll.setWidget(plots_content)
        center_layout.addWidget(plots_scroll)
        self.h_splitter.addWidget(center_panel)

    # =========================================================================
    # PANEL 3: ENVIRONMENT
    # =========================================================================
    def setup_panel_3_environment(self):
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5,0,0,0)
        
        env_group = QGroupBox("Geophysical Cross-Section")
        env_layout = QVBoxLayout()
        self.env_view = EnvironmentVisualization()
        env_layout.addWidget(self.env_view)
        env_group.setLayout(env_layout)
        right_layout.addWidget(env_group)
        self.h_splitter.addWidget(right_panel)

    # =========================================================================
    # PANEL 4: ANALYTICS
    # =========================================================================
    def setup_panel_4_analytics(self):
        analytics_panel = QWidget()
        analytics_layout = QHBoxLayout(analytics_panel)
        
        metrics = [
            ("ANOMALY_DEPTH", "lbl_depth", "m"),
            ("REFLECT_TIME", "lbl_time", "ns"),
            ("SNR_ESTIMATE", "lbl_snr", "dB"),
            ("MEDIA_VELOCITY", "lbl_vel", "m/s"),
            ("SIGNAL_AMP", "lbl_amp", "V/m")
        ]
        
        self.metric_labels = {}
        self.metric_widgets = {}
        for title, attr, unit in metrics:
            card = QFrame()
            card.setObjectName("metric_card")
            card_layout = QVBoxLayout(card)
            
            t_lbl = QLabel(f"[{title}]")
            t_lbl.setObjectName("metric_title")
            t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            v_lbl = QLabel(f"-- {unit}")
            v_lbl.setObjectName("metric_value")
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            card_layout.addWidget(t_lbl)
            card_layout.addWidget(v_lbl)
            
            self.metric_widgets[attr] = v_lbl
            self.metric_labels[attr] = unit
            analytics_layout.addWidget(card)
            
        return analytics_panel

    def load_preset(self):
        preset = self.cb_presets.currentText()
        if preset == "Custom Override": return
        
        self.cb_presets.blockSignals(True)
        # Safely remove all layers before populating the preset
        while len(self.layer_widgets) > 0: 
            w = self.layer_widgets.pop()
            w['container'].setParent(None)
            w['container'].deleteLater()
        
        if preset == "Road Infrastructure":
            self.le_frequency.setText("2e9")
            self.add_layer_widget("Atmos (Air)", "inf", "1", "1", "0")
            self.add_layer_widget("Asphalt Binder", "0.08", "4.5", "1", "0.01")
            self.add_layer_widget("Granular Base", "0.20", "6.5", "1", "0.02")
            self.add_layer_widget("Subgrade Soil", "inf", "12", "1", "0.05")
            self.cb_obj_type.setCurrentIndex(2) # Void
            self.le_obj_radius.setText("0.03")
            self.le_obj_depth.setText("0.05") 
            self.cb_obj_layer.setCurrentIndex(1)
            self.le_obj_eps.setText("1.0")
            self.le_obj_sig.setText("0.0")
            
        elif preset == "Utility Detection":
            self.le_frequency.setText("4e8")
            self.add_layer_widget("Atmos (Air)", "inf", "1", "1", "0")
            self.add_layer_widget("Dry Topsoil", "0.50", "4", "1", "0.001")
            self.add_layer_widget("Saturated Clay", "inf", "15", "1", "0.05")
            self.cb_obj_type.setCurrentIndex(1) # Metal Cyl
            self.le_obj_radius.setText("0.1")
            self.le_obj_depth.setText("0.3")
            self.cb_obj_layer.setCurrentIndex(1)
            self.le_obj_sig.setText("1e7")
            
        elif preset == "Landmine Sweeper":
            self.le_frequency.setText("1e9")
            self.add_layer_widget("Atmos (Air)", "inf", "1", "1", "0")
            self.add_layer_widget("Desert Sand", "inf", "3.0", "1", "0.0001")
            self.cb_obj_type.setCurrentIndex(3) # Dielectric
            self.le_obj_radius.setText("0.05")
            self.le_obj_depth.setText("0.1")
            self.cb_obj_layer.setCurrentIndex(1)
            self.le_obj_eps.setText("3.2")
            self.le_obj_sig.setText("0.0")
            
        self.cb_presets.blockSignals(False)
        
        # Only auto-run if the entire UI has finished loading
        if hasattr(self, 'metric_widgets'):
            self.run_simulation()

    def run_simulation(self):
        try:
            # 1. Gather config
            rc = RadarConfig(
                radar_type=self.cb_radar_type.currentText(),
                frequency=float(self.le_frequency.text()),
                bandwidth=float(self.le_bandwidth.text()),
                pulse_width=float(self.le_pulse_width.text()),
                transmit_power=float(self.le_transmit_power.text()),
                antenna_gain=float(self.le_antenna_gain.text()),
                sampling_frequency=float(self.le_sampling_freq.text())
            )
            
            # 2. Gather Layers
            layers = []
            for lw in self.layer_widgets:
                t_str = lw['thick'].text()
                t = np.inf if 'inf' in t_str.lower() else float(t_str)
                layers.append(Layer(lw['name'].text(), t, float(lw['eps'].text()), 1.0, float(lw['sig'].text())))
                
            # 3. Gather Object
            idx = self.cb_obj_layer.currentIndex()
            obj = BuriedObject(
                object_type=self.cb_obj_type.currentText(),
                radius=float(self.le_obj_radius.text()),
                depth=float(self.le_obj_depth.text()),
                sigma=float(self.le_obj_sig.text()),
                epsilon_r=float(self.le_obj_eps.text()),
                mu_r=1.0, layer_index=idx
            )
            
            # 4. Execute
            engine = SimulationEngine(rc, layers, obj)
            res = engine.run_simulation()
            
            # 5. Paint Arrays
            plots = res['plots']
            self.a_scan.plot_data(plots['time_ns'], plots['a_scan'])
            self.b_scan.plot_data(plots['b_scan'], plots['time_ns'])
            self.c_scan.plot_data(plots['c_scan'])
            self.env_view.render_environment(layers, obj)
            
            # 6. Update Analytics
            a = res['analytics']
            o = res['object_results']
            
            self.metric_widgets['lbl_depth'].setText(f"{o.get('absolute_depth', 0):.3f} m")
            self.metric_widgets['lbl_time'].setText(f"{o.get('reflection_time', 0)*1e9:.2f} ns")
            self.metric_widgets['lbl_snr'].setText(f"{a['snr']:.1f} dB")
            self.metric_widgets['lbl_vel'].setText(f"{a['velocity']:.2e} m/s")
            
            amp = o.get('received_amplitude', 0)
            if amp > 0.01:
                self.metric_widgets['lbl_amp'].setText(f"{amp:.2f} (HI)")
                self.metric_widgets['lbl_amp'].setStyleSheet("color: #00FF00; font-weight: bold; font-size: 16px; border:none;")
            else:
                self.metric_widgets['lbl_amp'].setText(f"{amp:.1e} (LO)")
                self.metric_widgets['lbl_amp'].setStyleSheet("color: #FFBF00; font-weight: bold; font-size: 16px; border:none;")
                
            self.current_results = res
            
        except Exception as e:
            print(f"Engine Failure: {e}")
            import traceback
            traceback.print_exc()

    def export_results(self):
        if hasattr(self, 'current_results') and self.current_results:
            import csv
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(self, "Export Telemetry", "", "CSV Files (*.csv)")
            if path:
                try:
                    with open(path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(["Time (ns)", "A-Scan Amplitude"])
                        t_data = self.current_results['plots']['time_ns']
                        a_data = self.current_results['plots']['a_scan']
                        for t, a in zip(t_data, a_data):
                            writer.writerow([t, a])
                except Exception as e:
                    print(f"Export Error: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_CSS)
    window = MissionControlGUI()
    window.show()
    sys.exit(app.exec())
