"""Initial schema for videos, transcripts, advertisers, and mentions.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("youtube_video_id", sa.String(length=32), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("channel_name", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column("transcript_status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_videos_youtube_video_id", "videos", ["youtube_video_id"], unique=True)

    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_seconds", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transcript_segments_video_id", "transcript_segments", ["video_id"])

    op.create_table(
        "advertisers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_advertisers_name", "advertisers", ["name"], unique=True)

    op.create_table(
        "advertiser_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "advertiser_id",
            sa.Integer(),
            sa.ForeignKey("advertisers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_advertiser_aliases_advertiser_id", "advertiser_aliases", ["advertiser_id"])
    op.create_index("ix_advertiser_aliases_alias", "advertiser_aliases", ["alias"])

    op.create_table(
        "mentions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "advertiser_id",
            sa.Integer(),
            sa.ForeignKey("advertisers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transcript_segment_id",
            sa.Integer(),
            sa.ForeignKey("transcript_segments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("timestamp_seconds", sa.Float(), nullable=False),
        sa.Column("matched_text", sa.Text(), nullable=False),
        sa.Column("mention_type", sa.String(length=50), nullable=False, server_default="unknown"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mentions_video_id", "mentions", ["video_id"])
    op.create_index("ix_mentions_advertiser_id", "mentions", ["advertiser_id"])


def downgrade() -> None:
    op.drop_table("mentions")
    op.drop_table("advertiser_aliases")
    op.drop_table("advertisers")
    op.drop_table("transcript_segments")
    op.drop_table("videos")
