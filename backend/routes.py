from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import yfinance as yf
from database import db
import time

router = APIRouter()

# Define the exact data structure the frontend will send to the backend
class TradeRequest(BaseModel):
    user_id: str
    symbol: str  # e.g., "RELIANCE.NS" for Indian stocks on Yahoo Finance
    quantity: int

@router.post("/buy")
async def buy_stock(req: TradeRequest):
    # 1. Fetch live market price
    ticker = yf.Ticker(req.symbol)
    todays_data = ticker.history(period='1d')
    if todays_data.empty:
        raise HTTPException(status_code=404, detail="Stock symbol not found")
    
    current_price = todays_data['Close'].iloc[0]
    total_cost = current_price * req.quantity

    # 2. Check the user's wallet
    user_ref = db.collection('users').document(req.user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_data = user_doc.to_dict()
    if user_data['cashBalance'] < total_cost:
        raise HTTPException(status_code=400, detail="Insufficient funds in wallet")

    # 3. Deduct money & Update holdings
    new_balance = user_data['cashBalance'] - total_cost
    user_ref.update({'cashBalance': new_balance})

    holding_id = f"{req.user_id}_{req.symbol}"
    holding_ref = db.collection('holdings').document(holding_id)
    holding_doc = holding_ref.get()

    if holding_doc.exists:
        # Calculate new average price if they already own this stock
        old_data = holding_doc.to_dict()
        new_qty = old_data['quantity'] + req.quantity
        new_avg = ((old_data['avgPrice'] * old_data['quantity']) + total_cost) / new_qty
        holding_ref.update({'quantity': new_qty, 'avgPrice': new_avg})
    else:
        # Create a new holding document
        holding_ref.set({
            'userId': req.user_id, 'symbol': req.symbol, 
            'quantity': req.quantity, 'avgPrice': current_price
        })

    # 4. Log the transaction for the dashboard history
    db.collection('transactions').add({
        'userId': req.user_id, 'type': 'BUY', 'asset': req.symbol,
        'quantity': req.quantity, 'price': current_price, 'timestamp': time.time()
    })

    return {"message": "Purchase successful", "new_balance": new_balance}

@router.post("/sell")
async def sell_stock(req: TradeRequest):
    # 1. Fetch live price
    ticker = yf.Ticker(req.symbol)
    todays_data = ticker.history(period='1d')
    if todays_data.empty:
        raise HTTPException(status_code=404, detail="Stock symbol not found")
    
    current_price = todays_data['Close'].iloc[0]
    total_revenue = current_price * req.quantity

    # 2. Check if user actually owns enough shares to sell
    holding_id = f"{req.user_id}_{req.symbol}"
    holding_ref = db.collection('holdings').document(holding_id)
    holding_doc = holding_ref.get()

    if not holding_doc.exists or holding_doc.to_dict()['quantity'] < req.quantity:
        raise HTTPException(status_code=400, detail="Not enough shares to sell")

    # 3. Add money to wallet & Update holdings
    user_ref = db.collection('users').document(req.user_id)
    user_data = user_ref.get().to_dict()
    new_balance = user_data['cashBalance'] + total_revenue
    user_ref.update({'cashBalance': new_balance})

    old_qty = holding_doc.to_dict()['quantity']
    if old_qty == req.quantity:
        holding_ref.delete() # Sold everything, remove the document
    else:
        holding_ref.update({'quantity': old_qty - req.quantity})

    # 4. Log transaction
    db.collection('transactions').add({
        'userId': req.user_id, 'type': 'SELL', 'asset': req.symbol,
        'quantity': req.quantity, 'price': current_price, 'timestamp': time.time()
    })

    return {"message": "Sale successful", "new_balance": new_balance}