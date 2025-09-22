import logging
import time
import traceback
from typing import List, Optional
import json
import os

from app.services import api_client
from thefuzz import process

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
CACHE_FILE = "team_cache.json"

class TeamNameCache:
    """
    A singleton cache for storing team names to avoid repeated API calls.
    It now supports persisting the cache to a file to speed up restarts.
    """
    def __init__(self):
        self.team_names: List[str] = []
        self._load_cache_from_file()

    def _load_cache_from_file(self):
        """Tries to load the team names from a local JSON file."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    self.team_names = json.load(f)
                logging.info(f"Team name cache loaded successfully from {CACHE_FILE}. Found {len(self.team_names)} teams.")
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Error loading cache from {CACHE_FILE}: {e}. Will try to populate from API.")
                self.team_names = []
        else:
            logging.info(f"{CACHE_FILE} not found. Cache will be populated from API.")

    def _save_cache_to_file(self):
        """Saves the current team names to a local JSON file."""
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(self.team_names, f, indent=4)
            logging.info(f"Team name cache saved successfully to {CACHE_FILE}.")
        except IOError as e:
            logging.error(f"Error saving cache to {CACHE_FILE}: {e}")

    def populate_cache(self):
        """
        Fetches fixtures and extracts unique team names, with a retry mechanism.
        If the cache is already populated (from file), this method does nothing.
        """
        if self.team_names:
            logging.info("Team name cache is already populated. Skipping API call.")
            return

        logging.info("Attempting to populate team name cache from API...")
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
                    # Correctly parse the nested team name structure
                    home_team_name = fixture.get("home_team_data", {}).get("name", {}).get("en")
                    away_team_name = fixture.get("away_team_data", {}).get("name", {}).get("en")

                    if home_team_name:
                        all_names.add(home_team_name)
                    if away_team_name:
                        all_names.add(away_team_name)
                
                self.team_names = list(all_names)
                logging.info(f"Team name cache populated successfully with {len(self.team_names)} unique teams.")
                self._save_cache_to_file() # Save the newly populated cache to a file
                return
            except Exception:
                logging.error(f"An unexpected error occurred during cache population attempt {i+1}:")
                # This will log the full stack trace of the exception
                logging.error(traceback.format_exc())
                time.sleep(RETRY_DELAY)

        logging.error("Could not populate team name cache after multiple retries.")

    def get_all_team_names(self) -> List[str]:
        return self.team_names

    def get_best_match(self, query: str, threshold: int = 80) -> Optional[str]:
        """
        Find the best matching team name from the cache using fuzzy matching.
        
        Args:
            query: The team name to search for
            threshold: Minimum similarity score (0-100) to consider a match
            
        Returns:
            The best matching team name if found above threshold, None otherwise
        """
        if not self.team_names:
            return None
            
        match = process.extractOne(query, self.team_names)
        if match and match[1] >= threshold:
            return match[0]
        return None


# Create a singleton instance
team_name_cache = TeamNameCache()
