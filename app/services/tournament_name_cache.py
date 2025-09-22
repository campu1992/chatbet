import logging
from typing import Dict
import json
import os
from app.services import api_client

CACHE_FILE = "tournament_cache.json"

class TournamentNameCache:
    """
    Handles fetching and caching of football tournament names and their IDs.
    Supports persisting the cache to a file to speed up application restarts.
    """
    def __init__(self):
        self._tournaments_map: Dict[str, str] = {}
        self._load_cache_from_file()

    def _load_cache_from_file(self):
        """Loads the tournament map from a local JSON file if it exists."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    self._tournaments_map = json.load(f)
                logging.info(f"Tournament name cache loaded successfully from {CACHE_FILE}. Found {len(self._tournaments_map)} tournaments.")
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Error loading cache from {CACHE_FILE}: {e}. Will repopulate from API.")
                self._tournaments_map = {}
        else:
            logging.info(f"{CACHE_FILE} not found. Cache will be populated from API.")
    
    def _save_cache_to_file(self):
        """Saves the current tournament map to a local JSON file."""
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(self._tournaments_map, f, indent=4)
            logging.info(f"Tournament name cache saved successfully to {CACHE_FILE}.")
        except IOError as e:
            logging.error(f"Error saving cache to {CACHE_FILE}: {e}")

    def populate_cache(self):
        """
        Fetches all football tournaments and populates the cache if it's not already loaded.
        """
        if self._tournaments_map:
            logging.info("Tournament name cache is already populated. Skipping API call.")
            return

        logging.info("Attempting to populate tournament name cache from API...")
        tournaments = api_client.get_all_tournaments()
        if not tournaments or not isinstance(tournaments, list):
            logging.error("Failed to populate tournament name cache: API call returned no data or incorrect format.")
            return

        tournaments_map = {}
        for tournament in tournaments:
            name = tournament.get("tournament_name")
            tour_id = tournament.get("tournament_id")
            if name and tour_id:
                tournaments_map[name.strip()] = tour_id
        
        self._tournaments_map = tournaments_map
        logging.info(f"Tournament name cache populated successfully with {len(self._tournaments_map)} football tournaments.")
        self._save_cache_to_file() # Save the new cache to file
        
        logging.debug(f"Available tournaments in cache: {list(self._tournaments_map.keys())}")

    def get_all_tournaments_map(self) -> Dict[str, str]:
        return self._tournaments_map

# Singleton instance
tournament_name_cache = TournamentNameCache()
