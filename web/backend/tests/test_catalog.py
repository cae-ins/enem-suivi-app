import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_catalog_exposes_current_modules():
    user = get_user_model().objects.create_user("tester", password="secret-test-only")
    client = APIClient()
    client.force_authenticate(user)
    response = client.get("/api/v1/modules/")
    assert response.status_code == 200
    assert len(response.json()) == 12
    assert "preparation_bases" in {module["id"] for module in response.json()}
    evolution = next(module for module in response.json() if module["id"] == "evolution_zd")
    parameters = {parameter["key"]: parameter for parameter in evolution["parameters"]}
    assert parameters["lundi_semaine1"]["type"] == "date"
    assert parameters["lundi_semaine1"]["required"] is True
    assert parameters["cohortes"]["type"] == "tableau"
    assert parameters["cohortes"]["required"] is False
    assert "dossier_sortie" not in parameters


@pytest.mark.django_db
def test_catalog_requires_authentication():
    response = APIClient().get("/api/v1/modules/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_jwt_authentication():
    get_user_model().objects.create_user("jwt-user", password="strong-test-password")
    client = APIClient()
    token = client.post(
        "/api/v1/auth/token/",
        {"username": "jwt-user", "password": "strong-test-password"},
        format="json",
    )
    assert token.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.json()['access']}")
    assert client.get("/api/v1/modules/").status_code == 200


@pytest.mark.django_db
def test_execution_rejects_unknown_module():
    user = get_user_model().objects.create_user("executor", password="strong-test-password")
    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        "/api/v1/executions/",
        {"module_id": "module-inconnu", "quarter": "T3_2026", "parameters": {}},
        format="json",
    )
    assert response.status_code == 400
    assert "module_id" in response.json()


@pytest.mark.django_db
def test_execution_rejects_missing_business_parameters_before_queue():
    user = get_user_model().objects.create_user("parameter-user", password="strong-test-password")
    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        "/api/v1/executions/",
        {"module_id": "evolution_zd", "quarter": "T3_2026", "parameters": {}},
        format="json",
    )
    assert response.status_code == 400
    messages = " ".join(response.json()["parameters"])
    assert "Lundi de la semaine" in messages
    assert "Semaine_ref.xlsx" in messages
    assert "versions de la base" in messages
    assert "Cohortes de réinterrogation" not in messages
