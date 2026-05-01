# Contributing

## Setup

```sh
uv sync
uv run pre-commit install
```

## Tenant scoping rule

Tenant-owned models must be queried in views/viewsets via the
`TenantOwnedManager` helpers, not raw `.objects`:

```python
# good
qs = Order.tenant_objects.for_request(self.request)
qs = Order.tenant_objects.for_organization(org)

# bad — bypasses tenant scoping
qs = Order.objects.all()
qs = Order.objects.filter(...)
qs = Order.objects.get(...)
```

`scripts/tenant_lint.py` runs in CI and as a `pre-commit` hook. It
rejects `.objects.{all,filter,get}(` in any file matching
`**/views.py`, `**/viewsets.py`, `**/views/*.py`, or
`**/viewsets/*.py`.

### Escape hatch

For non-tenant models or intentional system-level access, append
`# noqa: tenant-lint` to the offending line. Prefer
`Model._default_manager` over `.objects` when bypassing scoping
deliberately.

```python
SiteConfig.objects.get(pk=1)  # noqa: tenant-lint
```

## Running checks locally

```sh
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python scripts/tenant_lint.py
uv run pytest
```
