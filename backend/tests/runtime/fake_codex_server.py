"""A deterministic native-protocol peer; never contacts a model."""
import json
import os
import select
import sys
import time
from pathlib import Path

active = None
scenario = ''
last_noise = 0.0
input_buffer = b''
held_start = None
thread_id = 'thread-' + Path.cwd().name

def send(message):
    print(json.dumps(message), flush=True)

def event(method, **params):
    send({'method': method, 'params': {'threadId': thread_id, **params}})

def complete(status='completed'):
    event('item/completed', turnId=active, item={'id':'answer','type':'agentMessage','text':Path.cwd().name})
    event('turn/completed', turn={'id':active,'status':status,'error':None})

while True:
    if b'\n' not in input_buffer:
        ready, _, _ = select.select([sys.stdin], [], [], 0.005)
        if not ready:
            if active and scenario == 'chatter' and time.monotonic()-last_noise > 0.005:
                event('item/reasoning/textDelta', turnId=active, delta='Still thinking')
                last_noise=time.monotonic()
            continue
        chunk=os.read(sys.stdin.fileno(), 8192)
        if not chunk:
            break
        input_buffer+=chunk
        continue
    line, _, input_buffer=input_buffer.partition(b'\n')
    request=json.loads(line)
    with Path('protocol.jsonl').open('a') as out:
        out.write(json.dumps(request)+'\n')
    if 'method' not in request:
        if request.get('id')=='approval-1': complete()
        continue
    method=request['method']; params=request.get('params',{}); result={}
    if method=='initialize': result={'userAgent':'fake'}
    elif method=='account/read': result={'account':{'type': 'apiKey' if Path('api-key-account').exists() else 'chatgpt'}}
    elif method in ('thread/start','thread/resume'): result={'thread':{'id':thread_id},'modelProvider':'openai'}
    elif method=='turn/start':
        active='turn-'+str(request['id']); scenario=params['input'][0]['text']
        result={'turn':{'id':active,'status':'inProgress','items':[]}}
        if scenario=='delayed-start':
            held_start={'id':request['id'],'result':result}
            continue
    elif method=='test/releaseStart':
        send(held_start);held_start=None
        result={}
    elif method=='turn/steer': result={'turnId':active}
    elif method=='turn/interrupt':
        if scenario in ('tools','tokens'):
            send({'id':request['id'],'error':{'code':-32600,'message':'Turn already completed'}})
            continue
        result={}
    if 'id' in request: send({'id':request['id'],'result':result})
    if method=='turn/start':
        if scenario=='other-thread':
            send({'method':'turn/completed','params':{'threadId':'unrelated','turn':{'id':active,'status':'completed'}}})
            complete()
        elif scenario=='tools':
            for n in range(4):
                item={'id':str(n),'type':'commandExecution','command':'echo hello','status':'completed'}
                event('item/started',turnId=active,item=item)
                event('item/started',turnId=active,item=item)  # duplicate delivery
                event('item/completed',turnId=active,item=item)
            complete()
        elif scenario=='tokens':
            event('thread/tokenUsage/updated',turnId=active,tokenUsage={'total':{'totalTokens':101}})
            complete()
        elif scenario=='approval':
            send({'id':'approval-1','method':'item/commandExecution/requestApproval','params':{'threadId':thread_id,'turnId':active,'command':'forbidden'}})
        elif scenario in ('hang','chatter','steer'):
            event('item/started',turnId=active,item={'id':'work','type':'reasoning'})
        elif scenario=='failed': complete('failed')
        else: complete()
    elif method=='turn/steer':
        complete()
    elif method=='turn/interrupt':
        complete('interrupted');active=None
