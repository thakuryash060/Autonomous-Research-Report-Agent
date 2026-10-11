import json
import math
import os
import re
import time
import urllib.request
import urllib.error
import urllib.parse

from .sources import normalize_url


OPENALEX_API_BASE = "https://api.openalex.org/works"
OPENALEX_PER_PAGE = 25
OPENALEX_MAX_PAGES = 3
OPENALEX_DELAY_SECONDS = 0.5

_PROVIDER_EVENT_HOOK = None


def set_provider_event_hook(hook):
    """Register an event hook callback for provider status alerts: hook(provider_name, issue, fallback)."""
    global _PROVIDER_EVENT_HOOK
    _PROVIDER_EVENT_HOOK = hook


def _emit_provider_event(provider_name: str, issue: str, fallback: str = ""):
    if _PROVIDER_EVENT_HOOK:
        try:
            _PROVIDER_EVENT_HOOK(provider_name, issue, fallback)
        except Exception:
            pass


class SourceProvider:
    """Base class for academic source providers."""

    name = "base"

    def search(self, query_text, question_id=None, **kwargs):
        """Return a list of source dicts compatible with the Phase 2 source schema."""
        raise NotImplementedError


def _sanitize_openalex_query(query_text: str, max_terms: int = 12) -> str:
    """
    Sanitize search query for OpenAlex to prevent Elasticsearch syntax errors (HTTP 400).
    Strips parenthetical examples, punctuation, and reserved Elasticsearch query characters,
    and bounds query length to substantive keywords.
    """
    if not query_text:
        return ""
    q = re.sub(r"\(.*?\)", " ", str(query_text))
    q = re.sub(r"[^\w\s-]", " ", q)
    q = re.sub(r"[\s_-]+", " ", q).strip()
    words = [w for w in q.split() if len(w) > 1]
    if len(words) > max_terms:
        words = words[:max_terms]
    return " ".join(words)


class OpenAlexProvider(SourceProvider):
    name = "openalex"

    def __init__(self, mailto=None, per_page=None, max_pages=None, delay=None):
        self.mailto = mailto
        self.per_page = per_page or OPENALEX_PER_PAGE
        self.max_pages = max_pages or OPENALEX_MAX_PAGES
        self.delay = delay if delay is not None else OPENALEX_DELAY_SECONDS

    def search(self, query_text, question_id=None, **kwargs):
        if not query_text or not str(query_text).strip():
            return []

        query_text = str(query_text).strip()
        question_id = str(question_id or "").strip().upper()
        all_results = []

        for page in range(1, self.max_pages + 1):
            page_results = self._fetch_page(
                query_text,
                page,
                question_id=question_id,
            )
            all_results.extend(page_results)
            if not page_results or len(page_results) < self.per_page:
                break
            if page < self.max_pages:
                time.sleep(self.delay)

        return all_results

    def _fetch_page(self, query_text, page, question_id=None):
        clean_query = _sanitize_openalex_query(query_text)
        if not clean_query:
            return []

        params = {
            "search": clean_query,
            "per-page": self.per_page,
            "page": page,
        }
        url = f"{OPENALEX_API_BASE}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(url, method="GET")
        req.add_header(
            "User-Agent",
            "research-agent/1.0 (https://github.com/your-repo)"
        )
        if self.mailto:
            req.add_header("mailto", self.mailto)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status != 200:
                    print(
                        f"  [Warning] OpenAlex returned HTTP {resp.status}"
                    )
                    return []
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
        except urllib.error.HTTPError as exc:
            print(
                f"  [Warning] OpenAlex HTTP error {exc.code}: "
                f"{exc.reason}"
            )
            issue = "rate limited" if exc.code == 429 else f"HTTP error {exc.code}"
            _emit_provider_event("OpenAlex", issue, "Continuing with Semantic Scholar")
            return []
        except urllib.error.URLError as exc:
            print(f"  [Warning] OpenAlex request failed: {exc.reason}")
            _emit_provider_event("OpenAlex", "connection failed", "Continuing with Semantic Scholar")
            return []
        except (TimeoutError, OSError) as exc:
            print(f"  [Warning] OpenAlex network error: {exc}")
            _emit_provider_event("OpenAlex", "network timeout", "Continuing with Semantic Scholar")
            return []
        except (json.JSONDecodeError, UnicodeDecodeError):
            print("  [Warning] OpenAlex returned malformed response")
            return []
        except Exception as exc:
            print(f"  [Warning] OpenAlex unexpected error: {exc}")
            return []

        raw_results = data.get("results")
        if not isinstance(raw_results, list):
            return []

        sources = []
        for item in raw_results:
            source = self._convert(item, query_text, question_id)
            if source is not None:
                sources.append(source)

        return sources

    def _convert(self, item, query_text, question_id):
        openalex_id = item.get("id", "")
        stable_id = openalex_id
        if stable_id and "/" in stable_id:
            stable_id = stable_id.rstrip("/").split("/")[-1]

        if not stable_id:
            return None

        source_id = f"OA-{stable_id}"

        title = str(item.get("title", "") or "").strip()
        if not title:
            return None

        abstract = _reconstruct_abstract(
            item.get("abstract_inverted_index")
        )

        content = abstract if abstract else ""

        url = _best_url(item)

        authorships = item.get("authorships", []) or []
        authors = []
        for authorship in authorships:
            author = authorship.get("author", {}) or {}
            name = str(author.get("display_name", "") or "").strip()
            if name and name not in authors:
                authors.append(name)

        oa_info = item.get("open_access", {}) or {}
        oa_url = oa_info.get("oa_url") or oa_info.get("url")
        is_oa = oa_info.get("is_oa")

        cited_by = item.get("cited_by_count")
        citation_count = int(cited_by) if cited_by is not None else None

        doi = item.get("doi")
        if doi and not str(doi).startswith("https://"):
            doi = f"https://doi.org/{doi}"

        venue_info = item.get("host_venue", {}) or {}
        venue_name = str(venue_info.get("display_name", "") or "").strip()

        pub_year = item.get("publication_year")
        publication_year = int(pub_year) if pub_year is not None else None

        score = None
        if citation_count is not None:
            score = round(min(0.95, max(0.50, 0.50 + 0.15 * math.log10(citation_count + 1))), 4)

        return {
            "source_id": source_id,
            "question_id": question_id,
            "query_text": query_text,
            "query_type": "normal",
            "title": title,
            "url": url,
            "normalized_url": normalize_url(url),
            "content": content,
            "score": score,
            "discovered_by": [
                {
                    "question_id": question_id,
                    "query_text": query_text,
                    "query_type": "normal",
                }
            ],
            "duplicate_count": 0,
            "alternate_urls": [],
            "authors": authors,
            "publication_year": publication_year,
            "doi": doi,
            "venue": venue_name,
            "citation_count": citation_count,
            "abstract": abstract,
            "open_access_url": oa_url,
            "is_open_access": (
                bool(is_oa) if is_oa is not None else None
            ),
            "provider_name": self.name,
            "provider_query": query_text,
        }


def _reconstruct_abstract(inverted_index):
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    positions = []
    for word, pos_list in inverted_index.items():
        if not isinstance(pos_list, list):
            continue
        for pos in pos_list:
            try:
                positions.append((int(pos), str(word)))
            except (TypeError, ValueError):
                continue
    positions.sort()
    return " ".join(word for _, word in positions)


def _best_url(item):
    doi = item.get("doi")
    if doi:
        doi = str(doi).strip()
        if not doi.startswith("https://"):
            doi = f"https://doi.org/{doi}"
        return doi

    primary = item.get("primary_location", {}) or {}
    landing = primary.get("landing_page_url")
    if landing:
        return str(landing).strip()

    oa = item.get("open_access", {}) or {}
    oa_url = oa.get("oa_url") or oa.get("url")
    if oa_url:
        return str(oa_url).strip()

    openalex_id = item.get("id", "")
    if openalex_id:
        return str(openalex_id).strip()

    return ""



class SemanticScholarProvider(SourceProvider):
    """
    Dual-Mode Semantic Scholar Provider:
    - Mode A (Authenticated): Uses Semantic Scholar Graph API if SEMANTIC_SCHOLAR_API_KEY is available.
    - Mode B (Autonomous Web Discovery): Uses Tavily site:semanticscholar.org discovery if no API key is set.
      This eliminates HTTP 429 errors while discovering genuine Semantic Scholar papers.
    """
    name = "semanticscholar"

    def __init__(self, api_key=None, tavily_client=None, limit=10):
        self.api_key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self.tavily_client = tavily_client
        self.limit = limit

    def search(self, query_text, question_id=None, **kwargs):
        if not query_text or not str(query_text).strip():
            return []

        query_text = str(query_text).strip()
        question_id = str(question_id or "").strip().upper()

        if self.api_key:
            results = self._search_graph_api(query_text, question_id)
            if results:
                return results
            # Graceful fallback to web discovery if graph API is empty or blocked
            return self._search_via_web_discovery(query_text, question_id)
        else:
            return self._search_via_web_discovery(query_text, question_id)

    def _search_via_web_discovery(self, query_text, question_id):
        client = self.tavily_client
        if client is None:
            tavily_key = os.getenv("TAVILY_API_KEY")
            if tavily_key:
                try:
                    from tavily import TavilyClient
                    client = TavilyClient(api_key=tavily_key)
                    self.tavily_client = client
                except Exception:
                    return []
            else:
                return []

        target_query = f"site:semanticscholar.org/paper {query_text}"
        try:
            res = client.search(target_query, max_results=self.limit)
        except Exception as exc:
            print(f"  [Warning] Semantic Scholar web discovery search failed: {exc}")
            return []

        raw_results = res.get("results", []) if isinstance(res, dict) else []
        sources = []

        for item in raw_results:
            url = str(item.get("url", "") or "").strip()
            if "semanticscholar.org/paper" not in url:
                continue

            # Strip figure / table sub-pages from Semantic Scholar URLs so they point to the canonical paper
            url = re.sub(r"/(?:figure|table)/\d+/?$", "", url)

            raw_title = str(item.get("title", "") or "").strip()
            title = (
                raw_title.replace(" | Semantic Scholar", "")
                .replace("[PDF]", "")
                .strip()
            )
            # Clean "Figure X from " and "Table X from " prefixes from titles
            title = re.sub(r"^(?:Figure|Table)\s+\d+\s+from\s+", "", title, flags=re.I).strip()
            if not title:
                continue

            parts = url.rstrip("/").split("/")
            paper_hash = parts[-1] if parts else ""
            source_id = f"S2-{paper_hash[:16]}" if paper_hash else f"S2-{abs(hash(url)) % 10000000}"

            snippet = str(item.get("content", "") or "").strip()
            score = item.get("score")
            if score is not None:
                try:
                    score = round(float(score), 4)
                except (ValueError, TypeError):
                    score = None

            source = {
                "source_id": source_id,
                "question_id": question_id,
                "query_text": query_text,
                "query_type": "normal",
                "title": title,
                "url": url,
                "normalized_url": normalize_url(url),
                "content": snippet,
                "score": score,
                "discovered_by": [
                    {
                        "question_id": question_id,
                        "query_text": query_text,
                        "query_type": "normal",
                    }
                ],
                "duplicate_count": 0,
                "alternate_urls": [],
                "authors": [],
                "publication_year": None,
                "doi": None,
                "venue": "Semantic Scholar",
                "citation_count": None,
                "abstract": snippet,
                "open_access_url": None,
                "is_open_access": None,
                "provider_name": self.name,
                "provider_query": query_text,
            }
            sources.append(source)

        return sources

    def _search_graph_api(self, query_text, question_id):
        params = {
            "query": query_text,
            "limit": self.limit,
            "fields": (
                "paperId,title,abstract,venue,year,authors,citationCount,"
                "isOpenAccess,openAccessPdf,externalIds,url"
            ),
        }
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "research-agent/1.0")
        if self.api_key:
            req.add_header("x-api-key", self.api_key)

        data = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status != 200:
                        return []
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt == 0:
                    time.sleep(1.5)
                    continue
                print(f"  [Warning] Semantic Scholar API HTTP {exc.code}: {exc.reason}")
                issue = "rate limited" if exc.code == 429 else f"HTTP error {exc.code}"
                _emit_provider_event("Semantic Scholar", issue, "Continuing with Tavily web discovery")
                return []
            except Exception as exc:
                print(f"  [Warning] Semantic Scholar API error: {exc}")
                return []

        if not data:
            return []

        raw_items = data.get("data", []) if isinstance(data, dict) else []
        sources = []
        for item in raw_items:
            paper_id = item.get("paperId", "")
            if not paper_id:
                continue
            title = str(item.get("title", "") or "").strip()
            if not title:
                continue

            authors = [
                str(a.get("name", "")).strip()
                for a in item.get("authors", []) or []
                if a.get("name")
            ]
            abstract = str(item.get("abstract", "") or "").strip()
            ext_ids = item.get("externalIds") or {}
            doi = ext_ids.get("DOI")
            paper_url = item.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"

            source = {
                "source_id": f"S2-{paper_id[:16]}",
                "question_id": question_id,
                "query_text": query_text,
                "query_type": "normal",
                "title": title,
                "url": paper_url,
                "normalized_url": normalize_url(paper_url),
                "content": abstract,
                "score": 0.85,
                "discovered_by": [
                    {
                        "question_id": question_id,
                        "query_text": query_text,
                        "query_type": "normal",
                    }
                ],
                "duplicate_count": 0,
                "alternate_urls": [],
                "authors": authors,
                "publication_year": item.get("year"),
                "doi": f"https://doi.org/{doi}" if doi and not str(doi).startswith("http") else doi,
                "venue": str(item.get("venue", "") or "").strip(),
                "citation_count": item.get("citationCount"),
                "abstract": abstract,
                "open_access_url": (item.get("openAccessPdf") or {}).get("url"),
                "is_open_access": item.get("isOpenAccess"),
                "provider_name": self.name,
                "provider_query": query_text,
            }
            sources.append(source)

        return sources


_providers = {}


def register_provider(name, provider):
    if not isinstance(provider, SourceProvider):
        raise TypeError("Provider must be a SourceProvider instance")
    _providers[name] = provider


def get_provider(name):
    return _providers.get(name)


def search_academic(provider_name, query_text, question_id=None, **kwargs):
    provider = get_provider(provider_name)
    if provider is None:
        raise ValueError(
            f"Unknown source provider: {provider_name}"
        )
    return provider.search(query_text, question_id=question_id, **kwargs)


register_provider("openalex", OpenAlexProvider())
register_provider("semanticscholar", SemanticScholarProvider())


class ProviderCircuitBreaker:
    """Tracks provider health, failure counts, and circuit open/closed states."""
    def __init__(self, failure_threshold: int = 3, reset_timeout_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.failure_counts: dict = {}
        self.circuit_open_until: dict = {}

    def record_success(self, provider_name: str):
        self.failure_counts[provider_name] = 0
        self.circuit_open_until.pop(provider_name, None)

    def record_failure(self, provider_name: str):
        count = self.failure_counts.get(provider_name, 0) + 1
        self.failure_counts[provider_name] = count
        if count >= self.failure_threshold:
            self.circuit_open_until[provider_name] = time.time() + self.reset_timeout_seconds

    def is_available(self, provider_name: str) -> bool:
        if provider_name not in self.circuit_open_until:
            return True
        if time.time() > self.circuit_open_until[provider_name]:
            # Half-open: attempt recovery
            self.circuit_open_until.pop(provider_name, None)
            self.failure_counts[provider_name] = 0
            return True
        return False


_CIRCUIT_BREAKER = ProviderCircuitBreaker()


def execute_providers_independently(
    provider_names,
    query_text: str,
    question_id: str = None,
    timeout_per_provider: float = 12.0,
    **kwargs
) -> dict:
    """
    Execute multiple academic providers independently in parallel.
    Guarantees fault isolation: failures or timeouts in one provider do not block
    or corrupt execution of other providers.
    """
    import concurrent.futures

    results_by_provider = {}
    provider_errors = {}
    combined_sources = []

    def _run_single(p_name):
        if not _CIRCUIT_BREAKER.is_available(p_name):
            return p_name, [], f"Circuit breaker open (consecutive failures)"

        prov = get_provider(p_name)
        if prov is None:
            return p_name, [], f"Provider '{p_name}' not registered"

        try:
            items = prov.search(query_text, question_id=question_id, **kwargs)
            _CIRCUIT_BREAKER.record_success(p_name)
            return p_name, items, None
        except Exception as exc:
            _CIRCUIT_BREAKER.record_failure(p_name)
            return p_name, [], str(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(provider_names) or 1) as executor:
        futures = {executor.submit(_run_single, name): name for name in provider_names}
        for future in concurrent.futures.as_completed(futures):
            p_name = futures[future]
            try:
                name, items, err = future.result(timeout=timeout_per_provider + 1.0)
                if err:
                    provider_errors[name] = err
                    results_by_provider[name] = []
                else:
                    results_by_provider[name] = items
                    combined_sources.extend(items)
            except Exception as exc:
                provider_errors[p_name] = f"Timeout or fatal error: {exc}"
                results_by_provider[p_name] = []
                _CIRCUIT_BREAKER.record_failure(p_name)

    return {
        "sources": combined_sources,
        "results_by_provider": results_by_provider,
        "errors": provider_errors,
        "success_providers": [p for p, res in results_by_provider.items() if res],
    }



if __name__ == "__main__":
    provider = OpenAlexProvider()
    print("Testing OpenAlex provider...")
    results = provider.search(
        "transformer architecture attention mechanism",
        question_id="TEST",
    )
    print(f"Found {len(results)} results")
    for r in results[:3]:
        print(f"  {r['source_id']}: {r['title']}")
        print(f"    URL: {r['url']}")
        print(f"    Authors: {r.get('authors', [])}")
        print(f"    Year: {r.get('publication_year')}")
        print(f"    Citations: {r.get('citation_count')}")
        print(f"    OA: {r.get('is_open_access')}")
        print(f"    DOI: {r.get('doi')}")
        print(f"    Provider: {r.get('provider_name')}")
        preview = r.get("abstract") or ""
        print(f"    Abstract preview: {preview[:120]}...")
