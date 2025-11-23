from typing import List
import struct

class Int16:
    def __init__(self, number:int|bytes) -> bytes|int:
        if isinstance(number, int):
            if number>32767 or number<-32768:
                raise Exception('outside range')
            self.number = number
        elif isinstance(number, bytes):
            num = struct.unpack('>h', number)[0]
            if num>32767 or num<-32768:
                raise Exception('outside range')
            self.number = num 
    def __call__(self) -> int:
        return self.number
    def bytes(self) -> bytes:
        return struct.pack('>h', self.__call__())
    
def int16(number:int|bytes) -> bytes|int:
    ''' convert int to bytes and backwards '''
    num=Int16(number)
    if isinstance(number, int):
        return num.bytes()
    elif isinstance(number, bytes):
        return num()    
    else:
        raise Exception(f'invalid type: {type(number)}')
    


def ignore_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            return None
    return wrapper



def pack_rreq(broadcast_id:int, source_id:str, destination_id:str, path:List[str], hop_count, header="RREQ"):
    '''
    packet struct ( [a-b) ):
    0-4 header
    4-6 broadcast id
    6-8 length of source id (losi)
    8-(8+losi) source id, bytes
    (8+losi)-(10+losi) length of destination id (lodi)
    (10+losi)-(10+losi+lodi) destination id, bytes 
    (10+losi+lodi = ps)-(ps+2) path len (plt)
    (2+ps)-(4+ps) path[0] len (pl[0])
    (4+ps)-(4+ps+pl[0] = pe[0]) path[0]
    (pe[0])-(pe[0]+2) path[1] len(pl[1])
    (pe[0]+2)-(pe[0]+2+pl[1]) path[1]
    ...
    (pe[-1])-(pe[-1]+2) hop_count
    '''
    packet = header.encode('ascii')+int16(broadcast_id) + int16(len(source_id)) + source_id.encode("ascii") + int16(len(destination_id)) + \
        destination_id.encode("ascii")
    packet+=int16(len(path))
    for i in path:
        packet+=int16(len(i))+i.encode("ascii")
    packet+=int16(hop_count)
    return packet

def unpack_rreq(packet):
    res = {
        "header": packet[:4].decode('ascii'),
        "broadcast_id":int16(packet[4:6]),
        "source_id": packet[8:8+(losi:=int16(packet[6:8]))].decode('ascii'),
        "destination_id": packet[10+losi:(ps:=(10+losi+int16(packet[8+losi:10+losi])))].decode('ascii'),
    }
    plt = int16(packet[ps:ps+2])
    pe = ps+2
    print(pe, plt)
    res['path'] = []
    for i in range(plt):
        res['path'] = res.get('path', []) + [packet[pe+2:(pe_new:=pe+2+int16(packet[pe:pe+2]))].decode('ascii')]
        pe = pe_new
    res['hop_count'] = int16(packet[pe:pe+2])
    return res

def pack_rrep(*args):
    '''same as rreq but withoud broadcast id'''
    args[0]=-1
    return pack_rreq(*args, header='RREP')

def unpack_rrep(packet):
    '''same as rreq but without broadcast id'''
    res = unpack_rreq(packet)
    del res['broadcast_id']
    return res

def flat(serv, path=[], servers=[]):
    servers.append((serv, path))
    for ind, c in enumerate(serv.get('children', [])):
        flat(c, path=path+[ind])
    return servers

# packet = pack_rreq(
#     Int16(228),
#     "source",
#     "dest",
#     ["source", "dest"],
#     2
#     )

# print(packet)
# print(unpack_rreq(packet))