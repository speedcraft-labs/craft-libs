# craft-jobs

`craft-jobs` runs immutable snapshots on a small native worker pool. Jobs receive a
`JobContext`, check cancellation at bounded intervals, and report progress. Their final value is
polled by the caller and should be applied on the UI thread.

```rust,ignore
let job = jobs.submit_latest("document-render", Priority::Interactive, move |ctx| {
    let result = render(snapshot, || ctx.check_cancelled())?;
    Ok(result)
});
// In the UI loop: poll `job.try_recv()` and apply `Completed(Ok(result))` there.
```

`submit_latest` cancels an older job with the same key, which is useful for stale renders and
previews. Cancellation is cooperative; a running computation must check its token. Queued jobs
are ordered by priority, with FIFO order within one priority. The pool uses only the standard
library and is available on native targets.
