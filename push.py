"""
Web push (VAPID) helper for GreenDial.

Sending requires `pywebpush` (see requirements.txt) and VAPID keys in config.py.
Everything degrades to a safe no-op when either is missing, so importing and
calling these functions never breaks the API server.

Subscriptions live on the user record under `user['push_subscriptions']`
(a list of browser PushSubscription dicts).
"""
import json

import config

try:
    from pywebpush import webpush, WebPushException
    _HAVE_PYWEBPUSH = True
except Exception:  # pragma: no cover - optional dependency
    _HAVE_PYWEBPUSH = False


def vapid_public_key():
    return getattr(config, 'VAPID_PUBLIC_KEY', '') or ''


def push_configured():
    return bool(_HAVE_PYWEBPUSH and vapid_public_key() and getattr(config, 'VAPID_PRIVATE_KEY', ''))


def _claims():
    return {"sub": getattr(config, 'VAPID_SUBJECT', 'mailto:admin@greendial.org')}


def send_to_subscription(subscription, payload):
    """Send one push. Returns True on success, False (and prunes) on 404/410.

    `subscription` is a browser PushSubscription dict; `payload` is a dict
    ({title, body, url, tag}). Raises nothing — logs and returns a bool.
    """
    if not push_configured():
        return False
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=config.VAPID_PRIVATE_KEY,
            vapid_claims=dict(_claims()),
        )
        return True
    except WebPushException as e:
        status = getattr(getattr(e, 'response', None), 'status_code', None)
        if status in (404, 410):
            # Subscription is dead — signal the caller to drop it.
            return None
        print(f"[Push] send failed: {e}")
        return False
    except Exception as e:
        print(f"[Push] unexpected error: {e}")
        return False


def send_to_user(user, payload):
    """Send `payload` to all of a user's subscriptions, pruning dead ones.

    Mutates `user['push_subscriptions']` in place (removing 404/410 endpoints)
    and returns the number of successful sends. Caller is responsible for
    persisting the user if subscriptions changed.
    """
    subs = user.get('push_subscriptions') or []
    if not subs or not push_configured():
        return 0
    sent = 0
    keep = []
    for sub in subs:
        result = send_to_subscription(sub, payload)
        if result is None:
            continue  # dead — drop it
        keep.append(sub)
        if result:
            sent += 1
    user['push_subscriptions'] = keep
    return sent
