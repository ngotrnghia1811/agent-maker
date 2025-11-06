# Agent Compiler — Development Plan

> A pipeline for creating new agent instances based on user preferences and requirements, by composing existing agent components and configurations in a modular fashion.

- [Agent Compiler — Development Plan](#agent-compiler--development-plan)
  - [1. Overview](#1-overview)
  - [2. Current Architecture Inventory](#2-current-architecture-inventory)
    - [2.1 Available Building Blocks](#21-available-building-blocks)
    - [2.2 Capability Matrix](#22-capability-matrix)
    - [2.3 Parts That Can Be Modularized \& Reused](#23-parts-that-can-be-modularized--reused)
  - [3. Compiler-LLM (The Intelligent Intermediary)](#3-compiler-llm-the-intelligent-intermediary)
    - [3.1 Role](#31-role)
    - [3.2 Default Configuration](#32-default-configuration)
    - [3.3 Compiler-LLM Invocation Points](#33-compiler-llm-invocation-points)
    - [3.4 Changing the Compiler-LLM](#34-changing-the-compiler-llm)
  - [4. Agent Compiler Architecture](#4-agent-compiler-architecture)
    - [4.1 Module Structure](#41-module-structure)
    - [4.2 Core Classes](#42-core-classes)
  - [5. Question Flow Design](#5-question-flow-design)
    - [Phase 0: Compiler-LLM Setup (1 question)](#phase-0-compiler-llm-setup-1-question)
    - [Phase 1: Use Case (1-2 questions)](#phase-1-use-case-1-2-questions)
    - [Phase 2: Quality \& Intelligence (2-3 questions)](#phase-2-quality--intelligence-2-3-questions)
    - [Phase 3: Provider \& Cost (2-4 questions)](#phase-3-provider--cost-2-4-questions)
    - [Phase 4: Resilience \& Monitoring (2 questions)](#phase-4-resilience--monitoring-2-questions)
    - [Phase 5: Customization (1-2 questions)](#phase-5-customization-1-2-questions)
    - [Question Flow Diagram](#question-flow-diagram)
  - [6. Capability Resolution Logic](#6-capability-resolution-logic)
    - [6.1 Provider Selection Algorithm](#61-provider-selection-algorithm)
    - [6.2 Agent Class Selection](#62-agent-class-selection)
    - [6.3 Config Generation](#63-config-generation)
  - [7. Agent Assembly](#7-agent-assembly)
    - [Output Formats](#output-formats)
  - [8. Presets (Quick-Start Configurations)](#8-presets-quick-start-configurations)
  - [9. Codebase Adaptations Required](#9-codebase-adaptations-required)
    - [9.1 Refactoring (Before Compiler Implementation)](#91-refactoring-before-compiler-implementation)
    - [9.2 New Modules](#92-new-modules)
    - [9.3 CLI \& Integration](#93-cli--integration)
  - [10. Implementation Order](#10-implementation-order)
    - [Phase 1: Foundation (refactoring)](#phase-1-foundation-refactoring)
    - [Phase 2: Core Compiler](#phase-2-core-compiler)
    - [Phase 3: Question Flow](#phase-3-question-flow)
    - [Phase 4: Integration \& Polish](#phase-4-integration--polish)
  - [11. Test Strategy](#11-test-strategy)
  - [12. Future Extensions](#12-future-extensions)
  - [13. Detailed Examples — Claude (10 Test Cases)](#13-detailed-examples--claude-10-test-cases)
    - [Example 1: Chat Single Turn (`chat_single`)](#example-1-chat-single-turn-chat_single)
    - [Example 2: Chat Multi-Turn (`chat_multi`)](#example-2-chat-multi-turn-chat_multi)
    - [Example 3: Chat with Thinking (`chat_thinking`)](#example-3-chat-with-thinking-chat_thinking)
    - [Example 4: Data JSON Extraction (`data_json`)](#example-4-data-json-extraction-data_json)
    - [Example 5: Data BREAK Prompt (`data_break`)](#example-5-data-break-prompt-data_break)
    - [Example 6: Translator Single Chunk (`translator_single`)](#example-6-translator-single-chunk-translator_single)
    - [Example 7: Translator Multi-Chunk (`translator_multi`)](#example-7-translator-multi-chunk-translator_multi)
    - [Example 8: Translator PDF Upload (`translator_pdf`)](#example-8-translator-pdf-upload-translator_pdf)
    - [Example 9: Translator Multi-Page PDF (`translator_multi_pdf`)](#example-9-translator-multi-page-pdf-translator_multi_pdf)
    - [Example 10: Model Change (`model_change`)](#example-10-model-change-model_change)
  - [14. Detailed Examples — OpenRouter (10 Test Cases)](#14-detailed-examples--openrouter-10-test-cases)
    - [Example 1: Chat Single Turn (`chat_single`)](#example-1-chat-single-turn-chat_single-1)
    - [Example 2: Chat Multi-Turn (`chat_multi`)](#example-2-chat-multi-turn-chat_multi-1)
    - [Example 3: Chat with Thinking (`chat_thinking`)](#example-3-chat-with-thinking-chat_thinking-1)
    - [Example 4: Data JSON Extraction (`data_json`)](#example-4-data-json-extraction-data_json-1)
    - [Example 5: Data BREAK Prompt (`data_break`)](#example-5-data-break-prompt-data_break-1)
    - [Example 6: Model Change (`model_change`)](#example-6-model-change-model_change)
    - [Example 7: Streaming Chat (additional scenario)](#example-7-streaming-chat-additional-scenario)
    - [Example 8: Fallback Chain with Monitoring (additional scenario)](#example-8-fallback-chain-with-monitoring-additional-scenario)
    - [Example 9: Custom System Prompt via Compiler-LLM (additional scenario)](#example-9-custom-system-prompt-via-compiler-llm-additional-scenario)
    - [Example 10: Paid Model with Reasoning (additional scenario)](#example-10-paid-model-with-reasoning-additional-scenario)


---

## 1. Overview

The **Agent Compiler** is an interactive system that:

1. **Interviews** the user through a structured question flow to determine desired agent behavior, capabilities, and configuration
2. **Selects and composes** the appropriate existing agent components (transport, provider, capabilities, wrappers) based on user responses
3. **Outputs** a fully assembled, ready-to-use agent instance (Python code + config) that meets the user's specifications

The compiler operates at the **configuration and composition** level — it does not generate new agent classes at runtime but rather selects, configures, and wires together existing building blocks from the universal-agents framework.

---

## 2. Current Architecture Inventory

### 2.1 Available Building Blocks

| Layer            | Components                                                                                          | Selection Criteria                                         |
| ---------------- | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| **Transport**    | `BrowserManager` (Camoufox/Playwright), `httpx.AsyncClient`, `asyncio.subprocess`                   | Free vs. paid, needs browser auth vs. API key vs. CLI tool |
| **Base Agent**   | `BaseBrowserAgent`, `BaseAPIAgent`, `BaseCLIAgent`                                                  | Determined by transport                                    |
| **Provider**     | Claude, Gemini, GPT, Perplexity (browser); OpenAI, OpenRouter (API); Copilot (CLI)                  | User preference, cost, model quality, available auth       |
| **Config**       | 10 dataclass configs with provider-specific fields                                                  | Auto-generated from provider + capability choices          |
| **Capabilities** | Chat, Data/JSON, Translation, Thinking/Reasoning, Citations, File Upload, Streaming, Model Fallback | User requirements                                          |
| **Wrappers**     | `MonitoredAgent`, Translator wrappers                                                               | Optional monitoring/translation needs                      |

### 2.2 Capability Matrix

```
                  Chat  Data/JSON  Translator  Thinking  Citations  FileUpload  Streaming  Fallback
Claude (browser)   ✓      ✓          ✓           ✓                    ✓
Gemini (browser)   ✓      ✓          ✓           ✓                    ✓
GPT (browser)      ✓
Perplexity         ✓                                        ✓
OpenAI (API)       ✓      ✓                      ✓                                ✓
OpenRouter (API)   ✓      ✓                      ✓                                ✓         ✓
Copilot (CLI)      ✓
```

### 2.3 Parts That Can Be Modularized & Reused

**Already modular (ready for compiler):**
- All config dataclasses — composable via dataclass inheritance and field overrides
- `MonitoredAgent` wrapper — can wrap any `BaseChatAgent`
- `@retry` decorator — applicable to any async function
- `ConversationHistory` — shared across all agents
- `output.py` — `save_turn()`, `save_summary()`, `save_full_results()` for any agent
- `Reporter` + `Dashboard` — work with any `MonitoredAgent`

**Needs extraction/refactoring for compiler:**

| Component                 | Current Location                                                                                                                                                       | Refactoring Needed                                                                                                            |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| JSON extraction logic     | Duplicated in `ClaudeDataAgent.extract_json()`, `GeminiDataAgent.extract_json()`, `OpenAIDataAgent.parse_json_response()`, `OpenRouterDataAgent.parse_json_response()` | Extract to shared `utils/json_parser.py` mixin                                                                                |
| `build_data_prompt()`     | Duplicated in all 4 data agents                                                                                                                                        | Extract to shared `utils/prompt_builder.py`                                                                                   |
| File upload strategies    | Different in Claude (3 strategies) vs Gemini (Angular Material)                                                                                                        | Create abstract `FileUploader` protocol; keep provider impls                                                                  |
| Translation orchestration | Duplicated in `ClaudeTranslatorAgent` and `GeminiTranslatorAgent`                                                                                                      | Extract shared `TranslationOrchestrator` with provider-agnostic multi-turn logic; delegates to agent for actual chat + upload |
| Thinking extraction       | 4 different strategies across 4 providers                                                                                                                              | Already appropriately provider-specific, no need to unify                                                                     |

---

## 3. Compiler-LLM (The Intelligent Intermediary)

The Agent Compiler uses a **Compiler-LLM** — a lightweight LLM that acts as the intelligent intermediary between the user and the compiler pipeline. Instead of rigid pattern-matching on user answers, the Compiler-LLM interprets natural language, resolves ambiguity, and maps human intent to concrete component selections.

### 3.1 Role

| Responsibility              | Description                                                                                                                                                   |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Interpret answers**       | When the user selects "Custom" and types a free-form description, the Compiler-LLM maps it to the closest `UserRequirements` fields                           |
| **Resolve ambiguity**       | If a user says "I want something fast and cheap," the LLM decides the right trade-off between `cost_sensitivity` and `latency_sensitivity`                    |
| **Validate combinations**   | The LLM checks whether the selected options are compatible (e.g., "free + Claude browser + file upload" is valid, but "free + OpenAI API + citations" is not) |
| **Generate system prompts** | When the user describes their use case in natural language, the LLM drafts an appropriate system prompt                                                       |
| **Explain choices**         | After compilation, the LLM produces a human-readable summary of why each component was chosen                                                                 |

### 3.2 Default Configuration

```python
COMPILER_LLM_DEFAULTS = {
    "provider": "openrouter",
    "model": os.getenv("DEFAULT_OPENROUTER_MODEL", "stepfun/step-3.5-flash:free"),
    "max_tokens": 1024,
    "temperature": 0.0,
    "system_prompt": (
        "You are a component selector for the universal-agents framework. "
        "Given a user's natural language answer, map it to the corresponding "
        "structured field values. Respond with JSON only."
    ),
}
```

- **Default**: Uses the OpenRouter default LLM (`DEFAULT_OPENROUTER_MODEL` from `.env`, currently `stepfun/step-3.5-flash:free`) — free, fast, good enough for intent classification
- **User-changeable**: The very first question in the compiler flow asks whether to keep or change the Compiler-LLM (see Question 0.1 in §4)
- **Fallback**: If OpenRouter is unavailable, falls back to any available API provider (OpenAI, then Copilot CLI)

### 3.3 Compiler-LLM Invocation Points

```
User selects option ──► Is it "Custom"? ──► YES ──► Compiler-LLM interprets free-text ──► Structured value
                                           │
                                           NO ──► Direct mapping (no LLM call needed)
```

The Compiler-LLM is only invoked when:
1. The user selects "Custom" and provides free-form text
2. The compiler needs to generate a system prompt
3. The compiler produces the final human-readable summary
4. Ambiguity resolution is needed between conflicting option selections

For standard option selections (1-N), no LLM call is made — the mapping is deterministic.

### 3.4 Changing the Compiler-LLM

```
Question 0.1: Compiler-LLM is currently set to: stepfun/step-3.5-flash:free (OpenRouter)
  1. Keep current (recommended — free & fast)
  2. Use OpenAI (gpt-5.4-mini — faster, requires OPENAI_API_KEY)
  3. Use a different OpenRouter model
  4. Custom (specify provider and model)
```

This is asked once at the very start, before the main interview begins. The selected Compiler-LLM is used for all subsequent interpretation during the session.

---

## 4. Agent Compiler Architecture

### 4.1 Module Structure

> **Note:** The `compiler/` module now includes a `compiler_llm.py` for the Compiler-LLM client (see §3).

```
src/universal_agents/compiler/
├── __init__.py
├── compiler.py          # Main AgentCompiler class
├── question_flow.py     # Interview question definitions and flow logic
├── capability_resolver.py  # Maps user answers → component selections
├── config_builder.py    # Generates provider-specific config dataclasses
├── agent_assembler.py   # Wires components together → agent instance
├── templates/           # Code templates for generated agent scripts
│   ├── api_agent.py.j2
│   ├── browser_agent.py.j2
│   └── cli_agent.py.j2
└── presets.py           # Pre-built common configurations
```

### 4.2 Core Classes

```python
@dataclass
class UserRequirements:
    """Collected user responses from the interview."""
    use_case: str                     # "chat", "data_extraction", "translation", "research"
    provider_preference: str | None   # "claude", "gemini", "openai", "openrouter", etc.
    needs_thinking: bool
    needs_json_output: bool
    needs_file_upload: bool
    needs_translation: bool
    needs_citations: bool
    needs_streaming: bool
    needs_monitoring: bool
    needs_fallback: bool
    cost_sensitivity: str             # "free", "low", "medium", "unlimited"
    latency_sensitivity: str          # "low", "medium", "high"
    auth_available: dict[str, bool]   # {"claude_storage": True, "openai_key": True, ...}
    model_preference: str | None
    custom_system_prompt: str | None
    output_format: str                # "instance", "script", "config_only"

@dataclass
class CompiledAgent:
    """Output of the agent compiler."""
    agent_class: type                 # The selected agent class
    config: BaseConfig                # Fully populated config
    wrappers: list[type]              # MonitoredAgent, etc.
    code: str                         # Generated Python script
    description: str                  # Human-readable summary
    capabilities: list[str]           # ["chat", "data", "thinking", ...]
```

```python
class AgentCompiler:
    """Main orchestrator for the agent compilation pipeline."""

    def __init__(self):
        self.question_flow = QuestionFlow()
        self.resolver = CapabilityResolver()
        self.config_builder = ConfigBuilder()
        self.assembler = AgentAssembler()

    async def compile_interactive(self) -> CompiledAgent:
        """Run the full interactive pipeline."""
        requirements = await self.question_flow.interview()
        components = self.resolver.resolve(requirements)
        config = self.config_builder.build(components)
        return self.assembler.assemble(components, config)

    def compile_from_spec(self, spec: dict) -> CompiledAgent:
        """Non-interactive compilation from a JSON spec."""
        requirements = UserRequirements(**spec)
        components = self.resolver.resolve(requirements)
        config = self.config_builder.build(components)
        return self.assembler.assemble(components, config)
```

---

## 5. Question Flow Design

The interview proceeds in 6 phases (0–5), each building on previous answers. Questions are skipped when they become irrelevant based on prior answers.

**Every question presents numbered options.** The last option is always **"Custom"** — when selected, the user types a free-form description and the **Compiler-LLM** (§3) interprets it into the corresponding structured value. For standard option selections, no LLM call is needed.

### Phase 0: Compiler-LLM Setup (1 question)

```
0.1  Compiler-LLM is set to: stepfun/step-3.5-flash:free (OpenRouter)

     1. Keep current (recommended — free & fast)
     2. Use OpenAI (gpt-5.4-mini)
     3. Use a different OpenRouter model
     4. Custom (specify provider and model)
```

| Maps To | `compiler_llm_provider`, `compiler_llm_model` |
| ------- | --------------------------------------------- |

### Phase 1: Use Case (1-2 questions)

```
1.1  What will you use this agent for?

     1. General chat / conversation
     2. Structured data extraction (JSON output)
     3. Document translation
     4. Research with citations
     5. Code assistance / review
     6. Custom (describe your use case)
```

| Maps To | `use_case` |
| ------- | ---------- |

**Auto-set logic** (applied immediately after 1.1):
- Option 2 (`data`) → `needs_json_output=True`
- Option 3 (`translation`) → `needs_file_upload=True`, `needs_json_output=True`
- Option 4 (`research`) → `needs_citations=True`
- Option 5 (`code`) → `needs_thinking=True`

```
1.2  Does the agent need to process files (PDF, images)?
     [SKIPPED if use_case = "chat" or "translation" (auto-set)]

     1. Yes — PDF and/or image upload required
     2. No — text-only input
     3. Custom (describe file needs)
```

| Maps To | `needs_file_upload` |
| ------- | ------------------- |

### Phase 2: Quality & Intelligence (2-3 questions)

```
2.1  Should the agent show its reasoning/thinking process?

     1. Yes — I want to see chain-of-thought
     2. No — just the final answer
     3. Don't care — let the compiler decide
     4. Custom (describe reasoning needs)
```

| Maps To | `needs_thinking` |
| ------- | ---------------- |

```
2.2  Response speed vs. quality preference?

     1. Speed — fast responses, lower cost
     2. Balanced — good quality at reasonable speed
     3. Quality — best output, cost/speed secondary
     4. Custom (describe your priority)
```

| Maps To | `latency_sensitivity`, influences model selection |
| ------- | ------------------------------------------------- |

```
2.3  Do you need real-time streaming responses?
     [SKIPPED if browser provider already selected]

     1. Yes — stream tokens as they arrive
     2. No — wait for complete response
     3. Custom (describe streaming needs)
```

| Maps To | `needs_streaming` |
| ------- | ----------------- |

### Phase 3: Provider & Cost (2-4 questions)

```
3.1  Budget preference?

     1. Free — free-tier models only ($0)
     2. Low — minimize cost (< $0.01/request)
     3. Medium — reasonable cost for good quality
     4. Unlimited — best available, cost doesn't matter
     5. Custom (describe budget constraints)
```

| Maps To | `cost_sensitivity` |
| ------- | ------------------ |

```
3.2  Preferred provider?

     1. Claude (browser — free with login)
     2. Gemini (browser — free with login)
     3. OpenAI (API — requires OPENAI_API_KEY)
     4. OpenRouter (API — many models, free tier available)
     5. GPT (browser — free with login)
     6. Perplexity (browser — citations, free with login)
     7. Copilot (CLI — free with GitHub auth)
     8. No preference — let the compiler decide
     9. Custom (describe provider requirements)
```

| Maps To | `provider_preference` |
| ------- | --------------------- |

**Auto-resolution logic** applied after 3.1 + 3.2:
- `free` + no preference → OpenRouter with `:free` models
- `free` + `needs_citations` → Perplexity (browser, free with auth)
- `unlimited` + `needs_thinking` → Claude (best thinking) or OpenAI (fastest reasoning)
- No API key detected → browser-based providers only

```
3.3  Authentication detected:
     [Auto-detected from .env keys + storage/ browser state files]
     Showing what was found — confirm or override.

     ✓ OPENROUTER_API_KEY .... found
     ✓ OPENAI_API_KEY ....... found
     ✗ Claude browser state . not found
     ✗ Gemini browser state . not found

     1. Looks correct — proceed
     2. I have additional auth not detected
     3. Custom (describe auth situation)
```

| Maps To | `auth_available` |
| ------- | ---------------- |

```
3.4  Preferred model?
     [SKIPPED if already determined by earlier choices]
     [Shows available models for selected provider]

     Example for OpenRouter:
     1. stepfun/step-3.5-flash:free (default — fast, free)
     2. anthropic/claude-sonnet-4 (smart, paid)
     3. openai/gpt-4.1 (fast, paid)
     4. deepseek/deepseek-chat-v3.1:free (free, good quality)
     5. No preference — use provider default
     6. Custom (specify model name)
```

| Maps To | `model_preference` |
| ------- | ------------------ |

### Phase 4: Resilience & Monitoring (2 questions)

```
4.1  Auto-retry with backup models on failure?
     [SKIPPED if browser provider — no API fallback]

     1. Yes — automatically try fallback models
     2. No — fail immediately on error
     3. Custom (describe retry strategy)
```

| Maps To | `needs_fallback` |
| ------- | ---------------- |

```
4.2  Enable monitoring dashboard?

     1. Yes — wrap agent with MonitoredAgent + Reporter
     2. No — lightweight, no monitoring overhead
     3. Custom (describe monitoring needs)
```

| Maps To | `needs_monitoring` |
| ------- | ------------------ |

### Phase 5: Customization (1-2 questions)

```
5.1  System prompt?

     1. Default — use provider's built-in system prompt
     2. Minimal — "You are a helpful assistant."
     3. Data-focused — "Extract structured data. Respond only with valid JSON."
     4. Code-focused — "You are an expert programmer. Think step-by-step."
     5. Custom (write your own system prompt)
        → If selected, Compiler-LLM may refine the user's draft
```

| Maps To | `custom_system_prompt` |
| ------- | ---------------------- |

```
5.2  Output format?

     1. Instance — ready-to-use Python object (await agent.chat(...))
     2. Script — standalone .py file you can run directly
     3. Config-only — JSON config dict for external tooling
     4. Custom (describe output needs)
```

| Maps To | `output_format` |
| ------- | --------------- |

### Question Flow Diagram

```
[0.1 Compiler-LLM Setup]
           │
[1.1 Use Case] ──┐
                  ├── auto-set capabilities ──► [2.1 Thinking]
[1.2 File Upload]─┘                              │
                                                  ▼
                                            [2.2 Speed vs Quality]
                                                  │
                                    ┌─────────────┤
                                    │ if API      │ if browser
                                    ▼             ▼
                            [2.3 Streaming]  (skip)
                                    │             │
                                    └──────┬──────┘
                                           ▼
                                    [3.1 Budget]
                                           │
                                    [3.2 Provider] ◄── auto-resolve if constrained
                                           │
                                    [3.3 Auth Check] ◄── auto-detect .env + storage
                                           │
                                    [3.4 Model] ◄── show available for provider
                                           │
                              ┌────────────┤
                              │ if API     │
                              ▼            ▼
                       [4.1 Fallback]  (skip)
                              │            │
                              └─────┬──────┘
                                    ▼
                             [4.2 Monitoring]
                                    │
                             [5.1 System Prompt]
                                    │
                             [5.2 Output Format]
                                    │
                                    ▼
                              [COMPILE & OUTPUT]

     ┌────────────────────────────────────────────────┐
     │  At any question: selecting "Custom" triggers   │
     │  Compiler-LLM (§3) to interpret free-form text │
     └────────────────────────────────────────────────┘
```

---

## 6. Capability Resolution Logic

The `CapabilityResolver` maps `UserRequirements` → concrete component selections.

### 6.1 Provider Selection Algorithm

```python
def resolve_provider(req: UserRequirements) -> str:
    # 1. Explicit preference wins (if auth available)
    if req.provider_preference and req.auth_available.get(req.provider_preference):
        return req.provider_preference

    # 2. Capability-driven selection
    if req.needs_citations:
        return "perplexity"  # only provider with citations

    if req.needs_translation and req.needs_file_upload:
        if req.auth_available.get("claude_storage"):
            return "claude"  # best translator
        if req.auth_available.get("gemini_storage"):
            return "gemini"

    # 3. Cost-driven selection
    if req.cost_sensitivity == "free":
        if req.auth_available.get("openrouter_key"):
            return "openrouter"  # free-tier models
        # Fall back to browser providers (free with session auth)
        for p in ["gemini", "claude", "gpt"]:
            if req.auth_available.get(f"{p}_storage"):
                return p

    # 4. Quality-driven selection
    if req.latency_sensitivity == "high":
        if req.auth_available.get("openai_key"):
            return "openai"  # fastest API
        return "openrouter"

    if req.needs_thinking:
        if req.auth_available.get("openai_key"):
            return "openai"  # reasoning_effort support
        if req.auth_available.get("claude_storage"):
            return "claude"  # 3-strategy thinking

    # 5. Default fallback
    for p in ["openai", "openrouter", "claude", "gemini", "gpt", "copilot"]:
        if req.auth_available.get(f"{p}_key") or req.auth_available.get(f"{p}_storage"):
            return p

    raise CompilerError("No provider available with current authentication")
```

### 6.2 Agent Class Selection

| Provider   | Use Case    | Agent Class             |
| ---------- | ----------- | ----------------------- |
| claude     | chat        | `ClaudeChatAgent`       |
| claude     | data        | `ClaudeDataAgent`       |
| claude     | translation | `ClaudeTranslatorAgent` |
| gemini     | chat        | `GeminiChatAgent`       |
| gemini     | data        | `GeminiDataAgent`       |
| gemini     | translation | `GeminiTranslatorAgent` |
| gpt        | chat        | `GPTChatAgent`          |
| perplexity | research    | `PerplexityChatAgent`   |
| openai     | chat        | `OpenAIChatAgent`       |
| openai     | data/code   | `OpenAIDataAgent`       |
| openrouter | chat        | `OpenRouterChatAgent`   |
| openrouter | data/code   | `OpenRouterDataAgent`   |
| copilot    | chat/code   | `CopilotChatAgent`      |

### 6.3 Config Generation

The `ConfigBuilder` creates the appropriate config dataclass with:

```python
def build(self, provider: str, use_case: str, req: UserRequirements) -> BaseConfig:
    config_cls = CONFIG_MAP[(provider, use_case)]  # e.g., OpenAIDataConfig
    
    overrides = {}
    if req.custom_system_prompt:
        overrides["system_prompt"] = req.custom_system_prompt
    if req.model_preference:
        overrides["model"] = req.model_preference
    if req.needs_thinking:
        # Provider-specific thinking config
        if provider == "openai":
            overrides["reasoning_effort"] = "medium"
        elif provider == "openrouter":
            overrides["enable_thinking"] = True
            overrides["thinking_budget"] = 10000
        elif provider in ("claude", "gemini"):
            overrides["extract_thinking"] = True
    if req.needs_fallback and provider == "openrouter":
        overrides["fallback_models"] = self._get_fallback_models(req)
    if req.needs_streaming and provider in ("openai", "openrouter"):
        overrides["stream"] = True
    
    return config_cls(**overrides)
```

---

## 7. Agent Assembly

The `AgentAssembler` wires components:

```python
def assemble(self, agent_cls, config, req: UserRequirements) -> CompiledAgent:
    # 1. Create base agent
    agent = agent_cls(config)
    
    # 2. Apply wrappers
    wrappers = []
    if req.needs_monitoring:
        event_bus = EventBus()
        agent = MonitoredAgent(agent, event_bus)
        wrappers.append(MonitoredAgent)
    
    # 3. Generate code (for "script" output format)
    code = self._generate_script(agent_cls, config, wrappers)
    
    return CompiledAgent(
        agent_class=agent_cls,
        config=config,
        wrappers=wrappers,
        code=code,
        description=self._describe(agent_cls, config, req),
        capabilities=self._list_capabilities(agent_cls, req),
    )
```

### Output Formats

**Instance mode** — returns a ready-to-use Python object:
```python
agent = compiled.agent  # Use directly: await agent.chat("Hello")
```

**Script mode** — generates a standalone `.py` file:
```python
#!/usr/bin/env python3
"""Auto-generated agent: OpenAI Data Agent with reasoning."""
from universal_agents.providers.openai.data import OpenAIDataAgent
from universal_agents.providers.openai.config import OpenAIDataConfig

config = OpenAIDataConfig(
    model="gpt-5.4-mini-2026-03-17",
    max_tokens=4096,
    reasoning_effort="medium",
    system_prompt="You are a helpful data extraction assistant.",
)

async def main():
    async with OpenAIDataAgent(config) as agent:
        response = await agent.chat("Your prompt here")
        print(response)
```

**Config-only mode** — returns a JSON-serializable config dict for external use.

---

## 8. Presets (Quick-Start Configurations)

For common use cases, skip the full interview:

```python
PRESETS = {
    "quick-chat": {
        "use_case": "chat",
        "cost_sensitivity": "free",
        "provider_preference": "openrouter",
    },
    "smart-chat": {
        "use_case": "chat",
        "needs_thinking": True,
        "cost_sensitivity": "medium",
        "provider_preference": "openai",
    },
    "data-extractor": {
        "use_case": "data",
        "needs_json_output": True,
        "cost_sensitivity": "low",
    },
    "translator-ja-en": {
        "use_case": "translation",
        "needs_file_upload": True,
        "provider_preference": "claude",
    },
    "researcher": {
        "use_case": "research",
        "needs_citations": True,
        "provider_preference": "perplexity",
    },
    "code-reviewer": {
        "use_case": "code",
        "needs_thinking": True,
        "cost_sensitivity": "medium",
        "provider_preference": "openai",
    },
}
```

---

## 9. Codebase Adaptations Required

### 9.1 Refactoring (Before Compiler Implementation)

| Task                             | Effort | Description                                                                                                            |
| -------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------- |
| Extract `JsonParser` utility     | Small  | Move `extract_json()` / `parse_json_response()` to `utils/json_parser.py`. All 4 data agents import from there.        |
| Extract `PromptBuilder` utility  | Small  | Move `build_data_prompt()` to `utils/prompt_builder.py`. All 4 data agents import from there.                          |
| Create `AuthDetector`            | Medium | Scans `.env` for API keys and `storage/` for browser state files. Returns `dict[str, bool]` of available auth methods. |
| Standardize config serialization | Small  | Add `to_dict()` and `from_dict()` to all config dataclasses (for config-only output mode).                             |

### 9.2 New Modules

| Module                            | Effort | Description                                                             |
| --------------------------------- | ------ | ----------------------------------------------------------------------- |
| `compiler/question_flow.py`       | Medium | 12-15 interview questions with skip/branch logic, input validation      |
| `compiler/capability_resolver.py` | Medium | Provider selection algorithm, agent class mapping, compatibility checks |
| `compiler/config_builder.py`      | Small  | Config dataclass instantiation with computed overrides                  |
| `compiler/agent_assembler.py`     | Small  | Wiring agent + wrappers + code generation                               |
| `compiler/presets.py`             | Small  | 6-8 preset configurations                                               |
| `compiler/templates/`             | Small  | Jinja2 templates for script generation                                  |
| `compiler/compiler.py`            | Small  | Top-level orchestrator tying phases together                            |

### 9.3 CLI & Integration

```bash
# Interactive mode
python -m universal_agents.compiler

# Preset mode
python -m universal_agents.compiler --preset quick-chat

# Spec mode (JSON file)
python -m universal_agents.compiler --spec agent_spec.json

# Output to file
python -m universal_agents.compiler --output my_agent.py
```

---

## 10. Implementation Order

### Phase 1: Foundation (refactoring)
1. Extract `JsonParser` utility from 4 data agents
2. Extract `PromptBuilder` utility from 4 data agents
3. Add `to_dict()` / `from_dict()` to all config dataclasses
4. Create `AuthDetector` (scan .env + storage/)
5. Unit tests for all extracted utilities

### Phase 2: Core Compiler
6. Implement `UserRequirements` dataclass
7. Implement `CapabilityResolver` (provider selection + agent class mapping)
8. Implement `ConfigBuilder` (config generation)
9. Implement `AgentAssembler` (agent wiring + code generation)
10. Unit tests for resolver, builder, assembler

### Phase 3: Question Flow
11. Implement `QuestionFlow` with 5-phase interview (terminal input)
12. Implement skip/branch logic based on prior answers
13. Integrate `AuthDetector` into Phase 3 questions
14. Implement preset shortcuts

### Phase 4: Integration & Polish
15. Implement `AgentCompiler` orchestrator
16. CLI entry point (`__main__.py`)
17. Script template generation (Jinja2)
18. Integration tests: compile → instantiate → single chat turn → verify
19. Documentation

---

## 11. Test Strategy

| Test Type                  | Scope                                                                        | Count |
| -------------------------- | ---------------------------------------------------------------------------- | ----- |
| Unit: `CapabilityResolver` | Each provider selection path, edge cases (no auth, conflicting requirements) | ~15   |
| Unit: `ConfigBuilder`      | Each (provider, use_case) pair generates valid config                        | ~12   |
| Unit: `QuestionFlow`       | Each branch/skip path, input validation                                      | ~10   |
| Integration: Presets       | Each preset → compile → create instance → single chat → verify response      | 6     |
| Integration: Full flow     | Interactive mock → compile → run agent → verify capabilities                 | 3-5   |
| E2E: Script generation     | Compile to script → execute script → verify output                           | 3     |

---

## 12. Future Extensions

- **Web UI**: Replace terminal interview with a web form (FastAPI + React), render the compiled agent config visually
- **Agent chaining**: Compiler outputs a pipeline of multiple agents (e.g., Perplexity for research → Claude for analysis → OpenAI for formatting)
- **Dynamic capability discovery**: Scan installed providers at startup, auto-update capability matrix
- **Versioned specs**: Save compiled agent specs as YAML files, version control them, re-compile when framework updates
- **A/B testing**: Compile two agent variants, run same prompts through both, compare outputs using the Reporter

---

## 13. Detailed Examples — Claude (10 Test Cases)

These examples show the full compiler flow for each of the 10 Claude integration tests (from `test_v1_claude_jobs_live.py`). Each example traces: **user answers → Compiler-LLM interpretation (if "Custom" selected) → resolved requirements → compiled agent + config → equivalent test code**.

Auth context for all Claude examples: `.env` has no Claude API key; `storage/claude_state.json` browser state is detected.

---

### Example 1: Chat Single Turn (`chat_single`)

**User answers:**
```
0.1  Compiler-LLM? → 1 (Keep current)
1.1  Use case?     → 1 (General chat)
1.2  File upload?  → [SKIPPED — chat use case]
2.1  Thinking?     → 2 (No)
2.2  Speed/quality? → 1 (Speed)
2.3  Streaming?    → [SKIPPED — browser provider]
3.1  Budget?       → 1 (Free)
3.2  Provider?     → 1 (Claude browser)
3.3  Auth?         → 1 (Looks correct — claude_storage detected)
3.4  Model?        → [SKIPPED — browser default]
4.1  Fallback?     → [SKIPPED — browser provider]
4.2  Monitoring?   → 2 (No)
5.1  System prompt? → 1 (Default)
5.2  Output?       → 2 (Script)
```

**No Compiler-LLM calls** — all standard option selections.

**Resolved `UserRequirements`:**
```python
UserRequirements(
    use_case="chat", provider_preference="claude",
    needs_thinking=False, needs_json_output=False,
    needs_file_upload=False, needs_translation=False,
    needs_citations=False, needs_streaming=False,
    needs_monitoring=False, needs_fallback=False,
    cost_sensitivity="free", latency_sensitivity="high",
    auth_available={"claude_storage": True},
    model_preference=None, custom_system_prompt=None,
    output_format="script",
)
```

**Compiled output:**
```python
from universal_agents.providers.claude.chat import ClaudeChatAgent
from universal_agents.providers.claude.config import ClaudeConfig

config = ClaudeConfig()

async def main():
    async with ClaudeChatAgent(config) as agent:
        response = await agent.chat("What is 2+2?")
        print(response)  # "4"
```

**Equivalent test:** `test_chat_single_turn` — sends "What is 2+2?", asserts "4" in response.

---

### Example 2: Chat Multi-Turn (`chat_multi`)

**User answers:**
```
0.1  → 1 (Keep current)
1.1  → 1 (General chat)
2.1  → 2 (No thinking)
2.2  → 2 (Balanced)
3.1  → 1 (Free)
3.2  → 1 (Claude browser)
3.3  → 1 (Confirmed)
4.2  → 2 (No monitoring)
5.1  → 1 (Default)
5.2  → 1 (Instance)
```

**Compiled output:**
```python
config = ClaudeConfig()
agent = ClaudeChatAgent(config)

# Multi-turn: agent retains conversation history automatically
r1 = await agent.chat("Remember the number 42")
r2 = await agent.chat("Double that number")      # expects "84"
r3 = await agent.chat("Add 16 to the result")    # expects "100"
assert len(agent.history.turns) == 3
```

**Equivalent test:** `test_chat_multi_turn` — 3-turn context retention (42→84→100).

---

### Example 3: Chat with Thinking (`chat_thinking`)

**User answers:**
```
0.1  → 1 (Keep current)
1.1  → 1 (General chat)
2.1  → 1 (Yes — show reasoning)              ← key difference
2.2  → 3 (Quality)
3.1  → 1 (Free)
3.2  → 1 (Claude browser)
3.3  → 1 (Confirmed)
4.2  → 2 (No monitoring)
5.1  → 1 (Default)
5.2  → 2 (Script)
```

**Resolved requirements:** `needs_thinking=True` → compiler sets `extract_thinking=True` on ClaudeConfig.

**Compiled output:**
```python
config = ClaudeConfig(extract_thinking=True)

async with ClaudeChatAgent(config) as agent:
    response = await agent.chat("What is the 10th prime number?")
    # response contains answer "29"
    # agent.last_thinking contains chain-of-thought reasoning
    # agent.last_thinking_source is "playwright_intercept" or "dom_scrape"
```

**Equivalent test:** `test_chat_thinking` — verifies thinking content captured, thinking source identified.

---

### Example 4: Data JSON Extraction (`data_json`)

**User answers:**
```
0.1  → 1 (Keep current)
1.1  → 2 (Structured data extraction)        ← auto-sets needs_json_output=True
1.2  → 2 (No file upload)
2.1  → 2 (No thinking)
2.2  → 2 (Balanced)
3.1  → 1 (Free)
3.2  → 1 (Claude browser)
3.3  → 1 (Confirmed)
4.2  → 2 (No monitoring)
5.1  → 3 (Data-focused — "Extract structured data. Respond only with JSON.")
5.2  → 2 (Script)
```

**Agent selection:** `use_case="data"` + `provider="claude"` → `ClaudeDataAgent`.

**Compiled output:**
```python
from universal_agents.providers.claude.data import ClaudeDataAgent
from universal_agents.providers.claude.config import ClaudeDataConfig

config = ClaudeDataConfig(
    system_prompt="Extract structured data. Respond only with valid JSON.",
)

async with ClaudeDataAgent(config) as agent:
    input_data = {"name": "test", "value": 42}
    prompt = agent.build_data_prompt(
        instruction="Process and categorize",
        data=input_data,
    )
    response = await agent.chat(prompt)
    result = agent.extract_json(response)
    # result has "processed", "category_upper" fields
```

**Equivalent test:** `test_data_json_generation` — sends JSON, verifies structured output with expected fields.

---

### Example 5: Data BREAK Prompt (`data_break`)

**User answers:**
```
0.1  → 1 (Keep current)
1.1  → 6 (Custom) → "I need to convert quiz questions into training examples for ML"
     Compiler-LLM interprets → use_case="data", needs_json_output=True
1.2  → 2 (No file upload)
2.1  → 2 (No thinking)
2.2  → 2 (Balanced)
3.1  → 1 (Free)
3.2  → 1 (Claude browser)
3.3  → 1 (Confirmed)
4.2  → 2 (No monitoring)
5.1  → 5 (Custom) → "You transform academic quiz questions into BREAK-dataset training examples"
     Compiler-LLM refines → "You are a dataset generator. Given a quiz question, produce a JSON training example with 'question', 'answer', and 'decomposition' fields."
5.2  → 2 (Script)
```

**Compiler-LLM invoked twice** — once for use case interpretation, once for system prompt refinement.

**Compiled output:**
```python
config = ClaudeDataConfig(
    system_prompt="You are a dataset generator. Given a quiz question, produce a JSON training example with 'question', 'answer', and 'decomposition' fields.",
)

async with ClaudeDataAgent(config) as agent:
    prompt = agent.build_data_prompt(
        instruction="Convert to BREAK-dataset training example",
        data={"question": "What is the boiling point of water?"},
    )
    response = await agent.chat(prompt)
    result = agent.extract_json(response)
    assert "question" in result
```

**Equivalent test:** `test_data_break_prompt` — BREAK-dataset quiz→training-example transformation.

---

### Example 6: Translator Single Chunk (`translator_single`)

**User answers:**
```
0.1  → 1 (Keep current)
1.1  → 3 (Document translation)              ← auto-sets needs_file_upload=True, needs_json_output=True
2.1  → 2 (No thinking)
2.2  → 2 (Balanced)
3.1  → 1 (Free)
3.2  → 1 (Claude browser)
3.3  → 1 (Confirmed)
4.2  → 2 (No monitoring)
5.1  → 1 (Default)
5.2  → 2 (Script)
```

**Agent selection:** `use_case="translation"` + `provider="claude"` → `ClaudeTranslatorAgent`.

**Compiled output:**
```python
from universal_agents.providers.claude.translator import ClaudeTranslatorAgent
from universal_agents.providers.claude.config import ClaudeTranslatorConfig

config = ClaudeTranslatorConfig(
    source_language="Japanese",
    target_language="English",
)

async with ClaudeTranslatorAgent(config) as agent:
    chunk = await agent.translate_text("東京は日本の首都です。")
    # chunk.translated_text contains "Tokyo is the capital of Japan."
    assert "Tokyo" in chunk.translated_text
```

**Equivalent test:** `test_translator_single_chunk` — JA→EN, verifies "Tokyo" in output.

---

### Example 7: Translator Multi-Chunk (`translator_multi`)

**User answers:** Same as Example 6 (translation use case, Claude browser).

**Compiled output:** Same agent, but used with multi-chunk workflow:
```python
config = ClaudeTranslatorConfig(
    source_language="Japanese",
    target_language="English",
)

async with ClaudeTranslatorAgent(config) as agent:
    chunk1 = await agent.translate_text("第一段落の日本語テキスト...")
    chunk2 = await agent.translate_text(
        "第二段落のテキスト...",
        continue_prompt="Continue translating the next section:",
    )
    full = agent.get_full_translation()
    assert len(agent.history.turns) >= 2
```

**Equivalent test:** `test_translator_multi_chunk` — 2 sequential chunks, conversation turn management.

---

### Example 8: Translator PDF Upload (`translator_pdf`)

**User answers:**
```
0.1  → 1 (Keep current)
1.1  → 3 (Document translation)              ← auto-sets needs_file_upload=True
2.1  → 2 (No thinking)
2.2  → 2 (Balanced)
3.1  → 1 (Free)
3.2  → 1 (Claude browser)
3.3  → 1 (Confirmed)
4.2  → 1 (Yes — enable monitoring)           ← with monitoring this time
5.1  → 1 (Default)
5.2  → 2 (Script)
```

**Compiled output** (with monitoring wrapper):
```python
from universal_agents.providers.claude.translator import ClaudeTranslatorAgent
from universal_agents.providers.claude.config import ClaudeTranslatorConfig
from universal_agents.core.monitoring import MonitoredAgent, EventBus

config = ClaudeTranslatorConfig(
    source_language="Japanese",
    target_language="English",
)

async with ClaudeTranslatorAgent(config) as base_agent:
    event_bus = EventBus()
    agent = MonitoredAgent(base_agent, event_bus)
    result = await agent.translate_file("document.pdf")
    # File uploaded via Playwright browser automation
    # Monitoring captures timing, token usage, success/failure
```

**Equivalent test:** `test_translator_pdf` — PDF upload via browser, file handling.

---

### Example 9: Translator Multi-Page PDF (`translator_multi_pdf`)

**User answers:** Same as Example 8 but with a multi-page document.

**Key config difference:** `max_turns_per_conversation` limits context window management.

**Compiled output:**
```python
config = ClaudeTranslatorConfig(
    source_language="Japanese",
    target_language="English",
    max_turns_per_conversation=5,  # Reset context after 5 turns
)

async with ClaudeTranslatorAgent(config) as agent:
    # Process 3 PDF pages sequentially
    for page_pdf in ["page1.pdf", "page2.pdf", "page3.pdf"]:
        result = await agent.translate_file(page_pdf)
    full = agent.get_full_translation()
```

**Equivalent test:** `test_translator_multi_page_pdf` — 3 PDFs, conversation context across uploads.

---

### Example 10: Model Change (`model_change`)

**User answers:**
```
0.1  → 1 (Keep current)
1.1  → 1 (General chat)
2.1  → 2 (No thinking)
2.2  → 3 (Quality — best output)             ← quality preference
3.1  → 4 (Unlimited)
3.2  → 1 (Claude browser)
3.3  → 1 (Confirmed)
3.4  → 6 (Custom) → "Start with Sonnet, but I want to switch to Opus mid-session"
     Compiler-LLM interprets → model_preference="claude-sonnet", notes model_change intent
4.2  → 2 (No monitoring)
5.1  → 1 (Default)
5.2  → 2 (Script)
```

**Compiler-LLM invoked** to parse the model change intent.

**Compiled output:**
```python
config = ClaudeConfig()  # defaults to Sonnet

async with ClaudeChatAgent(config) as agent:
    # Initial chat with Sonnet
    r1 = await agent.chat("Hello, which model are you?")
    
    # Switch to Opus via browser DOM model selector
    await agent.change_model("claude-opus")
    
    # Verify new model
    r2 = await agent.chat("Confirm your model name")
```

**Equivalent test:** `test_model_change` — discovers available models via DOM dropdown, switches to Opus, verifies.

---

## 14. Detailed Examples — OpenRouter (10 Test Cases)

These examples show the full compiler flow for OpenRouter API agent use cases. The first 6 match `test_openrouter_live.py` tests; examples 7–10 demonstrate additional compiler scenarios for capabilities OpenRouter supports.

Auth context for all OpenRouter examples: `.env` has `OPENROUTER_API_KEY`, `DEFAULT_OPENROUTER_MODEL=stepfun/step-3.5-flash:free`.

---

### Example 1: Chat Single Turn (`chat_single`)

**User answers:**
```
0.1  → 1 (Keep current — uses OpenRouter as Compiler-LLM too)
1.1  → 1 (General chat)
2.1  → 2 (No thinking)
2.2  → 1 (Speed)
3.1  → 1 (Free)
3.2  → 4 (OpenRouter)
3.3  → 1 (Confirmed — OPENROUTER_API_KEY detected)
3.4  → 1 (stepfun/step-3.5-flash:free — default)
4.1  → 2 (No fallback)
4.2  → 2 (No monitoring)
5.1  → 1 (Default)
5.2  → 2 (Script)
```

**No Compiler-LLM calls** — all deterministic.

**Compiled output:**
```python
from universal_agents.providers.openrouter.chat import OpenRouterChatAgent
from universal_agents.providers.openrouter.config import OpenRouterConfig

config = OpenRouterConfig(
    model="stepfun/step-3.5-flash:free",
    temperature=0.0,
)

async def main():
    async with OpenRouterChatAgent(config) as agent:
        response = await agent.chat("What is 2+2?")
        print(response)  # "4"
```

**Equivalent test:** `test_chat_single` — single Q&A with `temperature=0.0`.

---

### Example 2: Chat Multi-Turn (`chat_multi`)

**User answers:**
```
0.1  → 1     1.1 → 1     2.1 → 2     2.2 → 2 (Balanced)
3.1  → 1     3.2 → 4     3.3 → 1     3.4 → 1
4.1  → 2     4.2 → 2     5.1 → 1     5.2 → 1 (Instance)
```

**Compiled output:**
```python
config = OpenRouterConfig(
    model="stepfun/step-3.5-flash:free",
    temperature=0.0,
)
agent = OpenRouterChatAgent(config)

r1 = await agent.chat("Remember the number 42")
r2 = await agent.chat("Double that number")      # "84"
r3 = await agent.chat("Add 16 to the result")    # "100"
assert len(agent.history.turns) == 3
```

**Equivalent test:** `test_chat_multi` — 3-turn context retention via API conversation history.

---

### Example 3: Chat with Thinking (`chat_thinking`)

**User answers:**
```
0.1  → 1
1.1  → 1 (General chat)
2.1  → 1 (Yes — show reasoning)              ← triggers thinking config
2.2  → 3 (Quality)
2.3  → 2 (No streaming)
3.1  → 3 (Medium budget)                      ← thinking needs a capable model
3.2  → 4 (OpenRouter)
3.3  → 1 (Confirmed)
3.4  → 2 (anthropic/claude-sonnet-4)          ← auto-suggested: thinking requires Claude/OpenAI model
4.1  → 1 (Yes — fallback)
4.2  → 2 (No monitoring)
5.1  → 1 (Default)
5.2  → 2 (Script)
```

**Compiler logic:** `needs_thinking=True` + OpenRouter → compiler must select a thinking-capable model. If user's default model doesn't support thinking (e.g., `stepfun/step-3.5-flash`), the compiler auto-suggests Claude or OpenAI models on OpenRouter and sets `enable_thinking=True`, `thinking_budget=5000`, `temperature=1.0` (required for Claude thinking).

**Compiled output:**
```python
from universal_agents.providers.openrouter.data import OpenRouterDataAgent
from universal_agents.providers.openrouter.config import OpenRouterDataConfig

config = OpenRouterDataConfig(
    model="anthropic/claude-sonnet-4",  # auto-switched for thinking support
    temperature=1.0,                     # required for Claude thinking
    enable_thinking=True,
    thinking_budget=5000,
)

async with OpenRouterDataAgent(config) as agent:
    response = await agent.chat("What are all the prime numbers below 20?")
    # response contains answer
    # agent.last_thinking contains chain-of-thought (if model supports it)
```

**Equivalent test:** `test_chat_thinking` — auto-switches to Claude model, `temperature=1.0`, extended thinking.

---

### Example 4: Data JSON Extraction (`data_json`)

**User answers:**
```
0.1  → 1
1.1  → 2 (Structured data extraction)        ← auto-sets needs_json_output=True
1.2  → 2 (No file upload)
2.1  → 2 (No thinking)
2.2  → 1 (Speed)
3.1  → 1 (Free)
3.2  → 4 (OpenRouter)
3.3  → 1 (Confirmed)
3.4  → 1 (default free model)
4.1  → 2 (No fallback)
4.2  → 2 (No monitoring)
5.1  → 3 (Data-focused system prompt)
5.2  → 2 (Script)
```

**Agent selection:** `use_case="data"` + `provider="openrouter"` → `OpenRouterDataAgent`.

**Compiled output:**
```python
from universal_agents.providers.openrouter.data import OpenRouterDataAgent
from universal_agents.providers.openrouter.config import OpenRouterDataConfig

config = OpenRouterDataConfig(
    model="stepfun/step-3.5-flash:free",
    temperature=0.0,
    system_prompt="Extract structured data. Respond only with valid JSON.",
)

async with OpenRouterDataAgent(config) as agent:
    prompt = agent.build_data_prompt(
        instruction="Process this record and add category",
        data={"name": "test_item", "value": 42},
    )
    response = await agent.chat(prompt)
    result = agent.parse_json_response(response)
    assert "name" in result and "processed" in result
```

**Equivalent test:** `test_data_json` — `build_data_prompt()` + `parse_json_response()`, verifies structured fields.

---

### Example 5: Data BREAK Prompt (`data_break`)

**User answers:**
```
0.1  → 1
1.1  → 6 (Custom) → "Generate chemistry trivia in Q/A JSON format"
     Compiler-LLM → use_case="data", needs_json_output=True
1.2  → 2 (No file upload)
2.1  → 2     2.2 → 1     3.1 → 1     3.2 → 4
3.3  → 1     3.4 → 1     4.1 → 2     4.2 → 2
5.1  → 5 (Custom) → "You generate chemistry trivia questions in JSON"
     Compiler-LLM refines → "You are a trivia generator. Given a topic, produce a JSON object with 'question' and 'answer' fields."
5.2  → 2 (Script)
```

**Compiler-LLM invoked twice.**

**Compiled output:**
```python
config = OpenRouterDataConfig(
    model="stepfun/step-3.5-flash:free",
    temperature=0.0,
    system_prompt="You are a trivia generator. Given a topic, produce a JSON object with 'question' and 'answer' fields.",
)

async with OpenRouterDataAgent(config) as agent:
    prompt = agent.build_data_prompt(
        instruction="Generate a chemistry trivia question about the periodic table",
        data={},
    )
    response = await agent.chat(prompt)
    result = agent.parse_json_response(response)
    assert "question" in result
```

**Equivalent test:** `test_data_break` — chemistry trivia Q/A JSON generation.

---

### Example 6: Model Change (`model_change`)

**User answers:**
```
0.1  → 1
1.1  → 1 (General chat)
2.1  → 2     2.2 → 2
3.1  → 1 (Free)
3.2  → 4 (OpenRouter)
3.3  → 1 (Confirmed)
3.4  → 6 (Custom) → "I want to use two models and compare them"
     Compiler-LLM → model_preference="stepfun/step-3.5-flash:free",
                     notes: multi-model comparison intent
4.1  → 1 (Yes — fallback with backup model)
4.2  → 2 (No monitoring)
5.1  → 1     5.2 → 2
```

**Compiler-LLM interprets** the multi-model intent and generates code with two config variants.

**Compiled output:**
```python
config_primary = OpenRouterConfig(
    model="stepfun/step-3.5-flash:free",
    temperature=0.0,
)
config_backup = OpenRouterConfig(
    model="nvidia/nemotron-3-super-120b-a12b:free",  # BACKUP_OPENROUTER_MODEL
    temperature=0.0,
)

async with OpenRouterChatAgent(config_primary) as agent1:
    r1 = await agent1.chat("What is 2+2?")

async with OpenRouterChatAgent(config_backup) as agent2:
    r2 = await agent2.chat("What is 2+2?")

# Both should respond correctly with different models
```

**Equivalent test:** `test_model_change` — creates two agents with different models, verifies both respond.

---

### Example 7: Streaming Chat (additional scenario)

**User answers:**
```
0.1  → 1
1.1  → 1 (General chat)
2.1  → 2 (No thinking)
2.2  → 1 (Speed)
2.3  → 1 (Yes — stream tokens)               ← streaming enabled
3.1  → 2 (Low cost)
3.2  → 4 (OpenRouter)
3.3  → 1     3.4 → 1
4.1  → 2     4.2 → 2
5.1  → 1     5.2 → 2
```

**Resolved requirements:** `needs_streaming=True` → config sets `stream=True`.

**Compiled output:**
```python
config = OpenRouterConfig(
    model="stepfun/step-3.5-flash:free",
    temperature=0.0,
    stream=True,
)

async with OpenRouterChatAgent(config) as agent:
    async for chunk in agent.chat_stream("Tell me a short joke"):
        print(chunk, end="", flush=True)
```

**Demonstrates:** Streaming capability unique to API providers. Not available on browser-based agents.

---

### Example 8: Fallback Chain with Monitoring (additional scenario)

**User answers:**
```
0.1  → 1
1.1  → 2 (Data extraction)
1.2  → 2 (No files)
2.1  → 2     2.2 → 2
3.1  → 1 (Free)
3.2  → 4 (OpenRouter)
3.3  → 1     3.4 → 1
4.1  → 1 (Yes — auto-retry with fallback)    ← fallback enabled
4.2  → 1 (Yes — monitoring)                  ← monitoring enabled
5.1  → 3 (Data-focused)
5.2  → 2 (Script)
```

**Compiled output:**
```python
from universal_agents.providers.openrouter.data import OpenRouterDataAgent
from universal_agents.providers.openrouter.config import OpenRouterDataConfig
from universal_agents.core.monitoring import MonitoredAgent, EventBus, Reporter

config = OpenRouterDataConfig(
    model="stepfun/step-3.5-flash:free",
    temperature=0.0,
    fallback_models=[
        "nvidia/nemotron-3-super-120b-a12b:free",
        "deepseek/deepseek-chat-v3.1:free",
    ],
    system_prompt="Extract structured data. Respond only with valid JSON.",
)

async with OpenRouterDataAgent(config) as base_agent:
    event_bus = EventBus()
    agent = MonitoredAgent(base_agent, event_bus)
    reporter = Reporter(event_bus)

    response = await agent.chat("Extract key entities from: ...")
    result = agent.parse_json_response(response)

    # If primary model fails, automatically tries fallback models
    # MonitoredAgent tracks: timing, tokens, success/failure, retries
    reporter.print_summary()
```

**Demonstrates:** Resilience (fallback chain) + observability (monitoring) — two Phase 4 capabilities combined.

---

### Example 9: Custom System Prompt via Compiler-LLM (additional scenario)

**User answers:**
```
0.1  → 1
1.1  → 6 (Custom) → "I want a code review assistant that checks Python for security issues"
     Compiler-LLM → use_case="code", needs_thinking=True
2.1  → [SKIPPED — auto-set by "code"]
2.2  → 3 (Quality)
2.3  → 2 (No streaming)
3.1  → 2 (Low cost)
3.2  → 4 (OpenRouter)
3.3  → 1     3.4 → 4 (deepseek/deepseek-chat-v3.1:free)
4.1  → 1 (Yes — fallback)
4.2  → 2 (No monitoring)
5.1  → 5 (Custom) → "Review Python code for OWASP top 10 vulnerabilities"
     Compiler-LLM refines → "You are a Python security code reviewer. Analyze code for OWASP Top 10 vulnerabilities including injection, broken auth, XSS, insecure deserialization, and known CVEs. Output findings as JSON with 'severity', 'vulnerability', 'line', and 'fix' fields."
5.2  → 2 (Script)
```

**Compiler-LLM invoked twice** — use case interpretation + system prompt generation.

**Compiled output:**
```python
config = OpenRouterDataConfig(
    model="deepseek/deepseek-chat-v3.1:free",
    temperature=0.0,
    fallback_models=["nvidia/nemotron-3-super-120b-a12b:free"],
    system_prompt=(
        "You are a Python security code reviewer. Analyze code for OWASP Top 10 "
        "vulnerabilities including injection, broken auth, XSS, insecure deserialization, "
        "and known CVEs. Output findings as JSON with 'severity', 'vulnerability', "
        "'line', and 'fix' fields."
    ),
)

async with OpenRouterDataAgent(config) as agent:
    code = open("app.py").read()
    prompt = agent.build_data_prompt(
        instruction="Review this code for security vulnerabilities",
        data={"code": code},
    )
    response = await agent.chat(prompt)
    findings = agent.parse_json_response(response)
```

**Demonstrates:** Full Compiler-LLM utilization — interpreting a custom use case and generating a specialized system prompt.

---

### Example 10: Paid Model with Reasoning (additional scenario)

**User answers:**
```
0.1  → 2 (Use OpenAI as Compiler-LLM)        ← changed Compiler-LLM!
1.1  → 2 (Data extraction)
1.2  → 2 (No files)
2.1  → 1 (Yes — show reasoning)
2.2  → 3 (Quality)
2.3  → 2 (No streaming)
3.1  → 4 (Unlimited)
3.2  → 4 (OpenRouter)
3.3  → 1 (Confirmed)
3.4  → 6 (Custom) → "Use the best Claude model available on OpenRouter"
     Compiler-LLM (now gpt-5.4-mini) → model_preference="anthropic/claude-sonnet-4"
4.1  → 1 (Yes — fallback)
4.2  → 1 (Yes — monitoring)
5.1  → 2 (Minimal)
5.2  → 2 (Script)
```

**Note:** Compiler-LLM is now OpenAI `gpt-5.4-mini` (user changed in 0.1). All subsequent "Custom" interpretations use that model.

**Compiled output:**
```python
from universal_agents.providers.openrouter.data import OpenRouterDataAgent
from universal_agents.providers.openrouter.config import OpenRouterDataConfig
from universal_agents.core.monitoring import MonitoredAgent, EventBus

config = OpenRouterDataConfig(
    model="anthropic/claude-sonnet-4",
    temperature=1.0,                    # required for Claude thinking
    enable_thinking=True,
    thinking_budget=10000,
    fallback_models=["openai/gpt-4.1", "anthropic/claude-haiku-4"],
    system_prompt="You are a helpful assistant.",
)

async with OpenRouterDataAgent(config) as base_agent:
    event_bus = EventBus()
    agent = MonitoredAgent(base_agent, event_bus)

    prompt = agent.build_data_prompt(
        instruction="Analyze this dataset and find anomalies",
        data={"records": [...]},
    )
    response = await agent.chat(prompt)
    result = agent.parse_json_response(response)
    # agent.last_thinking contains reasoning chain
    # agent.last_usage["reasoning_tokens"] shows thinking cost
```

**Demonstrates:** Changed Compiler-LLM, paid model, thinking + monitoring + fallback, all capabilities combined.
