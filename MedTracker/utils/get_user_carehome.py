#reusable function to get the carehome of a user
def get_user_carehome(user):
    if hasattr(user, 'manager'):
        return user.manager.carehome
    elif hasattr(user, 'carer'):
        return user.carer.carehome
    else:
        return None