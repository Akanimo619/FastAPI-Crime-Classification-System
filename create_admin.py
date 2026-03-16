from database import SessionLocal
import models
from auth import get_password_hash

# Create DB session
db = SessionLocal()

username = "admin"
email = "admin@example.com"
password = "admin123"  # change after login

# Check if admin already exists
existing_user = db.query(models.User).filter(models.User.username == username).first()

if existing_user:
    print("Admin already exists.")
else:
    admin_user = models.User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        role="admin"  # 🔥 THIS MAKES THEM ADMIN
    )

    db.add(admin_user)
    db.commit()
    print("Admin created successfully!")

db.close()