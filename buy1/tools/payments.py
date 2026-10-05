"""Simulated PSP that mimics a hosted-payment-page + tokenization flow.

No cardholder data (PAN, expiry, CVV) is ever accepted by these tools; all
card entry happens on a hosted page owned by the (simulated) payment
processor. The agent only sees a session identifier and, later, a token
returned by the hosted page.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any


DEFAULT_HOSTED_PAGE_URL = "https://pay.example.com/checkout"
ALLOWED_CURRENCIES = {"USD"}
ALLOWED_FREQUENCIES = {"Annual", "Semi-Annual", "Quarterly", "Monthly"}
SESSION_TTL_MINUTES = 15

_SESSIONS: dict[str, dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hosted_page_base_url() -> str:
    return os.getenv("PAYMENT_HOSTED_PAGE_URL", DEFAULT_HOSTED_PAGE_URL).rstrip("/")


def create_payment_session(
    quote_reference: str,
    amount_cents: int,
    currency: str,
    payment_frequency: str,
) -> dict[str, Any]:
    """Start a simulated hosted-page payment session for the quoted premium.

    Args:
        quote_reference:   Staging key that identifies this quote (e.g. STG-XXXXXX).
                            Do NOT pass a policy_id: no policy exists yet and one
                            will be issued only after payment is approved.
        amount_cents:      Installment amount to charge, in the smallest currency unit.
        currency:          ISO-4217 currency code (only ``USD`` is supported today).
        payment_frequency: One of Annual, Semi-Annual, Quarterly, Monthly.

    Returns:
        SUCCESS with ``payment_session_id``, ``hosted_page_url``, ``expires_at``,
        and the exact ``amount_cents`` / ``currency`` echoed back. The agent
        MUST send the customer to ``hosted_page_url`` and MUST NOT ask for
        card number, expiry, or CVV in chat.
    """
    quote_reference = (quote_reference or "").strip()
    currency = (currency or "").strip().upper()
    frequency = (payment_frequency or "").strip().title()

    if not quote_reference:
        return {"status": "ERROR", "message": "quote_reference is required."}
    try:
        amount = int(amount_cents)
    except (TypeError, ValueError):
        return {"status": "ERROR", "message": "amount_cents must be an integer."}
    if amount <= 0:
        return {"status": "ERROR", "message": "amount_cents must be positive."}
    if currency not in ALLOWED_CURRENCIES:
        return {"status": "ERROR", "message": f"currency must be one of {sorted(ALLOWED_CURRENCIES)}."}
    if frequency not in ALLOWED_FREQUENCIES:
        return {
            "status": "ERROR",
            "message": f"payment_frequency must be one of {sorted(ALLOWED_FREQUENCIES)}.",
        }

    session_id = f"pay_sess_{secrets.token_hex(8)}"
    expires_at = _now() + timedelta(minutes=SESSION_TTL_MINUTES)
    _SESSIONS[session_id] = {
        "quote_reference": quote_reference,
        "amount_cents": amount,
        "currency": currency,
        "payment_frequency": frequency,
        "expires_at": expires_at,
        "consumed": False,
    }
    return {
        "status": "SUCCESS",
        "payment_session_id": session_id,
        "hosted_page_url": f"{_hosted_page_base_url()}?session={session_id}",
        "amount_cents": amount,
        "currency": currency,
        "payment_frequency": frequency,
        "expires_at": expires_at.isoformat(),
        "message": (
            "Prototype simulator: ask the customer to pick APPROVE, DECLINE, "
            "or EXPIRE and call simulate_payment_outcome. Never collect card "
            "number, expiry, CVV, or cardholder name in chat."
        ),
    }


def verify_payment_token(
    payment_session_id: str,
    payment_token: str,
    expected_amount_cents: int,
) -> dict[str, Any]:
    """Verify a token returned by the (simulated) hosted payment page.

    Simulated token conventions (returned by the hosted page in demo mode):

    * ``tok_approved_<session_id>``  -> APPROVED
    * ``tok_declined_<session_id>``  -> DECLINED
    * ``tok_expired_<session_id>``   -> EXPIRED_CARD
    * ``tok_pending_<session_id>``   -> PENDING

    Args:
        payment_session_id:    ID from ``create_payment_session``.
        payment_token:         Token returned by the hosted payment page.
        expected_amount_cents: The installment amount the customer agreed to pay.
    """
    session_id = (payment_session_id or "").strip()
    token = (payment_token or "").strip()

    session = _SESSIONS.get(session_id)
    if session is None:
        return {"status": "ERROR", "message": "Unknown payment session."}
    if session["consumed"]:
        return {"status": "ERROR", "message": "This payment session has already been used."}
    if _now() > session["expires_at"]:
        return {"status": "EXPIRED_SESSION", "message": "Payment session expired; create a new one."}

    try:
        expected = int(expected_amount_cents)
    except (TypeError, ValueError):
        return {"status": "ERROR", "message": "expected_amount_cents must be an integer."}
    if expected != session["amount_cents"]:
        return {
            "status": "ERROR",
            "message": "expected_amount_cents does not match the session amount.",
        }

    if not token.endswith(session_id):
        return {"status": "ERROR", "message": "Token does not belong to this payment session."}

    outcomes = {
        "tok_approved_": ("APPROVED", "Payment authorised by processor."),
        "tok_declined_": ("DECLINED", "Payment declined by processor."),
        "tok_expired_": ("EXPIRED_CARD", "Card expired; ask the customer to try another card."),
        "tok_pending_": ("PENDING", "Payment pending; wait for the processor callback."),
    }
    for prefix, (status, message) in outcomes.items():
        if token.startswith(prefix):
            if status in {"APPROVED", "DECLINED", "EXPIRED_CARD"}:
                session["consumed"] = True
            return {
                "status": status,
                "message": message,
                "payment_session_id": session_id,
                "quote_reference": session["quote_reference"],
                "amount_cents": session["amount_cents"],
                "currency": session["currency"],
                "payment_frequency": session["payment_frequency"],
            }

    return {"status": "ERROR", "message": "Unrecognised payment token."}


OUTCOME_WORDS = {
    "APPROVE": ("APPROVED", "Payment authorised (simulated)."),
    "APPROVED": ("APPROVED", "Payment authorised (simulated)."),
    "DECLINE": ("DECLINED", "Payment declined (simulated)."),
    "DECLINED": ("DECLINED", "Payment declined (simulated)."),
    "EXPIRE": ("EXPIRED_CARD", "Card expired (simulated)."),
    "EXPIRED": ("EXPIRED_CARD", "Card expired (simulated)."),
}


def simulate_payment_outcome(
    payment_session_id: str,
    outcome_choice: str,
    expected_amount_cents: int,
) -> dict[str, Any]:
    """Process an in-chat simulated payment outcome without any card data.

    The agent asks the customer to pick a named test outcome
    (``APPROVE``, ``DECLINE``, or ``EXPIRE``) and passes it here. No PAN,
    expiry, CVV, or cardholder name is accepted. On ``APPROVE`` the session
    is consumed and a simulated ``transaction_id`` is returned so the agent
    can proceed to policy creation.
    """
    session_id = (payment_session_id or "").strip()
    choice = (outcome_choice or "").strip().upper()

    session = _SESSIONS.get(session_id)
    if session is None:
        return {"status": "ERROR", "message": "Unknown payment session."}
    if session["consumed"]:
        return {"status": "ERROR", "message": "This payment session has already been used."}
    if _now() > session["expires_at"]:
        return {"status": "EXPIRED_SESSION", "message": "Payment session expired; create a new one."}

    try:
        expected = int(expected_amount_cents)
    except (TypeError, ValueError):
        return {"status": "ERROR", "message": "expected_amount_cents must be an integer."}
    if expected != session["amount_cents"]:
        return {
            "status": "ERROR",
            "message": "expected_amount_cents does not match the session amount.",
        }

    if choice not in OUTCOME_WORDS:
        return {
            "status": "ERROR",
            "message": "outcome_choice must be APPROVE, DECLINE, or EXPIRE.",
        }

    status, message = OUTCOME_WORDS[choice]
    session["consumed"] = True
    transaction_id = (
        f"TXN-{_now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
    )
    return {
        "status": status,
        "message": message,
        "payment_session_id": session_id,
        "quote_reference": session["quote_reference"],
        "amount_cents": session["amount_cents"],
        "currency": session["currency"],
        "payment_frequency": session["payment_frequency"],
        "transaction_id": transaction_id,
        "simulated": True,
    }


ALLOWED_PAYMENT_METHOD_TYPES = {"Visa", "Mastercard", "American Express", "Discover"}
ALLOWED_RESULT_STATUSES = {"APPROVED", "DECLINED"}


def record_payment_result(
    payment_session_id: str,
    payment_status: str,
    transaction_id: str,
    payment_method_type: str,
    card_last4: str,
    expected_amount_cents: int,
) -> dict[str, Any]:
    """Record the non-sensitive result returned by an external secure payment component.

    This tool is the ONLY sanctioned way for a real (non-simulated) payment
    outcome to enter the agent. It is designed so raw cardholder data cannot
    be passed in: it accepts ``card_last4`` (exactly 4 digits) and a
    ``payment_method_type`` label, and nothing else about the card.

    Full card number, CVV, expiry, cardholder name, and billing ZIP MUST
    be collected and tokenised by a PCI-compliant payment widget outside
    the LLM; the widget then calls this tool with only the fields below.
    """
    session_id = (payment_session_id or "").strip()
    status = (payment_status or "").strip().upper()
    txn = (transaction_id or "").strip()
    method = (payment_method_type or "").strip().title().replace("Mastercard", "Mastercard")
    last4 = (card_last4 or "").strip()

    session = _SESSIONS.get(session_id)
    if session is None:
        return {"status": "ERROR", "message": "Unknown payment session."}
    if session["consumed"]:
        return {"status": "ERROR", "message": "This payment session has already been used."}
    if _now() > session["expires_at"]:
        return {"status": "EXPIRED_SESSION", "message": "Payment session expired; create a new one."}

    try:
        expected = int(expected_amount_cents)
    except (TypeError, ValueError):
        return {"status": "ERROR", "message": "expected_amount_cents must be an integer."}
    if expected != session["amount_cents"]:
        return {
            "status": "ERROR",
            "message": "expected_amount_cents does not match the session amount.",
        }

    if status not in ALLOWED_RESULT_STATUSES:
        return {
            "status": "ERROR",
            "message": "payment_status must be APPROVED or DECLINED.",
        }
    if not txn:
        return {"status": "ERROR", "message": "transaction_id is required."}
    if method not in ALLOWED_PAYMENT_METHOD_TYPES:
        return {
            "status": "ERROR",
            "message": f"payment_method_type must be one of {sorted(ALLOWED_PAYMENT_METHOD_TYPES)}.",
        }
    if not (len(last4) == 4 and last4.isdigit()):
        return {
            "status": "ERROR",
            "message": "card_last4 must be exactly 4 digits (the final 4 of the card number).",
        }
    if len(last4) != len(card_last4.strip()):  # defensive: catches "4242 " etc.
        return {"status": "ERROR", "message": "card_last4 must contain only digits."}

    session["consumed"] = True
    return {
        "status": status,
        "message": (
            "Payment authorised by the external secure payment component."
            if status == "APPROVED"
            else "Payment declined by the external secure payment component."
        ),
        "payment_session_id": session_id,
        "quote_reference": session["quote_reference"],
        "amount_cents": session["amount_cents"],
        "currency": session["currency"],
        "payment_frequency": session["payment_frequency"],
        "transaction_id": txn,
        "payment_method_type": method,
        "card_last4": last4,
        "simulated": False,
    }
