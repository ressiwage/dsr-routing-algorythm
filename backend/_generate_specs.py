import json, random
from random_word import RandomWords

r=RandomWords()
port = 7999

def _make_server(id, num_children, restriction):
    global port
    port+=1
    serv = {
        "name": id,
        "port": port,
        "cpu": random.randint(1,4)*2,
        "children": [_make_server(r.get_random_word(), min(random.randint(0, 3), restriction), restriction-1) for i in range(num_children)]
    }
    return serv

data = _make_server('root', 2, 3)

servers = []
def flat(serv, path=[]):
    global servers
    servers.append((serv, path))
    for ind, c in enumerate(serv.get('children', [])):
        flat(c, path=path+[ind])
flat(data)
print(servers)
def get_serv_indexes(serv, inds):
    for i in inds:
        serv = serv['children'][i]
    return serv
for i in range(10):
    s1 = random.choice(servers)
    s2 = random.choice(servers)
    if s1[0]['name']!=s2[0]['name']:
        serv =get_serv_indexes(data, s1[1]) 
        # print(serv, 123)
        serv['children']= serv.get('children', [] ) + [{'port':s2[0]['port'], 'name':s2[0]['name']}]
print(data)
json.dump(data, open("topology.json", 'w+'), indent=2)