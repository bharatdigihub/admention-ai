from fastapi.testclient import TestClient

from app.models.advertiser import Advertiser, AdvertiserAlias
from app.models.transcript import TranscriptSegment
from app.models.video import Video


def _seed_video(db, youtube_id: str = "dQw4w9WgXcQ") -> Video:
    video = Video(
        youtube_video_id=youtube_id,
        url=f"https://www.youtube.com/watch?v={youtube_id}",
        title="Sports show",
        transcript_status="available",
    )
    db.add(video)
    db.flush()
    db.add_all(
        [
            TranscriptSegment(video_id=video.id, start_seconds=100.0, duration_seconds=3.0, text="Welcome back to the show"),
            TranscriptSegment(
                video_id=video.id,
                start_seconds=872.4,
                duration_seconds=4.2,
                text="Today's show is brought to you by Feldman Automotive",
            ),
            TranscriptSegment(video_id=video.id, start_seconds=880.0, duration_seconds=3.0, text="Stay tuned after the break"),
            TranscriptSegment(
                video_id=video.id,
                start_seconds=2838.0,
                duration_seconds=4.0,
                text="We want to thank FELDMAN AUTOMOTIVE for supporting today's show",
            ),
        ]
    )
    db.commit()
    db.refresh(video)
    return video


def test_case_insensitive_mention_matching(client: TestClient, db) -> None:
    _seed_video(db)
    response = client.post(
        "/api/mentions/search",
        json={"video_id": "dQw4w9WgXcQ", "advertiser": "Feldman Automotive"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_mentions"] == 2
    assert body["mentions"][0]["timestamp"] == "00:14:32"
    assert body["mentions"][0]["youtube_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=872s"
    assert body["mentions"][0]["context_before"] == "Welcome back to the show"
    assert body["mentions"][0]["context_after"] == "Stay tuned after the break We want to thank FELDMAN AUTOMOTIVE for supporting today's show"
    assert body["mentions"][0]["mention_type"] == "unknown"
    assert body["mentions"][0]["confidence"] == 1.0
    assert body["mentions"][1]["matched_text"] == "FELDMAN AUTOMOTIVE"


def test_alias_matching(client: TestClient, db) -> None:
    video = _seed_video(db)
    advertiser = Advertiser(name="Feldman Automotive")
    db.add(advertiser)
    db.flush()
    db.add(AdvertiserAlias(advertiser_id=advertiser.id, alias="Feldman Auto"))
    db.add(
        TranscriptSegment(
            video_id=video.id,
            start_seconds=12.0,
            duration_seconds=2.0,
            text="Visit Feldman Auto this weekend",
        )
    )
    db.commit()

    response = client.post(
        "/api/mentions/search",
        json={"video_id": "dQw4w9WgXcQ", "advertiser": "Feldman Automotive"},
    )
    assert response.status_code == 200
    texts = [item["matched_text"] for item in response.json()["mentions"]]
    assert "Feldman Auto" in texts
    assert response.json()["total_mentions"] == 3


def test_empty_search_results(client: TestClient, db) -> None:
    _seed_video(db)
    response = client.post(
        "/api/mentions/search",
        json={"video_id": "dQw4w9WgXcQ", "advertiser": "Acme Insurance"},
    )
    assert response.status_code == 200
    assert response.json() == {"advertiser": "Acme Insurance", "total_mentions": 0, "mentions": []}


def test_search_requires_existing_video(client: TestClient) -> None:
    response = client.post(
        "/api/mentions/search",
        json={"video_id": "xxxxxxxxxxx", "advertiser": "Feldman Automotive"},
    )
    assert response.status_code == 404


def test_word_boundary_ignores_partial_words(client: TestClient, db) -> None:
    video = Video(
        youtube_video_id="bbbbbbbbbbb",
        url="https://www.youtube.com/watch?v=bbbbbbbbbbb",
        title="Unrelated show",
        transcript_status="available",
    )
    db.add(video)
    db.flush()
    db.add(
        TranscriptSegment(
            video_id=video.id,
            start_seconds=12.0,
            duration_seconds=2.0,
            text="Feldmanesque branding is unrelated",
        )
    )
    db.commit()
    response = client.post(
        "/api/mentions/search",
        json={"video_id": "bbbbbbbbbbb", "advertiser": "Feldman"},
    )
    assert response.status_code == 200
    assert response.json()["total_mentions"] == 0


def test_alias_confidence_is_deterministic(client: TestClient, db) -> None:
    video = _seed_video(db)
    advertiser = Advertiser(name="Feldman Automotive")
    db.add(advertiser)
    db.flush()
    db.add(AdvertiserAlias(advertiser_id=advertiser.id, alias="Feldman Auto"))
    db.add(
        TranscriptSegment(
            video_id=video.id,
            start_seconds=12.0,
            duration_seconds=2.0,
            text="Visit Feldman Auto this weekend",
        )
    )
    db.commit()

    response = client.post(
        "/api/mentions/search",
        json={"video_id": "dQw4w9WgXcQ", "advertiser": "Feldman Automotive"},
    )
    alias_hit = next(item for item in response.json()["mentions"] if item["matched_text"] == "Feldman Auto")
    assert alias_hit["mention_type"] == "unknown"
    assert alias_hit["confidence"] == 0.9


def test_context_window_is_configurable(client: TestClient, db) -> None:
    _seed_video(db)
    response = client.post(
        "/api/mentions/search",
        json={
            "video_id": "dQw4w9WgXcQ",
            "advertiser": "Feldman Automotive",
            "context_before": 0,
            "context_after": 0,
        },
    )
    assert response.status_code == 200
    assert response.json()["mentions"][0]["context_before"] == ""
    assert response.json()["mentions"][0]["context_after"] == ""


def test_mentions_are_persisted(client: TestClient, db) -> None:
    from app.models.mention import Mention

    _seed_video(db)
    client.post("/api/mentions/search", json={"video_id": "dQw4w9WgXcQ", "advertiser": "Feldman Automotive"})
    stored = db.query(Mention).all()
    assert len(stored) == 2
    assert {item.mention_type for item in stored} == {"unknown"}
    assert stored[0].timestamp_seconds == 872.4
