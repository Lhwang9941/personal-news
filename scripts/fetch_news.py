import requests
import os
import trafilatura
import json
from datetime import datetime, timedelta, timezone
import pytz
from urllib.parse import urlparse
import re
from bs4 import BeautifulSoup


# ============================================================
# LOAD KEYWORDS
# ============================================================

def load_keywords():

    with open(
        "config/keywords.json",
        "r",
        encoding="utf-8"
    ) as file:

        config = json.load(file)

    return config.get("topics", {})


KEYWORDS = load_keywords()

print()
print("Loaded keywords:")
print(KEYWORDS)
print()


# ============================================================
# COUNTRY / TIMEZONE
# ============================================================

def infer_country_from_url(url):

    domain = urlparse(url).netloc.lower()

    mapping = {
        ".kr": ("South Korea", "Asia/Seoul"),
        ".jp": ("Japan", "Asia/Tokyo"),
        ".cn": ("China", "Asia/Shanghai"),
        ".ru": ("Russia", "Europe/Moscow"),
        ".fr": ("France", "Europe/Paris"),
        ".de": ("Germany", "Europe/Berlin"),
        ".uk": ("United Kingdom", "Europe/London"),
        ".co.uk": ("United Kingdom", "Europe/London"),
        ".it": ("Italy", "Europe/Rome"),
        ".es": ("Spain", "Europe/Madrid"),
        ".pt": ("Portugal", "Europe/Lisbon"),
        ".ua": ("Ukraine", "Europe/Kyiv"),
        ".pl": ("Poland", "Europe/Warsaw"),
        ".se": ("Sweden", "Europe/Stockholm"),
        ".no": ("Norway", "Europe/Oslo"),
        ".fi": ("Finland", "Europe/Helsinki"),
        ".com": ("Unknown", "UTC"),
        ".org": ("Unknown", "UTC"),
        ".net": ("Unknown", "UTC")
    }

    for tld, data in mapping.items():

        if domain.endswith(tld):
            return data

    return ("Unknown", "UTC")


# ============================================================
# ARTICLE SCRAPER
# ============================================================

def fetch_full_article(url):

    try:

        downloaded = trafilatura.fetch_url(url)

        if not downloaded:
            return None

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            include_images=False
        )

        return text

    except Exception as e:

        print("SCRAPE ERROR:", e)

        return None


# ============================================================
# KEYWORD SCORING
# ============================================================

def score_article(title, body):

    combined_text = (
        title + " " + body
    ).lower()

    matched_keywords = []

    score = 0

    for keyword, weight in KEYWORDS.items():

        keyword_lower = keyword.lower()

        matches = combined_text.count(
            keyword_lower
        )

        if matches > 0:

            matched_keywords.append(
                keyword
            )

            score += (
                matches * weight
            )

    return score, matched_keywords


# ============================================================
# NEWSBLUR LOGIN
# ============================================================

NB_USERNAME = os.getenv("NB_USERNAME")
NB_PASSWORD = os.getenv("NB_PASSWORD")


if not NB_USERNAME or not NB_PASSWORD:

    print(
        "ERROR: NewsBlur credentials are missing."
    )

    exit(1)


session = requests.Session()


login_response = session.post(

    "https://newsblur.com/api/login",

    data={
        "username": NB_USERNAME,
        "password": NB_PASSWORD
    }
)


if login_response.status_code != 200:

    print("NewsBlur login failed.")

    print(
        login_response.text
    )

    exit(1)


print(
    "Successfully logged into NewsBlur."
)


# ============================================================
# FETCH LAST 24 HOURS
# ============================================================

CUTOFF = (
    datetime.now(timezone.utc)
    - timedelta(hours=24)
)

PAGE = 1

ALL_SELECTED = []


print(
    "Fetching unread stories..."
)


while True:

    url = (
        "https://newsblur.com/reader/river_stories"
    )

    params = {

        "read_filter": "unread",

        "order": "newest",

        "page": PAGE

    }


    response = session.get(

        url,

        params=params

    )


    if not response.headers.get(

        "Content-Type",
        ""

    ).startswith("application/json"):

        print(
            "Non-JSON response. Stopping."
        )

        break


    data = response.json()

    stories = data.get(
        "stories",
        []
    )


    if not stories:

        break


    print(
        f"Page {PAGE}: {len(stories)} stories"
    )


    stop_pagination = False


    for story in stories:

        try:

            timestamp = datetime.fromtimestamp(

                int(
                    story["story_timestamp"]
                ),

                tz=timezone.utc

            )

        except Exception:

            continue


        if timestamp >= CUTOFF:

            ALL_SELECTED.append(
                story
            )

        else:

            stop_pagination = True

            break


    if stop_pagination:

        break


    PAGE += 1


print()

print(
    f"Collected {len(ALL_SELECTED)} "
    "stories from the last 24 hours."
)

print()


# ============================================================
# PROCESS STORIES
# ============================================================

KST = pytz.timezone(
    "Asia/Seoul"
)


# ============================================================
# FIRST FILTER
# ============================================================

def quick_keyword_score(story):

    title = story.get(
        "story_title",
        ""
    )

    content = story.get(
        "story_content",
        ""
    )

    text = (
        title + " " + content
    ).lower()

    score = 0

    matched = []

    for keyword, weight in KEYWORDS.items():

        keyword_lower = keyword.lower()

        if keyword_lower in text:

            score += weight

            matched.append(
                keyword
            )

    return score, matched


candidates = []


print(
    "Running initial keyword filter..."
)


for story in ALL_SELECTED:

    score, matched = (
        quick_keyword_score(
            story
        )
    )

    if score > 0:

        candidates.append({

            "story": story,

            "quick_score": score,

            "quick_keywords": matched

        })


print()

print(
    f"Keyword filter found "
    f"{len(candidates)} relevant candidates."
)

print()


# ============================================================
# LIMIT EXPENSIVE SCRAPING
# ============================================================

MAX_CANDIDATES = 300


candidates.sort(

    key=lambda item:
        item["quick_score"],

    reverse=True

)


candidates = candidates[
    :MAX_CANDIDATES
]


print(
    f"Will fully scrape "
    f"{len(candidates)} articles."
)

print()


# ============================================================
# FULL ARTICLE PROCESSING
# ============================================================

processed_articles = []


for index, candidate in enumerate(

    candidates,

    start=1

):

    story = candidate["story"]


    title = story.get(

        "story_title",
        ""

    ).strip()


    permalink = story.get(

        "story_permalink",
        ""

    )


    publisher = story.get(

        "story_feed_title",
        "Unknown Publisher"

    )


    try:

        timestamp_utc = datetime.fromtimestamp(

            int(
                story["story_timestamp"]
            ),

            tz=timezone.utc

        )

    except Exception:

        continue


    country, timezone_name = (
        infer_country_from_url(
            permalink
        )
    )


    try:

        local_timezone = pytz.timezone(
            timezone_name
        )

    except Exception:

        local_timezone = timezone.utc


    local_time = (
        timestamp_utc.astimezone(
            local_timezone
        )
    )


    kst_time = (
        timestamp_utc.astimezone(
            KST
        )
    )


    print(

        f"[{index}/{len(candidates)}] "
        f"{title}"

    )


    body = fetch_full_article(
        permalink
    )


    if not body:

        body = title


    relevance_score, matched_keywords = (
        score_article(
            title,
            body
        )
    )


    article = {

        "title": title,

        "publisher": publisher,

        "url": permalink,

        "country": country,

        "timezone": timezone_name,

        "published_utc":
            timestamp_utc.isoformat(),

        "published_local":
            local_time.isoformat(),

        "published_kst":
            kst_time.isoformat(),

        "relevance_score":
            relevance_score,

        "matched_keywords":
            matched_keywords,

        "body": body

    }


    processed_articles.append(
        article
    )


# ============================================================
# SORT
# ============================================================

processed_articles.sort(

    key=lambda article:
        article["relevance_score"],

    reverse=True

)


# ============================================================
# STATISTICS
# ============================================================

keyword_frequency = {}


for article in processed_articles:

    for keyword in article[
        "matched_keywords"
    ]:

        keyword_frequency[keyword] = (
            keyword_frequency.get(
                keyword,
                0
            ) + 1
        )


# ============================================================
# OUTPUT
# ============================================================

output = {

    "generated_at":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "article_count":
        len(ALL_SELECTED),

    "processed_article_count":
        len(processed_articles),

    "relevant_article_count":
        len(processed_articles),

    "keyword_frequency":
        keyword_frequency,

    "articles":
        processed_articles

}


os.makedirs(

    "data",

    exist_ok=True

)


with open(

    "data/news.json",

    "w",

    encoding="utf-8"

) as file:

    json.dump(

        output,

        file,

        ensure_ascii=False,

        indent=2

    )


print()

print(
    "================================"
)

print(
    "NEWS UPDATE COMPLETE"
)

print(
    "Unread stories:",
    len(ALL_SELECTED)
)

print(
    "Articles fully processed:",
    len(processed_articles)
)

print(
    "================================"
)
