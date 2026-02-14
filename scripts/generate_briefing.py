import os
import json
import datetime
import anthropic

def generate_briefing():
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    today = datetime.date.today().strftime("%A, %B %d, %Y")

    prompt = f"""Today is {today}. You are a professional news curator.
Search the web and create a daily briefing with EXACTLY 50 top stories covering these areas:

1. Active wars/conflicts worldwide
2. India AI Mission updates
3. India Semiconductor Mission updates
4. Latest from OpenAI, Google AI, Microsoft AI, Grok/xAI, Cursor
5. Global AI business news
6. US Politics & Economy
7. India Politics & Economy
8. India Government policies
9. Fortune 500 company news
10. India corporate news (BFSI, Pharma, Manufacturing, Mining, Hospitality, Services)
11. Top 10 from India startup ecosystem
12. Top 10 from AI startup ecosystem
13. India Budget, Economics, GDP & Rare Earth/Mining priorities

For EACH story provide:
- A bold headline
- Source name and date
- 2-3 sentence summary of key facts and implications
- Direct URL to the source article

Format the output as a JSON array where each item has:
{{"section": "...", "headline": "...", "source": "...", "date": "...", "summary": "...", "url": "..."}}

Search sources including: Guardian, Bloomberg, The Economist, Times of India,
Wall Street Journal, Mint, Hindustan Times, Business Insider, Analytics India Magazine,
TechCrunch, Reuters, CNBC, Economic Times, and others.

Return ONLY the JSON array, no other text."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8000,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search"
        }],
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract text content from response
    text_content = ""
    for block in response.content:
        if hasattr(block, "text"):
            text_content += block.text

    # Parse JSON from response
    # Try to find JSON array in the response
    start = text_content.find("[")
    end = text_content.rfind("]") + 1
    if start >= 0 and end > start:
        stories = json.loads(text_content[start:end])
    else:
        stories = []

    return stories, today


def build_html(stories, date_str):
    """Build the PWA-ready HTML briefing page."""

    # Group stories by section
    sections = {}
    for story in stories:
        sec = story.get("section", "Other")
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(story)

    # Section colors
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

    # Build story cards HTML
    cards_json = json.dumps(stories, ensure_ascii=False)

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
       overscroll-behavior:none; -webkit-user-select:none; user-select:none; }}
.top-bar {{ position:fixed; top:0; left:0; right:0; z-index:100;
           background:rgba(15,23,42,0.95); backdrop-filter:blur(10px);
           padding:12px 16px; display:flex; justify-content:space-between; align-items:center;
           border-bottom:1px solid rgba(255,255,255,0.1); }}
.top-bar h1 {{ font-size:14px; font-weight:600; color:#F8FAFC; }}
.counter {{ font-size:12px; color:#94A3B8; }}
.progress {{ position:fixed; top:52px; left:0; right:0; height:3px; background:rgba(255,255,255,0.1); z-index:100; }}
.progress-fill {{ height:100%; background:linear-gradient(90deg,#F59E0B,#EF4444); transition:width 0.3s; }}
.card-container {{ padding:68px 16px 80px; min-height:100vh; }}
.card {{ background:#1E293B; border-radius:16px; padding:20px; margin-bottom:12px;
        border-left:4px solid #666; transition:transform 0.2s; }}
.card:active {{ transform:scale(0.98); }}
.section-tag {{ display:inline-block; font-size:11px; font-weight:600; text-transform:uppercase;
               letter-spacing:0.05em; padding:4px 10px; border-radius:20px;
               margin-bottom:10px; color:#fff; }}
.headline {{ font-size:17px; font-weight:700; color:#F8FAFC; line-height:1.35;
            margin-bottom:8px; }}
.headline a {{ color:inherit; text-decoration:none; }}
.headline a:hover {{ text-decoration:underline; }}
.meta {{ font-size:12px; color:#64748B; margin-bottom:8px; }}
.summary {{ font-size:14px; color:#CBD5E1; line-height:1.55; }}
.section-header {{ font-size:13px; font-weight:700; text-transform:uppercase;
                  letter-spacing:0.08em; color:#94A3B8; padding:16px 0 8px;
                  border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:12px; }}
.footer {{ text-align:center; padding:24px; color:#475569; font-size:12px; }}
</style>
</head>
<body>

<div class="top-bar">
  <h1>📰 Daily Briefing</h1>
  <span class="counter" id="date">{date_str}</span>
</div>
<div class="progress"><div class="progress-fill" id="progressFill"></div></div>

<div class="card-container" id="cards">
"""

    # Build cards grouped by section
    for section, items in sections.items():
        color = section_colors.get(section, "#64748B")
        html += f'<div class="section-header" style="color:{color}">{section}</div>\\n'
        for item in items:
            headline = item.get("headline", "")
            source = item.get("source", "")
            date = item.get("date", "")
            summary = item.get("summary", "")
            url = item.get("url", "#")
            html += f"""<div class="card" style="border-left-color:{color}">
  <span class="section-tag" style="background:{color}40;color:{color}">{section}</span>
  <div class="headline"><a href="{url}" target="_blank" rel="noopener">{headline}</a></div>
  <div class="meta">{source} · {date}</div>
  <div class="summary">{summary}</div>
</div>
"""

    html += """</div>
<div class="footer">Generated automatically by your AI News Curator</div>

<script>
// Progress bar on scroll
window.addEventListener('scroll', () => {
  const h = document.documentElement;
  const pct = (h.scrollTop / (h.scrollHeight - h.clientHeight)) * 100;
  document.getElementById('progressFill').style.width = Math.min(pct, 100) + '%';
});
// Register service worker for PWA
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
</script>
</body>
</html>"""
    return html


def build_manifest():
    return json.dumps({
        "name": "Daily News Briefing",
        "short_name": "Briefing",
        "description": "Your personalized daily news briefing",
        "start_url": "/daily-briefing/",
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
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(['./', 'index.html'])));
});
self.addEventListener('fetch', e => {
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});"""


if __name__ == "__main__":
    print("🔍 Generating today's briefing...")
    stories, date_str = generate_briefing()
    print(f"📰 Got {len(stories)} stories")

    html = build_html(stories, date_str)

    # Write outputs
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w") as f:
        f.write(html)
    with open("docs/manifest.json", "w") as f:
        f.write(build_manifest())
    with open("docs/sw.js", "w") as f:
        f.write(build_service_worker())

    print("✅ Briefing generated at docs/index.html")
