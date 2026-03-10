import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from physics import (
    calculate_velocity,
    calculate_reflection_coefficient,
    calculate_travel_time,
    calculate_wavelength,
    calculate_attenuation,
    estimate_attenuation_coefficient,
    radar_equation,
    EPSILON_0,
    MU_0,
    C
)

@dataclass
class RadarConfig:
    radar_type: str = "Ground Penetrating Radar"
    frequency: float = 1e9  # Hz
    bandwidth: float = 5e8  # Hz
    pulse_width: float = 1e-9  # seconds
    transmit_power: float = 1.0  # Watts
    antenna_gain: float = 1.0 # Linear gain, not dB
    sampling_frequency: float = 10e9  # Hz
    pulse_repetition_frequency: float = 1e6  # Hz

@dataclass
class Layer:
    name: str = "Air"
    thickness: float = np.inf  # meters
    epsilon_r: float = 1.0
    mu_r: float = 1.0
    sigma: float = 0.0

@dataclass
class BuriedObject:
    object_type: str = "Metal sphere"
    radius: float = 0.05  # meters
    depth: float = 0.25  # meters from the top of its containing layer
    sigma: float = 1e7  # S/m
    epsilon_r: float = 1.0
    mu_r: float = 1.0
    layer_index: int = -1 # Which layer it sits in

class RadarSimulation:
    def __init__(self, radar_config: RadarConfig, layers: List[Layer], buried_object: Optional[BuriedObject] = None):
        self.radar = radar_config
        self.layers = layers
        self.buried_object = buried_object
        self.results: Dict = {}
    
    def run_simulation(self) -> Dict:
        """
        Executes the entire computation pipeline for EM propagation and synthetic scans.
        """
        # 1. Layer-by-layer computation of physics parameters
        layer_results = self._compute_layer_properties()
        
        # 2. Object detection simulation
        object_results = self._compute_object_properties(layer_results)
        
        # 3. Generate synthetic data (A-Scan, B-Scan, C-Scan arrays)
        # Combine reflection events
        events = self._collect_reflection_events(layer_results, object_results)
        
        # Make the time array
        max_time = 0
        if events:
            max_time = max([e['time'] for e in events]) * 1.5 # Add buffer
        if max_time == 0:
            max_time = 20e-9 # Default 20ns
        
        max_time_ns = max_time * 1e9
        
        t = np.linspace(0, max_time_ns, int(max_time * self.radar.sampling_frequency))
        
        a_scan = self._generate_a_scan(t, events)
        b_scan = self._generate_b_scan(t, events, object_results, layer_results)
        c_scan_data = self._generate_c_scan(b_scan)
        
        self.results = {
            "layer_results": layer_results,
            "object_results": object_results,
            "radar_properties": {
                "wavelength": layer_results[0]['wavelength'] if layer_results else 0.0,
                "propagation_speed": layer_results[0]['velocity'] if layer_results else C
            },
            "plots": {
                "time_ns": t,
                "a_scan": a_scan,
                "b_scan": b_scan,
                "c_scan": c_scan_data
            }
        }
        return self.results

    def _compute_layer_properties(self) -> List[Dict]:
        results = []
        cumulative_time = 0.0
        cumulative_depth = 0.0
        
        for i, layer in enumerate(self.layers):
            vel = calculate_velocity(layer.epsilon_r, layer.mu_r)
            wl = calculate_wavelength(self.radar.frequency, vel)
            alpha = estimate_attenuation_coefficient(layer.sigma, layer.epsilon_r, self.radar.frequency)
            impedance = np.sqrt((layer.mu_r * MU_0) / (layer.epsilon_r * EPSILON_0))
            
            # calculate reflection from PREVIOUS layer boundary
            R = 0.0
            if i > 0:
                prev_layer = self.layers[i-1]
                R = calculate_reflection_coefficient(prev_layer.epsilon_r, layer.epsilon_r)
            
            # 1-way travel time through THIS layer
            t_layer = 0.0
            if layer.thickness != np.inf:
                t_layer = calculate_travel_time(layer.thickness, vel)
            
            results.append({
                "velocity": vel,
                "wavelength": wl,
                "alpha": alpha,
                "impedance": impedance,
                "reflection_coefficient": R,
                "layer_travel_time": t_layer,
                "cumulative_time_to_top": cumulative_time,
                "cumulative_depth_to_top": cumulative_depth
            })
            
            # Prepare boundaries for the next layer
            cumulative_time += t_layer
            cumulative_depth += layer.thickness if layer.thickness != np.inf else 0.0
            
        return results

    def _compute_object_properties(self, layer_results: List[Dict]) -> Dict:
        if not self.buried_object or self.buried_object.layer_index < 0 or self.buried_object.layer_index >= len(self.layers):
            return {}
        
        obj = self.buried_object
        layer_idx = obj.layer_index
        host_layer = self.layers[layer_idx]
        host_props = layer_results[layer_idx]
        
        # Depth from surface = top of host layer + depth inside host layer
        absolute_depth = host_props["cumulative_depth_to_top"] + obj.depth
        
        # Reflection time = 2 * (time to top of layer + time inside layer)
        t_inside = calculate_travel_time(obj.depth, host_props["velocity"])
        total_1way_time = host_props["cumulative_time_to_top"] + t_inside
        reflection_time = 2 * total_1way_time
        
        # Reflection coefficient between host layer and object
        R_obj = calculate_reflection_coefficient(host_layer.epsilon_r, obj.epsilon_r)
        
        # Attenuation approximation
        # Cumulative attenuation alpha * z for each layer
        total_attenuation = 0.0
        for i in range(layer_idx): # Attenuation through fully traversed layers
            if self.layers[i].thickness != np.inf:
                total_attenuation += layer_results[i]["alpha"] * self.layers[i].thickness
        # Attenuation through host layer down to the object
        total_attenuation += host_props["alpha"] * obj.depth
        
        # 1-way Attenuated incoming wave amplitude E0 e^(-alpha z)
        # assuming E0 = 1 for relative plotting
        received_amplitude = R_obj * np.exp(-2 * total_attenuation) # 2-way attenuation
        
        # Radar cross section (sigma) approximation for sphere: pi * r^2
        rcs = np.pi * (obj.radius**2)
        pr = radar_equation(self.radar.transmit_power, self.radar.antenna_gain, 
                            host_props["wavelength"], rcs, absolute_depth)
        
        return {
            "absolute_depth": absolute_depth,
            "reflection_time": reflection_time,
            "reflection_coefficient": R_obj,
            "received_power": pr,
            "received_amplitude": received_amplitude,
            "host_velocity": host_props["velocity"]
        }

    def _collect_reflection_events(self, layer_results: List[Dict], object_results: Dict) -> List[Dict]:
        """
        Compiles all distinct reflections (layer boundaries + objects) to construct the radar trace.
        """
        events = [] # Each event is {time (2-way), amplitude}
        
        # Add layer boundaries
        for i, lr in enumerate(layer_results):
            if i == 0:
                continue # No reflection at top of layer 1 (Air)
            
            # The boundary is between layer i-1 and i
            t_1way = lr["cumulative_time_to_top"]
            t_2way = 2 * t_1way
            amplitude = lr["reflection_coefficient"]
            
            # Simplify attenuation for layer boundaries:
            total_attenuation = 0.0
            for j in range(i):
                if self.layers[j].thickness != np.inf:
                    total_attenuation += layer_results[j]["alpha"] * self.layers[j].thickness
            amplitude *= np.exp(-2 * total_attenuation)
            
            events.append({"time": t_2way, "amplitude": amplitude, "type": f"boundary_{i}"})
            
        # Add Object reflection
        if object_results:
            events.append({
                "time": object_results["reflection_time"],
                "amplitude": object_results["received_amplitude"] * 2, # scale object up slightly for visibility vs strong boundaries
                "type": "object"
            })
            
        return events

    def _generate_a_scan(self, t: np.ndarray, events: List[Dict]) -> np.ndarray:
        """
        Creates a 1D time-series synthetic radar pulse.
        """
        scan = np.zeros_like(t)
        f = self.radar.frequency
        t_ns_array = t # which is already in ns
        time_s = t * 1e-9
        
        # The transmitted pulse is simulated as a Ricker wavelet or a few cycles of a sine wave multiplied by a gaussian window
        pulse_width_ns = self.radar.pulse_width * 1e9
        
        for event in events:
            event_time_ns = event['time'] * 1e9
            # Gaussian enveloped sinusoid
            # E(t) = E0 * cos(2*pi*f*(t-t0)) * exp(-((t-t0)/(pw/4))^2)
            pulse = event['amplitude'] * np.cos(2 * np.pi * f * (time_s - event['time']))
            envelope = np.exp(-((t_ns_array - event_time_ns) / (pulse_width_ns/4))**2)
            scan += pulse * envelope
            
        # Add a tiny bit of noise
        noise = np.random.normal(0, 0.01, size=scan.shape)
        return scan + noise
        
    def _generate_b_scan(self, t: np.ndarray, events: List[Dict], object_results: Dict, layer_results: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Produces a 2D matrix (scans x samples).
        Simulates moving the radar across a surface over an object.
        """
        num_traces = 50
        b_scan = np.zeros((len(t), num_traces))
        
        # Center the object at trace 25
        center_trace = num_traces // 2
        
        # Distance steps
        step_size = 0.05 # meters per trace
        
        for i in range(num_traces):
            # Layer boundaries are horizontal lines (same time for all traces)
            trace_events = []
            for ev in events:
                if 'boundary' in ev['type']:
                    trace_events.append(ev)
                    
            if object_results:
                # Calculate hyperbolic travel time
                x_dist = (i - center_trace) * step_size
                z_depth = object_results['absolute_depth']
                velocity = object_results['host_velocity']
                
                # Pythagoras for diagonal distance
                diagonal_dist = np.sqrt(x_dist**2 + z_depth**2)
                
                # This is a simplification treating the whole path as having the object's host velocity, 
                # a true ray-tracing approach is complex, but this gives the requested hyperbola visual.
                t_hyperbola_1way = diagonal_dist / velocity
                t_hyperbola_2way = 2 * t_hyperbola_1way
                
                # We need to add the offset correctly... 
                # actually, simpler approach: base reflection time + difference
                base_time = object_results['reflection_time']
                t_hyperbola_2way = 2 * np.sqrt(x_dist**2 + (velocity * base_time / 2)**2) / velocity
                
                # Beam width attenuation: further away it's weaker
                angular_attenuation = np.exp(-(x_dist)**2 / 0.1) # Arbitrary narrow beam
                amp = object_results['received_amplitude'] * angular_attenuation * 2
                
                trace_events.append({
                    "time": t_hyperbola_2way,
                    "amplitude": amp,
                    "type": "object_hyperbola"
                })
                
            b_scan[:, i] = self._generate_a_scan(t, trace_events)
            
        return b_scan
        
    def _generate_c_scan(self, b_scan: np.ndarray) -> np.ndarray:
        """
        Generates a top-down slice. We take the max amplitude at the object's depth across the B-Scan,
        and extrapolate it into a 2D grid.
        """
        # Take the energy (RMS or max absolute value) along the columns
        energy = np.max(np.abs(b_scan), axis=0)
        
        # Create a simple 2D map (Top View)
        # We model the target as a 2D gaussian spot
        x_grid = np.linspace(-1, 1, len(energy))
        y_grid = np.linspace(-1, 1, len(energy))
        X, Y = np.meshgrid(x_grid, y_grid)
        
        # We center the detection at 0,0
        # Energy profile gives us the X-axis intensity, we copy it to Y for a round object
        c_map = np.outer(energy, energy) 
        
        return c_map

