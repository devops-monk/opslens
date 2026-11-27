import pytest

from opslens.config import ConfigError, load_config, param_rows

pytestmark = pytest.mark.unit


def test_defaults():
    cfg, src = load_config()
    assert cfg.steampipe.port == 9193 and cfg.llm.provider == "none" and src == {}


def test_layers_file_env_set_in_order(tmp_path, monkeypatch):
    f = tmp_path / "opslens.yaml"
    f.write_text("steampipe:\n  port: 1111\n  max_rows: 5\n")
    monkeypatch.setenv("OPSLENS__STEAMPIPE__PORT", "2222")
    cfg, src = load_config(sets=["steampipe.statement_timeout_s=7", "steampipe.max_rows=9"])
    assert cfg.steampipe.port == 2222 and cfg.steampipe.max_rows == 9 and cfg.steampipe.statement_timeout_s == 7
    assert src["steampipe.port"].startswith("env") and src["steampipe.max_rows"] == "--set"


def test_lists_parse_as_yaml():
    cfg, _ = load_config(sets=["catalog.plugins=[aws, jira]"])
    assert cfg.catalog.plugins == ["aws", "jira"]


@pytest.mark.parametrize("sets", [["steampipe.nope=1"], ["steampipe.port=abc"], ["steampipe.port=0"],
                                  ["llm.provider=skynet"], ["bogus=1"], ["noequals"]])
def test_bad_values_fail_fast_and_name_the_key(sets):
    with pytest.raises(ConfigError):
        load_config(sets=sets)


def test_missing_explicit_file():
    with pytest.raises(ConfigError, match="not found"):
        load_config(path="/nope/opslens.yaml")


def test_password_is_masked_in_params():
    cfg, src = load_config(sets=["steampipe.password=hunter2"])
    rows = {r["key"]: r for r in param_rows(cfg, src)}
    assert rows["steampipe.password"]["value"] == "***"
