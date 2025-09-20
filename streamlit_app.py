import streamlit as st
import requests
import os
import time

# --- Page Configuration ---
st.set_page_config(
    page_title="ChatBet Assistant",
    page_icon="⚽",
    layout="wide"
)

# --- Backend API Configuration ---
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def check_backend_ready():
    """Polls the backend's health check endpoint until the cache is ready."""
    while True:
        try:
            response = requests.get(f"{API_BASE_URL}/health/status")
            if response.status_code == 200 and response.json().get("cache_ready"):
                return True
        except requests.ConnectionError:
            # Backend is not up yet, wait a bit
            pass
        time.sleep(2) # Wait 2 seconds before polling again

def main():
    """Main function to run the Streamlit app."""
    st.title("ChatBet Assistant ⚽")

    # --- Initialization and State Management ---
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        # Generate a unique session ID for the user
        st.session_state.session_id = os.urandom(24).hex()

    # --- Cache Loading UI ---
    if "backend_ready" not in st.session_state or not st.session_state.backend_ready:
        with st.spinner("Initializing the assistant's knowledge base... Please wait a moment."):
            if check_backend_ready():
                st.session_state.backend_ready = True
                st.rerun() # Rerun the script to show the main chat UI
        return # Stop execution until backend is ready

    # --- Main Chat Interface (only shows after cache is ready) ---
    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)
            
    # Chat input
    if user_input := st.chat_input("What can I bet on today?"):
        # Add user message to chat history and display it
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
            
        # Get response from the backend
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            with st.spinner("Thinking..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/chat",
                        json={"user_input": user_input, "session_id": st.session_state.session_id}
                    )
                    response.raise_for_status()
                    full_response = response.json()["response"]
                    message_placeholder.markdown(full_response, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                except requests.exceptions.RequestException as e:
                    error_message = f"Error connecting to the backend: {e}"
                    message_placeholder.error(error_message)
                    st.session_state.messages.append({"role": "assistant", "content": error_message})

if __name__ == "__main__":
    main()
