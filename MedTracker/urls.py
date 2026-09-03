from django.urls import path
from MedTracker import views
from django.conf.urls import handler404
from MedTracker.views import custom_404
from django.conf import settings
from django.conf.urls.static import static
from MedTracker.utils.get_medication_inventory import *

handler404 = custom_404

urlpatterns = [
    path("", views.index, name="index"),
    path("aboutus/", views.aboutus, name="aboutus"),
    path('logout/', views.logout_view, name='logout'),

    path('register/', views.registration, name='register'),
   
    path('carehomesetup/', views.setup_carehome, name='setup_carehome'),
    path('login/', views.login_view, name='login'),
    
    path('carerdashboard/', views.carer_dashboard, name='carer_dashboard'),

    path('record-medication/<int:schedule_id>/<int:time_slot_id>/', 
         views.record_medication, 
         name='record_medication'),
     

    path('dashboard/updates/', views.get_dashboard_updates, name='get_dashboard_updates'),
    path('managerdashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/residents/', views.manager_dashboard_residents, name='manager_dashboard_residents'),
    path('manager/residents/edit/<int:resident_id>/', views.edit_resident, name='edit_resident'),
    path('manager/carers/', views.manager_dashboard_carers, name='manager_dashboard_carers'),

    path('manager/manage_invites/', views.manage_invitation_codes, name='manage_invitation_codes'),

    path('resident/<int:resident_id>/medications/', views.resident_medications, name='resident_medications'),
    path('resident/<int:resident_id>/add-medication/', views.add_medication_schedule, name='add_medication_schedule'),


    path('medications/', views.medication_inventory, name='medication_inventory'),


    path('medications/add/', views.add_medication_to_db, name='add_medication_to_db'),
    path('medications/search/<str:search_term>/', views.search_medications, name='search_medications'),
    path('medications/audit-log/', views.medication_audit_log, name='medication_audit_log'),


    path('medication-schedule/<int:schedule_id>/delete/', views.delete_medication_schedule, name='delete_medication_schedule'),


    path('manage-carer-permissions/<int:carer_id>/', views.manage_carer_permissions, name='manage_carer_permissions'),

    path('resident/<int:resident_id>/mar-chart/', views.generate_mar_chart, name='generate_mar_chart'),

    path('resident/add/', views.add_resident, name='add_resident'),

    path('api/medication/<int:medication_id>/inventory-items/', get_medication_inventory_items, name='get_medication_inventory_items'),
    path('medications/inventory/add/<int:medication_id>/', views.add_inventory_item, name='add_inventory_item'),
    path('medications/inventory/adjust-stock/<int:inventory_item_id>/', views.adjust_inventory_stock, name='adjust_inventory_stock'),

     path('medications/inventory/<int:inventory_item_id>/delete/', views.delete_inventory_item, name='delete_inventory_item'),
     path('medications/delete/<int:medication_id>/', views.delete_medication, name='delete_medication'),

     path('manage-carer-access/<int:carer_id>/', views.manage_carer_access, name='manage_carer_access'),
]
