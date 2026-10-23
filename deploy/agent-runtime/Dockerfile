# Build only in an explicitly provisioned environment. PYTHON_BASE must be an
# approved immutable python:3.13-slim-bookworm@sha256:... reference; no default.
ARG PYTHON_BASE
FROM ${PYTHON_BASE}
USER root
COPY requirements.lock /opt/runtime/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /opt/runtime/requirements.lock \
    && python -c "import openpyxl, docx, pptx, yaml"
RUN mkdir -p /task/inputs /task/outputs /task/scratch \
    && chmod 755 /task /task/inputs && chmod 777 /task/outputs /task/scratch
USER 65532:65532
WORKDIR /task
ENTRYPOINT ["/usr/bin/env", "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp", "TMPDIR=/tmp", "/usr/local/bin/python", "-I", "-B"]
