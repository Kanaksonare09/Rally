def test_all_models_import_cleanly():
    from app.models import (  # noqa: F401
        Alert,
        Group,
        GroupMember,
        LocationHistory,
        Profile,
        SOSEvent,
        Trip,
    )


def test_expected_tables_are_registered_on_metadata():
    from app.models import Base

    expected = {
        "profiles",
        "groups",
        "group_members",
        "trips",
        "location_history",
        "alerts",
        "sos_events",
    }
    assert expected.issubset(set(Base.metadata.tables.keys()))


def test_group_members_has_unique_group_user_constraint():
    from app.models import Base

    table = Base.metadata.tables["group_members"]
    unique_constraints = [c for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"]
    assert any(
        {col.name for col in uc.columns} == {"group_id", "user_id"} for uc in unique_constraints
    )


def test_join_code_is_unique():
    from app.models import Base

    table = Base.metadata.tables["groups"]
    assert table.columns["join_code"].unique or any(
        {col.name for col in uc.columns} == {"join_code"}
        for uc in table.constraints
        if uc.__class__.__name__ == "UniqueConstraint"
    )
