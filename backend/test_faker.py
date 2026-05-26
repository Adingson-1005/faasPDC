from faker import Faker

# Test that faker was auto-installed
fake = Faker()

print("faker auto-install test!")
print("=" * 35)
print("\nGenerated fake user profiles:\n")

for i in range(5):
    print(f"User {i + 1}:")
    print(f"  Name    : {fake.name()}")
    print(f"  Email   : {fake.email()}")
    print(f"  Address : {fake.address().replace(chr(10), ', ')}")
    print(f"  Job     : {fake.job()}")
    print()

print("faker auto-install test complete!")
