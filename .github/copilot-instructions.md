# Copilot Instructions for error_bot

**TL;DR**: Telegram bot managing error reports for telephony services (BMW, Звонари). Built with `python-telegram-bot` 20.7 + SQLite. Three roles (manager, admin, pult) with strict access control. **Critical**: all Google Sheets calls must use `GoogleSheetsServiceWithFallback` for resilience; validate ALL user inputs with `InputValidator`; never clear user role in context.

---

## Architecture Overview

### Core Components

1. **main.py** - Entry point. Registers handlers in priority groups (-1: commands, 0: callbacks, 1+: messages) with rate-limiting middleware
2. **handlers/** (11 modules)
   - `commands.py` - /start, /health
   - `callbacks.py` - Button callbacks (role/telephony selection)
   - `messages.py` - Text messages (filters by role/state)
   - `management.py` - Admin workflows (managers, telephonies, broadcasts, quick errors) using ConversationHandler
   - `analytics.py` - Statistics queries (4 stat types × 2 views = 8 endpoints)
   - `quick_errors.py` - Fast error dispatch (SIP input → error code selection)
   - `errors.py` - Global error handler
   - `health.py` - Bot health checks
   - `telephony_handler.py` - Unified telephony selection (DRY pattern)
   - `menu.py` - Menu navigation

3. **services/** (13 services)
   - `google_sheets_fallback.py` ⭐ - **USE THIS** (wraps API with graceful cache fallback)
   - `google_sheets_service.py` - Direct API calls (never call directly)
   - `google_sheets_cache.py` - Disk cache for resilience
   - `base_stats_service.py`, `managers_stats_service.py` - Sheet automation
   - `quick_error_service.py`, `broadcast_service.py` - Business operations
   - `analytics_service.py`, `stats_service.py` - Data aggregation
   - `user_service.py`, `scheduler_service.py` - Utilities

4. **database/models.py** - SQLite wrapper with ~40 CRUD methods

5. **config/**
   - `settings.py` - Env var validation (BOT_TOKEN, ADMIN_ID, group IDs, Google credentials)
   - `constants.py` - Hardcoded values (timeouts, menus, quick error codes, Pavlograd manager list NAME_MAP)
   - `validators.py` - `InputValidator` class with 6 validation methods (user_id, SIP, tel_code, description, group_id, username)

6. **utils/**
   - `state.py` - User session state management with 10-min timeouts for quick errors
   - `logger.py` - RotatingFileHandler (10MB×5 files) with color support
   - `rate_limiter.py` - Middleware protection (5 msg/10s, 50 cb/60s)

### Data Flow
```
User sends message
        ↓
[Rate Limit Middleware checks user]
        ↓
Handler (CommandHandler/MessageHandler/CallbackQueryHandler)
        ↓
[Role check + input validation]
        ↓
Service layer (business logic)
        ↓
[GoogleSheetsServiceWithFallback if API needed]
        ↓
Database.models (persist data)
        ↓
Send response (keyboard + text)
```

---

## Critical Patterns

### 1. ⭐ Google Sheets with Fallback (MANDATORY)
**DO NOT call `google_sheets_service.py` directly.** Always use:
```python
from services.google_sheets_fallback import GoogleSheetsServiceWithFallback
service = GoogleSheetsServiceWithFallback()
data = await service.fetch_manager_stats("Sheet1!A1:C10")
# Returns cached data if API fails → bot continues working
```
This ensures bot operates even when Google API is down.

### 2. Input Validation (ALL user inputs)
**Validate EVERYTHING from users** using [config/validators.py](config/validators.py):
```python
from config.validators import InputValidator

is_valid, error_msg = InputValidator.validate_user_id(user_id)
if not is_valid:
    await update.message.reply_text(f"❌ {error_msg}")
    return

is_valid, error_msg = InputValidator.validate_sip_number(sip)
if not is_valid:
    await update.message.reply_text(f"❌ {error_msg}")
    return WAITING_SIP  # ConversationHandler state
```
Covers: user_id (positive 4-digit+), SIP (digits only, max 50 chars), telephony codes, descriptions, group IDs, usernames.

### 3. Role-Based Access Control
- **Roles** stored in `context.user_data["role"]` on `/start`
- **NEVER cleared** during conversation (persists entire session)
- Always check role before sensitive ops:
```python
from utils.state import get_user_role

async def admin_command(update, context):
    role = get_user_role(context)
    if role != "admin":
        await update.message.reply_text("❌ Только администраторы")
        return
    # Continue...
```
Roles: "manager", "admin", "pult" (lowercase). Admin ID from `settings.ADMIN_ID`, pult IDs from `settings.PULT_IDS`.

### 4. ConversationHandler Multi-Step Workflows
Used in [handlers/management.py](handlers/management.py) for forms (add manager, add telephony, broadcasts, quick errors):
```python
# State constants at module level
WAITING_MANAGER_ID, WAITING_TEL_NAME = range(2)

async def add_manager_start(update, context):
    """Entry point callback"""
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("Enter manager ID:")
    return WAITING_MANAGER_ID

async def add_manager_process(update, context):
    """Handles text response"""
    user_id = int(update.message.text)  # Already validated
    db.add_manager(user_id, ...)
    return ConversationHandler.END  # Exit conversation

# In main.py:
ConversationHandler(
    entry_points=[CallbackQueryHandler(add_manager_start, pattern="^mgmt_add_manager$")],
    states={WAITING_MANAGER_ID: [MessageHandler(filters.TEXT, add_manager_process)]},
    fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^cancel$")]
)
```
**Critical**: `context.user_data` persists across states. Always clear sensitive data with `clear_*()` utilities when done:
```python
from utils.state import clear_all_states
clear_all_states(context)  # Clears temporary states (NOT role)
```

### 5. State Timeout for Quick Errors
Quick error workflow has 10-minute timeouts for SIP input:
```python
from utils.state import (
    set_quick_error_sip, get_quick_error_sip, is_quick_error_sip_expired,
    clear_quick_error_state
)

# After user enters SIP
set_quick_error_sip(context, sip, timeout_minutes=10)

# Later, before using SIP
sip = get_quick_error_sip(context)
if not sip or is_quick_error_sip_expired(context):
    await update.message.reply_text("❌ Timeout. Restart with /start")
    clear_quick_error_state(context)
    return
```

### 6. Database Singleton Pattern
Always use context manager:
```python
from database.models import db  # Singleton instance
managers = db.get_managers()  # Automatic connection handling
db.add_manager(user_id, username, first_name, added_by)
```
Never create raw `sqlite3.connect()` calls—see [database/models.py](database/models.py) for all available methods.

### 7. Middleware for Rate Limiting
Already integrated in main.py:
```python
# Automatically checks all updates
# Limits: 5 messages/10s, 50 callbacks/60s per user
# User blocked 1 min if exceeded
# No additional code needed in handlers
```

---

## Project-Specific Conventions

### Naming & Constants
- **Telephony codes**: "bmw", "zvon" (lowercase, from `config.constants.TEL_CODES`)
- **Role names**: "manager", "admin", "pult" (lowercase)
- **SIP validation**: Digits only, regex `^\d+$`, max 50 chars (see `config.constants.SIP_PATTERN`)
- **Timeouts**: TEL_CHOICE_TIMEOUT=10 min, QUICK_ERROR_*=10 min
- **Timezone**: Europe/Kiev (UTC+2) for timestamps

### Error Messages
All user-facing errors use emoji prefixes:
```python
logger.error("❌ Critical error message")       # Red X
logger.warning("⚠️ Non-critical warning")      # Orange warning
logger.info("✅ Success message")              # Green checkmark
logger.debug("📞 Detailed trace")              # Phone emoji for tracing
```

### Callback Data Patterns (in fallback_callback)
```python
known_patterns = [
    'mgmt_',      # management operations
    'role_',      # role selection
    'tel_',       # telephony selection
    'fix_',       # error fixing
    'stats_',     # statistics
    'qerr_',      # quick errors
    'dash_',      # dashboard
    'select_tel_' # telephony selection
]
```

### State Clearing Pattern
```python
# BEFORE showing new menu
from utils.state import clear_all_states
clear_all_states(context)  # Clears tel_choice, support_mode (preserves role)

# AFTER ConversationHandler completes
return ConversationHandler.END
```

---

## Testing

### Framework & Structure
- **pytest** with fixtures in [tests/conftest.py](tests/conftest.py)
- **Run**: `pytest tests/ -v`
- **Config**: [pytest.ini](pytest.ini) with markers (unit, validators, state, integration)
- **Coverage**: 54+ unit tests (all passing)

### Mock Fixtures
```python
@pytest.fixture
def mock_context():
    """Mock telegram.ext.ContextTypes"""
    context = MagicMock()
    context.user_data = {}  # User session storage
    return context

@pytest.fixture
def mock_update():
    """Mock telegram Update"""
    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.username = "test_user"
    return update
```

### Example Test
```python
def test_validate_user_id():
    from config.validators import InputValidator
    
    # Valid cases
    is_valid, error = InputValidator.validate_user_id("123456789")
    assert is_valid == True
    assert error is None
    
    # Invalid cases
    is_valid, error = InputValidator.validate_user_id("-5")
    assert is_valid == False
    assert "positive" in error.lower()
```

---

## Common Workflows

### 1. Adding a New Admin Command
```python
# 1. Create handler in handlers/commands.py or handlers/management.py
async def my_command(update, context):
    from utils.state import get_user_role
    
    role = get_user_role(context)
    if role != "admin":
        await update.message.reply_text("❌ Only admins can use this")
        return
    
    # Validate inputs
    from config.validators import InputValidator
    is_valid, error = InputValidator.validate_user_id(user_id)
    if not is_valid:
        await update.message.reply_text(error)
        return
    
    # Call service
    from services.broadcast_service import BroadcastService
    result = BroadcastService().send_broadcast(...)
    
    # Respond
    await update.message.reply_text(f"✅ Done: {result}")

# 2. Register in main.py
app.add_handler(CommandHandler("mycommand", my_command), group=-1)
```

### 2. Querying Statistics
```python
# Use appropriate service (never direct Google Sheets)
from services.analytics_service import AnalyticsService

service = AnalyticsService()
stats = service.get_general_stats()  # Uses GoogleSheetsServiceWithFallback internally

# Format response
message = "📊 Statistics:\n"
for key, value in stats.items():
    message += f"  {key}: {value}\n"
await update.message.reply_text(message)
```

### 3. Multi-Step Error Entry Form
```python
# handlers/quick_errors.py - Entry point
async def handle_quick_error_callback(update, context):
    await update.callback_query.answer()
    
    # Store chosen telephony
    context.user_data["chosen_tel"] = "bmw"
    context.user_data["chosen_tel_code"] = "bmw"
    
    # Ask for SIP
    await update.message.reply_text("Enter SIP number:")
    return WAITING_SIP

# Next state - process SIP input
async def handle_sip_input_for_quick_error(update, context):
    from config.validators import InputValidator
    from utils.state import set_quick_error_sip
    
    sip = update.message.text
    is_valid, error = InputValidator.validate_sip_number(sip)
    if not is_valid:
        await update.message.reply_text(f"❌ {error}")
        return WAITING_SIP
    
    set_quick_error_sip(context, sip)
    
    # Show error code buttons
    from keyboards.inline import get_quick_errors_keyboard
    keyboard = get_quick_errors_keyboard()
    await update.message.reply_text(
        "Select error code:",
        reply_markup=keyboard
    )
    return WAITING_ERROR_CODE
```

---

## Integration Points & Dependencies

### External Services
- **Telegram API**: python-telegram-bot v20.7 (Application, handlers, keyboards)
- **Google Sheets**: gspread + oauth2client (read manager stats via API)
- **Google Apps Script**: Custom webhook (env var `GOOGLE_APPS_SCRIPT_URL`)
- **SQLite**: Local database `bot_data.db`

### Critical Environment Variables
```env
BOT_TOKEN=123456:ABC...                           # Telegram bot token
ADMIN_ID=987654321                                # Admin user ID
BMW_GROUP_ID=-100123456                           # BMW group ID (must start with -)
ZVONARI_GROUP_ID=-100654321                       # Zvonari group ID
PULT_IDS=111,222,333                             # Comma-separated pult user IDs
GOOGLE_SHEETS_ID=abc123...                        # Stats spreadsheet ID
BASE_STATS_SHEET_ID=def456...                     # Base stats sheet ID
GOOGLE_APPS_SCRIPT_URL=https://script.google...   # Webhook for stats sync
GOOGLE_CREDENTIALS_FILE=google_credentials.json   # Service account JSON
```

### Cross-Module Communication
```
user_service → database.models       (check user roles in SQLite)
handlers → services                  (delegate business logic)
analytics_service → GoogleSheetsFallback  (fetch external stats)
management.py → database.models      (add/remove managers, telephonies)
rate_limiter → all handlers          (enforce limits)
```

---

## 10 Critical Issues & Solutions

### ❌ 1. Calling google_sheets_service Directly
```python
# ❌ WRONG - bot crashes if API fails
from services.google_sheets_service import google_sheets
stats = google_sheets.get_stats()

# ✅ CORRECT - uses cache when API fails
from services.google_sheets_fallback import GoogleSheetsServiceWithFallback
service = GoogleSheetsServiceWithFallback()
stats = await service.fetch_manager_stats(...)  # Returns cache on failure
```

### ❌ 2. Missing query.answer()
```python
# ❌ WRONG - user sees spinning loader forever
async def my_callback(update, context):
    query = update.callback_query
    await query.message.edit_text("Done")

# ✅ CORRECT
async def my_callback(update, context):
    query = update.callback_query
    await query.answer()  # Close loading indicator
    await query.message.edit_text("Done")
```

### ❌ 3. Skipping Input Validation
```python
# ❌ WRONG - KeyError, type errors, negative IDs crash bot
user_id = int(update.message.text)
db.add_manager(user_id, ...)

# ✅ CORRECT
from config.validators import InputValidator
is_valid, error = InputValidator.validate_user_id(update.message.text)
if not is_valid:
    await update.message.reply_text(f"❌ {error}")
    return WAITING_ID
db.add_manager(int(update.message.text), ...)
```

### ❌ 4. Clearing User Role Mid-Conversation
```python
# ❌ WRONG - role lost, bot shows wrong menu
context.user_data["role"] = "admin"  # Direct assignment
clear_all_states(context)  # Also clears role

# ✅ CORRECT - role persists
from utils.state import get_user_role
role = get_user_role(context)  # "manager", "admin", or "pult"
clear_all_states(context)  # Clears temporary states ONLY
```

### ❌ 5. SIP/Error Codes Live Forever
```python
# ❌ WRONG - user enters SIP, waits 30 min, data stale
sip = context.user_data.get("quick_error_sip")
# No timeout check

# ✅ CORRECT - 10-min timeout enforced
from utils.state import get_quick_error_sip, is_quick_error_sip_expired
sip = get_quick_error_sip(context)
if not sip or is_quick_error_sip_expired(context):
    await update.message.reply_text("❌ Timeout. Restart.")
    return
```

### ❌ 6. Unhandled Callback Patterns
```python
# ❌ WRONG - user clicks button → "unknown callback" warning
# New callback pattern not registered

# ✅ CORRECT - add pattern to fallback_callback
known_patterns = [
    'mgmt_', 'role_', 'tel_', 'stats_',
    'my_new_pattern_'  # ← Add here
]
```

### ❌ 7. No Error Handling for Telegram API Calls
```python
# ❌ WRONG - group unavailable, message too long → crash
await context.bot.send_message(group_id, message)

# ✅ CORRECT
import telegram.error
try:
    await context.bot.send_message(
        chat_id=group_id,
        text=message[:4096],  # Telegram limit
        parse_mode="HTML"
    )
except telegram.error.ChatNotFound:
    logger.error(f"❌ Chat {group_id} not found")
except Exception as e:
    logger.error(f"❌ Message send failed: {e}")
```

### ❌ 8. ConversationHandler State Not Cleared
```python
# ❌ WRONG - user in form, presses /start → old state active
async def start_command(update, context):
    await update.message.reply_text("Select role:")
    # State from previous conversation still active

# ✅ CORRECT
async def start_command(update, context):
    from utils.state import clear_all_states
    clear_all_states(context)  # Clean state before showing menu
    await update.message.reply_text("Select role:")
```

### ❌ 9. Using Raw sqlite3 Instead of Database Class
```python
# ❌ WRONG - no connection management
import sqlite3
conn = sqlite3.connect("bot_data.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM managers")

# ✅ CORRECT - uses context manager internally
from database.models import db
managers = db.get_managers()
```

### ❌ 10. Not Using Rate Limiter
```python
# ❌ WRONG - user spams 100 messages → flood in group
async def message_handler(update, context):
    # No rate limit check

# ✅ CORRECT - middleware auto-checks (or manual check)
from utils.rate_limiter import rate_limiter
allowed, msg = rate_limiter.check_message_rate(update.effective_user.id)
if not allowed:
    await update.message.reply_text(msg)
    return
```

---

## Completed Improvements (December 2025)

✅ **Input Validation** (`config/validators.py`) - 6 methods, 50+ unit tests  
✅ **Rate Limiting** (`utils/rate_limiter.py`) - 5 msg/10s, 50 cb/60s  
✅ **Google Sheets Fallback** (`services/google_sheets_fallback.py`) - resilient with disk cache  
✅ **State Timeouts** (`utils/state.py`) - 10-min SIP/error code timeout  
✅ **Unit Tests** (54 tests) - validators, state management, all passing  
✅ **Code Refactoring** - `broadcast_service.py`, `quick_error_service.py`, `telephony_handler.py`  
✅ **Logger** - RotatingFileHandler with color support

**Project Quality: 8.5/10** | **Test Coverage: 20%+** | **Critical Bugs Fixed: 1**

---

## Quick Reference Files

| Purpose | File |
|---------|------|
| Entry point | [main.py](main.py#L1) |
| Config validation | [config/settings.py](config/settings.py) |
| Input validators | [config/validators.py](config/validators.py) |
| Database schema | [database/models.py](database/models.py#L1-L100) |
| State management | [utils/state.py](utils/state.py) |
| Google Sheets (resilient) | [services/google_sheets_fallback.py](services/google_sheets_fallback.py) |
| Test fixtures | [tests/conftest.py](tests/conftest.py) |
| Multi-step forms | [handlers/management.py](handlers/management.py#L1-L50) |

---

*Last updated: January 1, 2026 | Quality: 8.5/10 | Test Coverage: 20%+ | Status: Ready for AI agents*
