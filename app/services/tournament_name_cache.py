import logging
from typing import Dict
from app.services import api_client

class TournamentNameCache:
    """
    Handles fetching and caching of football tournament names and their IDs
    on an in-memory, on-demand basis.
    """
    def __init__(self):
        self._tournaments_map: Dict[str, str] = {}
        self._is_populated = False

    def _ensure_populated(self):
        """
        Ensures the cache is populated from the API, but only runs the API call once.
        """
        if self._is_populated:
            return

        logging.info("Tournament name cache is empty. Populating from API...")
        tournaments = api_client.get_all_tournaments()
        if not tournaments or not isinstance(tournaments, list):
            logging.error("Failed to populate tournament name cache: API call returned no data or incorrect format.")
            self._is_populated = True # Mark as populated to prevent retries
            return

        tournaments_map = {}
        for tournament in tournaments:
            name = tournament.get("tournament_name")
            tour_id = tournament.get("tournament_id")
            if name and tour_id:
                tournaments_map[name.strip()] = tour_id
        
        self._tournaments_map = tournaments_map
        self._is_populated = True # Mark as populated
        logging.info(f"Tournament name cache populated successfully with {len(self._tournaments_map)} football tournaments.")
        logging.debug(f"Available tournaments in cache: {list(self._tournaments_map.keys())}")

    def get_all_tournaments_map(self) -> Dict[str, str]:
        self._ensure_populated()
        return self._tournaments_map

# Singleton instance
tournament_name_cache = TournamentNameCache()
