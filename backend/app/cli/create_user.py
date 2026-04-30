import argparse
import asyncio
from getpass import getpass

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import User


async def create_user(args: argparse.Namespace) -> None:
    password = args.password or getpass("Password: ")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == args.username))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(username=args.username)
            session.add(user)

        user.password_hash = hash_password(password)
        user.display_name = args.display_name
        user.role = args.role
        user.is_active = True
        await session.commit()
        print(f"User ready: {user.username} ({user.role})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a local admin/operator user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password")
    parser.add_argument("--display-name")
    parser.add_argument("--role", choices=["admin", "operator", "viewer"], default="admin")
    args = parser.parse_args()
    asyncio.run(create_user(args))


if __name__ == "__main__":
    main()
