from duckduckgo_search import DDGS
import feedparser

def search_web(query, max_results=3):
    try:
        results = DDGS().text(query, max_results=max_results)
        return [{"title": r['title'], "snippet": r['body'], "link": r['href']} for r in results]
    except Exception as e:
        return [{"title": "Web Search Error", "snippet": str(e), "link": ""}]

def get_latest_arxiv(query="reinforcement learning", max_results=3):
    feed_url = f"http://export.arxiv.org/api/query?search_query=all:{query.replace(' ', '+')}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    feed = feedparser.parse(feed_url)
    papers = []
    for entry in feed.entries:
        papers.append({
            "title": entry.title,
            "summary": entry.summary[:200] + "...",
            "link": entry.link
        })
    return papers
