# Execution cost and resource evidence

Each assistant garment turn contains `metadata.garment.intelligence_execution`. The owned job result carries a second `intelligence_execution` record because the worker continues after submission. The job ID joins those observations across restart.

| Measurement | Source and interpretation |
| --- | --- |
| Turn duration | Monotonic time from execution-context creation through preparation of the assistant reply. Excludes upload validation before the context and asynchronous job completion. |
| Operation duration | Monotonic elapsed time including admission, queue wait, execution and result validation. |
| Classifier inference | Per-view v6 receipt includes preprocessing, forward pass, device synchronization during output checks and probability validation. Inherited evidence from an earlier turn is not charged again. |
| CPU and memory | Synchronous router operations expose thread CPU time. The aggregate is partial CPU consumption. Peak RSS is a process-wide high-water mark, including other work in the process. GPU utilization and per-user memory allocation are unknown. |
| Geometry, rendering and evaluation | Monotonic timers in the worker surround geometry and fusion, thumbnail rendering and structural inspection respectively. Job duration includes other stages. |
| External service calls | The transport wrapper counts actual Gemini, Groq and OpenRouter requests in the active context, including transport errors. The record excludes keys, headers, prompt text and image bytes. A missing credential produces zero transport attempts. |
| Tokens | Only returned provider usage fields contribute. A missing field on any attempted request leaves the corresponding aggregate unknown. A turn with no requests has zero external tokens. |
| Money | No external requests means zero external API charge for this path. A request without billing evidence leaves actual billed dollars unknown. Existing estimated prices are separate and are excluded from actual cost. Local CPU/GPU dollar costs are unmeasured. |
| Retry and fallback | Adapter transport retries are counted separately from a change of route. Capture of legacy backend-internal retries outside the instrumented transports is incomplete. |

The existing daily limit remains a conservative admission budget based on turns and image count. Its units are separate from actual requests and token totals. The software holds a dispatcher slot for late-running native work to avoid creating extra workers after a timeout. A timeout does not establish how much compute an upstream provider consumed.

## Local staging observation

In the final durable browser run, one jacket reconstruction turn took 7,601.321 ms before the reply. Recorded v6 inference was 92.189 ms on MPS. Recorded synchronous thread CPU time was 1,569.975 ms and process peak RSS was 643,334,144 bytes. The worker measured 930.953 ms for geometry and fusion, 240.664 ms for structural evaluation and 78.107 ms for thumbnail rendering. It issued zero metered external requests, consumed zero external tokens and recorded zero provider retries or route fallbacks on the initiating turn. These values describe one local execution, not a throughput target or an inference accuracy measurement.
