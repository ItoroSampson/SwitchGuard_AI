import os

import joblib
import pandas as pd
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

FEATURE_COLS = [
    "volume_5m",
    "time_decayed_fail_rate",
    "avg_latency_ms",
    "hard_technical_errors",
    "max_consecutive_strikes",
    "ghost_debit_count",
]


def train_anomaly_model():
    data_path = "data/route_telemetry_training.csv"
    if not os.path.exists(data_path):
        raise FileNotFoundError("Run scripts/generate_training_data.py first!")

    df = pd.read_csv(data_path)
    X = df[FEATURE_COLS]
    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        eval_metric="mlogloss",
        random_state=42,
    )

    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print(" Model Evaluation Report:\n")
    print(
        classification_report(
            y_test, preds, target_names=["HEALTHY", "DEGRADED", "CRITICAL"]
        )
    )

    os.makedirs("models", exist_ok=True)
    joblib.dump(model, "models/xgb_route_evaluator.joblib")
    print(" Saved model artifact to models/xgb_route_evaluator.joblib")


if __name__ == "__main__":
    train_anomaly_model()
