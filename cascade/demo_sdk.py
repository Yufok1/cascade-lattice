"""
CASCADE SDK Demo - Shows automatic observation of calls.

Run: python -m cascade.demo_sdk
"""

import os
import sys

# Add cascade to path if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def demo_manual_observation():
    """Demo manual observation without any provider installed."""
    print("=" * 60)
    print("CASCADE SDK Demo - Manual Observation")
    print("=" * 60)
    
    import cascade
    from cascade.sdk import CascadeSDK
    
    # Initialize with verbose mode
    sdk = CascadeSDK()
    sdk.init(emit_async=False, verbose=True)
    
    print("\n[1] Simulating an OpenAI call...")
    sdk.observe(
        model_id="openai/gpt-4",
        input_data="What is the capital of France?",
        output_data="The capital of France is Paris.",
        metrics={"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        context={"provider": "openai", "endpoint": "chat.completions"}
    )
    
    print("\n[2] Simulating an Anthropic call...")
    sdk.observe(
        model_id="anthropic/claude-3-opus-20240229",
        input_data="Explain quantum entanglement simply.",
        output_data="Quantum entanglement is when two particles become connected...",
        metrics={"input_tokens": 6, "output_tokens": 45},
        context={"provider": "anthropic", "endpoint": "messages"}
    )
    
    print("\n[3] Simulating an Ollama local call...")
    sdk.observe(
        model_id="ollama/llama2:7b",
        input_data="Write a haiku about coding.",
        output_data="Fingers on keyboard\nLogic flows like mountain stream\nBugs become features",
        metrics={"eval_count": 20, "eval_duration": 1.5},
        context={"provider": "ollama", "endpoint": "generate"}
    )
    
    print("\n" + "=" * 60)
    print("Observations saved to lattice/observations/")
    print("=" * 60)
    
    # Show what was saved
    from cascade.observation import ObservationManager
    manager = ObservationManager()
    stats = manager.get_stats()
    print(f"\nTotal observations: {stats['total_observations']}")
    print(f"Model observations: {stats['model_observations']}")
    print(f"Unique models: {stats['unique_models']}")


def demo_auto_patch():
    """Demo auto-patching (requires providers to be installed)."""
    print("\n" + "=" * 60)
    print("CASCADE Auto-Patch Demo")
    print("=" * 60)
    
    import cascade
    
    # This patches all installed providers
    cascade.init(verbose=True)
    
    print("\nPatched providers. Now any call will emit receipts.")
    print("Example usage:")
    print("""
    import cascade
    cascade.init()
    
    # OpenAI (if installed)
    import openai
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    # ^^^ Receipt automatically emitted to lattice
    
    # Anthropic (if installed)
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello!"}]
    )
    # ^^^ Receipt automatically emitted to lattice
    
    # Ollama (if installed)
    import ollama
    response = ollama.chat(model="llama2", messages=[
        {"role": "user", "content": "Hello!"}
    ])
    # ^^^ Receipt automatically emitted to lattice
    """)


if __name__ == "__main__":
    demo_manual_observation()
    demo_auto_patch()
