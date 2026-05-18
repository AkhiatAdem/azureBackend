import uuid

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class Room(models.Model):
    name = models.CharField(max_length=100, unique=True)
    rows = models.PositiveIntegerField(default=5)
    cols = models.PositiveIntegerField(default=5)

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

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Movie(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    age_rating = models.CharField(max_length=10, default='G')
    language = models.CharField(max_length=100)
    genres = models.ManyToManyField(Genre, related_name='movies', blank=True)
    duration_minutes = models.PositiveIntegerField()
    poster_url = models.URLField(max_length=1000, blank=True, null=True)

    def __str__(self):
        return self.title

class Screening(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='screenings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='screenings')
    date = models.DateField()
    start_time = models.PositiveIntegerField() 
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)

    @property
    def end_time(self):
        # We handle cases where movie might not be assigned yet
        if not hasattr(self, 'movie') or not self.movie_id:
            return self.start_time
        return self.start_time + self.movie.duration_minutes

    def clean(self):
        super().clean()
        if not hasattr(self, 'room') or not hasattr(self, 'movie'):
            return

        conflicts = Screening.objects.filter(room=self.room, date=self.date)
        if self.pk:
            conflicts = conflicts.exclude(pk=self.pk)

        new_start = self.start_time
        new_end = self.end_time

        for existing in conflicts:
            existing_start = existing.start_time
            existing_end = existing.end_time

            if (new_start < existing_end) and (new_end > existing_start):
                raise ValidationError({
                    'start_time': f"This screening overlaps with '{existing.movie.title}' scheduled from {existing_start} to {existing_end}."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.movie.title} in {self.room.name} on {self.date}"

class Ticket(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    screening = models.ForeignKey(Screening, on_delete=models.CASCADE, related_name='tickets')
    seats = models.ManyToManyField(Seat, related_name='tickets')
    booked_at = models.DateTimeField(auto_now_add=True)
    price_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Ticket: {self.user.username} - {self.screening.movie.title}"

class VerificationCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_codes')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.code}"

class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_codes')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.code}"

class Profile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        MANAGER = "MANAGER", "Manager"
        SPECTATOR = "SPECTATOR", "Spectator"

    class Membership(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        PREMIUM = "PREMIUM", "Premium"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SPECTATOR)
    membership_type = models.CharField(max_length=20, choices=Membership.choices, default=Membership.NORMAL)
    monthly_credits = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
