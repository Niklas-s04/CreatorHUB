from __future__ import annotations

import pyotp

from app.services.auth_security import (
    generate_recovery_codes,
    hash_recovery_codes,
    protect_totp_secret,
    verify_recovery_code,
    verify_totp_code,
)


def test_totp_secret_is_encrypted_but_still_verifiable() -> None:
    secret = pyotp.random_base32()
    encrypted = protect_totp_secret(secret)
    code = pyotp.TOTP(secret).now()

    assert encrypted.startswith("enc:v1:")
    assert secret not in encrypted
    assert verify_totp_code(encrypted, code)


def test_plaintext_totp_secret_remains_verifiable_for_migration() -> None:
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()

    assert verify_totp_code(secret, code)


def test_recovery_codes_use_more_entropy_and_slow_hashes() -> None:
    codes = generate_recovery_codes()
    hashes = hash_recovery_codes(codes)

    assert all(len(code) == 16 for code in codes)
    assert all(item.startswith("$pbkdf2-sha256$") for item in hashes)

    ok, remaining = verify_recovery_code(hashes, codes[0])
    assert ok is True
    assert len(remaining) == len(hashes) - 1
