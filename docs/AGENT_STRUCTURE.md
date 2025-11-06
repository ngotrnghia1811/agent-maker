# Agent Structure

## Directory Layout

```
src/universal_agents/
├── __init__.py
├── core/                           # Shared abstractions
│   ├── __init__.py
│   ├── base_agent.py               # BaseChatAgent ABC
│   ├── config.py                   # BaseConfig, BrowserConfig, APIConfig, CLIConfig
│   ├── exceptions.py               # AgentError hierarchy
│   ├── history.py                  # ConversationHistory (sliding window)
│   ├── output.py                   # save_turn, save_summary, save_full_results
│   ├── retry.py                    # @retry decorator
│   ├── types.py                    # Message, ConversationTurn, TurnResult, AgentStats
│   ├── json_utils.py               # JSON extraction from LLM responses
│   ├── prompt_builder.py           # System prompt builder
│   ├── srt_utils.py                # SRT parsing, chunking, overlap
│   ├── translation_prompts.py      # Translation prompt templates
│   └── kendo_context.py            # Kendo dictionary loader + SRT prompts
│
├── browser/                        # Browser automation layer
│   ├── __init__.py
│   ├── base_browser_agent.py       # BaseBrowserAgent (shared chat loop)
│   ├── browser_manager.py          # Playwright lifecycle, stealth, storage_state
│   ├── dom.py                      # find_element, type_text, click_submit
│   ├── response_detector.py        # 2-phase response detection
│   ├── selectors.py                # ProviderSelectors dataclass
│   └── js/                         # Injectable JavaScript
│       ├── fetch_override.js       # Claude API fetch interceptor
│       ├── gemini_fetch_override.js # Gemini API fetch interceptor
│       └── thinking_extractor.js   # React state BFS for thinking blocks
│
├── api/                            # HTTP API layer
│   ├── __init__.py
│   └── base_api_agent.py           # BaseAPIAgent (httpx, sync/stream)
│
├── cli/                            # CLI subprocess layer
│   ├── __init__.py
│   └── base_cli_agent.py           # BaseCLIAgent (asyncio.subprocess)
│
├── compiler/                       # Agent compiler pipeline
│   ├── __init__.py
│   ├── __main__.py                 # CLI: python -m universal_agents.compiler
│   ├── requirements.py             # UserRequirements dataclass
│   ├── question_flow.py            # Interview questions + presets
│   ├── auth_detector.py            # Detect API keys + storage states
│   ├── capability_resolver.py      # Map requirements → components
│   ├── config_builder.py           # Build config kwargs
│   ├── agent_assembler.py          # Assemble CompiledAgent + scripts
│   ├── agent_packager.py           # Self-contained package creator
│   ├── compiler_llm.py             # LLM for Custom option interpretation
│   └── compiler.py                 # Top-level orchestrator
│
├── providers/                      # Provider implementations
│   ├── __init__.py
│   ├── claude/
│   │   ├── __init__.py
│   │   ├── config.py               # ClaudeConfig, ClaudeDataConfig, ClaudeTranslatorConfig
│   │   ├── selectors.py            # CLAUDE_SELECTORS
│   │   ├── chat.py                 # ClaudeChatAgent (3-strategy thinking)
│   │   ├── data.py                 # ClaudeDataAgent (JSON prompts/extraction)
│   │   └── translator.py           # ClaudeTranslatorAgent (multi-turn + file upload)
│   ├── gemini/
│   │   ├── __init__.py
│   │   ├── config.py               # GeminiConfig, GeminiTranslatorConfig
│   │   ├── selectors.py            # GEMINI_SELECTORS
│   │   ├── chat.py                 # GeminiChatAgent (API interception thinking)
│   │   ├── data.py                 # GeminiDataAgent (JSON prompts/extraction)
│   │   └── translator.py           # GeminiTranslatorAgent (model select, rate limit, progress)
│   ├── gpt/
│   │   ├── __init__.py
│   │   ├── config.py               # GPTConfig
│   │   ├── selectors.py            # GPT_SELECTORS
│   │   └── chat.py                 # GPTChatAgent (minimal)
│   ├── pplx/
│   │   ├── __init__.py
│   │   ├── config.py               # PerplexityConfig
│   │   ├── selectors.py            # PPLX_SELECTORS + CITATION_SELECTORS
│   │   └── chat.py                 # PerplexityChatAgent (Citation extraction)
│   ├── openrouter/
│   │   ├── __init__.py
│   │   ├── config.py               # OpenRouterConfig, OpenRouterDataConfig
│   │   ├── chat.py                 # OpenRouterChatAgent (model fallback)
│   │   └── data.py                 # OpenRouterDataAgent (thinking budget)
│   ├── openai/
│   │   ├── __init__.py
│   │   ├── config.py               # OpenAIConfig
│   │   ├── chat.py                 # OpenAIChatAgent
│   │   └── data.py                 # OpenAIDataAgent (extended thinking)
│   └── copilot/
│       ├── __init__.py
│       ├── config.py               # CopilotConfig
│       └── chat.py                 # CopilotChatAgent (gh copilot CLI)
│
└── monitor/                        # Multi-agent monitoring
    ├── __init__.py
    ├── events.py                   # EventType, AgentEvent, EventBus
    ├── agent_registry.py           # AgentRegistry
    ├── monitored_agent.py          # MonitoredAgent wrapper
    ├── dashboard.py                # Dashboard (rich Live terminal UI)
    └── reporter.py                 # Reporter (post-run reports)
```

## Inheritance Hierarchy

```
BaseChatAgent (ABC)
├── BaseBrowserAgent
│   ├── ClaudeChatAgent
│   ├── ClaudeDataAgent
│   ├── GeminiChatAgent
│   ├── GeminiDataAgent
│   ├── GPTChatAgent
│   └── PerplexityChatAgent
├── BaseAPIAgent
│   ├── OpenRouterChatAgent
│   ├── OpenRouterDataAgent
│   ├── OpenAIChatAgent
│   └── OpenAIDataAgent
└── BaseCLIAgent
    └── CopilotChatAgent

# Standalone (wraps DataAgent, not in hierarchy)
GeminiTranslatorAgent  → wraps GeminiDataAgent
ClaudeTranslatorAgent  → wraps ClaudeDataAgent

BaseConfig
├── BrowserConfig
│   ├── ClaudeConfig → ClaudeDataConfig → ClaudeTranslatorConfig
│   ├── GeminiConfig → GeminiTranslatorConfig
│   ├── GPTConfig
│   └── PerplexityConfig
├── APIConfig
│   ├── OpenRouterConfig → OpenRouterDataConfig
│   └── OpenAIConfig
└── CLIConfig
    └── CopilotConfig
```

## Adding a New Provider

### Browser Provider (~50 lines)

1. Create `providers/my_provider/config.py`:
   ```python
   @dataclass
   class MyConfig(BrowserConfig):
       provider_name: str = "my_provider"
       base_url: str = "https://my-provider.com/chat"
   ```

2. Create `providers/my_provider/selectors.py`:
   ```python
   MY_SELECTORS = ProviderSelectors(
       input_selectors=["textarea#prompt"],
       submit_selectors=["button[type='submit']"],
       response_selectors=["div.response"],
   )
   ```

3. Create `providers/my_provider/chat.py`:
   ```python
   class MyChatAgent(BaseBrowserAgent):
       SELECTORS = MY_SELECTORS
       def __init__(self, config=None):
           super().__init__(config or MyConfig())
   ```

### API Provider (~30 lines)

Implement `_build_request_body()`, `_parse_response()`, and optionally `_parse_stream_chunk()`.

### CLI Provider (~20 lines)

Implement `_build_command()` and `_parse_output()`.
