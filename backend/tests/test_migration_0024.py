from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def migration_0024() -> ModuleType:
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0024.py"
    spec = importlib.util.spec_from_file_location("migration_0024", migration_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_recreates_missing_registration_requests_table(
    migration_0024: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bind = Mock()
    inspector = Mock()
    inspector.has_table.return_value = False
    monkeypatch.setattr(migration_0024.op, "get_bind", Mock(return_value=bind))
    monkeypatch.setattr(migration_0024.sa, "inspect", Mock(return_value=inspector))
    create_table = Mock()
    create_index = Mock()
    add_column = Mock()
    monkeypatch.setattr(migration_0024.op, "create_table", create_table)
    monkeypatch.setattr(migration_0024.op, "create_index", create_index)
    monkeypatch.setattr(migration_0024.op, "add_column", add_column)
    enum_create = Mock()
    monkeypatch.setattr(
        migration_0024.registrationrequeststatus_enum,
        "create",
        enum_create,
    )

    migration_0024.upgrade()

    enum_create.assert_called_once_with(bind, checkfirst=True)
    create_table.assert_called_once()
    created_columns = {
        item.name for item in create_table.call_args.args[1:] if hasattr(item, "name")
    }
    assert created_columns == {
        "id",
        "username",
        "hashed_password",
        "status",
        "reviewed_by_user_id",
        "reviewed_at",
        "rejection_reason",
        "created_at",
        "updated_at",
    }
    assert create_index.call_count == 2
    add_column.assert_not_called()


def test_upgrade_only_adds_missing_metadata_columns(
    migration_0024: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspector = Mock()
    inspector.has_table.return_value = True
    inspector.get_columns.return_value = [
        {"name": "id"},
        {"name": "reviewed_at"},
    ]
    monkeypatch.setattr(migration_0024.op, "get_bind", Mock())
    monkeypatch.setattr(migration_0024.sa, "inspect", Mock(return_value=inspector))
    create_table = Mock()
    add_column = Mock()
    monkeypatch.setattr(migration_0024.op, "create_table", create_table)
    monkeypatch.setattr(migration_0024.op, "add_column", add_column)

    migration_0024.upgrade()

    create_table.assert_not_called()
    add_column.assert_called_once()
    assert add_column.call_args.args[0] == migration_0024.TABLE_NAME
    assert add_column.call_args.args[1].name == "rejection_reason"
