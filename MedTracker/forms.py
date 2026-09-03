from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.forms.fields import EmailField
from django.forms.forms import Form


from django.utils import timezone
from datetime import timedelta
from .models import InvitationCode

from .models import *


#form for generating a invitation code to be used by a carer during signup
class GenerateInvitationCodeForm(forms.Form):
    expiry_days = forms.IntegerField(
        min_value=1, 
        max_value=30, 
        initial=7,
        label="Invitation valid for (days)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    def generate_code(self, carehome, created_by):
        
        # Set expiry date
        expiry_days = self.cleaned_data['expiry_days']
        expires_at = timezone.now() + timedelta(days=expiry_days)
        
        # Generate code
        code = InvitationCode.generate_unique_code()
        
        # Create invitation
        invitation = InvitationCode.objects.create(
            code=code,
            carehome=carehome,
            created_by=created_by,
            expires_at=expires_at
        )
        
        return invitation
    




#User signup forms
#fields: first name, last name, email, password, and password confirmation
#inherits from the Django UserCreationForm
#extends the function of Djangos default form, taking in first name/last name/email
class CustomUserForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your first name'
        })
    )

    last_name = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your last name'
        })
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password'
        })
    )
    
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')




#form for taking in manager signup details, inherits from the custom user form.
#email is set to the username and manager is created in the database.
class ManagerSignUpForm(CustomUserForm):

    #inherits the fields from the custom user form
    class Meta(CustomUserForm.Meta):
        model = User
        

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email.lower()
        if commit:
            user.save()
            Manager.objects.create(user=user)
        return user





#form for taking in carer signup details, inherits from the custom user form. 
# The carehome code is used to check that the carehome exists, before allowing a carer to be created
#data is cleaned, email is set to the username and carer is created in the database.
class CarerSignUpForm(CustomUserForm):
    invitation_code = forms.CharField(
        max_length=10, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your invitation code'
        })
    )

    class Meta(CustomUserForm.Meta):
        model = User

    def clean_invitation_code(self):
        code = self.cleaned_data.get('invitation_code')
        now = timezone.now()
        
        # Check if code exists and is valid
        try:
            invitation = InvitationCode.objects.get(
                code=code,
                is_used=False,
                expires_at__gt=now
            )
        except InvitationCode.DoesNotExist:
            raise forms.ValidationError(
                "Invalid or expired invitation code. Please check and try again."
            )
            
        return code

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email.lower()
        if commit:
            user.save()
            
            # Get the invitation code and its related carehome
            invitation = InvitationCode.objects.get(code=self.cleaned_data['invitation_code'])
            carehome = invitation.carehome
            
            # Create carer object
            Carer.objects.create(user=user, carehome=carehome)
            
            # Mark invitation as used
            invitation.mark_as_used(user)
            
        return user
    



#carehome setup form

#form for setting up a carehome, takes in name and location
#location data from django-cities-light plugin, query search filter is used to only show cities in the UK
class CareHomeSetupForm(forms.ModelForm):
    location = forms.ModelChoiceField(queryset=City.objects.filter(country__code2='GB'))
    class Meta:
        model = CareHome
        fields = ['name', 'location']



#resident form, takes in name, photo, age and conditions. The photo and group are optional
class ResidentForm(forms.ModelForm):
    class Meta:
        model = Resident
        fields = ['name', 'photo', 'date_of_birth', 'conditions', 'allergies', 'room_number', 'group']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', }),
            'conditions': forms.Textarea(attrs={'rows': 3, 'placeholder': 'List any medical conditions'}),
            'allergies': forms.Textarea(attrs={'rows': 3, 'placeholder': 'List any allergies'}),
            'room_number': forms.TextInput(attrs={'placeholder': 'Enter room number'}),
        }
    

    def __init__(self, *args, **kwargs):
        carehome = kwargs.pop('carehome', None)

        super().__init__(*args, **kwargs)

        self.fields['photo'].required = False 
        self.fields['group'].required = False
        self.fields['allergies'].required = False
        self.fields['conditions'].required = False
        self.fields['room_number'].required = False
        
        if carehome:
            self.fields['group'].queryset = ResidentGroup.objects.filter(carehome=carehome)
            self.fields['group'].label_from_instance = lambda obj: obj.name
            
        self.fields['date_of_birth'].input_formats = ['%Y-%m-%d']
            

#form for creating a resident group, takes in name and colour, the colour is a hex code 
#and is displayed as a colour picker in the webpage.
class ResidentGroupForm(forms.ModelForm):
    class Meta:
        model = ResidentGroup
        fields = ['name', 'colour']
        widgets = {
            'colour': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
                'title': 'Choose group colour'
            })
        }

#defines the fields for a medication variant in the database
class MedicationInventoryItemForm(forms.ModelForm):
    class Meta:
        model = MedicationInventoryItem
        fields = ['dosage', 'form', 'stock', 'reorder_level']
        widgets = {
            'dosage': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '500mg'}),
            'form': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'tablet'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'value': '10'}),
        }

#form for creating a medication schedule, takes in medication, dosage and frequency
#the frequency is a number between 1 and 6, reffering to each instance a medicine should be dispensed a day
#the route (way resident takes the medicaiton) is a dropdown field, with the predefined options
#  being oral, topical, inhalation and injection
class MedicationScheduleForm(forms.ModelForm):
    class Meta:
        model = MedicationSchedule
        fields = ['medication', 'inventory_item', 'frequency', 'route']
        widgets = {
            'frequency': forms.NumberInput(attrs={'min': 1, 'max': 6}),
            'route': forms.Select(attrs={'class': 'form-control'})
        }
    
    def __init__(self, *args, **kwargs):
        # Extract carehome
        carehome = kwargs.pop('carehome', None)
        super().__init__(*args, **kwargs)
        
        # Set medication choices to those in the carehome
        if carehome:
            self.fields['medication'].queryset = Medication.objects.filter(carehome=carehome)
        
        # Start with empty inventory item queryset
        self.fields['inventory_item'].queryset = MedicationInventoryItem.objects.none()
        
        # If form has medication field and is POST.
        if self.is_bound and 'medication' in self.data:
            try:
                medication_id = int(self.data.get('medication'))
                # Set the inventory item based on the selected medication
                self.fields['inventory_item'].queryset = MedicationInventoryItem.objects.filter(
                    medication_id=medication_id
                )
            except (ValueError, TypeError):
                pass
                
        # If editing an existing instance with a medication
        elif self.instance.pk and self.instance.medication:
            self.fields['inventory_item'].queryset = MedicationInventoryItem.objects.filter(
                medication=self.instance.medication
            )

#carer permissions set as booleans
#displayed as checkboxes on the webpage
class CarerPermissionsForm(forms.ModelForm):
    class Meta:
        model = CarerPermissions
        fields = [
            'can_edit_residents',
            'can_edit_medications',
            'can_view_inventory',
            'can_adjust_stock'
        ]
        labels = {
            'can_edit_residents': 'Can edit resident information',
            'can_edit_medications': 'Can edit medication schedules',
            'can_view_inventory': 'Can view medication inventory',
            'can_adjust_stock': 'Can adjust medication stock levels'
        }

class CarerAccessForm(forms.ModelForm):
    access_duration = forms.ChoiceField(
        choices=[
            ('24h', '24 Hours'),
            ('48h', '48 Hours'),
            ('1w', '1 Week'),
            ('2w', '2 Weeks'),
            ('1m', '1 Month'),
            ('indefinite', 'Indefinite')
        ],
        widget=forms.RadioSelect,
        required=True
    )
    
    class Meta:
        model = Carer
        fields = ['indefinite_access']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['indefinite_access'].widget = forms.HiddenInput()
        
        # Initialize the access_duration field based on current settings
        instance = kwargs.get('instance')
        if instance:
            if instance.indefinite_access:
                self.fields['access_duration'].initial = 'indefinite'
            elif instance.access_end_date:
                # Calculate remaining time and select closest option
                remaining = instance.access_end_date - timezone.now()
                days = remaining.days
                if days <= 1:
                    self.fields['access_duration'].initial = '24h'
                elif days <= 2:
                    self.fields['access_duration'].initial = '48h'
                elif days <= 7:
                    self.fields['access_duration'].initial = '1w'
                elif days <= 14:
                    self.fields['access_duration'].initial = '2w'
                else:
                    self.fields['access_duration'].initial = '1m'
    
    def save(self, commit=True):
        carer = super().save(commit=False)
        access_duration = self.cleaned_data.get('access_duration')
        
        if access_duration == 'indefinite':
            carer.indefinite_access = True
            carer.access_end_date = None
        else:
            carer.indefinite_access = False
            now = timezone.now()
            
            if access_duration == '24h':
                carer.access_end_date = now + timedelta(hours=24)
            elif access_duration == '48h':
                carer.access_end_date = now + timedelta(hours=48)
            elif access_duration == '1w':
                carer.access_end_date = now + timedelta(weeks=1)
            elif access_duration == '2w':
                carer.access_end_date = now + timedelta(weeks=2)
            elif access_duration == '1m':
                carer.access_end_date = now + timedelta(days=30)
        
        if commit:
            carer.save()
        return carer