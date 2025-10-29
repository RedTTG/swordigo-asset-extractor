# import PVRTexLibPy as pvr
import os, sys
from pathlib import Path

from PIL import Image

def import_pvrtexlib():
    # try to locate PVRTexTool via common environment variables
    pvr_root = os.environ.get("PVRTEXTOOL_ROOT")
    if pvr_root is None:
        # fallback to typical install path
        pvr_root = Path("C:/Program Files/Imgtec/PowerVR_Tools/PVRTexTool/Library/Windows_x86_64")

    else:
        pvr_root = Path(pvr_root) / "Library/Windows_x86_64"

    if not pvr_root.exists():
        raise FileNotFoundError(f"PVRTexLib path not found: {pvr_root}")

    # ensure DLL is visible to Python
    os.add_dll_directory(str(pvr_root))

    # add path to sys.path to import the .pyd
    sys.path.insert(0, str(pvr_root))

    import PVRTexLibPy
    return PVRTexLibPy

# usage
pvr = import_pvrtexlib()

def pvr_to_png(pvr_file, png_file):
    tex = pvr.PVRTexture(pvr_file)

    tex.Decompress()
    tex.Flip(pvr.Axis.Y)
    tex.SaveSurfaceToImageFile(png_file)