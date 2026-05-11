# Murmure — multilingual Telegram support bot for natural-stone jewelry shops

A production RAG chatbot for small Telegram-based jewelry shops. Customers ask in Ukrainian, Russian, or English; the bot answers from the live catalog and hands off to the owner when it doesn't know.

Portfolio piece + sellable product for SMB shop owners. Stack: Vercel Functions (Python) + Supabase pgvector + Gemini.

> Live demo: see [For Telegram-shop owners](#for-telegram-shop-owners-ruua) below for a contact link.

---

## The problem

Telegram is the de-facto sales channel for thousands of small jewelry/accessories shops in Ukraine, Russia, Kazakhstan, and Belarus. The owner is usually one person who:

- Answers every customer DM personally — `Чи є цей колір?`, `Скільки доставка в Алмати?`, `Що подарувати мамі?`
- Re-types the same answers across Instagram, Telegram, WhatsApp, sometimes 100+ messages a day
- Loses leads while sleeping or off

Off-the-shelf chatbots either cost $50-200/mo (Manychat, Chatfuel) or speak only English. Owners who tried generic GPT bots got back unrelated marketing copy or hallucinated products.

## The solution

A grounded RAG agent that:

1. Reads the shop's product catalog from Supabase (pgvector for semantic search)
2. Detects the customer's language (UA / RU / EN) and replies in the same one
3. Uses **only** items present in the catalog (no hallucinated products)
4. Hands off to the owner when no good match exists, and logs the missed question for the owner to review later
5. Gives the owner `/stats` and `/missed` admin commands so they can iterate on catalog content

## Architecture

```
Customer (Telegram)
   │
   ▼  POST /api/index
Vercel Function (Python 3.12)
   │  ① Verify X-Telegram-Bot-Api-Secret-Token  ──► 403 on mismatch
   │  ② Build python-telegram-bot Application, dispatch one Update
   ▼
   ├──► Embed query (Gemini text-embedding-2, 1536-dim)
   │       │
   │       ▼
   │     Supabase RPC murmure.match_products
   │       │  (pgvector cosine similarity, top-3, in-stock filter)
   │       ▼
   │     Threshold check (similarity ≥ 0.4)
   │       │
   │       ├── below ──► reply with multilingual handoff text
   │       │           ──► insert row in murmure.missed
   │       │
   │       └── above ──► Gemini 2.5-flash + system prompt with product context
   │                   (retry + fallback chain to flash-lite, 2.0-flash on 503)
   │                   ──► reply in detected language
   │
   └──► Fire-and-forget insert into murmure.messages
```

### Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Bot framework | `python-telegram-bot` 22.7 | Async, mature, official BotFather workflows |
| LLM | `gemini-2.5-flash` with fallback chain | Free tier covers 1k msgs/mo, multilingual quality good |
| Embeddings | `gemini-embedding-2` @ 1536-dim | Cross-lingual (matches `amethyst` to `аметист`), free |
| Vector DB | Supabase pgvector | Managed Postgres + ivfflat index, plays well with logs |
| Logs | Supabase Postgres (separate `murmure` schema) | One backend, RLS for isolation |
| Deploy | Vercel Functions (Python runtime) | Serverless, free Hobby tier, GitHub auto-deploy |
| Webhook auth | `secret_token` header | Telegram-recommended, replaces Vercel SSO (which Telegram doesn't speak) |

### Cost (production at 1000 messages/month)

| Service | Free tier covers it? | Cost beyond free |
| --- | --- | --- |
| Gemini API | Yes (1k requests/min, 1M tokens/day) | ~$0.50/mo at 10k msg/mo on paid tier |
| Supabase | Yes (500 MB DB, 5 GB bandwidth) | $25/mo Pro tier when you outgrow |
| Vercel | Yes (Hobby: 100k function invocations/mo) | $20/mo Pro |
| **Total at 1k msgs/mo** | **$0** | — |

## Quick start (self-host)

```bash
# 1. Clone + venv
git clone https://github.com/Noritur/tg-shop-rag-bot.git
cd tg-shop-rag-bot
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Get credentials
#    TELEGRAM_BOT_TOKEN  ← BotFather (/newbot)
#    GEMINI_API_KEY      ← https://aistudio.google.com/apikey (free)
#    SUPABASE_URL/KEY/SERVICE_KEY ← https://supabase.com (free project)
#    ADMIN_USER_ID       ← @userinfobot in Telegram
#    WEBHOOK_SECRET      ← openssl rand -hex 32
cp .env.example .env  # fill in the values

# 3. Apply Supabase schema (run the SQL in Supabase SQL editor)
#    See migrations: init_murmure_schema, grant_murmure_to_anon, enable_rls_murmure
#    Then: Settings → API → Exposed schemas → add `murmure` → Save

# 4. Seed the catalog
python -m bot.scripts.seed_supabase

# 5. Local dev (polling — simplest):
python -m bot.main

# 6. Production (Vercel Functions + webhook):
vercel link --yes
vercel env add TELEGRAM_BOT_TOKEN production  # repeat for all 7 vars
vercel --prod
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=https://YOUR-PROJECT.vercel.app/api/index" \
  -d "secret_token=$WEBHOOK_SECRET"
```

## What's NOT in MVP (intentional)

- Payment processing (Telegram Payments API exists, deferred)
- Multi-tenancy — one shop = one deploy
- Web admin dashboard — `/stats` and `/missed` Telegram commands cover daily use
- Voice / photo messages
- Photo-based search (`find a ring like this`)
- Languages beyond UA / RU / EN

## Roadmap

- **Catalog v2 schema** — rich product fields (`occasions`, `dress_code`, `gift_for`, `care`, `pairs_with`) — see [Content Strategy](#content-strategy-for-shop-owners) below
- Multi-tenancy with shared infra and per-shop catalogs
- Web admin UI for catalog edits (replace JSON-by-hand)
- Voice / photo input
- Auto-translate catalog into target languages (DE, PL, ES) so EU markets work without manual rewriting
- Customer review aggregation as additional RAG context

## Content Strategy for shop owners

The hardest part of this bot isn't the code — it's what's in the catalog.

Bot quality is bound by content depth. Flat product descriptions force the LLM to summarize verbatim. Rich, structured content lets it answer questions the description doesn't literally answer (`what to gift my mom on her 60th who's a teacher?`).

### Five principles for RAG-friendly product content

1. **Structured fields beat long prose.** Embeddings match better on short specific blocks; the LLM cites concrete fields instead of paraphrasing one big paragraph.
2. **Cover the queries you expect.** If customers ask `for the office?`, your fields must include `occasions: ["office"]` or `dress_code: ["business"]`.
3. **Use sensory and emotional language.** `warm pink overtone`, `grounding`, `calming` — embeddings match on vibe, not just facts.
4. **Include the negatives.** `not for the shower`, `not for nickel allergies`. The bot can then honestly say `this isn't for you`, which builds trust.
5. **Pair-with for upsell.** Each item should reference 2–3 `pairs_with` IDs. The bot will naturally add `also pairs with…` to replies — direct revenue lift with zero extra UX work.

### Recommended catalog v2 schema

```json
{
  "id": "earr-pearl-009",
  "name": "Pearl Drop Earrings",
  "category": "earrings",
  "stone": "freshwater pearl",
  "stone_origin": "cultured, teardrop shape",
  "stone_properties": "elegance, purity, motherhood symbolism",
  "color": "white with warm pink overtone",
  "size_cm": 2,
  "material": "925 silver, nickel-free hooks",
  "price_uah": 1750,
  "price_reasoning": "natural pearl + hypoallergenic silver hooks, not bulk costume",
  "occasions": ["wedding", "evening", "office", "smart casual"],
  "dress_code": ["business", "evening gown"],
  "gift_for": ["mother", "bride", "30+ friend", "teacher"],
  "season": "all-year",
  "care": "Store separately in soft cloth. Avoid showers and saunas. Apply perfume before wearing, never after.",
  "warning": "Hypoallergenic — suits sensitive skin. Not for contact sports.",
  "pairs_with": [
    "neck-rose-quartz-003 — soft pastel palette",
    "earr-citrine-010 — warm contrast for a different look"
  ],
  "description": "Classic teardrop earrings on nickel-free silver hooks. The pearls have a warm pink overtone that comes alive in evening light, especially against an open neckline.",
  "tags": ["classic", "wedding", "bridal", "office", "gift_milestone_birthday"],
  "vibes": ["elegant", "timeless", "soft_feminine"]
}
```

### Operational angle

- ~15 minutes per item × 50 items ≈ 12 hours of focused content work for a real shop
- Recommended workflow: questionnaire template in Notion / Google Sheets → script converts to `catalog.json`
- This is the single highest-leverage thing a shop can do to make the bot actually useful

---

## For Telegram-shop owners (RU/UA)

**Хочеш такий бот для свого магазину?**

Бот говорить українською / російською / English і:

- Відповідає 24/7 на типові питання (наявність, доставка, поради)
- Не вигадує товари — відповідає тільки з твого каталогу
- Передає тобі складні питання + логує те що не зміг відповісти, щоб ти бачив куди покращити каталог
- Адмін-команди `/stats` (за 7 днів) і `/missed` (останні 20 невирішених)

**Setup:** $200 одноразово (підключаю до твого магазину, налаштовую, деплою на Vercel — твоя infra, твій акаунт) + $50/міс підтримка (моніторинг, оновлення, нові товари в каталог).

**Опційно:** $200–300 — content audit + переписування описів товарів за rich-schema форматом вище. Найкраща інвестиція в якість бота — описи рулять, не код.

**Контакт:** [@mahtalaran](https://t.me/mahtalaran) у Telegram.

---

## Project status & honest notes

- This is a **portfolio implementation** with a mock catalog of 15 stone-jewelry items. For a real shop, replace `bot/data/catalog.json` and re-run `seed_supabase.py`.
- The mock shop "Murmure" doesn't sell anything — DMs to the bot are stored in `murmure.messages` for analysis only.
- Security boundary: the only thing protecting `/api/index` from the open internet is the `secret_token` header. Don't commit `WEBHOOK_SECRET` or any of the Supabase / Gemini / Telegram tokens.

## License

MIT
