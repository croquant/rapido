from django.http import HttpRequest, HttpResponse


def verify_placeholder(request: HttpRequest, token: str) -> HttpResponse:
    del request, token
    return HttpResponse(status=501)
