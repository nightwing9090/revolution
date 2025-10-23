import requests
import sys
import re
import concurrent.futures
from urllib.parse import urljoin

FALLBACK_LOGOS = {
    "american-football": "https://i.postimg.cc/FHKccJkQ/fallback.webp",
    "football":          "https://i.postimg.cc/FHKccJkQ/fallback.webp",
    "fight":             "https://i.postimg.cc/FHKccJkQ/fallback.webp",
    "basketball":        "https://i.postimg.cc/FHKccJkQ/fallback.webp",
    "motor sports":      "https://i.postimg.cc/FHKccJkQ/fallback.webp",
    "darts":             "https://i.postimg.cc/FHKccJkQ/fallback.webp",
    "hockey":             "https://i.postimg.cc/FHKccJkQ/fallback.webp"
}

CUSTOM_HEADERS = {
    "Origin": "https://embedsports.top",
    "Referer": "https://embedsports.top/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0"
}

TV_IDS = {
    "Baseball": "MLB.Baseball.Dummy.us",
    "Fight": "PPV.EVENTS.Dummy.us",
    "American Football": "NFL.Dummy.us",
    "Afl": "AUS.Rules.Football.Dummy.us",
    "Football": "Soccer.Dummy.us",
    "Basketball": "Basketball.Dummy.us",
    "Hockey": "NHL.Hockey.Dummy.us",
    "Tennis": "Tennis.Dummy.us",
    "Darts": "Darts.Dummy.us",
    "Motor Sports": "Racing.Dummy.us"
}

def get_matches(endpoint="all"):
    url = f"https://streamed.pk/api/matches/{endpoint}"
    try:
        print(f"📡 Fetching {endpoint} matches from the API...")
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        print(f"✅ Successfully fetched {endpoint} matches.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching {endpoint} matches: {e}", file=sys.stderr)
        return []

def get_stream_embed_url(source):
    try:
        src_name = source.get('source')
        src_id = source.get('id')
        if not src_name or not src_id:
            return None
        api_url = f"https://streamed.pk/api/stream/{src_name}/{src_id}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        streams = response.json()
        if streams and streams[0].get('embedUrl'):
            return streams[0]['embedUrl']
    except:
        pass
    return None

def find_m3u8_in_content(page_content):
    patterns = [
        r'source:\s*["\'](https?://[^\'"]+\.m3u8?[^\'"]*)["\']',
        r'file:\s*["\'](https?://[^\'"]+\.m3u8?[^\'"]*)["\']',
        r'hlsSource\s*=\s*["\'](https?://[^\'"]+\.m3u8?[^\'"]*)["\']',
        r'src\s*:\s*["\'](https?://[^\'"]+\.m3u8?[^\'"]*)["\']',
        r'["\'](https?://[^\'"]+\.m3u8?[^\'"]*)["\']'
    ]
    for pattern in patterns:
        match = re.search(pattern, page_content)
        if match:
            return match.group(1)
    return None

def extract_m3u8_from_embed(embed_url):
    if not embed_url:
        return None
    try:
        response = requests.get(embed_url, headers=CUSTOM_HEADERS, timeout=15)
        response.raise_for_status()
        return find_m3u8_in_content(response.text)
    except:
        return None

def validate_logo(url, category):
    """Validate poster URL; fallback strictly based on category."""
    cat = (category or "").lower().replace('-', ' ').strip()
    fallback = None
    for key in FALLBACK_LOGOS:
        if key.lower() == cat:
            fallback = FALLBACK_LOGOS[key]
            break

    if url:
        try:
            resp = requests.get(url, timeout=8, headers={"User-Agent": CUSTOM_HEADERS["User-Agent"]})
            if resp.status_code == 200 and resp.content:
                return url
            else:
                print(f"⚠️ Invalid logo ({resp.status_code}): {url}")
        except requests.RequestException:
            print(f"⚠️ Failed to fetch logo: {url}")

    return fallback

def build_logo_url(match):
    """Poster-only logo logic (no badges)."""
    api_category = (match.get('category') or '').strip()
    poster = match.get('poster')
    logo_url = None

    if poster:
        if poster.startswith("http"):
            logo_url = poster
        else:
            logo_url = urljoin("https://streamed.pk", poster)

    if logo_url:
        logo_url = re.sub(r'(https://streamed\.pk)+', 'https://streamed.pk', logo_url)
        logo_url = re.sub(r'/+', '/', logo_url).replace('https:/', 'https://')

    logo_url = validate_logo(logo_url, api_category)
    return logo_url, api_category

def process_match(match):
    title = match.get('title', 'Untitled Match')
    sources = match.get('sources', [])
    for source in sources:
        embed_url = get_stream_embed_url(source)
        if embed_url:
            print(f"  🔎 Checking '{title}': {embed_url}")
            m3u8 = extract_m3u8_from_embed(embed_url)
            if m3u8:
                return match, m3u8
    return match, None

def generate_m3u8():
    all_matches = get_matches("all")
    live_matches = get_matches("live")
    matches = all_matches + live_matches

    if not matches:
        return "#EXTM3U\n#EXTINF:-1,No Matches Found\n"

    content = ["#EXTM3U"]
    success = 0

    vlc_header_lines = [
        f'#EXTVLCOPT:http-origin={CUSTOM_HEADERS["Origin"]}',
        f'#EXTVLCOPT:http-referrer={CUSTOM_HEADERS["Referer"]}',
        f'#EXTVLCOPT:user-agent={CUSTOM_HEADERS["User-Agent"]}'
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_match, m): m for m in matches}
        for future in concurrent.futures.as_completed(futures):
            match, url = future.result()
            title = match.get('title', 'Untitled Match')
            if url:
                logo, cat = build_logo_url(match)
                display_cat = cat.replace('-', ' ').title() if cat else "General"
                tv_id = TV_IDS.get(display_cat, "General.Dummy.us")

                content.append(f'#EXTINF:-1 tvg-id="{tv_id}" tvg-name="{title}" tvg-logo="{logo}" group-title="{display_cat} - Live Events",{title}')
                content.extend(vlc_header_lines)
                content.append(url)
                success += 1
                print(f"  ✅ {title} ({logo}) TV-ID: {tv_id}")

    print(f"🎉 Found {success} working streams.")
    return "\n".join(content)

if __name__ == "__main__":
    playlist = generate_m3u8()
    try:
        with open("StreamedSU.m3u8", "w", encoding="utf-8") as f:
            f.write(playlist)
        print("💾 Playlist saved successfully.")
    except IOError as e:
        print(f"⚠️ Error saving file: {e}")
        print(playlist)
