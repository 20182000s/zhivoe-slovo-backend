import express from "express";
import OpenAI from "openai";

const app = express();
app.use(express.json({ limit: "1mb" }));

const port = process.env.PORT || 3000;
const openaiApiKey = process.env.OPENAI_API_KEY;
const openaiModel = process.env.OPENAI_MODEL || "gpt-5.4-mini";

if (!openaiApiKey) {
    throw new Error("OPENAI_API_KEY is required.");
}

const openai = new OpenAI({
    apiKey: openaiApiKey
});

app.get("/health", (_request, response) => {
    response.json({ ok: true });
});

app.post("/api/resolve-scripture", async (request, response) => {
    try {
        const input = String(request.body?.input ?? "").trim();
        if (!input) {
            return response.status(400).json({
                error: "Field 'input' is required."
            });
        }

        const prompt = [
            "Ты помогаешь приложению с местописаниями.",
            "Верни только JSON.",
            "Нужно извлечь или нормализовать местописания из пользовательского ввода.",
            "Если в большом тексте встречается несколько отдельных местописаний, выдели каждое отдельно.",
            "Если пользователь ввёл только ссылку, обязательно верни каноническую ссылку и полный текст стиха на русском языке.",
            "Если пользователь ввёл текст без ссылки, сохрани текст как есть и оставь reference пустым, если ссылка неочевидна.",
            "Если пользователь ввёл и ссылку, и текст, приведи их к единому виду.",
            "Никогда не возвращай пустой text, если reference распознан.",
            "Если можешь выделить несколько местописаний, верни массив items с несколькими объектами.",
            "Если не можешь уверенно дать текст стиха, не включай такой элемент в items.",
            "Не добавляй пояснений вне JSON.",
            "Формат ответа:",
            '{"items":[{"reference":"", "text":""}], "confidence":"high|medium|low", "needsReview":false}',
            `Пользовательский ввод: ${input}`
        ].join("\n");

        const completion = await openai.chat.completions.create({
            model: openaiModel,
            temperature: 0.1,
            response_format: { type: "json_object" },
            messages: [
                {
                    role: "system",
                    content: "Ты возвращаешь только корректный JSON без markdown."
                },
                {
                    role: "user",
                    content: prompt
                }
            ]
        });

        const content = completion.choices[0]?.message?.content;
        if (!content) {
            return response.status(502).json({
                error: "OpenAI returned an empty response."
            });
        }

        let parsed;
        try {
            parsed = JSON.parse(content);
        } catch {
            return response.status(502).json({
                error: "OpenAI returned invalid JSON."
            });
        }

        const normalized = {
            items: Array.isArray(parsed.items)
                ? parsed.items
                    .map((item) => ({
                        reference: String(item?.reference ?? "").trim(),
                        text: String(item?.text ?? "").trim()
                    }))
                    .filter((item) => item.reference || item.text)
                : [],
            confidence: String(parsed.confidence ?? "low").trim(),
            needsReview: Boolean(parsed.needsReview)
        };

        if (normalized.items.some((item) => item.reference && !item.text)) {
            return response.status(422).json({
                error: "Model returned a reference without scripture text."
            });
        }

        if (!normalized.items.length) {
            return response.status(422).json({
                error: "Could not resolve scripture from input."
            });
        }

        response.json(normalized);
    } catch (error) {
        response.status(500).json({
            error: "Internal server error.",
            message: error instanceof Error ? error.message : "Unknown error."
        });
    }
});

app.listen(port, () => {
    console.log(`Zhivoe Slovo backend listening on port ${port}`);
});
