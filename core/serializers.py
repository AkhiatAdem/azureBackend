import string
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Movie, Room, Seat, Screening, Ticket

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'is_staff']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = '__all__'

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
        fields = ['id', 'name', 'seats', 'rows_count', 'seats_per_row']

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
    poster_url = serializers.ReadOnlyField(source='movie.poster_url')
    duration = serializers.ReadOnlyField(source='movie.duration_minutes')
    room_name = serializers.ReadOnlyField(source='room.name')
    end_time = serializers.ReadOnlyField()
    booked_seats = serializers.SerializerMethodField()

    class Meta:
        model = Screening
        fields = [
            'id', 'movie', 'movie_title', 'poster_url', 'duration', 
            'room', 'room_name', 'date', 'start_time', 'end_time', 'booked_seats'
        ]

    def get_booked_seats(self, obj):
        booked_ids = obj.tickets.values_list('seats', flat=True).filter(seats__isnull=False).distinct()
        return list(booked_ids)

class TicketSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source='user.username')
    movie_title = serializers.ReadOnlyField(source='screening.movie.title')
    room_name = serializers.ReadOnlyField(source='screening.room.name')
    screening_date = serializers.ReadOnlyField(source='screening.date')
    seats = serializers.PrimaryKeyRelatedField(many=True, queryset=Seat.objects.all())
    seat_labels = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = ['id', 'user', 'user_username', 'screening', 'screening_date', 'movie_title', 'room_name', 'seats', 'seat_labels', 'booked_at']
        read_only_fields = ['user']

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