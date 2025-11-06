# Compiled Agent Development Guideline

## Overview

A **compiled agent** is a self-contained, distributable Python package generated
by the universal-agents compiler pipeline. It bundles everything needed to run a
specific task: an executable script, configuration, reference data, and directory
structure — all wired to the core `universal_agents` library.

**Compiled agents are never created manually.** They are always produced by a
compile script that invokes the compiler infrastructure.

---

## Development Process

### Step 1 — Define the Task

Clearly describe:
- **What** the agent does (e.g., "translate a kendo book PDF page-by-page")
- **Provider** (Gemini, Claude, etc.) and transport (browser, API, CLI)
- **Input format** (PDF, SRT, plain text, etc.)
- **Output format** (Markdown, SRT, JSON, etc.)
- **Conversation strategy** (turns per conversation, splitting rules, etc.)

### Step 2 — Identify Required Modules

Check which core modules already exist and which need to be created.

**Existing core modules** (in `src/universal_agents/core/`):
- `srt_utils.py` — SRT parsing, chunking, normalization
- `kendo_context.py` — Kendo SRT prompt builder + dictionary loader
- `json_utils.py` — JSON extraction from LLM responses
- `prompt_builder.py` — System prompt builder
- `translation_prompts.py` — Translation prompt templates

**If the task needs a new module**, implement it in `src/universal_agents/core/`.
Examples:
- `pdf_utils.py` — PDF splitting for page-by-page translation
- `book_prompts.py` — Book translation prompt builder

Each new module should:
- Live in `src/universal_agents/core/`
- Be importable as `from universal_agents.core.{module} import ...`
- Have focused responsibilities (one module per concern)
- Work independently of any compiled agent

### Step 3 — Write the Compile Script

Create a script at `scripts/compile_{task_name}.py` that:

1. **Defines `UserRequirements`** — the task's needs
2. **Resolves components** via `CapabilityResolver`
3. **Overrides config** with task-specific settings
4. **Creates a `CompiledAgent`** artifact
5. **Packages it** via `AgentPackager` into `compiled_agents/{package_name}/`
6. **Copies task-specific assets** (dictionaries, prompts, etc.)
7. **Writes the custom `agent.py`** (the executable run script)
8. **Updates `config.json`** with task-specific fields
9. **Creates required directories** (input, output, progress, storage)

**The compile script is the single source of truth** for producing the compiled
agent. Running it regenerates the entire package from scratch.

#### Template Structure

```python
#!/usr/bin/env python3
"""Compile a self-contained {Provider} {Task} agent package."""

import argparse
import json
import shutil
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from universal_agents.compiler import (
    AgentPackager, CapabilityResolver, CompiledAgent, UserRequirements,
)


def compile_agent(output_dir: Path) -> Path:
    # 1. Requirements
    req = UserRequirements(
        use_case="translation",
        needs_file_upload=True,
        provider_preference="gemini",
        output_format="package",
        package_dir=str(output_dir),
        package_name="my_agent",
    )
    req.apply_use_case_defaults()

    # 2. Resolve components
    resolver = CapabilityResolver()
    components = resolver.resolve(req)

    # 3. Config overrides
    config_kwargs = { ... }

    # 4. Compiled agent
    compiled = CompiledAgent(
        provider="gemini",
        agent_class_name=components.agent_class_name,
        config_class_name=components.config_class_name,
        config_kwargs=config_kwargs,
        capabilities=[...],
        script="# replaced below",
    )

    # 5. Package
    packager = AgentPackager(project_root=PROJECT_ROOT)
    pkg_dir = packager.package(compiled, components, req, output_dir, "my_agent")

    # 6. Copy assets
    shutil.copy2(src, pkg_dir / "asset.md")

    # 7. Write custom agent.py
    _write_run_script(pkg_dir)

    # 8. Update config.json
    config_path = pkg_dir / "config.json"
    config = json.loads(config_path.read_text())
    config["task"] = { ... }
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    # 9. Directories
    (pkg_dir / "input").mkdir(exist_ok=True)
    (pkg_dir / "output").mkdir(exist_ok=True)

    return pkg_dir


def _write_run_script(pkg_dir: Path) -> None:
    script = textwrap.dedent('''\\
        #!/usr/bin/env python3
        ...
    ''')
    agent_path = pkg_dir / "agent.py"
    agent_path.write_text(script, encoding="utf-8")
    agent_path.chmod(0o755)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", "-o",
                        default=str(PROJECT_ROOT / "compiled_agents"))
    args = parser.parse_args()
    compile_agent(Path(args.output_dir))

if __name__ == "__main__":
    main()
```

### Step 4 — Run the Compile Script

```bash
python scripts/compile_{task_name}.py
```

This generates the full package under `compiled_agents/{package_name}/`.

### Step 5 — Test the Compiled Agent

```bash
# Dry-run import check
python -c "import py_compile; py_compile.compile('compiled_agents/{pkg}/agent.py', doraise=True)"

# Test login flow
python compiled_agents/{pkg}/agent.py --login

# Test with real input
python compiled_agents/{pkg}/agent.py INPUT_FILE --visible

# Iterate: fix issues in compile script, re-run, re-test
```

### Step 6 — Commit

Commit both:
- New core modules in `src/universal_agents/core/`
- The compile script in `scripts/`
- The compiled package in `compiled_agents/`

---

## Package Structure Convention

Every compiled agent package follows this layout:

```
compiled_agents/{package_name}/
├── agent.py                # Executable main script
├── config.json             # User-editable configuration
├── source_spec.json        # Recompilation metadata
├── requirements.txt        # Python dependencies
├── README.md               # Usage instructions
├── storage/                # Browser cookies / auth state
│   └── .gitkeep
├── {input_dir}/            # Task-specific input directory
│   └── .gitkeep
├── {output_dir}/           # Task-specific output directory
│   └── .gitkeep
├── progress/               # Checkpoint files for resume
│   └── .gitkeep
└── {assets}                # Task-specific files (dictionaries, prompts)
```

---

## Key Compiler Classes

| Class                | Module                         | Purpose                                   |
| -------------------- | ------------------------------ | ----------------------------------------- |
| `UserRequirements`   | `compiler.requirements`        | Structured interview output               |
| `CapabilityResolver` | `compiler.capability_resolver` | Maps requirements → components            |
| `ResolvedComponents` | `compiler.capability_resolver` | Provider, transport, agent/config classes |
| `ConfigBuilder`      | `compiler.config_builder`      | Builds config kwargs from components      |
| `CompiledAgent`      | `compiler.agent_assembler`     | Result artifact with config + script      |
| `AgentPackager`      | `compiler.agent_packager`      | Creates self-contained package directory  |
| `AgentCompiler`      | `compiler.compiler`            | Top-level orchestrator (interactive mode) |

---

## Existing Compiled Agents (Reference)

| Agent                        | Compile Script                               | Package                                         |
| ---------------------------- | -------------------------------------------- | ----------------------------------------------- |
| Gemini Kendo SRT Translator  | `scripts/compile_kendo_translator.py`        | `compiled_agents/gemini_kendo_srt_translator/`  |
| Claude Kendo SRT Translator  | `scripts/compile_kendo_translator_claude.py` | `compiled_agents/claude_kendo_srt_translator/`  |
| Gemini Kendo Book Translator | `scripts/compile_kendo_book_translator.py`   | `compiled_agents/gemini_kendo_book_translator/` |

---

## Anti-patterns

- **Never create compiled agents by hand.** Always write a compile script.
- **Never edit `agent.py` inside the package.** Edit the `_write_run_script()`
  function in the compile script and re-run.
- **Never copy-paste code between agents.** Extract shared logic into
  `src/universal_agents/core/` modules.
- **Never hardcode absolute paths in `agent.py`.** Use `SCRIPT_DIR` for
  package-relative paths. Config values for everything else.
