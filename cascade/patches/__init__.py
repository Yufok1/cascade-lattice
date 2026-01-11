"""
CASCADE Patches - Auto-intercept LLM provider libraries

Each patch module wraps a provider's API to automatically emit receipts.
"""

from .openai_patch import patch_openai
from .anthropic_patch import patch_anthropic
from .huggingface_patch import patch_huggingface
from .ollama_patch import patch_ollama
from .litellm_patch import patch_litellm

__all__ = [
    "patch_openai",
    "patch_anthropic", 
    "patch_huggingface",
    "patch_ollama",
    "patch_litellm",
]
