"""Instrument identity = exchange + symbol. Never guessed, always declared."""

from __future__ import annotations

import re

from ..core.errors import IngestError

_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9._&-]*$")
_EXCHANGE = re.compile(r"^[A-Z0-9_]+$")
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def normalise_exchange(value) -> str:
    text = ("" if value is None else str(value)).strip().upper()
    if not text:
        raise IngestError("The exchange is empty.", code="E_INSTRUMENT_REQUIRED", check="instrument_declared",
                          action="Declare the exchange in the source profile (fixed value, column or file-name pattern).")
    if not _EXCHANGE.match(text) or len(text) > 20 or text in _WINDOWS_RESERVED:
        raise IngestError(f"The exchange code {text!r} is not valid (letters, digits and underscore only).",
                          code="E_INSTRUMENT_INVALID", check="instrument_declared")
    return text


def normalise_symbol(value) -> str:
    text = ("" if value is None else str(value)).strip().upper()
    if not text:
        raise IngestError("The symbol is empty.", code="E_INSTRUMENT_REQUIRED", check="instrument_declared",
                          action="Declare the symbol in the source profile (fixed value, column, file-name pattern) "
                                 "or supply it when ingesting.")
    base = text.split(".")[0]
    if (not _SYMBOL.match(text) or len(text) > 40 or text.endswith(".") or base in _WINDOWS_RESERVED):
        raise IngestError(
            f"The symbol {text!r} is not valid. Allowed: letters, digits and . _ & - (it must start with a letter or digit).",
            code="E_INSTRUMENT_INVALID", check="instrument_declared")
    return text


def instrument_key(exchange: str, symbol: str) -> str:
    return f"{exchange}:{symbol}"


def get_or_create_instrument(conn, exchange: str, symbol: str) -> tuple[int, bool]:
    """Return (instrument_id, created). Must be called inside a write transaction."""
    row = conn.execute("SELECT instrument_id FROM instruments WHERE exchange = ? AND symbol = ?",
                       (exchange, symbol)).fetchone()
    if row is not None:
        return int(row["instrument_id"]), False
    cur = conn.execute("INSERT INTO instruments(exchange, symbol) VALUES (?, ?)", (exchange, symbol))
    return int(cur.lastrowid), True
