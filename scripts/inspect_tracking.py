import sqlite3
import json

def inspect_db():
    try:
        conn = sqlite3.connect('artifacts/job_tracker.db')
        cursor = conn.cursor()
        
        print("--- Table Schema ---")
        cursor.execute("PRAGMA table_info(applications);")
        for row in cursor.fetchall():
            print(row)
            
        print("\n--- All records ---")
        cursor.execute("SELECT job_id, status, resume_docx_path FROM job_applications;")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row[0][:50]}... | Status: {row[1]} | Path: {row[2]}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_db()
