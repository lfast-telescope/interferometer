# High-Level Surface Measurement Function

## `measure_and_process_surface()` - Complete Measurement Workflow

A high-level function in `interferometer_utils.py` that encapsulates the entire workflow from lines 28-49 of `main.py`.

### What It Does

1. **Setup**: Configures paths and parameters based on mirror number
2. **Measure** (optional): Takes new interferometer measurement with alignment
3. **Load**: Loads surface data from interferometer
4. **Process**: Applies multiple Zernike correction levels
5. **Visualize** (optional): Generates PSF and cross-section plots
6. **Return**: Comprehensive results dictionary

---

## Basic Usage

### Simple Measurement

```python
from interferometer_utils import measure_and_process_surface

# Take new measurement and process with defaults
result = measure_and_process_surface(mirror_num="10", take_new=True)

# Access results
raw_surface = result['surface']
trefoil_corrected = result['processed_surfaces']['trefoil corrected']
rms = np.nanstd(trefoil_corrected)

print(f"Trefoil-corrected RMS: {rms:.3f} μm")
```

### Load Existing Measurement

```python
# Load most recent measurement without taking new data
result = measure_and_process_surface(
    mirror_num="10", 
    take_new=False,
    save_date=-1,        # Most recent date
    save_instance=-1     # Most recent instance
)
```

### Custom Correction Modes

```python
# Define custom Zernike modes to remove
custom_modes = [
    [0, 1, 2],           # Just piston, tip, tilt
    [0, 1, 2, 4],        # Add defocus
    [0, 1, 2, 4, 5, 6]   # Add astigmatism
]

result = measure_and_process_surface(
    mirror_num="10",
    take_new=False,
    correction_modes=custom_modes,
    plot_results=True
)

# Results will have keys: 'mode_set_0', 'mode_set_1', 'mode_set_2'
for name, surface in result['processed_surfaces'].items():
    print(f"{name}: RMS = {np.nanstd(surface):.4f} μm")
```

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mirror_num` | str/int | `"10"` | Mirror identifier |
| `take_new` | bool | `True` | Take new measurement vs load existing |
| `save_date` | int | `-1` | Date folder index (-1 = most recent) |
| `save_instance` | int | `-1` | Instance index within date (-1 = most recent) |
| `new_folder` | str/None | `None` | Custom folder name (None = timestamp) |
| `correction_modes` | list/None | `None` | Custom Zernike modes (None = defaults) |
| `plot_results` | bool | `True` | Generate diagnostic plots |
| `number_alignment_iterations` | int | `7` | Alignment iterations for new measurements |

---

## Return Value

Dictionary with keys:

| Key | Type | Description |
|-----|------|-------------|
| `'surface'` | ndarray | Raw loaded surface (500×500) |
| `'processed_surfaces'` | dict | Processed surfaces for each correction level |
| `'config'` | dict | Mirror configuration parameters |
| `'save_path'` | str | Path where data is stored |
| `'Z'` | ndarray | Zernike matrix (44 modes) |
| `'clear_outer'` | float | Outer clear aperture (mm) |
| `'clear_inner'` | float | Inner clear aperture (mm) |
| `'mirror_num'` | str | Mirror number |

---

## Default Correction Modes

When `correction_modes=None`, three standard correction levels are applied:

### 1. **Uncorrected** - `[0, 1, 2, 4]`
Removes only:
- Piston (Z0)
- Tip/Tilt (Z1, Z2)
- Defocus (Z4)

Shows surface with all higher-order aberrations intact.

### 2. **Spherical Corrected** - `[0, 1, 2, 4, 12, 24, 40]`
Adds removal of:
- Primary spherical (Z12)
- Secondary spherical (Z24)
- Tertiary spherical (Z40)

Shows surface with spherical aberration compensated.

### 3. **Trefoil Corrected** - `[0, 1, 2, 3, 4, 5, 6, 9, 10, 14, 15, 20, 21, 27, 28, 35, 36, 44]`
Comprehensive mode removal including:
- Low-order modes (0-6)
- Trefoil modes (9, 10)
- Coma modes (14, 15)
- Additional higher-order modes

Shows surface with most common fabrication errors removed.

---

## Integration with Existing Code

### Before (main.py lines 28-49):

```python
def main(mirror_num="10", take_new=True, save_date=-1, save_instance=-1, new_folder=None):
    if smc100 is False and take_new:
        print("Newport SMC100 library not found. Cannot take new measurements.")
        return
    config = get_mirror_params(mirror_num)
    OD, ID = config["OD"], config["ID"]
    clear_outer, clear_inner = 0.5 * OD, 0.5 * ID

    mirror_path = config["base_path"]
    os.makedirs(mirror_path, exist_ok=True)

    save_subfolder = setup_paths(mirror_path, take_new, save_date, save_instance, new_folder)
    Z = General_zernike_matrix(44, int(clear_outer * 1e6), int(clear_inner * 1e6))

    if True:
        if take_new:
            take_new_measurement(save_subfolder, number_alignment_iterations=7)
        if True:
            surface = load_single_surface(save_subfolder, clear_outer=clear_outer, clear_inner=clear_inner, Z=Z)
            updated_surface = surface.copy()

            coefs = [[0,1,2,4], [0,1,2,4,12,24,40], [0, 1, 2, 3, 4, 5, 6, 9, 10, 14, 15, 20, 21, 27, 28, 35, 36, 44]]
            coef_names = ['uncorrected', 'sph corrected', 'trefoil corrected']
            coef_dict = dict(zip([tuple(c) for c in coefs],coef_names))

            for coefs_tuple, name in coef_dict.items():
                remove_coef = list(coefs_tuple)
                updated_surface = prepare_surface(surface, Z, remove_coef, config, crop_ca = True)
                plot_psf_from_surface(updated_surface, Z, f"N{mirror_num}" +' (' + name + ')', config)
                plot_mirror_cs(mirror_num, [updated_surface], [datetime.datetime.now().strftime('%Y%m%d')])
```

### After (simplified):

```python
from interferometer_utils import measure_and_process_surface

def main(mirror_num="10", take_new=True, save_date=-1, save_instance=-1, new_folder=None):
    # All the setup, measurement, processing, and plotting in one call
    result = measure_and_process_surface(
        mirror_num=mirror_num,
        take_new=take_new,
        save_date=save_date,
        save_instance=save_instance,
        new_folder=new_folder,
        plot_results=True
    )
    
    # Access results as needed
    return result
```

---

## Use Cases

### 1. Quick Quality Check

```python
# Measure and immediately see diagnostics
result = measure_and_process_surface("10", take_new=True)
# Plots automatically generated
```

### 2. Batch Processing

```python
# Process multiple mirrors
mirrors = ["10", "11", "12"]
results = {}

for mirror in mirrors:
    results[mirror] = measure_and_process_surface(
        mirror_num=mirror,
        take_new=False,
        plot_results=False  # Skip plots for batch
    )

# Compare RMS across mirrors
for mirror, result in results.items():
    rms = np.nanstd(result['processed_surfaces']['trefoil corrected'])
    print(f"Mirror {mirror}: {rms:.4f} μm")
```

### 3. Analysis Pipeline

```python
# Get surface for further analysis
result = measure_and_process_surface(
    mirror_num="10",
    take_new=False,
    plot_results=False
)

surface = result['processed_surfaces']['trefoil corrected']
Z = result['Z']

# Perform custom analysis
from shared.zernike_utils import get_M_and_C
M, C = get_M_and_C(surface, Z)

# Analyze specific modes
print(f"Coma X (Z7): {C[7]:.4f} μm")
print(f"Coma Y (Z8): {C[8]:.4f} μm")
```

### 4. TEC Correction Integration

```python
# Measure surface and prepare for TEC correction
result = measure_and_process_surface("10", take_new=True, plot_results=False)

# Get surface with basic corrections applied
target_surface = result['processed_surfaces']['uncorrected']

# Use with TEC influence library
from tec.define_tec_influence import TECInfluenceLibrary

lib = TECInfluenceLibrary()
lib.load('tec_influence_library.pkl')

correction = lib.compute_optimal_tec_commands(
    target_surface,
    mode='heating',
    method='svd'
)

print(f"Predicted RMS after TEC correction: {correction['residual_rms']:.4f} μm")
```

---

## Advantages Over Original Code

1. **Simplicity**: One function call vs 20+ lines
2. **Reusability**: Can be called from any script
3. **Consistency**: Same processing pipeline everywhere
4. **Maintainability**: Fix bugs in one place
5. **Documentation**: Clear parameter descriptions
6. **Flexibility**: Easy to customize while keeping defaults
7. **Return Values**: Access all intermediate results
8. **Error Handling**: Centralized (can be improved)

---

## Notes

- Function requires `prepare_surface`, `load_single_surface`, `take_new_measurement` from interferometer module
- Plots are displayed but not automatically saved
- For TEC training workflows, use `plot_results=False` to avoid blocking
- Compatible with existing `main.py` logic - can be drop-in replacement
- Does **not** check for Newport SMC100 library - caller must handle this

---

## Future Enhancements

Potential additions:
- Save plots to file option
- Return Zernike coefficients for each correction level
- Automatic comparison with previous measurements
- Email notifications for completed measurements
- Integration with database logging
- Configurable plot types
- Support for saving intermediate processing steps

---

## See Also

- `main.py` - Original implementation
- `interferometer_utils.py` - Full implementation
- `surface_processing.py` - Surface preparation functions
- `tec/zernike_training.py` - Iterative TEC correction
