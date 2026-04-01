import json

from iklab.config import get_config
from iklab.prompt_builder import build_system_prompt
from iklab.skill_registry import build_skill_registry


def test_skill_discovery_and_prompt(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    skills_dir = project / ".iklab" / "skills"
    skills_dir.mkdir(parents=True)
    skill_file = skills_dir / "test_skill.md"
    skill_file.write_text(
        "---\n"
        "name: TestSkill\n"
        "triggers: [test]\n"
        "recommended_tools: [List]\n"
        "description: 'A test skill'\n"
        "---\n"
        "\n"
        "This is the body of the test skill.\n"
    )

    # write settings pointing to project .iklab/skills
    settings = project / ".iklab" / "settings.json"
    settings.write_text(json.dumps({"skills_paths": [str(skills_dir)]}))

    monkeypatch.setenv("IKLAB_SETTINGS", str(settings))
    monkeypatch.chdir(project)

    # Clear cached config
    import iklab.config as ikconfig

    ikconfig._config = None

    reg = build_skill_registry()
    names = reg.names()
    assert "TestSkill" in names

    # Build a minimal prompt and assert skill snippet included
    from iklab.tool_pool import assemble_tool_pool
    from iklab.tool_registry import build_tool_registry

    cfg = get_config()
    pool = assemble_tool_pool(build_tool_registry())
    prompt = build_system_prompt(cfg, pool)
    assert "TestSkill" in prompt or "A test skill" in prompt
