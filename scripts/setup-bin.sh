#!/usr/bin/env bash
set -euo pipefail

src_dir="$(cd -- "${1:?Source checkout directory is required}" && pwd)"
for file in files/themes.json scripts/commit.sh scripts/setup-onnx.sh; do
  if [[ ! -f "$src_dir/$file" ]]; then
    printf '::error::Missing %s in source checkout %s.\n' "$file" "$src_dir"
    exit 1
  fi
done

case "$(uname -s)/$(uname -m)" in
  Linux/x86_64) platform=linux-x64 ;;
  Linux/aarch64) platform=linux-arm64 ;;
  *) echo '::error::Prebuilt actions support Linux x64 and ARM64. Build locally with Cargo on other platforms.' >&2; exit 1 ;;
esac

src_sha="$(git -C "$src_dir" rev-parse HEAD)"
origin="$(git -C "$src_dir" remote get-url origin)"
repo="${origin#https://github.com/}"
repo="${repo%.git}"
if [[ ! "$src_sha" =~ ^[0-9a-f]{40}$ || ! "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo '::error::Expected a GitHub HTTPS source checkout and a full commit SHA.' >&2
  exit 1
fi

tag="binary-$src_sha"
asset="gh-profile-repo-pins-$platform.tar.gz"
bin_dir="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/repo-pins-bin/$src_sha/$platform"
mkdir -p "$bin_dir"
tmp_dir="$(mktemp -d "$bin_dir/download.XXXXXX")"
trap 'rm -rf -- "$tmp_dir"' EXIT
url="https://github.com/$repo/releases/download/$tag"

if ! curl --fail --location --retry 3 --proto '=https' --tlsv1.2 \
  "$url/$asset.sha256" --output "$tmp_dir/$asset.sha256"; then
  printf '::error::No published binary for %s. Wait for verify to finish in %s, or dispatch, then retry.\n' "$src_sha" "$repo" >&2
  exit 1
fi
curl --fail --location --retry 3 --proto '=https' --tlsv1.2 \
  "$url/$asset" --output "$tmp_dir/$asset"
(
  cd "$tmp_dir"
  sha256sum --check --strict "$asset.sha256"
  tar --extract --gzip --no-same-owner --no-same-permissions \
    --file "$asset" gh-profile-repo-pins SOURCE_COMMIT
)
if [[ -L "$tmp_dir/gh-profile-repo-pins" || -L "$tmp_dir/SOURCE_COMMIT" \
  || ! -f "$tmp_dir/gh-profile-repo-pins" || ! -f "$tmp_dir/SOURCE_COMMIT" \
  || "$(cat "$tmp_dir/SOURCE_COMMIT")" != "$src_sha" ]]; then
  echo '::error::The binary archive does not match the checked-out source commit.' >&2
  exit 1
fi
install -m 755 "$tmp_dir/gh-profile-repo-pins" "$bin_dir/gh-profile-repo-pins"
"$bin_dir/gh-profile-repo-pins" --help >/dev/null

if [[ -n "${GITHUB_ENV:-}" ]]; then
  printf 'REPO_PINS_SRC_DIR=%s\n' "$src_dir" >> "$GITHUB_ENV"
  printf 'REPO_PINS_BIN=%s/gh-profile-repo-pins\n' "$bin_dir" >> "$GITHUB_ENV"
fi
printf 'Ready: %s (%s)\n' "$tag" "$platform"
