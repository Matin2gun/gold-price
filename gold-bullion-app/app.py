"""
FastAPI Server & Real-time Bullion Dashboard Engine
Runs an autonomous 30-second data collection loop, serves REST and WebSocket APIs,
and renders the high-performance Persian financial dashboard.
"""

import os
import json
import time
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Set, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from collectors import TradingViewCollector, TGJUCollector, CalculationEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GoldApp")

app = FastAPI(
    title="24k Gold Bullion Real-time Terminal (Iran)",
    description="سیستم محاسبه هوشمند و بی‌درنگ ارزش واقعی و حباب شمش طلا ۲۴ عیار ایران با به‌روزرسانی ۳۰ ثانیه‌ای",
    version="2.0.0"
)

# Enable CORS for all domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# State Management
REFRESH_INTERVAL_SECONDS = 30
tv_collector = TradingViewCollector()
tgju_collector = TGJUCollector()

current_state: Dict[str, Any] = {}
price_history: List[Dict[str, Any]] = []
active_connections: Set[WebSocket] = set()
last_update_timestamp = 0.0
next_update_timestamp = 0.0
loop_running = False


class CalculateRequest(BaseModel):
    weight_grams: Optional[float] = None
    budget_toman: Optional[float] = None
    purity: Optional[float] = 0.9999


async def update_market_data():
    """Fetch new market data, calculate bullion metrics, and broadcast."""
    global current_state, price_history, last_update_timestamp, next_update_timestamp
    try:
        # Fetch from TradingView and TGJU concurrently
        tv_task = asyncio.create_task(tv_collector.get_quotes())
        tgju_task = asyncio.create_task(tgju_collector.get_rates())
        tv_data, tgju_data = await asyncio.gather(tv_task, tgju_task, return_exceptions=False)

        # Run mathematical analysis engine
        metrics = CalculationEngine.calculate(tv_data, tgju_data)
        metrics["interval_seconds"] = REFRESH_INTERVAL_SECONDS
        last_update_timestamp = time.time()
        next_update_timestamp = last_update_timestamp + REFRESH_INTERVAL_SECONDS
        metrics["next_update_timestamp"] = next_update_timestamp
        current_state = metrics

        # Append to history buffer (max 120 points = 1 hour)
        history_point = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "timestamp": last_update_timestamp,
            "fair_24k": metrics["bullion_24k"]["fair_per_gram_toman"],
            "market_24k": metrics["bullion_24k"]["market_per_gram_toman"],
            "bubble_pct": metrics["bullion_24k"]["bubble_pct"],
            "gold_ounce": metrics["inputs"]["gold_ounce_usd"],
            "usd_toman": metrics["inputs"]["usd_toman"]
        }
        price_history.append(history_point)
        if len(price_history) > 120:
            price_history.pop(0)

        # Broadcast via WebSocket to all connected clients
        if active_connections:
            message = json.dumps({"type": "tick", "data": current_state})
            disconnected = set()
            for ws in active_connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.add(ws)
            for dead_ws in disconnected:
                active_connections.discard(dead_ws)

        logger.info(
            f"30s Tick: Ounce=${metrics['inputs']['gold_ounce_usd']} | "
            f"USD={metrics['inputs']['usd_toman']:,.0f} T | "
            f"Fair 24k={metrics['bullion_24k']['fair_per_gram_toman']:,.0f} T | "
            f"Bubble={metrics['bullion_24k']['bubble_pct']}% | "
            f"Clients={len(active_connections)}"
        )
    except Exception as e:
        logger.error(f"Error in update_market_data: {e}", exc_info=True)


async def background_scheduler():
    """Autonomous loop updating data precisely every 30 seconds."""
    global loop_running
    loop_running = True
    # Initial immediate fetch
    await update_market_data()

    while loop_running:
        try:
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
            await update_market_data()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
            await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    """Start background 30s scheduler on FastAPI startup."""
    asyncio.create_task(background_scheduler())


# API Endpoints
@app.get("/api/rates")
async def get_rates():
    """Return latest calculated 24k bullion rates and market comparisons."""
    if not current_state:
        await update_market_data()
    # Add dynamic remaining countdown seconds
    res = dict(current_state)
    res["countdown_seconds"] = max(0, int(next_update_timestamp - time.time()))
    return JSONResponse(content=res)


@app.get("/api/history")
async def get_history():
    """Return historical trend points for interactive Chart.js visualization."""
    return JSONResponse(content={"history": price_history})


@app.post("/api/refresh")
async def force_refresh():
    """Trigger an immediate manual refresh cycle without waiting for the 30s timer."""
    await update_market_data()
    return JSONResponse(content={"status": "ok", "message": "Rates refreshed", "data": current_state})


@app.post("/api/calculate")
async def calculate_custom(req: CalculateRequest):
    """
    Custom bullion calculator:
    Calculate fair price, market cost, and bubble for any custom weight or budget.
    """
    if not current_state:
        await update_market_data()

    fair_gram = current_state["bullion_24k"]["fair_per_gram_toman"]
    market_gram = current_state["bullion_24k"]["market_per_gram_toman"]

    if req.weight_grams and req.weight_grams > 0:
        w = req.weight_grams
        fair_tot = w * fair_gram
        market_tot = w * market_gram
        bubble_tot = market_tot - fair_tot
        return {
            "weight_grams": w,
            "fair_total_toman": round(fair_tot),
            "fair_total_rial": round(fair_tot * 10),
            "market_total_toman": round(market_tot),
            "market_total_rial": round(market_tot * 10),
            "bubble_total_toman": round(bubble_tot),
            "bubble_pct": round((bubble_tot / fair_tot) * 100, 2) if fair_tot > 0 else 0
        }
    elif req.budget_toman and req.budget_toman > 0:
        b = req.budget_toman
        affordable_grams_fair = b / fair_gram if fair_gram > 0 else 0
        affordable_grams_market = b / market_gram if market_gram > 0 else 0
        return {
            "budget_toman": b,
            "purchasable_grams_fair": round(affordable_grams_fair, 3),
            "purchasable_grams_market": round(affordable_grams_market, 3),
            "purchasable_mithqal_market": round(affordable_grams_market / 4.6083, 3)
        }
    else:
        raise HTTPException(status_code=400, detail="Provide weight_grams or budget_toman")


@app.get("/api/health")
async def health_check():
    """Healthcheck endpoint for Docker and cloud orchestrators."""
    return {
        "status": "healthy",
        "loop_running": loop_running,
        "active_ws_clients": len(active_connections),
        "last_update": last_update_timestamp,
        "seconds_since_last_update": round(time.time() - last_update_timestamp, 1)
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for real-time 30-second ticks."""
    await websocket.accept()
    active_connections.add(websocket)
    try:
        # Send current state immediately on connect
        if current_state:
            res = dict(current_state)
            res["countdown_seconds"] = max(0, int(next_update_timestamp - time.time()))
            await websocket.send_text(json.dumps({"type": "init", "data": res}))

        while True:
            # Keep connection alive & handle incoming pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "time": time.time()}))
            elif data == "refresh":
                await update_market_data()
    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception:
        active_connections.discard(websocket)


# Mount static directory for frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the single-page bullion dashboard."""
    index_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>داشبورد شمش طلا ۲۴ عیار در حال بارگذاری است...</h1>")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"🚀 Bullion Dashboard running at http://localhost:{port}")
    uvicorn.run("app:app", host=host, port=port, reload=False)
