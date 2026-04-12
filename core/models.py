from django.db import models
from django.contrib.auth.models import User

class Room(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Seat(models.Model):
    class SeatType(models.TextChoices):
        REGULAR = 'REGULAR', 'Regular'
        VIP = 'VIP', 'VIP'
        ACCESSIBLE = 'ACCESSIBLE', 'Accessible'

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='seats')
    row_label = models.CharField(max_length=5)
    number = models.PositiveIntegerField()
    seat_type = models.CharField(max_length=20, choices=SeatType.choices, default=SeatType.REGULAR)

    class Meta:
        unique_together = ('room', 'row_label', 'number')
        ordering = ['row_label', 'number']

    def __str__(self):
        return f"{self.room.name} - {self.row_label}{self.number}"

class Movie(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    age_rating = models.CharField(max_length=10, default='G')
    language = models.CharField(max_length=100)
    duration_minutes = models.PositiveIntegerField()
    poster_url = models.URLField(max_length=1000, blank=True, null=True)

    def __str__(self):
        return self.title

class Screening(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='screenings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='screenings')
    date = models.DateField()
    start_time = models.PositiveIntegerField() 

    @property
    def end_time(self):
        return self.start_time + self.movie.duration_minutes

    def __str__(self):
        return f"{self.movie.title} in {self.room.name} on {self.date}"

class Ticket(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    screening = models.ForeignKey(Screening, on_delete=models.CASCADE, related_name='tickets')
    seats = models.ManyToManyField(Seat, related_name='tickets') 
    booked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket: {self.user.username} - {self.screening.movie.title}"