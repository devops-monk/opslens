"""The pinned versions live in four places (versions.py, install.sh, Dockerfile, CI). They must agree."""

import re
from pathlib import Path

import pytest

from opslens import __version__, versions

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def text(name):
    return (ROOT / name).read_text()


def test_flowpipe_and_steampipe_versions_agree_everywhere():
    sh, df = text("install.sh"), text("Dockerfile")
    assert re.search(rf'FLOWPIPE_VERSION="{re.escape(versions.FLOWPIPE_VERSION)}"', sh)
    assert re.search(rf'STEAMPIPE_VERSION="{re.escape(versions.STEAMPIPE_VERSION)}"', sh)
    assert f"ARG FLOWPIPE_VERSION={versions.FLOWPIPE_VERSION}" in df
    assert f"ARG STEAMPIPE_VERSION={versions.STEAMPIPE_VERSION}" in df


def test_plugin_pins_agree():
    sh, df = text("install.sh"), text("Dockerfile")
    for meta in versions.PLUGINS.values():
        assert meta["install"] in sh, f"{meta['install']} missing from install.sh"
        assert meta["install"] in df, f"{meta['install']} missing from Dockerfile"


def test_package_version_matches_pyproject_and_changelog():
    assert re.search(rf'^version = "{re.escape(__version__)}"', text("pyproject.toml"), re.MULTILINE)
    assert f"## {__version__}" in text("CHANGELOG.md")


def test_license_metadata_is_apache():
    assert "Apache License" in text("LICENSE")
    assert 'license = "Apache-2.0"' in text("pyproject.toml")
    assert 'org.opencontainers.image.licenses="Apache-2.0"' in text("Dockerfile")


def test_notice_names_the_agpl_process_boundary():
    n = text("NOTICE")
    assert "GNU AGPL-3.0" in n and "separate processes" in n


def test_every_shipped_data_file_is_in_the_wheel_tree():
    data = ROOT / "src" / "opslens" / "catalog" / "data"
    names = {p.name for p in data.iterdir()}
    assert "pipelines.json.gz" in names and {f"tables_{p}.json.gz" for p in versions.PLUGINS} <= names


def test_installer_defaults_to_this_release_and_is_served_by_the_site():
    sh = text("install.sh")
    assert f'REF="${{OPSLENS_REF:-v{__version__}}}"' in sh, "install.sh must default to the current release tag"
    assert "https://opslens.devops-monk.com/install.sh" in sh
