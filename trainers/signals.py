from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from allauth.socialaccount.signals import social_account_added
from .models import Trainer


@receiver(post_save, sender=User)
def create_trainer_profile(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'trainer'):
        Trainer.objects.create(
            user=instance,
            full_name=instance.get_full_name() or instance.username,
            organization="",
            phone="",
        )


@receiver(social_account_added)
def create_trainer_on_social_signup(request, sociallogin, **kwargs):
    user = sociallogin.user
    if not hasattr(user, 'trainer'):
        Trainer.objects.create(
            user=user,
            full_name=user.get_full_name() or user.username or user.email,
            organization="",
            phone="",
        )
