from __future__ import annotations
import warnings

from harness.shared.llm import openai_compat

# create_react_agent still works in langgraph 1.x but warns that it moved to langchain.agents.
warnings.filterwarnings("ignore", message=".*create_react_agent.*")


def chat_model():
    from langchain_openai import ChatOpenAI
    c = openai_compat()
    return ChatOpenAI(model=c["model"], base_url=c["base_url"], api_key=c["api_key"],
                      default_headers=c["headers"])
