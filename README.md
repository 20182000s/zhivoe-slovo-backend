# Слово API v2

Backend for the native iPhone app with Synodal and Ogienko Bible texts.

Render keeps its existing Node service, URL and plan. npm install installs Gunicorn; npm start runs Python WSGI.

Required environment: OPENAI_API_KEY, API_TOKEN (at least 24 random characters).
Optional: OPENAI_MODEL (defaults to gpt-6-astra), DATABASE_PATH.

GET /health is public. POST /v1/status and /v2/import, /v2/practice, /v2/answer, /v2/reflect require Bearer API_TOKEN.

Tests: python3 -m unittest discover -v

Bible quotations come from the bundled corpus, never from generated text. See SCROLLMAPPER-LICENSE.txt. Original source: https://github.com/scrollmapper/bible_databases.

The previous Node source remains in server.js and Git history for rollback; npm start runs app.py.

## Prepared content · 24 September 2026

880 independently authored RU/UK situations, each with two accepted passages. All-Bible practice selects from this bank by theme or book without generation calls. Exact prepared references and complete quotations are checked locally; other answers retain semantic AI evaluation. Correct answers grant 5 XP and 2 mastery when the passage is in the library.

The thematic library contains 6000 unique passages, 400 for each of 15 topics. The selection adapts the OpenBible.info topical index (https://www.openbible.info/topics/), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); topic assignments and reference mappings were modified for this app. Bible text licensing remains in SCROLLMAPPER-LICENSE.txt.
