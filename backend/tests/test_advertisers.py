from fastapi.testclient import TestClient


def test_advertiser_crud_and_aliases(client: TestClient) -> None:
    created = client.post(
        "/api/advertisers",
        json={"name": "Feldman Automotive", "aliases": ["Feldman", "Feldman Auto"]},
    )
    assert created.status_code == 201
    body = created.json()
    advertiser_id = body["id"]
    assert body["name"] == "Feldman Automotive"
    assert [item["alias"] for item in body["aliases"]] == ["Feldman", "Feldman Auto"]

    listed = client.get("/api/advertisers")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Feldman Automotive"

    fetched = client.get(f"/api/advertisers/{advertiser_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == advertiser_id

    renamed = client.put(f"/api/advertisers/{advertiser_id}", json={"name": "Feldman Automotive Group"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Feldman Automotive Group"

    extra = client.post(f"/api/advertisers/{advertiser_id}/aliases", json={"alias": "Feldman Auto Group"})
    assert extra.status_code == 201
    alias_id = next(item["id"] for item in extra.json()["aliases"] if item["alias"] == "Feldman Auto Group")

    removed = client.delete(f"/api/advertisers/{advertiser_id}/aliases/{alias_id}")
    assert removed.status_code == 200
    assert "Feldman Auto Group" not in [item["alias"] for item in removed.json()["aliases"]]

    deleted = client.delete(f"/api/advertisers/{advertiser_id}")
    assert deleted.status_code == 204
    missing = client.get(f"/api/advertisers/{advertiser_id}")
    assert missing.status_code == 404


def test_advertiser_duplicate_name_rejected(client: TestClient) -> None:
    first = client.post("/api/advertisers", json={"name": "Feldman Automotive"})
    assert first.status_code == 201
    duplicate = client.post("/api/advertisers", json={"name": "feldman automotive"})
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]


def test_advertiser_duplicate_alias_rejected(client: TestClient) -> None:
    created = client.post("/api/advertisers", json={"name": "Feldman Automotive", "aliases": ["Feldman"]})
    advertiser_id = created.json()["id"]

    duplicate = client.post(f"/api/advertisers/{advertiser_id}/aliases", json={"alias": "feldman"})
    assert duplicate.status_code == 409

    same_as_name = client.post(f"/api/advertisers/{advertiser_id}/aliases", json={"alias": "Feldman Automotive"})
    assert same_as_name.status_code == 409


def test_advertiser_not_found(client: TestClient) -> None:
    response = client.get("/api/advertisers/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
