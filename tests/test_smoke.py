from django.http.response import HttpResponse
from django.test import Client


def test_admin_login_page_renders(client: Client) -> None:
    response: HttpResponse = client.get(path="/admin/login/")
    assert response.status_code == 200
