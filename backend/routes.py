from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import yfinance as yf
from database import db
import time
import random

router = APIRouter()

# --- Data Models (Schemas) ---

class TradeRequest(BaseModel):
    user_id: str
    symbol: str  # e.g., "TCS.NS"
    quantity: int

class FDRequest(BaseModel):
    user_id: str
    amount: float
    duration_months: int

# --- 1. STOCKS: BUY LOGIC ---

@router.post("/buy")
async def buy_stock(req: TradeRequest):
    # Fetch live market price via yfinance
    ticker = yf.Ticker(req.symbol)
    todays_data = ticker.history(period='1d')
    if todays_data.empty:
        raise HTTPException(status_code=404, detail="Stock symbol not found")
    
    current_price = todays_data['Close'].iloc[0]
    total_cost = current_price * req.quantity

    # Check the user's wallet in Firestore
    user_ref = db.collection('users').document(req.user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_data = user_doc.to_dict()
    if user_data['cashBalance'] < total_cost:
        raise HTTPException(status_code=400, detail="Insufficient funds in wallet")

    # Deduct money & Update holdings
    new_balance = user_data['cashBalance'] - total_cost
    user_ref.update({'cashBalance': new_balance})

    holding_id = f"{req.user_id}_{req.symbol}"
    holding_ref = db.collection('holdings').document(holding_id)
    holding_doc = holding_ref.get()

    if holding_doc.exists:
        # Re-calculate average price for existing holding
        old_data = holding_doc.to_dict()
        new_qty = old_data['quantity'] + req.quantity
        new_avg = ((old_data['avgPrice'] * old_data['quantity']) + total_cost) / new_qty
        holding_ref.update({'quantity': new_qty, 'avgPrice': new_avg})
    else:
        # Create new holding record
        holding_ref.set({
            'userId': req.user_id, 'symbol': req.symbol, 
            'quantity': req.quantity, 'avgPrice': current_price
        })

    # Log transaction for history
    db.collection('transactions').add({
        'userId': req.user_id, 'type': 'BUY', 'asset': req.symbol,
        'quantity': req.quantity, 'price': current_price, 'timestamp': time.time()
    })

    return {"message": f"Successfully bought {req.quantity} shares of {req.symbol}", "new_balance": new_balance}

# --- 2. STOCKS: SELL LOGIC ---

@router.post("/sell")
async def sell_stock(req: TradeRequest):
    ticker = yf.Ticker(req.symbol)
    todays_data = ticker.history(period='1d')
    if todays_data.empty:
        raise HTTPException(status_code=404, detail="Stock symbol not found")
    
    current_price = todays_data['Close'].iloc[0]
    total_revenue = current_price * req.quantity

    holding_id = f"{req.user_id}_{req.symbol}"
    holding_ref = db.collection('holdings').document(holding_id)
    holding_doc = holding_ref.get()

    if not holding_doc.exists or holding_doc.to_dict()['quantity'] < req.quantity:
        raise HTTPException(status_code=400, detail="Not enough shares to sell")

    # Update Wallet Balance
    user_ref = db.collection('users').document(req.user_id)
    user_data = user_ref.get().to_dict()
    new_balance = user_data['cashBalance'] + total_revenue
    user_ref.update({'cashBalance': new_balance})

    # Update or Delete holding
    old_qty = holding_doc.to_dict()['quantity']
    if old_qty == req.quantity:
        holding_ref.delete()
    else:
        holding_ref.update({'quantity': old_qty - req.quantity})

    db.collection('transactions').add({
        'userId': req.user_id, 'type': 'SELL', 'asset': req.symbol,
        'quantity': req.quantity, 'price': current_price, 'timestamp': time.time()
    })

    return {"message": f"Successfully sold {req.quantity} shares of {req.symbol}", "new_balance": new_balance}

# --- 3. MUTUAL FUNDS: EOD SIMULATION ---

@router.post("/buy_mf")
async def buy_mutual_fund(req: TradeRequest):
    # Simulate Net Asset Value (NAV) with a random variation
    base_nav = 150.0 
    current_nav = base_nav + random.uniform(-2.0, 5.0) 
    total_cost = current_nav * req.quantity
    
    user_ref = db.collection('users').document(req.user_id)
    user_data = user_ref.get().to_dict()
    
    if user_data['cashBalance'] < total_cost:
        raise HTTPException(status_code=400, detail="Insufficient funds for Mutual Fund")
    
    user_ref.update({'cashBalance': user_data['cashBalance'] - total_cost})
    
    # Store in a separate Mutual Funds collection
    db.collection('mutual_funds').add({
        'userId': req.user_id,
        'fundName': req.symbol,
        'units': req.quantity,
        'navAtPurchase': current_nav,
        'timestamp': time.time()
    })
    
    return {"message": f"Invested in {req.symbol}", "nav": current_nav}

# --- 4. FIXED DEPOSITS: SIMPLE INTEREST SIMULATION ---

@router.post("/create_fd")
async def create_fd(req: FDRequest):
    interest_rate = 0.07 # 7% Annual Interest
    
    user_ref = db.collection('users').document(req.user_id)
    user_data = user_ref.get().to_dict()
    
    if user_data['cashBalance'] < req.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds to open FD")
        
    user_ref.update({'cashBalance': user_data['cashBalance'] - req.amount})
    
    db.collection('fixed_deposits').add({
        'userId': req.user_id,
        'amount': req.amount,
        'rate': interest_rate,
        'startDate': time.time(),
        'durationMonths': req.duration_months,
        'status': 'ACTIVE'
    })
    
    return {"message": f"FD of ₹{req.amount} created successfully at {interest_rate*100}% interest"}