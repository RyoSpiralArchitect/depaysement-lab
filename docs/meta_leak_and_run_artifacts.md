# v0.6: meta-leak filtering and run artifacts

## Why this exists

Instruction-tuned chat models sometimes obey the instruction frame too literally and append text such as:

```text
(Note: I've tried to continue the fragment while maintaining the atmosphere...)
```

That is a useful experimental signal: the model is still in assistant mode. But it should not win the depaysement rerank.

## What v0.6 changes

1. **Scene-only prompt style**

   The default `--prompt-style scene` avoids naming the theory inside the prompt. It asks for the next visible image and bans notes/commentary.

2. **Cleanup**

   `cleanup_continuation` cuts appended `Note:` / prompt-frame commentary and removes dangling incomplete tails after token truncation.

3. **Scoring**

   `meta_leak_penalty` appears as `meta` in `--trace`. A value like `meta=-1.00` means the candidate leaked assistant/prompt commentary and should rank lower.

4. **Higher token budget**

   `write` and `rank` now default to `--max-new-tokens 120`, up from 70.

## Recommended MLX command

```bash
depaysement-lab write \
  --backend mlx \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --chat-template \
  --seed "A forgotten umbrella at the station" \
  --steps 4 \
  --candidates 8 \
  --max-new-tokens 120 \
  --trace \
  --out experiments/umbrella_run.json
```

## Output formats

```bash
# Structured one-run artifact
depaysement-lab write --backend dummy --out experiments/run.json

# Append one line per run for sweeps
depaysement-lab write --backend dummy --out experiments/runs.jsonl --out-format jsonl

# Compact human-readable report
depaysement-lab write --backend dummy --out experiments/run.txt
```

Use `--save-candidates N` to control how many ranked candidates per step are stored in JSON output. Use `--include-prompt` when you want prompt audit trails.
