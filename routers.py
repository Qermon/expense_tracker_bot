from sqlalchemy.orm import Session
from datetime import datetime
from models import User, Expense
from io import BytesIO
from sqlalchemy import func
import pandas as pd

from parse_exchange_rate import usd_exchange_rate


def create_user(db: Session, telegram_id: int, username: str):
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if db_user is None:
        new_user = User(telegram_id=telegram_id, username=username)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    return db_user


def post_expense(db: Session, telegram_id: int, data: dict):
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not db_user:
        return "User не знайдено"

    new_expense = Expense(
        user_id=db_user.id,
        name=data['name'],
        date=data['date'],
        uah=float(data['amount']),
        usd=data.get('amount_usd'),
    )

    db.add(new_expense)
    db.commit()


def get_expenses(db: Session, telegram_id: int, start_date_str: str, end_date_str: str):
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not db_user:
        return "User не знайдено"

    try:
        start_date = datetime.strptime(start_date_str, "%d.%m.%Y")
        end_date = datetime.strptime(end_date_str, "%d.%m.%Y")
    except ValueError:
        return "Невірний формат дат. Використовуйте формат dd.mm.YYYY."

    expenses = db.query(Expense).filter(
        Expense.user_id == db_user.id,
        Expense.date >= start_date,
        Expense.date <= end_date
    ).all()

    if not expenses:
        return "Витрати за вказаний період не знайдено."

    total_amount_uah = db.query(func.sum(Expense.uah)).filter(
        Expense.user_id == db_user.id,
        Expense.date >= start_date,
        Expense.date <= end_date
    ).scalar() or 0

    total_amount_usd = db.query(func.sum(Expense.usd)).filter(
        Expense.user_id == db_user.id,
        Expense.date >= start_date,
        Expense.date <= end_date
    ).scalar() or 0

    data = [{
        "ID": exp.id,
        "Назва": exp.name,
        "Дата": exp.date.strftime('%d.%m.%Y'),
        "Сума (грн)": exp.uah,
        "Сума (USD)": exp.usd if exp.usd else "None"
    } for exp in expenses]

    df = pd.DataFrame(data)

    df.loc[len(df)] = ["", "Загальна сума витрат (грн)", "", total_amount_uah, ""]
    df.loc[len(df)] = ["", "Загальна сума витрат (USD)", "", "", total_amount_usd]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Звіт витрат")
    output.seek(0)

    return output


def get_expenses_all(db: Session, telegram_id: int):
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not db_user:
        return "User не знайдено"

    expenses = db.query(Expense).filter(Expense.user_id == db_user.id).all()
    if not expenses:
        return "У вас поки немає витрат."

    total_amount_uah = db.query(func.sum(Expense.uah)).filter(Expense.user_id == db_user.id).scalar() or 0
    total_amount_usd = db.query(func.sum(Expense.usd)).filter(Expense.user_id == db_user.id).scalar() or 0

    data = [{
        "ID": exp.id,
        "Назва": exp.name,
        "Дата": exp.date.strftime('%d.%m.%Y'),
        "Сума (грн)": exp.uah,
        "Сума (USD)": exp.usd if exp.usd else "None"
    } for exp in expenses]

    df = pd.DataFrame(data)

    df.loc[len(df)] = ["", "Загальна сума витрат (грн)", "", total_amount_uah, ""]
    df.loc[len(df)] = ["", "Загальна сума витрат (USD)", "", "", total_amount_usd]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Звіт витрат")
    output.seek(0)

    return output


def delete_expense(db: Session, telegram_id: int, expense_id: int):
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not db_user:
        return False

    expense_to_delete = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == db_user.id).first()

    if not expense_to_delete:
        return False
    db.delete(expense_to_delete)
    db.commit()

    return True


def get_expense_by_id(db: Session, telegram_id: int, expense_id: int):
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not db_user:
        return "User не знайдено"

    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == db_user.id).first()
    if not expense:
        return "Витрата не знайдена"

    return {
        "ID": expense.id,
        "Назва": expense.name,
        "Дата": expense.date.strftime('%d.%m.%Y'),
        "Сума (грн)": expense.uah,
        "Сума (USD)": expense.usd if expense.usd else "None"
    }


def update_expense(db: Session, telegram_id: int, expense_id: int, new_name: str, new_amount: float):
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not db_user:
        return "User не знайдено"

    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == db_user.id).first()
    if not expense:
        return "Витрата не знайдена"

    expense.name = new_name
    expense.uah = new_amount

    usd_rate = usd_exchange_rate()
    expense.usd = round(new_amount / usd_rate, 2) if usd_rate else None

    db.commit()

    return "Витрата успішно оновлена"
