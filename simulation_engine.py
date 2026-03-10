import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

# Physical Constants
C = 3e8  # Speed of light in vacuum (m/s)
EPSILON_0 = 8.85e-12  # Vacuum permittivity (F/m)
MU_0 = 4 * np.pi * 1e-7  # Vacuum permeability (H/m)

@dataclass
class RadarConfig:
    radar_type: str = "Ground Penetrating Radar"
    frequency: float = 1e9  # Hz
    bandwidth: float = 5e8  # Hz
    pulse_width: float = 1e-9  # seconds
    transmit_power: float = 1.0  # Watts
    antenna_gain: float = 1.0 # Linear gain
    sampling_frequency: float = 10e9  # Hz
    prf: float = 1e6  # Hz
    noise_level: float = 0.02 # Base noise multiplier

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

class SimulationEngine:
    def __init__(self, radar_config: RadarConfig, layers: List[Layer], buried_object: Optional[BuriedObject] = None):
        self.radar = radar_config
        self.layers = layers
        self.buried_object = buried_object
        
    def calculate_velocity(self, epsilon_r: float, mu_r: float) -> float:
        return C / np.sqrt(epsilon_r * mu_r)

    def calculate_reflection_coefficient(self, eps1: float, eps2: float) -> float:
        sqrt_e1 = np.sqrt(eps1)
        sqrt_e2 = np.sqrt(eps2)
        if (sqrt_e1 + sqrt_e2) == 0:
            return 0.0
        return (sqrt_e1 - sqrt_e2) / (sqrt_e1 + sqrt_e2)
        
    def estimate_attenuation(self, conductivity: float, epsilon_r: float, freq: float) -> float:
        epsilon = epsilon_r * EPSILON_0
        mu = MU_0
        return (conductivity / 2.0) * np.sqrt(mu / epsilon)
        
    def run_simulation(self) -> Dict:
        """Core execution pipeline."""
        layer_results = self._compute_layer_properties()
        object_results = self._compute_object_properties(layer_results)
        
        events = self._collect_reflection_events(layer_results, object_results)
        
        # Max time window bounds
        max_time = 0
        if events:
            max_time = max([e['time'] for e in events]) * 1.5 
        if max_time == 0:
            max_time = 20e-9
            
        max_time_ns = max_time * 1e9
        
        # Avoid extremely huge arrays by capping samples
        num_samples = int(max_time * self.radar.sampling_frequency)
        num_samples = min(num_samples, 5000) # Safety cap
        
        t = np.linspace(0, max_time_ns, num_samples)
        
        a_scan = self._generate_a_scan(t, events)
        b_scan = self._generate_b_scan(t, events, object_results, layer_results)
        c_scan_data = self._generate_c_scan(b_scan)
        
        # Analytics calculations
        snr = self._calculate_snr(a_scan, events)
        est_size = self._estimate_size(object_results)
        
        return {
            "layer_results": layer_results,
            "object_results": object_results,
            "analytics": {
                "wavelength": layer_results[0]['wavelength'] if layer_results else 0.0,
                "velocity": layer_results[0]['velocity'] if layer_results else C,
                "snr": snr,
                "est_size": est_size
            },
            "plots": {
                "time_ns": t,
                "a_scan": a_scan,
                "b_scan": b_scan,
                "c_scan": c_scan_data
            }
        }

    def _compute_layer_properties(self) -> List[Dict]:
        results = []
        cumulative_time = 0.0
        cumulative_depth = 0.0
        
        for i, layer in enumerate(self.layers):
            vel = self.calculate_velocity(layer.epsilon_r, layer.mu_r)
            wl = vel / self.radar.frequency if self.radar.frequency > 0 else 0
            alpha = self.estimate_attenuation(layer.sigma, layer.epsilon_r, self.radar.frequency)
            
            R = 0.0
            if i > 0:
                prev_layer = self.layers[i-1]
                R = self.calculate_reflection_coefficient(prev_layer.epsilon_r, layer.epsilon_r)
            
            t_layer = 0.0
            if layer.thickness != np.inf:
                t_layer = layer.thickness / vel
            
            results.append({
                "velocity": vel,
                "wavelength": wl,
                "alpha": alpha,
                "reflection_coefficient": R,
                "cumulative_time": cumulative_time,
                "cumulative_depth": cumulative_depth
            })
            
            cumulative_time += t_layer
            cumulative_depth += layer.thickness if layer.thickness != np.inf else 0.0
            
        return results

    def _compute_object_properties(self, layer_results: List[Dict]) -> Dict:
        if not self.buried_object or self.buried_object.layer_index < 0 or self.buried_object.layer_index >= len(self.layers):
            return {}
            
        obj = self.buried_object
        host_idx = obj.layer_index
        host_layer = self.layers[host_idx]
        host_props = layer_results[host_idx]
        
        abs_depth = host_props["cumulative_depth"] + obj.depth
        t_inside = obj.depth / host_props["velocity"]
        ref_time = 2 * (host_props["cumulative_time"] + t_inside)
        
        R_obj = self.calculate_reflection_coefficient(host_layer.epsilon_r, obj.epsilon_r)
        
        # Approximate 2-way attenuation
        total_att = sum([layer_results[i]["alpha"] * self.layers[i].thickness for i in range(host_idx) if self.layers[i].thickness != np.inf])
        total_att += host_props["alpha"] * obj.depth
        
        recv_amp = R_obj * np.exp(-2 * total_att)
        
        return {
            "absolute_depth": abs_depth,
            "reflection_time": ref_time,
            "reflection_coefficient": R_obj,
            "received_amplitude": recv_amp,
            "host_velocity": host_props["velocity"]
        }

    def _collect_reflection_events(self, layer_results: List[Dict], object_results: Dict) -> List[Dict]:
        events = []
        for i, lr in enumerate(layer_results):
            if i == 0 or lr["reflection_coefficient"] == 0: continue
            
            total_att = sum([layer_results[j]["alpha"] * self.layers[j].thickness for j in range(i) if self.layers[j].thickness != np.inf])
            amp = lr["reflection_coefficient"] * np.exp(-2 * total_att)
            events.append({"time": 2 * lr["cumulative_time"], "amplitude": amp, "type": "layer"})
            
        if object_results:
            events.append({
                "time": object_results["reflection_time"],
                "amplitude": object_results["received_amplitude"] * 2.0, # Enhance object visibility
                "type": "object"
            })
        return events

    def _generate_a_scan(self, t: np.ndarray, events: List[Dict]) -> np.ndarray:
        scan = np.zeros_like(t)
        f = self.radar.frequency
        time_s = t * 1e-9
        pw_ns = self.radar.pulse_width * 1e9
        
        for ev in events:
            # Ricker wavelet approx (Gaussian envelope)
            pulse = ev['amplitude'] * np.cos(2 * np.pi * f * (time_s - ev['time']))
            env = np.exp(-((t - ev['time']*1e9) / (pw_ns/4))**2)
            scan += pulse * env
            
        # Add configurable noise
        noise = np.random.normal(0, self.radar.noise_level * max(1e-6, np.max(np.abs(scan)) if len(scan) > 0 else 0.01), size=scan.shape)
        return scan + noise

    def _generate_b_scan(self, t: np.ndarray, events: List[Dict], object_results: Dict, layer_results: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        num_traces = 60
        b_scan = np.zeros((len(t), num_traces))
        center = num_traces // 2
        step = 0.05
        
        for i in range(num_traces):
            trace_events = [e for e in events if e['type'] == 'layer']
            if object_results:
                x_dist = (i - center) * step
                v = object_results['host_velocity']
                base_t = object_results['reflection_time']
                
                # Hyperbolic time curve
                t_hyp = 2 * np.sqrt(x_dist**2 + (v * base_t / 2)**2) / v
                
                # Beam antenna pattern (angular attenuation)
                ang_att = np.exp(-(x_dist)**2 / 0.15) 
                amp = object_results['received_amplitude'] * ang_att * 2.0
                
                trace_events.append({"time": t_hyp, "amplitude": amp, "type": "object"})
                
            b_scan[:, i] = self._generate_a_scan(t, trace_events)
            
        return b_scan

    def _generate_c_scan(self, b_scan: np.ndarray) -> np.ndarray:
        energy = np.max(np.abs(b_scan), axis=0)
        return np.outer(energy, energy)
        
    def _calculate_snr(self, a_scan: np.ndarray, events: List[Dict]) -> float:
        if len(events) == 0: return 0.0
        signal_power = np.max(np.abs(a_scan))**2
        noise_power = (self.radar.noise_level * signal_power)**2 
        if noise_power == 0: noise_power = 1e-12
        snr = 10 * np.log10(signal_power / noise_power)
        return round(snr, 1)

    def _estimate_size(self, obj_res: Dict) -> float:
        if not obj_res or not self.buried_object: return 0.0
        # Placeholder for analytic size estimation logic
        return self.buried_object.radius * 2
