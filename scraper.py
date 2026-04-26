import json
import urllib.request
import urllib.parse
import re
import sys
import os
import ssl

# Add lib folder to sys.path for bs4
lib_path = os.path.join(os.path.dirname(__file__), 'lib')
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

from bs4 import BeautifulSoup


def _create_ssl_context():
    """Create an SSL context with certificate verification enabled."""
    ctx = ssl.create_default_context()
    return ctx


class TamilDholScraper:
    BASE_URL = "https://tamildhol.se/"
    MAX_RETRIES = 2

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def _get_soup(self, url):
        ctx = _create_ssl_context()
        req = urllib.request.Request(url, headers=self.headers)
        for attempt in range(self.MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                    html = response.read().decode('utf-8')
                    return BeautifulSoup(html, 'html.parser')
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    continue
                raise

    def _get_json(self, url):
        """Fetch JSON from WP REST API. Returns (data, response_headers)."""
        ctx = _create_ssl_context()
        req = urllib.request.Request(url, headers=self.headers)
        for attempt in range(self.MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    # Normalize headers to lowercase for consistent access
                    headers = {k.lower(): v for k, v in response.headers.items()}
                    return data, headers
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    continue
                raise

    def _parse_post_items(self, soup):
        """Extract video items from a parsed HTML document."""
        items = []
        for post in soup.find_all('li', class_='post-item'):
            title_tag = post.find('h2', class_='post-title')
            if title_tag and title_tag.find('a'):
                link = title_tag.find('a')
                href = link['href']
                # Normalize relative URLs to absolute
                if href.startswith('//'):
                    href = 'https:' + href
                elif not href.startswith('http'):
                    href = self.BASE_URL.rstrip('/') + '/' + href.lstrip('/')
                items.append({
                    'title': link.text.strip(),
                    'url': href
                })
        return items

    def get_home_items(self, page=1):
        """Fetch home page items using WP REST API for reliable pagination."""
        try:
            api_url = f"{self.BASE_URL}wp-json/wp/v2/posts?per_page=21&page={page}"
            data, headers = self._get_json(api_url)
            total_pages = int(headers.get('x-wp-totalpages', '1'))
            items = []
            for post in data:
                title = post.get('title', {}).get('rendered', '').strip()
                link = post.get('link', '')
                if title and link:
                    items.append({'title': title, 'url': link})
            return {'items': items, 'has_next': page < total_pages}
        except Exception as e:
            print(f"[TamilDhol] Error fetching home items: {e}")
            return {'items': [], 'has_next': False}

    def search_items(self, query, page=1):
        """Fetch search results. Uses /page/N/?s=query for pagination."""
        try:
            encoded_query = urllib.parse.quote(query)
            if page > 1:
                search_url = f"{self.BASE_URL}page/{page}/?s={encoded_query}"
            else:
                search_url = f"{self.BASE_URL}?s={encoded_query}"
            soup = self._get_soup(search_url)
            items = self._parse_post_items(soup)
            # If we got a full page of results, there's likely a next page
            has_next = len(items) >= 10
            return {'items': items, 'has_next': has_next}
        except Exception as e:
            print(f"[TamilDhol] Error searching items: {e}")
            return {'items': [], 'has_next': False}

    def get_stream_url(self, page_url):
        try:
            # 1. Get the embed iframe URL
            soup = self._get_soup(page_url)

            # Try multiple iframe detection strategies (skip about:blank)
            embed_url = None
            for attr in ['src', 'data-src', 'data-litespeed-src']:
                iframe = soup.find('iframe', {attr: True})
                if iframe and iframe.get(attr):
                    val = iframe[attr]
                    if val and val != 'about:blank':
                        embed_url = val
                        break
            if not embed_url:
                return None

            # Normalize embed URL as well
            if embed_url.startswith('//'):
                embed_url = 'https:' + embed_url
            elif not embed_url.startswith('http'):
                embed_url = urllib.parse.urljoin(page_url, embed_url)

            print("[TamilDhol] iframe src: " + embed_url)

            # 2. Get the content of the embed page with Referer header
            ctx = _create_ssl_context()
            req = urllib.request.Request(embed_url, headers=self.headers)
            req.add_header('Referer', page_url)
            for attempt in range(self.MAX_RETRIES):
                try:
                    with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                        html = response.read().decode('utf-8')
                    break
                except Exception:
                    if attempt < self.MAX_RETRIES - 1:
                        continue
                    return None

            # Try multiple patterns in order of priority
            decoded_html = self._decode_packed_js(html) if 'eval(function(p,a,c,k,e,d)' in html else html
            stream_url = self._extract_stream_from_html(decoded_html)

            if stream_url:
                print("[TamilDhol] Found stream URL: " + stream_url)
                return {'url': stream_url, 'referer': embed_url, 'user_agent': self.headers['User-Agent']}
        except Exception as e:
            print("[TamilDhol] Error getting stream URL: " + str(e))
        return None

    def _decode_packed_js(self, html):
        """Decode Dean Edwards packed JavaScript to extract real URLs."""
        m = re.search(r"eval\(function\(p,a,c,k,e,d\)\{(.+?)\}\('(.+?)'\.split", html)
        if not m:
            return html

        func_body = m.group(1)
        packed = m.group(2)
        items = packed.split('|')

        # Replace |N| patterns with actual values
        decoded = packed
        for i, item in enumerate(items):
            if item:
                pattern = r'\|' + str(i) + r'\|'
                decoded = re.sub(pattern, '|' + item + '|', decoded)

        # Decode base-36 encoded identifiers (like 4e, 1t, etc.)
        def decode_identifier(match):
            identifier = match.group(0)
            try:
                decimal_value = int(identifier, 36)
                if 0 <= decimal_value < len(items) and items[decimal_value]:
                    return items[decimal_value]
            except ValueError:
                pass
            return identifier

        decoded = re.sub(r'\b[a-zA-Z0-9]+\b', decode_identifier, decoded)
        return decoded

    def _extract_stream_from_html(self, html):
        """Try multiple patterns to extract a playable stream URL from embed page."""
        # Pattern 1: JWPlayer sources array - sources:[{file:"http://...",label:"360p"}]
        sources_pattern = r'sources\s*:\s*\[(.*?)\]'
        match = re.search(sources_pattern, html)
        if match:
            sources_block = match.group(1)
            # Extract all file URLs from the sources block
            file_urls = re.findall(r'file["\']?\s*:\s*["\'](https?://[^"\']+?)["\']', sources_block)
            if file_urls:
                print("[TamilDhol] Found JWPlayer sources with " + str(len(file_urls)) + " URLs")
                # Return the first (highest quality) URL
                return self._normalize_stream(file_urls[0])

        # Pattern 2: Standard JWPlayer config - "file":"http://..." (no space required)
        pattern2 = r'["\'](?:file|source)["\']\s*:\s*["\'](https?://[^"\']+?)["\']'
        match = re.search(pattern2, html)
        if match:
            return self._normalize_stream(match.group(1))

        # Pattern 3: Variable assignment - var file = "http://..." or var source = '...'
        pattern3 = r'var\s+\w*\b(?:file|source)\b\w*=\s*["\'](https?://[^"\']+?)["\']'
        match = re.search(pattern3, html)
        if match:
            return self._normalize_stream(match.group(1))

        # Pattern 4: HTML source tag - <source src="http://...">
        pattern4 = r'<source\s+src=["\'](https?://[^"\']+?)["\']'
        match = re.search(pattern4, html)
        if match:
            return self._normalize_stream(match.group(1))

        # Pattern 5: data-file or data-src attributes in any tag
        pattern5 = r'(?:data-file|data-src)=["\'](https?://[^"\']+?)["\']'
        match = re.search(pattern5, html)
        if match:
            return self._normalize_stream(match.group(1))

        # Pattern 6: Look for .m3u8 or .mp4 URLs directly in the HTML
        pattern6 = r'(https?://[^"\'>\s]+\.(?:m3u8|mp4)[^"\'>\s]*)'
        match = re.search(pattern6, html)
        if match:
            return self._normalize_stream(match.group(1))

        # Pattern 7: Base64 encoded config - decode and search inside
        b64_pattern = r'data-config=["\']([A-Za-z0-9+/=]{20,})["\']'
        match = re.search(b64_pattern, html)
        if match:
            try:
                import base64
                decoded = base64.b64decode(match.group(1)).decode('utf-8', errors='ignore')
                stream_url = self._extract_stream_from_html(decoded)
                if stream_url:
                    return stream_url
            except Exception:
                pass

        # Pattern 8: Look for any http URL that looks like a media file
        pattern8 = r'(https?://[^"\'>\s]+\.(?:m3u8|mp4|ts|m3u8\.js)[^"\'>\s]*)'
        match = re.search(pattern8, html)
        if match:
            return self._normalize_stream(match.group(1))

        print("[TamilDhol] No stream URL found in embed page")
        return None

    def _normalize_stream(self, url):
        """Normalize stream URL for Kodi playback."""
        # Add hls:// prefix for HLS streams
        if '.m3u8' in url:
            return 'hls://' + url
        return url
