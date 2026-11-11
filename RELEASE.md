# Release steps (for the owner)

Nothing here has been run. The repo is private until you decide otherwise, and nothing has been published.

## 0–1. History and push: done

Done on 2026-11-12 (see `BLOCKED.md` → Resolved): the repository was recreated from one clean commit with `v0.1.0`. If anything private is ever pushed again, recreate the repository from a clean commit; a force-push is not enough.

## 2. Go public

```bash
GH_TOKEN=$(gh auth token -u vulbsti) gh api -X PATCH repos/vulbsti/agent-readback -f visibility=public --jq .visibility
GH_TOKEN=$(gh auth token -u vulbsti) gh api -X PUT repos/vulbsti/agent-readback/private-vulnerability-reporting   # the channel SECURITY.md points to
GH_TOKEN=$(gh auth token -u vulbsti) gh repo edit vulbsti/agent-readback \
  --add-topic claude-code --add-topic codex --add-topic coding-agents --add-topic llm --add-topic developer-tools
GH_TOKEN=$(gh auth token -u vulbsti) gh release create v0.1.0 --title "agent-readback 0.1.0" --notes-file CHANGELOG.md
```

Once the repo is public, the README install line (`uv tool install git+https://github.com/vulbsti/agent-readback`) and the plugin marketplace (`claude plugin marketplace add vulbsti/agent-readback`) work as written.

## 3. Publish to PyPI (optional; the name `agent-readback` was free on 2026-11-05)

```bash
uv build
uv publish            # needs a PyPI token: UV_PUBLISH_TOKEN=pypi-...
```

After publishing, add `uv tool install agent-readback` / `pipx install agent-readback` to the README.

## 4. Claude Code plugin directories (optional)

The repo is already a valid marketplace (`.claude-plugin/marketplace.json`, `claude plugin validate .` passes). To submit it to a public plugin directory, run `claude plugin validate . --profile directory` first and fix anything it reports.
