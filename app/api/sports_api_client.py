import os
import requests
from dotenv import load_dotenv
from typing import Optional, Dict, List, Any
import logging

load_dotenv()

class SportsAPIClient:
    def __init__(self):
        self.base_url = os.getenv("SPORTS_API_BASE_URL")
        self.user_id = os.getenv("DEFAULT_USER_ID", "1")
        self.user_key = os.getenv("DEFAULT_USER_KEY", "1")
        self.token = None
        self._authenticate()

    def _authenticate(self):
        if not self.base_url:
            raise ValueError("SPORTS_API_BASE_URL is not configured.")
        auth_url = f"{self.base_url}/auth/generate_token"
        try:
            response = requests.post(auth_url, data={})
            response.raise_for_status()
            self.token = response.json().get("token")
            if not self.token:
                raise ValueError("Authentication failed: 'token' key not found in response.")
            print("Successfully authenticated and got session token.")
        except requests.exceptions.RequestException as e:
            print(f"Error authenticating: {e}")
            self.token = None

    def _get_headers(self):
        if not self.token:
            raise ConnectionError("Not authenticated.")
        # The API expects the token directly in a 'token' header.
        return {"token": self.token}

    def get_user_balance(self):
        url = f"{self.base_url}/auth/get_user_balance"
        params = {"userId": self.user_id, "userKey": self.user_key}
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching user balance: {e}")
            return None

    # ... other methods like get_sports, get_odds etc. remain here ...
    # Omitted for brevity.
    def place_bet(self, fixture_id: int, tournament_id: str, bet_id: str, odd: float, amount: float):
        url = f"{self.base_url}/place-bet"
        
        # Add the additional headers for this specific endpoint
        headers = self._get_headers()
        headers["accept-language"] = "es"
        headers["country-code"] = "BR"

        payload = {
            "user": {"userKey": self.user_key, "id": self.user_id},
            "betInfo": {
                "amount": str(amount),
                "betId": [{"betId": bet_id, "fixtureId": str(fixture_id), "odd": str(odd), "sportId": "1", "tournamentId": tournament_id}],
                "source": "ChatBot"
            }
        }
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error placing bet: {e}")
            return None
    
    def get_sports(self):
        url = f"{self.base_url}/sports"
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching sports: {e}")
            return None

    def get_all_tournaments(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches a list of all available football tournaments from the API.
        Uses the /sports/tournaments endpoint with sport_id=1 as per user feedback.
        """
        if not self.token:
            self._authenticate()
        
        url = f"{self.base_url}/sports/tournaments"
        params = {"language": "en", "sport_id": 1, "with_active_fixtures": "false"}
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"API call to get_all_tournaments failed: {e}")
            return None

    def get_fixtures_by_sport(self, sport_id: int = 1) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/sports/sports-fixtures"
        params = {"sportId": sport_id}
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching fixtures for sport {sport_id}: {e}")
            return None

    def get_odds(self, fixture_id: int, tournament_id: str, sport_id: str):
        """
        Fetches odds for a specific fixture.
        Requires sport_id and tournament_id to get an 'Active' status response.
        """
        url = f"{self.base_url}/sports/odds"
        # The 'amount' parameter seems to be required, defaulting to 1.
        params = {
            "fixtureId": fixture_id,
            "tournamentId": tournament_id,
            "sportId": sport_id,
            "amount": 1  
        }
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching odds for fixture {fixture_id}: {e}")
            return None

# Example of how to use the client
if __name__ == "__main__":
    client = SportsAPIClient()
    if client.token:
        # Example: Get today's football fixtures by fetching all and filtering
        from datetime import datetime, timezone
        
        print("\nFetching all football fixtures to filter for today...")
        all_fixtures = client.get_fixtures_by_sport(sport_id=1)
        if all_fixtures and "data" in all_fixtures and all_fixtures["data"]:
            today = datetime.now(timezone.utc).date()
            todays_fixtures = [
                f for f in all_fixtures["data"]
                if datetime.fromisoformat(f["fixture_date"].replace("Z", "+00:00")).date() == today
            ]
            
            if todays_fixtures:
                print(f"Found {len(todays_fixtures)} fixtures for today:")
                # Print the first 5 for brevity
                for fixture in todays_fixtures[:5]:
                    print(f"- {fixture['home_team']} vs {fixture['away_team']}")

                # Example: Get odds for the first fixture
                first_fixture_id = todays_fixtures[0]["fixture_id"]
                odds = client.get_odds(fixture_id=first_fixture_id)
                if odds:
                    print(f"\nOdds for fixture ID {first_fixture_id}:")
                    print(odds)
            else:
                print("No fixtures found for today after filtering.")
        
        # Example: Get user balance
        print("\nFetching user balance...")
        balance = client.get_user_balance()
        if balance:
            print(f"User Balance: {balance}")
