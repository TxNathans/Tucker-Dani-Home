"""Turn an Apple Health export (export.zip or export.xml) into small CSVs in notes/personal/health/apple/.

Get the export on iPhone: Health app > profile picture > Export All Health Data, then save the zip
to Google Drive (or anywhere Claude can reach). Then:

  python tools/apple_health/parse_export.py path/to/export.zip

Writes:
  sleep.csv     one row per night per source (Apple Watch, WHOOP, iPhone...), stage totals in hours
  daily.csv     one row per day: steps, energy, exercise, heart rate, HRV, SpO2, weight...
  workouts.csv  one row per workout
The raw export is not kept in git (it can be hundreds of MB).
"""

import csv
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree.ElementTree import iterparse

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "notes" / "personal" / "health" / "apple"

SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
SLEEP_STAGES = {
    "HKCategoryValueSleepAnalysisInBed": "in_bed",
    "HKCategoryValueSleepAnalysisAsleepUnspecified": "asleep_unspecified",
    "HKCategoryValueSleepAnalysisAsleep": "asleep_unspecified",
    "HKCategoryValueSleepAnalysisAsleepCore": "core",
    "HKCategoryValueSleepAnalysisAsleepDeep": "deep",
    "HKCategoryValueSleepAnalysisAsleepREM": "rem",
    "HKCategoryValueSleepAnalysisAwake": "awake",
}
STAGE_COLUMNS = ["in_bed", "asleep", "core", "deep", "rem", "asleep_unspecified", "awake"]

# Daily metrics. "sum" totals are taken per source and the largest source wins, because iPhone and
# Watch both log steps and adding them would double count. "mean"/"min"/"max" pool all sources.
DAILY = {
    "HKQuantityTypeIdentifierStepCount": ("steps", "sum"),
    "HKQuantityTypeIdentifierDistanceWalkingRunning": ("walk_run_distance", "sum"),
    "HKQuantityTypeIdentifierActiveEnergyBurned": ("active_energy", "sum"),
    "HKQuantityTypeIdentifierBasalEnergyBurned": ("resting_energy", "sum"),
    "HKQuantityTypeIdentifierAppleExerciseTime": ("exercise_min", "sum"),
    "HKQuantityTypeIdentifierAppleStandTime": ("stand_min", "sum"),
    "HKQuantityTypeIdentifierFlightsClimbed": ("flights", "sum"),
    "HKQuantityTypeIdentifierRestingHeartRate": ("resting_hr", "mean"),
    "HKQuantityTypeIdentifierHeartRate": ("hr_avg", "mean"),
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": ("walking_hr", "mean"),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv_sdnn_ms", "mean"),
    "HKQuantityTypeIdentifierRespiratoryRate": ("resp_rate", "mean"),
    "HKQuantityTypeIdentifierOxygenSaturation": ("spo2", "mean"),
    "HKQuantityTypeIdentifierAppleSleepingWristTemperature": ("wrist_temp_c", "mean"),
    "HKQuantityTypeIdentifierVO2Max": ("vo2max", "mean"),
    "HKQuantityTypeIdentifierBodyMass": ("weight", "mean"),
    "HKQuantityTypeIdentifierBodyFatPercentage": ("body_fat", "mean"),
}
DAILY_COLUMNS = [col for col, _ in DAILY.values()]


def parse_time(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")


def night_of(start):
    # Sleep that starts between noon yesterday and noon today counts as last night.
    return (start + timedelta(hours=12)).date().isoformat()


def open_xml(path):
    path = Path(path)
    if path.suffix == ".zip":
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist() if n.endswith("export.xml") and "cda" not in n)
        return z.open(name)
    return open(path, "rb")


def parse(path):
    sleep = defaultdict(lambda: defaultdict(float))  # (night, source) -> stage -> hours
    sums = defaultdict(float)  # (day, column, source) -> total
    pooled = defaultdict(list)  # (day, column) -> values
    workouts = []

    for _, el in iterparse(open_xml(path), events=("end",)):
        tag = el.tag
        if tag == "Record":
            kind = el.get("type")
            if kind == SLEEP_TYPE:
                stage = SLEEP_STAGES.get(el.get("value"))
                if stage:
                    start, end = parse_time(el.get("startDate")), parse_time(el.get("endDate"))
                    key = (night_of(start), el.get("sourceName", ""))
                    sleep[key][stage] += (end - start).total_seconds() / 3600
            elif kind in DAILY:
                col, how = DAILY[kind]
                try:
                    value = float(el.get("value"))
                except (TypeError, ValueError):
                    pass
                else:
                    if el.get("unit") == "%" and value <= 1:
                        value *= 100
                    day = el.get("startDate")[:10]
                    if how == "sum":
                        sums[(day, col, el.get("sourceName", ""))] += value
                    else:
                        pooled[(day, col)].append(value)
            el.clear()
        elif tag == "Workout":
            stats = {s.get("type"): s for s in el.iter("WorkoutStatistics")}
            energy = stats.get("HKQuantityTypeIdentifierActiveEnergyBurned")
            workouts.append({
                "start": el.get("startDate"),
                "end": el.get("endDate"),
                "type": el.get("workoutActivityType", "").replace("HKWorkoutActivityType", ""),
                "duration_min": round(float(el.get("duration") or 0), 1)
                if el.get("durationUnit", "min") == "min" else el.get("duration"),
                "active_energy": round(float(energy.get("sum")), 1) if energy is not None and energy.get("sum") else
                el.get("totalEnergyBurned", ""),
                "distance": el.get("totalDistance", ""),
                "distance_unit": el.get("totalDistanceUnit", ""),
                "source": el.get("sourceName", ""),
            })
            el.clear()
        elif tag in ("ActivitySummary", "Correlation", "ClinicalRecord"):
            el.clear()

    return sleep, sums, pooled, workouts


def write(sleep, sums, pooled, workouts):
    OUT.mkdir(parents=True, exist_ok=True)

    with open(OUT / "sleep.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["night_of", "source"] + [f"{c}_h" for c in STAGE_COLUMNS])
        for (night, source), stages in sorted(sleep.items(), reverse=True):
            stages["asleep"] = stages["core"] + stages["deep"] + stages["rem"] + stages["asleep_unspecified"]
            w.writerow([night, source] + [round(stages[c], 2) for c in STAGE_COLUMNS])

    daily = defaultdict(dict)
    best = {}
    for (day, col, _source), total in sums.items():
        best[(day, col)] = max(best.get((day, col), 0), total)
    for (day, col), total in best.items():
        daily[day][col] = round(total, 1)
    for (day, col), values in pooled.items():
        daily[day][col] = round(sum(values) / len(values), 1)
    with open(OUT / "daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date"] + DAILY_COLUMNS)
        for day in sorted(daily, reverse=True):
            w.writerow([day] + [daily[day].get(c, "") for c in DAILY_COLUMNS])

    with open(OUT / "workouts.csv", "w", newline="") as f:
        cols = ["start", "end", "type", "duration_min", "active_energy", "distance", "distance_unit", "source"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(sorted(workouts, key=lambda r: r["start"], reverse=True))

    print(f"sleep: {len(sleep)} night/source rows, daily: {len(daily)} days, workouts: {len(workouts)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    write(*parse(sys.argv[1]))
