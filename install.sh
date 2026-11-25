#!/bin/sh
set -eu
DEST="${HOME}/.local/bin"
mkdir -p "$DEST"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -m 755 "$SCRIPT_DIR/unifetch.py" "$DEST/unifetch"
printf 'Installed UniFetch to %s/unifetch\\n' "$DEST"
case ":${PATH}:" in
  *":$DEST:"*) ;;
  *) printf 'Add this to your shell profile if needed:\\n  export PATH="$HOME/.local/bin:$PATH"\\n' ;;
esac
