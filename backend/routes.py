from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
import random
from firebase_admin import firestore
from database import db  

router = APIRouter()

# --- 1. Request Models ---
class TradeRequest(BaseModel):
    user_id: str
    symbol: str
    quantity: int

class FDRequest(BaseModel):
    user_id: str
    amount: float
    duration_months: int

class FOTradeRequest(BaseModel):
    user_id: str
    symbol: str
    option_type: str
    lots: int

# --- 2. Helper Functions (WITH HACKATHON FAIL-SAFE) ---
def get_stock_price(symbol: str) -> float:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        
        # STRICT 2-SECOND TIMEOUT: If Yahoo is slow, we abort immediately to prevent freezing!
        response = requests.get(url, headers=headers, timeout=2)
        
        if response.status_code == 200:
            data = response.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            if price and price > 0:
                return float(price)
    except Exception as e:
        print(f"Yahoo API Timeout/Blocked for {symbol}. Activating Mock Data...")

    # =========================================================
    # HACKATHON FAIL-SAFE: MOCK DATA GENERATOR
    # If Yahoo blocks us, we instantly return a realistic fake 
    # price so the UI never gets stuck on "Processing..."
    # =========================================================
    if symbol == "^NSEI": return round(22000.0 + random.uniform(-15.0, 15.0), 2)
    if symbol == "^NSEBANK": return round(46000.0 + random.uniform(-30.0, 30.0), 2)
    
    # Generate a realistic base price using the length of the ticker symbol
    base_price = (len(symbol) * 150.0) + (ord(symbol[0]) * 5)
    mock_price = base_price + random.uniform(-5.0, 5.0)
    
    return round(mock_price, 2)

def get_user_balance(user_id: str):
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")
    return user_ref, user_doc.to_dict().get("cashBalance", 0)

# --- 3. System Routes ---
@router.get("/ping")
def ping():
    return {"status": "Backend is running"}

@router.get("/price/{symbol}")
def get_price(symbol: str):
    price = get_stock_price(symbol)
    return {"symbol": symbol, "price": price}

# --- 4. STOCK ROUTES ---
@router.post("/buy")
def buy_stock(req: TradeRequest):
    try:
        price = get_stock_price(req.symbol)
        total_cost = price * req.quantity
        user_ref, current_balance = get_user_balance(req.user_id)
        if current_balance < total_cost: raise HTTPException(status_code=400, detail="Insufficient balance.")
        user_ref.update({"cashBalance": current_balance - total_cost})
        db.collection("holdings").add({"userId": req.user_id, "symbol": req.symbol, "quantity": req.quantity, "avgPrice": price, "timestamp": firestore.SERVER_TIMESTAMP})
        return {"message": f"Bought {req.quantity} shares of {req.symbol}!"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/sell")
def sell_stock(req: TradeRequest):
    try:
        price = get_stock_price(req.symbol)
        holdings_ref = db.collection("holdings").where("userId", "==", req.user_id).where("symbol", "==", req.symbol).get()
        total_owned = sum([doc.to_dict().get("quantity", 0) for doc in holdings_ref])
        if total_owned < req.quantity: raise HTTPException(status_code=400, detail="Insufficient shares.")
        user_ref, current_balance = get_user_balance(req.user_id)
        user_ref.update({"cashBalance": current_balance + (price * req.quantity)})
        remaining_to_sell = req.quantity
        for doc in holdings_ref:
            doc_data, doc_qty = doc.to_dict(), doc.to_dict().get("quantity", 0)
            if remaining_to_sell <= 0: break
            if doc_qty <= remaining_to_sell:
                db.collection("holdings").document(doc.id).delete()
                remaining_to_sell -= doc_qty
            else:
                db.collection("holdings").document(doc.id).update({"quantity": doc_qty - remaining_to_sell})
                remaining_to_sell = 0
        return {"message": f"Sold {req.quantity} shares of {req.symbol}!"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- 5. MUTUAL FUND ROUTES ---
@router.post("/buy_mf")
def buy_mf(req: TradeRequest):
    try:
        nav = get_stock_price(req.symbol)
        total_cost = nav * req.quantity
        user_ref, current_balance = get_user_balance(req.user_id)
        if current_balance < total_cost: raise HTTPException(status_code=400, detail="Insufficient balance.")
        user_ref.update({"cashBalance": current_balance - total_cost})
        db.collection("mutual_funds").add({"userId": req.user_id, "fundName": req.symbol, "units": req.quantity, "navAtPurchase": nav, "timestamp": firestore.SERVER_TIMESTAMP})
        return {"message": f"Invested {req.quantity} units in {req.symbol}!"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/sell_mf")
def sell_mf(req: TradeRequest):
    try:
        nav = get_stock_price(req.symbol)
        mf_ref = db.collection("mutual_funds").where("userId", "==", req.user_id).where("fundName", "==", req.symbol).get()
        total_owned = sum([doc.to_dict().get("units", 0) for doc in mf_ref])
        if total_owned < req.quantity: raise HTTPException(status_code=400, detail="Insufficient units.")
        user_ref, current_balance = get_user_balance(req.user_id)
        user_ref.update({"cashBalance": current_balance + (nav * req.quantity)})
        remaining_to_sell = req.quantity
        for doc in mf_ref:
            doc_data, doc_qty = doc.to_dict(), doc.to_dict().get("units", 0)
            if remaining_to_sell <= 0: break
            if doc_qty <= remaining_to_sell:
                db.collection("mutual_funds").document(doc.id).delete()
                remaining_to_sell -= doc_qty
            else:
                db.collection("mutual_funds").document(doc.id).update({"units": doc_qty - remaining_to_sell})
                remaining_to_sell = 0
        return {"message": f"Sold {req.quantity} units of {req.symbol}!"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- 6. FUTURES & OPTIONS ROUTES (F/O) ---
@router.post("/buy_fo")
def buy_fo(req: FOTradeRequest):
    try:
        lot_size = 50 if req.symbol == "^NSEI" else 15
        margin_per_lot = 5000 
        total_margin = margin_per_lot * req.lots
        user_ref, current_balance = get_user_balance(req.user_id)
        if current_balance < total_margin: raise HTTPException(status_code=400, detail=f"Insufficient balance. Need ₹{total_margin:,.2f}")
        index_price = get_stock_price(req.symbol)
        user_ref.update({"cashBalance": current_balance - total_margin})
        db.collection("fo_holdings").add({"userId": req.user_id, "symbol": req.symbol, "optionType": req.option_type, "lots": req.lots, "lotSize": lot_size, "entryPrice": index_price, "marginPaid": total_margin, "timestamp": firestore.SERVER_TIMESTAMP})
        return {"message": f"Bought {req.lots} lots of {req.symbol} {req.option_type}!"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/close_fo")
def close_fo(req: FOTradeRequest):
    try:
        current_price = get_stock_price(req.symbol)
        fo_ref = db.collection("fo_holdings").where("userId", "==", req.user_id).where("symbol", "==", req.symbol).where("optionType", "==", req.option_type).get()
        if not fo_ref: raise HTTPException(status_code=400, detail="Position not found.")
        user_ref, current_balance = get_user_balance(req.user_id)
        total_refund = 0
        for doc in fo_ref:
            data = doc.to_dict()
            lots, lot_size, entry, margin = data.get("lots", 0), data.get("lotSize", 50), data.get("entryPrice", 0), data.get("marginPaid", 0)
            if req.option_type == "CE": pnl = (current_price - entry) * (lots * lot_size)
            else: pnl = (entry - current_price) * (lots * lot_size)
            refund = max(0, margin + pnl)
            total_refund += refund
            db.collection("fo_holdings").document(doc.id).delete()
        user_ref.update({"cashBalance": current_balance + total_refund})
        return {"message": f"Closed position. Refunded ₹{total_refund:,.2f}"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- 7. FIXED DEPOSIT ROUTES ---
@router.post("/create_fd")
def create_fd(req: FDRequest):
    try:
        user_ref, current_balance = get_user_balance(req.user_id)
        if current_balance < req.amount: raise HTTPException(status_code=400, detail="Insufficient balance.")
        user_ref.update({"cashBalance": current_balance - req.amount})
        db.collection("fixed_deposits").add({"userId": req.user_id, "amount": req.amount, "durationMonths": req.duration_months, "rate": 0.07, "status": "Active", "timestamp": firestore.SERVER_TIMESTAMP})
        return {"message": "FD created successfully!"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))