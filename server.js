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
        const translation = String(request.body?.translation ?? "Синодальный перевод").trim();
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
            "Если пользователь ввёл диапазон, например 'Псалом 126:3-5', это один элемент items.",
            "Если пользователь ввёл перечисление через запятую, например 'Псалом 126:3, 126:4, 126:5', это три отдельных элемента items.",
            `Верни текст стихов строго в этом переводе: ${translation}.`,
            "Если пользователь ввёл только ссылку, обязательно верни каноническую ссылку и полный текст стиха именно в указанном переводе.",
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

app.post("/api/practice-guidance", async (request, response) => {
    try {
        const mode = String(request.body?.mode ?? "").trim();
        const translation = String(request.body?.translation ?? "Синодальный перевод").trim();
        const primaryInput = String(request.body?.primaryInput ?? "").trim();
        const secondaryInput = String(request.body?.secondaryInput ?? "").trim();
        const selectedTheme = String(request.body?.selectedTheme ?? "").trim();
        const selectedHeartState = String(request.body?.selectedHeartState ?? "").trim();
        const libraryVerses = Array.isArray(request.body?.libraryVerses) ? request.body.libraryVerses : [];

        if (!mode) {
            return response.status(400).json({
                error: "Field 'mode' is required."
            });
        }

        const serializedLibrary = libraryVerses.length
            ? JSON.stringify(libraryVerses.slice(0, 40))
            : "[]";

        const prompt = [
            "Ты помогаешь христианскому приложению практики применения Писания.",
            "Верни только JSON без markdown.",
            `Режим практики: ${mode}.`,
            `Перевод Библии для всех стихов: ${translation}.`,
            "Крайне важно: сначала предложи подходящие местописания из личной библиотеки пользователя.",
            "Если в личной библиотеке нет подходящих местописаний, явно напиши это в libraryPriorityMessage.",
            "Только после этого предложи дополнительные местописания из более широкого библейского контекста.",
            "Не говори от имени Бога.",
            "Не давай категоричных духовных приказов.",
            "Используй мягкие формулировки: 'может быть связано', 'можно увидеть принцип', 'возможное применение'.",
            "Не возвращай пустой text у стихов.",
            "Если указан режим 'livingApplication', мягко дополни ответ пользователя в userResponseFeedback.",
            "Если указан режим 'scriptureToday', заполни focusForToday и можешь вернуть tomorrowVerse пустым.",
            "Если указан режим 'eveningLight', постарайся вернуть tomorrowVerse.",
            "Формат ответа:",
            '{"detectedThemes":[""],"libraryPriorityMessage":"","libraryVerses":[{"reference":"","text":"","reason":""}],"biblePriorityMessage":"","bibleVerses":[{"reference":"","text":"","reason":""}],"explanation":"","conclusion":"","reflectionQuestion":"","nextStep":"","tomorrowVerse":{"reference":"","text":"","reason":""},"focusForToday":"","userResponseFeedback":""}',
            `Ввод пользователя: ${primaryInput}`,
            `Дополнительный ввод пользователя: ${secondaryInput}`,
            `Тема дня: ${selectedTheme}`,
            `Внутреннее состояние: ${selectedHeartState}`,
            `Личная библиотека пользователя: ${serializedLibrary}`
        ].join("\n");

        const completion = await openai.chat.completions.create({
            model: openaiModel,
            temperature: 0.2,
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

        const normalizeVerse = (item) => {
            const reference = String(item?.reference ?? "").trim();
            const text = String(item?.text ?? "").trim();
            const reason = String(item?.reason ?? "").trim();
            if (!reference || !text) {
                return null;
            }
            return { reference, text, reason };
        };

        const normalized = {
            detectedThemes: Array.isArray(parsed.detectedThemes)
                ? parsed.detectedThemes.map((item) => String(item).trim()).filter(Boolean)
                : [],
            libraryPriorityMessage: String(parsed.libraryPriorityMessage ?? "").trim(),
            libraryVerses: Array.isArray(parsed.libraryVerses)
                ? parsed.libraryVerses.map(normalizeVerse).filter(Boolean)
                : [],
            biblePriorityMessage: String(parsed.biblePriorityMessage ?? "").trim(),
            bibleVerses: Array.isArray(parsed.bibleVerses)
                ? parsed.bibleVerses.map(normalizeVerse).filter(Boolean)
                : [],
            explanation: String(parsed.explanation ?? "").trim(),
            conclusion: String(parsed.conclusion ?? "").trim(),
            reflectionQuestion: String(parsed.reflectionQuestion ?? "").trim(),
            nextStep: String(parsed.nextStep ?? "").trim(),
            tomorrowVerse: normalizeVerse(parsed.tomorrowVerse),
            focusForToday: String(parsed.focusForToday ?? "").trim(),
            userResponseFeedback: String(parsed.userResponseFeedback ?? "").trim()
        };

        if (!normalized.libraryPriorityMessage) {
            normalized.libraryPriorityMessage = libraryVerses.length
                ? "Сначала рассмотрены местописания из личной библиотеки пользователя."
                : "В личной библиотеке пользователя пока нет подходящих местописаний."
        }

        if (!normalized.biblePriorityMessage) {
            normalized.biblePriorityMessage = "После этого предложены дополнительные местописания из более широкого библейского контекста."
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
