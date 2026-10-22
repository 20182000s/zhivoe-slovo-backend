# Слово API v2

Backend for the native iPhone app with Synodal and Ogienko Bible texts.

Render keeps its existing Node service, URL and plan. npm install installs Gunicorn; npm start runs Python WSGI.

Required environment: OPENAI_API_KEY, API_TOKEN (at least 24 random characters).
Optional: DATABASE_PATH. All generative AI workloads use the approved `gpt-6.1-sol` model through Responses with medium reasoning. Library reflection uses `text-embedding-3-small` (512 dimensions) for retrieval only. Legacy generative model-routing environment variables are ignored.

GET /health is public. POST /v1/status and /v2/import, /v2/practice, /v2/answer, /v2/reflect require Bearer API_TOKEN.

Tests: python3 -m unittest discover -v

Bible quotations come from the bundled corpus, never from generated text. See SCROLLMAPPER-LICENSE.txt. Original source: https://github.com/scrollmapper/bible_databases.

The previous Node source remains in server.js and Git history for rollback; npm start runs app.py.

## Prepared content · 19 October 2026

5000 independently authored RU/UK situations, each with two accepted passages. Each answer has its own “Why it fits” explanation; each situation has a concrete “How to apply” action, in both languages. All-Bible practice selects from this bank by theme or book without generation calls. Exact prepared references and complete quotations use this authored guidance locally. Other answers retain semantic AI evaluation, which returns both the passage-specific reason and application using exact Bible text. Correct answers grant 5 XP and 2 mastery when the passage is in the library; blank reveals grant neither.

The thematic library contains 6000 unique passages, 400 for each of 15 topics. The selection adapts the OpenBible.info topical index (https://www.openbible.info/topics/), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); topic assignments and reference mappings were modified for this app. Bible text licensing remains in SCROLLMAPPER-LICENSE.txt.

## Everyday practice · 21 October 2026

The 5000 Russian narratives received a complete review, supported by bilingual screening. 505 stories were revised into everyday contexts with corresponding RU/UK reasons and actions. Accepted passages were checked against the exact local corpus and reviewed for their fit to the revised story. The catalog retains two non-overlapping accepted answers per situation.

Library-practice generation now requests everyday work, study, home and conversation scenarios. Prepared all-Bible practice continues to use the local catalog.

Bulk import supports up to 100 passages and 200,000 input characters per request. Limit errors include the allowed amount and excess in Russian or Ukrainian.

## Practice reliability · 5 October 2026

Library practice accepts `target_id` only when it belongs to the submitted library. The iOS client randomly chooses from the least-shown passages, persists counts per language, and counts only successfully received situations. Older clients use server-side least-shown selection.

New questions return `focus`, naming the person and task to consider, and an encrypted `recovery` token. Submit it with `/v2/answer` to restore the original question after a database reset, within seven days. The token is bound to the owner, quiz ID and translation; its key derives from the existing API_TOKEN. It hides the expected passage and cannot be modified. No new account credential or persistent disk is needed. Previously lost questions without a token require a new situation.

Practice, reflection and prayer suggestions exclude duplicate shortened or expanded ranges. AI evaluations preserve separate passage-specific reasons and applications. External library-practice suggestions appear under a separate heading in the iOS app.

## Meditation coaching · 19 October 2026

Authenticated `/v2/meditation` grades meaning and personal application on a 1–5 rubric using exact corpus text. `/v2/application` adapts saved practice actions into personal plans without fictional names. Both validate structured responses and cache successful coaching results per owner for up to 30 days; raw submitted answers are not stored in this cache. Failed evaluations never produce a grade. Library practice addresses the reader directly. The approved model and existing shared request budget remain unchanged.

Client progression records five combined rewarded meaning/application submissions per saved passage across translations, with same-session improvements paying only the positive score difference. Recall can earn up to five points during the first complete session. Day recommendations of saved passages add two mastery points without account XP.

## Library reflection retrieval · 22 October 2026

`/v2/reflect` sends libraries of 1–99 saved passages directly to the generative model. Libraries of 100–5000 passages use semantic search over every supplied passage, considering the whole story and its separate aspects. The initial shortlist has 30 candidates, expanded to 60 for weak or flat similarity scores. An empty model selection can trigger one wider pass of up to 90–120 candidates within the request deadline. Similarity thresholds are conservative heuristics, not calibrated probabilities.

The generative model receives exact corpus text with short temporary IDs. The server maps its selection back to the original saved passage; it cannot select an outside-library ID. Very long ranges are indexed in lossless chunks, and the model sees the best exact span with adjacent chunks. The app still receives the full original saved passage. All-Bible reflection retains its existing workflow.

Only public passage embeddings are cached in SQLite, keyed by model, dimensions and exact text. Story embeddings stay in memory and are never cached or logged. The shared index is reused across requests and grows only for uncached public text; on an ephemeral Render filesystem it may rebuild after a restart or deployment. Completed index batches survive a later request failure while that database exists. Index and query calls count toward the existing shared daily AI limit, and usage logs distinguish `library_index` and `library_query`. Provider failures return a retryable error rather than a false empty match or a costly silent full-library fallback. The reflection deadline is 110 seconds, below the app's 120-second timeout.
