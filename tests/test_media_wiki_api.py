import requests
from dataclasses import dataclass, field
from typing import List, Optional

# --- Dataclass Definition ---

@dataclass
class WebSourceData:
    """
    A dataclass to hold structured data for a single Wiki page.
    
    Attributes
    ----------
    title : str
        The title of the page.
    url : str
        The URL of the page.
    pageid : int
        The unique page ID.
    last_updated : str
        The last updated timestamp of the page.
    summary : str
        A brief summary of the page.
    content_plaintext : str
        The full plaintext content of the page.
    categories : list of str
        A list of category titles the page belongs to.
    links_to : list of str
        A list of titles of pages that this page links to.
    """
    title: str
    url: str
    pageid: int
    last_updated: str
    summary: str
    content_plaintext: str
    categories: List[str] = field(default_factory=list)
    links_to: List[str] = field(default_factory=list)

# --- Private Helper Functions ---

def _get_all_article_ids(api_endpoint: str) -> List[dict] | None:
    """
    Fetches all article page IDs and titles from a MediaWiki site.
    
    This is a helper function to get the initial list of pages to process.
    """
    print(f"Starting to fetch all article IDs from: {api_endpoint}")

    all_articles = []
    
    # --- Define a User-Agent ---
    headers = {
        "User-Agent": "MyWikiScraper/1.0 (contact@example.com; https://example.com)"
    }
    
    # These are the parameters for the API request
    # We set apnamespace=0 to get *only* main articles
    params = {
        "action": "query",
        "list": "allpages",
        "aplimit": "max",      # Request the maximum allowed (usually 500)
        "apnamespace": 0,    # Namespace 0 is the main article namespace
        "apfilterredir": "nonredirects", # Filter out redirect pages
        "format": "json",
    }

    while True:
        try:
            # Make the API request
            response = requests.get(api_endpoint, params=params, headers=headers)
            response.raise_for_status()  # Raise an error for bad responses (4xx or 5xx)

            data = response.json()

            # Add the fetched pages to our list
            articles = data.get("query", {}).get("allpages", [])
            if not articles and not all_articles:
                print("No articles found in the main namespace.")
                break
                
            all_articles.extend(articles)

            print(f"Found {len(all_articles)} article IDs so far...")

            # Check if the API has more pages to send
            if "continue" in data:
                # Update the parameters with the continuation token
                params.update(data["continue"])
            else:
                # No 'continue' key means we are done
                break

        except requests.exceptions.RequestException as e:
            print(f"Error fetching article list: {e}")
            return None
        except KeyError as e:
            print(f"Error parsing article list response: {e}")
            print(f"Response data: {data}")
            return None

    print(f"Finished. Total article IDs found: {len(all_articles)}")
    return all_articles

def _fetch_batch_data(api_endpoint: str, page_ids: List[int]) -> List[WebSourceData]:
    """
    Fetches the detailed data for a specific batch of page IDs.
    
    This performs two API calls to get all data required
    by the WebSourceData dataclass.
    """
    page_ids_str = "|".join(map(str, page_ids))
    
    # This dictionary will hold all the data, keyed by pageid
    page_data_map = {pid: {} for pid in page_ids}

    # --- Define a User-Agent ---
    headers = {
        "User-Agent": "MyWikiScraper/1.0 (contact@example.com; https://example.com)"
    }

    # 1. --- First API Call: Get info, summary, categories, links ---
    # We get the summary by using exintro=True
    params1 = {
        "action": "query",
        "prop": "info|extracts|categories|links",
        "pageids": page_ids_str,
        "format": "json",
        "inprop": "url",       # Get full URL
        "exintro": True,       # Get summary (intro)
        "explaintext": True,   # Get plaintext
        "cllimit": "max",      # Get max categories (up to 500)
        "plnamespace": 0,    # Get links to other articles
        "pllimit": "max"       # Get max links (up to 500)
    }
    
    try:
        response1 = requests.get(api_endpoint, params=params1, headers=headers)
        response1.raise_for_status()
        data1 = response1.json()
        
        pages_data1 = data1.get("query", {}).get("pages", {})
        
        for page_id_str, page_data in pages_data1.items():
            page_id = int(page_id_str)
            if page_id not in page_data_map:
                continue

            page_data_map[page_id]['title'] = page_data.get('title', 'N/A')
            page_data_map[page_id]['url'] = page_data.get('fullurl', '')
            page_data_map[page_id]['pageid'] = page_id
            page_data_map[page_id]['last_updated'] = page_data.get('touched', '')
            page_data_map[page_id]['summary'] = page_data.get('extract', '')
            page_data_map[page_id]['categories'] = [
                c.get('title', '') for c in page_data.get('categories', [])
            ]
            page_data_map[page_id]['links_to'] = [
                l.get('title', '') for l in page_data.get('links', [])
            ]

    except requests.exceptions.RequestException as e:
        print(f"Error in API call 1 (metadata): {e}")
        # Continue to next call, some data might be missing
    except KeyError as e:
        print(f"Error parsing API call 1 response: {e}")

    # 2. --- Second API Call: Get full plaintext content ---
    # We get full content by *not* setting exintro
    params2 = {
        "action": "query",
        "prop": "extracts",
        "pageids": page_ids_str,
        "format": "json",
        "explaintext": True,   # Get plaintext
        # No 'exintro' means get full page
    }

    # 2. --- Second API Call: Get full plaintext content ---
        # No 'exintro' means get full page

    try:
        response2 = requests.get(api_endpoint, params=params2, headers=headers)
        response2.raise_for_status()
        data2 = response2.json()
        
        pages_data2 = data2.get("query", {}).get("pages", {})
        
        for page_id_str, page_data in pages_data2.items():
            page_id = int(page_id_str)
            if page_id in page_data_map:
                if 'extract' in page_data:
                    page_data_map[page_id]['content_plaintext'] = page_data.get('extract', '')
                else:
                    print(f"Warning: No 'extract' found for page ID {page_id} in content fetch.")

    except requests.exceptions.RequestException as e:
        print(f"Error in API call 2 (content): {e}")
    except KeyError as e:
        print(f"Error parsing API call 2 response: {e}")
        
    # 3. --- Construct Dataclass Objects ---
    batch_results = []
    for page_id, data in page_data_map.items():
        if not data.get('title'): # Skip if call 1 failed and we have no data
            continue
            
        try:
            web_data = WebSourceData(
                title=data.get('title', 'N/A'),
                url=data.get('url', ''),
                pageid=page_id,
                last_updated=data.get('last_updated', ''),
                summary=data.get('summary', ''),
                content_plaintext=data.get('content_plaintext', 'N/A: Could not fetch content'),
                categories=data.get('categories', []),
                links_to=data.get('links_to', [])
            )
            batch_results.append(web_data)
        except Exception as e:
            print(f"Error creating dataclass for page {page_id}: {e}")

    return batch_results

# --- Public Function ---

def get_all_wiki_articles(base_url: str, limit: Optional[int] = None) -> List[WebSourceData]:
    """
    Fetches all article pages from a MediaWiki site (like Fandom)
    and returns a list of WebSourceData objects.

    This is a data-intensive operation and may take a very
    long time for large wikis.

    Args:
        base_url: The base domain of the wiki (e.g., "senkosan.fandom.com"
                  or "en.wikipedia.org").
        limit: An optional maximum number of articles to fetch.
               Useful for testing.

    Returns:
        A list of WebSourceData objects.
        Returns an empty list if an error occurs.
    """
    # Clean up the base URL to ensure it's just the domain
    clean_url = base_url.replace("https://", "").replace("http://", "").strip("/")
    api_endpoint = f"https://{clean_url}/api.php"
    
    # 1. Get all article IDs
    article_ids = _get_all_article_ids(api_endpoint)
    if not article_ids:
        return []

    # 2. Apply limit if provided
    if limit is not None:
        print(f"Limiting fetch to {limit} articles.")
        article_ids = article_ids[:limit]
    else:
        print(f"WARNING: About to fetch full data for {len(article_ids)} articles.")
        print("This may take a very long time and consume a lot of data.")

    # 3. Batch process articles
    all_article_data: List[WebSourceData] = []
    # MediaWiki API limit for 'pageids' is 50
    BATCH_SIZE = 50 
    
    for i in range(0, len(article_ids), BATCH_SIZE):
        batch_ids = [article['pageid'] for article in article_ids[i:i+BATCH_SIZE]]
        
        print(f"Fetching full data for batch {i//BATCH_SIZE + 1}/{(len(article_ids) + BATCH_SIZE - 1)//BATCH_SIZE}...")
        
        batch_data = _fetch_batch_data(api_endpoint, batch_ids)
        all_article_data.extend(batch_data)

    print(f"Finished. Total articles processed: {len(all_article_data)}")
    return all_article_data

if __name__ == "__main__":
    # --- Example Usage ---
    # Using a smaller wiki for testing is highly recommended.
    wiki_url = "osrs.wiki"
    # wiki_url = "en.wikipedia.org" # DANGER: This will try to fetch > 6 million pages.
    
    # Use a limit for testing
    TEST_LIMIT = 10
    
    print(f"Querying: {wiki_url} (limit={TEST_LIMIT})")
    
    articles_data = get_all_wiki_articles(wiki_url, limit=TEST_LIMIT)

    if articles_data:
        print(f"\nSuccessfully retrieved data for {len(articles_data)} articles.")
        
        # Print details for the first article
        print("\n--- Data for First Article ---")
        
        # Pretty print the dataclass
        import json
        
        if articles_data:
            first_article = articles_data[1]
            
            # Create a dict, but truncate long content for printing
            article_dict = {
                "title": first_article.title,
                "url": first_article.url,
                "pageid": first_article.pageid,
                "last_updated": first_article.last_updated,
                "summary_snippet": first_article.summary[:150] + "...",
                "content_snippet": first_article.content_plaintext[:150] + "...",
                "categories": first_article.categories,
                "links_to (first 5)": first_article.links_to[:5]
            }
            
            print(json.dumps(article_dict, indent=2))

    else:
        print("Could not retrieve articles.")