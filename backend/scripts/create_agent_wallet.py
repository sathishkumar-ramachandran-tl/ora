"""One-off: create the real Circle agent wallet using Ora's own CircleClient (not a
throwaway script), so the resulting wallet genuinely comes from the app's integration
code. Doesn't require Flask/Postgres — CircleClient.create_wallet() only needs Circle
credentials, which we pass in directly.

Loads circle_client.py directly (bypassing `import app...`) since that package's
__init__.py pulls in the full Flask/SQLAlchemy stack, which isn't installed in this
lightweight verification environment — circle_client.py itself has no relative
imports, so this is safe.
"""
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
sys.modules["circle_client"] = _circle_client_module  # dataclass needs this registered first
_spec.loader.exec_module(_circle_client_module)
CircleClient = _circle_client_module.CircleClient

client = CircleClient(
    api_key=os.environ["CIRCLE_API_KEY"],
    base_url=os.environ.get("CIRCLE_API_BASE_URL", "https://api-sandbox.circle.com"),
    entity_secret=os.environ["CIRCLE_ENTITY_SECRET"],
    wallet_set_id=os.environ["CIRCLE_WALLET_SET_ID"],
    default_chain=os.environ.get("CIRCLE_BLOCKCHAIN", "MATIC-AMOY"),
)

info = client.create_wallet(workspace_id="ora-demo-workspace")
print("Circle wallet ID:", info.circle_wallet_id)
print("Address:", info.address)
print("Blockchain:", info.blockchain)
print("Simulated:", info.is_simulated)
