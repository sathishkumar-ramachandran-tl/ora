"""Add an Arc Testnet wallet to our existing wallet set — Circle docs say EVM wallets
in the same set share the same address, so this should resolve to the same address
that already received the 20 testnet USDC."""
import importlib.util
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

_spec = importlib.util.spec_from_file_location(
    "circle_client",
    os.path.join(BACKEND_DIR, "app", "payments", "circle_client.py"),
)
_circle_client_module = importlib.util.module_from_spec(_spec)
sys.modules["circle_client"] = _circle_client_module
_spec.loader.exec_module(_circle_client_module)
CircleClient = _circle_client_module.CircleClient

client = CircleClient(
    api_key=os.environ["CIRCLE_API_KEY"],
    base_url=os.environ.get("CIRCLE_API_BASE_URL", "https://api-sandbox.circle.com"),
    entity_secret=os.environ["CIRCLE_ENTITY_SECRET"],
    wallet_set_id=os.environ["CIRCLE_WALLET_SET_ID"],
    default_chain="ARC-TESTNET",
)

info = client.create_wallet(workspace_id="ora-demo-workspace-arc")
print("Circle wallet ID:", info.circle_wallet_id)
print("Address:", info.address)
print("Blockchain:", info.blockchain)

balance = client.get_balance(info.circle_wallet_id, simulated=False)
print("Balance:", balance)
