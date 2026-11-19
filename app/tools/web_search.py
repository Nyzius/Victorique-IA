import re
import urllib.parse
from typing import Dict, Any, List
import httpx

async def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Executes a web search via DuckDuckGo lite HTML parser.
    Mandatory requirement: Must be authorized by the user before invocation.
    """
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    results = []
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            return {
                "query": query,
                "error": f"Falha na busca web (status {resp.status_code})",
                "results": []
            }

        html = resp.text
        # Extract title and snippet patterns
        links = re.findall(r'<a class="result__url" href="([^"]+)">([^<]+)</a>', html)
        snippets = re.findall(r'<a class="result__snippet[^>]*>([\s\S]*?)</a>', html)

        for i in range(min(len(links), len(snippets), max_results)):
            link_url, display_url = links[i]
            # Strip html tags from snippet
            clean_snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
            # Duckduckgo redirect link cleanup
            if "uddg=" in link_url:
                parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(link_url).query)
                real_url = parsed_q.get("uddg", [link_url])[0]
            else:
                real_url = link_url

            results.append({
                "title": display_url.strip(),
                "url": real_url,
                "snippet": clean_snippet
            })

    return {
        "query": query,
        "total_found": len(results),
        "results": results,
        "source": "Web (DuckDuckGo)"
    }
