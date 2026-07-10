#!/usr/bin/env python3
"""Mint HS256 JWTs for the local PostgREST stack (docker/local-supabase).

Stdlib only (hmac/base64/json) -- no PyJWT dependency, so it runs with
whatever python3 the operator has on hand.

Usage:
    python3 docker/local-supabase/mint_supabase_jwt.py --secret <JWT_SECRET>

Prints one token per role (service_role and anon by default) as env-file
lines ready to paste into web_ui_hosted/.env.local.
"""
import argparse
import base64
import hashlib
import hmac
import json
import time


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def mint(secret: str, role: str, days: int, issuer: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"role": role, "iss": issuer, "iat": now, "exp": now + days * 86400}
    signing_input = "{}.{}".format(
        b64url(json.dumps(header, separators=(",", ":")).encode()),
        b64url(json.dumps(payload, separators=(",", ":")).encode()),
    )
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(sig)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secret", required=True, help="JWT_SECRET from docker/local-supabase/.env")
    parser.add_argument("--roles", nargs="+", default=["service_role", "anon"])
    parser.add_argument(
        "--days",
        type=int,
        default=3650,
        help="Token lifetime in days (default ~10y -- this stack is local-only and trusted)",
    )
    parser.add_argument("--issuer", default="podcast-local")
    args = parser.parse_args()

    env_names = {"service_role": "SUPABASE_SERVICE_ROLE"}

    for role in args.roles:
        token = mint(args.secret, role, args.days, args.issuer)
        env_name = env_names.get(role, f"SUPABASE_{role.upper()}_KEY")
        print(f"# role={role}")
        print(f"{env_name}={token}")
        print()


if __name__ == "__main__":
    main()
