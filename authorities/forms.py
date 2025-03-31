from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import GovernmentOfficial, ComplaintUpdate, Complaint

class OfficialSignUpForm(UserCreationForm):
    ward_number = forms.CharField(
        max_length=50, 
        required=True, 
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Enter the ward number you are responsible for.'
    )
    department = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Optional: Your department or designation'
    )
    contact_number = forms.CharField(
        max_length=15, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Optional: Your contact number'
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email')
        
        if commit:
            user.save()
            # Create GovernmentOfficial profile
            GovernmentOfficial.objects.create(
                user=user,
                ward_number=self.cleaned_data['ward_number'],
                department=self.cleaned_data.get('department'),
                contact_number=self.cleaned_data.get('contact_number')
            )
        return user

class ComplaintUpdateForm(forms.ModelForm):
    class Meta:
        model = ComplaintUpdate
        fields = ['status', 'update_description', 'proof_image']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'update_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'proof_image': forms.FileInput(attrs={'class': 'form-control'})
        }
        labels = {
            'status': 'Update Complaint Status',
            'update_description': 'Additional Notes (Optional)',
            'proof_image': 'Proof Image (Required)'
        }

    def clean_proof_image(self):
        proof_image = self.cleaned_data.get('proof_image')
        if not proof_image:
            raise forms.ValidationError("Proof image is required when updating complaint status.")
        return proof_image

class OfficialProfileUpdateForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    ward_number = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    department = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    contact_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = GovernmentOfficial
        fields = ['ward_number', 'department', 'contact_number']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['username'].initial = user.username
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        user_id = self.instance.user.id
        if User.objects.filter(username=username).exclude(id=user_id).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        user_id = self.instance.user.id
        if User.objects.filter(email=email).exclude(id=user_id).exists():
            raise forms.ValidationError("This email is already registered.")
        return email