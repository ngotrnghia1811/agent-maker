# agent-maker

**Compile LLM agents the way you compile code.**

`agent-maker` is to LLM agents what `make` and `cmake` are to C/C++ binaries: a
declarative pipeline that takes a high-level spec — your use case, your
provider preference, your auth, your output format — and produces a ready-to-run
agent. No glue code, no provider-specific scaffolding, no plumbing.

Underneath sits a unified async runtime for seven providers across three
transport layers (browser automation, HTTP API, CLI subprocess), so the same
spec can target Claude, Gemini, GPT, Perplexity, OpenAI, OpenRouter, or GitHub
Copilot interchangeably.

## The `agent-make` philosophy

```
spec  →  agent-make  →  agent
```

Just like `make` reads a `Makefile` and decides what to build, `agent-make`
reads a requirement (interactive interview, preset name, or JSON spec) and
resolves it into:

1. **A provider** (the right LLM for the job)
2. **A transport** (browser / API / CLI — whichever your auth supports)
3. **An agent class** (chat, data extraction, translator, research, …)
4. **A config** (model, thinking effort, JSON mode, storage state, …)

The output is either a live agent instance, a standalone Python script, or a
deployable package — your choice.

## Features

- **`agent-make` CLI** — interactive interview, preset shortcuts, or JSON-spec
  driven compilation; auth auto-detection picks the transport that will
  actually work on your machine
- **7 providers** — Claude, Gemini, GPT, Perplexity (browser); OpenAI,
  OpenRouter (API); Copilot (CLI)
- **3 transport layers** — Playwright browser automation with stealth mode,
  HTTP API via httpx, CLI subprocess
- **Extended thinking extraction** — Claude (3 strategies: API interception,
  fetch override, React fiber), Gemini (API interception)
- **Multi-agent monitoring** — event bus, agent registry, real-time dashboard,
  reporting
- **Conversation history** — sliding-window with configurable max turns
- **Translation pipeline** — chunk-based translation with conversation
  splitting and progress tracking
- **Data extraction** — structured JSON output with shared prompt builder
- **Async-first** — `asyncio` throughout, context-manager support

## Requirements

- Python 3.10+
- [Playwright](https://playwright.dev/python/) (for browser agents)

## Installation

```bash
git clone <repo-url> agent-maker
cd agent-maker
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Install Playwright browsers (for browser agents)
playwright install chromium
```

This installs the `agent-make` console script.

## Configuration

Copy the environment template and fill in your keys:

```bash
cp .env.example .env
```

| Variable             | Required for      | Description                                                     |
| -------------------- | ----------------- | --------------------------------------------------------------- |
| `OPENROUTER_API_KEY` | OpenRouter agents | API key from [openrouter.ai](https://openrouter.ai)             |
| `OPENAI_API_KEY`     | OpenAI agents     | API key from [platform.openai.com](https://platform.openai.com) |

Browser agents (Claude, Gemini, GPT, Perplexity) use Playwright storage state
files for authentication. Log in manually once, then save the session:

```bash
python -m universal_agents.browser.save_login claude
```

`agent-make` will detect available credentials and refuse to compile an agent
whose transport can't authenticate.

## Quick start: `agent-make`

```bash
# Interactive interview — answers any unknowns by asking you
agent-make --interactive

# Preset shortcuts (skip the interview)
agent-make --preset free-chat
agent-make --preset openai-data
agent-make --preset research

# List available presets
agent-make --list-presets

# Reproducible build from a JSON spec
agent-make --spec my_requirements.json --output agent_script.py
```

Or compile programmatically:

```python
from universal_agents.compiler import AgentCompiler

compiler = AgentCompiler()

compiled = compiler.compile_from_spec({
    "use_case": "data",
    "provider_preference": "openai",
    "needs_json_output": True,
    "output_format": "instance",
})

agent = compiled.agent_instance
response = await agent.chat("Extract key facts from this text...")
```

## Using a compiled agent directly

You can also bypass the compiler and use the runtime directly.

### API agent

```python
import asyncio
from universal_agents.providers.openrouter.chat import OpenRouterChatAgent
from universal_agents.providers.openrouter.config import OpenRouterConfig

async def main():
    config = OpenRouterConfig(model="anthropic/claude-sonnet-4")
    async with OpenRouterChatAgent(config) as agent:
        response = await agent.chat("What is the capital of France?")
        print(response)

asyncio.run(main())
```

### Browser agent

```python
import asyncio
from universal_agents.providers.claude.chat import ClaudeChatAgent
from universal_agents.providers.claude.config import ClaudeConfig

async def main():
    config = ClaudeConfig()  # uses CLAUDE_STORAGE_STATE env var
    async with ClaudeChatAgent(config) as agent:
        response = await agent.chat("What is the capital of France?")
        print(response)

        response = await agent.chat("What about Germany?")
        print(response)

        stats = agent.get_stats()
        print(f"{stats.total_turns} turns, avg {stats.avg_processing_time_ms:.0f}ms")

asyncio.run(main())
```

## Architecture

```
universal_agents/
├── core/               # Shared abstractions
│   ├── base_agent.py   # BaseChatAgent (ABC) — async chat(), history, stats
│   ├── config.py       # BaseConfig → BrowserConfig, APIConfig
│   ├── types.py        # Message, ConversationTurn, TurnResult, AgentStats
│   ├── history.py      # Sliding-window conversation history
│   ├── exceptions.py   # AgentError → BrowserError, APIError, CLIError
│   └── retry.py        # @retry with exponential backoff
│
├── browser/            # Playwright browser automation layer
│   ├── base_browser_agent.py   # Shared chat loop: input → submit → wait → extract
│   ├── browser_manager.py      # Lifecycle, stealth mode, API interception
│   ├── dom.py                  # DOM utilities
│   └── response_detector.py    # 2-phase response detection
│
├── api/                # HTTP API layer
│   └── base_api_agent.py       # httpx-based with sync/streaming support
│
├── cli/                # CLI subprocess layer
│   └── base_cli_agent.py
│
├── providers/          # Provider implementations
│   ├── claude/         # Chat, Data, Translator agents
│   ├── gemini/         # Chat, Data, Translator agents
│   ├── gpt/            # Chat agent
│   ├── pplx/           # Chat agent (Perplexity)
│   ├── openai/         # Chat, Data agents (API)
│   ├── openrouter/     # Chat, Data agents (API)
│   └── copilot/        # Chat agent (CLI)
│
├── compiler/           # The agent-make pipeline
│   ├── compiler.py             # AgentCompiler orchestrator
│   ├── __main__.py             # `agent-make` CLI entrypoint
│   ├── question_flow.py        # Interactive interview with skip logic
│   ├── capability_resolver.py  # Maps requirements → provider + agent class
│   ├── config_builder.py       # Builds transport-specific config dicts
│   ├── agent_assembler.py      # Script generation + dynamic instantiation
│   ├── agent_packager.py       # Deployable package emission
│   ├── compiler_llm.py         # LLM for interpreting free-text answers
│   ├── auth_detector.py        # Detects available credentials
│   └── requirements.py         # UserRequirements dataclass
│
└── monitor/            # Multi-agent monitoring
    ├── agent_registry.py       # Central registry
    ├── monitored_agent.py      # Event-emitting agent wrapper
    ├── events.py               # Event types
    ├── dashboard.py            # Real-time terminal dashboard
    └── reporter.py             # JSON/text reports
```

## Providers

| Provider   | Transport | Agents                 | Thinking         | Notes                                         |
| ---------- | --------- | ---------------------- | ---------------- | --------------------------------------------- |
| Claude     | Browser   | Chat, Data, Translator | 3 strategies     | API interception, fetch override, React fiber |
| Gemini     | Browser   | Chat, Data, Translator | API interception | Model selector support                        |
| GPT        | Browser   | Chat                   | —                |                                               |
| Perplexity | Browser   | Chat, Research         | —                | Citation selectors                            |
| OpenAI     | API       | Chat, Data             | Reasoning effort | `gpt-4o`, `o3-mini`, etc.                     |
| OpenRouter | API       | Chat, Data             | Model-dependent  | 200+ models via unified API                   |
| Copilot    | CLI       | Chat                   | —                | GitHub Copilot CLI subprocess                 |

## `agent-make` presets

| Preset             | Use Case    | Provider   | Key Features                       |
| ------------------ | ----------- | ---------- | ---------------------------------- |
| `free-chat`        | Chat        | OpenRouter | Free models, no API cost           |
| `openai-data`      | Data        | OpenAI     | JSON output, thinking enabled      |
| `openrouter-free`  | Data        | OpenRouter | Free data extraction               |
| `claude-translate` | Translation | Claude     | File upload, translation pipeline  |
| `research`         | Research    | Perplexity | Citations enabled                  |
| `code-review`      | Code        | OpenAI     | Thinking enabled for code analysis |

Reproducible builds: every compilation writes a `source_spec.json` alongside
the generated agent. Recompile any time with `agent-make --spec
source_spec.json`.

## Testing

```bash
# Unit tests (fast, no external deps)
python -m pytest tests/unit/ -q

# Verbose
python -m pytest tests/unit/ -v

# Integration (requires API keys / browser auth)
python -m pytest tests/integration/ -m integration
```

## Examples

See the [`examples/`](examples/) directory:

- [`basic_chat.py`](examples/basic_chat.py) — single-agent chat with stats
- [`multi_agent_run.py`](examples/multi_agent_run.py) — concurrent
  multi-provider run with monitoring
- [`translation_job.py`](examples/translation_job.py) — chunk-based translation
  with progress tracking

## License

Private — all rights reserved.
