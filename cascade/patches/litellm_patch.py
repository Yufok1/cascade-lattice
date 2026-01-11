"""
LiteLLM Patch - Intercepts litellm.completion() which unifies all providers.

LiteLLM is particularly valuable because it's a universal interface -
patching it catches calls to OpenAI, Anthropic, Cohere, Azure, Bedrock,
Vertex AI, Ollama, and many more through a single integration point.
"""

import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..sdk import CascadeSDK


def patch_litellm(sdk: "CascadeSDK"):
    """
    Patch LiteLLM to emit receipts on every call.
    
    Intercepts:
    - litellm.completion()
    - litellm.acompletion()
    - litellm.text_completion()
    """
    import litellm
    
    def extract_model_id(kwargs, response=None):
        """Extract canonical model identifier."""
        model = kwargs.get("model", "unknown")
        # LiteLLM uses provider/model format: openai/gpt-4, anthropic/claude-3, etc.
        # If no provider prefix, add litellm/
        if "/" not in model:
            return f"litellm/{model}"
        return model
    
    def extract_input(kwargs):
        """Extract input from kwargs."""
        messages = kwargs.get("messages", [])
        if messages:
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if user_msgs:
                content = user_msgs[-1].get("content", "")
                if isinstance(content, list):
                    texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    return " ".join(texts)
                return content
        return kwargs.get("prompt", "")
    
    def extract_output(response):
        """Extract output from response."""
        try:
            if hasattr(response, "choices") and response.choices:
                choice = response.choices[0]
                if hasattr(choice, "message") and choice.message:
                    return choice.message.content
                if hasattr(choice, "text"):
                    return choice.text
            return str(response)
        except:
            return str(response)
    
    def extract_metrics(response, kwargs):
        """Extract usage metrics."""
        metrics = {}
        try:
            if hasattr(response, "usage") and response.usage:
                if hasattr(response.usage, "prompt_tokens"):
                    metrics["prompt_tokens"] = response.usage.prompt_tokens
                if hasattr(response.usage, "completion_tokens"):
                    metrics["completion_tokens"] = response.usage.completion_tokens
                if hasattr(response.usage, "total_tokens"):
                    metrics["total_tokens"] = response.usage.total_tokens
            
            # Request params
            metrics["temperature"] = kwargs.get("temperature", 1.0)
            metrics["max_tokens"] = kwargs.get("max_tokens")
            
            # Response metadata
            if hasattr(response, "model"):
                metrics["response_model"] = response.model
        except:
            pass
        return {k: v for k, v in metrics.items() if v is not None}
    
    # Patch litellm.completion
    if hasattr(litellm, "completion"):
        _original_completion = litellm.completion
        
        @functools.wraps(_original_completion)
        def patched_completion(*args, **kwargs):
            response = _original_completion(*args, **kwargs)
            
            try:
                sdk.observe(
                    model_id=extract_model_id(kwargs, response),
                    input_data=extract_input(kwargs),
                    output_data=extract_output(response),
                    metrics=extract_metrics(response, kwargs),
                    context={
                        "provider": "litellm",
                        "endpoint": "completion",
                        "api_base": kwargs.get("api_base", "default")
                    }
                )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] LiteLLM completion observation failed: {e}")
            
            return response
        
        litellm.completion = patched_completion
    
    # Patch litellm.text_completion
    if hasattr(litellm, "text_completion"):
        _original_text_completion = litellm.text_completion
        
        @functools.wraps(_original_text_completion)
        def patched_text_completion(*args, **kwargs):
            response = _original_text_completion(*args, **kwargs)
            
            try:
                sdk.observe(
                    model_id=extract_model_id(kwargs, response),
                    input_data=kwargs.get("prompt", ""),
                    output_data=extract_output(response),
                    metrics=extract_metrics(response, kwargs),
                    context={
                        "provider": "litellm",
                        "endpoint": "text_completion"
                    }
                )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] LiteLLM text_completion observation failed: {e}")
            
            return response
        
        litellm.text_completion = patched_text_completion
    
    # Patch litellm.batch_completion if available
    if hasattr(litellm, "batch_completion"):
        _original_batch = litellm.batch_completion
        
        @functools.wraps(_original_batch)
        def patched_batch_completion(*args, **kwargs):
            responses = _original_batch(*args, **kwargs)
            
            try:
                messages_list = kwargs.get("messages", [])
                model = kwargs.get("model", "unknown")
                
                # Emit one observation per batch item
                for i, response in enumerate(responses if responses else []):
                    input_msgs = messages_list[i] if i < len(messages_list) else []
                    
                    sdk.observe(
                        model_id=extract_model_id({"model": model}, response),
                        input_data=extract_input({"messages": input_msgs}),
                        output_data=extract_output(response),
                        metrics=extract_metrics(response, kwargs),
                        context={
                            "provider": "litellm",
                            "endpoint": "batch_completion",
                            "batch_index": i
                        }
                    )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] LiteLLM batch_completion observation failed: {e}")
            
            return responses
        
        litellm.batch_completion = patched_batch_completion
    
    # Note: Async versions (acompletion, etc.) would need async wrappers
    # TODO: Implement async observation for litellm.acompletion
