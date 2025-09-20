import logging
from typing import Dict
from app.services import api_client

class TournamentNameCache:
    """
    Handles fetching and caching of all unique football tournament names and their IDs.
    This is populated once at startup to provide a definitive list for matching.
    """
    def __init__(self):
        self._tournaments_map: Dict[str, str] = {}

    def populate_cache(self):
        """
        Fetches all football tournaments and populates the cache
        with a mapping of tournament name to tournament ID.
        """
        logging.info("Attempting to populate tournament name cache...")
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
        # Add a debugging log to print all the cached tournament names
        logging.info(f"Available tournaments in cache: {list(self._tournaments_map.keys())}")

    def get_all_tournaments_map(self) -> Dict[str, str]:
        return self._tournaments_map

# Singleton instance
tournament_name_cache = TournamentNameCache()
