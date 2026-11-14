from django import forms

from accounts.models import Profile


class ProfileEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False, disabled=True)

    class Meta:
        model = Profile
        fields = (
            "phone",
            "organization",
            "profile_picture",
            "specialization",
            "years_experience",
            "bio",
        )
        widgets = {
            "profile_picture": forms.ClearableFileInput(
                attrs={"accept": "image/*", "class": "profile-picture-input"}
            ),
            "years_experience": forms.NumberInput(attrs={"min": 0}),
            "bio": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name
        self.fields["email"].initial = user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.email = self.cleaned_data["email"]
        if commit:
            self.user.save()
            profile.save()
        return profile
