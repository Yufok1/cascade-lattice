"""
OpenAI API Patch - Intercepts OpenAI Responses and Completions calls.
"""

import functools
import inspect
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..sdk import CascadeSDK


def patch_openai(sdk: "CascadeSDK"):
    """
    Patch the OpenAI library to emit receipts on every call.

    Intercepts:
    - openai.responses.create()
    - openai.OpenAI().responses.create()
    - openai.chat.completions.create()
    - openai.completions.create()
    - openai.OpenAI().chat.completions.create()
    """
    import openai

    # Store original methods for debugging/readability.
    _original_responses_create = None
    _original_chat_create = None
    _original_completions_create = None

    def extract_model_id(kwargs, response):
        """Extract canonical model identifier."""
        model = kwargs.get("model", "unknown")
        return f"openai/{model}"

    def extract_input(kwargs):
        """Extract input from Responses, Chat Completions, or legacy Completions kwargs."""
        if "input" in kwargs:
            return _stable_text(kwargs.get("input"))
        messages = kwargs.get("messages", [])
        if messages:
            user_msgs = [m for m in messages if _message_role(m) == "user"]
            if user_msgs:
                return _stable_text(_message_content(user_msgs[-1]))
        return kwargs.get("prompt", "")

    def extract_output(response):
        """Extract output from response."""
        try:
            output_text = getattr(response, "output_text", None)
            if output_text:
                return output_text

            output = getattr(response, "output", None)
            if output:
                text = _extract_response_output_items(output)
                if text:
                    return text

            if hasattr(response, "choices") and response.choices:
                choice = response.choices[0]
                if hasattr(choice, "message"):
                    return choice.message.content
                if hasattr(choice, "text"):
                    return choice.text

            return str(response)
        except Exception:
            return str(response)

    def extract_metrics(response, kwargs):
        """Extract usage metrics."""
        metrics = {}
        try:
            if hasattr(response, "usage") and response.usage:
                usage = response.usage
                for source_name, target_name in [
                    ("prompt_tokens", "prompt_tokens"),
                    ("completion_tokens", "completion_tokens"),
                    ("input_tokens", "input_tokens"),
                    ("output_tokens", "output_tokens"),
                    ("total_tokens", "total_tokens"),
                ]:
                    value = _read_attr_or_key(usage, source_name)
                    if value is not None:
                        metrics[target_name] = value

            metrics["temperature"] = kwargs.get("temperature", 1.0)
            metrics["max_tokens"] = kwargs.get("max_tokens")
            metrics["max_output_tokens"] = kwargs.get("max_output_tokens")
        except Exception:
            pass
        return metrics

    def observe_response(kwargs, response, endpoint):
        sdk.observe(
            model_id=extract_model_id(kwargs, response),
            input_data=extract_input(kwargs),
            output_data=extract_output(response),
            metrics=extract_metrics(response, kwargs),
            context={"provider": "openai", "endpoint": endpoint},
        )

    def wrap_create(original, endpoint):
        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            response = original(*args, **kwargs)
            try:
                observe_response(kwargs, response, endpoint)
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] OpenAI observation failed: {e}")
            return response

        return wrapper

    def wrap_async_create(original, endpoint):
        @functools.wraps(original)
        async def wrapper(*args, **kwargs):
            response = await original(*args, **kwargs)
            try:
                observe_response(kwargs, response, endpoint)
            except Exception as e:
                if sdk.config.get("verbose"):
                    print(f"[CASCADE] OpenAI observation failed: {e}")
            return response

        return wrapper

    def wrap_auto_create(original, endpoint):
        if inspect.iscoroutinefunction(original):
            return wrap_async_create(original, endpoint)
        return wrap_create(original, endpoint)

    def wrap_responses_create(original):
        return wrap_auto_create(original, "responses")

    def wrap_chat_create(original):
        return wrap_auto_create(original, "chat.completions")

    def wrap_completions_create(original):
        return wrap_auto_create(original, "completions")

    if hasattr(openai, "responses"):
        _original_responses_create = openai.responses.create
        openai.responses.create = wrap_responses_create(_original_responses_create)

    if hasattr(openai, "chat") and hasattr(openai.chat, "completions"):
        _original_chat_create = openai.chat.completions.create
        openai.chat.completions.create = wrap_chat_create(_original_chat_create)

    if hasattr(openai, "completions"):
        _original_completions_create = openai.completions.create
        openai.completions.create = wrap_completions_create(_original_completions_create)

    if hasattr(openai, "OpenAI"):
        _OriginalClient = openai.OpenAI

        class PatchedOpenAI(_OriginalClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if hasattr(self, "responses"):
                    original_responses = self.responses.create
                    self.responses.create = wrap_responses_create(original_responses)
                if hasattr(self, "chat") and hasattr(self.chat, "completions"):
                    original_chat = self.chat.completions.create
                    self.chat.completions.create = wrap_chat_create(original_chat)
                if hasattr(self, "completions"):
                    original_comp = self.completions.create
                    self.completions.create = wrap_completions_create(original_comp)

        openai.OpenAI = PatchedOpenAI

    if hasattr(openai, "AsyncOpenAI"):
        _OriginalAsyncClient = openai.AsyncOpenAI

        class PatchedAsyncOpenAI(_OriginalAsyncClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if hasattr(self, "responses"):
                    original_responses = self.responses.create
                    self.responses.create = wrap_responses_create(original_responses)
                if hasattr(self, "chat") and hasattr(self.chat, "completions"):
                    original_chat = self.chat.completions.create
                    self.chat.completions.create = wrap_chat_create(original_chat)
                if hasattr(self, "completions"):
                    original_comp = self.completions.create
                    self.completions.create = wrap_completions_create(original_comp)

        openai.AsyncOpenAI = PatchedAsyncOpenAI


def _read_attr_or_key(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _message_role(message):
    if isinstance(message, dict):
        return message.get("role")
    return getattr(message, "role", None)


def _message_content(message):
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", "")


def _stable_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return str(value)


def _extract_response_output_items(items):
    chunks = []
    for item in items:
        content = _read_attr_or_key(item, "content")
        if not content:
            text = _read_attr_or_key(item, "text")
            if text:
                chunks.append(str(text))
            continue
        if isinstance(content, str):
            chunks.append(content)
            continue
        for part in content:
            text = _read_attr_or_key(part, "text")
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)
