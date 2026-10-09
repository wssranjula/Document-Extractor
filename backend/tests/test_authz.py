from app.db import SessionLocal
from app.models import Reference


def _signup(client, email: str) -> str:
    response = client.post("/auth/signup", json={"email": email, "password": "password123"})
    assert response.status_code == 201
    return response.json()["access_token"]


def _reference_id() -> str:
    with SessionLocal() as session:
        reference = Reference(name="Formulary", filename="reference.docx", storage_path="reference.docx")
        session.add(reference)
        session.commit()
        return reference.id


def test_user_cannot_read_another_users_job_or_file(client):
    owner = _signup(client, "owner@example.com")
    other = _signup(client, "other@example.com")
    response = client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {owner}"},
        data={"reference_id": _reference_id()},
        files={"file": ("discharge.docx", b"discharge text", "application/octet-stream")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    job_id = body["job_id"]

    status = client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {owner}"})
    assert status.status_code == 200
    assert [stage["status"] for stage in status.json()["stages"]] == ["pending"] * 8

    for path in (f"/jobs/{job_id}", f"/jobs/{job_id}/result", f"/jobs/{job_id}/file"):
        denied = client.get(path, headers={"Authorization": f"Bearer {other}"})
        assert denied.status_code == 404
