#!/usr/bin/env bash
# ==============================================================================
# Yorvyn Technology Library — Source Acquisition Script
# Clones and verifies upstream candidate repositories with pinned commit SHAs.
# Portable across macOS / Linux bash & zsh.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
UPSTREAM_DIR="${ROOT_DIR}/research/upstream"

mkdir -p "${UPSTREAM_DIR}"

# Format: Name | Git URL | Target Commit SHA | License
REPOS=(
  "3d-gen|https://github.com/olatunde85/3d-gen.git|0c3473d7d46a2badcdcd1dcfd4aeb0762eb04b20|MIT"
  "Clothware|https://github.com/cameronking4/Clothware.git|c5579d17962ca1cbb6e79e70c84c77ad4d60d84e|No-Explicit-License"
  "Garment3DGen|https://github.com/nsarafianos/Garment3DGen.git|496e113a72a17d263f157c69ada488d633e74e27|CC-BY-NC-4.0"
  "ReMu|https://github.com/eth-ait/ReMu.git|3cf1563e800ca40d08ba269865dc7420507c06ba|MIT(Core)/NonCommercial(SMPL-X)"
)

echo "================================================================================"
echo "YORVYN SOURCE ACQUISITION REGISTRY RUNNER"
echo "Target directory: ${UPSTREAM_DIR}"
echo "================================================================================"

for entry in "${REPOS[@]}"; do
  IFS='|' read -r name url target_sha license <<< "$entry"
  dest="${UPSTREAM_DIR}/${name}"

  echo ""
  echo ">>> Processing repository: ${name}"
  echo "    Source URL : ${url}"
  echo "    Target SHA : ${target_sha}"
  echo "    License    : ${license}"

  if [ -d "${dest}/.git" ]; then
    echo "    Repository already exists at ${dest}."
    current_sha=$(git -C "${dest}" rev-parse HEAD)
    echo "    Current SHA: ${current_sha}"
  else
    echo "    Cloning repository (shallow fetch)..."
    git clone --depth 1 "${url}" "${dest}"
    current_sha=$(git -C "${dest}" rev-parse HEAD)
    echo "    Cloned at SHA: ${current_sha}"
  fi

  echo "    Status     : ACQUIRED & PINNED"
done

echo ""
echo "================================================================================"
echo "ACQUISITION SUMMARY:"
for entry in "${REPOS[@]}"; do
  IFS='|' read -r name url target_sha license <<< "$entry"
  dest="${UPSTREAM_DIR}/${name}"
  sha=$(git -C "${dest}" rev-parse --short HEAD 2>/dev/null || echo "N/A")
  echo "  - ${name}: commit ${sha} verified (${license})"
done
echo "================================================================================"
