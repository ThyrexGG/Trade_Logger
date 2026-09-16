import asyncio
import json
import websockets
import pytest

# This file was gitignored at root (`/test_*.py`) until the 2026-09-16
# cleanup moved it into tests/ properly -- which is the first time it's ever
# actually been collected. Doing so surfaced a real, pre-existing gap:
# pytest-asyncio isn't installed, so `@pytest.mark.asyncio` can't run this at
# all (unrelated to the reorg itself). It also targets ws://localhost:8000,
# the legacy Streamlit-era server's port, not the current api.main:app
# (port 8010) -- so even with the plugin installed, this needs a decision
# (install pytest-asyncio? repoint the port? both?) before it's worth
# un-skipping, not a silent fix bundled into a file move.
@pytest.mark.skip(reason="pytest-asyncio not installed, and this targets the legacy port-8000 server, not api.main:app")
@pytest.mark.asyncio
async def test_websocket_stream():
    """Validates live tick websocket payload format if server is running."""
    try:
        async with websockets.connect("ws://127.0.0.1:8000/ws/live_ticks/EURUSD", close_timeout=2) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(msg)
            assert "symbol" in data
            assert data["symbol"] == "EURUSD"
    except Exception:
        pytest.skip("FastAPI websocket server not running on localhost:8000")
