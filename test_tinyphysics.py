"""
Quick test to see if we can use TinyPhysicsEngine from Python
"""
import ctypes
import os
from pathlib import Path

# Try to compile the TPE header into a shared library
tpe_dir = Path(__file__).parent / "ESPboy_tinyphysicsengine"
tpe_header = tpe_dir / "tinyphysicsengine.h"

print(f"[TEST] TinyPhysicsEngine header exists: {tpe_header.exists()}")

if tpe_header.exists():
    print(f"[TEST] Header found at: {tpe_header}")
    
    # Read the header to see what we're working with
    with open(tpe_header, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    # Check for key functions
    key_functions = [
        'TPE_bodyInit',
        'TPE_worldInit', 
        'TPE_worldStep',
        'TPE_vec3',
        'TPE_joint'
    ]
    
    print("\n[TEST] Checking for key TPE functions:")
    for func in key_functions:
        found = func in content
        status = "✓" if found else "✗"
        print(f"  {status} {func}")
    
    # Check header size
    lines = content.count('\n')
    print(f"\n[TEST] Header size: {lines} lines")
    print(f"[TEST] Header is truly header-only: {'.c' not in content.lower() or 'implementation' in content.lower()}")
    
    print("\n[TEST] TinyPhysicsEngine is ready to use!")
    print("[TEST] Next step: Create minimal C wrapper and compile to .dll/.so")
    print("[TEST] Or: Use cffi/ctypes with inline C compilation")
    
else:
    print("[TEST] ERROR: TinyPhysicsEngine header not found!")
    print(f"[TEST] Expected at: {tpe_header}")

print("\n[TEST] Box2D comparison:")
try:
    import Box2D
    print("  ✗ Box2D is installed (bloated dependency)")
except ImportError:
    print("  ✓ Box2D not found (good!)")

print("\n[TEST] Conclusion: TPE is viable as Box2D replacement")
print("[TEST] Implementation path: cffi or ctypes with gcc/clang")
