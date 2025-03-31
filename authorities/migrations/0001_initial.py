# Generated by Django 5.1.6 on 2025-03-31 07:05

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("complaints", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GovernmentOfficial",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ward_number", models.CharField(max_length=50)),
                ("department", models.CharField(blank=True, max_length=100, null=True)),
                (
                    "contact_number",
                    models.CharField(blank=True, max_length=15, null=True),
                ),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="official_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ComplaintUpdate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("Pending", "Pending"),
                            ("In Progress", "In Progress"),
                            ("Resolved", "Resolved"),
                        ],
                        max_length=20,
                    ),
                ),
                ("update_description", models.TextField(blank=True, null=True)),
                ("proof_image", models.ImageField(upload_to="complaint_updates/")),
                ("updated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "complaint",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="updates",
                        to="complaints.complaint",
                    ),
                ),
                (
                    "official",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="authorities.governmentofficial",
                    ),
                ),
            ],
        ),
    ]
