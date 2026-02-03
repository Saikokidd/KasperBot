"""
Inline клавиатуры (кнопки в сообщениях)
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config.constants import QUICK_ERROR_BUTTONS
from database.models import db
from typing import List, Dict


def get_telephony_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру выбора телефонии (динамическая из БД)

    Returns:
        InlineKeyboardMarkup с кнопками телефоний
    """
    telephonies = db.get_all_telephonies()

    # Если нет телефоний в БД, показываем старые (совместимость)
    if not telephonies:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("BMW", callback_data="tel_bmw")],
                [InlineKeyboardButton("Звонари", callback_data="tel_zvon")],
            ]
        )

    # Создаём кнопки из БД
    buttons = []
    for tel in telephonies:
        buttons.append(
            [InlineKeyboardButton(tel["name"], callback_data=f"tel_{tel['code']}")]
        )

    return InlineKeyboardMarkup(buttons)


def get_role_choice_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру выбора роли для админа

    Returns:
        InlineKeyboardMarkup с кнопками выбора роли
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👨‍💼 Войти как Менеджер", callback_data="role_manager"
                )
            ],
            [InlineKeyboardButton("👑 Войти как Админ", callback_data="role_admin")],
        ]
    )


def get_support_keyboard(user_id: int, tel_code: str) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру с кнопками для саппорта (только для белых телефоний)

    Args:
        user_id: ID пользователя
        tel_code: Код телефонии

    Returns:
        InlineKeyboardMarkup с кнопками саппорта или None для чёрных
    """
    # Проверяем тип телефонии из БД
    tel = db.get_telephony_by_code(tel_code)

    # Если нет в БД, проверяем старые
    if not tel:
        if tel_code != "bmw":
            return None
    else:
        # Если чёрная телефония - без кнопок
        if tel["type"] == "black":
            return None

    # Белая телефония - показываем кнопки
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Исправлено", callback_data=f"fix_{user_id}_{tel_code}"
                ),
                InlineKeyboardButton(
                    "⏱ 2-3 мин", callback_data=f"wait_{user_id}_{tel_code}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚠️ Неверный формат", callback_data=f"wrong_{user_id}_{tel_code}"
                ),
                InlineKeyboardButton(
                    "✅ Сим ворк", callback_data=f"sim_{user_id}_{tel_code}"
                ),
            ],
        ]
    )


# ===== НОВЫЕ КЛАВИАТУРЫ ДЛЯ УПРАВЛЕНИЯ =====


def get_management_menu() -> InlineKeyboardMarkup:
    """Главное меню управления ботом"""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👥 Менеджеры", callback_data="mgmt_managers")],
            [InlineKeyboardButton("📞 Телефонии", callback_data="mgmt_telephonies")],
            [
                InlineKeyboardButton(
                    "⚡️ Быстрые ошибки", callback_data="mgmt_quick_errors"
                )
            ],
            [InlineKeyboardButton("📢 Рассылка", callback_data="mgmt_broadcast")],
        ]
    )


def get_telephony_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа телефонии"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⚪️ Белая (с кнопками саппорта)", callback_data="tel_type_white"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚫️ Чёрная (без кнопок)", callback_data="tel_type_black"
                )
            ],
        ]
    )


# ✅ НОВАЯ ФУНКЦИЯ: Клавиатура быстрых ошибок BMW
def get_quick_errors_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру быстрых ошибок BMW (2 колонки)

    Returns:
        InlineKeyboardMarkup с 10 кнопками ошибок + изменить SIP
    """
    buttons = [
        # Первый ряд
        [
            InlineKeyboardButton(QUICK_ERROR_BUTTONS["1"], callback_data="qerr_1"),
            InlineKeyboardButton(QUICK_ERROR_BUTTONS["2"], callback_data="qerr_2"),
        ],
        # Второй ряд
        [
            InlineKeyboardButton(QUICK_ERROR_BUTTONS["3"], callback_data="qerr_3"),
            InlineKeyboardButton(QUICK_ERROR_BUTTONS["4"], callback_data="qerr_4"),
        ],
        # Третий ряд
        [
            InlineKeyboardButton(QUICK_ERROR_BUTTONS["5"], callback_data="qerr_5"),
            InlineKeyboardButton(QUICK_ERROR_BUTTONS["6"], callback_data="qerr_6"),
        ],
        # Четвёртый ряд
        [
            InlineKeyboardButton(QUICK_ERROR_BUTTONS["7"], callback_data="qerr_7"),
            InlineKeyboardButton(QUICK_ERROR_BUTTONS["8"], callback_data="qerr_8"),
        ],
        # Пятый ряд
        [
            InlineKeyboardButton(QUICK_ERROR_BUTTONS["9"], callback_data="qerr_9"),
            InlineKeyboardButton(QUICK_ERROR_BUTTONS["10"], callback_data="qerr_10"),
        ],
        # Шестой ряд - изменить SIP
        [InlineKeyboardButton("⚙️ Изменить SIP", callback_data="change_sip")],
    ]

    return InlineKeyboardMarkup(buttons)


def get_quick_errors_management_keyboard(
    telephonies: List[Dict],
) -> InlineKeyboardMarkup:
    """
    Клавиатура управления быстрыми ошибками

    Args:
        telephonies: Список белых телефоний со статусом

    Returns:
        InlineKeyboardMarkup с переключателями
    """
    buttons = []

    for tel in telephonies:
        # Иконка статуса
        if tel["enabled"]:
            if tel["quick_errors_enabled"]:
                icon = "✅"
            else:
                icon = "❌"
        else:
            icon = "⚠️"  # Телефония отключена

        # Текст кнопки
        if not tel["enabled"]:
            button_text = f"{icon} {tel['name']} (отключена)"
            callback = "noop"  # Не делать ничего
        else:
            button_text = f"{icon} {tel['name']}"
            callback = f"toggle_qe_{tel['code']}"

        buttons.append([InlineKeyboardButton(button_text, callback_data=callback)])

    # Дополнительные кнопки
    buttons.append([InlineKeyboardButton("ℹ️ Информация", callback_data="qe_info")])
    buttons.append([InlineKeyboardButton("« Назад", callback_data="mgmt_menu")])

    return InlineKeyboardMarkup(buttons)
