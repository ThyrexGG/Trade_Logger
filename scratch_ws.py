import asyncio; import websockets; async def test(): async with websockets.connect('ws://localhost:8000/ws/live_ticks/EURUSD') as ws: print(await ws.recv()); asyncio.run(test())
