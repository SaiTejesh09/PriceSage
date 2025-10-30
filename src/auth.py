from __future__ import annotations

import getpass
import re
from typing import Optional

import bcrypt

from models import UserAccount
from storage import PriceStorage


EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def prompt_yes_no(message: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        choice = input(f"{message} {suffix} ").strip().lower()
        if not choice:
            return default
        if choice in {"y", "yes"}:
            return True
        if choice in {"n", "no"}:
            return False
        print("Please answer with 'y' or 'n'.")


def prompt_email(prompt: str, default: Optional[str] = None) -> str:
    while True:
        value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
        if not value and default:
            value = default
        if not value:
            print("Email cannot be empty.")
            continue
        if not EMAIL_REGEX.match(value):
            print("Please enter a valid email address.")
            continue
        return value


def prompt_password(prompt: str = "Password: ") -> str:
    while True:
        pwd = getpass.getpass(prompt)
        if len(pwd) < 6:
            print("Please choose a password with at least 6 characters.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if pwd != confirm:
            print("Passwords do not match. Try again.")
            continue
        return pwd


def prompt_login_password(prompt: str = "Password: ") -> str:
    return getpass.getpass(prompt)


def prompt_signup(storage: PriceStorage) -> UserAccount:
    print("=== Create a new PriceSage account ===")
    while True:
        email = prompt_email("Account email")
        if storage.get_user_by_email(email):
            print("An account with this email already exists. Please choose another.")
        else:
            break

    password = prompt_password()
    notify_email = prompt_email("Recipient email for alerts", default=email)

    smtp_server = input("SMTP server [smtp.gmail.com]: ").strip() or "smtp.gmail.com"
    smtp_port_raw = input("SMTP port [587]: ").strip()
    smtp_port = int(smtp_port_raw) if smtp_port_raw else 587
    smtp_username = input("SMTP username (leave blank to use account email): ").strip() or email
    smtp_password = getpass.getpass("SMTP password (app password recommended): ")
    smtp_use_tls = prompt_yes_no("Use TLS?", default=True)

    password_hash = hash_password(password)
    user = storage.create_user(
        email=email,
        password_hash=password_hash,
        notify_email=notify_email,
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        smtp_username=smtp_username,
        smtp_password=smtp_password or None,
        smtp_use_tls=smtp_use_tls,
    )
    print(f"Account created for {user.email}.")
    return user


def prompt_login(storage: PriceStorage) -> Optional[UserAccount]:
    print("=== Sign in to PriceSage ===")
    for _ in range(5):
        email = prompt_email("Account email")
        hashed = storage.get_password_hash(email)
        if not hashed:
            print("No account found with that email.")
            if prompt_yes_no("Do you want to try again?", default=True):
                continue
            return None
        password = prompt_login_password()
        if verify_password(password, hashed):
            user = storage.get_user_by_email(email)
            if user:
                print(f"Welcome back, {user.email}!")
                return user
            print("Unexpected error retrieving your account. Please try again.")
            return None
        print("Incorrect password.")
        if not prompt_yes_no("Try again?", default=True):
            return None
    print("Too many failed attempts.")
    return None


def authenticate_user(storage: PriceStorage) -> UserAccount:
    existing = storage.list_users()
    if not existing:
        return prompt_signup(storage)

    while True:
        choice = input("Do you want to [l]ogin or [s]ign up a new account? [l/s]: ").strip().lower()
        if choice in {"s", "signup"}:
            return prompt_signup(storage)
        if choice in {"l", "login", ""}:
            user = prompt_login(storage)
            if user:
                return user
        print("Please choose 'l' to login or 's' to sign up.")


def ensure_smtp_settings(storage: PriceStorage, user: UserAccount) -> UserAccount:
    needs_password = not user.smtp_password
    if needs_password or prompt_yes_no("Update email notification settings?", default=False):
        notify_email = prompt_email("Recipient email", default=user.notify_email)
        smtp_server = input(f"SMTP server [{user.smtp_server}]: ").strip() or user.smtp_server
        smtp_port_raw = input(f"SMTP port [{user.smtp_port}]: ").strip()
        smtp_port = int(smtp_port_raw) if smtp_port_raw else user.smtp_port
        default_username = user.smtp_username or user.email
        smtp_username = (
            input(f"SMTP username [{default_username}]: ").strip() or default_username
        )
        new_password = getpass.getpass(
            "SMTP password (leave blank to keep existing): "
        )
        smtp_password = new_password if new_password else user.smtp_password
        smtp_use_tls = prompt_yes_no("Use TLS?", default=user.smtp_use_tls)
        storage.update_user_smtp(
            user_id=user.id,
            notify_email=notify_email,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            smtp_use_tls=smtp_use_tls,
        )
        refreshed = storage.get_user_by_id(user.id)
        if refreshed:
            user = refreshed
    return user
