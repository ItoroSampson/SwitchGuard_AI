from typing import Any, Dict, List


class SwitchGuardEngine:
    def __init__(
        self, failure_rate_threshold: float = 0.40, latency_threshold_ms: float = 8000.0
    ):
        """
        Optimized for both high-traffic urban centers and low-volume local kiosks.
        """
        self.failure_rate_threshold = failure_rate_threshold
        self.latency_threshold_ms = latency_threshold_ms

    def analyze_route_window(
        self, recent_transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        total_count = len(recent_transactions)

        if total_count == 0:
            return {
                "lockdown_recommended": False,
                "reason": "No recent transaction activity.",
                "metrics": {},
            }

        failed_count = 0
        total_latency = 0.0
        response_code_counts = {}

        systemic_errors = {"91", "68", "N5", "PY", "98"}

        consecutive_failures = 0
        max_consecutive_failures = 0

        for tx in recent_transactions:
            is_failed = (
                tx.get("off_status", "").strip().capitalize() == "Failed"
                or str(tx.get("response_code")).strip().upper() in systemic_errors
            )

            if is_failed:
                failed_count += 1
                consecutive_failures += 1
                if consecutive_failures > max_consecutive_failures:
                    max_consecutive_failures = consecutive_failures
            else:
                consecutive_failures = 0

            total_latency += float(tx.get("latency_ms", 0.0))
            code = str(tx.get("response_code", "UNKNOWN")).strip().upper()
            response_code_counts[code] = response_code_counts.get(code, 0) + 1

        rolling_failure_rate = failed_count / total_count
        average_latency = total_latency / total_count

        failure_rate_breached = rolling_failure_rate >= self.failure_rate_threshold
        latency_breached = average_latency >= self.latency_threshold_ms

        consecutive_strike = max_consecutive_failures >= 2

        lockdown_recommended = (
            failure_rate_breached or latency_breached or consecutive_strike
        )

        reason = "Route Healthy"
        if lockdown_recommended:
            reasons = []
            if consecutive_strike:
                reasons.append(
                    f"Instant Lock: {max_consecutive_failures} consecutive backend failures detected"
                )
            if failure_rate_breached:
                reasons.append(f"Rolling failure rate at {rolling_failure_rate:.1%}")
            if latency_breached:
                reasons.append(f"Average gateway latency at {average_latency:.0f}ms")
            reason = "CRITICAL LOCKDOWN: " + " | ".join(reasons)

        return {
            "lockdown_recommended": lockdown_recommended,
            "reason": reason,
            "metrics": {
                "rolling_failure_rate": rolling_failure_rate,
                "average_latency_ms": average_latency,
                "max_consecutive_failures": max_consecutive_failures,
                "response_code_distribution": response_code_counts,
                "total_transactions_evaluated": total_count,
            },
        }
