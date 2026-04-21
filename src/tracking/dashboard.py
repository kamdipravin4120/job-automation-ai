from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from src.utils.config import load_config
from src.utils.logging import configure_logging
from src.tracking.service import TrackingService


def launch_dashboard(config_path: Path) -> None:
    dashboard_path = Path(__file__).resolve()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(dashboard_path),
            "--",
            "--config",
            str(config_path),
        ],
        check=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Job application tracking dashboard")
    parser.add_argument("--config", default="config.yaml")
    return parser


def main() -> None:
    import pandas as pd
    import streamlit as st

    args = build_parser().parse_args()
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    logger = configure_logging(config.logging, config_path.parent)
    tracking_service = TrackingService(config.tracking, config_path.parent, logger)

    records = tracking_service.list_records()
    frame = pd.DataFrame([record.model_dump(mode="json") for record in records])

    st.set_page_config(page_title="Job Automation Dashboard", layout="wide")
    st.title("Job Automation Dashboard")

    if frame.empty:
        st.info("No job records yet. Run the pipeline first.")
        return

    st.metric("Tracked Jobs", len(frame))
    st.metric("Applied", int((frame["status"] == "applied").sum()))
    st.metric("Ready For Review", int((frame["status"] == "manual_review_required").sum()))

    statuses = sorted(frame["status"].dropna().unique().tolist())
    selected_statuses = st.multiselect("Filter by status", options=statuses, default=statuses)
    filtered_frame = frame[frame["status"].isin(selected_statuses)]

    st.subheader("Applications")
    st.dataframe(filtered_frame, use_container_width=True)

    st.subheader("Status Breakdown")
    st.bar_chart(filtered_frame["status"].value_counts())


if __name__ == "__main__":
    main()

