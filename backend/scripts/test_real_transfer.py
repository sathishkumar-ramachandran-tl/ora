"""Real end-to-end test: create a second wallet (standing in for 'the provider's
wallet'), then transfer 1 testnet USDC to it from our funded Arc Testnet wallet, using
Ora's own circle_client.py exactly as payments/service.py would call it."""
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
    usdc_token_address=os.environ["CIRCLE_USDC_TOKEN_ADDRESS"],
)

print("Creating destination wallet (the 'provider')...")
dest_info = client.create_wallet(workspace_id="ora-demo-provider")
print("Destination address:", dest_info.address)

SOURCE_WALLET_ID = "46b2f541-e25f-5df9-bc35-57d458583947"
SOURCE_ADDRESS = "0xf6b16105783cd7c15b093485081ebb04af0e6f17"

print("\nSending 1 USDC from", SOURCE_ADDRESS, "to", dest_info.address, "...")
result = client.create_payment(
    circle_wallet_id=SOURCE_WALLET_ID,
    from_address=SOURCE_ADDRESS,
    to_address=dest_info.address,
    amount_usdc=1.0,
    chain="ARC-TESTNET",
    idempotency_key="ora-real-transfer-test-1",
)

print("\n--- Result ---")
print("Transaction ID:", result.circle_transaction_id)
print("Status:", result.status)
print("Transaction hash:", result.transaction_hash)
print("Explorer URL:", result.explorer_url)
