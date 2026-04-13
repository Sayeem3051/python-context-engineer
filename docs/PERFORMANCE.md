## Performance & scaling

### Practical tips
- Use `.ctxengignore` to exclude large or irrelevant directories (`node_modules/`, `dist/`, `venv/`, logs, build artifacts).
- Prefer `--git-diff` for PR reviews (limits the candidate set dramatically).
- Turn off git recency if you’re not in a repo or git is slow: `--no-git`.

### Parallel scoring
For large repositories, ctxeng parallelizes file scoring to improve throughput. (Scoring is CPU + IO bound.)

### Semantic scoring
Semantic scoring is optional and can be expensive on very large repos. For best results:\n- Install extras: `pip install \"ctxeng[semantic]\"`\n- Use a strong model (default): `all-mpnet-base-v2`\n
### Benchmarks
Target: **< 5 seconds for 10K files** on a modern laptop, depending on disk speed and git performance.\n\nIf you want to benchmark, run the CI pipeline and compare timings across commits.\n
