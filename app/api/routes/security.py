from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.core.security import (
    SecurityConfigurationError,
    encryption_service,
    field_encryptor,
    transport_security,
)

from app.schemas.security import (
    SecurityEncryptPayload,
    SecurityDecryptPayload,
    SecurityFieldsPayload,
)

router = APIRouter(
    prefix="/security",
    tags=["Security"],
)


# ---------------------------------------------------------
# Transport Security
# ---------------------------------------------------------

@router.get("/transport")
def transport_security_status() -> Dict[str, Any]:
    """
    Return the application's transport-security configuration.
    """
    try:
        return transport_security.validate()

    except SecurityConfigurationError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Overall Security Status
# ---------------------------------------------------------

@router.get("/status")
def security_status() -> Dict[str, Any]:
    """
    Return the overall security configuration status.
    """
    try:
        transport = transport_security.validate()

        return {
            "transport_security": transport,
            "encryption": {
                "algorithm": encryption_service.ALGORITHM,
                "key_size": encryption_service.KEY_SIZE,
                "nonce_size": encryption_service.NONCE_SIZE,
            },
            "field_encryption": {
                "available": field_encryptor is not None,
            },
        }

    except SecurityConfigurationError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# AES-GCM Encryption
# ---------------------------------------------------------

@router.post("/encryption/encrypt")
def encrypt_data(
    payload: SecurityEncryptPayload,
) -> Dict[str, Any]:
    """
    Encrypt plaintext using AES-GCM.
    """
    plaintext = payload.plaintext

    try:
        encrypted = encryption_service.encrypt(
            value=plaintext
        )

        return encrypted.to_dict()

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# AES-GCM Decryption
# ---------------------------------------------------------

@router.post("/encryption/decrypt")
def decrypt_data(
    payload: SecurityDecryptPayload,
) -> Dict[str, Any]:
    """
    Decrypt an AES-GCM encrypted value.
    """
    encrypted = payload.encrypted

    try:
        plaintext = encryption_service.decrypt_text(
            encrypted=encrypted
        )

        return {
            "plaintext": plaintext
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Field Encryption
# ---------------------------------------------------------

@router.post("/fields/encrypt")
def encrypt_fields(
    payload: SecurityFieldsPayload,
) -> Dict[str, Any]:
    """
    Encrypt sensitive fields.
    """
    fields = payload.fields

    try:
        return field_encryptor.encrypt_fields(fields)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Field Decryption
# ---------------------------------------------------------

@router.post("/fields/decrypt")
def decrypt_fields(
    payload: SecurityFieldsPayload,
) -> Dict[str, Any]:
    """
    Decrypt previously encrypted sensitive fields.
    """
    fields = payload.fields

    try:
        return field_encryptor.decrypt_fields(fields)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc