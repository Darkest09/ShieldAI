"""Generate a labelled synthetic Nepali-banking PII dataset for evaluation.

No real customer data is used (Research Ethics §15 of the proposal). Each record
is a prompt plus the gold-standard PII spans it contains, so detection accuracy,
precision/recall, and false-positive/negative rates can be measured.

Usage:
    python scripts/generate_synthetic_dataset.py --n 300 --out data/eval/synthetic_banking.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

FIRST = ["Sarita", "Bishal", "Anita", "Ramesh", "Sujata", "Prakash", "Nisha",
         "Deepak", "Gita", "Hari", "Manish", "Sabina", "Rajan", "Puja"]
LAST = ["Shrestha", "Gurung", "Tamang", "Adhikari", "Karki", "Thapa", "Rai",
        "Magar", "Bhattarai", "Lama", "Maharjan", "Poudel"]
EMAIL_DOMAINS = ["gmail.com", "outlook.com", "nabilbank.com", "globalimebank.com"]

# Templates: each is (sentence_with_{placeholders}, list-of-placeholder-entity-types)
TEMPLATES = [
    ("Please draft an email to {person} at {email} about their loan.", ["PERSON", "EMAIL_ADDRESS"]),
    ("Customer {person} (citizenship {citizenship}) requested a statement.", ["PERSON", "NP_CITIZENSHIP_NUMBER"]),
    ("Call the client on {mobile} regarding KYC for account {account}.", ["NP_MOBILE_NUMBER", "BANK_ACCOUNT_NUMBER"]),
    ("Refund the charge on card {card} for {person}.", ["CREDIT_CARD", "PERSON"]),
    ("Wire funds via SWIFT {swift} to settle the remittance.", ["SWIFT_BIC_CODE"]),
    ("Summarise the dispute: email {email}, phone {mobile}.", ["EMAIL_ADDRESS", "NP_MOBILE_NUMBER"]),
    ("The teller logged account {account} for {person}, citizenship {citizenship}.",
     ["BANK_ACCOUNT_NUMBER", "PERSON", "NP_CITIZENSHIP_NUMBER"]),
    ("No sensitive data here — just summarise our quarterly branch performance.", []),
    ("Translate this polite reminder about an overdue payment into Nepali.", []),
    ("Internal note: rotate the API secret {stripe} after the audit.", ["STRIPE_API_KEY"]),
]


def _person(rng): return f"{rng.choice(FIRST)} {rng.choice(LAST)}"
def _email(rng): return f"{rng.choice(FIRST).lower()}.{rng.choice(LAST).lower()}@{rng.choice(EMAIL_DOMAINS)}"
def _citizenship(rng): return f"{rng.randint(10,99)}-{rng.randint(10,99)}-{rng.randint(10,99)}-{rng.randint(10000,99999)}"
def _mobile(rng): return f"{rng.choice(['98','97'])}{rng.randint(10**7,10**8-1)}"
def _account(rng): return str(rng.randint(10**10, 10**12 - 1))


def _card(rng):
    """A Luhn-valid 16-digit test card (so realistic detectors accept it)."""
    digits = [4] + [rng.randint(0, 9) for _ in range(14)]
    # Compute Luhn check digit.
    s = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:  # positions that will be doubled once check digit appended
            d = d * 2
            if d > 9:
                d -= 9
        s += d
    check = (10 - (s % 10)) % 10
    return "".join(str(d) for d in digits) + str(check)
def _swift(rng): return f"{''.join(rng.choice('ABCDEFGHJKLMNP') for _ in range(4))}NP{rng.choice('AB')}{rng.choice('XY')}"
def _stripe(rng): return "sk_live_" + "".join(rng.choice("0123456789abcdefABCDEF") for _ in range(24))

_GEN = {
    "PERSON": _person, "EMAIL_ADDRESS": _email, "NP_CITIZENSHIP_NUMBER": _citizenship,
    "NP_MOBILE_NUMBER": _mobile, "BANK_ACCOUNT_NUMBER": _account, "CREDIT_CARD": _card,
    "SWIFT_BIC_CODE": _swift, "STRIPE_API_KEY": _stripe,
}


def build_record(rng: random.Random) -> dict:
    template, types = rng.choice(TEMPLATES)
    # Map each placeholder name to a generated value, tracking entity types in order.
    import re

    placeholder_order = re.findall(r"\{(\w+)\}", template)
    ph_to_type = {
        "person": "PERSON", "email": "EMAIL_ADDRESS", "citizenship": "NP_CITIZENSHIP_NUMBER",
        "mobile": "NP_MOBILE_NUMBER", "account": "BANK_ACCOUNT_NUMBER", "card": "CREDIT_CARD",
        "swift": "SWIFT_BIC_CODE", "stripe": "STRIPE_API_KEY",
    }
    values = {ph: _GEN[ph_to_type[ph]](rng) for ph in placeholder_order}
    text = template.format(**values)

    entities = []
    for ph in placeholder_order:
        val = values[ph]
        start = text.index(val)
        entities.append({"start": start, "end": start + len(val),
                         "type": ph_to_type[ph], "value": val})
    return {"text": text, "entities": entities}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/eval/synthetic_banking.jsonl")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for _ in range(args.n):
            f.write(json.dumps(build_record(rng), ensure_ascii=False) + "\n")
    print(f"Wrote {args.n} labelled records to {out}")


if __name__ == "__main__":
    main()
