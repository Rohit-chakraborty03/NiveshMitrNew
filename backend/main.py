from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import routes  # This connects to your trading logic in routes.py

app = FastAPI()

# --- STEP 1: ADD CORS MIDDLEWARE ---
# This tells your backend to allow requests from your frontend (Port 5501)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits all origins for the hackathon
    allow_credentials=True,
    allow_methods=["*"],  # Permits all methods (POST, GET, etc.)
    allow_headers=["*"],  # Permits all headers
)

# --- STEP 2: INCLUDE YOUR ROUTES ---
app.include_router(routes.router)

# --- STEP 3: HEALTH CHECK ---
@app.get("/")
async def root():
    return {"message": "NiveshMitr Backend is Online!"}