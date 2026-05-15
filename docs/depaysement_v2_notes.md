# Depaysement prototype v2 notes

## What changed from v1

### 1. Lexicon scoring is no longer the main reward

The lexicon is now a weak anchor only. It contributes capped concept dispersion and cross-domain distance, but repeated keywords do not keep increasing the score. Keyword stuffing is penalized by term density, repeated hits, list-like noun collages, and “many concept fields but no relation schema.”

Useful flags:

```bash
--disable-lexicon      # turn off lexicon features entirely
--lexicon fields.json  # provide your own concept fields
--no-bank-score        # turn off prompt-bank contrast
--embed-model MODEL    # use an HF encoder for semantic bank contrast instead of hash n-grams
```

### 2. Image schema scoring separates depaysement from mere weirdness

A candidate gets image-schema credit when it contains relation scaffolding such as spatial, contact, possession/part, transformation, containment, or exchange relations.

Examples of rewarded structures:

```text
X の中で Y が眠る
X が Y を持つ
X は Y になる
X の壁に Y が貼られる
X が Y に触れる
```

This is meant to detect whether the sentence is staged as a scene, not just strange nouns placed in sequence.

### 3. Context overlap became anchor resonance

v1 punished overlap directly. v2 uses a band-pass idea:

```text
zero retained anchors      => weak orphan penalty
some retained anchors      => resonance bonus
too many retained anchors  => overfit/context inertia penalty
```

The generator prompt also uses motif jitter. Sometimes it preserves one previous motif, sometimes it drops it, and rarely it preserves two. This gives連作性 without forcing every sentence to be a direct continuation.

### 4. Repair phrases are contextual

“つまり” is no longer automatically bad.

```text
Bad:
つまり、これは孤独の比喩だった。

Good:
つまり、傘は海の肺だった。駅の壁に影が貼られている。
```

The first is penalized because it contains explanatory meta terms. The second gets a voice-hinge bonus because it uses the connector to open an image rather than interpret it.

## Core commands

Dependency-free dummy run:

```bash
python depaysement_proto_v2.py write --backend dummy --seed "駅に忘れられた傘が" --steps 4 --trace
```

Rank candidates for one continuation:

```bash
python depaysement_proto_v2.py rank --backend dummy --seed "駅に忘れられた傘が" --candidates 12
```

Score a fragment:

```bash
python depaysement_proto_v2.py score "つまり、傘は海の肺だった。駅の壁に影が貼られている。"
python depaysement_proto_v2.py score "机、月、骨、切符、魚、窓、判子、舌、海、海、海。"
```

Expand a prompt bank:

```bash
python depaysement_proto_v2.py expand-bank \
  --backend dummy \
  --out depaysement_bank_v2.json \
  --positive 24 \
  --negative 16 \
  --trace
```

Collect layer-wise steering vectors:

```bash
python depaysement_proto_v2.py collect-vectors \
  --model gpt2 \
  --bank depaysement_bank_v2.json \
  --out depaysement_vectors.pt \
  --token-strategy mean
```

Generate with activation steering:

```bash
python depaysement_proto_v2.py write \
  --backend hf \
  --model gpt2 \
  --bank depaysement_bank_v2.json \
  --vectors depaysement_vectors.pt \
  --steer-alpha 1.2 \
  --steer-layers 4-8 \
  --seed "A forgotten umbrella at the station" \
  --trace
```

## Suggested steering sweep

Start with middle layers and keep the external scorer active:

```text
alpha: 0.4, 0.8, 1.2, 1.8
layers: lower-middle, middle, upper-middle
position: last first; all only if the model under-responds
```

The desired region is not maximum weirdness. It is:

```text
semantic distance high
image schema present
local fluency preserved
explanation/closure low
context resonance nonzero but not dominant
```
