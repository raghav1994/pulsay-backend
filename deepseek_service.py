"""
DeepSeek API integration for AI-powered comment analysis and suggestions.
Falls back gracefully if the API is unavailable or the key is not set.
"""

from __future__ import annotations

import json
import logging

import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

_HEADERS = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json",
}


def _chat(messages: list[dict], temperature: float = 0.7, max_tokens: int = 512, timeout: int = 20) -> str | None:
    """Send a chat request to DeepSeek. Returns the response text or None on failure."""
    if not DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY not set — skipping AI call.")
        return None

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=_HEADERS,
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.error("DeepSeek API error: %s", exc)
        return None


def ai_suggestion(distribution: dict, dominant: str, platform: str = "instagram") -> str | None:
    """
    Generate a creator content suggestion using DeepSeek.
    Returns None if the API call fails (caller should fall back to rule-based suggestion).
    """
    dist_summary = ", ".join(f"{k}: {v}%" for k, v in distribution.items())

    messages = [
        {
            "role": "system",
            "content": (
                "You are a sharp, concise creator coach who advises Indian social media creators. "
                "Give ONE punchy, actionable suggestion in 1-2 sentences. "
                "Mix Hindi and English naturally (Hinglish). No bullet points, no preamble."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Platform: {platform}\n"
                f"Audience emotion breakdown — {dist_summary}\n"
                f"Dominant mood: {dominant}\n\n"
                "What should the creator do in their next post?"
            ),
        },
    ]

    return _chat(messages, temperature=0.8, max_tokens=120)


def ai_deep_analysis(
    distribution: dict,
    dominant: str,
    top_positive: list[str],
    top_negative: list[str],
    platform: str = "instagram",
    caption: str = "",
    handle: str = "",
    full_comments: list[dict] | None = None,
    profile: dict | None = None,
) -> dict | None:
    """
    Run a comprehensive AI perception analysis.
    Returns a rich structured dict (14+ fields) or None on failure.
    When full_comments and profile are provided, the analysis is deeply personalised.
    """
    dist_summary = ", ".join(f"{k}: {v}%" for k, v in distribution.items())

    # Build a deduplicated comment sample (up to 45 comments, max 150 chars each)
    comment_sample: list[str] = []
    if full_comments:
        seen: set[str] = set()
        for c in full_comments[:120]:
            text = (c.get("text") or "").strip()
            if text and text not in seen:
                seen.add(text)
                comment_sample.append(text[:150])
                if len(comment_sample) >= 45:
                    break
    # Fall back to top positive/negative if no full comments
    if not comment_sample:
        comment_sample = (top_positive or [])[:5] + (top_negative or [])[:5]

    comments_block = "\n".join(f'- "{t}"' for t in comment_sample) if comment_sample else "(no comments available)"

    # Build profile context line
    profile_line = ""
    if profile:
        parts = []
        if profile.get("full_name"): parts.append(profile["full_name"])
        if profile.get("posts_analyzed"): parts.append(f"{profile['posts_analyzed']} posts scraped")
        if profile.get("comments_analyzed"): parts.append(f"{profile['comments_analyzed']} comments collected")
        if profile.get("avg_likes"): parts.append(f"avg {profile['avg_likes']:,} likes/post")
        profile_line = " · ".join(parts)

    messages = [
        {
            "role": "system",
            "content": (
                "You are India's sharpest social media reputation analyst. "
                "You deeply understand Indian internet culture, Hinglish, creator fandom dynamics, "
                "and the difference between real fans, casual scrollers, and trolls on Instagram.\n\n"
                "Respond ONLY with a single valid JSON object — no markdown fences, no text outside the JSON.\n\n"
                'Return ALL of these keys:\n'
                '{\n'
                '  "summary": "2-3 sentence Hinglish audience mood summary — personal, sharp, creator-first tone",\n'
                '  "insight": "one killer observation about what the audience REALLY thinks (not surface-level)",\n'
                '  "action": "one concrete, specific, high-impact next step for the creator",\n'
                '  "risk": "the biggest reputation threat right now — one sentence, brutally honest",\n'
                '  "sentiment_score": <integer 0-100, 100 = fully positive>,\n'
                '  "reputation_score": <integer 0-100 overall perception health>,\n'
                '  "reputation_label": "<2-3 word label e.g. Trusted Voice, Rising Star, Under Scrutiny, Crowd Favourite>",\n'
                '  "audience_dna": [\n'
                '    {"segment": "<name>", "pct": <number>, "description": "<1-2 sentences: who they are and what they want from this creator>"},\n'
                '    ... exactly 4 segments\n'
                '  ],\n'
                '  "reputation_drivers": ["<driver 1>", "<driver 2>", ...],  // 5-6 strings mixing positive and negative factors\n'
                '  "top_narratives": [\n'
                '    {"label": "<how a segment of the audience describes this creator>", "pct": <number>},\n'
                '    ... 6 items summing to ~100\n'
                '  ],\n'
                '  "hinglish_positive": ["<actual comment text from the sample>", ...],  // up to 3 Hinglish/positive quotes\n'
                '  "hinglish_negative": ["<actual comment text from the sample>", ...],  // up to 3 Hinglish/critical quotes\n'
                '  "troll_risk": "<low or medium or high>",\n'
                '  "troll_comments": ["<actual troll/hostile comment from the sample>", ...],  // up to 3\n'
                '  "audience_geography": [\n'
                '    {"label": "India - Tier 1 metros", "pct": <number>},\n'
                '    {"label": "India - Tier 2 cities", "pct": <number>},\n'
                '    {"label": "India - Tier 3 towns", "pct": <number>},\n'
                '    {"label": "International / diaspora", "pct": <number>}\n'
                '  ],\n'
                '  "recommendations": [\n'
                '    {"title": "<short imperative>", "body": "<2-3 sentence strategy with specific, actionable steps>"},\n'
                '    {"title": "<short imperative>", "body": "..."},\n'
                '    {"title": "<short imperative>", "body": "..."}\n'
                '  ]\n'
                '}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"Platform: {platform}\n"
                f"Handle: @{handle or 'creator'}\n"
                f"{profile_line}\n"
                f"Latest post caption: {(caption or '').strip()[:300] or '(not provided)'}\n"
                f"Emotion breakdown: {dist_summary}\n"
                f"Dominant emotion: {dominant}\n\n"
                f"Comment sample ({len(comment_sample)} comments):\n"
                f"{comments_block}\n\n"
                "Give the complete JSON. Be brutally honest, hyperpersonalised, and specific to the actual comments above."
            ),
        },
    ]

    raw = _chat(messages, temperature=0.4, max_tokens=2200, timeout=60)
    if not raw:
        return None

    try:
        # Strip accidental markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 2)[-1] if cleaned.count("```") >= 2 else cleaned
            cleaned = cleaned.removeprefix("json").strip()
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("DeepSeek returned non-JSON for deep analysis: %s", raw[:300])
        return None
