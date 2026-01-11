"""
CASCADE CLI - Full-featured Rich TUI for cascade-ai.

Exposes all CASCADE capabilities:
- Lattice: stats, list, inspect, chains, pin, export, watch
- Model: observe, fingerprint
- Data: entities, provenance, pii scan
- System: logs, analyze, ingest
- Proxy: start intercepting proxy
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

# Rich imports with fallback
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.text import Text
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console() if HAS_RICH else None


# ═══════════════════════════════════════════════════════════════════════════════
# LATTICE COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_stats(args):
    """Show lattice statistics with Rich panels."""
    from cascade.observation import ObservationManager
    
    manager = ObservationManager()
    stats = manager.get_stats()
    
    if HAS_RICH:
        stats_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        stats_table.add_column("Key", style="cyan")
        stats_table.add_column("Value", style="green")
        
        stats_table.add_row("Genesis Root", f"[bold magenta]{stats['genesis_root']}[/]")
        stats_table.add_row("", "")
        stats_table.add_row("Total Observations", str(stats['total_observations']))
        stats_table.add_row("  └─ Model", str(stats['model_observations']))
        stats_table.add_row("  └─ Data", str(stats['data_observations']))
        stats_table.add_row("  └─ System", str(stats['system_observations']))
        stats_table.add_row("", "")
        stats_table.add_row("Registered Models", str(stats['registered_models']))
        stats_table.add_row("Unique Models Observed", str(stats['unique_models']))
        
        panel = Panel(
            stats_table,
            title="[bold cyan]CASCADE LATTICE[/]",
            subtitle="[dim]The Neural Internetwork[/]",
            border_style="cyan",
        )
        console.print(panel)
    else:
        print(f"""
CASCADE LATTICE STATS
═════════════════════
Genesis Root: {stats['genesis_root']}

Observations:
  Total:  {stats['total_observations']}
  Model:  {stats['model_observations']}
  Data:   {stats['data_observations']}
  System: {stats['system_observations']}

Models:
  Registered: {stats['registered_models']}
  Observed:   {stats['unique_models']}
""")


def cmd_list(args):
    """List recent observations."""
    from cascade.observation import ObservationManager
    
    manager = ObservationManager()
    observations = manager.list_observations(limit=args.limit)
    
    if not observations:
        if HAS_RICH:
            console.print("[yellow]No observations yet.[/]")
        else:
            print("No observations yet.")
        return
    
    if HAS_RICH:
        table = Table(title=f"Recent Observations", box=box.ROUNDED)
        table.add_column("Type", style="cyan", width=8)
        table.add_column("Source", style="white", max_width=40)
        table.add_column("Merkle Root", style="magenta")
        table.add_column("Time", style="dim")
        
        for obs in observations:
            obs_type = obs.get('observation_type', '?')[:7]
            source = obs.get('source_id', 'unknown')[:39]
            merkle = obs.get('merkle_root', '?')[:16]
            timestamp = obs.get('timestamp', '')
            if timestamp:
                try:
                    if isinstance(timestamp, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
                    else:
                        timestamp = str(timestamp)[:8]
                except:
                    timestamp = '?'
            
            table.add_row(obs_type, source, merkle, timestamp)
        
        console.print(table)
        console.print(f"[dim]Showing {len(observations)} of {manager.get_stats()['total_observations']}[/]")
    else:
        print(f"\n{'TYPE':<8} {'SOURCE':<40} {'MERKLE ROOT':<20}")
        print("─" * 70)
        for obs in observations:
            print(f"{obs.get('observation_type', '?')[:7]:<8} {obs.get('source_id', '?')[:39]:<40} {obs.get('merkle_root', '?')[:19]:<20}")


def cmd_inspect(args):
    """Inspect a specific observation by merkle root."""
    from cascade.observation import ObservationManager
    
    manager = ObservationManager()
    obs = manager.get_observation(args.root)
    
    if not obs:
        if HAS_RICH:
            console.print(f"[red]Observation not found:[/] {args.root}")
        else:
            print(f"Observation not found: {args.root}")
        return
    
    if HAS_RICH:
        tree = Tree(f"[bold magenta]{args.root}[/]")
        
        for key, value in obs.items():
            if isinstance(value, dict):
                branch = tree.add(f"[cyan]{key}[/]")
                for k, v in value.items():
                    branch.add(f"[dim]{k}:[/] {v}")
            elif isinstance(value, list):
                branch = tree.add(f"[cyan]{key}[/] ({len(value)} items)")
                for item in value[:5]:
                    branch.add(str(item)[:60])
                if len(value) > 5:
                    branch.add(f"[dim]... and {len(value) - 5} more[/]")
            else:
                tree.add(f"[cyan]{key}:[/] {value}")
        
        console.print(Panel(tree, title="Observation Details", border_style="magenta"))
    else:
        print(json.dumps(obs, indent=2, default=str))


def cmd_chains(args):
    """List all chains in the lattice."""
    from cascade.viz.lattice_gateway import load_lattice_data
    
    data = load_lattice_data()
    chains = data.get('chains', [])
    
    if HAS_RICH:
        table = Table(title="Lattice Chains", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Merkle Root", style="magenta")
        table.add_column("Records", justify="right")
        table.add_column("CID", style="dim")
        
        for chain in chains:
            name = chain.get('name', '?')
            root = chain.get('merkle_root', '?')[:16]
            records = len(chain.get('records', {}))
            cid = chain.get('cid', 'Not pinned')
            if cid and cid != 'Not pinned':
                cid = cid[:20] + '...'
            
            style = "bold green" if name == 'genesis' else None
            table.add_row(name, root, str(records), cid, style=style)
        
        console.print(table)
        console.print(f"\n[dim]Genesis: {data.get('genesis_root', 'N/A')}[/]")
    else:
        print(f"Chains in lattice: {len(chains)}")
        for chain in chains:
            print(f"  {chain.get('name')}: {chain.get('merkle_root', '?')[:16]} ({len(chain.get('records', {}))} records)")


def cmd_pin(args):
    """Pin observation to IPFS."""
    from cascade.observation import ObservationManager
    
    manager = ObservationManager()
    obs = manager.get_observation(args.root)
    
    if not obs:
        if HAS_RICH:
            console.print(f"[red]Observation not found:[/] {args.root}")
        else:
            print(f"Observation not found: {args.root}")
        return
    
    if HAS_RICH:
        with console.status("[cyan]Pinning to IPFS...[/]"):
            cid = manager.pin_to_ipfs(obs)
        
        if cid:
            console.print(f"[green]✓ Pinned to IPFS[/]")
            console.print(f"  CID: [magenta]{cid}[/]")
            console.print(f"  URL: https://storacha.link/ipfs/{cid}")
        else:
            console.print("[red]✗ Failed to pin[/]")
    else:
        print(f"Pinning {args.root}...")
        cid = manager.pin_to_ipfs(obs)
        if cid:
            print(f"✓ Pinned: {cid}")
        else:
            print("✗ Failed")


def cmd_export(args):
    """Export lattice or chain to file."""
    from cascade.viz.lattice_gateway import load_lattice_data
    
    data = load_lattice_data()
    
    if args.chain:
        chains = [c for c in data.get('chains', []) if c['name'] == args.chain]
        if not chains:
            msg = f"Chain not found: {args.chain}"
            console.print(f"[red]{msg}[/]") if HAS_RICH else print(msg)
            return
        export_data = chains[0]
    else:
        export_data = data
    
    output = Path(args.output)
    output.write_text(json.dumps(export_data, indent=2, default=str))
    
    msg = f"✓ Exported to {output}"
    console.print(f"[green]{msg}[/]") if HAS_RICH else print(msg)


def cmd_watch(args):
    """Watch live observations in real-time."""
    from cascade.observation import ObservationManager
    import time
    
    manager = ObservationManager()
    last_count = 0
    
    if HAS_RICH:
        console.print("[cyan]Watching for observations... (Ctrl+C to stop)[/]\n")
    else:
        print("Watching... (Ctrl+C to stop)")
    
    try:
        while True:
            stats = manager.get_stats()
            current = stats['total_observations']
            
            if current > last_count:
                new_obs = manager.list_observations(limit=current - last_count)
                for obs in reversed(new_obs):
                    if HAS_RICH:
                        console.print(
                            f"[green]●[/] [{datetime.now().strftime('%H:%M:%S')}] "
                            f"[cyan]{obs.get('observation_type', '?')}[/] "
                            f"[white]{obs.get('source_id', '?')[:40]}[/] "
                            f"[magenta]{obs.get('merkle_root', '?')[:16]}[/]"
                        )
                    else:
                        print(f"● {obs.get('observation_type', '?')} {obs.get('merkle_root', '?')[:16]}")
                last_count = current
            
            time.sleep(1)
    except KeyboardInterrupt:
        msg = "\nStopped watching."
        console.print(f"[yellow]{msg}[/]") if HAS_RICH else print(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL COMMANDS  
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_observe(args):
    """Manually observe a model interaction."""
    from cascade import observe
    
    result = observe(
        model_id=args.model,
        input_data=args.input,
        output_data=args.output,
        observation_type='model',
    )
    
    if HAS_RICH:
        console.print(f"[green]✓ Observed[/]")
        console.print(f"  Merkle Root: [magenta]{result.get('merkle_root', 'N/A')}[/]")
    else:
        print(f"Observed: {result.get('merkle_root', 'N/A')}")


def cmd_fingerprint(args):
    """Generate model fingerprint."""
    try:
        from cascade.forensics.fingerprints import ModelFingerprinter
        
        if HAS_RICH:
            with console.status(f"[cyan]Fingerprinting {args.model}...[/]"):
                fp = ModelFingerprinter()
                result = fp.fingerprint(args.model)
            
            if result:
                table = Table(title=f"Fingerprint: {args.model}", box=box.ROUNDED)
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="white")
                
                for key, value in result.items():
                    if isinstance(value, dict):
                        value = json.dumps(value)[:50] + '...'
                    table.add_row(str(key), str(value)[:60])
                
                console.print(table)
            else:
                console.print("[yellow]Could not fingerprint model[/]")
        else:
            fp = ModelFingerprinter()
            result = fp.fingerprint(args.model)
            print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        msg = f"Error: {e}"
        console.print(f"[red]{msg}[/]") if HAS_RICH else print(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_entities(args):
    """Run entity resolution on a file."""
    try:
        from cascade.data.entities import EntityResolver
        
        if HAS_RICH:
            with console.status(f"[cyan]Resolving entities in {args.file}...[/]"):
                resolver = EntityResolver()
                result = resolver.resolve_file(args.file)
            
            if result:
                console.print(f"[green]✓ Found {len(result)} entities[/]")
                
                table = Table(box=box.SIMPLE)
                table.add_column("Entity", style="cyan")
                table.add_column("Type", style="magenta")
                table.add_column("Count", justify="right")
                
                for entity in result[:20]:
                    table.add_row(
                        str(entity.get('name', '?'))[:30],
                        entity.get('type', '?'),
                        str(entity.get('count', 1))
                    )
                
                console.print(table)
                if len(result) > 20:
                    console.print(f"[dim]... and {len(result) - 20} more[/]")
        else:
            resolver = EntityResolver()
            result = resolver.resolve_file(args.file)
            print(f"Found {len(result)} entities")
    except Exception as e:
        msg = f"Error: {e}"
        console.print(f"[red]{msg}[/]") if HAS_RICH else print(msg)


def cmd_pii(args):
    """Scan for PII in a file."""
    try:
        from cascade.data.pii import PIIScanner
        
        if HAS_RICH:
            with console.status(f"[cyan]Scanning {args.file} for PII...[/]"):
                scanner = PIIScanner()
                results = scanner.scan_file(args.file)
            
            if results:
                console.print(f"[yellow]⚠ Found {len(results)} potential PII instances[/]")
                
                table = Table(box=box.ROUNDED)
                table.add_column("Type", style="red")
                table.add_column("Value", style="yellow")
                table.add_column("Location", style="dim")
                
                for pii in results[:20]:
                    val = pii.get('value', '?')
                    table.add_row(
                        pii.get('type', '?'),
                        val[:30] + '...' if len(val) > 30 else val,
                        str(pii.get('location', '?'))
                    )
                
                console.print(table)
            else:
                console.print("[green]✓ No PII detected[/]")
        else:
            scanner = PIIScanner()
            results = scanner.scan_file(args.file)
            print(f"Found {len(results)} PII instances")
    except Exception as e:
        msg = f"Error: {e}"
        console.print(f"[red]{msg}[/]") if HAS_RICH else print(msg)


def cmd_provenance(args):
    """Show data provenance for a file/dataset."""
    try:
        from cascade.data.provenance import DataProvenance
        
        if HAS_RICH:
            with console.status(f"[cyan]Analyzing provenance...[/]"):
                prov = DataProvenance()
                result = prov.analyze(args.path)
            
            if result:
                tree = Tree(f"[bold cyan]{args.path}[/]")
                
                if 'hash' in result:
                    tree.add(f"[magenta]Hash:[/] {result['hash']}")
                if 'sources' in result:
                    sources = tree.add("[cyan]Sources[/]")
                    for src in result['sources']:
                        sources.add(str(src))
                if 'transformations' in result:
                    transforms = tree.add("[cyan]Transformations[/]")
                    for t in result['transformations']:
                        transforms.add(str(t))
                
                console.print(Panel(tree, title="Data Provenance", border_style="cyan"))
        else:
            prov = DataProvenance()
            result = prov.analyze(args.path)
            print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        msg = f"Error: {e}"
        console.print(f"[red]{msg}[/]") if HAS_RICH else print(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_ingest(args):
    """Ingest logs/files into the lattice."""
    try:
        from cascade.system.repo_ingester import RepoIngester
        
        if HAS_RICH:
            with console.status(f"[cyan]Ingesting {args.path}...[/]"):
                ingester = RepoIngester()
                result = ingester.ingest(args.path)
            
            console.print(f"[green]✓ Ingested[/]")
            console.print(f"  Files: {result.get('files', 0)}")
            console.print(f"  Observations: {result.get('observations', 0)}")
            console.print(f"  Merkle Root: [magenta]{result.get('merkle_root', 'N/A')}[/]")
        else:
            ingester = RepoIngester()
            result = ingester.ingest(args.path)
            print(f"Ingested: {result}")
    except Exception as e:
        msg = f"Error: {e}"
        console.print(f"[red]{msg}[/]") if HAS_RICH else print(msg)


def cmd_analyze(args):
    """Analyze a log file or folder."""
    try:
        from cascade.system.omnidirectional_analyzer import OmnidirectionalAnalyzer
        
        if HAS_RICH:
            with console.status(f"[cyan]Analyzing {args.path}...[/]"):
                analyzer = OmnidirectionalAnalyzer()
                result = analyzer.analyze(args.path)
            
            if result:
                console.print(Panel(
                    Syntax(json.dumps(result, indent=2, default=str), "json"),
                    title="Analysis Result",
                    border_style="cyan"
                ))
        else:
            analyzer = OmnidirectionalAnalyzer()
            result = analyzer.analyze(args.path)
            print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        msg = f"Error: {e}"
        console.print(f"[red]{msg}[/]") if HAS_RICH else print(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# PROXY & INIT
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_proxy(args):
    """Start the CASCADE proxy server."""
    if HAS_RICH:
        console.print(Panel(
            f"""[cyan]CASCADE Proxy Server[/]
            
Listening on [bold]{args.host}:{args.port}[/]

Set these environment variables in your app:
[green]
  OPENAI_BASE_URL=http://localhost:{args.port}/v1
  ANTHROPIC_BASE_URL=http://localhost:{args.port}/anthropic
[/]
Press Ctrl+C to stop.""",
            title="🌐 Proxy Mode",
            border_style="cyan",
        ))
    else:
        print(f"CASCADE Proxy on {args.host}:{args.port}")
    
    from cascade.proxy import run_proxy
    run_proxy(host=args.host, port=args.port, verbose=not args.quiet)


def cmd_init(args):
    """Show initialization instructions."""
    if HAS_RICH:
        md = """
# CASCADE Setup

## Option 1: Auto-Patch (Python)
```python
import cascade
cascade.init()

# Now every call emits a receipt
from openai import OpenAI
client = OpenAI()
client.chat.completions.create(...)  # ← automatically observed
```

## Option 2: Proxy Mode (Any Language)
```bash
cascade proxy --port 7777
```
Then set environment variables:
```bash
export OPENAI_BASE_URL=http://localhost:7777/v1
export ANTHROPIC_BASE_URL=http://localhost:7777/anthropic
```

## Option 3: Manual Observation
```python
from cascade import observe
observe(model_id="my-model", input_data="prompt", output_data="response")
```

---
**Genesis Root:** `89f940c1a4b7aa65`
"""
        console.print(Panel(Markdown(md), title="[bold cyan]CASCADE[/]", border_style="cyan"))
    else:
        print("""
CASCADE - Universal AI Provenance Layer

OPTION 1: Auto-Patch (Python)
  import cascade
  cascade.init()

OPTION 2: Proxy Mode (Any Language)  
  cascade proxy
  export OPENAI_BASE_URL=http://localhost:7777/v1

OPTION 3: Manual
  from cascade import observe
  observe(model_id="...", input_data="...", output_data="...")
""")


def cmd_version(args):
    """Show version."""
    try:
        from cascade import __version__
        version = __version__
    except:
        version = "0.1.1"
    
    if HAS_RICH:
        console.print(f"[cyan]cascade-ai[/] [bold]{version}[/]")
        console.print(f"[dim]Genesis: 89f940c1a4b7aa65[/]")
    else:
        print(f"cascade-ai {version}")


# ═══════════════════════════════════════════════════════════════════════════════
# HOLD COMMANDS - Inference-Level Halt Protocol
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_hold_status(args):
    """Show HOLD system status."""
    try:
        from cascade.hold import Hold
        hold = Hold.get()
        
        if HAS_RICH:
            from rich.table import Table
            
            table = Table(title="🛑 HOLD System Status", box=box.SIMPLE)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Hold Count", str(hold._hold_count))
            table.add_row("Override Count", str(hold._override_count))
            table.add_row("Timeout", f"{hold.timeout}s")
            table.add_row("Auto Accept", str(hold.auto_accept))
            table.add_row("Listeners", str(len(hold._listeners)))
            table.add_row("Last Merkle", hold._last_merkle or "None")
            table.add_row("Current Hold", "Active" if hold._current_hold else "None")
            
            console.print(table)
        else:
            print(f"HOLD Count: {hold._hold_count}")
            print(f"Override Count: {hold._override_count}")
            print(f"Timeout: {hold.timeout}s")
            print(f"Listeners: {len(hold._listeners)}")
    except Exception as e:
        if HAS_RICH:
            console.print(f"[red]Error: {e}[/]")
        else:
            print(f"Error: {e}")


def cmd_hold_info(args):
    """Show HOLD usage information."""
    info = """
🛑 HOLD - Inference-Level Halt Protocol

HOLD pauses AI inference so humans can observe and intervene.

USAGE IN YOUR CODE:
    from cascade.hold import Hold
    
    hold = Hold.get()
    
    # In your inference loop:
    probs = model.predict(observation)
    
    resolution = hold.yield_point(
        action_probs=probs,
        value=value_estimate,
        observation=obs,
        brain_id="my_model",
        # Optional informational wealth:
        action_labels=["up", "down", "left", "right"],
        latent=model.latent,
        attention=model.attention,
        features=model.features,
        imagination=model.imagine(),
    )
    
    action = resolution.action        # Final action (AI or override)
    was_override = resolution.was_override  # True if human intervened

REGISTERING LISTENERS:
    def my_handler(hold_point):
        print(f"HOLD: {hold_point.action_probs}")
        # Send to UI, game engine, logger, etc.
    
    hold.register_listener(my_handler)

RESOLVING HOLDS:
    hold.resolve(action=3, source="human")  # Override with action 3
    hold.accept()                            # Accept AI's choice
"""
    if HAS_RICH:
        console.print(Panel(info, title="[bold red]HOLD[/]", border_style="red"))
    else:
        print(info)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="cascade",
        description="CASCADE - Universal AI Provenance Layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cascade stats                    Show lattice statistics
  cascade list -n 20               List recent observations
  cascade chains                   List all chains
  cascade inspect <root>           Inspect an observation
  cascade watch                    Live observation feed
  cascade proxy                    Start proxy server
  cascade fingerprint <model>      Fingerprint a model
  cascade pii <file>               Scan file for PII
  cascade ingest <path>            Ingest logs/files
        """
    )
    parser.add_argument("--version", "-v", action="store_true", help="Show version")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # ─── Lattice commands ───
    subparsers.add_parser("stats", help="Show lattice statistics").set_defaults(func=cmd_stats)
    subparsers.add_parser("chains", help="List all chains").set_defaults(func=cmd_chains)
    subparsers.add_parser("init", help="Show setup instructions").set_defaults(func=cmd_init)
    subparsers.add_parser("watch", help="Watch live observations").set_defaults(func=cmd_watch)
    
    list_p = subparsers.add_parser("list", help="List recent observations")
    list_p.add_argument("--limit", "-n", type=int, default=10, help="Number to show")
    list_p.set_defaults(func=cmd_list)
    
    inspect_p = subparsers.add_parser("inspect", help="Inspect an observation")
    inspect_p.add_argument("root", help="Merkle root to inspect")
    inspect_p.set_defaults(func=cmd_inspect)
    
    pin_p = subparsers.add_parser("pin", help="Pin observation to IPFS")
    pin_p.add_argument("root", help="Merkle root to pin")
    pin_p.set_defaults(func=cmd_pin)
    
    export_p = subparsers.add_parser("export", help="Export lattice/chain to JSON")
    export_p.add_argument("--chain", "-c", help="Export specific chain")
    export_p.add_argument("--output", "-o", default="cascade_export.json", help="Output file")
    export_p.set_defaults(func=cmd_export)
    
    # ─── Model commands ───
    observe_p = subparsers.add_parser("observe", help="Manual observation")
    observe_p.add_argument("--model", "-m", required=True, help="Model ID")
    observe_p.add_argument("--input", "-i", required=True, help="Input data")
    observe_p.add_argument("--output", "-o", required=True, help="Output data")
    observe_p.set_defaults(func=cmd_observe)
    
    fp_p = subparsers.add_parser("fingerprint", help="Fingerprint a model")
    fp_p.add_argument("model", help="Model name/path")
    fp_p.set_defaults(func=cmd_fingerprint)
    
    # ─── Data commands ───
    entities_p = subparsers.add_parser("entities", help="Entity resolution")
    entities_p.add_argument("file", help="File to analyze")
    entities_p.set_defaults(func=cmd_entities)
    
    pii_p = subparsers.add_parser("pii", help="Scan for PII")
    pii_p.add_argument("file", help="File to scan")
    pii_p.set_defaults(func=cmd_pii)
    
    prov_p = subparsers.add_parser("provenance", help="Data provenance")
    prov_p.add_argument("path", help="File or dataset path")
    prov_p.set_defaults(func=cmd_provenance)
    
    # ─── System commands ───
    ingest_p = subparsers.add_parser("ingest", help="Ingest logs/files")
    ingest_p.add_argument("path", help="Path to ingest")
    ingest_p.set_defaults(func=cmd_ingest)
    
    analyze_p = subparsers.add_parser("analyze", help="Analyze logs/files")
    analyze_p.add_argument("path", help="Path to analyze")
    analyze_p.set_defaults(func=cmd_analyze)
    
    # ─── Proxy ───
    proxy_p = subparsers.add_parser("proxy", help="Start proxy server")
    proxy_p.add_argument("--host", default="0.0.0.0", help="Host to bind")
    proxy_p.add_argument("--port", "-p", type=int, default=7777, help="Port")
    proxy_p.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")
    proxy_p.set_defaults(func=cmd_proxy)
    
    # ─── HOLD - Inference-Level Halt Protocol ───
    hold_p = subparsers.add_parser("hold", help="Show HOLD usage and API info")
    hold_p.set_defaults(func=cmd_hold_info)
    
    hold_status_p = subparsers.add_parser("hold-status", help="Show HOLD system status")
    hold_status_p.set_defaults(func=cmd_hold_status)
    
    # Parse
    args = parser.parse_args()
    
    if args.version:
        cmd_version(args)
        return
    
    if not args.command:
        if HAS_RICH:
            console.print(Panel(
                """[cyan]CASCADE[/] - Universal AI Provenance Layer

[bold]Lattice Commands:[/]
  [green]stats[/]        Show lattice statistics
  [green]chains[/]       List all chains  
  [green]list[/]         List recent observations
  [green]inspect[/]      Inspect an observation
  [green]watch[/]        Live observation feed
  [green]pin[/]          Pin to IPFS
  [green]export[/]       Export to JSON

[bold]Model Commands:[/]
  [green]observe[/]      Manual observation
  [green]fingerprint[/]  Fingerprint a model

[bold]Data Commands:[/]
  [green]entities[/]     Entity resolution
  [green]pii[/]          PII scanner
  [green]provenance[/]   Data provenance

[bold]System Commands:[/]
  [green]ingest[/]       Ingest files/logs
  [green]analyze[/]      Analyze files

[bold]HOLD (Inference Halt):[/]
  [green]hold[/]         Show HOLD usage and API info
  [green]hold-status[/]  Show HOLD system status

[bold]Other:[/]
  [green]proxy[/]        Start proxy server
  [green]init[/]         Setup instructions

Use [cyan]cascade <command> --help[/] for details.""",
                title="[bold magenta]🌀 CASCADE[/]",
                subtitle="[dim]pip install cascade-ai[/]",
                border_style="magenta",
            ))
        else:
            parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
