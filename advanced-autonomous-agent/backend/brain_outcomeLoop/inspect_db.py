import os
import asyncio
import aiosqlite

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

# Use the SAME path as orchestrator
DB_PATH = os.path.join(BASE_DIR, "brain4", "brain4_Database.db")

print("=" * 60)
print("DATABASE INSPECTOR")
print("=" * 60)
print(f"Script location: {__file__}")
print(f"Base directory: {BASE_DIR}")
print(f"Database path: {DB_PATH}")
print(f"Database exists: {os.path.exists(DB_PATH)}")
print("=" * 60)

async def inspect():
    if not os.path.exists(DB_PATH):
        print("\n❌ ERROR: Database file not found!")
        print(f"Expected location: {DB_PATH}")
        print("\nSearching for database files...")
        
        # Search for the database
        search_dir = os.path.dirname(BASE_DIR)
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file == "brain4_Database.db":
                    print(f"✅ Found database at: {os.path.join(root, file)}")
        return
    
    print("\n✅ Database file found! Connecting...\n")
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Get table schema
            async with db.execute("PRAGMA table_info(JOBS)") as cursor:
                columns = await cursor.fetchall()
                print("TABLE SCHEMA:")
                print("-" * 60)
                for col in columns:
                    print(f"  {col[1]}: {col[2]}")
                print()
            
            # Get all jobs
            async with db.execute("SELECT * FROM JOBS") as cursor:
                rows = await cursor.fetchall()
                print(f"TOTAL JOBS: {len(rows)}")
                print("-" * 60)
                
                if len(rows) == 0:
                    print("  No jobs found in database.")
                else:
                    for r in rows:
                        print(f"\n📋 Job ID: {r[0]}")
                        print(f"   JOB:     {r[1]}")
                        print(f"   USER_ID: {r[2]}")
                        print(f"   COMPANY  {r[3]}")
                        print(f"   STATUS   {r[4]}")
                        print(f"   APPLIED: {r[5]}")
                        print(f"   OUTCOME: {r[6]}")
                        print(f"   SOURCE:  {r[7]}")
                        print(f"   last_followup_at: {r[14]}")
                        print(f"   followup_count:  {r[15]}")
                        
                        
                    # 1. SCHEMA
            async with db.execute("PRAGMA table_info(AGENT_STATE)") as cursor:
                columns = await cursor.fetchall()
                print("\nAGENT_STATE SCHEMA:")
                print("-" * 60)
                for col in columns:
                    print(f"  {col[1]}: {col[2]}")


            # 2. DATA
            async with db.execute("SELECT * FROM AGENT_STATE") as cursor:
                rows = await cursor.fetchall()
                print(f"\nAGENT_STATE RECORDS: {len(rows)}")
                print("-" * 60)

                if len(rows) == 0:
                    print("  ❌ No agent state found.")
                else:
                    for r in rows:
                        print(f"\n👤 USER ID: {r[0]}")
                        print(f"   LAST METRICS: {r[1]}")
                        print(f"   LAST FINGERPRINT: {r[2]}")
                        print(f"   LAST REFETCH: {r[3]}")
                        print(f"   COOLDOWN UNTIL: {r[4]}")
                        print(f"   UPDATED AT: {r[6]}")
            
            # 3. Users
            async with db.execute("PRAGMA table_info(USERS)") as cursor:
                columns = await cursor.fetchall()
                print("\nUSERS SCHEMA:")
                print("-" * 60)
                for col in columns:
                    print(f"  {col[1]}: {col[2]}")

            async with db.execute("SELECT * FROM USERS") as cursor:
                rows = await cursor.fetchall()
                print(f"\nUSERS RECORDS: {len(rows)}")
                print("-" * 60)

                if len(rows) == 0:
                    print("  ❌ No users found.")
                else:
                    for r in rows:
                        print(f"\n👤 USER ID:    {r[0]}")
                        print(f"   EMAIL:      {r[1]}")
                        print(f"   Name: {r[2]}")
                        print(f"   Password: {r[3]}")
                        print(f"   Created at :{r[4]}")
                        print(f"   Last Active: {r[5]}")


            print("\n" + "=" * 60)
            print("✅ Inspection complete!")
            print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ ERROR accessing database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(inspect())