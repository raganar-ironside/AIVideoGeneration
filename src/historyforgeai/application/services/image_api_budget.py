"""Conservative *estimated* per-job image API request guard.

This is NOT a Google/OpenAI billing meter. Pricing varies by model,
resolution, tokens and billing tier; failed requests may also incur charges.
The ledger counts attempted calls before they leave the process.
"""
import fcntl
import json
import math
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_JOB_BUDGET_USD = 1.00
DEFAULT_ESTIMATE_USD = 0.25
DEFAULT_MAX_IMAGE_REQUESTS = 8


def _positive(value, name):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return number


def job_budget_limit(limit_usd=None) -> float:
    value = (limit_usd if limit_usd is not None else
             os.getenv("IMAGE_JOB_BUDGET_USD", str(DEFAULT_JOB_BUDGET_USD)))
    return _positive(value, "Per-job image budget")


def estimated_call_cost(provider: str) -> float:
    if provider not in ("gemini", "openai"):
        raise ValueError("Budget applies only to Gemini and OpenAI")
    return _positive(os.getenv(f"{provider.upper()}_IMAGE_ESTIMATED_USD",
                               str(DEFAULT_ESTIMATE_USD)),
                     f"{provider} image call estimate")


def _paths(job_dir: Path):
    folder = Path(job_dir).resolve() / "animation"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "image_api_usage.json", folder / ".image_api_usage.lock"


@contextmanager
def _locked_usage(job_dir):
    ledger_path, lock_path = _paths(job_dir)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            usage = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {
                "estimated_spend_usd": 0.0, "attempted_requests": 0, "requests": [],
            }
            yield ledger_path, usage
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def usage_summary(job_dir: Path) -> dict:
    with _locked_usage(job_dir) as (_, usage):
        return json.loads(json.dumps(usage))


def _check(usage: dict, provider: str, count: int, limit: float):
    estimate = estimated_call_cost(provider)
    if not isinstance(count, int) or count < 1:
        raise ValueError("Request count must be positive")
    max_requests = int(os.getenv("IMAGE_JOB_MAX_REQUESTS", str(DEFAULT_MAX_IMAGE_REQUESTS)))
    if max_requests < 1:
        raise ValueError("IMAGE_JOB_MAX_REQUESTS must be at least 1")
    attempted = usage.get("attempted_requests", 0)
    projected = usage.get("estimated_spend_usd", 0.0) + estimate * count
    if attempted + count > max_requests:
        raise ValueError(
            f"Image API request guard: {attempted + count} exceeds "
            f"IMAGE_JOB_MAX_REQUESTS={max_requests} for this job")
    if round(projected, 6) > limit + 1e-8:
        raise ValueError(
            f"Estimated image budget exceeded: ${projected:.2f} projected "
            f"for this job, limit ${limit:.2f}. Increase --image-budget-usd "
            f"only after reviewing API pricing and your actual provider billing.")
    return estimate


def preflight_image_budget(job_dir: Path, provider: str, calls: int,
                           limit_usd=None) -> None:
    limit = job_budget_limit(limit_usd)
    with _locked_usage(job_dir) as (_, usage):
        _check(usage, provider, calls, limit)


def reserve_image_request(job_dir: Path, provider: str, model: str,
                          limit_usd=None) -> None:
    """Record an attempted paid request *before* the network call.

    Attempts are intentionally not refunded on errors: providers may charge
    for unsuccessful responses. Atomic file replacement and a POSIX lock
    prevent parallel workers from bypassing the estimate guard.
    """
    limit = job_budget_limit(limit_usd)
    with _locked_usage(job_dir) as (path, usage):
        estimate = _check(usage, provider, 1, limit)
        usage["attempted_requests"] = usage.get("attempted_requests", 0) + 1
        usage["estimated_spend_usd"] = round(
            usage.get("estimated_spend_usd", 0.0) + estimate, 6)
        usage["last_budget_limit_usd"] = limit
        usage.setdefault("requests", []).append({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "provider": provider, "model": model, "estimated_usd": estimate,
            "status": "attempted",
        })
        temp = path.with_suffix(".tmp")
        try:
            temp.write_text(json.dumps(usage, indent=2), encoding="utf-8")
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
