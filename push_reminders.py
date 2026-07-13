#!/usr/bin/env python3
"""
Daily check-in push reminders for GreenDial.

Sends a "time for your daily check-in" web push to every user who has at least
one push subscription and has notifications enabled. Prunes dead subscriptions.

Run from cron on the prod VM, e.g. once a day:
    0 15 * * *  cd /root/GreenDial && /root/GreenDial/venv/bin/python push_reminders.py

Requires `pywebpush` installed and VAPID keys in config.py — otherwise it
prints a notice and exits without sending (safe no-op).
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import s3_storage
import push

REMINDER = {
    "title": "GreenDial 🌿",
    "body": "Time for your daily check-in — how are you feeling today?",
    "url": "/?view=stickers",
    "tag": "greendial-checkin",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not push.push_configured():
        print("[Reminders] Push not configured (missing pywebpush or VAPID keys). Nothing sent.")
        return

    user_ids = s3_storage.list_users()
    print(f"[Reminders] Scanning {len(user_ids)} users")

    sent_users = 0
    sent_pushes = 0
    for user_id in user_ids:
        try:
            user = s3_storage.get_user(user_id)
        except Exception as e:
            print(f"[Reminders] skip {user_id}: {e}")
            continue
        if not user:
            continue
        if not user.get("settings", {}).get("notifications_enabled", True):
            continue
        subs = user.get("push_subscriptions") or []
        if not subs:
            continue

        if args.dry_run:
            print(f"[Reminders] would notify {user_id} ({len(subs)} device(s))")
            continue

        before = len(subs)
        n = push.send_to_user(user, REMINDER)
        # Persist if any dead subscriptions were pruned.
        if len(user.get("push_subscriptions") or []) != before:
            try:
                s3_storage.save_user(user_id, user)
            except Exception as e:
                print(f"[Reminders] failed to prune {user_id}: {e}")
        if n:
            sent_users += 1
            sent_pushes += n

    print(f"[Reminders] Done. Notified {sent_users} users, {sent_pushes} pushes.")


if __name__ == "__main__":
    main()
