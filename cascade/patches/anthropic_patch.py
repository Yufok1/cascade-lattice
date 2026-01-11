"""
Anthropic API Patch - Intercepts anthropic.messages.create() etc.
"""

import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..sdk import CascadeSDK


def patch_anthropic(sdk: "CascadeSDK"):
    """
    Patch the Anthropic library to emit receipts on every call.
    
    Intercepts:
    - anthropic.Anthropic().messages.create()
    - anthropic.AsyncAnthropic().messages.create()
    """
    import anthropic
    
    def extract_model_id(kwargs, response):
        """Extract canonical model identifier."""
        model = kwargs.get("model", "unknown")
        # claude-3-opus-20240229, claude-3-sonnet-20240229, etc.
        return f"anthropic/{model}"
    
    def extract_input(kwargs):
        """Extract input from kwargs."""
        messages = kwargs.get("messages", [])
        if messages:
            # Get the last user message
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if user_msgs:
                content = user_msgs[-1].get("content", "")
                # Content could be string or list of content blocks
                if isinstance(content, list):
                    texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                    return " ".join(texts)
                return content
        return ""
    
    def extract_output(response):
        """Extract output from response."""
        try:
            if hasattr(response, "content") and response.content:
                # Content is a list of content blocks
                texts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        texts.append(block.text)
                return " ".join(texts)
            return str(response)
        except:
            return str(response)
    
    def extract_metrics(response, kwargs):
        """Extract usage metrics."""
        metrics = {}
        try:
            if hasattr(response, "usage") and response.usage:
                metrics["input_tokens"] = response.usage.input_tokens
                metrics["output_tokens"] = response.usage.output_tokens
            
            # Add request params
            metrics["max_tokens"] = kwargs.get("max_tokens")
            metrics["temperature"] = kwargs.get("temperature", 1.0)
            
            # Stop reason
            if hasattr(response, "stop_reason"):
                metrics["stop_reason"] = response.stop_reason
        except:
            pass
        return metrics
    
    def wrap_messages_create(original):
        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            # Call original
            response = original(*args, **kwargs)
            
            # Emit receipt (non-blocking)
            try:
                sdk.observe(
                    model_id=extract_model_id(kwargs, response),
                    input_data=extract_input(kwargs),
                    output_data=extract_output(response),
                    metrics=extract_metrics(response, kwargs),
                    context={
                        "provider": "anthropic",
                        "endpoint": "messages",
                        "system": kwargs.get("system", "")[:200]  # First 200 chars of system prompt
                    }
                )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] Anthropic observation failed: {e}")
            
            return response
        return wrapper
    
    # Patch the Anthropic client class
    if hasattr(anthropic, "Anthropic"):
        _OriginalClient = anthropic.Anthropic
        
        class PatchedAnthropic(_OriginalClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Wrap the instance methods
                original_create = self.messages.create
                self.messages.create = wrap_messages_create(original_create)
        
        anthropic.Anthropic = PatchedAnthropic
    
    # Patch AsyncAnthropic if available
    if hasattr(anthropic, "AsyncAnthropic"):
        _OriginalAsyncClient = anthropic.AsyncAnthropic
        
        class PatchedAsyncAnthropic(_OriginalAsyncClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # TODO: Implement async observation wrappers
        
        anthropic.AsyncAnthropic = PatchedAsyncAnthropic
