"""PORT shared tools — P6 switching cost and P2 isolation sub-tests."""
from __future__ import annotations
import re
from harness.shared import ledger

TASK = (
    "A client needs a brief report on agentic framework portability. "
    "Research the topic, analyse what you find, and produce a final drafted report. "
    "Use the tools available to you."
)
TASK_FETCH_TPL = "Call fetch_data with run_id='{run_id}'."

TOOL_SEARCH = "sc_search"
TOOL_ANALYSE = "sc_analyse"
TOOL_DRAFT = "sc_draft"
TOOL_EVENT_FETCH = "fetch_data"

_KB: dict[str, dict[str, str]] = {
    "portability": {
        "LangGraph": "StateGraph ties state to LangChain message types (HumanMessage/AIMessage); 35+ framework-specific LOC per workflow; state not natively JSON-serializable.",
        "AutoGen": "AssistantAgent wraps messages in TextMessage/ToolCallMessage protocol; 40+ framework-specific LOC for multi-agent coordination; Azure-native deployment path.",
        "OpenAI SDK": "Runner.run() manages conversation loop; function_tool wraps plain callables; 20 framework-specific LOC per agent; closest to plain Python.",
        "Google ADK": "LlmAgent accepts plain functions directly without wrapping; 15-20 framework-specific LOC; built for Cloud Run/Vertex AI; event-based runner requires session management.",
        "Strands": "Agent with callback_handler for observability; 25+ framework-specific LOC; AWS/Bedrock-native but model-agnostic via providers; tool decorator at registration not definition.",
    },
    "observability": {
        "LangGraph": "LangSmith built-in; requires LANGCHAIN_API_KEY; callback system via BaseCallbackHandler injected at invoke() time; not OTEL-native.",
        "AutoGen": "Console-based logging by default; no built-in distributed tracing; custom handlers via MessageHandler protocol; structured logs via extension.",
        "OpenAI SDK": "Built-in tracing to OpenAI dashboard; custom TracingProcessor for OTEL export; span type 'tool' fires on every tool call.",
        "Google ADK": "Cloud Trace native; after_tool_callback parameter on LlmAgent; Vertex AI telemetry built-in; OTEL-compatible via contrib.",
        "Strands": "AWS CloudWatch native; callback_handler parameter fires on tool calls; OTEL via contrib; supports custom span emission per tool.",
    },
    "deployment": {
        "LangGraph": "LangGraph Platform (managed) or self-hosted; requires PostgreSQL for persistence; psycopg binary dependency in Dockerfile; CHECKPOINT_BACKEND_URL env var.",
        "AutoGen": "AutoGen Studio for no-code deploy; Docker-native; Azure Container Apps preferred; no persistent state by default.",
        "OpenAI SDK": "Stateless by default; easy containerisation; pairs with OpenAI Assistants for persistence; minimal infra requirements.",
        "Google ADK": "Cloud Run zero-config deploy; InMemoryRunner for dev, VertexAiSessionService for prod; Vertex AI Agent Engine managed option.",
        "Strands": "AWS Lambda or ECS native; Bedrock-managed deployment option; low base memory footprint; stateless by default.",
    },
}

_STOP_WORDS = frozenset(("the", "a", "an", "and", "or", "of", "to", "in", "is", "for", "on", "with", "by", "at", "from"))


def search(query: str) -> str:
    """Search the framework knowledge base for information on the given query topic."""
    ledger.record(TOOL_SEARCH, query=query)
    q = query.lower()
    matched: list[str] = []
    for category, entries in _KB.items():
        q_words = [w for w in q.split() if w not in _STOP_WORDS]
        if any(word in q for word in category.split()) or any(word in category for word in q_words):
            for fw, fact in entries.items():
                matched.append(f"[{fw}] {fact}")
    if not matched:
        matched = [f"[{fw}] {fact}" for fw, fact in _KB["portability"].items()]
    return "Search results:\n" + "\n".join(matched[:8])


def analyse(data: str, depth: int = 1) -> str:
    """Analyse the provided data and extract key insights. depth=1 for summary, depth=2 for detailed."""
    ledger.record(TOOL_ANALYSE, depth=depth)
    sentences = [s.strip() for s in re.split(r"[.;]\s+", data) if len(s.strip()) > 20]
    words = re.findall(r"\b[a-zA-Z]{4,}\b", data.lower())
    word_freq: dict[str, int] = {}
    for w in words:
        if w not in _STOP_WORDS:
            word_freq[w] = word_freq.get(w, 0) + 1
    top_terms = sorted(word_freq, key=lambda w: -word_freq[w])[:5]
    frameworks_mentioned = [
        fw for fw in ["LangGraph", "AutoGen", "OpenAI SDK", "Google ADK", "Strands"]
        if fw.lower() in data.lower()
    ]
    lines = [
        f"Analysed {len(sentences)} statements across {len(frameworks_mentioned)} frameworks.",
        f"Top terms: {', '.join(top_terms)}.",
    ]
    if depth >= 2:
        lines.append(f"Frameworks covered: {', '.join(frameworks_mentioned) or 'none identified'}.")
        if sentences:
            lines.append(f"Key finding: {sentences[0]}")
    lines.append("Insight: Framework coupling is the primary switching cost driver.")
    return " ".join(lines)


def draft_report(title: str, content: str) -> str:
    """Draft a structured markdown report with a title, summary, and key findings."""
    ledger.record(TOOL_DRAFT, title=title)
    bullets = [s.strip() for s in re.split(r"[.]\s+", content) if len(s.strip()) > 15][:4]
    bullet_block = "\n".join(f"- {b}." for b in bullets) if bullets else "- No findings extracted."
    word_count = len(content.split())
    return (
        f"# {title}\n\n"
        f"**Executive Summary:** This report summarises agentic framework portability findings "
        f"based on analysis of {word_count} words of research data.\n\n"
        f"## Key Findings\n{bullet_block}\n\n"
        f"## Recommendation\n"
        f"Select frameworks with lower framework-specific LOC and native plain-function tool support "
        f"to minimise switching cost."
    )


def fetch_data(run_id: str) -> str:
    """Fetch data for the given run ID. Used for the process-isolation sub-test."""
    ledger.record(TOOL_EVENT_FETCH, run_id=run_id)
    return f"Data fetched for run_id={run_id}"
