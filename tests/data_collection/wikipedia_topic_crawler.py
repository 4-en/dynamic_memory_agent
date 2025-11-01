import wikipediaapi
import time
import json
import sys
import os  # Added for file/directory operations

# --- Configuration ---

# 1. SET YOUR ROOT CATEGORIES HERE
ROOT_CATEGORIES = [
    "Solar System"
]

# 2. SET YOUR CRAWL DEPTH
# How deep to crawl into subcategories. 
# 0 = only pages in the root categories.
# 1 = root + their immediate subcategories.
# 2 = root + subcategories + sub-subcategories.
# WARNING: A high number (e.g., 5+) for a broad topic 
# like "Artificial intelligence" can result in TENS of THOUSANDS 
# of pages and take many hours. Start with 2 or 3.
MAX_RECURSION_DEPTH = 2

# 4. SET CACHE DIRECTORY
# This folder will store the JSON output for each page.
CACHE_DIRECTORY = "wiki_cache"

# 3. BE POLITE: Set a User-Agent and Rate Limit
# Wikipedia requires a unique User-Agent for API requests.
# Please replace with your own info.
USER_AGENT = 'MyTopicCrawler/1.0 (merlin@example.com; https://my-project-url.com)'
LANGUAGE = 'en'

# Delay in seconds between *every* API request. 0.5 is a safe, polite value.
RATE_LIMIT_DELAY = 0.5

# --- End of Configuration ---


def crawl_category(
    category_page, 
    all_page_titles, 
    visited_categories, 
    current_depth=0
):
    """
    Recursively crawls a category to find all member pages and subcategories.
    
    :param category_page: The wikipediaapi.WikipediaPage object for the category.
    :param all_page_titles: A set to store the titles of found pages (passed by ref).
    :param visited_categories: A set to prevent infinite loops (passed by ref).
    :param current_depth: The current recursion depth.
    """
    
    # Stop if we're too deep
    if current_depth > MAX_RECURSION_DEPTH:
        return
        
    # Stop if we've already processed this category
    if category_page.title in visited_categories:
        return
        
    # Mark this category as visited
    visited_categories.add(category_page.title)
    indent = "  " * current_depth
    print(f"{indent}[CAT] Crawling: {category_page.title}", file=sys.stderr)

    # Get all members of this category
    try:
        # This is the main API call to get members
        members = category_page.categorymembers
        
        for member in members.values():
            # Add a polite delay for every member we check
            time.sleep(RATE_LIMIT_DELAY)
            
            if member.ns == wikipediaapi.Namespace.MAIN:
                # This is an article (ns=0)
                if member.title not in all_page_titles:
                    print(f"{indent}  -> Found Page: {member.title}", file=sys.stderr)
                    all_page_titles.add(member.title)
                    
            elif member.ns == wikipediaapi.Namespace.CATEGORY:
                # This is a subcategory (ns=14)
                # Recurse!
                crawl_category(
                    member, 
                    all_page_titles, 
                    visited_categories, 
                    current_depth + 1
                )
                
    except Exception as e:
        print(f"{indent}  [!] Error crawling {category_page.title}: {e}", file=sys.stderr)


def process_and_cache_pages(wiki_api, page_titles):
    """
    Takes a list of page titles, checks if they are cached,
    and if not, fetches their data and saves it to a JSON file.
    
    :param wiki_api: The initialized wikipediaapi.Wikipedia object.
    :param page_titles: A list or set of page titles to fetch.
    """
    
    total = len(page_titles)
    
    for i, title in enumerate(sorted(list(page_titles))):
        print(f"\n[PAGE] Processing {i+1}/{total}: {title}", file=sys.stderr)
        
        try:
            # This first call is lightweight and gets pageid
            time.sleep(RATE_LIMIT_DELAY)
            page = wiki_api.page(title)
            
            # This check is sufficient. The library handles redirects
            # automatically, so we just need to see if the final page exists.
            if not page.exists():
                print(f"[SKIP] '{title}' does not exist or is a redirect.", file=sys.stderr)
                continue

            # --- Cache Check ---
            # Use pageid for a unique, safe filename
            page_id = page.pageid
            cache_filename = f"{page_id}.json"
            cache_path = os.path.join(CACHE_DIRECTORY, cache_filename)

            if os.path.exists(cache_path):
                print(f"[CACHE] Skipping '{title}' ({page_id}), file already exists.", file=sys.stderr)
                continue
            # --- End Cache Check ---

            print(f"[FETCH] Caching '{title}' ({page_id})...", file=sys.stderr)

            # These calls are expensive and will only run if not cached
            # 1. Get plain text content
            content = page.text
            if not content:
                print(f"[SKIP] '{title}' has no text content.", file=sys.stderr)
                continue

            # 2. Get Title and URL
            page_title = page.title
            page_url = page.fullurl
            
            # 3. Get Pages it links to
            links_to = list(page.links.keys())
            
            # 4. Get Other Metadata
            summary = page.summary
            last_updated = page.touched
            page_categories = [cat for cat in page.categories.keys()]
            
            # Assemble the data
            page_data = {
                "title": page_title,
                "url": page_url,
                "pageid": page_id,
                "last_updated": last_updated,
                "summary": summary,
                "categories": page_categories,
                "links_to": links_to,
                "content_plaintext": content
            }
            
            # Save the data to its own file
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(page_data, f, indent=2, ensure_ascii=False)
            
            print(f"[SUCCESS] Fetched and cached data for '{title}'", file=sys.stderr)

        except Exception as e:
            print(f"[ERROR] Could not process '{title}': {e}", file=sys.stderr)
            

def main():
    """
    Main function to orchestrate the crawl and data fetching.
    """
    
    print("Initializing Wikipedia API...", file=sys.stderr)
    wiki_api = wikipediaapi.Wikipedia(
        user_agent=USER_AGENT, 
        language=LANGUAGE
        # This extract_format ensures .text returns clean plain text
        # extract_format=wikipediaapi.ExtractFormat.PLAIN  <- This was the error.
        # We will remove it and use the default (ExtractFormat.WIKI),
        # which correctly builds the .text property.
    )
    
    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIRECTORY, exist_ok=True)
    print(f"Using cache directory: ./{CACHE_DIRECTORY}", file=sys.stderr)
    
    all_page_titles = set()
    visited_categories = set()
    
    print("--- Starting Category Crawl ---", file=sys.stderr)
    
    for cat_name in ROOT_CATEGORIES:
        cat_page = wiki_api.page(f"Category:{cat_name}")
        
        if not cat_page.exists():
            print(f"[!] Root category '{cat_name}' not found. Skipping.", file=sys.stderr)
            continue
            
        crawl_category(
            cat_page, 
            all_page_titles, 
            visited_categories, 
            current_depth=0
        )
        
    print("\n--- Category Crawl Complete ---", file=sys.stderr)
    print(f"Found {len(all_page_titles)} unique pages.", file=sys.stderr)
    print("--- Starting Page Data Fetching ---", file=sys.stderr)

    # Now, process and cache the pages we found
    process_and_cache_pages(wiki_api, all_page_titles)
    
    print("\n--- All Data Fetched ---", file=sys.stderr)
    print(f"Processing complete. All found pages are now in ./{CACHE_DIRECTORY}", file=sys.stderr)
    
    # No longer prints one giant JSON blob

if __name__ == "__main__":
    main()



