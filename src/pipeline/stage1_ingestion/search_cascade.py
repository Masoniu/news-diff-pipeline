import logging
import pandas as pd
from typing import List
from gdeltdoc import GdeltDoc, Filters

logger = logging.getLogger(__name__)


class SearchCascade:
    def __init__(self):
        self.gd = GdeltDoc()

    def search_gdelt(self, keywords: List[str], start_date: str, end_date: str) -> List[str]:
        """
        Searches for articles via GDELT DOC API using keywords and a time window.
        Date format: 'YYYY-MM-DD'
        """
        keyword_query = " ".join(keywords)
        logger.info(f"Tier 1 (GDELT): Searching for query '{keyword_query}'")

        f = Filters(
            keyword=keyword_query,
            start_date=start_date,
            end_date=end_date,
            num_records=50
        )

        try:
            results_df = self.gd.article_search(f)

            if results_df.empty:
                logger.warning("GDELT returned no results.")
                return []

            urls = results_df['url'].dropna().tolist()
            logger.info(f"GDELT found {len(urls)} potential candidates.")
            return urls

        except ValueError as ve:
            logger.error(f"Error parsing GDELT response: {ve}")
            return []
        except Exception as e:
            logger.error(f"Critical GDELT error: {e}")
            return []