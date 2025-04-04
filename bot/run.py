import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import TOKEN
from database import SessionLocal
from parse_exchange_rate import usd_exchange_rate
from routers import create_user, post_expense, get_expenses, get_expenses_all, delete_expense, update_expense, \
    get_expense_by_id

bot = Bot(token=TOKEN)
dp = Dispatcher()


class ExpenseState(StatesGroup):
    name = State()
    date = State()
    amount = State()
    start_date = State()
    end_date = State()
    delete_id = State()
    edit_id = State()
    new_data = State()


menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Додати статтю витрат")],
        [KeyboardButton(text="Отримати звіт витрат")],
        [KeyboardButton(text="Видалити статтю витрат")],
        [KeyboardButton(text="Відредагувати статтю витрат")]
    ],
    resize_keyboard=True
)


@dp.message(CommandStart())
async def cmd_start(message: Message):
    telegram_id = message.from_user.id
    username = message.from_user.username

    db = SessionLocal()
    user = create_user(db, telegram_id, username)
    db.close()

    await message.answer(f"Привіт, {user.username}!\nОберіть дію:", reply_markup=menu_keyboard)


@dp.message(lambda message: message.text == "Додати статтю витрат")
async def add_expense(message: Message, state: FSMContext):
    await message.answer("Введіть назву статті витрат (наприклад, 'Щомісячна сплата за інтернет'):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ExpenseState.name)


@dp.message(ExpenseState.name)
async def expense_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введіть дату у форматі dd.mm.YYYY (наприклад, '19.03.2025'):")
    await state.set_state(ExpenseState.date)


@dp.message(ExpenseState.date)
async def expense_date(message: Message, state: FSMContext):
    date_str = message.text
    if not is_valid_date(date_str):
        await message.answer("Невірний формат дати! Використовуйте формат dd.mm.YYYY.")
        return

    await state.update_data(date=date_str)
    await message.answer("Введіть сумму витрат (наприклад, '1369'): ")
    await state.set_state(ExpenseState.amount)


@dp.message(ExpenseState.amount)
async def expense_amount(message: Message, state: FSMContext):
    amount_str = message.text
    if not amount_str.replace('.', '', 1).isdigit():  # Проверка, что сумма это число
        await message.answer("Сума витрат повинна бути числом! Будь ласка, введіть коректну суму.")
        return

    await state.update_data(amount=amount_str)

    data = await state.get_data()

    expense_name = data['name']
    expense_date = data['date']
    expense_amount = float(data['amount'])

    usd_rate = usd_exchange_rate()

    if usd_rate:
        expense_amount_usd = round(expense_amount / usd_rate, 2)
        data['amount_usd'] = expense_amount_usd
    else:
        data['amount_usd'] = None

    if data['amount_usd']:
        response_text = (
            f"Додано нову статтю витрат:\n"
            f"Назва: {expense_name}\n"
            f"Дата: {expense_date}\n"
            f"Сума: {expense_amount} грн\n"
            f"Сума в доларах: {data['amount_usd']} USD"
        )
    else:
        response_text = (
            f"Додано нову статтю витрат:\n"
            f"Назва: {expense_name}\n"
            f"Дата: {expense_date}\n"
            f"Сума: {expense_amount} грн\n"
            f"Не вдалося отримати курс долара"
        )

    db = SessionLocal()
    post_expense(db, message.from_user.id, data)
    db.close()

    await state.clear()
    await message.answer(response_text, reply_markup=menu_keyboard)
    await message.answer("Оберіть дію:", reply_markup=menu_keyboard)


def is_valid_date(date_str):
    return bool(re.match(r"\d{2}\.\d{2}\.\d{4}", date_str))


@dp.message(lambda message: message.text == "Отримати звіт витрат")
async def get_date(message: Message, state: FSMContext):
    await message.answer(
        "Введіть дату початку періоду (наприклад, '02.02.2025'):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ExpenseState.start_date)


@dp.message(ExpenseState.start_date)
async def start_date(message: Message, state: FSMContext):
    date_str = message.text
    if not is_valid_date(date_str):
        await message.answer("Невірний формат дати! Використовуйте формат dd.mm.YYYY.")
        return

    await state.update_data(start_date=date_str)
    await message.answer("Введіть дату кінця періоду (наприклад, '02.03.2025'):")
    await state.set_state(ExpenseState.end_date)


@dp.message(ExpenseState.end_date)
async def end_date(message: types.Message, state: FSMContext):
    date_str = message.text
    if not is_valid_date(date_str):
        await message.answer("Невірний формат дати! Використовуйте формат dd.mm.YYYY.")
        return

    await state.update_data(end_date=date_str)

    data = await state.get_data()
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    db = SessionLocal()
    report_file = get_expenses(db, message.from_user.id, start_date, end_date)
    db.close()

    if isinstance(report_file, str):
        await message.answer(report_file)
        await state.clear()
        await message.answer("Оберіть дію:", reply_markup=menu_keyboard)
    else:
        report_file.seek(0)
        await message.answer_document(types.BufferedInputFile(report_file.read(), filename="expense_report.xlsx"))
        await message.answer("Звіт витрат за вказаний період:", reply_markup=menu_keyboard)
        await message.answer("Оберіть дію:", reply_markup=menu_keyboard)
        await state.clear()


@dp.message(lambda message: message.text == "Видалити статтю витрат")
async def delete_expense_request(message: Message, state: FSMContext):
    await message.answer("Генеруємо список витрат...", reply_markup=ReplyKeyboardRemove())

    db = SessionLocal()
    report_file = get_expenses_all(db, message.from_user.id)
    db.close()

    if isinstance(report_file, str):
        await message.answer(report_file)
    else:
        report_file.seek(0)
        await message.answer_document(
            types.BufferedInputFile(report_file.read(), filename="expense_report.xlsx")
        )
        await message.answer("Введіть ID статті витрат, яку потрібно видалити:")

        await state.set_state(ExpenseState.delete_id)


@dp.message(ExpenseState.delete_id)
async def delete_expense_confirm(message: Message, state: FSMContext):
    expense_id = message.text.strip()

    if not expense_id.isdigit():
        await message.answer("ID має бути числом! Введіть коректний ID статті витрат:")
        return

    expense_id = int(expense_id)

    db = SessionLocal()
    delete_status = delete_expense(db, message.from_user.id, expense_id)
    db.close()

    if delete_status:
        await message.answer(f"Стаття витрат з ID {expense_id} успішно видалена.")
    else:
        await message.answer(f"Не вдалося знайти статтю витрат з ID {expense_id}. Перевірте введений ID і спробуйте ще раз.")

    await state.clear()
    await message.answer("Оберіть дію:", reply_markup=menu_keyboard)


@dp.message(lambda message: message.text == "Відредагувати статтю витрат")
async def edit_expense_request(message: Message, state: FSMContext):
    await message.answer("Генеруємо список витрат...", reply_markup=ReplyKeyboardRemove())

    db = SessionLocal()
    report_file = get_expenses_all(db, message.from_user.id)
    db.close()

    if isinstance(report_file, str):
        await message.answer(report_file)
    else:
        report_file.seek(0)
        await message.answer_document(
            types.BufferedInputFile(report_file.read(), filename="expense_report.xlsx")
        )
        await message.answer("Введіть ID статті витрат, яку потрібно відредагувати:")

        await state.set_state(ExpenseState.edit_id)


@dp.message(lambda message: message.text == "Відредагувати статтю витрат")
async def edit_expense_request(message: types.Message, state: FSMContext):
    await message.answer("Генеруємо список витрат...", reply_markup=ReplyKeyboardRemove())

    db = SessionLocal()
    report_file = get_expenses_all(db, message.from_user.id)
    db.close()

    if isinstance(report_file, str):
        await message.answer(report_file)
    else:
        report_file.seek(0)
        await message.answer_document(
            types.BufferedInputFile(report_file.read(), filename="expense_report.xlsx")
        )
        await message.answer("Введіть ID статті витрат, яку потрібно відредагувати:")

        await state.set_state(ExpenseState.edit_id)


@dp.message(ExpenseState.edit_id)
async def get_expense_id(message: types.Message, state: FSMContext):
    expense_id = message.text.strip()

    db = SessionLocal()
    expense = get_expense_by_id(db, message.from_user.id, expense_id)
    db.close()

    if expense:
        await state.update_data(expense_id=expense_id)
        await message.answer(
            f"Поточна стаття витрат:\n\n"
            f"Назва: {expense.get('Назва')}\n"
            f"Сума: {expense.get('Сума (грн)')}\n"

            "Введіть нову назву та нову суму через кому (наприклад: Продукти, 5500):"
        )
        await state.set_state(ExpenseState.new_data)
    else:
        await message.answer("Витрата з таким ID не знайдена. Спробуйте ще раз.")


@dp.message(ExpenseState.new_data)
async def update_expense_data(message: types.Message, state: FSMContext):
    try:
        new_data = message.text.strip().split(",")
        if len(new_data) != 2:
            raise ValueError

        new_name = new_data[0].strip()
        new_amount = float(new_data[1].strip())

        if not new_name or new_amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "Неправильний формат. Введіть дані у форматі: Нова назва, Сума (наприклад: Продукти, 5500)")
        return

    data = await state.get_data()
    expense_id = data["expense_id"]

    db = SessionLocal()
    success = update_expense(db, message.from_user.id, expense_id, new_name, new_amount)
    db.close()

    if success:
        await message.answer(
            f"Стаття витрат успішно оновлена:\n\n"
            f"Нова назва: {new_name}\n"
            f"Нова сума: {new_amount} грн\n\n"
            "Ви повернулися в головне меню.",
        )
    else:
        await message.answer("Сталася помилка при оновленні. Спробуйте ще раз.")

    await state.clear()
    await message.answer("Оберіть дію:", reply_markup=menu_keyboard)


async def start_bot():
    logging.info("Telegram Bot працює")
    await dp.start_polling(bot)


async def main():
    logging.basicConfig(level=logging.INFO)
    await start_bot()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Вихід')
