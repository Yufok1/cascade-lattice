"""
CASCADE-LATTICE Interactive Demo

Launch the LunarLander demo showcasing:
- cascade.hold: Human-in-the-loop intervention
- cascade.store: Provenance tracking  
- Merkle-chained decision records

Usage:
    cascade-demo              # Run the demo
    python -m cascade.demo    # Alternative

Controls:
    [H] HOLD-FREEZE   - Pause time, inspect AI decision
    [T] HOLD-TAKEOVER - Continue time, YOU control with WASD
    [ESC] Release hold, return to AI sovereignty
    
    In HOLD modes:
        [W] Main Engine (thrust up)
        [A] Left Engine (rotate)
        [D] Right Engine (rotate)  
        [S] No-op / Accept AI decision
"""

import sys
import subprocess
from pathlib import Path


def check_demo_dependencies():
    """Check if demo dependencies are installed."""
    missing = []
    
    try:
        import gymnasium
    except ImportError:
        missing.append("gymnasium")
    
    try:
        import pygame
    except ImportError:
        missing.append("pygame")
    
    try:
        import stable_baselines3
    except ImportError:
        missing.append("stable-baselines3")
    
    try:
        import box2d
    except ImportError:
        missing.append("box2d-py")
    
    return missing


def main():
    """Launch the interactive CASCADE-LATTICE demo."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║     ██████╗ █████╗ ███████╗ ██████╗ █████╗ ██████╗ ███████╗                  ║
║    ██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝                  ║
║    ██║     ███████║███████╗██║     ███████║██║  ██║█████╗                    ║
║    ██║     ██╔══██║╚════██║██║     ██╔══██║██║  ██║██╔══╝                    ║
║    ╚██████╗██║  ██║███████║╚██████╗██║  ██║██████╔╝███████╗                  ║
║     ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚══════╝                  ║
║                                                                               ║
║              LATTICE DEMO - Sovereign Neural Internetwork Control             ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Check dependencies
    missing = check_demo_dependencies()
    if missing:
        print(f"[!] Missing demo dependencies: {', '.join(missing)}")
        print()
        print("    Install with:")
        print("    pip install cascade-lattice[demo]")
        print()
        print("    Or manually:")
        print(f"    pip install {' '.join(missing)}")
        sys.exit(1)
    
    # Check for rl-zoo3 (needed for model download)
    try:
        import rl_zoo3
    except ImportError:
        print("[!] Missing rl-zoo3 (needed for pretrained model)")
        print("    pip install rl-zoo3")
        sys.exit(1)
    
    print("[CASCADE] Starting LunarLander demo...")
    print()
    print("Controls:")
    print("  [H] HOLD-FREEZE   - Pause time, inspect AI decision")
    print("  [T] HOLD-TAKEOVER - Continue time, YOU control with WASD")
    print("  [ESC] Release hold / Quit")
    print()
    print("In HOLD modes:")
    print("  [W] Main Engine   [A] Left Engine   [D] Right Engine")
    print("  [S] Accept AI choice / No-op")
    print()
    
    # Run the demo
    demo_path = Path(__file__).parent.parent / "examples" / "sovereign_lattice_eval.py"
    
    if not demo_path.exists():
        # Try installed package location
        import cascade
        package_dir = Path(cascade.__file__).parent
        demo_path = package_dir.parent / "examples" / "sovereign_lattice_eval.py"
    
    if not demo_path.exists():
        # Fallback: run inline demo
        print("[!] Demo file not found. Running inline version...")
        _run_inline_demo()
        return
    
    # Run the demo script
    subprocess.run([sys.executable, str(demo_path)])


def _run_inline_demo():
    """Minimal inline demo if main file not found."""
    import gymnasium as gym
    import numpy as np
    
    from cascade import init
    from cascade.hold import Hold
    from cascade.store import observe
    
    init(project="cascade_demo")
    hold = Hold.get()
    
    print("[CASCADE] Running minimal demo (install full package for GUI)")
    print()
    
    env = gym.make("LunarLander-v3")
    obs, _ = env.reset()
    
    for step in range(100):
        # Random policy for minimal demo
        action_probs = np.array([0.25, 0.25, 0.25, 0.25])
        
        resolution = hold.yield_point(
            action_probs=action_probs,
            value=0.0,
            observation={"state": obs.tolist()[:4]},
            brain_id="random_demo",
            action_labels=["NOOP", "LEFT", "MAIN", "RIGHT"],
            blocking=False
        )
        
        obs, reward, term, trunc, _ = env.step(resolution.action)
        
        observe("demo", {
            "step": step,
            "action": int(resolution.action),
            "reward": float(reward),
            "merkle": resolution.merkle_root,
        }, sync=False)
        
        if term or trunc:
            print(f"[CASCADE] Episode ended at step {step}")
            break
    
    env.close()
    print("[CASCADE] Demo complete. Check ~/.cascade/lattice for provenance data.")


if __name__ == "__main__":
    main()
