#!/bin/bash

# Setup script for the Neo4j and Qdrant GraphRAG project

# Colors for better readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up the Neo4j and Qdrant GraphRAG environment...${NC}"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}uv is not installed. Please install it first:${NC}"
    echo -e "${BLUE}curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
    exit 1
fi

# Create Python virtual environment and install dependencies
echo -e "${BLUE}Creating virtual environment and installing dependencies...${NC}"
uv sync
echo -e "${GREEN}Dependencies installed.${NC}"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${BLUE}Creating .env file...${NC}"
    cat > .env << EOL
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Embedding Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
EOL
    echo -e "${GREEN}.env file created.${NC}"
fi

echo -e "${GREEN}Setup complete!${NC}"
echo -e "To run scripts, use: ${BLUE}uv run python <script>${NC}"
echo -e "To start the databases, run: ${BLUE}docker-compose up -d${NC}"
