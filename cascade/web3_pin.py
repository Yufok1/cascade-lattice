"""
Pin lattice to web3.storage (Filecoin-backed permanence).

Usage:
    python -m cascade.web3_pin --token YOUR_TOKEN
"""

import os
import json
import argparse
import requests
from pathlib import Path

WEB3_STORAGE_API = "https://api.web3.storage"

def pin_file(filepath: Path, token: str) -> dict:
    """Pin a single file to web3.storage."""
    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{WEB3_STORAGE_API}/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filepath.name, f)},
        )
    resp.raise_for_status()
    return resp.json()

def pin_lattice(token: str, lattice_dir: Path = None):
    """Pin all lattice CBOR files."""
    if lattice_dir is None:
        lattice_dir = Path(__file__).parent.parent / "lattice" / "ipld"
    
    results = {}
    
    for cbor_file in lattice_dir.glob("*.cbor"):
        print(f"Pinning {cbor_file.name}...")
        result = pin_file(cbor_file, token)
        cid = result.get("cid")
        results[cbor_file.stem] = cid
        print(f"  ✓ {cid}")
        
        # Verify it matches our computed CID
        ipld_json = cbor_file.with_suffix(".ipld.json")
        if ipld_json.exists():
            expected = json.loads(ipld_json.read_text())["cid"]
            if cid == expected:
                print(f"  ✓ CID matches!")
            else:
                print(f"  ⚠ CID mismatch: expected {expected}")
    
    return results

def verify_availability(cid: str, timeout: int = 30) -> bool:
    """Check if CID is accessible via public gateway."""
    gateways = [
        f"https://w3s.link/ipfs/{cid}",
        f"https://ipfs.io/ipfs/{cid}",
        f"https://dweb.link/ipfs/{cid}",
    ]
    
    for gateway in gateways:
        try:
            resp = requests.head(gateway, timeout=timeout)
            if resp.status_code == 200:
                return True
        except:
            continue
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pin lattice to web3.storage")
    parser.add_argument("--token", required=True, help="web3.storage API token")
    parser.add_argument("--verify", action="store_true", help="Verify availability after pinning")
    args = parser.parse_args()
    
    print("=== Pinning lattice to web3.storage ===\n")
    results = pin_lattice(args.token)
    
    print(f"\n=== Pinned {len(results)} files ===\n")
    
    if args.verify:
        print("Verifying availability (may take a minute)...\n")
        for name, cid in results.items():
            available = verify_availability(cid)
            status = "✓ LIVE" if available else "⏳ propagating"
            print(f"  {name}: {status}")
            print(f"    https://w3s.link/ipfs/{cid}")
    
    print("\n=== Layer 2 complete ===")
