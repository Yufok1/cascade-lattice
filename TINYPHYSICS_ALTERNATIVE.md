# TinyPhysicsEngine - A Lightweight Box2D Alternative

## Why TinyPhysicsEngine?

Box2D has become problematic with installation issues, build dependencies, and platform compatibility problems. **TinyPhysicsEngine (TPE)** is a superior alternative for CASCADE-LATTICE demos.

## Key Advantages

### 1. **Zero Dependencies**
- Pure C99 header-only library
- No build system required
- No dynamic allocation (malloc)
- No standard library dependencies (except stdint)
- **No compilation nightmares like Box2D**

### 2. **Truly Free**
- CC0 Public Domain (not just "open source")
- No licensing worries
- No patents, trademarks, or IP restrictions
- Do whatever you want with it

### 3. **Embedded-Ready**
- Runs on 32 kB RAM devices
- Fixed-point math (no floating point unit needed)
- Tested on embedded systems like Pokitto (48 MHz CPU)
- Perfect for resource-constrained environments

### 4. **Simple & Hackable**
- KISS/suckless philosophy
- Well-commented, readable code
- Easy to modify and extend
- No PhD-level math required

## Technical Comparison

| Feature | Box2D | TinyPhysicsEngine |
|---------|-------|-------------------|
| Dependencies | Many (SWIG, C++ compiler, etc.) | None |
| Installation | Often fails on Windows | Copy header file |
| License | Zlib (restrictive) | CC0 Public Domain |
| Language | C++ | Pure C99 |
| Math | Floating point | Fixed point (32-bit int) |
| Size | Large codebase | Single header file |
| Build System | CMake/complex | None needed |

## Integration Path for CASCADE-LATTICE

### Current Problem
```bash
pip install box2d-py  # FAILS on Windows
# Error: Microsoft Visual C++ 14.0 or greater is required
```

### TinyPhysicsEngine Solution
```c
#include "tinyphysicsengine.h"  // That's it!
```

## Use Cases for CASCADE

- **Lunar Lander Demo**: Replace Box2D physics with TPE soft bodies
- **Provenance Tracking**: Simpler physics = clearer decision chains
- **Embedded Deployment**: Run CASCADE on resource-constrained devices
- **Educational**: Students can actually understand the physics code

## Repository

**Original**: https://github.com/ESPboy-edu/ESPboy_tinyphysicsengine

**Cloned locally**: `./ESPboy_tinyphysicsengine/`

## Next Steps

1. Create Python bindings using ctypes (no compilation needed!)
2. Replace LunarLander-v3 environment with TPE-based physics
3. Demonstrate CASCADE HOLD system with simpler, more transparent physics
4. Eliminate Box2D dependency hell forever

## Philosophy Alignment

TinyPhysicsEngine embodies the same principles as CASCADE-LATTICE:
- **Sovereignty**: No corporate dependencies
- **Transparency**: Readable, hackable code
- **Accessibility**: Works everywhere, for everyone
- **Freedom**: True public domain

---

*"Why does this exist? Because all other engines suck, they are either trivial or bloated, have licensing conditions, dependencies, require floating point unit, complex build systems, bad languages, PhD level math etcetc."* - drummyfish (TPE creator)

Box2D is dead. Long live TinyPhysicsEngine.
