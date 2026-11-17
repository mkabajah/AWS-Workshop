"""Safety check: make sure boto3 is talking to the local emulator, never to your real AWS account.

Every script and test in this lab calls check_emulator() first. It passes only when
  1. AWS_ENDPOINT_URL points at your own machine (127.0.0.1 or localhost), and
  2. STS answers with the emulator's account ID, 000000000000.
"""

import os
from urllib.parse import urlparse

import boto3

EMULATOR_ACCOUNT = "000000000000"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class NotTheEmulator(RuntimeError):
    """Raised when the current settings would reach real AWS."""


def check_emulator():
    """Return the account ID if we are on the emulator, otherwise raise NotTheEmulator."""
    endpoint = os.environ.get("AWS_ENDPOINT_URL", "")
    if not endpoint:
        raise NotTheEmulator("AWS_ENDPOINT_URL is not set. Run:  source labs/09-aws-emulator/emulator-env.sh")
    host = urlparse(endpoint).hostname
    if host not in LOCAL_HOSTS:
        raise NotTheEmulator(f"AWS_ENDPOINT_URL points at {host}, not at your machine. Refusing to run.")

    account = boto3.client("sts").get_caller_identity()["Account"]
    if account != EMULATOR_ACCOUNT:
        raise NotTheEmulator(
            f"STS says account {account}, not {EMULATOR_ACCOUNT}: this may be real AWS. Refusing to run."
        )
    return account
