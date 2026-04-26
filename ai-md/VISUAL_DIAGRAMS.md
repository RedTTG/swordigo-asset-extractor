# Visual Diagrams: critter_konna_green Structure

## 1. Complete Node Hierarchy

```
SCENE ROOT
│
├─ [0] GeoSphere01 ─ MESH (376 verts)
│                  └─ Material: "02 - Default" (body texture)
│                  └─ Skinned to: Node 3 (BoneBody1)
│
├─ [1] Box01 ────── MESH (47 verts)
│                  └─ Material: "01 - Default" (eyes)
│                  └─ Skinned to: Node 1 (?)
│
├─ [2] Sphere01 ──── MESH (52 verts)
│                   └─ Material: "03 - Default" (pupils)
│                   └─ Skinned to: Node 1 (?)
│
├─ [3] BoneBody1 ─── BONE (SKELETON ROOT)
│      │            └─ animation_position: [x, y, z]
│      │            └─ animation_rotation: [qx, qy, qz, qw]
│      │
│      ├─ [4] BoneBodyController ─ BONE (Controller)
│      │                           └─ Parent: 3
│      │
│      ├─ [5] BoneRightLeg1 ────── BONE (Right Leg Base)
│      │      └─ animation_position: [3.93, 10.42, -0.94]
│      │      └─ animation_rotation: [≈0, -0.999, ≈0, -0.009]
│      │
│      │   └─ [6] BoneRightLegController ─ BONE (Right Leg IK)
│      │                                   └─ Parent: 5
│      │
│      └─ [7] BoneLeftLeg1 ───────── BONE (Left Leg Base)
│             └─ animation_position: [3.93, -8.69, -0.94]
│             └─ animation_rotation: [≈0, -0.999, ≈0, -0.009]
│
│         └─ [8] BoneLeftLegController ─ BONE (Left Leg IK)
│                                       └─ Parent: 7
│
├─ [9] Rectangle01 ─── RIG (IK Root - NOT A BONE!)
│      │               └─ children: [10, 12]
│      │
│      ├─ [10] LeftLegRig ──────── RIG (NOT A BONE)
│      │       └─ [11] IK Chain01 ─ RIG (NOT A BONE)
│      │
│      └─ [12] RightLegRig ─────── RIG (NOT A BONE)
│              └─ [13] IK Chain02 ─ RIG (NOT A BONE)
│
├─ [14] CenterPoint ──── RIG (NOT A BONE)
│
└─ [15] Circle01 ───── RIG (NOT A BONE)
```

**Critical Note**: Nodes 9-15 are IK rigs and control objects, NOT bones. Only nodes 3-8 should be in Skin.joints!

---

## 2. Bone Skinning Architecture

```
                    ┌─────────────────────────┐
                    │   GeoSphere01 (Node 0)  │
                    │   376 Vertices          │
                    └────────────┬────────────┘
                                 │
                     ┌───────────┴───────────┐
                     │                       │
            bone_indices array    bone_batch_indexes array
            ┌─────────────────┐   ┌──────────────────────┐
            │ [0, 0, 0, ... ] │   │ [3, 0, 0, 0, ... ]   │
            │ 376 values      │   │ 1000 values (padded)  │
            └────────┬────────┘   └──────────┬───────────┘
                     │                       │
                     └───────────┬───────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Index Mapping:          │
                    │ bone_indices[i] = 0     │
                    │ → bone_batch_indexes[0] │
                    │ = 3                     │
                    └─────────┬────────────┬──┘
                              │            │
                    ┌─────────▼────┐  ┌───▼──────────┐
                    │ Skin.joints  │  │ Bone Node ID │
                    │ = [gltf_idx] │  │ = 3          │
                    └──────────────┘  └──────┬───────┘
                                             │
                                    ┌────────▼────────┐
                                    │ gltf.nodes[3]   │
                                    │ BoneBody1       │
                                    │ (SKELETON ROOT) │
                                    └─────────────────┘
```

---

## 3. Current (Broken) Data Layout

```
POD Input:
┌─────────────────────────────────────────────┐
│ Node 0 (GeoSphere01)                        │
├─────────────────────────────────────────────┤
│ bone_indices:    [0, 0, 0, ..., 0]          │
│                  ^─ 376 SCALAR uint16 values│
│                                             │
│ bone_weights:    [1.0, 1.0, 1.0, ..., 1.0] │
│                  ^─ 376 SCALAR float values │
│                                             │
│ bone_batch_idx:  [3, 0, 0, ..., 0]         │
│                  ^─ 1000 padding values     │
│                  maps bone_indices → nodes  │
│                                             │
│ num_of_bones_per_batch: [1]                │
│                  ^─ Use first 1 bone       │
└─────────────────────────────────────────────┘
        ↓ (glb_compiler.py - WRONG!)
GLB Output:
┌─────────────────────────────────────────────┐
│ JOINTS_0 Accessor                           │
│ ├─ type: "SCALAR" ← WRONG! Should be VEC4  │
│ ├─ componentType: 5123 (uint16) ✓           │
│ ├─ count: 376 ✓                             │
│ └─ data: [0, 0, 0, ..., 0]                 │
│          ^─ 376 uint16 values ✗            │
│          (should be 1504 = 376 × 4)        │
│                                             │
│ WEIGHTS_0 Accessor                          │
│ ├─ type: "SCALAR" ← WRONG! Should be VEC4  │
│ ├─ componentType: 5126 (float) ✓            │
│ ├─ count: 376 ✓                             │
│ └─ data: [1.0, 1.0, 1.0, ..., 1.0]        │
│          ^─ 376 float values ✗             │
│          (should be 1504 = 376 × 4)        │
│                                             │
│ Skin.skeleton: joints[0] ← WRONG! Could be │
│                any node, not root          │
│                                             │
│ Skin.joints: [node_idx] ← Incomplete!      │
│             Missing mapping info            │
│                                             │
│ inverseBindMatrices: null ← MISSING!       │
│                (Required by glTF2 spec)    │
└─────────────────────────────────────────────┘
```

---

## 4. Fixed (Correct) Data Layout

```
POD Input:
┌──────────────────────────────────────────────────┐
│ Node 0 (GeoSphere01)                             │
├──────────────────────────────────────────────────┤
│ bone_indices:    [0, 0, 0, ..., 0]              │
│ bone_weights:    [1.0, 1.0, 1.0, ..., 1.0]     │
│ bone_batch_idx:  [3, 0, 0, ..., 0]             │
│ num_of_bones_per_batch: [1]                     │
└──────────────────────────────────────────────────┘
        ↓ (glb_compiler.py - FIXED)
Transform Step 1: Identify bone mapping
┌──────────────────────────────────────────────────┐
│ num_bones = 1                                    │
│ bone_node_ids = bone_batch_indexes[0:1] = [3]   │
│                                                  │
│ Build Skin.joints:                               │
│ - Node ID 3 → gltf.nodes[3]                     │
│ - Skin.joints = [3]                             │
└──────────────────────────────────────────────────┘
        ↓
Transform Step 2: Expand bone data to VEC4
┌──────────────────────────────────────────────────┐
│ For each vertex:                                 │
│   bone_indices[i] = 0                            │
│   → Expand to VEC4: [0, 0, 0, 0]                │
│   bone_weights[i] = 1.0                          │
│   → Expand to VEC4: [1.0, 0.0, 0.0, 0.0]       │
│                                                  │
│ Result:                                          │
│ flat_indices:  [0,0,0,0, 0,0,0,0, ..., 0,0,0,0]│
│               376 × 4 = 1504 uint16 values       │
│ flat_weights: [1.0,0,0,0, 1.0,0,0,0, ...]      │
│               376 × 4 = 1504 float values        │
└──────────────────────────────────────────────────┘
        ↓
Transform Step 3: Compute inverse bind matrices
┌──────────────────────────────────────────────────┐
│ For each joint in Skin.joints:                   │
│   Extract node TRS                               │
│   Build 4×4 transform matrix                     │
│   Invert to get inverse bind matrix              │
│                                                  │
│ Result: 1 matrix (4×4 = 16 floats per joint)   │
└──────────────────────────────────────────────────┘
        ↓
GLB Output (VALID glTF2):
┌──────────────────────────────────────────────────┐
│ JOINTS_0 Accessor                                │
│ ├─ type: "VEC4" ✓ CORRECT                       │
│ ├─ componentType: 5123 (uint16) ✓                │
│ ├─ count: 376 ✓                                  │
│ └─ data: [0,0,0,0, 0,0,0,0, ..., 0,0,0,0]     │
│          ^─ 1504 uint16 values ✓                │
│          (376 vertices × 4 components)          │
│                                                  │
│ WEIGHTS_0 Accessor                               │
│ ├─ type: "VEC4" ✓ CORRECT                       │
│ ├─ componentType: 5126 (float) ✓                │
│ ├─ count: 376 ✓                                  │
│ └─ data: [1.0,0,0,0, 1.0,0,0,0, ...]           │
│          ^─ 1504 float values ✓                 │
│          (376 vertices × 4 components)          │
│                                                  │
│ inverseBindMatrices Accessor ✓                   │
│ ├─ type: "MAT4"                                  │
│ ├─ componentType: 5126 (float)                   │
│ ├─ count: 1 (one matrix per joint)               │
│ └─ data: [16 floats = 4×4 matrix]               │
│                                                  │
│ Skin object:                                     │
│ ├─ skeleton: 3 (BoneBody1 - ROOT) ✓             │
│ ├─ joints: [3] ✓ (only bones, no IK rigs)       │
│ └─ inverseBindMatrices: [accessor_index] ✓      │
│                                                  │
│ Result: ✓ VALID glTF2!                          │
└──────────────────────────────────────────────────┘
```

---

## 5. Issue Timeline

```
Problem Detection Chain:
┌──────────────────────────────┐
│ 1. JOINTS_0 = "SCALAR"       │ ← First Issue
│    (should be "VEC4")        │
├──────────────────────────────┤
│ 2. WEIGHTS_0 = "SCALAR"      │ ← Parallel Issue
│    (should be "VEC4")        │
├──────────────────────────────┤
│ 3. Data only 376 values      │ ← Data Size Mismatch
│    (should be 1504)          │
├──────────────────────────────┤
│ 4. No bone padding to 4      │ ← Root Cause
│                              │   (not VEC4 expanded)
├──────────────────────────────┤
│ 5. No inverseBindMatrices    │ ← Separate Issue
│    (spec violation)          │
├──────────────────────────────┤
│ 6. Skeleton root is wrong    │ ← Hierarchy Issue
│    (joints[0] instead of 3)  │
├──────────────────────────────┤
│ 7. Joint mapping incomplete  │ ← Logical Issue
│    (indices don't map)       │
└──────────────────────────────┘
```

---

## 6. Bone Hierarchy with Bind Poses

```
Skeleton Root: Node 3 (BoneBody1)
├─ Translation: [x, y, z] (world position)
├─ Rotation: [qx, qy, qz, qw] (quaternion)
├─ Scale: [sx, sy, sz] (from unknown_5009)
│
├─ Child 1: Node 4 (BoneBodyController)
│   ├─ Translation: [33.8, 0, 0]
│   ├─ Rotation: [≈0, ≈0, ≈0, 1.0]
│   └─ Purpose: Body control point
│
├─ Child 2: Node 5 (BoneRightLeg1) ← Right Leg
│   ├─ Translation: [3.93, 10.42, -0.94]
│   ├─ Rotation: [0, -0.999, 0, -0.009]
│   ├─ Connected to: BoneBody1
│   │
│   └─ Child: Node 6 (BoneRightLegController)
│       ├─ Translation: [10.37, 0, 0]
│       ├─ Rotation: [0.000005, 0, 0, 1.0]
│       └─ Purpose: IK control for right leg
│
└─ Child 3: Node 7 (BoneLeftLeg1) ← Left Leg
    ├─ Translation: [3.93, -8.69, -0.94]
    ├─ Rotation: [0, -0.999, 0, -0.009]
    ├─ Connected to: BoneBody1
    │
    └─ Child: Node 8 (BoneLeftLegController)
        ├─ Translation: [10.37, 0, 0]
        ├─ Rotation: [0.000005, 0, 0, 1.0]
        └─ Purpose: IK control for left leg
```

---

## 7. Comparison: Current vs Required glTF2

```
╔══════════════════════════════════════════════════════════════╗
║                   GLTF2 COMPLIANCE MATRIX                   ║
╠════════════════════════╦══════════════╦══════════════════════╣
║ Requirement            ║ Current      ║ Required             ║
╠════════════════════════╬══════════════╬══════════════════════╣
║ JOINTS_0 type          ║ SCALAR ✗     ║ VEC4 ✓               ║
║ JOINTS_0 component     ║ uint16 ✓     ║ uint16 ✓             ║
║ JOINTS_0 data size     ║ 376 ✗        ║ 1504 ✓               ║
╠════════════════════════╬══════════════╬══════════════════════╣
║ WEIGHTS_0 type         ║ SCALAR ✗     ║ VEC4 ✓               ║
║ WEIGHTS_0 component    ║ float ✓      ║ float ✓              ║
║ WEIGHTS_0 data size    ║ 376 ✗        ║ 1504 ✓               ║
╠════════════════════════╬══════════════╬══════════════════════╣
║ inverseBindMatrices    ║ missing ✗    ║ required ✓           ║
║ Skin.skeleton valid    ║ maybe ✗      ║ node 3 ✓             ║
║ Skin.joints           ║ incomplete ✗  ║ [3] ✓                ║
╚════════════════════════╩══════════════╩══════════════════════╝

Current Score: 3/10 ✗ INVALID
After Fixes:   10/10 ✓ VALID
```

---

## 8. Animation Flow (Future Implementation)

```
Animation File: critter_konna_walk.POD
         ↓
POD Decoder
         ↓
Animation Data Structure:
┌─────────────────────────────────────┐
│ Frame 0:                            │
│  Node 3: pos, rot, scale            │
│  Node 4: pos, rot, scale            │
│  Node 5: pos, rot, scale  ← animated│
│  Node 6: pos, rot, scale  ← animated│
│  Node 7: pos, rot, scale  ← animated│
│  Node 8: pos, rot, scale  ← animated│
│                                     │
│ Frame 1:                            │
│  ... (new positions/rotations)      │
│                                     │
│ ... more frames ...                 │
└─────────────────────────────────────┘
         ↓
glTF2 AnimationSampler (not yet implemented)
         ↓
GLB Output Animation Tracks
         ↓
Runtime (Three.js, Babylon.js, etc.)
         ↓
Model Deformation Based on Skeleton
```

