import wikipediaapi
import time
import json
import sys
import os
import urllib.parse  # <-- Added for safe filenames
from collections import Counter

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
CATEGORY_CACHE_DIRECTORY = "wiki_category_cache"

# 5. SET EXPANSION OPTIONS
# After fetching all pages from categories, this will find the
# most-linked-to pages that are *not* in the core set and add them.
# Set to 0 to disable.
EXPANSION_TOP_N_LINKS = "EQUAL" # number or "EQUAL" for same as original found set size

# 6. SET CATEGORY EXPANSION OPTIONS
# This will find the most common categories *in our set*, filter
# out meta-categories, and then crawl the remaining "outlier" categories.
EXPANSION_TOP_N_CATEGORIES = 20
MANUAL_CATEGORY_CONFIRMATION = True  # Set to True to manually confirm before crawling new categories

# 7. CATEGORY NOISE FILTER
# Keywords for "meta" categories to ignore during expansion.
# These are case-insensitive.
META_CATEGORY_BLOCKLIST = [
    "articles", "disambiguation", "stubs", "pages", "people", 
    "births", "deaths", "all", "with", "from", "in", "by", "cs1", "use",
    "using", "wikipedia", "commons", "wikidata", "lists", "containing"
]


# 3. BE POLITE: Set a User-Agent and Rate Limit
# Wikipedia requires a unique User-Agent for API requests.
# Please replace with your own info.
USER_AGENT = 'DynamicMemoryAgentCrawler/0.3 (ben.schumacher0@gmail.com; https://dynmem.xyz/)'
LANGUAGE = 'en'

# Delay in seconds between *every* API request. 0.5 is a safe, polite value.
RATE_LIMIT_DELAY = 0.5

# --- End of Configuration ---


def crawl_category(
    category_page, 
    all_page_titles, 
    visited_categories, 
    current_depth=0,
    max_level=None  # <-- ADDED to fix bug in Phase 4
):
    """
    Recursively crawls a category to find all member pages and subcategories.
    
    :param category_page: The wikipediaapi.WikipediaPage object for the category.
    :param all_page_titles: A set to store the titles of found pages (passed by ref).
    :param visited_categories: A set to prevent infinite loops (passed by ref).
    :param current_depth: The current recursion depth.
    :param max_level: (Optional) Override for MAX_RECURSION_DEPTH.
    """
    
    # Determine the correct max depth for this run
    stop_depth = MAX_RECURSION_DEPTH if max_level is None else max_level
    
    # Stop if we're too deep
    if current_depth > stop_depth:  # <-- Use stop_depth
        return
        
    # Stop if we've already processed this category
    if category_page.title in visited_categories:
        return
        
    # Mark this category as visited
    visited_categories.add(category_page.title)
    indent = "  " * current_depth
    print(f"{indent}[CAT] Crawling: {category_page.title}", file=sys.stderr)
    
    # attempt to use cached category members if available
    cache_filename = category_page.title.replace("Category:", "").replace("/", "_") + ".json"
    cache_path = os.path.join(CATEGORY_CACHE_DIRECTORY, cache_filename)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                members_data = json.load(f)
                
            for member in members_data:
                
                if member['ns'] == wikipediaapi.Namespace.MAIN:
                    if member['title'] not in all_page_titles:
                        print(f"{indent}  -> Found Page: {member['title']}", file=sys.stderr)
                        all_page_titles.add(member['title'])
                        
                elif member['ns'] == wikipediaapi.Namespace.CATEGORY:
                    subcat_page = category_page.wiki.page(member['title'])
                    crawl_category(
                        subcat_page, 
                        all_page_titles, 
                        visited_categories, 
                        current_depth + 1,
                        max_level=max_level  # <-- Pass along
                    )
            return
        except Exception as e:
            print(f"{indent}  [!] Error reading cache for {category_page.title}: {e}", file=sys.stderr)
            # Fall back to live crawl if cache read fails
            
    found_members = []

    # Get all members of this category
    try:
        # This is the main API call to get members.
        # We apply the rate limit *before* this single call.
        print(f"{indent}  [FETCH] Fetching members for {category_page.title}...", file=sys.stderr)
        time.sleep(RATE_LIMIT_DELAY)  # <-- MOVED HERE
        members = category_page.categorymembers
        
        for member in members.values():
            # time.sleep(RATE_LIMIT_DELAY) # <-- REMOVED. This was inefficient.
            
            if member.ns == wikipediaapi.Namespace.MAIN:
                # add to found members for caching
                found_members.append({'title': member.title, 'ns': member.ns})
                # This is an article (ns=0)
                if member.title not in all_page_titles:
                    print(f"{indent}  -> Found Page: {member.title}", file=sys.stderr)
                    all_page_titles.add(member.title)
                    
            elif member.ns == wikipediaapi.Namespace.CATEGORY:
                # This is a subcategory (ns=14)
                found_members.append({'title': member.title, 'ns': member.ns})
                # Recurse!
                crawl_category(
                    member, 
                    all_page_titles, 
                    visited_categories, 
                    current_depth + 1,
                    max_level=max_level  # <-- Pass along
                )
                
        # Cache the found members for future runs
        os.makedirs(CATEGORY_CACHE_DIRECTORY, exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(found_members, f, indent=2, ensure_ascii=False)
                
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
    
    # --- MODIFICATION: Build in-memory cache index ---
    print(f"Building in-memory cache index from ./{CACHE_DIRECTORY}...", file=sys.stderr)
    cached_filenames = set()
    if os.path.exists(CACHE_DIRECTORY):
        # We only care about the .json files
        cached_filenames = set(f for f in os.listdir(CACHE_DIRECTORY) if f.endswith('.json'))
    print(f"Cache index built. Found {len(cached_filenames)} cached .json files.", file=sys.stderr)
    # --- END MODIFICATION ---

    for i, title in enumerate(sorted(list(page_titles))):
        print(f"\n[PAGE] Processing {i+1}/{total}: {title}", file=sys.stderr)
        
        requested_title = title
        try:
            safe_filename_title = urllib.parse.quote_plus(requested_title)
            cache_filename = f"{safe_filename_title}.json" # e.g., "ISS.json"
            cache_path = os.path.join(CACHE_DIRECTORY, cache_filename)

            # --- MODIFIED CACHE CHECK ---
            # This is now an O(1) set lookup, not an I/O call.
            if cache_filename in cached_filenames:
                # File exists. Let's peek inside to see if it's a redirect.
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    if 'redirect_to' in cache_data:
                        print(f"[CACHE] '{requested_title}' is a redirect to '{cache_data['redirect_to']}'.", file=sys.stderr)
                    else:
                        print(f"[CACHE] Skipping '{requested_title}', file already exists.", file=sys.stderr)
                except Exception as e:
                    print(f"[WARN] Cache file {cache_path} exists but failed to load. Re-fetching. Error: {e}", file=sys.stderr)
                    # Fall through to re-fetch
                else:
                    continue # <-- This is the efficiency gain! We skip the API call.
            # --- END MODIFIED CACHE CHECK ---

        except Exception as e:
            print(f"[WARN] Could not check cache for '{requested_title}': {e}. Will attempt to fetch.", file=sys.stderr)


        # If we're here, the page is not in our cache set.
        # NOW we apply the rate limit and make API calls.
        try:
            time.sleep(RATE_LIMIT_DELAY)
            page = wiki_api.page(requested_title)
            
            if not page.exists():
                print(f"[SKIP] '{requested_title}' does not exist.", file=sys.stderr)
                continue
                
            resolved_title = page.title
            
            # Get the safe filename for the *resolved* title
            resolved_safe_filename = f"{urllib.parse.quote_plus(resolved_title)}.json" # e.g., "International_Space_Station.json"
            resolved_cache_path = os.path.join(CACHE_DIRECTORY, resolved_safe_filename)

            if requested_title != resolved_title:
                print(f"[FETCH] '{requested_title}' redirects to '{resolved_title}'.", file=sys.stderr)
                
                # 1. Create a small redirect file for the *requested* title
                redirect_data = {"redirect_to": resolved_title}
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(redirect_data, f, indent=2, ensure_ascii=False)
                
                # --- MODIFICATION: Add new redirect file to in-memory set ---
                cached_filenames.add(cache_filename)
                
                # 2. Check if the *resolved* page is already cached.
                #    --- MODIFIED CHECK ---
                if resolved_safe_filename in cached_filenames:
                    print(f"[CACHE] Target page '{resolved_title}' is already cached.", file=sys.stderr)
                    continue
            
            # --- Fetch and save the main page data ---
            print(f"[FETCH] Caching '{resolved_title}' ({page.pageid})...", file=sys.stderr)
            
            content = page.text
            if not content:
                print(f"[SKIP] '{resolved_title}' has no text content.", file=sys.stderr)
                continue

            page_url = page.fullurl
            links_to = list(page.links.keys())
            summary = page.summary
            last_updated = page.touched
            page_categories = [cat for cat in page.categories.keys()]
            
            page_data = {
                "title": resolved_title,
                "url": page_url,
                "pageid": page.pageid,
                "last_updated": last_updated,
                "summary": summary,
                "categories": page_categories,
                "links_to": links_to,
                "content_plaintext": content
            }
            
            # Save the data to its own file (using the resolved path)
            with open(resolved_cache_path, 'w', encoding='utf-8') as f:
                json.dump(page_data, f, indent=2, ensure_ascii=False)
            
            # --- MODIFICATION: Add new page file to in-memory set ---
            cached_filenames.add(resolved_safe_filename)
            
            print(f"[SUCCESS] Fetched and cached data for '{resolved_title}'", file=sys.stderr)

        except Exception as e:
            print(f"[ERROR] Could not process '{requested_title}': {e}", file=sys.stderr)


            

def analyze_and_expand_links(wiki_api, core_page_titles):
    """
    Analyzes all cached pages to find the most-linked-to external pages
    and adds them to the cache.
    
    :param wiki_api: The initialized wikipediaapi.Wikipedia object.
    :param core_page_titles: A set of page titles from the initial category crawl.
    """
    top_n = EXPANSION_TOP_N_LINKS
    if EXPANSION_TOP_N_LINKS == "EQUAL":
        top_n = len(core_page_titles)
    
    if top_n <= 0:
        print("\n--- Link Expansion Disabled ---", file=sys.stderr)
        return

    print("\n--- Starting 'Phase 3' Link Expansion Analysis ---", file=sys.stderr)
    
    all_links_counter = Counter()
    cached_page_titles = set(core_page_titles) # Start with our core set
    
    # 1. Read all cached files and count all links
    print(f"Analyzing links in {len(os.listdir(CACHE_DIRECTORY))} cached files...", file=sys.stderr)
    for filename in os.listdir(CACHE_DIRECTORY):
        if filename.endswith(".json"):
            try:
                file_path = os.path.join(CACHE_DIRECTORY, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Skip redirect files
                    if 'redirect_to' in data:
                        continue
                        
                    # Add this page's title to our set of "already have"
                    cached_page_titles.add(data['title'])
                    
                    # Add all its links to the counter
                    all_links_counter.update(data['links_to'])
            except Exception as e:
                print(f"[WARN] Could not read cache file {filename}: {e}", file=sys.stderr)

    # 2. Filter out links to pages we already have
    for title in cached_page_titles:
        if title in all_links_counter:
            del all_links_counter[title]
            
    if not all_links_counter:
        print("No external links found to expand.", file=sys.stderr)
        return
        
    # 3. Get the Top N most common external links
    top_external_links = all_links_counter.most_common(top_n)
    
    new_pages_to_fetch = set()
    print(f"\nFound {len(top_external_links)} new 'hub' pages to fetch based on link frequency:", file=sys.stderr)
    for i, (title, count) in enumerate(top_external_links):
        print(f"  {i+1}. {title} (linked to {count} times)", file=sys.stderr)
        new_pages_to_fetch.add(title)
        
    # 4. Fetch and cache these new pages
    print("\n--- Fetching 'Phase 3' Expansion Pages ---", file=sys.stderr)
    process_and_cache_pages(wiki_api, new_pages_to_fetch)
    

def analyze_and_expand_categories(wiki_api, all_page_titles, visited_categories):
    """
    Analyzes cached pages to find common, non-meta categories that
    we haven't crawled yet. It then crawls them for new pages.
    
    :param wiki_api: The initialized wikipediaapi.Wikipedia object.
    :param all_page_titles: A set of all page titles we *already* have.
    :param visited_categories: A set of all categories we've *already* crawled.
    """
    if EXPANSION_TOP_N_CATEGORIES <= 0:
        print("\n--- Category Expansion Disabled ---", file=sys.stderr)
        return

    print("\n--- Starting 'Phase 4' Category Expansion Analysis ---", file=sys.stderr)

    category_counter = Counter()

    # 1. Read all cached files and count all categories
    print(f"Analyzing categories in {len(os.listdir(CACHE_DIRECTORY))} cached files...", file=sys.stderr)
    for filename in os.listdir(CACHE_DIRECTORY):
        if filename.endswith(".json"):
            try:
                file_path = os.path.join(CACHE_DIRECTORY, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Skip redirect files
                    if 'redirect_to' in data:
                        continue
                    category_counter.update(data['categories'])
            except Exception as e:
                print(f"[WARN] Could not read cache file {filename}: {e}", file=sys.stderr)

    if not category_counter:
        print("No categories found to analyze.", file=sys.stderr)
        return

    # 2. Filter, find outliers, and select Top N
    top_outlier_categories = []
    print("Finding 'outlier' categories...", file=sys.stderr)

    for cat_title, count in category_counter.most_common(500): # Check top 500
        # Check if we already crawled it
        if cat_title in visited_categories:
            continue
            
        # Check if it's a "noise" category
        is_meta = False
        cat_title_lower = cat_title.lower()
        for keyword in META_CATEGORY_BLOCKLIST:
            if keyword in cat_title_lower:
                is_meta = True
                break
        
        if is_meta:
            continue
        
        if MANUAL_CATEGORY_CONFIRMATION:
            # Ask user to confirm
            response = input(f"Do you want to crawl category '{cat_title}' (count: {count})? [y/N]: ")
            if response.strip().lower() != 'y':
                continue
        
        top_outlier_categories.append((cat_title, count))
            
        # Stop once we have enough
        if len(top_outlier_categories) >= EXPANSION_TOP_N_CATEGORIES:
            break

    if not top_outlier_categories:
        print("No new 'outlier' categories found to expand.", file=sys.stderr)
        return

    # 3. Crawl these new categories for pages
    new_pages_from_categories = set()
    print(f"\nFound {len(top_outlier_categories)} new 'outlier' categories to crawl:", file=sys.stderr)

    for i, (title, count) in enumerate(top_outlier_categories):
        print(f"  {i+1}. {title} (appeared {count} times)", file=sys.stderr)
        
        # Mark as visited *before* crawling to prevent re-crawling
        visited_categories.add(title) 
        
        cat_page = wiki_api.page(title)
        if cat_page.exists():
            # Crawl this new category
            # We set a max_level of 0 to only get pages *directly* in
            # this category, not its entire sub-tree, to keep it focused.
            crawl_category(
                cat_page,
                new_pages_from_categories,
                visited_categories,
                current_depth=0, # Start at 0
                max_level=0      # <-- This now works!
            )

    # 4. Filter out any pages we *already* have
    new_pages_to_fetch = new_pages_from_categories - all_page_titles

    if not new_pages_to_fetch:
        print("Outlier categories did not yield any new pages.", file=sys.stderr)
        return

    # 5. Fetch and cache these new pages
    print(f"\n--- Fetching 'Phase 4' Expansion Pages ({len(new_pages_to_fetch)} new) ---", file=sys.stderr)
    process_and_cache_pages(wiki_api, new_pages_to_fetch)


def main():
    """
    Main function to orchestrate the crawl and data fetching.
    """
    
    print("Initializing Wikipedia API...", file=sys.stderr)
    wiki_api = wikipediaapi.Wikipedia(
        user_agent=USER_AGENT, 
        language=LANGUAGE
    )
    
    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIRECTORY, exist_ok=True)
    os.makedirs(CATEGORY_CACHE_DIRECTORY, exist_ok=True)
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
            # max_level is omitted, so it correctly uses the global default
        )
        
    print("\n--- Category Crawl Complete ---", file=sys.stderr)
    print(f"Found {len(all_page_titles)} unique pages.", file=sys.stderr)
    print("--- Starting 'Phase 2' Page Data Fetching (Core Pages) ---", file=sys.stderr)

    # Now, process and cache the pages we found
    process_and_cache_pages(wiki_api, all_page_titles)
    
    # --- Phase 3: Link Expansion ---
    # This will read the cache and fetch the most-linked-to pages
    analyze_and_expand_links(wiki_api, all_page_titles)
    
    # --- Phase 4: Category Expansion ---
    # This will read the cache, find "outlier" categories,
    # crawl them, and fetch the new pages.
    analyze_and_expand_categories(wiki_api, all_page_titles, visited_categories)
    
    print("\n--- All Data Fetched ---", file=sys.stderr)
    print(f"Processing complete. All found pages are now in ./{CACHE_DIRECTORY}", file=sys.stderr)
    

if __name__ == "__main__":
    main()