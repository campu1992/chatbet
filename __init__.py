from app.api.sports_api_client import SportsAPIClient

# Create a singleton instance of the Sports API client.
# This ensures that authentication happens only once when the app starts.
api_client = SportsAPIClient()
