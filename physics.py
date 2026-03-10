import numpy as np

# Physical Constants
C = 3e8  # Speed of light in vacuum (m/s)
EPSILON_0 = 8.85e-12  # Vacuum permittivity (F/m)
MU_0 = 4 * np.pi * 1e-7  # Vacuum permeability (H/m)

def calculate_velocity(epsilon_r: float, mu_r: float) -> float:
    """
    Calculate propagation velocity in a medium.
    v = c / sqrt(epsilon_r * mu_r)
    Returns: velocity in m/s
    """
    return C / np.sqrt(epsilon_r * mu_r)

def calculate_reflection_coefficient(eps1: float, eps2: float) -> float:
    """
    Calculate reflection coefficient between two media.
    R = (sqrt(eps1) - sqrt(eps2)) / (sqrt(eps1) + sqrt(eps2))
    Returns: Reflection coefficient (-1 to 1)
    """
    sqrt_e1 = np.sqrt(eps1)
    sqrt_e2 = np.sqrt(eps2)
    
    if (sqrt_e1 + sqrt_e2) == 0:
        return 0.0
        
    return (sqrt_e1 - sqrt_e2) / (sqrt_e1 + sqrt_e2)

def calculate_travel_time(distance: float, velocity: float) -> float:
    """
    Compute 1-way travel time through a layer.
    t = distance / velocity
    Returns: time in seconds
    """
    if velocity <= 0:
        return 0.0
    return distance / velocity

def calculate_wavelength(frequency: float, velocity: float) -> float:
    """
    Calculate radar wavelength in a medium.
    lambda = v / f
    Returns: wavelength in meters
    """
    if frequency <= 0:
        return 0.0
    return velocity / frequency

def calculate_attenuation(E0: float, alpha: float, z: float) -> float:
    """
    Model signal attenuation.
    E(z) = E0 * exp(-alpha * z)
    Returns: Electric field amplitude at depth z
    """
    return E0 * np.exp(-alpha * z)

def estimate_attenuation_coefficient(conductivity: float, epsilon_r: float, frequency: float) -> float:
    """
    Estimate attenuation coefficient (alpha) for low-loss and high-loss media.
    A simplified approach using conductivity and permittivity.
    alpha = (sigma / 2) * sqrt(mu / epsilon)
    Returns: alpha in Np/m
    """
    epsilon = epsilon_r * EPSILON_0
    mu = MU_0 # assuming non-magnetic for simplicity of alpha
    
    # simplified attenuation constant
    alpha = (conductivity / 2.0) * np.sqrt(mu / epsilon)
    return alpha

def radar_equation(Pt: float, G: float, wavelength: float, radar_cross_section: float, R: float) -> float:
    """
    Implement simplified radar equation.
    Pr = (Pt * G^2 * lambda^2 * sigma) / ((4*pi)^3 * R^4)
    Returns: received power in Watts
    """
    if R <= 0:
        return 0.0
        
    numerator = Pt * (G**2) * (wavelength**2) * radar_cross_section
    denominator = ((4 * np.pi)**3) * (R**4)
    return numerator / denominator
