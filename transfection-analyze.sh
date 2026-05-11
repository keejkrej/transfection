#!/usr/bin/env bash
# Interactive pipeline for transfection analyze: timeseries, plots, AUC, fit.
# Dev: from repo root, run: bash transfection-analyze.sh
# Prod (transfection.zip): run from extracted bundle root after install.sh

set -euo pipefail

pause_to_exit() {
  if [[ -t 0 ]]; then
    read -r -p "Press Enter to exit..." _ || true
  fi
}
trap pause_to_exit EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$SCRIPT_DIR/../apps/transfection" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
  REPO_ROOT="$SCRIPT_DIR"
else
  echo "Run this script from the repo root (next to pyproject.toml) or from an extracted transfection bundle root." >&2
  exit 1
fi

if [[ -x "$REPO_ROOT/.uv/uv.exe" ]]; then
  UV_EXE="$REPO_ROOT/.uv/uv.exe"
elif [[ -x "$REPO_ROOT/.uv/uv" ]]; then
  UV_EXE="$REPO_ROOT/.uv/uv"
elif command -v uv >/dev/null 2>&1; then
  UV_EXE="uv"
else
  echo "Neither $REPO_ROOT/.uv/uv.exe, $REPO_ROOT/.uv/uv, nor uv on PATH was found. Run install.sh or install uv." >&2
  exit 1
fi

cpu_jobs() {
  if command -v nproc >/dev/null 2>&1; then nproc
  elif [[ "$(uname -s)" == Darwin ]] && command -v sysctl >/dev/null 2>&1; then sysctl -n hw.ncpu
  else echo 1
  fi
}

DEFAULT_FIT_JOBS="$(cpu_jobs)"
if [[ "${DEFAULT_FIT_JOBS:-1}" -lt 1 ]]; then DEFAULT_FIT_JOBS=1; fi
DEFAULT_MAX_ONSET=0.0

read_nonempty() {
  local prompt="$1" line
  while true; do
    read -r -p "$prompt " line || exit 1
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    if [[ -n "$line" ]]; then echo "$line"; return 0; fi
    echo "Value required." >&2
  done
}

read_positive_double() {
  local prompt="$1" line
  while true; do
    read -r -p "$prompt " line || exit 1
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    if [[ -z "$line" ]]; then echo "Value required." >&2; continue; fi
    if awk -v x="$line" 'BEGIN { exit !(x == x + 0 && x > 0) }' </dev/null; then echo "$line"; return 0; fi
    echo "Enter a number greater than 0 (use . for decimals)." >&2
  done
}

read_positive_int_with_default() {
  local prompt="$1" default="$2" line
  while true; do
    echo "$prompt [default: $default]" >&2
    read -r -p "Value (Enter for default): " line || exit 1
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    if [[ -z "$line" ]]; then echo "$default"; return 0; fi
    if [[ "$line" =~ ^[1-9][0-9]*$ ]]; then echo "$line"; return 0; fi
    echo "Enter an integer >= 1." >&2
  done
}

read_nonnegative_double_with_default() {
  local prompt="$1" default="$2" line d_str
  d_str="$default"
  while true; do
    echo "$prompt [default: $d_str; 0 = translation_onset fixed at 0]" >&2
    read -r -p "Value (Enter for default): " line || exit 1
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    if [[ -z "$line" ]]; then echo "$default"; return 0; fi
    if awk -v x="$line" 'BEGIN { exit !(x == x + 0 && x >= 0) }' </dev/null; then echo "$line"; return 0; fi
    echo "Enter a number >= 0 (use . for decimals)." >&2
  done
}

abs_dir() {
  (cd "$1" && pwd)
}

get_timeseries_metrics_count() {
  local ws="$1" d="$ws/timeseries" n=0
  [[ -d "$d" ]] || { echo 0; return 0; }
  local f b
  shopt -s nullglob
  for f in "$d"/*.csv; do
    b=$(basename "$f" .csv)
    if [[ "$b" =~ ^sc[0-9]+_ch[0-9]+$ ]]; then n=$((n + 1)); fi
  done
  shopt -u nullglob
  echo "$n"
}

find_results_auc_csv() {
  local ws="$1" r="$ws/results" f
  [[ -d "$r" ]] || { echo ""; return 0; }
  if [[ -f "$r/auc.csv" ]]; then echo "$(cd "$r" && pwd)/auc.csv"; return 0; fi
  f="$(find "$r" -maxdepth 1 -type f -name '*_auc.csv' -print | LC_ALL=C sort | head -1)"
  if [[ -n "$f" ]]; then echo "$(cd "$(dirname "$f")" && pwd)/$(basename "$f")"; else echo ""; fi
}

find_results_fit_csv() {
  local ws="$1" r="$ws/results" f
  [[ -d "$r" ]] || { echo ""; return 0; }
  if [[ -f "$r/fit.csv" ]]; then echo "$(cd "$r" && pwd)/fit.csv"; return 0; fi
  f="$(find "$r" -maxdepth 1 -type f -name '*_fit.csv' -print | LC_ALL=C sort | head -1)"
  if [[ -n "$f" ]]; then echo "$(cd "$(dirname "$f")" && pwd)/$(basename "$f")"; else echo ""; fi
}

invoke_transfection_analyze() {
  local -a args=("$@")
  echo "" >&2
  echo ">> $UV_EXE run transfection analyze ${args[*]}" >&2
  echo "" >&2
  (cd "$REPO_ROOT" && exec "$UV_EXE" run transfection analyze "${args[@]}")
}

exit_if_failed() {
  local code="$1" step="$2"
  if [[ "$code" -ne 0 ]]; then
    echo "" >&2
    echo "Stopped: $step failed (exit $code)." >&2
    exit "$code"
  fi
}

cat << 'EOF'

transfection analyze
--------------------
Runs in order: timeseries (optional) -> plot-timeseries -> auc -> plot-auc -> fit -> plot-fit
Analyze timeseries and fit share --jobs; plot-timeseries, auc, fit, and plot-fit share --interval (minutes per frame); fit also receives --max-onset-minutes (defaults from this script, Enter to accept).
Requires roi/Pos* and slide.json when generating timeseries.

EOF

workspace_raw="$(read_nonempty "Workspace directory (dataset root):")"
workspace="$(abs_dir "$workspace_raw")"

metric_count="$(get_timeseries_metrics_count "$workspace")"
run_timeseries=1
if [[ "$metric_count" -gt 0 ]]; then
  echo "timeseries/ already contains $metric_count workspace metrics CSV (sc*_ch*.csv)." >&2
  while true; do
    read -r -p "[D]elete timeseries/ and regenerate, or [S]kip timeseries (use existing): " c || exit 1
    k=$(printf '%s' "$c" | tr '[:lower:]' '[:upper:]')
    k="${k#"${k%%[![:space:]]*}"}"
    if [[ "$k" == "D" ]]; then
      rm -rf "${workspace%/}/timeseries"
      echo "Removed timeseries/." >&2
      run_timeseries=1
      break
    fi
    if [[ "$k" == "S" ]]; then run_timeseries=0; break; fi
    echo "Enter D or S." >&2
  done
fi

interval="$(read_positive_double "Frame interval in minutes (for plot-timeseries, auc, fit, plot-fit):")"

echo "" >&2
echo "Analyze timeseries & fit - set --jobs and (for fit) --max-onset-minutes (defaults from this script):" >&2
fit_jobs="$(read_positive_int_with_default "Worker processes for timeseries & fit (--jobs)" "$DEFAULT_FIT_JOBS")"
fit_max_onset="$(read_nonnegative_double_with_default "Max onset minutes (--max-onset-minutes)" "$DEFAULT_MAX_ONSET")"

correction_args=()
if [[ "$run_timeseries" -eq 1 ]]; then
  slide_default="${workspace}/slide.json"
  echo "Slide mapping JSON path [default: $slide_default]" >&2
  read -r -p "Path (Enter for default): " slide_in || exit 1
  slide_in="${slide_in#"${slide_in%%[![:space:]]*}"}"
  slide_in="${slide_in%"${slide_in##*[![:space:]]}"}"
  if [[ -z "$slide_in" ]]; then slide_path="$slide_default"; else slide_path="$slide_in"; fi
  if [[ ! -f "$slide_path" ]]; then echo "Slide file not found: $slide_path" >&2; exit 1; fi
  slide_path="$(cd "$(dirname "$slide_path")" && pwd)/$(basename "$slide_path")"

  echo "Correction quartile for timeseries [0.25]" >&2
  read -r -p "Value (Enter for default): " q_in || exit 1
  q_in="${q_in#"${q_in%%[![:space:]]*}"}"
  q_in="${q_in%"${q_in##*[![:space:]]}"}"
  if [[ -n "$q_in" ]]; then correction_args+=(--correction-quartile "$q_in"); fi

  set +e
  invoke_transfection_analyze \
    timeseries "$workspace" \
    --sample "$slide_path" \
    --jobs "$fit_jobs" \
    "${correction_args[@]}"
  code=$?
  set -e
  exit_if_failed "$code" "analyze timeseries"
fi

ts_dir="${workspace}/timeseries"
if [[ ! -d "$ts_dir" ]]; then
  echo "No timeseries/ directory - run timeseries first." >&2
  exit 1
fi
if [[ "$(get_timeseries_metrics_count "$workspace")" -lt 1 ]]; then
  echo "timeseries/ has no workspace metrics CSVs (sc*_ch*.csv)." >&2
  exit 1
fi

set +e
invoke_transfection_analyze plot-timeseries "$ts_dir" --interval "$interval"
code=$?
set -e
exit_if_failed "$code" "analyze plot-timeseries"

set +e
invoke_transfection_analyze auc "$workspace" --interval "$interval"
code=$?
set -e
exit_if_failed "$code" "analyze auc"

auc_csv="$(find_results_auc_csv "$workspace")"
if [[ -z "$auc_csv" ]]; then
  echo "Could not find auc.csv or *_auc.csv under results/." >&2
  exit 1
fi

set +e
invoke_transfection_analyze plot-auc "$auc_csv"
code=$?
set -e
exit_if_failed "$code" "analyze plot-auc"

set +e
invoke_transfection_analyze fit "$workspace" \
  --interval "$interval" \
  --jobs "$fit_jobs" \
  --max-onset-minutes "$fit_max_onset"
code=$?
set -e
exit_if_failed "$code" "analyze fit"

fit_csv="$(find_results_fit_csv "$workspace")"
if [[ -z "$fit_csv" ]]; then
  echo "Could not find fit.csv or *_fit.csv under results/." >&2
  exit 1
fi

set +e
invoke_transfection_analyze plot-fit "$fit_csv" --interval "$interval"
code=$?
set -e
exit_if_failed "$code" "analyze plot-fit"

echo "" >&2
echo "Pipeline finished." >&2
exit 0
