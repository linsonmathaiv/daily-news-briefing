import os
import json
import re
import datetime
import anthropic


def generate_briefing():
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    today = datetime.date.today().strftime("%A, %B %d, %Y")

    system_prompt = """You are a professional news curator. You MUST respond with ONLY a valid JSON array.
No markdown, no code fences, no explanation — ONLY the raw JSON array.

The JSON array must contain objects with these exact keys:
"section", "headline", "source", "date", "summary", "url"

Valid section values are:
"Wars & Conflicts", "India AI Mission", "India Semiconductor Mission",
"AI — Big Tech", "AI Business News", "US Politics & Economy",
"India Politics & Economy", "India Government Policies", "Fortune 500",
"India Corporate", "India Startups", "AI Startups", "India Economy & Rare Earth"
"""

    user_prompt = f"""Today is {today}.

Search the web thoroughly and create a daily briefing with 50 top stories across these areas:

1. Active wars/conflicts worldwide (4 stories)
2. India AI Mission updates (3 stories)
3. India Semiconductor Mission updates (3 stories)
4. Latest from OpenAI, Google AI, Microsoft AI, Grok/xAI, Cursor (5 stories)
5. Global AI business news (4 stories)
6. US Politics & Economy (4 stories)
7. India Politics & Economy (4 stories)
8. India Government policies (3 stories)
9. Fortune 500 company news (4 stories)
10. India corporate news — BFSI, Pharma, Manufacturing, Mining, Hospitality, Services (5 stories)
11. India startup ecosystem (5 stories)
12. AI startup ecosystem (3 stories)
13. India Budget, Economics, GDP, Rare Earth & Mining (3 stories)

Search sources including: Guardian, Bloomberg, The Economist, Times of India,
Wall Street Journal, Mint, Hindustan Times, Business Insider, Analytics India Magazine,
TechCrunch, Reuters, CNBC, Economic Times, and any other credible sources.

For each story provide: headline, source name, date, a 2-3 sentence summary, and the source URL.

IMPORTANT: Your ENTIRE response must be a valid JSON array. No other text before or after.
Example format:
[
  {{"section": "Wars & Conflicts", "headline": "...", "source": "Reuters", "date": "Feb 15, 2026", "summary": "...", "url": "https://..."}},
  ...
]"""

    # Use a loop to handle multi-turn tool use (web search requires this)
    messages = [{"role": "user", "content": user_prompt}]

    all_text = ""
    max_iterations = 20  # Safety limit

    for i in range(max_iterations):
        print(f"  API call {i + 1}...")

        # Retry up to 3 times on server errors
        response = None
        for attempt in range(3):
            try:
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=16000,
                    system=system_prompt,
                    tools=[{
                        "type": "web_search_20250305",
                        "name": "web_search"
                    }],
                    messages=messages
                )
                break  # Success, exit retry loop
            except Exception as e:
                print(f"  Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    import time
                    wait_time = 10 * (attempt + 1)  # 10s, 20s
                    print(f"  Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise  # Give up after 3 attempts

        if response is None:
            raise Exception("Failed to get API response after 3 attempts")

        # Collect all text blocks from this response
        for block in response.content:
            if hasattr(block, "text") and block.text:
                all_text += block.text

        print(f"  Stop reason: {response.stop_reason}")

        # If the model is done, break
        if response.stop_reason == "end_turn":
            break

        # If the model wants to use a tool (web search), we need to send the
        # response back and let it continue
        if response.stop_reason == "tool_use":
            # Add assistant's response to messages
            messages.append({"role": "assistant", "content": response.content})

            # Collect all tool_use blocks and create results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Search completed. Continue generating the briefing."
                    })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
        else:
            # Any other stop reason, we're done
            break

    print(f"  Total text collected: {len(all_text)} characters")

    # Parse JSON from collected text
    stories = extract_json_array(all_text)
    return stories, today


def extract_json_array(text):
    """Robustly extract a JSON array from text that may contain other content."""

    # First, try to find a JSON array directly
    # Remove markdown code fences if present
    cleaned = re.sub(r'```json\s*', '', text)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()

    # Try parsing the whole cleaned text
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            print(f"  Parsed {len(result)} stories (direct parse)")
            return result
    except json.JSONDecodeError:
        pass

    # Try to find array boundaries
    start = cleaned.find("[")
    if start >= 0:
        # Find the matching closing bracket
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
                            print(f"  Parsed {len(result)} stories (bracket match)")
                            return result
                    except json.JSONDecodeError:
                        pass
                    break

    # Last resort: try to find individual JSON objects and collect them
    objects = []
    for match in re.finditer(r'\{[^{}]*"headline"[^{}]*\}', cleaned):
        try:
            obj = json.loads(match.group())
            objects.append(obj)
        except json.JSONDecodeError:
            pass

    if objects:
        print(f"  Parsed {len(objects)} stories (individual objects)")
        return objects

    print("  WARNING: Could not parse any stories from response")
    print(f"  Response preview: {text[:500]}...")
    return []


def build_html(stories, date_str):
    """Build the PWA-ready HTML briefing page."""

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

    def get_color(section):
        for key, color in section_colors.items():
            if key.lower() in section.lower():
                return color
        return "#64748B"

    # Group stories by section
    sections = {}
    for story in stories:
        sec = story.get("section", "Other")
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(story)

    # Build cards HTML
    cards_html = ""
    story_count = 0

    for section, items in sections.items():
        color = get_color(section)
        cards_html += f'<div class="section-header" style="color:{color}">{section}</div>\n'
        for item in items:
            story_count += 1
            headline = item.get("headline", "No headline")
            source = item.get("source", "Unknown")
            date = item.get("date", "")
            summary = item.get("summary", "")
            url = item.get("url", "#")

            # Escape HTML entities
            headline = headline.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            summary = summary.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            source = source.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            cards_html += f"""<div class="card" style="border-left-color:{color}">
  <span class="section-tag" style="background:{color}30;color:{color}">{section}</span>
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
  <p>The briefing generation may have encountered an issue. Check the GitHub Actions log for details.</p>
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

    print("\n1. Generating today's briefing...")
    stories, date_str = generate_briefing()
    print(f"\n2. Got {len(stories)} stories")

    if stories:
        print(f"   Sections found: {set(s.get('section', 'Other') for s in stories)}")

    print("\n3. Building HTML...")
    html = build_html(stories, date_str)

    print("\n4. Writing files...")
    os.makedirs("docs", exist_ok=True)

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   docs/index.html ({len(html)} bytes)")

    with open("docs/manifest.json", "w") as f:
        f.write(build_manifest())
    print("   docs/manifest.json")

    with open("docs/sw.js", "w") as f:
        f.write(build_service_worker())
    print("   docs/sw.js")

    print(f"\n{'=' * 50}")
    print(f"DONE — {len(stories)} stories generated for {date_str}")
    print(f"{'=' * 50}")
