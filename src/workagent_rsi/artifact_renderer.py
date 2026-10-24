"""Render only checked copies through an explicitly configured isolated worker."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
import time
from typing import Literal
from uuid import uuid4
import subprocess  # Test seam: rendering never spawns host Office.

from pydantic import BaseModel, ConfigDict, Field

from .hashing import canonical_json_hash, sha256_file
from .run_contracts import RunContract
from .view_safety import checked_path, ordinary_file


class RenderPolicy(RunContract):
    engine: Literal['libreoffice-sandbox'] = 'libreoffice-sandbox'
    read_only_copy: Literal[True] = True
    macros: Literal['never'] = 'never'
    update_external_links: Literal[False] = False
    cleanup: Literal['owned_worker'] = 'owned_worker'
    network: Literal['none'] = 'none'


class RenderedPage(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    image_id: str
    path: str
    sha256: str
    page: int = Field(ge=1)
    artifact_location: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class RenderResult(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    status: Literal['available', 'unavailable', 'error', 'timeout']
    artifact_sha256: str
    renderer_identity: str
    pages: list[RenderedPage] = Field(default_factory=list)
    elapsed_seconds: float = Field(ge=0)
    error: str | None = None
    environment: dict[str, str | int | None] = Field(default_factory=dict)


class OfficeArtifactRenderer:
    """LibreOffice + Poppler inside the T04 boundary; no host COM fallback.

    Legacy executable keywords remain accepted for call compatibility. They do
    not authorize host execution. Supply a provisioned, frozen Office sandbox.
    """
    def __init__(self, output_root: str | Path, *, dpi: int = 144, timeout_seconds: int = 90,
                 powershell: str = 'powershell.exe', pdftoppm: str | None = None, max_pages: int = 40,
                 sandbox=None, policy: RenderPolicy | None = None):
        if type(dpi) is not int or not 36 <= dpi <= 300 or type(max_pages) is not int or not 1 <= max_pages <= 40:
            raise ValueError('render DPI/pages must be within fixed bounds')
        if type(timeout_seconds) is not int or timeout_seconds < 1:
            raise ValueError('render timeout must be positive')
        self.output_root = Path(output_root)
        self.dpi, self.timeout_seconds, self.max_pages = dpi, timeout_seconds, max_pages
        self.sandbox, self.policy = sandbox, policy or RenderPolicy()

    def identity_config(self):
        return {'renderer': 'isolated-office-pdf-poppler-v2', 'dpi': self.dpi, 'max_pages': self.max_pages,
                'policy': self.policy.model_dump(mode='json'),
                'worker': self.sandbox.policy.model_dump(mode='json') if self.sandbox is not None else None,
                'worker_code_sha256': sha256_file(Path(__file__).with_name('libreoffice_worker.py'))}

    def render(self, path: str | Path, domain: str, artifact_sha256: str | None = None) -> RenderResult:
        started = time.monotonic()
        digest = artifact_sha256 or canonical_json_hash({'missing': str(path)})
        identity = canonical_json_hash(self.identity_config())
        environment = {'engine': self.policy.engine, 'worker_status': 'unavailable'}
        def result(status, error=None, pages=None):
            return RenderResult(status=status, artifact_sha256=digest, renderer_identity=identity,
                                elapsed_seconds=time.monotonic()-started, pages=pages or [], error=error,
                                environment=environment)
        try:
            source = ordinary_file(Path(path))
            if source.stat().st_size > 104857600:
                return result('unavailable', 'artifact exceeds fixed render input budget')
            observed = sha256_file(source)
            if artifact_sha256 is not None and observed != artifact_sha256:
                return result('error', 'artifact SHA-256 does not match trusted hash')
            digest = observed
            suffix = {'excel': '.xlsx', 'word': '.docx', 'powerpoint': '.pptx'}.get(domain)
            if suffix is None or source.suffix.lower() != suffix:
                return result('unavailable', 'unsupported artifact domain or format')
            if self.sandbox is None:
                return result('unavailable', 'isolated Office worker is not configured')
            root = checked_path(self.output_root) / (identity[:12] + '-' + uuid4().hex[:12])
            root.mkdir(parents=True, exist_ok=False)
            inputs = root / 'inputs'
            inputs.mkdir()
            copied = inputs / ('artifact' + suffix)
            shutil.copyfile(source, copied)
            if sha256_file(copied) != digest or sha256_file(source) != digest:
                return result('error', 'artifact changed while preparing read-only copy')
            config = {'domain': domain, 'source': copied.relative_to(root).as_posix(), 'source_sha256': digest,
                      'dpi': self.dpi, 'max_pages': self.max_pages, 'policy': self.policy.model_dump(mode='json')}
            (inputs / 'render-policy.json').write_text(json.dumps(config), encoding='utf-8')
            script = root / 'render_office.py'
            script.write_bytes(Path(__file__).with_name('libreoffice_worker.py').read_bytes())
            outcome = self.sandbox.run(script, root, self.timeout_seconds)
            if sha256_file(source) != digest or sha256_file(copied) != digest:
                return result('error', 'source or rendering copy changed during worker execution')
            if outcome.status != 'succeeded':
                status = 'timeout' if outcome.status == 'timeout' else 'unavailable' if outcome.status == 'unavailable' else 'error'
                return result(status, 'isolated Office execution ' + outcome.status)
            report_path = ordinary_file(root / 'outputs/render-metadata.json')
            report = json.loads(report_path.read_text(encoding='utf-8'))
            environment.update(report.get('environment', {}))
            if report.get('status') != 'available':
                return result('unavailable', report.get('error', 'required Office capability unavailable'))
            if (report.get('source_sha256') != digest or report.get('load_policy') != {
                    'ReadOnly': True, 'MacroExecutionMode': 0, 'UpdateDocMode': 0} or report.get('owned_cleanup') is not True):
                return result('error', 'worker did not establish copy/load/cleanup policy')
            pages = []
            rows = report.get('pages', [])
            if not rows or len(rows) > self.max_pages:
                return result('unavailable', 'worker page coverage outside fixed bounds')
            from PIL import Image
            for index, item in enumerate(rows, 1):
                if item.get('page') != index or item.get('file') != f'outputs/page-{index}.png':
                    return result('error', 'invalid worker page reference')
                image_path = ordinary_file(root / item['file'])
                if sha256_file(image_path) != item['sha256']:
                    return result('error', 'worker page hash mismatch')
                with Image.open(image_path) as image:
                    width, height = image.size
                    if image.format != 'PNG' or width*height > 50000000:
                        return result('error', 'invalid rendered PNG')
                location = f'slide {index}' if domain == 'powerpoint' else f'rendered page {index} ({domain}; LibreOffice pagination)'
                pages.append(RenderedPage(image_id=f'page-{index}', path=str(image_path), sha256=item['sha256'],
                                          page=index, artifact_location=location, width=width, height=height))
            environment.update(worker_status='available', page_count=len(pages), dpi=self.dpi)
            return result('available', pages=pages)
        except FileNotFoundError as exc:
            return result('error', 'required file unavailable: ' + str(exc))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return result('error', 'render boundary rejected input/output: ' + str(exc))
