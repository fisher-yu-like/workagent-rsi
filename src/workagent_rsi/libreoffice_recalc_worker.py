"""Trusted standalone program. Execute only in the configured T04 boundary."""
from pathlib import Path
import hashlib,json,subprocess,tempfile,time
from uuid import uuid4


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def recalculate(config):
    import uno,unohelper
    from com.sun.star.beans import PropertyValue
    from com.sun.star.task import XInteractionHandler,XInteractionAbort
    class Abort(unohelper.Base,XInteractionHandler):
        def handle(self,request):
            for continuation in request.getContinuations():
                abort=uno.queryInterface(XInteractionAbort,continuation)
                if abort is not None:abort.select();return
    def prop(name,value):
        p=PropertyValue();p.Name=name;p.Value=value;return p
    source=Path(config['source']);output=Path('outputs/recalculated.xlsx');output.parent.mkdir(exist_ok=True)
    if sha(source)!=config['source_sha256']:raise ValueError('source hash mismatch')
    binary=Path('/usr/lib/libreoffice/program/soffice.bin')
    with tempfile.TemporaryDirectory(prefix='wrsi-recalc-') as folder:
        profile=Path(folder)/'profile';profile.mkdir();pipe='wrsi_'+uuid4().hex
        args=[str(binary),'-env:UserInstallation='+profile.as_uri(),'--headless','--norestore','--nodefault','--nologo','--accept=pipe,name='+pipe+';urp;StarOffice.ComponentContext']
        log=(Path(folder)/'office.log').open('wb');process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
        desktop=document=None;restarted=False
        try:
            context=uno.getComponentContext();resolver=context.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',context)
            deadline=time.monotonic()+25;remote=None
            while time.monotonic()<deadline:
                if process.poll()==81 and not restarted:process.wait();process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log);restarted=True
                elif process.poll() is not None:break
                try:remote=resolver.resolve('uno:pipe,name='+pipe+';urp;StarOffice.ComponentContext');break
                except Exception:time.sleep(.1)
            if remote is None:raise RuntimeError('isolated LibreOffice startup failed')
            desktop=remote.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',remote)
            load={'ReadOnly':True,'MacroExecutionMode':0,'UpdateDocMode':0}
            document=desktop.loadComponentFromURL(source.absolute().as_uri(),'_blank',0,tuple([prop(k,v) for k,v in load.items()]+[prop('Hidden',True),prop('InteractionHandler',Abort())]))
            if document is None or not document.isReadonly():raise RuntimeError('read-only copy was not established')
            document.calculateAll()
            document.storeToURL(output.absolute().as_uri(),(prop('FilterName','Calc MS Excel 2007 XML'),prop('Overwrite',False)))
            document.setModified(False);document.close(True);document=None
            version=subprocess.run([str(binary),'--version'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
        finally:
            if document is not None:
                try:document.dispose()
                except Exception:pass
            if desktop is not None:
                try:desktop.terminate()
                except Exception:pass
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            log.close()
    if sha(source)!=config['source_sha256']:raise ValueError('source modified')
    return {'status':'available','source_sha256':sha(source),'output_sha256':sha(output),'worker_sha256':config['worker_sha256'],
        'calculate_all':True,'load_policy':load,'owned_cleanup':process.poll() is not None,
        'environment':{'office_version':version,'office_binary_sha256':sha(binary),'network':'none'}}


if __name__=='__main__':
    try:result=recalculate(json.loads(Path('inputs/recalc-policy.json').read_text()))
    except Exception as exc:result={'status':'unavailable','error':type(exc).__name__+': '+str(exc)}
    Path('outputs').mkdir(exist_ok=True);Path('outputs/recalc-metadata.json').write_text(json.dumps(result,indent=2))
