"""AgentCompiler — top-level orchestrator that ties all compiler components together."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, TextIO

from .agent_assembler import AgentAssembler, CompiledAgent
from .auth_detector import AuthDetector
from .capability_resolver import CapabilityResolver
from .compiler_llm import CompilerLLM
from .config_builder import ConfigBuilder
from .question_flow import QuestionFlow
from .requirements import UserRequirements

logger = logging.getLogger(__name__)


class AgentCompiler:
    """Orchestrates the full compile pipeline: interview → resolve → build → assemble."""

    def __init__(
        self,
        auth_detector: AuthDetector | None = None,
        input_fn: Callable[[str], str] | None = None,
        output: TextIO | None = None,
    ) -> None:
        self._auth_detector = auth_detector or AuthDetector()
        self._question_flow = QuestionFlow(
            auth_detector=self._auth_detector,
            input_fn=input_fn,
            output=output,
        )
        self._resolver = CapabilityResolver()
        self._config_builder = ConfigBuilder()
        self._assembler = AgentAssembler(self._config_builder)

    def compile_interactive(self, preset: str | None = None) -> CompiledAgent:
        """Run the interactive interview and compile an agent.

        If *preset* is given, skip the interview and use the preset values.
        """
        req = self._question_flow.interview(preset=preset)
        return self._compile(req)

    def compile_from_spec(self, spec: dict[str, Any]) -> CompiledAgent:
        """Compile from a requirements dict (non-interactive mode)."""
        req = UserRequirements(**{
            k: v for k, v in spec.items()
            if hasattr(UserRequirements, k)
        })
        req.apply_use_case_defaults()
        # Detect auth if not provided
        if not req.auth_available:
            auth_status = self._auth_detector.detect()
            req.auth_available = auth_status.available
        return self._compile(req)

    def compile_from_json(self, path: str) -> CompiledAgent:
        """Compile from a JSON spec file (including recompilation from source_spec.json)."""
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
        # Support source_spec.json format: strip _compiled metadata
        spec = {k: v for k, v in spec.items() if not k.startswith("_")}
        return self.compile_from_spec(spec)

    def _compile(self, req: UserRequirements) -> CompiledAgent:
        """Internal: resolve → build → assemble → describe."""
        components = self._resolver.resolve(req)
        compiled = self._assembler.assemble(components, req)

        # Generate description via Compiler-LLM if available
        compiler_llm = self._question_flow._compiler_llm
        if compiler_llm:
            try:
                compiled.description = asyncio.run(
                    compiler_llm.explain_compilation(
                        provider=compiled.provider,
                        agent_class=compiled.agent_class_name,
                        capabilities=compiled.capabilities,
                    )
                )
            except Exception:
                logger.debug("explain_compilation failed", exc_info=True)
            finally:
                try:
                    asyncio.run(compiler_llm.close())
                except Exception:
                    pass

        return compiled
