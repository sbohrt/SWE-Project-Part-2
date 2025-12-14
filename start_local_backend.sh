#!/bin/bash
# Start local Flask backend with local DynamoDB configuration

echo "🚀 Starting Flask backend with local DynamoDB..."
echo ""

# Set environment variables for local DynamoDB
export AWS_ENDPOINT_URL=http://localhost:8000
export AWS_ACCESS_KEY_ID=dummy
export AWS_SECRET_ACCESS_KEY=dummy
export AWS_DEFAULT_REGION=us-east-1

# Optional: Set GitHub token if you have one
# export GITHUB_TOKEN=your_github_token_here

# Optional: Set admin API key for /reset endpoint
export ADMIN_API_KEY=test-secret-key

# Optional: Set allowed CORS origins
export ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5000

# Add src to Python path so imports work
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"

echo "Environment configured:"
echo "  AWS_ENDPOINT_URL: $AWS_ENDPOINT_URL"
echo "  ADMIN_API_KEY: $ADMIN_API_KEY"
echo "  PYTHONPATH: $PYTHONPATH"
echo ""

# Start the Flask server
echo "Starting Flask server on http://localhost:5001..."
python3 src/swe_project/api/run.py
