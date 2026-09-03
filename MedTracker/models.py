from django.db import models
from django.forms import ModelForm
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.conf import settings
from django.contrib.auth.models import User,AbstractUser,BaseUserManager
from django.utils.translation import gettext_lazy as _
import random
from datetime import date
from cities_light.models import *
from django.utils import timezone


#carehome model 
class CareHome(models.Model):
    name = models.CharField(max_length=100)
    location = models.ForeignKey(City, on_delete=models.SET_NULL, null=True,  related_name='carehomes')
    manager = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, related_name='managed_carehomes')

    

class InvitationCode(models.Model):
    code = models.CharField(max_length=10, unique=True)
    carehome = models.ForeignKey(CareHome, on_delete=models.CASCADE, related_name='invitation_codes')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_invitations')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='used_invitation')
    used_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def generate_unique_code(cls):
        #generates a unique, 8 letter long alphanumeric code
        import random
        import string
        
        while True:
            # Generate an 8-character alphanumeric code
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            # Makes sure code is unique and doesnt already exist.
            if not cls.objects.filter(code=code).exists():
                return code
    
    def mark_as_used(self, user):
        #Marks a code as used
        from django.utils import timezone
        
        self.is_used = True
        self.used_by = user
        self.used_at = timezone.now()
        self.save()



#defines the resident group model, associated with a colour and a carehome
class ResidentGroup(models.Model):
    name = models.CharField(max_length=100)
    carehome = models.ForeignKey(CareHome, on_delete=models.CASCADE, related_name='resident_groups')
    colour = models.CharField(max_length=7, default='#FF0000')  

    

#User models
class Manager(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    carehome = models.ForeignKey(CareHome, on_delete=models.CASCADE, related_name='managers', null=True, blank=True)

class CarerPermissions(models.Model):
    can_edit_residents = models.BooleanField(default=False)
    can_edit_medications = models.BooleanField(default=False)
    can_view_inventory = models.BooleanField(default=False)
    can_adjust_stock = models.BooleanField(default=False)
    carer = models.OneToOneField('Carer', on_delete=models.CASCADE, related_name='permissions')

    def __str__(self):
        return f"Permissions for {self.carer.user.username}"

#Carer iser model, created after a carer successfully signs up, one-to-one realtion with a Django-User.
class Carer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    carehome = models.ForeignKey(CareHome, on_delete=models.CASCADE, related_name='carers')
    resident_group = models.ForeignKey(ResidentGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='carers')
    access_end_date = models.DateTimeField(null=True, blank=True)
    indefinite_access = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            CarerPermissions.objects.create(carer=self)
    
    #used to check if the carer has access to the carehome
    #if the carer has indefinite access, returns true
    #additonally, if the access end date is more than the current date, returns true
    #otherwise returns false
    @property
    def has_valid_access(self):
        if self.indefinite_access:
            return True
        if self.access_end_date and timezone.now() < self.access_end_date:
            return True
        return False

#This model is used to store the information of the residents in the carehome.
#It contains the name, photo, conditions, carehome, group, date of birth, allergies and room number.
class Resident(models.Model):
    name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='resident_photos/', null=True, blank=True, default='resident_photos/default.png')
    conditions = models.TextField(blank=True)
    carehome = models.ForeignKey(CareHome, on_delete=models.CASCADE, related_name='residents')
    group = models.ForeignKey(ResidentGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='residents')
    date_of_birth = models.DateField(null=True, blank=True)
    allergies = models.TextField(blank=True, help_text="List any known allergies")
    room_number = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return self.name

    #used to calculate the age of the resident using the current date and the date of birth
    @property
    def calculate_age(self):
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None
 




#Medication models


#medication model, takes in name, description, nhs_id, stock and carehome
#the carehome is set to the carehome that the medication belongs to,
class Medication(models.Model):
    name = models.CharField(max_length=100)
    nhs_id = models.CharField(max_length=50, default=None)
    carehome = models.ForeignKey(CareHome, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

#Stores a variant of a carehomes stored medication.
class MedicationInventoryItem(models.Model):
    medication = models.ForeignKey(Medication, on_delete=models.CASCADE, related_name='inventory_items')
    dosage = models.CharField(max_length=100)  # e.g., "500mg"
    form = models.CharField(max_length=100, blank=True)  # e.g., "tablet", "capsule", "liquid"
    stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=10)  # Threshold for reordering
    
    class Meta:
        unique_together = ['medication', 'dosage', 'form']
        
    def __str__(self):
        return f"{self.medication.name} {self.dosage} {self.form} - Stock: {self.stock}"
    
    def is_low_stock(self):
        return self.stock <= self.reorder_level


#medication schedule model, takes in resident, medication, dosage, frequency and is_active
#the is_active is a boolean to check if the schedule is active
class MedicationSchedule(models.Model):
    ROUTE_CHOICES = [
        ('oral', 'Oral'),
        ('topical', 'Topical'),
        ('injection', 'Injection'),
        ('inhaled', 'Inhaled'),
        ('other', 'Other'),
    ]

    resident = models.ForeignKey(Resident, on_delete=models.CASCADE)
    medication = models.ForeignKey(Medication, on_delete=models.CASCADE)
    inventory_item = models.ForeignKey(MedicationInventoryItem, on_delete=models.CASCADE, default=None)
    frequency = models.CharField(max_length=100)    
    route = models.CharField(max_length=20, choices=ROUTE_CHOICES, default='oral')
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.resident.name} - {self.inventory_item} - {self.frequency} times daily"
    
    @property
    def dosage(self):
        return self.inventory_item.dosage


#medication time model, records every instance/time in a daily schedule were medicaiton needs to me dispensed.
class MedicationTime(models.Model):
    schedule = models.ForeignKey(MedicationSchedule, on_delete=models.CASCADE, related_name='times')
    time = models.TimeField()




#medication log model
#It records the time the medication was given, the carer who gave it and any 
#used to keep track of medication transactions.
#contains the method called when generating a mar chart.
class MedicationLog(models.Model):
    schedule = models.ForeignKey(MedicationSchedule, on_delete=models.CASCADE)
    scheduled_time = models.ForeignKey(MedicationTime, on_delete=models.CASCADE)
    given_at = models.DateTimeField(auto_now_add=True)
    given_by = models.ForeignKey(Carer, on_delete=models.CASCADE)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-given_at']

    @classmethod
    def generate_mar_chart(cls, resident, start_date, output_path):
        from .utils.mar_generator import MARGenerator
        
        generator = MARGenerator(resident, start_date)
        generator.generate_mar_chart(output_path)
