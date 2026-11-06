"""Strict private specifications for the bounded Paper allocation workflow."""

from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re

from apps.execution_runner.config import RunnerSettings
from packages.execution_policies.paper_allocation import (
    AllocationError,
    AllocationPolicy,
    aware,
)
from packages.market_model import normalize_symbol


@dataclass(frozen=True)
class AllocationSpec:
    run_id: str
    account: str
    symbol: str
    con_id: int
    primary_exchange: str
    window_start: datetime
    window_end: datetime
    policy: AllocationPolicy
    allowed_positions: tuple[str, ...] = ()
    settings: RunnerSettings = RunnerSettings(dry_run=True)

    def validate(self, now, *, check_window=True):
        if not isinstance(self.run_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,24}", self.run_id
        ):
            raise AllocationError("invalid_run_id")
        if not isinstance(self.account, str) or not re.fullmatch(
            r"DU[0-9]+", self.account
        ):
            raise AllocationError("explicit_paper_account_required")
        if self.settings.environment != "paper" or self.settings.live_enabled:
            raise AllocationError("paper_only")
        if self.settings.gateway_port not in (4002, 7497):
            raise AllocationError("paper_endpoint_required")
        if type(self.con_id) is not int or self.con_id <= 0:
            raise AllocationError("qualified_contract_identity_required")
        if not isinstance(self.primary_exchange, str) or not re.fullmatch(
            r"[A-Z0-9]+", self.primary_exchange
        ):
            raise AllocationError("primary_exchange_required")
        if normalize_symbol(
            self.symbol
        ).market.value != "US" or not self.symbol.endswith(".US"):
            raise AllocationError("us_equity_required")
        for item in self.allowed_positions:
            normalize_symbol(item)
        start, end, current = (
            aware(self.window_start),
            aware(self.window_end),
            aware(now),
        )
        if not 0 < (end - start).total_seconds() <= 1800:
            raise AllocationError("window_must_be_bounded_to_30_minutes")
        if start.date() != end.date():
            raise AllocationError("single_session_window_required")
        if check_window and not start <= current <= end:
            raise AllocationError("outside_authorized_window")
        self.policy.validate(now)

    def to_dict(self):
        value = asdict(self)
        value["schema"] = "paper-allocation.v1"
        value["window_start"] = self.window_start.isoformat()
        value["window_end"] = self.window_end.isoformat()
        value["allowed_positions"] = list(self.allowed_positions)
        value["policy"] = {
            k: v.isoformat()
            if isinstance(v, date)
            else str(v)
            if isinstance(v, Decimal)
            else v
            for k, v in value["policy"].items()
        }
        return value

    @classmethod
    def from_dict(cls, value):
        try:
            required = {
                "schema",
                "run_id",
                "account",
                "symbol",
                "con_id",
                "primary_exchange",
                "window_start",
                "window_end",
                "policy",
                "allowed_positions",
                "settings",
            }
            if (
                not isinstance(value, dict)
                or set(value) != required
                or value["schema"] != "paper-allocation.v1"
            ):
                raise AllocationError("invalid_spec_fields")
            p = value["policy"]
            if not isinstance(p, dict) or set(p) != {
                f.name for f in fields(AllocationPolicy)
            }:
                raise AllocationError("invalid_policy_fields")
            parsed = {}
            for key, item in p.items():
                if key == "max_shares":
                    parsed[key] = item
                elif key == "reference_date":
                    parsed[key] = date.fromisoformat(item)
                else:
                    if not isinstance(item, str):
                        raise AllocationError("decimal_strings_required")
                    parsed[key] = Decimal(item)
            settings = value["settings"]
            if not isinstance(settings, dict) or set(settings) != {
                f.name for f in fields(RunnerSettings)
            }:
                raise AllocationError("invalid_settings_fields")
            if not isinstance(value["allowed_positions"], list) or not all(
                isinstance(x, str) for x in value["allowed_positions"]
            ):
                raise AllocationError("invalid_allowed_positions")
            return cls(
                **{
                    k: value[k]
                    for k in (
                        "run_id",
                        "account",
                        "symbol",
                        "con_id",
                        "primary_exchange",
                    )
                },
                window_start=datetime.fromisoformat(value["window_start"]),
                window_end=datetime.fromisoformat(value["window_end"]),
                policy=AllocationPolicy(**parsed),
                allowed_positions=tuple(value["allowed_positions"]),
                settings=RunnerSettings(**settings),
            )
        except (TypeError, ValueError, InvalidOperation, KeyError) as exc:
            raise AllocationError("invalid_allocation_spec") from exc
