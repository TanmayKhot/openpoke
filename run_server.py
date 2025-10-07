#!/usr/bin/env python3
"""Simple script to run the OpenPoke server."""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up environment
os.environ.setdefault("OPENROUTER_API_KEY", "your-api-key-here")

if __name__ == "__main__":
    import uvicorn
    from server.app import app
    
    print("🚀 Starting OpenPoke Server...")
    print("📡 Server will be available at: http://localhost:8000")
    print("🔄 Press Ctrl+C to stop the server")
    print("-" * 50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=False
    )
