# Optimized prompt (token-minimized, structured)

Analyze the pre-processed call excerpt. Boilerplate and filler have already been
removed and spoken digits normalized. Return ONLY minified JSON matching this schema:

{"member_id": string|null, "sentiment": "positive"|"neutral"|"negative", "escalation": boolean, "summary": string}

Rules:
- Do not restate the transcript.
- `summary` must be <= 240 characters.
- If no member id is present, use null.

Excerpt:

{transcript}
