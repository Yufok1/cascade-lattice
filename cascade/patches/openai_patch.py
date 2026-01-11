"""
OpenAI API Patch - Intercepts openai.chat.completions.create() etc.
"""

import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..sdk import CascadeSDK


def patch_openai(sdk: "CascadeSDK"):
    """
    Patch the OpenAI library to emit receipts on every call.
    
    Intercepts:
    - openai.chat.completions.create()
    - openai.completions.create()
    - openai.Client().chat.completions.create()
    """
    import openai
    
    # Store original methods
    _original_chat_create = None
    _original_completions_create = None
    
    def extract_model_id(kwargs, response):
        """Extract canonical model identifier."""
        model = kwargs.get("model", "unknown")
        # Could be gpt-4, gpt-4-turbo, gpt-4-0125-preview, etc.
        return f"openai/{model}"
    
    def extract_input(kwargs):
        """Extract input from kwargs."""
        messages = kwargs.get("messages", [])
        if messages:
            # Get the last user message
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if user_msgs:
                return user_msgs[-1].get("content", "")
        return kwargs.get("prompt", "")
    
    def extract_output(response):
        """Extract output from response."""
        try:
            # Chat completion
            if hasattr(response, "choices") and response.choices:
                choice = response.choices[0]
                if hasattr(choice, "message"):
                    return choice.message.content
                elif hasattr(choice, "text"):
                    return choice.text
            return str(response)
        except:
            return str(response)
    
    def extract_metrics(response, kwargs):
        """Extract usage metrics."""
        metrics = {}
        try:
            if hasattr(response, "usage") and response.usage:
                metrics["prompt_tokens"] = response.usage.prompt_tokens
                metrics["completion_tokens"] = response.usage.completion_tokens
                metrics["total_tokens"] = response.usage.total_tokens
            
            # Add request params
            metrics["temperature"] = kwargs.get("temperature", 1.0)
            metrics["max_tokens"] = kwargs.get("max_tokens")
        except:
            pass
        return metrics
    
    def wrap_chat_create(original):
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
                    context={"provider": "openai", "endpoint": "chat.completions"}
                )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] OpenAI observation failed: {e}")
            
            return response
        return wrapper
    
    def wrap_completions_create(original):
        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            response = original(*args, **kwargs)
            
            try:
                sdk.observe(
                    model_id=extract_model_id(kwargs, response),
                    input_data=kwargs.get("prompt", ""),
                    output_data=extract_output(response),
                    metrics=extract_metrics(response, kwargs),
                    context={"provider": "openai", "endpoint": "completions"}
                )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] OpenAI observation failed: {e}")
            
            return response
        return wrapper
    
    # Patch the module-level client if it exists
    if hasattr(openai, "chat") and hasattr(openai.chat, "completions"):
        _original_chat_create = openai.chat.completions.create
        openai.chat.completions.create = wrap_chat_create(_original_chat_create)
    
    if hasattr(openai, "completions"):
        _original_completions_create = openai.completions.create
        openai.completions.create = wrap_completions_create(_original_completions_create)
    
    # Patch the OpenAI client class
    if hasattr(openai, "OpenAI"):
        _OriginalClient = openai.OpenAI
        
        class PatchedOpenAI(_OriginalClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Wrap the instance methods
                original_chat = self.chat.completions.create
                self.chat.completions.create = wrap_chat_create(original_chat)
                
                if hasattr(self, "completions"):
                    original_comp = self.completions.create
                    self.completions.create = wrap_completions_create(original_comp)
        
        openai.OpenAI = PatchedOpenAI
    
    # Also patch AsyncOpenAI if available
    if hasattr(openai, "AsyncOpenAI"):
        _OriginalAsyncClient = openai.AsyncOpenAI
        
        class PatchedAsyncOpenAI(_OriginalAsyncClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # For async, we'd need async wrappers
                # TODO: Implement async observation
        
        openai.AsyncOpenAI = PatchedAsyncOpenAI
