# import PVRTexLibPy as pvr
import os, sys
import shutil
import tempfile
from pathlib import Path

from PIL import Image


def import_pvrtexlib():
    submodule = Path("PVRTexToolLib")

    if not submodule.exists():
        raise FileNotFoundError(
            f"Please make sure to pull the PVRTexToolLib submodule: git submodule update --init --recursive")

    if os.name == "nt":
        pvr_root = submodule / "Windows_x86_64"
    elif sys.platform == "darwin":
        raise NotImplementedError("macOS is not currently supported")
    elif sys.platform.startswith("linux"):
        pvr_root = submodule / "Linux_x86_64"

    if not pvr_root.exists():
        raise FileNotFoundError(f"Could not find PVRTexLib binaries for platform: {sys.platform}")


    # ensure DLL is visible to Python
    if os.name == "nt":
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
