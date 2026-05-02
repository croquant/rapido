from collections.abc import Callable
from functools import wraps
from typing import ParamSpec

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
)

from core.models import OrganizationMembership, Role

P = ParamSpec("P")


def permission_required(
    role: Role | None = None,
) -> Callable[[Callable[P, HttpResponse]], Callable[P, HttpResponse]]:
    def decorator(
        view_func: Callable[P, HttpResponse],
    ) -> Callable[P, HttpResponse]:
        @wraps(view_func)
        def _wrapped(*args: P.args, **kwargs: P.kwargs) -> HttpResponse:
            request = args[0]
            assert isinstance(request, HttpRequest)
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(
                    request.get_full_path(),
                    login_url=settings.LOGIN_URL,
                )
            organization = getattr(request, "organization", None)
            if organization is None:
                raise Http404
            if user.is_superuser:
                return view_func(*args, **kwargs)
            membership = OrganizationMembership.objects.filter(
                user=user, organization=organization, is_active=True
            ).first()
            if membership is None:
                return HttpResponseForbidden()
            if role is not None and membership.role != role:
                return HttpResponseForbidden()
            return view_func(*args, **kwargs)

        return _wrapped

    return decorator
