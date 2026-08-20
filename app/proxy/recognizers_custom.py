"""Custom Presidio pattern recognizers for regional PII and API keys."""

from presidio_analyzer import Pattern, PatternRecognizer


def citizenship_nepal_recognizer() -> PatternRecognizer:
    """Strict Nepalese citizenship: exactly XX-XX-XX-XXXXX (digits)."""
    return PatternRecognizer(
        supported_entity="NP_CITIZENSHIP_NUMBER",
        supported_language="en",
        patterns=[
            Pattern(
                name="np_citizenship_strict",
                regex=r"\b\d{2}-\d{2}-\d{2}-\d{5}\b",
                score=0.95,
            ),
        ],
        context=["citizenship", "nagarik", "nepal"],
    )


def nepal_mobile_recognizer() -> PatternRecognizer:
    """Ncell/NTC patterns: numbers starting with 97 or 98 (10-digit local or with +977)."""
    return PatternRecognizer(
        supported_entity="NP_MOBILE_NUMBER",
        supported_language="en",
        patterns=[
            Pattern(
                name="np_mobile_intl",
                regex=r"\b\+?977[-\s]?(?:97|98)\d{8}\b",
                score=0.92,
            ),
            Pattern(
                name="np_mobile_local",
                regex=r"\b(?:97|98)\d{8}\b",
                score=0.88,
            ),
        ],
        context=["ncell", "ntc", "nepal", "mobile", "phone"],
    )


def aws_access_key_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="AWS_ACCESS_KEY_ID",
        supported_language="en",
        patterns=[
            Pattern(name="akia_iam_std", regex=r"\bAKIA[0-9A-Z]{16}\b", score=0.97),
            Pattern(
                name="akia_partial",
                regex=r"\bAKIA[0-9A-Z]{14,15}\b",
                score=0.88,
            ),
        ],
        context=["aws", "access", "key", "secret"],
    )


def aws_secret_key_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="AWS_SECRET_ACCESS_KEY",
        supported_language="en",
        patterns=[
            Pattern(
                name="aws_secret_40",
                regex=r"\b[A-Za-z0-9/+=]{40}\b",
                score=0.55,
            ),
        ],
        context=["aws", "secret"],
    )


def stripe_key_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="STRIPE_API_KEY",
        supported_language="en",
        patterns=[
            Pattern(
                name="sk_live",
                regex=r"\bsk_live_[0-9a-zA-Z]{24,}\b",
                score=0.95,
            ),
            Pattern(
                name="rk_live",
                regex=r"\brk_live_[0-9a-zA-Z]{24,}\b",
                score=0.93,
            ),
            Pattern(
                name="pk_live",
                regex=r"\bpk_live_[0-9a-zA-Z]{24,}\b",
                score=0.75,
            ),
        ],
        context=["stripe", "payment"],
    )


def bank_account_recognizer() -> PatternRecognizer:
    """Bank account / KYC identifiers.

    Base score is intentionally below the analyzer threshold so a bare number is
    NOT flagged; Presidio's context enhancement only lifts it above threshold
    when account-related words ('account', 'a/c', 'KYC', …) appear nearby. This
    keeps mobiles and card numbers from being mislabelled as accounts.
    """
    return PatternRecognizer(
        supported_entity="BANK_ACCOUNT_NUMBER",
        supported_language="en",
        patterns=[
            Pattern(name="acct_11_18", regex=r"\b\d{11,18}\b", score=0.3),
        ],
        context=["account", "a/c", "acct", "kyc", "bank", "ledger", "deposit"],
    )


def swift_bic_recognizer() -> PatternRecognizer:
    """SWIFT/BIC codes used in interbank transfers."""
    return PatternRecognizer(
        supported_entity="SWIFT_BIC_CODE",
        supported_language="en",
        patterns=[
            Pattern(
                name="swift_bic",
                regex=r"\b[A-Z]{4}NP[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b",
                score=0.85,
            ),
        ],
        context=["swift", "bic", "transfer", "remittance", "bank"],
    )


def all_custom_recognizers() -> list[PatternRecognizer]:
    return [
        citizenship_nepal_recognizer(),
        nepal_mobile_recognizer(),
        aws_access_key_recognizer(),
        aws_secret_key_recognizer(),
        stripe_key_recognizer(),
        bank_account_recognizer(),
        swift_bic_recognizer(),
    ]
