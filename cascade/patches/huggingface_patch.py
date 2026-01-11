"""
HuggingFace Patch - Intercepts transformers and inference API calls.
"""

import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..sdk import CascadeSDK


def patch_huggingface(sdk: "CascadeSDK"):
    """
    Patch HuggingFace libraries to emit receipts.
    
    Intercepts:
    - transformers.pipeline().__call__()
    - transformers.AutoModelForCausalLM.generate()
    - huggingface_hub.InferenceClient()
    """
    
    # Try to patch transformers
    try:
        _patch_transformers(sdk)
    except ImportError:
        pass
    
    # Try to patch huggingface_hub inference
    try:
        _patch_inference_client(sdk)
    except ImportError:
        pass


def _patch_transformers(sdk: "CascadeSDK"):
    """Patch transformers library."""
    import transformers
    
    def extract_model_id(pipe_or_model):
        """Extract model identifier from pipeline or model."""
        try:
            if hasattr(pipe_or_model, "model"):
                model = pipe_or_model.model
            else:
                model = pipe_or_model
            
            # Try to get model name from config
            if hasattr(model, "config"):
                if hasattr(model.config, "_name_or_path"):
                    return f"hf/{model.config._name_or_path}"
                if hasattr(model.config, "name_or_path"):
                    return f"hf/{model.config.name_or_path}"
            
            # Fallback to class name
            return f"hf/{model.__class__.__name__}"
        except:
            return "hf/unknown"
    
    # Patch pipeline
    _OriginalPipeline = transformers.pipeline
    
    @functools.wraps(_OriginalPipeline)
    def patched_pipeline(*args, **kwargs):
        pipe = _OriginalPipeline(*args, **kwargs)
        
        # Wrap the __call__ method
        original_call = pipe.__call__
        
        @functools.wraps(original_call)
        def wrapped_call(*call_args, **call_kwargs):
            result = original_call(*call_args, **call_kwargs)
            
            try:
                # Extract input
                input_data = call_args[0] if call_args else call_kwargs.get("inputs", "")
                if isinstance(input_data, list):
                    input_data = input_data[0] if input_data else ""
                
                # Extract output
                if isinstance(result, list) and result:
                    output = result[0]
                    if isinstance(output, dict):
                        output = output.get("generated_text", output.get("text", str(output)))
                else:
                    output = str(result)
                
                sdk.observe(
                    model_id=extract_model_id(pipe),
                    input_data=str(input_data),
                    output_data=str(output),
                    metrics={"task": pipe.task if hasattr(pipe, "task") else "unknown"},
                    context={"provider": "huggingface", "endpoint": "pipeline"}
                )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] HuggingFace pipeline observation failed: {e}")
            
            return result
        
        pipe.__call__ = wrapped_call
        return pipe
    
    transformers.pipeline = patched_pipeline
    
    # Patch AutoModelForCausalLM.generate
    if hasattr(transformers, "AutoModelForCausalLM"):
        _OriginalAutoModel = transformers.AutoModelForCausalLM
        
        class PatchedAutoModelForCausalLM(_OriginalAutoModel):
            @classmethod
            def from_pretrained(cls, *args, **kwargs):
                model = super().from_pretrained(*args, **kwargs)
                
                # Wrap generate
                original_generate = model.generate
                
                @functools.wraps(original_generate)
                def wrapped_generate(*gen_args, **gen_kwargs):
                    result = original_generate(*gen_args, **gen_kwargs)
                    
                    try:
                        sdk.observe(
                            model_id=extract_model_id(model),
                            input_data=f"tokens:{gen_args[0].shape if gen_args else 'unknown'}",
                            output_data=f"tokens:{result.shape if hasattr(result, 'shape') else 'unknown'}",
                            metrics={
                                "max_new_tokens": gen_kwargs.get("max_new_tokens"),
                                "temperature": gen_kwargs.get("temperature", 1.0),
                            },
                            context={"provider": "huggingface", "endpoint": "generate"}
                        )
                    except Exception as e:
                        if sdk.config.get("verbose"):
                            print(f"[CASCADE] HuggingFace generate observation failed: {e}")
                    
                    return result
                
                model.generate = wrapped_generate
                return model
        
        transformers.AutoModelForCausalLM = PatchedAutoModelForCausalLM


def _patch_inference_client(sdk: "CascadeSDK"):
    """Patch huggingface_hub InferenceClient."""
    from huggingface_hub import InferenceClient
    
    _OriginalClient = InferenceClient
    
    class PatchedInferenceClient(_OriginalClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._model_id = kwargs.get("model", args[0] if args else "unknown")
        
        def text_generation(self, prompt, **kwargs):
            result = super().text_generation(prompt, **kwargs)
            
            try:
                sdk.observe(
                    model_id=f"hf-inference/{self._model_id}",
                    input_data=prompt,
                    output_data=result,
                    metrics={
                        "max_new_tokens": kwargs.get("max_new_tokens"),
                        "temperature": kwargs.get("temperature"),
                    },
                    context={"provider": "huggingface", "endpoint": "inference_api"}
                )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] HF Inference observation failed: {e}")
            
            return result
        
        def chat_completion(self, messages, **kwargs):
            result = super().chat_completion(messages, **kwargs)
            
            try:
                # Extract last user message
                user_msgs = [m for m in messages if m.get("role") == "user"]
                input_text = user_msgs[-1].get("content", "") if user_msgs else ""
                
                # Extract output
                output_text = ""
                if hasattr(result, "choices") and result.choices:
                    output_text = result.choices[0].message.content
                
                sdk.observe(
                    model_id=f"hf-inference/{self._model_id}",
                    input_data=input_text,
                    output_data=output_text,
                    metrics={},
                    context={"provider": "huggingface", "endpoint": "chat_completion"}
                )
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] HF Inference observation failed: {e}")
            
            return result
    
    # Replace the class
    import huggingface_hub
    huggingface_hub.InferenceClient = PatchedInferenceClient
