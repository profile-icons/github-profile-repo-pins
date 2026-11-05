#!/usr/bin/env bash
set -euo pipefail

case "$(uname -s)/$(uname -m)" in
  Linux/x86_64) platform=linux-x64 ;;
  Linux/aarch64) platform=linux-aarch64 ;;
  *) echo "Install ONNX Runtime and set ORT_DYLIB_PATH on this platform; see README." >&2; exit 1 ;;
esac
runtime_parent="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/repo-pins-onnx"
runtime_dir="$runtime_parent/onnxruntime-$platform-1.22.0"
mkdir -p "$runtime_parent"
if [[ ! -f "$runtime_dir/lib/libonnxruntime.so.1.22.0" ]]; then
  archive="$(mktemp "$runtime_parent/runtime.XXXXXX.tgz")"
  trap '[[ -z "${archive:-}" ]] || unlink "$archive"' EXIT
  curl --fail --location --retry 3 --proto '=https' --tlsv1.2 \
    "https://github.com/microsoft/onnxruntime/releases/download/v1.22.0/onnxruntime-$platform-1.22.0.tgz" \
    --output "$archive"
  tar --no-same-owner -xzf "$archive" -C "$runtime_parent"
fi
runtime_lib="$runtime_dir/lib/libonnxruntime.so.1.22.0"
if [[ -n "${GITHUB_ENV:-}" ]]; then
  echo "ORT_DYLIB_PATH=$runtime_lib" >> "$GITHUB_ENV"
fi
printf 'export ORT_DYLIB_PATH="%s"\n' "$runtime_lib"
