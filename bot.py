import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import requests
import json
import asyncio

# Конфигурация
TELEGRAM_TOKEN = "7758024840:AAEKdhT1S_aXOkBiy4kPExYyp5fj-RalI2Q"  # Замените на ваш токен
API_BASE_URL = "http://localhost:8000"  # URL вашего FastAPI сервера
ADMIN_IDS = [1038789342]  # Замените на ваш Telegram ID

# Определение состояний FSM (Finite State Machine)
class ExchangeForm(StatesGroup):
    CHOOSE_ACTION = State()
    ADD_EXCHANGE_NAME = State()
    ADD_EXCHANGE_PRICE = State()
    ADD_EXCHANGE_VOLUME = State()
    ADD_EXCHANGE_DEPTH_PLUS = State()
    ADD_EXCHANGE_DEPTH_MINUS = State()
    ADD_EXCHANGE_VOLUME_PERCENTAGE = State()
    ADD_EXCHANGE_ICON = State()
    UPDATE_EXCHANGE_CHOOSE = State()
    UPDATE_EXCHANGE_FIELD = State()
    UPDATE_EXCHANGE_VALUE = State()

# Поля для обновления
UPDATE_FIELDS = {
    "price": "Цена",
    "volume24h": "Объем 24ч",
    "plusTwoPercentDepth": "Глубина +2%",
    "minusTwoPercentDepth": "Глубина -2%",
    "volumePercentage": "Процент объема",
    "icon": "Иконка"
}

# Временное хранилище данных для добавления биржи
exchange_data = {}

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Функция проверки прав администратора
async def check_admin(message: types.Message) -> bool:
    """Проверка прав администратора"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.reply("У вас нет прав для использования этого бота.")
        return False
    return True

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    """Начало работы с ботом"""
    if not await check_admin(message):
        return

    keyboard = [
        [InlineKeyboardButton(text="Добавить биржу", callback_data="add")],
        [InlineKeyboardButton(text="Обновить биржу", callback_data="update")],
        [InlineKeyboardButton(text="Удалить биржу", callback_data="delete")],
        [InlineKeyboardButton(text="Список бирж", callback_data="list")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.reply("Выберите действие:", reply_markup=reply_markup)
    await state.set_state(ExchangeForm.CHOOSE_ACTION)

# Обработчик для получения списка бирж
@dp.callback_query(F.data == "list")
async def list_exchanges(callback: types.CallbackQuery) -> None:
    """Получение списка бирж"""
    await callback.answer()

    try:
        response = requests.get(f"{API_BASE_URL}/api/custom-exchanges")
        if response.status_code == 200:
            exchanges = response.json()['data']
            if not exchanges:
                await callback.message.reply("Список пользовательских бирж пуст.")
                return

            message = "Список пользовательских бирж:\n\n"
            for exchange in exchanges:
                message += f"🏦 {exchange['exchange']}\n"
                message += f"💰 Цена: {exchange['price']}\n"
                message += f"📊 Объем 24ч: {exchange['volume24h']}\n"
                message += f"📈 Глубина +2%: {exchange['plusTwoPercentDepth']}\n"
                message += f"📉 Глубина -2%: {exchange['minusTwoPercentDepth']}\n"
                message += "➖➖➖➖➖➖➖➖➖➖\n"
            
            await callback.message.reply(message)
        else:
            await callback.message.reply("Ошибка при получении списка бирж.")
    except Exception as e:
        await callback.message.reply(f"Произошла ошибка: {str(e)}")

# Обработчики для добавления биржи
@dp.callback_query(F.data == "add")
async def add_exchange_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Начало процесса добавления биржи"""
    await callback.answer()
    
    exchange_data.clear()
    await callback.message.reply("Введите название биржи:")
    await state.set_state(ExchangeForm.ADD_EXCHANGE_NAME)

@dp.message(ExchangeForm.ADD_EXCHANGE_NAME)
async def add_exchange_name(message: types.Message, state: FSMContext) -> None:
    """Обработка названия биржи"""
    exchange_data['exchange'] = message.text
    await message.reply("Введите текущую цену LTC (например: 92.45):")
    await state.set_state(ExchangeForm.ADD_EXCHANGE_PRICE)

@dp.message(ExchangeForm.ADD_EXCHANGE_PRICE)
async def add_exchange_price(message: types.Message, state: FSMContext) -> None:
    """Обработка цены"""
    try:
        exchange_data['price'] = float(message.text)
        await message.reply("Введите объем торгов за 24 часа в USD (например: 1000000):")
        await state.set_state(ExchangeForm.ADD_EXCHANGE_VOLUME)
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число. Попробуйте снова:")
        # Остаемся в том же состоянии

@dp.message(ExchangeForm.ADD_EXCHANGE_VOLUME)
async def add_exchange_volume(message: types.Message, state: FSMContext) -> None:
    """Обработка объема торгов"""
    try:
        exchange_data['volume24h'] = float(message.text)
        await message.reply("Введите глубину +2% в USD (например: 500000):")
        await state.set_state(ExchangeForm.ADD_EXCHANGE_DEPTH_PLUS)
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число. Попробуйте снова:")
        # Остаемся в том же состоянии

@dp.message(ExchangeForm.ADD_EXCHANGE_DEPTH_PLUS)
async def add_exchange_depth_plus(message: types.Message, state: FSMContext) -> None:
    """Обработка глубины +2%"""
    try:
        exchange_data['plusTwoPercentDepth'] = float(message.text)
        await message.reply("Введите глубину -2% в USD (например: 500000):")
        await state.set_state(ExchangeForm.ADD_EXCHANGE_DEPTH_MINUS)
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число. Попробуйте снова:")
        # Остаемся в том же состоянии

@dp.message(ExchangeForm.ADD_EXCHANGE_DEPTH_MINUS)
async def add_exchange_depth_minus(message: types.Message, state: FSMContext) -> None:
    """Обработка глубины -2%"""
    try:
        exchange_data['minusTwoPercentDepth'] = float(message.text)
        await message.reply("Введите процент объема (например: 1.5):")
        await state.set_state(ExchangeForm.ADD_EXCHANGE_VOLUME_PERCENTAGE)
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число. Попробуйте снова:")
        # Остаемся в том же состоянии

@dp.message(ExchangeForm.ADD_EXCHANGE_VOLUME_PERCENTAGE)
async def add_exchange_volume_percentage(message: types.Message, state: FSMContext) -> None:
    """Обработка процента объема"""
    try:
        exchange_data['volumePercentage'] = float(message.text)
        await message.reply("Введите URL иконки биржи (или отправьте '-' для пропуска):")
        await state.set_state(ExchangeForm.ADD_EXCHANGE_ICON)
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число. Попробуйте снова:")
        # Остаемся в том же состоянии

@dp.message(ExchangeForm.ADD_EXCHANGE_ICON)
async def add_exchange_icon(message: types.Message, state: FSMContext) -> None:
    """Обработка URL иконки"""
    icon_url = message.text
    if icon_url != '-':
        exchange_data['icon'] = icon_url
    await finish_adding(message, state)

async def finish_adding(message: types.Message, state: FSMContext) -> None:
    """Завершение добавления биржи"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/custom-exchanges",
            json=exchange_data
        )
        if response.status_code == 200:
            await message.reply("Биржа успешно добавлена!")
        else:
            await message.reply(f"Ошибка при добавлении биржи: {response.text}")
    except Exception as e:
        await message.reply(f"Произошла ошибка: {str(e)}")
    
    await state.clear()

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    """Отмена текущей операции"""
    await message.reply("Операция отменена.")
    await state.clear()

# Обработчики для обновления биржи
@dp.callback_query(F.data == "update")
async def update_exchange_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Начало процесса обновления биржи"""
    await callback.answer()

    try:
        response = requests.get(f"{API_BASE_URL}/api/custom-exchanges")
        if response.status_code == 200:
            exchanges = response.json()['data']
            if not exchanges:
                await callback.message.reply("Нет бирж для обновления.")
                return

            keyboard = []
            for exchange in exchanges:
                keyboard.append([InlineKeyboardButton(
                    text=exchange['exchange'],
                    callback_data=f"update_{exchange['exchange']}"
                )])

            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await callback.message.reply(
                "Выберите биржу для обновления:",
                reply_markup=reply_markup
            )
            await state.set_state(ExchangeForm.UPDATE_EXCHANGE_CHOOSE)
    except Exception as e:
        await callback.message.reply(f"Произошла ошибка: {str(e)}")

@dp.callback_query(lambda c: c.data and c.data.startswith("update_"))
async def update_exchange_choose(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Выбор биржи для обновления"""
    await callback.answer()
    
    exchange_name = callback.data.replace("update_", "")
    await state.update_data(current_exchange=exchange_name)

    keyboard = []
    for field_key, field_name in UPDATE_FIELDS.items():
        keyboard.append([InlineKeyboardButton(
            text=field_name, 
            callback_data=f"field_{field_key}"
        )])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.reply(
        f"Выберите поле для обновления биржи {exchange_name}:",
        reply_markup=reply_markup
    )
    await state.set_state(ExchangeForm.UPDATE_EXCHANGE_FIELD)

@dp.callback_query(lambda c: c.data and c.data.startswith("field_"))
async def update_exchange_field(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Выбор поля для обновления"""
    await callback.answer()
    
    field = callback.data.replace("field_", "")
    await state.update_data(update_field=field)
    
    await callback.message.reply(f"Введите новое значение для поля {UPDATE_FIELDS[field]}:")
    await state.set_state(ExchangeForm.UPDATE_EXCHANGE_VALUE)

@dp.message(ExchangeForm.UPDATE_EXCHANGE_VALUE)
async def update_exchange_value(message: types.Message, state: FSMContext) -> None:
    """Обновление значения поля"""
    try:
        user_data = await state.get_data()
        field = user_data['update_field']
        exchange_name = user_data['current_exchange']
        
        # Преобразование значения в нужный тип
        value = message.text
        if field in ['price', 'volume24h', 'plusTwoPercentDepth', 'minusTwoPercentDepth', 'volumePercentage']:
            value = float(value)
        
        # Отправка запроса на обновление
        response = requests.patch(
            f"{API_BASE_URL}/api/custom-exchanges/{exchange_name}",
            json={field: value}
        )
        
        if response.status_code == 200:
            await message.reply(f"Биржа {exchange_name} успешно обновлена!")
        else:
            await message.reply(f"Ошибка при обновлении биржи: {response.text}")
    
    except ValueError:
        await message.reply("Пожалуйста, введите корректное значение. Попробуйте снова:")
        return
    except Exception as e:
        await message.reply(f"Произошла ошибка: {str(e)}")
    
    await state.clear()

# Обработчики для удаления биржи
@dp.callback_query(F.data == "delete")
async def delete_exchange_start(callback: types.CallbackQuery) -> None:
    """Начало процесса удаления биржи"""
    await callback.answer()

    try:
        response = requests.get(f"{API_BASE_URL}/api/custom-exchanges")
        if response.status_code == 200:
            exchanges = response.json()['data']
            if not exchanges:
                await callback.message.reply("Нет бирж для удаления.")
                return

            keyboard = []
            for exchange in exchanges:
                keyboard.append([InlineKeyboardButton(
                    text=f"❌ {exchange['exchange']}",
                    callback_data=f"delete_{exchange['exchange']}"
                )])

            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await callback.message.reply(
                "Выберите биржу для удаления:",
                reply_markup=reply_markup
            )
    except Exception as e:
        await callback.message.reply(f"Произошла ошибка: {str(e)}")

@dp.callback_query(lambda c: c.data and c.data.startswith("delete_"))
async def delete_exchange_confirm(callback: types.CallbackQuery) -> None:
    """Подтверждение удаления биржи"""
    await callback.answer()

    exchange_name = callback.data.replace("delete_", "")
    try:
        response = requests.delete(f"{API_BASE_URL}/api/custom-exchanges/{exchange_name}")
        if response.status_code == 200:
            await callback.message.reply(f"Биржа {exchange_name} успешно удалена!")
        else:
            await callback.message.reply(f"Ошибка при удалении биржи: {response.text}")
    except Exception as e:
        await callback.message.reply(f"Произошла ошибка: {str(e)}")

# Функция запуска бота
async def main() -> None:
    """Запуск бота"""
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 
