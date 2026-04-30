from core.models import TimestampedModel


def test_timestamped_model_is_abstract() -> None:
    assert TimestampedModel._meta.abstract is True


def test_timestamped_model_has_auto_timestamp_fields() -> None:
    fields = {f.name: f for f in TimestampedModel._meta.get_fields()}
    assert fields["created_at"].auto_now_add is True  # type: ignore[attr-defined]
    assert fields["updated_at"].auto_now is True  # type: ignore[attr-defined]
