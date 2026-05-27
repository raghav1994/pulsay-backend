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

    # Apify requires tilde in URLs: apify~instagram-scraper (not slash)
    actor_id_url = actor_id.replace("/", "~")

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
    Fetch public profile metadata by scraping the latest post and reading owner fields.
    Uses directUrls (the only reliable approach for apify/instagram-scraper).
    Returns normalised dict or None on failure.
    """
    clean = username.lstrip("@").strip().lower()
    try:
        items = _run_actor(
            APIFY_INSTAGRAM_ACTOR,
            {
                "directUrls": [f"https://www.instagram.com/{clean}/"],
                "resultsType": "posts",
                "resultsLimit": 1,
            },
        )
        if not items or items[0].get("error"):
            return None

        raw = items[0]
        return {
            "username": raw.get("ownerUsername", clean),
            "full_name": raw.get("ownerFullName", ""),
            "bio": "",  # not available from post scrape; requires profile endpoint
            "followers": 0,  # not available from post scrape
            "following": 0,
            "posts_count": 0,
            "profile_pic_url": "",
            "is_verified": False,
            "is_business": False,
        }
    except Exception as exc:
        logger.warning("get_profile(%s) failed: %s", clean, exc)
        return None


def get_posts(username: str, limit: int | None = None) -> list[dict]:
    """
    Fetch recent public posts for an Instagram username using directUrls.
    Returns list of normalised post dicts.
    """
    clean = username.lstrip("@").strip().lower()
    limit = limit or APIFY_RESULTS_LIMIT

    try:
        items = _run_actor(
            APIFY_INSTAGRAM_ACTOR,
            {
                "directUrls": [f"https://www.instagram.com/{clean}/"],
                "resultsType": "posts",
                "resultsLimit": limit,
            },
        )

        posts = []
        for raw in items:
            if raw.get("error"):
                continue
            # Extract latestComments bundled inside the post object
            latest_comments = [
                {
                    "id": c.get("id", ""),
                    "text": c.get("text", ""),
                    "username": c.get("ownerUsername", "unknown"),
                    "like_count": c.get("likesCount", 0),
                    "timestamp": c.get("timestamp", ""),
                }
                for c in raw.get("latestComments", [])
                if c.get("text", "").strip()
            ]
            posts.append({
                "id": raw.get("id") or raw.get("shortCode", ""),
                "shortcode": raw.get("shortCode", ""),
                "caption": raw.get("caption", ""),
                "likes": raw.get("likesCount", 0),
                "comments_count": raw.get("commentsCount", 0),
                "timestamp": raw.get("timestamp", ""),
                "url": raw.get("url") or f"https://www.instagram.com/p/{raw.get('shortCode', '')}",
                "owner_username": raw.get("ownerUsername", clean),
                "owner_full_name": raw.get("ownerFullName", ""),
                "platform": "instagram",
                "latest_comments": latest_comments,
            })

        return posts
    except Exception as exc:
        logger.warning("get_posts(%s) failed: %s", clean, exc)
        return []


def get_comments(username: str, post_shortcode: str | None = None, limit: int | None = None) -> list[dict]:
    """
    Fetch comments from a post via directUrls.
    Uses post shortcode if provided, otherwise fetches from latest post of username.
    Returns list of normalised comment dicts.
    """
    clean = username.lstrip("@").strip().lower()
    limit = limit or APIFY_RESULTS_LIMIT

    if post_shortcode:
        url = f"https://www.instagram.com/p/{post_shortcode}/"
    else:
        url = f"https://www.instagram.com/{clean}/"

    try:
        items = _run_actor(
            APIFY_INSTAGRAM_ACTOR,
            {
                "directUrls": [url],
                "resultsType": "comments",
                "resultsLimit": limit,
            },
        )

        comments = []
        for raw in items:
            if raw.get("error"):
                continue
            # latestComments array inside a post OR top-level comment items
            if "latestComments" in raw:
                for c in raw["latestComments"]:
                    comments.append({
                        "id": c.get("id", ""),
                        "text": c.get("text", ""),
                        "username": c.get("ownerUsername", "unknown"),
                        "like_count": c.get("likesCount", 0),
                        "timestamp": c.get("timestamp", ""),
                    })
            else:
                comments.append({
                    "id": raw.get("id", ""),
                    "text": raw.get("text", ""),
                    "username": raw.get("ownerUsername", "unknown"),
                    "like_count": raw.get("likesCount", 0),
                    "timestamp": raw.get("timestamp", ""),
                })

        return comments
    except Exception as exc:
        logger.warning("get_comments(%s) failed: %s", clean, exc)
        return []
