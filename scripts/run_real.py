"""Run the corrected study and measure its processing time and peak process memory."""
import json
from pathlib import Path
import threading
import time
import psutil
from guardrails.analysis import Settings, run

ROOT=Path(__file__).resolve().parents[1]


def main():
    proc=psutil.Process()
    peak=[proc.memory_info().rss]
    stop=threading.Event()
    def monitor():
        while not stop.wait(.05):
            peak[0]=max(peak[0],proc.memory_info().rss)
    thread=threading.Thread(target=monitor,daemon=True)
    thread.start()
    started=time.perf_counter()
    try:
        summary=run(ROOT/"data/trondheim_2022/guardrails.gpkg",ROOT/"data/trondheim_2022/tile.laz",
                    ROOT/"outputs/real",Settings(),
                    reference_lines_path=ROOT/"data/trondheim_2022/reference_nvdb/guardrails.gpkg")
    finally:
        stop.set()
        thread.join()
    metrics=dict(wall_seconds=time.perf_counter()-started,peak_process_rss_mb=peak[0]/1024**2,
                 scope="Full local pipeline: LAZ crop, ground, support, DBSCAN, exports, figure. Excludes imports and network download.",
                 measurement="Process RSS sampled every 50 ms, not a hard upper bound")
    (ROOT/"outputs/real/performance.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
    print(json.dumps(metrics,indent=2))


if __name__=="__main__":
    main()
