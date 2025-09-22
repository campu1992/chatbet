import logging
import time
import traceback
from typing import List, Optional
from app.services import api_client
from thefuzz import process

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

class TeamNameCache:
    """
    A singleton cache for storing team names to avoid repeated API calls.
    Fetches data on-demand and stores it in memory for the application's lifetime.
    """
    def __init__(self):
        self._team_names: List[str] = []
        self._is_populated = False

    def _ensure_populated(self):
        """
        Ensures the cache is populated from the API, but only runs the API call once.
        Includes a retry mechanism for robustness.
        """
        if self._is_populated:
            return

        logging.info("Team name cache is empty. Populating from API...")
        for i in range(MAX_RETRIES):
            logging.info(f"Cache population attempt {i+1}/{MAX_RETRIES}...")
            try:
                response = api_client.get_fixtures_by_sport(sport_id=1)
                
                logging.debug(f"Raw API response for fixtures: {response}")

                if not response:
                    logging.warning(f"API returned no response on attempt {i+1}.")
                    time.sleep(RETRY_DELAY)
                    continue

                fixtures = response.get("data") if isinstance(response, dict) else response
                
                if not fixtures or not isinstance(fixtures, list):
                    logging.warning(f"API response did not contain a list of fixtures on attempt {i+1}.")
                    time.sleep(RETRY_DELAY)
                    continue

                all_names = set()
                for fixture in fixtures:
                    home_team_name = fixture.get("home_team_data", {}).get("name", {}).get("en")
                    away_team_name = fixture.get("away_team_data", {}).get("name", {}).get("en")

                    if home_team_name:
                        all_names.add(home_team_name)
                    if away_team_name:
                        all_names.add(away_team_name)
                
                self._team_names = list(all_names)
                self._is_populated = True
                logging.info(f"Team name cache populated successfully with {len(self._team_names)} unique teams.")
                return
            except Exception:
                logging.error(f"An unexpected error occurred during cache population attempt {i+1}:")
                logging.error(traceback.format_exc())
                time.sleep(RETRY_DELAY)

        logging.error("Could not populate team name cache after multiple retries.")
        self._is_populated = True # Mark as populated even on failure to prevent retrying on every call

    def get_all_team_names(self) -> List[str]:
        self._ensure_populated()
        return self._team_names

    def get_best_match(self, query: str, threshold: int = 80) -> Optional[str]:
        """
        Find the best matching team name from the cache using fuzzy matching.
        
        Args:
            query: The team name to search for
            threshold: Minimum similarity score (0-100) to consider a match
            
        Returns:
            The best matching team name if found above threshold, None otherwise
        """
        self._ensure_populated()
            
        if not self._team_names:
            return None
            
        match = process.extractOne(query, self._team_names)
        if match and match[1] >= threshold:
            return match[0]
        return None


# Create a singleton instance
team_name_cache = TeamNameCache()
