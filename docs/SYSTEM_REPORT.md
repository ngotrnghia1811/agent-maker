# Synode — Council of AI Agents: System Report

> **Version:** 0.4.2 · **Generated:** 2026-03-13 · **Repo:** `mahatab/synode-council-of-ai-agents` · **Branch:** `main`
>
> A Tauri 2 desktop application that orchestrates multi-AI council discussions. React 19 + TypeScript frontend, Rust backend. Supports 8 AI providers with real-time SSE streaming, session persistence, and an embedded Telegram bot.

---

## 0. Report Guideline

### When to Update

| Code Change | Sections to Update |
|---|---|
| New file added | §1 Codebase Mapping |
| New class / module | §1, §2 Core Components |
| New AI provider | §1, §2, §3, §4 (constants, API endpoint), §5 (stream flow) |
| Parameter / config change | §4 Parameters & Configuration |
| New Tauri IPC command | §2 (`src-tauri/src/commands/`), §3 (IPC surface), §5 |
| New Telegram bot command | §2 (`telegram-bot/src/handlers.rs`), §3, §5 |
| Flow logic change (council orchestration) | §3, §5 Process Flows |
| New test file | §6 Verification & Quality |
| CI workflow change | §6 |
| Dependency version bump | §4 (dependency versions table) |

### How to Update

| Section | Trigger | Action |
|---|---|---|
| §0 Report Guideline | New section type needed | Add row to checklist |
| §1 Codebase Mapping | Any file added/removed/moved | Update ASCII tree; update "Files to Archive" if deprecated |
| §2 Core Components | New core module or method signature change | Add/update component table; verify dependencies list |
| §3 Key Abstractions | Domain logic change (prompts, state machine, IPC) | Update abstraction walkthroughs; re-verify code examples |
| §4 Parameters & Config | Default changed, env var added, constant moved | Update relevant sub-table; note old value if breaking |
| §5 Process Flows | Control flow change | Redraw affected ASCII diagram; update pseudocode |
| §6 Verification | Test added, CI pipeline modified | Update counts, commands, workflow description |
| §7 Quick Reference | Key file renamed/deleted | Update path + line count |

### Style Guidelines

| Element | Convention |
|---|---|
| Diagrams | ASCII box art: `┌─┐│└─┘───►` and `- - -►` for conditional |
| Tables | Markdown pipe-delimited |
| File paths | Relative from repo root, inline `backticks` |
| Identifiers | Exact as in code, in `backticks` |
| Uncertainties | `[UNCLEAR]` tag with explanation |

---

## 1. Codebase Mapping

**Total:** ~9,900 lines of source code across 76 files (`.ts`, `.tsx`, `.rs`).

```
synode-council-of-ai-agents/
│
# ══════════════ ROOT CONFIG ══════════════
├── Cargo.toml                         # Rust workspace root (src-tauri, council-core, telegram-bot)
├── Cargo.lock                         # Rust dependency lockfile
├── package.json                       # Node/npm config (v0.4.2), scripts: dev, build, lint, preview, tauri
├── package-lock.json                  # npm lockfile
├── tsconfig.json                      # TS project references (app + node)
├── tsconfig.app.json                  # TS config for src/ (ES2022, react-jsx, strict)
├── tsconfig.node.json                 # TS config for vite.config.ts (ES2023)
├── eslint.config.js                   # ESLint 9 flat config (TS + React Hooks + React Refresh)
├── vite.config.ts                     # Vite 7 config (React, Tailwind CSS v4, Tauri dev integration)
├── index.html                         # SPA entry point (Inter + JetBrains Mono fonts)
│
# ══════════════ DOCUMENTATION ══════════════
├── README.md                          # Project overview, features, quick start
├── CLAUDE.md                          # Current development status, architecture decisions
├── CONTRIBUTING.md                    # Contribution guidelines, setup, code style, PR process
├── LICENSE                            # MIT license
├── docs/
│   ├── ARCHITECTURE.md                # State machines, workspace structure, IPC, storage, streaming
│   ├── ADDING_PROVIDERS.md            # Step-by-step tutorial for adding new AI providers (6 steps)
│   ├── API_PROVIDERS.md               # Details for all 8 provider integrations
│   ├── SETUP_GUIDE.md                 # Development setup, API keys, Telegram bot
│   ├── TELEGRAM_BOT.md               # Telegram bot setup, commands, deployment
│   └── images/                        # Screenshots and diagrams
│       ├── screenshots/               # hero.png, settings.png, direct-chat.png, etc.
│       ├── synod.jpg
│       └── pixel-art-flowchart.jpg
│
# ══════════════ CI/CD ══════════════
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                     # macOS + Windows checks: ESLint, tsc, cargo check, clippy
│   │   └── release.yml                # Tauri build + release on v* tags (Apple code signing)
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
│
# ══════════════ SCRIPTS ══════════════
├── scripts/
│   ├── tauri-dev.sh                   # Wrapper: `cargo tauri dev`
│   └── tauri-build.sh                 # Wrapper: `cargo tauri build`
│
# ══════════════ FRONTEND (React 19 + TypeScript) ══════════════
├── src/
│   ├── main.tsx                       # React DOM entry point (StrictMode)
│   ├── App.tsx                        # Root component: loading → SetupWizard → MainLayout
│   │
│   ├── types/
│   │   └── index.ts                   # All TS types, Provider enum, PROVIDERS registry (355 lines)
│   │
│   ├── stores/                        # Zustand state management
│   │   ├── councilStore.ts            # Council discussion state machine (1,009 lines) ★
│   │   ├── directChatStore.ts         # 1-on-1 direct chat state (86 lines)
│   │   ├── sessionStore.ts            # Session CRUD + persistence (95 lines)
│   │   └── settingsStore.ts           # App settings + theme management (73 lines)
│   │
│   ├── lib/                           # Utility modules
│   │   ├── tauri.ts                   # Tauri IPC bindings — 15 exported functions (110 lines)
│   │   ├── sessionTitle.ts            # AI-generated session titles via master model
│   │   ├── theme.ts                   # Light/dark/system theme application
│   │   └── markdown.ts                # Markdown rendering config for react-markdown
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── MainLayout.tsx         # App shell: Sidebar + Header + ChatView/DirectChatView
│   │   │   ├── Header.tsx             # Top bar with settings button
│   │   │   └── Sidebar.tsx            # Session list, new chat, mode toggle
│   │   │
│   │   ├── chat/                      # Council & direct chat UI
│   │   │   ├── ChatView.tsx           # Council discussion view (534 lines) ★
│   │   │   ├── DirectChatView.tsx     # 1-on-1 chat view
│   │   │   ├── ModelResponse.tsx      # Individual model response card
│   │   │   ├── MasterVerdict.tsx      # Final verdict display with Scale icon
│   │   │   ├── StreamingText.tsx      # react-markdown with streaming cursor
│   │   │   ├── ThinkingIndicator.tsx  # Animated thinking dots
│   │   │   ├── UserMessage.tsx        # User message bubble
│   │   │   ├── ClarifyingQuestion.tsx # Clarifying Q&A UI
│   │   │   ├── FollowUpQuestion.tsx   # Follow-up question display
│   │   │   ├── AgentPicker.tsx        # Searchable model grid for direct chat
│   │   │   ├── MentionDropdown.tsx    # @mention autocomplete for follow-ups
│   │   │   ├── DiscussionSettingsBar.tsx  # Inline depth/style controls
│   │   │   └── ParallelStatusOverlay.tsx  # Real-time parallel execution tracker
│   │   │
│   │   ├── settings/
│   │   │   ├── SettingsModal.tsx      # Tabbed settings modal
│   │   │   ├── ApiKeyManager.tsx      # API key input per provider
│   │   │   ├── ApiKeyInfoPopover.tsx  # API key help/instructions
│   │   │   ├── ModelManager.tsx       # Drag-and-drop council model configuration
│   │   │   ├── AdvancedSettings.tsx   # System prompt mode, depth, style
│   │   │   ├── AppearanceSettings.tsx # Theme + cursor style selection
│   │   │   ├── SessionSettings.tsx    # Session save path configuration
│   │   │   └── TelegramSettings.tsx   # Telegram bot token + enable/disable
│   │   │
│   │   ├── setup/
│   │   │   └── SetupWizard.tsx        # First-run onboarding wizard
│   │   │
│   │   └── common/
│   │       ├── Button.tsx             # Reusable button (primary/secondary/ghost/danger)
│   │       ├── Modal.tsx              # Reusable modal overlay
│   │       ├── Toggle.tsx             # Toggle switch
│   │       └── ModeToggle.tsx         # Council ↔ Direct Chat mode toggle
│   │
│   └── styles/
│       └── globals.css                # Tailwind CSS v4 + CSS custom properties for theming
│
# ══════════════ TAURI DESKTOP APP (Rust) ══════════════
├── src-tauri/
│   ├── Cargo.toml                     # Crate "synode" v0.4.2, depends on council-core + telegram-bot
│   ├── Cargo.lock
│   ├── build.rs                       # Tauri code generation
│   ├── tauri.conf.json                # Tauri config: window, CSP, bundle, identifiers
│   ├── capabilities/
│   │   └── default.json               # Permissions: core, dialog, fs (read/write)
│   ├── icons/                         # App icons (ICO, ICNS, PNGs for all platforms)
│   └── src/
│       ├── main.rs                    # Entry point (windows_subsystem hidden in release)
│       ├── lib.rs                     # Tauri Builder: plugins, state, IPC handlers, bot auto-start
│       └── commands/
│           ├── mod.rs                 # Module re-exports
│           ├── api_calls.rs           # `stream_chat` — streaming chat via SSE (143 lines)
│           ├── keychain.rs            # `save/get/delete/has_api_key` (27 lines)
│           ├── sessions.rs            # `save/load/list/delete_session` + default path
│           ├── settings.rs            # `load/save_settings` (13 lines)
│           └── telegram.rs            # `start/stop/get_telegram_status` + TelegramBotState
│
# ══════════════ SHARED RUST LIBRARY ══════════════
├── crates/
│   ├── council-core/
│   │   ├── Cargo.toml                 # reqwest, tokio, serde, security-framework/keyring
│   │   └── src/
│   │       ├── lib.rs                 # Public module exports
│   │       ├── chat.rs               # `call_model()`, `call_model_streaming()`, provider router (155 lines)
│   │       ├── settings.rs            # JSON settings load/save to OS config dir
│   │       ├── sessions.rs            # JSON session CRUD to OS data dir
│   │       ├── models/
│   │       │   ├── mod.rs             # Module re-exports
│   │       │   ├── config.rs          # Provider, AppSettings, ModelConfig, enums (all data types)
│   │       │   └── session.rs         # Session, DiscussionEntry, SessionSummary
│   │       ├── providers/
│   │       │   ├── mod.rs             # AIProvider trait, `parse_sse_stream()`, StreamEvent (112 lines)
│   │       │   ├── anthropic.rs       # Anthropic Messages API
│   │       │   ├── openai.rs          # OpenAI Chat Completions API
│   │       │   ├── google.rs          # Google Generative Language API
│   │       │   ├── xai.rs             # xAI (OpenAI-compatible)
│   │       │   ├── deepseek.rs        # DeepSeek (OpenAI-compatible)
│   │       │   ├── mistral.rs         # Mistral (OpenAI-compatible)
│   │       │   ├── together.rs        # Together AI (OpenAI-compatible)
│   │       │   └── cohere.rs          # Cohere v2 API
│   │       └── keychain/
│   │           ├── mod.rs             # ApiKeyCache, provider extraction, CRUD operations
│   │           ├── macos.rs           # macOS Keychain via security-framework
│   │           └── windows.rs         # Windows Credential Manager via keyring crate
│   │
│   └── telegram-bot/
│       ├── Cargo.toml                 # teloxide 0.13, council-core dependency
│       └── src/
│           ├── lib.rs                 # `start_bot()` — teloxide dispatcher setup
│           ├── main.rs               # Standalone binary entry point
│           ├── handlers.rs            # 8 slash commands: /start, /council, /chat, /models, etc. (314 lines)
│           ├── council.rs             # `run_council()`, verdict generation, prompt building (634 lines)
│           ├── direct_chat.rs         # `start_direct_chat()`, `continue_direct_chat()` (260 lines)
│           ├── formatting.rs          # Markdown → Telegram HTML, typing indicators (496 lines)
│           └── state.rs               # AppState, ChatMode enum, per-chat tracking
│
# ══════════════ MISC / BUILD ARTIFACTS ══════════════
├── public/
│   └── synod-icon.png                 # App icon for web
├── CouncilOfAIAgents.xcodeproj/       # Xcode project (macOS build integration)
│   ├── project.pbxproj
│   └── xcshareddata/xcschemes/
│       ├── Build.xcscheme
│       └── Dev.xcscheme
└── .gitignore
```

### Package Boundaries (Rust Workspace)

| Crate | Path | Type | Depends On |
|---|---|---|---|
| `synode` | `src-tauri/` | Binary (Tauri app) | `council-core`, `council-telegram-bot` |
| `council-core` | `crates/council-core/` | Library | (external only) |
| `council-telegram-bot` | `crates/telegram-bot/` | Library + Binary | `council-core` |

### Files to Archive

| File | Reason | Recommended Action |
|---|---|---|
| `CouncilOfAIAgents.xcodeproj/` | macOS build artifact — Tauri handles native builds | Archive or add to `.gitignore` |
| `src-tauri/Cargo.lock` | Redundant — workspace root `Cargo.lock` is authoritative | Remove (workspace resolver handles this) |

---

## 2. Core Components (Detailed)

### 2.1 `councilStore` — Council Discussion State Machine

**File:** `src/stores/councilStore.ts` (1,009 lines)

Orchestrates the full multi-model council discussion lifecycle: user input → system prompt generation → model turns (sequential or parallel) → clarifying Q&A → master verdict → follow-ups. This is the most complex module in the frontend.

| Method | Description | Parameters | Returns |
|---|---|---|---|
| `startDiscussion()` | Run full council flow: prompt generation, model turns, verdict | `userQuestion: string`, `models: ModelConfig[]`, `masterModel`, `systemPromptMode`, `discussionDepth`, `discussionStyle`, `getApiKey`, `onEntryComplete` | `Promise<void>` |
| `sendFollowUp()` | Send @mention follow-up to specific model with full context | `targetProvider`, `targetModel`, `targetDisplayName`, `followUpQuestion`, `discussionEntries`, `getApiKey`, `onEntryComplete` | `Promise<void>` |
| `submitClarification()` | Submit user answer to clarifying question | `answer: string` | `void` |
| `reset()` | Reset all state to idle | — | `void` |

**Key State:**

| Attribute | Type | Description |
|---|---|---|
| `state` | `CouncilState` | State machine: `idle → user_input → generating_system_prompts → model_turn → clarifying_qa → master_verdict → complete` |
| `currentModelIndex` | `number` | Index of currently responding model (-1 = none) |
| `currentStreamContent` | `string` | Accumulated streaming content for active model |
| `systemPrompts` | `Map<string, string>` | Generated system prompts keyed by `provider:model` |
| `parallelStreams` | `Map<number, { content: string; done: boolean }>` | Parallel model streams in independent mode |
| `waitingForClarification` | `boolean` | Whether UI should show clarification input |

**Dependencies:** `zustand`, `uuid`, `../lib/tauri` (IPC), `../types`

---

### 2.2 `council-core::providers` — AI Provider Abstraction Layer

**File:** `crates/council-core/src/providers/mod.rs` (112 lines) + 8 provider modules

Unified streaming interface for all AI providers. Handles SSE parsing with TCP chunk-boundary-safe line buffering.

| Function/Type | Description | Parameters | Returns |
|---|---|---|---|
| `parse_sse_stream()` | Parse SSE byte stream into `StreamEvent`s | `byte_stream: S`, `parse_event: F` | `TokenStream` (pinned boxed stream) |
| `trait AIProvider` | Provider interface (async streaming chat) | — | — |
| `StreamEvent::Token(String)` | A text token from the model | — | — |
| `StreamEvent::Usage(UsageData)` | Token usage data from the model | — | — |

**Key Types:**

| Type | Fields | Description |
|---|---|---|
| `TokenStream` | `Pin<Box<dyn Stream<Item = Result<StreamEvent>> + Send>>` | Async stream of events |
| `UsageData` | `input_tokens: u32`, `output_tokens: u32` | Token usage tracking |

**Provider Implementations:**

| Provider | File | API Endpoint | Notes |
|---|---|---|---|
| `AnthropicProvider` | `anthropic.rs` | `api.anthropic.com/v1/messages` | Custom SSE format (`content_block_delta`) |
| `OpenAIProvider` | `openai.rs` | `api.openai.com/v1/chat/completions` | Standard SSE |
| `GoogleProvider` | `google.rs` | `generativelanguage.googleapis.com` | `streamGenerateContent` with SSE=true |
| `XAIProvider` | `xai.rs` | `api.x.ai/v1/chat/completions` | OpenAI-compatible |
| `DeepSeekProvider` | `deepseek.rs` | `api.deepseek.com/chat/completions` | OpenAI-compatible |
| `MistralProvider` | `mistral.rs` | `api.mistral.ai/v1/chat/completions` | OpenAI-compatible |
| `TogetherProvider` | `together.rs` | `api.together.xyz/v1/chat/completions` | OpenAI-compatible |
| `CohereProvider` | `cohere.rs` | `api.cohere.com/v2/chat` | Custom SSE format |

**Dependencies:** `reqwest` (HTTP), `futures` (stream combinators), `serde_json`, `anyhow`, `bytes`

---

### 2.3 `council-core::keychain` — Secure Credential Storage

**File:** `crates/council-core/src/keychain/mod.rs` + `macos.rs` + `windows.rs`

Thread-safe API key management with platform-native secure storage. All keys stored as a single JSON blob per platform keychain entry with in-memory caching.

| Function | Description | Parameters | Returns |
|---|---|---|---|
| `save_api_key()` | Save API key for a provider | `cache: &ApiKeyCache`, `service: &str`, `api_key: &str` | `Result<(), String>` |
| `get_api_key()` | Retrieve API key | `cache: &ApiKeyCache`, `service: &str` | `Result<Option<String>, String>` |
| `delete_api_key()` | Remove API key | `cache: &ApiKeyCache`, `service: &str` | `Result<(), String>` |
| `has_api_key()` | Check if key exists | `cache: &ApiKeyCache`, `service: &str` | `Result<bool, String>` |

**Key Types:**

| Type | Description |
|---|---|
| `ApiKeyCache` | `Mutex<Option<HashMap<String, String>>>` — Lazy-loaded thread-safe cache |

**Platform Details:**
- **macOS:** `security-framework` crate → macOS Keychain (`get/set/delete_generic_password`)
- **Windows:** `keyring` crate → Windows Credential Manager
- **Legacy migration:** On macOS, migrates old per-provider keychain entries to unified JSON blob

---

### 2.4 `council-core::chat` — Chat Orchestration

**File:** `crates/council-core/src/chat.rs` (155 lines)

High-level chat API used by the Telegram bot. Routes to the correct provider and collects streaming results.

| Function | Description | Parameters | Returns |
|---|---|---|---|
| `call_model()` | Non-streaming model call (collects full response) | `provider`, `model`, `messages`, `system_prompt`, `api_key` | `Result<ChatResult>` |
| `call_model_streaming()` | Streaming call with per-token callback | same + `on_token: FnMut(&str)` | `Result<ChatResult>` |
| `create_stream()` | Internal: route to provider's `stream_chat` | same as `call_model` | `Result<TokenStream>` |
| `collect_stream()` | Internal: drain stream into `ChatResult` | `stream: TokenStream` | `Result<ChatResult>` |

**Key Type:** `ChatResult { content: String, usage: Option<UsageData> }`

**Dependencies:** All 8 provider modules, `futures::StreamExt`, `anyhow`

---

### 2.5 `src-tauri::commands::api_calls` — Tauri IPC Streaming Bridge

**File:** `src-tauri/src/commands/api_calls.rs` (143 lines)

Bridges the Tauri frontend to the Rust streaming backend. Emits `stream-token-{streamId}` events to the frontend as tokens arrive.

| Command | Description | Parameters | Returns |
|---|---|---|---|
| `stream_chat` | Stream LLM response with real-time token emission | `provider: Provider`, `model`, `messages`, `system_prompt`, `api_key`, `stream_id` | `Result<StreamChatResult, String>` |

**Token Emission:** Uses `app.emit("stream-token-{id}", StreamToken { ... })` for each token.

**Usage Tracking:** MAX aggregation (not SUM) to handle cumulative usage reports from some providers (e.g., Google).

---

### 2.6 `telegram-bot` — Telegram Bot Integration

**Files:** `crates/telegram-bot/src/` (6 source files, 1,704+ lines total)

Full Telegram bot via `teloxide` 0.13 with council orchestration, direct chat, and slash commands.

| Module | File | Description |
|---|---|---|
| `handlers` | `handlers.rs` (314 lines) | 8 slash commands + free-text message routing |
| `council` | `council.rs` (634 lines) | `run_council()`, system prompts, clarifying Q&A, master verdict |
| `direct_chat` | `direct_chat.rs` (260 lines) | 1-on-1 chat with any model, multi-turn history |
| `formatting` | `formatting.rs` (496 lines) | Markdown → Telegram HTML, typing indicators, message splitting |
| `state` | `state.rs` | `AppState`, `ChatMode` enum, per-chat tracking |
| `lib` | `lib.rs` | `start_bot()` — teloxide dispatcher setup with dptree |

**Telegram Commands:**

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/council <question>` | Start council discussion |
| `/chat <model> <message>` | Direct 1-on-1 chat |
| `/models` | List configured council models |
| `/sessions` | List recent sessions |
| `/settings` | Show current settings |
| `/stop` | Cancel ongoing activity |
| `/help` | Show command reference |

**Dependencies:** `teloxide`, `council-core`, `tokio`, `serde_json`, `chrono`, `log`

---

### 2.7 `settingsStore` — Application Settings State

**File:** `src/stores/settingsStore.ts` (73 lines)

Zustand store managing all app settings with persistence via Tauri IPC.

| Method | Description | Parameters | Returns |
|---|---|---|---|
| `loadSettings()` | Load settings from disk via Tauri, apply theme | — | `Promise<void>` |
| `updateSettings()` | Merge partial update, persist | `partial: Partial<AppSettings>` | `Promise<void>` |
| `setTheme()` | Apply and persist theme | `theme: ThemeMode` | `Promise<void>` |
| `setAppMode()` | Switch between council and direct chat | `mode: AppMode` | `void` |

**Key State:** `settings: AppSettings`, `loaded: boolean`, `appMode: AppMode`

---

### 2.8 `sessionStore` — Session Persistence

**File:** `src/stores/sessionStore.ts` (95 lines)

CRUD operations for council and direct chat sessions, persisted as JSON files.

| Method | Description |
|---|---|
| `loadSessions()` | List all session summaries from disk |
| `createSession()` | Create and persist a new session |
| `saveCurrentSession()` | Persist current session state |
| `loadSession(id)` | Load full session by ID |
| `deleteSession(id)` | Delete session file from disk |

---

## 3. Key Abstractions and Domain Logic

### 3.1 Council Discussion Model

The core domain concept is a **council of AI models** deliberating on a user question. The discussion follows a configurable state machine.

**State Machine (`CouncilState`):**

```
idle
 │
 ▼
user_input ──► generating_system_prompts (if upfront mode)
                   │
                   ▼
              model_turn ◄────────── (loop for each council model)
                   │
                   ├──► clarifying_qa (first model only, if question detected)
                   │         │
                   │         ▼ submitClarification()
                   │    model_turn (retry with clarification context)
                   │
                   ▼
              master_verdict
                   │
                   ▼
              complete ──► follow_up (via @mention)
```

**Discussion Entries (`DiscussionEntry` union type):**

| Variant | Fields | Description |
|---|---|---|
| `User` | `content` | User's original question |
| `Model` | `provider`, `model`, `displayName`, `content`, `systemPrompt?`, `clarifyingExchange?`, `usage?` | Individual model's response |
| `MasterVerdict` | `provider`, `model`, `content`, `usage?` | Synthesized final verdict |
| `FollowUpQuestion` | `content`, `targetProvider`, `targetModel`, `targetDisplayName` | User's @mention follow-up |
| `FollowUpAnswer` | `provider`, `model`, `displayName`, `content`, `usage?` | Model's follow-up response |

### 3.2 System Prompt Generation

Two modes controlled by `SystemPromptMode`:

**Upfront Mode:**
1. Master model receives the user question + council model list
2. Returns JSON object mapping `provider:model` → tailored system prompt
3. Each council model gets its unique prompt before responding
4. First model is instructed it MAY ask up to 2 clarifying questions
5. Remaining models are told they CANNOT ask questions

**Prompt generation request (from `councilStore.ts`):**
```
"You are the orchestrator of a council of AI models helping a user make 
an informed decision. The user's question is: "{question}"

The following AI models will {discuss|independently analyze} this question:
1. {model1} ({provider1})
2. {model2} ({provider2})
...

Generate a specific, tailored system prompt for EACH council model..."
```

**Dynamic Mode:** System prompts generated per-model at runtime with discussion context included. The master model generates a context-aware prompt for each subsequent model.

### 3.3 Discussion Styles

| Style | Behavior | First Model | Remaining Models |
|---|---|---|---|
| `sequential` | Each model sees all prior responses | Runs first, may ask clarifying Qs | Run one-by-one, each sees all prior |
| `independent` | Models respond without seeing each other | Runs first (sequentially, may ask Qs) | Run **in parallel** for speed |

In `independent` mode, the first model still runs sequentially (to handle clarifying Q&A), then remaining models execute concurrently via `Promise.all()` with per-stream tracking in `parallelStreams`.

### 3.4 Tauri IPC Contract

All frontend ↔ backend communication uses Tauri's `invoke()` (request/response) and `listen()` (events).

**Commands (invoke):**

| Command | Direction | Payload | Response |
|---|---|---|---|
| `save_api_key` | FE → BE | `{ service, apiKey }` | `()` |
| `get_api_key` | FE → BE | `{ service }` | `Option<String>` |
| `delete_api_key` | FE → BE | `{ service }` | `()` |
| `has_api_key` | FE → BE | `{ service }` | `bool` |
| `stream_chat` | FE → BE | `{ provider, model, messages, systemPrompt, apiKey, streamId }` | `StreamChatResult` |
| `save_session` | FE → BE | `{ session, customPath? }` | `()` |
| `load_session` | FE → BE | `{ sessionId, customPath? }` | `Session` |
| `list_sessions` | FE → BE | `{ customPath? }` | `Vec<SessionSummary>` |
| `delete_session` | FE → BE | `{ sessionId, customPath? }` | `()` |
| `get_default_sessions_path` | FE → BE | `{}` | `String` |
| `load_settings` | FE → BE | `{}` | `AppSettings` |
| `save_settings` | FE → BE | `{ settings }` | `()` |
| `start_telegram_bot` | FE → BE | `{ token }` | `()` |
| `stop_telegram_bot` | FE → BE | `{}` | `()` |
| `get_telegram_status` | FE → BE | `{}` | `{ running: bool }` |

**Events (listen):**

| Event | Direction | Payload | Description |
|---|---|---|---|
| `stream-token-{streamId}` | BE → FE | `StreamToken { streamId, token, done, error?, usage? }` | Real-time SSE token forwarding |

### 3.5 Provider Integration Pattern

Each provider follows this pattern:

1. **Constructor:** Create `reqwest::Client` instance
2. **`stream_chat()`:** Build provider-specific JSON body → POST to API → Get byte stream → Pass to `parse_sse_stream()` with a provider-specific JSON parser closure
3. **SSE Parsing:** `parse_sse_stream()` handles line buffering across TCP chunks, strips `data:` prefixes, detects `[DONE]`, parses JSON events
4. **Usage Tracking:** `MAX` aggregation (not SUM) — accommodates providers like Google that send cumulative usage counts

**Provider-specific differences:**

| Provider | SSE Token Field | SSE Usage Location |
|---|---|---|
| Anthropic | `event.delta.text` (on `content_block_delta`) | `message_start.message.usage` + `message_delta.usage` |
| OpenAI-compatible (5 providers) | `event.choices[0].delta.content` | `event.usage` (final event) |
| Google | `event.candidates[0].content.parts[0].text` | `event.usageMetadata` |
| Cohere | `event.delta.message.content.text` | `event.delta.usage` |

### 3.6 Session Persistence Model

Sessions are stored as individual JSON files, one per session:

**Storage Locations:**
- **Settings:** `{config_dir}/council-of-ai-agents/settings.json`
  - macOS: `~/Library/Application Support/council-of-ai-agents/settings.json`
- **Sessions:** `{data_dir}/council-of-ai-agents/sessions/{uuid}.json`
  - macOS: `~/Library/Application Support/council-of-ai-agents/sessions/`
- **Custom path:** User-configurable override via `sessionSavePath` setting

**Session JSON Structure:**
```json
{
  "id": "uuid-v4",
  "title": "AI-generated title",
  "createdAt": "ISO8601",
  "updatedAt": "ISO8601",
  "userQuestion": "...",
  "councilConfig": {
    "models": [...],
    "masterModel": { "provider": "...", "model": "..." },
    "systemPromptMode": "upfront"
  },
  "discussion": [ /* DiscussionEntry[] */ ],
  "sessionType": "council | direct_chat",
  "directChatAgent": { "provider": "...", "model": "...", "displayName": "..." },
  "directChatMessages": [ /* DirectChatMessage[] */ ]
}
```

### 3.7 Telegram Bot Architecture

The Telegram bot can run in two modes:

1. **Embedded:** Spawned as a `tokio` task inside the Tauri app process. Shares the same `ApiKeyCache`, settings, and session storage. Started/stopped via frontend toggle.

2. **Standalone:** Run as a separate binary (`council-telegram-bot`), reads settings and keychain from the same OS-standard paths.

**State management:** Per-chat `ChatMode` enum tracked in `Arc<RwLock<HashMap<i64, ChatMode>>>`:
- `Idle` — No active operation
- `CouncilActive` — Council discussion in progress
- `CouncilWaitingClarification { ... }` — Waiting for user's clarification answer
- `DirectChat { session, agent, messages }` — Active 1-on-1 chat with message history

---

## 4. Parameters and Configuration (Complete)

### 4.1 Environment Variables

| Variable | Required? | Default | Description |
|---|---|---|---|
| `TELOXIDE_TOKEN` | Yes (standalone bot only) | — | Telegram bot token for standalone binary |
| `TAURI_DEV_HOST` | No | — | Override Vite dev server host (for Tauri mobile dev) |
| `TAURI_ENV_PLATFORM` | No | — | Set by Tauri: `windows` or `macos` — affects build target |
| `TAURI_ENV_DEBUG` | No | — | Set by Tauri: enables sourcemaps, disables minification |

### 4.2 Application Settings (`AppSettings`)

Persisted to `{config_dir}/council-of-ai-agents/settings.json`.

| Key | Type | Default | Description |
|---|---|---|---|
| `councilModels` | `ModelConfig[]` | `[]` | Ordered list of council member models |
| `masterModel` | `MasterModelConfig` | `{ provider: "anthropic", model: "claude-opus-4-6" }` | Model for prompt generation + verdicts |
| `systemPromptMode` | `"upfront" \| "dynamic"` | `"upfront"` | When to generate system prompts |
| `discussionDepth` | `"thorough" \| "concise"` | `"thorough"` | Response detail level instruction |
| `discussionStyle` | `"sequential" \| "independent"` | `"sequential"` | Whether models see each other's responses |
| `theme` | `"light" \| "dark" \| "system"` | `"system"` | UI theme |
| `cursorStyle` | `"ripple" \| "breathing" \| "orbit" \| "multi"` | `"orbit"` | Streaming cursor animation style |
| `sessionSavePath` | `string \| null` | `null` (uses OS default) | Custom session storage directory |
| `setupCompleted` | `boolean` | `false` | Whether first-run wizard was completed |
| `telegramEnabled` | `boolean` | `false` | Whether Telegram bot auto-starts with app |

### 4.3 Tauri Configuration (`src-tauri/tauri.conf.json`)

| Key | Value | Description |
|---|---|---|
| `productName` | `"Synode"` | Application display name |
| `version` | `"0.4.2"` | Current release version |
| `identifier` | `"com.council-of-ai-agents.app"` | Bundle identifier |
| `build.devUrl` | `http://localhost:5173` | Vite dev server URL |
| `build.frontendDist` | `../dist` | Built frontend assets path |
| `app.windows[0].width` | `1200` | Default window width |
| `app.windows[0].height` | `800` | Default window height |
| `app.windows[0].minWidth` | `900` | Minimum window width |
| `app.windows[0].minHeight` | `600` | Minimum window height |
| `app.windows[0].titleBarStyle` | `"Overlay"` | macOS-style overlay title bar |
| `app.security.csp` | (see below) | Content Security Policy |
| `bundle.category` | `"Utility"` | macOS app category |
| `bundle.macOS.minimumSystemVersion` | `"10.15"` | Minimum macOS version (Catalina) |

**CSP connects to:** `api.anthropic.com`, `api.openai.com`, `generativelanguage.googleapis.com`, `api.x.ai`, `api.deepseek.com`, `api.mistral.ai`, `api.together.xyz`, `api.cohere.com`

### 4.4 Vite Configuration (`vite.config.ts`)

| Key | Value | Description |
|---|---|---|
| `server.port` | `5173` | Dev server port |
| `server.strictPort` | `true` | Fail if port unavailable |
| `server.hmr.port` | `5174` | HMR WebSocket port (when Tauri host set) |
| `build.target` | `chrome105` (Windows) / `safari13` (macOS) | Browser target per platform |
| `envPrefix` | `['VITE_', 'TAURI_ENV_*']` | Env vars exposed to frontend |

### 4.5 Hardcoded Constants

| Constant | Value | Location | Description |
|---|---|---|---|
| `KEYCHAIN_SERVICE` | `"com.council-of-ai-agents.keys"` | `crates/council-core/src/keychain/mod.rs` | Keychain service name for unified blob |
| `KEYCHAIN_ACCOUNT` | `"api-keys"` | same | Keychain account name |
| `max_tokens` | `4096` | `crates/council-core/src/providers/anthropic.rs` | Max tokens per Anthropic request |
| Typing interval | `4s` | `crates/telegram-bot/src/formatting.rs` | Telegram typing indicator refresh |
| Clarifying Q detection | `looksLikeClarifyingQuestion()` | `src/stores/councilStore.ts` | Heuristic: checks if response ends with `?` pattern |

### 4.6 Provider Registry (`PROVIDERS` constant in `src/types/index.ts`)

| Provider ID | Display Name | Keychain Service | Models |
|---|---|---|---|
| `anthropic` | Anthropic | `com.council-of-ai-agents.anthropic` | Claude Opus 4.6, Sonnet 4.6, Sonnet 4.5, Haiku 4.5 |
| `openai` | OpenAI | `com.council-of-ai-agents.openai` | (configured in types) |
| `google` | Google | `com.council-of-ai-agents.google` | (configured in types) |
| `xai` | xAI | `com.council-of-ai-agents.xai` | (configured in types) |
| `deepseek` | DeepSeek | `com.council-of-ai-agents.deepseek` | (configured in types) |
| `mistral` | Mistral | `com.council-of-ai-agents.mistral` | (configured in types) |
| `together` | Together AI | `com.council-of-ai-agents.together` | (configured in types) |
| `cohere` | Cohere | `com.council-of-ai-agents.cohere` | (configured in types) |

### 4.7 Dependency Versions

**Rust (key dependencies from Cargo.toml files):**

| Dependency | Version | Crate | Purpose |
|---|---|---|---|
| `tauri` | 2.10.0 | src-tauri | Desktop framework |
| `reqwest` | 0.12 | council-core | HTTP (stream + JSON + rustls-tls) |
| `tokio` | 1 (full) | all | Async runtime |
| `serde` | 1.0 | all | Serialization |
| `serde_json` | 1.0 | all | JSON parsing |
| `futures` | 0.3 | council-core, src-tauri | Stream combinators |
| `teloxide` | 0.13 | telegram-bot | Telegram bot framework |
| `security-framework` | 2.11 | council-core (macOS) | Keychain access |
| `keyring` | 3 | council-core (Windows) | Credential Manager |
| `chrono` | 0.4 | council-core, telegram-bot | Date/time |
| `dirs` | 5 | council-core | OS standard directories |
| `anyhow` | 1 | council-core | Error handling |
| `bytes` | 1 | council-core | Byte buffer manipulation |

**JavaScript/TypeScript (from package.json):**

| Dependency | Version | Purpose |
|---|---|---|
| `react` | ^19.2.0 | UI framework |
| `react-dom` | ^19.2.0 | React DOM renderer |
| `zustand` | ^5.0.11 | State management |
| `@tauri-apps/api` | ^2.10.1 | Tauri frontend API |
| `@tauri-apps/plugin-dialog` | ^2.6.0 | Native file dialogs |
| `@tauri-apps/plugin-fs` | ^2.4.5 | Native filesystem access |
| `framer-motion` | ^12.34.3 | Animations |
| `react-markdown` | ^10.1.0 | Markdown rendering |
| `react-syntax-highlighter` | ^16.1.1 | Code block highlighting |
| `remark-gfm` | ^4.0.1 | GitHub Flavored Markdown |
| `lucide-react` | ^0.575.0 | Icons |
| `uuid` | ^13.0.0 | UUID generation |
| `@dnd-kit/core` | ^6.3.1 | Drag and drop |
| `@dnd-kit/sortable` | ^10.0.0 | Sortable DnD |
| `tailwindcss` | ^4.2.1 | CSS framework (via Vite plugin) |
| `vite` | ^7.3.1 | Build tool |
| `typescript` | ~5.9.3 | Type checking |
| `eslint` | ^9.39.1 | Linting |

---

## 5. Process Flows

### 5.1 Primary Flow: Council Discussion (Sequential Mode)

```
┌──────────┐  question   ┌──────────────────┐  JSON prompts  ┌──────────────┐
│   User   │────────────►│  Master Model    │───────────────►│ System Prompt│
│  Input   │             │  (Prompt Gen)    │                │    Map       │
└──────────┘             └──────────────────┘                └──────┬───────┘
                                                                    │
                          ┌─────────────────────────────────────────┘
                          │
                          ▼
                  ┌───────────────┐  SSE tokens  ┌───────────┐
                  │  Model 1      │─────────────►│  Frontend │
                  │  (+ sys prompt)│              │  Render   │
                  └───────┬───────┘              └───────────┘
                          │
               clarifying │ question?
                          │
                    ┌─────▼─────┐  answer   ┌───────────────┐
                    │ Clarify   │◄──────────│     User      │
                    │   Q&A     │           └───────────────┘
                    └─────┬─────┘
                          │
                          ▼
                  ┌───────────────┐  SSE tokens  ┌───────────┐
                  │  Model 2      │─────────────►│  Frontend │
                  │  (sees M1)    │              │  Render   │
                  └───────┬───────┘              └───────────┘
                          │
                         ...  (repeat for N models)
                          │
                          ▼
                  ┌───────────────┐  SSE tokens  ┌───────────┐
                  │  Master Model │─────────────►│  Verdict  │
                  │  (Verdict)    │              │  Display  │
                  └───────────────┘              └─────┬─────┘
                                                       │
                                                       ▼
                                                ┌─────────────┐
                                                │  Complete    │
                                                │ (auto-save)  │
                                                └─────────────┘

Pseudocode: Verdict = Master(M1(Q, clarify?) + M2(Q, ctx) + ... + Mn(Q, ctx))
```

### 5.2 Independent (Parallel) Mode

```
┌──────────┐
│   User   │
│  Input   │
└────┬─────┘
     │
     ▼
┌──────────────┐   sequential   ┌──────────────┐
│  Model 1     │───────────────►│  Clarify?    │
│ (first only) │                │              │
└──────────────┘                └──────┬───────┘
                                       │
     ┌─────────────────────────────────┘
     │                 parallel (Promise.all)
     ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Model 2  │    │ Model 3  │    │ Model N  │
│ (stream) │    │ (stream) │    │ (stream) │
└────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │
     └───────┬───────┘───────┬───────┘
             │               │
             ▼               ▼
       ┌──────────────────────────┐
       │  ParallelStatusOverlay   │
       │  (real-time per-model)   │
       └────────────┬─────────────┘
                    │ all done
                    ▼
            ┌───────────────┐
            │ Master Verdict│
            └───────────────┘

Pseudocode: Verdict = Master(M1(Q) ‖ M2(Q) ‖ ... ‖ Mn(Q))
```

### 5.3 Streaming Token Flow (Tauri IPC)

```
┌──────────────┐ HTTP POST  ┌──────────┐  SSE bytes  ┌────────────┐
│  Provider    │◄───────────│  reqwest  │◄────────────│  AI API    │
│  Module      │            │  Client   │             │  Server    │
└──────┬───────┘            └──────────┘             └────────────┘
       │ parse_sse_stream()
       │ StreamEvent::Token
       ▼
┌──────────────┐ app.emit()  ┌──────────────┐ listen()  ┌──────────┐
│  api_calls   │────────────►│  Tauri Event │──────────►│  React   │
│  (command)   │ "stream-    │  Bus         │           │  Store   │
└──────────────┘  token-{id}"└──────────────┘           └────┬─────┘
                                                             │ setState
                                                             ▼
                                                      ┌──────────────┐
                                                      │ StreamingText│
                                                      │ (Markdown)   │
                                                      └──────────────┘

Flow: HTTP SSE → parse_sse_stream → StreamEvent → app.emit → listen → setState → render
```

### 5.4 Application Startup Sequence

```
┌──────────┐   create    ┌────────────────┐
│ main.rs  │────────────►│ Tauri Builder  │
└──────────┘             └───────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
             ┌──────────┐ ┌──────────┐ ┌──────────────┐
             │ Register │ │ Register │ │   .setup()   │
             │ Plugins  │ │   State  │ │   callback   │
             │ (log,    │ │(ApiKey   │ │              │
             │  dialog, │ │ Cache,   │ └──────┬───────┘
             │  fs)     │ │ BotState)│        │
             └──────────┘ └──────────┘        │
                                              ▼
                                   ┌─────────────────────┐
                                   │ load_settings()     │
                                   │ if telegram_enabled: │
                                   │   get bot token     │
                                   │   spawn bot task    │
                                   └─────────┬───────────┘
                                             │
                                             ▼
                                   ┌─────────────────────┐ loadSettings()
                                   │  invoke_handler     │◄──────────────── React App
                                   │  (15 IPC commands)  │ setup_completed?
                                   └─────────────────────┘      │
                                                                ▼
                                                    SetupWizard OR MainLayout
```

### 5.5 Telegram Bot Message Flow

```
┌──────────┐  /council Q   ┌──────────────┐
│ Telegram │──────────────►│  handlers.rs │
│  User    │               │  (command)   │
└──────────┘               └──────┬───────┘
                                  │
                 ┌────────────────┘
                 ▼
       ┌──────────────────┐ call_model_streaming()  ┌────────────┐
       │  council.rs      │────────────────────────►│ council-   │
       │  run_council()   │                         │ core::chat │
       └────────┬─────────┘                         └────────────┘
                │
                │ for each model:
                │   1. Build messages + system prompt
                │   2. Stream response
                │   3. Check for clarifying Q
                │   4. Send typing indicator
                │   5. Format markdown → HTML
                │
                ▼
       ┌──────────────────┐   formatted HTML  ┌──────────┐
       │  formatting.rs   │─────────────────►│ Telegram │
       │  md → HTML       │                  │  API     │
       └──────────────────┘                  └──────────┘
```

### 5.6 CI/CD Pipeline

```
┌────────────┐  push/PR     ┌──────────────────────────────┐
│   GitHub   │─────────────►│  ci.yml                      │
│            │              │                              │
└────────────┘              │  ┌────────────────────┐      │
                            │  │  check-macos       │      │
                            │  │  1. npm install     │      │
                            │  │  2. npm run lint    │      │
                            │  │  3. npx tsc --noEmit│      │
                            │  │  4. cargo check     │      │
                            │  │  5. cargo clippy    │      │
                            │  └────────────────────┘      │
                            │                              │
                            │  ┌────────────────────┐      │
                            │  │  check-windows     │      │
                            │  │  (same steps)      │      │
                            │  └────────────────────┘      │
                            └──────────────────────────────┘

┌────────────┐  tag v*      ┌──────────────────────────────┐
│   GitHub   │─────────────►│  release.yml                 │
│            │              │                              │
└────────────┘              │  ┌────────────────────┐      │
                            │  │  build-macos       │      │
                            │  │  + Apple code sign │      │
                            │  │  + tauri-action    │      │
                            │  └────────────────────┘      │
                            │                              │
                            │  ┌────────────────────┐      │
                            │  │  build-windows     │      │
                            │  │  + tauri-action    │      │
                            │  └────────────────────┘      │
                            │                              │
                            │  → GitHub Release with       │
                            │    .dmg + .msi assets        │
                            └──────────────────────────────┘
```

---

## 6. Verification and Quality

### Test Summary

**No test files detected in the repository.** There are no `tests/` directories, no `*_test.rs` files, no `*.test.ts` or `*.spec.ts` files. Testing appears to have been done manually via live Telegram bot and desktop app interaction (per `CLAUDE.md`: "Tested with live Telegram bot").

### CI/CD Status

| Workflow | File | Trigger | Checks |
|---|---|---|---|
| CI | `.github/workflows/ci.yml` | Push to `main`, PRs to `main` | ESLint, TypeScript (`tsc --noEmit`), `cargo check --workspace`, `cargo clippy --workspace -- -D warnings` |
| Release | `.github/workflows/release.yml` | Tags matching `v*` | Full Tauri build for macOS (with Apple code signing) + Windows, creates GitHub Release |

**CI Platforms:** macOS (latest) + Windows (latest), Node.js 20, Rust stable

**CI Caching:** Cargo registry + git + target dirs keyed on `Cargo.lock` hash

### Known Issues and Tech Debt

| Issue | Location | Description |
|---|---|---|
| No automated tests | (entire repo) | Zero unit, integration, or e2e tests. All validation relies on CI type checks + manual testing. |
| Exposed bot token in CLAUDE.md | `CLAUDE.md` | A Telegram bot token appears in plaintext in the development status file. Should be removed/rotated. |
| `src-tauri/Cargo.lock` redundancy | `src-tauri/Cargo.lock` | Duplicate lockfile; workspace root `Cargo.lock` is authoritative. |
| `CouncilOfAIAgents.xcodeproj/` | root | Xcode build artifacts committed to repo. Not needed — Tauri handles native builds. |
| `noUnusedLocals: false` | `tsconfig.app.json` | Unused local variable checking disabled (strict mode partially relaxed). |
| No error boundary | `src/App.tsx` | No React error boundary — unhandled component errors will white-screen the app. |
| Usage aggregation via MAX | `api_calls.rs`, `chat.rs` | Usage tracking uses MAX instead of SUM. This is intentional for cumulative-reporting providers but may undercount for providers that report per-chunk deltas. `[UNCLEAR]` — not clear if all providers tested. |

---

## 7. Key Files Quick Reference

| File | Lines | Purpose |
|---|---|---|
| `src/stores/councilStore.ts` | 1,009 | Council discussion state machine — the core frontend logic |
| `crates/telegram-bot/src/council.rs` | 634 | Telegram bot council orchestration (Rust port of councilStore) |
| `src/components/chat/ChatView.tsx` | 534 | Council discussion UI with streaming, follow-ups, auto-save |
| `crates/telegram-bot/src/formatting.rs` | 496 | Markdown → Telegram HTML converter with typing indicators |
| `src/types/index.ts` | 355 | All TypeScript types, Provider enum, PROVIDERS registry |
| `crates/telegram-bot/src/handlers.rs` | 314 | 8 Telegram slash commands + message routing |
| `crates/telegram-bot/src/direct_chat.rs` | 260 | Telegram 1-on-1 chat with multi-turn history |
| `crates/council-core/src/chat.rs` | 155 | Provider-agnostic chat API (streaming + non-streaming) |
| `src-tauri/src/commands/api_calls.rs` | 143 | Tauri IPC bridge: streaming chat with event emission |
| `crates/council-core/src/providers/mod.rs` | 112 | AIProvider trait + SSE parsing infrastructure |
| `src/lib/tauri.ts` | 110 | Frontend Tauri IPC bindings (15 functions) |
| `src-tauri/src/lib.rs` | ~60 | Tauri app setup: plugins, state, handlers, bot auto-start |
| `crates/council-core/src/keychain/mod.rs` | ~80 | Thread-safe API key CRUD with platform abstraction |
| `src-tauri/tauri.conf.json` | ~50 | Tauri configuration: window, CSP, bundle, signing |
| `vite.config.ts` | ~30 | Vite build config with Tauri integration |
