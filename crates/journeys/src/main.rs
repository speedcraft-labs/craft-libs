//! App-level journey runner. App adapters are one-shot commands: they consume one pinned input,
//! exercise the app's existing performance channel, and print a stable result to stdout.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};

use craft_bench::{Config, Paired, Report, report::Revs};
use serde::Deserialize;
use sha2::{Digest, Sha256};

const USAGE: &str = "usage:\n  craft-journeys run --journey X --out file.json [--no-build]\n  craft-journeys compare --base REV --head REV --journey X [--no-build]\n  craft-journeys prepare --base REV --head REV --journey X";

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
    #[serde(default)]
    run_head: Option<CommandSpec>,
    #[serde(default)]
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
    #[serde(default)]
    env: BTreeMap<String, String>,
    /// Extra Cargo config values after the craft-libs revision patches. This lets an adapter use
    /// an app-local patched dependency while keeping the rest of the revision's patch set.
    #[serde(default)]
    cargo_config_overrides: Vec<String>,
    /// Output protocol: `markers` (default) or a native app channel parser.
    #[serde(default)]
    output: OutputProtocol,
    /// Row in the app's native operation report (used when an app exposes several timings).
    #[serde(default)]
    measure: Option<String>,
}

#[derive(Debug, Clone, Copy, Default, Deserialize)]
#[serde(rename_all = "kebab-case")]
enum OutputProtocol {
    #[default]
    Markers,
    CadcraftOpen,
    CadcraftEdit,
    WordcraftProbe,
    DeckcraftBench,
    DeckcraftDrag,
    LightcraftDrag,
    PdfcraftExport,
    VectorcraftExport,
    DesigncraftPerf,
    EffectcraftOps,
    PhotocraftLargeImage,
    FigcraftPerf,
    GridcraftPerf,
    SoundcraftMix,
    FilmcraftProject,
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

fn render(s: &str, rev: &str, input: &Input, app: &str, app_repo: &Path) -> String {
    let path = resolve_input_path(&input.path);
    s.replace("{rev}", rev)
        .replace("{input}", &path.to_string_lossy())
        .replace("{input_name}", &input.name)
        .replace("{app}", app)
        .replace("{app_repo}", &app_repo.to_string_lossy())
}

fn run_command(spec: &CommandSpec, cwd: &Path, rev: &str, app_rev: &str, input: &Input, app: &str, cargo_config: &Path) -> Result<AppResult, String> {
    let app_binary = target_dir(app, rev, app_rev).join(format!("release/examples/perf_probe{}", std::env::consts::EXE_SUFFIX));
    let rendered_program = render(&spec.program, rev, input, app, cwd)
        .replace("{app_binary}", &app_binary.to_string_lossy())
        .replace("{target_dir}", &target_dir(app, rev, app_rev).to_string_lossy());
    let program = rendered_program;
    let mut cmd = Command::new(program);
    cmd.current_dir(cwd)
        .env("CRAFT_JOURNEY_REV", rev)
        .env("ARTCRAFT_CORPUS", corpus_root())
        .env("CARGO_TARGET_DIR", target_dir(app, rev, app_rev))
        .env("SQLX_OFFLINE", "true")
        .env("RUST_MIN_STACK", "8388608");
    if let Some(root) = std::env::var_os("ARTCRAFT_HYPER_ROOT") {
        let root = PathBuf::from(root);
        cmd.env("CRAFT_I18N_DIR", root.join("repos/libs/craft-i18n")).env("CRAFT_FONTS_DIR", root.join("repos/libs/craft-fonts"));
    }
    for (key, value) in &spec.env {
        cmd.env(key, render(value, rev, input, app, cwd));
    }
    if Path::new(&spec.program).file_name().is_some_and(|name| name == "cargo") {
        cmd.args(["--config"]).arg(cargo_config);
        for config in &spec.cargo_config_overrides {
            cmd.args(["--config"]).arg(render(config, rev, input, app, cwd));
        }
    }
    cmd.args(spec.args.iter().map(|a| render(a, rev, input, app, cwd)));
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
        OutputProtocol::CadcraftEdit => {
            if !stdout.lines().any(|line| line.contains("identical=true")) {
                return Err("cadcraft edit output did not confirm identical display lists".into());
            }
            let duration_ns = stdout
                .lines()
                .find_map(|line| line.strip_prefix("CRAFT_JOURNEY_NS="))
                .ok_or_else(|| "cadcraft edit output is missing CRAFT_JOURNEY_NS".to_string())?
                .parse::<u64>()
                .map_err(|e| format!("invalid cadcraft edit duration: {e}"))?;
            let identity = stdout
                .lines()
                .find_map(|line| line.strip_prefix("CRAFT_OUTPUT_HASH="))
                .ok_or_else(|| "cadcraft edit output is missing CRAFT_OUTPUT_HASH".to_string())?
                .to_owned();
            (duration_ns, identity)
        }
        OutputProtocol::WordcraftProbe | OutputProtocol::DeckcraftBench => {
            let value: serde_json::Value = serde_json::from_str(stdout.trim()).map_err(|e| format!("invalid app JSON output: {e}"))?;
            let (millis, identity) = match spec.output {
                OutputProtocol::WordcraftProbe => {
                    let first_page_ms = value
                        .get("open_to_first_page_ms")
                        .and_then(serde_json::Value::as_f64)
                        .ok_or_else(|| "wordcraft probe JSON is missing open_to_first_page_ms".to_string())?;
                    let page_count = value
                        .get("page_count")
                        .and_then(serde_json::Value::as_u64)
                        .ok_or_else(|| "wordcraft probe JSON is missing page_count".to_string())?;
                    let body_paragraphs = value
                        .get("body_paragraphs")
                        .and_then(serde_json::Value::as_u64)
                        .ok_or_else(|| "wordcraft probe JSON is missing body_paragraphs".to_string())?;
                    (first_page_ms, format!("{page_count}|{body_paragraphs}"))
                }
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
        OutputProtocol::DeckcraftDrag => {
            let value: serde_json::Value = serde_json::from_str(stdout.trim()).map_err(|e| format!("invalid deckcraft drag JSON: {e}"))?;
            let millis = value
                .get("p50_frame_ms")
                .and_then(serde_json::Value::as_f64)
                .ok_or_else(|| "deckcraft drag JSON is missing p50_frame_ms".to_string())?;
            if !millis.is_finite() || millis < 0.0 {
                return Err("deckcraft drag frame time must be finite and non-negative".into());
            }
            let identity = value
                .get("pixel_hash_sha256")
                .and_then(serde_json::Value::as_str)
                .ok_or_else(|| "deckcraft drag JSON is missing pixel_hash_sha256".to_string())?;
            let shape = value
                .get("shapes_on_slide")
                .and_then(serde_json::Value::as_u64)
                .ok_or_else(|| "deckcraft drag JSON is missing shapes_on_slide".to_string())?;
            ((millis * 1_000_000.0) as u64, format!("{shape}|{identity}"))
        }
        OutputProtocol::LightcraftDrag => {
            let line = stdout
                .lines()
                .find(|line| line.starts_with("light.exposure,"))
                .ok_or_else(|| "lightcraft drag output is missing the light.exposure row".to_string())?;
            let columns: Vec<_> = line.split(',').map(str::trim).collect();
            let millis = columns
                .get(3)
                .ok_or_else(|| "lightcraft drag output is missing lat_ms_med".to_string())?
                .parse::<f64>()
                .map_err(|e| format!("invalid lightcraft latency: {e}"))?;
            if !millis.is_finite() || millis < 0.0 {
                return Err("lightcraft latency must be finite and non-negative".into());
            }
            let identity = [columns.get(9), columns.get(10)].into_iter().flatten().copied().collect::<Vec<_>>().join(",");
            if identity.is_empty() {
                return Err("lightcraft output is missing texture dimensions".into());
            }
            ((millis * 1_000_000.0) as u64, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
        OutputProtocol::PdfcraftExport => {
            let line = stdout
                .lines()
                .find(|line| line.contains(" median ") && line.contains(" bytes, hash "))
                .ok_or_else(|| "pdfcraft export output is missing its summary".to_string())?;
            let millis = line
                .split_once(" median ")
                .and_then(|(_, rest)| rest.split_once(" ms,"))
                .map(|(value, _)| value)
                .ok_or_else(|| "pdfcraft export output is missing median milliseconds".to_string())?
                .parse::<f64>()
                .map_err(|e| format!("invalid pdfcraft export time: {e}"))?;
            if !millis.is_finite() || millis < 0.0 {
                return Err("pdfcraft export time must be finite and non-negative".into());
            }
            let identity = line
                .split_once(" bytes, hash ")
                .map(|(_, hash)| hash.trim())
                .filter(|hash| !hash.is_empty())
                .ok_or_else(|| "pdfcraft export output is missing its output hash".to_string())?;
            ((millis * 1_000_000.0) as u64, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
        OutputProtocol::VectorcraftExport => {
            let line = stdout
                .lines()
                .find(|line| line.contains(": median ") && line.ends_with(" bytes)"))
                .ok_or_else(|| "vectorcraft export output is missing its summary".to_string())?;
            let (label, rest) = line.split_once(": median ").ok_or_else(|| "vectorcraft export output is missing its file label".to_string())?;
            let (millis, rest) =
                rest.split_once(" ms, min ").ok_or_else(|| "vectorcraft export output is missing median milliseconds".to_string())?;
            let millis = millis.parse::<f64>().map_err(|e| format!("invalid vectorcraft export time: {e}"))?;
            if !millis.is_finite() || millis < 0.0 {
                return Err("vectorcraft export time must be finite and non-negative".into());
            }
            let bytes = rest
                .strip_suffix(" bytes)")
                .and_then(|r| r.rsplit_once('('))
                .map(|(_, count)| count)
                .ok_or_else(|| "vectorcraft export output is missing output size".to_string())?
                .parse::<u64>()
                .map_err(|e| format!("invalid vectorcraft output size: {e}"))?;
            let identity = format!("{label}:{bytes}");
            ((millis * 1_000_000.0) as u64, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
        OutputProtocol::DesigncraftPerf => {
            let summary = stdout
                .lines()
                .find(|line| line.starts_with("DesignCraft performance budgets — synthetic: "))
                .ok_or_else(|| "designcraft perf output is missing its synthetic document summary".to_string())?;
            let identity = summary
                .strip_prefix("DesignCraft performance budgets — synthetic: ")
                .and_then(|s| s.split_once(" (built in ").map(|(stable, _)| stable))
                .ok_or_else(|| "designcraft perf output is missing stable document details".to_string())?;
            let measured = stdout
                .lines()
                .find(|line| line.contains("compose all stories cold, MT ("))
                .ok_or_else(|| "designcraft perf output is missing the compose measurement".to_string())?;
            let fields: Vec<_> = measured.split_whitespace().collect();
            let millis = fields
                .iter()
                .position(|field| *field == "ms")
                .and_then(|index| index.checked_sub(1).and_then(|previous| fields.get(previous)))
                .ok_or_else(|| "designcraft perf output is missing measured milliseconds".to_string())?
                .parse::<f64>()
                .map_err(|e| format!("invalid designcraft compose time: {e}"))?;
            if !millis.is_finite() || millis < 0.0 {
                return Err("designcraft compose time must be finite and non-negative".into());
            }
            ((millis * 1_000_000.0) as u64, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
        OutputProtocol::EffectcraftOps => {
            let value: serde_json::Value = serde_json::from_str(stdout.trim()).map_err(|e| format!("invalid effectcraft bench JSON: {e}"))?;
            let measures = value
                .get("measures")
                .and_then(serde_json::Value::as_array)
                .ok_or_else(|| "effectcraft bench JSON is missing measures".to_string())?;
            let measure_name = spec.measure.as_deref().unwrap_or("open");
            let measure = measures
                .iter()
                .find(|row| row.get("name").and_then(serde_json::Value::as_str) == Some(measure_name))
                .ok_or_else(|| format!("effectcraft bench JSON is missing the {measure_name} measurement"))?;
            let millis = measure
                .get("ms")
                .and_then(serde_json::Value::as_f64)
                .ok_or_else(|| format!("effectcraft {measure_name} measurement is missing ms"))?;
            if !millis.is_finite() || millis < 0.0 {
                return Err("effectcraft open time must be finite and non-negative".into());
            }
            let spec = value
                .get("spec")
                .and_then(serde_json::Value::as_str)
                .ok_or_else(|| "effectcraft bench JSON is missing its generated project spec".to_string())?;
            let note = measure.get("note").and_then(serde_json::Value::as_str).unwrap_or("");
            let identity = format!("{spec}|{measure_name}|{note}");
            ((millis * 1_000_000.0) as u64, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
        OutputProtocol::PhotocraftLargeImage => {
            let document = stdout
                .lines()
                .find(|line| line.starts_with("document "))
                .ok_or_else(|| "photocraft benchmark output is missing its document summary".to_string())?;
            let details = document.strip_prefix("document ").ok_or_else(|| "invalid photocraft document summary".to_string())?;
            let (dimensions, rest) = details.split_once(" (").ok_or_else(|| "photocraft summary is missing image dimensions".to_string())?;
            let op = rest.split_once(", op ").map(|(_, op)| op.trim()).ok_or_else(|| "photocraft summary is missing its operation".to_string())?;
            let measured = stdout
                .lines()
                .find(|line| line.starts_with("open (decode + document)"))
                .ok_or_else(|| "photocraft benchmark output is missing the open measurement".to_string())?;
            let fields: Vec<_> = measured.split_whitespace().collect();
            let millis = fields
                .iter()
                .position(|field| *field == "ms")
                .and_then(|index| index.checked_sub(1).and_then(|previous| fields.get(previous)))
                .ok_or_else(|| "photocraft benchmark output is missing measured milliseconds".to_string())?
                .parse::<f64>()
                .map_err(|e| format!("invalid photocraft open time: {e}"))?;
            if !millis.is_finite() || millis < 0.0 {
                return Err("photocraft open time must be finite and non-negative".into());
            }
            let identity = format!("{dimensions}|{op}");
            ((millis * 1_000_000.0) as u64, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
        OutputProtocol::FigcraftPerf => {
            let title = stdout
                .lines()
                .find(|line| line.starts_with("figcraft perf ("))
                .ok_or_else(|| "figcraft perf output is missing its title".to_string())?;
            let header = stdout
                .lines()
                .find(|line| line.starts_with("| operation |"))
                .ok_or_else(|| "figcraft perf output is missing its layer-count header".to_string())?;
            let line = stdout
                .lines()
                .find(|line| line.starts_with("| render 1440×900 @100% |"))
                .ok_or_else(|| "figcraft perf output is missing its viewport render row".to_string())?;
            let cells: Vec<_> = line.split('|').map(str::trim).collect();
            let millis = cells
                .get(2)
                .ok_or_else(|| "figcraft perf render row is missing a measurement".to_string())?
                .parse::<f64>()
                .map_err(|e| format!("invalid figcraft render time: {e}"))?;
            if !millis.is_finite() || millis < 0.0 {
                return Err("figcraft render time must be finite and non-negative".into());
            }
            let identity = format!("{title}|{header}|render 1440×900 @100%");
            ((millis * 1_000_000.0) as u64, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
        OutputProtocol::GridcraftPerf => {
            let summary = stdout
                .lines()
                .find(|line| line.starts_with("fill ") && line.contains("x6 values:"))
                .ok_or_else(|| "gridcraft perf output is missing its row-count summary".to_string())?;
            let shape = summary.split_once(": ").map(|(shape, _)| shape).ok_or_else(|| "gridcraft perf summary is malformed".to_string())?;
            let saved = stdout
                .lines()
                .find(|line| line.starts_with("save xlsx ("))
                .ok_or_else(|| "gridcraft perf output is missing its workbook size".to_string())?;
            let bytes = saved
                .strip_prefix("save xlsx (")
                .and_then(|s| s.split_once(" bytes): ").map(|(size, _)| size))
                .ok_or_else(|| "gridcraft perf save summary is malformed".to_string())?;
            let open = stdout
                .lines()
                .find(|line| line.starts_with("open xlsx + full recalc:"))
                .and_then(|line| line.split_once(": ").map(|(_, timing)| timing))
                .ok_or_else(|| "gridcraft perf output is missing the open measurement".to_string())?;
            let duration_ns = parse_duration_debug_ns(open, "gridcraft")?;
            let identity = format!("{shape}|xlsx-bytes:{bytes}");
            (duration_ns, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
        OutputProtocol::SoundcraftMix => {
            let line = stdout
                .lines()
                .find(|line| line.contains(" tracks × ") && line.contains(": rendered in "))
                .ok_or_else(|| "soundcraft mix output is missing its render summary".to_string())?;
            let (workload, rest) = line.split_once(": rendered in ").ok_or_else(|| "soundcraft mix summary is malformed".to_string())?;
            let (seconds, rest) = rest.split_once(" s → ").ok_or_else(|| "soundcraft mix summary is missing rendered seconds".to_string())?;
            let seconds = seconds.parse::<f64>().map_err(|e| format!("invalid soundcraft render time: {e}"))?;
            if !seconds.is_finite() || seconds < 0.0 {
                return Err("soundcraft render time must be finite and non-negative".into());
            }
            let peak = rest
                .split_once("(peak ")
                .and_then(|(_, value)| value.strip_suffix(')'))
                .ok_or_else(|| "soundcraft mix summary is missing its output peak".to_string())?;
            let identity = format!("{workload}|peak:{peak}");
            let nanos = seconds * 1_000_000_000.0;
            if nanos > u64::MAX as f64 {
                return Err("soundcraft render time is too large".into());
            }
            (nanos as u64, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
        OutputProtocol::FilmcraftProject => {
            let value: serde_json::Value = serde_json::from_str(stdout.trim()).map_err(|e| format!("invalid filmcraft bench JSON: {e}"))?;
            let rows = value.get("rows").and_then(serde_json::Value::as_array).ok_or_else(|| "filmcraft bench JSON is missing rows".to_string())?;
            let open = rows
                .iter()
                .find(|row| row.get("what").and_then(serde_json::Value::as_str) == Some("open (file.open)"))
                .ok_or_else(|| "filmcraft project bench is missing the open measurement".to_string())?;
            let millis = open.get("p50_ms").and_then(serde_json::Value::as_f64).ok_or_else(|| "filmcraft open row is missing p50_ms".to_string())?;
            if !millis.is_finite() || millis < 0.0 {
                return Err("filmcraft open time must be finite and non-negative".into());
            }
            let clips =
                open.get("clips").and_then(serde_json::Value::as_u64).ok_or_else(|| "filmcraft open row is missing its clip count".to_string())?;
            let megabytes =
                open.get("mbytes").and_then(serde_json::Value::as_f64).ok_or_else(|| "filmcraft open row is missing project size".to_string())?;
            let identity = format!("{clips} clips|{megabytes:.1} MB project");
            ((millis * 1_000_000.0) as u64, format!("{:x}", Sha256::digest(identity.as_bytes())))
        }
    };
    Ok(AppResult { duration_ns, identity })
}

fn corpus_root() -> String {
    std::env::var("ARTCRAFT_CORPUS")
        .unwrap_or_else(|_| std::env::var("ARTCRAFT_HYPER_ROOT").map_or_else(|_| "../../corpus".to_string(), |root| format!("{root}/corpus")))
}

fn resolve_input_path(path: &Path) -> PathBuf {
    if path.is_absolute() {
        return path.to_path_buf();
    }
    if let Ok(relative) = path.strip_prefix(".journey-fixtures") {
        return PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("fixtures").join(relative);
    }
    PathBuf::from(corpus_root()).join(path)
}

fn verify_corpus_input(path: &Path) -> Result<(), String> {
    if let Ok(relative) = path.strip_prefix(".journey-fixtures") {
        let fixture = resolve_input_path(path);
        let parts: Vec<_> = relative.components().collect();
        if parts.len() < 2 || parts.iter().any(|part| !matches!(part, std::path::Component::Normal(_))) {
            return Err(format!("invalid journey fixture path: {}", path.display()));
        }
        let dataset = parts[0].as_os_str().to_string_lossy();
        let file = parts[1..].iter().fold(PathBuf::new(), |mut acc, part| {
            acc.push(part);
            acc
        });
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("fixtures").join(dataset.as_ref());
        let manifest_path = root.join(".craft-corpus.json");
        let manifest: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&manifest_path).map_err(|e| format!("{}: {e}", manifest_path.display()))?)
                .map_err(|e| format!("{}: {e}", manifest_path.display()))?;
        let expected = manifest
            .get("files")
            .and_then(serde_json::Value::as_array)
            .and_then(|files| files.iter().find(|item| item.get("path").and_then(serde_json::Value::as_str) == Some(file.to_string_lossy().as_ref())))
            .and_then(|item| item.get("sha256"))
            .and_then(serde_json::Value::as_str)
            .ok_or_else(|| format!("journey fixture is not pinned in {}: {}", manifest_path.display(), file.display()))?;
        let actual = format!("{:x}", Sha256::digest(std::fs::read(&fixture).map_err(|e| format!("{}: {e}", fixture.display()))?));
        return if actual == expected {
            Ok(())
        } else {
            Err(format!("journey fixture hash mismatch for {}: expected {expected}, got {actual}", fixture.display()))
        };
    }
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
    if let Some(path) = std::env::var_os("CRAFT_JOURNEYS_APP_REPO") {
        return Ok(PathBuf::from(path));
    }
    if let Some(suffix) = path.to_string_lossy().strip_prefix("$ARTCRAFT_HYPER_ROOT/") {
        let root = std::env::var_os("ARTCRAFT_HYPER_ROOT").ok_or("set ARTCRAFT_HYPER_ROOT to the hyper checkout")?;
        return Ok(PathBuf::from(root).join(suffix));
    }
    if path.is_absolute() { Ok(path.to_path_buf()) } else { Ok(std::env::current_dir().map_err(|e| e.to_string())?.join(path)) }
}

struct AppCheckout {
    repo: PathBuf,
    path: PathBuf,
}

impl AppCheckout {
    fn alias(checkout: &Self) -> Self {
        Self { repo: checkout.repo.clone(), path: checkout.path.clone() }
    }

    fn at(repo: &Path, rev: &str) -> Result<Self, String> {
        if rev == "working-tree" {
            return Ok(Self { repo: repo.to_path_buf(), path: repo.to_path_buf() });
        }
        let resolved = Command::new("git")
            .args(["rev-parse", "--verify"])
            .arg(format!("{rev}^{{commit}}"))
            .current_dir(repo)
            .output()
            .map_err(|e| format!("launch git rev-parse for {rev}: {e}"))?;
        if !resolved.status.success() {
            return Err(format!("git could not resolve {rev}: {}", String::from_utf8_lossy(&resolved.stderr)));
        }
        let commit = String::from_utf8_lossy(&resolved.stdout).trim().to_string();
        let repo_key = format!("{:x}", Sha256::digest(repo.to_string_lossy().as_bytes()));
        let commit_key = format!("{:x}", Sha256::digest(commit.as_bytes()));
        let path = target_root().join("worktrees").join(&repo_key[..16]).join(&commit_key[..16]);
        if path.exists() {
            let current = Command::new("git").args(["rev-parse", "--verify", "HEAD"]).current_dir(&path).output();
            if current.is_ok_and(|output| output.status.success() && String::from_utf8_lossy(&output.stdout).trim() == commit) {
                return Ok(Self { repo: repo.to_path_buf(), path });
            }
            let removed = Command::new("git")
                .args(["worktree", "remove", "--force"])
                .arg(&path)
                .current_dir(repo)
                .output()
                .map_err(|e| format!("remove stale craft-journeys worktree {}: {e}", path.display()))?;
            if !removed.status.success() {
                return Err(format!("remove stale craft-journeys worktree {} failed: {}", path.display(), String::from_utf8_lossy(&removed.stderr)));
            }
        }
        let parent = path.parent().ok_or_else(|| format!("invalid worktree path: {}", path.display()))?;
        std::fs::create_dir_all(parent).map_err(|e| format!("{}: {e}", parent.display()))?;
        let result = Command::new("git")
            .args(["worktree", "add", "--detach"])
            .arg(&path)
            .arg(&commit)
            .current_dir(repo)
            .output()
            .map_err(|e| format!("launch git worktree for {rev}: {e}"))?;
        if !result.status.success() {
            return Err(format!("git worktree for {rev} failed ({}): {}", result.status, String::from_utf8_lossy(&result.stderr)));
        }
        Ok(Self { repo: repo.to_path_buf(), path })
    }
}

struct LibRevision {
    _checkout: AppCheckout,
    cargo_config: PathBuf,
}

impl LibRevision {
    fn alias(revision: &Self) -> Self {
        Self { _checkout: AppCheckout::alias(&revision._checkout), cargo_config: revision.cargo_config.clone() }
    }

    fn at(repo: &Path, rev: &str) -> Result<Self, String> {
        let checkout = AppCheckout::at(repo, rev)?;
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
        let repo_key = format!("{:x}", Sha256::digest(repo.to_string_lossy().as_bytes()));
        let rev_key = format!("{:x}", Sha256::digest(checkout.path.to_string_lossy().as_bytes()));
        let config_dir = target_root().join("configs");
        std::fs::create_dir_all(&config_dir).map_err(|e| format!("{}: {e}", config_dir.display()))?;
        let cargo_config = config_dir.join(format!("{}-{}.toml", &repo_key[..16], &rev_key[..16]));
        std::fs::write(&cargo_config, config).map_err(|e| format!("{}: {e}", cargo_config.display()))?;
        Ok(Self { _checkout: checkout, cargo_config })
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

fn parse_duration_debug_ns(value: &str, app: &str) -> Result<u64, String> {
    let (number, scale) = if let Some(n) = value.strip_suffix("ns") {
        (n, 1.0)
    } else if let Some(n) = value.strip_suffix("µs") {
        (n, 1_000.0)
    } else if let Some(n) = value.strip_suffix("ms") {
        (n, 1_000_000.0)
    } else if let Some(n) = value.strip_suffix('s') {
        (n, 1_000_000_000.0)
    } else {
        return Err(format!("{app} benchmark has an unknown duration unit: {value:?}"));
    };
    let number = number.parse::<f64>().map_err(|e| format!("invalid {app} duration: {e}"))?;
    let nanos = number * scale;
    if !nanos.is_finite() || nanos < 0.0 || nanos > u64::MAX as f64 {
        return Err(format!("{app} duration must be finite and non-negative"));
    }
    Ok(nanos as u64)
}

fn craft_libs_repo() -> Result<PathBuf, String> {
    if let Some(path) = std::env::var_os("CRAFT_LIBS_REPO") {
        return Ok(PathBuf::from(path));
    }
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.ancestors().nth(2).map(Path::to_path_buf).ok_or_else(|| "cannot locate craft-libs workspace root".to_string())
}

fn target_root() -> PathBuf {
    std::env::var_os("CRAFT_JOURNEYS_TARGET_DIR").map_or_else(|| PathBuf::from("/jobs/work/speedcraft-labs/targets/craft-journeys"), PathBuf::from)
}

fn target_dir(app: &str, libs_rev: &str, app_rev: &str) -> PathBuf {
    let root = target_root();
    let revision_key = format!("{libs_rev}:{app_rev}");
    let rev_hash = format!("{:x}", Sha256::digest(revision_key.as_bytes()));
    root.join(app).join(&rev_hash[..16])
}

struct JourneyContext {
    inputs: Vec<Input>,
    app_base: String,
    app_head: String,
    checkouts: [AppCheckout; 2],
    revisions: [LibRevision; 2],
}

fn journey_context(journey: &Journey, old_rev: &str, new_rev: &str) -> Result<JourneyContext, String> {
    let mut inputs = journey.inputs.clone();
    if inputs.is_empty() {
        // App-owned deterministic generators (for example `designcraft-cli perf`) still provide
        // one measured case to craft-bench, but have no external file to verify or pass as input.
        inputs.push(Input { name: "synthetic".into(), path: PathBuf::new() });
    }
    for input in &inputs {
        if !input.path.as_os_str().is_empty() {
            verify_corpus_input(&input.path)?;
        }
    }
    let repo = app_repo(&journey.repo)?;
    if !repo.is_dir() {
        return Err(format!("app repo does not exist: {}", repo.display()));
    }
    let app_base = std::env::var("CRAFT_JOURNEYS_APP_BASE_REV").unwrap_or_else(|_| "HEAD".into());
    let app_head = std::env::var("CRAFT_JOURNEYS_APP_HEAD_REV").unwrap_or_else(|_| app_base.clone());
    let app_old = AppCheckout::at(&repo, &app_base)?;
    let app_new = if app_base == app_head { AppCheckout::alias(&app_old) } else { AppCheckout::at(&repo, &app_head)? };
    let checkouts = [app_old, app_new];
    let lib_repo = craft_libs_repo()?;
    let libs_old = LibRevision::at(&lib_repo, old_rev)?;
    let libs_new = if old_rev == new_rev { LibRevision::alias(&libs_old) } else { LibRevision::at(&lib_repo, new_rev)? };
    Ok(JourneyContext { inputs, app_base, app_head, checkouts, revisions: [libs_old, libs_new] })
}

fn build_app(journey: &Journey, rev: &str, app_rev: &str, input: &Input, checkout: &AppCheckout, libs: &LibRevision) -> Result<(), String> {
    let build_program = render(&journey.build.program, rev, input, &journey.app, &checkout.path);
    let cargo_build = Path::new(&build_program).file_name().is_some_and(|name| name == "cargo");
    let mut cmd = if cargo_build {
        let mut command = Command::new("nice");
        let build_jobs = std::env::var("CARGO_BUILD_JOBS").unwrap_or_else(|_| "6".into());
        command.args(["-n", "19", "cargo"]).env("CARGO_BUILD_JOBS", build_jobs);
        command
    } else {
        Command::new(build_program)
    };
    cmd.current_dir(&checkout.path)
        .env("CRAFT_JOURNEY_REV", rev)
        .env("ARTCRAFT_CORPUS", corpus_root())
        .env("CARGO_TARGET_DIR", target_dir(&journey.app, rev, app_rev))
        .env("SQLX_OFFLINE", "true")
        .env("RUST_MIN_STACK", "8388608");
    if let Some(root) = std::env::var_os("ARTCRAFT_HYPER_ROOT") {
        let root = PathBuf::from(root);
        cmd.env("CRAFT_I18N_DIR", root.join("repos/libs/craft-i18n")).env("CRAFT_FONTS_DIR", root.join("repos/libs/craft-fonts"));
    }
    if cargo_build {
        cmd.args(["--config"]).arg(&libs.cargo_config);
        for config in &journey.build.cargo_config_overrides {
            cmd.args(["--config"]).arg(render(config, rev, input, &journey.app, &checkout.path));
        }
    }
    cmd.args(journey.build.args.iter().map(|a| render(a, rev, input, &journey.app, &checkout.path)));
    let result = cmd.output().map_err(|e| format!("build {} at {rev}: {e}", journey.app))?;
    if !result.status.success() {
        return Err(format!("build {} at {rev} failed ({})\n{}", journey.app, result.status, String::from_utf8_lossy(&result.stderr)));
    }
    Ok(())
}

fn prepare(journey: &Journey, old_rev: &str, new_rev: &str) -> Result<(), String> {
    let context = journey_context(journey, old_rev, new_rev)?;
    for (rev, app_rev, checkout, libs) in [
        (old_rev, context.app_base.as_str(), &context.checkouts[0], &context.revisions[0]),
        (new_rev, context.app_head.as_str(), &context.checkouts[1], &context.revisions[1]),
    ] {
        build_app(journey, rev, app_rev, &context.inputs[0], checkout, libs)?;
    }
    Ok(())
}

fn execute(journey: &Journey, old_rev: &str, new_rev: &str, out: Option<&Path>, build: bool) -> Result<Report, String> {
    let context = journey_context(journey, old_rev, new_rev)?;
    if build {
        for (rev, app_rev, checkout, libs) in [
            (old_rev, context.app_base.as_str(), &context.checkouts[0], &context.revisions[0]),
            (new_rev, context.app_head.as_str(), &context.checkouts[1], &context.revisions[1]),
        ] {
            build_app(journey, rev, app_rev, &context.inputs[0], checkout, libs)?;
        }
    }
    let JourneyContext { inputs, app_base, app_head, checkouts, revisions } = context;
    let input_pairs: Vec<_> = inputs.into_iter().map(|i| (i.name.clone(), i)).collect();
    let head_run = journey.run_head.as_ref().unwrap_or(&journey.run);
    let mut report = Paired::new(format!("{} / {}", journey.app, journey.name))
        .old(|input: &Input| {
            run_command(&journey.run, &checkouts[0].path, old_rev, &app_base, input, &journey.app, &revisions[0].cargo_config)
                .unwrap_or_else(|e| AppResult { duration_ns: 0, identity: format!("ERROR: {e}") })
        })
        .new(|input: &Input| {
            run_command(head_run, &checkouts[1].path, new_rev, &app_head, input, &journey.app, &revisions[1].cargo_config)
                .unwrap_or_else(|e| AppResult { duration_ns: 0, identity: format!("ERROR: {e}") })
        })
        .inputs(input_pairs)
        .check(|a, b| !a.identity.starts_with("ERROR:") && a.identity == b.identity)
        .wall_meter(|output| output.duration_ns)
        .run(&Config { revs: Revs::default(), ..Config::default() })
        .map_err(|e| e.to_string())?;
    // A journey compares app code as well as the patched craft-libs checkout. Preserve both
    // revisions in the raw report so the measured implementation can be recreated later.
    report.revs = Revs { old: Some(format!("app:{app_base};craft-libs:{old_rev}")), new: Some(format!("app:{app_head};craft-libs:{new_rev}")) };
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
            let build = !args.iter().any(|value| value == "--no-build");
            let report = execute(&journey, &current, &current, Some(Path::new(&arg(args, "--out")?)), build)?;
            print!("{}", report.to_markdown());
            Ok(report.publishable)
        }
        Some("compare") => {
            let (base, head) = (arg(args, "--base")?, arg(args, "--head")?);
            let journey = choose(catalog()?, &arg(args, "--journey")?)?;
            let out = args.iter().position(|v| v == "--out").and_then(|i| args.get(i + 1)).map(Path::new);
            let build = !args.iter().any(|value| value == "--no-build");
            let report = execute(&journey, &base, &head, out, build)?;
            print!("{}", report.to_markdown());
            if report.publishable {
                println!("verdict: {}", report.aggregate.wall.verdict().label());
            } else {
                println!("verdict: not publishable ({})", report.publish_problems().join("; "));
            }
            Ok(report.publishable)
        }
        Some("prepare") => {
            let (base, head) = (arg(args, "--base")?, arg(args, "--head")?);
            let journey = choose(catalog()?, &arg(args, "--journey")?)?;
            prepare(&journey, &base, &head)?;
            println!("prepared {} for {base} → {head}", journey.name);
            Ok(true)
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
