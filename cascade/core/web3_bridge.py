"""
CASCADE // WEB3 BRIDGE
Blockchain integration for AI provenance.

The bridge between neural networks and decentralized infrastructure.

┌─────────────────────────────────────────────────────────────────┐
│                    THE IMMUTABLE RECORD                         │
│                                                                 │
│   AI Inference ──► Provenance Chain ──► Merkle Root ──► Chain  │
│                                              │                  │
│                                              ▼                  │
│                    ┌─────────────────────────────────┐         │
│                    │     ETHEREUM / SOLANA / etc     │         │
│                    │  ┌───────────────────────────┐  │         │
│                    │  │   Attestation Contract    │  │         │
│                    │  │   - Model hash            │  │         │
│                    │  │   - Input hash            │  │         │
│                    │  │   - Merkle root           │  │         │
│                    │  │   - Timestamp             │  │         │
│                    │  └───────────────────────────┘  │         │
│                    └─────────────────────────────────┘         │
│                                              │                  │
│                                              ▼                  │
│                              IPFS / Arweave / Filecoin          │
│                              (Full provenance chain storage)    │
└─────────────────────────────────────────────────────────────────┘

Web3 provides:
    - Timestamping (block finality)
    - Immutability (blockchain consensus) 
    - Decentralized storage (IPFS)
    - Public verifiability (anyone can audit)
    - Economic incentives (staking, reputation)

This module provides:
    - EIP-712 typed data signatures (Ethereum standard)
    - IPFS CID computation (content addressing)
    - Smart contract ABI for attestation
    - Multi-chain attestation format
    - NFT metadata for provenance tokens
"""

import hashlib
import json
import time
import struct
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
import base64

try:
    from .provenance import ProvenanceChain, ProvenanceRecord, compute_merkle_root
except ImportError:
    from provenance import ProvenanceChain, ProvenanceRecord, compute_merkle_root


# =============================================================================
# CONSTANTS
# =============================================================================

# EIP-712 Domain for CASCADE attestations
CASCADE_DOMAIN = {
    "name": "CASCADE Provenance",
    "version": "1",
    "chainId": 1,  # Ethereum mainnet, override for other chains
    "verifyingContract": "0x0000000000000000000000000000000000000000",  # Set on deployment
}

# Attestation type definition for EIP-712
ATTESTATION_TYPES = {
    "Attestation": [
        {"name": "model_hash", "type": "bytes32"},
        {"name": "input_hash", "type": "bytes32"},
        {"name": "merkle_root", "type": "bytes32"},
        {"name": "timestamp", "type": "uint256"},
        {"name": "session_id", "type": "string"},
        {"name": "layer_count", "type": "uint256"},
    ]
}


# =============================================================================
# ATTESTATION RECORD
# =============================================================================

@dataclass
class Web3Attestation:
    """
    Blockchain-ready attestation of AI inference provenance.
    
    This is the "receipt" that can be posted on-chain.
    Minimal data for on-chain storage, full data on IPFS.
    """
    
    # Core identity
    model_hash: str           # 32-byte hash of model weights
    input_hash: str           # 32-byte hash of input data
    output_hash: str          # 32-byte hash of output
    merkle_root: str          # Merkle root of provenance chain
    
    # Metadata
    session_id: str           # Unique session identifier
    timestamp: int            # Unix timestamp
    layer_count: int          # Number of layers in chain
    
    # Content addressing
    ipfs_cid: Optional[str] = None       # IPFS CID for full chain
    arweave_id: Optional[str] = None     # Arweave transaction ID
    
    # Signatures (set by wallet)
    signature: Optional[str] = None       # EIP-712 signature
    signer: Optional[str] = None          # Ethereum address
    
    # Chain info
    chain_id: int = 1                     # 1=Ethereum, 137=Polygon, etc.
    contract_address: Optional[str] = None
    tx_hash: Optional[str] = None         # Transaction hash after posting
    
    def to_eip712_message(self, domain: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Format as EIP-712 typed data for signing.
        
        This is the standard Ethereum signing format that wallets understand.
        """
        domain = domain or CASCADE_DOMAIN
        
        return {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                **ATTESTATION_TYPES
            },
            "primaryType": "Attestation",
            "domain": domain,
            "message": {
                "model_hash": self._to_bytes32(self.model_hash),
                "input_hash": self._to_bytes32(self.input_hash),
                "merkle_root": self._to_bytes32(self.merkle_root),
                "timestamp": self.timestamp,
                "session_id": self.session_id,
                "layer_count": self.layer_count,
            }
        }
    
    def _to_bytes32(self, hex_str: str) -> str:
        """Pad hash to bytes32 format."""
        # Remove 0x prefix if present
        clean = hex_str.replace("0x", "")
        # Pad to 64 chars (32 bytes)
        padded = clean.zfill(64)
        return "0x" + padded
    
    def to_contract_args(self) -> Tuple:
        """
        Format for smart contract function call.
        
        Returns tuple matching: 
            function attest(bytes32 modelHash, bytes32 inputHash, bytes32 merkleRoot, 
                           string memory sessionId, uint256 layerCount)
        """
        return (
            bytes.fromhex(self.model_hash.replace("0x", "").zfill(64)),
            bytes.fromhex(self.input_hash.replace("0x", "").zfill(64)),
            bytes.fromhex(self.merkle_root.replace("0x", "").zfill(64)),
            self.session_id,
            self.layer_count,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage/transmission."""
        return asdict(self)
    
    def to_json(self) -> str:
        """JSON export."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_chain(cls, chain: ProvenanceChain) -> 'Web3Attestation':
        """Create attestation from provenance chain."""
        if not chain.finalized:
            chain.finalize()
        
        return cls(
            model_hash=chain.model_hash,
            input_hash=chain.input_hash,
            output_hash=chain.output_hash or "0" * 16,
            merkle_root=chain.merkle_root,
            session_id=chain.session_id,
            timestamp=int(chain.created_at),
            layer_count=len(chain.records),
        )


# =============================================================================
# IPFS CONTENT ADDRESSING
# =============================================================================

def compute_ipfs_cid_v0(data: bytes) -> str:
    """
    Compute IPFS CID v0 (Qm...) for data.
    
    This is a simplified computation - actual IPFS uses more complex
    chunking for large files. Suitable for JSON chain data.
    
    CIDv0 format: Base58(0x12 || 0x20 || SHA256(data))
    """
    # SHA-256 hash
    sha_hash = hashlib.sha256(data).digest()
    
    # Multihash prefix: 0x12 (sha2-256), 0x20 (32 bytes)
    multihash = bytes([0x12, 0x20]) + sha_hash
    
    # Base58 encode (Bitcoin alphabet)
    return base58_encode(multihash)


def compute_ipfs_cid_v1(data: bytes) -> str:
    """
    Compute IPFS CID v1 (bafy...) for data.
    
    CIDv1 format: multibase || version || codec || multihash
    """
    # SHA-256 hash
    sha_hash = hashlib.sha256(data).digest()
    
    # Build CIDv1:
    # 0x01 = CID version 1
    # 0x55 = raw binary codec (could also use 0x71 for dag-cbor)
    # 0x12 = sha2-256
    # 0x20 = 32 bytes
    cid_bytes = bytes([0x01, 0x55, 0x12, 0x20]) + sha_hash
    
    # Base32 lower with 'b' prefix (multibase)
    import base64
    b32 = base64.b32encode(cid_bytes).decode('ascii').lower().rstrip('=')
    return 'b' + b32


def base58_encode(data: bytes) -> str:
    """Base58 encoding (Bitcoin alphabet)."""
    ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    
    # Count leading zeros
    leading_zeros = 0
    for byte in data:
        if byte == 0:
            leading_zeros += 1
        else:
            break
    
    # Convert to integer
    num = int.from_bytes(data, 'big')
    
    # Convert to base58
    result = ""
    while num > 0:
        num, remainder = divmod(num, 58)
        result = ALPHABET[remainder] + result
    
    # Add leading '1's for each leading zero byte
    return '1' * leading_zeros + result


def chain_to_ipfs_ready(chain: ProvenanceChain) -> Tuple[bytes, str]:
    """
    Prepare provenance chain for IPFS upload.
    
    Returns:
        (data_bytes, cid) - The data to upload and its expected CID
    """
    json_data = chain.to_json().encode('utf-8')
    cid = compute_ipfs_cid_v0(json_data)
    return json_data, cid


# =============================================================================
# SMART CONTRACT ABI
# =============================================================================

CASCADE_ATTESTATION_ABI = [
    {
        "name": "Attest",
        "type": "event",
        "inputs": [
            {"name": "attester", "type": "address", "indexed": True},
            {"name": "modelHash", "type": "bytes32", "indexed": True},
            {"name": "merkleRoot", "type": "bytes32", "indexed": False},
            {"name": "sessionId", "type": "string", "indexed": False},
            {"name": "timestamp", "type": "uint256", "indexed": False},
        ]
    },
    {
        "name": "attest",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "modelHash", "type": "bytes32"},
            {"name": "inputHash", "type": "bytes32"},
            {"name": "merkleRoot", "type": "bytes32"},
            {"name": "sessionId", "type": "string"},
            {"name": "layerCount", "type": "uint256"},
        ],
        "outputs": [{"name": "attestationId", "type": "uint256"}]
    },
    {
        "name": "verify",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "attestationId", "type": "uint256"},
        ],
        "outputs": [
            {"name": "valid", "type": "bool"},
            {"name": "attester", "type": "address"},
            {"name": "modelHash", "type": "bytes32"},
            {"name": "merkleRoot", "type": "bytes32"},
        ]
    },
    {
        "name": "getAttestation",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "attestationId", "type": "uint256"},
        ],
        "outputs": [
            {"name": "attester", "type": "address"},
            {"name": "modelHash", "type": "bytes32"},
            {"name": "inputHash", "type": "bytes32"},
            {"name": "merkleRoot", "type": "bytes32"},
            {"name": "sessionId", "type": "string"},
            {"name": "layerCount", "type": "uint256"},
            {"name": "timestamp", "type": "uint256"},
        ]
    },
    {
        "name": "attestationsByModel",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "modelHash", "type": "bytes32"},
        ],
        "outputs": [
            {"name": "attestationIds", "type": "uint256[]"},
        ]
    },
]


# Solidity source for the attestation contract
CASCADE_ATTESTATION_SOLIDITY = '''
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title CascadeAttestation
 * @notice On-chain attestation of AI inference provenance
 * @dev Stores Merkle roots for off-chain provenance chains
 */
contract CascadeAttestation {
    
    struct Attestation {
        address attester;
        bytes32 modelHash;
        bytes32 inputHash;
        bytes32 merkleRoot;
        string sessionId;
        uint256 layerCount;
        uint256 timestamp;
        string ipfsCid;  // Optional: full chain on IPFS
    }
    
    // Attestation storage
    mapping(uint256 => Attestation) public attestations;
    uint256 public attestationCount;
    
    // Index by model
    mapping(bytes32 => uint256[]) public attestationsByModel;
    
    // Index by attester
    mapping(address => uint256[]) public attestationsByAttester;
    
    // Events
    event Attested(
        uint256 indexed attestationId,
        address indexed attester,
        bytes32 indexed modelHash,
        bytes32 merkleRoot,
        string sessionId
    );
    
    /**
     * @notice Create a new attestation
     * @param modelHash Hash of the model weights
     * @param inputHash Hash of the input data
     * @param merkleRoot Merkle root of the provenance chain
     * @param sessionId Unique session identifier
     * @param layerCount Number of layers in the chain
     * @return attestationId The ID of the new attestation
     */
    function attest(
        bytes32 modelHash,
        bytes32 inputHash,
        bytes32 merkleRoot,
        string memory sessionId,
        uint256 layerCount
    ) external returns (uint256 attestationId) {
        attestationId = attestationCount++;
        
        attestations[attestationId] = Attestation({
            attester: msg.sender,
            modelHash: modelHash,
            inputHash: inputHash,
            merkleRoot: merkleRoot,
            sessionId: sessionId,
            layerCount: layerCount,
            timestamp: block.timestamp,
            ipfsCid: ""
        });
        
        attestationsByModel[modelHash].push(attestationId);
        attestationsByAttester[msg.sender].push(attestationId);
        
        emit Attested(attestationId, msg.sender, modelHash, merkleRoot, sessionId);
        
        return attestationId;
    }
    
    /**
     * @notice Attest with IPFS CID for full chain data
     */
    function attestWithIPFS(
        bytes32 modelHash,
        bytes32 inputHash,
        bytes32 merkleRoot,
        string memory sessionId,
        uint256 layerCount,
        string memory ipfsCid
    ) external returns (uint256 attestationId) {
        attestationId = this.attest(modelHash, inputHash, merkleRoot, sessionId, layerCount);
        attestations[attestationId].ipfsCid = ipfsCid;
        return attestationId;
    }
    
    /**
     * @notice Verify an attestation exists and return core data
     */
    function verify(uint256 attestationId) external view returns (
        bool valid,
        address attester,
        bytes32 modelHash,
        bytes32 merkleRoot
    ) {
        if (attestationId >= attestationCount) {
            return (false, address(0), bytes32(0), bytes32(0));
        }
        
        Attestation storage a = attestations[attestationId];
        return (true, a.attester, a.modelHash, a.merkleRoot);
    }
    
    /**
     * @notice Get all attestations for a model
     */
    function getModelAttestations(bytes32 modelHash) external view returns (uint256[] memory) {
        return attestationsByModel[modelHash];
    }
    
    /**
     * @notice Get all attestations by an address
     */
    function getAttesterAttestations(address attester) external view returns (uint256[] memory) {
        return attestationsByAttester[attester];
    }
}
'''


# =============================================================================
# NFT METADATA (for provenance tokens)
# =============================================================================

def generate_nft_metadata(chain: ProvenanceChain, 
                         image_url: Optional[str] = None,
                         animation_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate ERC-721 compatible metadata for a provenance NFT.
    
    Each unique model×input×output combination could be an NFT,
    proving that this specific inference happened.
    """
    if not chain.finalized:
        chain.finalize()
    
    # Generate attributes from chain
    attributes = [
        {"trait_type": "Model Hash", "value": chain.model_hash[:16]},
        {"trait_type": "Input Hash", "value": chain.input_hash},
        {"trait_type": "Merkle Root", "value": chain.merkle_root},
        {"trait_type": "Layer Count", "value": len(chain.records)},
        {"trait_type": "Timestamp", "value": int(chain.created_at)},
    ]
    
    # Add layer statistics as traits
    if chain.records:
        total_params = 0
        layer_types = set()
        for record in chain.records.values():
            if record.params_hash != "no_params":
                total_params += 1
            # Extract layer type from name
            parts = record.layer_name.split('.')
            if len(parts) >= 2:
                layer_types.add(parts[-1])
        
        attributes.append({"trait_type": "Parameterized Layers", "value": total_params})
        for lt in list(layer_types)[:5]:  # Max 5 layer types
            attributes.append({"trait_type": f"Has {lt}", "value": "Yes"})
    
    return {
        "name": f"CASCADE Provenance #{chain.session_id}",
        "description": f"Cryptographic proof of AI inference. Model: {chain.model_id}. "
                      f"This NFT attests that a specific input was processed through "
                      f"the model, producing a verifiable Merkle root of all layer activations.",
        "image": image_url or "ipfs://QmDefaultCascadeImage",  # Placeholder
        "animation_url": animation_url,  # Could link to 3D visualization
        "external_url": f"https://cascade.ai/verify/{chain.session_id}",
        "attributes": attributes,
        "properties": {
            "model_id": chain.model_id,
            "model_hash": chain.model_hash,
            "input_hash": chain.input_hash,
            "output_hash": chain.output_hash,
            "merkle_root": chain.merkle_root,
            "session_id": chain.session_id,
            "layer_count": len(chain.records),
            "created_at": chain.created_at,
        }
    }


# =============================================================================
# MULTI-CHAIN SUPPORT
# =============================================================================

CHAIN_CONFIGS = {
    "ethereum": {
        "chain_id": 1,
        "name": "Ethereum Mainnet",
        "explorer": "https://etherscan.io",
        "native_token": "ETH",
    },
    "polygon": {
        "chain_id": 137,
        "name": "Polygon",
        "explorer": "https://polygonscan.com",
        "native_token": "MATIC",
    },
    "arbitrum": {
        "chain_id": 42161,
        "name": "Arbitrum One",
        "explorer": "https://arbiscan.io",
        "native_token": "ETH",
    },
    "optimism": {
        "chain_id": 10,
        "name": "Optimism",
        "explorer": "https://optimistic.etherscan.io",
        "native_token": "ETH",
    },
    "base": {
        "chain_id": 8453,
        "name": "Base",
        "explorer": "https://basescan.org",
        "native_token": "ETH",
    },
    "solana": {
        "chain_id": -1,  # Not EVM
        "name": "Solana",
        "explorer": "https://solscan.io",
        "native_token": "SOL",
    },
}


def get_chain_config(chain_name: str) -> Dict[str, Any]:
    """Get configuration for a specific blockchain."""
    return CHAIN_CONFIGS.get(chain_name.lower(), CHAIN_CONFIGS["ethereum"])


# =============================================================================
# WEB3 EXPORT UTILITIES
# =============================================================================

def export_for_web3(chain: ProvenanceChain, 
                    chain_name: str = "ethereum",
                    include_full_chain: bool = True) -> Dict[str, Any]:
    """
    Export provenance chain in Web3-ready format.
    
    Returns everything needed to post attestation on-chain.
    """
    attestation = Web3Attestation.from_chain(chain)
    chain_config = get_chain_config(chain_name)
    
    result = {
        "attestation": attestation.to_dict(),
        "eip712": attestation.to_eip712_message({
            **CASCADE_DOMAIN,
            "chainId": chain_config["chain_id"]
        }),
        "contract_abi": CASCADE_ATTESTATION_ABI,
        "chain_config": chain_config,
    }
    
    if include_full_chain:
        data, cid = chain_to_ipfs_ready(chain)
        result["ipfs"] = {
            "data": base64.b64encode(data).decode('ascii'),
            "cid": cid,
            "size_bytes": len(data),
        }
    
    return result


def generate_verification_page(attestation: Web3Attestation, 
                              chain: Optional[ProvenanceChain] = None) -> str:
    """
    Generate an HTML verification page for an attestation.
    
    This can be hosted anywhere and allows public verification.
    """
    records_html = ""
    if chain:
        for record in chain.records.values():
            records_html += f"""
            <tr>
                <td>{record.layer_name}</td>
                <td><code>{record.state_hash}</code></td>
                <td>{record.shape}</td>
                <td>{record.stats.get('mean', 0):.4f}</td>
            </tr>
            """
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>CASCADE Provenance Verification</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Courier New', monospace; background: #0a0a0a; color: #00ff88; padding: 40px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ color: #00ffcc; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }}
        .hash {{ font-family: monospace; background: #1a1a2e; padding: 10px; border-radius: 4px; word-break: break-all; }}
        .verified {{ color: #00ff88; }}
        .label {{ color: #888; font-size: 0.9em; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 8px; border: 1px solid #333; text-align: left; }}
        th {{ background: #1a1a2e; }}
        code {{ background: #1a1a2e; padding: 2px 6px; border-radius: 3px; }}
        .merkle {{ font-size: 1.5em; color: #ffcc00; text-align: center; padding: 20px; background: #1a1a2e; border-radius: 8px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 CASCADE Provenance Verification</h1>
        
        <div class="merkle">
            Merkle Root: <code>{attestation.merkle_root}</code>
        </div>
        
        <h2>Attestation Details</h2>
        <p class="label">Session ID</p>
        <div class="hash">{attestation.session_id}</div>
        
        <p class="label">Model Hash</p>
        <div class="hash">{attestation.model_hash}</div>
        
        <p class="label">Input Hash</p>
        <div class="hash">{attestation.input_hash}</div>
        
        <p class="label">Output Hash</p>
        <div class="hash">{attestation.output_hash}</div>
        
        <p class="label">Timestamp</p>
        <div class="hash">{attestation.timestamp} ({time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(attestation.timestamp))})</div>
        
        <p class="label">Layer Count</p>
        <div class="hash">{attestation.layer_count} layers</div>
        
        {"<h2>Provenance Chain</h2><table><tr><th>Layer</th><th>State Hash</th><th>Shape</th><th>Mean</th></tr>" + records_html + "</table>" if chain else ""}
        
        <h2>On-Chain Verification</h2>
        <p>{"<span class='verified'>✓ Verified on " + get_chain_config('ethereum')['name'] + "</span>" if attestation.tx_hash else "⏳ Pending on-chain attestation"}</p>
        {f"<p class='label'>Transaction</p><div class='hash'><a href='{get_chain_config('ethereum')['explorer']}/tx/{attestation.tx_hash}' style='color: #00ff88;'>{attestation.tx_hash}</a></div>" if attestation.tx_hash else ""}
        
        <h2>IPFS Storage</h2>
        <p>{f"<a href='https://ipfs.io/ipfs/{attestation.ipfs_cid}' style='color: #00ff88;'>{attestation.ipfs_cid}</a>" if attestation.ipfs_cid else "Full chain not yet pinned to IPFS"}</p>
        
        <hr style="border-color: #333; margin: 40px 0;">
        <p style="color: #666; text-align: center;">CASCADE Provenance Engine • Due process infrastructure for AI</p>
    </div>
</body>
</html>
"""


# =============================================================================
# SIGNATURE UTILITIES (for wallet integration)
# =============================================================================

def prepare_for_signing(attestation: Web3Attestation, 
                       chain_name: str = "ethereum") -> Dict[str, Any]:
    """
    Prepare attestation for wallet signing (MetaMask, etc).
    
    Returns the EIP-712 message that wallets can sign.
    """
    chain_config = get_chain_config(chain_name)
    
    eip712 = attestation.to_eip712_message({
        **CASCADE_DOMAIN,
        "chainId": chain_config["chain_id"]
    })
    
    return {
        "method": "eth_signTypedData_v4",
        "params": [
            None,  # Address filled by wallet
            json.dumps(eip712)
        ],
        "display": {
            "title": "Sign CASCADE Attestation",
            "description": f"Attest that model {attestation.model_hash[:16]}... "
                          f"processed input {attestation.input_hash[:16]}...",
            "merkle_root": attestation.merkle_root,
        }
    }


def verify_signature(attestation: Web3Attestation, 
                    signature: str, 
                    expected_signer: str) -> Tuple[bool, str]:
    """
    Verify an EIP-712 signature.
    
    Note: Full verification requires eth_utils/web3.py.
    This is a structural check only.
    """
    if not signature or len(signature) < 130:
        return False, "Invalid signature length"
    
    if not signature.startswith("0x"):
        return False, "Signature must start with 0x"
    
    # Extract r, s, v components
    try:
        sig_bytes = bytes.fromhex(signature[2:])
        if len(sig_bytes) != 65:
            return False, f"Signature must be 65 bytes, got {len(sig_bytes)}"
        
        r = sig_bytes[:32]
        s = sig_bytes[32:64]
        v = sig_bytes[64]
        
        # v should be 27 or 28 (or 0/1 for some implementations)
        if v not in [0, 1, 27, 28]:
            return False, f"Invalid v value: {v}"
        
        # Structural validation passed
        # Full cryptographic verification requires ecrecover
        return True, "Signature structure valid (full verification requires web3.py)"
        
    except Exception as e:
        return False, f"Signature parsing error: {str(e)}"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def attest_inference(chain: ProvenanceChain, 
                    chain_name: str = "ethereum") -> Web3Attestation:
    """
    One-liner to create attestation from provenance chain.
    
    Usage:
        attestation = attest_inference(chain)
        print(attestation.merkle_root)
    """
    if not chain.finalized:
        chain.finalize()
    
    attestation = Web3Attestation.from_chain(chain)
    
    # Compute IPFS CID
    data, cid = chain_to_ipfs_ready(chain)
    attestation.ipfs_cid = cid
    
    # Set chain
    attestation.chain_id = get_chain_config(chain_name)["chain_id"]
    
    return attestation


def quick_verify(merkle_root: str, layer_hashes: List[str]) -> bool:
    """
    Quick verification that layer hashes produce expected Merkle root.
    """
    computed = compute_merkle_root(layer_hashes)
    return computed == merkle_root


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("CASCADE // WEB3 BRIDGE")
    print("=" * 50)
    print()
    print("Smart Contract (Solidity):")
    print("-" * 50)
    print(CASCADE_ATTESTATION_SOLIDITY[:500] + "...")
    print()
    print("Contract ABI:")
    print("-" * 50)
    print(json.dumps(CASCADE_ATTESTATION_ABI, indent=2)[:500] + "...")
    print()
    print("Supported Chains:")
    print("-" * 50)
    for name, config in CHAIN_CONFIGS.items():
        print(f"  {name}: Chain ID {config['chain_id']}")
    print()
    print("Usage:")
    print("  from cascade.core.web3_bridge import attest_inference, export_for_web3")
    print("  attestation = attest_inference(provenance_chain)")
    print("  web3_data = export_for_web3(provenance_chain, 'polygon')")
