.PHONY: test test-unit test-integration test-system lint catalog docker-build docker-smoke wheel

PY ?= .venv/bin/python
MODS ?= ..                  # directory holding the flowpipe-mod-* checkouts
PLUGINS_SRC ?= ../plugins   # directory holding steampipe-plugin-* checkouts (aws, jira, ...)

test:              ## unit + integration (fast, no cloud, no services)
	$(PY) -m pytest

test-unit:
	$(PY) -m pytest -m unit

test-integration:
	$(PY) -m pytest -m integration

test-system:       ## needs a running Steampipe with the plugins: see tests/system/test_live.py
	OPSLENS_SYSTEM=1 $(PY) -m pytest -m system tests/system -v

lint:
	$(PY) -m ruff check src tests scripts

catalog:           ## rebuild both catalogs (needs flowpipe on PATH and plugin source checkouts)
	$(PY) scripts/build_pipeline_catalog.py $(MODS)
	$(PY) scripts/build_table_catalog.py aws $(PLUGINS_SRC)/aws --ref v1.35.0
	$(PY) scripts/build_table_catalog.py jira $(PLUGINS_SRC)/jira --ref v2.0.5
	$(PY) scripts/build_table_catalog.py microsoft365 $(PLUGINS_SRC)/microsoft365 --ref v1.3.0
	$(PY) scripts/build_table_catalog.py gitlab $(PLUGINS_SRC)/gitlab --ref v0.6.0
	$(PY) scripts/build_table_catalog.py opsgenie $(PLUGINS_SRC)/opsgenie --version 0.0.2

wheel:
	$(PY) -m pip wheel --no-deps --wheel-dir dist .

IMAGE ?= opslens:dev

docker-build:      ## build the image (Flowpipe, Steampipe and the five plugins baked in)
	docker build -t $(IMAGE) .

docker-smoke:      ## offline smoke test of the image: demo data only, no credentials, no network
	docker run --rm --network none $(IMAGE) --version
	docker run --rm --network none $(IMAGE) search "unattached ebs volumes then open a jira ticket" > /dev/null
	docker run --rm --network none $(IMAGE) query --source demo "select count(*) as n from aws_ebs_volume"
	docker run --rm --network none -e OPSLENS_STEAMPIPE_SERVICE=on $(IMAGE) doctor
