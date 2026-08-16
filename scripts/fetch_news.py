import requests
import os
import trafilatura
import json
from openai import OpenAI
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
# GPT DAILY SUMMARY
# ============================================================

def generate_daily_summary(articles):

    if not articles:
        return "No relevant news was found in the last 24 hours."

    news_items = []

    for article in articles[:30]:

        title = article.get("title", "")
        publisher = article.get("publisher", "Unknown")
        country = article.get("country", "Unknown")
        body = article.get("body", "")

        news_items.append(
            f"""
TITLE: {title}
PUBLISHER: {publisher}
COUNTRY: {country}
ARTICLE:
{body[:4000]}
"""
        )

    news_text = "\n\n".join(news_items)

    prompt = f"""
You are producing a concise daily intelligence-style news briefing.

Review the following news articles from the last 24 hours.

Identify the most important developments, especially those involving:

- international security
- geopolitics
- military activity
- intelligence
- diplomacy
- Ukraine
- Russia
- China
- North Korea
- NATO
- the Middle East

Do not simply list every article.

Produce a concise briefing with:

1. THREE TO FIVE major developments
2. A short explanation of why each matters
3. A final section called "WATCH" containing two or three developments that deserve monitoring

Use neutral, factual language.

Do not invent information that is not contained in the supplied articles.

NEWS ARTICLES:

{news_text}
"""

    try:

        client = OpenAI()

        response = client.responses.create(
            model="gpt-5.6",
            input=prompt
        )

        return response.output_text

    except Exception as e:

        print("OPENAI SUMMARY ERROR:", e)

        return "Daily summary unavailable."

# ============================================================
# GPT REGIONAL SUMMARIES
# ============================================================

# ============================================================
# GPT ARTICLE REGION CLASSIFICATION
# ============================================================

def classify_article_regions(articles):

    if not articles:

        return {}


    article_list = []


    for index, article in enumerate(articles):

        article_list.append({

            "index":
                index,

            "title":
                article.get(
                    "title",
                    ""
                ),

            "body":
                article.get(
                    "body",
                    ""
                )[:2500]

        })


    prompt = f"""
You are classifying international news articles
for a geopolitical news dashboard.

Assign EVERY article to exactly ONE of these regions:

1. asia
2. europe_russia
3. middle_east
4. america_other

Classification must be based on the PRIMARY SUBJECT
of the article, not the publisher's country.

Examples:

- A Guardian article about North Korea → asia
- A Reuters article about Israel → middle_east
- A French newspaper article about Ukraine → europe_russia
- A Japanese newspaper article about the US → america_other

If an article concerns multiple regions, choose the
region that is most central to the story.

Return ONLY valid JSON in this exact format:

{{
    "0": "asia",
    "1": "europe_russia",
    "2": "middle_east",
    "3": "america_other"
}}

Here are the articles:

{json.dumps(
    article_list,
    ensure_ascii=False
)}
"""


    try:

        response = client.responses.create(

            model="gpt-5.6",

            input=prompt

        )


        result = response.output_text.strip()


        result = result.replace(
            "```json",
            ""
        ).replace(
            "```",
            ""
        ).strip()


        classifications = json.loads(result)


        return classifications


    except Exception as e:

        print(
            "REGION CLASSIFICATION ERROR:",
            e
        )

        return {}
        
def generate_regional_summaries(articles):

    regions = {

        "asia": [],
        "europe_russia": [],
        "middle_east": [],
        "america_other": []

    }


    # --------------------------------------------------------
    # CLASSIFY ARTICLES
    # --------------------------------------------------------

    for article in articles:

        text = (
            article.get("title", "") +
            " " +
            article.get("body", "")
        ).lower()


        if any(keyword in text for keyword in [

            "south korea",
            "north korea",
            "china",
            "japan",
            "taiwan",
            "india",
            "pakistan",
            "indonesia",
            "vietnam",
            "thailand",
            "philippines",
            "singapore",
            "malaysia",
            "afghanistan",
            "central asia"

        ]):

            regions["asia"].append(article)


        elif any(keyword in text for keyword in [

            "russia",
            "ukraine",
            "belarus",
            "france",
            "germany",
            "united kingdom",
            "britain",
            "italy",
            "spain",
            "poland",
            "lithuania",
            "latvia",
            "estonia",
            "sweden",
            "norway",
            "finland",
            "europe",
            "nato",
            "european union"

        ]):

            regions["europe_russia"].append(article)


        elif any(keyword in text for keyword in [

            "israel",
            "palestine",
            "gaza",
            "lebanon",
            "hezbollah",
            "syria",
            "iran",
            "iraq",
            "saudi arabia",
            "yemen",
            "qatar",
            "bahrain",
            "kuwait",
            "oman",
            "gulf",
            "middle east"

        ]):

            regions["middle_east"].append(article)


        else:

            regions["america_other"].append(article)


    client = OpenAI()


    summaries = {}


    # --------------------------------------------------------
    # GENERATE ONE SUMMARY PER REGION
    # --------------------------------------------------------

    for region, region_articles in regions.items():

        if not region_articles:

            summaries[region] = (
                "No significant regional "
                "developments were identified."
            )

            continue


        news_items = []


        for article in region_articles[:20]:

            news_items.append(
                f"""
TITLE: {article.get("title", "")}

PUBLISHER:
{article.get("publisher", "Unknown")}

ARTICLE:
{article.get("body", "")[:3000]}
"""
            )


        news_text = "\n\n".join(
            news_items
        )


        prompt = f"""
You are producing a concise regional intelligence briefing.

REGION:
{region.replace("_", " ").upper()}

Review the following news articles.

Identify the THREE most important developments.

For each development:

- Give it a short descriptive heading.
- Explain what happened.
- Explain why it matters.

Use neutral, factual language.

Do not invent information.

Focus on geopolitical, military, diplomatic,
economic and security developments.

End with a short section called WATCH containing
one or two developments that deserve monitoring.

NEWS:

{news_text}
"""


        try:

            response = client.responses.create(

                model="gpt-5.6",

                input=prompt

            )


            summaries[region] = (
                response.output_text
            )


        except Exception as e:

            print(
                f"REGIONAL SUMMARY ERROR "
                f"({region}):",
                e
            )


            summaries[region] = (
                "Regional summary unavailable."
            )


    return summaries
    
# ============================================================
# PUBLISHER / COUNTRY DATABASE
# ============================================================

PUBLISHER_DATABASE = {

    # --------------------------------------------------------
    # UNITED KINGDOM
    # --------------------------------------------------------

    "reuters.com": (
        "Reuters",
        "United Kingdom",
        "Europe/London"
    ),

    "bbc.com": (
        "BBC",
        "United Kingdom",
        "Europe/London"
    ),

    "bbc.co.uk": (
        "BBC",
        "United Kingdom",
        "Europe/London"
    ),

    "theguardian.com": (
        "The Guardian",
        "United Kingdom",
        "Europe/London"
    ),

    "ft.com": (
        "Financial Times",
        "United Kingdom",
        "Europe/London"
    ),

    "telegraph.co.uk": (
        "The Telegraph",
        "United Kingdom",
        "Europe/London"
    ),

    "independent.co.uk": (
        "The Independent",
        "United Kingdom",
        "Europe/London"
    ),

    "economist.com": (
        "The Economist",
        "United Kingdom",
        "Europe/London"
    ),


    # --------------------------------------------------------
    # UNITED STATES
    # --------------------------------------------------------

    "nytimes.com": (
        "The New York Times",
        "United States",
        "America/New_York"
    ),

    "washingtonpost.com": (
        "The Washington Post",
        "United States",
        "America/New_York"
    ),

    "wsj.com": (
        "The Wall Street Journal",
        "United States",
        "America/New_York"
    ),

    "cnn.com": (
        "CNN",
        "United States",
        "America/New_York"
    ),

    "foxnews.com": (
        "Fox News",
        "United States",
        "America/New_York"
    ),

    "nbcnews.com": (
        "NBC News",
        "United States",
        "America/New_York"
    ),

    "cbsnews.com": (
        "CBS News",
        "United States",
        "America/New_York"
    ),

    "abcnews.go.com": (
        "ABC News",
        "United States",
        "America/New_York"
    ),

    "npr.org": (
        "NPR",
        "United States",
        "America/New_York"
    ),

    "apnews.com": (
        "Associated Press",
        "United States",
        "America/New_York"
    ),


    # --------------------------------------------------------
    # RUSSIA
    # --------------------------------------------------------

    "rt.com": (
        "RT",
        "Russia",
        "Europe/Moscow"
    ),

    "tass.com": (
        "TASS",
        "Russia",
        "Europe/Moscow"
    ),

    "ria.ru": (
        "RIA Novosti",
        "Russia",
        "Europe/Moscow"
    ),

    "rt.ru": (
        "RT",
        "Russia",
        "Europe/Moscow"
    ),


    # --------------------------------------------------------
    # FRANCE
    # --------------------------------------------------------

    "france24.com": (
        "France 24",
        "France",
        "Europe/Paris"
    ),

    "lemonde.fr": (
        "Le Monde",
        "France",
        "Europe/Paris"
    ),

    "lefigaro.fr": (
        "Le Figaro",
        "France",
        "Europe/Paris"
    ),


    # --------------------------------------------------------
    # GERMANY
    # --------------------------------------------------------

    "dw.com": (
        "Deutsche Welle",
        "Germany",
        "Europe/Berlin"
    ),

    "spiegel.de": (
        "Der Spiegel",
        "Germany",
        "Europe/Berlin"
    ),


    # --------------------------------------------------------
    # QATAR / MIDDLE EAST
    # --------------------------------------------------------

    "aljazeera.com": (
        "Al Jazeera",
        "Qatar",
        "Asia/Qatar"
    ),

    "aljazeera.net": (
        "Al Jazeera",
        "Qatar",
        "Asia/Qatar"
    ),


    # --------------------------------------------------------
    # ISRAEL
    # --------------------------------------------------------

    "timesofisrael.com": (
        "The Times of Israel",
        "Israel",
        "Asia/Jerusalem"
    ),

    "haaretz.com": (
        "Haaretz",
        "Israel",
        "Asia/Jerusalem"
    ),


    # --------------------------------------------------------
    # CHINA
    # --------------------------------------------------------

    "globaltimes.cn": (
        "Global Times",
        "China",
        "Asia/Shanghai"
    ),

    "chinadaily.com.cn": (
        "China Daily",
        "China",
        "Asia/Shanghai"
    ),


    # --------------------------------------------------------
    # JAPAN
    # --------------------------------------------------------

    "japantimes.co.jp": (
        "The Japan Times",
        "Japan",
        "Asia/Tokyo"
    ),

    "nhk.or.jp": (
        "NHK",
        "Japan",
        "Asia/Tokyo"
    ),


    # --------------------------------------------------------
    # SOUTH KOREA
    # --------------------------------------------------------

    "koreaherald.com": (
        "The Korea Herald",
        "South Korea",
        "Asia/Seoul"
    ),

    "koreatimes.co.kr": (
        "The Korea Times",
        "South Korea",
        "Asia/Seoul"
    ),


    # --------------------------------------------------------
    # POLAND
    # --------------------------------------------------------

    "pap.pl": (
        "Polish Press Agency",
        "Poland",
        "Europe/Warsaw"
    ),


    # --------------------------------------------------------
    # UKRAINE
    # --------------------------------------------------------

    "kyivindependent.com": (
        "The Kyiv Independent",
        "Ukraine",
        "Europe/Kyiv"
    ),

    "ukrinform.net": (
        "Ukrinform",
        "Ukraine",
        "Europe/Kyiv"
    )

}


# ============================================================
# COUNTRY / TIMEZONE FROM DOMAIN
# ============================================================

TLD_DATABASE = {

    ".kr": (
        "South Korea",
        "Asia/Seoul"
    ),

    ".jp": (
        "Japan",
        "Asia/Tokyo"
    ),

    ".cn": (
        "China",
        "Asia/Shanghai"
    ),

    ".ru": (
        "Russia",
        "Europe/Moscow"
    ),

    ".fr": (
        "France",
        "Europe/Paris"
    ),

    ".de": (
        "Germany",
        "Europe/Berlin"
    ),

    ".uk": (
        "United Kingdom",
        "Europe/London"
    ),

    ".it": (
        "Italy",
        "Europe/Rome"
    ),

    ".es": (
        "Spain",
        "Europe/Madrid"
    ),

    ".pt": (
        "Portugal",
        "Europe/Lisbon"
    ),

    ".ua": (
        "Ukraine",
        "Europe/Kyiv"
    ),

    ".pl": (
        "Poland",
        "Europe/Warsaw"
    ),

    ".se": (
        "Sweden",
        "Europe/Stockholm"
    ),

    ".no": (
        "Norway",
        "Europe/Oslo"
    ),

    ".fi": (
        "Finland",
        "Europe/Helsinki"
    ),

    ".nl": (
        "Netherlands",
        "Europe/Amsterdam"
    ),

    ".be": (
        "Belgium",
        "Europe/Brussels"
    ),

    ".at": (
        "Austria",
        "Europe/Vienna"
    ),

    ".ch": (
        "Switzerland",
        "Europe/Zurich"
    ),

    ".ca": (
        "Canada",
        "America/Toronto"
    ),

    ".au": (
        "Australia",
        "Australia/Sydney"
    ),

    ".in": (
        "India",
        "Asia/Kolkata"
    ),

    ".tr": (
        "Türkiye",
        "Europe/Istanbul"
    ),

    ".il": (
        "Israel",
        "Asia/Jerusalem"
    ),

    ".ir": (
        "Iran",
        "Asia/Tehran"
    )

}


def get_domain(url):

    try:

        domain = urlparse(
            url
        ).netloc.lower()

        domain = domain.split(":")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:

        return ""


def identify_publisher(url, feed_title=""):

    domain = get_domain(url)


    # --------------------------------------------------------
    # FIRST: EXACT DOMAIN DATABASE
    # --------------------------------------------------------

    if domain in PUBLISHER_DATABASE:

        publisher, country, timezone_name = (
            PUBLISHER_DATABASE[domain]
        )

        return publisher, country, timezone_name


    # --------------------------------------------------------
    # SECOND: SUBDOMAIN MATCH
    # --------------------------------------------------------

    for known_domain, data in PUBLISHER_DATABASE.items():

        if domain.endswith(
            "." + known_domain
        ):

            return data


    # --------------------------------------------------------
    # THIRD: NEWSBLUR FEED TITLE
    # --------------------------------------------------------

    if feed_title:

        cleaned_feed = (
            feed_title
            .strip()
        )

        if cleaned_feed:

            return (
                cleaned_feed,
                "Unknown",
                "UTC"
            )


    # --------------------------------------------------------
    # FOURTH: COUNTRY-CODE DOMAIN
    # --------------------------------------------------------

    for tld, data in TLD_DATABASE.items():

        if domain.endswith(tld):

            hostname_parts = domain.split(".")

            if len(hostname_parts) >= 2:

                possible_name = (
                    hostname_parts[-2]
                    .replace("-", " ")
                    .title()
                )

            else:

                possible_name = "Unknown Publisher"


            return (
                possible_name,
                data[0],
                data[1]
            )


    # --------------------------------------------------------
    # FIFTH: DOMAIN NAME FALLBACK
    # --------------------------------------------------------

    if domain:

        hostname_parts = domain.split(".")

        if len(hostname_parts) >= 2:

            publisher = (
                hostname_parts[-2]
                .replace("-", " ")
                .title()
            )

            return (
                publisher,
                "Unknown",
                "UTC"
            )


    return (
        "Unknown Publisher",
        "Unknown",
        "UTC"
    )


# ============================================================
# ARTICLE SCRAPER
# ============================================================

def fetch_full_article(url):

    try:

        downloaded = (
            trafilatura.fetch_url(
                url
            )
        )

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

        print(
            "SCRAPE ERROR:",
            e
        )

        return None


# ============================================================
# KEYWORD SCORING
# ============================================================

def score_article(title, body):

    combined_text = (
        title
        + " "
        + body
    ).lower()

    matched_keywords = []

    score = 0


    for keyword, weight in KEYWORDS.items():

        keyword_lower = (
            keyword.lower()
        )

        if keyword_lower in combined_text:

            matched_keywords.append(
                keyword
            )

            score += weight


    return (
        score,
        matched_keywords
    )


# ============================================================
# NEWSBLUR LOGIN
# ============================================================

NB_USERNAME = os.getenv(
    "NB_USERNAME"
)

NB_PASSWORD = os.getenv(
    "NB_PASSWORD"
)


if not NB_USERNAME or not NB_PASSWORD:

    print(
        "ERROR: NewsBlur credentials are missing."
    )

    exit(1)


session = requests.Session()


login_response = session.post(

    "https://newsblur.com/api/login",

    data={

        "username":
            NB_USERNAME,

        "password":
            NB_PASSWORD

    }

)


if login_response.status_code != 200:

    print(
        "NewsBlur login failed."
    )

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

    datetime.now(
        timezone.utc
    )

    - timedelta(
        hours=24
    )

)


PAGE = 1

ALL_SELECTED = []


print(
    "Fetching unread stories..."
)


while True:

    url = (
        "https://newsblur.com/"
        "reader/river_stories"
    )


    params = {

        "read_filter":
            "unread",

        "order":
            "newest",

        "page":
            PAGE

    }


    response = session.get(

        url,

        params=params

    )


    if not response.headers.get(

        "Content-Type",
        ""

    ).startswith(
        "application/json"
    ):

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
        f"Page {PAGE}: "
        f"{len(stories)} stories"
    )


    stop_pagination = False


    for story in stories:

        try:

            timestamp = (
                datetime.fromtimestamp(

                    int(
                        story[
                            "story_timestamp"
                        ]
                    ),

                    tz=timezone.utc

                )
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
    f"Collected "
    f"{len(ALL_SELECTED)} "
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
        title
        + " "
        + content
    ).lower()


    score = 0

    matched = []


    for keyword, weight in KEYWORDS.items():

        keyword_lower = (
            keyword.lower()
        )


        if keyword_lower in text:

            score += weight

            matched.append(
                keyword
            )


    return (
        score,
        matched
    )


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

            "story":
                story,

            "quick_score":
                score,

            "quick_keywords":
                matched

        })


print()

print(
    f"Keyword filter found "
    f"{len(candidates)} "
    "relevant candidates."
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

    story = candidate[
        "story"
    ]


    title = story.get(

        "story_title",

        ""

    ).strip()


    permalink = story.get(

        "story_permalink",

        ""

    )


    feed_title = story.get(

        "story_feed_title",

        ""

    )


    # --------------------------------------------------------
    # IDENTIFY PUBLISHER / COUNTRY
    # --------------------------------------------------------

    publisher, country, timezone_name = (
        identify_publisher(

            permalink,

            feed_title

        )
    )


    try:

        timestamp_utc = (
            datetime.fromtimestamp(

                int(
                    story[
                        "story_timestamp"
                    ]
                ),

                tz=timezone.utc

            )
        )

    except Exception:

        continue


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
        f"{publisher} · "
        f"{country} · "
        f"{title}"

    )


    # --------------------------------------------------------
    # FULL ARTICLE
    # --------------------------------------------------------

    body = fetch_full_article(
        permalink
    )


    if not body:

        body = title


    # --------------------------------------------------------
    # FINAL RELEVANCE SCORE
    # --------------------------------------------------------

    relevance_score, matched_keywords = (
        score_article(

            title,

            body

        )
    )


    # --------------------------------------------------------
    # ARTICLE OBJECT
    # --------------------------------------------------------

    article = {

        "title":
            title,

        "publisher":
            publisher,

        "url":
            permalink,

        "country":
            country,

        "region":
        "",

        "timezone":
            timezone_name,

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

        "body":
            body

    }


    processed_articles.append(
        article
    )


# ============================================================
# SORT
# ============================================================

processed_articles.sort(

    key=lambda article:
        article[
            "relevance_score"
        ],

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

            )

            + 1

        )


# ============================================================
# TOP 100
# ============================================================

top_articles = (
    processed_articles[:100]
)

# ============================================================
# DAILY GPT SUMMARY
# ============================================================

daily_summary = generate_daily_summary(
    top_articles
)


# ============================================================
# GPT ARTICLE REGION CLASSIFICATION
# ============================================================

region_classifications = (
    classify_article_regions(
        top_articles
    )
)


# ============================================================
# REGIONAL GPT SUMMARIES
# ============================================================

regional_summaries = (
    generate_regional_summaries(
        top_articles
    )
)

# ============================================================
# APPLY REGION CLASSIFICATIONS
# ============================================================

for index, article in enumerate(top_articles):

    article["region"] = (
        region_classifications.get(
            str(index),
            "america_other"
        )
    )


# ============================================================
# OUTPUT
# ============================================================

output = {

    "generated_at":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "daily_summary":
    daily_summary,

"regional_summaries":
    regional_summaries,

"article_count":
    len(ALL_SELECTED),

    "processed_article_count":
        len(processed_articles),

    "relevant_article_count":
        len(processed_articles),

    "displayed_article_count":
        len(top_articles),

    "keyword_frequency":
        keyword_frequency,

    "articles":
        top_articles

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
    "Articles displayed:",
    len(top_articles)
)

print(
    "================================"
)
