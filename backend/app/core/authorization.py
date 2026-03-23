from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.models.user import UserRole

if TYPE_CHECKING:
    from app.models.user import User


class Permission(str, enum.Enum):
    product_read = "product.read"
    product_write = "product.write"
    product_delete = "product.delete"
    product_import = "product.import"
    product_export = "product.export"
    product_auto_archive = "product.auto_archive"

    asset_read = "asset.read"
    asset_upload = "asset.upload"
    asset_review = "asset.review"

    content_read = "content.read"
    content_manage = "content.manage"

    deal_read = "deal.read"
    deal_manage = "deal.manage"

    email_read = "email.read"
    email_generate = "email.generate"

    image_search = "image.search"

    knowledge_read = "knowledge.read"
    knowledge_manage = "knowledge.manage"

    user_read = "user.read"
    user_manage = "user.manage"
    user_approve_registration = "user.approve_registration"

    audit_view = "audit.view"


class PermissionScope(str, enum.Enum):
    global_scope = "global"
    object_scope = "object"


@dataclass(frozen=True)
class PermissionDefinition:
    permission: Permission
    scope: PermissionScope


PERMISSION_DEFINITIONS: dict[Permission, PermissionDefinition] = {
    Permission.product_read: PermissionDefinition(
        Permission.product_read, PermissionScope.global_scope
    ),
    Permission.product_write: PermissionDefinition(
        Permission.product_write, PermissionScope.object_scope
    ),
    Permission.product_delete: PermissionDefinition(
        Permission.product_delete, PermissionScope.object_scope
    ),
    Permission.product_import: PermissionDefinition(
        Permission.product_import, PermissionScope.global_scope
    ),
    Permission.product_export: PermissionDefinition(
        Permission.product_export, PermissionScope.global_scope
    ),
    Permission.product_auto_archive: PermissionDefinition(
        Permission.product_auto_archive, PermissionScope.global_scope
    ),
    Permission.asset_read: PermissionDefinition(
        Permission.asset_read, PermissionScope.object_scope
    ),
    Permission.asset_upload: PermissionDefinition(
        Permission.asset_upload, PermissionScope.object_scope
    ),
    Permission.asset_review: PermissionDefinition(
        Permission.asset_review, PermissionScope.object_scope
    ),
    Permission.content_read: PermissionDefinition(
        Permission.content_read, PermissionScope.global_scope
    ),
    Permission.content_manage: PermissionDefinition(
        Permission.content_manage, PermissionScope.object_scope
    ),
    Permission.deal_read: PermissionDefinition(Permission.deal_read, PermissionScope.global_scope),
    Permission.deal_manage: PermissionDefinition(
        Permission.deal_manage, PermissionScope.object_scope
    ),
    Permission.email_read: PermissionDefinition(
        Permission.email_read, PermissionScope.global_scope
    ),
    Permission.email_generate: PermissionDefinition(
        Permission.email_generate, PermissionScope.global_scope
    ),
    Permission.image_search: PermissionDefinition(
        Permission.image_search, PermissionScope.global_scope
    ),
    Permission.knowledge_read: PermissionDefinition(
        Permission.knowledge_read, PermissionScope.global_scope
    ),
    Permission.knowledge_manage: PermissionDefinition(
        Permission.knowledge_manage, PermissionScope.object_scope
    ),
    Permission.user_read: PermissionDefinition(Permission.user_read, PermissionScope.global_scope),
    Permission.user_manage: PermissionDefinition(
        Permission.user_manage, PermissionScope.global_scope
    ),
    Permission.user_approve_registration: PermissionDefinition(
        Permission.user_approve_registration, PermissionScope.global_scope
    ),
    Permission.audit_view: PermissionDefinition(
        Permission.audit_view, PermissionScope.global_scope
    ),
}


VIEWER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.product_read,
        Permission.asset_read,
        Permission.content_read,
        Permission.deal_read,
        Permission.email_read,
        Permission.knowledge_read,
    }
)

EDITOR_PERMISSIONS: frozenset[Permission] = VIEWER_PERMISSIONS.union(
    {
        Permission.product_write,
        Permission.product_import,
        Permission.product_export,
        Permission.asset_upload,
        Permission.asset_review,
        Permission.content_manage,
        Permission.deal_manage,
        Permission.email_generate,
        Permission.image_search,
    }
)

ADMIN_PERMISSIONS: frozenset[Permission] = frozenset(PERMISSION_DEFINITIONS.keys())


ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.viewer: VIEWER_PERMISSIONS,
    UserRole.editor: EDITOR_PERMISSIONS,
    UserRole.admin: ADMIN_PERMISSIONS,
}


def permissions_for_role(role: UserRole) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, VIEWER_PERMISSIONS)


def permission_values_for_role(role: UserRole) -> list[str]:
    permissions = permissions_for_role(role)
    return sorted(permission.value for permission in permissions)


def has_permission(user: User, permission: Permission, resource: object | None = None) -> bool:
    allowed = permission in permissions_for_role(user.role)
    if not allowed:
        return False

    definition = PERMISSION_DEFINITIONS.get(permission)
    if definition and definition.scope == PermissionScope.object_scope and resource is not None:
        return True
    return True
