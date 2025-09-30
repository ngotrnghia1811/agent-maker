"""Agent packager — creates self-contained, distributable agent packages.

A packaged agent is a self-contained directory that includes:
- agent.py: The executable main script
- config.json: Modifiable configuration (edit without touching code)
- storage/: Auth state, progress files, runtime data
- requirements.txt: Python dependencies for the agent
- README.md: Usage instructions
- source_spec.json: The original compilation spec (for recompilation)
"""

from __future__ import annotations

import json
import os
import shutil
import textwrap
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent_assembler import CompiledAgent
from .capability_resolver import ResolvedComponents
from .requirements import UserRequirements


class AgentPackager:
    """Creates self-contained agent packages from compiled agents."""

    def __init__(self, project_root: Path | None = None):
        self._project_root = project_root or Path(__file__).resolve().parent.parent.parent.parent

    def package(
        self,
        compiled: CompiledAgent,
        components: ResolvedComponents,
        req: UserRequirements,
        output_dir: Path,
        package_name: str | None = None,
    ) -> Path:
        """Create a self-contained agent package directory.

        Args:
            compiled: The compiled agent from AgentAssembler.
            components: Resolved component selections.
            req: Original user requirements.
            output_dir: Parent directory for the package.
            package_name: Name for the package directory (auto-generated if None).

        Returns:
            Path to the created package directory.
        """
        name = package_name or self._generate_name(compiled)
        pkg_dir = output_dir / name
        pkg_dir.mkdir(parents=True, exist_ok=True)

        # 1. Config file (user-modifiable)
        self._write_config(pkg_dir, compiled, components)

        # 2. Agent script (executable)
        self._write_agent_script(pkg_dir, compiled, components, req)

        # 3. Storage directory with auth state
        self._copy_storage(pkg_dir, compiled)

        # 4. Requirements file
        self._write_requirements(pkg_dir, components)

        # 5. README
        self._write_readme(pkg_dir, compiled, components, req)

        # 6. Source spec for recompilation
        self._write_source_spec(pkg_dir, compiled, components, req)

        return pkg_dir

    @staticmethod
    def _generate_name(compiled: CompiledAgent) -> str:
        """Generate a package name from the compiled agent."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{compiled.provider}_{compiled.agent_class_name.lower()}_{timestamp}"

    @staticmethod
    def _write_config(pkg_dir: Path, compiled: CompiledAgent, components: ResolvedComponents) -> None:
        """Write config.json — the user-modifiable configuration."""
        config_data = {
            "provider": compiled.provider,
            "agent_class": compiled.agent_class_name,
            "config_class": compiled.config_class_name,
            "config_kwargs": compiled.config_kwargs,
            "capabilities": compiled.capabilities,
            "_metadata": {
                "created": datetime.now().isoformat(),
                "agent_module": components.agent_module,
                "config_module": components.config_module,
                "transport": components.transport,
            },
        }

        (pkg_dir / "config.json").write_text(
            json.dumps(config_data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )

    def _write_agent_script(
        self,
        pkg_dir: Path,
        compiled: CompiledAgent,
        components: ResolvedComponents,
        req: UserRequirements,
    ) -> None:
        """Write the executable agent.py script."""
        script = self._build_standalone_script(compiled, components, req)
        agent_path = pkg_dir / "agent.py"
        agent_path.write_text(script, encoding="utf-8")
        # Make executable
        agent_path.chmod(0o755)

    def _copy_storage(self, pkg_dir: Path, compiled: CompiledAgent) -> None:
        """Copy auth state and storage files into the package."""
        storage_dir = pkg_dir / "storage"
        storage_dir.mkdir(exist_ok=True)

        # Copy storage state file if referenced in config
        state_path = compiled.config_kwargs.get("storage_state", "")
        if state_path and Path(state_path).exists():
            dest = storage_dir / Path(state_path).name
            shutil.copy2(state_path, dest)

    @staticmethod
    def _write_requirements(pkg_dir: Path, components: ResolvedComponents) -> None:
        """Write requirements.txt based on the agent's dependencies."""
        deps = [
            "playwright>=1.40",
            "httpx>=0.25",
            "pyyaml>=6.0",
            "rich>=13.0",
        ]

        if components.transport == "browser":
            deps.append("playwright-stealth>=1.0")
            if components.provider == "gemini":
                deps.append("camoufox>=0.4")

        (pkg_dir / "requirements.txt").write_text("\n".join(deps) + "\n", encoding="utf-8")

    @staticmethod
    def _write_readme(
        pkg_dir: Path,
        compiled: CompiledAgent,
        components: ResolvedComponents,
        req: UserRequirements,
    ) -> None:
        """Write README.md with usage instructions."""
        caps = ", ".join(compiled.capabilities) if compiled.capabilities else "none"
        readme = textwrap.dedent(f"""\
            # {compiled.provider.title()} {compiled.agent_class_name}

            Self-contained agent package created by universal-agents compiler.

            ## Quick Start

            ```bash
            # Install dependencies
            pip install -r requirements.txt

            # Run the agent
            python agent.py
            ```

            ## Configuration

            Edit `config.json` to modify:
            - **config_kwargs**: Agent configuration (timeouts, model, URLs, etc.)
            - **capabilities**: What the agent can do

            ## Files

            | File | Purpose |
            |---|---|
            | `agent.py` | Main executable script |
            | `config.json` | Configuration (edit this!) |
            | `storage/` | Auth state and runtime data |
            | `requirements.txt` | Python dependencies |
            | `source_spec.json` | Original spec (for recompilation) |

            ## Details

            - **Provider:** {compiled.provider}
            - **Transport:** {components.transport}
            - **Agent Class:** {compiled.agent_class_name}
            - **Capabilities:** {caps}

            ## Recompilation

            To recompile with changes:

            ```bash
            python -m universal_agents.compiler --from-json source_spec.json
            ```
        """)
        (pkg_dir / "README.md").write_text(readme, encoding="utf-8")

    @staticmethod
    def _write_source_spec(
        pkg_dir: Path,
        compiled: CompiledAgent,
        components: ResolvedComponents,
        req: UserRequirements,
    ) -> None:
        """Write the compilation spec for recompilation."""
        spec = {
            "use_case": req.use_case,
            "needs_file_upload": req.needs_file_upload,
            "needs_thinking": req.needs_thinking,
            "needs_json_output": req.needs_json_output,
            "needs_streaming": req.needs_streaming,
            "cost_sensitivity": req.cost_sensitivity,
            "latency_sensitivity": req.latency_sensitivity,
            "provider_preference": req.provider_preference,
            "model_preference": req.model_preference,
            "needs_fallback": req.needs_fallback,
            "needs_monitoring": req.needs_monitoring,
            "needs_translation": req.needs_translation,
            "custom_system_prompt": req.custom_system_prompt,
            "output_format": req.output_format,
            "_compiled": {
                "provider": compiled.provider,
                "agent_class": compiled.agent_class_name,
                "config_class": compiled.config_class_name,
                "config_kwargs": compiled.config_kwargs,
                "transport": components.transport,
            },
        }
        (pkg_dir / "source_spec.json").write_text(
            json.dumps(spec, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )

    def _build_standalone_script(
        self,
        compiled: CompiledAgent,
        components: ResolvedComponents,
        req: UserRequirements,
    ) -> str:
        """Build a fully standalone agent.py that reads config.json at runtime."""
        return textwrap.dedent(f'''\
            #!/usr/bin/env python3
            """Self-contained {compiled.provider} agent — reads config.json for all settings.

            Generated by universal-agents compiler.
            Edit config.json to change behavior without modifying this script.
            """

            import asyncio
            import json
            import sys
            from pathlib import Path

            # Allow running from the package directory
            SCRIPT_DIR = Path(__file__).resolve().parent

            # Load configuration
            config_path = SCRIPT_DIR / "config.json"
            if not config_path.exists():
                print("Error: config.json not found. Expected at:", config_path)
                sys.exit(1)

            with open(config_path, encoding="utf-8") as f:
                _config_data = json.load(f)

            # Resolve storage state path relative to package
            _kwargs = dict(_config_data["config_kwargs"])
            if "storage_state" in _kwargs:
                state_file = SCRIPT_DIR / "storage" / Path(_kwargs["storage_state"]).name
                if state_file.exists():
                    _kwargs["storage_state"] = str(state_file)

            # Import and configure
            from {components.config_module} import {compiled.config_class_name}
            from {components.agent_module} import {compiled.agent_class_name}

            config = {compiled.config_class_name}(**_kwargs)
            agent = {compiled.agent_class_name}(config)


            {self._get_usage_block(req)}
        ''')

    @staticmethod
    def _get_usage_block(req: UserRequirements) -> str:
        """Get the usage code block appropriate for the use case."""
        if req.use_case == "chat":
            return textwrap.dedent("""\
                async def main():
                    print("Agent ready. Type 'quit' to exit.")
                    async with agent:
                        while True:
                            user_input = input("\\nYou: ").strip()
                            if user_input.lower() in ("quit", "exit", "q"):
                                break
                            response = await agent.chat(user_input)
                            print(f"\\nAgent: {response}")

                if __name__ == "__main__":
                    asyncio.run(main())""")
        elif req.use_case == "translation":
            return textwrap.dedent("""\
                async def main():
                    print("Translation agent ready.")
                    print("Provide text to translate (Ctrl+D to finish):")
                    import sys
                    text = sys.stdin.read()
                    async with agent:
                        from universal_agents.providers.gemini.translator import TranslationChunk
                        chunk = TranslationChunk(chunk_id="input", chunk_index=0, source_text=text)
                        result = await agent.translate_text(chunk)
                        if result.success:
                            print(result.translated_text)
                        else:
                            print(f"Error: {result.error}", file=sys.stderr)

                if __name__ == "__main__":
                    asyncio.run(main())""")
        elif req.use_case == "data":
            return textwrap.dedent("""\
                async def main():
                    print("Data agent ready. Enter prompts (type 'quit' to exit):")
                    async with agent:
                        while True:
                            prompt = input("\\nPrompt: ").strip()
                            if prompt.lower() in ("quit", "exit", "q"):
                                break
                            response = await agent.chat(prompt)
                            print(f"\\nResponse: {response}")

                if __name__ == "__main__":
                    asyncio.run(main())""")
        else:
            return textwrap.dedent("""\
                async def main():
                    async with agent:
                        response = await agent.chat("Hello!")
                        print(response)

                if __name__ == "__main__":
                    asyncio.run(main())""")
