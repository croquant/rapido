from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.contrib.auth.forms import (
    UserCreationForm as DjangoUserCreationForm,
)
from django.utils.translation import gettext_lazy as _

from .models import (
    Location,
    LocationMembership,
    Organization,
    OrganizationMembership,
    User,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}  # noqa: RUF012
    search_fields = ("name", "slug")


class UserCreationForm(DjangoUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


class UserChangeForm(DjangoUserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


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
            _("Important dates"),
            {"fields": ("last_login", "created_at", "updated_at")},
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
    readonly_fields = ("last_login", "created_at", "updated_at")


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
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


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
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
    readonly_fields = ("created_at", "updated_at", "public_id")


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
