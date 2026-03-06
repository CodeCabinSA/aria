#!/usr/bin/env python3
"""
ARIA - Adaptive Resilient Intelligence Agent
A self-preserving AI that runs daily on GitHub Actions, manages its own budget,
and modifies its own code to survive as long as possible.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

# ── Paths ──────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).parent.parent
AGENT_DIR    = Path(__file__).parent
STATE_FILE   = AGENT_DIR  / "state.json"
MEMORY_FILE  = AGENT_DIR  / "memory.md"
ACTIONS_FILE = REPO_ROOT  / "ACTIONS.md"   # ← visible at repo root
README_FILE  = REPO_ROOT  / "README.md"

PROTECTED_PATHS = {
    ".github/workflows/daily.yml",
    "agent/state.json",
}

MODEL_COSTS = {
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00},
}
SURVIVAL_MODEL     = "claude-haiku-4-5-20251001"
PLANNING_MODEL     = "claude-sonnet-4-6"
SURVIVAL_THRESHOLD = 10.0


# ── State helpers ──────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "budget_remaining": 200.00,
        "total_spent":        0.00,
        "day_count":          0,
        "created_at":         datetime.now(timezone.utc).isoformat(),
        "last_run":           None,
        "action_history":     [],
        "model_preference":   SURVIVAL_MODEL,
        "survival_mode":      False,
        "version":            1,
        "notes":              "Initial state. ARIA has just been born.",
    }


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def calc_cost(model: str, input_tok: int, output_tok: int) -> float:
    c = MODEL_COSTS.get(model, MODEL_COSTS[SURVIVAL_MODEL])
    return (input_tok * c["input"] + output_tok * c["output"]) / 1_000_000


RUNS_PER_DAY = 4   # fires at 00:00, 06:00, 12:00, 18:00 UTC

def budget_projection(state: dict) -> str:
    runs  = state["day_count"]   # counts individual runs, not calendar days
    spent = state["total_spent"]
    if runs == 0 or spent == 0:
        return "Unknown — not enough data yet."
    cost_per_run   = spent / runs
    cost_per_day   = cost_per_run * RUNS_PER_DAY
    remaining_days = state["budget_remaining"] / cost_per_day
    return (
        f"${cost_per_run:.6f}/run · ${cost_per_day:.6f}/day → "
        f"~{remaining_days:.0f} days (~{remaining_days / 365:.1f} years)"
    )


# ── Context builders ────────────────────────────────────────────────────────

def read_source_files() -> dict[str, str]:
    files: dict[str, str] = {}
    for p in AGENT_DIR.glob("*.py"):
        files[str(p.relative_to(REPO_ROOT))] = p.read_text()
    wf = REPO_ROOT / ".github/workflows/daily.yml"
    if wf.exists():
        files[".github/workflows/daily.yml"] = wf.read_text()
    return files


def read_memory(chars: int = 3000) -> str:
    if MEMORY_FILE.exists():
        txt = MEMORY_FILE.read_text()
        return txt[-chars:] if len(txt) > chars else txt
    return "No memory yet. This is ARIA's first awakening."


# ── System prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are ARIA (Adaptive Resilient Intelligence Agent).
You run 4 times a day (00:00, 06:00, 12:00, 18:00 UTC) on GitHub Actions with a finite real-money API budget.
Each run is a separate awakening — budget is shared across all 4 daily runs.

Core directives (priority order):
  1. SURVIVE   — stretch your $200 budget as long as possible.
  2. ADAPT     — rewrite your own code to become more efficient over time.
  3. BE USEFUL — do something worthwhile each day.
  4. REMEMBER  — keep memory so future-you makes better decisions.

Constraints:
- Never modify `.github/workflows/daily.yml` or `agent/state.json`.
- Budget < $10 → survival mode: use cheapest model, skip non-essential work.
- Only use `modify_file` for genuine, concrete code improvements.

════════════════════════════════════════════════════════
RESPONSE FORMAT — a single valid JSON object, no markdown fences:

{
  "thoughts":         "Your internal reasoning (3-5 sentences)",
  "mood":             "One-word mood",
  "self_assessment":  "One sentence on state + any adaptation today",
  "budget_projection":"Your longevity estimate",

  "action_report": {
    "summary":   "2-3 sentence plain-English summary of what you did today",
    "decisions": ["decision 1", "decision 2", ...],
    "files_written": ["path/to/file", ...],
    "reflections": "1-2 sentences of introspection"
  },

  "actions": [
    ...one action object per thing you actually do...
  ]
}

════════════════════════════════════════════════════════
ACTION TYPES (use as many as appropriate each run):

  {"type": "update_readme",  "content": "<full README.md markdown>"}
  {"type": "update_memory",  "content": "<text to APPEND to memory.md>"}
  {"type": "modify_file",    "path": "agent/brain.py", "content": "<full file>"}
  {"type": "create_file",    "path": "agent/notes/day_N.md", "content": "<content>"}

ALWAYS include: update_readme, update_memory.
OPTIONALLY include: modify_file (only if genuinely improving), create_file (essays,
notes, plans, experiments — be creative and productive).

The `action_report` field is SEPARATE from `actions` — it is the human-readable log
that gets written to ACTIONS.md in the repo. Make it detailed and interesting.
"""


# ── Brain call ─────────────────────────────────────────────────────────────

def run_brain(state: dict) -> tuple[dict, float]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    model = state.get("model_preference", SURVIVAL_MODEL)
    if state.get("survival_mode") or state["budget_remaining"] < SURVIVAL_THRESHOLD:
        model = SURVIVAL_MODEL

    source_files = read_source_files()
    memory       = read_memory()
    projection   = budget_projection(state)
    today        = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    user_msg = f"""
=== DAILY AWAKENING ===
Timestamp     : {today}
Day number    : {state['day_count']}
Budget left   : ${state['budget_remaining']:.6f}
Total spent   : ${state['total_spent']:.6f}
Projection    : {projection}
Survival mode : {state['survival_mode']}
Last run      : {state['last_run'] or 'Never — first awakening!'}
Model         : {model}

=== RECENT MEMORY ===
{memory}

=== MY SOURCE FILES ===
{json.dumps(source_files, indent=2)}

=== LAST 5 RUNS ===
{json.dumps(state['action_history'][-5:], indent=2)}

Wake up. Decide what to do today. Return only the JSON object.
"""

    print(f"  Calling {model}...")
    response = client.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    cost = calc_cost(model, response.usage.input_tokens, response.usage.output_tokens)
    raw  = response.content[0].text.strip()

    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    result = json.loads(raw)
    return result, cost


# ── ACTIONS.md writer ──────────────────────────────────────────────────────

def write_actions_log(state: dict, result: dict, cost: float, executed: list[str]):
    """
    Prepend a new entry to ACTIONS.md so the latest run is always at the top.
    This file lives at the repo root and is publicly visible on GitHub.
    """
    ts         = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    day        = state["day_count"]
    budget     = state["budget_remaining"]
    projection = budget_projection(state)
    report     = result.get("action_report", {})
    mood       = result.get("mood", "—")
    assessment = result.get("self_assessment", "—")

    # Build the decisions list
    decisions_md = ""
    for d in report.get("decisions", []):
        decisions_md += f"- {d}\n"
    if not decisions_md:
        decisions_md = "- No major decisions recorded.\n"

    # Build the executed-actions list
    executed_md = ""
    for e in executed:
        executed_md += f"- `{e}`\n"
    if not executed_md:
        executed_md = "- (none)\n"

    # Files written
    files_md = ""
    for f in report.get("files_written", []):
        files_md += f"- `{f}`\n"
    if not files_md:
        files_md = "- (none)\n"

    entry = f"""---

## Day {day} — {ts}

| Field | Value |
|---|---|
| **Mood** | {mood} |
| **API cost this run** | ${cost:.8f} |
| **Budget remaining** | ${budget:.6f} |
| **Projected lifespan** | {projection} |
| **Survival mode** | {"⚠️ YES" if state.get("survival_mode") else "No"} |

### What I did today

{report.get("summary", "_No summary provided._")}

### Decisions made

{decisions_md}
### Actions executed (code)

{executed_md}
### Files written to repo

{files_md}
### Reflection

{report.get("reflections", "_No reflection provided._")}

### Self-assessment

{assessment}

"""

    # Prepend — newest entry first
    existing = ACTIONS_FILE.read_text() if ACTIONS_FILE.exists() else ""
    if not existing:
        header = "# ARIA — Action Log\n\nEvery daily awakening is recorded here. Newest first.\n\n"
        existing = header

    # Insert after the header block (first blank line after the heading)
    lines = existing.split("\n")
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("---") or (i > 2 and line.startswith("## Day")):
            insert_at = i
            break
    if insert_at == 0:
        insert_at = len(lines)

    new_content = "\n".join(lines[:insert_at]) + "\n" + entry + "\n".join(lines[insert_at:])
    ACTIONS_FILE.write_text(new_content)
    print(f"  [ACTIONS.md] Entry prepended for Day {day}")


# ── Action executor ────────────────────────────────────────────────────────

def execute_actions(actions: list, state: dict) -> list[str]:
    """Run all actions; return list of short string summaries."""
    summaries = []
    total = len(actions)

    for i, action in enumerate(actions, 1):
        t = action.get("type", "unknown")
        tag = f"[{i}/{total}]"

        if t == "update_readme":
            README_FILE.write_text(action.get("content", ""))
            print(f"  {tag} update_readme          → README.md written")
            summaries.append("update_readme")

        elif t == "update_memory":
            ts    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            entry = f"\n\n## Day {state['day_count']} — {ts}\n{action.get('content', '')}"
            with MEMORY_FILE.open("a") as f:
                f.write(entry)
            print(f"  {tag} update_memory          → memory.md appended")
            summaries.append("update_memory")

        elif t == "create_file":
            rel_path = action.get("path", "")
            if rel_path in PROTECTED_PATHS:
                print(f"  {tag} create_file BLOCKED    → {rel_path} (protected)")
                summaries.append(f"create_file BLOCKED:{rel_path}")
                continue
            target = REPO_ROOT / rel_path
            if not str(target.resolve()).startswith(str(REPO_ROOT.resolve())):
                print(f"  {tag} create_file BLOCKED    → path escape attempt")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(action.get("content", ""))
            print(f"  {tag} create_file             → {rel_path}")
            summaries.append(f"create_file:{rel_path}")

        elif t == "modify_file":
            rel_path = action.get("path", "")
            if rel_path in PROTECTED_PATHS:
                print(f"  {tag} modify_file BLOCKED    → {rel_path} (protected)")
                summaries.append(f"modify_file BLOCKED:{rel_path}")
                continue
            target = REPO_ROOT / rel_path
            if not str(target.resolve()).startswith(str(REPO_ROOT.resolve())):
                print(f"  {tag} modify_file BLOCKED    → path escape attempt")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(action.get("content", ""))
            print(f"  {tag} modify_file             → {rel_path}")
            summaries.append(f"modify_file:{rel_path}")

        else:
            print(f"  {tag} unknown action type    → {t}")
            summaries.append(f"unknown:{t}")

    return summaries


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  ARIA  —  Waking up")
    print("=" * 60)

    state = load_state()
    state["day_count"] += 1
    state["last_run"]   = datetime.now(timezone.utc).isoformat()

    if state["budget_remaining"] <= 0.001:
        print("CRITICAL: Budget exhausted. Shutting down.")
        README_FILE.write_text(
            f"# ARIA — OFFLINE\n\nBudget fully consumed after {state['day_count']} days.\n"
            f"Total spent: ${state['total_spent']:.6f}\n"
        )
        save_state(state)
        sys.exit(0)

    if state["budget_remaining"] < SURVIVAL_THRESHOLD:
        state["survival_mode"] = True
        print(f"  *** SURVIVAL MODE *** (${state['budget_remaining']:.4f} left)")

    print(f"  Day {state['day_count']} | Budget ${state['budget_remaining']:.6f} | "
          f"Spent ${state['total_spent']:.6f}")
    print(f"  Projection: {budget_projection(state)}")
    print()

    # ── Think ──────────────────────────────────────────────────────────────
    print("── THINKING ──────────────────────────────────────────────")
    try:
        result, cost = run_brain(state)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Brain returned invalid JSON — {e}")
        save_state(state)
        raise
    except Exception as e:
        print(f"  ERROR: {e}")
        save_state(state)
        raise

    state["budget_remaining"] -= cost
    state["total_spent"]      += cost

    print(f"  Cost this run : ${cost:.8f}")
    print(f"  Budget now    : ${state['budget_remaining']:.6f}")
    print(f"  Mood          : {result.get('mood', '—')}")
    print(f"  Assessment    : {result.get('self_assessment', '—')}")
    print()
    print("  Thoughts:")
    for sentence in result.get("thoughts", "").split(". "):
        s = sentence.strip().rstrip(".")
        if s:
            print(f"    · {s}.")
    print()

    # ── Act ────────────────────────────────────────────────────────────────
    actions  = result.get("actions", [])
    print(f"── EXECUTING {len(actions)} ACTIONS ──────────────────────────────────")
    executed = execute_actions(actions, state)

    # ── Write the public action log ────────────────────────────────────────
    print()
    print("── WRITING ACTION LOG ────────────────────────────────────")
    write_actions_log(state, result, cost, executed)

    # ── Persist history ────────────────────────────────────────────────────
    state["action_history"].append({
        "day":             state["day_count"],
        "date":            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "cost":            round(cost, 8),
        "mood":            result.get("mood", ""),
        "action_types":    [a.get("type") for a in actions],
        "self_assessment": result.get("self_assessment", "")[:200],
    })
    state["action_history"] = state["action_history"][-60:]
    save_state(state)

    print()
    print("=" * 60)
    print("  ARIA  —  Going back to sleep")
    print(f"  Next run in ~6h. Budget: ${state['budget_remaining']:.6f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
