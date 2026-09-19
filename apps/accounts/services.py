from django.contrib.auth.password_validation import validate_password

from .models import User


def create_user(user_data):
    data = user_data.copy()
    password = data.pop("password", None)
    validate_password(password)
    return User.objects.create_user(password=password, **data)


def get_user_by_id(user_id):
    return User.objects.filter(id=user_id).first()


def update_user(user, user_data):
    for field, value in user_data.items():
        if field != "password" and hasattr(user, field):
            setattr(user, field, value)
    user.save()
    return user
