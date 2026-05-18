import string
import random
import traceback
from datetime import date, datetime, timedelta
from django.utils import timezone

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import connection

from core.models import Genre, Movie, Room, Screening, Seat, Ticket, Profile, VerificationCode, PasswordResetCode


class Command(BaseCommand):
    help = "Flush all cinema data and re-seed with a fresh, rich dataset."

    def _clear(self):
        """Delete all application data in dependency-safe order."""
        self.stdout.write("  Clearing old data…")
        
        with connection.cursor() as cursor:
            try:
                cursor.execute("DELETE FROM core_subscription")
            except:
                pass
        
        Ticket.objects.all().delete()
        VerificationCode.objects.all().delete()
        PasswordResetCode.objects.all().delete()
        Profile.objects.all().delete()
        Screening.objects.all().delete()
        Movie.objects.all().delete()
        Genre.objects.all().delete()
        Seat.objects.all().delete()
        Room.objects.all().delete()
        
        User.objects.all().delete()
        self.stdout.write(self.style.WARNING("  ✓ Old data cleared."))

    def _make_room(self, name, rows, cols):
        """Create a room and populate it with seats."""
        room = Room.objects.create(name=name, rows=rows, cols=cols)
        row_labels = list(string.ascii_uppercase)[:rows]
        seats = []
        for r_idx, label in enumerate(row_labels):
            seat_type = (
                Seat.SeatType.VIP if r_idx < 2
                else Seat.SeatType.ACCESSIBLE if r_idx == rows - 1
                else Seat.SeatType.REGULAR
            )
            for num in range(1, cols + 1):
                seats.append(
                    Seat(room=room, row_label=label, number=num, seat_type=seat_type)
                )
        Seat.objects.bulk_create(seats)
        return room

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Cinema Seed DB ===\n"))

        self._clear()

        # 1. Users
        self.stdout.write("  Creating users…")
        admin_user = User.objects.create_superuser(username="admin", email="admin@cinema.com", password="admin123")
        admin_user.profile.role = Profile.Role.ADMIN
        admin_user.profile.save()

        manager_user = User.objects.create_user(username="manager", password="manager123", is_staff=True, is_active=True)
        manager_user.profile.role = Profile.Role.MANAGER
        manager_user.profile.save()

        spectators = []
        for i in range(1, 11):
            u = User.objects.create_user(username=f"user{i}", password="password123", is_active=True)
            u.profile.role = Profile.Role.SPECTATOR
            u.profile.save()
            spectators.append(u)

        # 2. Genres
        genres = {n: Genre.objects.create(name=n) for n in ["Action", "Sci-Fi", "Drama", "Animation"]}

        # 3. Rooms
        rooms = [self._make_room("Hall A", 8, 10), self._make_room("Hall B", 6, 8)]

        # 4. Movies
        movies = []
        # CHANGED: Added unique placeholder poster URLs for each movie entry
        movie_data = [
            (
                "Dune: Part Two", 
                "Epic sci-fi journey across a desolate desert planet.", 
                166, 
                "PG-13", 
                "https://images.unsplash.com/photo-1547483238-f400e65ccd56?q=80&w=600&auto=format&fit=crop"
            ),
            (
                "Oppenheimer", 
                "The sweeping story of the atomic bomb development.", 
                180, 
                "R", 
                "https://images.unsplash.com/photo-1461360370896-922624d12aa1?q=80&w=600&auto=format&fit=crop"
            ),
            (
                "Spirited Away", 
                "Mystical Japanese animated fantasy masterpiece.", 
                125, 
                "PG", 
                "https://images.unsplash.com/photo-1578632767115-351597cf2477?q=80&w=600&auto=format&fit=crop"
            ),
            (
                "The Dark Knight", 
                "The caped crusader battles chaos introduced by the Joker.", 
                152, 
                "PG-13", 
                "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?q=80&w=600&auto=format&fit=crop"
            )
        ]
        
        # CHANGED: Unpacked the image poster parameter from the dataset and injected it into the creation instance
        for title, desc, dur, rating, poster in movie_data:
            m = Movie.objects.create(
                title=title, 
                description=desc, 
                duration_minutes=dur, 
                age_rating=rating, 
                language="English",
                poster_url=poster
            )
            m.genres.set([random.choice(list(genres.values()))])
            movies.append(m)

        # 5. Screenings & Tickets
        today = date.today()
        ticket_count = 0
        screening_count = 0
        
        for d in range(-15, 7): # 15 days back, 7 forward
            current_date = today + timedelta(days=d)
            for room in rooms:
                for hour in [13, 17, 21]:
                    try:
                        s = Screening.objects.create(
                            movie=random.choice(movies),
                            room=room,
                            date=current_date,
                            start_time=hour * 60,
                            base_price=random.choice([50.00, 75.00, 100.00])
                        )
                        screening_count += 1
                        
                        if d <= 0:
                            seats = list(room.seats.all())
                            booked_count = random.randint(10, min(25, len(seats)))
                            booked_seats = random.sample(seats, booked_count)
                            
                            i = 0
                            while i < len(booked_seats):
                                group_size = random.randint(1, 3)
                                group = booked_seats[i : i + group_size]
                                
                                user = random.choice(spectators)
                                t = Ticket.objects.create(
                                    user=user, 
                                    screening=s, 
                                    price_paid=s.base_price * len(group)
                                )
                                t.seats.set(group)
                                
                                hist_time = timezone.make_aware(datetime.combine(current_date, datetime.min.time()) + timedelta(hours=hour-2))
                                Ticket.objects.filter(pk=t.pk).update(booked_at=hist_time)
                                
                                ticket_count += 1
                                i += group_size
                    except Exception as e:
                        if "overlap" not in str(e).lower():
                            self.stdout.write(self.style.ERROR(f"Error on date {current_date}: {e}"))
                        continue

        self.stdout.write(self.style.SUCCESS(f"\n✅ Seed complete: {screening_count} Screenings, {ticket_count} Tickets"))