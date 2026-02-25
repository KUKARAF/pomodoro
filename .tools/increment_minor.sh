#!/usr/bin/env bash
# Bump the patch version (0.1.X) in pyproject.toml
set -euo pipefail

TOML="$(git rev-parse --show-toplevel)/pyproject.toml"

current=$(sed -n 's/^version = "\(.*\)"/\1/p' "$TOML")
IFS='.' read -r major minor patch <<< "$current"
patch=$((patch + 1))
new="$major.$minor.$patch"

sed -i "s/^version = \"$current\"/version = \"$new\"/" "$TOML"
echo "$current -> $new"
