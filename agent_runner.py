"""
GreenDial Agent Runner
Cron script: run subscribed health agents for all active users.

Usage:
  python3 agent_runner.py [--agent diet] [--dry-run]

Crontab examples (on production VM):
  # Run all agents every morning at 8 AM UTC
  0 8 * * * /root/GreenDial/venv/bin/python /root/GreenDial/agent_runner.py >> /var/log/greendial_agents.log 2>&1

  # Run sleep agent at 10 PM UTC (bedtime reminder)
  0 22 * * * /root/GreenDial/venv/bin/python /root/GreenDial/agent_runner.py --agent sleep >> /var/log/greendial_agents.log 2>&1
"""

import sys
import json
import uuid
import argparse
from datetime import datetime, timedelta

# Ensure we can import from the project root
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import s3_storage
import utils
from prompts.agents import REGISTRY, ALL_AGENT_IDS


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
    """Return list of agent_ids the user has subscribed to."""
    settings = user.get("settings", {})
    subs = settings.get("agent_subscriptions", [])
    # Default: no subscriptions unless explicitly set
    return [aid for aid in subs if aid in REGISTRY]


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
    """Debounce window for this agent. Agents may declare CRON_CADENCE_HOURS
    (e.g. 164 for weekly synthesis); default is 20h (daily check-ins)."""
    module = REGISTRY.get(agent_id)
    return getattr(module, "CRON_CADENCE_HOURS", 20) if module else 20


def run_agent_for_user(user_id, user, agent_id, dry_run=False):
    """Run a single agent for a single user; append notification to user record."""
    module = REGISTRY.get(agent_id)
    if not module:
        print(f"[Runner] Unknown agent: {agent_id}")
        return

    profile = user.get("profile", {})
    transcript = user.get("transcript", "")
    settings = user.get("settings", {})

    # Build the cron prompt
    template = getattr(module, "CRON_PROMPT_TEMPLATE", None)
    if not template:
        print(f"[Runner] Agent {agent_id} has no CRON_PROMPT_TEMPLATE — skipping")
        return

    if agent_id == "custom":
        custom_prompt = settings.get("custom_agent_prompt", "")
        prompt = template.format(
            custom_prompt=custom_prompt,
            profile_json=json.dumps(profile, indent=2),
            transcript=transcript[-1500:] if transcript else ""
        )
    else:
        prompt = template.format(
            profile_json=json.dumps(profile, indent=2),
            transcript=transcript[-1500:] if transcript else ""
        )

    # Ground the check-in in tracked data so agents can reference real trends
    # ("your sleep has averaged 6.4h this week") instead of generic tips
    history_summary = utils.summarize_history(user, days=14)
    if history_summary:
        prompt += f"\n\nRECENT HEALTH HISTORY (last 14 days, tracked data):\n{history_summary}\n\nIf the history shows a clear trend or correlation, reference it specifically in your message."

    system_prompt = getattr(module, "SYSTEM_PROMPT", None)

    print(f"[Runner] Running {agent_id} for {user_id}...")

    if dry_run:
        print(f"[Runner] DRY RUN — prompt length: {len(prompt)}")
        return

    try:
        response = utils.completion(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=120
        )
    except Exception as e:
        print(f"[Runner] LLM error for {agent_id}/{user_id}: {e}")
        return

    # Parse the JSON response
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
        return

    if not message:
        print(f"[Runner] Empty message from {agent_id} for {user_id}")
        return

    # Append notification to user record
    notification = {
        "id": str(uuid.uuid4()),
        "type": notif_type,
        "agent": agent_id,
        "message": message,
        "created": _now_iso(),
        "read": False
    }

    user.setdefault("notifications", []).append(notification)
    user["notifications"] = user["notifications"][-20:]  # keep last 20

    user.setdefault("agent_last_ran", {})[agent_id] = _now_iso()

    try:
        s3_storage.save_user(user_id, user)
        print(f"[Runner] Saved notification for {user_id} from {agent_id}: {message[:60]}")
    except Exception as e:
        print(f"[Runner] Failed to save for {user_id}: {e}")


def main():
    parser = argparse.ArgumentParser(description="GreenDial Agent Runner")
    parser.add_argument("--agent", help="Run only this agent (default: all subscribed agents)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without calling LLM or saving")
    parser.add_argument("--user", help="Run only for this user_id (for testing)")
    args = parser.parse_args()

    target_agent = args.agent
    dry_run = args.dry_run
    target_user = args.user

    print(f"[Runner] Starting at {_now_iso()}")
    if target_agent:
        print(f"[Runner] Agent filter: {target_agent}")
    if dry_run:
        print("[Runner] DRY RUN mode")

    users = _load_all_users()
    print(f"[Runner] Loaded {len(users)} users")

    ran = 0
    skipped = 0

    for user_id, user in users:
        if target_user and user_id != target_user:
            continue

        # Skip users who haven't enabled notifications
        if not user.get("settings", {}).get("notifications_enabled", True):
            continue

        subscriptions = _get_user_agent_subscriptions(user)
        if not subscriptions:
            continue

        for agent_id in subscriptions:
            if target_agent and agent_id != target_agent:
                continue

            if _was_run_recently(user, agent_id, hours=_agent_cadence_hours(agent_id)):
                print(f"[Runner] Skipping {agent_id} for {user_id} — ran within cadence window")
                skipped += 1
                continue

            run_agent_for_user(user_id, user, agent_id, dry_run=dry_run)
            ran += 1

    print(f"[Runner] Done. Ran: {ran}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
