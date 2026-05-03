import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import Client

from core.models import Role
from core.templatetags.org_switcher import get_org_switcher_memberships
from tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_template_tag_returns_none_for_single_membership() -> None:
    # Single-org users see the static name, never the dropdown. Tested at
    # the tag level because single-org users are redirected away from the
    # only currently-rendered page that uses nav_top.html (the picker).
    user = UserFactory()
    OrganizationMembershipFactory(
        user=user,
        organization=OrganizationFactory(slug="solo"),
        role=Role.ADMIN,
    )

    assert get_org_switcher_memberships(user) is None


@pytest.mark.django_db
def test_template_tag_returns_none_for_anonymous() -> None:
    assert get_org_switcher_memberships(AnonymousUser()) is None
    assert get_org_switcher_memberships(None) is None


@pytest.mark.django_db
def test_template_tag_returns_list_for_multi_membership() -> None:
    user = UserFactory()
    OrganizationMembershipFactory(
        user=user,
        organization=OrganizationFactory(slug="a"),
        role=Role.ADMIN,
    )
    OrganizationMembershipFactory(
        user=user,
        organization=OrganizationFactory(slug="b"),
        role=Role.ADMIN,
    )

    result = get_org_switcher_memberships(user)

    assert result is not None
    assert {m.organization.slug for m in result} == {"a", "b"}


@pytest.mark.django_db
def test_multi_membership_topbar_lists_each_active_org() -> None:
    user = UserFactory()
    org_a = OrganizationFactory(name="Acme", slug="acme")
    org_b = OrganizationFactory(name="Beta", slug="beta")
    OrganizationMembershipFactory(
        user=user, organization=org_a, role=Role.ADMIN
    )
    OrganizationMembershipFactory(
        user=user, organization=org_b, role=Role.OPERATOR
    )
    client = Client()
    client.force_login(user)

    response = client.get("/orgs/")

    assert response.status_code == 200
    assert b'<option value="/o/acme/"' in response.content
    assert b'<option value="/o/beta/"' in response.content


@pytest.mark.django_db
def test_next_param_redirects_to_active_org() -> None:
    user = UserFactory()
    org_a = OrganizationFactory(slug="acme")
    org_b = OrganizationFactory(slug="beta")
    OrganizationMembershipFactory(
        user=user, organization=org_a, role=Role.ADMIN
    )
    OrganizationMembershipFactory(
        user=user, organization=org_b, role=Role.ADMIN
    )
    client = Client()
    client.force_login(user)

    response = client.get("/orgs/?next=/o/beta/")

    assert response.status_code == 302
    assert response["Location"] == "/o/beta/"


@pytest.mark.django_db
def test_next_param_accepts_path_under_org_slug() -> None:
    user = UserFactory()
    org = OrganizationFactory(slug="acme")
    OrganizationMembershipFactory(user=user, organization=org, role=Role.ADMIN)
    OrganizationMembershipFactory(
        user=user,
        organization=OrganizationFactory(slug="beta"),
        role=Role.ADMIN,
    )
    client = Client()
    client.force_login(user)

    response = client.get("/orgs/?next=/o/acme/settings/members/")

    assert response.status_code == 302
    assert response["Location"] == "/o/acme/settings/members/"


@pytest.mark.django_db
def test_next_param_for_non_member_renders_picker() -> None:
    user = UserFactory()
    OrganizationFactory(slug="stranger")
    OrganizationMembershipFactory(
        user=user,
        organization=OrganizationFactory(slug="mine-a"),
        role=Role.ADMIN,
    )
    OrganizationMembershipFactory(
        user=user,
        organization=OrganizationFactory(slug="mine-b"),
        role=Role.ADMIN,
    )
    client = Client()
    client.force_login(user)

    response = client.get("/orgs/?next=/o/stranger/")

    assert response.status_code == 200
    assert "auth/org_picker.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_inactive_org_excluded_from_switcher() -> None:
    user = UserFactory()
    active = OrganizationFactory(slug="active", is_active=True)
    inactive = OrganizationFactory(slug="inactive", is_active=False)
    OrganizationMembershipFactory(
        user=user, organization=active, role=Role.ADMIN
    )
    OrganizationMembershipFactory(
        user=user, organization=inactive, role=Role.ADMIN
    )
    other_active = OrganizationFactory(slug="other", is_active=True)
    OrganizationMembershipFactory(
        user=user, organization=other_active, role=Role.ADMIN
    )
    client = Client()
    client.force_login(user)

    response = client.get("/orgs/")

    assert response.status_code == 200
    # Inactive org is absent from the switcher dropdown (the picker page
    # body may still link to it via membership; we only guarantee the
    # switcher excludes it).
    assert b'<option value="/o/inactive/"' not in response.content
    assert b'<option value="/o/active/"' in response.content
    assert b'<option value="/o/other/"' in response.content


@pytest.mark.django_db
def test_inactive_membership_excluded_from_switcher() -> None:
    # Switching to an org where the user's membership was deactivated
    # is impossible (filtered out at the query level).
    user = UserFactory()
    active_org = OrganizationFactory(slug="active-mem")
    deactivated_mem_org = OrganizationFactory(slug="deactivated-mem")
    third_org = OrganizationFactory(slug="third")
    OrganizationMembershipFactory(
        user=user, organization=active_org, role=Role.ADMIN
    )
    OrganizationMembershipFactory(
        user=user,
        organization=deactivated_mem_org,
        role=Role.ADMIN,
        is_active=False,
    )
    OrganizationMembershipFactory(
        user=user, organization=third_org, role=Role.ADMIN
    )
    client = Client()
    client.force_login(user)

    response = client.get("/orgs/?next=/o/deactivated-mem/")

    assert response.status_code == 200
    assert "auth/org_picker.html" in [t.name for t in response.templates]
    # Switcher dropdown excludes the deactivated membership; redirect did
    # not fire (would have been a 302).
    assert b'<option value="/o/deactivated-mem/"' not in response.content


@pytest.mark.django_db
def test_switcher_query_count(django_assert_num_queries) -> None:  # noqa: ANN001
    # N+1 acceptance: switcher loads memberships in a single query
    # (with select_related on organization).
    user = UserFactory()
    for slug in ("a", "b", "c", "d"):
        OrganizationMembershipFactory(
            user=user,
            organization=OrganizationFactory(slug=f"q-{slug}"),
            role=Role.ADMIN,
        )
    client = Client()
    client.force_login(user)

    # session + user + picker view membership query + switcher template
    # tag membership query = 4. select_related on organization keeps both
    # membership queries flat regardless of N memberships.
    with django_assert_num_queries(4):
        response = client.get("/orgs/")
    assert response.status_code == 200
