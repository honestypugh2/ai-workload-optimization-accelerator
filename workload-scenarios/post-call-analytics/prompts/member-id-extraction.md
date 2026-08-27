# Member-ID extraction prompt (LLM fallback only)

This prompt is used ONLY as a fallback when deterministic extraction returns a
low-confidence result. Deterministic extraction (regex + spoken-digit and
delimiter normalization + fragment reconstruction) runs first.

Extract the member identification number from the excerpt. Member ids are
2-4 uppercase letters followed by 9 digits (e.g. a prefix like MBR/HPL/SVC).
The number may be spoken as digit words, separated by dashes or spaces, or split
across turns.

Return ONLY minified JSON: {"member_id": string|null, "confidence": number}

Excerpt:

{transcript}
