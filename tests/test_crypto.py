from backend.app.crypto import decrypt_env, derive_key, encrypt_env


def test_encrypt_decrypt_round_trip():
    key = derive_key("correct horse battery staple", "project-123")
    plaintext = "API_KEY=secret\nDEBUG=true\n"

    ciphertext = encrypt_env(plaintext, key)

    assert ciphertext != plaintext
    assert decrypt_env(ciphertext, key) == plaintext
