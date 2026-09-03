from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

#custom django decorator that uses the carer permissions table 
#to control view access. Takes a string input of a carer permission as a arguement.
def carer_permission_required(permission):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Allow access for managers
            if hasattr(request.user, 'manager'):
                return view_func(request, *args, **kwargs)
            
            # Check carer permissions
            if not hasattr(request.user, 'carer'):
                messages.error(request, "Access denied")
                return redirect('login')
            
            carer_permissions = request.user.carer.permissions
            if not getattr(carer_permissions, permission):
                messages.error(request, "You don't have permission to perform this action")
                return redirect('carer_dashboard')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator