from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions

class InactiveUserTokenAuthentication(TokenAuthentication):
    """
    Custom Token Authentication that allows inactive users to be authenticated.
    This prevents 401 errors for public endpoints when an inactive user's 
    token is sent in the header (e.g. during auto-login flows).
    
    We still check if the token exists and is valid.
    Permissions (like IsAuthenticated or IsActive) should handle blocking 
    inactive users from specific actions.
    """
    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.select_related('user').get(key=key)
        except model.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token.')

        # In standard TokenAuthentication, this is where it checks user.is_active.
        # We skip that check here so the request can proceed to permission checks.
        return (token.user, token)
