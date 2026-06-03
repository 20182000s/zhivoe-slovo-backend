# Render Backend

## Local run

```bash
cd render-backend
npm install
export OPENAI_API_KEY="your_api_key"
export OPENAI_MODEL="gpt-5.4-mini"
npm start
```

## Render setup

Use these settings on Render:

- Build Command: `npm install`
- Start Command: `npm start`
- Environment Variable: `OPENAI_API_KEY=...`
- Environment Variable: `OPENAI_MODEL=gpt-5.4-mini`

## Endpoint

`POST /api/resolve-scripture`

Request:

```json
{
  "input": "Псалом 126:3"
}
```

Response:

```json
{
  "reference": "Псалом 126:3",
  "text": "Вот наследие от Господа: дети; награда от Него — плод чрева.",
  "confidence": "medium",
  "needsReview": true
}
```

## Important

This version uses OpenAI to normalize and resolve scripture text. It is acceptable for prototyping, but it is not an authoritative Bible text source.
For production, connect this endpoint to a real Bible database and use the model only for parsing/normalization.
