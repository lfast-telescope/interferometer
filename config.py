INTERFEROMETER_MIRROR_DATA_DIR = "C:/Users/lfast-admin/Documents/mirrors/"
LOCAL_MIRROR_DATA_DIR = "C:/Users/warrenbfoster/OneDrive - University of Arizona/Documents/LFAST/mirrors/"

in_to_m = 25.4e-3  # Inches to meters conversion

# Default values for coated and uncoated mirrors
DEFAULTS = {
    "coated": {
        "OD": 30 * in_to_m,
        "ID": 3 * in_to_m,
    },
    "uncoated": {
        "OD": 32 * in_to_m,
        "ID": 3 * in_to_m,
    }
}

# Store only mirror-specific overrides here
MIRROR_CONFIG = {
    "1": {"coated": True},
    "9": {"coated": False},
    "10": {"coated": True},
    "19": {"coated": False}
    # Add others if needed
}

import os

def get_mirror_params(mirror_num):
    """Generate mirror configuration including OD, ID, and path."""
    coated = MIRROR_CONFIG.get(mirror_num, {}).get("coated", False)
    coating_key = "coated" if coated else "uncoated"
    defaults = DEFAULTS[coating_key]

    base_dir = INTERFEROMETER_MIRROR_DATA_DIR
    if not os.path.exists(base_dir):
        base_dir = LOCAL_MIRROR_DATA_DIR
    base_path = f"{base_dir}M{mirror_num}/"

    return {
        "OD": defaults["OD"],
        "ID": defaults["ID"],
        "base_path": base_path,
        "coated": coated
    }
