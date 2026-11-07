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
host_step = 0
thread_id = 'thread-' + Path.cwd().name

def send(message):
    """Emit one complete native protocol frame to the owning test process."""
    print(json.dumps(message), flush=True)

def event(method, **params):
    """Associate a synthetic observation with this real child peer's thread."""
    send({'method': method, 'params': {'threadId': thread_id, **params}})

def complete(status='completed'):
    """Report an answer and terminal turn while leaving product acceptance to its owner."""
    event('item/completed', turnId=active, item={'id':'answer','type':'agentMessage','text':Path.cwd().name})
    event('turn/completed', turn={'id':active,'status':status,'error':None})

def host_request():
    """Send a real host RPC with optional absent, duplicate or reordered lifecycle observations; all effects remain owned by the test callback."""
    item={'id':f'call-{host_step}','type':'dynamicToolCall','tool':'effect','arguments':{'number':host_step}}
    if scenario=='host-duplicate-start':
        event('item/started',turnId=active,item=item)
        event('item/started',turnId=active,item=item)
    if scenario=='host-kind-reuse':
        event('item/started',turnId=active,item={**item,'type':'commandExecution'})
    params={'threadId':thread_id,'turnId':active,'callId':item['id'],'tool':'effect','arguments':item['arguments']}
    if scenario=='host-no-callid':params.pop('callId')
    if scenario=='host-no-turnid':params.pop('turnId')
    send({'id':f'host-rpc-{host_step}','method':'item/tool/call','params':params})

while True:
    if b'\n' not in input_buffer:
        ready, _, _ = select.select([sys.stdin], [], [], 0.005)
        if not ready:
            if active and scenario == 'chatter' and time.monotonic()-last_noise > 0.005:
                event('item/reasoning/textDelta', turnId=active, delta='Still thinking')
                last_noise=time.monotonic()
            if active and scenario=='duplicate-completions' and time.monotonic()-last_noise>0.005:
                event('item/completed',turnId=active,item={'id':'same-work','type':'commandExecution'})
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
        if request.get('id') in ('approval-1', 'budget-1'): complete()
        elif str(request.get('id','')).startswith('host-rpc-'):
            if scenario=='host-duplicate-request':
                send({'id':'duplicate-rpc','method':'item/tool/call','params':{'threadId':thread_id,'turnId':active,'callId':f'call-{host_step}','tool':'effect','arguments':{'number':999}}})
                continue
            item={'id':f'call-{host_step}','type':'dynamicToolCall','tool':'effect','arguments':{'number':host_step}}
            if scenario in ('host-duplicate-start','host-late-start'):
                event('item/completed',turnId=active,item=item)
                event('item/completed',turnId=active,item=item)
            if scenario=='host-late-start':
                event('item/started',turnId=active,item=item)
                event('item/started',turnId=active,item=item)
            host_step+=1
            if host_step<4:host_request()
            else:complete()
        elif request.get('id')=='duplicate-rpc':complete()
        continue
    method=request['method']; params=request.get('params',{}); result={}
    if method=='initialize': result={'userAgent':'fake'}
    elif method=='test/pid': result={'pid':os.getpid()}
    elif method=='account/read': result={'account':{'type': 'apiKey' if Path('api-key-account').exists() else 'chatgpt'}}
    elif method in ('thread/start','thread/resume'): result={'thread':{'id':thread_id},'modelProvider':'openai'}
    elif method=='turn/start':
        active='turn-'+str(request['id']); scenario=params['input'][0]['text']
        host_step=0
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
        if scenario.startswith('host-'):
            host_request()
        elif scenario=='completed-tools':
            for n in range(4):
                event('item/completed',turnId=active,item={'id':f'native-{n}','type':'commandExecution'})
                event('item/completed',turnId=active,item={'id':f'native-{n}','type':'commandExecution'})
            complete()
        elif scenario=='other-thread':
            send({'method':'turn/completed','params':{'threadId':'unrelated','turn':{'id':active,'status':'completed'}}})
            complete()
        elif scenario in ('tools','search-tools'):
            for n in range(4):
                item={'id':str(n),'type':'webSearch' if scenario=='search-tools' else 'commandExecution','command':'echo hello','status':'completed'}
                event('item/started',turnId=active,item=item)
                event('item/started',turnId=active,item=item)  # duplicate delivery
                event('item/completed',turnId=active,item=item)
            complete()
        elif scenario in ('budget-host', 'budget-host-unknown', 'budget-large-context', 'budget-small-context'):
            for n in range(3):
                item={'id':str(n),'type':'dynamicToolCall','tool':'source','arguments':{}}
                event('item/started',turnId=active,item=item)
                event('item/started',turnId=active,item=item)
                event('item/completed',turnId=active,item=item)
            if scenario == 'budget-host':
                event('thread/tokenUsage/updated',turnId=active,tokenUsage={'total':{'totalTokens':80}})
            elif scenario in ('budget-large-context', 'budget-small-context'):
                # The next inference has already requested a tool while its usage
                # is still unreported, as in the retained planning regression.
                for total in ([25473, 25473] if scenario == 'budget-large-context' else [1000, 2000]):
                    event('thread/tokenUsage/updated',turnId=active,tokenUsage={'total':{'totalTokens':total}})
            send({'id':'budget-1','method':'item/tool/call','params':{'threadId':thread_id,'turnId':active,'callId':'2','tool':'source','arguments':{}}})
        elif scenario=='tokens':
            event('thread/tokenUsage/updated',turnId=active,tokenUsage={'total':{'totalTokens':101}})
            complete()
        elif scenario=='approval':
            send({'id':'approval-1','method':'item/commandExecution/requestApproval','params':{'threadId':thread_id,'turnId':active,'command':'forbidden'}})
        elif scenario in ('hang','chatter','steer','duplicate-completions'):
            event('item/started',turnId=active,item={'id':'work','type':'reasoning'})
        elif scenario=='failed': complete('failed')
        else: complete()
    elif method=='turn/steer':
        complete()
    elif method=='turn/interrupt':
        complete('interrupted');active=None
