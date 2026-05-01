import sys
import types
import unittest

from cascade.patches.openai_patch import patch_openai


class FakeUsage:
    input_tokens = 4
    output_tokens = 7
    total_tokens = 11


class FakeResponse:
    model = "gpt-test"
    output_text = "receipt kept"
    usage = FakeUsage()


class FakeResponses:
    def create(self, **kwargs):
        return FakeResponse()


class FakeMessage:
    content = "chat receipt"


class FakeChoice:
    message = FakeMessage()


class FakeChatResponse:
    model = "gpt-chat-test"
    choices = [FakeChoice()]
    usage = {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8}


class FakeChatCompletions:
    def create(self, **kwargs):
        return FakeChatResponse()


class FakeChat:
    def __init__(self):
        self.completions = FakeChatCompletions()


class FakeOpenAI:
    def __init__(self, *args, **kwargs):
        self.responses = FakeResponses()
        self.chat = FakeChat()


class FakeSDK:
    def __init__(self):
        self.config = {"verbose": False}
        self.calls = []

    def observe(self, **kwargs):
        self.calls.append(kwargs)


class OpenAIPatchTests(unittest.TestCase):
    def setUp(self):
        self.previous_openai = sys.modules.get("openai")
        module = types.ModuleType("openai")
        module.OpenAI = FakeOpenAI
        module.responses = FakeResponses()
        sys.modules["openai"] = module

    def tearDown(self):
        if self.previous_openai is None:
            sys.modules.pop("openai", None)
        else:
            sys.modules["openai"] = self.previous_openai

    def test_patch_observes_client_responses_create(self):
        sdk = FakeSDK()
        patch_openai(sdk)

        import openai

        response = openai.OpenAI().responses.create(
            model="gpt-test",
            input="keep a receipt",
            max_output_tokens=40,
        )

        self.assertEqual(response.output_text, "receipt kept")
        self.assertEqual(len(sdk.calls), 1)
        call = sdk.calls[0]
        self.assertEqual(call["model_id"], "openai/gpt-test")
        self.assertEqual(call["input_data"], "keep a receipt")
        self.assertEqual(call["output_data"], "receipt kept")
        self.assertEqual(call["context"], {"provider": "openai", "endpoint": "responses"})
        self.assertEqual(call["metrics"]["input_tokens"], 4)
        self.assertEqual(call["metrics"]["output_tokens"], 7)
        self.assertEqual(call["metrics"]["total_tokens"], 11)
        self.assertEqual(call["metrics"]["max_output_tokens"], 40)

    def test_patch_observes_module_responses_create(self):
        sdk = FakeSDK()
        patch_openai(sdk)

        import openai

        openai.responses.create(model="gpt-test", input=[{"role": "user", "content": "hi"}])

        self.assertEqual(len(sdk.calls), 1)
        self.assertEqual(sdk.calls[0]["context"]["endpoint"], "responses")
        self.assertIn("role", sdk.calls[0]["input_data"])

    def test_patch_preserves_chat_completions_observation(self):
        sdk = FakeSDK()
        patch_openai(sdk)

        import openai

        openai.OpenAI().chat.completions.create(
            model="gpt-chat-test",
            messages=[{"role": "user", "content": "hello"}],
        )

        self.assertEqual(len(sdk.calls), 1)
        call = sdk.calls[0]
        self.assertEqual(call["model_id"], "openai/gpt-chat-test")
        self.assertEqual(call["input_data"], "hello")
        self.assertEqual(call["output_data"], "chat receipt")
        self.assertEqual(call["context"], {"provider": "openai", "endpoint": "chat.completions"})


if __name__ == "__main__":
    unittest.main()
