#!/usr/bin/env bash
# Bump the minor version (0.X.0) in pyproject.toml, reset patch to 0
set -euo pipefail

TOML="$(git rev-parse --show-toplevel)/pyproject.toml"

current=$(sed -n 's/^version = "\(.*\)"/\1/p' "$TOML")
IFS='.' read -r major minor patch <<< "$current"
minor=$((minor + 1))
new="$major.$minor.0"

sed -i "s/^version = \"$current\"/version = \"$new\"/" "$TOML"
echo "$current -> $new"
