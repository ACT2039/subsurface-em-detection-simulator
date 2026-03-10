import sys
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QFormLayout, QLineEdit, QComboBox, 
                             QPushButton, QLabel, QGroupBox, QScrollArea, QFrame,
                             QSizePolicy, QSplitter)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator, QFont

from simulation import RadarSimulation, RadarConfig, Layer, BuriedObject
from plots import AScanWidget, BScanWidget, CScanWidget, LayerViewWidget

class RadarGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Subsurface EM Detection Simulator")
        self.resize(1200, 800)
        
        self.layer_widgets = []
        
        # Main Widget and Splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Use QSplitter for resizable panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # ---------------------------------------------------------
        # Left Panel (Sidebar - Simulation Controls)
        # ---------------------------------------------------------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        # Add Scroll Area for Inputs
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        
        self.validator = QDoubleValidator() # For numeric inputs
        
        self.setup_radar_config_panel()
        self.setup_layer_config_panel()
        self.setup_object_config_panel()
        
        # Run Button & Extra Controls
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(10)
        
        # Presets Group
        preset_group = QGroupBox("Presets")
        preset_layout = QVBoxLayout()
        self.cb_presets = QComboBox()
        self.cb_presets.addItems(["Custom", "Road Inspection", "Utility Detection", "Landmine Detection"])
        self.cb_presets.currentIndexChanged.connect(self.load_preset)
        preset_layout.addWidget(self.cb_presets)
        preset_group.setLayout(preset_layout)
        controls_layout.addWidget(preset_group)
        
        # Action Buttons
        self.run_btn = QPushButton("Run Simulation")
        self.run_btn.setFixedHeight(45)
        self.run_btn.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #28a745; color: white; border-radius: 4px;")
        self.run_btn.clicked.connect(self.run_simulation_clicked)
        
        self.reset_btn = QPushButton("Reset Parameters")
        self.reset_btn.setStyleSheet("background-color: #6c757d; color: white; border-radius: 4px;")
        self.reset_btn.clicked.connect(self.reset_parameters)
        
        self.export_btn = QPushButton("Export Results (CSV)")
        self.export_btn.setStyleSheet("background-color: #17a2b8; color: white; border-radius: 4px;")
        self.export_btn.clicked.connect(self.export_results)
        
        controls_layout.addWidget(self.run_btn)
        
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(self.export_btn)
        controls_layout.addLayout(btn_row)
        
        self.scroll_layout.addLayout(controls_layout)
        self.scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_content)
        left_layout.addWidget(scroll_area)
        
        # ---------------------------------------------------------
        # Center Panel (Simulation Outputs)
        # ---------------------------------------------------------
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(5, 0, 5, 0)
        
        # Results Summary Panel (Metric Cards)
        self.results_group = QGroupBox("Results Summary")
        self.results_group.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        
        # Use a grid layout for metric cards
        metrics_layout = QHBoxLayout()
        
        # Helper to create styled metric cards
        def create_metric_card(title):
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet("background-color: #F8F9FA; border: 1px solid #DEE2E6; border-radius: 6px; padding: 5px;")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(2)
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("color: #6C757D; font-size: 11px; font-weight: bold; border: none; background: transparent;")
            title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl = QLabel("-")
            val_lbl.setStyleSheet("color: #212529; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(title_lbl)
            card_layout.addWidget(val_lbl)
            return card, val_lbl

        card_depth, self.lbl_object_depth = create_metric_card("Object Depth")
        card_time, self.lbl_reflection_time = create_metric_card("Reflection Time")
        card_wave, self.lbl_radar_wavelength = create_metric_card("Wavelength")
        card_vel, self.lbl_velocity = create_metric_card("Host Velocity")
        card_amp, self.lbl_signal_amplitude = create_metric_card("Signal Amp")

        metrics_layout.addWidget(card_depth)
        metrics_layout.addWidget(card_time)
        metrics_layout.addWidget(card_wave)
        metrics_layout.addWidget(card_vel)
        metrics_layout.addWidget(card_amp)
        
        self.results_group.setLayout(metrics_layout)
        center_layout.addWidget(self.results_group)
        
        # Plots area (Scrollable or Splitter-based)
        plots_scroll = QScrollArea()
        plots_scroll.setWidgetResizable(True)
        plots_scroll.setFrameShape(QFrame.Shape.NoFrame)
        plots_content = QWidget()
        self.plots_layout = QVBoxLayout(plots_content)
        
        self.a_scan_widget = AScanWidget()
        self.b_scan_widget = BScanWidget()
        self.c_scan_widget = CScanWidget()
        
        self.a_scan_widget.setMinimumHeight(300)
        self.b_scan_widget.setMinimumHeight(400)
        self.c_scan_widget.setMinimumHeight(400)
        
        self.plots_layout.addWidget(self.a_scan_widget)
        self.plots_layout.addWidget(self.b_scan_widget)
        self.plots_layout.addWidget(self.c_scan_widget)
        self.plots_layout.addStretch()
        
        plots_scroll.setWidget(plots_content)
        center_layout.addWidget(plots_scroll, stretch=1)
        
        # ---------------------------------------------------------
        # Right Panel (Physical Environment)
        # ---------------------------------------------------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        env_group = QGroupBox("Environment Diagram")
        env_group.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        env_layout = QVBoxLayout(env_group)
        self.layer_view_widget = LayerViewWidget()
        env_layout.addWidget(self.layer_view_widget)
        right_layout.addWidget(env_group, stretch=1)
        
        # Add panels to splitter
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(center_panel)
        self.splitter.addWidget(right_panel)
        
        # Set initial sizes (e.g., 300px, 500px, 400px)
        self.splitter.setSizes([350, 500, 350])
        
        # Initial Plotting State
        self.layer_view_widget.plot_environment([], None)
        self.a_scan_widget.plot_data([], [])
        self.b_scan_widget.plot_data(np.zeros((0,0)), [])
        self.c_scan_widget.plot_data(np.zeros((0,0)))

    def reset_parameters(self):
        self.cb_radar_type.setCurrentIndex(0)
        self.le_frequency.setText("1e9")
        self.le_bandwidth.setText("5e8")
        self.le_pulse_width.setText("1e-9")
        self.le_transmit_power.setText("1.0")
        self.le_antenna_gain.setText("1.0")
        self.le_sampling_freq.setText("10e9")
        self.le_prf.setText("1e6")
        
        # Clear layers except default
        while len(self.layer_widgets) > 1:
            self.remove_layer()
            
        self.layer_widgets[0]['name'].setText("Air")
        self.layer_widgets[0]['thick'].setText("inf")
        self.layer_widgets[0]['eps'].setText("1.0")
        self.layer_widgets[0]['mu'].setText("1.0")
        self.layer_widgets[0]['sig'].setText("0.0")
        
        self.cb_obj_type.setCurrentIndex(0)
        self.le_obj_radius.setText("0.05")
        self.le_obj_depth.setText("0.25")
        self.le_obj_sig.setText("1e7")
        self.le_obj_eps.setText("1.0")
        self.le_obj_mu.setText("1.0")
        
        self.cb_presets.blockSignals(True)
        self.cb_presets.setCurrentIndex(0)
        self.cb_presets.blockSignals(False)

    def load_preset(self):
        preset = self.cb_presets.currentText()
        if preset == "Custom":
            return
            
        # Reset basic view
        while len(self.layer_widgets) > 0:
            self.remove_layer()
            
        if preset == "Road Inspection":
            self.le_frequency.setText("2e9")  # High frequency for shallow resolution
            self.le_bandwidth.setText("2e9")
            self.add_layer_widget("Air", "inf", "1", "1", "0")
            self.add_layer_widget("Asphalt", "0.08", "4.5", "1", "0.01")
            self.add_layer_widget("Base Course", "0.20", "6.5", "1", "0.02")
            self.add_layer_widget("Subgrade", "inf", "12", "1", "0.05")
            self.cb_obj_type.setCurrentIndex(2) # Void
            self.le_obj_radius.setText("0.03")
            self.le_obj_depth.setText("0.05") # Defect in asphalt
            self.cb_obj_layer.setCurrentIndex(1) # In Asphalt
            self.le_obj_eps.setText("1.0")
            self.le_obj_sig.setText("0.0")
            
        elif preset == "Utility Detection":
            self.le_frequency.setText("4e8")  # Mid freq for deeper penetration
            self.le_bandwidth.setText("4e8")
            self.add_layer_widget("Air", "inf", "1", "1", "0")
            self.add_layer_widget("Dry Soil", "0.50", "4", "1", "0.001")
            self.add_layer_widget("Wet Soil", "inf", "15", "1", "0.05")
            self.cb_obj_type.setCurrentIndex(1) # Metal cylinder
            self.le_obj_radius.setText("0.1")
            self.le_obj_depth.setText("0.3")
            self.cb_obj_layer.setCurrentIndex(1) # In Dry Soil
            self.le_obj_sig.setText("1e7")
            
        elif preset == "Landmine Detection":
            self.le_frequency.setText("1e9")
            self.le_bandwidth.setText("1e9")
            self.add_layer_widget("Air", "inf", "1", "1", "0")
            self.add_layer_widget("Sand", "inf", "3.0", "1", "0.0001")
            self.cb_obj_type.setCurrentIndex(3) # Dielectric inclusion
            self.le_obj_radius.setText("0.05")
            self.le_obj_depth.setText("0.1")
            self.cb_obj_layer.setCurrentIndex(1) # In Sand
            self.le_obj_eps.setText("2.8") # TNT-like permittivity
            self.le_obj_sig.setText("0.0")

    def export_results(self):
        if not hasattr(self, 'current_results') or not self.current_results:
            return
            
        import csv
        from PyQt6.QtWidgets import QFileDialog
        
        path, _ = QFileDialog.getSaveFileName(self, "Export Results", "", "CSV Files (*.csv)")
        if path:
            try:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Time (ns)", "A-Scan Amplitude"])
                    
                    time_data = self.current_results['plots']['time_ns']
                    a_scan_data = self.current_results['plots']['a_scan']
                    
                    for t, a in zip(time_data, a_scan_data):
                        writer.writerow([t, a])
            except Exception as e:
                print(f"Export Error: {e}")

    def setup_radar_config_panel(self):
        group = QGroupBox("Radar Configuration")
        layout = QFormLayout()
        
        self.cb_radar_type = QComboBox()
        self.cb_radar_type.addItems(["Ground Penetrating Radar", "FMCW Radar", "Impulse Radar", "Ultra Wideband Radar"])
        self.cb_radar_type.setToolTip("Select the type of radar system to simulate.")
        
        self.le_frequency = QLineEdit("1e9")
        self.le_frequency.setValidator(self.validator)
        self.le_frequency.setToolTip("Center frequency of the radar pulse (Hz)")
        
        self.le_bandwidth = QLineEdit("5e8")
        self.le_bandwidth.setValidator(self.validator)
        
        self.le_pulse_width = QLineEdit("1e-9")
        self.le_pulse_width.setValidator(self.validator)
        
        self.le_transmit_power = QLineEdit("1.0")
        self.le_transmit_power.setValidator(self.validator)
        
        self.le_antenna_gain = QLineEdit("1.0")
        self.le_antenna_gain.setValidator(self.validator)
        
        self.le_sampling_freq = QLineEdit("10e9")
        self.le_sampling_freq.setValidator(self.validator)
        
        self.le_prf = QLineEdit("1e6")
        self.le_prf.setValidator(self.validator)
        
        layout.addRow("Radar Type:", self.cb_radar_type)
        layout.addRow("Frequency (Hz):", self.le_frequency)
        layout.addRow("Bandwidth (Hz):", self.le_bandwidth)
        layout.addRow("Pulse Width (s):", self.le_pulse_width)
        layout.addRow("Transmit Power (W):", self.le_transmit_power)
        layout.addRow("Antenna Gain:", self.le_antenna_gain)
        layout.addRow("Sampling Freq (Hz):", self.le_sampling_freq)
        layout.addRow("Pulse Repetition (Hz):", self.le_prf)
        
        group.setLayout(layout)
        self.scroll_layout.addWidget(group)

    def setup_layer_config_panel(self):
        self.layer_group = QGroupBox("Layer Configuration")
        self.layer_main_layout = QVBoxLayout()
        
        self.layers_container = QWidget()
        self.layers_container_layout = QVBoxLayout(self.layers_container)
        self.layers_container_layout.setContentsMargins(0,0,0,0)
        
        self.layer_main_layout.addWidget(self.layers_container)
        
        btn_layout = QHBoxLayout()
        self.btn_add_layer = QPushButton("Add Layer")
        self.btn_add_layer.clicked.connect(self.add_empty_layer)
        self.btn_remove_layer = QPushButton("Remove Last Layer")
        self.btn_remove_layer.clicked.connect(self.remove_layer)
        btn_layout.addWidget(self.btn_add_layer)
        btn_layout.addWidget(self.btn_remove_layer)
        self.layer_main_layout.addLayout(btn_layout)
        
        self.layer_group.setLayout(self.layer_main_layout)
        self.scroll_layout.addWidget(self.layer_group)
        
        # Load Defaults
        self.add_layer_widget("Air", "inf", "1", "1", "0")
        self.add_layer_widget("Asphalt", "0.05", "4", "1", "0.01")
        self.add_layer_widget("Concrete", "0.30", "6", "1", "0.02")

    def add_empty_layer(self):
        idx = len(self.layer_widgets) + 1
        self.add_layer_widget(f"Layer {idx}", "1.0", "1", "1", "0")
        self.update_object_layer_combo()

    def remove_layer(self):
        if len(self.layer_widgets) > 1: # Don't remove the last one
            widget_data = self.layer_widgets.pop()
            widget_data['container'].setParent(None)
            widget_data['container'].deleteLater()
            self.update_object_layer_combo()

    def add_layer_widget(self, name, thick, eps, mu, sig):
        container = QFrame()
        container.setFrameShape(QFrame.Shape.StyledPanel)
        container.setStyleSheet("background-color: #FAFAFA; border: 1px solid #E0E0E0; border-radius: 4px; margin-bottom: 5px;")
        layout = QFormLayout(container)
        
        le_name = QLineEdit(name)
        le_thick = QLineEdit(thick)
        # We don't put a strict double validator on thickness because it can be 'inf'
        
        le_eps = QLineEdit(eps)
        le_eps.setValidator(self.validator)
        
        le_mu = QLineEdit(mu)
        le_mu.setValidator(self.validator)
        
        le_sig = QLineEdit(sig)
        le_sig.setValidator(self.validator)
        
        idx = len(self.layer_widgets)
        
        title_lbl = QLabel(f"<b>Layer {idx+1}</b>")
        title_lbl.setStyleSheet("border: none; background: transparent;")
        layout.addRow(title_lbl)
        
        layout.addRow("Name:", le_name)
        layout.addRow("Thickness (m, 'inf' for ∞):", le_thick)
        layout.addRow("Rel. Permittivity (εr):", le_eps)
        layout.addRow("Rel. Permeability (μr):", le_mu)
        layout.addRow("Conductivity (σ S/m):", le_sig)
        
        self.layers_container_layout.addWidget(container)
        
        self.layer_widgets.append({
            'container': container,
            'name': le_name,
            'thick': le_thick,
            'eps': le_eps,
            'mu': le_mu,
            'sig': le_sig
        })
        
        if hasattr(self, 'cb_obj_layer'):
            self.update_object_layer_combo()

    def setup_object_config_panel(self):
        group = QGroupBox("Hidden Object Configuration")
        layout = QFormLayout()
        
        self.cb_obj_type = QComboBox()
        self.cb_obj_type.addItems(["Metal sphere", "Metal cylinder", "Void", "Dielectric inclusion"])
        
        self.cb_obj_layer = QComboBox()
        self.update_object_layer_combo()
        self.cb_obj_layer.setCurrentIndex(2) # Default to Concrete
        
        self.le_obj_radius = QLineEdit("0.05")
        self.le_obj_radius.setValidator(self.validator)
        
        self.le_obj_depth = QLineEdit("0.25")
        self.le_obj_depth.setValidator(self.validator)
        
        self.le_obj_sig = QLineEdit("1e7")
        self.le_obj_sig.setValidator(self.validator)
        
        self.le_obj_eps = QLineEdit("1.0")
        self.le_obj_eps.setValidator(self.validator)
        
        self.le_obj_mu = QLineEdit("1.0")
        self.le_obj_mu.setValidator(self.validator)
        
        layout.addRow("Object type:", self.cb_obj_type)
        layout.addRow("Host Layer:", self.cb_obj_layer)
        layout.addRow("Radius (m):", self.le_obj_radius)
        layout.addRow("Depth in layer (m):", self.le_obj_depth)
        layout.addRow("Conductivity (S/m):", self.le_obj_sig)
        layout.addRow("Rel. Permittivity:", self.le_obj_eps)
        layout.addRow("Rel. Permeability:", self.le_obj_mu)
        
        group.setLayout(layout)
        self.scroll_layout.addWidget(group)

    def update_object_layer_combo(self):
        if not hasattr(self, 'cb_obj_layer'):
            return
        curr_idx = self.cb_obj_layer.currentIndex()
        self.cb_obj_layer.clear()
        for i, lw in enumerate(self.layer_widgets):
            name = lw['name'].text()
            self.cb_obj_layer.addItem(f"Layer {i+1}: {name}", i)
            
        if 0 <= curr_idx < len(self.layer_widgets):
            self.cb_obj_layer.setCurrentIndex(curr_idx)
        elif len(self.layer_widgets) > 0:
            self.cb_obj_layer.setCurrentIndex(len(self.layer_widgets)-1)

    def run_simulation_clicked(self):
        # 1. Gather Radar Config
        try:
            radar = RadarConfig(
                radar_type=self.cb_radar_type.currentText(),
                frequency=float(self.le_frequency.text()),
                bandwidth=float(self.le_bandwidth.text()),
                pulse_width=float(self.le_pulse_width.text()),
                transmit_power=float(self.le_transmit_power.text()),
                antenna_gain=float(self.le_antenna_gain.text()),
                sampling_frequency=float(self.le_sampling_freq.text()),
                pulse_repetition_frequency=float(self.le_prf.text())
            )
            
            # 2. Gather Layers
            layers = []
            for lw in self.layer_widgets:
                thick_str = lw['thick'].text()
                thick = np.inf if thick_str.lower() in ['inf', 'infinite'] else float(thick_str)
                
                layer = Layer(
                    name=lw['name'].text(),
                    thickness=thick,
                    epsilon_r=float(lw['eps'].text()),
                    mu_r=float(lw['mu'].text()),
                    sigma=float(lw['sig'].text())
                )
                layers.append(layer)
                
            # 3. Gather Object
            host_layer_idx = self.cb_obj_layer.currentData()
            if host_layer_idx is None:
                host_layer_idx = self.cb_obj_layer.currentIndex()
                
            obj = BuriedObject(
                object_type=self.cb_obj_type.currentText(),
                radius=float(self.le_obj_radius.text()),
                depth=float(self.le_obj_depth.text()),
                sigma=float(self.le_obj_sig.text()),
                epsilon_r=float(self.le_obj_eps.text()),
                mu_r=float(self.le_obj_mu.text()),
                layer_index=host_layer_idx
            )
            
            # 4. Run Physics Simulation
            sim = RadarSimulation(radar, layers, obj)
            results = sim.run_simulation()
            
            # Store results for export
            self.current_results = results
            
            # 5. Output Numerical Results
            self.update_numerical_results(results)
            
            # 6. Output Plots
            plots = results['plots']
            
            # Physical Environment View
            self.layer_view_widget.plot_environment(layers, obj)
            
            # A-Scan
            self.a_scan_widget.plot_data(plots['time_ns'], plots['a_scan'])
            
            # B-Scan
            self.b_scan_widget.plot_data(plots['b_scan'], plots['time_ns'])
            
            # C-Scan
            self.c_scan_widget.plot_data(plots['c_scan'])
            
        except Exception as e:
            print(f"Simulation Error: {str(e)}")
            import traceback
            traceback.print_exc()

    def update_numerical_results(self, res):
        radar_props = res['radar_properties']
        
        self.lbl_radar_wavelength.setText(f"{radar_props['wavelength']:.4f} m")
        
        obj_res = res['object_results']
        if obj_res:
            self.lbl_object_depth.setText(f"{obj_res.get('absolute_depth', 0):.4f} m")
            self.lbl_reflection_time.setText(f"{obj_res.get('reflection_time', 0)*1e9:.2f} ns")
            self.lbl_velocity.setText(f"{obj_res.get('host_velocity', 0):.2e} m/s")
            self.lbl_reflection_coeff.setText(f"{obj_res.get('reflection_coefficient', 0):.2f}")
            
            # Format amplitude text (could be very small)
            amp = obj_res.get('received_amplitude', 0)
            if amp > 1e-4:
                self.lbl_signal_amplitude.setText(f"{amp:.4f} (Strong)")
            else:
                self.lbl_signal_amplitude.setText(f"{amp:.2e} (Weak)")
        else:
            self.lbl_object_depth.setText("N/A")
            self.lbl_reflection_time.setText("N/A")
            self.lbl_velocity.setText("N/A")
            self.lbl_reflection_coeff.setText("N/A")
            self.lbl_signal_amplitude.setText("N/A")
