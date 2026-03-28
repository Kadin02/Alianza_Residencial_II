def require_admin(user):
    if user.role != "ADMIN":
        raise Exception("No autorizado")