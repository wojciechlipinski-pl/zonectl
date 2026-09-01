#!/bin/sh
set -eu

key="${1:-u}"
output="${2:-docs/images/tui-audit-browser.png}"
temporary="${output}.capture.png"

for tool in xvfb-run xterm xdotool import magick; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "missing screenshot dependency: $tool" >&2
        exit 2
    }
done

xvfb-run -a -s "-screen 0 1680x1050x24" sh -c '
    set -eu
    key="$1"
    output="$2"
    xterm -geometry 164x55+0+0 -fa "Noto Mono" -fs 11 +sb \
        -xrm "XTerm*background: black" \
        -xrm "XTerm*foreground: white" \
        -e env TERM=xterm-256color PYTHONPATH=src \
        .venv/bin/python scripts/run_screenshot_demo.py &
    terminal_pid=$!
    cleanup() {
        kill "$terminal_pid" 2>/dev/null || true
    }
    trap cleanup EXIT INT TERM
    window="$(xdotool search --sync --onlyvisible --class XTerm | head -n 1)"
    sleep 3
    xdotool windowfocus --sync "$window"
    xdotool key "$key"
    sleep 1
    import -window "$window" "$output"
    kill "$terminal_pid" 2>/dev/null || true
    wait "$terminal_pid" || true
' capture "$key" "$temporary"

magick "$temporary" -strip "$output"
rm -f -- "$temporary"
chmod 0644 "$output"
echo "$output"
