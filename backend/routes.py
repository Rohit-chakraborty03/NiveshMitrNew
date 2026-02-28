from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
import firebase_admin
from firebase_admin import credentials, firestore

router = APIRouter()

# 1. Initialize Firebase
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print("Firebase Init Error:", e)

db = firestore.client()

# 2. Request Models
class TradeRequest(BaseModel):
    user_id: str
    symbol: str
    quantity: int

class FDRequest(BaseModel):
    user_id: str
    amount: float
    duration_months: int

# 3. Helper Functions 
def get_stock_price(symbol: str) -> float:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Could not find ticker '{symbol}'.")
            
        data = response.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        
        if not price or price <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid price for '{symbol}'")
            
        return float(price)
        
    except requests.Timeout:
        raise HTTPException(status_code=408, detail="Price fetch timed out. Check your internet connection.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching price for '{symbol}': {str(e)}")

def get_user_balance(user_id: str):
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found. Please log out and log in again.")
    return user_ref, user_doc.to_dict().get("cashBalance", 0)

# 4. Routes
@router.get("/ping")
def ping():
    return {"status": "Backend is running"}

@router.get("/price/{symbol}")
def get_price(symbol: str):
    price = get_stock_price(symbol)
    return {"symbol": symbol, "price": price}

# --- STOCK ROUTES ---
@router.post("/buy")
def buy_stock(req: TradeRequest):
    try:
        price = get_stock_price(req.symbol)
        total_cost = price * req.quantity
        user_ref, current_balance = get_user_balance(req.user_id)
        
        if current_balance < total_cost:
            raise HTTPException(status_code=400, detail=f"Insufficient balance. Need ₹{total_cost:,.2f} but you have ₹{current_balance:,.2f}")
            
        user_ref.update({"cashBalance": current_balance - total_cost})
        
        db.collection("holdings").add({
            "userId": req.user_id,
            "symbol": req.symbol,
            "quantity": req.quantity,
            "avgPrice": price,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        
        return {"message": f"Bought {req.quantity} shares of {req.symbol} at ₹{price:,.2f}! Total: ₹{total_cost:,.2f}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sell")
def sell_stock(req: TradeRequest):
    try:
        price = get_stock_price(req.symbol)
        holdings_ref = db.collection("holdings").where("userId", "==", req.user_id).where("symbol", "==", req.symbol).get()
        
        if not holdings_ref:
            raise HTTPException(status_code=400, detail="You do not own any shares of this stock.")
        
        total_owned = sum([doc.to_dict().get("quantity", 0) for doc in holdings_ref])
        
        if total_owned < req.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient shares. You only own {total_owned} shares.")
        
        revenue = price * req.quantity
        user_ref, current_balance = get_user_balance(req.user_id)
        user_ref.update({"cashBalance": current_balance + revenue})
        
        remaining_to_sell = req.quantity
        for doc in holdings_ref:
            doc_data = doc.to_dict()
            doc_qty = doc_data.get("quantity", 0)
            
            if remaining_to_sell <= 0:
                break
            
            if doc_qty <= remaining_to_sell:
                db.collection("holdings").document(doc.id).delete()
                remaining_to_sell -= doc_qty
            else:
                db.collection("holdings").document(doc.id).update({
                    "quantity": doc_qty - remaining_to_sell
                })
                remaining_to_sell = 0
                
        return {"message": f"Successfully sold {req.quantity} shares of {req.symbol} at ₹{price:,.2f}!"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- MUTUAL FUND ROUTES ---
@router.post("/buy_mf")
def buy_mf(req: TradeRequest):
    try:
        # Now fetches real-time NAV instead of fake 150.0
        nav = get_stock_price(req.symbol)
        total_cost = nav * req.quantity
        user_ref, current_balance = get_user_balance(req.user_id)
        
        if current_balance < total_cost:
            raise HTTPException(status_code=400, detail=f"Insufficient balance. Need ₹{total_cost:,.2f} but you have ₹{current_balance:,.2f}")
            
        user_ref.update({"cashBalance": current_balance - total_cost})
        
        db.collection("mutual_funds").add({
            "userId": req.user_id,
            "fundName": req.symbol,
            "units": req.quantity,
            "navAtPurchase": nav,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        
        return {"message": f"Invested {req.quantity} units in {req.symbol} at NAV ₹{nav:,.2f}! Total: ₹{total_cost:,.2f}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sell_mf")
def sell_mf(req: TradeRequest):
    try:
        nav = get_stock_price(req.symbol)
        mf_ref = db.collection("mutual_funds").where("userId", "==", req.user_id).where("fundName", "==", req.symbol).get()
        
        if not mf_ref:
            raise HTTPException(status_code=400, detail="You do not own any units of this mutual fund.")
        
        total_owned = sum([doc.to_dict().get("units", 0) for doc in mf_ref])
        
        if total_owned < req.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient units. You only own {total_owned} units.")
        
        revenue = nav * req.quantity
        user_ref, current_balance = get_user_balance(req.user_id)
        user_ref.update({"cashBalance": current_balance + revenue})
        
        remaining_to_sell = req.quantity
        for doc in mf_ref:
            doc_data = doc.to_dict()
            doc_qty = doc_data.get("units", 0)
            
            if remaining_to_sell <= 0:
                break
            
            if doc_qty <= remaining_to_sell:
                db.collection("mutual_funds").document(doc.id).delete()
                remaining_to_sell -= doc_qty
            else:
                db.collection("mutual_funds").document(doc.id).update({
                    "units": doc_qty - remaining_to_sell
                })
                remaining_to_sell = 0
                
        return {"message": f"Successfully sold {req.quantity} units of {req.symbol} at ₹{nav:,.2f}!"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- FD ROUTES ---
@router.post("/create_fd")
def create_fd(req: FDRequest):
    try:
        user_ref, current_balance = get_user_balance(req.user_id)
        
        if current_balance < req.amount:
            raise HTTPException(status_code=400, detail=f"Insufficient balance. Need ₹{req.amount:,.2f} but you have ₹{current_balance:,.2f}")
            
        user_ref.update({"cashBalance": current_balance - req.amount})
        
        db.collection("fixed_deposits").add({
            "userId": req.user_id,
            "amount": req.amount,
            "durationMonths": req.duration_months,
            "rate": 0.07,
            "status": "Active",
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        
        return {"message": f"FD of ₹{req.amount:,.2f} for {req.duration_months} months created at 7% p.a.!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))