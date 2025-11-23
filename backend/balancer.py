from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import websocket
from pydantic import BaseModel
import json, heapq
import asyncio
import argparse, sys, threading, time, requests
from utils import ignore_exception

app = FastAPI(title="Socket Message Handler")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "http://localhost:8001"],  # Укажите точный origin React приложения
    allow_credentials=True,
    allow_methods=["*"],  # Или конкретные методы: ["GET", "POST", "PUT", "DELETE"]
    allow_headers=["*"],  # Или конкретные заголовки
)
config = json.load(open('config.json', 'r'))


def thread():
    # global app
    # while True:
    #     # sync_sockets_send(f"http://localhost:{8000}/ws", {'route':'echo', 'purpose':'rebalance'}, 'http://localhost:7999/ws')
    #     sync_sockets_send_bytes(f"http://localhost:{8000}/ws", bytes([123,ord('a'),123]))
    #     time.sleep(config['rebalance_interval'])
    pass
        

class MessageRequest(BaseModel):
    """Модель для отправки сообщения через REST API"""
    message: str
    target_url: str = "ws://localhost:8000/ws"

# Хранилище для последнего полученного сообщения
last_message = None

@app.on_event("startup")
async def startup_event():
    app.state.load = 0
    threading.Thread(target=thread).start()

clients = []  # клиенты (браузеры)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint для получения сырых пакетов данных.
    Принимает сообщения и сохраняет их для последующего просмотра через REST API.
    """
    await websocket.accept()
    clients.append(websocket)
    global last_message
    
    try:
        while True:
            data = await websocket.receive_text()
            last_message = data
            print(f"Получено сообщение: {data}")
            disconnected = []


            for client in clients:
                print(client)
                if client is not websocket:  # не отсылаем обратно источнику
                    try:
                        await client.send_text(data)
                    except Exception:
                        # если клиент уже отключился — добавляем в список на удаление
                        disconnected.append(client)
            for d in disconnected:
                if d in clients:
                    clients.remove(d)

            
    except WebSocketDisconnect:
        print("Клиент отключился")

        


sockets = {}

async def sockets_send(url: str, payload:dict, receiver: str):
    url = url.replace("http:","ws:")
    import websockets
    payload['sender'] = receiver #f'http://localhost:{7999}/ws'
    try:
        async with websockets.connect(url) as websocket:
            await websocket.send(json.dumps(payload))
            return {"status": "success", "message": "Сообщение отправлено"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def sync_sockets_send(url: str, payload: dict, receiver: str):
    url = url.replace("http:", "ws:")
    payload['sender'] = receiver
    
    try:
        ws = websocket.create_connection(url)
        ws.send(json.dumps(payload))
        ws.close()
        return {"status": "success", "message": "Сообщение отправлено"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
def sync_sockets_send_bytes(url: str, payload: bytes):
    url = url.replace("http:", "ws:")
    
    try:
        ws = websocket.create_connection(url)
        ws.send(payload, websocket.ABNF.OPCODE_BINARY)
        ws.close()
        return {"status": "success", "message": "Сообщение отправлено"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get('/avg-disbalance')
async def avg_disbalance():
    global cpu_total, load_total
    cpu_total = 0
    load_total = 0
    def rec(port):
        global cpu_total, load_total
        try:
            r = requests.get(f'http://localhost:{port}/specs')
        except:
            return
        if not r.ok:
            return
        data = r.json()
        cpu_total+=data['cpu']
        load_total+=data['load']
        for port in data['children']:
            rec(port)
    rec(8000)
    return {'load':load_total/cpu_total}



@app.get('/echo_ws')
async def route_echo(receiver: str):
    return await sockets_send(f"http://localhost:{8000}/ws", {'route':'echo'}, receiver)

@app.get('/finn_ws')
async def route_echo():
    return await sockets_send(f"http://localhost:{8000}/ws", {'route':'finn', 'inc': [], 'ninc':[]}, '')


    

if __name__ == "__main__":
    # Use args.config_path to load configuration or perform other actions
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7999)
