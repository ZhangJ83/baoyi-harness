import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
BASE = PACKAGE_DIR
ROOT = PACKAGE_DIR.parent  # Development repo root fallback


def env_file_path() -> Path:
    """Resolve project configuration file path.

    Checks explicit BAOYI_ENV_FILE / ENV_FILE first, then active workspace .env,
    current working directory .env, and finally development repo root .env if present.
    """
    explicit = os.getenv("BAOYI_ENV_FILE", os.getenv("ENV_FILE", ""))
    if explicit:
        return Path(explicit).expanduser().resolve()
    ws = os.getenv("BAOYI_WORKSPACE", os.getenv("WORKSPACE", ""))
    if ws:
        ws_env = Path(ws).expanduser().resolve() / ".env"
        if ws_env.exists():
            return ws_env
    cwd_env = Path.cwd().resolve() / ".env"
    if cwd_env.exists():
        return cwd_env
    repo_env = PACKAGE_DIR.parent / ".env"
    if repo_env.exists() and (PACKAGE_DIR.parent / "pyproject.toml").is_file():
        return repo_env.resolve()
    return cwd_env


ENV_FILE = env_file_path()


def workspace_default() -> Path:
    """Default workspace root when none is explicitly configured."""
    repo_workspace = PACKAGE_DIR.parent / "workspace"
    if repo_workspace.is_dir() and (PACKAGE_DIR.parent / "pyproject.toml").is_file():
        return repo_workspace.resolve()
    return Path.cwd().resolve()


WORKSPACE = workspace_default()


def load_dotenv() -> None:
    path = env_file_path()
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def provider() -> str:
    return os.getenv("PROVIDER", "openai").strip().lower()


def api_base() -> str:
    return os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com").strip()


def model() -> str:
    return os.getenv("OPENAI_MODEL", "deepseek-v4-flash").strip()


def api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def anthropic_api_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "").strip()


def provider_api_key() -> str:
    """Return the credential selected by ``PROVIDER`` without exposing it."""
    return anthropic_api_key() if provider() == "anthropic" else api_key()


def provider_credential_name() -> str:
    """Name of the required environment variable for actionable CLI errors."""
    return "ANTHROPIC_API_KEY" if provider() == "anthropic" else "OPENAI_API_KEY"


def anthropic_api_base() -> str:
    return os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic").strip()


def anthropic_model() -> str:
    return os.getenv("ANTHROPIC_MODEL", "deepseek-v4-flash").strip()


def anthropic_max_tokens() -> int:
    try:
        return max(256, int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096")))
    except ValueError:
        return 4096


def max_steps() -> int:
    try:
        return max(1, int(os.getenv("MAX_STEPS", "25")))
    except ValueError:
        return 25


def int_setting(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def float_setting(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return default


def max_tool_calls() -> int:
    return int_setting("MAX_TOOL_CALLS", 120)


def max_total_tokens() -> int:
    return int_setting("MAX_TOTAL_TOKENS", 120_000)


def max_output_tokens() -> int:
    return int_setting("OPENAI_MAX_TOKENS", 4096)


def update_env_settings(updates: dict[str, str]) -> None:
    for k, v in updates.items():
        os.environ[k] = str(v)
    
    path = env_file_path()
    lines: list[str] = []
    existing_keys: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, _ = stripped.partition("=")
                key = k.strip()
                if key in updates:
                    lines.append(f"{key}={updates[key]}")
                    existing_keys.add(key)
                else:
                    lines.append(line)
            else:
                lines.append(line)
    
    for k, v in updates.items():
        if k not in existing_keys:
            lines.append(f"{k}={v}")
    
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def thinking_enabled() -> bool:
    """Whether the provider should run its supported thinking mode."""
    eff = os.getenv("REASONING_EFFORT", "high").strip().lower()
    if eff in {"off", "none", "0", "disabled"}:
        return False
    return os.getenv("THINKING_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def reasoning_effort() -> str:
    raw = os.getenv("REASONING_EFFORT", "high").strip().lower()
    if raw in {"off", "none", "0", "disabled"}:
        return "off"
    if raw in {"xhigh", "extreme", "very_high"}:
        return "max"
    if raw in {"low", "medium", "high", "max"}:
        return raw
    return "high"


def max_generated_output_tokens() -> int:
    return int_setting("MAX_GENERATED_OUTPUT_TOKENS", max_total_tokens())


def first_action_output_tokens() -> int:
    """Maximum generation spent before an action task must emit a tool call."""
    return int_setting("FIRST_ACTION_OUTPUT_TOKENS", 1600, minimum=256)


def api_retries() -> int:
    return int_setting("API_RETRIES", 3, minimum=0)


def api_timeout() -> float:
    return float_setting("API_TIMEOUT", 120.0, minimum=1.0)


def max_command_timeout() -> int:
    return int_setting("MAX_COMMAND_TIMEOUT", 600)


def max_cost_usd() -> float:
    return float_setting("MAX_COST_USD", 0.10)


def command_policy() -> str:
    value = os.getenv("COMMAND_POLICY", "ask").strip().lower()
    return value if value in {"allow", "ask", "deny"} else "ask"


def set_command_policy(value: str) -> None:
    """Persist the shell command policy for this process.

    Invalid values are ignored so UI/CLI callers fail closed to the
    ``command_policy()`` default instead of crashing the request.
    """
    policy = str(value or "").strip().lower()
    if policy in {"allow", "ask", "deny"}:
        os.environ["COMMAND_POLICY"] = policy


def isolated_benchmark() -> bool:
    return os.getenv("ISOLATED_BENCHMARK", "0").strip().lower() in {"1", "true", "yes"}


def strict_run_budget() -> bool:
    """Hard cumulative token gates are for reproducible benchmark runs.

    Interactive project work follows the Claude Code/Codex pattern: retain a
    per-request output cap, compact history, and continue until the task or
    step/tool safety limit ends the run.
    """
    explicit = os.getenv("STRICT_RUN_BUDGET")
    if explicit is not None:
        return explicit.strip().lower() in {"1", "true", "yes", "on"}
    return isolated_benchmark()


def record_mode() -> str:
    """Select how much operational evidence a run persists.

    Recording is deliberately orthogonal to task execution. ``minimal`` keeps
    only lifecycle milestones, ``audit`` keeps a compact operational journal,
    and ``research`` retains the largest redacted payloads for trajectory
    studies.  Invalid values fail closed to the compact production default.
    """
    value = os.getenv("BAOYI_RECORD_MODE", os.getenv("XIAOPU_RECORD_MODE", "audit")).strip().lower()
    return value if value in {"minimal", "audit", "research"} else "audit"


def sandbox_root() -> Path:
    explicit = os.getenv("BAOYI_WORKSPACE", os.getenv("WORKSPACE", ""))
    p = Path(explicit).expanduser().resolve() if explicit else workspace_default()
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_home() -> Path:
    """Durable per-user state: sessions, prompt history, exports."""
    default_home = str(Path.home() / ".baoyi")
    p = Path(os.getenv("BAOYI_HOME", os.getenv("XIAOPU_HOME", default_home)))
    p.mkdir(parents=True, exist_ok=True)
    return p


def plan_mode() -> bool:
    return os.getenv("PLAN_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}


def set_plan_mode(enabled: bool) -> None:
    os.environ["PLAN_MODE"] = "1" if enabled else "0"


def known_models() -> list[str]:
    """OpenAI-compatible model choices exposed to /model and CLI.

    Falls back to the active model plus any BAOYI_MODELS / XIAOPU_MODELS comma list,
    so a product build can publish a curated picker without editing code.
    """
    active = model() if provider() != "anthropic" else anthropic_model()
    raw_models = os.getenv("BAOYI_MODELS", os.getenv("XIAOPU_MODELS", ""))
    extras = [m.strip() for m in raw_models.split(",") if m.strip()]
    seen: list[str] = []
    for candidate in [active, *extras]:
        if candidate and candidate not in seen:
            seen.append(candidate)
    return seen


THEMES = ("dark", "light", "dracula")


def theme() -> str:
    value = os.getenv("BAOYI_THEME", os.getenv("XIAOPU_THEME", "dark")).strip().lower()
    return value if value in THEMES else "dark"


def set_theme(value: str) -> None:
    if value in THEMES:
        os.environ["BAOYI_THEME"] = value
        os.environ["XIAOPU_THEME"] = value


def keymap() -> str:
    value = os.getenv("BAOYI_KEYMAP", os.getenv("XIAOPU_KEYMAP", "default")).strip().lower()
    return value if value in {"default", "minimal"} else "default"


def set_keymap(value: str) -> None:
    if value in {"default", "minimal"}:
        os.environ["BAOYI_KEYMAP"] = value
        os.environ["XIAOPU_KEYMAP"] = value
