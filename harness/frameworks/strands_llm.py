from __future__ import annotations

from harness.shared.llm import openai_compat


def model():
    from strands.models.openai import OpenAIModel
    c = openai_compat()
    return OpenAIModel(client_args={"base_url": c["base_url"], "api_key": c["api_key"],
                                    "default_headers": c["headers"]}, model_id=c["model"])
