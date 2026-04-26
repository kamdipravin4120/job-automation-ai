import time
import uuid

import pytest


def _make_keys():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    k = Ed25519PrivateKey.generate()
    priv = k.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
    pub = k.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    return priv, pub


def test_create_and_decode_jwt():
    from src.api.core.security import create_jwt, decode_jwt

    priv, pub = _make_keys()
    device_id = uuid.uuid4()
    token = create_jwt(device_id, private_key_pem=priv)
    payload = decode_jwt(token, public_key_pem=pub)
    assert payload["sub"] == str(device_id)
    assert "jti" in payload
    assert "iat" in payload
    assert "exp" in payload
    assert abs(payload["exp"] - (int(time.time()) + 7 * 86400)) < 5


def test_decode_jwt_wrong_key_raises():
    import jwt as pyjwt
    from src.api.core.security import create_jwt, decode_jwt

    priv, _ = _make_keys()
    _, other_pub = _make_keys()
    token = create_jwt(uuid.uuid4(), private_key_pem=priv)
    with pytest.raises(pyjwt.exceptions.InvalidSignatureError):
        decode_jwt(token, public_key_pem=other_pub)
