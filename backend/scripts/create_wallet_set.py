# Adapted from Circle's dev-controlled-wallet quickstart, trimmed to only create the
# wallet set (the actual wallet is created via our own circle_client.py instead, so
# it's attributable to Ora's own code path). Run from `backend/`:
#   python scripts/create_wallet_set.py
from circle.web3 import utils, developer_controlled_wallets
from dotenv import load_dotenv
import os
import json

load_dotenv()

client = utils.init_developer_controlled_wallets_client(
    api_key=os.getenv("CIRCLE_API_KEY"),
    entity_secret=os.getenv("CIRCLE_ENTITY_SECRET")
)

wallet_sets_api = developer_controlled_wallets.WalletSetsApi(client)

try:
    wallet_set = wallet_sets_api.create_wallet_set(
        developer_controlled_wallets.CreateWalletSetRequest.from_dict({
            "name": "Ora Agent Economy Wallet Set"
        })
    )
    print(json.dumps(json.loads(wallet_set.model_dump_json()), indent=2))

    wallet_set_id = wallet_set.data.wallet_set.actual_instance.id
    with open(".env", "a") as f:
        f.write(f"\nCIRCLE_WALLET_SET_ID={wallet_set_id}\n")
    print(f"\nCIRCLE_WALLET_SET_ID={wallet_set_id} added to .env")
except developer_controlled_wallets.ApiException as e:
    print("Exception when calling the Circle Wallets API: %s\n" % e)
