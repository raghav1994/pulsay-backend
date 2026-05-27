import logging
from datetime import datetime, timedelta
from secrets import randbelow

logger = logging.getLogger(__name__)

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from auth_service import get_current_user, login_user, register_user
from config import INSTAGRAM_PROVIDER, USER_ID
from deepseek_service import ai_deep_analysis
from emotion_detector import analyze_comments, generate_suggestion
from instagram_service import get_comments, get_posts
from mock_data import get_mock_comments, get_mock_posts

app = FastAPI(title="Pulsay API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "https://app.pulsay.in",
        "https://www.pulsay.in",
        "https://pulsay.in",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreatorClaimRequest(BaseModel):
    platform: str = Field(..., min_length=1)
    handle: str = Field(..., min_length=1)


class CreatorVerifyRequest(BaseModel):
    platform: str = Field(..., min_length=1)
    handle: str = Field(..., min_length=1)
    verification_code: str = Field(..., min_length=3)


class CreatorSourceUpdateRequest(BaseModel):
    platform: str = Field(..., min_length=1)
    handle: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    name: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class PaymentConfirmRequest(BaseModel):
    plan_id: str = Field(..., min_length=1)
    plan_name: str = Field(..., min_length=1)
    billing: str = Field(..., min_length=1)
    amount: int = Field(..., gt=0)
    method: str = Field(..., min_length=1)
    checkout_id: str = Field(..., min_length=1)


VERIFICATION_TTL_MINUTES = 10
MAX_FAILED_ATTEMPTS = 5
DEMO_USER_ID = "demo_user"
creator_claims = {}
creator_sources = {
    (DEMO_USER_ID, "instagram"): {"platform": "instagram", "handle": "aaravspeaks", "status": "matched"},
    (DEMO_USER_ID, "youtube"): {"platform": "youtube", "handle": "Aarav Speaks", "status": "matched"},
    (DEMO_USER_ID, "x"): {"platform": "x", "handle": "aaravbuilds", "status": "pending_verification"},
    (DEMO_USER_ID, "linkedin"): {"platform": "linkedin", "handle": "", "status": "needs_reconnect"},
    (DEMO_USER_ID, "facebook"): {"platform": "facebook", "handle": "Aarav Mehta Official", "status": "matched"},
}
subscriptions = {}
audit_events = []


def normalize_handle(handle):
    return handle.strip().lower().lstrip("@")


def claim_key(user_id, platform, handle):
    return (user_id, platform.strip().lower(), normalize_handle(handle))


def log_audit(event_type, request, **metadata):
    audit_events.append(
        {
            "event_type": event_type,
            "ip": request.client.host if request.client else "unknown",
            "created_at": datetime.utcnow().isoformat(),
            **metadata,
        }
    )


def generate_verification_code():
    return f"LOK-{randbelow(9000) + 1000}"


def get_mock_public_profile(platform, handle, verification_code=None):
    clean_handle = normalize_handle(handle)
    bio = "Comedy creator. Building funny office-life stories and practical creator lessons."

    if verification_code:
        # TODO: Replace this mock bio with a real platform profile lookup.
        bio = f"{bio} {verification_code}"

    return {
        "platform": platform,
        "handle": f"@{clean_handle}",
        "creator_name": "Aarav Mehta" if clean_handle in {"aaravspeaks", "aarav", "aaravmehta"} else clean_handle.replace("_", " ").title(),
        "bio": bio,
        "followers": "128K",
        "niche": "Comedy creator",
        "public_mood": "Mostly positive",
        "score_range": "70-80",
        "preview_notice": "Public preview only. Private insights require creator ownership verification.",
    }


def get_claim_or_404(user_id, platform, handle):
    key = claim_key(user_id, platform, handle)
    claim = creator_claims.get(key)

    if not claim:
        raise HTTPException(status_code=404, detail="No active claim found. Start a claim first.")

    return claim


def is_verified(user_id, platform, handle):
    claim = creator_claims.get(claim_key(user_id, platform, handle))
    return bool(claim and claim["verification_status"] == "verified")


def format_comments(raw_comments):
    return [
        {
            "id": comment.get("id"),
            "text": comment.get("text", ""),
            "username": comment.get("username", "unknown"),
            "like_count": comment.get("like_count", 0),
        }
        for comment in raw_comments
    ]


def build_response(post, comments, source="mock", platform="instagram"):
    analysis = analyze_comments(comments)
    suggestion = generate_suggestion(
        analysis["distribution"],
        analysis["dominant_emotion"],
    )

    likes = post.get("like_count", post.get("likes", 0))
    comments_count = post.get("comments_count", len(comments))

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "source": source,
        "platform": platform,
        "post": {
            "id": post.get("id"),
            "caption": post.get("caption", ""),
            "likes": likes,
            "comments_count": comments_count,
        },
        "mood": {
            "dominant_emotion": analysis["dominant_emotion"],
            "distribution": analysis["distribution"],
            "total_comments": analysis["total_comments"],
        },
        "highlights": {
            "top_positive": analysis["top_positive"],
            "top_negative": analysis["top_negative"],
        },
        "suggestion": suggestion,
        "engagement_rate": round((comments_count / max(likes, 1)) * 100, 2),
    }


def get_mock_mood(platform="instagram"):
    posts = get_mock_posts(platform)

    if not posts:
        posts = get_mock_posts()

    latest_post = posts[0]
    comments = get_mock_comments(latest_post["id"])
    return build_response(latest_post, comments, source="mock", platform=latest_post["platform"])


def validate_demo_payment(payload):
    allowed_plans = {
        "pulse": {"monthly": 399, "yearly": 3990},
        "creator-plus": {"monthly": 1999, "yearly": 19990},
        "brand-pro": {"monthly": 6999, "yearly": 69990},
    }
    clean_plan = payload.plan_id.strip().lower()
    clean_billing = payload.billing.strip().lower()
    clean_method = payload.method.strip().lower()

    if clean_plan not in allowed_plans:
        raise HTTPException(status_code=400, detail="Unknown plan.")

    if clean_billing not in {"monthly", "yearly"}:
        raise HTTPException(status_code=400, detail="Invalid billing cycle.")

    if clean_method not in {"upi", "credit", "debit"}:
        raise HTTPException(status_code=400, detail="Invalid payment method.")

    expected_amount = allowed_plans[clean_plan][clean_billing]
    if payload.amount != expected_amount:
        raise HTTPException(status_code=400, detail="Payment amount does not match selected plan.")

    return clean_plan, clean_billing, clean_method


def get_instagram_mood():
    if not USER_ID:
        raise RuntimeError("USER_ID is not configured")

    posts = get_posts(USER_ID)
    if not posts:
        raise RuntimeError("No Instagram posts found")

    latest_post = posts[0]
    raw_comments = get_comments(latest_post["id"])
    if not raw_comments:
        raise RuntimeError("No Instagram comments found")

    comments = format_comments(raw_comments)
    return build_response(latest_post, comments, source="instagram_live", platform="instagram")


def merge_distributions(responses):
    totals = {}
    total_comments = 0

    for response in responses:
        comments = response["mood"]["total_comments"]
        total_comments += comments

        for emotion, percent in response["mood"]["distribution"].items():
            totals[emotion] = totals.get(emotion, 0) + (percent * comments)

    if total_comments == 0:
        return {emotion: 0 for emotion in ["joy", "hype", "timepass", "anger", "sadness", "cringe"]}

    return {
        emotion: round(weighted_score / total_comments)
        for emotion, weighted_score in totals.items()
    }


@app.get("/health")
def health():
    return {"ok": True, "service": "Pulsay API"}


@app.post("/api/auth/register")
def register(payload: RegisterRequest):
    return register_user(payload.email, payload.password, payload.name)


@app.post("/api/auth/login")
def login(payload: LoginRequest):
    return login_user(payload.email, payload.password)


@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)):
    return user


@app.get("/")
def dashboard():
    return FileResponse("dashboard.html")


@app.get("/dashboard")
def dashboard_alias():
    return FileResponse("dashboard.html")


@app.get("/api/creator/preview")
def get_creator_preview(platform: str, handle: str, request: Request):
    clean_platform = platform.strip().lower()
    clean_handle = normalize_handle(handle)
    log_audit(
        "creator_preview_searched",
        request,
        user_id=DEMO_USER_ID,
        platform=clean_platform,
        handle=clean_handle,
    )

    # Use Apify for real public Instagram data when configured
    if clean_platform == "instagram" and INSTAGRAM_PROVIDER == "apify":
        try:
            from apify_service import get_profile, get_posts as apify_get_posts, get_comments as apify_get_comments
            profile = get_profile(clean_handle)
            if profile:
                posts = apify_get_posts(clean_handle, limit=5)
                latest_post = posts[0] if posts else {}
                comments = apify_get_comments(clean_handle, post_shortcode=latest_post.get("shortcode"), limit=30) if latest_post else []
                analysis = analyze_comments(comments) if comments else {}
                suggestion = generate_suggestion(
                    analysis.get("distribution", {}),
                    analysis.get("dominant_emotion", "timepass"),
                    platform="instagram",
                ) if analysis else "Connect your account for personalised insights."

                followers = profile["followers"]
                followers_display = f"{followers / 1000:.0f}K" if followers >= 1000 else str(followers)

                return {
                    "platform": clean_platform,
                    "handle": f"@{profile['username']}",
                    "creator_name": profile["full_name"] or clean_handle.title(),
                    "bio": profile["bio"],
                    "followers": followers_display,
                    "is_verified": profile["is_verified"],
                    "niche": "Creator",
                    "public_mood": analysis.get("dominant_emotion", "unknown").title() if analysis else "Unknown",
                    "score_range": f"{analysis.get('distribution', {}).get('joy', 0) + analysis.get('distribution', {}).get('hype', 0)}-100" if analysis else "N/A",
                    "suggestion": suggestion,
                    "preview_notice": "Public preview only. Private insights require creator ownership verification.",
                    "source": "apify",
                }
        except Exception as exc:
            logger.warning("Apify preview fallback for %s: %s", clean_handle, exc)

    return get_mock_public_profile(clean_platform, clean_handle)


@app.get("/api/creator/handle-check")
def check_creator_handle(platform: str, handle: str, request: Request):
    clean_platform = platform.strip().lower()
    raw_handle = handle.strip()
    clean_handle = normalize_handle(raw_handle)
    looks_like_url = "http://" in raw_handle or "https://" in raw_handle or ".com" in raw_handle
    wrong_platform_patterns = {
        "instagram": ["youtube.com", "youtu.be", "x.com", "twitter.com", "linkedin.com"],
        "youtube": ["instagram.com", "x.com", "twitter.com", "linkedin.com"],
        "x": ["instagram.com", "youtube.com", "youtu.be", "linkedin.com"],
        "linkedin": ["instagram.com", "youtube.com", "youtu.be", "x.com", "twitter.com"],
        "facebook": ["instagram.com", "youtube.com", "youtu.be", "x.com", "twitter.com", "linkedin.com"],
    }
    known_handles = {
        "instagram": {"aaravspeaks"},
        "youtube": {"aarav speaks", "aaravspeaks"},
        "x": {"aaravbuilds", "your_real_x"},
        "facebook": {"aarav mehta official", "aaravmehtaofficial"},
        "linkedin": {"aarav-mehta", "aaravmehta"},
    }

    if not clean_handle:
        return {"valid": False, "status": "empty", "message": "Add a handle first."}

    if any(pattern in raw_handle.lower() for pattern in wrong_platform_patterns.get(clean_platform, [])):
        log_audit(
            "creator_handle_check_failed",
            request,
            user_id=DEMO_USER_ID,
            platform=clean_platform,
            handle=clean_handle,
            reason="wrong_platform_link",
        )
        return {"valid": False, "status": "wrong_platform", "message": f"That looks like a different platform link, not {clean_platform}."}

    normalized_known = {normalize_handle(item) for item in known_handles.get(clean_platform, set())}
    is_known = clean_handle in normalized_known
    is_reasonable_format = len(clean_handle) >= 6 and " " not in clean_handle if clean_platform != "youtube" else len(clean_handle) >= 6
    valid = is_known or (is_reasonable_format and not looks_like_url)

    log_audit(
        "creator_handle_checked",
        request,
        user_id=DEMO_USER_ID,
        platform=clean_platform,
        handle=clean_handle,
        valid=valid,
    )

    if valid:
        return {"valid": True, "status": "found", "message": "Looks good. We found a matching public profile."}

    return {"valid": False, "status": "not_found", "message": "Could not find a matching public profile for this platform."}


@app.post("/api/creator/claim")
def create_creator_claim(payload: CreatorClaimRequest, request: Request):
    clean_platform = payload.platform.strip().lower()
    clean_handle = normalize_handle(payload.handle)
    key = claim_key(DEMO_USER_ID, clean_platform, clean_handle)
    now = datetime.utcnow()
    code = generate_verification_code()

    existing_claim = creator_claims.get(key)
    failed_attempts = existing_claim["failed_attempts"] if existing_claim else 0

    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        log_audit(
            "creator_claim_blocked",
            request,
            user_id=DEMO_USER_ID,
            platform=clean_platform,
            handle=clean_handle,
            failed_attempts=failed_attempts,
        )
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    claim = {
        "user_id": DEMO_USER_ID,
        "creator_handle": clean_handle,
        "platform": clean_platform,
        "verification_status": "pending",
        "verification_method": "bio_code",
        "verification_code": code,
        "code_expires_at": now + timedelta(minutes=VERIFICATION_TTL_MINUTES),
        "verified_at": None,
        "failed_attempts": failed_attempts,
    }
    creator_claims[key] = claim

    log_audit(
        "creator_claim_started",
        request,
        user_id=DEMO_USER_ID,
        platform=clean_platform,
        handle=clean_handle,
        verification_method="bio_code",
    )

    return {
        "verification_method": "bio_code",
        "verification_code": code,
        "expires_in_minutes": VERIFICATION_TTL_MINUTES,
        "instructions": "Add this code to your bio, then click Verify.",
    }


@app.post("/api/creator/verify")
def verify_creator_claim(payload: CreatorVerifyRequest, request: Request):
    clean_platform = payload.platform.strip().lower()
    clean_handle = normalize_handle(payload.handle)
    claim = get_claim_or_404(DEMO_USER_ID, clean_platform, clean_handle)

    if claim["failed_attempts"] >= MAX_FAILED_ATTEMPTS:
        log_audit(
            "creator_verify_blocked",
            request,
            user_id=DEMO_USER_ID,
            platform=clean_platform,
            handle=clean_handle,
            failed_attempts=claim["failed_attempts"],
        )
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    if datetime.utcnow() > claim["code_expires_at"]:
        claim["verification_status"] = "failed"
        log_audit(
            "creator_verify_failed",
            request,
            user_id=DEMO_USER_ID,
            platform=clean_platform,
            handle=clean_handle,
            reason="expired_code",
        )
        return {"verified": False, "message": "This code expired. Generate a fresh one and try again."}

    public_profile = get_mock_public_profile(clean_platform, clean_handle, verification_code=claim["verification_code"])
    # TODO: Replace mock bio check with real Instagram/YouTube/X profile API lookup.
    code_matches = payload.verification_code.strip().upper() in public_profile["bio"].upper()

    if code_matches:
        claim["verification_status"] = "verified"
        claim["verified_at"] = datetime.utcnow()
        log_audit(
            "creator_verify_success",
            request,
            user_id=DEMO_USER_ID,
            platform=clean_platform,
            handle=clean_handle,
        )
        return {"verified": True, "message": "Creator ownership verified."}

    claim["failed_attempts"] += 1
    claim["verification_status"] = "failed"
    remaining_attempts = max(MAX_FAILED_ATTEMPTS - claim["failed_attempts"], 0)
    log_audit(
        "creator_verify_failed",
        request,
        user_id=DEMO_USER_ID,
        platform=clean_platform,
        handle=clean_handle,
        reason="code_not_found",
        failed_attempts=claim["failed_attempts"],
    )

    return {
        "verified": False,
        "message": "Could not find the code in the public bio yet.",
        "remaining_attempts": remaining_attempts,
    }


@app.get("/api/creator/sources")
def get_creator_sources(request: Request):
    log_audit("creator_sources_viewed", request, user_id=DEMO_USER_ID)
    return {"sources": list(creator_sources.values())}


@app.post("/api/creator/sources")
def update_creator_source(payload: CreatorSourceUpdateRequest, request: Request):
    clean_platform = payload.platform.strip().lower()
    clean_status = payload.status.strip().lower()

    if clean_status not in {"matched", "confirmed", "rejected", "pending_verification", "verified", "removed", "needs_reconnect"}:
        raise HTTPException(status_code=400, detail="Invalid source status.")

    source = {
        "platform": clean_platform,
        "handle": payload.handle.strip().lstrip("@"),
        "status": clean_status,
    }
    creator_sources[(DEMO_USER_ID, clean_platform)] = source
    log_audit(
        "creator_source_updated",
        request,
        user_id=DEMO_USER_ID,
        platform=clean_platform,
        handle=source["handle"],
        status=clean_status,
    )
    return source


@app.get("/api/creator/dashboard")
def get_creator_dashboard(platform: str, handle: str, request: Request):
    clean_platform = platform.strip().lower()
    clean_handle = normalize_handle(handle)

    if not is_verified(DEMO_USER_ID, clean_platform, clean_handle):
        log_audit(
            "private_dashboard_blocked",
            request,
            user_id=DEMO_USER_ID,
            platform=clean_platform,
            handle=clean_handle,
        )
        raise HTTPException(status_code=403, detail="Creator ownership verification required.")

    return get_aggregate() if clean_platform == "all" else get_mock_mood(clean_platform)


@app.get("/api/audit-log")
def get_audit_log():
    return {"events": audit_events[-50:]}


@app.post("/api/payments/confirm")
def confirm_payment(payload: PaymentConfirmRequest, request: Request):
    clean_plan, clean_billing, clean_method = validate_demo_payment(payload)
    now = datetime.utcnow()
    subscription = {
        "user_id": DEMO_USER_ID,
        "status": "active",
        "plan_id": clean_plan,
        "plan_name": payload.plan_name.strip(),
        "billing": clean_billing,
        "amount": payload.amount,
        "method": clean_method,
        "checkout_id": payload.checkout_id.strip(),
        "paid_at": now.isoformat(),
    }
    subscriptions[DEMO_USER_ID] = subscription
    log_audit(
        "payment_confirmed",
        request,
        user_id=DEMO_USER_ID,
        plan_id=clean_plan,
        billing=clean_billing,
        amount=payload.amount,
        method=clean_method,
    )

    # TODO: Replace this demo confirmation with Razorpay/Stripe webhook signature verification.
    # Never unlock premium data in production from a client-only "success" event.
    return {"paid": True, "subscription": subscription}


@app.get("/api/ai-analysis")
def get_ai_analysis(platform: str = "instagram", request: Request = None):
    """
    Deep AI analysis of the latest post on a given platform using DeepSeek.
    Falls back to rule-based data if the AI call fails.
    """
    mood_data = get_mock_mood(platform)
    distribution = mood_data["mood"]["distribution"]
    dominant = mood_data["mood"]["dominant_emotion"]
    top_positive = mood_data["highlights"]["top_positive"]
    top_negative = mood_data["highlights"]["top_negative"]
    caption = mood_data["post"].get("caption", "")

    ai_result = ai_deep_analysis(
        distribution=distribution,
        dominant=dominant,
        top_positive=top_positive,
        top_negative=top_negative,
        platform=platform,
        caption=caption,
    )

    return {
        "platform": platform,
        "post": mood_data["post"],
        "mood": mood_data["mood"],
        "ai_analysis": ai_result or {
            "summary": mood_data["suggestion"],
            "insight": f"Dominant emotion is {dominant}.",
            "action": mood_data["suggestion"],
            "risk": "No AI analysis available — DeepSeek key missing or API unreachable.",
            "sentiment_score": distribution.get("joy", 0) + distribution.get("hype", 0),
            "source": "rule_based_fallback",
        },
        "source": "ai" if ai_result else "fallback",
    }


@app.get("/api/subscription")
def get_subscription(request: Request):
    log_audit("subscription_checked", request, user_id=DEMO_USER_ID)
    return subscriptions.get(
        DEMO_USER_ID,
        {
            "user_id": DEMO_USER_ID,
            "status": "free",
            "plan_id": "free",
            "plan_name": "Free",
            "billing": "monthly",
        },
    )


@app.get("/api/instagram/analyze")
def analyze_instagram_handle(handle: str, limit: int = 50):
    """
    Scrape a public Instagram profile via Apify and return real mood + AI analysis.
    Falls back to a 503 error (not mock) so the frontend can show a clear message.
    """
    from config import APIFY_TOKEN

    clean_handle = normalize_handle(handle)
    if not clean_handle:
        raise HTTPException(status_code=400, detail="Instagram handle is required.")

    if INSTAGRAM_PROVIDER != "apify" or not APIFY_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Apify is not configured on this server. Set INSTAGRAM_PROVIDER=apify and APIFY_TOKEN in Railway env vars.",
        )

    try:
        from apify_service import get_posts as apify_posts, get_comments as apify_comments

        posts = apify_posts(clean_handle, limit=5)
        if not posts:
            raise HTTPException(
                status_code=404,
                detail=f"No public posts found for @{clean_handle}. The account may be private or the handle is incorrect.",
            )

        latest_post = posts[0]
        comments_raw = apify_comments(
            clean_handle,
            post_shortcode=latest_post.get("shortcode"),
            limit=min(limit, 100),
        )

        comments = [
            {
                "id": c.get("id", ""),
                "text": c.get("text", ""),
                "username": c.get("username", "unknown"),
                "like_count": c.get("like_count", 0),
            }
            for c in comments_raw
            if c.get("text", "").strip()
        ]

        result = build_response(latest_post, comments, source="apify_live", platform="instagram")
        result["handle"] = f"@{clean_handle}"
        result["profile"] = {
            "username": latest_post.get("owner_username", clean_handle),
            "full_name": latest_post.get("owner_full_name", ""),
            "posts_analyzed": len(posts),
            "comments_analyzed": len(comments),
            "post_url": latest_post.get("url", ""),
            "post_likes": latest_post.get("likes", 0),
            "post_comments_count": latest_post.get("comments_count", 0),
        }

        # Deep AI analysis on real comment data
        ai_result = ai_deep_analysis(
            distribution=result["mood"]["distribution"],
            dominant=result["mood"]["dominant_emotion"],
            top_positive=result["highlights"]["top_positive"],
            top_negative=result["highlights"]["top_negative"],
            platform="instagram",
            caption=latest_post.get("caption", ""),
        )
        if ai_result:
            result["ai_analysis"] = ai_result

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Instagram Apify analysis failed for @%s: %s", clean_handle, exc)
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/api/mood")
def get_mood(use_live_instagram: bool = False):
    if not use_live_instagram:
        return get_mock_mood("instagram")

    try:
        return get_instagram_mood()
    except Exception as exc:
        fallback = get_mock_mood("instagram")
        fallback["source"] = "mock_fallback"
        fallback["warning"] = f"Instagram live API failed: {exc}"
        return fallback


@app.get("/api/aggregate")
def get_aggregate():
    responses = [
        get_mock_mood("instagram"),
        get_mock_mood("youtube"),
        get_mock_mood("x"),
        get_mock_mood("facebook"),
    ]

    distribution = merge_distributions(responses)
    dominant = max(distribution, key=distribution.get)
    top_positive = []
    top_negative = []

    for response in responses:
        top_positive.extend(response["highlights"]["top_positive"])
        top_negative.extend(response["highlights"]["top_negative"])

    total_likes = sum(response["post"]["likes"] for response in responses)
    total_comments = sum(response["post"]["comments_count"] for response in responses)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "source": "mock_aggregate",
        "platform": "all",
        "post": {
            "id": "aggregate",
            "caption": "All platform creator pulse",
            "likes": total_likes,
            "comments_count": total_comments,
        },
        "mood": {
            "dominant_emotion": dominant,
            "distribution": distribution,
            "total_comments": sum(response["mood"]["total_comments"] for response in responses),
        },
        "highlights": {
            "top_positive": top_positive[:3],
            "top_negative": top_negative[:3],
        },
        "suggestion": generate_suggestion(distribution, dominant),
        "engagement_rate": round((total_comments / max(total_likes, 1)) * 100, 2),
        "platforms": responses,
    }
