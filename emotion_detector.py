import re
from collections import Counter

EMOTIONS = ["joy", "hype", "timepass", "anger", "sadness", "cringe"]

EMOTION_PATTERNS = {
    "joy": [
        r"\b(op|fire|best|amazing|awesome|great|good|nice|love|like|happy|enjoy|fun|funny|lol|lmao|mast|badhiya|zabardast|respect)\b",
        r"\b(bhai.*(op|fire|best)|wah.*bhai|kya.*baat|mast.*hai|badhiya.*hai)\b",
    ],
    "hype": [
        r"\b(hype|excited|waiting|next|upcoming|soon|drop|release|viral|trending|goat|carryminati|blast|explode)\b",
        r"\b(next.*level|follow.*up|part.*2|series|collab)\b",
    ],
    "timepass": [
        r"\b(boring|timepass|time waste|scroll|random|bore|same|repetitive|template|thak)\b",
        r"\b(bas.*dekh|bas.*scroll|kuch.*nahi|same.*cheez)\b",
    ],
    "anger": [
        r"\b(hate|angry|mad|annoying|worst|terrible|bad|ganda|bekar|bkwas|bakwaas|ghatiya|faltu)\b",
        r"\b(bas.*karo|itna.*ganda|kya.*bakwaas)\b",
    ],
    "sadness": [
        r"\b(sad|cry|crying|miss|old|pehle|before|nostalgic|udas|dukhi|rona)\b",
        r"\b(pehle.*jaisa|maza.*nahi|miss.*karta|purana.*wala)\b",
    ],
    "cringe": [
        r"\b(cringe|cringy|awkward|weird|uncomfortable|secondhand)\b",
        r"\b(itna.*cringe|cringe.*hai|awkward.*hai|weird.*lag)\b",
    ],
}


def detect_emotion(text):
    if not text:
        return "timepass", 0.3

    text_lower = text.lower()
    scores = {}

    for emotion, patterns in EMOTION_PATTERNS.items():
        score = 0
        for pattern in patterns:
            score += len(re.findall(pattern, text_lower))
        scores[emotion] = score

    if max(scores.values()) == 0:
        return "timepass", 0.3

    dominant = max(scores, key=scores.get)
    confidence = min(0.5 + (scores[dominant] * 0.15), 0.95)
    return dominant, round(confidence, 2)


def analyze_comments(comments):
    analyzed_comments = []
    emotions = []

    for comment in comments:
        emotion, confidence = detect_emotion(comment.get("text", ""))
        analyzed_comments.append(
            {
                "id": comment.get("id"),
                "text": comment.get("text", ""),
                "username": comment.get("username", "unknown"),
                "like_count": comment.get("like_count", 0),
                "emotion": emotion,
                "confidence": confidence,
            }
        )
        emotions.append(emotion)

    total = len(emotions)
    counts = Counter(emotions)

    if total == 0:
        distribution = {emotion: 0 for emotion in EMOTIONS}
        dominant = "timepass"
    else:
        distribution = {
            emotion: round((counts.get(emotion, 0) / total) * 100)
            for emotion in EMOTIONS
        }
        dominant = max(distribution, key=distribution.get)

    top_positive = max(
        [comment for comment in analyzed_comments if comment["emotion"] in ["joy", "hype"]],
        key=lambda item: item["like_count"],
        default=None,
    )
    top_negative = max(
        [comment for comment in analyzed_comments if comment["emotion"] in ["anger", "sadness", "cringe"]],
        key=lambda item: item["like_count"],
        default=None,
    )

    return {
        "dominant_emotion": dominant,
        "distribution": distribution,
        "total_comments": total,
        "analyzed_comments": analyzed_comments,
        "top_positive": [top_positive["text"]] if top_positive else [],
        "top_negative": [top_negative["text"]] if top_negative else [],
    }


def _rule_based_suggestion(distribution, dominant):
    """Fallback rule-based suggestion when DeepSeek is unavailable."""
    joy = distribution.get("joy", 0)
    anger = distribution.get("anger", 0)
    timepass = distribution.get("timepass", 0)
    hype = distribution.get("hype", 0)
    sadness = distribution.get("sadness", 0)

    if timepass > 40 and joy < 20:
        return "Log thak gaye hain. Format break karo: behind the scenes ya Q&A try karo."
    if anger > 30:
        return "Controversy chal rahi hai. Top negative comment pe calm reply do ya next post positive rakho."
    if hype > 50:
        return "Viral potential. Abhi follow-up story daalo ya best comment pin karo."
    if joy > 60:
        return "Log khush hain. Same energy maintain karo. Isko series ya collab mein convert karo."
    if sadness > 30:
        return "Log purane content miss kar rahe hain. Nostalgic throwback ya then-vs-now try karo."
    if dominant == "cringe":
        return "Execution awkward lag rahi hai. Hook simple rakho aur punchline faster lao."

    return "Stable mood. Next post mein storytelling hook aur audience question add karo."


def generate_suggestion(distribution, dominant, platform="instagram"):
    """
    Generate a creator suggestion — tries DeepSeek AI first, falls back to rules.
    """
    try:
        from deepseek_service import ai_suggestion
        result = ai_suggestion(distribution, dominant, platform=platform)
        if result:
            return result
    except Exception:
        pass

    return _rule_based_suggestion(distribution, dominant)
