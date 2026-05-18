from rest_framework import permissions

class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)

class IsSystemAdmin(permissions.BasePermission):
    """
    Allows access only to Admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and 
                    hasattr(request.user, 'profile') and 
                    request.user.profile.role == 'ADMIN')

class IsCinemaManager(permissions.BasePermission):
    """
    Allows access only to Manager or Admin users.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and hasattr(request.user, 'profile')):
            return False
        return request.user.profile.role in ['ADMIN', 'MANAGER']

class IsCinemaManagerOrReadOnly(permissions.BasePermission):
    """
    Allows access only to Manager or Admin users for modification.
    Read-only access is allowed for others.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not (request.user and request.user.is_authenticated and hasattr(request.user, 'profile')):
            return False
        return request.user.profile.role in ['ADMIN', 'MANAGER']