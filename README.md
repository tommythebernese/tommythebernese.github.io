# Tommy the Bernese creator site

A static GitHub Pages site for brand inquiries. The layout is in `index.html` and `assets/site.css`; `assets/site.js` reads `data/social.json`. The page never receives API credentials.

## Connect daily updates

The [Refresh creator data](.github/workflows/refresh-social.yml) GitHub Action runs each day at 10:23 UTC and can also be started with **Actions → Refresh creator data → Run workflow**. Add the following in **Settings → Secrets and variables → Actions** before running it:

| Name | Type | Purpose |
| --- | --- | --- |
| `META_ACCESS_TOKEN` | Secret | Authorized non-expiring Meta system-user token for Tommy's Instagram professional account and Facebook Page, with read-focused permissions. Non-expiring means no scheduled expiry; access can still be revoked or changed by Meta. |
| `INSTAGRAM_USER_ID` | Variable | Instagram professional account numeric ID. |
| `FACEBOOK_PAGE_ID` | Variable | Tommy's Facebook Page numeric ID. The API must return `followers_count`; the site will never show Page likes as followers. |
| `YOUTUBE_API_KEY` | Secret | YouTube Data API v3 key. The script looks up `@tommythebernese` using `channels.list(forHandle)`. |
| `TIKTOK_CLIENT_KEY` | Secret | TikTok developer app client key. |
| `TIKTOK_CLIENT_SECRET` | Secret | TikTok developer app client secret. |
| `TIKTOK_REFRESH_TOKEN` | Secret | Owner-authorized TikTok refresh token with `user.info.stats` and `user.info.profile` scopes. |
| `SOCIAL_SECRETS_PAT` | Secret | Fine-grained GitHub token with repository **Secrets: read/write** permission so the workflow can save a rotated TikTok refresh token. |

Meta, YouTube, and TikTok require their owner-authorized credentials. The current TikTok connection uses a sandbox target account; production use may require TikTok app review. Add secrets directly in GitHub; never paste tokens into the repo or a chat. The Action commits only public counts, dated aggregate metrics, and post metadata to `data/social.json`.

The workflow uses `GITHUB_TOKEN` with **Contents: write** to commit refreshed JSON. If your repository limits workflow write access, enable it in **Settings → Actions → General → Workflow permissions**. Pages must publish from the `main` branch root (or deploy through your existing Pages workflow).

### What gets updated

- Instagram follower count; the last 12 retrieved posts' average likes plus comments; average views of recent Reels when the insights endpoint supplies `views`.
- Facebook Page followers when Meta supplies the `followers_count` field.
- TikTok follower count using the authorized Display API account.
- YouTube subscriber count and lifetime public views. YouTube rounds subscriber counts, so this is a platform-reported figure.
- Instagram videos in the available media feed with an ad disclosure, a caption @mention, or an owner-confirmed partnership URL. The Partnerships carousel includes tagged posts but labels them `TAGGED POST`; a tag alone is not a paid-work claim. The carousel moves when a mouse hovers near either edge and also supports touch or arrow keys.

Displayed metrics use rounded approximations, such as `~32K` for 31,721; a `+` is used only below the actual count. If a source is not connected, the site links to its profile without inventing a number. A failed API request preserves the last successful value and reports an Action failure. Check the Action logs and `sourceUpdatedAt` in the JSON when assessing freshness. The Instagram API only returns media accessible under the granted permissions; the showcase may be empty until those are connected.

To include a paid partnership that lacks one of those disclosures, add its Instagram permalink to `confirmedInstagramPermalinks` in `data/partnerships.json`. Only add a link when Tommy's team has confirmed that relationship. The media must also appear in the authorized Instagram media feed. The automated scan checks up to 1,000 accessible media items and shows up to nine cards. Instagram API data may not expose accounts tagged only inside the media without a caption mention. If an older campaign is missing, add a separate curated card after confirming the partnership.

## Local preview

From the repository root, run `python3 -m http.server 8000` and open `http://localhost:8000`. Run `python3 scripts/update_social.py` to refresh data with credentials in environment variables. Without credentials it leaves the public JSON unchanged.

## Data sources

- [Meta's official Instagram API collection](https://www.postman.com/meta/instagram/collection/6yqw8pt/instagram-api) describes professional account access, media, and insights.
- [TikTok user info and scope documentation](https://developers.tiktok.com/docs/en/tiktok-api-v2-get-user-info) covers `follower_count`; [token management](https://developers.tiktok.com/docs/en/oauth-user-access-token-management) explains required refresh-token rotation.
- [YouTube channels.list](https://developers.google.com/youtube/v3/docs/channels/list) supports lookup by handle; [channel statistics](https://developers.google.com/youtube/v3/docs/channels/) defines subscriber and view counts.
