# subsurface-em-detection-simulator
Scientific simulation tool for modeling subsurface electromagnetic wave propagation and detecting buried objects using radar imaging techniques.

# Subsurface EM Detection Simulator

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Desktop-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Active-success)

An interactive **Ground Penetrating Radar (GPR) simulation platform** for studying **subsurface electromagnetic wave propagation and buried object detection**.

The simulator provides scientific visualization tools such as **A-Scan, B-Scan, and C-Scan radar imaging** used in geophysics, civil engineering inspection, and underground sensing.

---

# Project Overview

Ground Penetrating Radar (GPR) systems emit electromagnetic waves into the ground and analyze reflected signals to detect subsurface objects and material boundaries.

This simulator recreates that process using configurable radar parameters and layered subsurface environments.

The software provides an **interactive graphical interface** to explore radar reflections and visualize detection patterns.

---

# Key Features

- Interactive scientific GUI
- Subsurface layer modeling
- Configurable radar parameters
- Hidden object simulation
- Real-time radar signal visualization
- A-Scan waveform display
- B-Scan radar profile generation
- C-Scan detection heatmap
- Subsurface cross-section visualization
- Scientific parameter configuration

---

# Radar Visualization Modes

## A-Scan (Radar Trace)

Displays radar signal **amplitude vs time**.

Used to analyze reflections from subsurface interfaces.

```
Amplitude
│
│        /\      Object reflection
│       /  \
│______/    \__________
           Time
```

---

## B-Scan (Radar Profile)

2D radar imaging across a scan line.

Buried objects appear as **hyperbolic reflection patterns**.

```
Time ↑

|        /\ 
|       /  \
|      /    \
|_____/______\________ Position →
```

---

## C-Scan (Detection Map)

Top-down visualization of reflection intensity.

Highlights regions with **strong radar returns**.

```
+-------------------+
|       ███         |
|     ███████       |
|       ███         |
+-------------------+
```

---

# Software Architecture

```
                 +----------------------+
                 |       GUI Layer      |
                 |  (PyQt / PySide UI)  |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 |   Simulation Engine  |
                 | EM wave propagation  |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 | Visualization Module |
                 | A-Scan / B-Scan /    |
                 | C-Scan generation    |
                 +----------------------+
```

---

# Project Structure

```
subsurface-em-detection-simulator
│
├── main.py
├── simulation_engine.py
├── visualization.py
├── environment_model.py
│
├── ui
│   ├── main_window.py
│   └── controls_panel.py
│
├── assets
│   └── screenshots
│
├── requirements.txt
└── README.md
```

---

# Installation

Clone the repository:

```bash
git clone https://github.com/ACT2039/subsurface-em-detection-simulator.git
```

Navigate to the project folder:

```bash
cd subsurface-em-detection-simulator
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the simulator:

```bash
python main.py
```

---

# Example Workflow

1️⃣ Configure radar parameters  
2️⃣ Define subsurface layers  
3️⃣ Add hidden object  
4️⃣ Run simulation  
5️⃣ Analyze radar reflections

---

# Applications

This simulator can be used for:

- Ground Penetrating Radar research
- Infrastructure inspection
- Underground utility detection
- Geophysical exploration
- Academic demonstrations
- Electromagnetic wave studies

---

# Future Improvements

- 3D subsurface visualization
- Realistic signal noise modeling
- Machine learning object detection
- GPU accelerated simulation
- Real world GPR dataset integration
- Advanced signal processing filters

---

# Screenshots

Add screenshots here after running the simulator.

Example:

```
/screenshots/gui_dashboard.png
/screenshots/bscan_profile.png
/screenshots/environment_model.png
```

---

# License

This project is licensed under the **MIT License**.

---

# Contributing

Contributions are welcome.

If you would like to improve the simulator:

1. Fork the repository  
2. Create a new branch  
3. Submit a pull request  

---

# Author

Developed as a scientific simulation tool for studying **subsurface electromagnetic detection and radar imaging techniques**.

---

⭐ If you found this project useful, consider giving it a **star** on GitHub.
