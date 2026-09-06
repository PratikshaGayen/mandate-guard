"""Deploy MandateGuard to the configured network.

Usage:
    python deploy/deploy_mandate_guard.py [--contract contracts/mandate_guard.py]

Uses genlayer_py directly. The `genlayer deploy` JS CLI is broken against
studionet (viem decode error "Position 32 is out of bounds" after the
transaction is accepted — see PROGRESS.md CP2b/CP4); the Python SDK path is
verified working and reaches real multi-validator consensus.

The default account comes from the genlayer CLI configuration via gltest.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gltest_cli.config.general import get_general_config  # noqa: E402
from gltest_cli.config.plugin import PluginConfig  # noqa: E402
from gltest_cli.config.user import load_user_config  # noqa: E402
from gltest import get_default_account, get_gl_client  # noqa: E402
from gltest.utils import extract_contract_address  # noqa: E402
from genlayer_py.types.transactions import TransactionStatus  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy MandateGuard")
    parser.add_argument("--contract", default="contracts/mandate_guard.py")
    parser.add_argument("--network", default="studionet")
    args = parser.parse_args()

    general_config = get_general_config()
    general_config.user_config = load_user_config("gltest.config.yaml")
    plugin_config = PluginConfig()
    plugin_config.network_name = args.network
    general_config.plugin_config = plugin_config

    client = get_gl_client()
    account = get_default_account()
    code = Path(args.contract).read_text(encoding="utf-8")

    print(f"Network RPC: {client.chain.rpc_urls['default']['http'][0]}")
    print(f"Deployer:    {account.address}")

    tx_hash = client.deploy_contract(code=code, account=account)
    print(f"Deploy tx:   {tx_hash}")
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx_hash,
        status=TransactionStatus.ACCEPTED,
    )
    status = receipt.get("status_name")
    votes = receipt.get("last_round", {}).get("validator_votes_name")
    address = extract_contract_address(receipt)
    print(f"Status:      {status}")
    print(f"Votes:       {votes}")
    print(f"Contract:    {address}")
    print(
        json.dumps(
            {"network": args.network, "address": address, "tx": str(tx_hash), "status": status},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
