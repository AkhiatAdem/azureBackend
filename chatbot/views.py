from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .services import get_chatbot_response

@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot_message(request):
    user_message = request.data.get('message')
    if not user_message:
        return Response({'error': 'Message is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    response_data = get_chatbot_response(user_message)
    return Response(response_data, status=status.HTTP_200_OK)
