"""Agent assembler — wires together resolved components into a runnable agent or script."""

from __future__ import annotations

import importlib
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .capability_resolver import ResolvedComponents
from .config_builder import ConfigBuilder
from .requirements import UserRequirements


@dataclass
class CompiledAgent:
    """Result of a compilation run."""

    provider: str
    agent_class_name: str
    config_class_name: str
    config_kwargs: dict[str, Any]
    capabilities: list[str]
    script: str | None = None  # Generated Python script text
    agent_instance: Any = None  # Live instance when output_format="instance"
    description: str | None = None  # Human-readable summary of why components were chosen
    package_dir: str | None = None  # Path to self-contained package directory


class AgentAssembler:
    """Orchestrates config building + (optionally) instantiation / script generation."""

    def __init__(self, config_builder: ConfigBuilder | None = None) -> None:
        self._config_builder = config_builder or ConfigBuilder()

    def assemble(
        self,
        components: ResolvedComponents,
        req: UserRequirements,
    ) -> CompiledAgent:
        """Build config, optionally instantiate, and/or generate a script."""
        cfg_kwargs = self._config_builder.build(components, req)

        compiled = CompiledAgent(
            provider=components.provider,
            agent_class_name=components.agent_class_name,
            config_class_name=components.config_class_name,
            config_kwargs=cfg_kwargs,
            capabilities=components.capabilities,
        )

        if req.output_format == "instance":
            compiled.agent_instance = self._instantiate(components, cfg_kwargs)
        elif req.output_format == "script":
            compiled.script = self._generate_script(components, cfg_kwargs, req)
        elif req.output_format == "package":
            compiled.script = self._generate_script(components, cfg_kwargs, req)
            from .agent_packager import AgentPackager
            packager = AgentPackager()
            pkg_dir = Path(req.package_dir) if req.package_dir else Path("compiled_agents")
            compiled.package_dir = str(
                packager.package(compiled, components, req, pkg_dir, req.package_name)
            )
        # "config_only" → just the config; no script or instance

        return compiled

    # ------------------------------------------------------------------
    # Instantiation
    # ------------------------------------------------------------------

    @staticmethod
    def _instantiate(
        components: ResolvedComponents,
        cfg_kwargs: dict[str, Any],
    ) -> Any:
        """Dynamically import and instantiate the agent."""
        config_mod = importlib.import_module(components.config_module)
        agent_mod = importlib.import_module(components.agent_module)

        config_cls = getattr(config_mod, components.config_class_name)
        agent_cls = getattr(agent_mod, components.agent_class_name)

        config = config_cls(**cfg_kwargs)
        return agent_cls(config)

    # ------------------------------------------------------------------
    # Script generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_script(
        components: ResolvedComponents,
        cfg_kwargs: dict[str, Any],
        req: UserRequirements,
    ) -> str:
        """Generate a standalone Python script that creates and uses the agent."""
        lines: list[str] = []

        # Imports
        lines.append('"""Auto-generated agent script — created by universal-agents compiler."""\n')
        lines.append(f"from {components.config_module} import {components.config_class_name}")
        lines.append(f"from {components.agent_module} import {components.agent_class_name}")

        # Env helpers for API keys
        if components.transport == "api":
            lines.append("import os")

        # Monitoring imports
        if req.needs_monitoring:
            lines.append(
                "from universal_agents.monitor import AgentRegistry, MonitoredAgent, Reporter"
            )

        lines.append("")
        lines.append("")

        # Config construction
        lines.append("# --- Configuration ---")
        lines.append(f"config = {components.config_class_name}(")
        for k, v in cfg_kwargs.items():
            lines.append(f"    {k}={_repr_value(k, v, components)},")
        lines.append(")")
        lines.append("")

        # Agent construction (with optional monitoring wrapper)
        lines.append("# --- Agent ---")
        if req.needs_monitoring:
            lines.append(f"_base_agent = {components.agent_class_name}(config)")
            lines.append("registry = AgentRegistry()")
            lines.append("registry.register(_base_agent)")
            lines.append("agent = MonitoredAgent(_base_agent, registry.event_bus)")
            lines.append("reporter = Reporter(registry)")
        else:
            lines.append(f"agent = {components.agent_class_name}(config)")
        lines.append("")

        # Usage example
        if req.use_case == "chat":
            lines.append(_chat_example())
        elif req.use_case == "data":
            lines.append(_data_example(req))
        elif req.use_case == "translation":
            lines.append(_translation_example())
        elif req.use_case == "research":
            lines.append(_chat_example())  # research uses chat interface
        elif req.use_case == "code":
            lines.append(_data_example(req))
        else:
            lines.append(_chat_example())

        return "\n".join(lines) + "\n"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _repr_value(key: str, value: Any, components: ResolvedComponents) -> str:
    """Pretty-print a config value for script output."""
    if key == "api_key":
        env_var = "OPENAI_API_KEY" if components.provider == "openai" else "OPENROUTER_API_KEY"
        return f'os.environ["{env_var}"]'
    if key == "storage_state":
        return repr(value)
    return repr(value)


def _chat_example() -> str:
    return textwrap.dedent("""\
        # --- Usage ---
        import asyncio

        async def main():
            async with agent:
                response = await agent.chat("Hello, how can you help me?")
                print(response)

        asyncio.run(main())""")


def _data_example(req: UserRequirements) -> str:
    prompt = "Analyze the given data and return structured results."
    if req.use_case == "code":
        prompt = "Review the code and identify potential improvements."
    return textwrap.dedent(f"""\
        # --- Usage ---
        import asyncio

        async def main():
            async with agent:
                result = await agent.run(
                    prompt="{prompt}",
                    input_json={{"example_key": "example_value"}},
                )
                print(result)

        asyncio.run(main())""")


def _translation_example() -> str:
    return textwrap.dedent("""\
        # --- Usage ---
        import asyncio

        async def main():
            async with agent:
                result = await agent.translate("path/to/source_file.txt")
                print(result)

        asyncio.run(main())""")
