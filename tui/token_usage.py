"""Token usage records and derived coding statistics."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


UTC = timezone.utc


@dataclass(frozen=True)
class TokenUsageEntry:
    """The token usage attributed to one submitted task."""

    task_id: str
    timestamp: datetime
    provider: str
    tokens: int
    prompt: str = ""
    state: str = "completed"
    # One conversation is one task; each submitted user turn is a prompt and
    # each execution attempt is a run. Legacy records count as one of each.
    prompts: int = 1
    runs: int = 1

    def __post_init__(self) -> None:
        timestamp = self.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        else:
            timestamp = timestamp.astimezone(UTC)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "tokens", max(0, int(self.tokens)))
        object.__setattr__(self, "provider", self.provider or "unknown")
        object.__setattr__(self, "prompts", max(1, int(self.prompts)))
        object.__setattr__(self, "runs", max(1, int(self.runs)))


@dataclass(frozen=True)
class TokenUsageStats:
    """Aggregates used by the coding statistics screen."""

    entries: tuple[TokenUsageEntry, ...]
    cumulative_tokens: int
    daily_tokens: int
    cumulative_tasks: int
    daily_tasks: int
    average_tokens_per_prompt_by_provider: tuple[tuple[str, float], ...]
    average_tasks_per_prompt_by_provider: tuple[tuple[str, float], ...]
    last_hour_tokens: int
    last_hour_tasks: int
    seven_day_expected_tokens: int
    seven_day_expected_tasks: int
    thirty_day_expected_tokens: int
    thirty_day_expected_tasks: int
    provider_tokens: tuple[tuple[str, int], ...]
    provider_tasks: tuple[tuple[str, int], ...]
    cumulative_prompts: int = 0
    cumulative_runs: int = 0

    def provider_split(self, unit: str = "tokens") -> tuple[tuple[str, int], ...]:
        """Return provider and absolute usage pairs for the selected unit."""
        if unit not in {"tokens", "tasks"}:
            raise ValueError("unit must be 'tokens' or 'tasks'")
        return self.provider_tokens if unit == "tokens" else self.provider_tasks

    def average_per_prompt(self, unit: str = "tokens") -> tuple[tuple[str, float], ...]:
        """Return per-provider average usage per prompt for the selected unit."""
        if unit not in {"tokens", "tasks"}:
            raise ValueError("unit must be 'tokens' or 'tasks'")
        if unit == "tokens":
            return self.average_tokens_per_prompt_by_provider
        return self.average_tasks_per_prompt_by_provider


def calculate_token_usage(
    entries: Iterable[TokenUsageEntry],
    *,
    now: datetime | None = None,
    recent_window_hours: int = 1,
    forecast_days: int = 7,
    thirty_day_forecast_days: int = 30,
) -> TokenUsageStats:
    """Calculate token and task totals, windows, and per-provider usage.

    Daily usage uses the user's local calendar day. Weekly and monthly
    forecasts annualize usage from the current local calendar week or month
    to the target period length, so older history does not dilute the
    current-period projection. The monthly forecast uses the actual number
    of days in the current calendar month.
    Average tokens per prompt are computed separately for each provider so
    providers with different token scales are not merged into one figure.
    """
    if recent_window_hours < 1:
        raise ValueError("recent_window_hours must be positive")
    if forecast_days < 1:
        raise ValueError("forecast_days must be positive")
    if thirty_day_forecast_days < 1:
        raise ValueError("thirty_day_forecast_days must be positive")

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    normalized = tuple(
        sorted(
            (entry for entry in entries if entry.state == "completed"),
            key=lambda entry: entry.timestamp,
            reverse=True,
        )
    )
    current_local = current.astimezone()
    today = current_local.date()
    recent_start = current - timedelta(hours=recent_window_hours)
    cumulative = sum(entry.tokens for entry in normalized)
    cumulative_tasks = len(normalized)
    daily = sum(
        entry.tokens
        for entry in normalized
        if entry.timestamp.astimezone(current_local.tzinfo).date() == today
    )
    daily_tasks = sum(
        1
        for entry in normalized
        if entry.timestamp.astimezone(current_local.tzinfo).date() == today
    )
    recent = sum(entry.tokens for entry in normalized if recent_start <= entry.timestamp <= current)
    recent_tasks = sum(1 for entry in normalized if recent_start <= entry.timestamp <= current)

    week_start = today - timedelta(days=current_local.weekday())
    localized_entries = tuple(
        (entry, entry.timestamp.astimezone(current_local.tzinfo))
        for entry in normalized
        if entry.timestamp <= current
    )
    period_entries = tuple(
        entry
        for entry, local_timestamp in localized_entries
        if week_start <= local_timestamp.date() <= today
    )
    month_entries = tuple(
        entry
        for entry, local_timestamp in localized_entries
        if local_timestamp.year == current_local.year
        and local_timestamp.month == current_local.month
    )
    week_days_passed = current_local.weekday() + 1
    month_days = monthrange(current_local.year, current_local.month)[1]
    week_tokens = sum(entry.tokens for entry in period_entries)
    month_tokens = sum(entry.tokens for entry in month_entries)
    week_tasks = len(period_entries)
    month_tasks = len(month_entries)
    expected = round(week_tokens * forecast_days / week_days_passed)
    expected_thirty_day = round(month_tokens * month_days / current_local.day)

    provider_totals: dict[str, int] = {}
    provider_task_totals: dict[str, int] = {}
    provider_prompt_totals: dict[str, int] = {}
    for entry in normalized:
        provider_totals[entry.provider] = provider_totals.get(entry.provider, 0) + entry.tokens
        provider_task_totals[entry.provider] = provider_task_totals.get(entry.provider, 0) + 1
        provider_prompt_totals[entry.provider] = provider_prompt_totals.get(entry.provider, 0) + entry.prompts
    provider_items = tuple(sorted(provider_totals.items(), key=lambda item: (-item[1], item[0])))
    provider_task_items = tuple(
        sorted(provider_task_totals.items(), key=lambda item: (-item[1], item[0]))
    )
    # Averages are per submitted prompt (user turn), so a conversation with
    # three prompts does not look like one expensive prompt, and retries
    # (runs) never count as additional prompts.
    average_tokens_by_provider = tuple(
        (provider, provider_totals[provider] / provider_prompt_totals[provider])
        for provider, _ in provider_items
    )
    average_tasks_by_provider = tuple(
        (provider, provider_task_totals[provider] / provider_prompt_totals[provider])
        for provider, _ in provider_task_items
    )
    return TokenUsageStats(
        entries=normalized,
        cumulative_tokens=cumulative,
        daily_tokens=daily,
        cumulative_tasks=cumulative_tasks,
        daily_tasks=daily_tasks,
        average_tokens_per_prompt_by_provider=average_tokens_by_provider,
        average_tasks_per_prompt_by_provider=average_tasks_by_provider,
        last_hour_tokens=recent,
        last_hour_tasks=recent_tasks,
        seven_day_expected_tokens=expected,
        seven_day_expected_tasks=round(week_tasks * forecast_days / week_days_passed),
        thirty_day_expected_tokens=expected_thirty_day,
        thirty_day_expected_tasks=round(month_tasks * month_days / current_local.day),
        provider_tokens=provider_items,
        provider_tasks=provider_task_items,
        cumulative_prompts=sum(entry.prompts for entry in normalized),
        cumulative_runs=sum(entry.runs for entry in normalized),
    )


def usage_entries_from_memory(store) -> tuple[TokenUsageEntry, ...]:
    """Convert persisted task snapshots into usage records."""
    entries: list[TokenUsageEntry] = []
    for task_id, task in store.get_tasks().items():
        if task.get("state") != "completed":
            continue
        timestamp = _parse_timestamp(task.get("timestamp"))
        if timestamp is None:
            continue
        provider = task.get("provider")
        tokens = task.get("tokens", 0)
        if not isinstance(provider, str):
            provider = "unknown"
        if not isinstance(tokens, int) or isinstance(tokens, bool):
            tokens = 0
        entries.append(
            TokenUsageEntry(
                task_id,
                timestamp,
                provider,
                tokens,
                str(task.get("prompt", "")),
                str(task.get("state", "")),
                prompts=_prompt_count(task),
                runs=_run_count(task),
            )
        )
    return tuple(entries)


def _prompt_count(task: dict[str, object]) -> int:
    """Count submitted user prompts, treating legacy snapshots as one prompt."""
    value = task.get("prompt_count")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    turns = task.get("turns")
    if isinstance(turns, list):
        user_turns = sum(
            1 for turn in turns if isinstance(turn, dict) and turn.get("kind", "user") == "user"
        )
        if user_turns:
            return user_turns
    return 1


def _run_count(task: dict[str, object]) -> int:
    runs = task.get("runs")
    if isinstance(runs, list) and runs:
        return len(runs)
    return 1


def merge_usage_entries(*entry_groups: Iterable[TokenUsageEntry]) -> tuple[TokenUsageEntry, ...]:
    """Merge snapshots by task ID, allowing live records to replace history."""
    merged: dict[str, TokenUsageEntry] = {}
    for group in entry_groups:
        for entry in group:
            merged[entry.task_id] = entry
    return tuple(sorted(merged.values(), key=lambda entry: entry.timestamp, reverse=True))


def _parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, UTC)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def task_usage_entry(record) -> TokenUsageEntry | None:
    """Convert a live task record without coupling this module to its class."""
    if record.status != "completed":
        return None
    turns = getattr(record, "turns", None) or ()
    prompts = sum(1 for turn in turns if getattr(turn, "kind", "user") == "user") or 1
    runs = len(getattr(record, "runs", None) or ()) or 1
    return TokenUsageEntry(
        record.memory_task_id or f"task-{record.task_id}",
        datetime.fromtimestamp(record.submitted_at, UTC),
        record.provider,
        record.tokens_consumed,
        record.prompt,
        record.status,
        prompts=prompts,
        runs=runs,
    )
