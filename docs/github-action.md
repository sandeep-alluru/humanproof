# GitHub Action

Use humanproof directly in your GitHub Actions workflow:

```yaml
- name: humanproof
  uses: sandeep-alluru/humanproof@v0.1.0
  with:
    # TODO: add action inputs
    fail-on-error: "true"
```

Or use the CLI directly:

```yaml
- name: Install humanproof
  run: pip install humanproof

- name: Run humanproof
  run: humanproof --help
```
