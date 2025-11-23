from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
import json
import queue
import asyncio, random
import argparse, sys, threading, time, requests, websocket
from utils import ignore_exception, flat, pack_rrep, pack_rreq, unpack_rrep, unpack_rreq, Int16

app = FastAPI(title="Socket Message Handler")
config = json.load(open('config.json', 'r'))
topology = json.load(open('topology.json', 'r'))
load_queue = queue.Queue()
message_back = None
parent = None
finn_messages_got=0

def thread():
    global app
    while True:
        if app.state.load>=app.state.cpu:
            print("overload")
        time.sleep(1)

load_lock = threading.Lock()

def task_worker():
    global app, load_queue
    while True:
        if random.randint(0,10)==10:
            serv_to_communicate = app.state.name
            while serv_to_communicate==app.state.name:
                serv_to_communicate = random.choice(flat(topology))[0]['name']
            print(f"server {app.state.name} decided to communicate with {serv_to_communicate}")
            sync_sockets_send_bytes(f"ws://localhost:{app.state.port}/ws", pack_rreq(
                random.randint(-500, 500),
                app.state.name,
                serv_to_communicate,
                [],
                0,  
            ))
        # time.sleep(1)
        time.sleep(config['task_time'])

class MessageRequest(BaseModel):
    """Модель для отправки сообщения через REST API"""
    message: str
    target_url: str = "ws://localhost:8000/ws"

class Specs(BaseModel):
    load: int
    cpu: int
    children: list[int]
    name: str
    port: int

# Хранилище для последнего полученного сообщения
last_message = None

@app.on_event("startup")
async def startup_event():
    app.state.load = 0
    threading.Thread(target=task_worker).start()

async def sockets_send(url: str, payload:dict):
    url = url.replace('http:', 'ws:')
    print(f'sending{url}{json.dumps(payload)}')
    import websockets
    payload['sender'] = f'http://localhost:{app.state.port}/ws'
    try:
        async with websockets.connect(url) as websocket:
            await websocket.send(json.dumps(payload))
            return {"status": "success", "message": "Сообщение отправлено"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
async def sockets_send_bytes(url: str, payload:bytes):
    url = url.replace('http:', 'ws:')
    import websockets
    try:
        async with websockets.connect(url) as websocket:
            await websocket.send(payload)
            return {"status": "success", "message": "Сообщение отправлено"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def finn_action(app):
    print(f"print from {app.state.name}: got finn message")
    app.state.load+=1
    load_queue.put(1)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint для получения сырых пакетов данных.
    Принимает сообщения и сохраняет их для последующего просмотра через REST API.
    """
    await websocket.accept()
    global last_message, parent, message_back, finn_messages_got
    
    try:
        while True:
            # print(await websocket.receive())
            message = await websocket.receive()
            # print(message)
            if 'text' in message:
                data = json.loads(message['text'])
                # data = json.loads(await websocket.receive_text())
                # print("received", data)
                if data['route'] == 'echo':
                    parent=data['sender']
                    await sockets_send(parent, {"route":"echo_back", "payload": json.load(open('topology.json')), "purpose":data.get('purpose', '')})
                    return
                    parent = data['sender']
                    for port in app.state.children:
                        await sockets_send(f"http://localhost:{port}/ws", {"route":"echo", "payload":get_specs(), "purpose":data.get('purpose', '')})
                    if len(app.state.children)==0:
                        await sockets_send(parent, {"route":"echo_back", "payload":get_specs(), "purpose":data.get('purpose', '')})
                if data['route'] == 'echo_back':
                    if message_back is None:
                        message_back = get_specs()
                        message_back['children'] = []
                        
                    message_back['children'].append(data['payload'])
                    message_back['children'] = sorted(message_back['children'], key = lambda x:x['name'])
                    if len(message_back['children'])==len(app.state.children):
                        await sockets_send(parent, {"route":"echo_back", "payload":message_back, 'purpose':data.get('purpose', '')})
                        message_back=None
                last_message = data
                print(f"Получено сообщение: {data}")

                if data['route'] == 'finn':
                    
                    app.state.inc.update(data['inc'])
                    app.state.ninc.update(data['ninc'])

                    finn_messages_got += 1 
                    if finn_messages_got>=app.state.num_parents: #>= in case if we sent message to root node with zero parents
                        app.state.ninc.add(app.state.port)

                        if app.state.inc==app.state.ninc:
                            finn_action(app)
                        try:
                        
                            for port in app.state.children:
                                await sockets_send(f"http://localhost:{port}/ws", {
                                    "route":"finn", 
                                    "inc":list(app.state.inc),
                                    "ninc": list(app.state.ninc)
                                    })
                        finally:
                            #сбрасываем настройки
                            app.state.inc = {app.state.port}
                            app.state.ninc = set()
                            finn_messages_got=0
            elif "bytes" in message:
                data = message['bytes']
                head = data[:4].decode('ascii')
                if head=='RREQ':
                    msg = unpack_rreq(data)
                    # если известен оптимальный путь
                    if (optipath:=app.state.paths.get(msg['destination_id'])):
                        # возвращаем его
                        await sockets_send_bytes(f"http://localhost:{msg['path'][0]}/ws", pack_rreq(
                            msg['broadcast_id'],
                            msg['source_id'],
                            msg['destination_id'],
                            msg['path']+optipath,
                            msg['hop_count']+len(optipath),
                            header='RREP'
                        ))
                        return
                    # если есть повторы то мы зашли в тупик
                    if len(set(msg['path']))!=len(msg['path']):
                        await sockets_send_bytes(f"http://localhost:{msg['path'][0]}/ws", pack_rreq(
                            msg['broadcast_id'],
                            msg['source_id'],
                            msg['destination_id'],
                            msg['path'],
                            -1,
                            header='RERR'
                        ))
                        return
                    msg['path'].append(str(app.state.port))
                    # если мы в точке назначения возвращаем RREP
                    print(app.state.name, msg['destination_id'])
                    if app.state.name == msg['destination_id']:
                        await sockets_send_bytes(f"http://localhost:{msg['path'][0]}/ws", pack_rreq(
                            msg['broadcast_id'],
                            msg['source_id'],
                            msg['destination_id'],
                            msg['path'],
                            msg['hop_count']+1,
                            header='RREP'
                        ))
                        return
                    #стандартное поведение: шлем RREQ дальше
                    if len(app.state.children)==0:
                        await sockets_send_bytes(f"http://localhost:{msg['path'][0]}/ws", pack_rreq(
                            msg['broadcast_id'],
                            msg['source_id'],
                            msg['destination_id'],
                            msg['path'],
                            -1,
                            header='RERR'
                        ))
                        return
                    for port in app.state.children:
                        await sockets_send_bytes(f"http://localhost:{port}/ws", pack_rreq(
                            msg['broadcast_id'],
                            msg['source_id'],
                            msg['destination_id'],
                            msg['path'],
                            msg['hop_count']+1,
                            header='RREQ'
                        ))

                elif head=='RERR':
                    msg = unpack_rreq(data)
                    print(f"oh no, {app.state.name} can not communicate with {msg['destination_id']} through path {'->'.join(msg['path'])}")

                elif head=='RREP':
                    msg=unpack_rreq(data)
                    print(f"got rrep with {msg}")
                    # если этот путь оптимальный, то меняем им тот что в кеше
                    if (did:=app.state.paths.get(msg['destination_id'])) is not None and len(did)>msg['path']:
                        await sockets_send("http://localhost:7999/ws", {"route":"new_path", "payload":{"new":msg['path'], "old":app.state.paths[msg['destination_id']]}})
                        app.state.paths[msg['destination_id']] = msg['path']
                        print(app.state.paths)
                    elif did is None:
                        await sockets_send("http://localhost:7999/ws", {"route":"new_path", "payload":{"new":msg['path']}})
    

    except (WebSocketDisconnect, RuntimeError) as e:
        print("Клиент отключился", str(e))


    
@app.get('/add_task')
async def add_task(background_tasks: BackgroundTasks):
    app.state.load+=1
    load_queue.put(1)
    # threading.Thread(target=start_task).start()
    return {"status":"ok"}

@app.post('/rebalance')
async def add_task(target:int):
    global load_lock
    requests.get(f"http://localhost:{target}/add_task")
    with load_lock:
        try:
            load_queue.get(block=False)
            app.state.load-=1
        except:
            return {"status":"error"}
        
    if app.state.load<1:
        return {"status":"error"}
    return {"status":"ok"}

def sync_sockets_send_bytes(url: str, payload: bytes):
    
    url = url.replace("http:", "ws:")
    
    try:
        ws = websocket.create_connection(url)
        ws.send(payload, websocket.ABNF.OPCODE_BINARY)
        ws.close()
        return {"status": "success", "message": "Сообщение отправлено"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# @app.get('/echo')
# async def echo():
#     info = get_specs()
#     del info['children']
#     if len(app.state.children)>0:
#         for port in app.state.children:
#             r = ignore_exception(requests.get)(f'http://localhost:{port}/echo')
#             if r is not None:
#                 info['children'] = info.get('children', [])+[r.json()]
#     return info

def get_specs():
    return {
        "name": app.state.name,
        "load":app.state.load,
        "cpu":app.state.cpu,
        "children": app.state.children,
        "port": app.state.port
        }
@app.get('/specs')
async def specs()->Specs:
    return get_specs()

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="set your params")
    parser.add_argument("--cpu", type=int, default=4, help="num cpu", required=True)
    parser.add_argument("--num_parents", type=int, help="how much parents does the process have", required=True)
    parser.add_argument("--port", type=int, default=8000, help="which port to run on", required=True)
    parser.add_argument('--children', nargs='+', type=int, help='ports of children processes', default=None)
    parser.add_argument('--name', type=str, help='name of server', required=True)
    args = parser.parse_args()
    app.state.cpu = args.cpu
    app.state.port = args.port
    app.state.children = args.children
    if app.state.children is None:
        app.state.children=[]
    app.state.name = args.name
    app.state.num_parents=args.num_parents
    app.state.inc = {args.port}
    app.state.ninc = set()
    app.state.paths={}
    # Use args.config_path to load configuration or perform other actions
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=args.port)
