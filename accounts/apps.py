from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        def get_display_name(self):
            try:
                return self.profile.nickname
            except Exception:
                return self.get_username()

        User.get_display_name = get_display_name
