# Optional visual assessment

Use only images rendered from the assessed artifact, with original digest, page/slide/region mapping and renderer identity. Model, prompt, sampling, image processing, timeout and budget are fixed for both execution versions. Require structured observations with image references. No image, render failure, timeout or insufficient evidence leaves the applicable check incomplete. Visual ratings do not override deterministic numerical requirements.

The verifier reuses these observations. Calling a second model is unnecessary. Record real calls, image counts, elapsed time and known cost; unknown fees stay null. Offline mocked responses establish interface behavior only, not real visual accuracy or human agreement.
