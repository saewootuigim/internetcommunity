def auth_panel(request):
    """Expose one-shot login/signup errors stored in the session to templates.

    Values are popped so they only appear once (after the redirect that follows
    a failed login/signup submission).
    """
    context = {}
    login_error = request.session.pop('login_error', None)
    signup_errors = request.session.pop('signup_errors', None)
    if login_error:
        context['login_error'] = login_error
        context['show_login'] = True
    if signup_errors:
        context['signup_errors'] = signup_errors
        context['show_signup'] = True
    return context
