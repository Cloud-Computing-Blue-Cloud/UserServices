"""
This file is used to test the connection to the database from the local machine.

Instructions: 
1. In a seperate terminal, run the following command to start the gcloud ssh tunnel:
    gcloud compute ssh mysql-vm --zone=us-central1-c -- -L 3307:localhost:3306 
2. In this terminal, run the following command to test the connection:
    python test_connection.py
"""

from sqlalchemy import create_engine, text

# Your working credentials
DB_USER = "dev_user"
DB_PASS = "password123"
DB_HOST = "127.0.0.1"
DB_PORT = "3307"
DB_NAME = "LookMyShow"

connection_string = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(connection_string)

def get_all_users():
    try:
        with engine.connect() as connection:
            # We select the specific columns we saw in your 'desc users;' output
            query = text("""
                SELECT user_id, first_name, last_name, email, is_deleted 
                FROM users
            """)
            result = connection.execute(query)
            
            # Fetch all rows
            users = result.fetchall()
            
            if not users:
                print("ø No users found in the database.")
                return

            print(f"--- Found {len(users)} User(s) ---")
            print(f"{'ID':<5} | {'Name':<20} | {'Email':<30} | {'Status'}")
            print("-" * 75)
            
            for user in users:
                # user_id is index 0, first_name is index 1, etc.
                full_name = f"{user[1]} {user[2] if user[2] else ''}"
                status = "Active" if not user[4] else "Deleted"
                print(f"{user[0]:<5} | {full_name:<20} | {user[3]:<30} | {status}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    get_all_users()