//! A small native job scheduler for work that must stay off the UI thread.
//!
//! Inputs should be immutable snapshots (`Arc` is usually appropriate). Jobs report progress
//! through [`JobContext`] and return their result for the caller to apply on its UI thread.
//! Cancellation is cooperative: long-running jobs should periodically call
//! [`JobContext::check_cancelled`].

#![deny(clippy::unwrap_used, clippy::expect_used, clippy::panic, clippy::unimplemented, clippy::todo, clippy::unreachable)]

use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering as AtomicOrdering};
use std::sync::{Arc, Condvar, Mutex, mpsc};
use std::thread;

/// Job importance; higher priorities start before lower priorities still in the queue.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum Priority {
    /// Speculative work such as prefetching or thumbnails.
    Background,
    /// Work that can wait behind user-visible work.
    #[default]
    Normal,
    /// Work directly requested by the user.
    Interactive,
    /// Work needed to keep the current interaction responsive.
    Urgent,
}

impl Priority {
    fn rank(self) -> u8 {
        match self {
            Self::Background => 0,
            Self::Normal => 1,
            Self::Interactive => 2,
            Self::Urgent => 3,
        }
    }
}

/// Why a job did not produce a value.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum JobError {
    /// The job was cancelled before it started or cooperatively stopped while running.
    Cancelled,
    /// The job's computation failed.
    Failed(String),
}

/// Messages delivered to the caller, which should apply `Completed` on the UI thread.
#[derive(Debug, Eq, PartialEq)]
pub enum JobEvent<T> {
    /// A bounded, caller-defined progress value.
    Progress(u8),
    /// The completed job result or error.
    Completed(Result<T, JobError>),
}

/// A cooperative cancellation signal shared by a queued job and its caller.
#[derive(Clone, Debug)]
pub struct CancellationToken(Arc<AtomicBool>);

impl CancellationToken {
    /// Returns whether cancellation has been requested.
    pub fn is_cancelled(&self) -> bool {
        self.0.load(AtomicOrdering::Acquire)
    }

    /// Requests cancellation. The job must check the token to stop promptly.
    pub fn cancel(&self) {
        self.0.store(true, AtomicOrdering::Release);
    }

    /// Shares the underlying flag with a lower-level API that accepts an atomic flag.
    pub fn atomic_flag(&self) -> Arc<AtomicBool> {
        Arc::clone(&self.0)
    }
}

/// Job-side helpers for cancellation and progress reporting.
pub struct JobContext {
    token: CancellationToken,
    progress: mpsc::Sender<u8>,
}

impl JobContext {
    /// Returns the cancellation token for use by nested operations.
    pub fn cancellation(&self) -> CancellationToken {
        self.token.clone()
    }

    /// Returns `Err(Cancelled)` when cancellation has been requested.
    pub fn check_cancelled(&self) -> Result<(), JobError> {
        if self.token.is_cancelled() { Err(JobError::Cancelled) } else { Ok(()) }
    }

    /// Reports progress as a percentage from 0 through 100.
    pub fn report_progress(&self, percent: u8) {
        let _ = self.progress.send(percent.min(100));
    }
}

/// A submitted job handle. Poll events without blocking from the UI loop.
pub struct JobHandle<T> {
    token: CancellationToken,
    progress: mpsc::Receiver<u8>,
    result: mpsc::Receiver<Result<T, JobError>>,
    cancel_on_drop: bool,
}

impl<T> JobHandle<T> {
    /// Requests cooperative cancellation.
    pub fn cancel(&self) {
        self.token.cancel();
    }

    /// Checks whether cancellation was requested.
    pub fn is_cancelled(&self) -> bool {
        self.token.is_cancelled()
    }

    /// Returns the next progress or completion event without waiting.
    pub fn try_recv(&self) -> Result<JobEvent<T>, mpsc::TryRecvError> {
        match self.progress.try_recv() {
            Ok(value) => return Ok(JobEvent::Progress(value)),
            Err(mpsc::TryRecvError::Disconnected) => {}
            Err(mpsc::TryRecvError::Empty) => {}
        }
        self.result.try_recv().map(JobEvent::Completed)
    }

    /// Stops observing the result without cancelling the job. Keyed jobs remain cancellable by
    /// a later [`JobSystem::submit_latest`] call with the same key.
    pub fn detach(mut self) {
        self.cancel_on_drop = false;
    }
}

impl<T> Drop for JobHandle<T> {
    fn drop(&mut self) {
        if self.cancel_on_drop {
            self.token.cancel();
        }
    }
}

type Work = Box<dyn FnOnce() + Send + 'static>;

struct Queued {
    priority: Priority,
    sequence: u64,
    work: Option<Work>,
}

impl PartialEq for Queued {
    fn eq(&self, other: &Self) -> bool {
        self.priority == other.priority && self.sequence == other.sequence
    }
}
impl Eq for Queued {}
impl PartialOrd for Queued {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for Queued {
    fn cmp(&self, other: &Self) -> Ordering {
        self.priority.rank().cmp(&other.priority.rank()).then_with(|| other.sequence.cmp(&self.sequence))
    }
}

struct Shared {
    queue: Mutex<BinaryHeap<Queued>>,
    ready: Condvar,
    latest: Mutex<HashMap<String, CancellationToken>>,
    stopping: AtomicBool,
}

/// A fixed-size worker pool with priority scheduling and latest-wins keyed jobs.
pub struct JobSystem {
    shared: Arc<Shared>,
    workers: Vec<thread::JoinHandle<()>>,
    sequence: AtomicU64,
}

impl JobSystem {
    /// Creates a worker pool with at least one thread.
    pub fn new(worker_count: usize) -> Self {
        let shared = Arc::new(Shared {
            queue: Mutex::new(BinaryHeap::new()),
            ready: Condvar::new(),
            latest: Mutex::new(HashMap::new()),
            stopping: AtomicBool::new(false),
        });
        let mut workers = Vec::new();
        for index in 0..worker_count.max(1) {
            let shared = Arc::clone(&shared);
            if let Ok(worker) = thread::Builder::new().name(format!("craft-job-{index}")).spawn(move || {
                loop {
                    let item = {
                        let mut queue = match shared.queue.lock() {
                            Ok(queue) => queue,
                            Err(poisoned) => poisoned.into_inner(),
                        };
                        while queue.is_empty() {
                            if shared.stopping.load(AtomicOrdering::Acquire) {
                                return;
                            }
                            queue = match shared.ready.wait(queue) {
                                Ok(queue) => queue,
                                Err(poisoned) => poisoned.into_inner(),
                            };
                        }
                        if shared.stopping.load(AtomicOrdering::Acquire) {
                            return;
                        }
                        queue.pop()
                    };
                    if let Some(mut item) = item
                        && let Some(work) = item.work.take()
                    {
                        work();
                    }
                }
            }) {
                workers.push(worker);
            }
        }
        Self { shared, workers, sequence: AtomicU64::new(0) }
    }

    /// Submits a job. The closure runs on a worker; its result is delivered to the handle.
    pub fn submit<T, F>(&self, priority: Priority, work: F) -> JobHandle<T>
    where
        T: Send + 'static,
        F: FnOnce(&JobContext) -> Result<T, JobError> + Send + 'static,
    {
        self.submit_inner(priority, None, work)
    }

    /// Submits a keyed latest-wins job, cancelling the prior job with the same key.
    pub fn submit_latest<T, F>(&self, key: impl Into<String>, priority: Priority, work: F) -> JobHandle<T>
    where
        T: Send + 'static,
        F: FnOnce(&JobContext) -> Result<T, JobError> + Send + 'static,
    {
        self.submit_inner(priority, Some(key.into()), work)
    }

    fn submit_inner<T, F>(&self, priority: Priority, key: Option<String>, work: F) -> JobHandle<T>
    where
        T: Send + 'static,
        F: FnOnce(&JobContext) -> Result<T, JobError> + Send + 'static,
    {
        let token = CancellationToken(Arc::new(AtomicBool::new(false)));
        if let Some(key) = &key {
            let mut latest = match self.shared.latest.lock() {
                Ok(latest) => latest,
                Err(poisoned) => poisoned.into_inner(),
            };
            if let Some(previous) = latest.insert(key.clone(), token.clone()) {
                previous.cancel();
            }
        }
        let (result_tx, result_rx) = mpsc::channel();
        let (progress_tx, progress_rx) = mpsc::channel();
        let job_token = token.clone();
        let latest_key = key.clone();
        let shared = Arc::clone(&self.shared);
        let task: Work = Box::new(move || {
            let context = JobContext { token: job_token.clone(), progress: progress_tx };
            let result = if job_token.is_cancelled() { Err(JobError::Cancelled) } else { work(&context) };
            let result = if job_token.is_cancelled() { Err(JobError::Cancelled) } else { result };
            if let Some(key) = latest_key {
                let mut latest = match shared.latest.lock() {
                    Ok(latest) => latest,
                    Err(poisoned) => poisoned.into_inner(),
                };
                if latest.get(&key).is_some_and(|current| Arc::ptr_eq(&current.0, &job_token.0)) {
                    latest.remove(&key);
                }
            }
            let _ = result_tx.send(result);
        });
        let queued = Queued { priority, sequence: self.sequence.fetch_add(1, AtomicOrdering::Relaxed), work: Some(task) };
        let mut queue = match self.shared.queue.lock() {
            Ok(queue) => queue,
            Err(poisoned) => poisoned.into_inner(),
        };
        queue.push(queued);
        drop(queue);
        self.shared.ready.notify_one();
        JobHandle { token, progress: progress_rx, result: result_rx, cancel_on_drop: true }
    }
}

impl Drop for JobSystem {
    fn drop(&mut self) {
        self.shared.stopping.store(true, AtomicOrdering::Release);
        let mut queue = match self.shared.queue.lock() {
            Ok(queue) => queue,
            Err(poisoned) => poisoned.into_inner(),
        };
        queue.clear();
        drop(queue);
        self.shared.ready.notify_all();
        // Detach running workers so an app does not freeze on shutdown waiting for a job that
        // has not yet reached its next cooperative cancellation point.
        self.workers.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;
    use std::time::Duration;

    fn completed<T>(handle: &JobHandle<T>) -> Result<T, JobError> {
        loop {
            match handle.try_recv() {
                Ok(JobEvent::Completed(result)) => return result,
                Ok(JobEvent::Progress(_)) | Err(mpsc::TryRecvError::Empty) => thread::sleep(Duration::from_millis(1)),
                Err(mpsc::TryRecvError::Disconnected) => return Err(JobError::Failed("job channel closed".into())),
            }
        }
    }

    #[test]
    fn cancellation_is_cooperative_and_reported() {
        let jobs = JobSystem::new(1);
        let (started_tx, started_rx) = mpsc::channel();
        let handle = jobs.submit(Priority::Interactive, move |ctx| {
            started_tx.send(()).ok();
            while !ctx.cancellation().is_cancelled() {
                thread::yield_now();
            }
            ctx.check_cancelled()?;
            Ok(1)
        });
        started_rx.recv_timeout(Duration::from_secs(2)).expect("job should start");
        handle.cancel();
        assert_eq!(completed(&handle), Err(JobError::Cancelled));
    }

    #[test]
    fn urgent_job_precedes_queued_background_job() {
        let jobs = JobSystem::new(1);
        let (block_tx, block_rx) = mpsc::channel();
        let (started_tx, started_rx) = mpsc::channel();
        let blocker = jobs.submit(Priority::Normal, move |_| {
            started_tx.send(()).ok();
            block_rx.recv().ok();
            Ok(())
        });
        started_rx.recv_timeout(Duration::from_secs(2)).expect("blocker should start");
        let (order_tx, order_rx) = mpsc::channel();
        let low_tx = order_tx.clone();
        let low = jobs.submit(Priority::Background, move |_| {
            low_tx.send("low").ok();
            Ok(())
        });
        let high = jobs.submit(Priority::Urgent, move |_| {
            order_tx.send("urgent").ok();
            Ok(())
        });
        block_tx.send(()).ok();
        assert_eq!(order_rx.recv_timeout(Duration::from_secs(2)).expect("urgent result"), "urgent");
        assert_eq!(order_rx.recv_timeout(Duration::from_secs(2)).expect("background result"), "low");
        assert_eq!(completed(&blocker), Ok(()));
        assert_eq!(completed(&high), Ok(()));
        assert_eq!(completed(&low), Ok(()));
    }

    #[test]
    fn latest_key_cancels_prior_job() {
        let jobs = JobSystem::new(1);
        let (release_tx, release_rx) = mpsc::channel();
        let (started_tx, started_rx) = mpsc::channel();
        let old = jobs.submit_latest("document", Priority::Normal, move |ctx| {
            started_tx.send(()).ok();
            release_rx.recv().ok();
            ctx.check_cancelled()?;
            Ok(1)
        });
        started_rx.recv_timeout(Duration::from_secs(2)).expect("old job should start");
        let new = jobs.submit_latest("document", Priority::Interactive, |_| Ok(2));
        assert!(old.is_cancelled());
        release_tx.send(()).ok();
        assert_eq!(completed(&old), Err(JobError::Cancelled));
        assert_eq!(completed(&new), Ok(2));
    }
}
