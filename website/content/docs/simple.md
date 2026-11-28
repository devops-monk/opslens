# Explained simply

What is opslens? Imagine you never read a manual. This page explains it with a story, one picture, and one thing you can really run in two minutes.

## The story: a toy room

Your company's cloud (AWS) is like a **giant toy room**. Every day people take toys out and forget to put them away. A big, expensive toy is left on the floor, nobody plays with it, and **you still pay for it every month**. In the cloud, one of those toys is a *disk* that is not plugged into anything.

Someone has to walk around, find the forgotten toys, tell the right people, and put them away. That is boring, easy to forget, and a little scary (what if you put away a toy somebody still needs?).

**opslens is a careful helper that does the walking-around for you, and always asks a grown-up before putting anything away.**

## Step 1. The four steps

[[diagram:simple_flow]]

1. **Look.** opslens looks at your cloud and finds forgotten things. It only *looks*. It cannot touch anything while looking.
2. **You read.** You see exactly what opslens plans to do, and you can test it. Nothing has happened yet.
3. **Tell.** opslens writes a ticket (in Jira) or sends a message (in Teams or Slack) so people know.
4. **Ask, then fix.** Before it deletes or changes anything, it stops and waits for a person to say yes.

That is the whole idea. Everything else on this website is detail about those four steps.

## Step 2. Try it (no cloud account needed)

Nothing below touches a real cloud. opslens comes with pretend data to practice on.

**2a. Install it** (one line, in a terminal):

```bash
curl -fsSL https://opslens.devops-monk.com/install.sh | sh
```

**2b. Look at the forgotten disks** (this is step 1, "Look"). The word `--source demo` means "use the pretend data":

```bash
opslens query --source demo \
  "select volume_id, size, region from aws_ebs_volume
   where state = 'available'"
```

You will see disks that nobody is using, like this:

```text
 volume_id              size  region
 vol-00000000000000003  500   us-east-1
 vol-00000000000000006  50    eu-west-1
 vol-00000000000000009  1000  us-east-1
```

Each row is one forgotten toy. (`state = 'available'` is cloud-speak for "not plugged into anything".)

## Step 3. Get a ready-made plan

You do not have to invent the plan. opslens ships with ready-made ones called **templates**. Pick the one for unused disks:

```bash
opslens pack install finops-cleanup/unattached-volumes
```

It prints where it saved the plan (a folder called `unattached_volume_cleanup`).

## Step 4. Ask opslens to explain the plan in plain words

```bash
opslens explain generated/unattached_volume_cleanup
```

```text
- Finds EBS volumes unattached for N days, opens a Jira ticket for each, and deletes them after approval.
- Runs every 24h (switched off until you turn it on), or on demand.
- For each one found, immediately: Open a ticket per volume (jira.create_issue).
- Then it asks: "Delete these unattached volumes?" Only on approval, for each one: Delete the volume.
```

Read that out loud. It says: *look, make a ticket, then ask before deleting.* That is steps 1, 3 and 4 from the picture.

## Step 5. Do a pretend run

```bash
opslens preview generated/unattached_volume_cleanup --source demo
```

opslens shows what it **would** do, and does none of it:

```text
1. jira.pipeline.create_issue  notify  runs automatically  x 8
   summary='Unattached EBS volume vol-00000000000000006 (50 GiB io1) in eu-west-1'

2. aws.pipeline.delete_ebs_volume  CHANGE  runs after approval  x 8
   volume_id='vol-00000000000000003', region='us-east-1'

8 state change(s) would be requested; 0 have been made (this was a preview).
```

Look at the last line: **"8 would be requested; 0 have been made."** Nothing was deleted. The word `CHANGE` and the words `runs after approval` are opslens telling you: *this part will wait for a person.*

## Step 6. When you are ready for real

1. [Connect your tools](../integrations/) (Jira, Teams, Slack, AWS) so opslens can reach them.
2. Run the same `preview` without `--source demo` to see your **real** forgotten disks. Still nothing changes.
3. Start it for real with `opslens deploy`. You must type the plan's fingerprint (a short code) so you cannot start a plan you have not read. See [Deploy, approve, audit](../deploy/).
4. When it finds disks, it makes tickets and then **waits**. A person answers yes or skip. Only after yes does it delete.

## Step 7. Where do I go next?

| I want to... | Read |
|---|---|
| Click instead of type | [The web app](../app/), or the [live demo](../../app/) |
| See more ready-made plans (there are 32) | [Templates](../packs/) |
| Describe my own plan in a sentence | [AI planner](../ai/) (optional; everything above works without AI) |
| See every command | [Commands](../../commands/) |
| Understand how it works inside | [Architecture](../../architecture/) |

## All the commands on one picture

If the many commands feel confusing, this map shows where each one fits. The [Commands page](../../commands/) explains every word.

[[diagram:command_map]]

## Words you will see

| Word | Simple meaning |
|---|---|
| **Cloud / AWS** | The giant toy room: computers and disks you rent |
| **Template** (also "pack") | A ready-made plan |
| **Spec** | The plan itself, a short file you can read |
| **Preview** | A pretend run: shows what would happen, does nothing |
| **Approve** | A person says yes before anything is changed |
| **Steampipe** | The part that *looks* at your cloud |
| **Flowpipe** | The part that *does* the steps |
