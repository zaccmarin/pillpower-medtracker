from django.shortcuts import render, redirect, \
    get_object_or_404
from django.db import IntegrityError
from django.views.decorators.http import require_http_methods
from django.contrib.auth import login, authenticate, logout
from django.http import HttpResponse, JsonResponse, request, FileResponse
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm,AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from datetime import datetime, date, timedelta
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
import logging
from django.db.models import Prefetch
from MedTracker.decoratorscustom import carer_permission_required
from django.template.loader import render_to_string
from django.template import RequestContext
from django.shortcuts import render
import os
from io import BytesIO



from .utils.get_medicines import get_medicine
from .utils.get_medicine_names import get_medicine_names
from .utils.get_upcoming_medications import get_upcoming_medications, calculate_urgency
from .utils.get_user_carehome import get_user_carehome
from .forms import *
from .models import *




#Basic website views, 404, logout, index, about us

def custom_404(request, exception=None):
    return render(request, 'staticpages/404.html', status=404)

#logout, sends user back to landing page
def logout_view(request):
    logout(request)
    return redirect('/')

#this is the landing page
def index(request):
    template = 'staticpages/index.html'
    return render(request, template)

#Little about us page to describe what the website is for
def aboutus(request):
    template = 'staticpages/aboutcompany.html'
    return render(request, template)




#after a manager has been created, they create a carehome within the database
@login_required
@ensure_csrf_cookie
def setup_carehome(request):
    #inital check for the user type, only accepts managers
    user = request.user
    try:
        manager = user.manager
    except Manager.DoesNotExist:
        return redirect('/')

    try:
        carehome = manager.carehome
    except CareHome.DoesNotExist:
        carehome = None

   
    #form to create a carehome, checks if the form is valid, generates a unique code for the carehome 
    # and saves the carehome to the database.
    if request.method == 'POST':
        form = CareHomeSetupForm(request.POST)
        if form.is_valid():
            carehome = form.save(commit=False)
            
            carehome.manager = user
            carehome.save()
            manager.carehome = carehome
            manager.save()
            return redirect('manager_dashboard')
    else:
        form = CareHomeSetupForm()

    return render(request, 'dashboards/setup_carehome.html',{'form': form})


#view for generating the one time inviation codes for carers.
@login_required
def manage_invitation_codes(request):
    # Checking user authorisation
    carehome = get_user_carehome(request.user)
    
    if not carehome:
        messages.error(request, "Unauthorized access")
        return redirect('/')
    

    if not hasattr(request.user, 'manager'):
        messages.error(request, "Unauthorized access")
        return redirect('carer_dashboard')
        
    
    # Get active invitations
    active_invitations = InvitationCode.objects.filter(
        carehome=carehome,
        is_used=False,
        expires_at__gt=timezone.now()
    ).order_by('-created_at')
    
    # Get used invitations
    used_invitations = InvitationCode.objects.filter(
        carehome=carehome,
        is_used=True
    ).order_by('-used_at')[:10]  # Show last 10 used codes
    
    # Handle form submission
    if request.method == 'POST':
        if 'generate_code' in request.POST:
            form = GenerateInvitationCodeForm(request.POST)
            if form.is_valid():
                invitation = form.generate_code(carehome, request.user)
                messages.success(request, f"Invitation code {invitation.code} generated successfully!")
                return redirect('manage_invitation_codes')
            
        elif 'delete_code' in request.POST:
            code_id = request.POST.get('code_id')
            try:
                code = InvitationCode.objects.get(id=code_id, carehome=carehome, is_used=False)
                code.delete()
                messages.success(request, "Invitation code deleted successfully!")
            except InvitationCode.DoesNotExist:
                messages.error(request, "Code not found or already used.")
    else:
        form = GenerateInvitationCodeForm()
    
    context = {
        'form': GenerateInvitationCodeForm(),
        'active_invitations': active_invitations,
        'used_invitations': used_invitations,
        'carehome': carehome
    }
    
    return render(request, 'manager/manage_invites.html', context)



#View for logging in and authenticating a user.
@csrf_protect
def login_view(request):
    user = request.user
    # if user is logged in, they are redirected to the dashboard
    if request.user.is_authenticated:
        try:
            manager = request.user.manager
            return redirect('manager_dashboard')
        except Manager.DoesNotExist:
            try:
                carer = request.user.carer
                # Check if carer's access is still valid
                if not carer.has_valid_access:
                    logout(request)
                    messages.error(request, "Your access period has expired. Please contact your manager.")
                    return redirect('login')
                return redirect('carer_dashboard')
            except Carer.DoesNotExist:
                logout(request)
                messages.error(request, "User account type not recognized. Please contact support.")
                return redirect('login')

    # if the user is not logged in, they are shown the login form
    if request.method == 'POST':
        form = AuthenticationForm(request, request.POST)
        if form.is_valid():

            user=form.get_user()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
           
            user = authenticate(username=username,
                                 password=password)
           
            if user is not None:
                login(request, user)
                #Redirects manager user and carer user to correct dashboard
                try:
                    manager = request.user.manager
                    return redirect('manager_dashboard')
                except Manager.DoesNotExist:
                    try:
                        #checks if the carer has valid access before redirecting them
                        carer = request.user.carer
                        if not carer.has_valid_access:
                            logout(request)
                            messages.error(request, "Your access period has expired. Please contact your manager.")
                            return redirect('login')
                        
                        return redirect('carer_dashboard')
                    except Carer.DoesNotExist:
                    
                        logout(request)
                        messages.error(request, "User account type not recognized. Please contact support.")
                    return redirect('login')
                
        else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{error}")
    else:
        form = AuthenticationForm()

    return render(request, 'auth/login.html', {'form': form})



#registration page view, handles both the manager and carer registration form
#validates the form and saves the data to the database.
@csrf_protect
@ensure_csrf_cookie
def registration(request):

    #if the server request is a post request, the form is checked for validity
    if request.method == 'POST':
        #The registration page manages both user types, manager and carer
        form1 = ManagerSignUpForm(request.POST)
        form2 = CarerSignUpForm(request.POST)

        #if the manager form is submitted, the form is checked for validity
        #the user is then created and logged in
        #the user is then redirected to the carehome setup page as a new manager.
        try:
            if 'sign_up_manager' in request.POST:
                form = ManagerSignUpForm(request.POST)
                if form.is_valid():
                    user = form.save()
                    login(request, user)
                    return redirect('setup_carehome')
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"{error}")

            #if the carer form is submitted, the form is checked for validity
            #the user is then created and logged in
            #the user is then redirected to the carer dashboard for their carehome.
            elif 'sign_up_carer' in request.POST:
                form = CarerSignUpForm(request.POST)
                if form.is_valid():
                    user = form.save()
                    login(request, user)
                    return redirect('carer_dashboard')
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"{error}")



        except IntegrityError as e:
            #handles email already existing in database
            if "unique constraint" in str(e).lower():
                messages.error(request, "An account with that email already exists.")
                
            

    else:
        form1 = ManagerSignUpForm()
        form2 = CarerSignUpForm()

    return render(request, 'auth/businesssignup.html', 
                  {'form1': form1, 'form2': form2}, )



#manager dashboard, displays all the information for the manager
#this includes the residents, carers, and medication stock
#and displays the medication schedule for the day
#Context is made of a database query for the respective carehome components.
@login_required
def manager_dashboard(request):
    carehome = get_user_carehome(request.user)
    if hasattr(request.user, 'carer'):
        return redirect('carer_dashboard')
    
    if not carehome:
        messages.error(request, "Unauthorized access")
        return redirect('/')
    

    # Fetch Context
    medications = Medication.objects.filter(carehome=carehome).prefetch_related(
    Prefetch(
        'inventory_items',
        queryset=MedicationInventoryItem.objects.filter(medication__carehome=carehome)
            )
        )

    context = {
        'today': date.today(),

        'carehome': carehome,

        'residents_count': carehome.residents.count(),
        'carers_count': carehome.carers.count(),

        'carers': carehome.carers.all(),
        'residents': carehome.residents.all(),
        'medication_stock': medications,

        'today_medications': MedicationSchedule.objects.filter(
            resident__carehome=carehome
        ).prefetch_related(
        Prefetch('times', queryset=MedicationTime.objects.filter(time__hour__gte=0))
        ).select_related('resident', 'medication'),

    
    }

    return render(request, 'dashboards/manager_dashboard.html',context)


#Primary view for carer users.
#Displays the medication schedule for the day, and allows the carer to record medication given to residents.
@login_required
def carer_dashboard(request):
    # If the user is not a carer, they are redirected to the login page
    if not hasattr(request.user, 'carer'):
        messages.error(request, "Unauthorized access")
        return redirect('login')
    
    # Get the correct carer from the database and timezone
    carer = request.user.carer
    now = timezone.now()
    
    # Get residents from carer's assigned group
    residents = []
    if carer.resident_group:
        residents = carer.resident_group.residents.all()
    
    # Get all medication schedules for these residents
    schedules = MedicationSchedule.objects.filter(
        resident__in=residents,
        is_active=True
    ).select_related(
        'resident', 
        'medication'
    ).prefetch_related('times')
    
    # Organize medications by time slots
    upcoming_meds = []
    for schedule in schedules:
        for time_slot in schedule.times.all():
            med_time = timezone.make_aware(
                datetime.combine(now.date(), time_slot.time)
            )
            # Time difference between when medication is due and the current time
            time_diff = med_time - now
            
            # If medication is more than 12 hours overdue, skip
            if time_diff.total_seconds() < -43200:  # 12 hours in seconds
                continue
            
            # Check if medication was already given today by checking the log
            was_given = MedicationLog.objects.filter(
                schedule=schedule,
                scheduled_time=time_slot,
                given_at__date=now.date()
            ).exists()
            
            # Calculate urgency level
            urgency = calculate_urgency(was_given, time_diff)
            
            upcoming_meds.append({
                'schedule': schedule,
                'time_slot': time_slot,
                'planned_time': med_time,
                'time_diff': time_diff,
                'urgency': urgency,
                'was_given': was_given
            })
    
    # Sort by time
    upcoming_meds.sort(key=lambda x: x['planned_time'])
    
    context = {
        'carer': carer,
        'upcoming_meds': upcoming_meds,
        'current_time': now,
        'residents': residents,
    }
    
    return render(request, 'dashboards/carer_dashboard.html', context)



#Main view for adding, editing and removing residents
#as well as creating resident groups
#and navigating to the create schedule view.
@login_required
@carer_permission_required('can_edit_residents')
def manager_dashboard_residents(request):
    carehome = get_user_carehome(request.user)
    if not carehome:
        messages.error(request, "Unauthorized access")
        return redirect('carer_dashboard')
    
    # This gets all the residents from the carehome
    residents = Resident.objects.filter(carehome=carehome)
    group_form = ResidentGroupForm()

    if request.method == 'POST':
        #form for adding a new group to carehome
        if 'add_group' in request.POST:
            group_form = ResidentGroupForm(request.POST)
            if group_form.is_valid():
                group = group_form.save(commit=False)
                group.carehome = carehome
                group.save()
                messages.success(request, 'Group added successfully.')
                return redirect('manager_dashboard_residents')
            
        #POST request to remove resident from carehome
        elif 'remove_resident' in request.POST:
            resident_id = request.POST.get('resident_id')
            try:
                resident = Resident.objects.get(id=resident_id, carehome=carehome)
                resident.delete()
                messages.success(request, 'Resident removed successfully.')
            except Resident.DoesNotExist:
                messages.error(request, 'Resident not found.')
            return redirect('manager_dashboard_residents')

        else:
            group_form = ResidentGroupForm()
            resident_form = ResidentForm(carehome=carehome)


    groups = ResidentGroup.objects.filter(carehome=carehome)
    
    context = {
        'residents': residents,
        'group_form': group_form,
        'groups': groups,
    }
    return render(request, 'dashboards/manager_dashboard_residents.html', context)


#View for managing the time-based access for Carers
#Allows the manager to set a carer to have indefinite access, or set a date for their access to end.
@login_required
def manage_carer_access(request, carer_id):
    carehome = get_user_carehome(request.user)
    carer = get_object_or_404(Carer, id=carer_id, carehome=carehome)
    
    if request.method == 'POST':
        form = CarerAccessForm(request.POST, instance=carer)
        if form.is_valid():
            form.save()
            if carer.indefinite_access:
                messages.success(request, f'Access for {carer.user.get_full_name()} set to indefinite')
            else:
                end_date = carer.access_end_date.strftime('%d %b %Y, %H:%M')
                messages.success(request, f'Access for {carer.user.get_full_name()} will expire on {end_date}')
            return redirect('manager_dashboard_carers')
    else:
        form = CarerAccessForm(instance=carer)
    
    return render(request, 'dashboards/manage_carer_access.html', {
        'form': form,
        'carer': carer
    })


#View for editing an existing resident in the carehome.
#Uses the same resident form used to create a resident, instead resident data
#is parsed to populate the form before editing.
@login_required
@carer_permission_required('can_edit_residents')
def edit_resident(request, resident_id):
    carehome = get_user_carehome(request.user)
    if not carehome:
        messages.error(request, "Unauthorized access")
        return redirect('/')
    
    resident = get_object_or_404(Resident, id=resident_id, carehome=carehome)


    if request.method == 'POST':

        form = ResidentForm(request.POST, request.FILES, instance=resident, carehome=carehome)
        if form.is_valid():
            form.save()
            messages.success(request, 'Resident updated successfully.')
            return redirect('manager_dashboard_residents')
    else:
        form = ResidentForm(instance=resident, carehome=carehome)


    
    return render(request, 'resident/edit_resident.html', {'form': form, 'resident': resident})




#View for mangement of care staff
#Allows the manager to assign a carer to a resident group, or remove them from a group.
#Also provides a overview for all the carers in the carehome.
@login_required
def manager_dashboard_carers(request):
    carehome = get_user_carehome(request.user)
    if not carehome:
        messages.error(request, "Unauthorized access")
        return redirect('/')
    if not hasattr(request.user, 'manager'):
        messages.error(request, "Unauthorized access")
        return redirect('carer_dashboard')
    
    carers = Carer.objects.filter(carehome=carehome)
    groups = ResidentGroup.objects.filter(carehome=carehome)

    if request.method == 'POST' and 'update_carer_group' in request.POST:
        carer_id = request.POST.get('carer_id')
        group_id = request.POST.get('group_id')
        
        try:
            carer = carers.get(id=carer_id)
            if group_id:
                group = groups.get(id=group_id)
                carer.resident_group = group
            else:
                carer.resident_group = None
            carer.save()
            messages.success(request, 'Carer group updated successfully.')
        except (Carer.DoesNotExist, ResidentGroup.DoesNotExist):
            messages.error(request, 'Error updating carer group.')

    context = {
        'carers': carers,
        'groups': groups,
        'carehome': carehome,
    }
    return render(request, 'dashboards/manager_dashboard_carers.html', context)


#Creates a medication schedule 
@login_required
@carer_permission_required('can_manage_schedules')
def add_medication_schedule(request, resident_id):
    resident = get_object_or_404(Resident, id=resident_id)
    carehome = get_user_carehome(request.user)
    
    # Verify user has access to this resident
    if resident.carehome != carehome:
        messages.error(request, "Unauthorized access")
        return redirect('carer_dashboard')
    
    if request.method == 'POST':
        
        form = MedicationScheduleForm(request.POST, carehome=carehome)
        
        
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.resident = resident
            schedule.save()
            
            # Process time slots
            times = request.POST.getlist('times[]')
            for time_str in times:
                if time_str:
                    try:
                        #create a MedicationTime record for each time instance
                        time_obj = datetime.strptime(time_str, '%H:%M').time()
                        MedicationTime.objects.create(
                            schedule=schedule,
                            time=time_obj
                        )
                    except ValueError:
                        pass  # Skip invalid time values
            
            messages.success(request, f"Medication schedule added for {resident.name}")
            return redirect('resident_medications', resident_id=resident_id)
        
                
    else:
        form = MedicationScheduleForm(carehome=carehome)
    
    return render(request, 'medication/add_medication_schedule.html', {
        'form': form,
        'resident': resident
    })


@login_required
def resident_medications(request, resident_id):
    resident = get_object_or_404(Resident, id=resident_id)
    carehome = get_user_carehome(request.user)
    if not carehome:
        messages.error(request, "Unauthorized access")
        return redirect('/')
    
    # Verify the resident belongs to the correct carehome
    if carehome != resident.carehome:
        messages.error(request, "Unauthorized access")
        return redirect('manager_dashboard')

    schedules = MedicationSchedule.objects.filter(resident=resident)\
        .select_related('medication')\
        .prefetch_related('times')


    return render(request, 'resident/resident_medications.html', {
        'resident': resident,
        'schedules': schedules
    })


#View for the API based medication search screen. Provides the context to populate the
#html page with medicaiton names.
@login_required
def search_medications(request, search_term):
    if not hasattr(request.user, 'manager'):
        messages.error(request, "Unauthorized access")
        return redirect('carer_dashboard')

    if len(search_term) == 1 and search_term.isalpha():
        try:
            data = get_medicine(search_term)
            medicine_names = get_medicine_names(data)
        except Exception as e:
            messages.error(request, f"Error fetching medicines: {str(e)}")
            medicine_names = []
    else:
        medicine_names = []

    return render(request, 'medication/search_medications.html', {
        'results': medicine_names,
        'search_term': search_term.upper() if search_term else ''
    })


#Runs the database query to store a new medicaiton to the database
#Checks that medicaiton doesnt already exist in the database
#Finds the medicaiton in the API call from the id parsed from the medicaiton search.

@login_required
def add_medication_to_db(request):
    if request.method == 'POST':
        nhs_id = request.POST.get('nhs_id')
        carehome = get_user_carehome(request.user)
        if not carehome:
            messages.error(request, "Unauthorized access")
            return redirect('/')

        if not nhs_id:
            messages.error(request, "Invalid medication ID")
            return redirect('search_medications', 'A')

        if Medication.objects.filter(nhs_id=nhs_id, carehome=carehome).exists():
            messages.warning(request, "This medication already exists in your carehome's database.")
            return redirect('search_medications', 'A')

        try:
            # Get first letter of medication name for API search
            first_letter = nhs_id[0].upper()
            data = get_medicine(first_letter)
            
            for item in data.get('significantLink', []):
                if nhs_id in item.get('url', ''):
                    
                    medication = Medication.objects.create(
                        name=item['name'],
                        nhs_id=nhs_id,
                        carehome=carehome
                    )
                    
                    
                    
                    messages.success(request, f"Successfully added {medication.name} to the database.")
                    return redirect('medication_inventory')
            
            messages.error(request, "Medication not found in API response.")
        except Exception as e:
            messages.error(request, f"Error adding medication: {str(e)}")

    return redirect('search_medications', 'A')


#View for deleting a residents medication schedule. Checks users carehome association.
@login_required
def delete_medication_schedule(request, schedule_id):
    if request.method == 'POST':
        schedule = get_object_or_404(MedicationSchedule, id=schedule_id)
        carehome = get_user_carehome(request.user)
   
        
        # ensure the user has permission to delete this schedule
        if carehome != schedule.resident.carehome:
            messages.error(request, "Unauthorized access")
            return redirect('manager_dashboard')
        
        resident_id = schedule.resident.id  
        schedule.delete()
        messages.success(request, "Medication schedule removed successfully")
        return redirect('resident_medications', resident_id=resident_id)
    
    return redirect('manager_dashboard')




#View for adjusting the sock level of a medciation invetory item.
#Gets the medication item record associated with the request and edits its stock level.

@login_required
@carer_permission_required('can_adjust_stock')
def adjust_inventory_stock(request, inventory_item_id):
    try:
        inventory_item = MedicationInventoryItem.objects.get(id=inventory_item_id)
        new_stock = request.POST.get('stock')
        
        carehome = get_user_carehome(request.user)
        # Check medication is from user carehome
        if carehome != inventory_item.medication.carehome:
            messages.error(request, "Unauthorized access")
            return redirect('medication_inventory')
            
        if new_stock is not None:
            inventory_item.stock = int(new_stock)
            inventory_item.save()
            messages.success(request, f"Stock updated for {inventory_item.medication.name} {inventory_item.dosage} {inventory_item.form}")
        else:
            messages.error(request, "Invalid stock value")
    except (MedicationInventoryItem.DoesNotExist, ValueError):
        messages.error(request, "Invalid update request")
    return redirect('medication_inventory')


#View for adding a new inventory item to the database.
#Processes the medicationinvetoryitem form
#saves the data to the database
#has a check for duplicate records.
@login_required
@carer_permission_required('can_adjust_stock')
def add_inventory_item(request, medication_id):
    medication = get_object_or_404(Medication, id=medication_id)
    carehome = get_user_carehome(request.user)
    
    if carehome != medication.carehome:
        messages.error(request, "Unauthorized access")
        return redirect('medication_inventory')
        
    if request.method == 'POST':
        form = MedicationInventoryItemForm(request.POST)
        if form.is_valid():
            inventory_item = form.save(commit=False)
            inventory_item.medication = medication
            
            try:
                inventory_item.save()
                messages.success(request, f"Added {inventory_item.dosage} {inventory_item.form} to {medication.name}")
            except IntegrityError:
                messages.error(request, "This dosage and form combination already exists")
                
        return redirect('medication_inventory')
    else:
        form = MedicationInventoryItemForm()
        
    return render(request, 'medication/add_inventory_item.html', {
        'form': form,
        'medication': medication
    })

#View for deleting a medication inventory item of a medciation.
#Checks if the item is used in any active medication schedules before deleting.
#If the item is used in an active schedule, the user is notified and redirected to the inventory page.
@login_required
@carer_permission_required('can_adjust_stock')
def delete_inventory_item(request, inventory_item_id):
    try:
        inventory_item = get_object_or_404(MedicationInventoryItem, id=inventory_item_id)
        medication_name = inventory_item.medication.name
        variant_info = f"{inventory_item.dosage} {inventory_item.form}"
        
        # Verify user has permission to delete this item
        carehome = get_user_carehome(request.user)
        if carehome != inventory_item.medication.carehome:
            messages.error(request, "Unauthorized access")
            return redirect('medication_inventory')
        
        # Check if inventory item is used in any active medication schedules
        if MedicationSchedule.objects.filter(inventory_item=inventory_item, is_active=True).exists():
            messages.error(request, f"Cannot delete {variant_info} as it is currently used in active medication schedules")
            return redirect('medication_inventory')
        
        # Delete the inventory item
        inventory_item.delete()
        messages.success(request, f"Successfully removed {medication_name} {variant_info} from inventory")
        
    except Exception as e:
        messages.error(request, f"Error deleting inventory item: {str(e)}")
    
    return redirect('medication_inventory')

#View for deleting a medication from the database, similar to delete_inventory_item.
#Checks if the medication is used in any active schedules before deleting.
@login_required
@carer_permission_required('can_adjust_stock')
def delete_medication(request, medication_id):
    if request.method == 'POST':
        medication = get_object_or_404(Medication, id=medication_id)
        carehome = get_user_carehome(request.user)
        
        # Verify user has permission to delete this item
        if carehome != medication.carehome:
            messages.error(request, "Unauthorized access")
            return redirect('medication_inventory')
        
        # Check if any medication inventory items are used in active schedules
        active_schedules = MedicationSchedule.objects.filter(
            medication=medication,
            is_active=True
        )
        
        if active_schedules.exists():
            messages.error(request, 
                f"Cannot delete {medication.name} as it is being used in {active_schedules.count()} active medication schedules")
            return redirect('medication_inventory')
        
        # Get the medication name before deletion for the success message
        medication_name = medication.name
        
        # Delete the medication (this will cascade delete all inventory items)
        medication.delete()
        
        messages.success(request, f"Successfully removed {medication_name} and all its variants from inventory")
    
    return redirect('medication_inventory')



#View for rendering the medicaiton inventory.
@login_required
@carer_permission_required('can_view_inventory')
def medication_inventory(request):
    
    carehome = get_user_carehome(request.user)
    if not carehome:
        messages.error(request, "Unauthorized access")
        return redirect('/')
    
    medications = Medication.objects.filter(carehome=carehome).prefetch_related(
        Prefetch(
            'medicationschedule_set',
            queryset=MedicationSchedule.objects.select_related('resident')
        )
    )
     
    return render(request, 'medication/medication_inventory.html', {
        'medications': medications
    })


#View for processing the Carer permisisons form and updating the record.
@login_required
def manage_carer_permissions(request, carer_id):
    carehome = get_user_carehome(request.user)
    carer = get_object_or_404(Carer, id=carer_id, carehome=carehome)
    
    if request.method == 'POST':
        form = CarerPermissionsForm(request.POST, instance=carer.permissions)
        if form.is_valid():
            form.save()
            messages.success(request, f'Permissions updated for {carer.user.username}')
            return redirect('manager_dashboard_carers')
    else:
        form = CarerPermissionsForm(instance=carer.permissions)
    
    return render(request, 'dashboards/manage_carer_permissions.html', {
        'form': form,
        'carer': carer
    })



#Records the instance of medication being dispensed to a carer
#Called when carer clicks 'mark as given' on a medicaiton.
#Creates a medicaiton log, inlcuding care ntoes and adjusts the stock level.
@login_required
def record_medication(request, schedule_id, time_slot_id):
    if request.method == 'POST':
        schedule = get_object_or_404(MedicationSchedule, id=schedule_id)
        time_slot = get_object_or_404(MedicationTime, id=time_slot_id)
        
        # Verify carer has access to this resident
        if not request.user.carer.resident_group or \
           schedule.resident not in request.user.carer.resident_group.residents.all():
            messages.error(request, "Unauthorized access")
            return redirect('carer_dashboard')
        
        notes = request.POST.get('notes', '')
        
        # Create medication log
        MedicationLog.objects.create(
            schedule=schedule,
            scheduled_time=time_slot,
            given_by=request.user.carer,
            notes=notes
        )
        
        # Decrease medication stock
        inventory_item = schedule.inventory_item
        if inventory_item.stock > 0:
            inventory_item.stock -= 1
            inventory_item.save()
            
        messages.success(request, f"Medication recorded for {schedule.resident.name}")
        return redirect('carer_dashboard')
    
    return redirect('carer_dashboard')

#Used to dynmaically update the Carer dashboard.
#Used in the Carer dashboard html file, called by javascript in the update dashboard function.
@login_required
def get_dashboard_updates(request):
    carehome = get_user_carehome(request.user)
    upcoming_meds = get_upcoming_medications(carehome)
    html = render_to_string('includes/medication_list.html', {'upcoming_meds': upcoming_meds})
    current_time = timezone.now().strftime('%H:%M:%S')
    return JsonResponse({'html': html, 'current_time': current_time})


#Generates the mar charts for the resident. it uses a in-memeory buffer because the data
#is sensitive and should not be stored on the server.
@login_required
def generate_mar_chart(request, resident_id):
    if not hasattr(request.user, 'manager'):
        messages.error(request, "Unauthorized access")
        return redirect('/')

    carehome = get_user_carehome(request.user)
    resident = get_object_or_404(Resident, id=resident_id)
    

    # Verify user has permission to access this resident's data
    if carehome != resident.carehome:
        messages.error(request, "Unauthorized access")
        return redirect('manager_dashboard')
    
    start_date = datetime.now().replace(day=1)  # Start from first of current month
    
    # Create in-memory PDF
    buffer = BytesIO()
    MedicationLog.generate_mar_chart(resident, start_date, buffer)
    
    # Set buffer's cursor at the beginning
    buffer.seek(0)
    
    # Return the PDF from memory
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f'MAR_{resident.name}_{start_date.strftime("%B_%Y")}.pdf'
    )

#View for adding a new resident to the carehome.
#Uses the same resident form as the edit resident view, but does not populate it with data.
#The form is then saved to the database with the carehome association.
@login_required
def add_resident(request):
    if not hasattr(request.user, 'manager'):
        messages.error(request, "Unauthorized access")
        return redirect('/')

    carehome = get_user_carehome(request.user)
    if not carehome:
        messages.error(request, "Unauthorized access")
        return redirect('/')

    
    if request.method == 'POST':
        form = ResidentForm(request.POST, request.FILES, carehome=carehome)
        if form.is_valid():
            resident = form.save(commit=False)
            resident.carehome = carehome
            resident.save()
            messages.success(request, 'Resident added successfully.')
            return redirect('manager_dashboard_residents')
    else:
        form = ResidentForm(carehome=carehome)
    
    return render(request, 'resident/add_resident.html', {'form': form})

#View for the medication audit log.
#This is a read only view for the manager to see all the medication logs for the carehome.
##The logs are filtered by date, and the user can select a date to view the logs for that date.
#Queries the medicationlog table for data.
@login_required
def medication_audit_log(request):
    if not hasattr(request.user, 'manager'):
        messages.error(request, "Unauthorized access")
        return redirect('carer_dashboard')

    carehome = get_user_carehome(request.user)
    selected_date = request.GET.get('date')

    try:
        if selected_date:
            selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        else:
            selected_date = date.today()
    except ValueError:
        selected_date = date.today()

    logs = MedicationLog.objects.filter(
        schedule__resident__carehome=carehome,
        given_at__date=selected_date
    ).select_related(
        'schedule__resident',
        'schedule__medication',
        'given_by__user',
        'scheduled_time'
    ).order_by('-given_at')

    return render(request, 'medication/audit_log.html', {
        'logs': logs,
        'selected_date': selected_date,
    })