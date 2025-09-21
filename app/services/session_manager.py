from typing import Dict, Any
from threading import Lock
from app.core.graph import AgentState
from app.services import api_client

class SessionManager:
    """
    A simple in-memory session manager for storing conversation states.
    
    Note: In a production environment, this should be replaced with a
    persistent and scalable store like Redis.
    """
    def __init__(self):
        self._sessions: Dict[str, AgentState] = {}
        self._lock = Lock()

    def get_session(self, session_id: str) -> AgentState:
        with self._lock:
            if session_id not in self._sessions:
                # Get initial real balance ONLY when creating a new session
                initial_balance_data = api_client.get_user_balance()
                initial_balance = initial_balance_data.get("money", 0.0) if initial_balance_data else 0.0
                
                self._sessions[session_id] = AgentState(
                    messages=[], 
                    match_context=None,
                    simulated_balance=initial_balance, # Start simulation with real balance
                    bets=[] # Start with an empty list of bets
                )
            return self._sessions[session_id]

    def save_session(self, session_id: str, state: AgentState):
        with self._lock:
            self._sessions[session_id] = state
            
    def get_latest_balance_data(self, session_id: str) -> Dict:
        # This function is not ideal, as the balance is now in the state.
        # But for now, we can retrieve it from the saved state.
        with self._lock:
            if session_id in self._sessions:
                balance = self._sessions[session_id].get("simulated_balance", 0.0)
                return {"money": balance}
        return {"money": 0.0}


# Create a singleton instance of the session manager to be used across the app
session_manager = SessionManager()
