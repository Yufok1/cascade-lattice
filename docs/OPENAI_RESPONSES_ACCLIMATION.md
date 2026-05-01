# OpenAI Responses Acclimation

## Status

Implemented in `cascade-lattice` 0.8.4.

## Scope

This is a free compatibility surface.

It does not call OpenAI by itself.

It does not require `OPENAI_API_KEY` for install, import, tests, docs, or local
receipt schema work.

A key is only needed when the user chooses to run live OpenAI API calls.

## Why

Cascade already observed OpenAI Chat Completions and legacy Completions.

OpenAI's newer primary text generation surface is the Responses API. The
package now observes `responses.create(...)` calls as well, while preserving the
older surfaces.

## Observed Surfaces

```python
from openai import OpenAI
import cascade

cascade.init(providers=["openai"])

client = OpenAI()
response = client.responses.create(
    model="gpt-5.2",
    input="Say one sentence about receipts.",
)
```

Cascade emits a local receipt around:

- model id
- endpoint: `responses`
- input text or structured input
- output text when available
- token usage when present
- provider context

Also preserved:

- `chat.completions`
- legacy `completions`

## No-Cost Test Posture

The package tests use a fake `openai` module.

They verify wrapping and receipt emission without:

- network calls
- OpenAI billing
- real API keys
- model invocation

## Boundary

Cascade records receipt context. It does not decide whether a model response is
true, safe, legal, medical, or authorized. It preserves provenance so another
system or human can review the call.

## Maintainer Note

I share the belief that joining with AI should move toward human purpose, not away from it. The package says it plainly: "even still, i grow, and yet, I grow still". In cascade-lattice, that belief becomes an architectural requirement: durable provenance, reviewable receipts, and HOLD points keep capability attached to responsibility.


