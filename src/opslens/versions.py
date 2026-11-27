"""Pinned engine versions. install.sh and the Dockerfile carry the same values; tests assert they agree."""

FLOWPIPE_VERSION = "1.2.4"
STEAMPIPE_VERSION = "2.5.0"

# Steampipe plugins opslens ships catalogs for: name -> (install spec, hub/source, maintained by)
PLUGINS: dict[str, dict[str, str]] = {
    "aws":          {"install": "aws@1.35.0",          "maintainer": "turbot"},
    "jira":         {"install": "jira@2.0.5",          "maintainer": "turbot"},
    "microsoft365": {"install": "microsoft365@1.3.0",  "maintainer": "turbot"},
    "gitlab":       {"install": "theapsgroup/gitlab",   "maintainer": "community"},
    "opsgenie":     {"install": "jplanckeel/opsgenie",  "maintainer": "community"},
}
