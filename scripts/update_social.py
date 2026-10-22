#!/usr/bin/env python3
"""Refresh public site data from owner-authorized platform APIs.

No secret is written to the generated JSON. Each platform fails independently so a
temporary outage does not erase the last verified values.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "social.json"
CONFIRMED = ROOT / "data" / "partnerships.json"
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v24.0")
DISCLOSURE = re.compile(r"(?i)(?:#(?:ad|sponsored|paidpartnership|brandpartner|brandambassador)\b|\bpaid partnership\b)")
INSTAGRAM_URL = re.compile(r"^https://(?:www\.)?instagram\.com/(?:p|reel|reels)/[^/?#]+/?")


def request_json(url, *, token=None, form=None):
    headers = {"Accept": "application/json", "User-Agent": "TommyCreatorSite/1.0"}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form is not None:
        body = urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = Request(url, data=body, headers=headers)
    try:
        with urlopen(req, timeout=25) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url.split('?')[0]}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"Request failed for {url.split('?')[0]}: {exc.reason if isinstance(exc, URLError) else exc}") from exc
    if isinstance(result, dict) and result.get("error"):
        error = result["error"]
        if isinstance(error, dict) and error.get("code") in (0, "ok"):
            return result
        raise RuntimeError(f"API error from {url.split('?')[0]}: {error.get('message', error) if isinstance(error, dict) else error}")
    return result


def number(value):
    if isinstance(value, bool):
        return None
    try:
        n = int(value)
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def graph(path, token, **params):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path}"
    if params:
        url += "?" + urlencode(params)
    return request_json(url, token=token)


def refresh_instagram(data, now):
    token = os.getenv("META_ACCESS_TOKEN")
    ig_id = os.getenv("INSTAGRAM_USER_ID")
    if not (token and ig_id):
        return
    if ig_id:
        user = graph(ig_id, token, fields="id,username,followers_count")
        if user.get("username", "").lower() != "tommythebernese":
            raise RuntimeError("Instagram account username did not match @tommythebernese")
        data["followers"]["instagram"] = number(user.get("followers_count"))
        data["sourceUpdatedAt"]["instagram"] = now
        media = graph(f"{ig_id}/media", token, fields="id,caption,permalink,media_type,media_product_type,media_url,thumbnail_url,like_count,comments_count,timestamp", limit=100)
        posts = media.get("data", [])
        if not isinstance(posts, list):
            raise RuntimeError("Unexpected Instagram media response")
        # Likes + comments are public interactions, not a private engagement rate.
        recent = [number(p.get("like_count")) + number(p.get("comments_count")) for p in posts[:12] if number(p.get("like_count")) is not None and number(p.get("comments_count")) is not None]
        data["insights"]["instagramRecentAverageInteractions"] = round(sum(recent) / len(recent)) if recent else None
        confirmed = set(json.loads(CONFIRMED.read_text()).get("confirmedInstagramPermalinks", []))
        selected = []
        for post in posts:
            permalink = post.get("permalink", "")
            if not INSTAGRAM_URL.match(permalink):
                continue
            caption = post.get("caption") or ""
            is_confirmed = permalink in confirmed or permalink.rstrip("/") in {u.rstrip("/") for u in confirmed}
            if not (is_confirmed or DISCLOSURE.search(caption)):
                continue
            clean = re.sub(r"\s+", " ", caption).strip()
            selected.append({"permalink": permalink, "thumbnail": post.get("thumbnail_url") or post.get("media_url") or "", "title": clean[:64].rstrip(" .,;:") or "Tommy x brand story", "excerpt": clean[:150] + ("…" if len(clean) > 150 else ""), "source": "confirmed" if is_confirmed else "disclosed", "timestamp": post.get("timestamp")})
        data["partnerships"] = selected[:6]
        data["sourceUpdatedAt"]["instagramPosts"] = now
        # Views are requested only for Reels; unsupported media metrics are skipped.
        views = []
        for post in posts[:12]:
            if post.get("media_product_type") != "REELS":
                continue
            try:
                insight = graph(f"{post['id']}/insights", token, metric="views")
                metric = next((m for m in insight.get("data", []) if m.get("name") == "views"), None)
                value = number((metric or {}).get("values", [{}])[0].get("value"))
                if value is not None:
                    views.append(value)
            except (RuntimeError, KeyError, IndexError, AttributeError):
                continue
        data["insights"]["instagramRecentAverageViews"] = round(sum(views) / len(views)) if views else None
def refresh_facebook(data, now):
    token = os.getenv("META_ACCESS_TOKEN")
    page_id = os.getenv("FACEBOOK_PAGE_ID")
    if not (token and page_id):
        return
    # Page follower count is distinct from fan_count (likes). Never substitute likes.
    page = graph(page_id, token, fields="id,name,followers_count")
    data["followers"]["facebook"] = number(page.get("followers_count"))
    data["sourceUpdatedAt"]["facebook"] = now


def refresh_youtube(data, now):
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        return
    query = urlencode({"part": "statistics,snippet", "forHandle": "@tommythebernese", "key": key})
    response = request_json(f"https://www.googleapis.com/youtube/v3/channels?{query}")
    channel = next(iter(response.get("items", [])), None)
    if not channel:
        raise RuntimeError("YouTube channel @tommythebernese was not found")
    stats = channel.get("statistics", {})
    if not stats.get("hiddenSubscriberCount"):
        data["followers"]["youtube"] = number(stats.get("subscriberCount"))
    data["insights"]["youtubeViews"] = number(stats.get("viewCount"))
    data["sourceUpdatedAt"]["youtube"] = now


def refresh_tiktok(data, now):
    key = os.getenv("TIKTOK_CLIENT_KEY")
    secret = os.getenv("TIKTOK_CLIENT_SECRET")
    refresh = os.getenv("TIKTOK_REFRESH_TOKEN")
    if not all((key, secret, refresh)):
        return
    auth = request_json("https://open.tiktokapis.com/v2/oauth/token/", form={"client_key": key, "client_secret": secret, "grant_type": "refresh_token", "refresh_token": refresh})
    access_token = auth.get("access_token")
    if not access_token:
        raise RuntimeError("TikTok did not return an access token")
    url = "https://open.tiktokapis.com/v2/user/info/?fields=username,follower_count"
    user_response = request_json(url, token=access_token)
    user = user_response.get("data", {}).get("user", {})
    if user.get("username", "").lower() != "tommythebernese":
        raise RuntimeError("TikTok account username did not match @tommythebernese")
    data["followers"]["tiktok"] = number(user.get("follower_count"))
    data["sourceUpdatedAt"]["tiktok"] = now
    new_refresh = auth.get("refresh_token")
    if new_refresh and new_refresh != refresh:
        # The workflow rotates its GitHub Secret with a separate authenticated step.
        output = os.getenv("TIKTOK_ROTATED_TOKEN_FILE")
        if not output:
            raise RuntimeError("TikTok rotated its refresh token but TIKTOK_ROTATED_TOKEN_FILE is unset")
        path = Path(output)
        path.write_text(new_refresh)
        path.chmod(0o600)


def main():
    data = json.loads(DATA.read_text())
    data.setdefault("followers", {})
    data.setdefault("insights", {})
    data.setdefault("sourceUpdatedAt", {})
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    errors = []
    for name, updater in (("Instagram", refresh_instagram), ("Facebook", refresh_facebook), ("YouTube", refresh_youtube), ("TikTok", refresh_tiktok)):
        try:
            updater(data, now)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    if any(value == now for value in data["sourceUpdatedAt"].values()):
        data["updatedAt"] = now
    DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
