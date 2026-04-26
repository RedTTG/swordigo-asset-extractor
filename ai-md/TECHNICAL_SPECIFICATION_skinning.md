# Detailed Technical Specification: critter_konna_green Skinning Issues

## CRITICAL ISSUE SUMMARY

The current glTF2 compiler generates **INVALID skinning data** that violates the glTF2.0 specification. Specifically:

1. JOINTS_0 and WEIGHTS_0 are SCALAR instead of VEC4
2. No inverse bind matrices
3. Incorrect joint index mapping
4. Wrong skeleton root

This renders the model's skeleton non-functional in all glTF2-compliant viewers.

---

## DETAILED ANALYSIS

### Current Data State

#### Node 0 (GeoSphere01) Raw Data:

```json
{
  "num_of_vertices": 376,
  "num_of_bones_per_batch": [1],
  "bone_offset_per_batch": [0],
  "bone_batch_indexes": [3, 0, 0, 0, ... 0],  // 1000 elements
  "data": {
    "bone_indices": [0, 0, 0, ..., 0],         // 376 elements
    "bone_weights": [1.0, 1.0, ..., 1.0]       // 376 elements
  }
}
```

**Critical Issue**: bone_indices and bone_weights are SCALAR arrays, not VEC4!

#### Node 1 (Box01) Raw Data:

```json
{
  "num_of_vertices": 47,
  "num_of_bones_per_batch": [2],
  "bone_offset_per_batch": [0],
  "bone_batch_indexes": [1, 0, 0, 0, ... 0],
  "data": {
    "bone_indices": [1, 1, 1, ..., 1],         // 47 elements
    "bone_weights": [1.0, 1.0, ..., 1.0]       // 47 elements
  }
}
```

#### Node 2 (Sphere01) Raw Data:

```json
{
  "num_of_vertices": 52,
  "num_of_bones_per_batch": [1],
  "bone_offset_per_batch": [0],
  "bone_batch_indexes": [1, 0, 0, 0, ... 0],
  "data": {
    "bone_indices": [1, 1, 1, ..., 1],         // 52 elements
    "bone_weights": [1.0, 1.0, ..., 1.0]       // 52 elements
  }
}
```

---

## CODE-BY-CODE ANALYSIS

### Problem #1: JOINTS_0 Accessor Type

**File**: glb_compiler.py, lines 250-256

**Current Code**:
```python
if has_skin:
    num_vertices = len(vertices)
    acc_joints = Accessor(bufferView=skin_offset, byteOffset=0, 
                         componentType=5123, count=num_vertices, type="SCALAR")
    acc_weights = Accessor(bufferView=skin_offset + 1, byteOffset=0, 
                          componentType=5126, count=num_vertices, type="SCALAR")
    accessors.extend([acc_joints, acc_weights])
```

**Why It's Wrong**:
- `type="SCALAR"` means 1 value per vertex
- glTF2 spec requires `type="VEC4"` - exactly 4 joint indices per vertex
- componentType 5123 (uint16) is correct ✓
- But we're only counting 1 component, not 4

**Correct Implementation**:
```python
if has_skin:
    num_vertices = len(vertices)
    # JOINTS_0 should be VEC4 uint16
    acc_joints = Accessor(bufferView=skin_offset, byteOffset=0, 
                         componentType=5123, count=num_vertices, type="VEC4")
    # WEIGHTS_0 should be VEC4 float
    acc_weights = Accessor(bufferView=skin_offset + 1, byteOffset=0, 
                          componentType=5126, count=num_vertices, type="VEC4")
    accessors.extend([acc_joints, acc_weights])
```

**Data Format Required**:
```
JOINTS_0 buffer layout:
vertex 0: [u16, u16, u16, u16]  <- 4 joint indices
vertex 1: [u16, u16, u16, u16]
...

WEIGHTS_0 buffer layout:
vertex 0: [f32, f32, f32, f32]  <- 4 weights
vertex 1: [f32, f32, f32, f32]
...
```

---

### Problem #2: Bone Data Flattening

**File**: glb_compiler.py, lines 161-175

**Current Code**:
```python
if data.get("bone_indices") and data.get("bone_weights"):
    bone_indices = data["bone_indices"]
    bone_weights = data["bone_weights"]
    has_skin = True

    # flatten weird tuple/list structures safely
    flat_indices = list(itertools.chain.from_iterable(
        (v if isinstance(v, (list, tuple)) else [v]) for v in bone_indices
    ))
    flat_weights = list(itertools.chain.from_iterable(
        (v if isinstance(v, (list, tuple)) else [v]) for v in bone_weights
    ))

    joints_flat = align4(array.array('H', flat_indices).tobytes())
    weights_flat = align4(array.array('f', flat_weights).tobytes())
```

**What Happens**:
- Input: bone_indices = [0, 0, 0, ..., 0] (376 values)
- Output: flat_indices = [0, 0, 0, ..., 0] (still 376 values!)
- This creates 376 uint16 values in buffer
- But we need 376 × 4 = 1504 uint16 values!

**Why It's Wrong**:
- Doesn't expand scalar indices to VEC4
- Doesn't pad with zeros
- Data size mismatch with accessor (says VEC4 but only SCALAR data)

**Correct Implementation**:
```python
if data.get("bone_indices") and data.get("bone_weights"):
    bone_indices = data["bone_indices"]
    bone_weights = data["bone_weights"]
    has_skin = True

    # Expand to VEC4: pad each value to 4-element group
    flat_indices = []
    for idx in bone_indices:
        idx_val = idx if isinstance(idx, (list, tuple)) else idx
        if isinstance(idx_val, (list, tuple)):
            flat_indices.extend(idx_val + [0] * (4 - len(idx_val)))
        else:
            flat_indices.extend([idx_val, 0, 0, 0])
    
    flat_weights = []
    for w in bone_weights:
        w_val = w if isinstance(w, (list, tuple)) else w
        if isinstance(w_val, (list, tuple)):
            flat_weights.extend(w_val + [0.0] * (4 - len(w_val)))
        else:
            flat_weights.extend([w_val, 0.0, 0.0, 0.0])

    joints_flat = align4(array.array('H', flat_indices).tobytes())
    weights_flat = align4(array.array('f', flat_weights).tobytes())
```

**Example Transformation**:
```
Input:
  bone_indices = [0, 0, 0]
  bone_weights = [1.0, 1.0, 1.0]

Output:
  flat_indices = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
  flat_weights = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
```

---

### Problem #3: Skin Joints Array

**File**: glb_compiler.py, lines 418-439

**Current Code**:
```python
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
```

**Problems**:

1. **Incorrect Logic**: `if idx == 0: continue` skips bone 0
   - But bone 0 might be a valid joint!
   - Should check parent_index and skeleton markers instead

2. **Direct Node ID Usage**: Uses idx directly as bone_batch_indexes values
   - But bone_indices in vertices use different numbering!
   - Creates mismatch between vertex data and skin.joints

3. **No Index Mapping**: Doesn't create mapping from bone_indices values to Skin.joints indices
   - Vertex bone_indices = [0, 0, 0] expects joint 0
   - But Skin.joints might be [node_id_3, node_id_5, node_id_7]
   - Need to map: vertex index 0 → skin.joints[0]

**Correct Implementation**:
```python
# Build joint mapping for each mesh/node
skins = []
mesh_to_skin_index = {}

for node_id, node in config['nodes'].items():
    data = node.get('data')
    if not data:
        continue
    
    bone_batch = node.get('bone_batch_indexes', [])
    num_bones = node.get('num_of_bones_per_batch', [0])[0]
    
    if not bone_batch or num_bones == 0:
        continue
    
    # Get actual bone node IDs from bone_batch_indexes
    bone_node_ids = []
    for i in range(num_bones):
        bone_node_id = bone_batch[i]
        if bone_node_id >= 0:  # Valid bone ID
            bone_node_ids.append(bone_node_id)
    
    if not bone_node_ids:
        continue
    
    # Build Skin.joints array with correct indices
    joints = []
    for bone_node_id in bone_node_ids:
        # Convert bone_node_id to node index in gltf.nodes
        joint_idx = nid_to_index.get(bone_node_id)
        if joint_idx is not None:
            joints.append(joint_idx)
    
    if not joints:
        continue
    
    # Create mapping: bone_index (in vertex data) → joint index (in Skin.joints)
    # bone_indices in vertices refer to positions in bone_node_ids array
    # This mapping is implicit: vertex index i maps to joints[i]
    
    mesh_index = vertices_count_to_mesh_index.get(len(data.get('vertices', [])))
    if mesh_index is None:
        continue
    
    mesh = gltf.meshes[mesh_index]
    # ... skin creation code ...
```

---

### Problem #4: Missing Inverse Bind Matrices

**File**: glb_compiler.py, currently not implemented

**glTF2 Spec Requirement**:
- Every Skin MUST have inverseBindMatrices
- One 4x4 matrix per joint
- Transforms from world space to joint local space

**Current Code**: Lines 418-506 don't include inverseBindMatrices at all

**Correct Implementation**:
```python
import numpy as np
from scipy.spatial.transform import Rotation as R

def compute_inverse_bind_matrices(bones, nodes):
    """
    Compute inverse bind matrices for skeleton.
    
    Args:
        bones: List of (node_id, node_index) for skeleton joints
        nodes: List of gltf.nodes
    
    Returns:
        List of 4x4 matrices (16 floats each)
    """
    matrices = []
    
    for bone_node_id, joint_idx in bones:
        node = nodes[joint_idx]
        
        # Extract TRS from node
        trans = np.array(node.translation or [0, 0, 0], dtype=np.float32)
        rot = np.array(node.rotation or [0, 0, 0, 1], dtype=np.float32)
        scale = np.array(node.scale or [1, 1, 1], dtype=np.float32)
        
        # Build 4x4 transform matrix
        rot_matrix = R.from_quat(rot).as_matrix()
        scale_matrix = np.diag(scale)
        bind_matrix = rot_matrix @ scale_matrix
        
        # Combine with translation
        matrix_4x4 = np.eye(4)
        matrix_4x4[:3, :3] = bind_matrix
        matrix_4x4[:3, 3] = trans
        
        # Invert to get inverse bind matrix
        inv_bind = np.linalg.inv(matrix_4x4)
        
        # Flatten and append
        matrices.append(inv_bind.flatten().tolist())
    
    return matrices

# In compile_glb():
for node_id, node in config['nodes'].items():
    # ... existing code ...
    
    if not joints:
        continue
    
    # NEW: Compute inverse bind matrices
    inv_bind_data = compute_inverse_bind_matrices(
        [(nid, idx) for nid, idx in zip(bone_node_ids, joints)],
        gltf.nodes
    )
    
    # Pack inverse bind matrices into buffer
    inv_bind_flat = []
    for matrix in inv_bind_data:
        inv_bind_flat.extend(matrix)
    
    inv_bind_bytes = align4(array.array('f', inv_bind_flat).tobytes())
    
    base_offset = len(all_buffer_bytes)
    all_buffer_bytes += inv_bind_bytes
    
    bv_inv_bind = BufferView(buffer=0, byteOffset=base_offset, 
                            byteLength=len(inv_bind_bytes), target=34962)
    gltf.bufferViews.append(bv_inv_bind)
    bv_inv_bind_index = len(gltf.bufferViews) - 1
    
    # Create accessor for inverse bind matrices
    acc_inv_bind = Accessor(bufferView=bv_inv_bind_index, byteOffset=0,
                           componentType=5126, count=len(joints), type="MAT4")
    gltf.accessors.append(acc_inv_bind)
    acc_inv_bind_index = len(gltf.accessors) - 1
    
    # Add to skin
    skin = Skin(joints=joints, skeleton=joints[0], 
               inverseBindMatrices=acc_inv_bind_index)
```

---

### Problem #5: Skeleton Root

**File**: glb_compiler.py, line 504

**Current Code**:
```python
skin = Skin(joints=joints, skeleton=joints[0])
```

**Problem**:
- Sets skeleton to first joint in list
- But glTF2 spec requires the root of the skeleton
- For critter_konna: root should be node 3 (BoneBody1)

**Correct Implementation**:
```python
# Find skeleton root by traversing parent chain
def find_skeleton_root(joint_indices, nodes, node_parent_nid):
    """Find the topmost parent of a skeleton."""
    if not joint_indices:
        return None
    
    # Start with first joint and traverse up
    current = joint_indices[0]
    visited = set()
    
    while current is not None and current not in visited:
        visited.add(current)
        # Find parent node ID
        parent_nid = None
        for nid, idx in nid_to_index.items():
            if idx == current:
                parent_nid = node_parent_nid.get(nid)
                break
        
        if parent_nid is None or parent_nid == -1:
            return current
        
        parent_idx = nid_to_index.get(parent_nid)
        if parent_idx is None:
            return current
        
        current = parent_idx
    
    return current

# In skin creation:
skeleton_root = find_skeleton_root(joints, gltf.nodes, node_parent_nid)
skin = Skin(joints=joints, skeleton=skeleton_root, 
           inverseBindMatrices=acc_inv_bind_index)
```

---

## DATA FLOW EXAMPLE

### Scenario: Node 0 (GeoSphere01) with critter_konna skeleton

**Input POD Data**:
```
Node 0:
  num_of_vertices = 376
  num_of_bones_per_batch = [1]
  bone_batch_indexes = [3, 0, 0, ..., 0]
  bone_indices = [0, 0, 0, ..., 0]    (376 values)
  bone_weights = [1.0, 1.0, ..., 1.0] (376 values)
```

**Interpretation**:
- 376 vertices in mesh
- Each vertex affected by 1 bone (batch size = 1)
- The bone index is 0
- bone_batch_indexes[0] = 3 means bone index 0 → node ID 3
- Therefore all vertices are skinned to node 3 (BoneBody1)

**How To Fix Data Transformation**:

```python
# Step 1: Identify bone mapping for this mesh
num_bones_in_batch = node['num_of_bones_per_batch'][0]  # = 1
bone_batch_indices = node['bone_batch_indexes'][:num_bones_in_batch]
# bone_batch_indices = [3]
# This means: joint index 0 → bone node ID 3

# Step 2: Build glTF2 compatible data
bone_indices_raw = data['bone_indices']  # [0, 0, 0, ..., 0]
bone_weights_raw = data['bone_weights']  # [1.0, 1.0, ..., 1.0]

# Step 3: Expand to VEC4
vec4_indices = []
vec4_weights = []
for idx, weight in zip(bone_indices_raw, bone_weights_raw):
    # idx is 0, weight is 1.0
    vec4_indices.append([idx, 0, 0, 0])      # Pad to 4 values
    vec4_weights.append([weight, 0.0, 0.0, 0.0])

# Step 4: Build Skin.joints array
# bones_used = [3] from bone_batch_indexes
# Find node index for node ID 3 -> assume it's index 3 in gltf.nodes
# Skin.joints = [3]

# Step 5: Create accessors
# JOINTS_0: VEC4 uint16, 376 vertices = 1504 uint16 values
# WEIGHTS_0: VEC4 float, 376 vertices = 1504 float values

# Step 6: Bind vertex to joint
# vertex 0: JOINTS_0 = [0, 0, 0, 0]  (all reference joint 0)
#           WEIGHTS_0 = [1.0, 0.0, 0.0, 0.0]
# Skin.joints[0] = 3 (node ID in gltf.nodes)
# Therefore: vertex 0 is fully controlled by gltf.nodes[3] (BoneBody1)
```

---

## IMPLEMENTATION CHECKLIST

- [ ] Change JOINTS_0 type from "SCALAR" to "VEC4"
- [ ] Change WEIGHTS_0 type from "SCALAR" to "VEC4"
- [ ] Expand bone_indices to VEC4 (pad with zeros)
- [ ] Expand bone_weights to VEC4 (pad with zeros)
- [ ] Fix joints array to include all referenced bones
- [ ] Remove `if idx == 0: continue` check (or make it proper)
- [ ] Build inverse bind matrices from bind poses
- [ ] Add inverseBindMatrices accessor to Skin
- [ ] Set correct skeleton root node
- [ ] Test with glTF2 validator
- [ ] Test with Three.js or Babylon.js
- [ ] Test animation playback

---

## GLFW2 VALIDATION

After implementing fixes, validate with:

```bash
python -m gltf2 --validate critter_konna_green.glb
```

Or use: https://www.khronos.org/gltf/

Expected valid output:
```
✓ JOINTS_0 type: VEC4 ✓
✓ WEIGHTS_0 type: VEC4 ✓
✓ inverseBindMatrices: present ✓
✓ Skin.skeleton: valid ✓
✓ Skin.joints: valid ✓
```

