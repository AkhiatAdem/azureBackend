import uuid
import logging
import random
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from django.shortcuts import render
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.core.mail import send_mail, EmailMessage

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication

from .models import Movie, Room, Screening, Ticket, VerificationCode, PasswordResetCode, Genre, Profile, Seat
from .serializers import (
    MovieSerializer, UserSerializer, RoomSerializer, ScreeningSerializer, 
    TicketSerializer, GenreSerializer, ProfileSerializer
)
from .permissions import IsSystemAdmin, IsCinemaManager, IsCinemaManagerOrReadOnly
from .utils import generate_ticket_pdf
from .utils_payment import simulate_payment
from django.db.models import Sum, Count
logger = logging.getLogger(__name__)

# --- AUTH ---

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Generate 6-digit code
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        VerificationCode.objects.create(user=user, code=code)
        
        # Send actual email
        try:
            send_mail(
                'Verify Your WebCinema Account',
                f'Welcome {user.username}!\n\nYour 6-digit verification code is: {code}\n\nPlease enter this code on the website to verify your account.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send registration email: {str(e)}")
            # Even if email fails, we don't want to break registration (maybe print to console in dev)
            print(f"VERIFICATION CODE (EMAIL FAILED): {code}")
        
        # Create token for auto-login (even if not verified yet)
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'message': 'User registered. Please verify your email.',
            'token': token.key,
            'is_staff': user.is_staff,
            'username': user.username,
            'email': user.email,
            'membership_type': 'NORMAL',
            'monthly_credits': 0,
            'role': user.profile.role if hasattr(user, 'profile') else 'SPECTATOR'
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    email = request.data.get('email')
    code = request.data.get('code')
    try:
        user = User.objects.get(email=email)
        vc = VerificationCode.objects.filter(user=user, code=code).first()
        if vc:
            user.is_active = True
            user.save()
            vc.delete()
            return Response({'message': 'Email verified successfully.'})
    except User.DoesNotExist:
        pass
    return Response({'error': 'Invalid code or email.'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    requested_role = request.data.get('role') # Extract the role chosen on the frontend

    if not requested_role:
        return Response({'error': 'Please select a login role.'}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)
    
    if user:
        # Check if the user has a profile and if their DB role matches the requested role
        if not hasattr(user, 'profile') or user.profile.role != requested_role:
            return Response(
                {'error': f'Access denied. You are not authorized as a {requested_role.title()}.'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        token, _ = Token.objects.get_or_create(user=user)
        profile = user.profile
        
        return Response({
            'token': token.key,
            'is_staff': user.is_staff,
            'role': profile.role,
            'membership_type': profile.membership_type,
            'monthly_credits': profile.monthly_credits,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active
        })
# --- USER MANAGEMENT ---

@api_view(['GET'])
@permission_classes([IsSystemAdmin])
def user_list(request):
    users = User.objects.all().order_by('-date_joined')
    data = []
    for u in users:
        data.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'role': u.profile.role if hasattr(u, 'profile') else 'SPECTATOR',
            'is_active': u.is_active,
            'last_login': u.last_login,
            'subscription': u.profile.membership_type if hasattr(u, 'profile') else 'NORMAL'
        })
    return Response(data)

@api_view(['POST'])
@permission_classes([IsSystemAdmin])
def promote_user(request, pk):
    try:
        user = User.objects.get(pk=pk)
        role = request.data.get('role')
        if role not in [Profile.Role.ADMIN, Profile.Role.MANAGER, Profile.Role.SPECTATOR]:
            return Response({'error': 'Invalid role'}, status=status.HTTP_400_BAD_REQUEST)
        
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        
        if role in [Profile.Role.ADMIN, Profile.Role.MANAGER]:
            user.is_staff = True
        else:
            user.is_staff = False
        user.save()
        
        return Response({'message': f'User {user.username} updated to {role}'})
    except User.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsSystemAdmin])
def toggle_user_status(request, pk):
    try:
        user = User.objects.get(pk=pk)
        user.is_active = not user.is_active
        user.save()
        return Response({'message': f'User {user.username} status toggled to {user.is_active}'})
    except User.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

# --- MEMBERSHIP ---

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upgrade_membership(request):
    """
    Upgrade the authenticated user to Premium through the demo payment gateway.

    For the PFE presentation this endpoint intentionally delegates to
    ``simulate_payment`` instead of a real bank/acquirer integration. A
    16-digit card number is treated as an approved transaction, then the user
    receives the Premium role benefits consumed by booking: a recurring monthly
    credit and the 20% dynamic ticket discount.
    """
    card_number = request.data.get('card_number')
    if not simulate_payment(card_number):
        return Response({'error': 'Payment failed. Invalid card number.'}, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    profile = request.user.profile
    profile.membership_type = Profile.Membership.PREMIUM
    profile.monthly_credits = 1 # Initial credit
    profile.save()
    
    return Response({'message': 'Upgraded to PREMIUM!', 'membership_type': 'PREMIUM'})

# --- STATISTICS ---

@api_view(['GET'])
@permission_classes([IsCinemaManager])
def cinema_stats(request):
    total_revenue = Ticket.objects.aggregate(total=Sum('price_paid'))['total'] or 0
    total_tickets = Ticket.objects.count()
    
    # Daily sales for last 7 days
    today = timezone.now().date()
    daily_sales = []
    for i in range(6, -1, -1):
        day = today - timezone.timedelta(days=i)
        rev = Ticket.objects.filter(booked_at__date=day).aggregate(total=Sum('price_paid'))['total'] or 0
        daily_sales.append({'date': day.strftime('%b %d'), 'revenue': float(rev)})
        
    # Top movies
    top_movies = Movie.objects.annotate(
        tickets_sold=Count('screenings__tickets')
    ).order_by('-tickets_sold')[:5]
    top_movies_data = [{'title': m.title, 'tickets_sold': m.tickets_sold} for m in top_movies]
    
    # --- NEW: Genre Distribution for Pie Chart ---
    genres = Genre.objects.annotate(
        tickets_sold=Count('movies__screenings__tickets')
    ).filter(tickets_sold__gt=0).order_by('-tickets_sold')
    
    genre_distribution = [
        {'name': g.name, 'value': g.tickets_sold} 
        for g in genres
    ]
    # -------------------------------------------
    
    # Occupancy rate
    screenings = Screening.objects.all()
    total_occupancy = 0
    for s in screenings:
        capacity = s.room.rows * s.room.cols
        booked = s.tickets.count()
        if capacity > 0:
            total_occupancy += (booked / capacity)
    
    avg_occupancy = (total_occupancy / screenings.count() * 100) if screenings.exists() else 0
    
    return Response({
        'total_revenue': total_revenue,
        'total_tickets': total_tickets,
        'daily_sales': daily_sales,
        'top_movies': top_movies_data,
        'genre_distribution': genre_distribution, # <-- Added to response
        'avg_occupancy': round(avg_occupancy, 1)
    })

# --- GENRES, MOVIES, ROOMS, SCREENINGS ---

@api_view(['GET', 'POST'])
@permission_classes([IsCinemaManagerOrReadOnly])
def genre_list(request):
    if request.method == 'GET':
        genres = Genre.objects.all()
        serializer = GenreSerializer(genres, many=True)
        return Response(serializer.data)
    if request.method == 'POST':
        serializer = GenreSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsCinemaManagerOrReadOnly])
def genre_detail(request, pk):
    try:
        genre = Genre.objects.get(pk=pk)
    except Genre.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = GenreSerializer(genre)
        return Response(serializer.data)
    if request.method == 'PUT':
        serializer = GenreSerializer(genre, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    if request.method == 'DELETE':
        genre.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
@permission_classes([IsCinemaManagerOrReadOnly])
def movie_list(request):
    if request.method == 'GET':
        movies = Movie.objects.all()
        serializer = MovieSerializer(movies, many=True)
        return Response(serializer.data)
    if request.method == 'POST':
        serializer = MovieSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsCinemaManagerOrReadOnly])
def movie_detail(request, pk):
    try:
        movie = Movie.objects.get(pk=pk)
    except Movie.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = MovieSerializer(movie)
        return Response(serializer.data)
    if request.method == 'PUT':
        serializer = MovieSerializer(movie, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    if request.method == 'DELETE':
        movie.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
@permission_classes([IsCinemaManagerOrReadOnly])
def room_list(request):
    if request.method == 'GET':
        rooms = Room.objects.all()
        serializer = RoomSerializer(rooms, many=True)
        return Response(serializer.data)
    if request.method == 'POST':
        serializer = RoomSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'DELETE'])
@permission_classes([IsCinemaManagerOrReadOnly])
def room_detail(request, pk):
    try:
        room = Room.objects.get(pk=pk)
    except Room.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = RoomSerializer(room)
        return Response(serializer.data)
    if request.method == 'DELETE':
        room.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
@permission_classes([IsCinemaManagerOrReadOnly])
def screening_list(request):
    """
    List upcoming screenings or create a manager-controlled screening.

    Each screening carries its own ``base_price``. Managers set this value from
    the React dashboard when creating a show, and the booking endpoint later
    uses the same persisted value instead of a global hardcoded ticket price.
    The serializer also returns a read-only ``price`` alias so older frontend
    screens continue to render while the project moves to ``base_price``.
    """
    if request.method == 'GET':
        now = timezone.localtime(timezone.now())
        screenings = Screening.objects.filter(
            date__gte=now.date()
        ).select_related('movie', 'room').order_by('date', 'start_time')
        serializer = ScreeningSerializer(screenings, many=True)
        return Response(serializer.data)
    if request.method == 'POST':
        serializer = ScreeningSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# --- TICKETS ---

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ticket_list(request):
    """
    Return the user's tickets or create a ticket after simulated payment.

    Booking price is calculated from ``screening.base_price`` multiplied by the
    selected seats. Premium spectators receive a 20% discount on that dynamic
    base price; monthly credits still reduce the final value to 0.00. For demo
    purposes the card payment path uses ``simulate_payment`` and then generates
    the ticket immediately. After persistence, the view attempts to build the
    PDF ticket and email it to the spectator, but email delivery errors are
    logged without cancelling the already-created booking.
    """
    if request.method == 'GET':
        tickets = Ticket.objects.filter(user=request.user).select_related('screening__movie', 'screening__room').prefetch_related('seats')
        serializer = TicketSerializer(tickets, many=True)
        return Response(serializer.data)
    
    if request.method == 'POST':
        if not request.user.is_active:
            return Response({'error': 'Please verify your email.'}, status=status.HTTP_403_FORBIDDEN)
        
        raw_use_credit = request.data.get('use_credit', False)
        use_credit = str(raw_use_credit).lower() in ['true', '1', 'yes', 'on']
        card_number = request.data.get('card_number')
        
        serializer = TicketSerializer(data=request.data)
        if serializer.is_valid():
            screening = serializer.validated_data['screening']
            seats = serializer.validated_data['seats']
            profile = request.user.profile
            
            base_price = screening.base_price * len(seats)
            final_price = base_price
            
            if profile.membership_type == Profile.Membership.PREMIUM:
                final_price = base_price * Decimal('0.80')
            
            if use_credit:
                if profile.monthly_credits > 0:
                    final_price = Decimal('0.00')
                else:
                    return Response({'error': 'No credits available.'}, status=status.HTTP_400_BAD_REQUEST)
            elif not simulate_payment(card_number):
                return Response({'error': 'Payment failed.'}, status=status.HTTP_402_PAYMENT_REQUIRED)

            final_price = final_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            try:
                with transaction.atomic():
                    ticket = serializer.save(user=request.user, price_paid=final_price)
                    if use_credit:
                        profile.monthly_credits -= 1
                        profile.save()
                
                seat_labels = ', '.join(f'{seat.row_label}{seat.number}' for seat in ticket.seats.all())
                if request.user.email:
                    try:
                        pdf_buffer = generate_ticket_pdf(
                            movie_title=ticket.screening.movie.title,
                            date=ticket.screening.date,
                            time=ticket.screening.start_time,
                            room_name=ticket.screening.room.name,
                            seats=seat_labels,
                            ticket_uuid=ticket.uuid,
                            base_url=request.build_absolute_uri('/').rstrip('/'),
                        )
                        email = EmailMessage(
                            subject=f'Your ticket for {ticket.screening.movie.title}',
                            body=(
                                f'Hello {request.user.username},\n\n'
                                f'Your booking is confirmed for {ticket.screening.movie.title}.\n'
                                f'Seats: {seat_labels}\n'
                                f'Amount paid: {ticket.price_paid} DZD\n\n'
                                'Your PDF ticket is attached.'
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            to=[request.user.email],
                        )
                        email.attach(f'ticket-{ticket.uuid}.pdf', pdf_buffer.getvalue(), 'application/pdf')
                        email.send(fail_silently=False)
                    except Exception as e:
                        logger.error(f"Failed to send ticket email for ticket {ticket.id}: {str(e)}")

                response_data = dict(TicketSerializer(ticket).data)
                response_data['message'] = 'Payment approved. Ticket generated successfully.'
                return Response(response_data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([AllowAny])
def verify_ticket(request, ticket_uuid):
    try:
        ticket = Ticket.objects.get(uuid=ticket_uuid)
        return Response({'valid': True, 'movie': ticket.screening.movie.title})
    except Ticket.DoesNotExist:
        return Response({'valid': False}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification(request):
    email = request.data.get('email')
    try:
        user = User.objects.get(email=email)
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        VerificationCode.objects.filter(user=user).delete()
        VerificationCode.objects.create(user=user, code=code)
        
        try:
            send_mail(
                'Verify Your WebCinema Account',
                f'Hello {user.username}!\n\nYour new 6-digit verification code is: {code}\n\nPlease enter this code on the website to verify your account.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send verification email: {str(e)}")
            print(f"VERIFICATION CODE (EMAIL FAILED): {code}")
        
        return Response({'message': 'Verification code sent.'})
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    email = request.data.get('email')
    try:
        user = User.objects.get(email=email)
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        PasswordResetCode.objects.filter(user=user).delete()
        PasswordResetCode.objects.create(user=user, code=code)
        
        try:
            send_mail(
                'Password Reset - WebCinema',
                f'Hello {user.username}!\n\nYour password reset code is: {code}\n\nPlease enter this code on the website to reset your password.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"Password reset email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            print(f"PASSWORD RESET CODE (EMAIL FAILED): {code}")
        
        return Response({'message': 'Password reset code sent.'})
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    email = request.data.get('email')
    code = request.data.get('code')
    new_password = request.data.get('new_password')
    
    if not all([email, code, new_password]):
        return Response({'error': 'Email, code, and new password are required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
        reset_code = PasswordResetCode.objects.filter(user=user, code=code).first()
        
        if not reset_code:
            return Response({'error': 'Invalid or expired reset code.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.save()
        reset_code.delete()
        
        logger.info(f"Password reset successful for {user.email}")
        return Response({'message': 'Password reset successfully.'})
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
