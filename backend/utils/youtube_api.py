"""
YouTube Data API v3 wrapper.
Falls back gracefully when API key is not provided — yt-dlp is used instead.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from any YouTube URL format."""
    import re

    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com\/watch\?.*?&v=([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def fetch_youtube_metadata(video_id: str, api_key: str) -> Dict[str, Any]:
    """
    Fetch rich metadata from YouTube Data API v3.
    Returns dict with: title, description, tags, upload_date, views, likes,
                       thumbnail_url, captions (if available), channel.
    """
    try:
        from googleapiclient.discovery import build  # type: ignore

        youtube = build("youtube", "v3", developerKey=api_key)

        # Video details
        video_resp = (
            youtube.videos()
            .list(
                part="snippet,statistics,contentDetails",
                id=video_id,
            )
            .execute()
        )

        if not video_resp.get("items"):
            logger.warning(f"No YouTube API results for video ID: {video_id}")
            return {}

        item = video_resp["items"][0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})

        # Captions
        captions_text = await _fetch_captions(youtube, video_id)

        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = (
            thumbnails.get("maxres", {}).get("url")
            or thumbnails.get("high", {}).get("url")
            or thumbnails.get("default", {}).get("url")
        )

        return {
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "tags": snippet.get("tags", []),
            "upload_date": snippet.get("publishedAt", ""),
            "channel": snippet.get("channelTitle", ""),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "thumbnail_url": thumbnail_url,
            "duration": content.get("duration", ""),
            "captions": captions_text,
            "language": snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage", ""),
        }

    except Exception as e:
        logger.error(f"YouTube API fetch failed: {e}")
        return {}


async def _fetch_captions(youtube: Any, video_id: str) -> Optional[str]:
    """Attempt to fetch auto-generated or manual captions."""
    try:
        captions_resp = (
            youtube.captions().list(part="snippet", videoId=video_id).execute()
        )
        items = captions_resp.get("items", [])
        if not items:
            return None

        # Prefer English, then first available
        caption_id = None
        for item in items:
            lang = item["snippet"].get("language", "")
            if lang.startswith("en"):
                caption_id = item["id"]
                break
        if not caption_id and items:
            caption_id = items[0]["id"]

        if caption_id:
            caption_data = (
                youtube.captions().download(id=caption_id, tfmt="srt").execute()
            )
            return caption_data.decode("utf-8") if isinstance(caption_data, bytes) else str(caption_data)

    except Exception as e:
        logger.debug(f"Caption fetch failed (non-critical): {e}")
    return None
