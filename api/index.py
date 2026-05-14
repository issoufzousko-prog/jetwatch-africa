import sys
import traceback
from fastapi import FastAPI

print("Python version:", sys.version)

try:
    from main import app
    print("Application loaded successfully")
except Exception as e:
    print("CRITICAL: Failed to load application")
    traceback.print_exc()
    
    # Fallback to a minimal app to report the error via HTTP if possible
    app = FastAPI()
    
    @app.get("/api/{full_path:path}")
    async def catch_all(full_path: str):
        return {
            "status": "error",
            "message": "Backend failed to initialize",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
