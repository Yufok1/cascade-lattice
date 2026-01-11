"""
HuggingFace → IPFS Bridge

Makes every CASCADE instance a node in the IPFS network.
Serves lattice content to DHT without running a full daemon.

Uses js-ipfs HTTP API compatible endpoints via ipfs-http-client.
For HF Spaces, we use Helia (browser/Node IPFS) style serving.
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
import threading
import time

# Optional: for full IPFS integration
try:
    import ipfshttpclient
    HAS_IPFS_CLIENT = True
except ImportError:
    HAS_IPFS_CLIENT = False

from cascade.ipld import chain_to_ipld, chain_to_cid, encode_to_dag_cbor


class LatticeServer:
    """
    Serves lattice content over IPFS-compatible protocols.
    
    Can run in multiple modes:
    1. Gateway mode: HTTP endpoints that mirror IPFS gateway API
    2. DHT mode: Announce content to IPFS DHT (needs daemon)
    3. Hybrid: Both
    """
    
    def __init__(self, lattice_dir: Path = None):
        if lattice_dir is None:
            # Try relative to this file first, then cwd
            candidate = Path(__file__).resolve().parent.parent / "lattice"
            if not candidate.exists():
                candidate = Path.cwd() / "lattice"
            self.lattice_dir = candidate
        else:
            self.lattice_dir = lattice_dir
        self.ipld_dir = self.lattice_dir / "ipld"
        self._index: Dict[str, Path] = {}  # CID -> file path
        self._build_index()
    
    def _build_index(self):
        """Index all known CIDs to their local files."""
        # Index CBOR files
        if self.ipld_dir.exists():
            for cbor_file in self.ipld_dir.glob("*.cbor"):
                ipld_json = cbor_file.with_suffix(".ipld.json")
                if ipld_json.exists():
                    meta = json.loads(ipld_json.read_text())
                    # Try both 'cid' and '_cid' keys
                    cid = meta.get("cid") or meta.get("_cid")
                    if cid:
                        self._index[cid] = cbor_file
        
        # Index JSON chain files (compute CID on the fly)
        for json_file in self.lattice_dir.glob("*.json"):
            if json_file.name == "README.md":
                continue
            try:
                chain_data = json.loads(json_file.read_text())
                cid = chain_to_cid(chain_data)
                self._index[cid] = json_file
            except:
                pass
        
        print(f"Indexed {len(self._index)} CIDs")
    
    def resolve(self, cid: str) -> Optional[bytes]:
        """Resolve a CID to its content."""
        if cid in self._index:
            filepath = self._index[cid]
            if filepath.suffix == ".cbor":
                return filepath.read_bytes()
            else:
                # JSON file - return as CBOR for consistency
                chain_data = json.loads(filepath.read_text())
                ipld_data = chain_to_ipld(chain_data)
                return encode_to_dag_cbor(ipld_data)
        return None
    
    def list_cids(self) -> list:
        """List all available CIDs."""
        return list(self._index.keys())
    
    def get_gateway_response(self, cid: str) -> tuple:
        """
        Return (content, content_type, status_code) for gateway-style serving.
        """
        content = self.resolve(cid)
        if content:
            return (content, "application/cbor", 200)
        return (b"CID not found", "text/plain", 404)
    
    def announce_to_dht(self, ipfs_api: str = "/ip4/127.0.0.1/tcp/5001"):
        """
        Announce all CIDs to IPFS DHT.
        Requires running IPFS daemon.
        """
        if not HAS_IPFS_CLIENT:
            print("ipfshttpclient not installed. Run: pip install ipfshttpclient")
            return
        
        try:
            client = ipfshttpclient.connect(ipfs_api)
        except Exception as e:
            print(f"Could not connect to IPFS daemon: {e}")
            print("Start daemon with: ipfs daemon")
            return
        
        for cid, filepath in self._index.items():
            try:
                # Add file to local IPFS node
                if filepath.suffix == ".cbor":
                    result = client.add(str(filepath))
                    print(f"Announced {filepath.name}: {result['Hash']}")
            except Exception as e:
                print(f"Failed to announce {cid}: {e}")
    
    def start_gateway(self, host: str = "0.0.0.0", port: int = 8080):
        """
        Start a simple HTTP gateway for serving lattice content.
        
        Compatible with IPFS gateway URL format:
            GET /ipfs/{cid}
        """
        from http.server import HTTPServer, BaseHTTPRequestHandler
        
        server = self
        
        class GatewayHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                # Parse /ipfs/{cid} or just /{cid}
                path = self.path.strip("/")
                if path.startswith("ipfs/"):
                    cid = path[5:]
                else:
                    cid = path
                
                content, content_type, status = server.get_gateway_response(cid)
                
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", len(content))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            
            def do_HEAD(self):
                path = self.path.strip("/")
                if path.startswith("ipfs/"):
                    cid = path[5:]
                else:
                    cid = path
                
                _, content_type, status = server.get_gateway_response(cid)
                
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
            
            def log_message(self, format, *args):
                print(f"[Gateway] {args[0]}")
        
        httpd = HTTPServer((host, port), GatewayHandler)
        print(f"Lattice gateway running at http://{host}:{port}")
        print(f"Serving {len(self._index)} CIDs")
        print(f"\nTry: http://localhost:{port}/ipfs/bafyreidixjlzdat7ex72foi6vm3vnskhzguovxj6ondbazrqks7v6ahmei")
        httpd.serve_forever()


def create_gradio_gateway():
    """
    Create a Gradio interface that serves as IPFS gateway.
    Suitable for HuggingFace Spaces deployment.
    """
    try:
        import gradio as gr
    except ImportError:
        print("Gradio not installed. Run: pip install gradio")
        return None
    
    server = LatticeServer()
    
    def resolve_cid(cid: str) -> str:
        """Resolve CID and return content as hex + JSON decode attempt."""
        content = server.resolve(cid.strip())
        if content is None:
            return f"❌ CID not found: {cid}\n\nAvailable CIDs:\n" + "\n".join(server.list_cids())
        
        # Try to decode as CBOR → JSON for display
        try:
            import dag_cbor
            decoded = dag_cbor.decode(content)
            return f"✓ Found! ({len(content)} bytes)\n\n{json.dumps(decoded, indent=2, default=str)}"
        except:
            return f"✓ Found! ({len(content)} bytes)\n\nRaw hex: {content.hex()[:200]}..."
    
    def list_all() -> str:
        """List all available CIDs."""
        cids = server.list_cids()
        lines = [f"=== Lattice Index ({len(cids)} chains) ===\n"]
        for cid in cids:
            filepath = server._index[cid]
            lines.append(f"• {filepath.stem}")
            lines.append(f"  {cid}\n")
        return "\n".join(lines)
    
    with gr.Blocks(title="CASCADE Lattice Gateway") as app:
        gr.Markdown("# 🌐 CASCADE Lattice Gateway")
        gr.Markdown("*The neural internetwork, content-addressed.*")
        
        with gr.Tab("Resolve CID"):
            cid_input = gr.Textbox(
                label="CID",
                placeholder="bafyrei...",
                value="bafyreidixjlzdat7ex72foi6vm3vnskhzguovxj6ondbazrqks7v6ahmei"
            )
            resolve_btn = gr.Button("Resolve")
            output = gr.Textbox(label="Content", lines=20)
            resolve_btn.click(resolve_cid, inputs=cid_input, outputs=output)
        
        with gr.Tab("Browse Lattice"):
            list_btn = gr.Button("List All CIDs")
            list_output = gr.Textbox(label="Available Chains", lines=20)
            list_btn.click(list_all, outputs=list_output)
        
        gr.Markdown("""
        ---
        **What is this?**
        
        This gateway serves the CASCADE lattice — a cryptographic provenance network for AI agents.
        
        Every chain has a CID (Content IDentifier). Same content = same CID. Forever.
        
        - **Genesis**: `bafyreidixjlzdat7ex72foi6vm3vnskhzguovxj6ondbazrqks7v6ahmei`
        - Protocol: [IPLD](https://ipld.io/) (InterPlanetary Linked Data)
        """)
    
    return app


if __name__ == "__main__":
    import sys
    
    if "--gradio" in sys.argv:
        app = create_gradio_gateway()
        if app:
            app.launch()
    elif "--announce" in sys.argv:
        server = LatticeServer()
        server.announce_to_dht()
    else:
        # Default: run HTTP gateway
        server = LatticeServer()
        server.start_gateway(port=8080)
