from __future__ import annotations

INTRO_TEXT = (
    "Welcome to The Signal, a short podcast for communicators at CN — the people "
    "who write the stories, build the presentations, draft the speeches, and send "
    "the emails that connect us. I'm Jeff Scott, and each episode, I'll pick one "
    "topic where AI and communications overlap to dig into what's actually useful "
    "for our work. Let's get into it."
)

ENDING_TOKEN = "Food for Thought"
OUTRO_TEXT = (
    "That's it for this week. If you've got a topic you'd like me to explore, "
    "or you tried something that worked, drop it in the CN GPT Teams channel. "
    "I'm Jeff Scott, and this has been The Signal."
)

# Paragraphs used to pad a script that falls below TARGET_MIN_WORDS.
# Listed in preferred insertion order.
PADDING_PARAGRAPHS: tuple[str, ...] = (
    (
        "Taken together, these updates point to a practical shift for communications teams: "
        "AI works best when it supports judgment, not when it replaces it. The strongest use "
        "cases are the ones that remove repetitive drafting and coordination friction while "
        "keeping accountability, context, and tone in human hands."
    ),
    (
        "That balance matters at CN as well. If teams define where AI can accelerate routine "
        "work, and where communicators need to lead with nuance and trust, they can move faster "
        "without sacrificing clarity or credibility."
    ),
)

BANNED_BOILERPLATE = [
    "subscribe",
    "sign up",
    "newsletter",
    "continue reading",
    "in your inbox",
    "this story originally appeared",
    "read more",
    "click here",
]

BANNED_TEMPLATE_MARKERS = ["Source:", "What happened:", "Why this matters:"]

EXCLUDE_KEYWORDS = [
    "policy",
    "politics",
    "military",
    "geopolitical",
    "war",
    "conflict",
    "legislation",
    "regulation",
    "congress",
    "senate",
    "parliament",
    "defense",
    "defence",
    "pentagon",
    "battlefield",
    "tariff",
    "trade war",
    "sanction",
    "border policy",
    "white house",
    "election",
    "campaign trail",
    "prime minister",
    "president",
    "seed round",
    "series a",
    "series b",
    "hands-on",
    "review",
    "camera sensor",
    "smartphone",
    "earbuds",
    "gaming",
    "game boy",
    "switch 2",
    "pokemon",
    # Layoffs / job losses — focus on empowering and educating, not fear
    "layoff",
    "layoffs",
    "laid off",
    "job losses",
    "job cuts",
    "cutting jobs",
    "downsizing",
    "workforce reduction",
    "mass firing",
    "replace workers",
    "replacing workers",
    "replacing jobs",
    "eliminate jobs",
    "eliminating jobs",
    # Sports — too much risk of false positives via "agent", "team", "media"
    "hockey",
    "nhl",
    "nfl",
    "nba",
    "mlb",
    "mls",
    "locker room",
    "playoff",
    "championship",
    "tournament",
    "athlete",
    "stadium",
    "soccer",
    "basketball",
    "football",
    "baseball",
    "tennis",
    "golf",
    "olympic",
    "olympics",
]

PREFERRED_KEYWORDS = [
    "workflow",
    "automation",
    "productivity",
    "adoption",
    "literacy",
    "tool",
    "copilot",
    "assistant",
    "customer service",
    "knowledge",
    "training",
    "communications",
    "comms",
    "pr",
    "prompt",
    "prompting",
    "chatgpt",
    "claude",
    "gemini",
    "writing assistant",
    "content tool",
    "template",
    "summarize",
    "summarization",
    "rewrite",
    "brainstorm",
    "ideation",
    "first draft",
    "how to use",
    "tips",
    "tutorial",
    "use case",
]

AI_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "llm",
    "chatbot",
    "generative",
    "machine learning",
    "large language model",
    "foundation model",
    "AI model",
]

COMMS_KEYWORDS = [
    "communications",
    "public relations",
    "pr",
    "internal comms",
    "marketing",
    "media",
    "stakeholder",
    "reputation",
    "brand",
    "messaging",
    "employee communications",
    "change communications",
    "executive communications",
    "press release",
    "media relations",
    "corporate communications",
    "writing",
    "content creation",
    "storytelling",
    "presentation",
    "speech",
    "email",
    "newsletter",
    "digital signage",
    "intranet",
    "video",
    "social media",
    "editing",
    "proofreading",
    "tone",
    "drafting",
    "copywriting",
    "content strategy",
]

WORKPLACE_KEYWORDS = [
    "enterprise",
    "business",
    "workplace",
    "employee",
    "operations",
    "process",
    "knowledge work",
    "customer support",
    "contact center",
]

SOURCE_ALLOWLIST_BASELINE = {
    # AI labs & companies
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "blog.google",
    "microsoft.com",
    "blogs.microsoft.com",
    "huggingface.co",
    "engineering.fb.com",
    "ai.meta.com",
    # AI practitioners & newsletters
    "simonwillison.net",
    "jack-clark.net",
    "thedeepview.substack.com",
    "therundown.substack.com",
    "lastweekin.ai",
    "stratechery.com",
    "ben-evans.com",
    # AI / tech press
    "theverge.com",
    "techcrunch.com",
    "wired.com",
    "technologyreview.com",
    "arstechnica.com",
    "venturebeat.com",
    "zdnet.com",
    "infoq.com",
    "axios.com",
    "fastcompany.com",
    "forbes.com",
    # Communications / PR
    "prdaily.com",
    "prweek.com",
    "prmoment.com",
    "meltwater.com",
    "everything-pr.com",
    "cision.com",
    "ragan.com",
    "spinsucks.com",
    # Business / analysis
    "hbr.org",
    "sloanreview.mit.edu",
    # Mainstream journalism
    "nytimes.com",
    "bbc.com",
    "bbc.co.uk",
    "theguardian.com",
    "cnbc.com",
    "theglobeandmail.com",
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "npr.org",
    "apnews.com",
    # Podcasts
    "simplecast.com",
    "lexfridman.com",
    "libsyn.com",
}

RSS_FEEDS = [
    # ── AI labs & company blogs ���─────────────────────────────────────
    "https://openai.com/news/rss.xml",
    "https://deepmind.google/blog/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://huggingface.co/blog/feed.xml",
    "https://engineering.fb.com/feed/",                        # Meta AI / engineering
    # ── AI practitioner blogs ─────��──────────────────────────────────
    "https://simonwillison.net/atom/everything/",              # Simon Willison
    "https://jack-clark.net/feed/",                            # Import AI (Anthropic co-founder)
    # ── AI newsletters ────────���──────────────────────────────────────
    "https://thedeepview.substack.com/feed",                   # The Deep View
    "https://therundown.substack.com/feed",                    # The Rundown AI
    "https://lastweekin.ai/feed",                              # Last Week in AI
    # ── AI / tech press ──────────────────────────────────────────────
    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://techcrunch.com/tag/generative-ai/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",
    "https://www.infoq.com/ai-ml-data-eng/feed/",
    "https://www.axios.com/technology/rss.xml",
    # ── AI + business / analysis ─────────────────────────────────────
    "https://stratechery.com/feed/",                           # Ben Thompson (free articles)
    "https://www.ben-evans.com/benedictevans?format=rss",      # Benedict Evans
    "https://sloanreview.mit.edu/tag/artificial-intelligence/feed/",
    "https://hbr.org/topic/subject/technology-and-analytics/rss",
    "https://hbr.org/topic/subject/artificial-intelligence/rss",
    "https://www.fastcompany.com/section/technology/rss",
    "https://www.forbes.com/innovation/feed2/",
    # ── Communications / PR industry ─���───────────────────────────────
    "https://www.prdaily.com/feed/",
    "https://www.prdaily.com/category/ai/feed/",
    "https://www.prdaily.com/category/media-relations/feed/",
    "https://www.prdaily.com/category/internal-communications/feed/",
    "https://www.ragan.com/feed/",                             # Ragan Communications
    "https://spinsucks.com/feed/",                             # Spin Sucks (AI in PR)
    # ── Mainstream / quality journalism ──────────────────────────────
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://www.bbc.com/news/technology/rss.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://www.theguardian.com/technology/artificialintelligenceai/rss",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html",
    "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/technology/?outputType=xml",
    # ── Podcasts (show notes as article source) ──────────────────────
    "https://feeds.simplecast.com/l2i9YnTd",                  # Hard Fork (NYT)
    "https://lexfridman.com/feed/podcast/",                    # Lex Fridman Podcast
    "https://allinchamathjason.libsyn.com/rss",                # All-In Podcast
]

COVER_PALETTE = [
    "#005f73",
    "#0a9396",
    "#94d2bd",
    "#ee9b00",
    "#ca6702",
    "#bb3e03",
    "#ae2012",
]

DEFAULT_STORY_COUNT = 3
MIN_STORY_COUNT = 1
MAX_STORY_COUNT = 30

MAX_CANDIDATES = 1200
MAX_CANDIDATES_PER_FEED = 120
MAX_SHORTLIST = 30
MAX_PER_SOURCE_WEEK = 3

TARGET_MIN_WORDS = 700
TARGET_MAX_WORDS = 850
HARD_MAX_WORDS = 900
MAX_REWRITES = 2

TIMEZONE = "America/Toronto"

THEME_COOLDOWN_DAYS = 30
THEME_BANK_PATH = "data/theme_bank.json"
