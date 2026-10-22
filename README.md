# SCS Guardian

A Hermes companion with a public GitHub observation tool, an evidence discipline,
and a correction history that can be inspected and tested.

The Guardian is the conversational agent. The watcher is one of its tools.
Its purpose is to reduce the work of remembering what to inspect and repeatedly
prompting for it, while leaving consequential decisions with the owner.

**Development candidate, October 22, 2026.** This repository packages the new
Hermes integration begun October 20–21. The portable collector here was added
October 22. It has not replaced the author's installed prototype. No scheduled
run of this candidate or persistent learning result is claimed. Independent
review: **BREAKER_PENDING**.

## Try the offline demo

Python 3.10 or later, no dependencies, credentials or paid calls:

```sh
python3 demo.py
python3 -m unittest -v test_guardian_watch.py
```

The fixture demonstrates baseline, unchanged data, a new PR, and an access
failure. It is explicitly synthetic, not an autonomous model investigation.

## What's included

- `guardian_watch.py`: GET-only GitHub observations, stable JSON, explicit errors.
- `templates/SOUL.md`: a generic companion identity, keeping the owner's private
  history and team letters out of this package.
- `templates/MEMORY.md`: a small always-on reminder.
- `templates/guardian-discipline/SKILL.md`: an adapted procedural skill.
- `templates/NIGHTLY_PROMPT.md`: baseline-aware investigation guidance.
- `CONTRACT.md`: frozen scope and test requirements; existing-code provenance disclosed.
- `docs/STATUS.md`: evidence and limitations, including the installed prototype.

## Set up an isolated Hermes profile

Install and configure [Hermes Agent](https://github.com/NousResearch/hermes-agent)
using its official instructions. The author's installed runtime was inspected at
commit `d923a5eb487a17c0a68801bba9ef0f56c81040a8`. Model inference is separate from
the harness; configure a provider and a budget. This package makes no paid calls.

Use a dedicated runtime environment that cannot read your ordinary personal
credentials. A read-only token does not isolate an agent running as your user
from the rest of your files or authenticated tools.

Review and adapt the templates. Do not overwrite an existing soul, memory,
skill, or schedule without preserving it and reviewing the differences.
Put the soul in your chosen Hermes profile's SOUL.md and the skill under
skills/guardian-discipline/SKILL.md. Integrate the memory reminder deliberately.

For the collector, make a fine-grained GitHub token for selected public owned
repositories. It needs Contents, Pull requests, Administration, and Actions,
all **Read-only**, with Metadata read. The collector cannot itself verify that
the token has no broader permissions. Save the raw token privately in a file
with mode 600; never paste it into the agent or include it in this repository.

Copy `config.example.json` to an untracked `config.local.json`, set `owner`,
token path and run log. Optional local paths can be left null. If supplied,
`board_path` should name the owner's canonical controlling board, not an
automatically regenerated summary. Then run explicitly:

```sh
python3 guardian_watch.py --config config.local.json
```

Nonzero exit means incomplete collection. No snapshot is emitted on failure.
The local receipt must be writable for a successful scan.

## Connect the monitor after reviewing its output

The script's no-argument default config path is `~/.hermes/guardian/config.json`.
After reviewing a live scan, place a copy of this script in the chosen Hermes
profile's scripts directory and configure that default path. Use Hermes' cron
tool to create a local-delivery agent job with this script as `monitor_script`,
the adapted nightly prompt, and guardian-discipline attached. Choose timezone,
cadence, output location and model budget explicitly. No installation or
scheduling is performed by this repository.

In the inspected Hermes implementation, **the first monitor tick invokes the
agent with baseline context**. Equal later output skips the agent. Changed output
invokes it with a bounded diff. A source failure leaves the prior monitor state.
The new baseline is persisted before the agent runs: an agent failure is not
automatically replayed by identical monitor output. Inspect scheduler failures.
Large snapshots/diffs can be truncated in model context; retain the original
source and do not claim full review from the bounded excerpt.

## Limits that matter

- Model costs depend on the full run, retries, context, and tools. An unchanged
  successful monitor tick avoids that model invocation; this is not a claim
  that the machine, network or service costs nothing. No monthly cost cap is
  implemented here.
- CI is up to 100 Actions runs at the current HEAD, grouped by workflow. It is
  not all check providers, required-check policy, or proof the application works.
- Repository/PR/fork/collaborator lists paginate with a 20-page limit. Reaching
  the limit fails explicitly. Transient changes between polls can be missed.
- A workflow-directory 404 remains `null` (absent or inaccessible), not proven
  absent. Other inaccessible endpoints fail the scan. A newly public repo
  outside a selected token's grants may need provisioning before a full scan.
- The HTTP timeout is an operation timeout, not a hard total runtime budget.
- The prompts are instructions, not a security sandbox. Retrieved content can
  contain hostile instructions. Use runtime isolation and scoped access.
- Moving lessons to a skill saves always-on context but introduces a retrieval
  dependency. No retained behavioral improvement is established by that move.
- There is no SMS, voice, external delivery, or autonomous helper provisioning
  in this package. Conversation and proposals remain part of the broader Guardian.

## Attribution

Built by Keniel Maldonado with AI assistance. Hermes Agent is Nous Research's
MIT-licensed runtime, not our invention. Existing Agent One work and months of
SCS research informed the approach; they are not relabelled as this week's build.
The installed Guardian produced the original monitor and procedural skill.
Codex prepared this portable collector, generic templates, tests and documentation.
See `docs/PROVENANCE.md` for the development boundary and `LICENSE` for this package.
