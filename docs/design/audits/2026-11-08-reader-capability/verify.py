"""Verify real Orca output and completed espeak synthesis before admitting the synthetic reader-tool capability."""
from pathlib import Path
import re,json,xml.etree.ElementTree as ET,hashlib,shutil
root=Path.cwd();source=root/'.researcher/evaluations/reader-capability-20261108-speech-complete'
orcalines=(source/'orca-debug.log').read_text().splitlines();speech=(source/'speech-logs/speech-dispatcher.log').read_text()
outputs=[{'line':i+1,'text':s} for i,s in enumerate(orcalines) if 'SPEECH OUTPUT:' in s]
frames=list(re.finditer(r'Command sent to output module: \|(<speak>.*?</speak>)\|',speech,re.S))
utterances=[{'text':''.join(ET.fromstring(m.group(1)).itertext()),'offset':m.start(),'end_after': '702 END' in speech[m.end():frames[i+1].start() if i+1<len(frames) else len(speech)]} for i,m in enumerate(frames)]
required=['Revisar fuentes','La segunda fuente no indica fecha. Comprueba la versión antes de comparar.']
for phrase in required:
 assert any(phrase in s['text'] for s in outputs),phrase
 assert any(phrase in s['text'] and s['end_after'] for s in utterances),phrase
r=json.loads((source/'result.json').read_text());assert all(c['exit']==0 for c in r['children']);assert json.loads((source/'container-result.json').read_text())['exit']==0
assert 'Got audio: eventually ' in speech and '200 OK SPEAKING' in speech
result={'status':'verified_capability_only','scope':'Real Orca AT-SPI speech generation, completed espeak-ng synthesis and native X keyboard on synthetic HTML; NOT product acceptance, physical listening or human evaluation','orca':'43.1','speech_dispatcher':'0.11.4','chromium':r['browser']['version'],'tooling_image':'bf56c2ebe47ab61283c64f8cf4c83b0dc4572426f4ce1c0ea0aac72dbab6dd1f','native_keyboard':r['native_keyboard'],'speech_output_events':outputs,'module_utterances':utterances,'required_phrases':required,'audio_blocks':speech.count('Got audio: eventually '),'audio_format':'16bit mono22050Hz observed','audio_sink':'ALSA null','voice_default':'en-us; Spanish labels retained, pronunciation and Spanish role localization unassessed','children':r['children'],'initial_diagnostic':'Orca initially starts without active browser; subsequent focused-control and alert speech observed','first_attempt':'Failed before reader/browser launch: gsettings CLI absent; replaced with installed Gio.Settings library','second_attempt':'Orca generated control speech but native Return interrupted before control reached output module. Alert synthesized. Not full synthesis acceptance; retained. Final probe waits for exact phrase plus module END before next key/teardown.','remaining':'Run installed owner routes with real reader. Pair before starting reader logs to avoid capturing private pairing code. Do not substitute accessible-tree/DOM label checks for Orca/Speech Dispatcher output.'}
dest=root/'docs/design/audits/2026-11-08-reader-capability';dest.mkdir()
for label,dirname in [('initial','reader-capability-20261108'),('speech-interrupted','reader-capability-20261108-gio'),('speech-complete','reader-capability-20261108-speech-complete')]:
 src=root/'.researcher/evaluations'/dirname;out=dest/label;out.mkdir()
 for p in src.rglob('*'):
  if not p.is_file() or '__pycache__' in str(p):continue
  rel=p.relative_to(src);target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
for name in ['Containerfile','build.py','build.log','build-result.json','verify.py']:shutil.copy2(root/'.superpowers/sdd/2026-10-31-actualizacion-proyecto/reader-tools'/name,dest/name)
(root/'docs/modernization/reader-capability-results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print('verified outputs',len(outputs),'module phrases',len(utterances),'audio blocks',result['audio_blocks'])
print('required completed utterances',[s for s in utterances if any(p in s['text'] for p in required)])
