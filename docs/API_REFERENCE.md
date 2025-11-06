# API Reference

## Core

### `BaseChatAgent` (`core/base_agent.py`)

Abstract base class for all agents.

| Method          | Signature                                   | Description                           |
| --------------- | ------------------------------------------- | ------------------------------------- |
| `chat`          | `async chat(message: str, **kwargs) -> str` | Send message, get response (abstract) |
| `get_history`   | `get_history() -> list[Message]`            | All messages in session               |
| `get_turns`     | `get_turns() -> list[ConversationTurn]`     | All user↔assistant turns              |
| `get_stats`     | `get_stats() -> AgentStats`                 | Session statistics                    |
| `clear_history` | `clear_history() -> None`                   | Reset conversation                    |
| `close`         | `async close() -> None`                     | Release resources                     |

Supports `async with` context manager.

### `BaseConfig` (`core/config.py`)

| Field               | Type  | Default      | Description                 |
| ------------------- | ----- | ------------ | --------------------------- |
| `provider_name`     | `str` | `""`         | Provider identifier         |
| `timeout`           | `int` | `120`        | Operation timeout (seconds) |
| `max_history_turns` | `int` | `50`         | Sliding window size         |
| `output_dir`        | `str` | `"./output"` | Output directory            |

### `BrowserConfig(BaseConfig)` (`core/config.py`)

| Field                     | Type    | Default | Description                               |
| ------------------------- | ------- | ------- | ----------------------------------------- |
| `headless`                | `bool`  | `True`  | Run browser headless                      |
| `base_url`                | `str`   | `""`    | Provider URL                              |
| `storage_state`           | `str`   | `""`    | Path to Playwright storage state JSON     |
| `response_check_interval` | `float` | `1.0`   | Polling interval for response detection   |
| `required_stable_checks`  | `int`   | `3`     | Consecutive identical reads before stable |

### `APIConfig(BaseConfig)` (`core/config.py`)

| Field           | Type    | Default | Description          |
| --------------- | ------- | ------- | -------------------- |
| `api_key`       | `str`   | `""`    | API key              |
| `model`         | `str`   | `""`    | Model identifier     |
| `base_url`      | `str`   | `""`    | API base URL         |
| `temperature`   | `float` | `0.7`   | Sampling temperature |
| `max_tokens`    | `int`   | `4096`  | Max response tokens  |
| `stream`        | `bool`  | `False` | Enable streaming     |
| `system_prompt` | `str`   | `""`    | System prompt        |

### `CLIConfig(BaseConfig)` (`core/config.py`)

| Field         | Type  | Default | Description       |
| ------------- | ----- | ------- | ----------------- |
| `command`     | `str` | `""`    | CLI executable    |
| `working_dir` | `str` | `"."`   | Working directory |

### Data Types (`core/types.py`)

- **`Message`** — `role`, `content`, `timestamp`, `metadata`
- **`ConversationTurn`** — `turn_number`, `user_message`, `assistant_message`, `thinking`, `processing_time_ms`, `success`, `error`
- **`TurnResult`** — Testbed-compatible result with `to_dict()`
- **`AgentStats`** — `session_id`, `provider`, `total_turns`, `successful_turns`, `failed_turns`, `total_processing_time_ms`, `avg_processing_time_ms`

### Exceptions (`core/exceptions.py`)

```
AgentError
├── BrowserError
│   ├── NavigationError
│   ├── ElementNotFoundError
│   ├── ResponseTimeoutError
│   ├── AuthenticationError
│   └── CloudflareChallengeError
├── APIError
│   └── RateLimitError
└── CLIError
```

### History (`core/history.py`)

`ConversationHistory(max_turns)` — Sliding window with `add_turn()`, `clear()`, `.messages`, `.turns`, `.turn_count`.

### Retry (`core/retry.py`)

`@retry(max_attempts=3, base_delay=1.0, backoff_factor=2.0, exceptions=(Exception,))` — Async decorator with exponential backoff.

### Output (`core/output.py`)

- `save_turn(turn, output_dir)` — Saves JSON/TXT/MD files
- `save_summary(turns, output_dir)` — Summary JSON
- `save_full_results(turns, config, output_dir)` — Complete results

---

## Browser Layer

### `BaseBrowserAgent` (`browser/base_browser_agent.py`)

Extends `BaseChatAgent` with shared browser chat loop.

Hooks (override in subclasses):
- `_post_navigate(page)` — After initial navigation
- `_pre_chat_hook(page)` — Before each chat turn
- `_extract_thinking(page) -> str | None` — Extract model thinking

### `BrowserManager` (`browser/browser_manager.py`)

Manages Playwright lifecycle: `ensure_page()`, `navigate(url)`, `inject_js(filename)`, `close()`.

### `ResponseDetector` (`browser/response_detector.py`)

`wait_for_new_response() -> str` — 2-phase detection: count increase → content stabilization.

### `ProviderSelectors` (`browser/selectors.py`)

Frozen dataclass: `input_selectors`, `submit_selectors`, `response_selectors`, plus optional `loading_selectors`, `new_chat_selectors`.

---

## API Layer

### `BaseAPIAgent` (`api/base_api_agent.py`)

Extends `BaseChatAgent` for HTTP APIs. Subclasses implement:
- `_build_request_body(messages) -> dict`
- `_parse_response(data) -> str`
- `_parse_stream_chunk(chunk) -> str`

Built-in: `chat()`, `chat_stream()`, retry with @retry, rate limit handling.

---

## CLI Layer

### `BaseCLIAgent` (`cli/base_cli_agent.py`)

Extends `BaseChatAgent` for CLI tools. Subclasses implement:
- `_build_command(message) -> list[str]`
- `_parse_output(stdout) -> str`

Built-in: async subprocess execution.

---

## Providers

### Claude
- **`ClaudeChatAgent`** — Browser chat with 3-strategy thinking extraction
- **`ClaudeDataAgent`** — Structured data generation (JSON prompts/extraction)
- **`ClaudeTranslatorAgent`** — Multi-turn translation with conversation splitting

### Gemini
- **`GeminiChatAgent`** — Browser chat with API interception thinking

### GPT
- **`GPTChatAgent`** — Browser chat (minimal)

### Perplexity
- **`PerplexityChatAgent`** — Browser chat with citation extraction (`Citation` dataclass)

### OpenRouter
- **`OpenRouterChatAgent`** — HTTP API with model fallback
- **`OpenRouterDataAgent`** — Data generation with thinking budget support

### Copilot
- **`CopilotChatAgent`** — CLI agent (`gh copilot suggest -I`)

---

## Monitor

### `EventBus` (`monitor/events.py`)

`subscribe(event_type, handler)` / `publish(event)` / `unsubscribe(event_type, handler)`

### `EventType` enum

`AGENT_REGISTERED`, `AGENT_STARTED`, `TURN_STARTED`, `TURN_COMPLETED`, `TURN_FAILED`, `AGENT_ERROR`, `AGENT_CLOSED`

### `AgentEvent` dataclass

`event_type`, `agent_id`, `provider`, `timestamp`, `data` dict

### `AgentRegistry` (`monitor/agent_registry.py`)

`register(agent) -> str` / `get(agent_id)` / `list_agents()` / `close_all()`

### `MonitoredAgent` (`monitor/monitored_agent.py`)

Wraps any agent, emits `TURN_STARTED`/`TURN_COMPLETED`/`TURN_FAILED` events on `chat()`.

### `Dashboard` (`monitor/dashboard.py`)

Live terminal table via `rich`. `run(stop_event)` for live mode, `print_snapshot()` for one-shot.

### `Reporter` (`monitor/reporter.py`)

`summary()` / `save_report(path)` / `print_report()` — Post-run aggregation of turns, latency, errors.
