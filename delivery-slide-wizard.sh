#!/usr/bin/env bash
# Interactive helper to build --sample and run delivery slide config.
# Dev: from repo root: bash scripts/delivery-slide-wizard.sh
# Prod (delivery.zip): from extracted bundle root

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$SCRIPT_DIR/../apps/delivery" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
  REPO_ROOT="$SCRIPT_DIR"
else
  echo "Run from repo (scripts/delivery-slide-wizard.sh) or extracted delivery bundle root." >&2
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

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

read_nonempty() {
  local prompt="$1" line
  while true; do
    read -r -p "$prompt " line || exit 1
    line="$(trim "$line")"
    if [[ -n "$line" ]]; then echo "$line"; return 0; fi
    echo "Value required." >&2
  done
}

read_nonnegative_int() {
  local prompt="$1" line
  while true; do
    read -r -p "$prompt " line || exit 1
    line="$(trim "$line")"
    if [[ -z "$line" ]]; then echo "Value required." >&2; continue; fi
    if [[ "$line" =~ ^[0-9]+$ ]]; then echo "$line"; return 0; fi
    echo "Enter a non-negative integer." >&2
  done
}

cat << 'EOF'

delivery slide wizard
---------------------
Slide channel ids are assigned automatically (0, 1, 2, … in entry order; not part of --sample text).
Each mapping: sample_name, then image channel, then positions (e.g. 10,11 or 0:12 for a range).
Compact fragments look like positions@image_channel#sample_name and are joined with | for --sample.
Do not use | # @ in the sample_name (they are syntax characters).

EOF

segments=()
next_slide_ch=0

echo "Add one or more slide channel mappings. Blank sample_name when done." >&2
echo "" >&2

while true; do
  read -r -p "Sample name (blank when done): " name_line || exit 1
  name="$(trim "$name_line")"
  if [[ -z "$name" ]]; then
    if [[ "${#segments[@]}" -eq 0 ]]; then
      echo "Add at least one mapping before finishing." >&2
      continue
    fi
    break
  fi
  if [[ "$name" =~ [\|\#@] ]]; then
    echo "sample_name must not contain | # or @" >&2
    continue
  fi

  image_ch="$(read_nonnegative_int "Image channel")"
  positions="$(read_nonempty "Positions (e.g. 10,11 or 0:12 for a range)")"

  slide_ch=$next_slide_ch
  next_slide_ch=$((next_slide_ch + 1))
  compact="${positions}@${image_ch}#${name}"
  segments+=("$compact")
  echo "Added slide_channel=$slide_ch | positions=$positions | image_channel=$image_ch | sample_name=$name" >&2
  echo "  (compact --sample fragment: $compact)" >&2
  echo "" >&2
done

sample_arg="${segments[0]:-}"
for ((i = 1; i < ${#segments[@]}; i++)); do
  sample_arg+="|${segments[i]}"
done

output_raw="$(read_nonempty "Output path for slide.json:")"
if [[ "$output_raw" != /* ]]; then
  output_path="$(pwd)/$output_raw"
else
  output_path="$output_raw"
fi

force_args=()
if [[ -e "$output_path" ]]; then
  read -r -p "Output exists. Overwrite? [y/N]: " ow || exit 1
  ow="$(trim "$ow")"
  if [[ "$ow" == "y" || "$ow" == "Y" ]]; then force_args+=(--force); fi
fi

echo "" >&2
echo "Running: $UV_EXE run delivery slide config ..." >&2
echo "" >&2

cd "$REPO_ROOT"
exec "$UV_EXE" run delivery slide config \
  --sample "$sample_arg" \
  --output "$output_path" \
  "${force_args[@]}"
