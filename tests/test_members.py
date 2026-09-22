import pytest

from app.services.members import MemberService


@pytest.fixture
def service():
    return MemberService()


# ============================================================
# Create Member
# ============================================================

def test_create_member():
    service = MemberService()

    member = service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        branch_id="branch-001",
        name="Test Member",
        mobile="9876543210",
        email="test@example.com",
        role="member",
        status="active",
        metadata={},
    )

    assert member["member_id"] == "member-001"
    assert member["tenant_id"] == "tenant-001"
    assert member["branch_id"] == "branch-001"
    assert member["name"] == "Test Member"
    assert member["status"] == "active"


# ============================================================
# Duplicate Member
# ============================================================

def test_duplicate_member_rejected():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Test Member",
    )

    with pytest.raises(ValueError, match="Member already exists"):
        service.create_member(
            member_id="member-001",
            tenant_id="tenant-001",
            name="Another Member",
        )


# ============================================================
# Get Member
# ============================================================

def test_get_member():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Test Member",
    )

    member = service.get_member(
        member_id="member-001",
        tenant_id="tenant-001",
    )

    assert member is not None
    assert member["member_id"] == "member-001"
    assert member["tenant_id"] == "tenant-001"


# ============================================================
# Tenant Isolation
# ============================================================

def test_get_member_tenant_isolation():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Test Member",
    )

    member = service.get_member(
        member_id="member-001",
        tenant_id="tenant-002",
    )

    assert member is None


# ============================================================
# Update Member
# ============================================================

def test_update_member():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Old Name",
        mobile="1111111111",
    )

    updated = service.update_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="New Name",
        mobile="9999999999",
    )

    assert updated["name"] == "New Name"
    assert updated["mobile"] == "9999999999"


# ============================================================
# Cross Tenant Update
# ============================================================

def test_update_member_cross_tenant_denied():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Test Member",
    )

    with pytest.raises(
        PermissionError,
        match="Cross-tenant member access denied",
    ):
        service.update_member(
            member_id="member-001",
            tenant_id="tenant-002",
            name="Hacked Name",
        )


# ============================================================
# Lifecycle
# ============================================================

def test_member_lifecycle():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Test Member",
        status="active",
    )

    member = service.lifecycle_action(
        member_id="member-001",
        tenant_id="tenant-001",
        action="deactivate",
        reason="Testing",
    )

    assert member["status"] == "inactive"
    assert member["metadata"]["lifecycle_reason"] == "Testing"


def test_member_suspend():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Test Member",
    )

    member = service.lifecycle_action(
        member_id="member-001",
        tenant_id="tenant-001",
        action="suspend",
    )

    assert member["status"] == "suspended"


def test_member_restore():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Test Member",
        status="suspended",
    )

    member = service.lifecycle_action(
        member_id="member-001",
        tenant_id="tenant-001",
        action="restore",
    )

    assert member["status"] == "active"


# ============================================================
# Search
# ============================================================

def test_search_members():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        branch_id="branch-001",
        name="Test Member",
        status="active",
    )

    service.create_member(
        member_id="member-002",
        tenant_id="tenant-001",
        branch_id="branch-001",
        name="Another Member",
        status="inactive",
    )

    result = service.search_members(
        tenant_id="tenant-001",
        query="Test",
        branch_id="branch-001",
        status="active",
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["member_id"] == "member-001"


# ============================================================
# Bulk Import
# ============================================================

def test_bulk_import():
    service = MemberService()

    records = [
        {
            "member_id": "member-001",
            "tenant_id": "tenant-001",
            "branch_id": "branch-001",
            "name": "Bulk Member One",
            "status": "active",
        },
        {
            "member_id": "member-002",
            "tenant_id": "tenant-001",
            "branch_id": "branch-001",
            "name": "Bulk Member Two",
            "status": "active",
        },
    ]

    result = service.bulk_import(
        tenant_id="tenant-001",
        records=records,
    )

    assert result["imported"] == 2
    assert result["updated"] == 0
    assert result["failed"] == 0
    assert result["errors"] == []


# ============================================================
# Bulk Import Update
# ============================================================

def test_bulk_import_updates_existing_member():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Old Name",
    )

    result = service.bulk_import(
        tenant_id="tenant-001",
        records=[
            {
                "member_id": "member-001",
                "tenant_id": "tenant-001",
                "name": "Updated Name",
                "status": "inactive",
            }
        ],
    )

    assert result["imported"] == 0
    assert result["updated"] == 1
    assert result["failed"] == 0

    member = service.get_member(
        member_id="member-001",
        tenant_id="tenant-001",
    )

    assert member["name"] == "Updated Name"
    assert member["status"] == "inactive"


# ============================================================
# Bulk Import Tenant Isolation
# ============================================================

def test_bulk_import_tenant_mismatch():
    service = MemberService()

    result = service.bulk_import(
        tenant_id="tenant-001",
        records=[
            {
                "member_id": "member-001",
                "tenant_id": "tenant-002",
                "name": "Wrong Tenant",
            }
        ],
    )

    assert result["imported"] == 0
    assert result["updated"] == 0
    assert result["failed"] == 1
    assert "tenant mismatch" in result["errors"][0]


# ============================================================
# Bulk Import Size Limit
# ============================================================

def test_bulk_import_max_size():
    service = MemberService()

    max_records = 10000

    records = [
        {
            "member_id": f"member-{i}",
            "tenant_id": "tenant-001",
            "name": f"Member {i}",
        }
        for i in range(max_records + 1)
    ]

    with pytest.raises(
        ValueError,
        match="Maximum bulk import size",
    ):
        service.bulk_import(
            tenant_id="tenant-001",
            records=records,
        )


# ============================================================
# Statistics
# ============================================================

def test_member_statistics():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Active Member",
        status="active",
    )

    service.create_member(
        member_id="member-002",
        tenant_id="tenant-001",
        name="Inactive Member",
        status="inactive",
    )

    service.create_member(
        member_id="member-003",
        tenant_id="tenant-001",
        name="Suspended Member",
        status="suspended",
    )

    statistics = service.statistics(
        tenant_id="tenant-001",
    )

    assert statistics["total"] == 3
    assert statistics["active"] == 1
    assert statistics["inactive"] == 1
    assert statistics["suspended"] == 1
    assert statistics["pending"] == 0


# ============================================================
# Delete
# ============================================================

def test_delete_member():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Test Member",
    )

    deleted = service.delete_member(
        member_id="member-001",
        tenant_id="tenant-001",
        reason="Testing deletion",
    )

    assert deleted is True

    member = service.get_member(
        member_id="member-001",
        tenant_id="tenant-001",
    )

    assert member is None


# ============================================================
# Cross Tenant Delete
# ============================================================

def test_delete_member_cross_tenant_denied():
    service = MemberService()

    service.create_member(
        member_id="member-001",
        tenant_id="tenant-001",
        name="Test Member",
    )

    with pytest.raises(
        PermissionError,
        match="Cross-tenant member access denied",
    ):
        service.delete_member(
            member_id="member-001",
            tenant_id="tenant-002",
        )
def test_member_lifecycle_cross_tenant_denied():
    service = MemberService()

    service.create_member(
        member_id="member-tenant-001",
        tenant_id="tenant-001",
        name="Test Member",
        status="active",
    )

    with pytest.raises(
        PermissionError,
        match="Cross-tenant member access denied",
    ):
        service.lifecycle_action(
            member_id="member-tenant-001",
            tenant_id="tenant-002",
            action="deactivate",
        )


def test_invalid_lifecycle_action_rejected():
    service = MemberService()

    service.create_member(
        member_id="member-invalid-action",
        tenant_id="tenant-001",
        name="Test Member",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported lifecycle action",
    ):
        service.lifecycle_action(
            member_id="member-invalid-action",
            tenant_id="tenant-001",
            action="delete",
        )


def test_search_pagination():
    service = MemberService()

    for index in range(5):
        service.create_member(
            member_id=f"page-member-{index}",
            tenant_id="tenant-001",
            name=f"Member {index}",
        )

    result = service.search_members(
        tenant_id="tenant-001",
        page=2,
        page_size=2,
    )

    assert result["total"] == 5
    assert result["page"] == 2
    assert result["page_size"] == 2
    assert len(result["items"]) == 2


def test_bulk_import_dry_run_does_not_modify_store():
    service = MemberService()

    result = service.bulk_import(
        tenant_id="tenant-001",
        records=[
            {
                "member_id": "dry-run-member",
                "tenant_id": "tenant-001",
                "name": "Dry Run Member",
            }
        ],
        dry_run=True,
    )

    assert result["imported"] == 1
    assert result["failed"] == 0

    member = service.get_member(
        member_id="dry-run-member",
        tenant_id="tenant-001",
    )

    assert member is None
