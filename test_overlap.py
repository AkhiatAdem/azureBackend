import os
import django
from datetime import date
from django.core.exceptions import ValidationError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from core.models import Movie, Room, Screening

def test_overlaps():
    existing_screening = Screening.objects.first()
    movie = existing_screening.movie
    room = existing_screening.room
    today = existing_screening.date
    
    print(f"Testing overlaps for room {room.name} on {today}...")
    # existing_screening is 600 -> 726
    
    # We seeded the DB. IMAX has:
    # 10:00 (600) -> 12:06 (726)
    # 13:00 (780) -> 14:51 (891)
    
    print("Testing overlapping screening...")
    try:
        # Try to schedule a screening at 11:00 (660) which overlaps with 600-726
        s = Screening(movie=movie, room=room, date=today, start_time=660)
        s.save()
        print("FAIL: Overlapping screening was saved!")
    except ValidationError as e:
        print(f"SUCCESS: Validation error raised: {e}")
        
    print("Testing valid screening...")
    try:
        # Try to schedule at 15:00 (900) which is after 891
        s = Screening(movie=movie, room=room, date=today, start_time=900)
        s.save()
        print("SUCCESS: Valid screening was saved!")
    except ValidationError as e:
        print(f"FAIL: Valid screening raised error: {e}")

if __name__ == '__main__':
    test_overlaps()
