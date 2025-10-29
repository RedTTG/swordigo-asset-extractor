import io
import json
import struct
from copy import deepcopy
from pathlib import Path
from pprint import pprint

from colorama import Fore, init

from pod_data_handlers import DATA_HANDLERS, DATA_HANDLERS_SIZE

init()

COLOR_BLOCKS = {
    2000: 'clear_color',
    2001: 'ambient_color'
}

NUM_OF_BLOCKS = {
    2002: 'num_of_cameras',
    2003: 'num_of_lights',
    2004: 'num_of_meshes',
    2005: 'num_of_nodes',
    2006: 'num_of_mesh_nodes',
    2007: 'num_of_textures',
    2008: 'num_of_materials',
    2009: 'num_of_frames',
}

MATERIAL_TEXTURE_INDEXES = {
    3001: 'diffuse_texture',
    3009: 'ambient_texture',
    3010: 'specular_color_texture',
    3011: 'specular_level_texture',
    3012: 'bump_map_texture',
    3013: 'emissive_texture',
    3014: 'glossiness_texture',
    3015: 'opacity_texture',
    3016: 'reflection_texture',
    3017: 'refraction_texture',
}

BLENDING_TYPES = {
    0: 'ZERO',
    1: 'ONE',
    2: 'BLEND_FACTOR',
    3: 'ONE_MINUS_BLEND_FACTOR',
    0x8001: 'CONSTANT_COLOUR',
    0x8002: 'ONE_MINUS_CONSTANT_COLOUR',
    0x8003: 'CONSTANT_ALPHA',
    0x8004: 'ONE_MINUS_CONSTANT_ALPHA',
    0x8006: 'ADD',
    0x8007: 'MIN',
    0x8008: 'MAX',
    0x800a: 'SUBTRACT',
    0x800b: 'REVERSE_SUBTRACT'
}

MESH_NUM_OF_BLOCKS = {
    6000: 'num_of_vertices',
    6001: 'num_of_faces',
    6002: 'num_of_uvw_channels',
    6005: 'num_of_strips',
    6018: 'max_num_of_bones_per_batch',
    6019: 'num_of_bones_batches',
}

BLOCK_NAMES = {
    1000: 'Version',
    1002: 'Export Options',
    1003: 'History',
    2000: 'Scene Clear Color',
    2001: 'Scene Ambient Color',
    2002: 'Num of Cameras',
    2003: 'Num of Lights',
    2004: 'Num of Meshes',
    2005: 'Num of Nodes',
    2006: 'Num of Mesh Nodes',
    2007: 'Num of textures',
    2008: 'Num of materials',
    2009: 'Num of frames',
    2010: 'Camera',
    2011: 'Light',
    2012: 'Mesh',
    2013: 'Node',
    2014: 'Texture',
    2015: 'Material',
    2016: 'Scene Flags',
    2017: 'FPS',
    3000: 'Material Name',
    3002: 'Material Opacity',
    3003: 'Material Ambient Color',
    3004: 'Material Diffuse Color',
    3005: 'Material Specular Color',
    3006: 'Material Shininess',
    3001: 'Material Diffuse Texture',
    3009: 'Material Ambient Texture',
    3010: 'Material Specular Color Texture',
    3011: 'Material Specular Level Texture',
    3012: 'Material Bump Map Texture',
    3013: 'Material Emissive Texture',
    3014: 'Material Glossiness Texture',
    3015: 'Material Opacity Texture',
    3016: 'Material Reflection Texture',
    3017: 'Material Refraction Texture',
    3018: 'Material Blending RGB Source',
    3019: 'Material Blending Alpha Source',
    3020: 'Material Blending RGB Destination',
    3021: 'Material Blending Alpha Destination',
    3022: 'Material Blending Operation',
    3023: 'Material Blending Alpha Operation',
    3024: 'Material Blending RGBA Color',
    3025: 'Material Blending Factor Array',
    3026: 'Material Flags',
    4000: 'Texture Name',
    5000: 'Node Index',
    5001: 'Node Name',
    5002: 'Node Material Index',
    5003: 'Node Parent Index',
    5007: 'Node Animation Position',
    5008: 'Node Animation Rotation',
    5009: 'Node Info UNKNOWN',
    5012: 'Node Animation Flags',
    6000: 'Mesh Num Of Vertices',
    6001: 'Mesh Num Of Faces',
    6002: 'Mesh Num Of UVW Channels',
    6005: 'Mesh Num Of Strips',
    6014: 'Mesh Interleaved Data',
    6015: 'Mesh Bone Batch Index List',
    6016: 'Mesh Number of Bones per Batch',
    6017: 'Mesh Bone Offset per Batch',
    6018: 'Mesh Max Num Of Bones Per Batch',
    6019: 'Mesh Num Of bones_batches',
    6020: 'Mesh Unpack Matrix',
    9000: 'Data Type',
    9001: 'Data Number of components',
    9002: 'Data Stride',
    9003: 'Data Array or Pointer',
}

TAG_START = b'\x00\x00'
TAG_END = b'\x00\x80'
DEBUG = False


def read_rgb(data) -> tuple[float, float, float]:
    return struct.unpack('<3f', data)


def read_rgba(data) -> tuple[float, float, float, float]:
    return struct.unpack('<4f', data)


def read_u32bit_int(data) -> int:
    (value,) = struct.unpack('<I', data)
    return value


def read_s32bit_int(data) -> int:
    (value,) = struct.unpack('<i', data)
    return value

def read_u32bit_int_array(data) -> list[int]:
    count = len(data) // 4
    return list(struct.unpack(f'<{count}I', data))

def read_float(data) -> float:
    (value,) = struct.unpack('<f', data)
    return value


def read_float_array(data) -> list[float]:
    count = len(data) // 4
    return list(struct.unpack(f'<{count}f', data))

def read_block(stream):
    header = stream.read(8)
    if len(header) < 8:
        raise EOFError
    block_type = int.from_bytes(header[:2], 'little')
    tag = header[2:4]
    size = int.from_bytes(header[4:8], 'little')
    if size > 0:
        data = stream.read(size)
    else:
        data = b''
    return block_type, tag, data


def handle_camera_data(block_type: int, data: bytes, camera_config: dict):
    # I implemented this as an example, please test if it comes to use
    print(f'  Handling camera block type: {block_type}, size: {len(data)}')
    if block_type == 8000:  # FOV
        camera_config['fov'] = read_float(data)
    elif block_type == 8001:  # FOV
        camera_config['target_index'] = read_u32bit_int(data)
    elif block_type == 8002:  # Far plane
        camera_config['far_plane'] = read_float(data)
    elif block_type == 8003:  # Near plane
        camera_config['near_plane'] = read_float(data)
    elif block_type == 8004:  # FOV Animation
        camera_config['fov_animation'] = read_float_array(data)
    else:
        raise ValueError(f'Unknown camera block type: {block_type}, size: {len(data)}')


def handle_data(block_type: int, data: bytes, config: dict, info: dict):
    if DEBUG:
        print(f'Handling block type: {BLOCK_NAMES.get(block_type,block_type)}, size: {len(data)}')
    if block_type == 1000:  # Version
        config['version'] = str(data[:-1], 'utf-8')
    elif block_type == 1002:  # Export Options
        lines = str(data[:-1], 'utf-8').strip().split('\n')
        config['export_options'] = {
            s[0]: float(s[1])
            for s in (line.split('=') for line in lines)
        }
    elif block_type == 1003:  # History
        config['history'] = str(data[:-1], 'utf-8').strip()
    elif block_type in COLOR_BLOCKS:  # Scene Colors
        config[COLOR_BLOCKS[block_type]] = read_rgb(data)
    elif block_type in NUM_OF_BLOCKS:  # Number of Cameras/Lights so on
        config[NUM_OF_BLOCKS[block_type]] = read_u32bit_int(data)
    elif block_type == 2010:  # Camera
        # The data contains individual camera blocks
        stream = memoryview(data)
        config['cameras'] = config.get('cameras', [])
        camera_config = {}
        config['cameras'].append(camera_config)
        while len(stream) > 0:
            block_type, tag, data = read_block(stream)
            if tag == TAG_START:  # START TAG
                handle_camera_data(block_type, data, camera_config)
            elif tag == TAG_END:  # END TAG
                pass
            else:
                raise ValueError(f'Tag error in camera block: {tag}')
    elif block_type == 2011:  # Light
        raise NotImplementedError("Light block not implemented yet")
    elif block_type == 2012:  # Mesh
        raise NotImplementedError("Mesh block not implemented yet")
    elif block_type == 2013:  # Node
        raise NotImplementedError("Node block not implemented yet")
    elif block_type == 2014:  # Texture
        # Contains a single block with the texture name
        config['textures'] = config.get('textures', [])
        stream = memoryview(data)
        _, _, raw_tex_name = read_block(stream)  # Read the texture name block
        tex_name = str(raw_tex_name[:-1], 'utf-8').strip()  # Remove null terminator
        config['textures'].append(tex_name)
    elif block_type == 2015:  # Material
        raise NotImplementedError("Material block not implemented yet")
    elif block_type == 2016:  # Scene Flags
        config['scene_flags'] = read_u32bit_int(data)
    elif block_type == 2017:  # FPS
        config['fps'] = read_u32bit_int(data)
    # DEFAULT MATERIAL BLOCKS
    elif block_type == 3000:  # Material Name
        if config['default_material']:
            config['materials'].append(config['default_material'])
            config['default_material'] = {}
        config['default_material']['name'] = str(data[:-1], 'utf-8').strip()
    elif block_type == 3002:  # Material Opacity
        config['default_material']['opacity'] = read_float(data)
    elif block_type == 3003:  # Material Ambient Color
        config['default_material']['ambient_color'] = read_rgb(data)
    elif block_type == 3004:  # Material Diffuse Color
        config['default_material']['diffuse_color'] = read_rgb(data)
    elif block_type == 3005:  # Material Specular Color
        config['default_material']['specular_color'] = read_rgb(data)
    elif block_type == 3006:  # Material Shininess
        config['default_material']['shininess'] = read_float(data)
    elif block_type in MATERIAL_TEXTURE_INDEXES:  # Material Texture Indexes
        config['default_material'][MATERIAL_TEXTURE_INDEXES[block_type]] = read_s32bit_int(data)
    elif block_type == 3018:  # Material Blending RGB Source
        config['default_material']['blending_rgb_src'] = read_u32bit_int(data)
    elif block_type == 3019:  # Material Blending Alpha Source
        config['default_material']['blending_alpha_src'] = read_u32bit_int(data)
    elif block_type == 3020:  # Material Blending RGB Destination
        config['default_material']['blending_rgb_dest'] = read_u32bit_int(data)
    elif block_type == 3021:  # Material Blending Alpha Destination
        config['default_material']['blending_alpha_dest'] = read_u32bit_int(data)
    elif block_type == 3022:  # Material Blending Operation
        _ = config['default_material']['_blending_oper'] = read_u32bit_int(data)
        config['default_material']['blending_oper'] = BLENDING_TYPES.get(_, f'Unknown({_})')
    elif block_type == 3023:  # Material Blending ALPHA Operation
        _ = config['default_material']['_blending_alpha_oper'] = read_u32bit_int(data)
        config['default_material']['blending_alpha_oper'] = BLENDING_TYPES.get(_, f'Unknown({_})')
    elif block_type == 3024:  # Material Blending RGBA Color
        config['default_material']['blending_rgba_color'] = read_rgba(data)
    elif block_type == 3025:  # Material Blending Factor Array
        config['default_material']['blending_factors'] = read_float_array(data)
    elif block_type == 3026:  # Material Flags
        config['material_flags'] = read_u32bit_int(data)
    # TEXTURE BLOCKS
    elif block_type == 4000:  # Texture Name
        config['textures'].append(str(data[:-1], 'utf-8').strip())
    # NODE BLOCKS
    elif block_type == 5000:  # Node Index
        index = str(read_s32bit_int(data))
        if index == '-1' and index in config['nodes']:
            info['unindexed_node'] += 1
            index = str(info['unindexed_node'])
            config['nodes'][index] = {'type': 'unindexed'}
            info['last_node_index'] = index
            return
        elif index == '-1':
            config['nodes'][index] = {'type': 'parent'}
            info['last_node_index'] = index
            return
        elif existing_node := config['nodes'].get(index):
            i = 1
            while (dup_node_index := f'{index}_dup{i}') in config['nodes']:
                i += 1
            config['nodes'][dup_node_index] = deepcopy(existing_node)
            info['last_node_index'] = dup_node_index
            return
        else:
            info['last_node_index'] = index
        if len(info['node_temp']) < 1:
            config['nodes'][index] = {'type': 'missing node data'}
            raise ValueError('Node index block found but no temp node data is available.')
        node_data = info['node_temp'].pop(0)
        if not node_data:
            config['nodes'][index] = {'type': 'missing node data'}
            raise ValueError('Node index block found but no temp node data is available.')

        node_type = node_data.get('type', 'unknown')

        if node_type == 'mesh':
            config['nodes'][index] = node_data
        else:
            config['nodes'][index] = {'type': 'unknown'}
            print(f'{Fore.RED} Warning: Node index block found but no open is available.{Fore.RESET}')
    elif block_type == 5001:  # Node name
        name = str(data[:-1], 'utf-8').strip()
        node = config['nodes'].get(info['last_node_index'], {})
        node['name'] = name
        # if info['last_node_index'] != '-1':
        #     if node.get('type', '') == 'mesh':
        #         node['data'] = {}

    elif block_type == 5002:  # Node Material Index
        if info['last_node_index'] != '-1':
            config['nodes'][info['last_node_index']]['material_index'] = read_s32bit_int(data)
    elif block_type == 5003:  # Node Parent Index
        if info['last_node_index'] != '-1':
            config['nodes'][info['last_node_index']]['parent_index'] = read_s32bit_int(data)
    elif block_type == 5007:  # Node Animation Position
        if info['last_node_index'] != '-1':
            config['nodes'][info['last_node_index']]['animation_position'] = read_float_array(data)
    elif block_type == 5008:  # Node Animation Rotation
        if info['last_node_index'] != '-1':
            config['nodes'][info['last_node_index']]['animation_rotation'] = read_float_array(data)
    elif block_type == 5009: # TODO: Figure out what 5009 block type is
        if info['last_node_index'] != '-1':
            config['nodes'][info['last_node_index']]['unknown_5009'] = read_float_array(data)
    elif block_type == 5012:  # Node Animation Flags
        if info['last_node_index'] != '-1':
            _ = config['nodes'][info['last_node_index']]['_animation_flags'] = read_u32bit_int(data)
            config['nodes'][info['last_node_index']]['animation_flags'] = {
                0x00: 'NONE',
                0x01: 'POS',
                0x02: 'ROT',
                0x04: 'SCALE',
                0x08: 'MATRIX',
            }.get(_, f'Unknown({_})')
    # DEFAULT MESH BLOCKS
    elif block_type in MESH_NUM_OF_BLOCKS:  # Mesh num of blocks
        if len(info['node_temp']) == 0 or info['node_temp'][-1] and info['node_temp'][-1].get('type', '') != 'mesh':
            info['node_temp'].append({})
        info['node_temp'][-1]['type'] = 'mesh'
        info['node_temp'][-1][MESH_NUM_OF_BLOCKS[block_type]] = read_u32bit_int(data)
    elif block_type == 6014:  # Interleaved Data
        info['interleaved_data'] = data
    elif block_type == 6015: # Mesh Bone Batch Index List
        info['node_temp'][-1]['bone_batch_indexes'] = read_u32bit_int_array(data)
    elif block_type == 6016: # Mesh Number of Bones per Batch
        info['node_temp'][-1]['num_of_bones_per_batch'] = read_u32bit_int_array(data)
    elif block_type == 6017: # Mesh Bone Offset per Batch
        info['node_temp'][-1]['bone_offset_per_batch'] = read_u32bit_int_array(data)
    elif block_type == 6020:  # Mesh unpack matrix
        info['node_temp'][-1]['unpack_matrix'] = read_float_array(data)
        info['node_temp'].append({})
    elif block_type == 9000:  # Data type
        info['data_type'] = read_u32bit_int(data)
        info['temp_datas'].append(None)
    elif block_type == 9001:  # Num Components
        info['num_components'] = read_u32bit_int(data)
    elif block_type == 9002:  # Stride
        info['stride'] = read_u32bit_int(data)
    elif block_type == 9003:  # Data Array or pointer
        final = []
        handler = DATA_HANDLERS.get(info['data_type'])
        if len(data) == 4:
            # Pointer
            pointer = read_u32bit_int(data)
            if DEBUG:
                print(
                    f"Read interleaved data, type: {info['data_type']}, components: {info['num_components']}, stride: {info['stride']}, POINTER: {pointer}")
            info['temp_datas'][-1] = []
            if not info.get('interleaved_data'):
                raise ValueError("Interleaved data not found.")
            stream = io.BytesIO(info['interleaved_data'])
            stream.seek(pointer)
            stream_size = lambda: len(info['interleaved_data']) - stream.tell()
        else:
            if DEBUG:
                print(
                    f"Read data, type: {info['data_type']}, components: {info['num_components']}, stride: {info['stride']}, size: {len(data)}")
            stream = io.BytesIO(data)
            stream_size = lambda: len(data) - stream.tell()
        if not handler:
            raise ValueError(f'No data handler for data type: {info["data_type"]}')

        if info['num_components'] == 0 or info['stride'] == 0:
            if DEBUG:
                print(" Data was empty due to zero components or stride.")
            info['temp_datas'][-1] = None
            return

        while stream_size() >= DATA_HANDLERS_SIZE[info['data_type']]*info['num_components']:
            before = stream_size()
            final.append(handler(stream, info['num_components']))
            if stream_size() == before and info['num_components'] > 0:
                raise RuntimeError("Data handler did not consume any data, infinite loop detected.")
            elif before - info['stride'] != stream_size():
                # Ensure we move to the next stride
                amount_to_seek = stream_size() - (before - info['stride'])
                stream.seek(amount_to_seek, io.SEEK_CUR)
        info['temp_datas'][-1] = final
        if DEBUG:
            print(" Finished reading data array, total items:", len(final))
    else:
        raise ValueError(f'Unknown block type: {block_type}, size: {len(data)}')


def read_pod_data(file: Path, config: dict, info: dict):
    with open(file, "rb") as f:
        while f.tell() < file.stat().st_size:
            # Read 8 bytes
            block_type, tag, data = read_block(f)[:3]
            if tag == TAG_START:  # START TAG
                if len(data) == 0:
                    continue
                handle_data(block_type, data, config, info)
            elif tag == TAG_END:  # END TAG
                pass
            else:
                raise ValueError(f'Tag error: {tag}')


def read_pod(input_file: Path, output_path: Path):
    config = {
        'default_material': {},
        'materials': [],
        'textures': [],
        'nodes': {},
    }
    info = {
        'data_type': 0,
        'num_components': 0,
        'stride': 0,
        'node_temp': [],
        'interleaved_data': None,
        'temp_datas': [],
        'last_node_index': '-1',
        'unindexed_node' : 999
    }

    try:
        ### Read pod data blocks to a dict
        read_pod_data(input_file, config, info)

        ### Add any unindexed nodes
        i = 0
        while len(info['node_temp']) > 0:
            config['nodes'][f'_{i}'] = info['node_temp'].pop(0)
            i += 1

        ### copy mesh data by checking vertex counts
        # there is probably a better way to this, but considering mesh data is unordered and messy
        # this ensures the correct mesh data is in the correct places,
        # trusting that the count of vertices is different per mesh
        datas = []
        vertex_map = {}
        datas_used = set()
        while len(info['temp_datas']) >= 9:
            datas.append({
                'indices': info['temp_datas'][0],
                'vertices': info['temp_datas'][1],
                'normals': info['temp_datas'][2],
                # tangent data
                # binormal data
                'uvs': info['temp_datas'][5],
                # vertex colors
                'bone_indices': info['temp_datas'][7],
                'bone_weights': info['temp_datas'][8]
            })
            vertex_map[len(datas[-1]['vertices'])] = len(datas) - 1
            info['temp_datas'] = info['temp_datas'][9:]  # Remove used data
        for node_key, node in config['nodes'].items():
            if (vertex_cound := node.get('num_of_vertices', 0)) > 0:
                if vertex_cound in vertex_map:
                    data_index = vertex_map[vertex_cound]
                    datas_used.add(data_index)
                    node['data'] = datas[data_index]
        for i, data in enumerate(datas):
            if i not in datas_used:
                config['unused_datas'] = config.get('unused_datas', [])
                config['unused_datas'].append(data)

    finally:
        if config['default_material']:
            config['materials'].append(config.pop('default_material'))
        else:
            config.pop('default_material')
        with open(output_path, "w") as f:
            json.dump(config, f, indent=4)