#!/usr/bin/env bash
# Build the self-contained single-file Windows exe (cross-built from Linux).
set -euo pipefail
cd "$(dirname "$0")"
DOTNET="${DOTNET:-$HOME/.dotnet/dotnet}"
export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
"$DOTNET" publish SteamLibrarySize.Gui -c Release -r win-x64 --self-contained \
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true \
  -o publish
ls -lh publish/*.exe
