import array
import itertools
import json
import math
from functools import partial
from pathlib import Path
from typing import List, Tuple, Optional

from pygltflib import Material, PbrMetallicRoughness, TextureInfo, Mesh, Primitive, Accessor, BufferView, GLTF2, Buffer, \
    Node, Scene, Sampler, Image, Texture, Skin
import numpy as np
from scipy.spatial.transform import Rotation as R


def axis_angle_to_quat(axis, angle):
    axis = np.array(axis, dtype=float)
    n = np.linalg.norm(axis)
    if n < 1e-8:
        return np.array([0, 0, 0, 1])
    axis /= n
    half = angle * 0.5
    s = np.sin(half)
    return np.array([axis[0]*s, axis[1]*s, axis[2]*s, np.cos(half)])

def safe_quat(q):
    q = np.array(q, dtype=float)
    if q.size == 3:  # accidentally truncated quat?
        return np.array([0,0,0,1])
    if np.allclose(q, 0):
        return np.array([0,0,0,1])
    n = np.linalg.norm(q)
    return q / n


def is_ancestor_of(nodes: List[Node], ancestor_idx: int, descendant_idx: int) -> bool:
    """
    Check if ancestor_idx is an ancestor of (or equal to) descendant_idx in the node hierarchy.
    """
    if ancestor_idx == descendant_idx:
        return True
    
    # Build parent map
    parent_map = {}
    for i, node in enumerate(nodes):
        if node.children:
            for child_idx in node.children:
                parent_map[child_idx] = i
    
    # Trace from descendant to root
    current = descendant_idx
    while current in parent_map:
        current = parent_map[current]
        if current == ancestor_idx:
            return True
    return False


def find_common_ancestor(nodes: List[Node], joint_indices: List[int]) -> Optional[int]:
    """
    Find the common ancestor of all joint nodes.
    Returns the node index that is a common ancestor of all joints,
    or None if no common ancestor exists.
    """
    if not joint_indices:
        return None

    if len(joint_indices) == 1:
        # Single joint: use the joint itself as skeleton root
        # (it's technically its own common ancestor)
        return joint_indices[0]

    # Build parent map: node_index -> parent_index
    parent_map = {}
    for i, node in enumerate(nodes):
        if node.children:
            for child_idx in node.children:
                parent_map[child_idx] = i

    # For each joint, build the path to root
    def get_path_to_root(node_idx):
        path = [node_idx]
        current = node_idx
        while current in parent_map:
            current = parent_map[current]
            path.append(current)
        return path

    # Get paths for all joints
    paths = [get_path_to_root(j) for j in joint_indices]

    # Reverse paths so they go from root to joint for easier comparison
    reversed_paths = [list(reversed(p)) for p in paths]

    # Find the deepest common node
    common_ancestor = None
    for depth in range(min(len(p) for p in reversed_paths)):
        candidates = [p[depth] for p in reversed_paths]
        if all(c == candidates[0] for c in candidates):
            common_ancestor = candidates[0]
        else:
            break

    return common_ancestor


def figure_out_transforms(n, node):
    pos = np.array(node.get('animation_position', [0, 0, 0])[:3], dtype=float)
    anim_q = safe_quat(node.get('animation_rotation', [0, 0, 0, 1])[:4])

    if 'unknown_5009' in node:
        scale = node['unknown_5009'][:3]
        axis = node['unknown_5009'][3:6]
        angle = float(node['unknown_5009'][6])
        bind_q = axis_angle_to_quat(axis, angle)
    else:
        scale = [1, 1, 1]
        bind_q = [0, 0, 0, 1]

    anim_q[2] = -anim_q[2]  # invert Z axis
    bind_q[2] = -bind_q[2]

    # only combine rotations
    final_rot = R.from_quat(anim_q) * R.from_quat(bind_q)

    n.translation = pos.tolist()
    n.rotation = final_rot.as_quat().tolist()
    n.scale = list(scale)

def create_material(mat_data):
    mat = Material(name=mat_data["name"])
    mat.pbrMetallicRoughness = PbrMetallicRoughness()  # initialize!

    diffuse = mat_data.get("diffuse_color", [1, 1, 1])
    opacity = mat_data.get("opacity", 1.0)
    mat.pbrMetallicRoughness.baseColorFactor = [diffuse[0], diffuse[1], diffuse[2], opacity]

    diffuse_index = mat_data.get("diffuse_texture", -1)
    if diffuse_index >= 0:
        mat.pbrMetallicRoughness.baseColorTexture = TextureInfo(index=diffuse_index)

    mat.extras = {
        "ambient_color": mat_data.get("ambient_color", [0, 0, 0]),
        "specular_color": mat_data.get("specular_color", [1, 1, 1]),
        "shininess": mat_data.get("shininess", 0.1)
    }

    return mat


def _pack_textures_into_buffer(config_textures, model_info_path: Path, all_buffer_bytes: bytes, all_buffer_views: list):
    """
    Appends each texture's bytes to all_buffer_bytes (4-byte aligned), creates a BufferView
    for it (appended to all_buffer_views) and returns three lists for gltf: images, samplers, textures,
    plus the updated all_buffer_bytes and all_buffer_views.
    """
    images = []
    textures = []
    samplers = []

    if not config_textures:
        return images, samplers, textures, all_buffer_bytes, all_buffer_views

    # create a single default sampler (index 0) to reuse
    default_sampler = Sampler()
    samplers.append(default_sampler)
    base_dir = Path(model_info_path).parent

    for tex in config_textures:
        p = Path('Swordigo_Export') / 'assets' / 'textures' / tex
        with open(p, "rb") as f:
            img_bytes = f.read()

        # align global buffer to 4 bytes before appending image
        pad_before = (4 - (len(all_buffer_bytes) % 4)) % 4
        if pad_before:
            all_buffer_bytes += b"\x00" * pad_before
        img_offset = len(all_buffer_bytes)

        # append image bytes and pad to 4 bytes
        all_buffer_bytes += img_bytes
        pad_after = (4 - (len(img_bytes) % 4)) % 4
        if pad_after:
            all_buffer_bytes += b"\x00" * pad_after
        img_length = len(img_bytes) + pad_after

        # create BufferView for the image and append it
        bv_index = len(all_buffer_views)
        all_buffer_views.append(BufferView(buffer=0, byteOffset=img_offset, byteLength=img_length))

        # create Image that references the bufferView
        images.append(Image(bufferView=bv_index, mimeType="image/png"))

        # create Texture referencing the image and default sampler
        textures.append(Texture(sampler=0, source=len(images) - 1))

    return images, samplers, textures, all_buffer_bytes, all_buffer_views


# Helper to 4-byte align each chunk
def align4(b: bytes) -> bytes:
    pad = (4 - (len(b) % 4)) % 4
    return b + (b'\x00' * pad)


def flip_uvs(uvs: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    # There is a vertical flip we need to apply
    return [
        (uv[0], 1 - uv[1])
        for uv in uvs
    ]


def create_mesh(data: dict, material_index: int):
    indices: Optional[List[int]] = data.get("indices", None)
    vertices: List[Tuple[float, float, float]] = data.get("vertices", [])
    normals: List[Tuple[float, float, float]] = data.get("normals", [])
    uvs: List[Tuple[float, float]] = data.get("uvs", [])
    if not vertices or not normals or not uvs:
        raise ValueError("Mesh data is incomplete")

    uvs = flip_uvs(uvs)

    # Flatten core arrays
    vertices_flat = array.array('f', [c for v in vertices for c in v]).tobytes()
    normals_flat = array.array('f', [c for n in normals for c in n]).tobytes()
    uvs_flat = array.array('f', [c for uv in uvs for c in uv]).tobytes()

    # optional bone data
    # Note: Skinning data (joints/weights) is NOT included in the mesh buffer here.
    # It will be properly structured and added later in the skinning processing loop.
    # We only set has_skin flag to track that this mesh needs skinning.
    has_skin = False
    if data.get("bone_indices") and data.get("bone_weights"):
        has_skin = True

    # Indices
    indices_bytes = b""
    index_type_code = None
    if indices is not None:
        if len(indices) > 0:
            max_index = max(indices)
            if max_index < 65536:
                index_type_code = 5123
                idx_array = array.array('H', indices)
            else:
                index_type_code = 5125
                idx_array = array.array('I', indices)
            indices_bytes = align4(idx_array.tobytes())
        else:
            indices_bytes = align4(b"")

    positions_bytes = align4(vertices_flat)
    normals_bytes = align4(normals_flat)
    uvs_bytes = align4(uvs_flat)

    # bufferViews
    buffer_views = []
    offset = 0
    if indices is not None:
        buffer_views.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(indices_bytes), target=34963))
        offset += len(indices_bytes)
    buffer_views.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(positions_bytes), target=34962)); offset += len(positions_bytes)
    buffer_views.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(normals_bytes), target=34962)); offset += len(normals_bytes)
    buffer_views.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(uvs_bytes), target=34962)); offset += len(uvs_bytes)

    # compute mins/maxs
    pos_min = [min(p[i] for p in vertices) for i in range(3)]
    pos_max = [max(p[i] for p in vertices) for i in range(3)]
    uv_min = [min(uv[i] for uv in uvs) for i in range(2)]
    uv_max = [max(uv[i] for uv in uvs) for i in range(2)]

    # accessors
    accessors = []
    accessor_index_map = {}

    if indices is not None:
        count_indices = len(indices)
        acc = Accessor(bufferView=0, byteOffset=0, componentType=index_type_code, count=count_indices, type="SCALAR",
                       min=[min(indices)], max=[max(indices)])
        accessors.append(acc)
        accessor_index_map["INDICES"] = 0
        pos_bv_index = 1
        norm_bv_index = 2
        uv_bv_index = 3
    else:
        pos_bv_index = 0
        norm_bv_index = 1
        uv_bv_index = 2

    accessors.append(Accessor(bufferView=pos_bv_index, byteOffset=0, componentType=5126, count=len(vertices), type="VEC3", min=pos_min, max=pos_max))
    accessor_index_map["POSITION"] = len(accessors) - 1

    accessors.append(Accessor(bufferView=norm_bv_index, byteOffset=0, componentType=5126, count=len(normals), type="VEC3"))
    accessor_index_map["NORMAL"] = len(accessors) - 1

    accessors.append(Accessor(bufferView=uv_bv_index, byteOffset=0, componentType=5126, count=len(uvs), type="VEC2", min=uv_min, max=uv_max))
    accessor_index_map["TEXCOORD_0"] = len(accessors) - 1

    # Note: Skinning accessors (JOINTS_0, WEIGHTS_0) are NOT created here.
    # They will be properly created later in the skinning processing loop with VEC4 type.
    # We just mark that this mesh has skin data.

    # concatenate (no joints/weights bytes here)
    buffer_bytes = b"".join(filter(None, [indices_bytes, positions_bytes, normals_bytes, uvs_bytes]))

    prim_attrs = {k: v for k, v in accessor_index_map.items() if k not in ("INDICES",)}
    prim = Primitive(attributes=prim_attrs, indices=accessor_index_map.get("INDICES"), material=material_index)
    mesh = Mesh(primitives=[prim], name=data.get("name", ""))

    return {
        "mesh": mesh,
        "buffer_bytes": buffer_bytes,
        "buffer_views": buffer_views,
        "accessors": accessors,
        "has_skin": has_skin,
    }


# Helper alignment function
def align4_len(n: int) -> int:
    return n + ((4 - (n % 4)) % 4)


def compile_glb(model_info: Path, glb_path: Path):
    with open(model_info, 'r') as f:
        config = json.load(f)

    # Handle the materials
    materials = list(map(create_material, config['materials']))

    # Handle the meshes
    mesh_chunks = []
    vertices_count_to_mesh_index = {}
    for node_id, node in config['nodes'].items():
        data = node.get('data')
        if not data:
            continue
        vertices = data.get('vertices', [])
        count_vertices = len(vertices)
        if not vertices:
            continue
        del vertices
        mesh_chunks.append(create_mesh(data, node.get('material_index', 0)))
        vertices_count_to_mesh_index[count_vertices] = len(mesh_chunks) - 1

    # Aggregate global binary, bufferViews, accessors, meshes
    all_buffer_bytes = b""
    all_buffer_views = []
    all_accessors = []
    all_meshes = []

    for chunk in mesh_chunks:
        # Align global buffer to 4 bytes before appending this chunk
        pad = (4 - (len(all_buffer_bytes) % 4)) % 4
        if pad:
            all_buffer_bytes += b'\x00' * pad
        global_base = len(all_buffer_bytes)

        # append chunk buffer bytes
        all_buffer_bytes += chunk['buffer_bytes']

        # Append bufferViews: their byteOffset is relative to chunk; convert to global offset
        base_bv_index = len(all_buffer_views)
        for bv in chunk['buffer_views']:
            new_bv = BufferView(
                buffer=0,
                byteOffset=global_base + (bv.byteOffset or 0),
                byteLength=bv.byteLength,
                target=bv.target
            )
            all_buffer_views.append(new_bv)

        # Append accessors: update bufferView references to global indices
        base_accessor_index = len(all_accessors)
        for acc in chunk['accessors']:
            new_acc = Accessor(
                bufferView=(base_bv_index + acc.bufferView) if acc.bufferView is not None else None,
                byteOffset=acc.byteOffset or 0,
                componentType=acc.componentType,
                count=acc.count,
                type=acc.type,
                min=acc.min,
                max=acc.max
            )
            all_accessors.append(new_acc)

        # Append mesh: update primitive accessor indices to global accessor indices
        mesh = chunk['mesh']
        # each mesh may have one primitive in this code path
        for prim in mesh.primitives:
            # indices is local accessor index (0)
            if prim.indices is not None:
                prim.indices = base_accessor_index + prim.indices
            # attributes map local accessor indices (POSITION=1, NORMAL=2, TEXCOORD_0=3) -> shift them
            new_attrs = {}
            for attr_name, local_acc_idx in prim.attributes.items():
                new_attrs[attr_name] = base_accessor_index + local_acc_idx
            prim.attributes = new_attrs
        all_meshes.append(mesh)

    # Create GLTF asset
    gltf = GLTF2()
    gltf.buffers = [Buffer(byteLength=len(all_buffer_bytes))]
    gltf.bufferViews = all_buffer_views
    gltf.accessors = all_accessors
    gltf.meshes = all_meshes
    gltf.materials = materials

    images, samplers, textures, all_buffer_bytes, all_buffer_views = _pack_textures_into_buffer(
        config.get("textures", []), model_info, all_buffer_bytes, all_buffer_views
    )
    gltf.images = images
    gltf.samplers = samplers
    gltf.textures = textures

    # Build nodes list preserving input order; support parent references.
    nodes: List[Node] = []
    nid_to_index = {}  # numeric node id -> index in nodes list
    node_parent_nid = {}  # numeric node id -> parent numeric id (or -1)

    for node_id, node in config['nodes'].items():
        nid = int(node_id)
        data = node.get('data')
        parent_nid = node.get('parent_index', -1)
        node_parent_nid[nid] = parent_nid

        n = Node(name=node.get('name', node_id))

        if data:
            count_vertices = len(data.get('vertices', []))
            mesh_index = vertices_count_to_mesh_index.get(count_vertices)
            if mesh_index is not None:
                n.mesh = mesh_index

        # Copy transform fields if present
        figure_out_transforms(n, node)

        nodes.append(n)
        nid_to_index[nid] = len(nodes) - 1

    # Second pass: link children into parents using numeric ids
    for nid, idx in nid_to_index.items():
        parent_nid = node_parent_nid.get(nid, -1)
        if parent_nid is None or parent_nid == -1:
            continue
        parent_idx = nid_to_index.get(parent_nid)
        if parent_idx is None:
            # parent not found in config; treat as root (skip linking)
            continue
        parent_node = nodes[parent_idx]
        if parent_node.children is None:
            parent_node.children = []
        parent_node.children.append(idx)

    gltf.nodes = nodes

    root_nodes = [
        idx for nid, idx in nid_to_index.items()
        if node_parent_nid.get(nid, -1) == -1 or node_parent_nid.get(nid) not in nid_to_index
    ]
    gltf.scenes = [Scene(nodes=root_nodes)]
    gltf.scene = 0

    skins = []
    mesh_to_skin_index = {}

    for node_id, node in config['nodes'].items():
        data = node.get('data')
        if not data:
            continue
        bone_batch = node.get('bone_batch_indexes', [])
        # your preferred presence test
        if not bone_batch or node.get('num_of_bones_per_batch', 0) == 0:
            continue

        joints = []
        for idx in bone_batch[: node.get('num_of_bones_per_batch', [0])[0]]:
            if idx == 0:
                continue
            j = nid_to_index.get(idx)
            if j is not None:
                joints.append(j)
        if not joints:
            continue

        mesh_index = vertices_count_to_mesh_index.get(len(data.get('vertices', [])))
        if mesh_index is None:
            continue

        mesh = gltf.meshes[mesh_index]
        prim = mesh.primitives[0]

        # Get the actual vertex count from the POSITION accessor in the primitive
        # This is the authoritative count that JOINTS_0 and WEIGHTS_0 must match
        position_accessor_idx = prim.attributes.get("POSITION")
        if position_accessor_idx is None:
            continue
        expected_vertex_count = gltf.accessors[position_accessor_idx].count

        # presence test per your request
        if data.get('bone_indices') is not None and data.get('bone_weights') is not None:
            raw_joints = np.array(data['bone_indices'])
            raw_weights = np.array(data['bone_weights'], dtype=np.float32)

            # Normalize shapes: support flat list or already grouped lists
            def ensure_grouped(arr, dtype, group=4):
                arr = np.array(arr, dtype=dtype)
                if arr.ndim == 1:
                    rem = arr.size % group
                    if rem != 0:
                        pad = group - rem
                        arr = np.pad(arr, (0, pad), constant_values=0)
                    arr = arr.reshape((-1, group))
                elif arr.ndim == 2 and arr.shape[1] != group:
                    # pad inner dimension
                    pad_cols = group - arr.shape[1] if arr.shape[1] < group else 0
                    if pad_cols:
                        arr = np.pad(arr, ((0, 0), (0, pad_cols)), constant_values=0)
                return arr

            joints_arr = ensure_grouped(raw_joints, dtype=np.uint16, group=4)
            weights_arr = ensure_grouped(raw_weights, dtype=np.float32, group=4)

            # if counts don't match, skip (malformed)
            if joints_arr.shape[0] != weights_arr.shape[0]:
                continue

            # Ensure bone data has same count as vertices (POSITION accessor count)
            # Pad or truncate to match the expected vertex count
            if joints_arr.shape[0] < expected_vertex_count:
                # Pad with zeros (no joint influence)
                pad_rows = expected_vertex_count - joints_arr.shape[0]
                joints_arr = np.pad(joints_arr, ((0, pad_rows), (0, 0)), constant_values=0)
                weights_arr = np.pad(weights_arr, ((0, pad_rows), (0, 0)), constant_values=0)
            elif joints_arr.shape[0] > expected_vertex_count:
                # Truncate to match vertex count
                joints_arr = joints_arr[:expected_vertex_count]
                weights_arr = weights_arr[:expected_vertex_count]

            # ensure weights per-vertex sum to ~1 (optional, but safer)
            s = weights_arr.sum(axis=1, keepdims=True)
            s[s == 0] = 1.0
            weights_arr = weights_arr / s

            # Convert to bytes
            joints_bytes_raw = joints_arr.tobytes()
            weights_bytes_raw = weights_arr.tobytes()
            
            # Calculate actual data lengths (without extra padding)
            joints_byte_length = len(joints_bytes_raw)
            weights_byte_length = len(weights_bytes_raw)
            
            # Pad the raw bytes for buffer alignment
            joints_bytes = align4(joints_bytes_raw)
            weights_bytes = align4(weights_bytes_raw)

            base_offset = len(all_buffer_bytes)
            all_buffer_bytes += joints_bytes + weights_bytes

            # BufferView byteLength should be the actual data size, not including final padding
            bv_joints = BufferView(buffer=0, byteOffset=base_offset, byteLength=joints_byte_length, target=34962)
            bv_weights = BufferView(buffer=0, byteOffset=base_offset + len(joints_bytes), byteLength=weights_byte_length,
                                    target=34962)
            gltf.bufferViews.extend([bv_joints, bv_weights])
            bv_joints_index = len(gltf.bufferViews) - 2
            bv_weights_index = len(gltf.bufferViews) - 1

            # Use the expected vertex count to ensure accessors match POSITION
            num_skin_vertices = expected_vertex_count
            acc_joints = Accessor(bufferView=bv_joints_index, componentType=5123, count=num_skin_vertices, type="VEC4")
            acc_weights = Accessor(bufferView=bv_weights_index, componentType=5126, count=num_skin_vertices, type="VEC4")

            gltf.accessors.extend([acc_joints, acc_weights])
            acc_joints_index = len(gltf.accessors) - 2
            acc_weights_index = len(gltf.accessors) - 1

            prim.attributes["JOINTS_0"] = acc_joints_index
            prim.attributes["WEIGHTS_0"] = acc_weights_index

            # Find common ancestor of all joints for skeleton
            skeleton_node = find_common_ancestor(gltf.nodes, joints)
            
            # Create skin with validated skeleton root
            if skeleton_node is not None:
                # Validate that skeleton_node is actually an ancestor of all joints
                if all(is_ancestor_of(gltf.nodes, skeleton_node, j) for j in joints):
                    skin = Skin(joints=joints, skeleton=skeleton_node)
                else:
                    # Invalid skeleton found, omit it
                    skin = Skin(joints=joints)
            else:
                # No common ancestor found by the algorithm
                # Try using the first scene root node if it's an ancestor of all joints
                if root_nodes:
                    candidate_root = root_nodes[0]
                    if all(is_ancestor_of(gltf.nodes, candidate_root, j) for j in joints):
                        skin = Skin(joints=joints, skeleton=candidate_root)
                    else:
                        # No valid skeleton root found, omit the skeleton property
                        skin = Skin(joints=joints)
                else:
                    # No root nodes available, omit skeleton
                    skin = Skin(joints=joints)
            skins.append(skin)
            mesh_to_skin_index[mesh_index] = len(skins) - 1

    for n in gltf.nodes:
        if n.mesh is not None and n.mesh in mesh_to_skin_index:
            n.skin = mesh_to_skin_index[n.mesh]

    gltf.skins = skins

    # Attach binary blob and write GLB
    gltf.set_binary_blob(all_buffer_bytes)
    gltf.save_binary(str(glb_path))

    # raise StopIteration()
