"""IKLab CLI — orchestrator that delegates to skills."""

from __future__ import annotations

import argparse
import asyncio
import pathlib

from . import __version__, sandbox
from .agent import run_interactive, run_single_task
from .permissions import ToolApprover, ToolPermissionContext


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iklab",
        description="IKLab — interactive CLI agent powered by Granite 4.0-H-Tiny",
        epilog=(
            "Configuration (env vars):\n"
            "  IKLAB_MODEL_URL      model endpoint (default: http://localhost:12434/v1/chat/completions)\n"
            "  IKLAB_MODEL_NAME     model name (default: ai/granite-4.0-h-tiny)\n"
            "  IKLAB_MODEL_TIMEOUT  timeout in seconds (default: 120)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "task",
        nargs="*",
        help="task description for single-task mode (omit for interactive)",
    )
    parser.add_argument(
        "--simple-mode",
        action="store_true",
        default=False,
        help="restrict to context-only tools (Read, ListDirectory, Glob, Grep)",
    )
    parser.add_argument(
        "--deny-tool",
        action="append",
        default=[],
        metavar="NAME",
        help="block a specific tool by name (repeatable)",
    )
    parser.add_argument(
        "--deny-prefix",
        action="append",
        default=[],
        metavar="PREFIX",
        help="block tools whose name starts with PREFIX (repeatable)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=10000,
        metavar="N",
        help="maximum conversation turns before stopping (default: 8)",
    )
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        metavar="ID",
        help="restore a previous session by ID",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        default=False,
        help="show session history on exit",
    )
    parser.add_argument(
        "--yolo",
        action="store_true",
        default=False,
        help="skip permission prompts — auto-approve all tool calls",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    sandbox.set_workdir(pathlib.Path.cwd())

    # Build permission context from deny flags
    perm_ctx: ToolPermissionContext | None = None
    if args.deny_tool or args.deny_prefix:
        perm_ctx = ToolPermissionContext.from_iterables(
            deny_names=args.deny_tool,
            deny_prefixes=args.deny_prefix,
        )

    # Build approver
    approver = ToolApprover(always_approve_all=args.yolo)

    if args.task:
        task = " ".join(args.task)
        asyncio.run(
            run_single_task(
                task,
                simple_mode=args.simple_mode,
                permission_context=perm_ctx,
                max_turns=args.max_turns,
                approver=approver,
            )
        )
    else:
        asyncio.run(
            run_interactive(
                simple_mode=args.simple_mode,
                permission_context=perm_ctx,
                max_turns=args.max_turns,
                session_id=args.session,
                show_history=args.history,
                approver=approver,
            )
        )


if __name__ == "__main__":
    main()
