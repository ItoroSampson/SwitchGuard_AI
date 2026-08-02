import os

import joblib
import numpy as np


class AnomalyEvaluator:
    def __init__(self, model_path: str = "models/xgb_route_evaluator.joblib"):
        self.status_map = {0: "HEALTHY", 1: "DEGRADED", 2: "CRITICAL"}
        self.model = None

        if os.path.exists(model_path):
            try:
                self.model = joblib.load(model_path)
                print(f" Loaded XGBoost model from {model_path}")
            except Exception as e:
                print(
                    f" Failed to load XGBoost model: {e}. Falling back to heuristic rule engine."
                )
        else:
            print("ℹModel artifact not found. Operating in heuristic mode.")

    def evaluate_route_health(self, features: dict) -> tuple[str, float, str]:
        """
        Evaluates route health using the XGBoost model if available,
        otherwise falls back to rule engine logic.

        Expects features dict:
        - volume_5m
        - time_decayed_fail_rate (or fail_rate)
        - avg_latency_ms
        - hard_technical_errors
        - max_consecutive_strikes
        - ghost_debit_count

        Returns: (status_str, anomaly_score, reason_str)
        """
        vol = features.get("volume_5m", 0)
        td_fail_rate = features.get(
            "time_decayed_fail_rate", features.get("fail_rate", 0.0)
        )
        avg_latency = features.get("avg_latency_ms", 0.0)
        hard_errors = features.get("hard_technical_errors", 0)
        consecutive_strikes = features.get("max_consecutive_strikes", 0)
        ghost_count = features.get("ghost_debit_count", features.get("ghost_count", 0))

        if vol < 3:
            return "HEALTHY", 0.0, "Insufficient sample volume (vol < 3)"

        if self.model:
            input_data = np.array(
                [
                    [
                        vol,
                        td_fail_rate,
                        avg_latency,
                        hard_errors,
                        consecutive_strikes,
                        ghost_count,
                    ]
                ]
            )

            probs = self.model.predict_proba(input_data)[0]
            predicted_class = int(np.argmax(probs))
            status = self.status_map[predicted_class]

            anomaly_score = round(float(1.0 - probs[0]), 4)
            reason = f"XGBoost inferenced {status} (Anomaly Confidence: {round(anomaly_score * 100, 1)}%)"

            return status, anomaly_score, reason

        if ghost_count >= 3 or td_fail_rate >= 0.50 or consecutive_strikes >= 5:
            return (
                "CRITICAL",
                0.95,
                "High failure rate, burst strikes, or severe ghost debit cluster",
            )
        elif ghost_count >= 1 or td_fail_rate >= 0.20 or consecutive_strikes >= 3:
            return (
                "DEGRADED",
                0.65,
                "Elevated route failure rate, consecutive strikes, or ghost debit detected",
            )

        return "HEALTHY", 0.05, "Route operating normally"
