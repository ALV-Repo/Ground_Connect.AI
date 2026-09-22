from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# Identity
# ============================================================

class IdentityRegisterRequest(BaseModel):
    subject_id: str
    tenant_id: str
    branch_id: Optional[str] = None
    role: str


# ============================================================
# Grants
# ============================================================

class GrantRequest(BaseModel):
    subject_id: str
    resource_type: str
    resource_id: str
    action: str
    tenant_id: str
    branch_id: Optional[str] = None


# ============================================================
# Authorization
# ============================================================

class AuthorizationRequest(BaseModel):
    subject_id: str
    action: str
    resource_type: str
    resource_id: str
    tenant_id: Optional[str] = None
    branch_id: Optional[str] = None
    client_identity: Optional[Dict[str, str]] = None
    context: Optional[Dict[str, str]] = None


class AuthorizationDecision(BaseModel):
    allowed: bool
    subject_id: str
    action: str
    resource_type: str
    resource_id: str
    reason: str
    failing_rule: Optional[str] = None
    rules_evaluated: List[str] = Field(default_factory=list)
    cache_hit: bool = False
    timestamp: float


# ============================================================
# Field-Level Authorization
# ============================================================

class FieldAuthorizationRequest(BaseModel):
    subject_id: str
    tenant_id: str
    resource_type: str
    resource_id: str
    fields: List[str]
    action: str = "READ"
    branch_id: Optional[str] = None


class FieldAuthorizationResponse(BaseModel):
    allowed: bool = False
    subject_id: str
    resource_type: str
    resource_id: str
    action: str
    allowed_fields: List[str] = Field(default_factory=list)
    denied_fields: List[str] = Field(default_factory=list)
    reason: Optional[str] = None


# ============================================================
# Field Policies
# ============================================================

class FieldPolicyRequest(BaseModel):
    role: str
    resource_type: str
    field: str
    actions: List[str]


class FieldPolicyResponse(BaseModel):
    success: bool = True
    role: str
    resource_type: str
    field: str
    actions: List[str] = Field(default_factory=list)


# ============================================================
# Field Cache
# ============================================================

class FieldCacheInvalidationRequest(BaseModel):
    subject_id: Optional[str] = None
    role: Optional[str] = None
    resource_type: Optional[str] = None


class FieldCacheInvalidationResponse(BaseModel):
    success: bool = True
    invalidated: int = 0
    message: Optional[str] = None


# ============================================================
# ADR Query
# ============================================================

class ADRQueryRequest(BaseModel):
    subject_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    decision: Optional[bool] = None
    tenant_id: Optional[str] = None
    branch_id: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)


class ADRQueryResponse(BaseModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)
    count: int


# ============================================================
# Denial Query
# ============================================================

class DenialQueryRequest(BaseModel):
    subject_id: Optional[str] = None
    tenant_id: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)


class DenialQueryResponse(BaseModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)
    count: int


# ============================================================
# What Can Access
# ============================================================

class WhatCanAccessRequest(BaseModel):
    subject_id: str
    decision: Optional[bool] = None
    limit: int = Field(default=100, ge=1, le=1000)


class WhatCanAccessResponse(BaseModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)
    count: int


# ============================================================
# Who Can Access
# ============================================================

class WhoCanAccessRequest(BaseModel):
    resource_type: str
    resource_id: str
    action: str
    tenant_id: str
    limit: int = Field(default=100, ge=1, le=1000)


class WhoCanAccessResponse(BaseModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)
    count: int