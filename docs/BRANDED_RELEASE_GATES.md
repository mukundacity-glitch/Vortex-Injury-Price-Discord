# Branded Discord 2026/27 — verified opt-in release gate

**Production unchanged.** This is a draft-only change. Do not merge or enable branded mode before the prerequisites below pass. Existing injury, price, webhook test, original cached state and Discord history stay in place.

## Scheduled jobs — no time changes
- `.github/workflows/injury-news.yml` still runs at `7,22,37,52 * * * *` UTC (every 15 minutes). The script now runs as `python -m src.injury_bot` for optional package imports, and original monitor logic, snapshots and X drafts remain intact.
- `.github/workflows/price-change.yml` still runs at `45 23 * * *` Europe/London. The old predictor/fallback path and its original design remain present and unchanged unless branded opt-in is explicitly enabled.
- `.github/workflows/discord-test.yml` remains a manual message test. PR validation reuses the **same existing workflow** without actually sending webhooks. No extra job schedules were created.

## Actual original blue slide
The user-supplied original blue FPL VORTEX master is `59698.png`, Git blob SHA-1 `b0d890a529ad7416a142d3cfbbadfc800eb26bd0`. The existing Telegram repository background file differs at Git blob `01d87ec98cf4d8d8ccff4814f4ddf5b3c339725e`. Strict Discord rendering must obtain the exact original from `FPL_BRAND_MASTER_PATH` or from the canonical Telegram repo **after the user-provided master is installed there**. The configured `FPL_BRAND_MASTER_BLOB_SHA` must match the pinned expected SHA and the actual image bytes or publication is blocked; no generic replacement.

## What strict opt-in adds
- `FPL_BRANDED_POSTS_ENABLED=true` uses real, current official FPL player/club identities, portraits/crests, prices, minutes and ownership; separate compact player rows/cards with five actual future FPL GW slots, opponent (H/A), 1-5 FDR, blank/double handling and concise MONITOR advice. Missing verified metrics are omitted; unverified xPts are never shown.
- Telegram and Discord **public** handles must both be confirmed and installed as `FPL_TELEGRAM_HANDLE` and `FPL_DISCORD_HANDLE`. They are not bot token/chat ID/webhook identifiers. Both appear in the preserved footer.
- A multi-page story (up to 10 PNGs in ONE Discord message) uses `?wait=true` and keeps a durable message ID in `data/branded_discord_deliveries.json`. Repeated semantic content IDs skip duplicate deliveries. The cached state is preserved by the existing workflows. Network failure after Discord acceptance but before receipt is a real idempotency limitation; never claim perfect exactly-once external delivery.
- For price-change forecasts, the strict path accepts only authentic LiveFPL predictor progress inputs; if unavailable, hold rather than present the old transfer-volume heuristic as independently verified.
- Provider/source details, full data audit and model assumptions stay in internal execution logs, not user-facing slide. Concise caption has four hashtags. No `N/A` placeholders or fabricated injury quotes.

## Remaining release blockers
1. Install exact user-supplied master in canonical repository and set digest.
2. Verify Telegram/Discord **public** handles and authorized Discord staging webhook.
3. Run actual end-to-end test with both Telegram and Discord for identical graphics and copy-ready caption; verify no duplicate on retry and post IDs in persistent state.
4. Confirm real mobile readability and full all-task parity; merging without verified cross-repo dedup can cause duplicate stories if both old and new publishers stay on.
5. Only after all checks, choose one authoritative publisher per news topic, switch off redundant schedules *without deleting any bots, files, archives or messages*, and retain rollback toggles.

None of these manual/live publishing gates were executed by this draft PR. The existing production mode is unchanged.

## User clarification: approved slide exists in GitHub
On 2026-11-02 the user explicitly confirmed that the existing `Telegram-Bot/assets/references/brand_background.png` in the `upgrade/unified-telegram-discord-news` branch is their desired slide. Its verified Git blob SHA-1 is `01d87ec98cf4d8d8ccff4814f4ddf5b3c339725e` (172062 bytes). The other in-chat PNG file (`59698.png`, blob `b0d890a529ad7416a142d3cfbbadfc800eb26bd0`) is a distinct binary. **Use the user-confirmed GitHub master without asking for a re-upload.** Renderer fingerprints were updated to match the confirmed GitHub master. Prior guidance in this document requiring re-upload of `59698.png` is superseded. Actual Telegram+Discord delivery/staging configuration and end-to-end duplicate safety remain separate release gates.

## Production release / direct-post status — 2026-11-02

PR #3 was merged to `main` as `3b06e45d57ac2b4d27dd5271f1478449849638f9`. The SAME existing injury and price workflows retain their original schedule expressions, their manual choices are now direct `monitor` / `post` without preview/test/force posting overrides, and `FPL_BRANDED_POSTS_ENABLED` defaults to true unless explicitly overridden by an Actions variable. Exact blue master SHA remains pinned. One-time direct release runs were triggered without creating a new scheduled task: injury run `41488564608` completed successfully with monitoring (no new change to post); price run `41488573891` completed successfully but declined to send a second unchanged prediction, preventing a duplicate. Both ran against the existing Discord repository's webhook secret.

The integrated Telegram+Discord posting of the four migrated ChatGPT task editions is separately blocked because `DISCORD_WEBHOOK_URL` was absent in the **Telegram-Bot repository**, despite the existing separate Discord repo posting working. That secret must be securely configured in Telegram-Bot. Do not imply that all former ChatGPT editions were already posted on both channels. Keep original jobs, chat tasks and history until live joined receipts are verified.


## Current audit correction — 2026-11-02

The latest explicit user instruction selects Library asset libfile_0947818b02d88191b357fe10080957ce, Git blob b0d890a529ad7416a142d3cfbbadfc800eb26bd0 (194358 bytes). This supersedes the earlier GitHub-asset confirmation above. Both renderer pins now require the original Library bytes. No new schedule or public test post is authorized by this correction.
