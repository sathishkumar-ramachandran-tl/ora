# Circle's official entity-secret registration script (from their "How-to: Generate
# and register your entity secret" guide), kept verbatim. Run from the `backend/`
# directory so its relative `.env`/`./recovery` paths land in the right place:
#   python scripts/register_entity_secret.py
import os
import re

from dotenv import load_dotenv
from circle.web3 import utils

load_dotenv()

api_key = os.environ.get("CIRCLE_API_KEY")
if not api_key:
    raise RuntimeError("CIRCLE_API_KEY is required. Set it in .env first.")

existing_env = ""
if os.path.exists(".env"):
    with open(".env", "r") as f:
        existing_env = f.read()

if re.search(r"^CIRCLE_ENTITY_SECRET=", existing_env, re.MULTILINE):
    raise RuntimeError(
        "CIRCLE_ENTITY_SECRET already exists in .env. Refusing to overwrite it."
    )

entity_secret = os.urandom(32).hex()
recovery_file_path = "./recovery"

os.makedirs(recovery_file_path, exist_ok=True)

utils.register_entity_secret_ciphertext(
    api_key=api_key,
    entity_secret=entity_secret,
    recoveryFileDownloadPath=recovery_file_path,
)

with open(".env", "a") as f:
    f.write(f"\nCIRCLE_ENTITY_SECRET={entity_secret}\n")

print("Entity secret registered.")
print(f"Recovery file saved to a new file in: {recovery_file_path}")
print("CIRCLE_ENTITY_SECRET added to .env")
