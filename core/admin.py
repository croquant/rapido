from __future__ import annotations

from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.contrib.auth.forms import (
    UserCreationForm as DjangoUserCreationForm,
)
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from .models import (
    Location,
    LocationMembership,
    Organization,
    OrganizationMembership,
    Role,
    User,
)
from .services.membership import (
    change_role,
    deactivate_membership,
    deactivate_user,
    other_qualifying_admin_exists,
)

# ---- forms with invariant validation -------------------------------------


class OrganizationMembershipAdminForm(forms.ModelForm):
    class Meta:
        model = OrganizationMembership
        fields = "__all__"  # noqa: DJ007

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        if not self.instance.pk:
            return cleaned
        db = OrganizationMembership.objects.select_related(
            "organization", "user"
        ).get(pk=self.instance.pk)
        new_active = cleaned.get("is_active", db.is_active)
        new_role = cleaned.get("role", db.role)
        was_qualifying = (
            db.role == Role.ADMIN and db.is_active and db.user.is_active
        )
        deactivating = was_qualifying and not new_active
        demoting = was_qualifying and new_role != Role.ADMIN and new_active
        if (deactivating or demoting) and not other_qualifying_admin_exists(
            db.organization, exclude_membership=db
        ):
            raise ValidationError(
                _("Cannot change: %(org)s would have no active ADMIN.")
                % {"org": db.organization.slug}
            )
        return cleaned


class UserCreationForm(DjangoUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


class UserChangeForm(DjangoUserChangeForm):
    class Meta:
        model = User
        fields = "__all__"

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        if not self.instance.pk:
            return cleaned
        db = User.objects.get(pk=self.instance.pk)
        new_active = cleaned.get("is_active", db.is_active)
        if not (db.is_active and not new_active):
            return cleaned
        offending: list[Organization] = []
        admin_memberships = (
            OrganizationMembership.objects.filter(
                user=db, role=Role.ADMIN, is_active=True
            )
            .select_related("organization")
            .order_by("organization__slug")
        )
        for m in admin_memberships:
            if not other_qualifying_admin_exists(
                m.organization, exclude_user=db
            ):
                offending.append(m.organization)
        if offending:
            raise ValidationError(
                _(
                    "Cannot deactivate: user is the last active ADMIN "
                    "of %(orgs)s."
                )
                % {"orgs": ", ".join(o.slug for o in offending)}
            )
        return cleaned


# ---- service-routing helper ----------------------------------------------


def _save_org_membership(obj: OrganizationMembership) -> None:
    """Persist obj. Route is_active / role transitions through services so
    the 'last active ADMIN' invariant has a single enforcement point."""
    if not obj.pk:
        obj.save()
        return
    with transaction.atomic():
        db = OrganizationMembership.objects.get(pk=obj.pk)
        if db.role != obj.role:
            change_role(db, obj.role)
        if db.is_active and not obj.is_active:
            deactivate_membership(db)
        elif not db.is_active and obj.is_active:
            db.is_active = True
            db.save(update_fields=["is_active", "updated_at"])
        obj.role = db.role
        obj.is_active = db.is_active
        obj.updated_at = db.updated_at
        obj.save()


# ---- inlines -------------------------------------------------------------


class OrganizationMembershipInline(admin.TabularInline):
    model = OrganizationMembership
    form = OrganizationMembershipAdminForm
    extra = 0
    fields = ("user", "role", "is_active", "created_by")
    autocomplete_fields = ("user", "created_by")
    show_change_link = True


class LocationMembershipInline(admin.TabularInline):
    model = LocationMembership
    extra = 0
    fields = ("user", "is_active", "created_by")
    autocomplete_fields = ("user", "created_by")
    show_change_link = True


# ---- ModelAdmins ---------------------------------------------------------


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    inlines = [OrganizationMembershipInline]  # noqa: RUF012
    prepopulated_fields = {"slug": ("name",)}  # noqa: RUF012
    list_display = (
        "name",
        "slug",
        "country",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "country")
    search_fields = (
        "name",
        "slug",
        "vat_number",
        "billing_email",
    )
    readonly_fields = ("public_id", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "slug", "is_active")}),
        (
            _("Localisation"),
            {
                "fields": (
                    "country",
                    "default_timezone",
                    "default_currency",
                    "default_language",
                ),
            },
        ),
        (_("Billing"), {"fields": ("vat_number", "billing_email")}),
        (
            _("Identifiers"),
            {"fields": ("public_id", "created_at", "updated_at")},
        ),
    )


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "preferred_language",
                ),
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (
            _("Identifiers"),
            {
                "fields": (
                    "public_id",
                    "last_login",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    readonly_fields = (
        "public_id",
        "last_login",
        "created_at",
        "updated_at",
    )

    def save_model(
        self,
        request: HttpRequest,
        obj: User,
        form: forms.ModelForm,
        change: bool,  # noqa: FBT001
    ) -> None:
        if change and obj.pk:
            db = User.objects.get(pk=obj.pk)
            if db.is_active and not obj.is_active:
                deactivate_user(db)
                obj.is_active = db.is_active
                obj.updated_at = db.updated_at
        super().save_model(request, obj, form, change)


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    form = OrganizationMembershipAdminForm
    list_display = (
        "user",
        "organization",
        "role",
        "is_active",
        "created_at",
    )
    list_filter = ("role", "is_active", "organization")
    search_fields = (
        "user__email",
        "organization__name",
        "organization__slug",
    )
    autocomplete_fields = ("user", "organization", "created_by")
    readonly_fields = ("created_at", "updated_at")

    def save_model(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: OrganizationMembership,
        form: forms.ModelForm,  # noqa: ARG002
        change: bool,  # noqa: ARG002, FBT001
    ) -> None:
        _save_org_membership(obj)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    inlines = [LocationMembershipInline]  # noqa: RUF012
    prepopulated_fields = {"slug": ("name",)}  # noqa: RUF012
    list_display = (
        "name",
        "organization",
        "city",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "organization")
    search_fields = (
        "name",
        "slug",
        "city",
        "organization__name",
        "organization__slug",
    )
    autocomplete_fields = ("organization",)
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(LocationMembership)
class LocationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "is_active", "created_at")
    list_filter = ("is_active", "location__organization")
    search_fields = (
        "user__email",
        "location__name",
        "location__slug",
    )
    autocomplete_fields = ("user", "location", "created_by")
    readonly_fields = ("created_at", "updated_at")
    exclude = ("pin",)
