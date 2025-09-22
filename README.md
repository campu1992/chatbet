# ChatBet: AI-Powered Sports Betting Assistant

ChatBet is a sophisticated, conversational chatbot designed for sports betting enthusiasts. It leverages a powerful Large Language Model (LLM) orchestrated by LangGraph to provide a seamless and intuitive chat experience. The chatbot integrates with a live sports API to deliver real-time data on match fixtures, tournament standings, and betting odds.

This README provides a comprehensive overview of the project, including its architecture, setup instructions, and key technical decisions.

---

## Key Features

- **Natural Language Queries**: Ask for match schedules, team fixtures, and tournament participants in plain English.
- **Real-Time Odds**: Get up-to-the-minute betting odds for various match outcomes.
- **Daily Analysis**: Receive daily betting insights, including the safest bet, highest reward, and most competitive match.
- **Betting Recommendations**: Get personalized betting strategies based on a specified budget, intelligently split between low-risk and high-risk options.
- **Simulated Betting**: Place bets within a session, track a simulated balance, and review your betting history.
- **Context-Aware Conversations**: The chatbot remembers the context of your conversation for natural follow-up questions.

---

## Technologies & Stack

- **Backend**: Python, FastAPI
- **Frontend**: Streamlit
- **AI/LLM Orchestration**: LangChain, LangGraph
- **LLM**: Google Gemini Pro (configurable)
- **Containerization**: Docker, Docker Compose
- **Core Libraries**: Pydantic, Requests, Dateparser, TheFuzz

---

## Getting Started

Follow these steps to set up and run the project locally using Docker.

**Note:** The very first time you run the application, the backend needs to build a cache of team and tournament data from the live API. This process can take **up to 10 minutes**, depending on your internet connection. Subsequent launches will be much faster.

### Prerequisites

- **Docker** and **Docker Compose** must be installed on your system.
- An **API Token** for the external sports API.

### 1. Clone the Repository

```bash
git clone https://your-repository-url/chatbet.git
cd chatbet
```

### 2. Configure Environment Variables

Create a `.env` file by copying the example file.

```bash
cp env.example .env
```

Now, open the `.env` file and add your specific credentials. See the [Environment Variables](#-environment-variables) section below for details.

### 3. Build and Run the Application

We've created simple scripts to automate the startup process. These scripts will build and start the Docker containers, intelligently wait for the backend caches to be fully initialized, and then automatically open the chatbot in your default web browser. This is the recommended way to run the application.

**On Linux or macOS:**
Make the script executable first, then run it.
```bash
chmod +x start.sh
./start.sh
```

**On Windows:**
```bash
start.bat
```

The script will handle everything for you. Once the app is ready, it will open at `http://localhost:8501`.

---

## Environment Variables

The `.env` file is used to configure the application.

```env
# The base URL for the FastAPI backend service.
# This is used by the Streamlit frontend to communicate with the API.
# It should match the service name defined in docker-compose.yml.
API_BASE_URL=http://api:8000

# Your personal authentication token for the external sports API.
# This is required to fetch match data and odds.
API_TOKEN="YOUR_SECRET_API_TOKEN"

# The identifier for the Google Gemini model you wish to use.
# 'gemini-1.5-pro-latest' is recommended for the best performance.
GEMINI_MODEL=gemini-1.5-pro-latest

# Note: The Google Application Credentials should be mounted via the Docker volume
# as specified in the docker-compose.yml file.
```

---

## Usage Examples & Demo

Interact with the chatbot using natural language to get sports and betting information. The agent is designed to handle a wide range of queries.

*(The following images demonstrate the chatbot in action.)*

image.png
image.png
image.png
image.png
image.png
image.png
image.png
image.png
image.png
image.png

---

## Technical Deep Dive & Reflection

This section answers key questions about the project's design and implementation.

### 1. Architecture: What design choices did you make and why?

I chose a decoupled, microservices-style architecture to ensure modularity, scalability, and maintainability.

-   **Decoupled Frontend/Backend**: The system is split into two main services: a **FastAPI backend** for the core logic and a **Streamlit frontend** for the user interface. This separation allows for independent development, deployment, and scaling. The frontend can be updated without touching the backend, and vice-versa.
-   **Stateful Agent Orchestration (LangGraph)**: Instead of a simple agent loop, I used **LangGraph** to build a stateful graph. This robust approach provides explicit control over the conversational flow, making it easier to manage complex interactions, tool calls, and error handling. The `AgentState` object acts as a central hub for all session data.
-   **Tool-Based Logic**: All business logic and external API interactions are encapsulated within discrete **Tools** (e.g., `get_fixtures_by_date`, `get_daily_odds_analysis`). This makes the system highly extensible; adding new capabilities is as simple as defining a new tool function and making the LLM aware of it.
-   **Modular Prompts**: The core system prompt that guides the LLM is managed in a separate `app/prompts` directory. This decouples the instructional logic from the agent's graph definition, making it easier to iterate on and manage the agent's behavior and persona.
-   **Asynchronous Backend (FastAPI)**: FastAPI's native `async` support is critical for an I/O-bound application like this, which spends much of its time waiting for responses from the LLM and the external sports API. This allows the server to handle many concurrent users efficiently.

### 2. LLM: Which model did you use and why?

I used **Google's Gemini Pro**, made configurable via the `GEMINI_MODEL` environment variable.

-   **Reasoning and Tool Use**: Gemini models, particularly the 1.5 Pro version, have excellent function-calling capabilities. The model's ability to accurately infer which tool to use based on the user's query and correctly populate its arguments is the cornerstone of this agent's success.
-   **Instruction Following**: The model is highly effective at adhering to the detailed instructions provided in the system prompt, ensuring that it maintains the desired persona, uses context correctly, and formats its responses as required (e.g., using HTML for robust rendering in Streamlit).
-   **Integration**: The `langchain-google-genai` library provides a seamless and well-maintained integration, making it easy to incorporate the model into the LangChain and LangGraph ecosystem.

### 3. Context: How did you manage conversational context?

Conversational context is managed through a multi-layered session management strategy.

-   **Stateful Graph (`AgentState`)**: The core of context management resides in LangGraph's `AgentState`. This object persists across turns within a single session and explicitly tracks `messages` (full chat history), `match_context` (detailed data about the last discussed match), `simulated_balance`, and a list of `bets` placed in the session.
-   **Backend Session Management**: The FastAPI backend maintains a `SessionManager` that stores the `AgentState` for each unique `session_id`. When a request comes in, the appropriate state is loaded; after the agent processes the request, the updated state is saved.
-   **Prompt Engineering**: On every turn, critical context (like the user's balance and details from `match_context`) is dynamically injected into the system prompt. This ensures the LLM has all the necessary information readily available to handle follow-up questions accurately, such as "How much would I win if I bet $50 on a draw?".

### 4. Optimization: How did you optimize API queries?

I implemented several strategies to minimize latency and reduce redundant calls to the external sports API.

-   **In-Memory Caching**: On startup, the backend populates two singleton caches: `TeamNameCache` and `TournamentNameCache`. These caches store relatively static data (like mappings of team names to IDs) that is frequently required for tool logic. This avoids hitting the API for the same information repeatedly.
-   **Asynchronous Cache Population**: To ensure the main server process is not blocked, cache population runs in a background thread. A `/health/status` endpoint allows the frontend to poll the backend and wait until the caches are ready before allowing user interaction, preventing errors and improving the user experience.
-   **Consolidated Tool Logic**: Complex queries like "What's the most competitive match today?" are handled by a single, powerful tool (`get_daily_odds_analysis`). This tool encapsulates all the necessary logic—fetching fixtures, retrieving odds for multiple matches, and performing analysis—into one optimized operation, preventing the LLM from making a series of slow, sequential tool calls.

### 5. Scalability: How did you handle multiple concurrent users?

The architecture is designed to be scalable, although the current implementation is tailored for local development.

-   **Stateless Backend Service**: The FastAPI application is stateless. All session-specific data is handled by the `SessionManager`. This design is crucial for horizontal scaling; we can run multiple instances of the backend container behind a load balancer.
-   **Centralized State (Production-Ready Design)**: The current in-memory `SessionManager` is a bottleneck for true multi-instance scalability. In a production environment, this would be swapped with an external, shared datastore like **Redis** or a database. This would allow any backend instance to handle any user's request without losing session context.
-   **Container Orchestration**: Using Docker Compose simplifies deployment. For a large-scale deployment, this would be migrated to a container orchestration platform like Kubernetes or AWS ECS for automated scaling, health checks, and load balancing.

### 6. Improvements: What would you add with more time?

-   **Persistent State Management**: The top priority would be to replace the in-memory session manager with a **Redis** cache. This would provide persistence for user sessions across server restarts and is essential for a multi-replica, scalable deployment.
-   **Real-Time Data with WebSockets**: I would implement a WebSocket connection to push real-time updates (e.g., live odds changes, match events) to the user, creating a more dynamic and engaging experience.
-   **Comprehensive Testing Suite**: I would build out a full suite of unit tests (for individual tools and functions) and integration tests (for the end-to-end conversational flow) to ensure the application is robust and reliable.
-   **CI/CD Pipeline**: I would set up a CI/CD pipeline (e.g., using GitHub Actions) to automate testing and deployment, ensuring that new features and fixes can be released quickly and safely.
-   **Advanced Analytics & Personalization**: I would enhance the betting recommendation tools to incorporate historical data, user preferences, and more advanced analytical models.

### 7. Monitoring: How would you measure chatbot conversation quality?

-   **LLM Tracing with LangSmith**: I would integrate **LangSmith** to get detailed traces of every conversation. This allows for debugging the agent's reasoning, tracking tool usage, and evaluating the quality of LLM responses. It's the most effective way to understand *why* the agent behaved a certain way.
-   **User Feedback Loop**: I would add simple "thumbs up/thumbs down" buttons to the UI. Collecting direct user feedback is one of the best ways to identify failed or unsatisfactory conversations, which can then be reviewed in LangSmith.
-   **Key Performance Indicators (KPIs)**: I would implement logging to track critical metrics:
    -   **Tool Error Rate**: A high error rate for a specific tool could indicate a bug or that the LLM is struggling to use it correctly.
    -   **Response Latency**: Tracking the time it takes to generate a response.
    -   **Conversation Depth**: Measuring how many turns it takes for a user to achieve their goal. Successful conversations are often efficient.

### 8. Security: What security considerations did you implement?

-   **Secrets Management**: All sensitive credentials (`API_TOKEN`) are managed through **environment variables** and are never hardcoded. The `.env` file is explicitly ignored by Git to prevent accidental exposure.
-   **Backend-for-Frontend (BFF) Pattern**: The Streamlit frontend only communicates with our FastAPI backend, never directly with the external sports API. The backend acts as a secure proxy, ensuring the `API_TOKEN` is never exposed to the client-side.
-   **Input Validation**: By using LangGraph's strongly-typed state and tool schemas, we inherently validate and structure the data passed between components. This, combined with FastAPI's Pydantic validation on the API boundary, minimizes the risk of injection attacks.
-   **Container Isolation**: Running the services within Docker containers provides process isolation from the host machine, limiting the potential impact of a security breach.
