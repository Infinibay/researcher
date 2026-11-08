"""Exercise Orca speech generation and native X keyboard focus on synthetic HTML in a private D-Bus session."""
import json
import os
from pathlib import Path
import subprocess
import time
import re
import xml.etree.ElementTree as ET
OUT=Path('/out')
processes=[]
logs=[]
result={'status':'running','scope':'Orca on synthetic HTML; ALSA null sink, no physical listening or product acceptance'}

def launch(name,command):
    """Own one exact child handle and its original log until explicit teardown."""
    log=(OUT/(name+'.log')).open('x');logs.append(log)
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT);processes.append((name,process));return process

def wait_for(predicate,label,seconds=15):
    """Poll a specific readiness condition with a deadline, preserving startup failure logs."""
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        dead=[(name,p.returncode) for name,p in processes if p.poll() is not None]
        if dead:raise RuntimeError(f'Child exited during {label}: {dead}')
        time.sleep(.1)
    raise TimeoutError(label)

def module_finished(phrase):
    """Require the exact synthesized phrase and its module END before another key can interrupt it."""
    log=OUT/'speech-logs/speech-dispatcher.log'
    if not log.exists():return False
    text=log.read_text(errors='replace')
    for match in re.finditer(r'Command sent to output module: \|(<speak>.*?</speak>)\|',text,re.S):
        if phrase not in ''.join(ET.fromstring(match.group(1)).itertext()):continue
        tail=text[match.end():]
        next_message=tail.find('Command sent to output module: |<speak>')
        if next_message!=-1:tail=tail[:next_message]
        if '702 END' in tail:return True
    return False

try:
    os.environ.update(DISPLAY=':99',XDG_RUNTIME_DIR='/tmp/reader-runtime',ACCESSIBILITY_ENABLED='1',SPEECHD_ADDRESS='unix_socket:/tmp/reader-speech.sock')
    Path('/tmp/reader-runtime').mkdir(mode=0o700)
    Path('/root/.asoundrc').write_text('pcm.!default { type null }\n')
    config=OUT/'speech-config';config.mkdir();(OUT/'speech-logs').mkdir()
    (config/'speechd.conf').write_text('LogLevel 5\nDefaultLanguage "es"\nDefaultModule "espeak-ng"\nAddModule "espeak-ng" "sd_espeak-ng" "/etc/speech-dispatcher/modules/espeak-ng.conf"\nAudioOutputMethod "alsa"\n')
    launch('xvfb',['Xvfb',':99','-screen','0','1440x1024x24','-nolisten','tcp'])
    wait_for(lambda:Path('/tmp/.X11-unix/X99').exists(),'Xvfb socket')
    from gi.repository import Gio
    settings=Gio.Settings.new('org.gnome.desktop.interface')
    assert settings.set_boolean('toolkit-accessibility',True)
    Gio.Settings.sync()
    launch('speech',['speech-dispatcher','--run-single','--config-dir',str(config),'--socket-path','/tmp/reader-speech.sock','--log-dir',str(OUT/'speech-logs'),'--log-level','5'])
    wait_for(lambda:Path('/tmp/reader-speech.sock').exists(),'Speech Dispatcher socket')
    launch('orca',['orca','--debug','--debug-file=/out/orca-debug.log','--user-prefs=/out/orca-profile','--enable=speech','--disable=braille'])
    launch('browser',['node','/opt/audit/probe.mjs'])
    wait_for(lambda:(OUT/'browser-ready.json').exists(),'Chromium page',30)
    ids=subprocess.run(['xdotool','search','--onlyvisible','--name','Prueba de lectura'],text=True,capture_output=True,check=True).stdout.split()
    assert ids
    subprocess.run(['xdotool','windowfocus','--sync',ids[-1]],check=True)
    subprocess.run(['xdotool','key','--clearmodifiers','Tab'],check=True)
    wait_for(lambda:(OUT/'orca-debug.log').exists() and 'Revisar fuentes' in (OUT/'orca-debug.log').read_text(errors='replace'),'Orca receives focused control')
    wait_for(lambda:module_finished('Revisar fuentes'),'Focused control synthesis completed')
    subprocess.run(['xdotool','key','--clearmodifiers','Return'],check=True)
    wait_for(lambda:(OUT/'browser-interaction.json').exists(),'Native activation effect')
    wait_for(lambda:'La segunda fuente no indica fecha' in (OUT/'orca-debug.log').read_text(errors='replace'),'Orca receives alert')
    wait_for(lambda:module_finished('La segunda fuente no indica fecha.'),'Alert synthesis completed')
    result['status']='observed_requires_speech_log_review'
    result['browser']=json.loads((OUT/'browser-ready.json').read_text())
    result['native_keyboard']=['Tab','Return']
except BaseException as error:
    result['status']='failed';result['error']=str(error);raise
finally:
    result['children']=[]
    for name,process in reversed(processes):
        if process.poll() is None:process.terminate()
        try:code=process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();code=process.wait(timeout=5)
        result['children'].append({'name':name,'exit':code})
    for log in logs:log.close()
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
