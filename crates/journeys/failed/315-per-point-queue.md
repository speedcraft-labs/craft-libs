# Failed approach: one input RPC per brush point

The first full typical-tier attempt emitted each of the 200 brush points as a separate `ui.latency.input` call and waited for the UI response before advancing. It serialized a real stroke into hundreds of tiny request/frame turns; the run reached roughly six seconds of CPU work per point and was stopped before a publishable session existed. Those artifacts are diagnostic only and must not be combined with the final campaign.

The accepted driver sends a distinct pointer press, queues the stroke’s move events through the normal egui input path, then releases. The recorder still stamps each accepted event and waits for the reflecting frame.

Evidence is preserved under `keep/315-photocraft-latency/reports/debug-full-typical/` and handoff 10 on hyper #291. This branch is an investigation note; it contains no PhotoCraft optimization.
