from django.contrib.auth import get_user_model
from django.utils.text import slugify
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class MenyaSocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        email = (data.get("email") or user.email or "").strip().lower()
        full_name = (
            data.get("name")
            or " ".join(
                part
                for part in (
                    data.get("first_name"),
                    data.get("last_name"),
                )
                if part
            )
            or (email.split("@", 1)[0] if email else "MENYA Learner")
        )
        user.email = email
        user.full_name = full_name.strip()[:150]
        user.phone_number = ""
        user.is_email_verified = any(
            address.verified for address in sociallogin.email_addresses
        )

        if not user.username:
            username_base = slugify(email.split("@", 1)[0])[:40] or "learner"
            username = username_base
            suffix = 1
            user_model = get_user_model()
            while user_model.objects.filter(username=username).exists():
                suffix_text = str(suffix)
                username = f"{username_base[:50 - len(suffix_text)]}{suffix_text}"
                suffix += 1
            user.username = username
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        if any(address.verified for address in sociallogin.email_addresses):
            user.is_email_verified = True
            user.save(update_fields=("is_email_verified",))
        return user
