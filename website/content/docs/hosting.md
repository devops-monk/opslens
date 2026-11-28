# Host it for your team

Run the full app for a team: build automations, test them on live data, deploy, and approve changes, from a browser, with sign-in. This is **team mode**. It is a different thing from the public [demo](../ways-to-run/), which only uses sample data.

> Team mode can deploy and run automations with your cloud credentials, so it **refuses to start without sign-in**. Put it behind HTTPS, and treat the team password like any shared admin credential.

## What you get

| | Local | Team | Public demo |
|---|---|---|---|
| For | One person | A team, on a server | Anyone, to look around |
| Live data, save, deploy, approve | Yes | Yes | No |
| Sign-in | None (loopback only) | **Required** | None |
| Binds beyond loopback | Never | Yes, with sign-in | Yes |
| Audit log names the person | The OS user | **The signed-in name** | n/a |

## Quick start with Docker Compose

You need a server with Docker, a DNS name pointing at it, and ports 80 and 443 open. The stack runs opslens and Caddy, which gets a free HTTPS certificate and renews it.

```bash
git clone https://github.com/devops-monk/opslens && cd opslens/deploy/team
cp .env.example .env          # set OPSLENS_HOST, OPSLENS_TEAM_PASSWORD, OPSLENS_SESSION_SECRET
touch credentials.env         # AWS_* style variables for your plugins (may stay empty for now)
docker compose up -d
```

Open `https://<your host>`. You are sent to the sign-in page. Enter your name (it appears in the audit log) and the team password.

| Setting | What it is |
|---|---|
| `OPSLENS_HOST` | The public host name, for example `ops.example.com`. It is also the allowed `Host` header. |
| `OPSLENS_TEAM_PASSWORD` | The shared password, 12 characters or more. Only read from the environment, never from a command line. |
| `OPSLENS_SESSION_SECRET` | A long random string (`openssl rand -hex 32`) that signs session cookies, so people stay signed in across restarts. |
| `OPSLENS_VERSION` | Pin a release for repeatable deploys. |

Everything people save, and the audit log, live on the `opslens-data` volume. Back that volume up.

## Connect your accounts

opslens never stores credentials. As elsewhere, they live in Steampipe (to read) and Flowpipe (to act), configured the way each plugin documents. In the container you have two ways:

- **Environment variables** that a plugin reads, in `credentials.env` (for AWS, the standard `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_REGION`, or a role if the host has one).
- **Connection files**: put Steampipe `.spc` files in `./config/steampipe` and Flowpipe `.fpc` files in `./config/flowpipe`, then uncomment the two volume lines in `docker-compose.yml`.

Give Steampipe read-only credentials where you can. After the first start, run `docker compose exec opslens opslens doctor` to see what is connected.

## Sign-in options

**Shared password** (the default above, `--auth password`). Simple, and fine for a small team. People type their own name at sign-in, but nothing verifies it, so the audit log names are *self-declared*. Sessions last 12 hours; the cookie is `HttpOnly`, `SameSite=Strict` and `Secure`. Ten sign-in attempts a minute are allowed per client.

**Single sign-on** (`--auth proxy`). Put an identity proxy such as oauth2-proxy, Cloudflare Access or your own gateway in front. It signs people in with your identity provider and tells opslens who they are, so the audit log names are *verified*.

```bash
export OPSLENS_PROXY_SECRET=$(openssl rand -hex 24)
opslens serve --mode team --auth proxy --host 0.0.0.0 --allow-host ops.example.com --trust-proxy
```

Your proxy must add two headers to every request it forwards: `X-Opslens-Proxy-Secret` with the secret above, and `X-Forwarded-Email` (or the header named by `--auth-header`) with the signed-in user. A request without the right secret is refused, so someone who reaches opslens without going through the proxy cannot make up an identity. **Do not publish the opslens port**; only the proxy should reach it.

## What stays the same

Team mode adds sign-in, nothing else changes the safety model:

- Changes still **wait for approval**, and you can only deploy the exact spec hash you reviewed.
- Every state-changing request still needs the per-session token (cross-site requests are refused).
- The `Host` allow-list, SQL guard, validator and audit log work as before. The audit log now records who deployed, ran and approved.

## Operating it

- **Restarts.** Saved automations and the audit log survive. A deployed automation is a Flowpipe process inside the container, so after a restart or an image upgrade it is **not running** until you open *My automations* and deploy it again (the same approved spec hash). Scheduled triggers do not fire in between.
- **Upgrades.** Change `OPSLENS_VERSION`, then `docker compose pull && docker compose up -d`.
- **Logs.** `docker compose logs -f opslens`.
- **Rotate the password.** Change `OPSLENS_TEAM_PASSWORD` and restart. Change `OPSLENS_SESSION_SECRET` too to sign everyone out.
- **One writer.** Run a single opslens container per workspace volume.

## What team mode is not

It is not multi-tenant and has no per-user roles: everyone who can sign in can deploy and approve. If you need to limit who may approve changes, use `--auth proxy` and restrict access in your identity provider, or keep the full app local and use the [CLI](../cli/) in CI for deploys.

## Without Docker

```bash
export OPSLENS_TEAM_PASSWORD='a long shared password'
opslens serve --mode team --auth password --host 127.0.0.1 --port 8077 --allow-host ops.example.com --trust-proxy
```

Run it under systemd and put nginx or Caddy in front for HTTPS. Add `--no-secure-cookies` only to try it over plain `http://localhost`.
