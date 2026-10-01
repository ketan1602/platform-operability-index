from __future__ import annotations

from harness.shared.llm import openai_compat


def chat_client():
    from autogen_core.models import ModelFamily, ModelInfo
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    c = openai_compat()
    # model_info is mandatory for model names OpenAI's client doesn't recognise.
    info = ModelInfo(vision=False, function_calling=True, json_output=True,
                     family=ModelFamily.UNKNOWN, structured_output=True)
    return OpenAIChatCompletionClient(model=c["model"], base_url=c["base_url"], api_key=c["api_key"],
                                      default_headers=c["headers"], model_info=info)
