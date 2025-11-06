"""`agent-make` CLI entry point.

Invoked either as the installed console script `agent-make` (defined in
pyproject.toml) or via `python -m universal_agents.compiler [OPTIONS]`.

`agent-make` is to LLM agents what `make`/`cmake` are to C/C++ binaries: a
declarative pipeline that takes a spec (interactive interview, preset name,
or JSON file) and emits a ready-to-run agent (live instance, standalone
script, or deployable package).
"""

import argparse
import sys

from .compiler import AgentCompiler
from .question_flow import PRESETS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-make",
        description=(
            "agent-make: compile LLM agents from a spec. "
            "Like cmake/make for binaries, but for agents."
        ),
        epilog=(
            "Examples:\n"
            "  agent-make --interactive\n"
            "  agent-make --preset free-chat\n"
            "  agent-make --spec source_spec.json --output agent.py\n"
            "  agent-make --list-presets"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--interactive", "-i",
        action="store_true",
        default=True,
        help="Run interactive interview (default).",
    )
    group.add_argument(
        "--preset", "-p",
        choices=sorted(PRESETS),
        help="Use a named preset instead of interview.",
    )
    group.add_argument(
        "--spec", "-s",
        metavar="FILE",
        help="Path to a JSON spec file.",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write generated script to FILE instead of stdout.",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available presets and exit.",
    )

    args = parser.parse_args(argv)

    if args.list_presets:
        print("[agent-make] Available presets:")
        for name, spec in sorted(PRESETS.items()):
            use_case = spec.get("use_case", "chat")
            provider = spec.get("provider_preference", "auto")
            print(f"  {name:20s}  use_case={use_case}, provider={provider}")
        print()
        print("Use one with:  agent-make --preset <name>")
        return 0

    compiler = AgentCompiler()

    if args.spec:
        compiled = compiler.compile_from_json(args.spec)
    elif args.preset:
        compiled = compiler.compile_interactive(preset=args.preset)
    else:
        compiled = compiler.compile_interactive()

    # Output
    if compiled.script:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(compiled.script)
            print(f"[agent-make] Script written to {args.output}")
        else:
            print(compiled.script)
    else:
        # config_only mode — print summary
        print("[agent-make] Compilation summary")
        print(f"  Provider:     {compiled.provider}")
        print(f"  Agent:        {compiled.agent_class_name}")
        print(f"  Config:       {compiled.config_class_name}")
        print(f"  Capabilities: {', '.join(compiled.capabilities)}")
        print(f"  Config kwargs: {compiled.config_kwargs}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
