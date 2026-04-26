# Quick Reference: critter_konna_green Model Issues & Fixes

## The Problem in 30 Seconds

The glTF2 compiler generates **INVALID skinning data**:
- JOINTS_0: Currently SCALAR, should be VEC4
- WEIGHTS_0: Currently SCALAR, should be VEC4  
- inverseBindMatrices: Missing (required by spec)
- Skeleton root: Wrong node
- Joint mapping: Incomplete

**Result**: Model skeleton doesn't work in any glTF2 viewer.

---

## 5 Issues to Fix

| # | Issue | File | Lines | Severity | Fix |
|---|-------|------|-------|----------|-----|
| 1 | JOINTS_0 type="SCALAR" | glb_compiler.py | 252 | CRITICAL | Change to type="VEC4" |
| 2 | WEIGHTS_0 type="SCALAR" | glb_compiler.py | 253 | CRITICAL | Change to type="VEC4" |
| 3 | Bone data not VEC4 | glb_compiler.py | 161-175 | CRITICAL | Pad indices/weights to 4 values |
| 4 | No inverseBindMatrices | glb_compiler.py | 418-506 | HIGH | Compute and add MAT4 accessor |
| 5 | Skeleton root wrong | glb_compiler.py | 504 | HIGH | Find true skeleton root |

---

## Data Structure Quick Facts

### Mesh Nodes
- Node 0: GeoSphere01 (376 verts) - body
- Node 1: Box01 (47 verts) - eyes
- Node 2: Sphere01 (52 verts) - pupils

### Bone Nodes
- Node 3: BoneBody1 (ROOT) ← Should be Skin.skeleton
- Node 4: BoneBodyController
- Node 5: BoneRightLeg1 → Node 6: BoneRightLegController
- Node 7: BoneLeftLeg1 → Node 8: BoneLeftLegController

### Key Data
- bone_indices: Small integers (0, 1) - indices into bone_batch_indexes!
- bone_batch_indexes: Actual bone node IDs [3, 1, ...]
- num_of_bones_per_batch: How many bones affect mesh [1, 2, 1]

### Mapping
```
bone_indices[i] = 0 → bone_batch_indexes[0] = 3 → gltf.nodes[3]
bone_indices[i] = 1 → bone_batch_indexes[1] = 1 → gltf.nodes[1]
```

---

## Quick Code Fixes

### Fix #1: Accessor Types
```python
# Line 252-253, CHANGE FROM:
acc_joints = Accessor(..., type="SCALAR")
acc_weights = Accessor(..., type="SCALAR")

# TO:
acc_joints = Accessor(..., type="VEC4")
acc_weights = Accessor(..., type="VEC4")
```

### Fix #2: Expand Data to VEC4
```python
# Lines 161-175, CHANGE FROM:
flat_indices = list(itertools.chain.from_iterable(...))
flat_weights = list(itertools.chain.from_iterable(...))

# TO:
flat_indices = []
for idx in bone_indices:
    flat_indices.extend([idx, 0, 0, 0])
flat_weights = []
for w in bone_weights:
    flat_weights.extend([w, 0.0, 0.0, 0.0])
```

### Fix #3: Add Inverse Bind Matrices
```python
# After line 502, ADD:
inv_bind_matrices = compute_inverse_bind_matrices(bones, gltf.nodes)
# Create accessor for MAT4 data
# Add to buffer
# Set skin.inverseBindMatrices = accessor_index
```

---

## Validation

After fixes, verify:
```bash
# Syntax check
python -m py_compile glb_compiler.py

# glTF2 validation (if gltf2 module installed)
python -m gltf2 --validate output.glb

# Manual checks:
# 1. JOINTS_0 is VEC4
# 2. WEIGHTS_0 is VEC4
# 3. Skin.joints includes only bones (nodes 3-8, not 9-15)
# 4. Skin.skeleton = 3 (BoneBody1)
# 5. inverseBindMatrices accessor exists
```

---

## Files Generated

1. **EXECUTIVE_SUMMARY.md** - Overview and findings
2. **ANALYSIS_critter_konna_structure.md** - Complete structure analysis
3. **TECHNICAL_SPECIFICATION_skinning.md** - Detailed fixes with code examples
4. **QUICK_REFERENCE.md** - This file

---

## Animation Status

- Animation exists: critter_konna_walk
- Has bind poses in nodes (animation_position, animation_rotation)
- NOT implemented in glTF2 compiler yet
- Fix skeleton first, then tackle animations

---

## Testing Checklist

- [ ] Code changes compile
- [ ] glTF2 spec validation passes
- [ ] Loads in Three.js viewer
- [ ] Loads in Babylon.js viewer
- [ ] Skeleton visible in viewer
- [ ] Model deforms when joints animated
- [ ] Animation playback works

