import string
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Movie, Room, Seat, Screening, Ticket, Genre, Profile

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['role', 'membership_type', 'monthly_credits']

class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    role = serializers.CharField(source='profile.role', read_only=True)
    membership_type = serializers.CharField(source='profile.membership_type', read_only=True)
    monthly_credits = serializers.IntegerField(source='profile.monthly_credits', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'is_staff', 'role', 'membership_type', 'monthly_credits']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.is_active = False # Require email verification
        user.save()
        return user

class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = '__all__'

class MovieSerializer(serializers.ModelSerializer):
    genres = serializers.PrimaryKeyRelatedField(many=True, queryset=Genre.objects.all(), required=False)

    class Meta:
        model = Movie
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['genres_info'] = GenreSerializer(instance.genres.all(), many=True).data
        return representation

class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ['id', 'row_label', 'number', 'seat_type']

class RoomSerializer(serializers.ModelSerializer):
    seats = SeatSerializer(many=True, read_only=True)
    rows_count = serializers.IntegerField(write_only=True, min_value=1, max_value=26)
    seats_per_row = serializers.IntegerField(write_only=True, min_value=1)

    class Meta:
        model = Room
        fields = ['id', 'name', 'seats', 'rows_count', 'seats_per_row', 'rows', 'cols']

    def create(self, validated_data):
        rows = validated_data.pop('rows_count')
        per_row = validated_data.pop('seats_per_row')
        room = Room.objects.create(**validated_data)
        
        seats_to_create = []
        row_labels = list(string.ascii_uppercase) 
        for r_idx in range(rows):
            label = row_labels[r_idx]
            for s_idx in range(1, per_row + 1):
                seats_to_create.append(Seat(room=room, row_label=label, number=s_idx))
        
        Seat.objects.bulk_create(seats_to_create)
        return room

class ScreeningSerializer(serializers.ModelSerializer):
    movie_title = serializers.ReadOnlyField(source='movie.title')
    movie_genre = serializers.SerializerMethodField()
    poster_url = serializers.ReadOnlyField(source='movie.poster_url')
    duration = serializers.ReadOnlyField(source='movie.duration_minutes')
    room_name = serializers.ReadOnlyField(source='room.name')
    end_time = serializers.ReadOnlyField()
    booked_seats = serializers.SerializerMethodField()
    total_seats = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, source='base_price', read_only=True)

    class Meta:
        model = Screening
        fields = [
            'id', 'movie', 'movie_title', 'movie_genre', 'poster_url', 'duration', 
            'room', 'room_name', 'date', 'start_time', 'end_time', 'booked_seats', 'total_seats', 'base_price', 'price'
        ]

    def to_internal_value(self, data):
        if 'base_price' not in data and 'price' in data:
            data = data.copy()
            data['base_price'] = data['price']
        return super().to_internal_value(data)

    def get_booked_seats(self, obj):
        booked_ids = obj.tickets.values_list('seats', flat=True).filter(seats__isnull=False).distinct()
        return list(booked_ids)

    def get_total_seats(self, obj):
        return obj.room.seats.count()

    def get_movie_genre(self, obj):
        if not hasattr(obj, 'movie') or not obj.movie:
            return ""
        return ", ".join(g.name for g in obj.movie.genres.all())

class TicketSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source='user.username')
    movie_title = serializers.ReadOnlyField(source='screening.movie.title')
    room_name = serializers.ReadOnlyField(source='screening.room.name')
    screening_date = serializers.ReadOnlyField(source='screening.date')
    seats = serializers.PrimaryKeyRelatedField(many=True, queryset=Seat.objects.all())
    seat_labels = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = ['id', 'user', 'user_username', 'screening', 'screening_date', 'movie_title', 'room_name', 'seats', 'seat_labels', 'booked_at', 'price_paid']
        read_only_fields = ['user', 'price_paid']

    def get_seat_labels(self, obj):
        return [f"{s.row_label}{s.number}" for s in obj.seats.all()]

    def to_internal_value(self, data):
        if 'seats' in data and isinstance(data['seats'], str):
            clean_str = data['seats'].replace('[', '').replace(']', '').replace('"', '')
            data = data.copy()
            data.setlist('seats', [s.strip() for s in clean_str.split(',') if s.strip()])
        return super().to_internal_value(data)

    def validate(self, data):
        screening = data.get('screening')
        seats = data.get('seats')
        if not seats:
            raise serializers.ValidationError({"seats": "You must select at least one seat."})
        for seat in seats:
            if seat.room != screening.room:
                raise serializers.ValidationError(f"Seat {seat.row_label}{seat.number} is not in this room.")
        if Ticket.objects.filter(screening=screening, seats__in=seats).exists():
            raise serializers.ValidationError("One or more selected seats are already booked.")
        return data

    def create(self, validated_data):
        seats = validated_data.pop('seats')
        ticket = Ticket.objects.create(**validated_data)
        ticket.seats.set(seats)
        return ticket
