"""
Interferometer submodule for LFAST mirror control system.

This module provides interferometer hardware control, data acquisition,
and processing capabilities for the LFAST telescope.

Core functionality:
- Hardware control via WebService4D interface
- Zernike coefficient acquisition
- Automated alignment and correction routines
- Data loading and processing utilities
- Visualization and analysis tools
"""

# Import main utility functions for easy access
from .interferometer_utils import (
    take_interferometer_measurements,
    take_interferometer_coefficients,
    correct_tip_tilt_power,
    hold_alignment,
    start_alignment
)

from .data_loader import *
from .surface_processing import *

__all__ = [
    'take_interferometer_measurements',
    'take_interferometer_coefficients', 
    'correct_tip_tilt_power',
    'hold_alignment',
    'start_alignment',
    'run_measurement',
    'take_new_measurement'
]
