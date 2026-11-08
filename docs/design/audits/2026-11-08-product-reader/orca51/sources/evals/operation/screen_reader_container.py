"""Own the private display, speech service, Orca and actual product browser inside reader tooling."""
import json
import os
from pathlib import Path
import subprocess
import time

OUT = Path('/out')


def main():
    """Start the reader only after pairing; close every exact child handle and preserve partial results."""
    processes, logs = [], []
    result = {'status': 'running', 'scope': 'Installed owner workspace with actual Orca; ALSA null, no physical listening or human acceptance'}

    def launch(name, command):
        """Retain the original child process and its log for deterministic teardown."""
        log = (OUT / (name + '.log')).open('x')
        logs.append(log)
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        processes.append((name, process))
        return process

    def wait_for(predicate, label, seconds=20):
        """Wait for an observed startup condition while checking the original children's liveness."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            dead = [(name, child.returncode) for name, child in processes if child.poll() is not None]
            if dead:
                raise RuntimeError(f'Child exited during {label}: {dead}')
            time.sleep(.1)
        raise TimeoutError(label)

    try:
        os.environ.update(DISPLAY=':99', XDG_RUNTIME_DIR='/tmp/reader-runtime', ACCESSIBILITY_ENABLED='1', SPEECHD_ADDRESS='unix_socket:/tmp/reader-speech.sock')
        Path('/tmp/reader-runtime').mkdir(mode=0o700)
        Path('/root/.asoundrc').write_text('pcm.!default { type null }\n')
        config = OUT / 'speech-config'
        config.mkdir()
        (OUT / 'speech-logs').mkdir()
        (config / 'speechd.conf').write_text('LogLevel 5\nDefaultLanguage "es"\nDefaultModule "espeak-ng"\nAddModule "espeak-ng" "sd_espeak-ng" "/etc/speech-dispatcher/modules/espeak-ng.conf"\nAudioOutputMethod "alsa"\n')
        launch('xvfb', ['Xvfb', ':99', '-screen', '0', '1440x1024x24', '-nolisten', 'tcp'])
        wait_for(lambda: Path('/tmp/.X11-unix/X99').exists(), 'Xvfb socket')
        from gi.repository import Gio
        settings = Gio.Settings.new('org.gnome.desktop.interface')
        assert settings.set_boolean('toolkit-accessibility', True)
        Gio.Settings.sync()
        launch('speech', ['speech-dispatcher', '--run-single', '--config-dir', str(config), '--socket-path', '/tmp/reader-speech.sock', '--log-dir', str(OUT / 'speech-logs'), '--log-level', '5'])
        wait_for(lambda: Path('/tmp/reader-speech.sock').exists(), 'Speech Dispatcher socket')
        browser = launch('browser', ['node', '/opt/frontend/tests/screen-reader-audit.mjs'])
        wait_for(lambda: (OUT / 'paired.json').exists(), 'Owner pairing before reader logging', 30)
        result['pairing_before_reader'] = True
        orca_version = subprocess.check_output(['orca', '--version'], text=True).strip()
        result['tools'] = {'orca': orca_version, 'node': subprocess.check_output(['node', '--version'], text=True).strip(),
                           'speech_dispatcher': subprocess.check_output(['speech-dispatcher', '--version'], text=True).splitlines()[0]}
        major = int(orca_version.split('.')[0])
        command = ['orca', '--debug-file=/out/orca-debug.log']
        if major >= 51:
            command += ['--speech-system=speechdispatcherfactory']
        else:
            command += ['--debug', '--user-prefs=/out/orca-profile', '--enable=speech', '--disable=braille']
        if Path('/opt/reader-packages.txt').exists():
            (OUT / 'tool-packages.txt').write_text(Path('/opt/reader-packages.txt').read_text())
        result['orca_arguments'] = command
        launch('orca', command)
        wait_for(lambda: (OUT / 'orca-debug.log').exists() and "SPEECH OUTPUT: 'Screen reader on." in (OUT / 'orca-debug.log').read_text(errors='replace'), 'Orca startup')
        (OUT / 'reader-ready.json').write_text(json.dumps({'reader_started_after_pairing': True}) + '\n')
        result['browser_exit'] = browser.wait(timeout=240)
        assert result['browser_exit'] == 0, 'Inspect browser-result.json and original reader logs'
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error=str(error))
        raise
    finally:
        result['children'] = []
        for name, process in reversed(processes):
            if process.poll() is None:
                process.terminate()
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait(timeout=5)
            result['children'].append({'name': name, 'exit': code})
        for log in logs:
            log.close()
        (OUT / 'reader-result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
