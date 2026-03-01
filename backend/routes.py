from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
from firebase_admin import firestore
from database import db  

router = APIRouter()

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

def get_stock_price(symbol: str) -> float:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            if price and price > 0:
                return float(price)
    except Exception as e:
        pass

    raise HTTPException(status_code=503, detail=f"Live market data temporarily unavailable for {symbol}")

def get_user_balance(user_id: str):
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")
    return user_ref, user_doc.to_dict().get("cashBalance", 0)

@router.get("/ping")
def ping():
    return {"status": "Backend is running"}

@router.get("/price/{symbol}")
def get_price(symbol: str):
    price = get_stock_price(symbol)
    return {"symbol": symbol, "price": price}

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
    except HTTPException as he:
        raise he
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
            doc_data = doc.to_dict()
            doc_qty = doc_data.get("quantity", 0)
            if remaining_to_sell <= 0: break
            if doc_qty <= remaining_to_sell:
                db.collection("holdings").document(doc.id).delete()
                remaining_to_sell -= doc_qty
            else:
                db.collection("holdings").document(doc.id).update({"quantity": doc_qty - remaining_to_sell})
                remaining_to_sell = 0
        return {"message": f"Sold {req.quantity} shares of {req.symbol}!"}
    except HTTPException as he:
        raise he
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

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
    except HTTPException as he:
        raise he
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
            doc_data = doc.to_dict()
            doc_qty = doc_data.get("units", 0)
            if remaining_to_sell <= 0: break
            if doc_qty <= remaining_to_sell:
                db.collection("mutual_funds").document(doc.id).delete()
                remaining_to_sell -= doc_qty
            else:
                db.collection("mutual_funds").document(doc.id).update({"units": doc_qty - remaining_to_sell})
                remaining_to_sell = 0
        return {"message": f"Sold {req.quantity} units of {req.symbol}!"}
    except HTTPException as he:
        raise he
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

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
    except HTTPException as he:
        raise he
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
            lots = data.get("lots", 0)
            lot_size = data.get("lotSize", 50)
            entry = data.get("entryPrice", 0)
            margin = data.get("marginPaid", 0)
            if req.option_type == "CE": pnl = (current_price - entry) * (lots * lot_size)
            else: pnl = (entry - current_price) * (lots * lot_size)
            refund = max(0, margin + pnl)
            total_refund += refund
            db.collection("fo_holdings").document(doc.id).delete()
        user_ref.update({"cashBalance": current_balance + total_refund})
        return {"message": f"Closed position. Refunded ₹{total_refund:,.2f}"}
    except HTTPException as he:
        raise he
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_fd")
def create_fd(req: FDRequest):
    try:
        user_ref, current_balance = get_user_balance(req.user_id)
        if current_balance < req.amount: raise HTTPException(status_code=400, detail="Insufficient balance.")
        user_ref.update({"cashBalance": current_balance - req.amount})
        db.collection("fixed_deposits").add({"userId": req.user_id, "amount": req.amount, "durationMonths": req.duration_months, "rate": 0.07, "status": "Active", "timestamp": firestore.SERVER_TIMESTAMP})
        return {"message": "FD created successfully!"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))