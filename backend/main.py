from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import routes  # This imports the trading logic from your routes.py file

# 1. Initialize the FastAPI app
app = FastAPI(title="NiveshMitr API", description="Paper Trading Backend for Diversion 2k26")

# 2. Setup CORS (Cross-Origin Resource Sharing)
# This is required so your frontend (running on Live Server) isn't blocked by the browser when talking to this backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (perfect for hackathon local testing)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],
)

# 3. Connect the buy/sell endpoints from routes.py
app.include_router(routes.router)

# 4. A simple root endpoint to check if the server is alive
@app.get("/")
def read_root():
    return {"message": "NiveshMitr Backend is running perfectly!"}