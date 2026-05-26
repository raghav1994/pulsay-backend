"""
Apify integration for public Instagram scraping.
Used in demo/manual mode when a user enters any Instagram handle.
Meta OAuth-connected accounts use instagram_service.py instead.
"""

from __future__ import annotations

import logging

import requests

from config import (
    APIFY_INSTAGRAM_ACTOR,
    APIFY_INSTAGRAM_PROFILE_ACTOR,
    APIFY_RESULTS_LIMIT,
    APIFY_TIMEOUT_SECONDS,
    APIFY_TOKEN,
)

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"


def _run_actor(actor_id: str, actor_input: dict) -> list[dict]:
    """
    Run an Apify actor synchronously and return the dataset items.
    Uses the run-sync-get-dataset-items endpoint — one call, waits for result.
    Raises on missing token or HTTP errors.
    """
    if not APIFY_TOKEN:
        raise RuntimeError("APIFY_TOKEN is not configured.")

    # Normalise actor id: apify/name or apify~name both work
    actor_id_url = actor_id.replace("~", "/")

    url = f"{APIFY_BASE}/acts/{actor_id_url}/run-sync-get-dataset-items"
    params = {
        "token": APIFY_TOKEN,
        "timeout": APIFY_TIMEOUT_SECONDS,
        "memory": 512,
    }

    try:
        resp = requests.post(url, json=actor_input, params=params, timeout=APIFY_TIMEOUT_SECONDS + 10)
        resp.raise_for_status()
        return resp.json() if isinstance(resp.json(), list) else []
    except requests.HTTPError as exc:
        logger.error("Apify actor %s failed: %s — %s", actor_id, exc, exc.response.text[:300])
        raise
    except Exception as exc:
        logger.error("Apify request error: %s", exc)
        raise


def get_profile(username: str) -> dict | None:
    """
    Fetch public profile metadata for an Instagram username.
    Returns normalised dict with: username, full_name, bio, followers, following, posts_count, profile_pic_url.
    Returns None on failure.
    """
    clean = username.lstrip("@").strip().lower()
    try:
        items = _run_actor(
            APIFY_INSTAGRAM_PROFILE_ACTOR,
            {"usernames": [clean]},
        )
        if not items:
            return None

        raw = items[0]
        return {
            "username": raw.get("username", clean),
            "full_name": raw.get("fullName") or raw.get("full_name", ""),
            "bio": raw.get("biography") or raw.get("bio", ""),
            "followers": raw.get("followersCount") or raw.get("followers_count", 0),
            "following": raw.get("followsCount") or raw.get("follows_count", 0),
            "posts_count": raw.get("postsCount") or raw.get("posts_count", 0),
            "profile_pic_url": raw.get("profilePicUrl") or raw.get("profile_pic_url", ""),
            "is_verified": raw.get("verified", False),
            "is_business": raw.get("isBusinessAccount", False),
        }
    except Exception as exc:
        logger.warning("get_profile(%s) failed: %s", clean, exc)
        return None


def get_posts(username: str, limit: int | None = None) -> list[dict]:
    """
    Fetch recent public posts for an Instagram username.
    Returns list of normalised post dicts.
    """
    clean = username.lstrip("@").strip().lower()
    limit = limit or APIFY_RESULTS_LIMIT

    try:
        items = _run_actor(
            APIFY_INSTAGRAM_ACTOR,
            {
                "usernames": [clean],
                "resultsType": "posts",
                "resultsLimit": limit,
                "addParentData": False,
            },
        )

        posts = []
        for raw in items:
            posts.append({
                "id": raw.get("id") or raw.get("shortCode", ""),
                "shortcode": raw.get("shortCode", ""),
                "caption": raw.get("caption", ""),
                "likes": raw.get("likesCount") or raw.get("likes_count", 0),
                "comments_count": raw.get("commentsCount") or raw.get("comments_count", 0),
                "timestamp": raw.get("timestamp", ""),
                "url": raw.get("url") or f"https://www.instagram.com/p/{raw.get('shortCode', '')}",
                "platform": "instagram",
            })

        return posts
    except Exception as exc:
        logger.warning("get_posts(%s) failed: %s", clean, exc)
        return []


def get_comments(username: str, post_shortcode: str | None = None, limit: int | None = None) -> list[dict]:
    """
    Fetch comments for a specific post (by shortcode) or the latest post of a username.
    Returns list of normalised comment dicts.
    """
    clean = username.lstrip("@").strip().lower()
    limit = limit or APIFY_RESULTS_LIMIT

    actor_input: dict = {
        "resultsType": "comments",
        "resultsLimit": limit,
        "addParentData": True,
    }

    if post_shortcode:
        actor_input["directUrls"] = [f"https://www.instagram.com/p/{post_shortcode}/"]
    else:
        actor_input["usernames"] = [clean]

    try:
        items = _run_actor(APIFY_INSTAGRAM_ACTOR, actor_input)

        comments = []
        for raw in items:
            comments.append({
                "id": raw.get("id", ""),
                "text": raw.get("text") or raw.get("ownerFullName", ""),
                "username": raw.get("ownerUsername") or raw.get("owner", {}).get("username", "unknown"),
                "like_count": raw.get("likesCount") or raw.get("likes_count", 0),
                "timestamp": raw.get("timestamp", ""),
            })

        return comments
    except Exception as exc:
        logger.warning("get_comments(%s) failed: %s", clean, exc)
        return []
