import math
from datetime import datetime, timezone
from typing import Any, Dict, List


class SwitchGuardEngine:
    def __init__(
        self,
        failure_rate_threshold: float = 0.35,
        latency_threshold_ms: float = 4000.0,
        half_life_seconds: float = 120.0,
    ):
        self.failure_rate_threshold = failure_rate_threshold
        self.latency_threshold_ms = latency_threshold_ms
        self.half_life_seconds = half_life_seconds

        self.HARD_ERROR_CODES = {"91", "96", "TO", "98", "PY", "06", "A3", "N5"}
        self.SOFT_ERROR_CODES = {"51", "55", "61", "75", "14", "01", "6841"}

    def _classify_error(self, code: str) -> str:
        code_str = str(code).strip().upper()
        if code_str in ("00", "0"):
            return "SUCCESS"
        elif code_str in self.HARD_ERROR_CODES:
            return "HARD_TECHNICAL"
        elif code_str in self.SOFT_ERROR_CODES:
            return "SOFT_USER"
        return "UNKNOWN_FAILURE"

    def _parse_datetime(self, ts_val: Any) -> datetime:
        """Parses various timestamp formats into a unified UTC datetime."""
        if isinstance(ts_val, datetime):
            return (
                ts_val.replace(tzinfo=timezone.utc) if ts_val.tzinfo is None else ts_val
            )
        try:
            clean_ts = str(ts_val).replace("T", " ")[:19]
            return datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except Exception:
            return datetime.now(timezone.utc)

    def _calculate_time_weight(
        self, tx_dt: datetime, reference_time: datetime
    ) -> float:
        """Calculates exponential decay weight based on transaction age relative to batch T_0."""
        try:
            age_seconds = max(0.0, (reference_time - tx_dt).total_seconds())
            decay_lambda = math.log(2) / self.half_life_seconds
            return math.exp(-decay_lambda * age_seconds)
        except Exception:
            return 1.0

    def analyze_route_window(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not records:
            return {
                "alert_recommended": False,
                "reason": "No transaction data available for evaluation.",
                "metrics": {},
            }

        parsed_dates = [self._parse_datetime(tx.get("timestamp")) for tx in records]
        ref_time = max(parsed_dates) if parsed_dates else datetime.now(timezone.utc)

        weighted_hard_failures = 0.0
        weighted_total_eligible = 0.0

        soft_error_count = 0
        hard_error_count = 0
        total_latency_ms = 0.0
        valid_latency_count = 0

        consecutive_hard_failures = 0
        max_consecutive_hard_failures = 0

        terminal_failures: Dict[str, int] = {}
        issuer_failures: Dict[str, int] = {}
        ghost_debit_risk_count = 0

        for tx, tx_dt in zip(records, parsed_dates):
            latency = float(tx.get("latency_ms", 250.0))
            total_latency_ms += latency
            valid_latency_count += 1

            code = str(tx.get("response_code", "00"))
            error_type = self._classify_error(code)
            weight = self._calculate_time_weight(tx_dt, ref_time)

            term_id = str(tx.get("terminal_id", "UNKNOWN"))
            issuing_bank = str(tx.get("issuing_bank", "UNKNOWN"))
            is_ghost = tx.get("ghost_debit", False)

            if error_type == "HARD_TECHNICAL":
                hard_error_count += 1
                consecutive_hard_failures += 1
                max_consecutive_hard_failures = max(
                    max_consecutive_hard_failures, consecutive_hard_failures
                )

                weighted_hard_failures += weight
                weighted_total_eligible += weight

                terminal_failures[term_id] = terminal_failures.get(term_id, 0) + 1
                issuer_failures[issuing_bank] = issuer_failures.get(issuing_bank, 0) + 1

                if is_ghost or latency >= 5000.0:
                    ghost_debit_risk_count += 1

            elif error_type == "SUCCESS":
                consecutive_hard_failures = 0
                weighted_total_eligible += weight

            elif error_type == "SOFT_USER":
                soft_error_count += 1

        avg_latency = (
            total_latency_ms / valid_latency_count if valid_latency_count > 0 else 0.0
        )
        weighted_failure_rate = (
            weighted_hard_failures / weighted_total_eligible
            if weighted_total_eligible > 0
            else 0.0
        )

        is_isolated_terminal_issue = False
        if hard_error_count >= 3 and terminal_failures:
            max_term_fails = max(terminal_failures.values())
            if (max_term_fails / hard_error_count) >= 0.8 and len(records) > 5:
                is_isolated_terminal_issue = True

        is_isolated_issuer_issue = False
        faulty_bank_name = ""
        if hard_error_count >= 3 and issuer_failures:
            faulty_bank_name, max_issuer_fails = max(
                issuer_failures.items(), key=lambda item: item[1]
            )
            if (max_issuer_fails / hard_error_count) >= 0.8:
                is_isolated_issuer_issue = True

        alert = False
        reasons = []

        if is_isolated_terminal_issue:
            reasons.append(
                "LOCAL HARDWARE/SIM ISSUE: Failures isolated to a single terminal. Check WiFi or SIM card."
            )
        elif is_isolated_issuer_issue:
            reasons.append(
                f"ISSUER BANK DOWN: Failures concentrated on {faulty_bank_name}. Switch is healthy, but {faulty_bank_name} cards will fail."
            )
        else:
            if weighted_failure_rate >= self.failure_rate_threshold:
                alert = True
                reasons.append(
                    f"HIGH NETWORK FAILURE RATE ({weighted_failure_rate:.1%}): Exceeded safe operating threshold ({self.failure_rate_threshold:.1%})."
                )

            if max_consecutive_hard_failures >= 3:
                alert = True
                reasons.append(
                    f"ROUTE DOWN: {max_consecutive_hard_failures} consecutive network timeouts detected."
                )

            if avg_latency >= self.latency_threshold_ms:
                alert = True
                reasons.append(
                    f"SEVERE LATENCY SPIKE: Average response time ({avg_latency:.0f}ms) degraded past threshold ({self.latency_threshold_ms:.0f}ms)."
                )

            if ghost_debit_risk_count >= 2:
                alert = True
                reasons.append(
                    f"GHOST DEBIT RISK: {ghost_debit_risk_count} delayed transactions flagged for potential unconfirmed debits."
                )

        is_route_recovered = False
        if (
            not alert
            and weighted_failure_rate < 0.10
            and max_consecutive_hard_failures == 0
        ):
            is_route_recovered = True

        primary_reason = (
            " | ".join(reasons)
            if reasons
            else "Route Healthy: Technical network signals are nominal."
        )

        return {
            "alert_recommended": alert,
            "merchant_action_recommended": "SWITCH_PROVIDER"
            if alert
            else "STAY_ON_ROUTE",
            "reason": primary_reason,
            "metrics": {
                "weighted_failure_rate": weighted_failure_rate,
                "avg_latency_ms": avg_latency,
                "hard_technical_errors": hard_error_count,
                "soft_user_errors_ignored": soft_error_count,
                "max_consecutive_hard_strikes": max_consecutive_hard_failures,
                "isolated_terminal_issue": is_isolated_terminal_issue,
                "isolated_issuer_issue": is_isolated_issuer_issue,
                "faulty_issuer": faulty_bank_name if is_isolated_issuer_issue else None,
                "ghost_debit_risk_count": ghost_debit_risk_count,
                "route_recovered": is_route_recovered,
                "total_transactions_evaluated": len(records),
            },
        }
