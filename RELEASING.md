# Releasing distillory

distillory publishes to PyPI via **Trusted Publishing** (OIDC) — GitHub Actions
authenticates to PyPI with no stored API token. A tag push does the rest.

## One-time setup (you, on pypi.org — ~2 minutes)

Trusted Publishing lets you register the publisher *before the project exists*.

1. Sign in at <https://pypi.org> (create an account if needed).
2. Go to **Your projects → Publishing** (or <https://pypi.org/manage/account/publishing/>).
3. Under **Add a new pending publisher**, fill in:
   - **PyPI Project Name:** `distillory`
   - **Owner:** `everyai-com`
   - **Repository name:** `distillory`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
4. Save.

That's it — no secret is copied anywhere. (Optional but recommended: in the GitHub
repo, create an Environment named `pypi` under Settings → Environments and add
required reviewers, so a human approves each publish.)

## Cutting a release

```bash
# 1. bump the version in pyproject.toml (e.g. 0.1.0) and update CHANGELOG.md
# 2. commit
git commit -am "release: v0.1.0"
# 3. tag + push — this triggers .github/workflows/publish.yml
git tag v0.1.0
git push origin main --tags
```

Watch the run under the repo's **Actions** tab. On success, `pip install distillory`
works for everyone. After the first release, update the README install section to
lead with `pip install distillory`.

## Token fallback (if you prefer not to use Trusted Publishing)

```bash
python -m pip install --upgrade build twine
python -m build                       # builds sdist + wheel into dist/
twine check dist/*
twine upload dist/*                   # paste a PyPI API token when prompted
```

## Pre-publish sanity check (local)

```bash
make build            # python -m build
twine check dist/*    # validates metadata + long description rendering
```
