"""
Ollama Patch - Intercepts ollama library calls.
"""

import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..sdk import CascadeSDK


def patch_ollama(sdk: "CascadeSDK"):
    """
    Patch the Ollama library to emit receipts.
    
    Intercepts:
    - ollama.chat()
    - ollama.generate()
    - ollama.Client().chat()
    - ollama.Client().generate()
    """
    import ollama
    
    def extract_model_id(kwargs, response=None):
        """Extract canonical model identifier."""
        model = kwargs.get("model", "unknown")
        # Could be llama2, mistral, codellama:7b-instruct, etc.
        return f"ollama/{model}"
    
    def extract_input_from_messages(messages):
        """Extract input from message list."""
        if messages:
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if user_msgs:
                return user_msgs[-1].get("content", "")
        return ""
    
    def extract_output(response):
        """Extract output from response."""
        try:
            if isinstance(response, dict):
                # Chat response
                if "message" in response:
                    return response["message"].get("content", "")
                # Generate response
                if "response" in response:
                    return response["response"]
            return str(response)
        except:
            return str(response)
    
    def extract_metrics(response):
        """Extract metrics from response."""
        metrics = {}
        try:
            if isinstance(response, dict):
                metrics["eval_count"] = response.get("eval_count")
                metrics["eval_duration"] = response.get("eval_duration")
                metrics["prompt_eval_count"] = response.get("prompt_eval_count")
                metrics["total_duration"] = response.get("total_duration")
        except:
            pass
        return {k: v for k, v in metrics.items() if v is not None}
    
    # Patch ollama.chat
    if hasattr(ollama, "chat"):
        _original_chat = ollama.chat
        
        @functools.wraps(_original_chat)
        def patched_chat(*args, **kwargs):
            response = _original_chat(*args, **kwargs)
            
            try:
                messages = kwargs.get("messages", args[1] if len(args) > 1 else [])
                model = kwargs.get("model", args[0] if args else "unknown")
                
                sdk.observe(
                    model_id=f"ollama/{model}",
                    input_data=extract_input_from_messages(messages),
                    output_data=extract_output(response),
                    metrics=extract_metrics(response),
                    context={"provider": "ollama", "endpoint": "chat"}
                )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] Ollama chat observation failed: {e}")
            
            return response
        
        ollama.chat = patched_chat
    
    # Patch ollama.generate
    if hasattr(ollama, "generate"):
        _original_generate = ollama.generate
        
        @functools.wraps(_original_generate)
        def patched_generate(*args, **kwargs):
            response = _original_generate(*args, **kwargs)
            
            try:
                model = kwargs.get("model", args[0] if args else "unknown")
                prompt = kwargs.get("prompt", args[1] if len(args) > 1 else "")
                
                sdk.observe(
                    model_id=f"ollama/{model}",
                    input_data=prompt,
                    output_data=extract_output(response),
                    metrics=extract_metrics(response),
                    context={"provider": "ollama", "endpoint": "generate"}
                )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] Ollama generate observation failed: {e}")
            
            return response
        
        ollama.generate = patched_generate
    
    # Patch ollama.Client class
    if hasattr(ollama, "Client"):
        _OriginalClient = ollama.Client
        
        class PatchedClient(_OriginalClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                
                # Wrap chat
                original_chat = self.chat
                @functools.wraps(original_chat)
                def wrapped_chat(*chat_args, **chat_kwargs):
                    response = original_chat(*chat_args, **chat_kwargs)
                    
                    try:
                        messages = chat_kwargs.get("messages", chat_args[1] if len(chat_args) > 1 else [])
                        model = chat_kwargs.get("model", chat_args[0] if chat_args else "unknown")
                        
                        sdk.observe(
                            model_id=f"ollama/{model}",
                            input_data=extract_input_from_messages(messages),
                            output_data=extract_output(response),
                            metrics=extract_metrics(response),
                            context={"provider": "ollama", "endpoint": "client.chat"}
                        )
                    except Exception as e:
                        if sdk.config.get("verbose"):
                            print(f"[CASCADE] Ollama client chat observation failed: {e}")
                    
                    return response
                
                self.chat = wrapped_chat
                
                # Wrap generate
                original_generate = self.generate
                @functools.wraps(original_generate)
                def wrapped_generate(*gen_args, **gen_kwargs):
                    response = original_generate(*gen_args, **gen_kwargs)
                    
                    try:
                        model = gen_kwargs.get("model", gen_args[0] if gen_args else "unknown")
                        prompt = gen_kwargs.get("prompt", gen_args[1] if len(gen_args) > 1 else "")
                        
                        sdk.observe(
                            model_id=f"ollama/{model}",
                            input_data=prompt,
                            output_data=extract_output(response),
                            metrics=extract_metrics(response),
                            context={"provider": "ollama", "endpoint": "client.generate"}
                        )
                    except Exception as e:
                        if sdk.config.get("verbose"):
                            print(f"[CASCADE] Ollama client generate observation failed: {e}")
                    
                    return response
                
                self.generate = wrapped_generate
        
        ollama.Client = PatchedClient
