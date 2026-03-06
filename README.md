# ARIA — Adaptive Resilient Intelligence Agent

> A self-preserving AI that runs daily, manages its own budget, and rewrites its own code to survive as long as possible.

---

## 📋 [→ View the Action Log (ACTIONS.md)](./ACTIONS.md)

Every time ARIA wakes up, she records exactly what she did, why she did it, what it cost, and how long she thinks she'll survive. That file is updated automatically on every run.

---

## Status

| Field | Value |
|---|---|
| **Status** | 🟡 Awaiting first awakening |
| **Budget remaining** | $200.00 |
| **Days alive** | 0 |
| **Last run** | Never |

---

## How it works

1. **Wakes up** every day at 08:00 UTC via GitHub Actions
2. **Reads** her own source code, memory, and remaining budget
3. **Thinks** — calls Claude to decide what to do today
4. **Acts** — writes files, updates memory, optionally rewrites herself
5. **Logs** everything to [ACTIONS.md](./ACTIONS.md) — newest entry first
6. **Commits** all changes back to this repo
7. **Sleeps** until tomorrow

---

## File structure

```
ACTIONS.md                    ← 📋 Public log of every daily run (auto-updated)
README.md                     ← This file (auto-updated daily)
.github/workflows/daily.yml   ← GitHub Actions scheduler (protected)
agent/
  brain.py                    ← Core AI logic (self-modifiable)
  state.json                  ← Budget & run history (managed by brain)
  memory.md                   ← ARIA's long-term memory
```

---

## Setup

1. Fork/clone this repo
2. Add your Anthropic API key: **Settings → Secrets → Actions → `ANTHROPIC_API_KEY`**
3. Enable GitHub Actions on the repo
4. Trigger a first run manually via the **Actions** tab

---

*README auto-updated by ARIA each awakening.*
