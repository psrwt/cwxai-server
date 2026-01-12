import re
import string 

from datetime import datetime


def generate_slug(title):
    # Strip leading and trailing spaces from the title
    title = title.strip()

    # Convert the title to lowercase
    slug = title.lower()

    # Replace multiple spaces with a single hyphen
    slug = re.sub(r'\s+', '-', slug)

    # Remove non-alphanumeric characters (except hyphens)
    slug = re.sub(r'[^a-z0-9-]', '', slug)

    # Remove trailing hyphens, if any
    slug = slug.rstrip('-')

    # Add current time in hours, minutes, and seconds to ensure uniqueness
    current_time = datetime.now().strftime("%H-%M-%S")  # Format: HH-MM-SS
    slug = f"{slug}-{current_time}"

    return slug


# title = "khushi acchi bacchi hai"

# print(generate_slug(title))