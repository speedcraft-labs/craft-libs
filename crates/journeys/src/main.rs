//! App-level journey runner. App adapters are one-shot commands: they consume one pinned input,
//! exercise the app's existing performance channel, and print a stable result to stdout.

use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};
use std::time::{SystemTime, UNIX_EPOCH};

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
    /// Output protocol: `markers` (default) or a native app channel parser.
    #[serde(default)]
    output: OutputProtocol,
}

#[derive(Debug, Clone, Copy, Default, Deserialize)]
#[serde(rename_all = "kebab-case")]
enum OutputProtocol {
    #[default]
    Markers,
    CadcraftOpen,
    WordcraftProbe,
    DeckcraftBench,
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
    let path = if input.path.is_absolute() { input.path.clone() } else { PathBuf::from(corpus_root()).join(&input.path) };
    s.replace("{rev}", rev).replace("{input}", &path.to_string_lossy()).replace("{input_name}", &input.name).replace("{app}", app)
}

fn run_command(spec: &CommandSpec, cwd: &Path, rev: &str, input: &Input, app: &str, cargo_config: &Path) -> Result<AppResult, String> {
    let mut cmd = Command::new(render(&spec.program, rev, input, app));
    cmd.current_dir(cwd)
        .env("CRAFT_JOURNEY_REV", rev)
        .env("ARTCRAFT_CORPUS", corpus_root())
        .env("CARGO_TARGET_DIR", target_dir(app, rev))
        .env("SQLX_OFFLINE", "true")
        .env("RUST_MIN_STACK", "8388608");
    if let Some(root) = std::env::var_os("ARTCRAFT_HYPER_ROOT") {
        let root = PathBuf::from(root);
        cmd.env("CRAFT_I18N_DIR", root.join("repos/libs/craft-i18n")).env("CRAFT_FONTS_DIR", root.join("repos/libs/craft-fonts"));
    }
    if Path::new(&spec.program).file_name().is_some_and(|name| name == "cargo") {
        cmd.args(["--config"]).arg(cargo_config);
    }
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
    let (duration_ns, identity) = match spec.output {
        OutputProtocol::Markers => {
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
            (duration_ns, identity)
        }
        OutputProtocol::CadcraftOpen => {
            let line =
                stdout.lines().find(|line| line.starts_with("open ")).ok_or_else(|| "cadcraft perf output is missing its open timing".to_string())?;
            let rest = line.strip_prefix("open ").ok_or_else(|| "invalid cadcraft perf output".to_string())?;
            let (millis, identity) = rest.split_once(" ms,").ok_or_else(|| "cadcraft perf output is missing `ms,`".to_string())?;
            let millis = millis.trim().parse::<f64>().map_err(|e| format!("invalid cadcraft open time: {e}"))?;
            if !millis.is_finite() || millis < 0.0 {
                return Err("cadcraft open time must be finite and non-negative".into());
            }
            ((millis * 1_000_000.0) as u64, format!("{:x}", Sha256::digest(identity.trim().as_bytes())))
        }
        OutputProtocol::WordcraftProbe | OutputProtocol::DeckcraftBench => {
            let value: serde_json::Value = serde_json::from_str(stdout.trim()).map_err(|e| format!("invalid app JSON output: {e}"))?;
            let (millis, identity) = match spec.output {
                OutputProtocol::WordcraftProbe => (
                    value.get("open_ms").and_then(serde_json::Value::as_f64).ok_or_else(|| "wordcraft probe JSON is missing open_ms".to_string())?,
                    value
                        .get("typing_para_len")
                        .and_then(serde_json::Value::as_u64)
                        .ok_or_else(|| "wordcraft probe JSON is missing typing_para_len".to_string())?
                        .to_string(),
                ),
                OutputProtocol::DeckcraftBench => {
                    let open_ms = value
                        .get("steps")
                        .and_then(serde_json::Value::as_array)
                        .and_then(|steps| steps.iter().find(|s| s.get("step").and_then(serde_json::Value::as_str) == Some("open")))
                        .and_then(|s| s.get("medianMs"))
                        .and_then(serde_json::Value::as_f64)
                        .ok_or_else(|| "deckcraft bench JSON is missing open medianMs".to_string())?;
                    let slides = value
                        .get("slides")
                        .and_then(serde_json::Value::as_u64)
                        .ok_or_else(|| "deckcraft bench JSON is missing slides".to_string())?;
                    (open_ms, slides.to_string())
                }
                _ => return Err("invalid JSON output protocol".into()),
            };
            if !millis.is_finite() || millis < 0.0 {
                return Err("app time must be finite and non-negative".into());
            }
            ((millis * 1_000_000.0) as u64, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
    };
    Ok(AppResult { duration_ns, identity })
}

fn corpus_root() -> String {
    std::env::var("ARTCRAFT_CORPUS")
        .unwrap_or_else(|_| std::env::var("ARTCRAFT_HYPER_ROOT").map_or_else(|_| "../../corpus".to_string(), |root| format!("{root}/corpus")))
}

fn verify_corpus_input(path: &Path) -> Result<(), String> {
    let root = PathBuf::from(corpus_root());
    let resolved = if path.is_absolute() { path.to_path_buf() } else { root.join(path) };
    let relative = resolved.strip_prefix(&root).map_err(|_| format!("corpus input must be under {}: {}", root.display(), resolved.display()))?;
    let mut components = relative.components();
    let dataset_component = components.next().ok_or_else(|| format!("invalid corpus path: {}", relative.display()))?;
    if !matches!(dataset_component, std::path::Component::Normal(_)) {
        return Err(format!("invalid corpus path: {}", relative.display()));
    }
    let dataset = dataset_component.as_os_str().to_str().ok_or_else(|| format!("invalid corpus path: {}", relative.display()))?;
    let file = components.as_path();
    if file.as_os_str().is_empty() || file.components().any(|c| !matches!(c, std::path::Component::Normal(_))) {
        return Err(format!("invalid corpus path: {}", relative.display()));
    }
    let manifest_path = root.join(dataset).join(".craft-corpus.json");
    let manifest: serde_json::Value =
        serde_json::from_slice(&std::fs::read(&manifest_path).map_err(|e| format!("{}: {e}", manifest_path.display()))?)
            .map_err(|e| format!("{}: {e}", manifest_path.display()))?;
    let file_name = file.to_string_lossy();
    let entry = manifest
        .get("files")
        .and_then(serde_json::Value::as_array)
        .and_then(|files| files.iter().find(|item| item.get("path").and_then(serde_json::Value::as_str) == Some(file_name.as_ref())))
        .ok_or_else(|| format!("input is not listed in {}: {}", manifest_path.display(), file.display()))?;
    let expected =
        entry.get("sha256").and_then(serde_json::Value::as_str).ok_or_else(|| format!("manifest entry has no sha256: {}", file.display()))?;
    let bytes = std::fs::read(&resolved).map_err(|e| format!("{}: {e}", resolved.display()))?;
    let actual = format!("{:x}", Sha256::digest(bytes));
    if actual != expected {
        return Err(format!("corpus input hash mismatch for {}: expected {expected}, got {actual}", resolved.display()));
    }
    Ok(())
}

fn app_repo(path: &Path) -> Result<PathBuf, String> {
    if let Some(suffix) = path.to_string_lossy().strip_prefix("$ARTCRAFT_HYPER_ROOT/") {
        let root = std::env::var_os("ARTCRAFT_HYPER_ROOT").ok_or("set ARTCRAFT_HYPER_ROOT to the hyper checkout")?;
        return Ok(PathBuf::from(root).join(suffix));
    }
    if path.is_absolute() { Ok(path.to_path_buf()) } else { Ok(std::env::current_dir().map_err(|e| e.to_string())?.join(path)) }
}

struct AppCheckout {
    repo: PathBuf,
    path: PathBuf,
    owned_worktree: bool,
}

impl AppCheckout {
    fn at(repo: &Path, rev: &str, side: usize) -> Result<Self, String> {
        if rev == "working-tree" {
            return Ok(Self { repo: repo.to_path_buf(), path: repo.to_path_buf(), owned_worktree: false });
        }
        let nonce = SystemTime::now().duration_since(UNIX_EPOCH).map_err(|e| e.to_string())?.as_nanos();
        let path = std::env::temp_dir().join(format!("craft-journeys-{}-{side}-{nonce}", std::process::id()));
        let result = Command::new("git")
            .args(["worktree", "add", "--detach"])
            .arg(&path)
            .arg(rev)
            .current_dir(repo)
            .output()
            .map_err(|e| format!("launch git worktree for {rev}: {e}"))?;
        if !result.status.success() {
            return Err(format!("git worktree for {rev} failed ({}): {}", result.status, String::from_utf8_lossy(&result.stderr)));
        }
        Ok(Self { repo: repo.to_path_buf(), path, owned_worktree: true })
    }
}

impl Drop for AppCheckout {
    fn drop(&mut self) {
        if self.owned_worktree {
            let _ = Command::new("git").args(["worktree", "remove", "--force"]).arg(&self.path).current_dir(&self.repo).output();
        }
    }
}

struct LibRevision {
    _checkout: AppCheckout,
    cargo_config: PathBuf,
}

impl LibRevision {
    fn at(repo: &Path, rev: &str, side: usize) -> Result<Self, String> {
        let checkout = AppCheckout::at(repo, rev, side)?;
        let metadata = Command::new("cargo")
            .args(["metadata", "--no-deps", "--format-version", "1", "--manifest-path"])
            .arg(checkout.path.join("Cargo.toml"))
            .current_dir(&checkout.path)
            .output()
            .map_err(|e| format!("launch cargo metadata for craft-libs {rev}: {e}"))?;
        if !metadata.status.success() {
            return Err(format!("cargo metadata for craft-libs {rev} failed: {}", String::from_utf8_lossy(&metadata.stderr)));
        }
        let metadata: serde_json::Value = serde_json::from_slice(&metadata.stdout).map_err(|e| format!("invalid craft-libs cargo metadata: {e}"))?;
        let mut config = String::from("[patch.\"https://github.com/storytold/craft-libs\"]\n");
        let packages = metadata.get("packages").and_then(serde_json::Value::as_array).ok_or("cargo metadata has no package list")?;
        for package in packages {
            let name = package.get("name").and_then(serde_json::Value::as_str).ok_or("cargo metadata package has no name")?;
            let manifest = package.get("manifest_path").and_then(serde_json::Value::as_str).ok_or("cargo metadata package has no manifest_path")?;
            let dir = Path::new(manifest).parent().ok_or_else(|| format!("invalid manifest path: {manifest}"))?;
            config.push_str(&format!("{} = {{ path = {} }}\n", toml_string(name), toml_string(&dir.to_string_lossy())));
        }
        let mut vendors = Vec::new();
        let vendor = checkout.path.join("vendor");
        if vendor.is_dir() {
            for entry in std::fs::read_dir(&vendor).map_err(|e| format!("{}: {e}", vendor.display()))? {
                let dir = entry.map_err(|e| e.to_string())?.path();
                let manifest = dir.join("Cargo.toml");
                if !manifest.is_file() {
                    continue;
                }
                let source = std::fs::read_to_string(&manifest).map_err(|e| format!("{}: {e}", manifest.display()))?;
                if let Some(name) = package_name(&source) {
                    vendors.push((name, dir));
                }
            }
        }
        if !vendors.is_empty() {
            config.push_str("\n[patch.crates-io]\n");
            for (name, dir) in vendors {
                config.push_str(&format!("{} = {{ path = {} }}\n", toml_string(&name), toml_string(&dir.to_string_lossy())));
            }
        }
        let nonce = SystemTime::now().duration_since(UNIX_EPOCH).map_err(|e| e.to_string())?.as_nanos();
        let cargo_config = std::env::temp_dir().join(format!("craft-journeys-cargo-{}-{side}-{nonce}.toml", std::process::id()));
        std::fs::write(&cargo_config, config).map_err(|e| format!("{}: {e}", cargo_config.display()))?;
        Ok(Self { _checkout: checkout, cargo_config })
    }
}

impl Drop for LibRevision {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.cargo_config);
    }
}

fn package_name(manifest: &str) -> Option<String> {
    let mut in_package = false;
    for line in manifest.lines() {
        let line = line.trim();
        if line.starts_with('[') {
            in_package = line == "[package]";
        }
        if in_package && let Some(value) = line.strip_prefix("name =") {
            return Some(value.trim().trim_matches('"').to_string());
        }
    }
    None
}

fn toml_string(value: &str) -> String {
    format!("\"{}\"", value.replace('\\', "\\\\").replace('"', "\\\"").replace('\n', "\\n"))
}

fn craft_libs_repo() -> Result<PathBuf, String> {
    if let Some(path) = std::env::var_os("CRAFT_LIBS_REPO") {
        return Ok(PathBuf::from(path));
    }
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.ancestors().nth(2).map(Path::to_path_buf).ok_or_else(|| "cannot locate craft-libs workspace root".to_string())
}

fn target_dir(app: &str, rev: &str) -> PathBuf {
    let root = std::env::var_os("CRAFT_JOURNEYS_TARGET_DIR")
        .map_or_else(|| PathBuf::from("/jobs/work/speedcraft-labs/targets/craft-journeys"), PathBuf::from);
    let rev_hash = format!("{:x}", Sha256::digest(rev.as_bytes()));
    root.join(app).join(&rev_hash[..16])
}

fn execute(journey: &Journey, old_rev: &str, new_rev: &str, out: Option<&Path>) -> Result<Report, String> {
    if journey.inputs.is_empty() {
        return Err(format!("journey {} has no pinned inputs", journey.name));
    }
    for input in &journey.inputs {
        verify_corpus_input(&input.path)?;
    }
    let repo = app_repo(&journey.repo)?;
    if !repo.is_dir() {
        return Err(format!("app repo does not exist: {}", repo.display()));
    }
    let checkouts = [AppCheckout::at(&repo, "HEAD", 0)?, AppCheckout::at(&repo, "HEAD", 1)?];
    let lib_repo = craft_libs_repo()?;
    let revisions = [LibRevision::at(&lib_repo, old_rev, 0)?, LibRevision::at(&lib_repo, new_rev, 1)?];
    for (rev, checkout, libs) in [(old_rev, &checkouts[0], &revisions[0]), (new_rev, &checkouts[1], &revisions[1])] {
        let mut cmd = Command::new(render(&journey.build.program, rev, &journey.inputs[0], &journey.app));
        cmd.current_dir(&checkout.path)
            .env("CRAFT_JOURNEY_REV", rev)
            .env("ARTCRAFT_CORPUS", corpus_root())
            .env("CARGO_TARGET_DIR", target_dir(&journey.app, rev))
            .env("SQLX_OFFLINE", "true")
            .env("RUST_MIN_STACK", "8388608");
        if let Some(root) = std::env::var_os("ARTCRAFT_HYPER_ROOT") {
            let root = PathBuf::from(root);
            cmd.env("CRAFT_I18N_DIR", root.join("repos/libs/craft-i18n")).env("CRAFT_FONTS_DIR", root.join("repos/libs/craft-fonts"));
        }
        if Path::new(&journey.build.program).file_name().is_some_and(|name| name == "cargo") {
            cmd.args(["--config"]).arg(&libs.cargo_config);
        }
        cmd.args(journey.build.args.iter().map(|a| render(a, rev, &journey.inputs[0], &journey.app)));
        let result = cmd.output().map_err(|e| format!("build {} at {rev}: {e}", journey.app))?;
        if !result.status.success() {
            return Err(format!("build {} at {rev} failed ({})\n{}", journey.app, result.status, String::from_utf8_lossy(&result.stderr)));
        }
    }
    let input_pairs: Vec<_> = journey.inputs.iter().cloned().map(|i| (i.name.clone(), i)).collect();
    let report = Paired::new(format!("{} / {}", journey.app, journey.name))
        .old(|input: &Input| {
            run_command(&journey.run, &checkouts[0].path, old_rev, input, &journey.app, &revisions[0].cargo_config)
                .unwrap_or_else(|e| AppResult { duration_ns: 0, identity: format!("ERROR: {e}") })
        })
        .new(|input: &Input| {
            run_command(&journey.run, &checkouts[1].path, new_rev, input, &journey.app, &revisions[1].cargo_config)
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
            let out = args.iter().position(|v| v == "--out").and_then(|i| args.get(i + 1)).map(Path::new);
            let report = execute(&journey, &base, &head, out)?;
            print!("{}", report.to_markdown());
            if report.publishable {
                println!("verdict: {}", report.aggregate.wall.verdict().label());
            } else {
                println!("verdict: not publishable ({})", report.publish_problems().join("; "));
            }
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
