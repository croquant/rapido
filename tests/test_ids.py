from core.utils.ids import uuid7


def test_uuid7_is_monotonic() -> None:
    a = uuid7()
    b = uuid7()
    assert a.bytes < b.bytes
