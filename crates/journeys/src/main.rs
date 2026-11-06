//! App-level journey runner. App adapters are one-shot commands: they consume one pinned input,
//! exercise the app's existing performance channel, and print a stable result to stdout.

use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};

use craft_bench::{Config, Paired, Report, report::Revs};
use serde::Deserialize;
use sha2::{Digest, Sha256};

const USAGE: &str = "usage:\n  craft-journeys run --journey X --out file.json\n  craft-journeys compare --base REV --head REV --journey X";

#[derive(Debug, Deserialize)]
struct Catalog {
    journeys: Vec<Journey>,
}

#[derive(Debug, Clone, Deserialize)]
struct Journey {
    name: String,
    app: String,
    repo: PathBuf,
    build: CommandSpec,
    run: CommandSpec,
    inputs: Vec<Input>,
}

#[derive(Debug, Clone, Deserialize)]
struct Input {
    name: String,
    path: PathBuf,
}

#[derive(Debug, Clone, Deserialize)]
struct CommandSpec {
    program: String,
    #[serde(default)]
    args: Vec<String>,
}

#[derive(Debug)]
struct AppResult {
    duration_ns: u64,
    identity: String,
}

fn catalog() -> Result<Catalog, String> {
    let path = std::env::var_os("CRAFT_JOURNEYS_CONFIG")
        .map_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("journeys/catalog.json"), PathBuf::from);
    let bytes = std::fs::read(&path).map_err(|e| format!("{}: {e}", path.display()))?;
    serde_json::from_slice(&bytes).map_err(|e| format!("{}: {e}", path.display()))
}

fn choose(catalog: Catalog, name: &str) -> Result<Journey, String> {
    catalog.journeys.into_iter().find(|j| j.name == name).ok_or_else(|| format!("unknown journey {name:?}"))
}

fn render(s: &str, rev: &str, input: &Input, app: &str) -> String {
    s.replace("{rev}", rev).replace("{input}", &input.path.to_string_lossy()).replace("{input_name}", &input.name).replace("{app}", app)
}

fn run_command(spec: &CommandSpec, cwd: &Path, rev: &str, input: &Input, app: &str) -> Result<AppResult, String> {
    let mut cmd = Command::new(render(&spec.program, rev, input, app));
    cmd.current_dir(cwd).env("CRAFT_JOURNEY_REV", rev).env("ARTCRAFT_CORPUS", corpus_root());
    cmd.args(spec.args.iter().map(|a| render(a, rev, input, app)));
    let output = cmd.output().map_err(|e| format!("launch {}: {e}", spec.program))?;
    if !output.status.success() {
        return Err(format!(
            "{} failed ({})\n{}\n{}",
            spec.program,
            output.status,
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        ));
    }
    // The adapter emits a stable `CRAFT_OUTPUT_SHA256=<hex>` line for semantic identity. This
    // avoids comparing timing text or logs, which naturally differ from run to run.
    let stdout = String::from_utf8_lossy(&output.stdout);
    let duration_ns = stdout
        .lines()
        .find_map(|line| line.strip_prefix("CRAFT_JOURNEY_NS="))
        .ok_or_else(|| "adapter output is missing CRAFT_JOURNEY_NS=<integer>".to_string())?
        .parse::<u64>()
        .map_err(|e| format!("invalid CRAFT_JOURNEY_NS: {e}"))?;
    let identity = stdout
        .lines()
        .find_map(|line| line.strip_prefix("CRAFT_OUTPUT_SHA256="))
        .map(str::to_owned)
        .unwrap_or_else(|| format!("{:x}", Sha256::digest(&output.stdout)));
    Ok(AppResult { duration_ns, identity })
}

fn corpus_root() -> String {
    std::env::var("ARTCRAFT_CORPUS").unwrap_or_else(|_| "../../corpus".to_string())
}

fn execute(journey: &Journey, old_rev: &str, new_rev: &str, out: Option<&Path>) -> Result<Report, String> {
    if journey.inputs.is_empty() {
        return Err(format!("journey {} has no pinned inputs", journey.name));
    }
    for input in &journey.inputs {
        let resolved = if input.path.is_absolute() { input.path.clone() } else { PathBuf::from(corpus_root()).join(&input.path) };
        if !resolved.exists() {
            return Err(format!("pinned corpus input does not exist: {}", resolved.display()));
        }
    }
    let cwd = if journey.repo.is_absolute() { journey.repo.clone() } else { std::env::current_dir().map_err(|e| e.to_string())?.join(&journey.repo) };
    if !cwd.is_dir() {
        return Err(format!("app repo does not exist: {}", cwd.display()));
    }
    for rev in [old_rev, new_rev] {
        let mut cmd = Command::new(render(&journey.build.program, rev, &journey.inputs[0], &journey.app));
        cmd.current_dir(&cwd).env("CRAFT_JOURNEY_REV", rev).env("ARTCRAFT_CORPUS", corpus_root());
        cmd.args(journey.build.args.iter().map(|a| render(a, rev, &journey.inputs[0], &journey.app)));
        let result = cmd.output().map_err(|e| format!("build {} at {rev}: {e}", journey.app))?;
        if !result.status.success() {
            return Err(format!("build {} at {rev} failed ({})\n{}", journey.app, result.status, String::from_utf8_lossy(&result.stderr)));
        }
    }
    let input_pairs: Vec<_> = journey.inputs.iter().cloned().map(|i| (i.name.clone(), i)).collect();
    let report = Paired::new(format!("{} / {}", journey.app, journey.name))
        .old(|input: &Input| {
            run_command(&journey.run, &cwd, old_rev, input, &journey.app)
                .unwrap_or_else(|e| AppResult { duration_ns: 0, identity: format!("ERROR: {e}") })
        })
        .new(|input: &Input| {
            run_command(&journey.run, &cwd, new_rev, input, &journey.app)
                .unwrap_or_else(|e| AppResult { duration_ns: 0, identity: format!("ERROR: {e}") })
        })
        .inputs(input_pairs)
        .check(|a, b| !a.identity.starts_with("ERROR:") && a.identity == b.identity)
        .wall_meter(|output| output.duration_ns)
        .run(&Config { revs: Revs { old: Some(old_rev.to_string()), new: Some(new_rev.to_string()) }, ..Config::default() })
        .map_err(|e| e.to_string())?;
    if let Some(path) = out {
        std::fs::write(path, report.to_json()).map_err(|e| format!("{}: {e}", path.display()))?;
    }
    Ok(report)
}

fn arg(args: &[String], flag: &str) -> Result<String, String> {
    let pos = args.iter().position(|v| v == flag).ok_or_else(|| format!("missing {flag}\n{USAGE}"))?;
    args.get(pos + 1).cloned().ok_or_else(|| format!("{flag} needs a value"))
}

fn execute_cli(args: &[String]) -> Result<bool, String> {
    match args.first().map(String::as_str) {
        Some("run") => {
            let journey = choose(catalog()?, &arg(args, "--journey")?)?;
            let current = std::env::var("CRAFT_JOURNEY_REV").unwrap_or_else(|_| "working-tree".into());
            let report = execute(&journey, &current, &current, Some(Path::new(&arg(args, "--out")?)))?;
            print!("{}", report.to_markdown());
            Ok(report.publishable)
        }
        Some("compare") => {
            let (base, head) = (arg(args, "--base")?, arg(args, "--head")?);
            let journey = choose(catalog()?, &arg(args, "--journey")?)?;
            let report = execute(&journey, &base, &head, None)?;
            print!("{}", report.to_markdown());
            println!("verdict: {}", report.aggregate.wall.verdict().label());
            Ok(report.publishable)
        }
        _ => Err(USAGE.to_string()),
    }
}

fn main() -> ExitCode {
    match execute_cli(&std::env::args().skip(1).collect::<Vec<_>>()) {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::from(1),
        Err(error) => {
            eprintln!("{error}");
            ExitCode::from(2)
        }
    }
}
