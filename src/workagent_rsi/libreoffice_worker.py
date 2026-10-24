"""Trusted render program: run ONLY inside an explicitly frozen T04 sandbox."""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time
from uuid import uuid4


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def render(config):
    output = Path('outputs')
    output.mkdir(exist_ok=True)
    source = Path(config['source'])
    digest = config['source_sha256']
    if sha(source) != digest:
        raise ValueError('worker source hash mismatch')
    policy = config['policy']
    if (policy['macros'] != 'never' or policy['update_external_links'] is not False
            or policy['read_only_copy'] is not True or policy['network'] != 'none'):
        raise ValueError('unsafe render policy')
    soffice = Path('/usr/lib/libreoffice/program/soffice.bin')
    poppler, pdfinfo = shutil.which('pdftoppm'), shutil.which('pdfinfo')
    if not soffice.is_file() or not poppler or not pdfinfo:
        return {'status': 'unavailable', 'source_sha256': digest, 'error': 'LibreOffice/Poppler runtime is not provisioned'}
    import uno
    import unohelper
    from com.sun.star.beans import PropertyValue
    from com.sun.star.task import XInteractionHandler, XInteractionAbort
    from com.sun.star.document.MacroExecMode import NEVER_EXECUTE
    from com.sun.star.document.UpdateDocMode import NO_UPDATE

    class AbortInteractions(unohelper.Base, XInteractionHandler):
        def handle(self, request):
            for continuation in request.getContinuations():
                abort = uno.queryInterface(XInteractionAbort, continuation)
                if abort is not None:
                    abort.select()
                    return

    def prop(name, value):
        item = PropertyValue()
        item.Name = name
        item.Value = value
        return item

    with tempfile.TemporaryDirectory(prefix='wrsi-office-') as temporary:
        profile = Path(temporary) / 'profile'
        (profile / 'user').mkdir(parents=True)
        (profile / 'user/registrymodifications.xcu').write_text('''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
</oor:items>''')
        pipe = 'wrsi_' + uuid4().hex
        args = [str(soffice), '-env:UserInstallation=' + profile.as_uri(), '--headless', '--norestore', '--nodefault',
                '--nologo', '--accept=pipe,name=' + pipe + ';urp;StarOffice.ComponentContext']
        log_path = Path(temporary) / 'office.stderr'
        log_stream = log_path.open('wb')
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log_stream)
        startup_restarts = 0
        desktop = document = None
        try:
            context = uno.getComponentContext()
            resolver = context.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', context)
            deadline = time.monotonic() + 25
            remote = None
            while time.monotonic() < deadline:
                # A brand-new LO profile requests a restart (81) after its
                # initial setup. Reap only our child and permit one restart.
                code = process.poll()
                if code == 81 and startup_restarts == 0:
                    process.wait()
                    process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log_stream)
                    startup_restarts += 1
                elif code is not None:
                    break
                try:
                    remote = resolver.resolve('uno:pipe,name=' + pipe + ';urp;StarOffice.ComponentContext')
                    break
                except Exception:
                    time.sleep(.1)
            if remote is None:
                raise RuntimeError('isolated LibreOffice did not start (exit=' + str(process.poll()) + '): '
                                   + log_path.read_text(errors='replace')[-4000:])
            desktop = remote.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', remote)
            load_policy = {'ReadOnly': True, 'MacroExecutionMode': NEVER_EXECUTE, 'UpdateDocMode': NO_UPDATE}
            document = desktop.loadComponentFromURL(source.absolute().as_uri(), '_blank', 0, tuple(
                [prop(name, value) for name,value in load_policy.items()] +
                [prop('Hidden', True), prop('InteractionHandler', AbortInteractions()), prop('AsTemplate', False)]))
            if document is None or not document.isReadonly():
                raise RuntimeError('Office did not open the copy read-only')
            pdf = output / 'rendered.pdf'
            filters = {'word': 'writer_pdf_Export', 'excel': 'calc_pdf_Export', 'powerpoint': 'impress_pdf_Export'}
            document.storeToURL(pdf.absolute().as_uri(), (prop('FilterName', filters[config['domain']]), prop('Overwrite', True)))
            document.setModified(False)
            document.close(True)
            document = None
            info = subprocess.run([pdfinfo, str(pdf)], capture_output=True, text=True, timeout=15, check=True)
            pages = int(next(line.split(':',1)[1].strip() for line in info.stdout.splitlines() if line.startswith('Pages:')))
            if not 1 <= pages <= config['max_pages']:
                return {'status': 'unavailable', 'source_sha256': digest, 'error': 'PDF exceeds fixed page coverage'}
            subprocess.run([poppler, '-png', '-r', str(config['dpi']), '-f', '1', '-l', str(pages), str(pdf), str(output/'raster')],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            images = sorted(output.glob('raster-*.png'), key=lambda p: int(p.stem.rsplit('-',1)[1]))
            if len(images) != pages:
                raise RuntimeError('incomplete PDF rasterization')
            rows = []
            for number, path in enumerate(images, 1):
                renamed = output / f'page-{number}.png'
                path.rename(renamed)
                rows.append({'page': number, 'file': renamed.as_posix(), 'sha256': sha(renamed)})
            version = subprocess.run([str(soffice), '--version'], capture_output=True, text=True, timeout=10, check=True).stdout.strip()
            poppler_version = subprocess.run([poppler, '-v'], capture_output=True, text=True, timeout=10).stderr.strip().splitlines()[0]
            fonts = {p.relative_to('/usr/share/fonts').as_posix(): sha(p) for p in sorted(Path('/usr/share/fonts').rglob('*')) if p.is_file()}
            environment = {'office_engine': 'LibreOffice', 'office_version': version, 'poppler_version': poppler_version,
                           'office_startup_restarts': startup_restarts,
                           'office_binary_sha256': sha(soffice), 'poppler_binary_sha256': sha(poppler),
                           'font_fingerprint': hashlib.sha256(json.dumps(fonts,sort_keys=True).encode()).hexdigest(),
                           'font_file_count': len(fonts), 'system_fingerprint': hashlib.sha256(platform.platform().encode()).hexdigest()}
            result = {'status': 'available', 'source_sha256': digest, 'pages': rows,
                      'load_policy': load_policy, 'environment': environment}
        finally:
            if document is not None:
                try: document.dispose()
                except Exception: pass
            if desktop is not None:
                try: desktop.terminate()
                except Exception: pass
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            cleanup = process.poll() is not None
            log_stream.close()
        if sha(source) != digest:
            raise RuntimeError('Office modified the rendering source')
        result['owned_cleanup'] = cleanup
        return result


if __name__ == '__main__':
    try:
        result = render(json.loads(Path('inputs/render-policy.json').read_text()))
    except Exception as exc:
        result = {'status': 'unavailable', 'error': type(exc).__name__ + ': ' + str(exc)}
    Path('outputs').mkdir(exist_ok=True)
    Path('outputs/render-metadata.json').write_text(json.dumps(result, indent=2))
