import jwt
import os
from datetime import datetime, timedelta, timezone

def generate_token(user_id, expiry_days=1):
    now = datetime.now(timezone.utc)
    expiry_time = now + timedelta(hours=2)
    payload = {
        'exp': expiry_time,
        'iat': now,
        'sub': str(user_id)
    }
    print("Generated Payload:", payload)
    return jwt.encode(
        payload,
        os.getenv('JWT_SECRET'),
        algorithm='HS256'
    )
