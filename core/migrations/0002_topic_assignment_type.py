# Generated manually for mentor flow: type-filtered topics

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="topic",
            name="assignment_type",
            field=models.CharField(
                choices=[
                    ("react", "React"),
                    ("sql", "SQL"),
                    ("python", "Python"),
                    ("html_css", "HTML/CSS"),
                ],
                default="python",
                max_length=20,
            ),
        ),
    ]
