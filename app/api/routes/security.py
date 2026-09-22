from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.core.security import (
    SecurityConfigurationError,
    encryption_service,
    field_encryptor,
    transport_security,
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
def encrypt_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt plaintext using AES-GCM.
    """
    plaintext = payload.get("plaintext")

    if plaintext is None:
        raise HTTPException(
            status_code=422,
            detail="plaintext is required",
        )

    try:
        encrypted = encryption_service.encrypt(
            value=str(plaintext)
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
def decrypt_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt an AES-GCM encrypted value.
    """
    encrypted = payload.get("encrypted")

    if encrypted is None:
        raise HTTPException(
            status_code=422,
            detail="encrypted is required",
        )

    if not isinstance(encrypted, dict):
        raise HTTPException(
            status_code=422,
            detail="encrypted must be an object",
        )

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
def encrypt_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt sensitive fields.
    """
    fields = payload.get("fields")

    if fields is None:
        raise HTTPException(
            status_code=422,
            detail="fields is required",
        )

    if not isinstance(fields, dict):
        raise HTTPException(
            status_code=422,
            detail="fields must be an object",
        )

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
def decrypt_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt previously encrypted sensitive fields.
    """
    fields = payload.get("fields")

    if fields is None:
        raise HTTPException(
            status_code=422,
            detail="fields is required",
        )

    if not isinstance(fields, dict):
        raise HTTPException(
            status_code=422,
            detail="fields must be an object",
        )

    try:
        return field_encryptor.decrypt_fields(fields)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc