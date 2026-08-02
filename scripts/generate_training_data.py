import numpy as np
import pandas as pd


def generate_telemetry_dataset(num_samples=10000, random_state=42):
    np.random.seed(random_state)

    volumes = np.random.randint(1, 150, size=num_samples)
    fail_rates = np.random.beta(a=0.5, b=5, size=num_samples)
    latencies = np.random.exponential(scale=1200, size=num_samples) + 150

    hard_errors = np.round(volumes * fail_rates).astype(int)

    consecutive_strikes = np.random.poisson(lam=fail_rates * 4, size=num_samples)

    ghost_prob = fail_rates * 0.4 + (latencies / 15000) * 0.3
    ghost_counts = np.random.poisson(lam=ghost_prob * 5, size=num_samples)

    labels = []
    for i in range(num_samples):
        vol = volumes[i]
        fr = fail_rates[i]
        gc = ghost_counts[i]
        strikes = consecutive_strikes[i]

        if vol < 3:
            labels.append(0)  # HEALTHY (prevent false positives on low volume)
        elif gc >= 3 or fr >= 0.50 or strikes >= 5:
            labels.append(2)  # CRITICAL
        elif gc >= 1 or fr >= 0.20 or strikes >= 3:
            labels.append(1)  # DEGRADED
        else:
            labels.append(0)  # HEALTHY

    df = pd.DataFrame(
        {
            "volume_5m": volumes,
            "time_decayed_fail_rate": np.round(fail_rates, 4),
            "avg_latency_ms": np.round(latencies, 2),
            "hard_technical_errors": hard_errors,
            "max_consecutive_strikes": consecutive_strikes,
            "ghost_debit_count": ghost_counts,
            "target": labels,
        }
    )

    df.to_csv("data/route_telemetry_training.csv", index=False)
    print(
        f" Generated {num_samples} samples with exact metric suite -> data/route_telemetry_training.csv"
    )


if __name__ == "__main__":
    generate_telemetry_dataset()
