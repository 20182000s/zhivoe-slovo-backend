# Слово API v2

Backend for the native iPhone app with Synodal and Ogienko Bible texts.

Render keeps its existing Node service, URL and plan. npm install installs Gunicorn; npm start runs Python WSGI.

Required environment: OPENAI_API_KEY, API_TOKEN (at least 24 random characters).
Optional: DATABASE_PATH. All AI workloads use the approved `gpt-6.1-sol` model through Responses with medium reasoning. Legacy model-routing environment variables are ignored.

GET /health is public. POST /v1/status and /v2/import, /v2/practice, /v2/answer, /v2/reflect require Bearer API_TOKEN.

Tests: python3 -m unittest discover -v

Bible quotations come from the bundled corpus, never from generated text. See SCROLLMAPPER-LICENSE.txt. Original source: https://github.com/scrollmapper/bible_databases.

The previous Node source remains in server.js and Git history for rollback; npm start runs app.py.

## Prepared content · 24 September 2026

1626 independently authored RU/UK situations, each with two accepted passages. Each answer has its own “Why it fits” explanation; each situation has a concrete “How to apply” action, in both languages. All-Bible practice selects from this bank by theme or book without generation calls. Exact prepared references and complete quotations use this authored guidance locally. Other answers retain semantic AI evaluation, which returns both the passage-specific reason and application using exact Bible text. Correct answers grant 5 XP and 2 mastery when the passage is in the library; blank reveals grant neither.

The thematic library contains 6000 unique passages, 400 for each of 15 topics. The selection adapts the OpenBible.info topical index (https://www.openbible.info/topics/), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); topic assignments and reference mappings were modified for this app. Bible text licensing remains in SCROLLMAPPER-LICENSE.txt.

Bulk import supports up to 100 passages and 200,000 input characters per request. Limit errors include the allowed amount and excess in Russian or Ukrainian.

## Practice reliability · 5 October 2026

Library practice accepts `target_id` only when it belongs to the submitted library. The iOS client randomly chooses from the least-shown passages, persists counts per language, and counts only successfully received situations. Older clients use server-side least-shown selection.

New questions return `focus`, naming the person and task to consider, and an encrypted `recovery` token. Submit it with `/v2/answer` to restore the original question after a database reset, within seven days. The token is bound to the owner, quiz ID and translation; its key derives from the existing API_TOKEN. It hides the expected passage and cannot be modified. No new account credential or persistent disk is needed. Previously lost questions without a token require a new situation.

Practice, reflection and prayer suggestions exclude duplicate shortened or expanded ranges. AI evaluations preserve separate passage-specific reasons and applications. External library-practice suggestions appear under a separate heading in the iOS app.
