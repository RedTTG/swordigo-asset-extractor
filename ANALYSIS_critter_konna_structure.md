# Critter_Konna_Green Model Analysis Report

## 1. NODE STRUCTURE ANALYSIS

### Complete Node Hierarchy

The model contains 16 nodes with the following structure:

#### Mesh Nodes (3):
- **Node 0**: GeoSphere01
  - Type: mesh
  - Parent: -1 (root)
  - Vertices: 376
  - Material: 0 (02 - Default)
  - num_of_bones_per_batch: [1]
  - bone_batch_indexes length: 1000 (first value is 3, rest are 0)
  - Bone Indices: 376 entries (all value 0)
  - Bone Weights: 376 entries (all value 1.0)
  
- **Node 1**: Box01
  - Type: mesh
  - Parent: -1 (root)
  - Vertices: 47
  - Material: 1 (01 - Default)
  - num_of_bones_per_batch: [2]
  - bone_batch_indexes length: 1000 (first value is 1, rest are 0)
  - Bone Indices: 47 entries (all value 1)
  - Bone Weights: 47 entries (all value 1.0)

- **Node 2**: Sphere01
  - Type: mesh
  - Parent: -1 (root)
  - Vertices: 52
  - Material: 2 (03 - Default)
  - num_of_bones_per_batch: [1]
  - bone_batch_indexes length: 1000 (first value is 1, rest are 0)
  - Bone Indices: 52 entries (all value 1)
  - Bone Weights: 52 entries (all value 1.0)

#### Bone/Structural Nodes (13):

- **Node -1 (ID: "3" after conversion)**: BoneBody1 [ROOT BONE]
  - Type: parent
  - Parent: null
  - Animation Flags: NONE
  - Has Position: true
  - Has Rotation: true
  - Children: Nodes 4, 5, 7

- **Node 4**: BoneBodyController
  - Type: unindexed (bone)
  - Parent: 3 (BoneBody1)
  - Animation Flags: NONE
  - Children: None

- **Node 5**: BoneRightLeg1
  - Type: unindexed (bone)
  - Parent: 3 (BoneBody1)
  - Animation Flags: NONE
  - Children: Node 6

- **Node 6**: BoneRightLegController
  - Type: unindexed (bone)
  - Parent: 5 (BoneRightLeg1)
  - Animation Flags: NONE
  - Children: None

- **Node 7**: BoneLeftLeg1
  - Type: unindexed (bone)
  - Parent: 3 (BoneBody1)
  - Animation Flags: NONE
  - Children: Node 8

- **Node 8**: BoneLeftLegController
  - Type: unindexed (bone)
  - Parent: 7 (BoneLeftLeg1)
  - Animation Flags: NONE
  - Children: None

- **Node 9**: Rectangle01 [IK RIG ROOT]
  - Type: unindexed
  - Parent: -1 (root)
  - Animation Flags: NONE
  - Children: Nodes 10, 12

- **Node 10**: LeftLegRig
  - Type: unindexed
  - Parent: 9 (Rectangle01)
  - Animation Flags: NONE
  - Children: Node 11

- **Node 11**: IK Chain01
  - Type: unindexed
  - Parent: 10 (LeftLegRig)
  - Animation Flags: NONE
  - Children: None

- **Node 12**: RightLegRig
  - Type: unindexed
  - Parent: 9 (Rectangle01)
  - Animation Flags: NONE
  - Children: Node 13

- **Node 13**: IK Chain02
  - Type: unindexed
  - Parent: 12 (RightLegRig)
  - Animation Flags: NONE
  - Children: None

- **Node 14**: CenterPoint
  - Type: unindexed
  - Parent: -1 (root)
  - Animation Flags: NONE
  - Children: None

- **Node 15**: Circle01
  - Type: unindexed
  - Parent: -1 (root)
  - Animation Flags: NONE
  - Children: None

### Hierarchy Visualization

```
ROOT
├── Node 0 (GeoSphere01) - MESH [376 verts]
├── Node 1 (Box01) - MESH [47 verts]
├── Node 2 (Sphere01) - MESH [52 verts]
├── Node 3 (BoneBody1) - BONE ROOT
│   ├── Node 4 (BoneBodyController) - BONE
│   ├── Node 5 (BoneRightLeg1) - BONE
│   │   └── Node 6 (BoneRightLegController) - BONE
│   └── Node 7 (BoneLeftLeg1) - BONE
│       └── Node 8 (BoneLeftLegController) - BONE
├── Node 9 (Rectangle01) - IK RIG
│   ├── Node 10 (LeftLegRig) - IK CHAIN
│   │   └── Node 11 (IK Chain01) - IK ENDPOINT
│   └── Node 12 (RightLegRig) - IK CHAIN
│       └── Node 13 (IK Chain02) - IK ENDPOINT
├── Node 14 (CenterPoint) - CONTROL
└── Node 15 (Circle01) - CONTROL
```

## 2. BONE AND SKIN STRUCTURE

### Bone Index Analysis

The critical discovery: **bone_indices arrays are INCORRECTLY STRUCTURED**

- **Node 0 (GeoSphere01)**:
  - bone_indices: [0, 0, 0, ..., 0] (all 376 vertices reference bone 0)
  - bone_weights: [1.0, 1.0, ..., 1.0] (all weight 1.0)
  - This is SCALAR data, NOT VEC4!
  - Currently generated as: 376 uint16 values
  - Should be: 376 VEC4 values (each vertex needs 4 joint indices)

- **Node 1 (Box01)**:
  - bone_indices: [1, 1, 1, ..., 1] (all 47 vertices reference bone 1)
  - bone_weights: [1.0, 1.0, ..., 1.0] (all weight 1.0)
  - Again SCALAR, NOT VEC4!
  - num_of_bones_per_batch: [2] - indicates 2 bones should be used

- **Node 2 (Sphere01)**:
  - bone_indices: [1, 1, 1, ..., 1] (all 52 vertices reference bone 1)
  - bone_weights: [1.0, 1.0, ..., 1.0] (all weight 1.0)
  - num_of_bones_per_batch: [1]

### Referenced Bones in Mesh Skinning

Node 0 (GeoSphere01) references bone index 0:
- This should map to actual bone node ID
- Currently unclear which bone this represents

Node 1 (Box01) and Node 2 (Sphere01) reference bone index 1:
- Need to identify what bone node index 1 represents

### Bone Batch Information

- bone_batch_indexes: Array of 1000 uint32 values
  - First value (index 0): Contains actual bone node references
  - Remaining 999 values: All zeros (padding)
  
- num_of_bones_per_batch: [value] array
  - Indicates how many bones are active per batch
  - Node 0: 1 bone per batch
  - Node 1: 2 bones per batch
  - Node 2: 1 bone per batch

- bone_offset_per_batch: [0] for all meshes
  - Offset into bone_batch_indexes array (always 0)

### Identified Skeleton

The actual bone skeleton consists of:
- Root: Node 3 (BoneBody1)
- Bone Joints:
  - Node 4 (BoneBodyController) - Body controller
  - Node 5 (BoneRightLeg1) - Right leg base
  - Node 6 (BoneRightLegController) - Right leg IK
  - Node 7 (BoneLeftLeg1) - Left leg base
  - Node 8 (BoneLeftLegController) - Left leg IK

## 3. ANIMATION RELATIONSHIPS

### Associated Animations

From animations_associations.json:
```json
"critter_konna": {
    "models": ["critter_konna_green"],
    "animations": ["critter_konna_walk"]
}
```

The model has only one animation: **critter_konna_walk**

### Animation Data Structure

All bones have animation data:
```
animation_position: [x, y, z] - bind pose position
animation_rotation: [qx, qy, qz, qw] - bind pose rotation
animation_flags: "NONE" - all bones have NONE flag
unknown_5009: [scale_x, scale_y, scale_z, axis_x, axis_y, axis_z, angle]
```

This "unknown_5009" field appears to contain:
- Scale vector (3 components)
- Axis-angle representation (3 components + 1 angle)

### Current Animation Handling in Code

From glb_compiler.py (lines 39-56):
1. Reads animation_position (translation)
2. Reads animation_rotation (quaternion)
3. Reads unknown_5009 for scale and bind rotation
4. Flips Z axis on both rotations
5. Combines rotations using scipy
6. Applies final transform to node

## 4. BONE BATCH INDEXES INTERPRETATION

The bone_batch_indexes array (1000 elements) represents:
- An allocation pool for bones per vertex
- First element(s) contain actual bone node IDs
- Remaining elements are padding

Example for Node 0:
```
bone_batch_indexes = [3, 0, 0, 0, 0, 0, 0, ...]
                      ^-- This is bone node ID 3 (BoneBody1)
```

Example for Node 1:
```
bone_batch_indexes = [1, 0, 0, 0, 0, 0, 0, ...]
                      ^-- First bone node ID is 1
```

## 5. glTF2 SPEC REQUIREMENTS vs. CURRENT IMPLEMENTATION

### glTF2 Skinning Requirements

#### JOINTS_0 Attribute:
- **Required Format**: VEC4 with componentType of 5123 (uint16) or 5125 (uint32)
- **Meaning**: 4 joint indices per vertex (XYZW = joint0, joint1, joint2, joint3)
- **Per Vertex Structure**: Must be exactly 4 values
- **Current Code**: Line 252-253, 468 of glb_compiler.py
  - Creates SCALAR type instead of VEC4 (WRONG!)
  - Uses uint16 which is correct component type
  - But counts only 1 component instead of 4

#### WEIGHTS_0 Attribute:
- **Required Format**: VEC4 with componentType 5126 (float) or normalized uint
- **Meaning**: Blend weights for 4 joints (must sum to 1.0)
- **Per Vertex Structure**: Must be exactly 4 values
- **Current Code**: Line 253-254, 469 of glb_compiler.py
  - Creates SCALAR type instead of VEC4 (WRONG!)
  - Uses float which is correct
  - But counts only 1 component instead of 4

#### Skin.joints Array:
- **Requirement**: List of node indices that are joints
- **Order Matters**: Index in array must correspond to joint index in JOINTS_0
- **Current Code**: Lines 430-436 in glb_compiler.py
  - Skips bones if idx == 0 (incorrect logic)
  - Uses node IDs from bone_batch_indexes array
  - Doesn't properly map to sequential joint indices

#### Skin.skeleton:
- **Requirement**: Index of root joint node
- **Current Code**: Line 504
  - Sets to joints[0] but should be root of skeleton hierarchy
  - Should be Node 3 (BoneBody1)

#### Inverse Bind Matrices:
- **Requirement**: Must provide inverseBindMatrices accessor
- **Current Code**: NOT IMPLEMENTED
  - Missing completely - should be identity or proper bind pose matrices

### Current Issues in Code

1. **JOINTS_0 Format Wrong**:
   ```python
   acc_joints = Accessor(bufferView=skin_offset, byteOffset=0, 
                        componentType=5123, count=num_vertices, type="SCALAR")
   # WRONG! Should be type="VEC4"
   ```

2. **WEIGHTS_0 Format Wrong**:
   ```python
   acc_weights = Accessor(bufferView=skin_offset + 1, byteOffset=0, 
                         componentType=5126, count=num_vertices, type="SCALAR")
   # WRONG! Should be type="VEC4"
   ```

3. **Bone Data Flattening Incorrect** (lines 167-172):
   - Flattens single-value bones into flat list
   - Doesn't expand to VEC4 (4 joints per vertex)
   - Needs to pad single bone indices to [bone_id, 0, 0, 0]

4. **Skin Joints Array Incomplete** (lines 430-436):
   - Filters with `if idx == 0: continue` - wrong logic
   - Doesn't properly number joints sequentially
   - Doesn't match joint indices in vertex data

5. **Missing Inverse Bind Matrices**:
   - glTF2 spec requires inverseBindMatrices
   - Currently skipped entirely
   - Should calculate from bind pose transforms

## 6. POD FILE FORMAT UNDERSTANDING

### POD Data Structure (from pod_decoder.py)

POD files are binary with tagged blocks:
- Header: 8 bytes (block_type:2, tag:2, size:4)
- Data: size bytes
- Tags: 0x0000 (START) or 0x8000 (END)

### Key POD Block Types for Nodes:

- 5000: Node Index (establishes node ID)
- 5001: Node Name (string)
- 5003: Node Parent Index (parent reference)
- 5007: Node Animation Position (float[3])
- 5008: Node Animation Rotation (float[4] quaternion)
- 5009: Node Info UNKNOWN (float[7] - scale + axis-angle)
- 5012: Node Animation Flags (uint32)

### Key POD Block Types for Meshes:

- 6000-6005: Mesh metadata (vertex count, face count, etc.)
- 6015: Mesh Bone Batch Index List (uint32 array)
- 6016: Mesh Number of Bones per Batch (uint32 array)
- 6017: Mesh Bone Offset per Batch (uint32 array)
- 6020: Mesh Unpack Matrix (float[16] transformation)

### Data Type Handlers (from pod_data_handlers.py):

- Type 1: Signed 32-bit float (4 bytes each)
- Type 2: Unsigned 32-bit integer (4 bytes each)
- Type 3: Unsigned 16-bit short (2 bytes each)
- Type 5: ARGB float (16 bytes = 4 floats)

### Mesh Data Assembly (lines 505-521 pod_decoder.py):

9 data blocks per mesh:
1. indices - triangle indices
2. vertices - positions
3. normals - face normals
4. (tangent data - unused)
5. (binormal data - unused)
6. uvs - texture coordinates
7. (vertex colors - unused)
8. bone_indices - joint indices per vertex
9. bone_weights - blend weights per vertex

## 7. CRITICAL FINDINGS AND ISSUES

### Issue #1: Bone Indices are SCALAR, Not VEC4

**Current State**:
- bone_indices stores single values per vertex (SCALAR)
- Examples: [0, 0, 0, ...] or [1, 1, 1, ...]
- Only one bone per vertex, weight 1.0

**Required for glTF2**:
- VEC4 of joint indices per vertex
- Must provide 4 joint IDs (or 0-fill if less than 4)
- Must have corresponding weights

**Fix Required**:
- Expand bone_indices from scalar to VEC4
- Convert bone_indices[i] to [bone_indices[i], 0, 0, 0]
- Convert bone_weights[i] to [bone_weights[i], 0.0, 0.0, 0.0]

### Issue #2: Joint Index Mapping Undefined

**Current State**:
- bone_indices contain values like 0 and 1
- These don't directly map to bone node IDs
- bone_batch_indexes holds actual node IDs

**Example**:
- Node 0 mesh has bone_indices=[0, 0, 0, ...]
- bone_batch_indexes[0:1] = [3]
- So joint index 0 → bone node ID 3

**Fix Required**:
- Build joint mapping: bone_index → bone_node_id
- Use num_of_bones_per_batch to know how many bones
- Create sequential Skin.joints array
- Update vertex bone_indices to use sequential indices

### Issue #3: Skeleton Root Not Set

**Current Code**: `skeleton=joints[0]` (line 504)

**Problem**: 
- joints[0] might not be skeleton root
- Should be node 3 (BoneBody1)

**Fix Required**:
- Identify skeleton root node
- Set skin.skeleton = root_node_index

### Issue #4: Missing Inverse Bind Matrices

**Required by glTF2 Spec**: Yes
**Currently Implemented**: No

**Fix Required**:
- Calculate inverse bind matrices from bind poses
- Create accessor and bufferView for inverseBindMatrices
- Add to Skin object: skin.inverseBindMatrices = accessor_index

## 8. RECOMMENDATIONS

### High Priority Fixes:

1. **Fix JOINTS_0 and WEIGHTS_0 Formats**:
   - Change from SCALAR to VEC4
   - Update componentType correctly
   - Ensure proper 4-value padding

2. **Implement Joint Index Mapping**:
   - Create mapping from bone_indices values to bone_node_ids
   - Build correct Skin.joints array
   - Update vertex bone_indices to use sequential indices

3. **Fix Skeleton Root**:
   - Identify and set correct skeleton root
   - For critter_konna: should be node 3 (BoneBody1)

4. **Implement Inverse Bind Matrices**:
   - Calculate from bind pose data
   - Store in buffer
   - Reference in Skin object

### Medium Priority:

5. Handle multi-bone skinning properly
6. Verify weight normalization (sum to 1.0)
7. Test with animations

### Low Priority:

8. Optimize bone_batch_indexes padding
9. Better documentation of POD format

