# test_system.py

from build_mobile_summary import main
from tracker import record, get_recent
from database import init_db

init_db()

print("Running system test...")

summary = main()
print("Summary:", summary)

record(summary)

history = get_recent(5)
print("Recent history:")
for row in history:
    print(row)

print("System test complete.")
