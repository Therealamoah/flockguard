"""Grant or revoke FlockGuard platform-admin access (the /admin console).

Usage, from backend/ with the same .env the API uses:

    python -m scripts.grant_platform_admin you@example.com
    python -m scripts.grant_platform_admin you@example.com --revoke

The person must sign out and back in (or wait up to an hour) before their
ID token carries the new claim. Deliberately a script, not an API route -
see app/core/admin_auth.py.
"""

import argparse

from firebase_admin import auth as firebase_auth

from app.core.firebase import _init_firebase_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    parser.add_argument("--revoke", action="store_true", help="remove platform-admin access instead")
    args = parser.parse_args()

    if _init_firebase_app() is None:
        raise SystemExit("Firebase Admin isn't configured - set FIREBASE_SERVICE_ACCOUNT_JSON in backend/.env")

    user = firebase_auth.get_user_by_email(args.email)
    claims = dict(user.custom_claims or {})
    if args.revoke:
        claims.pop("platform_admin", None)
    else:
        claims["platform_admin"] = True
    firebase_auth.set_custom_user_claims(user.uid, claims)
    if args.revoke:
        firebase_auth.revoke_refresh_tokens(user.uid)

    print(f"{'Revoked' if args.revoke else 'Granted'} platform admin for {args.email} (uid {user.uid}).")
    print("They need to sign out and back in for it to take effect.")


if __name__ == "__main__":
    main()
