import os
import json
from pathlib import Path

import pytest

from iklab.tool_registry import build_tool_registry


def write_tool_file(dirpath: Path, name: str = "discovered_tool"):
    p = dirpath / f"{name}.py"
    p.write_text(
        "TOOL_METADATA = [\n"
        "    {\n"
        "        'name': 'TempTool',\n"
        "        'category': 'context',\n"
        "        'description': 'A temporary discovered tool',\n"
        "        'source_module': 'temp.discovered_tool',\n"
        "    }\n"
        "]\n"
    )
    return p


def write_settings_file(dirpath: Path, tool_paths):
    cfg_dir = dirpath / ".iklab"
    cfg_dir.mkdir(exist_ok=True)
    cfg = cfg_dir / "settings.json"
    cfg.write_text(json.dumps({"tool_paths": tool_paths}))
    return cfg


def test_discovery_from_settings(tmp_path, monkeypatch):
    # create a temporary tool directory
    tool_dir = tmp_path / "mytools"
    tool_dir.mkdir()
    write_tool_file(tool_dir, name="discovered_tool")

    # create a project dir where .iklab/settings.json points to that dir
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    # write settings inside project_dir/.iklab/settings.json
    cfg_dir = project_dir / ".iklab"
    cfg_dir.mkdir()
    cfg = cfg_dir / "settings.json"
    cfg.write_text(json.dumps({"tool_paths": [str(tool_dir)]}))

    # set IKLAB_SETTINGS to our settings file and ensure cwd is project_dir
    monkeypatch.setenv("IKLAB_SETTINGS", str(cfg))
    monkeypatch.chdir(project_dir)

    # Clear cached config so build_tool_registry reads our IKLAB_SETTINGS
    import iklab.config as ikconfig
    ikconfig._config = None

    # Build registry and assert the tool name is present
    reg = build_tool_registry()
    names = reg.names()
    assert "TempTool" in names
