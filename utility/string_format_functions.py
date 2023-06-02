import datetime


def get_time_since_delta(delta: datetime.timedelta) -> str:
    now = datetime.datetime.utcnow()
    timestamp = int((now + delta).timestamp())
    return f"<t:{timestamp}:R>"