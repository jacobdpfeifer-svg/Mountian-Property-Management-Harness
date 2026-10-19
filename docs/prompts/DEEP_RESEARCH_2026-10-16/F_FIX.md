# F: Apply a review to a dossier (author fix pass)

Input: `docs/research/deep_2026-10/reviews/<id>_review.md`
Target: the dossier itself, edited in place.

1. Read the review in full, then the current dossier.
2. Apply **every** numbered fix. Do not accept the reviewer's word blindly:
   - re-open the source for each corrected citation;
   - re-derive any arithmetic yourself;
   - re-run any analysis yourself (Python with `-I`, scratch under `/private/tmp/wp_research/`).
3. If you disagree with a fix, do not apply it silently or ignore it. Explain why, with evidence,
   in an appendix titled **"Response to review"**. That appendix has one row per fix:
   `# | applied / partly / rejected | what changed or why not`.
4. Correct the numbers in place. Where a correction changes a recommendation's rank or
   confidence, update the ranked list too. Do not leave contradicted figures anywhere in the text.
5. Re-run the self-audit table against `00_DEPTH_STANDARD.md` and update its counts.
6. Save after each group of fixes, so an interruption loses little.
7. Reply with a one-paragraph summary of what changed, plus the list of rejected fixes.
