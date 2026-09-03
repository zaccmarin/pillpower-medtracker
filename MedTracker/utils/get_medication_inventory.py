import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from MedTracker.models import Medication, MedicationInventoryItem
from MedTracker.utils.get_user_carehome import get_user_carehome

# This function retrieves the inventory items for a specific medication.
# It checks if the user has access to the carehome associated with the medication.
# It returns a JSON response with the inventory items.
@login_required
def get_medication_inventory_items(request, medication_id):
    medication = get_object_or_404(Medication, id=medication_id)
    carehome = get_user_carehome(request.user)
    
    # Make sure user has access to this medication
    if medication.carehome != carehome:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Get all inventory items for this medication
    inventory_items = MedicationInventoryItem.objects.filter(
        medication_id=medication_id
    ).values('id', 'dosage', 'form', 'stock')
    
    return JsonResponse(list(inventory_items), safe=False)