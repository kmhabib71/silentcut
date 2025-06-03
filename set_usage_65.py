import sqlite3

# Set usage to 65 minutes to test limit enforcement
conn = sqlite3.connect('C:/Users/WALTON/.silence_cutter/usage.db')
cursor = conn.cursor()

cursor.execute('UPDATE usage_sessions SET total_minutes_used = 65 WHERE session_id = "2b61c9e79c106d9a"')
conn.commit()
conn.close()

print("✅ Set usage to 65 minutes (over the 60 minute free limit)")
print("🧪 Now test the Export Processed Media button - it should show usage limit exceeded message") 