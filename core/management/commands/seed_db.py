import string
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Movie, Room, Seat, Screening
from datetime import date

class Command(BaseCommand):
    help = 'Seeds the database with movies, rooms, and screenings'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding data...')

        # 1. Create an Admin & Test User
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            self.stdout.write('Admin created (admin/admin123)')

        # 2. Create Rooms
        room_imax, _ = Room.objects.get_or_create(name="IMAX Theatre")
        room_standard, _ = Room.objects.get_or_create(name="Standard Room 1")

        # 3. Create Seats (if they don't exist)
        for room in [room_imax, room_standard]:
            if not room.seats.exists():
                seats = []
                # Creating a small 5x5 grid for demo
                for row in list(string.ascii_uppercase)[:5]: 
                    for num in range(1, 6):
                        seat_type = Seat.SeatType.VIP if row == 'A' else Seat.SeatType.REGULAR
                        seats.append(Seat(room=room, row_label=row, number=num, seat_type=seat_type))
                Seat.objects.bulk_create(seats)
                self.stdout.write(f'Created 25 seats for {room.name}')

        # 4. Create Movies
        movies_data = [
            {
                "title": "Good Will Hunting",
                "description": "Will Hunting, a janitor at MIT, has a gift for mathematics which is discovered by a professor.",
                "duration_minutes": 126,
                "language": "English",
                "age_rating": "R",
                "poster_url": "https://www.avoir-alire.com/IMG/logo/arton21118.jpg"
            },
            {
                "title": "Kill Bill: Vol. 1",
                "description": "The Bride wakens from a four-year coma and seeks revenge on the assassins who betrayed her.",
                "duration_minutes": 111,
                "language": "English/Japanese",
                "age_rating": "R",
                "poster_url": "https://static.posters.cz/image/1300/97652.jpg"
            },
            {
                "title": "How To Train Your Dragon",
                "description": "A hapless young Viking who aspires to hunt dragons becomes the unlikely friend of a young dragon.",
                "duration_minutes": 98,
                "language": "English",
                "age_rating": "PG",
                "poster_url": "https://www.yourdecoration.fr/cdn/shop/files/Poster-How-To-Train-Your-Dragon-Live-Action-61x91-5cm-Grupo-Erik-GPE6002.jpg?v=1758096941"
            }
        ]

        movies = []
        for m in movies_data:
            movie, _ = Movie.objects.get_or_create(title=m['title'], defaults=m)
            movies.append(movie)

        # 5. Create Screenings (Today)
        today = date.today()
        
        # Clearing old screenings to keep it fresh
        Screening.objects.all().delete()

        # Screening 1: Good Will Hunting today at 14:00 (840 mins)
        Screening.objects.create(movie=movies[0], room=room_imax, date=today, start_time=840)
        
        # Screening 2: Kill Bill today at 20:00 (1200 mins)
        Screening.objects.create(movie=movies[1], room=room_standard, date=today, start_time=1200)

        # Screening 3: HTTYD today at 10:00 (600 mins)
        Screening.objects.create(movie=movies[2], room=room_standard, date=today, start_time=600)

        self.stdout.write(self.style.SUCCESS('Database seeded successfully!'))