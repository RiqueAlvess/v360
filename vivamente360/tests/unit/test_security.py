"""Testes unitários do módulo shared/security.py.

Cobre todos os caminhos críticos da Regra R7 — JWT com Refresh Token em Banco:
    - create_access_token: payload válido, estrutura do JWT, expiração
    - decode_access_token: token expirado, assinatura inválida, claims ausentes
    - hash_token: determinismo, SHA-256, não expõe valor raw
    - generate_refresh_token: comprimento, unicidade, URL-safe
    - encrypt_data / decrypt_data: round-trip, chave inválida, dados corrompidos
"""
import hashlib
import uuid
from datetime import timedelta

import pytest
from jose import jwt

from src.shared.config import settings
from src.shared.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    decrypt_data,
    encrypt_data,
    generate_refresh_token,
    hash_token,
)

# ---------------------------------------------------------------------------
# Constantes de teste
# ---------------------------------------------------------------------------

FAKE_SUBJECT: str = str(uuid.uuid4())
FAKE_COMPANY_ID: str = str(uuid.uuid4())
FAKE_ROLE: str = "admin"
ENCRYPTION_KEY: str = settings.ENCRYPTION_KEY


# ---------------------------------------------------------------------------
# create_access_token
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    """Testes para geração de JWT de acesso."""

    def test_returns_decodable_jwt_with_correct_claims(self) -> None:
        """Token gerado deve conter sub, company_id, role, exp e iat."""
        token: str = create_access_token(
            subject=FAKE_SUBJECT,
            company_id=FAKE_COMPANY_ID,
            role=FAKE_ROLE,
        )

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])

        assert payload["sub"] == FAKE_SUBJECT
        assert payload["company_id"] == FAKE_COMPANY_ID
        assert payload["role"] == FAKE_ROLE
        assert "exp" in payload
        assert "iat" in payload

    def test_custom_expires_delta_is_respected(self) -> None:
        """Expiração customizada deve ser refletida no claim exp."""
        token: str = create_access_token(
            subject=FAKE_SUBJECT,
            company_id=FAKE_COMPANY_ID,
            role=FAKE_ROLE,
            expires_delta=timedelta(hours=2),
        )

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # exp deve estar no futuro (em ~2h)
        from datetime import datetime, timezone

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta_seconds = (exp - iat).total_seconds()

        # Tolerância de ±5s para overhead de execução
        assert abs(delta_seconds - 7200) <= 5

    def test_default_expiry_uses_settings(self) -> None:
        """Sem expires_delta, usa ACCESS_TOKEN_EXPIRE_MINUTES do settings."""
        token: str = create_access_token(
            subject=FAKE_SUBJECT,
            company_id=FAKE_COMPANY_ID,
            role=FAKE_ROLE,
        )

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])

        from datetime import datetime, timezone

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        expected_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        assert abs((exp - iat).total_seconds() - expected_seconds) <= 5

    def test_signed_with_hs256(self) -> None:
        """Token deve ser assinado com o algoritmo HS256."""
        token: str = create_access_token(
            subject=FAKE_SUBJECT,
            company_id=FAKE_COMPANY_ID,
            role=FAKE_ROLE,
        )

        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"

    def test_different_subjects_produce_different_tokens(self) -> None:
        """Dois subjects diferentes devem gerar tokens diferentes."""
        token_a: str = create_access_token(
            subject=str(uuid.uuid4()),
            company_id=FAKE_COMPANY_ID,
            role=FAKE_ROLE,
        )
        token_b: str = create_access_token(
            subject=str(uuid.uuid4()),
            company_id=FAKE_COMPANY_ID,
            role=FAKE_ROLE,
        )
        assert token_a != token_b


# ---------------------------------------------------------------------------
# decode_access_token
# ---------------------------------------------------------------------------


class TestDecodeAccessToken:
    """Testes para validação e decodificação de JWT."""

    def test_valid_token_returns_payload(self) -> None:
        """Token válido deve retornar payload com os claims corretos."""
        token: str = create_access_token(
            subject=FAKE_SUBJECT,
            company_id=FAKE_COMPANY_ID,
            role=FAKE_ROLE,
        )

        payload = decode_access_token(token)

        assert payload["sub"] == FAKE_SUBJECT
        assert payload["company_id"] == FAKE_COMPANY_ID
        assert payload["role"] == FAKE_ROLE

    def test_expired_token_raises_value_error(self) -> None:
        """Token expirado deve levantar ValueError (R7 — rejeição imediata)."""
        expired_token: str = create_access_token(
            subject=FAKE_SUBJECT,
            company_id=FAKE_COMPANY_ID,
            role=FAKE_ROLE,
            expires_delta=timedelta(seconds=-1),
        )

        with pytest.raises(ValueError, match="Token inválido ou expirado"):
            decode_access_token(expired_token)

    def test_tampered_signature_raises_value_error(self) -> None:
        """Token com assinatura adulterada deve levantar ValueError."""
        token: str = create_access_token(
            subject=FAKE_SUBJECT,
            company_id=FAKE_COMPANY_ID,
            role=FAKE_ROLE,
        )
        # Adultera o último segmento (assinatura)
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + ".invalidsignature"

        with pytest.raises(ValueError, match="Token inválido ou expirado"):
            decode_access_token(tampered)

    def test_random_string_raises_value_error(self) -> None:
        """String arbitrária não é um JWT válido — deve levantar ValueError."""
        with pytest.raises(ValueError, match="Token inválido ou expirado"):
            decode_access_token("not.a.jwt")

    def test_empty_string_raises_value_error(self) -> None:
        """String vazia deve levantar ValueError."""
        with pytest.raises(ValueError, match="Token inválido ou expirado"):
            decode_access_token("")

    def test_token_signed_with_wrong_key_raises_value_error(self) -> None:
        """Token assinado com chave diferente deve ser rejeitado."""
        wrong_key_token: str = jwt.encode(
            {"sub": FAKE_SUBJECT, "company_id": FAKE_COMPANY_ID, "role": FAKE_ROLE},
            "a_completely_different_secret_key_that_is_long_enough",
            algorithm=JWT_ALGORITHM,
        )

        with pytest.raises(ValueError, match="Token inválido ou expirado"):
            decode_access_token(wrong_key_token)


# ---------------------------------------------------------------------------
# hash_token
# ---------------------------------------------------------------------------


class TestHashToken:
    """Testes para SHA-256 de tokens (armazenamento seguro no banco)."""

    def test_returns_sha256_hex_digest(self) -> None:
        """Deve retornar o digest SHA-256 em hexadecimal (64 chars)."""
        raw_token: str = "my_raw_token_value"
        result: str = hash_token(raw_token)

        expected: str = hashlib.sha256(raw_token.encode()).hexdigest()
        assert result == expected
        assert len(result) == 64

    def test_is_deterministic(self) -> None:
        """Mesma entrada sempre produz o mesmo hash."""
        raw_token: str = generate_refresh_token()
        assert hash_token(raw_token) == hash_token(raw_token)

    def test_different_inputs_produce_different_hashes(self) -> None:
        """Entradas diferentes devem produzir hashes diferentes."""
        token_a: str = generate_refresh_token()
        token_b: str = generate_refresh_token()
        assert hash_token(token_a) != hash_token(token_b)

    def test_hash_does_not_expose_raw_value(self) -> None:
        """O hash não deve conter o token original (R7 — sem plaintext no banco)."""
        raw_token: str = "sensitive_refresh_token_value"
        hashed: str = hash_token(raw_token)
        assert raw_token not in hashed

    def test_returns_only_hex_characters(self) -> None:
        """O resultado deve ser composto apenas por caracteres hexadecimais."""
        hashed: str = hash_token("any_token")
        assert all(c in "0123456789abcdef" for c in hashed)


# ---------------------------------------------------------------------------
# generate_refresh_token
# ---------------------------------------------------------------------------


class TestGenerateRefreshToken:
    """Testes para geração de refresh tokens seguros."""

    def test_returns_non_empty_string(self) -> None:
        """Deve retornar uma string não vazia."""
        token: str = generate_refresh_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_url_safe_characters_only(self) -> None:
        """Token deve conter apenas caracteres URL-safe (base64url sem padding)."""
        import re

        token: str = generate_refresh_token()
        # URL-safe base64 usa A-Z, a-z, 0-9, -, _
        assert re.match(r"^[A-Za-z0-9_-]+$", token)

    def test_minimum_length(self) -> None:
        """Token de 32 bytes em base64url resulta em ~43 caracteres."""
        token: str = generate_refresh_token()
        assert len(token) >= 40

    def test_each_call_returns_unique_token(self) -> None:
        """Cada chamada deve produzir um token único (R7 — sem reutilização)."""
        tokens: list[str] = [generate_refresh_token() for _ in range(100)]
        assert len(set(tokens)) == 100


# ---------------------------------------------------------------------------
# encrypt_data / decrypt_data (AES-256-GCM)
# ---------------------------------------------------------------------------


class TestEncryptDecryptData:
    """Testes para ciframento AES-256-GCM de dados sensíveis."""

    def test_round_trip_returns_original_plaintext(self) -> None:
        """encrypt → decrypt deve retornar o texto original."""
        plaintext: str = "dado sensível do usuário"
        encrypted: str = encrypt_data(plaintext, ENCRYPTION_KEY)
        decrypted: str = decrypt_data(encrypted, ENCRYPTION_KEY)
        assert decrypted == plaintext

    def test_encrypted_output_differs_from_plaintext(self) -> None:
        """Output cifrado não deve conter o plaintext legível."""
        plaintext: str = "texto secreto"
        encrypted: str = encrypt_data(plaintext, ENCRYPTION_KEY)
        assert plaintext not in encrypted

    def test_same_plaintext_different_ciphertexts(self) -> None:
        """Dois ciframentos do mesmo plaintext devem produzir resultados diferentes (nonce aleatório)."""
        plaintext: str = "texto repetido"
        encrypted_a: str = encrypt_data(plaintext, ENCRYPTION_KEY)
        encrypted_b: str = encrypt_data(plaintext, ENCRYPTION_KEY)
        assert encrypted_a != encrypted_b

    def test_wrong_key_raises_value_error(self) -> None:
        """Decifrar com chave errada deve levantar ValueError."""
        plaintext: str = "dado importante"
        encrypted: str = encrypt_data(plaintext, ENCRYPTION_KEY)
        wrong_key: str = "a_completely_different_key_for_testing_purposes"

        with pytest.raises(ValueError, match="Falha ao decifrar"):
            decrypt_data(encrypted, wrong_key)

    def test_corrupted_data_raises_value_error(self) -> None:
        """Dados corrompidos devem levantar ValueError."""
        with pytest.raises(ValueError, match="Falha ao decifrar"):
            decrypt_data("dados_corrompidos_nao_e_base64_valido==", ENCRYPTION_KEY)

    def test_empty_string_round_trip(self) -> None:
        """Ciframento de string vazia deve funcionar corretamente."""
        plaintext: str = ""
        encrypted: str = encrypt_data(plaintext, ENCRYPTION_KEY)
        decrypted: str = decrypt_data(encrypted, ENCRYPTION_KEY)
        assert decrypted == plaintext

    def test_unicode_plaintext_round_trip(self) -> None:
        """Texto com caracteres Unicode (acentos, emojis) deve sobreviver ao round-trip."""
        plaintext: str = "Olá, Mundo! 🌍 — dados sensíveis"
        encrypted: str = encrypt_data(plaintext, ENCRYPTION_KEY)
        decrypted: str = decrypt_data(encrypted, ENCRYPTION_KEY)
        assert decrypted == plaintext

    def test_output_is_base64_string(self) -> None:
        """O resultado cifrado deve ser uma string base64 válida."""
        import base64

        encrypted: str = encrypt_data("test", ENCRYPTION_KEY)
        # Não deve levantar exceção
        decoded = base64.b64decode(encrypted)
        # Deve ter pelo menos 12 bytes de nonce + 16 bytes de tag
        assert len(decoded) >= 28
