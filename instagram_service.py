import requests
from config import BASE_URL, ACCESS_TOKEN


def fetch_all_pages(url, params):
    data = []

    while url:
        res = requests.get(url, params=params)
        json_data = res.json()

        if "error" in json_data:
            raise Exception(json_data["error"]["message"])

        data.extend(json_data.get("data", []))

        url = json_data.get("paging", {}).get("next")
        params = None  # next already includes params

    return data


def get_posts(user_id):
    url = f"{BASE_URL}/{user_id}/media"
    params = {
        "fields": "id,caption,like_count,comments_count,timestamp",
        "access_token": ACCESS_TOKEN,
        "limit": 5
    }

    return fetch_all_pages(url, params)


def get_comments(media_id):
    url = f"{BASE_URL}/{media_id}/comments"
    params = {
        "fields": "id,text,like_count,username",
        "access_token": ACCESS_TOKEN,
        "limit": 50
    }

    return fetch_all_pages(url, params)