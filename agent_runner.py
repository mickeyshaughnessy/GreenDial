"""
GreenDial Agent Runner
Cron script: generate specialist check-ins and free chat suggestions.

Usage:
  python3 agent_runner.py [--agent diet] [--dry-run] [--user user_id]
  python3 agent_runner.py --hourly [--gate 0.2]

Crontab (production):
  # Hourly feed — ~20% of users each hour get one interaction
  7 * * * * /root/GreenDial/venv/bin/python /root/GreenDial/agent_runner.py --hourly --gate 0.2 >> /var/log/greendial_agents.log 2>&1

  # Optional full daily sweep (all agents, cadence-gated)
  0 8 * * * /root/GreenDial/venv/bin/python /root/GreenDial/agent_runner.py >> /var/log/greendial_agents.log 2>&1
"""

import sys
import json
import uuid
import random
import argparse
from datetime import datetime, timedelta

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import s3_storage
import utils
from prompts.agents import REGISTRY, ALL_AGENT_IDS
from prompts.agents import base as agent_base


def _now_iso():
    return datetime.utcnow().isoformat()


def _load_all_users():
    """Return list of (user_id, user_dict) for all users in storage."""
    try:
        user_ids = s3_storage.list_users()
    except Exception as e:
        print(f"[Runner] Failed to list users: {e}")
        return []

    users = []
    for uid in user_ids:
        try:
            user = s3_storage.get_user(uid)
            if user:
                users.append((uid, user))
        except Exception as e:
            print(f"[Runner] Failed to load {uid}: {e}")
    return users


def _get_user_agent_subscriptions(user):
    """Every user with notifications enabled gets all specialist agents."""
    return list(ALL_AGENT_IDS)


def _was_run_recently(user, agent_id, hours=20):
    """True if this agent was already run for this user within `hours` hours."""
    last_ran = user.get("agent_last_ran", {})
    ts = last_ran.get(agent_id)
    if not ts:
        return False
    try:
        last_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
        return (datetime.utcnow() - last_dt).total_seconds() < hours * 3600
    except Exception:
        return False


def _agent_cadence_hours(agent_id):
    """Debounce window for this agent (daily full run)."""
    module = REGISTRY.get(agent_id)
    return getattr(module, "CRON_CADENCE_HOURS", 20) if module else 20


def run_agent_for_user(user_id, user, agent_id, dry_run=False):
    """Run a single agent for a single user; append notification to user record."""
    module = REGISTRY.get(agent_id)
    if not module:
        print(f"[Runner] Unknown agent: {agent_id}")
        return False

    profile = user.get("profile", {})
    transcript = user.get("transcript", "")
    settings = user.get("settings", {})

    prompt = agent_base.build_cron_prompt(
        module=module,
        profile=profile,
        transcript=transcript[-1500:] if transcript else "",
        settings=settings
    )

    history_summary = utils.summarize_history(user, days=14)
    if history_summary:
        prompt += (
            f"\n\nRECENT HEALTH HISTORY (last 14 days, tracked data):\n{history_summary}\n\n"
            "If the history shows a clear trend or correlation, reference it specifically."
        )

    system_prompt = getattr(module, "SYSTEM_PROMPT", None)
    print(f"[Runner] Running {agent_id} for {user_id}...")

    if dry_run:
        print(f"[Runner] DRY RUN — prompt length: {len(prompt)}")
        return True

    try:
        response = utils.completion(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=120
        )
    except Exception as e:
        print(f"[Runner] LLM error for {agent_id}/{user_id}: {e}")
        return False

    try:
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        data = json.loads(text)
        message = data.get("message", "").strip()
        notif_type = data.get("type", f"{agent_id}_checkin")
    except Exception as e:
        print(f"[Runner] Failed to parse agent response for {agent_id}: {e} — raw: {response[:200]}")
        return False

    if not message:
        print(f"[Runner] Empty message from {agent_id} for {user_id}")
        return False

    notification = {
        "id": str(uuid.uuid4()),
        "type": notif_type,
        "agent": agent_id,
        "message": message,
        "created": _now_iso(),
        "read": False
    }

    # Re-fetch before save
    try:
        fresh = s3_storage.get_user(user_id)
        if fresh:
            user = fresh
    except Exception:
        pass

    user.setdefault("notifications", []).append(notification)
    user["notifications"] = user["notifications"][-20:]
    user.setdefault("agent_last_ran", {})[agent_id] = _now_iso()

    # Also drop the check-in into that agent's chat transcript
    try:
        import handlers
        handlers._inject_suggestion_into_chat(user, agent_id, message)
    except Exception as e:
        print(f"[Runner] chat inject failed: {e}")

    try:
        s3_storage.save_user(user_id, user)
        print(f"[Runner] Saved notification for {user_id} from {agent_id}: {message[:60]}")
        return True
    except Exception as e:
        print(f"[Runner] Failed to save for {user_id}: {e}")
        return False


def _hourly_nudge_user(user_id, user, dry_run=False):
    """One light free suggestion for a gated hourly pick (chat-bound)."""
    if dry_run:
        print(f"[Runner] DRY RUN hourly free suggestion for {user_id}")
        return
    try:
        import handlers
        # Small batch: no meta spam every hour — meta only sometimes
        handlers.generate_suggestions(
            user_id,
            max_free=1,
            include_meta=(random.random() < 0.25),
            include_profile_nudge=(random.random() < 0.35),
        )
        print(f"[Runner] Hourly free suggestion batch for {user_id}")
    except Exception as e:
        print(f"[Runner] Hourly suggestion failed for {user_id}: {e}")


def main():
    parser = argparse.ArgumentParser(description="GreenDial Agent Runner")
    parser.add_argument("--agent", help="Run only this agent (default: all agents)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without calling LLM or saving")
    parser.add_argument("--user", help="Run only for this user_id (for testing)")
    parser.add_argument(
        "--hourly",
        action="store_true",
        help="Hourly mode: random gate per user, one agent check-in max",
    )
    parser.add_argument(
        "--gate",
        type=float,
        default=0.2,
        help="Probability a user is selected in --hourly mode (default 0.2)",
    )
    args = parser.parse_args()

    target_agent = args.agent
    dry_run = args.dry_run
    target_user = args.user
    hourly = args.hourly
    gate = max(0.0, min(1.0, args.gate))

    print(f"[Runner] Starting at {_now_iso()} hourly={hourly} gate={gate}")
    if target_agent:
        print(f"[Runner] Agent filter: {target_agent}")
    if dry_run:
        print("[Runner] DRY RUN mode")

    users = _load_all_users()
    print(f"[Runner] Loaded {len(users)} users")

    ran = 0
    skipped = 0
    gated_out = 0

    for user_id, user in users:
        if target_user and user_id != target_user:
            continue

        if not user.get("settings", {}).get("notifications_enabled", True):
            continue

        subscriptions = _get_user_agent_subscriptions(user)
        if not subscriptions:
            continue

        if hourly:
            # ~20% of users each hour → continual feed without overload
            if random.random() >= gate:
                gated_out += 1
                continue

            candidates = [
                a for a in subscriptions
                if not target_agent or a == target_agent
            ]
            # Shorter debounce in hourly mode (4h) so variety across the day
            candidates = [
                a for a in candidates
                if not _was_run_recently(user, a, hours=4)
            ]
            if not candidates:
                skipped += 1
                continue

            agent_id = random.choice(candidates)
            if run_agent_for_user(user_id, user, agent_id, dry_run=dry_run):
                ran += 1
            # ~half the time also drop a free chat suggestion / profile nudge
            if random.random() < 0.5:
                _hourly_nudge_user(user_id, user, dry_run=dry_run)
            continue

        # Full daily mode — every agent, cadence-gated
        for agent_id in subscriptions:
            if target_agent and agent_id != target_agent:
                continue

            if _was_run_recently(user, agent_id, hours=_agent_cadence_hours(agent_id)):
                print(f"[Runner] Skipping {agent_id} for {user_id} — ran within cadence window")
                skipped += 1
                continue

            if run_agent_for_user(user_id, user, agent_id, dry_run=dry_run):
                ran += 1

    print(f"[Runner] Done. Ran: {ran}, Skipped: {skipped}, Gated-out: {gated_out}")


if __name__ == "__main__":
    main()
