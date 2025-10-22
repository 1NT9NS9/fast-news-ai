# Bot Reply Behavior Plan

## Objective
Ensure the Telegram bot responds with assistant-authored confirmations instead of forwarding or mirroring the raw text typed by the user during keyboard-driven workflows (channel management, folder management, and news delivery preferences).

## Plan
1. **Map current keyboard flows**
   - Trace the conversation states in `bot/handlers/manage.py` (e.g., `handle_add_channel_input`, `handle_remove_channel_input`, `handle_time_interval_input`, `handle_news_count_input`, `handle_create_folder_input`) and any supporting flows in `bot/handlers/buttons.py` that consume `update.message.text`.
   - Verify how `_reply_text` and the messenger service format outgoing messages, confirming where the user’s original text is being reused or forwarded.
   - Document each scenario that needs a bespoke assistant response.
2. **Define assistant reply templates**
   - Draft concise confirmation/error messages for: adding/removing channels, setting the news time window, updating the number of news items, and creating/deleting folders.
   - Align tone and language with existing bot copy (Russian UI strings) and decide whether to centralize the phrases (e.g., helper constants or functions) or keep them inline.
3. **Implement handler updates**
   - Replace any echo/forward logic with the new reply strings in the identified handlers.
   - Ensure the messenger wrapper does not implicitly forward user messages (adjust if necessary).
   - Handle edge cases (validation failures, duplicates, limits) so all responses originate from the bot’s wording.
4. **Add or update tests**
   - Extend existing handler/unit tests or add new ones to assert that the bot’s replies differ from the user input and match the expected templates.
   - Cover both success and failure paths where user-provided text previously leaked back to the chat.
5. **Manual verification and follow-up**
   - Run targeted manual checks (or integration tests if available) to confirm the conversational UX now surfaces bot-authored replies.
   - Update any relevant documentation or change logs to describe the behavioral fix.

