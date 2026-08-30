from gdeltdoc import GdeltDoc, Filters
import pandas as pd


def search_gdelt(keywords: list, start_date: str, end_date: str) -> list:
    f = Filters(
        keyword=" ".join(keywords),
        start_date=start_date,
        end_date=end_date,
        num_records=50
    )
    gd = GdeltDoc()

    try:
        results_df = gd.article_search(f)
        urls = results_df['url'].tolist()
        return urls
    except Exception as e:
        print(f"GDELT search failed: {e}")
        return []