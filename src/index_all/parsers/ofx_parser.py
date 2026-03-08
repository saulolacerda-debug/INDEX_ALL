from __future__ import annotations

from pathlib import Path

from ofxparse import OfxParser


def parse_ofx(path: Path) -> dict:
    with path.open("rb") as file_obj:
        ofx = OfxParser.parse(file_obj)

    blocks = []
    account = getattr(ofx, "account", None)
    statement = getattr(account, "statement", None) if account else None
    transactions = statement.transactions if statement else []

    for idx, txn in enumerate(transactions[:200], start=1):
        text = " | ".join(
            [
                str(getattr(txn, "date", "")),
                str(getattr(txn, "type", "")),
                str(getattr(txn, "amount", "")),
                str(getattr(txn, "memo", "")),
            ]
        )
        blocks.append(
            {
                "id": f"block_{idx:04d}",
                "kind": "transaction",
                "title": None,
                "text": text,
                "locator": {"page": None, "sheet": None, "line_start": idx, "line_end": idx},
                "extra": {
                    "date": str(getattr(txn, "date", "")),
                    "type": str(getattr(txn, "type", "")),
                    "amount": str(getattr(txn, "amount", "")),
                    "memo": str(getattr(txn, "memo", "")),
                },
            }
        )

    return {
        "content": {
            "blocks": blocks,
            "parser_metadata": {
                "bank_id": str(getattr(account, "routing_number", "")) if account else "",
                "account_id": getattr(account, "account_id", "") if account else "",
                "transaction_count": len(transactions),
            },
        }
    }
