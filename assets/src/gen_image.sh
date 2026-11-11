#!/usr/bin/env bash
# gen_image.sh OUT.png PROMPT.txt  -> landscape image via `codex exec` image generation (gpt-6-luna)
set -uo pipefail
out=$(realpath -m "$1"); prompt=$(cat "$2")
msg="Call your image generation tool directly, exactly once, landscape 1536x1024. Pass the image prompt below to the tool word for word. Do not read files, run shell commands or judge the result. Image prompt: $prompt"
wd=$(mktemp -d); log=$wd/log.txt
codex exec --ignore-user-config --skip-git-repo-check -s read-only -m gpt-6-luna -c model_reasoning_effort=low -C "$wd" -- "$msg" </dev/null >"$log" 2>&1
sid=$(grep -m1 -o 'session id: [0-9a-f-]*' "$log" | cut -d' ' -f3)
png=$(ls -t ~/.codex/generated_images/$sid/*.png 2>/dev/null | head -1)
[[ -n $png ]] && cp "$png" "$out" && echo "ok $out" || { echo "failed; log: $log"; tail -5 "$log"; }
