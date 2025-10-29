import json
from functools import partial
from pathlib import Path

from pygltflib import Material, PbrMetallicRoughness, TextureInfo


def create_material(mat_data, textures):
    mat = Material(name=mat_data["name"])
    mat.pbrMetallicRoughness = PbrMetallicRoughness()  # initialize!

    diffuse = mat_data.get("diffuse_color", [1, 1, 1])
    opacity = mat_data.get("opacity", 1.0)
    mat.pbrMetallicRoughness.baseColorFactor = [diffuse[0], diffuse[1], diffuse[2], opacity]

    diffuse_index = mat_data.get("diffuse_texture", -1)
    if diffuse_index >= 0:
        mat.pbrMetallicRoughness.baseColorTexture = TextureInfo(index=textures[diffuse_index])

    mat.extras = {
        "ambient_color": mat_data.get("ambient_color", [0, 0, 0]),
        "specular_color": mat_data.get("specular_color", [1, 1, 1]),
        "shininess": mat_data.get("shininess", 0.1)
    }

    return mat


def compile_glb(input_dir: Path):
    with open(input_dir / 'config.json', 'r') as f:
        config = json.load(f)
    glb_path = input_dir.parent / f"{input_dir.name}.glb"

    # Handle the materials
    materials = list(map(partial(create_material, textures=config['textures']), config['materials']))



    raise StopIteration()

