import array
import itertools
import json
import math
from functools import partial
from pathlib import Path
from typing import List, Tuple, Optional

from pygltflib import (
    Material,
    PbrMetallicRoughness,
    TextureInfo,
    Mesh,
    Primitive,
    Accessor,
    BufferView,
    GLTF2,
    Buffer,
    Node,
    Scene,
    Sampler,
    Image,
    Texture,
    Skin,
)
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
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s, np.cos(half)])


def safe_quat(q):
    q = np.array(q, dtype=float)
    if q.size == 3:  # accidentally truncated quat?
        return np.array([0, 0, 0, 1])
    if np.allclose(q, 0):
        return np.array([0, 0, 0, 1])
    n = np.linalg.norm(q)
    return q / n


def figure_out_transforms(n, node):
    # Check if this is a bone node (no mesh data, name starts with 'Bone')
    node_name = node.get("name", "")
    is_bone_node = "data" not in node and node_name.startswith("Bone")

    if is_bone_node:
        # Use unknown_5009 for bind pose transforms on bones
        if "unknown_5009" in node:
            scale = node["unknown_5009"][:3]
            axis = node["unknown_5009"][3:6]
            angle = float(node["unknown_5009"][6])
            bind_q = axis_angle_to_quat(axis, angle)
            bind_q[2] = -bind_q[2]
        else:
            scale = [1, 1, 1]
            bind_q = [0, 0, 0, 1]
        n.translation = [0.0, 0.0, 0.0]
        n.rotation = [float(v) for v in bind_q]
        n.scale = [float(v) for v in scale]
    else:
        # For mesh nodes: use animation transforms as before
        pos = np.array(node.get("animation_position", [0, 0, 0])[:3], dtype=float)
        anim_q = safe_quat(node.get("animation_rotation", [0, 0, 0, 1])[:4])

        if "unknown_5009" in node:
            scale = node["unknown_5009"][:3]
            axis = node["unknown_5009"][3:6]
            angle = float(node["unknown_5009"][6])
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
    mat.pbrMetallicRoughness.baseColorFactor = [
        diffuse[0],
        diffuse[1],
        diffuse[2],
        opacity,
    ]

    diffuse_index = mat_data.get("diffuse_texture", -1)
    if diffuse_index >= 0:
        mat.pbrMetallicRoughness.baseColorTexture = TextureInfo(index=diffuse_index)

    mat.extras = {
        "ambient_color": mat_data.get("ambient_color", [0, 0, 0]),
        "specular_color": mat_data.get("specular_color", [1, 1, 1]),
        "shininess": mat_data.get("shininess", 0.1),
    }

    return mat


def _pack_textures_into_buffer(
    config_textures,
    model_info_path: Path,
    all_buffer_bytes: bytes,
    all_buffer_views: list,
):
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
        p = Path("Swordigo_Export") / "assets" / "textures" / tex
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
        all_buffer_views.append(
            BufferView(buffer=0, byteOffset=img_offset, byteLength=img_length)
        )

        # create Image that references the bufferView
        images.append(Image(bufferView=bv_index, mimeType="image/png"))

        # create Texture referencing the image and default sampler
        textures.append(Texture(sampler=0, source=len(images) - 1))

    return images, samplers, textures, all_buffer_bytes, all_buffer_views


# Helper to 4-byte align each chunk
def align4(b: bytes) -> bytes:
    pad = (4 - (len(b) % 4)) % 4
    return b + (b"\x00" * pad)


def flip_uvs(uvs: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    # There is a vertical flip we need to apply
    return [(uv[0], 1 - uv[1]) for uv in uvs]


def create_mesh(data: dict, material_index: int):
    indices: Optional[List[int]] = data.get("indices", None)
    vertices: List[Tuple[float, float, float]] = data.get("vertices", [])
    normals: List[Tuple[float, float, float]] = data.get("normals", [])
    uvs: List[Tuple[float, float]] = data.get("uvs", [])
    if not vertices or not normals or not uvs:
        raise ValueError("Mesh data is incomplete")

    uvs = flip_uvs(uvs)

    # Flatten core arrays
    vertices_flat = array.array("f", [c for v in vertices for c in v]).tobytes()
    normals_flat = array.array("f", [c for n in normals for c in n]).tobytes()
    uvs_flat = array.array("f", [c for uv in uvs for c in uv]).tobytes()

    # optional bone data - DO NOT process here, handle in skin creation loop
    # This avoids creating orphaned JOINTS_0/WEIGHTS_0 accessors
    joints_flat = b""
    weights_flat = b""
    has_skin = False

    # Indices
    indices_bytes = b""
    index_type_code = None
    if indices is not None:
        if len(indices) > 0:
            max_index = max(indices)
            if max_index < 65536:
                index_type_code = 5123
                idx_array = array.array("H", indices)
            else:
                index_type_code = 5125
                idx_array = array.array("I", indices)
            indices_bytes = align4(idx_array.tobytes())
        else:
            indices_bytes = align4(b"")

    positions_bytes = align4(vertices_flat)
    normals_bytes = align4(normals_flat)
    uvs_bytes = align4(uvs_flat)
    if has_skin:
        joints_bytes = align4(joints_flat)
        weights_bytes = align4(weights_flat)
    else:
        joints_bytes = weights_bytes = b""

    # bufferViews
    buffer_views = []
    offset = 0
    if indices is not None:
        buffer_views.append(
            BufferView(
                buffer=0, byteOffset=offset, byteLength=len(indices_bytes), target=34963
            )
        )
        offset += len(indices_bytes)
    buffer_views.append(
        BufferView(
            buffer=0, byteOffset=offset, byteLength=len(positions_bytes), target=34962
        )
    )
    offset += len(positions_bytes)
    buffer_views.append(
        BufferView(
            buffer=0, byteOffset=offset, byteLength=len(normals_bytes), target=34962
        )
    )
    offset += len(normals_bytes)
    buffer_views.append(
        BufferView(buffer=0, byteOffset=offset, byteLength=len(uvs_bytes), target=34962)
    )
    offset += len(uvs_bytes)
    # NOTE: Bone data bufferViews are NOT created here
    # They will be created in the skin creation loop if needed

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
        acc = Accessor(
            bufferView=0,
            byteOffset=0,
            componentType=index_type_code,
            count=count_indices,
            type="SCALAR",
            min=[min(indices)],
            max=[max(indices)],
        )
        accessors.append(acc)
        accessor_index_map["INDICES"] = 0
        pos_bv_index = 1
        norm_bv_index = 2
        uv_bv_index = 3
        skin_offset = 4
    else:
        pos_bv_index = 0
        norm_bv_index = 1
        uv_bv_index = 2
        skin_offset = 3

    accessors.append(
        Accessor(
            bufferView=pos_bv_index,
            byteOffset=0,
            componentType=5126,
            count=len(vertices),
            type="VEC3",
            min=pos_min,
            max=pos_max,
        )
    )
    accessor_index_map["POSITION"] = len(accessors) - 1

    accessors.append(
        Accessor(
            bufferView=norm_bv_index,
            byteOffset=0,
            componentType=5126,
            count=len(normals),
            type="VEC3",
        )
    )
    accessor_index_map["NORMAL"] = len(accessors) - 1

    accessors.append(
        Accessor(
            bufferView=uv_bv_index,
            byteOffset=0,
            componentType=5126,
            count=len(uvs),
            type="VEC2",
            min=uv_min,
            max=uv_max,
        )
    )
    accessor_index_map["TEXCOORD_0"] = len(accessors) - 1

    # NOTE: Do NOT create JOINTS_0/WEIGHTS_0 accessors here
    # They will be created in the skin creation loop with proper VEC4 format

    # concatenate (NOTE: joints_bytes and weights_bytes NOT included, handled in skin creation)
    buffer_bytes = b"".join(
        filter(
            None,
            [
                indices_bytes,
                positions_bytes,
                normals_bytes,
                uvs_bytes,
            ],
        )
    )

    prim_attrs = {k: v for k, v in accessor_index_map.items() if k not in ("INDICES",)}
    prim = Primitive(
        attributes=prim_attrs,
        indices=accessor_index_map.get("INDICES"),
        material=material_index,
    )
    mesh = Mesh(primitives=[prim], name=data.get("name", ""))

    return {
        "mesh": mesh,
        "buffer_bytes": buffer_bytes,
        "buffer_views": buffer_views,
        "accessors": accessors,
    }


# Helper alignment function
def align4_len(n: int) -> int:
    return n + ((4 - (n % 4)) % 4)


def compile_glb(model_info: Path, glb_path: Path):
    with open(model_info, "r") as f:
        config = json.load(f)

    # Handle the materials
    materials = list(map(create_material, config["materials"]))

    # Handle the meshes
    mesh_chunks = []
    vertices_count_to_mesh_index = {}
    for node_id, node in config["nodes"].items():
        data = node.get("data")
        if not data:
            continue
        vertices = data.get("vertices", [])
        count_vertices = len(vertices)
        if not vertices:
            continue
        del vertices
        mesh_chunks.append(create_mesh(data, node.get("material_index", 0)))
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
            all_buffer_bytes += b"\x00" * pad
        global_base = len(all_buffer_bytes)

        # append chunk buffer bytes
        all_buffer_bytes += chunk["buffer_bytes"]

        # Append bufferViews: their byteOffset is relative to chunk; convert to global offset
        base_bv_index = len(all_buffer_views)
        for bv in chunk["buffer_views"]:
            new_bv = BufferView(
                buffer=0,
                byteOffset=global_base + (bv.byteOffset or 0),
                byteLength=bv.byteLength,
                target=bv.target,
            )
            all_buffer_views.append(new_bv)

        # Append accessors: update bufferView references to global indices
        base_accessor_index = len(all_accessors)
        for acc in chunk["accessors"]:
            new_acc = Accessor(
                bufferView=(base_bv_index + acc.bufferView)
                if acc.bufferView is not None
                else None,
                byteOffset=acc.byteOffset or 0,
                componentType=acc.componentType,
                count=acc.count,
                type=acc.type,
                min=acc.min,
                max=acc.max,
            )
            all_accessors.append(new_acc)

        # Append mesh: update primitive accessor indices to global accessor indices
        mesh = chunk["mesh"]
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

    images, samplers, textures, all_buffer_bytes, all_buffer_views = (
        _pack_textures_into_buffer(
            config.get("textures", []), model_info, all_buffer_bytes, all_buffer_views
        )
    )
    gltf.images = images
    gltf.samplers = samplers
    gltf.textures = textures

    # Find bones that are referenced but not in config - create them FIRST so they get correct indices
    referenced_bones = set()
    for node in config["nodes"].values():
        bones = node.get("bone_batch_indexes", [])
        num = node.get("num_of_bones_per_batch", [0])
        num_count = num[0] if isinstance(num, list) else num
        for b in bones[:num_count]:
            if b != 0:
                referenced_bones.add(b)

    # Build nodes list preserving input order; support parent references.
    nodes: List[Node] = []
    nid_to_index = {}  # numeric node id -> index in nodes list
    node_parent_nid = {}  # numeric node id -> parent numeric id (or -1)

    # Create missing bone nodes FIRST so they get correct indices (before other nodes)
    for bone_nid in sorted(referenced_bones):
        if str(bone_nid) not in config["nodes"]:
            n = Node(name=f"BoneBody{bone_nid}")
            n.translation = [0.0, 0.0, 0.0]
            n.rotation = [0.0, 0.0, 0.0, 1.0]
            n.scale = [1.0, 1.0, 1.0]
            nodes.append(n)
            nid_to_index[bone_nid] = len(nodes) - 1
            node_parent_nid[bone_nid] = -1

    for node_id, node in config["nodes"].items():
        nid = int(node_id)
        data = node.get("data")
        parent_nid = node.get("parent_index", -1)
        node_parent_nid[nid] = parent_nid

        n = Node(name=node.get("name", node_id))

        if data:
            count_vertices = len(data.get("vertices", []))
            mesh_index = vertices_count_to_mesh_index.get(count_vertices)
            if mesh_index is not None:
                n.mesh = mesh_index

        # Copy transform fields (bind pose transforms from source data)
        figure_out_transforms(n, node)

        nodes.append(n)
        nid_to_index[nid] = len(nodes) - 1

    # Second pass: link children into parents using numeric ids
    # Also track missing parents that need to be created synthetically
    missing_parents = {}
    for nid, idx in nid_to_index.items():
        parent_nid = node_parent_nid.get(nid, -1)
        if parent_nid is None or parent_nid == -1:
            continue
        parent_idx = nid_to_index.get(parent_nid)
        if parent_idx is None:
            # Parent not found in config; track for synthetic creation
            if parent_nid not in missing_parents:
                missing_parents[parent_nid] = []
            missing_parents[parent_nid].append(idx)
            continue
        parent_node = nodes[parent_idx]
        if parent_node.children is None:
            parent_node.children = []
        parent_node.children.append(idx)

    # Create synthetic parent nodes for missing bone hierarchy roots
    # This ensures skeleton hierarchy is complete for skinning
    if missing_parents:
        for missing_nid in sorted(missing_parents.keys()):
            # Create synthetic node with default transform
            synthetic_node = Node(name=f"SyntheticRoot_{missing_nid}")
            synthetic_node.children = missing_parents[missing_nid]
            nodes.append(synthetic_node)
            nid_to_index[missing_nid] = len(nodes) - 1
            # Mark as root since it has no parent in config
            node_parent_nid[missing_nid] = -1

    gltf.nodes = nodes

    root_nodes = [
        idx
        for nid, idx in nid_to_index.items()
        if node_parent_nid.get(nid, -1) == -1
        or node_parent_nid.get(nid) not in nid_to_index
    ]
    gltf.scenes = [Scene(nodes=root_nodes)]
    gltf.scene = 0

    # Helper function to find skeleton root
    def find_skeleton_root(joint_nids, nid_to_index, node_parent_nid):
        """Find the topmost parent of the skeleton."""
        if not joint_nids:
            return None

        # Start with first joint and traverse up the parent chain
        current_nid = joint_nids[0]
        visited = set()

        while current_nid is not None and current_nid not in visited:
            visited.add(current_nid)
            parent_nid = node_parent_nid.get(current_nid, -1)

            if parent_nid is None or parent_nid == -1 or parent_nid not in nid_to_index:
                # Reached the top
                return nid_to_index.get(current_nid)

            current_nid = parent_nid

        return nid_to_index.get(current_nid)

    # Helper function to compute inverse bind matrices
    def compute_inverse_bind_matrices(joint_nids, joint_indices, nodes, nid_to_index):
        """Compute inverse bind matrices for each joint."""
        # For now, use identity matrices (safe for bind pose = identity assumption)
        matrices = []
        for joint_idx in joint_indices:
            # Identity matrix as 16 floats [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
            matrices.append([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
        return matrices

    skins = []
    mesh_to_skin_index = {}

    for node_id, node in config["nodes"].items():
        data = node.get("data")
        if not data:
            continue
        bone_batch = node.get("bone_batch_indexes", [])
        # your preferred presence test
        if not bone_batch or node.get("num_of_bones_per_batch", 0) == 0:
            continue

        bone_node_ids = bone_batch[: node.get("num_of_bones_per_batch", [0])[0]]
        joints = []
        valid_bone_node_ids = []
        for bone_nid in bone_node_ids:
            if bone_nid == 0:
                continue
            j = nid_to_index.get(bone_nid)
            if j is not None:
                joints.append(j)
                valid_bone_node_ids.append(bone_nid)
        if not joints:
            continue

        # Build lookup: bone_node_index -> position in joints array (for mapping bone_indices)
        bone_to_joint_position = {joints[i]: i for i in range(len(joints))}

        mesh_index = vertices_count_to_mesh_index.get(len(data.get("vertices", [])))
        if mesh_index is None:
            continue

        mesh_index = vertices_count_to_mesh_index.get(len(data.get("vertices", [])))
        if mesh_index is None:
            print(f"[DEBUG] Node {node_id}: mesh_index is None")
            continue

        mesh = gltf.meshes[mesh_index]
        prim = mesh.primitives[0]

        # presence test per your request
        if (
            data.get("bone_indices") is not None
            and data.get("bone_weights") is not None
        ):
            # Map bone_indices: POD index -> position in joints array (0, 1, 2, ...)
            # bone_indices[i] = 1 means: use joint at position 1 (bone 5)
            mapped_joints = np.array(
                [bone_to_joint_position.get(idx, 0) for idx in data["bone_indices"]],
                dtype=np.uint16,
            )
            raw_joints = mapped_joints
            raw_weights = np.array(data["bone_weights"], dtype=np.float32)

            # Normalize shapes: support flat list or already grouped lists
            def ensure_grouped(arr, dtype, group=4):
                arr = np.array(arr, dtype=dtype)
                if arr.ndim == 1:
                    # For 1D input with N elements (one per vertex),
                    # expand to (N, group) by padding each row
                    n_vertices = len(arr)
                    expanded = np.zeros((n_vertices, group), dtype=dtype)
                    expanded[:, 0] = arr  # First column gets the data
                    # Rest are padded with zeros
                    return expanded
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

            # ensure weights per-vertex sum to ~1 (optional, but safer)
            s = weights_arr.sum(axis=1, keepdims=True)
            s[s == 0] = 1.0
            weights_arr = weights_arr / s

            joints_bytes = align4(joints_arr.tobytes())
            weights_bytes = align4(weights_arr.tobytes())

            base_offset = len(all_buffer_bytes)
            all_buffer_bytes += joints_bytes + weights_bytes

            bv_joints = BufferView(
                buffer=0,
                byteOffset=base_offset,
                byteLength=len(joints_bytes),
                target=34962,
            )
            bv_weights = BufferView(
                buffer=0,
                byteOffset=base_offset + len(joints_bytes),
                byteLength=len(weights_bytes),
                target=34962,
            )
            gltf.bufferViews.extend([bv_joints, bv_weights])
            bv_joints_index = len(gltf.bufferViews) - 2
            bv_weights_index = len(gltf.bufferViews) - 1

            num_vertices = len(data.get("vertices", []))
            acc_joints = Accessor(
                bufferView=bv_joints_index,
                componentType=5123,
                count=num_vertices,
                type="VEC4",
            )
            acc_weights = Accessor(
                bufferView=bv_weights_index,
                componentType=5126,
                count=num_vertices,
                type="VEC4",
            )

            gltf.accessors.extend([acc_joints, acc_weights])
            acc_joints_index = len(gltf.accessors) - 2
            acc_weights_index = len(gltf.accessors) - 1

            prim.attributes["JOINTS_0"] = acc_joints_index
            prim.attributes["WEIGHTS_0"] = acc_weights_index

            # Compute inverse bind matrices using valid bones
            inv_bind_matrices = compute_inverse_bind_matrices(
                valid_bone_node_ids, joints, nodes, nid_to_index
            )

            # Pack inverse bind matrices into buffer
            inv_bind_flat = []
            for matrix in inv_bind_matrices:
                inv_bind_flat.extend(matrix)

            inv_bind_bytes = align4(array.array("f", inv_bind_flat).tobytes())

            inv_base_offset = len(all_buffer_bytes)
            all_buffer_bytes += inv_bind_bytes

            bv_inv_bind = BufferView(
                buffer=0,
                byteOffset=inv_base_offset,
                byteLength=len(inv_bind_bytes),
            )
            gltf.bufferViews.append(bv_inv_bind)
            bv_inv_bind_index = len(gltf.bufferViews) - 1

            # Create accessor for inverse bind matrices (MAT4 = 4x4 matrix)
            acc_inv_bind = Accessor(
                bufferView=bv_inv_bind_index,
                byteOffset=0,
                componentType=5126,
                count=len(joints),
                type="MAT4",
            )
            gltf.accessors.append(acc_inv_bind)
            acc_inv_bind_index = len(gltf.accessors) - 1

            # Find skeleton root using valid bones
            skeleton_root = find_skeleton_root(
                valid_bone_node_ids, nid_to_index, node_parent_nid
            )

            # Create skin with inverse bind matrices
            skin = Skin(
                joints=joints,
                skeleton=skeleton_root,
                inverseBindMatrices=acc_inv_bind_index,
            )
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
