"""
CASCADE Proxy - Protocol-level AI observation.

Works with ANY language, ANY framework, ANY client.
Just set environment variables and CASCADE sees everything.

Usage:
    # Start the proxy
    python -m cascade.proxy
    
    # In another terminal, point your app at it
    export OPENAI_BASE_URL=http://localhost:7777/v1
    export ANTHROPIC_BASE_URL=http://localhost:7777/anthropic
    
    # Run your app normally - CASCADE observes all calls
    python your_agent.py

The proxy forwards requests to the real API and emits receipts for every call.
"""

import asyncio
import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path

try:
    from aiohttp import web, ClientSession
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# Import CASCADE SDK for emission
from cascade.sdk import CascadeSDK


class CascadeProxy:
    """
    HTTP proxy that intercepts LLM API calls and emits CASCADE receipts.
    
    Supported providers:
    - OpenAI (and OpenAI-compatible APIs)
    - Anthropic
    - Cohere
    - Mistral
    - Any OpenAI-compatible endpoint
    """
    
    # Real API endpoints
    ENDPOINTS = {
        "openai": "https://api.openai.com",
        "anthropic": "https://api.anthropic.com",
        "cohere": "https://api.cohere.ai",
        "mistral": "https://api.mistral.ai",
    }
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 7777,
        verbose: bool = True,
    ):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.sdk = CascadeSDK()
        self.sdk.init(emit_async=True, verbose=verbose)
        self.session: Optional[ClientSession] = None
        self.runner = None
        self.site = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._ready_event = threading.Event()
        self._start_error: Optional[str] = None
        self._running = False
        
        # Stats
        self.stats = {
            "requests": 0,
            "receipts_emitted": 0,
            "bytes_proxied": 0,
            "start_time": None,
        }
    
    async def _serve(self):
        """Async proxy server lifecycle."""
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp required for proxy mode. Install with: pip install aiohttp")

        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        self.session = ClientSession()
        self.stats["start_time"] = time.time()
        
        app = web.Application()
        
        # Route all requests
        app.router.add_route("*", "/{path:.*}", self.handle_request)
        
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        
        self.site = web.TCPSite(self.runner, self.host, self.port)
        
        if self.verbose:
            print(f"""
╔══════════════════════════════════════════════════════════════╗
║  CASCADE PROXY - Protocol-Level AI Observation               ║
╠══════════════════════════════════════════════════════════════╣
║  Listening: http://{self.host}:{self.port}                          ║
║                                                              ║
║  Set these environment variables in your app:                ║
║                                                              ║
║  export OPENAI_BASE_URL=http://localhost:{self.port}/v1          ║
║  export ANTHROPIC_BASE_URL=http://localhost:{self.port}/anthropic║
║                                                              ║
║  Then run your app normally. CASCADE sees everything.        ║
╚══════════════════════════════════════════════════════════════╝
""")
        
        await self.site.start()
        if self.port == 0:
            sockets = getattr(getattr(self.site, "_server", None), "sockets", None) or []
            if sockets:
                try:
                    self.port = sockets[0].getsockname()[1]
                except Exception:
                    pass
        self._running = True
        self._ready_event.set()
        
        # Keep running until stop() signals the event.
        await self._stop_event.wait()
        await self.shutdown()

    async def start_async(self):
        """Start the proxy in the current event loop and block until stopped."""
        try:
            await self._serve()
        finally:
            self._running = False

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._serve())
        except Exception as exc:
            self._start_error = str(exc)
            self._ready_event.set()
            if self.verbose:
                print(f"[CASCADE PROXY] Startup failed: {exc}")
            if self.session or self.runner:
                try:
                    loop.run_until_complete(self.shutdown())
                except Exception:
                    pass
        finally:
            self._running = False
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            if pending:
                try:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
            loop.close()
            self._loop = None

    def start(self, block: bool = False, timeout: float = 5.0):
        """Start the proxy.

        By default the proxy runs in a background thread so synchronous runtimes
        can start/stop it cleanly. Set block=True for CLI usage.
        """
        if self._running:
            return self.status()
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp required for proxy mode. Install with: pip install aiohttp")

        self._ready_event.clear()
        self._start_error = None

        if block:
            asyncio.run(self.start_async())
            return self.status()

        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()
        self._ready_event.wait(timeout=max(float(timeout or 0), 0.1))
        if self._start_error:
            raise RuntimeError(self._start_error)
        return self.status()

    def stop(self, timeout: float = 5.0):
        """Stop the proxy and wait briefly for cleanup."""
        if not self._running:
            return self.status()
        loop = self._loop
        stop_event = self._stop_event
        if loop and stop_event:
            loop.call_soon_threadsafe(stop_event.set)
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=max(float(timeout or 0), 0.1))
        return self.status()

    def status(self) -> Dict[str, Any]:
        """Return proxy lifecycle state."""
        runtime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0.0
        return {
            "running": bool(self._running),
            "host": self.host,
            "port": self.port,
            "requests": self.stats["requests"],
            "receipts_emitted": self.stats["receipts_emitted"],
            "bytes_proxied": self.stats["bytes_proxied"],
            "runtime_seconds": round(runtime, 3),
            "start_error": self._start_error,
        }
    
    async def handle_request(self, request: web.Request) -> web.Response:
        """Handle incoming request, proxy to real API, emit receipt."""
        path = request.path
        
        # Determine provider from path
        provider, real_url = self._resolve_provider(path, request)
        
        if not real_url:
            return web.json_response(
                {"error": "Unknown provider. Use /v1/* for OpenAI or /anthropic/* for Anthropic"},
                status=400
            )
        
        # Read request body
        body = await request.read()
        request_data = {}
        try:
            if body:
                request_data = json.loads(body)
        except:
            pass
        
        # Forward headers (strip host, add auth if needed)
        headers = dict(request.headers)
        headers.pop("Host", None)
        headers.pop("host", None)
        
        # Make request to real API
        try:
            async with self.session.request(
                method=request.method,
                url=real_url,
                headers=headers,
                data=body,
            ) as response:
                response_body = await response.read()
                response_data = {}
                try:
                    response_data = json.loads(response_body)
                except:
                    pass
                
                # Emit receipt
                self._emit_receipt(provider, request_data, response_data, path)
                
                # Update stats
                self.stats["requests"] += 1
                self.stats["bytes_proxied"] += len(body) + len(response_body)
                
                # Return response to client
                return web.Response(
                    body=response_body,
                    status=response.status,
                    headers={
                        k: v for k, v in response.headers.items()
                        if k.lower() not in ("transfer-encoding", "content-encoding")
                    },
                )
        
        except Exception as e:
            if self.verbose:
                print(f"[CASCADE PROXY] Error: {e}")
            return web.json_response(
                {"error": f"Proxy error: {str(e)}"},
                status=502
            )
    
    def _resolve_provider(self, path: str, request: web.Request) -> tuple:
        """Resolve which provider to forward to based on path."""
        
        # OpenAI: /v1/* -> api.openai.com/v1/*
        if path.startswith("/v1"):
            return "openai", f"https://api.openai.com{path}"
        
        # Anthropic: /anthropic/* -> api.anthropic.com/*
        if path.startswith("/anthropic"):
            real_path = path[len("/anthropic"):]
            return "anthropic", f"https://api.anthropic.com{real_path}"
        
        # Cohere: /cohere/* -> api.cohere.ai/*
        if path.startswith("/cohere"):
            real_path = path[len("/cohere"):]
            return "cohere", f"https://api.cohere.ai{real_path}"
        
        # Mistral: /mistral/* -> api.mistral.ai/*
        if path.startswith("/mistral"):
            real_path = path[len("/mistral"):]
            return "mistral", f"https://api.mistral.ai{real_path}"
        
        # Custom endpoint via header
        custom_base = request.headers.get("X-Cascade-Forward-To")
        if custom_base:
            return "custom", f"{custom_base}{path}"
        
        return None, None
    
    def _emit_receipt(
        self,
        provider: str,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        path: str,
    ):
        """Emit CASCADE receipt for this request/response."""
        try:
            # Extract model ID
            model_id = self._extract_model_id(provider, request_data, response_data)
            
            # Extract input
            input_text = self._extract_input(provider, request_data)
            
            # Extract output
            output_text = self._extract_output(provider, response_data)
            
            # Extract metrics
            metrics = self._extract_metrics(provider, response_data, request_data)
            
            # Emit via SDK
            self.sdk.observe(
                model_id=model_id,
                input_data=input_text,
                output_data=output_text,
                metrics=metrics,
                context={
                    "provider": provider,
                    "endpoint": path,
                    "via": "proxy",
                }
            )
            
            self.stats["receipts_emitted"] += 1
            
            if self.verbose:
                print(f"[CASCADE] Receipt: {model_id} via proxy")
        
        except Exception as e:
            if self.verbose:
                print(f"[CASCADE] Failed to emit receipt: {e}")
    
    def _extract_model_id(
        self,
        provider: str,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
    ) -> str:
        """Extract canonical model ID."""
        model = request_data.get("model") or response_data.get("model", "unknown")
        return f"{provider}/{model}"
    
    def _extract_input(self, provider: str, request_data: Dict[str, Any]) -> str:
        """Extract input text from request."""
        # Chat completion style
        messages = request_data.get("messages", [])
        if messages:
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if user_msgs:
                content = user_msgs[-1].get("content", "")
                if isinstance(content, list):
                    texts = [c.get("text", "") for c in content if isinstance(c, dict)]
                    return " ".join(texts)
                return str(content)
        
        # Completion style
        return request_data.get("prompt", "")
    
    def _extract_output(self, provider: str, response_data: Dict[str, Any]) -> str:
        """Extract output text from response."""
        # OpenAI style
        choices = response_data.get("choices", [])
        if choices:
            choice = choices[0]
            if "message" in choice:
                return choice["message"].get("content", "")
            if "text" in choice:
                return choice["text"]
        
        # Anthropic style
        content = response_data.get("content", [])
        if content and isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict)]
            return " ".join(texts)
        
        return ""
    
    def _extract_metrics(
        self,
        provider: str,
        response_data: Dict[str, Any],
        request_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract metrics from response."""
        metrics = {}
        
        # Usage stats
        usage = response_data.get("usage", {})
        if usage:
            metrics["prompt_tokens"] = usage.get("prompt_tokens") or usage.get("input_tokens")
            metrics["completion_tokens"] = usage.get("completion_tokens") or usage.get("output_tokens")
            metrics["total_tokens"] = usage.get("total_tokens")
        
        # Request params
        metrics["temperature"] = request_data.get("temperature")
        metrics["max_tokens"] = request_data.get("max_tokens")
        
        return {k: v for k, v in metrics.items() if v is not None}
    
    async def shutdown(self):
        """Shutdown proxy."""
        if self.session:
            await self.session.close()
            self.session = None
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
            self.site = None
        self.sdk.shutdown()
        self._running = False
        if self._stop_event and not self._stop_event.is_set():
            self._stop_event.set()
        
        # Print stats
        runtime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        if self.verbose:
            print(f"""
╔══════════════════════════════════════════════════════════════╗
║  CASCADE PROXY - Shutdown                                    ║
╠══════════════════════════════════════════════════════════════╣
║  Runtime: {runtime:.1f}s                                           ║
║  Requests: {self.stats['requests']}                                          ║
║  Receipts: {self.stats['receipts_emitted']}                                          ║
║  Bytes: {self.stats['bytes_proxied']}                                            ║
╚══════════════════════════════════════════════════════════════╝
""")


def run_proxy(host: str = "0.0.0.0", port: int = 7777, verbose: bool = True):
    """Run the CASCADE proxy server."""
    proxy = CascadeProxy(host=host, port=port, verbose=verbose)
    
    try:
        proxy.start(block=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
        proxy.stop()


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="CASCADE Proxy - Protocol-level AI observation"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=7777, help="Port to listen on")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output")
    
    args = parser.parse_args()
    
    run_proxy(host=args.host, port=args.port, verbose=not args.quiet)
