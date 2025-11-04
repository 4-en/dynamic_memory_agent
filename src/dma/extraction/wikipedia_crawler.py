#!/usr/bin/env python3

import wikipediaapi
import time
import json
import sys
import os
import urllib.parse
from collections import Counter
from pathlib import Path

from dma.utils import get_cache_dir
from dma.core import WebSourceData


# --- Crawler Class ---

class WikipediaCrawler:
    """
    Crawls Wikipedia categories, fetches pages, and expands the dataset.

    This class is initialized with general settings (like user agent and
    cache locations) and can be reused to perform multiple crawls
    via the `run` method.

    Parameters
    ----------
    user_agent : str, optional
        A polite User-Agent string for the Wikipedia API.
        (default is 'DefaultCrawler (example@example.com)')
    language : str, optional
        The Wikipedia language to crawl (default is 'en').
    rate_limit_delay : float, optional
        The delay in seconds between API requests (default is 0.5).
    manual_category_confirmation : bool, optional
        Whether to manually confirm outlier categories (default is True).
    meta_category_blocklist : list of str, optional
        A list of keywords to filter "meta" categories. If None,
        a default list is used (default is None).

    Attributes
    ----------
    user_agent : str
        Stores the User-Agent.
    language : str
        Stores the API language.
    rate_limit_delay : float
        Stores the API request delay.
    cache_dir : pathlib.Path
        Stores the page cache directory path.
    category_cache_dir : pathlib.Path
        Stores the category cache directory path.
    manual_category_confirmation : bool
        Stores the category confirmation setting.
    meta_category_blocklist : list of str
        Stores the category blocklist.
    wiki_api : wikipediaapi.Wikipedia
        The initialized Wikipedia API object.
    
    Notes
    -----
    Crawl-specific state (like `all_page_titles`, `all_pages_data`, etc.)
    is not stored on the instance after a `run` completes. It is
    initialized within `run` and returned by it.
    """

    def __init__(self,
                 language='en',
                 rate_limit_delay=0.5,
                 manual_category_confirmation=False,
                 meta_category_blocklist=None
                 ):
        """
        Initializes the WikipediaCrawler worker.
        """
        self.user_agent = "DynamicMemoryAgentCrawler/0.3 (ben.schumacher0@gmail.com; https://dynmem.xyz/)"
        self.language = language
        self.rate_limit_delay = rate_limit_delay
        
        # --- Cache Directory Setup (Using pathlib) ---
        base_cache_dir = get_cache_dir()
        self.cache_dir = base_cache_dir / "wiki_pages"
        self.category_cache_dir = base_cache_dir / "wiki_categories"
        # --- End Cache Setup ---
        
        self.manual_category_confirmation = manual_category_confirmation
        
        if meta_category_blocklist is None:
            self.meta_category_blocklist = [
                "articles", "disambiguation", "stubs", "pages", "people", 
                "births", "deaths", "all", "with", "from", "in", "by", "cs1", "use",
                "using", "wikipedia", "commons", "wikidata", "lists", "containing"
            ]
        else:
            self.meta_category_blocklist = meta_category_blocklist
        
        # Initialize Wikipedia API
        print("Initializing Wikipedia API...", file=sys.stderr)
        self.wiki_api = wikipediaapi.Wikipedia(
            user_agent=self.user_agent,
            language=self.language
        )

        # Create cache directories
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.category_cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"Using page cache directory: {self.cache_dir}", file=sys.stderr)
        print(f"Using category cache directory: {self.category_cache_dir}", file=sys.stderr)

        # --- Crawl-specific state ---
        # These are initialized in run() to ensure each crawl is fresh
        self.all_page_titles = set()
        self.visited_categories = set()
        self.all_pages_data = {}
        
        # These are the crawl-specific parameters, set in run()
        self.run_max_depth = 0
        self.run_expansion_top_n_links = 0
        self.run_expansion_top_n_categories = 0


    def _crawl_category(self, category_page, current_depth=0, max_level=None):
        """
        Recursively crawls a category to find all member pages and subcategories.

        Parameters
        ----------
        category_page : wikipediaapi.WikipediaPage
            The WikipediaPage object for the category to crawl.
        current_depth : int, optional
            The current recursion depth (default is 0).
        max_level : int, optional
            An override for the instance's `self.run_max_depth` (default is None).
        
        Notes
        -----
        This method modifies the instance attributes `self.all_page_titles`
        and `self.visited_categories` during a crawl.
        """
        
        # Use the max_depth set for the current run
        stop_depth = self.run_max_depth if max_level is None else max_level
        
        if current_depth > stop_depth:
            return
            
        if category_page.title in self.visited_categories:
            return
            
        self.visited_categories.add(category_page.title)
        indent = "  " * current_depth
        print(f"{indent}[CAT] Crawling: {category_page.title}", file=sys.stderr)
        
        cache_filename = category_page.title.replace("Category:", "").replace("/", "_") + ".json"
        cache_path = self.category_cache_dir / cache_filename
        
        # Attempt to use cached category members
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    members_data = json.load(f)
                    
                for member in members_data:
                    if member['ns'] == wikipediaapi.Namespace.MAIN:
                        if member['title'] not in self.all_page_titles:
                            print(f"{indent}  -> Found Page: {member['title']}", file=sys.stderr)
                            self.all_page_titles.add(member['title'])
                            
                    elif member['ns'] == wikipediaapi.Namespace.CATEGORY:
                        subcat_page = self.wiki_api.page(member['title'])
                        self._crawl_category(
                            subcat_page, 
                            current_depth + 1,
                            max_level=max_level
                        )
                return  # Success from cache
            except Exception as e:
                print(f"{indent}  [!] Error reading cache for {category_page.title}: {e}", file=sys.stderr)
                # Fall back to live crawl
                
        found_members = []
        try:
            print(f"{indent}  [FETCH] Fetching members for {category_page.title}...", file=sys.stderr)
            time.sleep(self.rate_limit_delay)
            members = category_page.categorymembers
            
            for member in members.values():
                if member.ns == wikipediaapi.Namespace.MAIN:
                    found_members.append({'title': member.title, 'ns': member.ns})
                    if member.title not in self.all_page_titles:
                        print(f"{indent}  -> Found Page: {member.title}", file=sys.stderr)
                        self.all_page_titles.add(member.title)
                        
                elif member.ns == wikipediaapi.Namespace.CATEGORY:
                    found_members.append({'title': member.title, 'ns': member.ns})
                    self._crawl_category(
                        member, 
                        current_depth + 1,
                        max_level=max_level
                    )
                    
            # Cache the found members
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(found_members, f, indent=2, ensure_ascii=False)
                    
        except Exception as e:
            print(f"{indent}  [!] Error crawling {category_page.title}: {e}", file=sys.stderr)

    def _load_page_data_from_cache(self, cache_path: Path) -> bool:
        """
        Helper to load page data from a JSON file and store it.
        
        Parameters
        ----------
        cache_path : pathlib.Path
            The full path to the JSON cache file.
            
        Returns
        -------
        bool
            True if data was successfully loaded into memory, False otherwise.
        """
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check if it's a redirect file
            if 'redirect_to' in cache_data:
                print(f"[CACHE] '{cache_path.name}' is a redirect.", file=sys.stderr)
                return False # Not an article, don't store
            
            # Create dataclass and store it
            article = WebSourceData(**cache_data)
            self.all_pages_data[article.title] = article
            return True
            
        except Exception as e:
            print(f"[WARN] Cache file {cache_path} exists but failed to load. Re-fetching. Error: {e}", file=sys.stderr)
            return False

    def _process_and_cache_pages(self, page_titles):
        """
        Fetches, processes, and caches data for a set of page titles.

        Populates `self.all_pages_data` with `WebSourceData` objects.
        If a page is already in the file cache, it's loaded into memory.
        If not, it's fetched from the API, saved to cache, and stored in memory.

        Parameters
        ----------
        page_titles : list of str or set of str
            A collection of page titles to fetch and cache.
        """
        
        total = len(page_titles)
        
        print(f"Building in-memory cache index from {self.cache_dir}...", file=sys.stderr)
        cached_filenames = set()
        if self.cache_dir.exists():
            # Use iterdir() for idiomatic pathlib iteration
            cached_filenames = set(f.name for f in self.cache_dir.iterdir() 
                                   if f.is_file() and f.suffix == '.json')
        print(f"Cache index built. Found {len(cached_filenames)} cached .json files.", file=sys.stderr)

        for i, title in enumerate(sorted(list(page_titles))):
            # Skip if we *already* have this page in our memory dict
            if title in self.all_pages_data:
                continue

            print(f"\n[PAGE] Processing {i+1}/{total}: {title}", file=sys.stderr)
            
            requested_title = title
            try:
                safe_filename_title = urllib.parse.quote_plus(requested_title)
                cache_filename = f"{safe_filename_title}.json"
                cache_path = self.cache_dir / cache_filename

                # --- MODIFIED CACHE CHECK ---
                if cache_filename in cached_filenames:
                    print(f"[CACHE] File exists for '{requested_title}'. Loading...", file=sys.stderr)
                    if self._load_page_data_from_cache(cache_path):
                        # Successfully loaded data from this file
                        print(f"[CACHE] Loaded '{self.all_pages_data[title].title}' from cache.", file=sys.stderr)
                        continue # Move to the next title
                    else:
                        # File was a redirect or corrupt, fall through to fetch
                        pass
            except Exception as e:
                print(f"[WARN] Could not check cache for '{requested_title}': {e}. Will attempt to fetch.", file=sys.stderr)


            try:
                time.sleep(self.rate_limit_delay)
                page = self.wiki_api.page(requested_title)
                
                if not page.exists():
                    print(f"[SKIP] '{requested_title}' does not exist.", file=sys.stderr)
                    continue
                    
                resolved_title = page.title
                
                # Check if we already have the *resolved* title in memory
                if resolved_title in self.all_pages_data:
                    print(f"[SKIP] Resolved page '{resolved_title}' already in memory.", file=sys.stderr)
                    continue

                resolved_safe_filename = f"{urllib.parse.quote_plus(resolved_title)}.json"
                resolved_cache_path = self.cache_dir / resolved_safe_filename

                if requested_title != resolved_title:
                    print(f"[FETCH] '{requested_title}' redirects to '{resolved_title}'.", file=sys.stderr)
                    
                    redirect_data = {"redirect_to": resolved_title}
                    with open(cache_path, 'w', encoding='utf-8') as f:
                        json.dump(redirect_data, f, indent=2, ensure_ascii=False)
                    cached_filenames.add(cache_filename)
                    
                    # --- MODIFIED REDIRECT CHECK ---
                    if resolved_safe_filename in cached_filenames:
                        print(f"[CACHE] Target page '{resolved_title}' is already cached. Loading...", file=sys.stderr)
                        if self._load_page_data_from_cache(resolved_cache_path):
                            continue # Successfully loaded, move to next title
                        else:
                            # Cache file was corrupt, fall through to re-fetch
                            pass
                    
                print(f"[FETCH] Caching '{resolved_title}' ({page.pageid})...", file=sys.stderr)
                
                content = page.text
                if not content:
                    print(f"[SKIP] '{resolved_title}' has no text content.", file=sys.stderr)
                    continue

                page_data_dict = {
                    "title": resolved_title,
                    "url": page.fullurl,
                    "pageid": page.pageid,
                    "last_updated": page.touched,
                    "summary": page.summary,
                    "categories": list(page.categories.keys()),
                    "links_to": list(page.links.keys()),
                    "content_plaintext": content
                }
                
                # --- STORE IN MEMORY ---
                article = WebSourceData(**page_data_dict)
                self.all_pages_data[resolved_title] = article
                
                # --- SAVE TO FILE CACHE ---
                with open(resolved_cache_path, 'w', encoding='utf-8') as f:
                    json.dump(page_data_dict, f, indent=2, ensure_ascii=False)
                
                cached_filenames.add(resolved_safe_filename)
                print(f"[SUCCESS] Fetched and cached data for '{resolved_title}'", file=sys.stderr)

            except Exception as e:
                print(f"[ERROR] Could not process '{requested_title}': {e}", file=sys.stderr)

    def _analyze_and_expand_links(self):
        """
        Analyzes in-memory pages to find and fetch most-linked-to "hub" pages.

        Uses `self.run_expansion_top_n_links` to determine how many
        pages to fetch.

        Notes
        -----
        This method calls `self._process_and_cache_pages` to fetch the
        newly found pages, which will add them to `self.all_pages_data`.
        """
        top_n_setting = self.run_expansion_top_n_links
        top_n = 0
        
        # Use titles from the *original* core set for "EQUAL" calculation
        core_page_count = len(self.all_page_titles)
        
        if isinstance(top_n_setting, str) and top_n_setting.upper() == "EQUAL":
            top_n = core_page_count
        elif isinstance(top_n_setting, int):
            top_n = top_n_setting
        
        if top_n <= 0 or core_page_count == 0:
            print("\n--- Link Expansion Disabled ---", file=sys.stderr)
            return

        print("\n--- Starting 'Phase 3' Link Expansion Analysis ---", file=sys.stderr)
        
        all_links_counter = Counter()
        
        # --- MODIFIED: Read from in-memory data ---
        print(f"Analyzing links in {len(self.all_pages_data)} pages in memory...", file=sys.stderr)
        for page_data in self.all_pages_data.values():
            all_links_counter.update(page_data.links_to)
        # --- End Modification ---

        # Filter out links to pages we *already* have in memory
        for title in self.all_pages_data.keys():
            if title in all_links_counter:
                del all_links_counter[title]
                
        if not all_links_counter:
            print("No external links found to expand.", file=sys.stderr)
            return
            
        top_external_links = all_links_counter.most_common(top_n)
        
        new_pages_to_fetch = set()
        print(f"\nFound {len(top_external_links)} new 'hub' pages to fetch based on link frequency:", file=sys.stderr)
        for i, (title, count) in enumerate(top_external_links):
            print(f"  {i+1}. {title} (linked to {count} times)", file=sys.stderr)
            new_pages_to_fetch.add(title)
            
        print("\n--- Fetching 'Phase 3' Expansion Pages ---", file=sys.stderr)
        self._process_and_cache_pages(new_pages_to_fetch)
    
    def _analyze_and_expand_categories(self):
        """
        Analyzes in-memory pages to find and crawl common "outlier" categories.

        Uses `self.run_expansion_top_n_categories` and
        `self.manual_category_confirmation`.

        Notes
        -----
        This method calls `self._crawl_category` (with `max_level=0`)
        and `self._process_and_cache_pages` to fetch newly found pages.
        """
        if self.run_expansion_top_n_categories <= 0:
            print("\n--- Category Expansion Disabled ---", file=sys.stderr)
            return

        print("\n--- Starting 'Phase 4' Category Expansion Analysis ---", file=sys.stderr)

        category_counter = Counter()

        # --- MODIFIED: Read from in-memory data ---
        print(f"Analyzing categories in {len(self.all_pages_data)} pages in memory...", file=sys.stderr)
        for page_data in self.all_pages_data.values():
            category_counter.update(page_data.categories)
        # --- End Modification ---

        if not category_counter:
            print("No categories found to analyze.", file=sys.stderr)
            return

        top_outlier_categories = []
        print("Finding 'outlier' categories...", file=sys.stderr)

        for cat_title, count in category_counter.most_common(500):
            if cat_title in self.visited_categories:
                continue
                
            is_meta = False
            cat_title_lower = cat_title.lower()
            for keyword in self.meta_category_blocklist:
                if keyword in cat_title_lower:
                    is_meta = True
                    break
            
            if is_meta:
                continue
            
            if self.manual_category_confirmation:
                try:
                    response = input(f"Do you want to crawl category '{cat_title}' (count: {count})? [y/N]: ")
                    if response.strip().lower() != 'y':
                        continue
                except EOFError:
                    print("\nEOF received, stopping category confirmation.", file=sys.stderr)
                    break
            
            top_outlier_categories.append((cat_title, count))
                
            if len(top_outlier_categories) >= self.run_expansion_top_n_categories:
                break

        if not top_outlier_categories:
            print("No new 'outlier' categories found to expand.", file=sys.stderr)
            return

        # Use a *new* set to hold pages found just from this expansion
        new_pages_from_categories = set()
        # Temporarily swap `all_page_titles` to this new set for the crawl
        original_page_titles_set = self.all_page_titles
        self.all_page_titles = new_pages_from_categories

        print(f"\nFound {len(top_outlier_categories)} new 'outlier' categories to crawl:", file=sys.stderr)

        for i, (title, count) in enumerate(top_outlier_categories):
            print(f"  {i+1}. {title} (appeared {count} times)", file=sys.stderr)
            
            self.visited_categories.add(title) 
            
            cat_page = self.wiki_api.page(title)
            if cat_page.exists():
                self._crawl_category(
                    cat_page,
                    current_depth=0,
                    max_level=0
                )
        
        # Restore the original page title set
        self.all_page_titles = original_page_titles_set
        
        # Filter out pages we *already* have in memory from the new finds
        new_pages_to_fetch = new_pages_from_categories - set(self.all_pages_data.keys())

        if not new_pages_to_fetch:
            print("Outlier categories did not yield any new pages.", file=sys.stderr)
            return

        print(f"\n--- Fetching 'Phase 4' Expansion Pages ({len(new_pages_to_fetch)} new) ---", file=sys.stderr)
        self._process_and_cache_pages(new_pages_to_fetch)


    def run(self, 
            root_categories: list[str],
            max_depth: int = 2,
            expansion_top_n_links: str | int = "EQUAL",
            expansion_top_n_categories: int = 20
            ) -> list[WebSourceData]:
        """
        Executes a full crawl-and-expand process with specific parameters.

        This method is the main entry point for a crawl. It resets the
        crawler's internal state and then runs the four-phase process.

        Parameters
        ----------
        root_categories : list of str
            A list of root category titles to start the crawl from.
        max_depth : int, optional
            How deep to crawl into subcategories (default is 2).
        expansion_top_n_links : int or str, optional
            How many top-linked pages to add during expansion (default is "EQUAL").
        expansion_top_n_categories : int, optional
            How many top "outlier" categories to crawl for expansion (default is 20).

        Returns
        -------
        list[WebSourceData]
            A list of all unique WebSourceData objects retrieved during this run.
        """
        
        # --- Initialize/Reset Crawl State ---
        self.all_page_titles = set()
        self.visited_categories = set()
        self.all_pages_data = {}
        
        # --- Set Crawl-Specific Parameters ---
        self.run_max_depth = max_depth
        self.run_expansion_top_n_links = expansion_top_n_links
        self.run_expansion_top_n_categories = expansion_top_n_categories
        
        print(f"\n--- Starting New Crawl ---", file=sys.stderr)
        print(f"Root Categories: {root_categories}", file=sys.stderr)
        print(f"Max Depth: {self.run_max_depth}", file=sys.stderr)

        # --- Phase 1: Core Category Crawl ---
        print("--- Starting 'Phase 1' Category Crawl ---", file=sys.stderr)
        for cat_name in root_categories:
            cat_page = self.wiki_api.page(f"Category:{cat_name}")
            
            if not cat_page.exists():
                print(f"[!] Root category '{cat_name}' not found. Skipping.", file=sys.stderr)
                continue
                
            self._crawl_category(
                cat_page, 
                current_depth=0
            )
            
        print("\n--- 'Phase 1' Category Crawl Complete ---", file=sys.stderr)
        print(f"Found {len(self.all_page_titles)} unique page titles.", file=sys.stderr)
        
        # --- Phase 2: Core Page Fetching ---
        print("--- Starting 'Phase 2' Page Data Fetching (Core Pages) ---", file=sys.stderr)
        core_pages_to_fetch = self.all_page_titles.copy()
        self._process_and_cache_pages(core_pages_to_fetch)
        
        # --- Phase 3: Link Expansion ---
        self._analyze_and_expand_links()
        
        # --- Phase 4: Category Expansion ---
        self._analyze_and_expand_categories()
        
        print("\n--- All Data Fetched ---", file=sys.stderr)
        print(f"Processing complete. {len(self.all_pages_data)} total pages in memory.", file=sys.stderr)
        
        # Return the list of dataclass objects
        return list(self.all_pages_data.values())


# --- Main execution ---
if __name__ == "__main__":
    
    # 1. Create an instance of the crawler *once* with general settings
    crawler = WikipediaCrawler()
    
    # 2. Run the first crawl and capture the returned data
    print("--- 🚀 STARTING FIRST CRAWL ---")
    all_articles = crawler.run(
        root_categories=["Solar System"],
        max_depth=2,
        expansion_top_n_links="EQUAL",
        expansion_top_n_categories=10 # Reduced for a quicker test run
    )
    
    # 3. Print a summary of the first run
    print(f"\n--- First run complete ---", file=sys.stderr)
    if all_articles:
        print(f"Successfully retrieved {len(all_articles)} articles.", file=sys.stderr)
        print(f"Example article: {all_articles[0].title}", file=sys.stderr)
    else:
        print("No articles were retrieved.", file=sys.stderr)

    # 4. Run a *second*, different crawl using the same instance
    print("\n--- 🚀 STARTING SECOND CRAWL ---")
    moon_articles = crawler.run(
        root_categories=["Moon landings"],
        max_depth=1,
        expansion_top_n_links=10,
        expansion_top_n_categories=5
    )

    # 5. Print a summary of the second run
    print(f"\n--- Second run complete ---", file=sys.stderr)
    if moon_articles:
        print(f"Successfully retrieved {len(moon_articles)} articles.", file=sys.stderr)
        print(f"Example article: {moon_articles[0].title}", file=sys.stderr)
    else:
        print("No articles were retrieved.", file=sys.stderr)