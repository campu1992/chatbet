from typing import Dict, Any

class SessionManager:
    """
    A simple in-memory session manager for storing conversation states.
    
    Note: In a production environment, this should be replaced with a
    persistent and scalable store like Redis.
    """
    def __init__(self):
        self._histories: Dict[str, Dict[str, Any]] = {}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieves the state for a given session_id.
        If the session does not exist, it initializes a new one with a starting balance.
        """
        if session_id not in self._histories:
            self._histories[session_id] = {
                "messages": [],
                "user_balance": 1000.0  # Starting balance for new sessions
            }
        return self._histories[session_id]

    def update_session(self, session_id: str, new_state: Dict[str, Any]):
        """
        Updates the state for a given session_id.
        """
        self._histories[session_id] = new_state

# Create a singleton instance of the session manager to be used across the app
session_manager = SessionManager()
