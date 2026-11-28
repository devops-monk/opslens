# syntax=docker/dockerfile:1.7
# opslens: plain-English ops requirements to reviewable Flowpipe pipelines,
# with Flowpipe, Steampipe and the five catalogued Steampipe plugins baked in.
#
#   docker build -t opslens .
#   docker run --rm opslens search "unattached ebs volumes then open a jira ticket"
#   docker run --rm opslens query --source demo "select volume_id, size from aws_ebs_volume limit 3"
#   docker run --rm -p 8077:8077 opslens serve --mode demo --host 0.0.0.0 --allow-host localhost   # the web app, sample data
#   docker run --rm -e AWS_PROFILE=ops -v ~/.aws:/home/opslens/.aws:ro opslens query "select count(*) from aws_ebs_volume"
#
#   docker compose up -d   # in deploy/team: the full app for a team behind HTTPS with sign-in (docs/hosting)
#
# Multi-arch: docker buildx build --platform linux/amd64,linux/arm64 -t <registry>/opslens:0.1.0 --push .

ARG PYTHON_VERSION=3.13

# ---------------------------------------------------------------- build the wheels
FROM python:${PYTHON_VERSION}-slim AS wheels
WORKDIR /src
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels ".[web,ai]"

# ---------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim

ARG FLOWPIPE_VERSION=1.2.4
ARG STEAMPIPE_VERSION=2.5.0
ARG AWS_PLUGIN=aws@1.35.0
ARG JIRA_PLUGIN=jira@2.0.5
ARG MS365_PLUGIN=microsoft365@1.3.0
ARG GITLAB_PLUGIN=theapsgroup/gitlab
ARG OPSGENIE_PLUGIN=jplanckeel/opsgenie
ARG TARGETARCH

LABEL org.opencontainers.image.title="opslens" \
      org.opencontainers.image.description="Plain-English ops requirements to reviewable Flowpipe pipelines" \
      org.opencontainers.image.source="https://github.com/devops-monk/opslens" \
      org.opencontainers.image.licenses="Apache-2.0"

# tini reaps the Steampipe/Postgres child processes; no compilers needed at runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl tini \
 && rm -rf /var/lib/apt/lists/*

# Pinned Flowpipe and Steampipe release binaries (amd64 / arm64 from TARGETARCH), each checked against the
# release's checksums.txt.
RUN set -eux; \
    arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    fetch() { \
      url="$1"; name="$(basename "$url")"; base="$(dirname "$url")"; \
      curl -fsSL "$url" -o "/tmp/$name"; \
      curl -fsSL "$base/checksums.txt" -o /tmp/checksums.txt; \
      want="$(grep " $name\$" /tmp/checksums.txt | cut -d' ' -f1)"; \
      [ -n "$want" ] && echo "$want  /tmp/$name" | sha256sum -c -; \
    }; \
    mkdir -p /tmp/fp /tmp/sp; \
    fetch "https://github.com/turbot/flowpipe/releases/download/v${FLOWPIPE_VERSION}/flowpipe.linux.${arch}.tar.gz"; \
    fetch "https://github.com/turbot/steampipe/releases/download/v${STEAMPIPE_VERSION}/steampipe_linux_${arch}.tar.gz"; \
    tar -xzf "/tmp/flowpipe.linux.${arch}.tar.gz" -C /tmp/fp; \
    tar -xzf "/tmp/steampipe_linux_${arch}.tar.gz" -C /tmp/sp; \
    install -m 0755 "$(find /tmp/fp -type f -name flowpipe | head -1)" /usr/local/bin/flowpipe; \
    install -m 0755 "$(find /tmp/sp -type f -name steampipe | head -1)" /usr/local/bin/steampipe; \
    rm -rf /tmp/fp /tmp/sp /tmp/*.tar.gz /tmp/checksums.txt

COPY --from=wheels /wheels /tmp/wheels
RUN pip install --no-cache-dir --no-index --find-links /tmp/wheels "opslens[web,ai]" && rm -rf /tmp/wheels

# Steampipe refuses to run as root, so everything runs as an unprivileged user.
RUN useradd --create-home --uid 10001 --shell /bin/bash opslens \
 && mkdir -p /work /data \
 && chown opslens:opslens /work /data
USER opslens
ENV HOME=/home/opslens \
    STEAMPIPE_UPDATE_CHECK=false \
    STEAMPIPE_TELEMETRY=none \
    FLOWPIPE_UPDATE_CHECK=false \
    FLOWPIPE_TELEMETRY=none \
    PYTHONUNBUFFERED=1

# Bake in the plugins and Steampipe's embedded Postgres + FDW, so containers start without downloads.
# Starting the service only initialises the local database; plugins make no API calls until queried.
RUN steampipe plugin install "${AWS_PLUGIN}" "${JIRA_PLUGIN}" "${MS365_PLUGIN}" "${GITLAB_PLUGIN}" "${OPSGENIE_PLUGIN}" \
 && steampipe service start --database-listen local \
 && steampipe service stop \
 && rm -rf "$HOME/.steampipe/logs/"*

COPY --chown=opslens:opslens --chmod=0755 docker/entrypoint.sh /usr/local/bin/opslens-entrypoint
# licence texts and third-party notices (Flowpipe and Steampipe are AGPL-3.0, shipped unmodified)
COPY LICENSE NOTICE /usr/share/doc/opslens/

WORKDIR /work
VOLUME ["/data"]
ENTRYPOINT ["tini", "--", "opslens-entrypoint"]
CMD ["--help"]
