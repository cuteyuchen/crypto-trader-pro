"""
Flask 基础认证模块
"""
import base64
from functools import wraps
from flask import request, Response, current_app


def require_auth(username: str, password: str):
    """装饰器：要求 HTTP Basic Auth"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not (auth.username == username and auth.password == password):
                return authenticate()
            return f(*args, **kwargs)
        return decorated
    return decorator


def authenticate():
    """返回 401 挑战"""
    return Response(
        '需要认证\n',
        401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )
