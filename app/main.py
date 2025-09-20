import threading
import time
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.core.graph import app as chat_agent
from langchain_core.messages import HumanMessage
from app.services.session_manager import session_manager
from app.services.team_name_cache import team_name_cache
from app.services.tournament_name_cache import tournament_name_cache
from app.services import api_client

# Global flag to track if the caches are ready
CACHE_READY = False

app = FastAPI(title="ChatBet API", version="1.0.0")

def populate_caches_background():
    """Function to run in a background thread to populate caches."""
    global CACHE_READY
    logging.info("Background cache population started.")
    time.sleep(2) # Give server time to start up fully
    try:
        tournament_name_cache.populate_cache()
        team_name_cache.populate_cache()
        CACHE_READY = True # Signal that the cache is ready
        logging.info("Background cache population finished successfully. Chatbot is now fully operational.")
    except Exception as e:
        logging.error(f"FATAL: Background cache population failed: {e}. Chatbot will not be operational.")
        # CACHE_READY remains False

@app.on_event("startup")
def on_startup():
    """Start the cache population in a background thread."""
    logging.info("Application startup...")
    cache_thread = threading.Thread(target=populate_caches_background)
    cache_thread.start()

# --- Pydantic Models ---
class ChatRequest(BaseModel):
    user_input: str
    session_id: str

class ChatResponse(BaseModel):
    response: str
    session_id: str

class HealthStatus(BaseModel):
    cache_ready: bool

# --- New Health Check Endpoint ---
@app.get("/health/status", response_model=HealthStatus)
def get_health_status():
    """Endpoint for the frontend to check if the backend caches are ready."""
    return {"cache_ready": CACHE_READY}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Welcome to ChatBet API!"}

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Main endpoint to interact with the chatbot.
    Checks if the cache is ready before processing.
    """
    if not CACHE_READY:
        raise HTTPException(
            status_code=503, # Service Unavailable
            detail="The chatbot is still initializing its knowledge base. Please wait a moment and try again."
        )
    current_state = session_manager.get_session(request.session_id)
    
    current_state["messages"].append(HumanMessage(content=request.user_input))
    
    response_state = chat_agent.invoke(current_state)
    
    final_message = response_state['messages'][-1]
    
    session_manager.update_session(request.session_id, response_state)
    
    # Fetch the latest balance for the default user to return to the UI
    latest_balance_data = api_client.get_user_balance()
    
    return {
        "response": final_message.content, 
        "balance": latest_balance_data.get("money", 0.0) if latest_balance_data else 0.0
    }
