#!/bin/bash
# This script automates the startup process for the ChatBet application.

echo "🚀 Starting ChatBet services..."

# Start containers in detached mode to run them in the background.
# The --build flag ensures the images are up-to-date with the latest code.
docker-compose up --build -d

echo "⏳ Waiting for the backend service to initialize..."
echo "This may take a minute during the first run as caches are being built from the API."
echo "Subsequent runs will be much faster by using the local cache files."

# Poll the health check endpoint until the caches are ready.
while true; do
    # Use curl to get the HTTP status code of the health endpoint.
    STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/status)
    
    # Check if the server is responding (status code 200)
    if [ "$STATUS_CODE" -eq 200 ]; then
        # If the server is up, check the content of the response for '"cache_ready": true'
        READY_STATUS=$(curl -s http://localhost:8000/health/status | grep -o '"cache_ready":\s*true')
        
        if [ -n "$READY_STATUS" ]; then
            echo ""
            echo "✅ ChatBet is ready!"
            echo "Opening the application in your default browser..."
            
            # Open the URL in the default browser based on the OS.
            if [[ "$OSTYPE" == "linux-gnu"* ]]; then
                    xdg-open http://localhost:8501
            elif [[ "$OSTYPE" == "darwin"* ]]; then
                    open http://localhost:8501
            fi
            break
        fi
    fi
    # Print a dot to show progress
    echo -n "."
    sleep 5
done

echo ""
echo "✨ Your ChatBet instance is running in the background."
echo "➡️ To view live logs, run: docker-compose logs -f"
echo "➡️ To stop the services, run: docker-compose down"
