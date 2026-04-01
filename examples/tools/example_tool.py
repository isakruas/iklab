"""Example tool file for the examples folder.

This module exposes TOOL_METADATA so the registry can discover it when
`./examples` is configured as a tool path.
"""

TOOL_METADATA = [
    {
        "name": "ExampleList",
        "category": "context",
        "description": "Example tool that lists a fixed set of items for testing.",
        "source_module": "examples.tools.example_tool",
    }
]
