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

def main():
    """Main function to run the Streamlit app."""
    st.title("ChatBet Assistant ⚽")

    # --- Initialization and State Management ---
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        # Generate a unique session ID for the user
        st.session_state.session_id = os.urandom(24).hex()

    # --- Main Chat Interface ---
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
