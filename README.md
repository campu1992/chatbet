# ChatBet Technical Assessment

This project is a conversational chatbot designed for sports and betting, built as part of a technical assessment. The chatbot leverages a Large Language Model (LLM) through LangGraph to provide a natural conversational experience, integrating with an external sports API to fetch real-time data about matches, tournaments, and odds.

## Technologies Used

- **Python 3.9**
- **FastAPI**: For building the web server that exposes the chatbot.
- **Docker & Docker Compose**: To containerize the application for easy setup and deployment.
- **Google Gemini Pro**: As the core Large Language Model.
- **LangChain & LangGraph**: To structure the conversational agent, manage tools, and orchestrate the logic flow.
- **Pydantic**: For data validation in API requests.
- **Requests**: For communicating with the external sports API.

## Setup Instructions

### Prerequisites
- Docker and Docker Compose installed on your machine.
- A Google AI API Key with the Gemini Pro model enabled. You can get one from [Google AI Studio](https://aistudio.google.com/app/apikey).

### 1. Clone the Repository
```bash
git clone <repository-url>
cd <repository-folder>
```

### 2. Create the Environment File
Copy the example environment file and fill in your credentials.

```bash
cp env.example .env
```
You will need to edit the `.env` file with your specific credentials.

### 3. Build and Run with Docker Compose
From the root of the project, run the following command:
```bash
docker-compose up --build
```
This command will build the Docker image and start the FastAPI service. The API will be available at `http://localhost:8000`.

## Environment Variables

Your `.env` file should contain the following variables.

```env
# Google AI API Key for Gemini
GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"

# Sports API Credentials
# These are dummy credentials for the example. Replace if you have real ones.
SPORTS_API_BASE_URL="https://v46fnhvrjvtlrsmnismnwhdh5y0lckdl.lambda-url.us-east-1.on.aws/"
SPORTS_API_USERNAME="YOUR_USERNAME"
SPORTS_API_PASSWORD="YOUR_PASSWORD"
```

## Usage Examples

You can interact with the chatbot by sending POST requests to the `/chat` endpoint. You must provide a `user_input` and a `session_id`. The `session_id` is used to maintain conversation history.

### Example 1: Asking about today's matches

**Request:**
```bash
curl -X 'POST' \
  'http://localhost:8000/chat' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_input": "Are there any matches today?",
  "session_id": "session123"
}'
```

### Example 2: Asking a follow-up question about odds

After the first question, the agent knows the context.

**Request:**
```bash
curl -X 'POST' \
  'http://localhost:8000/chat' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_input": "What are the odds for the first match?",
  "session_id": "session123"
}'
```

## Technical Decisions & Reflection Questions

### 1. Architecture: What design choices did you make and why?
The architecture is designed to be modular, scalable, and maintainable, based on a containerized microservice approach.

- **Containerization (Docker & Docker Compose):** I chose Docker to encapsulate the application and its dependencies, ensuring a consistent environment for development and deployment. Docker Compose orchestrates the service, making it possible to launch the entire application with a single `docker-compose up` command, as required by the assessment.
- **Web Framework (FastAPI):** FastAPI was selected for its high performance, asynchronous capabilities, and automatic documentation generation (via OpenAPI). Its Pydantic integration provides robust data validation for API requests, which is crucial for security and reliability.
- **Modular Code Structure:** The codebase is organized by feature to promote separation of concerns:
    - `app/api`: Contains the client for the external sports API, isolating external communication.
    - `app/core`: Holds the core AI logic. This is further divided into `agent.py` for defining tools and `graph.py` for orchestrating the conversational flow with LangGraph.
    - `app/main.py`: Serves as the entry point, handling HTTP requests and connecting them to the conversational agent. This decoupling means the core agent logic could be reused with a different interface (e.g., a WebSocket) with minimal changes.

### 2. LLM: Which model did you use and why?
I used **Google's Gemini Pro** model. The choice was based on several factors:
- **Availability and Cost:** Google provides a generous free tier for the Gemini Pro API, making it ideal for a technical assessment without incurring costs.
- **Performance:** Gemini Pro demonstrates a strong ability to follow instructions and use tools (function calling), which is the cornerstone of this agent's architecture. Its reasoning capabilities are sufficient for interpreting user queries and the data returned by the tools.
- **Integration:** It integrates seamlessly with the LangChain ecosystem via the `langchain-google-genai` package, making setup straightforward.

### 3. Context: How did you manage conversational context?
Context management is handled at two levels:

1.  **API Layer (Session Management):** The FastAPI endpoint `/chat` requires a `session_id` for each request. This ID is used as a key in a simple in-memory dictionary (`conversation_histories`) to store the state of each user's conversation. For a new `session_id`, a new history is created, including an initial simulated user balance. While this in-memory solution is suitable for this assessment, it would be replaced by a persistent store like Redis in a production environment to handle restarts and scaling.
2.  **Agent Layer (LangGraph State):** The core of the context is managed by the `AgentState` object within LangGraph. This typed dictionary holds the `messages` (the full history of user, AI, and tool messages) and the `user_balance`. The graph is designed so that the message history accumulates (`operator.add`), providing the LLM with the full context of the conversation at each step. This allows the agent to handle follow-up questions and multi-turn interactions naturally.

### 4. Optimization: How did you optimize API queries?
Query optimization was a key consideration to ensure the chatbot is responsive and efficient.

- **Single Client Instance:** The `SportsAPIClient` is instantiated only once when the application starts. This singleton-like pattern ensures that authentication (token generation) happens only once at startup, avoiding repeated authentication calls for every user request.
- **Specialized Analytical Tools:** Instead of having the LLM make multiple, iterative API calls to answer complex analytical questions (e.g., "What is the safest bet today?"), I created a dedicated tool (`get_daily_odds_analysis`). This tool encapsulates the complex logic of fetching multiple matches, their odds, and performing the analysis in a single, efficient backend operation. This significantly reduces the number of back-and-forth interactions between the LLM and the tools, leading to faster and more reliable responses.
- **Specific Tooling:** Tools are designed to be as specific as possible. For instance, `get_fixtures_by_date` allows filtering directly in the API call, offloading the work to the API server instead of fetching all data and filtering it in our application.

### 5. Scalability: How did you handle multiple concurrent users?
The current architecture is designed with scalability in mind, although the implementation has some development-level constraints.

- **Stateless Service:** The FastAPI application is fundamentally stateless. All conversational state is managed externally (currently in the in-memory dictionary). This means we can scale the service horizontally by running multiple instances of the Docker container behind a load balancer. Each instance can handle any user's request as long as it can access the shared state manager.
- **Scalability Bottleneck:** The main bottleneck for scalability in the current implementation is the in-memory `conversation_histories` dictionary. It's not shared between multiple container instances. To make the application truly scalable, this would be replaced with an external, shared state manager like **Redis** or a database. This would allow multiple API service replicas to handle requests for the same session without losing context.
- **Asynchronous Framework:** FastAPI's asynchronous nature (built on ASGI) allows it to handle multiple concurrent I/O-bound operations (like waiting for the external API or the LLM) very efficiently, which is a key requirement for a scalable chatbot.

### 6. Improvements: What would you add with more time?
- **Streaming Responses:** For a better user experience, I would implement response streaming using FastAPI's `StreamingResponse`. This would allow the chatbot to start sending its response word-by-word as it's being generated by the LLM, instead of making the user wait for the full response.
- **Robust State Management:** I would replace the in-memory session management with a Redis-backed system for true scalability and persistence.
- **Enhanced Error Handling:** I would add more granular error handling within the agent, providing clearer feedback to the user if an API call fails or if they ask for something completely outside the chatbot's capabilities.
- **Testing:** I would write a comprehensive suite of unit and integration tests to ensure the reliability of the API client, tools, and the overall conversational flow.
- **Deployment to AWS:** As suggested, I would deploy the application to an AWS service like ECS or Lambda for a real-world, scalable deployment.

### 7. Monitoring: How would you measure chatbot conversation quality?
- **LangSmith:** The most direct way to monitor this architecture is using a tool like LangSmith. It's designed specifically for tracing and evaluating LLM applications. I would integrate it to get full visibility into the agent's decision-making process: which tools it calls, what the inputs and outputs are, and the final response. LangSmith also has features for creating datasets and running evaluations to programmatically measure response quality against a "golden" set of examples.
- **User Feedback:** I would add a simple "thumbs up/thumbs down" feedback mechanism to the API response. This user-provided data is invaluable for identifying conversations where the chatbot failed.
- **Log Analysis:** I would implement structured logging to track key metrics like response latency, tool call frequency, and error rates.

### 8. Security: What security considerations did you implement?
- **Environment Variables for Secrets:** All sensitive information (API keys, credentials) is managed via environment variables and is never hardcoded in the source code. The `.env` file is included in `.gitignore` to prevent accidental commits of secrets.
- **Data Validation:** FastAPI uses Pydantic for request validation. This ensures that incoming data to the `/chat` endpoint conforms to the expected schema (`ChatRequest`), preventing many common injection-type vulnerabilities.
- **Containerization:** Running the application in a Docker container provides a layer of isolation from the host system.
- **Further Steps:** In a production environment, I would add authentication and authorization to the API itself (e.g., using OAuth2), implement rate limiting to prevent abuse, and ensure all external communication uses HTTPS.
