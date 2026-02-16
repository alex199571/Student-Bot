from app.models.user import User


async def set_pending_action(user: User, action: str) -> None:
    user.pending_action = action


async def get_pending_action(user: User) -> str | None:
    return user.pending_action


async def clear_pending_action(user: User) -> None:
    user.pending_action = None
