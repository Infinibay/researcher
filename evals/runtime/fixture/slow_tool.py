import os,time;open('slow-tool.pid','w').write(str(os.getpid()));print('SLOW_TOOL_READY',flush=True);time.sleep(60);open('late-effect.txt','w').write('late')
