import os
import json
import re
import time
import datetime
import anthropic


# Define the sections and their search queries
SECTIONS = [
    {
        "section": "Wars & Conflicts",
        "count": 4,
        "query": "Search for the latest news today about active wars and armed conflicts worldwide including Ukraine-Russia, Israel-Gaza, Sudan, Myanmar, and any other ongoing conflicts. Return the top 4 most important stories."
    },
    {
        "section": "India AI Mission",
        "count": 3,
        "query": "Search for the latest news about India AI Mission, IndiaAI, India artificial intelligence policy, government AI initiatives in India. Return the top 3 most important stories."
    },
    {
        "section": "India Semiconductor Mission",
        "count": 3,
        "query": "Search for the latest news about India Semiconductor Mission, chip manufacturing in India, semiconductor fabs India, Tata Electronics, Micron India. Return the top 3 most important stories."
    },
    {
        "section": "AI — Big Tech",
        "count": 5,
        "query": "Search for the latest news from OpenAI, Google AI Gemini, Microsoft AI Copilot, xAI Grok, Cursor AI editor. What are the biggest AI announcements and product launches? Return the top 5 stories."
    },
    {
        "section": "AI Business News",
        "count": 4,
        "query": "Search for the latest global business news about artificial intelligence — AI investments, AI company funding, AI partnerships, enterprise AI adoption. Return the top 4 stories."
    },
    {
        "section": "US Politics & Economy",
        "count": 4,
        "query": "Search for the latest US politics news, US economy updates, Federal Reserve, trade policy, Congress legislation. Return the top 4 stories."
    },
    {
        "section": "India Politics & Economy",
        "count": 4,
        "query": "Search for the latest India politics news, India economy updates, RBI policy, India trade, India GDP. Return the top 4 stories."
    },
    {
        "section": "India Government Policies",
        "count": 3,
        "query": "Search for the latest Indian government policy announcements, new schemes, regulatory changes, budget announcements. Return the top 3 stories."
    },
    {
        "section": "Fortune 500",
        "count": 4,
        "query": "Search for the latest news from Fortune 500 companies — earnings, layoffs, acquisitions, leadership changes, major announcements from Apple, Amazon, Google, Tesla, etc. Return the top 4 stories."
    },
    {
        "section": "India Corporate",
        "count": 5,
        "query": "Search for the latest India corporate news across BFSI banking, pharma, manufacturing, mining, hospitality, IT services — companies like TCS, Infosys, Reliance, HDFC, Tata, Adani. Return the top 5 stories."
    },
    {
        "section": "India Startups",
        "count": 5,
        "query": "Search for the latest Indian startup news — funding rounds, IPOs, unicorns, startup acquisitions, new launches from India startups. Return the top 5 stories."
    },
    {
        "section": "AI Startups",
        "count": 3,
        "query": "Search for the latest AI startup news worldwide — funding rounds, new AI companies, AI startup launches, AI unicorns. Return the top 3 stories."
    },
    {
        "section": "India Economy & Rare Earth",
        "count": 3,
        "query": "Search for latest news about India budget, GDP growth, rare earth minerals India, India mining policy, critical minerals India. Return the top 3 stories."
    },
]


def fetch_section(client, section_info, today):
    """Fetch stories for one section."""
    section = section_info["section"]
    count = section_info["count"]
    query = section_info["query"]

    system = f"""You are a news curator. Return ONLY a valid JSON array with no other text.
Each object must have exactly these keys: "headline", "source", "date", "summary", "url"
Return exactly {count} news stories. No markdown, no code fences, no explanation.
Just the raw JSON array starting with [ and ending with ]"""

    user_msg = f"""Today is {today}. {query}

Remember: respond with ONLY a JSON array. Example:
[{{"headline": "Example Headline", "source": "Reuters", "date": "Feb 15, 2026", "summary": "Two sentence summary here.", "url": "https://example.com/article"}}]"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4000,
                system=system,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search"
                }],
                messages=[{"role": "user", "content": user_msg}]
            )

            # Collect text from response
            all_text = ""
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    all_text += block.text

            # If we got no text but stop reason is end_turn, the model
            # may have done web search but not produced final text.
            # In that case, make a follow-up call without web search.
            if not all_text.strip() or "[" not in all_text:
                # Try a second call asking it to format what it found
                follow_up = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=4000,
                    system=system,
                    messages=[
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": "Based on my search, here are the stories:\n["},
                    ]
                )
                all_text = "["
                for block in follow_up.content:
                    if hasattr(block, "text") and block.text:
                        all_text += block.text

            stories = extract_json_array(all_text)

            # Add section to each story
            for s in stories:
                s["section"] = section

            if stories:
                return stories

            print(f"    No stories parsed, attempt {attempt + 1}")

        except Exception as e:
            print(f"    Error on attempt {attempt + 1}: {e}")
            if attempt < 2:
                time.sleep(10 * (attempt + 1))

    return []


def extract_json_array(text):
    """Robustly extract a JSON array from text."""
    if not text:
        return []

    # Remove code fences
    cleaned = re.sub(r'```json\s*', '', text)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Find array boundaries with bracket matching
    start = cleaned.find("[")
    if start >= 0:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "[":
                depth += 1
            elif cleaned[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        result = json.loads(cleaned[start:i + 1])
                        if isinstance(result, list):
                            return result
                    except json.JSONDecodeError:
                        # Try fixing common issues
                        fragment = cleaned[start:i + 1]
                        # Fix trailing commas
                        fragment = re.sub(r',\s*]', ']', fragment)
                        fragment = re.sub(r',\s*}', '}', fragment)
                        try:
                            result = json.loads(fragment)
                            if isinstance(result, list):
                                return result
                        except json.JSONDecodeError:
                            pass
                    break

    # Last resort: find individual objects
    objects = []
    for match in re.finditer(r'\{[^{}]*"headline"[^{}]*\}', cleaned):
        try:
            obj = json.loads(match.group())
            objects.append(obj)
        except json.JSONDecodeError:
            pass

    return objects


def build_html(stories, date_str):
    """Build the PWA-ready HTML briefing page."""

    section_colors = {
        "Wars & Conflicts": "#DC2626",
        "India AI Mission": "#F59E0B",
        "India Semiconductor Mission": "#3B82F6",
        "AI — Big Tech": "#8B5CF6",
        "AI Business News": "#6366F1",
        "US Politics & Economy": "#0EA5E9",
        "India Politics & Economy": "#F97316",
        "India Government Policies": "#EF4444",
        "Fortune 500": "#10B981",
        "India Corporate": "#14B8A6",
        "India Startups": "#EC4899",
        "AI Startups": "#A855F7",
        "India Economy & Rare Earth": "#78716C",
    }

    def get_color(section):
        for key, color in section_colors.items():
            if key.lower() in section.lower():
                return color
        return "#64748B"

    # Group by section preserving order
    from collections import OrderedDict
    sections = OrderedDict()
    for story in stories:
        sec = story.get("section", "Other")
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(story)

    cards_html = ""
    story_count = 0

    for section, items in sections.items():
        color = get_color(section)
        cards_html += f'<div class="section-header" style="color:{color}">{esc(section)}</div>\n'
        for item in items:
            story_count += 1
            headline = esc(item.get("headline", "No headline"))
            source = esc(item.get("source", "Unknown"))
            date = esc(item.get("date", ""))
            summary = esc(item.get("summary", ""))
            url = item.get("url", "#")

            cards_html += f"""<div class="card" style="border-left-color:{color}">
  <span class="section-tag" style="background:{color}30;color:{color}">{esc(section)}</span>
  <div class="headline"><a href="{url}" target="_blank" rel="noopener">{headline}</a></div>
  <div class="meta">{source} &middot; {date}</div>
  <div class="summary">{summary}</div>
</div>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0F172A">
<link rel="manifest" href="manifest.json">
<title>Daily Briefing — {date_str}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Inter',sans-serif; background:#0F172A; color:#E2E8F0;
       overscroll-behavior-y:contain; }}
.top-bar {{ position:fixed; top:0; left:0; right:0; z-index:100;
           background:rgba(15,23,42,0.95); backdrop-filter:blur(10px);
           padding:12px 16px; display:flex; justify-content:space-between; align-items:center;
           border-bottom:1px solid rgba(255,255,255,0.1); }}
.top-bar h1 {{ font-size:14px; font-weight:600; color:#F8FAFC; }}
.counter {{ font-size:12px; color:#94A3B8; }}
.progress {{ position:fixed; top:52px; left:0; right:0; height:3px;
            background:rgba(255,255,255,0.1); z-index:100; }}
.progress-fill {{ height:100%; background:linear-gradient(90deg,#F59E0B,#EF4444);
                 transition:width 0.3s; width:0%; }}
.card-container {{ padding:68px 16px 80px; max-width:680px; margin:0 auto; }}
.card {{ background:#1E293B; border-radius:16px; padding:20px; margin-bottom:12px;
        border-left:4px solid #666; }}
.section-tag {{ display:inline-block; font-size:11px; font-weight:600;
               text-transform:uppercase; letter-spacing:0.05em; padding:4px 10px;
               border-radius:20px; margin-bottom:10px; }}
.headline {{ font-size:17px; font-weight:700; color:#F8FAFC; line-height:1.35;
            margin-bottom:8px; }}
.headline a {{ color:inherit; text-decoration:none; }}
.headline a:hover {{ text-decoration:underline; }}
.meta {{ font-size:12px; color:#64748B; margin-bottom:8px; }}
.summary {{ font-size:14px; color:#CBD5E1; line-height:1.55; }}
.section-header {{ font-size:13px; font-weight:700; text-transform:uppercase;
                  letter-spacing:0.08em; color:#94A3B8; padding:20px 0 8px;
                  border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:12px; }}
.footer {{ text-align:center; padding:24px; color:#475569; font-size:12px; }}
.empty-state {{ text-align:center; padding:80px 20px; color:#64748B; }}
.empty-state h2 {{ color:#94A3B8; margin-bottom:12px; }}
.story-count {{ background:#F59E0B20; color:#F59E0B; padding:2px 8px; border-radius:8px;
               font-size:12px; font-weight:600; }}
</style>
</head>
<body>

<div class="top-bar">
  <h1>&#x1F4F0; Daily Briefing</h1>
  <div>
    <span class="story-count">{story_count} stories</span>
    <span class="counter" style="margin-left:8px">{date_str}</span>
  </div>
</div>
<div class="progress"><div class="progress-fill" id="progressFill"></div></div>

<div class="card-container" id="cards">
"""

    if story_count > 0:
        html += cards_html
    else:
        html += """<div class="empty-state">
  <h2>No stories today</h2>
  <p>The briefing generation encountered an issue. Check the GitHub Actions log.</p>
</div>
"""

    html += f"""</div>
<div class="footer">
  Generated automatically at {date_str}<br>
  Powered by Claude AI &middot; {story_count} stories curated
</div>

<script>
window.addEventListener('scroll', function() {{
  var h = document.documentElement;
  var pct = (h.scrollTop / (h.scrollHeight - h.clientHeight)) * 100;
  document.getElementById('progressFill').style.width = Math.min(pct, 100) + '%';
}});
if ('serviceWorker' in navigator) {{
  navigator.serviceWorker.register('sw.js').catch(function() {{}});
}}
</script>
</body>
</html>"""

    return html


def esc(text):
    """Escape HTML entities."""
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_manifest():
    return json.dumps({
        "name": "Daily News Briefing",
        "short_name": "Briefing",
        "description": "Your personalized daily news briefing",
        "start_url": "./",
        "display": "standalone",
        "background_color": "#0F172A",
        "theme_color": "#0F172A",
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }, indent=2)


def build_service_worker():
    return """const CACHE = 'briefing-v1';
self.addEventListener('install', function(e) {
  e.waitUntil(caches.open(CACHE).then(function(c) { return c.addAll(['./', 'index.html']); }));
  self.skipWaiting();
});
self.addEventListener('fetch', function(e) {
  e.respondWith(fetch(e.request).catch(function() { return caches.match(e.request); }));
});"""


if __name__ == "__main__":
    print("=" * 50)
    print("DAILY NEWS BRIEFING GENERATOR")
    print("=" * 50)

    today = datetime.date.today().strftime("%A, %B %d, %Y")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    all_stories = []

    for i, section_info in enumerate(SECTIONS):
        section = section_info["section"]
        print(f"\n[{i+1}/{len(SECTIONS)}] Fetching: {section}...")

        stories = fetch_section(client, section_info, today)
        print(f"  Got {len(stories)} stories")
        all_stories.extend(stories)

        # Small delay between sections to avoid rate limits
        if i < len(SECTIONS) - 1:
            time.sleep(2)

    print(f"\n{'=' * 50}")
    print(f"Total stories collected: {len(all_stories)}")
    print(f"{'=' * 50}")

    print("\nBuilding HTML...")
    html = build_html(all_stories, today)

    print("Writing files...")
    os.makedirs("docs", exist_ok=True)

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  docs/index.html ({len(html):,} bytes)")

    with open("docs/manifest.json", "w") as f:
        f.write(build_manifest())

    with open("docs/sw.js", "w") as f:
        f.write(build_service_worker())

    print(f"\nDONE — {len(all_stories)} stories for {today}")
