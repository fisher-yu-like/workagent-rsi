# Natural20 elapsed-time correction

The original qualification CLI settled completed calls at no more than their
reserved timeout, and retained only that reservation for failures. This could
undercharge a request when the host did not return control at the expected
timeout. During the natural review, one request recorded 2259.785 seconds of
actual elapsed time despite a 120-second reservation. The cause of the long
wait has not been established and it is not excluded as idle time.

The controller stopped its own process tree before issuing more requests under
the understated balance. The original ledger remains unchanged. A separately
hashed corrected ledger adds 2140 seconds, giving 5177 conservative charged
seconds instead of 3037. Both interrupted calls retain their full reservations;
their unavailable token and tool telemetry is not treated as observed zero.

The runner now charges complete measured elapsed time. Failed or unknown calls
retain at least the full reservation. A response returned after its allocated
timeout is rejected, even if the child reports success. Subsequent calls are
blocked when the time balance is exhausted. Tests cover delayed timeouts, late
successes, preserved historical calls and unchanged successful judgments.

At the stop, 72 original request slots were recorded, with 65 valid decisions.
Seven processed channels were missing and twenty slots had never been issued.
The prepared completion proposal contains only these 27 slots. It preserves the
65 successful decisions and original records, rather than replaying the entire
cohort. Missing consistency reviews use literal report fields to avoid the
nested JSON quotation problem. They remain summaries rather than original
factual sources.

The proposed cumulative bounds are 109 attempts and 7200 seconds, including the
82 attempts and corrected 5177 seconds already charged. These are proposed
bounds only; explicit new user approval is required before execution. The
proposal hash is
`ed5a6ca903f28f80208de7754c50fd2c7a4a1c14ae85f297152d1ecb64dcc513`.

See `project_artifacts/formal_study/hardening_natural20_clock_audit_20261028.json`
for hashes and the corrected ledger. Eighteen focused checks passed. This is an
accounting correction and a completion plan, not a claim of completed evaluation
or evaluator accuracy.
