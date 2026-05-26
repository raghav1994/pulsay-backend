MOCK_POSTS = [
    {
        "id": "ig_post_1",
        "platform": "instagram",
        "caption": "Office life be like",
        "like_count": 1245,
        "comments_count": 89,
        "posted_at": "2026-05-02T10:00:00",
        "comments": [
            {"id": "ig_c1", "text": "bhai OP content, next level fire", "username": "fan_1", "like_count": 45},
            {"id": "ig_c2", "text": "bas karo yaar same cheez baar baar", "username": "hater_1", "like_count": 23},
            {"id": "ig_c3", "text": "literally crying this is too funny", "username": "laugher_1", "like_count": 67},
            {"id": "ig_c4", "text": "pehle jaisa maza nahi aa raha", "username": "bored_1", "like_count": 12},
            {"id": "ig_c5", "text": "always fire content bro", "username": "loyal_1", "like_count": 89},
            {"id": "ig_c6", "text": "itna ganda kyun hai bhai", "username": "angry_1", "like_count": 8},
            {"id": "ig_c7", "text": "main toh bas timepass ke liye dekhta hun", "username": "casual_1", "like_count": 5},
            {"id": "ig_c8", "text": "bhai tu toh carryminati se bhi aage nikal gaya", "username": "hype_1", "like_count": 156},
            {"id": "ig_c9", "text": "same template same joke same everything thak gaya hun", "username": "tired_1", "like_count": 34},
            {"id": "ig_c10", "text": "bhai motivation mil gaya aaj ka thank you", "username": "grateful_1", "like_count": 56},
        ],
    },
    {
        "id": "yt_post_1",
        "platform": "youtube",
        "caption": "Behind the scenes of my latest reel",
        "like_count": 892,
        "comments_count": 45,
        "posted_at": "2026-05-01T15:30:00",
        "comments": [
            {"id": "yt_c1", "text": "wah bhai itni mehnat dikhti hai", "username": "appreciator_1", "like_count": 34},
            {"id": "yt_c2", "text": "yeh toh better hai actual reel se", "username": "honest_1", "like_count": 67},
            {"id": "yt_c3", "text": "kitne takes lage the", "username": "curious_1", "like_count": 12},
            {"id": "yt_c4", "text": "real content real effort respect", "username": "respect_1", "like_count": 89},
            {"id": "yt_c5", "text": "bas yahi chahiye tha behind the scenes", "username": "fan_2", "like_count": 45},
        ],
    },
    {
        "id": "x_post_1",
        "platform": "x",
        "caption": "Quick thought on creator burnout",
        "like_count": 420,
        "comments_count": 30,
        "posted_at": "2026-05-01T09:30:00",
        "comments": [
            {"id": "x_c1", "text": "needed this today good point", "username": "reader_1", "like_count": 22},
            {"id": "x_c2", "text": "same topic again boring", "username": "reader_2", "like_count": 11},
            {"id": "x_c3", "text": "drop a longer video on this", "username": "reader_3", "like_count": 39},
        ],
    },
    {
        "id": "fb_post_1",
        "platform": "facebook",
        "caption": "Family group comedy sketch",
        "like_count": 310,
        "comments_count": 18,
        "posted_at": "2026-04-30T20:00:00",
        "comments": [
            {"id": "fb_c1", "text": "nice family comedy mast hai", "username": "viewer_1", "like_count": 18},
            {"id": "fb_c2", "text": "cringe thoda zyada ho gaya", "username": "viewer_2", "like_count": 9},
            {"id": "fb_c3", "text": "more storytelling please", "username": "viewer_3", "like_count": 15},
        ],
    },
]


def get_mock_posts(platform=None):
    if platform:
        return [post for post in MOCK_POSTS if post["platform"] == platform]

    return MOCK_POSTS


def get_mock_comments(post_id):
    for post in MOCK_POSTS:
        if post["id"] == post_id:
            return post["comments"]

    return []
