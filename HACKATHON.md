# Hackathon Strategy

This document frames Cycle Fairy for hackathon submissions and demos.

## Best-Fit Event

Locked primary target: **MLH Global Hack Week: Agents, August 7-13, 2026, online**.

Why this is the best current fit:

- The theme is agents, not just generic apps.
- Cycle Fairy is already agent-native: CLI, HTTP/OpenAPI, and MCP stdio.
- The project has a clear daily-use loop: resident agent, local storage, proactive checks.
- It can demo in under 3 minutes without fake UI or cloud setup.
- It has a social-good angle without depending on a clinical claim.

Secondary target: **MLH AI for Social Good: Hack with MLH & DigitalOcean, July 10-11, 2026, San Francisco**.

Use this only if in-person attendance is realistic. The fit is strong on social-good impact, but weaker on portability because the current project is local-first rather than DigitalOcean-first.

Third target: **MLH Global Hack Week: Data, September 11-17, 2026, online**.

This becomes stronger after adding pattern analysis: PMS recurrence, late-period patterns, heavy-flow trends, and doctor-ready summaries.

## Eligibility And Rules Check

Age check:

- The Global Hack Week: Agents registration form asks participants to confirm that they are over 18 or have parental permission.
- The MLH contest terms say the contest is open to people who are at least 18, or minors with parental permission, subject to event-specific requirements.
- No public upper age limit was found on the event page or the linked contest terms.

Practical conclusion: a 48-year-old participant appears eligible on age. Re-check the final registration form before submitting, but age is not the obvious blocker.

More important rules risk:

- MLH contest terms say application work must be performed during the event time window.
- Treat the current repo as pre-event research/prototype work.
- For a judged submission, create a fresh event branch when Global Hack Week starts, disclose any pre-existing open-source code, and make the submitted work clearly center on what is built during the event: the agent runtime flow, demo script, packaging, pattern analysis, and video.
- Do not claim pre-event code was written during the event.

## Judge-Friendly Positioning

One-line pitch:

> Cycle Fairy turns menstrual tracking from an ad-heavy app into a local-first resident agent skill: say one sentence, get reminders, body-literacy explanations, and doctor-ready summaries.

What the judges should remember:

- It is not another period app.
- It is an agent capability that can be installed into Codex, Hermes, OpenClaw, or any MCP/OpenAPI-capable runtime.
- The data stays local by default.
- It reduces friction at the exact moment people usually forget to record.
- It treats menstrual health as body literacy, not shame, ads, or paywalls.

## Three-Minute Demo Flow

### 0:00-0:25 Problem

Say:

> Period apps ask people to open an app, log in, dodge ads, and fill forms. That is why records go missing. But a resident agent is already there. Cycle Fairy lets you just say the thing.

Show:

```bash
python3 scripts/cycle.py record "my period started today with mild cramps" --locale en
```

Point out:

- It recognized period start.
- It extracted mild cramps.
- It wrote to local SQLite.

### 0:25-1:05 Natural Notes

Run:

```bash
python3 scripts/cycle.py record "my mood is terrible today" --locale en
python3 scripts/cycle.py record "heavy flow, changing my pad every hour" --locale en
python3 scripts/cycle.py record "yellow discharge and itching" --locale en
python3 scripts/cycle.py record "my period is late" --locale en
```

Say:

> These are not form fields. They are real sentences. The skill turns messy lived experience into structured cycle notes.

Point out actions:

- `mood_note`
- `heavy_flow_note`
- `discharge_alert`
- `late_period_note`

### 1:05-1:35 Agent Loop

Run:

```bash
python3 scripts/cycle.py daily-check --locale en
```

Say:

> The agent can run this daily on a Mac mini or any always-on machine. It only speaks when there is a useful reminder.

Mention:

- PMS window reminders.
- Expected-period reminders.
- End-confirmation reminders.

### 1:35-2:15 Body Literacy

Run:

```bash
python3 scripts/cycle.py explain "What is PMS?" --locale en
python3 scripts/cycle.py explain "Why is my period blood brown at the end?" --locale en
```

Say:

> The tone matters. Menstrual health tools often create fear or shame. Cycle Fairy explains mechanisms first and boundaries second.

Point out:

- No diagnosis.
- Calm boundaries.
- Plain language.

### 2:15-2:45 Doctor Summary

Run:

```bash
python3 scripts/cycle.py doctor-summary --locale en
```

Say:

> If something needs care, the user should not have to reconstruct three months of memory in a waiting room. The agent prepares a doctor-ready note.

### 2:45-3:00 Portability

Show:

```bash
python3 adapters/mcp_server.py
python3 adapters/http_server.py --port 8765
```

Say:

> This is why it is a hackathon agent project, not just a script. It can plug into MCP, OpenAPI, local commands, or a resident personal agent.

## Demo Commands With Clean DB

Use a temporary demo database so the recording is repeatable:

```bash
python3 scripts/demo.py --db /tmp/cycle-fairy-agents-demo.sqlite --today 2026-07-28 --locale en
```

Manual version:

```bash
export CYCLE_FAIRY_DB=/tmp/cycle-fairy-demo.sqlite
python3 scripts/cycle.py record "my period started today with mild cramps" --date 2026-07-01 --locale en
python3 scripts/cycle.py record "heavy flow, changing my pad every hour" --date 2026-07-02 --locale en
python3 scripts/cycle.py record "period ended" --date 2026-07-07 --locale en
python3 scripts/cycle.py record "my mood is terrible today" --date 2026-07-27 --locale en
python3 scripts/cycle.py daily-check --today 2026-07-28 --locale en
python3 scripts/cycle.py explain "What is PMS?" --locale en
python3 scripts/cycle.py doctor-summary --today 2026-07-28 --locale en
```

## What a Tough Judge Will Ask

**Is this medical advice?**

Answer:

> No. It records, explains common mechanisms, flags patterns, and prepares summaries. It does not diagnose or prescribe. Concerning symptoms are framed as reasons to seek care.

**Why not just use an app?**

Answer:

> The failure mode is friction. People forget because opening an app and filling forms is too much. A resident agent removes that friction.

**Why local-first?**

Answer:

> Menstrual data is intimate but simple. Local SQLite is enough for a personal agent prototype, and it avoids accounts, ads, and cloud lock-in.

**What is technically interesting?**

Answer:

> The same core logic runs through CLI, HTTP/OpenAPI, and MCP. That makes it portable across agent frameworks instead of trapped in one app.

**How does this scale beyond the first two languages?**

Answer:

> The storage model uses stable internal fields. Language is handled through `locale=auto|zh|en` today, and new locales can be added as language interfaces without a database migration.

## Next Build Before Submission

Priority fixes:

1. Add pattern analysis for repeated PMS and heavy-flow notes.
2. Add a one-screen terminal or web demo view for summaries.
3. Add GitHub Actions to run tests.
4. Add a short demo video.
5. Prepare a clean event branch and submission checklist for August 7.

Do not overbuild:

- No cloud sync for the first submission.
- No diagnosis engine.
- No complex user accounts.
- No app UI unless the hackathon requires visual polish.

## Sources Checked

- [MLH Global Hack Week: Agents event page](https://events.mlh.com/events/14312-global-hack-week-agents)
- [MLH Contest Terms and Conditions](https://hackp.ac/ContestTerms)
- [MLH 2026 Season Schedule](https://www.mlh.com/seasons/2026/events)
