import json
import pprint
import shutil
from collections import Counter
from pathlib import Path
from traceback import print_exc

from slashr import SlashR

from glb_compiler import compile_glb
from pod_decoder import read_pod
from pvr_extractor import pvr_to_png

swordigo_dir = Path("swordigo_source_code")
resource_dir = swordigo_dir / "assets" / "resources"

# Output directories
results_dir = Path("Swordigo_Export")
results_dir.mkdir(exist_ok=True)
results_assets_dir = results_dir / "assets"
results_assets_dir.mkdir(exist_ok=True)
results_textures_dir = results_assets_dir / "textures"
results_textures_dir.mkdir(exist_ok=True)
results_combined_dir = results_assets_dir / "combined"
results_combined_dir.mkdir(exist_ok=True)
results_pod_decode_dir = results_assets_dir / "pod_decode"
results_pod_decode_dir.mkdir(exist_ok=True)
results_models_dir = results_assets_dir / "models"
results_models_dir.mkdir(exist_ok=True)
results_animations_dir = results_assets_dir / "animations"
results_animations_dir.mkdir(exist_ok=True)
results_audio_dir = results_assets_dir / "audio"
results_audio_dir.mkdir(exist_ok=True)

FULL_EXPORT = False


def print_file_types():
    files = [p for p in resource_dir.rglob('*') if p.is_file()]
    exts = set((p.suffix.lower() or '<no_extension>') for p in files)
    print("File types:  ", end='')
    print(*exts, sep=", ")


def export_pvr_textures():
    items = list(resource_dir.rglob("*.pvr"))
    with SlashR(False) as sr:
        for i, file in enumerate(items, 1):
            percent = i / len(items) * 100
            sr.print(f"[{percent:.2f}] Exporting texture {i} / {len(items)}: {file.name}")
            output_path = results_textures_dir / ((file.stem.removesuffix('_2x')) + ".png")
            if output_path.exists() and not FULL_EXPORT:
                continue
            try:
                pvr_to_png(str(file), str(output_path))
            except KeyboardInterrupt:
                if output_path.exists():
                    output_path.unlink()
                raise


def copy_audio_files():
    items = list(resource_dir.rglob("*.wav"))
    with SlashR(False) as sr:
        for i, file in enumerate(items, 1):
            percent = i / len(items) * 100
            sr.print(f"[{percent:.2f}] Copying audio {i} / {len(items)}: {file.name}")
            output_path = results_audio_dir / file.name
            if output_path.exists() and not FULL_EXPORT:
                continue
            try:
                shutil.copy2(file, output_path)
            except KeyboardInterrupt:
                if output_path.exists():
                    output_path.unlink()
                raise


def copy_pod_files():
    items = list(resource_dir.rglob("*.pod"))
    with SlashR(False) as sr:
        for i, file in enumerate(items, 1):
            percent = i / len(items) * 100
            sr.print(f"[{percent:.2f}] Copying pod {i} / {len(items)}: {file.name}")
            output_path = results_combined_dir / file.name
            if output_path.exists() and not FULL_EXPORT:
                continue
            try:
                shutil.copy2(file, output_path)
            except KeyboardInterrupt:
                if output_path.exists():
                    output_path.unlink()
                raise


def decode_pod_files(redo: bool = False):
    items = list(resource_dir.rglob("*.pod"))
    with SlashR(False) as sr:
        for i, file in enumerate(items, 1):
            percent = i / len(items) * 100
            sr.print(f"[{percent:.2f}] Decoding pod {i} / {len(items)}: {file.name}")
            output_path = results_pod_decode_dir / f'{file.stem}.json'
            if output_path.exists() and not FULL_EXPORT and not redo:
                continue
            try:
                read_pod(file, output_path)
            except KeyboardInterrupt:
                if output_path.exists():
                    shutil.rmtree(output_path)
                raise


def sort_model_animations(redo: bool = False):
    items = list(results_pod_decode_dir.rglob("*"))
    model_files = set()
    animation_files = set()
    animation_associations = {}
    model_animations = {}
    animations_models = {}
    path_model_files = Path('model_files.json')
    path_animation_files = Path('animation_files.json')
    path_animation_associations = Path('animations_associations.json')

    if path_model_files.exists() and not FULL_EXPORT and not redo:
        with open(path_model_files, 'r') as f:
            model_files = set(json.load(f))

    if path_animation_files.exists() and not FULL_EXPORT and not redo:
        with open(path_animation_files, 'r') as f:
            animation_files = set(json.load(f))

    if path_animation_associations.exists():
        with open(path_animation_associations, 'r') as f:
            animation_associations = json.load(f)
            for entity, data in animation_associations.items():
                for model in data['models']:
                    for animation in data['animations']:
                        animations_models[animation] = animations_models.get(animation, [])
                        if model not in animations_models[animation]:
                            animations_models[animation].append(model)
                        model_animations[model] = model_animations.get(model, [])
                        if animation not in model_animations[model]:
                            model_animations[model].append(animation)

    with SlashR(False) as sr:
        for i, file in enumerate(items, 1):
            percent = i / len(items) * 100
            sr.print(f"[{percent:.2f}] Reading pod information {i} / {len(items)}: {file.name}")
            if (file.stem in model_files) or (file in animation_files):
                continue
            with open(file, 'r') as f:
                obj = json.load(f)
                if obj.get('num_of_meshes', 0) == 0 and obj.get('num_of_frames', 0) > 0:
                    animation_files.add(file.stem)
                else:
                    model_files.add(file.stem)

        with open(path_model_files, 'w') as f:
            json.dump(list(model_files), f)
        with open(path_animation_files, 'w') as f:
            json.dump(list(animation_files), f)

    with SlashR(False) as sr:
        for i, animation in enumerate(animation_files, 1):
            percent = i / len(animation_files) * 100
            sr.print(f"[{percent:.2f}] Processing animations {i} / {len(animation_files)}: {file.name}")
            animation_parent = animation.rsplit('_', 1)[0]
            animation_models = animations_models.get(animation, [])
            if len(animations_models.get(animation, [])) > 0:
                continue  # Already associated
            if animation_parent not in model_files:
                print("Missing parent for animation:", animation, "Checked:", animation_parent)
            elif animation_parent not in animation_models:
                animations_models[animation] = [*animation_models, animation_parent]
                model_animations_list = model_animations.get(animation_parent, [])
                if animation not in model_animations:
                    model_animations[animation_parent] = [*model_animations_list, animation]
            result_path = results_animations_dir / f'{animation}.json'
            if not result_path.exists() or FULL_EXPORT:
                shutil.copy(results_pod_decode_dir / f'{animation}.json', result_path)

    with SlashR(False) as sr:
        for i, model in enumerate(model_files, 1):
            percent = i / len(model_files) * 100
            sr.print(f"[{percent:.2f}] Processing models {i} / {len(model_files)}: {file.name}")
            model_dir = results_models_dir / model
            model_dir.mkdir(exist_ok=True)
            result_path = model_dir / 'model.json'
            if not result_path.exists() or FULL_EXPORT or redo:
                shutil.copy(results_pod_decode_dir / f'{model}.json', result_path)
                with open(model_dir / 'animations.json', 'w') as f:
                    json.dump(model_animations.get(model, []), f)


def copy_textures_to_combined():
    items = list(results_textures_dir.rglob("*.png"))
    with SlashR(False) as sr:
        for i, file in enumerate(items, 1):
            percent = i / len(items) * 100
            sr.print(f"[{percent:.2f}] Copying textures to combined {i} / {len(items)}: {file.name}")
            output_path = results_combined_dir / file.name
            if output_path.exists() and not FULL_EXPORT:
                continue
            try:
                shutil.copy2(file, output_path)
            except KeyboardInterrupt:
                if output_path.exists():
                    output_path.unlink()
                raise


def compile_models():
    items = list(results_models_dir.glob("*"))
    with SlashR(False) as sr:
        for i, model_dir in enumerate(items, 1):
            percent = i / len(items) * 100
            sr.print(f"[{percent:.2f}] Compiling model {i} / {len(items)}: {model_dir.name}")
            model_data = model_dir / 'model.json'
            glb_path = model_dir / f"{model_dir.name}.glb"
            try:
                compile_glb(model_data, glb_path)
            except KeyboardInterrupt:
                raise
            except (ValueError, FileNotFoundError):
                print_exc()


if __name__ == "__main__":
    print("Swordigo Resource Exporter")
    print_file_types()
    copy_audio_files()
    export_pvr_textures()
    copy_textures_to_combined()
    copy_pod_files()
    decode_pod_files(redo=True)
    sort_model_animations(redo=True)

    TEST = 'bat'
    output_path = results_pod_decode_dir / f'{TEST}.json'
    model_path = results_models_dir / TEST
    model_path.mkdir(exist_ok=True)
    read_pod(resource_dir / f'{TEST}.POD', output_path)
    shutil.copy(output_path, model_path / 'model.json')

    compile_models()
