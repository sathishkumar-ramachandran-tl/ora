"""Circle Agent Wallet client — the ONLY module in Ora allowed to talk to Circle.

Everything else (discovery, policy, service orchestration, routes, agent tools) calls
through the narrow interface below (get_wallet/get_balance/create_wallet/pay/get_
transaction/list_transactions) and never imports Circle SDK types directly. That
isolation is what lets Circle's API surface change without touching Ora's planning or
execution logic — see docs/ARCHITECTURE.md's dependency-direction rule.

Two modes, selected purely by configuration (same graceful-degrade shape as
billing/routes.py's _stripe() and documents/storage.py's _bucket()):

- REAL mode (CIRCLE_API_KEY set): uses Circle's official `circle-developer-controlled-
  wallets` Python SDK. The SDK re-encrypts CIRCLE_ENTITY_SECRET into a fresh, single-use
  ciphertext for every call automatically — this module never handles that encryption
  itself, deliberately, since Circle's own SDK is the source of truth for that protocol.
- SIMULATION mode (no CIRCLE_API_KEY): every wallet/transaction is a deterministic,
  clearly-flagged (`is_simulated=True`) local fixture backed by AgentWallet's own
  ledger column, so the full acquire-capability loop (policy -> payment -> provider
  call -> verification -> evidence) is exercisable end to end without live credentials.
  No code outside this file needs to know which mode is active.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from flask import current_app

logger = logging.getLogger(__name__)


class CircleClientError(Exception):
    """Raised for a failed Circle call. Callers must not assume the payment did not
    happen — check get_transaction()/list_transactions() before retrying."""


@dataclass
class WalletInfo:
    circle_wallet_id: str
    address: str
    blockchain: str
    status: str
    is_simulated: bool


@dataclass
class TransferResult:
    circle_transaction_id: str
    transaction_hash: Optional[str]
    status: str  # PENDING|CONFIRMED|FAILED
    explorer_url: Optional[str]
    is_simulated: bool


# Circle's real transaction `state` values (INITIATED -> PENDING_RISK_SCREENING ->
# PENDING -> COMPLETE, or FAILED/CANCELLED/DENIED) mapped onto the PENDING/CONFIRMED/
# FAILED/CANCELLED vocabulary used everywhere else in this module (PaymentTransaction,
# EconomicAction, the verify() gate in payments/service.py's _execute_payment). Source:
# Circle's "Send tokens across wallets" guide's terminal_states set.
_CIRCLE_TERMINAL_STATES = {"COMPLETE", "FAILED", "CANCELLED", "DENIED"}
_CIRCLE_STATE_MAP = {
    "COMPLETE": "CONFIRMED",
    "FAILED": "FAILED",
    "DENIED": "FAILED",
    "CANCELLED": "CANCELLED",
}

_EXPLORER_BASE = {
    'MATIC-AMOY': 'https://amoy.polygonscan.com/tx/',
    'ETH-SEPOLIA': 'https://sepolia.etherscan.io/tx/',
    'BASE-SEPOLIA': 'https://sepolia.basescan.org/tx/',
    'AVAX-FUJI': 'https://testnet.snowtrace.io/tx/',
    'ARC-TESTNET': 'https://testnet.arcscan.app/tx/',
    'MATIC': 'https://polygonscan.com/tx/',
    'ETH': 'https://etherscan.io/tx/',
    'BASE': 'https://basescan.org/tx/',
}


def _explorer_url(chain: str, tx_hash: str) -> str:
    base = _EXPLORER_BASE.get(chain, 'https://amoy.polygonscan.com/tx/')
    return f"{base}{tx_hash}"


def _fake_address(seed: str) -> str:
    return "0x" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:40]


def _fake_tx_hash(seed: str) -> str:
    return "0x" + hashlib.sha256((seed + str(time.time())).encode("utf-8")).hexdigest()


def _model_dict(response) -> dict:
    """Circle's Python SDK returns pydantic response models; this is the safe,
    doc-confirmed way to get a plain dict back regardless of the nested oneOf/discri-
    minated-union typing Circle uses internally."""
    return json.loads(response.model_dump_json())


class CircleClient:
    """Narrow Circle Agent Wallet interface. Construct via get_circle_client()."""

    def __init__(self, api_key: Optional[str], base_url: str, entity_secret: Optional[str],
                 wallet_set_id: Optional[str], default_chain: str,
                 usdc_token_address: Optional[str] = None):
        self._api_key = api_key
        self._base_url = base_url.rstrip('/')
        self._entity_secret = entity_secret
        self._wallet_set_id = wallet_set_id
        self._default_chain = default_chain
        self._usdc_token_address = usdc_token_address
        self.is_simulated = not bool(api_key)
        self._dcw = None  # the `developer_controlled_wallets` SDK module, once loaded
        self._sdk_client = None
        self._wallet_sets_api = None
        self._wallets_api = None
        self._transactions_api = None

    # -- SDK bootstrap (real mode only) ------------------------------------------
    def _ensure_sdk(self):
        if self._sdk_client is not None:
            return
        if not self._entity_secret:
            raise CircleClientError(
                "CIRCLE_ENTITY_SECRET is not configured — generate and register one "
                "with Circle (see register_entity_secret.py) before making real "
                "(non-simulated) calls."
            )
        from circle.web3 import utils, developer_controlled_wallets
        self._dcw = developer_controlled_wallets
        self._sdk_client = utils.init_developer_controlled_wallets_client(
            api_key=self._api_key, entity_secret=self._entity_secret,
        )
        self._wallet_sets_api = developer_controlled_wallets.WalletSetsApi(self._sdk_client)
        self._wallets_api = developer_controlled_wallets.WalletsApi(self._sdk_client)
        self._transactions_api = developer_controlled_wallets.TransactionsApi(self._sdk_client)

    # -- public interface -------------------------------------------------------

    def create_wallet(self, workspace_id: str) -> WalletInfo:
        if self.is_simulated:
            wallet_id = f"sim_wallet_{uuid.uuid4().hex[:16]}"
            address = _fake_address(f"wallet:{workspace_id}")
            logger.info("circle_wallet_simulated", extra={"workspace_id": workspace_id})
            return WalletInfo(wallet_id, address, self._default_chain, "ACTIVE", True)

        self._ensure_sdk()
        if not self._wallet_set_id:
            raise CircleClientError(
                "CIRCLE_WALLET_SET_ID is not configured — create a wallet set with "
                "Circle before creating wallets in it."
            )
        dcw = self._dcw
        try:
            response = self._wallets_api.create_wallet(
                dcw.CreateWalletRequest.from_dict({
                    "walletSetId": self._wallet_set_id,
                    "blockchains": [self._default_chain],
                    "count": 1,
                    "accountType": "EOA",
                    # refId links the Circle wallet back to the Ora workspace that owns
                    # it — confirmed field shape from Circle's "Batch-create wallets for
                    # existing users" guide (metadata: [{name, refId}], one per wallet,
                    # array length must match `count`).
                    "metadata": [{"name": f"ora-workspace-{workspace_id}", "refId": workspace_id}],
                })
            )
        except dcw.ApiException as exc:
            raise CircleClientError(str(exc)) from exc

        wallets = _model_dict(response).get("data", {}).get("wallets", [])
        if not wallets:
            raise CircleClientError("Circle did not return a wallet")
        w = wallets[0]
        return WalletInfo(w["id"], w["address"], w.get("blockchain", self._default_chain), "ACTIVE", False)

    def get_wallet(self, circle_wallet_id: str, *, fallback_address: str = "",
                    fallback_chain: str = "", simulated: bool = True) -> WalletInfo:
        if simulated or self.is_simulated:
            return WalletInfo(circle_wallet_id, fallback_address, fallback_chain or self._default_chain,
                               "ACTIVE", True)
        # Not currently called by any Ora code path (service.ensure_wallet only ever
        # calls create_wallet once and trusts its own DB row after that) and not
        # confirmed against a Circle docs example the way create_wallet/create_payment
        # are — kept for interface completeness, `id=` kwarg inferred from the
        # confirmed get_transaction(id=...) pattern.
        self._ensure_sdk()
        dcw = self._dcw
        try:
            response = self._wallets_api.get_wallet(id=circle_wallet_id)
        except dcw.ApiException as exc:
            raise CircleClientError(str(exc)) from exc
        w = _model_dict(response).get("data", {}).get("wallet", {})
        return WalletInfo(w.get("id", circle_wallet_id), w.get("address", fallback_address),
                           w.get("blockchain", fallback_chain), "ACTIVE", False)

    def get_balance(self, circle_wallet_id: str, *, simulated_balance: float = 0.0,
                     simulated: bool = True) -> dict:
        if simulated or self.is_simulated:
            return {"amount": float(simulated_balance), "currency": "USDC"}
        self._ensure_sdk()
        dcw = self._dcw
        try:
            response = self._wallets_api.list_wallet_balance(id=circle_wallet_id)
        except dcw.ApiException as exc:
            raise CircleClientError(str(exc)) from exc
        balances = _model_dict(response).get("data", {}).get("token_balances", [])
        for b in balances:
            if (b.get("token") or {}).get("symbol") == "USDC":
                return {"amount": float(b.get("amount", 0)), "currency": "USDC"}
        return {"amount": 0.0, "currency": "USDC"}

    def create_payment(self, *, circle_wallet_id: str, from_address: str, to_address: str,
                        amount_usdc: float, chain: str, idempotency_key: str) -> TransferResult:
        """Execute a USDC transfer out of the given wallet. The SDK generates its own
        idempotency key internally, so `idempotency_key` here is only used for
        simulation-mode determinism and logging."""
        if self.is_simulated:
            tx_hash = _fake_tx_hash(idempotency_key)
            circle_tx_id = f"sim_tx_{uuid.uuid4().hex[:16]}"
            logger.info("circle_payment_simulated", extra={
                "wallet_id": circle_wallet_id, "amount_usdc": amount_usdc, "to_address": to_address,
            })
            return TransferResult(circle_tx_id, tx_hash, "CONFIRMED", _explorer_url(chain, tx_hash), True)

        self._ensure_sdk()
        dcw = self._dcw
        token_address = self._usdc_token_address
        if not token_address:
            raise CircleClientError(
                f"CIRCLE_USDC_TOKEN_ADDRESS is not configured for chain {chain} — set it "
                "to the USDC contract address on that chain before making real payments."
            )

        try:
            request = dcw.CreateTransferTransactionForDeveloperRequest.from_dict({
                "walletAddress": from_address,
                "blockchain": chain,
                "destinationAddress": to_address,
                "tokenAddress": token_address,
                "amounts": [str(amount_usdc)],
                "feeLevel": "MEDIUM",
            })
            transfer_response = self._transactions_api.create_developer_transaction_transfer(request)
        except dcw.ApiException as exc:
            raise CircleClientError(str(exc)) from exc

        transfer_data = transfer_response.data.to_dict()
        tx_id = transfer_data["id"]
        raw_state = transfer_data.get("state", "INITIATED")
        # Confirmed against a live API response: this SDK version's .to_dict() returns
        # camelCase "txHash", not the snake_case "tx_hash" Circle's own docs sample
        # showed — verified by inspecting a real completed transaction directly.
        tx_hash = transfer_data.get("txHash")

        # Circle transfers settle asynchronously — a fresh transfer almost never comes
        # back COMPLETE in the initial response. Poll a bounded number of times so this
        # synchronous call still returns a definitive CONFIRMED/FAILED for typical
        # testnet confirmation times, instead of leaving the caller stuck on PENDING.
        deadline = time.monotonic() + 45
        while raw_state not in _CIRCLE_TERMINAL_STATES and time.monotonic() < deadline:
            time.sleep(3)
            try:
                poll_response = self._transactions_api.get_transaction(id=tx_id)
            except dcw.ApiException:
                break
            transaction = poll_response.data.to_dict().get("transaction", {})
            raw_state = transaction.get("state", raw_state)
            tx_hash = transaction.get("txHash") or tx_hash

        status = _CIRCLE_STATE_MAP.get(raw_state, "PENDING")
        return TransferResult(
            tx_id, tx_hash, status,
            _explorer_url(chain, tx_hash) if tx_hash else None,
            False,
        )

    def get_transaction(self, circle_transaction_id: str, *, simulated: bool = True,
                         cached: Optional[dict] = None) -> dict:
        """Poll settlement status for manual reconciliation (e.g. a REFUND_PENDING
        action). In simulation mode transfers confirm instantly at creation time, so
        this just echoes back what create_payment already returned."""
        if simulated or self.is_simulated:
            return cached or {"id": circle_transaction_id, "state": "CONFIRMED"}
        self._ensure_sdk()
        dcw = self._dcw
        try:
            response = self._transactions_api.get_transaction(id=circle_transaction_id)
        except dcw.ApiException as exc:
            raise CircleClientError(str(exc)) from exc
        tx = response.data.to_dict().get("transaction", {})
        if "state" in tx:
            tx["state"] = _CIRCLE_STATE_MAP.get(tx["state"], "PENDING")
        return tx

    def list_transactions(self, circle_wallet_id: str, *, simulated: bool = True) -> list[dict]:
        if simulated or self.is_simulated:
            return []  # simulation mode: Ora's own PaymentTransaction table is authoritative
        # Not currently called by any Ora code path (routes.py reads the local
        # PaymentTransaction table instead) and the `wallet_ids` kwarg name isn't
        # confirmed against a docs example — kept for interface completeness.
        self._ensure_sdk()
        dcw = self._dcw
        try:
            response = self._transactions_api.list_transactions(wallet_ids=[circle_wallet_id])
        except dcw.ApiException as exc:
            raise CircleClientError(str(exc)) from exc
        return _model_dict(response).get("data", {}).get("transactions", [])

    def supported_chains(self) -> list[str]:
        return list(_EXPLORER_BASE.keys())


def get_circle_client() -> CircleClient:
    """Lazy per-app singleton factory, same pattern as core/email.py's SES client.
    Cached on `current_app.extensions` (not a module global) so each Flask app instance
    — notably a fresh one per pytest function — gets a client built from its own
    config, instead of one process-wide client leaking stale config across tests.
    Always returns a usable client — falls back to simulation mode when unconfigured
    rather than returning None, because payments are the point of this feature (unlike
    Stripe billing, which is optional)."""
    existing = current_app.extensions.get("circle_client")
    if existing is not None:
        return existing
    cfg = current_app.config
    client = CircleClient(
        api_key=cfg.get("CIRCLE_API_KEY"),
        base_url=cfg.get("CIRCLE_API_BASE_URL", "https://api-sandbox.circle.com"),
        entity_secret=cfg.get("CIRCLE_ENTITY_SECRET"),
        wallet_set_id=cfg.get("CIRCLE_WALLET_SET_ID"),
        default_chain=cfg.get("CIRCLE_BLOCKCHAIN", "MATIC-AMOY"),
        usdc_token_address=cfg.get("CIRCLE_USDC_TOKEN_ADDRESS"),
    )
    if client.is_simulated:
        logger.warning("circle_client_simulation_mode", extra={
            "reason": "CIRCLE_API_KEY not set — Agent Economy runs on simulated USDC wallets/payments",
        })
    current_app.extensions["circle_client"] = client
    return client
