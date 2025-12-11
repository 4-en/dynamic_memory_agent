# builds the benchmark input data from wikipedia articles

from dma.extraction import WikipediaCrawler
from dma.core import WebSourceData

from dma.utils import get_data_dir

import os
import random

benchmark_data_dir = get_data_dir() / "benchmark_data"
os.makedirs(benchmark_data_dir, exist_ok=True)

CATEGORIES = ["Solar System"]
N_BENCHMARK_ARTICLES = 100

crawler = WikipediaCrawler()
web_sources = crawler.run(root_categories=CATEGORIES, expansion_top_n_categories=0)

# count and rank articles by number of links to that article
article_link_counts = {}
for source in web_sources:
    for link in source.links_to:
        if link not in article_link_counts:
            article_link_counts[link] = 0
        article_link_counts[link] += 1
        
ranked_articles = sorted(web_sources, key=lambda x: article_link_counts.get(x.title, 0), reverse=True)

# filter articles that are too short
ranked_articles = [article for article in ranked_articles if len(article.content_plaintext) > 200]

# sample N articles from the top of the ranked list with higher probability for higher ranked articles
top_ranked = ranked_articles[:N_BENCHMARK_ARTICLES * 2]
sampled_articles = random.choices(top_ranked, k=N_BENCHMARK_ARTICLES)

# save article contents as plain text files
for article in sampled_articles:
    safe_title = article.title.replace("/", "_").replace("\\", "_")
    file_path = benchmark_data_dir / f"{safe_title}.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"{article.title}\n\n{article.content_plaintext}")



